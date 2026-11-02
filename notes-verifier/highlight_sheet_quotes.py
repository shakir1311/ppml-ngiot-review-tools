#!/usr/bin/env python3
"""Highlight every evidence-sheet quotation in its study's PDF, where the whole quotation is certainly on that page.

A quotation is highlighted only if all its words are found, in order and without gaps, on the page the sheet names
(letters and digits compared; case, punctuation, ligatures, line breaks and end-of-line hyphens ignored). Anything less
is left unhighlighted and counted. The highlights are real PDF highlight annotations in yellow, like the apps' own,
titled "Evidence sheet" with the question (e.g. "P3 — Ledger"), so they show in Preview too, and can be removed in the
apps by right-clicking like any other highlight. --recolour gives existing sheet highlights the current colour.

Before a PDF is first changed, its untouched copy is kept in notes-verifier/originals/<study>/ (as the apps do).
Running again adds only what is missing (each highlight carries the fingerprint of its page and quotation).
Close the Sheet Reviewer and the Notes Verifier first: they keep the open PDF in memory.

--rebuild (15 October 2026) makes the highlighted corpus afresh: for every study a copy of its PDF is written to
corpus/ppmlcorpus/highlighted/<study folder>/, with the earlier sheet-quote highlights removed and the author's own
highlights kept, and the quotations of the study's current sheet are highlighted in it. The folder's INDEX.csv names
each copy, and the apps (Notes Verifier, Sheet Reviewer, Review Viewer) open the copy where it exists. The study's own
PDF in its folder is never changed by --rebuild. The question titles come from the extraction guide in force
(EXTRACTION-GUIDE-V3-2026-10-15.md).

Usage: notes-verifier/.venv/bin/python notes-verifier/highlight_sheet_quotes.py [--dry-run | --recolour] [key ...]
       notes-verifier/.venv/bin/python notes-verifier/highlight_sheet_quotes.py --rebuild [--dry-run] [key ...]
       notes-verifier/.venv/bin/python notes-verifier/highlight_sheet_quotes.py --self-test
"""
from __future__ import annotations

import argparse
import collections
import csv
import datetime
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
import unicodedata
from pathlib import Path

import pymupdf

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SHEETS = ROOT / 'search-ppml' / 'evidence' / 'sheets'
PAPERS = HERE / 'data' / 'papers.json'
ORIGINALS = HERE / 'originals'
SHEET_RGB = (1.0, 0.89, 0.2)                      # yellow, as the apps' own highlights (the author's choice, 12 Oct 2026)
TITLE = 'Evidence sheet'
TAG = 'sheet-quote '                              # + fingerprint, in the annotation's subject
QUESTIONS = {'P1': 'System, setting and tiers', 'P2': 'Privacy', 'P3': 'Ledger', 'P4': 'Checking', 'P5': 'Threats',
             'P6': 'Evaluation', 'P7': "Regulation and the ledger's data", 'P8': 'Limitations',
             'S1': 'Scope and method', 'S2': 'The five layers', 'S3': 'Privacy mechanisms covered',
             'S4': "The review's angles", 'S5': 'Regulation', 'S6': 'What it concludes',
             'S7': 'Open issues and future directions', 'S8': 'Limitations of the survey'}
GUIDE = ROOT / 'search-ppml' / 'evidence' / 'EXTRACTION-GUIDE-V3-2026-10-15.md'
HIGHLIGHTED = ROOT / 'corpus' / 'ppmlcorpus' / 'highlighted'
INCLUDED_INDEX = ROOT / 'corpus' / 'ppmlcorpus' / 'included' / 'INDEX.csv'


def question_titles():
    """the question titles of the extraction guide in force, over the earlier form's"""
    titles = dict(QUESTIONS)
    if GUIDE.exists():
        for m in re.finditer(r'^\| ([PS]\d+[a-z]?) \| \*\*(.+?)\*\*', GUIDE.read_text(encoding='utf-8'), re.M):
            titles[m.group(1)] = m.group(2).rstrip('.')
    return titles


QUESTIONS = question_titles()


def squash(text):
    return re.sub(r'[^0-9a-z]', '', unicodedata.normalize('NFKC', text).lower())


def fingerprint(page, quote):
    return hashlib.sha1(f'{page}\x00{squash(quote)}'.encode()).hexdigest()[:16]


def locate(page, quote):
    """The line rectangles of the first place where the whole quotation stands on the page, or []."""
    target = squash(quote)
    if len(target) < 12:                                  # too short to be sure where it is
        return []
    words = page.get_text('words')
    text, owner = [], []
    for k, w in enumerate(words):
        s = squash(w[4])
        text.append(s)
        owner += [k] * len(s)
    joined = ''.join(text)
    at = joined.find(target)
    if at < 0:
        return []
    first, last = owner[at], owner[at + len(target) - 1]
    lines = collections.OrderedDict()
    for w in words[first:last + 1]:
        r = pymupdf.Rect(w[:4])
        k = (w[5], w[6])
        lines[k] = lines[k] | r if k in lines else r
    return list(lines.values())


def existing(page):
    return {(a.info.get('subject') or '')[len(TAG):] for a in page.annots(types=[pymupdf.PDF_ANNOT_HIGHLIGHT])
            if (a.info.get('subject') or '').startswith(TAG)}


def keep_original(key, path):
    dest = ORIGINALS / key / path.name
    if not dest.exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, dest)


def save(doc, path):
    try:
        if doc.can_save_incrementally():
            doc.save(doc.name, incremental=True, encryption=pymupdf.PDF_ENCRYPT_KEEP)
            return
    except Exception:
        pass
    fd, tmp = tempfile.mkstemp(prefix='.' + path.name + '.', suffix='.pdf', dir=str(path.parent))
    os.close(fd)
    doc.save(tmp, garbage=1, deflate=True)
    doc.close()
    os.replace(tmp, path)


def strip_sheet_highlights(doc):
    """remove the sheet-quote highlights (never the author's own); returns how many"""
    n = 0
    for page in doc:
        for a in list(page.annots(types=[pymupdf.PDF_ANNOT_HIGHLIGHT])):
            if (a.info.get('subject') or '').startswith(TAG):
                page.delete_annot(a)
                n += 1
    return n


def highlight_study(key, sheet, pdf_path, dry_run=False, originals=None, strip=False, by_answer=None):
    """Counts for one study: quotations, highlighted now, already highlighted, not certain (left alone).
    strip: remove the earlier sheet-quote highlights first (a rebuild). by_answer: a Counter to fill with the quotations
    not certain, per answer key."""
    count = collections.Counter()
    doc = pymupdf.open(pdf_path)
    added = 0
    if strip:
        count['removed'] = strip_sheet_highlights(doc)
        added += count['removed'] if not dry_run else 0
    for q, ans in sheet['answers'].items():
        for ev in ans.get('evidence') or []:
            quote, page_no = str(ev.get('quote') or ''), ev.get('page')
            count['quotations'] += 1
            if not isinstance(page_no, int) or not 1 <= page_no <= doc.page_count:
                count['not certain'] += 1
                continue
            page = doc[page_no - 1]
            fp = fingerprint(page_no, quote)
            if fp in existing(page):
                count['already highlighted'] += 1
                continue
            rects = locate(page, quote)
            if not rects:
                count['not certain'] += 1
                if by_answer is not None:
                    by_answer[q] += 1
                continue
            count['highlighted now'] += 1
            if dry_run:
                continue
            annot = page.add_highlight_annot(rects)
            annot.set_colors(stroke=SHEET_RGB)
            annot.set_info(title=TITLE, subject=TAG + fp, content=f'{q} — {QUESTIONS.get(q, "")}')
            annot.update()
            added += 1
    if added:
        (originals or keep_original)(key, pdf_path)
        save(doc, pdf_path)
    if not doc.is_closed:
        doc.close()
    return count


def rebuild(keys, papers, dry_run):
    """the highlighted corpus afresh: a copy of each study's PDF (from its own folder) in HIGHLIGHTED/<study folder>/,
    the earlier sheet-quote highlights removed, the current sheet's quotations highlighted; INDEX.csv and README.md"""
    folders = {r['corpus_id']: r for r in csv.DictReader(INCLUDED_INDEX.open(encoding='utf-8'))}
    rows, total, log = [], collections.Counter(), {}
    for key in keys:
        sheet = json.loads((SHEETS / f'{key}.json').read_text(encoding='utf-8'))
        src = ROOT / papers[key]['pdf']
        if HIGHLIGHTED in src.parents or key in folders:          # the study's own PDF, never an earlier copy
            src = next((ROOT / folders[key]['folder']).glob('*.pdf'))
        dest = HIGHLIGHTED / Path(folders[key]['folder']).name / src.name
        if not dry_run:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
        by_answer = collections.Counter()
        c = highlight_study(key, sheet, dest if not dry_run else src, dry_run=dry_run, originals=lambda k, p: None,
                            strip=True, by_answer=by_answer)
        total.update(c)
        rows.append({'corpus_id': key, 'kind': sheet.get('kind', ''), 'folder': str(dest.parent.relative_to(ROOT)),
                     'pdf': str(dest.relative_to(ROOT)), 'quotations': c['quotations'], 'highlighted': c['highlighted now'],
                     'not_certain': c['not certain']})
        log[key] = {'quotations': c['quotations'], 'highlighted': c['highlighted now'], 'not_certain': c['not certain'],
                    'not_certain_by_answer': dict(by_answer), 'earlier_highlights_removed': c['removed']}
        print(f"{key}: {c['quotations']} quotations · highlighted {c['highlighted now']} · not certain {c['not certain']} "
              f"· earlier sheet highlights removed {c['removed']}", flush=True)
    if not dry_run:
        with open(HIGHLIGHTED / 'INDEX.csv', 'w', encoding='utf-8', newline='') as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
        (HIGHLIGHTED / f'HIGHLIGHT-LOG-{datetime.date.today().isoformat()}.json').write_text(
            json.dumps({'made_on': datetime.datetime.now().isoformat(timespec='seconds'), 'studies': log}, indent=1), encoding='utf-8')
        (HIGHLIGHTED / 'README.md').write_text(
            '# The highlighted corpus\n\n'
            f'{len(rows)} studies, one folder each named as in corpus/ppmlcorpus/included/: a copy of the study\'s PDF in which '
            'every quotation of its current evidence sheet (search-ppml/evidence/sheets/) is a yellow highlight titled '
            '"Evidence sheet" with the answer it belongs to (P1b, S4, …), and the author\'s own highlights are kept. The Notes '
            'Verifier, the Sheet Reviewer and the Review Viewer open these copies (INDEX.csv); the untouched PDF stays in the '
            'study\'s own folder. Made and remade by notes-verifier/highlight_sheet_quotes.py --rebuild; the log file beside '
            'this README counts, per study, the quotations highlighted and those not found with certainty.\n', encoding='utf-8')
    print(f"\n{len(keys)} studies · {total['quotations']} quotations · highlighted {total['highlighted now']} · not certain "
          f"{total['not certain']} · earlier sheet highlights removed {total['removed']}"
          + ('  (dry run: nothing written)' if dry_run else f'  -> {HIGHLIGHTED.relative_to(ROOT)}/'))


def recolour(key, pdf_path):
    """Give the study's existing sheet highlights the current colour; returns how many changed."""
    doc = pymupdf.open(pdf_path)
    changed = 0
    for page in doc:
        for a in page.annots(types=[pymupdf.PDF_ANNOT_HIGHLIGHT]):
            if (a.info.get('subject') or '').startswith(TAG) and \
                    tuple(round(c, 2) for c in a.colors.get('stroke') or ()) != SHEET_RGB:
                a.set_colors(stroke=SHEET_RGB)
                a.update()
                changed += 1
    if changed:
        save(doc, pdf_path)
    if not doc.is_closed:
        doc.close()
    return changed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--recolour', action='store_true')
    ap.add_argument('--rebuild', action='store_true')
    ap.add_argument('--self-test', action='store_true')
    ap.add_argument('keys', nargs='*')
    a = ap.parse_args()
    if a.self_test:
        sys.exit(self_test())
    papers = {p['key']: p for p in json.loads(PAPERS.read_text(encoding='utf-8'))['papers']}
    keys = a.keys or sorted(p.stem for p in SHEETS.glob('*.json'))
    total = collections.Counter()
    if a.rebuild:
        rebuild(keys, papers, a.dry_run)
        return
    if a.recolour:
        n = sum(recolour(key, ROOT / papers[key]['pdf']) for key in keys)
        print(f'{len(keys)} studies · sheet highlights given the colour {SHEET_RGB}: {n}')
        return
    for key in keys:
        sheet = json.loads((SHEETS / f'{key}.json').read_text(encoding='utf-8'))
        pdf = ROOT / papers[key]['pdf']
        c = highlight_study(key, sheet, pdf, dry_run=a.dry_run)
        total.update(c)
        print(f"{key}: {c['quotations']} quotations · highlighted now {c['highlighted now']} · already "
              f"{c['already highlighted']} · not certain {c['not certain']}", flush=True)
    print(f"\n{len(keys)} studies · {total['quotations']} quotations · highlighted now {total['highlighted now']} · "
          f"already {total['already highlighted']} · not certain (left unhighlighted) {total['not certain']}"
          + ('  (dry run: nothing written)' if a.dry_run else ''))


def self_test():
    """On a generated PDF (never a real paper): finds a two-line, hyphenated, ligature quotation; refuses a partial one;
    keeps the original; a second run adds nothing."""
    ok = True

    def check(label, cond):
        nonlocal ok
        ok &= bool(cond)
        print(('PASS ' if cond else 'FAIL ') + label)

    home = Path(tempfile.mkdtemp(prefix='.selftest-hl-', dir=str(HERE)))
    try:
        path = home / 'demo.pdf'
        doc = pymupdf.open()
        page = doc.new_page()
        page.insert_text((72, 100), 'The ledger is a consortium chain run by the edge servers of the pri-', fontsize=11)
        page.insert_text((72, 115), 'vacy preserving operators, and it records only the hashes of updates.', fontsize=11)
        page.insert_text((72, 160), 'An unrelated sentence about something else entirely.', fontsize=11)
        doc.new_page().insert_text((72, 100), 'Second page.', fontsize=11)
        doc.save(path)
        doc.close()
        sheet = {'answers': {'P3': {'evidence': [
            {'page': 1, 'quote': 'edge servers of the privacy-preserving operators, and it records only the hashes'},
            {'page': 1, 'quote': 'the edge servers record full model updates on the chain'},
            {'page': 2, 'quote': 'consortium chain run by the edge servers'}]}}}
        kept = []
        c = highlight_study('demo', sheet, path, originals=lambda k, p: (kept.append(p), shutil.copy2(p, home / 'orig.pdf')))
        check('a quotation across a line break and a hyphen is highlighted', c['highlighted now'] == 1)
        check('a quotation not on its page is left alone', c['not certain'] == 2)
        check('the original is kept before the first change', kept and (home / 'orig.pdf').exists()
              and sum(1 for pg in pymupdf.open(home / 'orig.pdf') for _ in pg.annots()) == 0)
        d = pymupdf.open(path)
        first_page = d[0]                                   # the annotations live only as long as their page object
        annots = list(first_page.annots(types=[pymupdf.PDF_ANNOT_HIGHLIGHT]))
        check('one yellow highlight on page 1, titled "Evidence sheet" with the question',
              len(annots) == 1 and annots[0].info['title'] == TITLE and annots[0].info['content'].startswith('P3')
              and tuple(round(x, 2) for x in annots[0].colors['stroke']) == SHEET_RGB)
        covered = first_page.get_textbox(annots[0].rect)
        check('… covering both lines of the quotation', 'edge servers' in covered and 'hashes' in covered)
        check('… and not the unrelated sentence', 'unrelated' not in covered)
        d.close()
        c2 = highlight_study('demo', sheet, path, originals=lambda k, p: None)
        check('a second run adds nothing', c2['highlighted now'] == 0 and c2['already highlighted'] == 1)
    finally:
        shutil.rmtree(home, ignore_errors=True)
    print('ALL PASS' if ok else 'SOME CHECKS FAILED')
    return 0 if ok else 1


if __name__ == '__main__':
    main()
