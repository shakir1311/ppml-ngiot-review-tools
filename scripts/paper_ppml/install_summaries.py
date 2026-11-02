#!/usr/bin/env python3
"""Install the re-cut short notes (search-ppml/evidence/summaries-recut/out/<id>.md) as notes/SUMMARY.md of their studies,
only where the note passes scripts/check_summary.py (protocol V2) and every page it cites is a page the study's
notes/NOTES.md cites (the note is written from the notes, so it can cite no other page). The earlier note is kept in
notes-verifier/history/<id>/ (SUMMARY-original.md if absent, SUMMARY-before-recut-<stamp>.md). Log:
search-ppml/evidence/summaries-recut/INSTALLED.jsonl. Prints one line per study; never the notes' text.
Usage: python3 scripts/paper_ppml/install_summaries.py [--dry-run] [id ...]
"""
import csv, datetime, json, pathlib, re, sys
ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import check_summary as CK
OUT = ROOT / 'search-ppml' / 'evidence' / 'summaries-recut' / 'out'
LOG = ROOT / 'search-ppml' / 'evidence' / 'summaries-recut' / 'INSTALLED.jsonl'
HIST = ROOT / 'notes-verifier' / 'history'
STAMP = datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
NOW = datetime.datetime.now().isoformat(timespec='seconds')
PAGE = re.compile(r'\[p(\d+)(?:\s*[–-]\s*p?(\d+))?')


def pages_in(text):
    out = set()
    for m in re.finditer(r'\[(p\d+[^\[\]]*)\]', text):
        for a, b in PAGE.findall('[' + m.group(1)):
            a, b = int(a), int(b or a)
            out |= set(range(a, min(b, a + 6) + 1))
    return out


def main(args):
    dry = '--dry-run' in args
    ids = [a for a in args if not a.startswith('--')] or sorted(p.stem for p in OUT.glob('*.md'))
    inc = {r['corpus_id']: ROOT / r['folder'] for r in csv.DictReader((ROOT / 'corpus/ppmlcorpus/included/INDEX.csv').open(encoding='utf-8'))}
    n_ok = n_bad = 0
    for cid in ids:
        src = OUT / f'{cid}.md'
        if not src.exists() or cid not in inc:
            print(f'{cid}: no staged note' if cid in inc else f'{cid}: not an included study'); n_bad += 1; continue
        text = src.read_text(encoding='utf-8')
        first, _, rest = text.partition('\n')             # the title line names the study by its corpus id, whatever the old note used
        if first.startswith('# ') and ' · ' in first and first[2:].split(' · ', 1)[0] != cid:
            src.write_text(f'# {cid} · ' + first[2:].split(' · ', 1)[1] + '\n' + rest, encoding='utf-8')
        errs, words = CK.check(cid, src)
        notes = inc[cid] / 'notes' / 'NOTES.md'
        cited, allowed = pages_in(src.read_text(encoding='utf-8')), pages_in(notes.read_text(encoding='utf-8', errors='replace')) if notes.exists() else set()
        stray = sorted(cited - allowed)
        if stray:
            errs.append(f'cites pages the notes do not cite: {stray}')
        entry = {'on': NOW, 'id': cid, 'words': words, 'problems': errs, 'installed': not errs and not dry}
        if errs:
            print(f"{cid}: refused ({'; '.join(errs)})"); n_bad += 1
        else:
            print(f"{cid}: {'would install' if dry else 'installed'} ({words} words)"); n_ok += 1
            if not dry:
                dest = inc[cid] / 'notes' / 'SUMMARY.md'
                h = HIST / cid; h.mkdir(parents=True, exist_ok=True)
                if dest.exists():
                    old = dest.read_text(encoding='utf-8', errors='replace')
                    if not (h / 'SUMMARY-original.md').exists():
                        (h / 'SUMMARY-original.md').write_text(old, encoding='utf-8')
                    (h / f'SUMMARY-before-recut-{STAMP}.md').write_text(old, encoding='utf-8')
                dest.write_text(src.read_text(encoding='utf-8'), encoding='utf-8')
        if not dry:
            with open(LOG, 'a', encoding='utf-8') as fh:
                fh.write(json.dumps(entry, ensure_ascii=False) + '\n')
    print(f"{n_ok} {'would be ' if dry else ''}installed, {n_bad} refused")


if __name__ == '__main__':
    main(sys.argv[1:])
