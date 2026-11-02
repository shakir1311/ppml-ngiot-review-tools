"""Several papers at once, each in a Python process of its own — as many as the computer can carry.

The number of papers at once is chosen from the computer: two thirds of its processor cores (a paper keeps about one and a half
cores busy; measured on an 18-core Mac, 8 papers used 13 to 14 cores), no more than its memory allows at about 1.5 GB a paper
with 2 GB left for the system, and at most 16. Each process
gives the OCR engines its share of the cores: Tesseract one thread, RapidOCR (ONNX Runtime) cores ÷ papers at once.
"""
from __future__ import annotations

import multiprocessing as mp
import os
import subprocess
import sys
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
from pathlib import Path

PER_PAPER_GB, KEEP_GB, MOST = 1.5, 2.0, 16


def memory_gb() -> float:
    """The computer's memory in GB (4 when it cannot be read)."""
    try:
        if sys.platform == "darwin":
            return int(subprocess.run(["sysctl", "-n", "hw.memsize"], capture_output=True, text=True).stdout) / 2 ** 30
        if sys.platform == "win32":
            import ctypes

            class Status(ctypes.Structure):
                _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong), ("ullTotalPhys", ctypes.c_ulonglong),
                            ("ullAvailPhys", ctypes.c_ulonglong), ("ullTotalPageFile", ctypes.c_ulonglong),
                            ("ullAvailPageFile", ctypes.c_ulonglong), ("ullTotalVirtual", ctypes.c_ulonglong),
                            ("ullAvailVirtual", ctypes.c_ulonglong), ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
            st = Status()
            st.dwLength = ctypes.sizeof(Status)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(st))
            return st.ullTotalPhys / 2 ** 30
        return os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / 2 ** 30
    except Exception:  # noqa: BLE001
        return 4.0


def machine() -> tuple[int, float]:
    return os.cpu_count() or 1, memory_gb()


def default_workers() -> int:
    cores, ram = machine()
    return max(1, min(cores * 2 // 3, int((ram - KEEP_GB) // PER_PAPER_GB), MOST))


def _init(threads: int) -> None:
    os.environ["OMP_THREAD_LIMIT"] = "1"                       # Tesseract: one thread in each process
    from . import ocr
    ocr.RAPID_THREADS = threads                                # RapidOCR: its share of the cores


def _one(pdf: Path, out: Path, use_ocr: bool, queue, stop):
    from . import pipeline as P
    try:
        return "done", pdf.name, P.process_pdf(pdf, out, use_ocr, lambda d, t, m: queue.put((pdf.name, d, t, m)), stop.is_set)
    except InterruptedError:
        return "stopped", pdf.name, None
    except Exception as exc:  # noqa: BLE001 - one paper must not stop the others
        return "failed", pdf.name, f"{type(exc).__name__}: {exc}"


def run(pdfs: list[Path], out: Path, use_ocr: bool, workers: int, on_event, should_stop) -> None:
    """Extract the PDFs, `workers` at once. on_event(kind, name, payload) is called in this process with ("progress", name,
    (done, total, message)), ("done", name, summary), ("failed", name, error) or ("stopped", name, None); should_stop() ends the
    run after the pages being read."""
    ctx = mp.get_context("spawn")                              # the same on macOS and Windows
    workers = max(1, min(workers, len(pdfs)))
    threads = max(1, (os.cpu_count() or 1) // workers)
    with ctx.Manager() as manager:
        queue, stop = manager.Queue(), manager.Event()
        with ProcessPoolExecutor(max_workers=workers, mp_context=ctx, initializer=_init, initargs=(threads,)) as pool:
            futures = [pool.submit(_one, pdf, out, use_ocr, queue, stop) for pdf in pdfs]
            names = {f: pdf.name for f, pdf in zip(futures, pdfs)}
            pending = set(futures)
            while pending:
                done, pending = wait(pending, timeout=0.3, return_when=FIRST_COMPLETED)
                while not queue.empty():
                    name, d, t, m = queue.get_nowait()
                    on_event("progress", name, (d, t, m))
                for f in done:
                    if f.cancelled():
                        continue
                    try:
                        kind, name, payload = f.result()
                    except Exception as exc:  # noqa: BLE001 - a process that died
                        kind, name, payload = "failed", names.get(f, "?"), f"{type(exc).__name__}: {exc}"
                    on_event(kind, name, payload)
                if should_stop() and not stop.is_set():
                    stop.set()
                    for f in pending:
                        f.cancel()
