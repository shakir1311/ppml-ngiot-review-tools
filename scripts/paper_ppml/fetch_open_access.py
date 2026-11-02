#!/usr/bin/env python3
"""Fetch the open-access published versions of the full texts that the full second screening needs (rescreen.py), so
that the author downloads only what is not openly available.

For every record flagged for full text that the corpus does not hold, OpenAlex (api.openalex.org, by DOI; no e-mail or
other personal data is sent) lists the copies of the work. Only a copy that OpenAlex labels "publishedVersion" with a PDF
link is used — never a preprint, a submitted or an accepted manuscript. The PDF is fetched, must start with %PDF and must
carry the record's title on its first two pages; it is then filed as corpus/ppmlcorpus/check/p<record>/p<record>.pdf with
PROVENANCE.json (source URL, OpenAlex id, open-access status and licence, SHA-256, time) and extracted with
extract_paper.py and ocr_scanned.py. Every lookup and every attempt, with its outcome, is written to
search-ppml/evidence/rescreen/OPEN-ACCESS-2026-10-05.json; a record already filed is skipped, so the script can be rerun.

Usage: scripts/.venv/bin/python scripts/paper_ppml/fetch_open_access.py [how-many]     (a first few as a test; default all)
"""
import csv, datetime, hashlib, json, pathlib, re, subprocess, sys, time, unicodedata, urllib.parse
import pymupdf

csv.field_size_limit(10 ** 9)
ROOT = pathlib.Path(__file__).resolve().parents[2]
RS = ROOT / 'search-ppml' / 'evidence' / 'rescreen'
CHECK = ROOT / 'corpus' / 'ppmlcorpus' / 'check'
PY = ROOT / 'scripts' / '.venv' / 'bin' / 'python'
LOG = RS / 'OPEN-ACCESS-2026-10-05.json'
UA = 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15'


def norm(s):
    return re.sub(r'[^a-z0-9]+', '', unicodedata.normalize('NFKC', s or '').lower())


def sha(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


def curl(url, out=None, timeout=60):
    cmd = ['curl', '-sSL', '-m', str(timeout), '-A', UA, url]
    if out:
        cmd += ['-o', str(out)]
    r = subprocess.run(cmd, capture_output=True, timeout=timeout + 10)
    return r.returncode, r.stdout


def openalex(doi):
    code, body = curl('https://api.openalex.org/works/doi:' + urllib.parse.quote(doi, safe='/:'), timeout=30)
    if code:
        return None
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        return None


def main():
    recs = [r for r in csv.DictReader(open(RS / 'RESCREEN-DECISIONS-2026-10-05.csv', encoding='utf-8'))
            if r['full_text_needed'] and not r['corpus_folder']]
    if len(sys.argv) > 1:
        recs = recs[:int(sys.argv[1])]
    log = json.loads(LOG.read_text(encoding='utf-8')) if LOG.exists() else {}
    got = 0
    for r in recs:
        n, pid = r['n'], f"p{int(r['n']):04d}"
        if (CHECK / pid / f'{pid}.pdf').exists():
            continue
        w = openalex(r['doi'])
        time.sleep(0.2)
        entry = {'doi': r['doi'], 'title': r['title'], 'checked_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds')}
        if not w:
            entry['outcome'] = 'not found in OpenAlex'
            log[n] = entry
            continue
        entry.update({'openalex': w.get('id'), 'oa_status': (w.get('open_access') or {}).get('oa_status'), 'attempts': []})
        pub = [l for l in w.get('locations') or [] if l.get('version') == 'publishedVersion' and l.get('pdf_url')]
        if not pub:
            entry['outcome'] = 'no open-access published PDF listed'
            log[n] = entry
            continue
        dest = CHECK / pid
        for loc in pub:
            url = loc['pdf_url']
            tmp = RS / f'_fetch-{pid}.pdf'
            code, _ = curl(url, tmp)
            ok, why = False, ''
            if code or not tmp.exists() or tmp.read_bytes()[:4] != b'%PDF':
                why = 'not a PDF (blocked or a web page)'
            else:
                try:
                    doc = pymupdf.open(tmp)
                    first = norm(''.join(doc[i].get_text() for i in range(min(2, doc.page_count))))
                    ok = norm(r['title'])[:40] in first
                    why = '' if ok else 'title not on the first pages'
                except Exception as ex:                       # noqa: BLE001
                    why = f'unreadable PDF ({type(ex).__name__})'
            entry['attempts'].append({'url': url, 'source': (loc.get('source') or {}).get('display_name'), 'license': loc.get('license'),
                                      'result': 'filed' if ok else why})
            if ok:
                dest.mkdir(parents=True, exist_ok=True)
                out = dest / f'{pid}.pdf'
                tmp.replace(out)
                prov = {'id': pid, 'record': int(n), 'doi': r['doi'], 'title': r['title'],
                        'role': 'full text sought after the full second screening',
                        'how': 'open-access published version fetched by Claude Code (scripts/paper_ppml/fetch_open_access.py)',
                        'source_url': url, 'source': (loc.get('source') or {}).get('display_name'), 'version': 'publishedVersion',
                        'license': loc.get('license'), 'oa_status': entry['oa_status'], 'openalex': w.get('id'),
                        'file': out.name, 'sha256': sha(out), 'pages': pymupdf.open(out).page_count,
                        'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds')}
                (dest / 'PROVENANCE.json').write_text(json.dumps(prov, indent=1, ensure_ascii=False), encoding='utf-8')
                subprocess.run([str(PY), str(ROOT / 'scripts' / 'extract_paper.py'), str(out), '--quiet'], check=False)
                subprocess.run([str(PY), str(ROOT / 'scripts' / 'ocr_scanned.py'), str(dest)], check=False, capture_output=True)
                got += 1
                break
            if tmp.exists():
                tmp.unlink()
            time.sleep(1)
        entry['outcome'] = 'filed' if (dest / f'{pid}.pdf').exists() else 'open-access copy listed but not fetched'
        log[n] = entry
        LOG.write_text(json.dumps(log, indent=1, ensure_ascii=False), encoding='utf-8')
    LOG.write_text(json.dumps(log, indent=1, ensure_ascii=False), encoding='utf-8')
    import collections
    print(f'filed now: {got}', dict(collections.Counter(v['outcome'] for v in log.values())))


if __name__ == '__main__':
    main()
