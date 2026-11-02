#!/usr/bin/env python3
"""Licence check of the works cited in a version of the PPML review: what licence does the copy we read carry?

Only the works in the paper's reference list are checked (ppml2026/refs.json, which build.py prints as the reference
list; the caller confirms the two agree). For each work it records:

  1. The copy held in the workspace (the PDF that was read, and for studies replaced by their published version,
     both copies): every page is searched for a licence statement — Creative Commons wording, an "open access article
     distributed under …" sentence, or a publisher's reservation of rights ("All rights reserved", IEEE's "requires IEEE
     permission", Springer's "exclusive licence", ACM's "Publication rights licensed to ACM") — and the first match of
     each kind is kept with its page and the surrounding words, so a person can confirm it against the PDF.
  2. A second witness: OpenAlex (api.openalex.org, looked up by DOI; no e-mail or other personal data is sent) lists the
     open-access status and the licence of each known copy of the work. The raw answer is saved.

This is a licence lookup, not a search for studies. Nothing is decided here: the result is a record for the Library.

Writes search-ppml/evidence/licences/LICENCES-V<n>-<date>.csv and openalex/<key>.json; prints a summary.
Usage: scripts/.venv/bin/python scripts/paper_ppml/licence_check.py <version>        e.g. 42
"""
import csv, datetime, json, pathlib, re, subprocess, sys, time, unicodedata, urllib.parse

ROOT = pathlib.Path(__file__).resolve().parents[2]
REFS = ROOT / 'myliteraturereviewpaper' / 'ppml2026' / 'refs.json'
INDEX = ROOT / 'search-ppml' / 'CORPUS-INDEX-2026-10-04.csv'
PUBLISHED = ROOT / 'search-ppml' / 'evidence' / 'PUBLISHED-VERSIONS.json'
OUT = ROOT / 'search-ppml' / 'evidence' / 'licences'

CC = re.compile(r'creative\s*commons|\bCC[\s-]?BY\b|\bCC0\b|open access article (?:distributed )?under|'
                r'distributed under the terms (?:and conditions )?of the', re.I)
RESERVED = re.compile(r'all rights (?:are )?reserved|requires IEEE permission|personal use is permitted|'
                      r'under exclusive licen[cs]e|publication rights licensed to ACM|exclusive licensee', re.I)
TDM_AI = re.compile(r'text and data mining,? (?:and )?AI training|AI training,? and similar technologies|'
                    r'text and data mining,? and training of artificial intelligence|'
                    r'(?:not|nor) (?:be )?used (?:for|to) (?:train|training)', re.I)
LIBRARY = re.compile(r'Authori[sz]ed licensed use limited to:?\s*([^.]{3,60}?)\s*\.\s*Downloaded|'
                     r'Downloaded from https?://\S*onlinelibrary\.wiley\.com\S* by (.{3,60}?), Wiley Online Library', re.I)
NOT_A_LICENCE = re.compile(r'OA articles are governed by the applicable Creative Commons', re.I)   # Wiley's download footer
CIRCLED_C = 'c' + chr(0x20DD)          # IEEE's PDFs set the copyright sign as c + combining enclosing circle
COPYRIGHT = re.compile(r'(?:©|' + CIRCLED_C + r'|\(c\)|copyright)\s*(?:©\s*)?((?:19|20)\d{2})\s*,?\s*([^.;|]{2,70})',
                       re.I)
ARXIV = re.compile(r'arXiv:\s?\d{4}\.\d{4,5}(?:v\d+)?')
VARIANT_WINDOW = 400


def flat(text):
    """One line of text with ligatures unfolded (NFKC: 'artiﬁcial' -> 'artificial')."""
    return re.sub(r'\s+', ' ', unicodedata.normalize('NFKC', text)).strip()


def cc_variant(snippet):
    s = snippet.lower()
    if re.search(r'\bcc0\b|public domain dedication', s):
        return 'CC0'
    parts = ['BY']
    if re.search(r'non-?commercial|\bnc\b', s):
        parts.append('NC')
    if re.search(r'no-?deriv|noderiv|\bnd\b', s):
        parts.append('ND')
    if re.search(r'share-?alike|\bsa\b', s):
        parts.append('SA')
    return 'CC ' + '-'.join(parts)


def scan(folder):
    """First Creative Commons statement, first reservation of rights, and an arXiv stamp, with page and context."""
    found = {}
    pages = sorted((folder / 'text' / 'pages').glob('page_*.txt'))
    for page in pages:
        n = int(page.stem.split('_')[1])
        text = flat(page.read_text(errors='ignore'))
        for kind, rx in (('cc', CC), ('reserved', RESERVED), ('tdm_ai', TDM_AI), ('library', LIBRARY),
                         ('copyright', COPYRIGHT)):
            if kind in found:
                continue
            for m in rx.finditer(text):
                a, b = max(0, m.start() - 120), min(len(text), m.end() + VARIANT_WINDOW)
                if kind == 'cc' and NOT_A_LICENCE.search(text[a:b]):
                    continue
                found[kind] = {'page': n, 'context': text[a:b],
                               'match': next((g for g in m.groups() if g), m.group(0)) if m.groups() else m.group(0),
                               'whole': m.group(0)}
                break
        if n == 1 and 'arxiv' not in found:
            m = ARXIV.search(text)
            if m:
                found['arxiv'] = {'page': 1, 'context': m.group(0)}
    found['pages'] = len(pages)
    return found


def openalex(key, doi):
    path = OUT / 'openalex' / f'{key}.json'
    if not path.exists():
        url = 'https://api.openalex.org/works/doi:' + urllib.parse.quote(doi, safe='/')
        r = subprocess.run(['curl', '-sS', '-m', '60', url], capture_output=True, timeout=80)
        try:
            data = json.loads(r.stdout)
        except json.JSONDecodeError:
            data = {'error': r.stdout.decode(errors='ignore')[:300] or r.stderr.decode(errors='ignore')[:300]}
        data['_retrieved_utc'] = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
        data['_url'] = url
        path.write_text(json.dumps(data, indent=1))
        time.sleep(0.2)
    data = json.loads(path.read_text())
    if 'error' in data or 'id' not in data:
        return {'oa_status': 'lookup failed', 'licences': ''}
    locs = []
    for loc in data.get('locations') or []:
        src = (loc.get('source') or {}).get('display_name') or ''
        if loc.get('license') or loc.get('is_oa'):
            locs.append(f"{loc.get('license') or 'no licence'} ({loc.get('version') or '?'}; {src[:40]})")
    oa = data.get('open_access') or {}
    return {'oa_status': oa.get('oa_status') or '', 'licences': ' | '.join(locs)}


def main():
    version = sys.argv[1] if len(sys.argv) > 1 else '42'
    refs = json.loads(REFS.read_text())
    index = {row['id']: row for row in csv.DictReader(INDEX.open())}
    published = {k: v for k, v in json.loads(PUBLISHED.read_text()).items() if k != 'about'}
    (OUT / 'openalex').mkdir(parents=True, exist_ok=True)

    rows = []
    for key, ref in refs.items():
        copies = []
        if ref.get('folder'):
            copies.append(('held', ROOT / ref['folder']))
        else:
            copies.append(('held', (ROOT / index[ref['corpus_id']]['pdf']).parent))
        if ref.get('corpus_id') in published:
            copies.append(('published version', ROOT / published[ref['corpus_id']]))
        witness = openalex(key, ref['doi']) if ref.get('doi') else {'oa_status': 'no DOI', 'licences': ''}
        for which, folder in copies:
            found = scan(folder)
            cc = found.get('cc')
            rows.append({
                'key': key, 'role': ref.get('role', ''), 'doi': ref.get('doi', ''), 'copy': which,
                'folder': str(folder.relative_to(ROOT)), 'pages': found['pages'],
                'cc_licence': cc_variant(cc['context']) if cc else '',
                'cc_page': cc['page'] if cc else '', 'cc_context': cc['context'] if cc else '',
                'reserved_page': found['reserved']['page'] if 'reserved' in found else '',
                'reserved_context': found['reserved']['context'][:260] if 'reserved' in found else '',
                'tdm_ai_reserved': found['tdm_ai']['context'][:200] if 'tdm_ai' in found else '',
                'library_licence': found['library']['match'].strip() if 'library' in found else '',
                'copyright_line': found['copyright']['whole'].strip() if 'copyright' in found else '',
                'arxiv': found['arxiv']['context'] if 'arxiv' in found else '',
                'openalex_oa_status': witness['oa_status'], 'openalex_licences': witness['licences'],
                'reference': ref.get('ieee', ''),
            })

    out = OUT / f'LICENCES-V{version}-{datetime.date.today().isoformat()}.csv'
    with out.open('w', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    held = [r for r in rows if r['copy'] == 'held']
    print(f'{len(refs)} cited works, {len(rows)} copies checked -> {out.relative_to(ROOT)}')
    print('held copies with a Creative Commons statement:', sum(1 for r in held if r['cc_licence']))
    print('held copies with a reservation of rights only:', sum(1 for r in held if not r['cc_licence'] and r['reserved_page']))
    print('held copies with neither:', sum(1 for r in held if not r['cc_licence'] and not r['reserved_page']))
    print('held copies reserving text and data mining / AI training:', sum(1 for r in held if r['tdm_ai_reserved']))
    print('held copies stamped as licensed to a library:', sum(1 for r in held if r['library_licence']))


if __name__ == '__main__':
    main()
