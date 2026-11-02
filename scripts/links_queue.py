#!/usr/bin/env python3
"""Keeps track of which primary studies have had their links to earlier work recorded (LINKS-PROTOCOL.md), so that
the work can run in small batches and resume after an interruption. A study is done when its notes/LINKS.json
passes check_links.py; nothing else counts.

    links_queue.py next [N]        the next N studies to hand out (default 5): marks them handed out and builds
                                   their packs in corpus/_extraction/links-packs/
    links_queue.py done            records, for every study handed out, whether its LINKS.json now passes
    links_queue.py status          how many studies are done, handed out, and waiting
    links_queue.py release ID ...  puts studies back in the queue (a batch that stopped before finishing)

The record is corpus/_extraction/links-log.json. Studies are handed out in ID order.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent / 'review'))
import corpus as C              # noqa: E402
import check_links as CL        # noqa: E402
import ref_links as RL          # noqa: E402
import links_packs as LP        # noqa: E402

LOG = C.OUT / 'links-log.json'
PACKS = C.OUT / 'links-packs'


def load() -> dict:
    return json.loads(LOG.read_text(encoding='utf-8')) if LOG.exists() else {}


def save(log: dict) -> None:
    LOG.write_text(json.dumps(log, indent=1, ensure_ascii=False), encoding='utf-8')


def refresh(log: dict, ids: list[str]) -> None:
    """a study is done exactly when its LINKS.json passes the checker"""
    by, titles = RL.manifest(), RL.corpus_titles()
    for pid in ids:
        err, _, stats = CL.check(pid, titles, by)
        e = log.setdefault(pid, {})
        e['done'] = not err
        if not err:
            e['checked'] = time.strftime('%Y-%m-%d %H:%M')
            e['links'] = stats.get('links')


def main() -> int:
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'status'
    log = load()
    ids = CL.primary_ids()
    if cmd == 'next':
        n = int(sys.argv[2]) if len(sys.argv) > 2 else 5
        refresh(log, [p for p in ids if not log.get(p, {}).get('done')])
        out = [p for p in ids if not log.get(p, {}).get('done') and not log.get(p, {}).get('handed_out')][:n]
        PACKS.mkdir(parents=True, exist_ok=True)
        by, titles = RL.manifest(), RL.corpus_titles()
        for p in out:
            text, _ = LP.pack(p, titles, by)
            (PACKS / f'{p}.md').write_text(text, encoding='utf-8')
            log.setdefault(p, {})['handed_out'] = time.strftime('%Y-%m-%d %H:%M')
        save(log)
        print(' '.join(out) if out else 'nothing left to hand out')
        return 0
    if cmd == 'done':
        handed = [p for p in ids if log.get(p, {}).get('handed_out') and not log.get(p, {}).get('done')]
        refresh(log, handed)
        for p in handed:
            if log[p]['done']:
                log[p].pop('handed_out', None)
        save(log)
        ok = [p for p in handed if log[p]['done']]
        print(f"{len(ok)} of {len(handed)} handed-out studies now pass: {' '.join(ok)}")
        left = [p for p in handed if not log[p]['done']]
        if left:
            print(f"still open (release them if their batch stopped): {' '.join(left)}")
        return 0
    if cmd == 'release':
        for p in sys.argv[2:]:
            log.get(p, {}).pop('handed_out', None)
        save(log)
        print('released:', ' '.join(sys.argv[2:]))
        return 0
    refresh(log, ids)
    save(log)
    done = [p for p in ids if log[p].get('done')]
    handed = [p for p in ids if not log[p].get('done') and log[p].get('handed_out')]
    print(f'{len(ids)} primary studies: {len(done)} done, {len(handed)} handed out, '
          f'{len(ids) - len(done) - len(handed)} waiting')
    if handed:
        print('handed out:', ' '.join(handed))
    return 0


if __name__ == '__main__':
    sys.exit(main())
