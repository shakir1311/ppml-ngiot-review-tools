#!/usr/bin/env python3
"""Shared helpers of the design evaluation: the list of the 45 designs, their folders, and recorded web requests.

Every request made for the evaluation goes through `fetch()`, which saves the response (with abstract and summary fields
removed, so no paper text is kept) under the design's `evidence/raw/` and appends one line to `evidence/log.jsonl`: time,
URL, status, size and SHA-256 of the body as received. The designs are the primary studies of the review
(corpus/ppmlcorpus/included/INDEX.csv), with the DOI from myliteraturereviewpaper/ppml2026/refs.json and the extraction
answer P3 from search-ppml/evidence/sheets/<id>.json.

Usage: imported by the other scripts of scripts/design_eval/.
"""
import csv, datetime, hashlib, json, pathlib, re, subprocess, time

ROOT = pathlib.Path(__file__).resolve().parents[2]
EVAL = ROOT / 'design-evaluation'
DESIGNS = EVAL / 'designs'
UA = 'design-eval/1.0 (academic research; reproducibility study)'

# fields that can carry a paper's own text (abstracts, summaries); removed before anything is saved or printed
TEXT_FIELDS = {'abstract', 'abstract_inverted_index', 'summary', 'ai_summary', 'ai_keywords', 'abstractText',
               'fullText', 'full_text', 'tldr'}


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds')


def strip_text(obj):
    """Return a copy of a JSON value with every abstract- or summary-like field removed, at any depth."""
    if isinstance(obj, dict):
        return {k: strip_text(v) for k, v in obj.items() if k not in TEXT_FIELDS}
    if isinstance(obj, list):
        return [strip_text(v) for v in obj]
    return obj


def slug(text, n=40):
    s = re.sub(r'[^A-Za-z0-9]+', '-', text).strip('-')
    return s[:n].rstrip('-')


def acronym(title):
    """The design's own short name when the title starts with one ("PrSeFL: ..."), else ''."""
    m = re.match(r'^\s*([A-Za-z][A-Za-z0-9\-]{2,24}):\s', title)
    return m.group(1) if m and sum(c.isupper() for c in m.group(1)) >= 2 else ''


def load_designs():
    """The 45 designs, each with id, title, year, first author, DOI, paper folder, sheet values and design folder."""
    refs = json.load(open(ROOT / 'myliteraturereviewpaper' / 'ppml2026' / 'refs.json'))
    out = []
    for r in csv.DictReader(open(ROOT / 'corpus' / 'ppmlcorpus' / 'included' / 'INDEX.csv')):
        if r['kind'] != 'primary':
            continue
        sheet = json.load(open(ROOT / 'search-ppml' / 'evidence' / 'sheets' / f"{r['corpus_id']}.json"))
        acr = acronym(r['title'])
        name = '-'.join(x for x in (r['corpus_id'], slug(r['first_author'], 20), r['year'], acr) if x)
        out.append({
            'id': r['corpus_id'], 'title': r['title'], 'year': r['year'], 'first_author': r['first_author'],
            'acronym': acr, 'doi': refs[r['corpus_id']]['doi'], 'reference': refs[r['corpus_id']]['ieee'],
            'paper_folder': r['folder'], 'folder': DESIGNS / name,
            'sheet_p3': {k: sheet['answers']['P3']['values'].get(k) for k in ('code', 'datasets', 'environment', 'scale')},
        })
    return sorted(out, key=lambda d: d['id'].lower())


def design(design_id):
    for d in load_designs():
        if d['id'] == design_id:
            return d
    raise SystemExit(f'unknown design {design_id}')


def page_texts(paper_folder):
    """The paper's pages as [(number, path)], each page from text/pages/ or, where the extraction recovered the page by
    OCR (text/pages_ocr/), from whichever of the two holds more letters."""
    base = ROOT / paper_folder / 'text'
    out = []
    for p in sorted((base / 'pages').glob('page_*.txt')):
        q = base / 'pages_ocr' / p.name
        if q.exists():
            letters = lambda f: sum(ch.isalpha() for ch in f.read_text(errors='replace'))
            p = q if letters(q) > letters(p) else p
        out.append((int(p.stem.split('_')[1]), p))
    return out


def save_json(path, obj):
    path = pathlib.Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=1, ensure_ascii=False) + '\n')


def github_token():
    return subprocess.run(['gh', 'auth', 'token'], capture_output=True, text=True).stdout.strip()


class Recorder:
    """Makes and records the web requests of one design: raw responses under evidence/raw/, one log line per request."""

    def __init__(self, d, pause=1.0):
        import requests
        self.requests = requests
        self.d = d
        self.raw = d['folder'] / 'evidence' / 'raw'
        self.raw.mkdir(parents=True, exist_ok=True)
        self.log = d['folder'] / 'evidence' / 'log.jsonl'
        self.pause = pause
        self.n = len(list(self.raw.glob('*'))) if self.raw.exists() else 0
        self._gh = None

    def fetch(self, label, url, github=False, params=None, timeout=60, retries=3, accept=None, links_only=False,
              transform=None):
        """GET a URL; return (status, parsed JSON or text). The body is saved stripped of text fields; with
        links_only (for HTML pages that may carry a paper's text) only the page's links are saved and returned;
        transform(text) -> JSON value replaces a text body (e.g. an arXiv feed without its abstracts)."""
        headers = {'User-Agent': UA}
        if accept:
            headers['Accept'] = accept
        if github:
            if self._gh is None:
                self._gh = github_token()
            headers['Authorization'] = f'Bearer {self._gh}'
            headers.setdefault('Accept', 'application/vnd.github+json')
        status, body, err = None, b'', None
        for attempt in range(retries):
            try:
                r = self.requests.get(url, params=params, headers=headers, timeout=timeout)
                status, body = r.status_code, r.content
                if github and status in (403, 429) and 'rate limit' in r.text.lower():
                    reset = int(r.headers.get('X-RateLimit-Reset', time.time() + 60))
                    time.sleep(max(5, reset - time.time() + 2))
                    continue
                if status >= 500:
                    time.sleep(5 * (attempt + 1))
                    continue
                break
            except Exception as e:                       # network errors are recorded, not raised
                err = repr(e)
                time.sleep(5 * (attempt + 1))
        final_url = r.url if status is not None else url
        try:
            parsed = strip_text(json.loads(body)) if body else None
            kind = 'json'
        except Exception:
            parsed, kind = body.decode('utf-8', 'replace'), 'text'
        if links_only and kind == 'text':
            parsed = sorted(set(re.findall(r'''href=["']([^"'#]+)["']''', parsed)))
            kind = 'json'
        elif transform and kind == 'text':
            parsed, kind = transform(parsed), 'json'
        self.n += 1
        fname = f"{self.n:03d}-{slug(label, 50)}.{ 'json' if kind == 'json' else 'txt'}"
        if kind == 'json':
            save_json(self.raw / fname, parsed)
        else:
            (self.raw / fname).write_text(parsed)
        with open(self.log, 'a') as f:
            f.write(json.dumps({'time': now(), 'label': label, 'url': final_url, 'params': params, 'status': status,
                                'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest(), 'saved': f'raw/{fname}',
                                'error': err}) + '\n')
        time.sleep(self.pause)
        return status, parsed
