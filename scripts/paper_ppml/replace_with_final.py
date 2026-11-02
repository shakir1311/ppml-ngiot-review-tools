#!/usr/bin/env python3
"""Replace an unedited copy (early access, in press, author's version) of a filed paper with its final published version,
and carry the paper's records over to it.

1. The new PDF must carry the record's title on its first two pages and none of the phrases that mark an unedited copy
   (version_notes.MARKERS); otherwise nothing is changed.
2. The old PDF, its PROVENANCE.json and its extraction (text/, images/) move to <folder>/_superseded/<old sha256[:12]>/ —
   kept, because the eligibility decision and the notes were made on them.
3. The new PDF is filed as <folder>/<id>.pdf with a new PROVENANCE.json ("replaces": the old file's SHA-256 and version
   note), and extracted with extract_paper.py and ocr_scanned.py.
4. Every quotation in notes/NOTES.md and in the full-text record (search-ppml/evidence/rescreen/fulltext/<id>.json) is
   looked up on the new pages; where it is no longer on the page cited, the citation moves to the page it is on now (the
   nearest to the old page if several). Page references in notes/SUMMARY.md follow the page moves of the notes. A quotation
   found on no page is listed for a reader to fix. Every move is logged in
   search-ppml/evidence/rescreen/REANCHOR-LOG-2026-10-05.json; then the notes checker and fulltext-check run.

Usage: scripts/.venv/bin/python scripts/paper_ppml/replace_with_final.py <id> <path to the final PDF>
       scripts/.venv/bin/python scripts/paper_ppml/replace_with_final.py --reanchor <id>   (finish an interrupted replacement)
"""
import collections, datetime, hashlib, json, pathlib, re, shutil, subprocess, sys, unicodedata
import pymupdf

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(pathlib.Path(__file__).parent))
from version_notes import MARKERS                         # noqa: E402
from check_sheets import found                            # noqa: E402

PY = ROOT / 'scripts' / '.venv' / 'bin' / 'python'
EXTRACTION = ('text', 'images', 'tables', 'metadata.json', 'README.md')     # what extract_paper.py writes
RS = ROOT / 'search-ppml' / 'evidence' / 'rescreen'
NOW = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds')
CITE_QUOTE = re.compile(r'\[p(\d+)\]\s*"([^"]+)"')


def sha(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


def norm(s):
    return re.sub(r'[^a-z0-9]+', '', unicodedata.normalize('NFKC', s or '').lower())


def pages_of(folder):
    return {int(p.stem.split('_')[1]): p.read_text(encoding='utf-8', errors='ignore') for p in (folder / 'text' / 'pages').glob('page_*.txt')}


def locate(quote, old, pages):
    if old in pages and found(quote, pages[old]):
        return old
    hits = [p for p, t in pages.items() if found(quote, t)]
    return min(hits, key=lambda p: abs(p - old)) if hits else None


def main(pid, new_pdf):
    folder = ROOT / 'corpus' / 'ppmlcorpus' / 'check' / pid
    old_prov = json.loads((folder / 'PROVENANCE.json').read_text(encoding='utf-8'))
    doc = pymupdf.open(new_pdf)
    first = re.sub(r'\s+', ' ', ''.join(doc[i].get_text() for i in range(min(2, doc.page_count)))).lower()
    if norm(old_prov['title'])[:60] not in norm(first):
        sys.exit(f'{pid}: the new PDF does not carry the title "{old_prov["title"][:60]}" — nothing changed')
    if any(re.search(m, first) for m in MARKERS):
        sys.exit(f'{pid}: the new PDF is itself marked as not final — nothing changed')
    old_pdf = folder / f'{pid}.pdf'
    if sha(old_pdf) == sha(new_pdf):
        sys.exit(f'{pid}: the new PDF is the copy already filed — nothing changed')
    old_pages = pages_of(folder)
    sup = folder / '_superseded' / sha(old_pdf)[:12]
    sup.mkdir(parents=True, exist_ok=True)
    for name in (old_pdf.name, 'PROVENANCE.json') + EXTRACTION:
        if (folder / name).exists():
            shutil.move(str(folder / name), str(sup / name))
    shutil.copy2(new_pdf, old_pdf)
    prov = {k: old_prov[k] for k in ('id', 'record', 'doi', 'title', 'role') if k in old_prov}
    prov.update({'how': 'final published version downloaded by the author; filed by Claude Code (replace_with_final.py)',
                 'source_file': pathlib.Path(new_pdf).name, 'source_sha256': sha(new_pdf), 'file': old_pdf.name, 'sha256': sha(old_pdf),
                 'pages': doc.page_count, 'utc': NOW,
                 'replaces': {'sha256': old_prov.get('sha256'), 'source': old_prov.get('source_url') or old_prov.get('source_file'),
                              'version_note': old_prov.get('version_note', ''), 'kept_in': str(sup.relative_to(folder))}})
    (folder / 'PROVENANCE.json').write_text(json.dumps(prov, indent=1, ensure_ascii=False), encoding='utf-8')
    extract(folder, old_pdf)
    reanchor(pid, folder, len(old_pages))


def extract(folder, pdf):
    subprocess.run([str(PY), str(ROOT / 'scripts' / 'extract_paper.py'), str(pdf), '--force', '--quiet'], check=True)
    subprocess.run([str(PY), str(ROOT / 'scripts' / 'ocr_scanned.py'), str(folder)], check=False, capture_output=True)


def reanchor(pid, folder, n_old):
    pages = pages_of(folder)
    if not pages:
        sys.exit(f'{pid}: the new copy has no extracted pages — nothing re-anchored')
    moves, lost, page_map = [], [], collections.defaultdict(collections.Counter)

    def fix_line(line, where):
        def sub(m):
            old, q = int(m.group(1)), m.group(2)
            new = locate(q, old, pages)
            if new is None:
                lost.append(f'{where}: p{old} "{q[:70]}"')
                return m.group(0)
            page_map[old][new] += 1
            if new != old:
                moves.append({'where': where, 'from': old, 'to': new, 'quote': q[:90]})
            return f'[p{new}] "{q}"'
        return CITE_QUOTE.sub(sub, line)

    notes = folder / 'notes' / 'NOTES.md'
    if notes.exists():
        notes.write_text('\n'.join(fix_line(l, 'NOTES.md') for l in notes.read_text(encoding='utf-8').splitlines()) + '\n', encoding='utf-8')
        summ = folder / 'notes' / 'SUMMARY.md'
        if summ.exists():
            pm = {o: c.most_common(1)[0][0] for o, c in page_map.items()}
            s = re.sub(r'\[p(\d+)\]', lambda m: f'[p{pm.get(int(m.group(1)), int(m.group(1)))}]', summ.read_text(encoding='utf-8'))
            summ.write_text(s, encoding='utf-8')
    ft = RS / 'fulltext' / f'{pid}.json'
    if ft.exists():
        d = json.loads(ft.read_text(encoding='utf-8'))
        for k, c in (d.get('conditions') or {}).items():
            for ev in c.get('evidence', []):
                new = locate(ev['quote'], int(ev['page']), pages)
                if new is None:
                    lost.append(f'fulltext {k}: p{ev["page"]} "{ev["quote"][:70]}"')
                elif new != int(ev['page']):
                    moves.append({'where': f'fulltext {k}', 'from': int(ev['page']), 'to': new, 'quote': ev['quote'][:90]})
                    ev['page'] = new
        d['version'] = f'final published version (replaced the unedited copy on {NOW[:10]})'
        ft.write_text(json.dumps(d, indent=1, ensure_ascii=False), encoding='utf-8')
    logf = RS / 'REANCHOR-LOG-2026-10-05.json'
    log = json.loads(logf.read_text(encoding='utf-8')) if logf.exists() else {}
    log[pid] = {'utc': NOW, 'old_pages': n_old, 'new_pages': len(pages), 'moves': moves, 'not_found': lost}
    logf.write_text(json.dumps(log, indent=1, ensure_ascii=False), encoding='utf-8')
    subprocess.run([sys.executable, str(pathlib.Path(__file__).with_name('version_notes.py')), str(folder.parent)], check=False)
    print(f'{pid}: {n_old} -> {len(pages)} pages; {len(moves)} citations moved; {len(lost)} quotations not found')
    for l in lost:
        print('   not found:', l)


if __name__ == '__main__':
    if sys.argv[1] == '--reanchor':                 # finish a replacement whose extraction or re-anchoring did not complete
        pid = sys.argv[2]
        folder = ROOT / 'corpus' / 'ppmlcorpus' / 'check' / pid
        sup = sorted((folder / '_superseded').iterdir())[-1]
        for name in EXTRACTION:                     # extraction outputs of the old copy left behind go with it
            if (folder / name).exists() and not (sup / name).exists():
                shutil.move(str(folder / name), str(sup / name))
        extract(folder, folder / f'{pid}.pdf')
        reanchor(pid, folder, len(list((sup / 'text' / 'pages').glob('page_*.txt'))))
    else:
        main(sys.argv[1], pathlib.Path(sys.argv[2]))
