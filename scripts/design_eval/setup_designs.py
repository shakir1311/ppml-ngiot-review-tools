#!/usr/bin/env python3
"""Creates one folder per design under design-evaluation/designs/, with its identity and what the evidence sheet records.

Each folder gets `design.json` (id, title, year, first author, DOI, reference, paper folder) and `evidence/01-sheet.json`
(the extraction answer P3: code, datasets, environment, scale, and the sheet's quotations that carry a link), and the
empty sub-folders `evidence/`, `code/`, `datasets/` and `algorithm/`. Safe to re-run: existing files other than these two
are left alone.

Usage: python3 scripts/design_eval/setup_designs.py
"""
import json, sys

sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parent))
from common import ROOT, load_designs, save_json, now   # noqa: E402


def main():
    designs = load_designs()
    for d in designs:
        f = d['folder']
        for sub in ('evidence', 'code', 'datasets', 'algorithm'):
            (f / sub).mkdir(parents=True, exist_ok=True)
        save_json(f / 'design.json', {k: (str(v) if k == 'folder' else v) for k, v in d.items() if k != 'folder'}
                  | {'folder': str(f.relative_to(ROOT))})
        sheet = json.load(open(ROOT / 'search-ppml' / 'evidence' / 'sheets' / f"{d['id']}.json"))
        link_quotes = [e for e in sheet['answers']['P3']['evidence']
                       if any(k in e.get('quote', '').lower() for k in ('http', 'github', 'www.', 'doi.org'))]
        save_json(f / 'evidence' / '01-sheet.json', {
            'about': 'What the evidence sheet (search-ppml/evidence/sheets/<id>.json, answer P3) records about code and '
                     'data; the quotations are the sheet\'s own, those that carry a link.',
            'made': now(), 'sheet_values': d['sheet_p3'], 'sheet_link_quotations': link_quotes})
    print(f'{len(designs)} design folders under design-evaluation/designs/')


if __name__ == '__main__':
    main()
