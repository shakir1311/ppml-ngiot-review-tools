#!/usr/bin/env python3
"""Flag downloaded PDFs that are not the final published version, from what their first pages say.

The standing rule (scripts/NOTES-PPML-PROTOCOL-V2.md) allows published versions only; an unedited copy is recorded and
replaced when the final version is available. Labels from indexes are not trusted for this (OpenAlex called two
"in press" copies the published version). For every folder with a PROVENANCE.json under the folders given (default
corpus/ppmlcorpus/check), the text of the first two extracted pages is searched for the phrases publishers print on such
copies; a match is written to PROVENANCE.json as "version_note" (with the phrase), and the folder is listed.

Usage: python3 scripts/paper_ppml/version_notes.py [folder ...]
"""
import json, pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
MARKERS = [r"has not been fully edited", r"journal pre-?proof", r"accepted manuscript", r"article in press",
           r"early access", r"unedited", r"this is the author'?s version", r"preprint (?:submitted|version|not peer)",
           r"this (?:article )?is a preprint", r"not yet been (?:copy)?edited"]          # never a bare "preprint": papers cite preprints


def first_pages(folder):
    pages = sorted((folder / 'text' / 'pages').glob('page_*.txt'))[:2]
    return ' '.join(p.read_text(encoding='utf-8', errors='ignore') for p in pages)


def main(roots):
    flagged = []
    for root in roots:
        for prov in sorted(root.rglob('PROVENANCE.json')):
            if '_superseded' in prov.parts:                         # archived copies keep their own record
                continue
            folder = prov.parent
            text = re.sub(r'\s+', ' ', first_pages(folder)).lower()
            hit = next((m for m in MARKERS if re.search(m, text)), None)
            d = json.loads(prov.read_text(encoding='utf-8'))
            if not hit and d.get('version_note', '').startswith('not the final published version'):
                del d['version_note']                                   # a note this script wrote that no longer matches
                prov.write_text(json.dumps(d, indent=1, ensure_ascii=False), encoding='utf-8')
            if hit:
                note = f'not the final published version: the first pages say "{re.search(hit, text).group(0)}"; replace when the final version is available'
                if d.get('version_note') != note:
                    d['version_note'] = note
                    prov.write_text(json.dumps(d, indent=1, ensure_ascii=False), encoding='utf-8')
                flagged.append(folder.name)
    print(f'{len(flagged)} not final:', ', '.join(flagged) or '—')


if __name__ == '__main__':
    main([pathlib.Path(a) for a in sys.argv[1:]] or [ROOT / 'corpus' / 'ppmlcorpus' / 'check'])
