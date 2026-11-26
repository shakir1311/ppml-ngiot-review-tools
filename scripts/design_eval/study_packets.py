#!/usr/bin/env python3
"""Writes the reader packets of the Phase 2 design study: for each of the eleven designs that need a reader, which page files, page images, code and records the reader may use.

The six designs carried forward (kind "six") are read for the design, datasets, set-up, runs, reported results and code against
the paper; the five new designs not carried forward (kind "qualitative") for the review's P1 to P3 classification and the Phase 1
checklist. The 43 review designs not carried forward need no reader: their evidence sheets and Phase 1 checklists hold the study's
fields. A packet (`study/READER-PACKET.md` in the design's folder) holds no paper text: ids, titles, paths and the output files.
Instructions: design-evaluation/study/READER-PROMPT.md. The author's permission: CLAUDE.md, 26 November 2026.

Usage: python3 scripts/design_eval/study_packets.py [<id> ...]
"""
import json, pathlib, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import EVAL, ROOT, design, page_texts   # noqa: E402

SIX = ['n2721', 'n3378', 'Z01', 'Z04', 'Z06', 'Z07']
QUALITATIVE = ['Z02', 'Z03', 'Z05', 'Z08', 'Z09']
OUR_RECORDS = {   # the October reproductions (our own records, not paper text)
    'n2721': ['experiments/zkpet/ (README, env/, runs/)', 'experiments/MY-EXPERIMENT-AGENDA.md'],
    'n3378': ['experiments/fl-bc-ids/ (README, env/, runs/)', 'experiments/fl-bc-ids-attacks/README.md', 'experiments/MY-EXPERIMENT-AGENDA.md'],
}


def resolve(i):
    """-> dict(id, title, who, folder, paper_folder (relative to ROOT), sheet or None)"""
    if i.startswith('Z'):
        folder = next((EVAL / 'new-designs' / 'designs').glob(f'{i}-*'))
        m = json.load(open(folder / 'design.json'))
        return {'id': i, 'title': m['paper'], 'who': f"{m['authors'].split(',')[0]} et al., {m['year']}", 'name': m['name'],
                'folder': folder, 'paper_folder': (folder / 'paper' / i).relative_to(ROOT), 'sheet': None}
    d = design(i)
    return {'id': i, 'title': d['title'], 'who': f"{d['first_author']} et al., {d['year']}", 'name': {'n2721': 'zkPET', 'n3378': 'FL-BC-IDS'}.get(i, d['acronym'] or i),
            'folder': d['folder'], 'paper_folder': pathlib.Path(d['paper_folder']),
            'sheet': ROOT / 'search-ppml' / 'evidence' / 'sheets' / f'{i}.json'}


def packet(i):
    d = resolve(i)
    kind = 'six' if i in SIX else 'qualitative'
    pages = page_texts(d['paper_folder'])
    img = ROOT / d['paper_folder'] / 'images' / 'pages'
    L = [f"# Study reader packet: {i} ({d['name']})", '',
         f"Paper: {d['title']} ({d['who']}).", f"Kind: **{kind}**.", '',
         'Instructions: `design-evaluation/study/READER-PROMPT.md` (read it first).', '']
    if d['sheet']:
        L += [f"This design has an evidence sheet (the review's P1 to P3, verified by the author): `{d['sheet']}`. "
              'Leave `sheet_values` out; read the sheet if it helps you find things in the paper.', '']
    else:
        L += ['This design has no evidence sheet: fill `sheet_values` (P1, P2, P3) with the allowed values.', '']
    if kind == 'six':
        codes = sorted(p for p in (d['folder'] / 'code').iterdir() if p.is_dir())
        L += ['Code (read README, configs, scripts and the source as far as you need):', '']
        L += [f'- `{c}`' for c in codes] + ['']
        if i in OUR_RECORDS:
            L += ['Our own October reproduction of this design (records you may read, to compare with the paper):', '']
            L += [f'- `{ROOT / r.split(" ")[0]}`{(" " + r.split(" ", 1)[1]) if " " in r else ""}' for r in OUR_RECORDS[i]] + ['']
    L += [f'Paper: {len(pages)} pages. Page files (absolute paths) and page images:', '']
    for n, p in pages:
        im = img / f'page_{n:04d}.png'
        L.append(f'- p{n}: `{p}`' + (f' · image `{im}`' if im.exists() else ''))
    L += ['', 'Write:', '', f"- `{d['folder'] / 'study' / 'reader.json'}`", f"- `{d['folder'] / 'study' / 'reader-quotes.json'}`", '']
    out = d['folder'] / 'study' / 'READER-PACKET.md'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text('\n'.join(L))
    return out, kind, len(pages)


if __name__ == '__main__':
    for i in sys.argv[1:] or SIX + QUALITATIVE:
        out, kind, n = packet(i)
        print(i, kind, n, 'pages ->', out.relative_to(ROOT))
