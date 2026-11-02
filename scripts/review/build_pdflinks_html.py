#!/usr/bin/env python3
"""Build a reading copy of the review as one HTML file in which every reference [n] links to its PDF in the corpus.

Each in-text [n] becomes a hyperlink to the cited work's PDF (file:// URL), opened at the page of the evidence behind the
citation where it can be settled (resolve()), in this order:
  1. the sentence's own evidence: the page-cited quotation of the study's extraction record that the build marked for
     that sentence (build/LINKS-V<n>.json, written by scripts/paper_ppml/links.py from the sheets);
  2. a citation inside a table built from the records: the sheet answer behind that column (QUESTION_OF_COLUMN: e.g.
     a "SQ3 Ledger checks the updates" column is answer P3, the Studies column of the privacy table is P2);
  3. a distinctive fact of the sentence (a number with a comma or decimal, a long number, a quoted phrase) found on
     exactly one page of the cited paper's extracted text; the EDPB guidelines open at the cited paragraph's page;
  4. the sheet answer whose subject the sentence's wording names (question_by_wording: "ledger", "consensus" -> P3,
     "poisoning", "malicious" -> P5, and so on), else the answer of the section's survey question;
  5. page 1.
The page's quotation and the sheet question travel with the link, so the Review Viewer outlines the quoted words.
The reference-list entries link to page 1. Foundations and laws without a PDF in the corpus are left unlinked.

Where a paper is: PUBLISHED-VERSIONS.json first (a published version replaces the preprint), then the included
studies' own index (corpus/ppmlcorpus/included/INDEX.csv), then the older manifests, then the three foundations.

Usage: scripts/.venv/bin/python scripts/review/build_pdflinks_html.py <in.docx> <out.html>
"""
import csv, json, pathlib, re, subprocess, sys, urllib.parse

ROOT = pathlib.Path(__file__).resolve().parents[2]
SRC = ROOT / 'myliteraturereviewpaper' / '_src' / 'V18'
CORPUS = ROOT / 'corpus'
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import ref_links as RL          # noqa: E402

CITED = json.loads((SRC / 'citations.json').read_text())          # [n] = CITED[n-1]
BY = RL.manifest()


# the three works cited from outside the corpus, each extracted with notes like a corpus paper
EXTRA = {
    'page2021': ROOT / 'foundations' / 'papers' / '2021 - The PRISMA 2020 Statement - An Updated Guideline for Reporting Systematic Reviews (Page)',
    'gdpr2016': ROOT / 'Regulatory' / 'papers' / '2016 - Regulation (EU) 2016-679 General Data Protection Regulation (GDPR)',
    'edpb2026': ROOT / 'Regulatory' / 'papers' / ('2026 - EDPB Guidelines 02-2025 on Processing of Personal Data through '
                                                 'Blockchain Technologies, Version 2.0 (EDPB)'),
}


# the systematic review of 2 October 2026 (series "Verifiable Privacy-Preserving FL on Blockchains - Systematic Review"):
# its own bibliography (keys n####, the search records) and the manifest of its corpus folders
NEW_REFS = json.loads((ROOT / 'myliteraturereviewpaper' / 'slr2026' / 'refs.json').read_text(encoding='utf-8'))
SEARCH_ROWS = list(csv.DictReader(open(CORPUS / 'searchcorpus' / 'MANIFEST-2026-10-02.csv', encoding='utf-8')))
# the PPML review (V29 onwards, series "Privacy Preserving Machine Learning in NextGeneration IoT"): its bibliography is
# keyed by corpus id (myliteraturereviewpaper/ppml2026/refs.json), and every corpus id has its PDF in the corpus index
_PPML_REFS_F = ROOT / 'myliteraturereviewpaper' / 'ppml2026' / 'refs.json'
PPML_REFS = json.loads(_PPML_REFS_F.read_text(encoding='utf-8')) if _PPML_REFS_F.exists() else {}
_PPML_IDX_F = ROOT / 'search-ppml' / 'CORPUS-INDEX-2026-10-04.csv'
PPML_IDX = ({r['id']: (ROOT / r['pdf']).parent for r in csv.DictReader(open(_PPML_IDX_F, encoding='utf-8')) if r.get('pdf')}
            if _PPML_IDX_F.exists() else {})


def _new_folder(key):
    """a key of the new bibliography -> its folder: by its search-record id or DOI in the search manifest, else by its
    corpus id in the corpus manifest (e.g. S014), else a foundation"""
    r = NEW_REFS[key]
    doi = (r.get('doi') or '').lower()
    for row in SEARCH_ROWS:
        if row['id'] == key or (doi and row['doi'].lower() == doi):
            return ROOT / row['folder']
    cid = r.get('corpus_id')
    if cid and cid in BY:
        return CORPUS / BY[cid]['folder']
    return EXTRA.get(key)


_PUB_F = ROOT / 'search-ppml' / 'evidence' / 'PUBLISHED-VERSIONS.json'
PUBLISHED = {k: ROOT / v for k, v in json.loads(_PUB_F.read_text(encoding='utf-8')).items() if k != 'about'} if _PUB_F.exists() else {}


# the studies included in the PPML review, one folder each (scripts/paper_ppml/organise_included.py): the place a study
# is read from, whatever the older manifests say (links at the old places still point here)
_INC_F = CORPUS / 'ppmlcorpus' / 'included' / 'INDEX.csv'
INCLUDED = ({r['corpus_id']: ROOT / r['folder'] for r in csv.DictReader(open(_INC_F, encoding='utf-8'))}
            if _INC_F.exists() else {})


def folder_for(key):
    """the paper folder (PDF, text/, notes/) for a reference key, or None"""
    if key in PUBLISHED:                                     # a published version that replaces the preprint in the corpus
        return PUBLISHED[key]
    if key in INCLUDED and INCLUDED[key].is_dir():           # the included studies' own folder
        return INCLUDED[key]
    if re.fullmatch(r'[NOS]\d{3}', key) and key in BY:
        return CORPUS / BY[key]['folder']
    if key in NEW_REFS:
        return _new_folder(key)
    if key in PPML_REFS and key in PPML_IDX:                 # the PPML review's corpus ids (p####, n####, …)
        return PPML_IDX[key]
    return EXTRA.get(key)


_HL_F = CORPUS / 'ppmlcorpus' / 'highlighted' / 'INDEX.csv'
HIGHLIGHTED = ({r['corpus_id']: ROOT / r['pdf'] for r in csv.DictReader(open(_HL_F, encoding='utf-8'))}
               if _HL_F.exists() else {})                   # the copies with the sheets' quotations highlighted (15 Oct 2026)


def pdf_for(key):
    """the absolute PDF path for a reference key, or None: the highlighted copy where one exists, else the PDF in the
    study's folder (text/, notes/ always come from the folder, folder_for)"""
    h = HIGHLIGHTED.get(key)
    if h and h.exists():
        return h
    f = folder_for(key)
    return next(f.glob('*.pdf'), None) if f and f.exists() else None


def notes_pages(key):
    """{pdf_page: lowercased_text} for the cited paper, from the page-cited statements of its notes/NOTES.md.

    The notes record each fact with its page and a verbatim quotation ('... [p13] "377 and 342 seconds" ...'), checked
    against the paper by check_notes.py. Each [pN] tag owns the text up to the next tag, so a fact sits under the page
    its quotation was recorded on — the pages we captured. The notes can list a fact under more than one page, so a
    number may not be unique here; then find_page falls back to the extracted page text, where it physically appears."""
    if not folder_for(key):
        return {}
    f = folder_for(key) / 'notes' / 'NOTES.md'
    if not f.exists():
        return {}
    t = f.read_text(encoding='utf-8', errors='replace')
    out, marks = {}, list(re.finditer(r'\[p(\d{1,4})(?:,\s*image)?\]', t))
    for i, m in enumerate(marks):
        n = int(m.group(1))
        seg = t[m.end():marks[i + 1].start()] if i + 1 < len(marks) else t[m.end():m.end() + 400]
        out[n] = out.get(n, '') + ' ' + seg.lower()
    return out


def pages_text(key):
    """{pdf_page: lowercased_text} from the paper's already-extracted per-page text (text/pages/page_NNNN.txt); the
    authority for the page a number physically appears on. This is the same extracted text the notes were built from,
    not a fresh read of the PDF or its images."""
    if not folder_for(key):
        return {}
    d = folder_for(key) / 'text' / 'pages'
    return {int(re.search(r'(\d+)', f.name).group(1)): f.read_text(encoding='utf-8', errors='replace').lower()
            for f in sorted(d.glob('page_*.txt'))}


SHEETS = ROOT / 'search-ppml' / 'evidence' / 'sheets'
_SHEET = {}


def sheet_evidence(key):
    """{question: [(page, quote), ...]} from the study's extraction record (search-ppml/evidence/sheets/<key>.json):
    every page-cited quotation of each answer, in the record's order (the first is the one a column opens at); {} for a
    work without a sheet (the foundations)"""
    if key not in _SHEET:
        f = SHEETS / f'{key}.json'
        out = {}
        if f.exists():
            for q, a in (json.loads(f.read_text(encoding='utf-8')).get('answers') or {}).items():
                ev = [(int(e['page']), e.get('quote') or '') for e in (a or {}).get('evidence') or []
                      if str(e.get('page', '')).isdigit() and int(e['page']) > 0]
                if ev:
                    out[q] = ev
        _SHEET[key] = out
    return _SHEET[key]


def sheet_kind(key):
    """'P' (a primary study), 'S' (a survey) or '' (no sheet)"""
    qs = sheet_evidence(key)
    return 'S' if any(q.startswith('S') for q in qs) else ('P' if qs else '')


def section_for(key, page):
    """the section of the cited paper that `page` falls in: from the extraction's text/sections.json where the pipeline
    has produced it (the deepest section running over that page), else from the PDF's own outline (bookmarks) kept in
    metadata.json (the last entry starting at or before the page); '' when neither says"""
    f = folder_for(key)
    if not f:
        return ''
    s = f / 'text' / 'sections.json'
    if s.exists():
        best = ''
        for sec in json.loads(s.read_text(encoding='utf-8')).get('sections', []):
            pages = [int(p) for p in sec.get('pages') or [] if str(p).isdigit()]
            if pages and min(pages) <= page <= max(pages):
                best = f"{sec.get('number', '')} {sec.get('title', '')}".strip()
        return best
    m = f / 'metadata.json'
    if m.exists():
        best = ''
        for item in json.loads(m.read_text(encoding='utf-8')).get('outline') or []:
            if isinstance(item, list) and len(item) >= 3 and isinstance(item[2], int) and 1 <= item[2] <= page:
                best = str(item[1]).strip()
        return best
    return ''


# ---- which sheet answer stands behind a citation that no marked sentence settles ---------------------------------
# the tables built from the records (scripts/paper_ppml/data.py, checked by verify_tables.py): the answer behind each
# column, by the column's label (SQ, C, QA, QS), else by the row's first cell, else the table's own answer
# the form of 15 October 2026 (EXTRACTION-GUIDE-V3): a design answers P1 (fabric and cost), P2 (privacy with the
# blockchain), P3 (security and the evidence); a survey answers S1. Keys of earlier forms are translated (OLD2NEW).
OLD2NEW = {'P1': 'P1', 'P1b': 'P1', 'P2': 'P2', 'P3': 'P2', 'P3b': 'P2', 'P7': 'P2', 'P4': 'P3', 'P5': 'P3', 'P6': 'P3',
           'P6b': 'P3', 'P8': 'P3', 'S1': 'S1', 'S2': 'S1', 'S3': 'S1', 'S4': 'S1', 'S5': 'S1', 'S6': 'S1', 'S7': 'S1', 'S8': 'S1'}
_SQ_P = {'SQ1': 'P1', 'SQ2': 'P2', 'SQ3': 'P3', 'SQ4': 'P3', 'SQ5': 'P2'}
_SQ_S = {'SQ1': 'S1', 'SQ2': 'S1', 'SQ3': 'S1', 'SQ4': 'S1', 'SQ5': 'S1'}
_COND = {'C1': 'P1', 'C2': 'P2', 'C3': 'P2', 'C4': 'P3', 'C5': 'P2'}
_QA = {'QA1': 'P3', 'QA2': 'P3', 'QA3': 'P3', 'QA4': 'P1', 'QA5': 'P3', 'QA6': 'P3',
       'QS1': 'S1', 'QS2': 'S1', 'QS3': 'S1', 'QS4': 'S1'}
TABLE_ANSWER = {'ledger': 'P2', 'ledger_platforms': 'P2', 'privacy': 'P2', 'checks': 'P3', 'zk': 'P3', 'fabric': 'P1',
                'threats': 'P3', 'surveys': 'S1', 'qa_primary': 'P3', 'qa_secondary': 'S1', 'chars_primary': 'P1',
                'chars_secondary': 'S1'}
_HEAD = [(r'setting|enabler|fabric', 'P1', 'S1'), (r'privacy', 'P2', 'S1'), (r'ledger|chain', 'P2', 'S1'),
         (r'verif|check|zk|proof', 'P3', 'S1'), (r'pois|mal|free|attack|threat', 'P3', 'S1'),
         (r'studies|period|database', 'P3', 'S1'), (r'law|gdpr|legal', 'P2', 'S1')]
TABLES = {}                 # "IX" -> table key of the build, for the version on screen (load_evidence)


def question_for_column(table_key, header, first_cell, key):
    """the sheet answer behind a cell of a table of the records, or None where no single answer stands behind the
    citation (a row-level citation of a table with one column per question)"""
    kind = sheet_kind(key)
    if not kind:
        return None
    h = header or ''
    if (m := re.match(r'\s*(SQ[1-5]|C[1-5]|Q[AS][1-6])', h)):
        lab = m.group(1)
        if lab.startswith('SQ'):
            if lab == 'SQ3' and kind == 'P' and re.search(r'ledger|chain', h, re.I):
                return 'P2'
            return (_SQ_S if kind == 'S' else _SQ_P)[lab]
        q = _COND.get(lab) or _QA.get(lab)
        return q if q and q[0] == kind else None
    if table_key == 'open_areas':
        if kind == 'S':
            return 'S1'
        m = re.search(r'SQ[1-5]', first_cell or '')
        return _SQ_P[m.group(0)] if m else 'P3'
    if table_key in ('included_angles', 'chars_primary', 'chars_secondary') and h:
        for pat, p, sq in _HEAD:
            if re.search(pat, h, re.I):
                return p if kind == 'P' else sq
    q = TABLE_ANSWER.get(table_key)
    return q if q and q[0] == kind else None


_WORDING = {
    'P1': r'\b(device|hardware|raspberry|jetson|latency|bandwidth|network link|5g|6g|edge|fog|mec|cost|energy|throughput|storage)',
    'P2': r'\b(privacy|encrypt|homomorphic|differential|secure aggregation|secret shar|hides?|hidden|unlinkab|anonym|confidential|'
          r'ledger|chain|consensus|permission|smart contract|hyperledger|ethereum|trusted|gdpr|personal data|erasure|law|regulat|edpb)',
    'P3': r'\b(check|verif|proof|zero-knowledge|zkp|snark|audit|attest|validat|poison|backdoor|malicious|fake|sybil|free.?rid|attack|'
          r'byzantine|collusion|threat|defen|data ?sets?|baseline|accuracy|metric|results?|code|experiment|simulat|emulat|limitation|future work)',
    'S1': r'\b(treats?|subject|covers?|database|period|studies|privacy|poison|malicious|fake|free.?rid|blockchain|ledger|law|regulat|open|future)'}


def question_by_wording(sentence, heading, key):
    """the sheet answer whose subject the sentence names most, among the answers the study's sheet has; ties go to the
    answer of the section's survey question (its heading names SQ<n>); None when the wording names none"""
    kind = sheet_kind(key)
    if not kind:
        return None
    hit = {q: len(set(m.group(0).lower() for m in re.finditer(pat, sentence, re.I)))
           for q, pat in _WORDING.items() if q[0] == kind and q in sheet_evidence(key)}
    sq = re.search(r'SQ([1-5])', heading or '')
    pref = (_SQ_S if kind == 'S' else _SQ_P).get(f'SQ{sq.group(1)}') if sq else None
    best = max(hit.values(), default=0)
    if best:
        top = [q for q, n in hit.items() if n == best]
        return pref if pref in top else top[0]
    return pref if pref in sheet_evidence(key) else None


_NOTES, _TEXT = {}, {}
_COMPACT = re.compile(r'[^a-z0-9]')


_YEARS = {'2020', '2021', '2022', '2023', '2024', '2025', '2026'}


def _anchors(context):
    """distinctive facts from the citation's sentence, nearest the citation first: quoted phrases, decimals, thousands
    numbers, and standalone integers of at least three digits (years and all-equal digits excluded). Ordering by
    proximity means the fact just before the [n] is tried first, so a number belonging to a neighbouring citation in the
    same sentence is not preferred. Bracketed reference numbers are stripped by clause() before this runs."""
    found = [(m.start(), 'phrase', m.group(1)) for m in re.finditer(r'[“"]([^”"]{10,80})[”"]', context)]
    found += [(m.start(), 'num', m.group(0)) for m in re.finditer(r'\d+\.\d+', context)
              if not re.fullmatch(r'\d\.0', m.group(0))]          # skip version-like decimals (Industry 4.0, 5.0)
    found += [(m.start(), 'num', m.group(0)) for m in re.finditer(r'\d{1,3}(?:,\d{3})+', context)]
    for m in re.finditer(r'(?<![\d.,])\d{3,}(?![\d.,])', context):
        if m.group(0) not in _YEARS and len(set(m.group(0))) > 1:
            found.append((m.start(), 'num', m.group(0)))
    found.sort(key=lambda t: -t[0])          # nearest the citation first
    return [(k, v) for _, k, v in found]


def _num_pattern(value):
    """a regex that matches the number as a standalone token, allowing comma/space grouping and a 'k' for round thousands"""
    if '.' in value:
        return r'(?<![\d.])' + re.escape(value) + r'(?!\d)'
    digits = value.replace(',', '')
    variants = {digits, value, value.replace(',', ' ')}
    if digits.endswith('000'):
        variants.add(digits[:-3] + 'k')
    return r'(?<![\d.])(?:' + '|'.join(re.escape(v) for v in sorted(variants, key=len, reverse=True)) + r')(?!\d)'


def _unique_page(pages, context):
    for kind, value in _anchors(context):
        if kind == 'phrase':
            cv = _COMPACT.sub('', value.lower())
            if len(cv) < 8:
                continue
            hits = [p for p, t in pages.items() if cv in _COMPACT.sub('', t)]
        else:
            pat = re.compile(_num_pattern(value))
            hits = [p for p, t in pages.items() if pat.search(t)]
        if len(hits) == 1:
            return hits[0]
    return None


def find_page(key, context):
    """the PDF page to open for a citation of `key`: the captured notes page when a distinctive fact from the sentence
    sits uniquely there, else the extracted-text page where it physically appears, else None (open at page 1)."""
    if key not in _NOTES:
        _NOTES[key] = notes_pages(key)
    return _unique_page(_NOTES[key], context) or (
        _TEXT.setdefault(key, pages_text(key)) and _unique_page(_TEXT[key], context))


import os


def href(path, page, base_dir):
    """a RELATIVE link from the HTML to the PDF, url-encoded per segment, so it resolves both as a local file and,
    crucially, when the folder is served over http://localhost (where the browser renders the PDF inline and honours
    #page instead of downloading it)."""
    rel = os.path.relpath(str(path), base_dir)
    url = '/'.join(urllib.parse.quote(seg) for seg in rel.split(os.sep))
    return url + (f'#page={page}' if page and page > 1 else '')


_EDPB_PARA = None


def edpb_para_pages():
    """{paragraph number: PDF page where it starts} for the EDPB guidelines: from the page text, where each numbered
    paragraph opens a line, else from the page-cited notes (every "para. N [pX]" there was checked against the PDF)."""
    global _EDPB_PARA
    if _EDPB_PARA is None:
        import collections
        folder, pages = EXTRA['edpb2026'], {}
        for f in sorted((folder / 'text' / 'pages').glob('page_*.txt')):
            for m in re.finditer(r'(?m)^\s*(\d{1,3})\.?\s', f.read_text(encoding='utf-8')):
                pages.setdefault(int(m.group(1)), int(f.stem[5:]))
        notes = folder / 'notes' / 'NOTES.md'
        votes = collections.defaultdict(set)
        if notes.exists():
            for m in re.finditer(r'paras?\.\s*(\d{1,3})[^\[\n]{0,25}\[p(\d+)', notes.read_text(encoding='utf-8')):
                votes[int(m.group(1))].add(int(m.group(2)))
        for n, ps in votes.items():                 # the notes decide; the text only fills gaps and picks the start
            if n not in pages or pages[n] not in ps:
                pages[n] = min(ps)
        _EDPB_PARA = pages
    return _EDPB_PARA


def edpb_page(context):
    """the EDPB page for the last paragraph named in the context ("para. 46", "paras. 102-103"), else page 1"""
    m = re.findall(r'paras?\.\s*(\d{1,3})', context)
    return edpb_para_pages().get(int(m[-1]), 1) if m else 1


PARA_REF = re.compile(r'(?:Recommendation \d+, )?paras?\. \d{1,3}(?:[–-]\d{1,3})?(?:(?:, | and )\d{1,3}(?:[–-]\d{1,3})?)*')


def link_paragraphs(body, make_link):
    """turn each mention of an EDPB paragraph into a link to the page where that paragraph starts; in "paras. 46 and
    103" each number gets its own link"""
    pdf, pmap = pdf_for('edpb2026'), edpb_para_pages()
    stats = {'para_links': 0}

    def one(m):
        out, text, pos = [], m.group(0), 0
        for k, nm in enumerate(re.finditer(r'\d{1,3}(?:[–-]\d{1,3})?', text)):
            if text[:nm.start()].rstrip().endswith('Recommendation') or re.search(r'Recommendation $', text[:nm.start()]):
                continue                              # the number of a Recommendation, not a paragraph
            first = int(re.match(r'\d+', nm.group(0)).group(0))
            page = pmap.get(first)
            if not page:
                continue
            start = 0 if k == 0 or not out else nm.start()
            if not out:
                start = text.find('para')
            out.append((start, nm.end(), page))
        if not out:
            return text
        res, last = [], 0
        for a, b, page in out:
            res.append(text[last:a])
            res.append(make_link(text[a:b], 'edpb2026', page, False, pdf, how='paragraph'))
            stats['para_links'] += 1
            last = b
        res.append(text[last:])
        return ''.join(res)
    return PARA_REF.sub(one, body), stats['para_links']


def pandoc_html(in_docx, comments=False):
    """the docx as standalone HTML; comments=True keeps Word comments (as comment-start/-end spans) and highlights.
    A citation number's bold comes from the Word "Citation" style (paper_look.py), which pandoc reads as <strong>;
    it is the look, not the text, so it is dropped and every [n] reaches the linking below as before."""
    extra = ['--track-changes=all'] if comments else []
    out = subprocess.run(['pandoc', in_docx, '-o', '/dev/stdout', '--standalone', '--embed-resources', *extra,
                          '--metadata', 'title=Privacy-preserving and verifiable FL on blockchains for NG-IoT'],
                         check=True, capture_output=True, text=True).stdout
    return re.sub(r'<strong>(\[\d{1,3}\])</strong>', r'\1', out)


# evidence pages for the version being linked (new series only): [(key, words of the marked sentence, page)], written at
# build time by scripts/paper/links.py from the page-cited evidence sheets; empty for the earlier series
EVIDENCE = []
_W = re.compile(r'[a-z0-9]+')


def _words(s):
    return {w for w in _W.findall(s.lower()) if len(w) > 2}


def _roman(n):
    out = ''
    for v, r in ((1000, 'M'), (900, 'CM'), (500, 'D'), (400, 'CD'), (100, 'C'), (90, 'XC'), (50, 'L'), (40, 'XL'),
                 (10, 'X'), (9, 'IX'), (5, 'V'), (4, 'IV'), (1, 'I')):
        while n >= v:
            out, n = out + r, n - v
    return out


def load_evidence(docx):
    """set EVIDENCE for one docx of the new series (its build/LINKS-V<n>.json: key, sentence words, page, quote,
    question), and TABLES (the build report's table numbers -> table keys), or clear them; returns the file used"""
    EVIDENCE.clear()
    TABLES.clear()
    m = re.search(r'Systematic Review - V(\d+)(?: with author checks)?\.docx$', str(docx))
    build = ROOT / 'myliteraturereviewpaper' / 'slr2026' / 'build' if m else None
    mp = re.search(r'NextGeneration IoT - V(\d+)(?: with author checks)?\.docx$', str(docx))   # the PPML review, V29 onwards
    if mp and (ROOT / 'myliteraturereviewpaper' / 'ppml2026' / 'build' / f'LINKS-V{mp.group(1)}.json').exists():
        m, build = mp, ROOT / 'myliteraturereviewpaper' / 'ppml2026' / 'build'
    f = build / f'LINKS-V{m.group(1)}.json' if build else None
    if f and f.exists():
        for e in json.loads(f.read_text(encoding='utf-8'))['entries']:
            EVIDENCE.append((e['key'], _words(e['sentence']), int(e['page']), e.get('quote') or '', OLD2NEW.get(e.get('q') or '', e.get('q') or '')))
        rep = build / f'BUILD-REPORT-V{m.group(1)}.json'
        if rep.exists():
            tabs = json.loads(rep.read_text(encoding='utf-8')).get('tables') or {}
            TABLES.update({_roman(int(n)): k for k, n in tabs.items() if str(n).isdigit()})
        return f
    return None


def _sentence_at(base, pos):
    """the sentence around a citation at `pos` (and the one after it), without tags and citation numbers"""
    plain = re.sub(r'<[^>]+>', ' ', base[max(0, pos - 700):pos]), re.sub(r'<[^>]+>', ' ', base[pos:pos + 700])
    para_after = re.split(r'\n\s*\n|</p>', plain[1], maxsplit=1)[0]          # stay inside the citation's paragraph
    before = re.split(r'(?<=[.!?])\s+(?=[A-Z])', plain[0])[-1]
    after = re.split(r'(?<=[.!?])\s+(?=[A-Z])', para_after, maxsplit=2)
    own, two = before + ' ' + after[0], before + ' ' + ' '.join(after[:2])
    return re.sub(r'\[\d{1,3}\]', ' ', own), re.sub(r'\[\d{1,3}\]', ' ', two)


def evidence_entry(base, pos, key):
    """the evidence behind the citation's own sentence: (page, quote, question) of the marked sentence of the build
    that best matches the sentence around [n] (at least 60% of its words), for the same key; None when none matches"""
    if not EVIDENCE:
        return None
    # its own sentence first; then its own and the next one, for "X [n] is the closest design. Its clients prove …"
    for ctx in _sentence_at(base, pos):
        ctx = _words(ctx)
        best = None
        for k, ws, page, quote, q in EVIDENCE:
            if k == key and ws:
                score = len(ws & ctx) / len(ws)
                if best is None or score > best[0]:
                    best = (score, page, quote, q)
        if best and best[0] >= 0.6:
            return best[1:]
    return None


def evidence_page(base, pos, key):
    e = evidence_entry(base, pos, key)
    return e[0] if e else None


# how a citation's page was settled, in words for the reader
HOW = {'sentence': 'the evidence behind this sentence', 'table': 'the record behind this table column',
       'paragraph': 'the cited paragraph', 'fact': 'a distinctive fact of the sentence',
       'wording': "the record's answer the sentence's wording names", 'none': 'no single cited page'}


def resolve(base, pos, key, table=None, heading=''):
    """where a citation at `pos` opens its PDF: {'page', 'q', 'quote', 'how'} — the evidence behind its own sentence;
    in a table of the records, the sheet answer behind the column (`table` = (table key, column header, first cell));
    else a distinctive fact of the sentence (the EDPB guidelines: the cited paragraph's page); else the answer the
    sentence's wording names; else page 1 (how = 'none')"""
    none = {'page': 1, 'q': '', 'quote': '', 'how': 'none'}
    if table is not None:
        q = question_for_column(table[0], table[1], table[2], key)
        ev = sheet_evidence(key).get(q) if q else None
        return {'page': ev[0][0], 'q': q, 'quote': ev[0][1], 'how': 'table'} if ev else none
    ev = evidence_entry(base, pos, key)
    if ev:
        return {'page': ev[0], 'q': ev[2], 'quote': ev[1], 'how': 'sentence'}
    raw = re.sub(r'<[^>]+>', ' ', base[max(0, pos - 320):pos])
    cut = max(raw.rfind(x) for x in ('. ', '; ', ': ', ']'))
    ctx = re.sub(r'\[\d{1,3}\]', ' ', raw[cut + 1:] if cut > 0 else raw)[-260:]
    if key == 'edpb2026':
        page = edpb_page(ctx)
        return {'page': page, 'q': '', 'quote': '', 'how': 'paragraph'} if page else none
    page = find_page(key, ctx)
    if page:
        return {'page': page, 'q': '', 'quote': '', 'how': 'fact'}
    q = question_by_wording(_sentence_at(base, pos)[0], heading, key)
    ev = sheet_evidence(key).get(q) if q else None
    return {'page': ev[0][0], 'q': q, 'quote': ev[0][1], 'how': 'wording'} if ev else none


def resolve_page(base, pos, key, in_table):
    """the PDF page a citation at `pos` should open (resolve() without the table's column)"""
    return 1 if in_table else resolve(base, pos, key)['page']


def _table_cells(base, span, pos):
    """(table key, column header, first cell) for a citation at `pos` inside the table at `span`"""
    a, b = span
    t = base[a:b]
    cap = re.search(r'<caption[^>]*>(.*?)</caption>', t, re.S)
    m = re.match(r'\s*Table\s+([IVXLC]+)\.', re.sub(r'<[^>]+>', '', cap.group(1)).strip()) if cap else None
    tkey = TABLES.get(m.group(1), '') if m else ''
    headers = [re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', '', h)).strip()
               for h in re.findall(r'<th[^>]*>(.*?)</th>', (re.search(r'<thead>(.*?)</thead>', t, re.S) or [None, ''])[1], re.S)]
    row = base.rfind('<tr', a, pos)
    cells = re.findall(r'<t[dh][^>]*>', base[row:pos]) if row > 0 else []
    col = max(0, len(cells) - 1)
    first = re.search(r'<t[dh][^>]*>(.*?)</t[dh]>', base[row:pos] + base[pos:pos + 400], re.S) if row > 0 else None
    first = re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', '', first.group(1))).strip() if first else ''
    return tkey, headers[col] if col < len(headers) else '', first


_REFS = None
_NEW = None
_PPML = None


def _title_in(ieee):
    m = re.search(r'“(.*?)[,.]?”', ieee)
    return m.group(1) if m else ''


def _norm_ref(s):
    import unicodedata, html as _h
    s = unicodedata.normalize('NFKC', _h.unescape(re.sub(r'<[^>]+>', ' ', s)))
    return re.sub(r'[^a-z0-9]+', ' ', s.lower()).strip()


def cited_from_html(base):
    """[n] -> reference key for ONE version of the paper, read from that version's own reference list, so that every
    version links to the right papers even though the numbering differs between versions. Each entry is matched to the
    bibliography (references.json) by its whole text, else by its title; an entry that matches no key, or more than one,
    stays None and is not linked (never guessed). Returns (cited list, unmatched entry numbers)."""
    global _REFS, _NEW, _PPML
    if _REFS is None:
        _PPML = {k: (_norm_ref(v['ieee']), _norm_ref(_title_in(v['ieee']))) for k, v in PPML_REFS.items()}
        R = json.loads((ROOT / 'myliteraturereviewpaper' / '_src' / 'V14' / 'references.json').read_text(encoding='utf-8'))['refs']
        _REFS = {k: (_norm_ref(v.get('text_ieee', '')), _norm_ref(v.get('title', ''))) for k, v in R.items()}
        _NEW = {k: (_norm_ref(v['ieee']), _norm_ref(_title_in(v['ieee']))) for k, v in NEW_REFS.items()}
    mref = re.search(r'<h1[^>]*>\s*References\s*</h1>', base)
    if not mref:
        return [], []
    entries = {}
    for m in re.finditer(r'<p>\s*\[(\d{1,3})\]\s*(.*?)</p>', base[mref.end():], re.S):
        entries.setdefault(int(m.group(1)), _norm_ref(m.group(2)))
    # the bibliography of the series this version belongs to: the one whose entries match more reference lines whole
    exact = lambda B: sum(1 for t in entries.values() if any(full == t for full, _ in B.values()))
    BIB = max((_REFS, _NEW, _PPML), key=exact)                # the bibliography that matches most entries whole (ties: earliest)
    whole = {}
    for k, (full, _) in BIB.items():
        whole.setdefault(full, []).append(k)
    cited, unmatched = [None] * (max(entries) if entries else 0), []
    for n, text in entries.items():
        hit = whole.get(text, [])
        if len(hit) != 1:
            hit = [k for k, (_, title) in BIB.items() if len(title) > 12 and title in text]
        if len(hit) == 1:
            cited[n - 1] = hit[0]
        else:
            unmatched.append(n)
    return cited, sorted(unmatched)


def annotate(base, make_link, cited=None):
    """Wrap every in-text [n] with a link built by make_link(token, key, page, in_refs, pdf_path, q=, quote=, how=):
    the page from resolve(), with the sheet question and quotation behind it and how it was settled (HOW). The
    reference-list entries (after the References heading) link to page 1. Foundations with no corpus PDF are left as
    plain text. `cited` maps [n] to keys for the version being annotated (cited_from_html); by default the current
    build's. Returns (html, stats; stats['by'] counts the citations by how their page was settled). This is the single,
    audited place that turns citations into links; the static file and the viewer app share it so both link identically."""
    CIT = CITED if cited is None else cited
    mref = re.search(r'<h1[^>]*>\s*References\s*</h1>', base)
    ref_start = mref.start() if mref else len(base)
    table_spans = [(m.start(), m.end()) for m in re.finditer(r'<table.*?</table>', base, re.S)]
    headings = [(m.start(), re.sub(r'<[^>]+>', '', m.group(1))) for m in re.finditer(r'<h[12][^>]*>(.*?)</h[12]>', base, re.S)]
    stats = {'intext': 0, 'linked': 0, 'exact': 0, 'no_pdf': 0, 'by': {}}

    def repl(m, in_refs):
        n = int(m.group(1))
        if not (1 <= n <= len(CIT)) or CIT[n - 1] is None:
            return m.group(0)
        key = CIT[n - 1]
        pdf = pdf_for(key)
        if not in_refs:
            stats['intext'] += 1
        if not pdf:
            if not in_refs:
                stats['no_pdf'] += 1
            return m.group(0)
        if in_refs:
            r = {'page': 1, 'q': '', 'quote': '', 'how': 'list'}
        else:
            span = next(((a, b) for a, b in table_spans if a <= m.start() < b), None)
            heading = next((h for p, h in reversed(headings) if p < m.start()), '')
            r = resolve(base, m.start(), key, _table_cells(base, span, m.start()) if span else None, heading)
            stats['linked'] += 1
            if r['page'] > 1:
                stats['exact'] += 1
            stats['by'][r['how']] = stats['by'].get(r['how'], 0) + 1
        return make_link(m.group(0), key, r['page'], in_refs, pdf, q=r['q'], quote=r['quote'], how=r['how'])

    tok = re.compile(r'\[(\d{1,3})\]')
    body, stats['para_links'] = link_paragraphs(tok.sub(lambda m: repl(m, False), base[:ref_start]), make_link)
    html = body + tok.sub(lambda m: repl(m, True), base[ref_start:])
    return html, stats


def main(in_docx, out_html):
    base_dir = str(pathlib.Path(out_html).resolve().parent)

    def make_link(token, key, page, in_refs, pdf, q='', quote='', how=''):
        title = f'{key}: opens the PDF' + (f' at page {page} ({HOW.get(how, how)}{", answer " + q if q else ""})' if page > 1 else '')
        return (f'<a href="{href(pdf, page, base_dir)}" title="{title}" '
                f'style="text-decoration:none;color:#1a5fb4;font-weight:600">{token}</a>')

    base = pandoc_html(in_docx)
    load_evidence(in_docx)
    cited, unmatched = cited_from_html(base)
    html, stats = annotate(base, make_link, cited=cited or None)
    if unmatched:
        print('reference entries not matched (left unlinked):', unmatched)
    banner = ('<div style="max-width:52rem;margin:0 auto;padding:8px 12px;border:1px solid #cde2fb;background:#eef5fd;'
              'border-radius:6px;font:14px system-ui,sans-serif;color:#33475b">Each reference <b>[n]</b> links to its '
              'PDF in the corpus; where the cited fact could be located, the link opens that page, otherwise page one. '
              'To read with the PDFs beside the text, open Review Viewer.app.</div>')
    html = re.sub(r'(<body[^>]*>)', r'\1\n' + banner, html, count=1)
    pathlib.Path(out_html).write_text(html, encoding='utf-8')
    print(f"in-text citations: {stats['intext']}; linked: {stats['linked']}; "
          f"opened at an exact page: {stats['exact']} {stats['by']}; no PDF (foundations): {stats['no_pdf']}")
    print('wrote', out_html)


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
