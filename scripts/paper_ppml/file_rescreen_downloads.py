#!/usr/bin/env python3
"""File the full texts the author downloads for the records flagged by the full second screening (rescreen.py), and
extract each with the corpus pipeline.

Only the PDFs the author lists (a text file of paths, --files) are opened — never a whole folder, which holds private
documents. Each is matched to a flagged record that the corpus does not yet hold, by the record's whole title on the
first two pages of the PDF (normalised; the first 60 characters if the whole title is broken; the longest title wins). A match is filed
as corpus/ppmlcorpus/check/p<record>/p<record>.pdf with PROVENANCE.json (source file and SHA-256, filed file and SHA-256,
time), then extract_paper.py and ocr_scanned.py run on the folder. PDFs that match no record are listed and left alone;
nothing in Downloads is moved or deleted. Records the author could not get are recorded with --not-retrieved.
Every filed paper then gets brief thematic notes by the standing rule (scripts/NOTES-PPML-PROTOCOL-V2.md, template ppml-2).

Usage: scripts/.venv/bin/python scripts/paper_ppml/file_rescreen_downloads.py --files <list.txt> [--dry-run] [--only n n ...]
       (--dry-run lists the matches and files nothing; --only files just the records named)
       scripts/.venv/bin/python scripts/paper_ppml/file_rescreen_downloads.py --not-retrieved 1234 5678 "reason"
"""
import csv, datetime, hashlib, json, pathlib, re, shutil, subprocess, sys, unicodedata
import pymupdf

csv.field_size_limit(10 ** 9)
ROOT = pathlib.Path(__file__).resolve().parents[2]
RS = ROOT / 'search-ppml' / 'evidence' / 'rescreen'
CHECK = ROOT / 'corpus' / 'ppmlcorpus' / 'check'
PY = ROOT / 'scripts' / '.venv' / 'bin' / 'python'
HOW = 'downloaded by the author through institutional access after the full second screening; filed by Claude Code'


def norm(s):
    return re.sub(r'[^a-z0-9]+', '', unicodedata.normalize('NFKC', s).lower())


def sha(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


def wanted():
    recs = list(csv.DictReader(open(RS / 'RESCREEN-DECISIONS-2026-10-05.csv', encoding='utf-8')))
    return {r['n']: r for r in recs if r['full_text_needed'] and not r['corpus_folder'] and not (CHECK / f"p{int(r['n']):04d}").exists()}


def not_retrieved(ns, why):
    f = RS / 'NOT-RETRIEVED-2026-10-05.json'
    d = json.loads(f.read_text(encoding='utf-8')) if f.exists() else {}
    recs = {r['n']: r for r in csv.DictReader(open(RS / 'RESCREEN-DECISIONS-2026-10-05.csv', encoding='utf-8'))}
    for n in ns:
        d[n] = {'title': recs[n]['title'], 'doi': recs[n]['doi'], 'why': why}
    f.write_text(json.dumps(d, indent=1, ensure_ascii=False), encoding='utf-8')
    print(f'recorded as not retrieved: {", ".join(ns)}')


def main(files, dry=False, only=None):
    W = wanted()
    if only:
        W = {n: r for n, r in W.items() if n in only}
    keys = {n: norm(r['title']) for n, r in W.items()}
    filed, unmatched = [], []
    for pdf in sorted(files):
        try:
            doc = pymupdf.open(pdf)
            first = norm(''.join(doc[i].get_text() for i in range(min(2, doc.page_count))))
        except Exception:                                         # noqa: BLE001 — unreadable files are listed, not filed
            unmatched.append(pdf.name)
            continue
        hit = [n for n, k in keys.items() if k and k in first]              # the whole title on the first pages
        if not hit:                                                       # titles broken by a line-end hyphen or a subtitle
            hit = [n for n, k in keys.items() if k and k[:60] in first]
        if len(hit) > 1:                                                  # keep the longest title that matches
            longest = max(len(keys[n]) for n in hit)
            hit = [n for n in hit if len(keys[n]) == longest]
        if len(hit) != 1:
            unmatched.append(pdf.name + (f' (matches {hit})' if hit else ''))
            continue
        n = hit[0]
        pid = f'p{int(n):04d}'
        if dry:
            print(f'match  {n:>5}  {pid}  <- {pdf.name}')
            filed.append(pid)
            del keys[n]
            continue
        dest = CHECK / pid
        dest.mkdir(parents=True, exist_ok=True)
        out = dest / f'{pid}.pdf'
        shutil.copy2(pdf, out)
        r = W[n]
        prov = {'id': pid, 'record': int(n), 'doi': r['doi'], 'title': r['title'], 'role': 'full text sought after the full second screening',
                'source_file': pdf.name, 'source_sha256': sha(pdf), 'file': out.name, 'sha256': sha(out), 'pages': doc.page_count,
                'how': HOW, 'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds')}
        side = pdf.parent / (pdf.name + '.carve.json')            # a chapter carved out of a book (carve_chapters.py)
        if side.exists():
            c = json.loads(side.read_text(encoding='utf-8'))
            prov.update({'source_file': c['source_file'], 'source_sha256': c['source_sha256'],
                         'pages_taken_from_source': c['pages_taken_from_source'], 'carved_by': 'scripts/paper_ppml/carve_chapters.py'})
        (dest / 'PROVENANCE.json').write_text(json.dumps(prov, indent=1, ensure_ascii=False), encoding='utf-8')
        subprocess.run([str(PY), str(ROOT / 'scripts' / 'extract_paper.py'), str(out), '--quiet'], check=True)
        subprocess.run([str(PY), str(ROOT / 'scripts' / 'ocr_scanned.py'), str(dest)], check=False, capture_output=True)
        filed.append(pid)
        del keys[n]
    print(f'filed {len(filed)}: {", ".join(filed)}')
    if filed and not dry:
        subprocess.run([sys.executable, str(ROOT / 'scripts' / 'paper_ppml' / 'version_notes.py'), str(CHECK)], check=False)
        subprocess.run([sys.executable, str(ROOT / 'scripts' / 'search_ppml' / 'corpus_match.py')], check=False, capture_output=True)
        subprocess.run([str(PY), str(ROOT / 'scripts' / 'paper_ppml' / 'audit_corpus_copies.py')], check=False)
        print('next (standing rule, scripts/NOTES-PPML-PROTOCOL-V2.md): brief thematic notes + summary for each, then '
              'scripts/check_notes_simple.py <folder> must pass')
    print(f'still wanted {len(keys)}: {", ".join(sorted(keys, key=int))}')
    if unmatched:
        print('PDFs matching no wanted record (left alone):', *unmatched, sep='\n  ')


if __name__ == '__main__':
    a = sys.argv[1:]
    if a and a[0] == '--not-retrieved':
        not_retrieved(a[1:-1], a[-1])
    else:
        dry = '--dry-run' in a
        only = None
        if '--only' in a:
            i = a.index('--only') + 1
            only = set()
            while i < len(a) and not a[i].startswith('--'):
                only.add(a[i])
                i += 1
        lst = pathlib.Path(a[a.index('--files') + 1])
        files = [pathlib.Path(l.strip()) for l in lst.read_text(encoding='utf-8').splitlines() if l.strip().lower().endswith('.pdf')]
        main(files, dry, only)
