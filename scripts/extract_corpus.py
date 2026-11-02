#!/usr/bin/env python3
"""Run extract_paper.py on every paper in the manifest, or on the papers named, several at a time.

Each paper runs in a process of its own, so a paper that fails cannot stop the others. A paper whose process fails
or is killed (for instance by a crash while it exits) is run once more; whatever still fails is listed at the end.
The batch never stops early.

    extract_corpus.py [--manifest PATH] [--ids S007 N010 ...] [--skip S007 ...] [--text-only] [--force] [--jobs N] [--dpi N]

Writes a line per paper to scripts/logs/extraction_<time>.log and a summary to corpus/_extraction/extraction-run.json.
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import os
import signal
import subprocess
import sys
import threading
import time

import corpus as C

LOCK = threading.Lock()


def describe(code: int) -> str:
    if code < 0:
        try:
            return f"killed by signal {signal.Signals(-code).name}"
        except ValueError:
            return f"killed by signal {-code}"
    return f"exit status {code}"


def run_one(entry: dict, args: argparse.Namespace) -> dict:
    pdf = C.folder_of(entry) / entry["pdf"]
    cmd = [sys.executable, str(C.SCRIPTS / "extract_paper.py"), str(pdf), "--quiet", "--dpi", str(args.dpi)]
    cmd += ["--text-only"] if args.text_only else []
    cmd += ["--force"] if args.force else []
    attempts = []
    for attempt in (1, 2):
        t0 = time.time()
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=args.timeout,
                               env={**os.environ, "ORT_DISABLE_TELEMETRY": "1"})
            code, out, err = r.returncode, r.stdout.strip(), r.stderr.strip()
        except subprocess.TimeoutExpired:
            code, out, err = 124, "", f"timed out after {args.timeout} s"
        attempts.append({"attempt": attempt, "result": "ok" if code == 0 else describe(code),
                         "seconds": round(time.time() - t0, 1), "stdout": out[-500:], "stderr": err[-1500:]})
        if code == 0:
            break
    return {"id": entry["id"], "folder": entry["folder"], "ok": attempts[-1]["result"] == "ok", "attempts": attempts}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--manifest", help="a manifest of the corpus form (default: the corpus manifest)")
    ap.add_argument("--ids", nargs="*", help="paper IDs (default: every paper in the manifest)")
    ap.add_argument("--skip", nargs="*", default=[], help="paper IDs to leave out")
    ap.add_argument("--text-only", action="store_true", help="rewrite only the text of papers already extracted")
    ap.add_argument("--force", action="store_true", help="re-extract papers that are already extracted")
    ap.add_argument("--jobs", type=int, default=min(8, os.cpu_count() or 4))
    ap.add_argument("--dpi", type=int, default=150)
    ap.add_argument("--timeout", type=int, default=3600, help="seconds allowed per paper")
    args = ap.parse_args()

    papers = C.load_manifest(args.manifest)
    if args.ids:
        wanted = {i.upper() for i in args.ids}
        papers = [p for p in papers if p["id"].upper() in wanted]
        missing = wanted - {p["id"].upper() for p in papers}
        if missing:
            print(f"not in the manifest: {', '.join(sorted(missing))}", file=sys.stderr)
            return 2
    papers = [p for p in papers if p["id"].upper() not in {i.upper() for i in args.skip}]
    log_dir = C.SCRIPTS / "logs"
    log_dir.mkdir(exist_ok=True)
    log = log_dir / f"extraction_{time.strftime('%Y%m%d_%H%M%S')}.log"
    started = time.time()
    results: list[dict] = []
    with open(log, "w", encoding="utf-8") as fh, cf.ThreadPoolExecutor(max_workers=args.jobs) as pool:
        fh.write(f"extract_corpus.py {' '.join(sys.argv[1:])}\n{len(papers)} papers, {args.jobs} at a time\n\n")
        futures = [pool.submit(run_one, p, args) for p in papers]
        for n, fut in enumerate(cf.as_completed(futures), start=1):
            res = fut.result()
            results.append(res)
            last = res["attempts"][-1]
            line = (f"[{n}/{len(papers)}] {'OK  ' if res['ok'] else 'FAIL'} {res['id']}  "
                    f"{last['stdout'].splitlines()[-1] if last['stdout'] else last['result']}"
                    + (f"  (after a retry: first attempt {res['attempts'][0]['result']})" if len(res["attempts"]) > 1 else ""))
            with LOCK:
                print(line, flush=True)
                fh.write(line + "\n")
                for a in res["attempts"]:
                    if a["result"] != "ok" and a["stderr"]:
                        fh.write(f"    attempt {a['attempt']} stderr: {a['stderr']}\n")
                fh.flush()
    failed = [r for r in results if not r["ok"]]
    retried = [r for r in results if len(r["attempts"]) > 1]
    summary = {"started": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(started)),
               "seconds": round(time.time() - started, 1), "arguments": sys.argv[1:], "papers": len(results),
               "ok": len(results) - len(failed), "failed": [r["id"] for r in failed],
               "retried": [r["id"] for r in retried], "log": str(log.relative_to(C.ROOT)),
               "results": sorted(results, key=lambda r: r["id"])}
    C.OUT.mkdir(parents=True, exist_ok=True)
    (C.OUT / "extraction-run.json").write_text(json.dumps(summary, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"\n{summary['ok']} of {len(results)} papers extracted in {summary['seconds']} s; "
          f"failed: {', '.join(summary['failed']) or 'none'}; retried: {', '.join(summary['retried']) or 'none'}\n"
          f"log: {summary['log']}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
