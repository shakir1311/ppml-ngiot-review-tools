#!/usr/bin/env python3
"""Check every entry of the PPML review's reference list (myliteraturereviewpaper/ppml2026/refs.json) against the
metadata its DOI has at Crossref: first author's family name, title, year, venue, volume, issue and pages or article
number. Only bibliographic metadata is fetched; no paper is read. Nothing in refs.json is changed.

Writes search-ppml/evidence/refs-check/CROSSREF-<date>.json (every Crossref record as fetched, so the check can be redone
offline) and REFS-CHECK-<date>.json (per reference: the fields that differ). Prints a summary.

Usage: python3 scripts/paper_ppml/check_refs_crossref.py [--offline]     (--offline: reuse the saved Crossref records)
"""
import datetime
import difflib
import html
import json
import pathlib
import re
import sys
import time
import unicodedata
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[2]
REFS = ROOT / 'myliteraturereviewpaper' / 'ppml2026' / 'refs.json'
OUT = ROOT / 'search-ppml' / 'evidence' / 'refs-check'
DATE = datetime.date.today().isoformat()


def plain(s):
    s = html.unescape(re.sub(r'<[^>]+>', '', str(s or '')))
    s = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode()
    return re.sub(r'[^a-z0-9 ]+', ' ', s.lower()).split()


def similar(a, b):
    return difflib.SequenceMatcher(None, ' '.join(plain(a)), ' '.join(plain(b))).ratio()


def fetch(doi):
    url = 'https://api.crossref.org/works/' + urllib.parse.quote(doi)
    req = urllib.request.Request(url, headers={'User-Agent': 'ppml-review-reference-check/1.0'})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())['message']


def ieee_parts(s):
    """the fields of our IEEE-style entry: authors, “title,” venue, vol., no., pp./Art. no., year"""
    m = re.match(r'^(.*?), “(.*?),” (.*)$', s)
    if not m:
        return {}
    authors, title, rest = m.groups()
    d = {'authors': authors, 'title': title, 'rest': rest}
    for key, pat in (('volume', r'\bvol\. ([\w-]+)'), ('issue', r'\bno\. ([\w-]+)'), ('pages', r'\bpp\. ([\w–-]+)'),
                     ('article', r'\bArt\. no\. ([\w.-]+)')):
        x = re.search(pat, rest)
        d[key] = x.group(1) if x else ''
    return d


def year_of(m):
    for k in ('published-print', 'published-online', 'issued', 'published'):
        p = (m.get(k) or {}).get('date-parts') or [[None]]
        if p and p[0] and p[0][0]:
            return str(p[0][0])
    return ''


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    refs = json.loads(REFS.read_text(encoding='utf-8'))
    saved = OUT / f'CROSSREF-{DATE}.json'
    cache = json.loads(saved.read_text(encoding='utf-8')) if saved.exists() else {}
    if '--offline' not in sys.argv:
        for k, r in refs.items():
            doi = (r.get('doi') or '').strip()
            if doi and k not in cache:
                try:
                    cache[k] = fetch(doi)
                except Exception as e:                     # recorded, not fatal
                    cache[k] = {'error': f'{type(e).__name__}: {e}'}
                time.sleep(0.3)
        saved.write_text(json.dumps(cache, indent=1, ensure_ascii=False), encoding='utf-8')
    report, n_ok = {}, 0
    for k, r in refs.items():
        doi = (r.get('doi') or '').strip()
        ours = ieee_parts(r.get('ieee', ''))
        if not doi:
            report[k] = {'note': 'no DOI: checked by hand'}
            continue
        m = cache.get(k) or {}
        if 'error' in m or not m:
            report[k] = {'note': 'Crossref: ' + m.get('error', 'no record')}
            continue
        diffs = {}
        cr_title = ' '.join(m.get('title') or [])
        if similar(ours.get('title', ''), cr_title) < 0.9:
            diffs['title'] = [ours.get('title', ''), cr_title]
        au = m.get('author') or []
        first = next((a for a in au if a.get('sequence') == 'first'), au[0] if au else {})
        fam = first.get('family') or first.get('name') or ''
        if plain(fam) and plain(r.get('first_author_surname', '')) != plain(fam):
            diffs['first author'] = [r.get('first_author_surname', ''), f"{first.get('given', '')} {fam}".strip()]
        y = year_of(m)
        if y and str(r.get('year', '')) != y:
            diffs['year'] = [str(r.get('year', '')), y, {k2: ((m.get(k2) or {}).get('date-parts') or [[None]])[0] for k2 in ('published-print', 'published-online', 'issued')}]
        venue = ' '.join(m.get('container-title') or [])
        if venue and similar(ours.get('rest', '').split(', vol.')[0].split(', pp.')[0], venue) < 0.6 and \
                not any(w in ' '.join(plain(ours.get('rest', ''))) for w in [' '.join(plain(venue))]):
            diffs['venue'] = [ours.get('rest', '')[:120], venue]
        for f, cf in (('volume', 'volume'), ('issue', 'issue')):
            if m.get(cf) and ours.get(f) and str(ours[f]) != str(m[cf]):
                diffs[f] = [ours[f], m[cf]]
        pg = (m.get('page') or '').replace('-', '–')
        art = m.get('article-number') or ''
        if pg and ours.get('pages') and ours['pages'].replace('-', '–') != pg:
            diffs['pages'] = [ours['pages'], pg]
        if art and ours.get('article') and ours['article'] != art:
            diffs['article'] = [ours['article'], art]
        if (m.get('type') or '') == 'posted-content':
            diffs['type'] = ['', 'Crossref lists a preprint']
        if diffs:
            report[k] = {'doi': doi, 'differs': diffs}
        else:
            n_ok += 1
    (OUT / f'REFS-CHECK-{DATE}.json').write_text(json.dumps(report, indent=1, ensure_ascii=False), encoding='utf-8')
    print(f'{len(refs)} references: {n_ok} agree with Crossref on every field checked; {len(report)} to look at')
    for k, x in report.items():
        print(f'  {k}: ' + (x.get('note') or '; '.join(f"{f}: ours {v[0]!r} | Crossref {v[1]!r}" for f, v in x['differs'].items()))[:400])


if __name__ == '__main__':
    main()
