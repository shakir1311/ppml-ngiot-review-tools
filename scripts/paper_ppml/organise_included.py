#!/usr/bin/env python3
"""Move the studies included in the PPML review into one dedicated folder, corpus/ppmlcorpus/included/, one folder per study
named as the corpus has always named papers: "<year> - <title> (<first author>)" (the author, 5 October 2026: "please move the
included corpus in a dedicated folder naming each folder as the title of the paper and main author (just like the way we
used to do)").

For each study of search-ppml/FINAL-STUDIES-2026-10-05.csv, its folder (the published version where
search-ppml/evidence/PUBLISHED-VERSIONS.json names one) is moved — PDF, PROVENANCE, extraction, notes and all — and a
symbolic link is left at the old place, so that the scripts, indexes and apps of this and the earlier reviews, which share
many of these papers, still find them. A published version adopted after a study was moved replaces the preprint in the
included folder: the preprint goes back to its old place and the link is left at the published version's place. The first author's surname is taken from the review's reference list
(myliteraturereviewpaper/ppml2026/refs.json). Writes corpus/ppmlcorpus/included/INDEX.csv (study, folder, old place) and
README.md. A study no longer included moves back to its old place (its link is replaced by the folder). Running it twice
changes nothing.

Usage: python3 scripts/paper_ppml/organise_included.py [--dry-run]
"""
import csv, json, pathlib, re, shutil, sys, unicodedata

csv.field_size_limit(10 ** 9)
ROOT = pathlib.Path(__file__).resolve().parents[2]
P = ROOT / 'search-ppml'
DEST = ROOT / 'corpus' / 'ppmlcorpus' / 'included'
INDEX = DEST / 'INDEX.csv'


def folder_of(cid, idx, pub):
    if cid in pub:
        return ROOT / pub[cid]
    return ROOT / pathlib.Path(idx[cid]['pdf']).parent


def clean(title):
    t = unicodedata.normalize('NFKC', title)
    t = re.sub(r'\s*:\s*', ' - ', t)
    t = re.sub(r'[/\\?%*|"<>]', '-', t)
    t = re.sub(r'\s+', ' ', t).strip(' .')
    if len(t) > 140:
        t = t[:140].rsplit(' ', 1)[0].rstrip(' -,.')
    return t


def main(dry):
    idx = {r['id']: r for r in csv.DictReader(open(P / 'CORPUS-INDEX-2026-10-04.csv', encoding='utf-8'))}
    pubf = P / 'evidence' / 'PUBLISHED-VERSIONS.json'
    pub = json.loads(pubf.read_text(encoding='utf-8')) if pubf.exists() else {}
    refs = json.loads((ROOT / 'myliteraturereviewpaper' / 'ppml2026' / 'refs.json').read_text(encoding='utf-8'))
    fin = list(csv.DictReader(open(P / 'FINAL-STUDIES-2026-10-05.csv', encoding='utf-8')))
    prev = {r['corpus_id']: r for r in csv.DictReader(open(INDEX, encoding='utf-8'))} if INDEX.exists() else {}
    DEST.mkdir(parents=True, exist_ok=True)
    rows, moved = [], 0
    for f in fin:
        cid = f['corpus_id']
        author = (refs.get(cid) or {}).get('first_author_surname', '') or 'unknown'
        name = f"{f['year']} - {clean(f['title'])} ({author})"
        target = DEST / name
        old = ROOT / prev[cid]['old_place'] if cid in prev else folder_of(cid, idx, pub)
        pubdir = ROOT / pub[cid] if cid in pub else None
        if (pubdir is not None and pubdir.is_dir() and not pubdir.is_symlink() and target.is_dir()
                and not target.is_symlink() and target.resolve() != pubdir.resolve()):
            # a published version adopted after the move: it replaces the preprint in the included folder, the preprint
            # goes back to its old place, and a link at the published version's place points here (as for S026)
            print(f'{cid}: published version {pubdir.relative_to(ROOT)} -> included/{name}; '
                  f'the preprint goes back to {old.relative_to(ROOT)}')
            if not dry:
                if old.is_symlink():
                    old.unlink()
                shutil.move(str(target), str(old))
                shutil.move(str(pubdir), str(target))
                pubdir.symlink_to(target, target_is_directory=True)
            old = pubdir
            moved += 1
        elif old.is_symlink() and old.resolve() == target.resolve():
            pass                                                   # already moved
        elif old.is_dir() and not old.is_symlink():
            if target.exists():
                sys.exit(f'{cid}: {target.name} exists already — nothing moved')
            print(f'{cid}: {old.relative_to(ROOT)} -> included/{name}')
            if not dry:
                shutil.move(str(old), str(target))
                old.symlink_to(target, target_is_directory=True)
            moved += 1
        elif old.is_symlink() and old.resolve().parent == DEST.resolve() and old.resolve().is_dir():
            cur = old.resolve()                                    # moved earlier under another name (e.g. author then unknown)
            if target.exists():
                sys.exit(f'{cid}: {target.name} exists already — nothing renamed')
            print(f'{cid}: included/{cur.name} -> included/{name} (renamed)')
            if not dry:
                shutil.move(str(cur), str(target))
                old.unlink()
                old.symlink_to(target, target_is_directory=True)
            moved += 1
        else:
            sys.exit(f'{cid}: {old} is neither the folder nor a link to it — check by hand')
        rows.append({'corpus_id': cid, 'kind': f['kind'], 'year': f['year'], 'first_author': author, 'title': f['title'],
                     'folder': f'corpus/ppmlcorpus/included/{name}', 'old_place': str(old.relative_to(ROOT))})
    keep = {r['corpus_id'] for r in rows}
    for cid, r in prev.items():                                    # no longer included: back to its old place
        if cid in keep:
            continue
        old, target = ROOT / r['old_place'], ROOT / r['folder']
        print(f'{cid}: no longer included -> back to {r["old_place"]}')
        if not dry and old.is_symlink() and target.is_dir():
            old.unlink()
            shutil.move(str(target), str(old))
    if dry:
        print(f'dry run: {moved} to move')
        return
    with open(INDEX, 'w', encoding='utf-8', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(sorted(rows, key=lambda r: (r['kind'] != 'primary', r['year'], r['title'])))
    (DEST / 'README.md').write_text(
        '# The studies included in the PPML review\n\n'
        f'{len(rows)} studies ({sum(r["kind"] == "primary" for r in rows)} primary, {sum(r["kind"] == "secondary" for r in rows)} secondary), '
        'one folder each, named "<year> - <title> (<first author>)": the PDF, PROVENANCE.json, the extracted text and page images, and '
        'the notes (notes/SUMMARY.md to read; notes/NOTES.md the page-cited record). INDEX.csv gives each study\'s corpus id and the '
        'place it came from, where a link now points here, so the earlier reviews\' scripts and apps still find it.\n\n'
        'Kept up to date by scripts/paper_ppml/organise_included.py from search-ppml/FINAL-STUDIES-2026-10-05.csv.\n', encoding='utf-8')
    print(f'{moved} moved; {len(rows)} studies in corpus/ppmlcorpus/included/')


if __name__ == '__main__':
    main('--dry-run' in sys.argv)
