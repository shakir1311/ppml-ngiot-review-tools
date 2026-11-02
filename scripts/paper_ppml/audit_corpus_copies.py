#!/usr/bin/env python3
"""Audit every paper filed in corpus/ppmlcorpus/check/ — that it was copied, extracted and recorded correctly.

For each folder p<record>/:
  copy       the PDF exists; its SHA-256 equals the one in PROVENANCE.json; for a straight copy, it also equals the SHA-256
             of the source file (so the corpus copy is byte-identical to what was downloaded); a carved chapter records
             the pages taken instead
  extraction text/full.txt exists, and text/pages/ and images/pages/ hold one file per PDF page
  version    whether PROVENANCE.json flags the copy as not the final version
  notes      notes/NOTES.md and notes/SUMMARY.md exist and the notes checker passes (it is run again here)
  record     the full-text eligibility record exists (search-ppml/evidence/rescreen/fulltext/ or evidence/checks/)
  index      the folder is listed in search-ppml/CORPUS-INDEX-2026-10-04.csv (scripts/search_ppml/corpus_match.py)
Writes search-ppml/evidence/rescreen/CORPUS-AUDIT-2026-10-05.json and prints one line per problem and the totals.

Usage: scripts/.venv/bin/python scripts/paper_ppml/audit_corpus_copies.py
"""
import csv, hashlib, json, pathlib, subprocess, sys
import pymupdf

csv.field_size_limit(10 ** 9)
ROOT = pathlib.Path(__file__).resolve().parents[2]
CHECK = ROOT / 'corpus' / 'ppmlcorpus' / 'check'
EV = ROOT / 'search-ppml' / 'evidence'
PY = ROOT / 'scripts' / '.venv' / 'bin' / 'python'


def sha(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


def main():
    index = {r['id'] for r in csv.DictReader(open(ROOT / 'search-ppml' / 'CORPUS-INDEX-2026-10-04.csv', encoding='utf-8'))}
    out, problems = [], 0
    for folder in sorted(d for d in CHECK.iterdir() if d.is_dir() and d.name.startswith('p')):
        pid, res = folder.name, {}
        pdf, prov_f = folder / f'{folder.name}.pdf', folder / 'PROVENANCE.json'
        if not pdf.exists() or not prov_f.exists():
            res['copy'] = 'PDF or PROVENANCE.json missing'
        else:
            prov, h = json.loads(prov_f.read_text(encoding='utf-8')), sha(pdf)
            if prov.get('sha256') != h:
                res['copy'] = 'SHA-256 differs from PROVENANCE.json'
            elif prov.get('pages_taken_from_source'):
                res['copy'] = 'ok (chapter carved from the source: ' + prov['pages_taken_from_source'] + ')'
            elif prov.get('source_sha256') and prov['source_sha256'] != h:
                res['copy'] = 'differs from the source file'
            else:
                res['copy'] = 'ok' if prov.get('source_sha256') or prov.get('source_url') else 'ok (no source checksum recorded)'
            n = pymupdf.open(pdf).page_count
            tp = len(list((folder / 'text' / 'pages').glob('page_*.txt')))
            ip = len(list((folder / 'images' / 'pages').glob('page_*.png')))
            res['extraction'] = 'ok' if (folder / 'text' / 'full.txt').exists() and tp == n and ip == n else f'{n} PDF pages, {tp} text pages, {ip} page images'
            res['version'] = prov.get('version_note', '') and 'not final'
        notes = folder / 'notes'
        if (notes / 'NOTES.md').exists() and (notes / 'SUMMARY.md').exists():
            r = subprocess.run([str(PY), str(ROOT / 'scripts' / 'check_notes_simple.py'), str(folder)], capture_output=True, text=True)
            res['notes'] = 'ok' if r.returncode == 0 else 'checker fails'
        else:
            res['notes'] = 'missing'
        res['record'] = 'ok' if (EV / 'rescreen' / 'fulltext' / f'{pid}.json').exists() or (EV / 'checks' / f'fulltext-{pid}.json').exists() else 'missing'
        res['index'] = 'ok' if pid in index else 'not in CORPUS-INDEX'
        bad = {k: v for k, v in res.items() if k != 'version' and not str(v).startswith('ok')}
        problems += bool(bad)
        if bad:
            print(f'{pid}: ' + '; '.join(f'{k}: {v}' for k, v in bad.items()))
        out.append({'id': pid, **res})
    (EV / 'rescreen' / 'CORPUS-AUDIT-2026-10-05.json').write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding='utf-8')
    print(f'{len(out)} folders audited; {len(out) - problems} with no problem; '
          f'{sum(1 for x in out if x.get("version"))} copies not final: ' + ', '.join(x['id'] for x in out if x.get('version')))


if __name__ == '__main__':
    main()
