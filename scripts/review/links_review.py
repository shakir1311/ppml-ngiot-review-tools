#!/usr/bin/env python3
"""Citation Links: list the links to review for consistency with the final rules of LINKS-PROTOCOL.md.

The rules were clarified while the batches ran, so early records may attach claims that the final rules leave out.
This lists, for every study with a LINKS.json, the critiques, positionings and unmeasured comparisons whose
quotations use wording the rules restrict: hedged or unnamed groups ("most", "usually", "existing works", "the
aforementioned"). Each listed link is then read against the protocol and kept, retyped or removed.

Usage: scripts/.venv/bin/python scripts/review/links_review.py [ID ...]
"""
import json, pathlib, re, sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
sys.path.insert(0, str(pathlib.Path(__file__).parents[1]))
import ref_links as RL          # noqa: E402
import check_links as CL        # noqa: E402

HEDGE = re.compile(r'\b(most|mostly|usually|typically|generally|mainly|primarily|often|existing|prior work|previous '
                   r'(?:work|works|studies|schemes)|aforementioned|the above|these (?:schemes|methods|works|approaches|'
                   r'solutions|protocols)|state[- ]of[- ]the[- ]art)\b', re.I)


def main():
    by = RL.manifest()
    ids = sys.argv[1:] or CL.primary_ids()
    n = 0
    for pid in ids:
        f = RL.CORPUS / by[pid]['folder'] / 'notes' / 'LINKS.json'
        if not f.exists():
            continue
        for k, l in enumerate(json.loads(f.read_text(encoding='utf-8'))['links'], 1):
            quotes = ' '.join(e.get('quote', '') for e in l.get('evidence', []))
            why = []
            if l['type'] in ('critique', 'positions_against', 'compared_not_measured') and HEDGE.search(quotes):
                why.append('group or hedged wording: ' + ', '.join(sorted({m.group(0).lower() for m in HEDGE.finditer(quotes)})))
            if why:
                n += 1
                print(f"{pid} link {k} {l['type']} → {l.get('to') or l.get('to_name')}: {'; '.join(why)}\n"
                      f"    says: {l.get('says', '')}")
    print(f'\n{n} links to review')


if __name__ == '__main__':
    main()
