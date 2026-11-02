"""PDF Text Extractor — the window.

Choose an input folder of PDFs and an output folder; Extract reads every PDF into its own subfolder (pipeline.py), checking
every page with three text engines and local OCR. The papers are listed with their confidence; a paper opens with its pages on
the left and, in a side panel that can be dragged wider or narrower, the page's verified text, the sections, the full text, the
figures and tables, and the checks of every page.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from PySide6.QtCore import QObject, QSettings, QSize, Qt, QThread, QUrl, Signal
from PySide6.QtGui import QColor, QDesktopServices, QFont, QIcon, QImage, QKeySequence, QPixmap, QShortcut
from PySide6.QtWidgets import (QApplication, QCheckBox, QFileDialog, QGridLayout, QGroupBox, QHBoxLayout, QHeaderView, QLabel,
                               QLineEdit, QListWidget, QListWidgetItem, QMainWindow, QMessageBox, QPlainTextEdit, QProgressBar,
                               QPushButton, QScrollArea, QSpinBox, QSplitter, QTableWidget, QTableWidgetItem, QTabWidget,
                               QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget)

from . import __version__
from . import parallel as PAR
from . import pipeline as P

GOOD, FAIR = 0.98, 0.95


def colour(c: float) -> QColor:
    return QColor("#1a7f37") if c >= GOOD else QColor("#b26a00") if c >= FAIR else QColor("#b42318")


class KeepAwake:
    """While papers are extracted: on a Mac an activity that keeps App Nap and idle sleep away from the app, on Windows the system
    kept awake; the screen may still sleep."""

    def __enter__(self):
        self.token = None
        try:
            if sys.platform == "darwin":
                import Foundation
                self.token = Foundation.NSProcessInfo.processInfo().beginActivityWithOptions_reason_(
                    Foundation.NSActivityUserInitiatedAllowingIdleSystemSleep | Foundation.NSActivityIdleSystemSleepDisabled,
                    "Extracting the text of PDF papers")
            elif sys.platform == "win32":
                import ctypes
                ctypes.windll.kernel32.SetThreadExecutionState(0x80000000 | 0x00000001)     # ES_CONTINUOUS | ES_SYSTEM_REQUIRED
        except Exception:  # noqa: BLE001 - staying awake is a convenience, never a reason to stop
            pass
        return self

    def __exit__(self, *exc):
        try:
            if sys.platform == "darwin" and self.token is not None:
                import Foundation
                Foundation.NSProcessInfo.processInfo().endActivity_(self.token)
            elif sys.platform == "win32":
                import ctypes
                ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)
        except Exception:  # noqa: BLE001
            pass
        return False


class Worker(QObject):
    progress = Signal(str, int, int, str)
    paper_done = Signal(dict)
    failed = Signal(str, str)
    finished = Signal()

    def __init__(self, pdfs: list[Path], out: Path, use_ocr: bool, skip_done: bool = False, workers: int = 1):
        super().__init__()
        self.pdfs, self.out, self.use_ocr, self.skip_done, self.workers, self._stop = pdfs, out, use_ocr, skip_done, workers, False

    def stop(self):
        self._stop = True

    def run(self):
        with KeepAwake():
            todo = []
            for pdf in self.pdfs:
                done = P.finished_folder(pdf, self.out) if self.skip_done else None
                if done is not None:                       # already extracted, the same file: kept as it is
                    self.paper_done.emit(P.summary_of(done) | {"skipped": True})
                else:
                    todo.append(pdf)

            def on_event(kind, name, payload):
                if kind == "progress":
                    self.progress.emit(name, *payload)
                elif kind == "done":
                    self.paper_done.emit(payload)
                elif kind == "failed":
                    self.failed.emit(name, payload)
            if todo and not self._stop:
                try:
                    PAR.run(todo, self.out, self.use_ocr, self.workers, on_event, lambda: self._stop)
                except Exception as exc:  # noqa: BLE001 - the run itself could not go on
                    self.failed.emit("the run", f"{type(exc).__name__}: {exc}")
            P.write_index(self.out)
        self.finished.emit()


class Window(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"PDF Text Extractor {__version__}")
        self.settings = QSettings("PDFTextExtractor", "app")
        self.paper: Path | None = None
        self.report: dict = {}
        self.doc = None
        self.page = 0
        self.zoom = 1.0
        self.thread: QThread | None = None
        self.worker: Worker | None = None
        self.total, self.done_count = 0, 0
        self.build()
        self.inp.setText(self.settings.value("input", ""))
        self.out.setText(self.settings.value("output", ""))
        if self.out.text():
            self.load_papers()
        geo = self.settings.value("geometry")
        if geo is not None:
            self.restoreGeometry(geo)
        else:
            self.resize(1500, 920)

    # ------------------------------------------------------------------------------------------------------- layout
    def build(self):
        central = QWidget()
        v = QVBoxLayout(central)
        box = QGroupBox("Folders")
        g = QGridLayout(box)
        self.inp, self.out = QLineEdit(), QLineEdit()
        self.inp.setPlaceholderText("the folder that holds the PDFs")
        self.out.setPlaceholderText("where each paper gets its own folder")
        for row, (label, edit) in enumerate((("Input folder", self.inp), ("Output folder", self.out))):
            g.addWidget(QLabel(label), row, 0)
            g.addWidget(edit, row, 1)
            b = QPushButton("Browse…")
            b.clicked.connect(lambda _=False, e=edit: self.browse(e))
            g.addWidget(b, row, 2)
        self.use_ocr = QCheckBox("Check every page with local OCR (slower; finds missing or hidden text, reads scanned pages)")
        self.use_ocr.setChecked(True)
        self.skip_done = QCheckBox("Skip papers already extracted into the output folder (the same file)")
        self.skip_done.setChecked(False)
        cores, ram = PAR.machine()
        self.workers = QSpinBox()
        self.workers.setRange(1, max(1, cores))
        self.workers.setValue(PAR.default_workers())
        self.workers.setToolTip(f"This computer: {cores} cores, {ram:.0f} GB of memory; chosen for it: {PAR.default_workers()}")
        at_once = QHBoxLayout()
        at_once.addWidget(QLabel("Papers at once:"))
        at_once.addWidget(self.workers)
        at_once.addWidget(QLabel(f"(this computer: {cores} cores, {ram:.0f} GB — {PAR.default_workers()} chosen for it)"))
        at_once.addStretch(1)
        opts = QVBoxLayout()
        opts.addWidget(self.use_ocr)
        opts.addWidget(self.skip_done)
        opts.addLayout(at_once)
        g.addLayout(opts, 2, 1)
        self.start, self.stopb, self.open_out = QPushButton("Extract"), QPushButton("Stop"), QPushButton("Show results")
        self.open_dir = QPushButton("Open folder")
        self.open_dir.setToolTip("Open the selected paper's folder (or the output folder) in Finder or Explorer")
        self.start.clicked.connect(self.run)
        self.stopb.clicked.connect(self.stop)
        self.stopb.setEnabled(False)
        self.open_out.clicked.connect(self.load_papers)
        self.open_dir.clicked.connect(self.reveal)
        bh = QHBoxLayout()
        for b in (self.start, self.stopb, self.open_out, self.open_dir):
            bh.addWidget(b)
        bh.addStretch(1)
        g.addLayout(bh, 3, 1)
        v.addWidget(box)

        split = QSplitter(Qt.Orientation.Horizontal)
        self.papers = QListWidget()
        self.papers.currentItemChanged.connect(lambda cur, _prev: self.open_paper(cur))
        split.addWidget(self.papers)

        viewer = QWidget()
        vv = QVBoxLayout(viewer)
        nav = QHBoxLayout()
        self.prev_b, self.next_b = QPushButton("◀"), QPushButton("▶")
        self.page_spin = QSpinBox()
        self.page_spin.setMinimum(1)
        self.page_spin.valueChanged.connect(lambda n: self.show_page(n - 1))
        self.prev_b.clicked.connect(lambda: self.page_spin.setValue(self.page_spin.value() - 1))
        self.next_b.clicked.connect(lambda: self.page_spin.setValue(self.page_spin.value() + 1))
        zin, zout = QPushButton("+"), QPushButton("−")
        zin.clicked.connect(lambda: self.set_zoom(self.zoom * 1.2))
        zout.clicked.connect(lambda: self.set_zoom(self.zoom / 1.2))
        self.page_info = QLabel("")
        for w in (self.prev_b, self.page_spin, self.next_b, zout, zin, self.page_info):
            nav.addWidget(w)
        nav.addStretch(1)
        vv.addLayout(nav)
        self.image = QLabel(alignment=Qt.AlignmentFlag.AlignCenter)
        scroll = QScrollArea()
        scroll.setWidget(self.image)
        scroll.setWidgetResizable(True)
        vv.addWidget(scroll, 1)
        split.addWidget(viewer)

        self.tabs = QTabWidget()
        mono = QFont("Menlo" if sys.platform == "darwin" else "Consolas")
        self.page_text, self.full_text = QPlainTextEdit(readOnly=True), QPlainTextEdit(readOnly=True)
        for t in (self.page_text, self.full_text):
            t.setFont(mono)
        self.tabs.addTab(self.page_text, "Page text")
        sec = QSplitter(Qt.Orientation.Vertical)
        self.sec_tree = QTreeWidget()
        self.sec_tree.setHeaderLabels(["Section", "Pages"])
        self.sec_tree.currentItemChanged.connect(lambda cur, _prev: self.show_section(cur))
        self.sec_text = QPlainTextEdit(readOnly=True)
        self.sec_text.setFont(mono)
        sec.addWidget(self.sec_tree)
        sec.addWidget(self.sec_text)
        self.tabs.addTab(sec, "Sections")
        self.tabs.addTab(self.full_text, "Full text")
        self.figs = QListWidget()
        self.figs.setViewMode(QListWidget.ViewMode.IconMode)
        self.figs.setIconSize(QSize(220, 160))
        self.figs.setResizeMode(QListWidget.ResizeMode.Adjust)
        self.figs.itemDoubleClicked.connect(lambda it: self.goto(it.data(Qt.ItemDataRole.UserRole)))
        self.tabs.addTab(self.figs, "Figures && tables")
        self.checks = QTableWidget(0, 4)
        self.checks.setHorizontalHeaderLabels(["Page", "Confidence", "Read from", "Checks"])
        self.checks.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.checks.cellDoubleClicked.connect(lambda r, _c: self.goto(int(self.checks.item(r, 0).text())))
        self.tabs.addTab(self.checks, "Checks")
        split.addWidget(self.tabs)
        split.setSizes([260, 700, 540])
        split.setChildrenCollapsible(False)
        v.addWidget(split, 1)

        bottom = QHBoxLayout()
        self.bar = QProgressBar()
        self.status = QLabel("Choose the folders and press Extract.")
        bottom.addWidget(self.bar, 1)
        bottom.addWidget(self.status, 2)
        v.addLayout(bottom)
        self.log = QPlainTextEdit(readOnly=True)
        self.log.setMaximumHeight(90)
        v.addWidget(self.log)
        self.setCentralWidget(central)
        QShortcut(QKeySequence(Qt.Key.Key_Right), self, activated=lambda: self.page_spin.setValue(self.page_spin.value() + 1))
        QShortcut(QKeySequence(Qt.Key.Key_Left), self, activated=lambda: self.page_spin.setValue(self.page_spin.value() - 1))

    # ------------------------------------------------------------------------------------------------------- actions
    def browse(self, edit: QLineEdit):
        d = QFileDialog.getExistingDirectory(self, "Choose a folder", edit.text() or str(Path.home()))
        if d:
            edit.setText(d)

    def run(self):
        inp, out = Path(self.inp.text().strip()), Path(self.out.text().strip())
        if not inp.is_dir():
            QMessageBox.warning(self, "PDF Text Extractor", "Choose an input folder that holds PDFs.")
            return
        if not self.out.text().strip():
            QMessageBox.warning(self, "PDF Text Extractor", "Choose an output folder.")
            return
        out.mkdir(parents=True, exist_ok=True)
        pdfs = P.pdfs_in(inp)
        if not pdfs:
            QMessageBox.information(self, "PDF Text Extractor", "The input folder holds no PDF.")
            return
        self.settings.setValue("input", str(inp))
        self.settings.setValue("output", str(out))
        self.start.setEnabled(False)
        self.stopb.setEnabled(True)
        self.total, self.done_count = len(pdfs), 0
        self.bar.setMaximum(self.total)
        self.bar.setValue(0)
        self.log.appendPlainText(f"Extracting {len(pdfs)} PDF(s) into {out}, {self.workers.value()} at once")
        self.thread, self.worker = QThread(), Worker(pdfs, out, self.use_ocr.isChecked(), self.skip_done.isChecked(),
                                                     self.workers.value())
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.progress.connect(self.on_progress)
        self.worker.paper_done.connect(self.on_done)
        self.worker.failed.connect(self.on_failed)
        self.worker.finished.connect(self.on_finished)
        self.thread.start()

    def reveal(self):
        target = self.paper if self.paper and self.paper.is_dir() else Path(self.out.text().strip())
        if target.is_dir():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(target)))

    def stop(self):
        if self.worker:
            self.worker.stop()
            self.status.setText("Stopping after the current page…")

    def on_progress(self, name: str, done: int, total: int, msg: str):
        self.status.setText(f"{self.done_count} of {self.total} papers done · {self.workers.value()} at once · {name}: {msg}")

    def count_one(self):
        self.done_count += 1
        self.bar.setValue(self.done_count)

    def on_failed(self, name: str, err: str):
        self.count_one()
        self.log.appendPlainText(f"{name}: could not be extracted — {err}")

    def on_done(self, s: dict):
        look = f"; pages to look at: {', '.join(map(str, s['pages_needing_a_look']))}" if s["pages_needing_a_look"] else ""
        kept = " (already extracted: kept)" if s.get("skipped") else ""
        self.count_one()
        self.log.appendPlainText(f"{s['paper']}{kept}: {s['pages']} pages, confidence {s['confidence']:.1%}, {s['sections']} sections, "
                                 f"{s['figures']} figures, {s['tables']} tables{look}")
        self.load_papers(select=s["paper"])

    def on_finished(self):
        self.start.setEnabled(True)
        self.stopb.setEnabled(False)
        self.status.setText("Done.")
        if self.thread:
            self.thread.quit()
            self.thread.wait()
        self.load_papers()

    def load_papers(self, select: str | None = None):
        out = Path(self.out.text().strip())
        current = select or (self.paper.name if self.paper else None)
        self.papers.blockSignals(True)
        self.papers.clear()
        for rep in sorted(out.glob("*/report.json")) if out.is_dir() else []:
            try:
                r = json.loads(rep.read_text(encoding="utf-8"))
            except Exception:  # noqa: BLE001
                continue
            it = QListWidgetItem(f"{r['confidence']:.1%}  {rep.parent.name}")
            it.setStatusTip(r.get("file", ""))
            it.setForeground(colour(r["confidence"]))
            it.setData(Qt.ItemDataRole.UserRole, str(rep.parent))
            it.setToolTip(f"{r['pages']} pages · {r['sections']['count']} sections · pages to look at: "
                          f"{', '.join(map(str, r['pages_needing_a_look'])) or 'none'}")
            self.papers.addItem(it)
            if rep.parent.name == current:
                self.papers.setCurrentItem(it)
        self.papers.blockSignals(False)
        if self.papers.currentItem():
            self.open_paper(self.papers.currentItem())

    def open_paper(self, item):
        if item is None:
            return
        import pymupdf
        self.paper = Path(item.data(Qt.ItemDataRole.UserRole))
        self.report = json.loads((self.paper / "report.json").read_text(encoding="utf-8"))
        pdfs = sorted(self.paper.glob("*.pdf"))
        self.doc = pymupdf.open(stream=pdfs[0].read_bytes(), filetype="pdf") if pdfs else None
        self.full_text.setPlainText((self.paper / "full_text.txt").read_text(encoding="utf-8"))
        self.fill_sections()
        self.fill_figures()
        self.fill_checks()
        self.page_spin.setMaximum(max(1, self.report["pages"]))
        self.page_spin.setValue(1)
        self.show_page(0)

    def fill_sections(self):
        self.sec_tree.clear()
        self.sections = json.loads((self.paper / "sections.json").read_text(encoding="utf-8"))["sections"]
        stack: list[tuple[int, QTreeWidgetItem]] = []
        for i, s in enumerate(self.sections):
            title = s["title"] if s["level"] == 0 else f"{(s['number'] + ' ') if s['number'] else ''}{s['title']}"
            pages = f"{s['pages'][0]}–{s['pages'][1]}" if s["pages"] and s["pages"][0] != s["pages"][1] else (str(s["pages"][0]) if s["pages"] else "")
            it = QTreeWidgetItem([title, pages])
            it.setData(0, Qt.ItemDataRole.UserRole, i)
            while stack and stack[-1][0] >= s["level"] and s["level"] > 0:
                stack.pop()
            (stack[-1][1].addChild(it) if stack and s["level"] > stack[-1][0] else self.sec_tree.addTopLevelItem(it))
            stack.append((s["level"], it))
        self.sec_tree.expandAll()
        self.sec_tree.resizeColumnToContents(0)

    def show_section(self, item):
        if item is None:
            return
        s = self.sections[item.data(0, Qt.ItemDataRole.UserRole)]
        self.sec_text.setPlainText("\n".join(f"[page {c['page']}]\n{c['text'].strip()}\n" for c in s["chunks"]))
        if s["pages"]:
            self.goto(s["pages"][0], switch=False)

    def fill_figures(self):
        self.figs.clear()
        for x in self.report.get("figures", []) + self.report.get("tables", []):
            pix = QPixmap(str(self.paper / x["file"]))
            it = QListWidgetItem(QIcon(pix), f"{x['kind']} · page {x['page']}" + (f"\n{x['caption'][:60]}" if x.get("caption") else ""))
            it.setData(Qt.ItemDataRole.UserRole, x["page"])
            it.setToolTip(x.get("caption") or x["file"])
            self.figs.addItem(it)

    def fill_checks(self):
        rows = self.report["page_results"]
        self.checks.setRowCount(len(rows))
        for i, r in enumerate(rows):
            items = [QTableWidgetItem(str(r["page"])), QTableWidgetItem(f"{r['confidence']:.1%}"), QTableWidgetItem(r["source"]),
                     QTableWidgetItem("; ".join(r["notes"]) or "all checks agree")]
            items[1].setForeground(colour(r["confidence"]))
            for j, it in enumerate(items):
                it.setFlags(it.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.checks.setItem(i, j, it)
        self.checks.resizeColumnsToContents()

    def goto(self, page: int, switch: bool = True):
        self.page_spin.setValue(page)
        if switch:
            self.tabs.setCurrentIndex(0)

    def set_zoom(self, z: float):
        self.zoom = max(0.3, min(4.0, z))
        self.show_page(self.page)

    def show_page(self, i: int):
        if not self.paper or not self.report:
            return
        self.page = max(0, min(i, self.report["pages"] - 1))
        r = self.report["page_results"][self.page]
        self.page_info.setText(f"page {self.page + 1} of {self.report['pages']} · confidence {r['confidence']:.1%} · read from {r['source']}")
        self.page_info.setStyleSheet(f"color: {colour(r['confidence']).name()};")
        text = (self.paper / "pages" / f"page_{self.page + 1:04d}.txt").read_text(encoding="utf-8")
        notes = "\n".join(f"• {n}" for n in r["notes"]) or "• all checks agree"
        self.page_text.setPlainText(f"[page {self.page + 1} — confidence {r['confidence']:.1%} — read from {r['source']}]\n{notes}\n\n{text}")
        if self.doc is not None:
            page = self.doc[self.page]
            ratio = self.devicePixelRatioF()
            pix = page.get_pixmap(dpi=int(96 * self.zoom * ratio))
            img = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format.Format_RGB888)
            shown = QPixmap.fromImage(img.copy())
            shown.setDevicePixelRatio(ratio)
            self.image.setPixmap(shown)

    def closeEvent(self, e):
        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("input", self.inp.text())
        self.settings.setValue("output", self.out.text())
        if self.thread and self.thread.isRunning():
            self.worker.stop()
            self.thread.quit()
            if not self.thread.wait(120_000):
                os._exit(0)
        super().closeEvent(e)


def main() -> int:
    """python -m pdftextextractor [--input DIR] [--output DIR] [--workers N] [--skip-done] [--start]: the folders filled in, the
    papers at once and the skipping of papers already extracted set, and with --start the extraction begun at once."""
    args = sys.argv[1:]
    opt = lambda name: args[args.index(name) + 1] if name in args and args.index(name) + 1 < len(args) else None
    if sys.stderr is None or sys.stdout is None or not sys.stderr.isatty():
        try:
            log = open(Path(__file__).resolve().parents[1] / "app.log", "a", encoding="utf-8", buffering=1)
            sys.stdout = sys.stdout if sys.stdout is not None and sys.stdout.isatty() else log
            sys.stderr = log
        except OSError:
            pass
    app = QApplication(sys.argv[:1])
    app.setApplicationName("PDF Text Extractor")
    w = Window()
    if opt("--input"):
        w.inp.setText(opt("--input"))
    if opt("--output"):
        w.out.setText(opt("--output"))
        w.load_papers()
    if opt("--workers"):
        w.workers.setValue(int(opt("--workers")))
    if "--skip-done" in args:
        w.skip_done.setChecked(True)
    w.show()
    if "--start" in args:
        from PySide6.QtCore import QTimer
        QTimer.singleShot(800, w.run)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
