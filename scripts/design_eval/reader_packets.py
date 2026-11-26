#!/usr/bin/env python3
"""Writes, for each design that needs a reader, the packet that tells the reader which page files of the paper to read first.

The packet (`algorithm/READER-PACKET.md` in the design's folder) holds no paper text: the design's id and title, the paths of
its page files (from text/pages/, or text/pages_ocr/ where the extraction recovered a page by OCR and that copy holds more
letters) and of its page images (images/pages/, for algorithm boxes, tables and equations missing from the text), the pages the local triage (algorithm/01-triage.json) names first, the output files, and a pointer to the shared
instructions design-evaluation/READER-PROMPT.md.

Usage: design-evaluation/.venv/bin/python scripts/design_eval/reader_packets.py <id> [<id> ...]
"""
import json, pathlib, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import ROOT, design, page_texts   # noqa: E402


def packet(design_id):
    d = design(design_id)
    tri = json.load(open(d['folder'] / 'algorithm' / '01-triage.json'))
    pages = page_texts(d['paper_folder'])
    first = tri['pages_for_reader']
    lines = [f"# Reader packet: {d['id']}", '',
             f"Design: {d['title']} ({d['first_author']} {d['year']}).", '',
             'Instructions: `design-evaluation/READER-PROMPT.md` (read it first).', '',
             f"Read first, pages: {', '.join(map(str, first))}.",
             f"Body of the paper (before the references): pages {tri['body_pages'][0]}-{tri['body_pages'][-1]}.", '',
             'Page files (absolute paths):', '']
    img_dir = ROOT / d['paper_folder'] / 'images' / 'pages'
    for n, p in pages:
        mark = ' (read first)' if n in first else ''
        img = img_dir / f'page_{n:04d}.png'
        lines.append(f'- page {n}: `{p}`{mark}' + (f'; image `{img}`' if img.exists() else ''))
    for sup in sorted((d['folder'] / 'evidence' / 'supplementary').glob('*/text/pages')):
        lines += ['', f'Supplementary material of the same paper (the publisher\'s file, extracted and OCR-verified by the pipeline; '
                      f'read it where the paper refers to it or the pages above leave an item unsettled):', '']
        imgs = sup.parent.parent / 'images' / 'pages'
        for p in sorted(sup.glob('page_*.txt')):
            n = int(p.stem.split('_')[1])
            img = imgs / f'page_{n:04d}.png'
            lines.append(f'- supplementary page {n}: `{p}`' + (f'; image `{img}`' if img.exists() else ''))
    lines += ['', 'Write:', '',
              f"- `{d['folder'] / 'algorithm' / 'reader.json'}`",
              f"- `{d['folder'] / 'algorithm' / 'reader-quotes.json'}`", '']
    (d['folder'] / 'algorithm' / 'READER-PACKET.md').write_text('\n'.join(lines))
    return d['folder'] / 'algorithm' / 'READER-PACKET.md'


if __name__ == '__main__':
    for i in sys.argv[1:]:
        print(packet(i).relative_to(ROOT))
