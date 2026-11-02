#!/usr/bin/env python3
"""Keeps track of which papers have been handed to a reader, so that every paper is read once and none is left out.

    reading_queue.py next [N]        the next N papers to hand out (default 12), marked as handed out
    reading_queue.py done            records, for every paper handed out, whether its notes now pass the check
    reading_queue.py status          how many papers are read, being read, and waiting
    reading_queue.py release ID ...  puts papers back in the queue (a reader that stopped without notes)

The record is corpus/_extraction/reading-log.json. Papers are handed out in the order of the manifest, newest
collections first (newcorpus, surveycorpus, oldcorpus); every paper is read in the same way.
"""
from __future__ import annotations

import json
import sys
import time

import corpus as C

LOG = C.OUT / "reading-log.json"
ORDER = {"newcorpus": 0, "surveycorpus": 1, "oldcorpus": 2}


def load() -> dict:
    return json.loads(LOG.read_text(encoding="utf-8")) if LOG.exists() else {}


def save(log: dict) -> None:
    LOG.write_text(json.dumps(log, indent=1, ensure_ascii=False), encoding="utf-8")


def state(entry: dict) -> tuple[bool, bool]:
    """-> (notes exist, notes pass the check and were not changed since)"""
    d = C.folder_of(entry) / "notes"
    notes, check = d / "NOTES.md", d / "check.json"
    if not notes.exists():
        return False, False
    if not check.exists() or check.stat().st_mtime < notes.stat().st_mtime:
        return True, False
    return True, bool(json.loads(check.read_text(encoding="utf-8")).get("passed"))


def refresh(log: dict) -> None:
    for entry in C.load_manifest():
        exists, passed = state(entry)
        rec = log.get(entry["id"])
        if exists and rec is None:
            rec = log[entry["id"]] = {"handed_out": None}
        if rec is not None:
            rec["notes"] = "pass" if passed else ("written, not passing" if exists else "none")
            if passed and not rec.get("finished"):
                rec["finished"] = time.strftime("%Y-%m-%d %H:%M")


def main() -> int:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    log = load()
    refresh(log)
    papers = sorted(C.load_manifest(), key=lambda e: (ORDER.get(e["corpus"], 9), e["id"]))
    if cmd == "next":
        n = int(sys.argv[2]) if len(sys.argv) > 2 else 12
        out = [e for e in papers if e["id"] not in log][:n]
        for e in out:
            log[e["id"]] = {"handed_out": time.strftime("%Y-%m-%d %H:%M"), "notes": "none"}
            print(f"{e['id']} | {e['corpus']} / {e['group']} | {e['pages']} | {C.folder_of(e)}")
        if not out:
            print("nothing left to hand out")
    elif cmd == "release":
        for pid in sys.argv[2:]:
            if log.get(pid.upper(), {}).get("notes") != "pass":
                log.pop(pid.upper(), None)
                print("back in the queue:", pid.upper())
    elif cmd not in ("done", "status"):
        print(__doc__)
        return 2
    save(log)
    passed = [i for i, r in log.items() if r.get("notes") == "pass"]
    failing = [i for i, r in log.items() if r.get("notes") == "written, not passing"]
    reading = [i for i, r in log.items() if r.get("notes") == "none"]
    waiting = [e["id"] for e in papers if e["id"] not in log]
    if cmd != "next":
        print(f"{len(papers)} papers | notes pass: {len(passed)} | written but not passing: {len(failing)} {failing} | "
              f"being read: {len(reading)} {reading} | waiting: {len(waiting)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
