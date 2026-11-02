#!/usr/bin/env python3
"""Build the PPML review paper (V29 onwards) from its parts and the evidence, with every check that makes it redoable.

Steps
 1. Assemble myliteraturereviewpaper/ppml2026/parts/*.md in order; replace {{STUDY:id}} by the study's paragraph from
    studies/*.md.
 2. Check every evidence marker:
      ⟦id:P3⟧ / ⟦id:P1,P5⟧ / ⟦id:S2⟧  — the study's sheet (search-ppml/evidence/sheets/<id>.json) has the answer;
      ⟦F:<refkey>:<page>⟧            — a page of a foundation (PRISMA 2020, GDPR, EDPB; its text/pages/page_NNNN.txt);
    every number in the marked sentence must occur in the cited answers (answer text, values, quotations) or on the cited
    page. Then remove the markers.
 3. Replace {{N:key}} by the computed value (build/stats.json from scripts/paper_ppml/data.py); unknown keys fail.
 4. Number tables and figures in order of placement: a line holding only {{TAB:key}} / {{FIG:key}} places it; any other
    occurrence becomes "Table n" / "Fig. n".
 4b. A block "::: takeaways" of numbered sentences (one at the end of each section, after the format of the author's model
    paper) becomes a Key Takeaways box: a header row in the theme's accent and a pale row with the points, kept on one page.
    Labels such as (SQ1), (C4) are cross-references and are never dropped as repeated abbreviations.
 5. Number citations [@a; @b] in order of first appearance (IEEE style) through refs.json; append the reference list.
 6. Refuse leftovers ({{, ⟦, [@) and words that do not belong in a paper (PhD, supervisor, draft, sheet …); every listed
    abbreviation must be used.
 7. Write build/paper-V<n>.md and build/BUILD-REPORT-V<n>.json and render with pandoc to
    myliteraturereviewpaper/PPML in NextGeneration IoT/<NAME> - V<n>.docx in the look of the Review Viewer
    (scripts/review/paper_look.py: the same fonts, sizes, colours, spacing, tables and boxes in Word as on screen);
    then the copy with the author checks (AUTHOR-CHECKS-V<n>.json, scripts/review/annotate_author_checks.py).
    An existing file is never overwritten.

Usage: python3 scripts/paper_ppml/build.py <version-number> [--check]     (--check: run every check, render nothing)
"""
import json, os, pathlib, re, subprocess, sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
P = ROOT / 'myliteraturereviewpaper' / 'ppml2026'
B = P / 'build'
PARTS = pathlib.Path(os.environ.get('PPML_PARTS') or P / 'parts')     # PPML_PARTS=<folder>: the parts of another frame (V68: parts-v68)
SHEETS = ROOT / 'search-ppml' / 'evidence' / 'sheets'
NAME = 'Privacy Preserving Machine Learning in NextGeneration IoT'
OUTDIR = ROOT / 'myliteraturereviewpaper' / 'PPML in NextGeneration IoT'
sys.path.insert(0, str(ROOT / 'scripts' / 'review'))
import paper_look as L                        # noqa: E402  the look shared by the docx and the Review Viewer
FIGCAP = {
    'spine': 'The spine of the review: for each layer, its focus angles and survey question, the sections that introduce and answer the question, the open issue it leaves, the condition of the research gap that the issue becomes, and the research question that takes it up.',
    'prisma': 'PRISMA 2020 flow of the identification, screening and inclusion of studies, showing which records the author screened and which the automated screening tool screened.',
    'architecture': 'Where learning, privacy, checking and the ledger sit on the tiers of an NG-IoT deployment, and where the threats enter (a schematic; the counts are in Section VI).',
    'taxonomy': 'Taxonomy of the primary studies by the design choices behind the five survey questions, with the number of designs that make each choice and, in brackets, the condition of the research gap that a choice meets; a design counts once under each question.',
    'threats': 'Threats the primary studies claim to counter, and those for which they report a test of the design by an attack (drawn inside the claim), with the attacks on the learning apart from the properties of the system.',
    'design': 'Reference design of the research agenda. IoT gateways train as FL clients, commit to their updates and secret-share them; a committee of gateways, which are also the validators of a permissioned edge ledger, computes the check against poisoning jointly on the shares, and the ledger accepts a round only with the check outcomes; the ledger holds commitments, outcomes and pseudonymous admission records. A zero-knowledge proof of the bound is an optional extension (dashed).',
    # the coverage maps of the two tiers, back in the main text at the author's request of 13 October 2026 (V56-V57: supplement)
    'survey_coverage': 'What each included survey treats as a subject of its own (Yes), mentions (Partial) or leaves out (No), layer by layer and focus angle by focus angle, as in {{TAB:surveys}}, with the surveys ordered by how many grades are Yes; the white cells are the areas a survey leaves out.',
    'prim_coverage': 'What each primary study does along the spine, graded Yes, Partial or No as in {{TAB:prim_cover}}, with the studies ordered by how many grades are Yes; the white cells are the areas a design leaves out.',
    # supplementary material (build_supplement.py)
    'trends': 'Year by year: (a) the focus angles of the primary studies; (b) their privacy mechanisms. A study can count under several rows; each panel is shaded on its own scale.',
}
if (PARTS / 'figcaps.json').exists():                                  # captions of the frame being built
    FIGCAP.update(json.loads((PARTS / 'figcaps.json').read_text(encoding='utf-8')))
# words not for a paper: process words, and the AI vocabulary the author banned on 15 October 2026 (CLAUDE.md, writing rules)
BANNED = re.compile(r'\b(PhD|supervisors?|proposal|draft|evidence sheets?|sheets?|Claude Code|TODO|located_via|delv\w*|tapestr\w*|testament|paramount|leverag\w*|multifaceted|bolster\w*|furthermore|moreover|in conclusion)\b', re.I)
NUM = re.compile(r'(?<![A-Za-z0-9])\d+(?:[.,]\d+)*')
problems = []
sys.path.insert(0, str(pathlib.Path(__file__).parent))



# Tables too wide for a portrait page get a landscape page of their own (US Letter turned, 1-inch margins): a section
# break closes the portrait text before the table and a landscape one after it.
LANDSCAPE_TABLES = {'prim_cover'}
PORTRAIT_END = '```{=openxml}\n<w:p><w:pPr><w:sectPr/></w:pPr></w:p>\n```'     # like the document's own final section
LANDSCAPE_END = '```{=openxml}\n<w:p><w:pPr><w:sectPr><w:pgSz w:w="15840" w:h="12240" w:orient="landscape"/><w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440" w:header="720" w:footer="720" w:gutter="0"/></w:sectPr></w:pPr></w:p>\n```'


def roman(n):
    """Table numbers in Roman numerals, as in IEEE journals."""
    out = ''
    for v, r in ((1000, 'M'), (900, 'CM'), (500, 'D'), (400, 'CD'), (100, 'C'), (90, 'XC'), (50, 'L'), (40, 'XL'),
                 (10, 'X'), (9, 'IX'), (5, 'V'), (4, 'IV'), (1, 'I')):
        while n >= v:
            out, n = out + r, n - v
    return out

def studies():
    out = {}
    folder = pathlib.Path(os.environ.get('PPML_STUDIES') or P / 'studies')     # PPML_STUDIES=<folder>: the paragraphs of another frame (V71: studies-v71)
    for f in sorted(folder.glob('*.md')):
        for m in re.finditer(r'^### (\S+)\n(.*?)(?=^### |\Z)', f.read_text(encoding='utf-8'), re.S | re.M):
            out[m.group(1)] = m.group(2).strip()
    return out


EXTRA_TERMS = [('HIPAA', 'Health Insurance Portability and Accountability Act'), ('CCPA', 'California Consumer Privacy Act'),
               ('V2X', 'vehicle-to-everything'), ('SVM', 'support vector machine'), ('CNN', 'convolutional neural network'),
               ('IPFS', 'InterPlanetary File System'), ('CTI', 'cyber threat intelligence'), ('IDS', 'intrusion detection system')]


LABEL = re.compile(r'(?:SQ|RQ|IC|EC|QA|QS|C|G)\d+[a-g]?')
TAKEAWAYS = re.compile(r'(?ms)^::: takeaways[ \t]*\n(.*?)\n:::[ \t]*$')
BOX_HEAD, BOX_BODY = L.BOX['head'].upper(), L.BOX['body'].upper()     # the theme's accent and a pale tint (paper_look.BOX)


def xml_runs(text):
    """plain text with *italic* spans as Word runs"""
    out = []
    for i, part in enumerate(re.split(r'\*([^*]+)\*', text)):
        if part:
            esc = part.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            out.append(f'<w:r>{"<w:rPr><w:i/></w:rPr>" if i % 2 else ""}<w:t xml:space="preserve">{esc}</w:t></w:r>')
    return ''.join(out)


def takeaways(m):
    """a "::: takeaways" block of numbered sentences -> a Key Takeaways box at the end of a section: a header row in the
    accent colour and a pale row with the points as bullets (one claim each; the author, 12 October 2026: "make them
    bullet points if needed"; "line breaks between bullet points": a blank line's space after each), kept together on one page;
    not a numbered table"""
    items = [re.sub(r'\s+', ' ', x).strip() for x in re.split(r'(?m)^\d+\.\s+', m.group(1)) if x.strip()]
    if not items:
        problems.append('empty takeaways block')
    X = L.BOX                                  # the box's measures, shared with the viewer's drawing of it
    edge = ''.join(f'<w:{s} w:val="single" w:sz="{X["rule"]}" w:space="0" w:color="{BOX_HEAD}"/>' for s in ('top', 'left', 'bottom', 'right'))
    row = lambda fill, paras: (f'<w:tr><w:trPr><w:cantSplit/></w:trPr><w:tc><w:tcPr><w:tcW w:w="5000" w:type="pct"/>'
                               f'<w:shd w:val="clear" w:color="auto" w:fill="{fill}"/></w:tcPr>{paras}</w:tc></w:tr>')
    head = (f'<w:p><w:pPr><w:pStyle w:val="Compact"/><w:keepNext/><w:spacing w:before="{X["head_space"]}" w:after="{X["head_space"]}"/></w:pPr>'
            '<w:r><w:rPr><w:b/><w:color w:val="FFFFFF"/></w:rPr><w:t>Key Takeaways</w:t></w:r></w:p>')
    body = ''.join(f'<w:p><w:pPr><w:pStyle w:val="Compact"/>{"<w:keepNext/>" if i < len(items) else ""}'
                   f'<w:tabs><w:tab w:val="left" w:pos="{X["hang"]}"/></w:tabs><w:spacing w:before="{X["item_before"]}" w:after="{X["item_after"] if i < len(items) else X["last_after"]}"/>'
                   f'<w:ind w:left="{X["hang"]}" w:hanging="{X["hang"]}"/></w:pPr><w:r><w:t>\u2022</w:t></w:r><w:r><w:tab/></w:r>{xml_runs(x)}</w:p>'
                   for i, x in enumerate(items, 1))
    xml = ('<w:p><w:pPr><w:keepNext/><w:spacing w:before="0" w:after="0"/></w:pPr></w:p>'
           f'<w:tbl><w:tblPr><w:tblW w:w="5000" w:type="pct"/><w:tblBorders>{edge}<w:insideH w:val="nil"/><w:insideV w:val="nil"/></w:tblBorders>'
           '<w:tblCellMar>' + ''.join(f'<w:{e} w:w="{v}" w:type="dxa"/>' for e, v in zip(('top', 'left', 'bottom', 'right'), X['pad']))
           + f'</w:tblCellMar><w:tblLook w:val="0000"/></w:tblPr><w:tblGrid><w:gridCol w:w="{X["width"]}"/></w:tblGrid>'
           f'{row(BOX_HEAD, head)}{row(BOX_BODY, body)}</w:tbl>')
    return '```{=openxml}\n' + xml + '\n```'


def _define_once(text):
    """within one part of the paper (the abstract, or the body): an abbreviation is written out with its short form once, at
    first use; later "long form (ABBR)" become "ABBR" (the study paragraphs were written to stand alone, so each defines its
    own terms)"""
    import thematic
    for abbr, meaning in thematic.ABBREVIATIONS + EXTRA_TERMS:
        if abbr in thematic.LABEL_FAMILIES:
            continue
        for a, m in zip(abbr.split(' / '), meaning.split(' / ')):
            pat = re.compile(r'\b' + re.escape(m) + r'(s?)\s*\(' + re.escape(a) + r's?\)', re.I)
            seen = [0]

            def keep_first(x):
                seen[0] += 1
                return x.group(0) if seen[0] == 1 else a + x.group(1)
            text = pat.sub(keep_first, text)
    # any other short form defined more than once with a different long form: keep the first "(ABBR)", drop the later ones
    for a in sorted({m for m in re.findall(r' \(([A-Z][A-Za-z0-9-]{1,8})\)', text)} - {'Anthropic'}):
        if LABEL.fullmatch(a):                      # (SQ1), (C4), (RQ2): cross-references, repeated on purpose
            continue
        n = [0]

        def drop_later(x):
            n[0] += 1
            return x.group(0) if n[0] == 1 else ''
        text = re.sub(r' \(' + re.escape(a) + r'\)', drop_later, text)
    return text


def split_front(text):
    """(YAML head + separator, front matter up to Section I, body from Section I)"""
    head, sep, rest = text.partition('\n---\n') if text.startswith('---') else ('', '', text)
    i = rest.find('\n# I. Introduction')
    return head + sep, (rest[:i] if i >= 0 else ''), (rest[i:] if i >= 0 else rest)


def define_once(text):
    """the abstract and the body each define their abbreviations at first use (standard practice: the abstract stands alone)"""
    head, front, body = split_front(text)
    return head + _define_once(front) + _define_once(body)


AN = {'AI', 'EDPB', 'EU', 'FL', 'FLchain', 'HE', 'IoT', 'IoV', 'IoMT', 'IIoT', 'LDP', 'MAE', 'MEC', 'ML', 'NG-IoT', 'RQ', 'RSU',
      'SGX', 'SMPC', 'SQ', 'SVM'}                                   # read with a vowel sound: "an FL client", "an SQ"
LONG_EXTRA = {'NG-IoT': ['next-generation IoT'], 'BCFL': ['blockchain-based FL'], 'PoW': ['proof-of-work'], 'IIoT': ['Industrial IoT'],
              'FLchain': ['FL combined with blockchain'], 'PRISMA': [], 'ML': [], 'HE': []}
NO_ARTICLE = {'HIPAA'}                                          # names read as words, without an article
KEEP_LONG = re.compile(r'(fully|additively|partially|somewhat|threshold) $', re.I)   # "fully homomorphic encryption" stays
FIXED_ROW = re.compile(r'^\| (?:P-S1|P-A|P-C|P-S2|P-B|R-S1|IC\d|EC\d) \|')      # search strings and criteria, as written


def consistent_forms(body):
    """after its single definition, an abbreviation is used throughout the running text (standard rule): later long forms
    become the short form ("a"/"an" adjusted); headings, captions, quotations, the search strings and the criteria stay"""
    import thematic
    forms = []
    for abbr, meaning in thematic.ABBREVIATIONS:
        if abbr in thematic.LABEL_FAMILIES or ' / ' in abbr:
            continue
        for m in [meaning] + LONG_EXTRA.get(abbr, []):
            forms.append((len(m), abbr, m))
    masks = {}

    def mask(s):
        k = f'\x00{len(masks)}\x00'
        masks[k] = s
        return k
    for _, abbr, m in sorted(forms, reverse=True):
        d = re.search(r'\(' + re.escape(abbr) + r's?[),;]', body)
        pat = re.compile(r'(?<![\w-])' + re.escape(m) + r'(s?)(?![\w-])', re.I)
        out, pos = [], 0
        for line in body.split('\n'):
            start = pos
            pos += len(line) + 1
            if not d or start + len(line) <= d.end() or line.startswith(('#', 'Table:', '![', '```', '<')) or FIXED_ROW.match(line):
                out.append(pat.sub(lambda x: mask(x.group(0)), line))
                continue
            quoted = [(q.start(), q.end()) for q in re.finditer(r'"[^"\n]*"|“[^”\n]*”|‘[^’\n]*’|(?<!\w)\'[^\'\n]{1,200}?\'(?!\w)', line)]

            def sub(x, start=start, quoted=quoted, line=line):
                if start + x.start() < d.end() or any(a <= x.start() < b for a, b in quoted) or KEEP_LONG.search(line[:x.start()]):
                    return mask(x.group(0))
                return abbr + x.group(1)
            line = pat.sub(sub, line)
            line = re.sub(r'\b([Aa])n? (' + re.escape(abbr) + r's?)\b',
                          lambda y: (y.group(1) + ('n ' if abbr in AN else ' ') + y.group(2)), line)
            if abbr in NO_ARTICLE:                                     # "HIPAA", never "the HIPAA"
                line = re.sub(r'\b[Tt]he (' + re.escape(abbr) + r')\b', r'\1', line)
            out.append(line)
        body = '\n'.join(out)
    for k in sorted(masks, key=lambda k: -int(k.strip('\x00'))):
        body = body.replace(k, masks[k])
    return body


def _uses(text, a):
    import thematic
    if a in thematic.LABEL_FAMILIES:
        return [m.start() for m in re.finditer(r'(?<![\w-])' + thematic.LABEL_FAMILIES[a] + r'(?![\w])', text)]
    return [m.start() for m in re.finditer(r'(?<![\w-])' + re.escape(a) + r's?(?![\w-])', text)]


def _plain(text):
    text = re.sub(r'```\{=openxml\}\n(.*?)\n```', lambda m: ' '.join(re.findall(r'<w:t[^>]*>([^<]*)</w:t>', m.group(1))), text, flags=re.S)
    return re.sub(r'\(/[^)]*\.png\)', '', text)


def abbreviation_list(src):
    """the List of Abbreviations: every abbreviation of thematic.ABBREVIATIONS that the paper uses, and no other"""
    import thematic
    _h, front, body = split_front(src)
    text = _plain(front.replace('@@ABBREVIATIONS@@', '') + body.split('\n# References')[0])
    used = []
    for abbr, meaning in thematic.ABBREVIATIONS:
        if abbr == '5G / 6G':
            if _uses(text, '5G') or _uses(text, '6G'):
                used.append((abbr, meaning))
        elif _uses(text, abbr):
            used.append((abbr, meaning))
    used.sort(key=lambda x: x[0].lower())
    half = (len(used) + 1) // 2
    rows = [(used[i], used[i + half] if i + half < len(used) else ('', '')) for i in range(half)]
    out = ['| Term | Meaning | Term  | Meaning  |', '|' + '-' * 14 + '|' + '-' * 36 + '|' + '-' * 14 + '|' + '-' * 36 + '|']
    out += [f'| {a[0]} | {a[1]} | {b[0]} | {b[1]} |' for a, b in rows]
    return '\n'.join(out)


ALLOWED_PARENS = re.compile(r'^(?:(?:SQ|RQ|C|IC|EC|QA|QS)\d+[a-c]?|Anthropic|n|p\d+|Table|Fig|Section|[IVX]+|[A-Z][a-z]+)$')   # C4a-C4c: the parts of C4


def abbreviation_problems(src):
    """the standard rules, checked on the built text: in the body, every abbreviation used is spelled out once, at or before
    its first use, and is in the list; the abstract defines its own; no abbreviation is spelled out twice"""
    import thematic
    _h, front, body = split_front(src)
    body = _plain(body.split('\n# References')[0])
    abstract = _plain(front.split('**List of Abbreviations**')[0])
    out = []
    for part, text in (('abstract', abstract), ('body', body)):
        for abbr, meaning in thematic.ABBREVIATIONS:
            if abbr in thematic.LABEL_FAMILIES:
                continue
            for a in abbr.split(' / '):
                uses = _uses(text, a)
                if not uses:
                    continue
                defs = [m.start() for m in re.finditer(r'\(' + re.escape(a) + r's?[),;]', text)]
                if a in ('5G', '6G'):                                       # defined together: "(5G and 6G)"
                    defs = sorted(defs + [m.start() for m in re.finditer(r'\(5G and 6G\)', text)])
                if part == 'abstract' and a in ('IoT',):                # in the title only
                    continue
                if not defs:
                    out.append(f'abbreviation {a} ({part}): used but never spelled out')
                    continue
                if uses[0] < defs[0] - len(a) - 2:
                    out.append(f'abbreviation {a} ({part}): used before it is spelled out …{text[max(0, uses[0] - 50):uses[0] + 20]}…')
                if len(defs) > 1:
                    out.append(f'abbreviation {a} ({part}): spelled out {len(defs)} times')
    known = {a for ab, _ in thematic.ABBREVIATIONS for a in ab.split(' / ')} | {a for a, _ in EXTRA_TERMS}
    for m in re.finditer(r'[a-z] \(([A-Z][A-Za-z0-9-]{1,10}?)s?\)', body):
        a = m.group(1)
        if a not in known and not ALLOWED_PARENS.match(a):
            out.append(f'abbreviation {a}: spelled out but not in the list (thematic.ABBREVIATIONS) …{body[max(0, m.start() - 50):m.end()]}…')
    return out


def sort_quality_rows(src):
    """the rows of the quality-appraisal tables and of the two coverage tables (surveys, primary studies) in the order of
    their reference numbers (a row without a number, such as 'This review' or the count of Yes, stays last); the table of the
    closest designs by the conditions of the research gap met (its last column), then in reference order"""
    pat = re.compile(r'(?m)^(Table: Table [IVXL]+\. (?:Quality appraisal of the|What each survey treats|What each primary study does'
                     r'|Primary studies that meet at least two)[^\n]*\n\n\|[^\n]*\n\|[-|]+\|\n)((?:\|[^\n]*\n?)+)')

    def fix(m):
        rows = [r for r in m.group(2).split('\n') if r.strip()]
        num = lambda r: (int(x.group(1)) if (x := re.match(r'^\| \[(\d+)\]', r)) else 10 ** 6)
        if 'Primary studies that meet at least two' in m.group(1):
            met = lambda r: -int(c) if (c := r.rstrip(' |').rsplit('|', 1)[-1].strip()).isdigit() and num(r) < 10 ** 6 else 1
            rows.sort(key=lambda r: (met(r), num(r)))
        else:
            rows.sort(key=num)
        return m.group(1) + '\n'.join(rows) + '\n'
    return pat.sub(fix, src)


def sheet_text(sid, keys):
    f = SHEETS / f'{sid}.json'
    if not f.exists():
        problems.append(f'marker {sid}: no evidence for this study')
        return ''
    s = json.loads(f.read_text(encoding='utf-8'))
    txt = []
    for k in keys:
        a = s.get('answers', {}).get(k)
        if a is None and k in OLD2NEW:                      # a marker of the earlier form: its content is in the merged answer
            a = s.get('answers', {}).get(OLD2NEW[k])
        if a is None:
            problems.append(f'marker {sid}:{k}: no such answer')
            continue
        txt.append(str(a.get('answer', '')) + ' ' + json.dumps(a.get('values', {}), ensure_ascii=False) + ' '
                   + ' '.join(((e.get('quote') or e.get('numbers') or '') or e.get('numbers') or '') for e in a.get('evidence', [])))
    return ' '.join(txt)


def page_text(refkey, page):
    refs = json.loads((P / 'refs.json').read_text(encoding='utf-8'))
    folder = refs.get(refkey, {}).get('folder')
    if not folder:
        problems.append(f'marker F:{refkey}: no folder for this source')
        return ''
    f = ROOT / folder / 'text' / 'pages' / f'page_{int(page):04d}.txt'
    if not f.exists():
        problems.append(f'marker F:{refkey}:{page}: no such page')
        return ''
    return f.read_text(encoding='utf-8', errors='ignore')


def check_markers(text):
    """Each marked sentence: the numbers it states must occur in the cited answers or pages."""
    plain = re.sub(r'\{\{[^}]*\}\}|\[@[^\]]*\]', '', text)
    for m in re.finditer(r'([^⟦⟧]*?)((?:\s*⟦[^⟧]+⟧)+)', plain):
        chunk, marks = m.group(1).rstrip(), m.group(2)
        if chunk.endswith('.'):
            chunk = chunk[:-1]
        sentence = re.split(r'(?<=[.!?])\s+|\n', chunk)[-1]          # colons do not end a sentence (all its numbers are checked)
        src = ''
        for mk in re.findall(r'⟦([^⟧]+)⟧', marks):
            if mk.startswith('F:'):
                _, ref, page = mk.split(':')
                for pg in page.split(','):
                    src += ' ' + page_text(ref.strip(), pg.strip())
                continue
            sid, _, ks = mk.partition(':')
            src += ' ' + sheet_text(sid.strip(), [k.strip() for k in ks.split(',')])
        have = {x.replace(',', '').rstrip('.') for x in NUM.findall(src)}       # whole numbers, not substrings
        for num in NUM.findall(sentence):
            n = num.replace(',', '').rstrip('.')
            if n not in have:
                problems.append(f'number {num} not in the cited evidence: …{sentence.strip()[-140:]}')
    return re.sub(r'\s*⟦[^⟧]+⟧', '', text)


WORDS = {w: i for i, w in enumerate('zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen twenty'.split())}
WORDS.update({'twenty-one': 21, 'twenty-two': 22, 'twenty-three': 23, 'twenty-four': 24, 'twenty-five': 25, 'thirty': 30})
# the answer keys of the earlier form (P1-P8, S1-S8) read against the merged form of 15 October 2026 (P1-P3, S1)
OLD2NEW = {'P1': 'P1', 'P1b': 'P1', 'P2': 'P2', 'P3': 'P2', 'P3b': 'P2', 'P7': 'P2', 'P4': 'P3', 'P5': 'P3', 'P6': 'P3', 'P6b': 'P3', 'P8': 'P3',
           'S1': 'S1', 'S2': 'S1', 'S3': 'S1', 'S4': 'S1', 'S5': 'S1', 'S6': 'S1', 'S7': 'S1', 'S8': 'S1'}


def check_group_counts(src):
    """A group heading such as "*Checks by ...* Eight designs ..." must head exactly that many study paragraphs."""
    blocks = re.split(r'(?m)^(?=\*[^*\n]+\*\s+\w+ (?:designs|surveys)\b|#)', src)
    for b in blocks:
        m = re.match(r'\*([^*\n]+)\*\s+(\w+) (designs|surveys)\b', b)
        if not m:
            continue
        n = len(re.findall(r'\{\{STUDY:\w+\}\}', b))
        if WORDS.get(m.group(2).lower()) != n:
            problems.append(f'group "{m.group(1)[:50]}" says {m.group(2)} {m.group(3)} but lists {n}')


def fmt(v):
    return f'{v:,}' if isinstance(v, int) and abs(v) >= 1000 else str(v)


def main(version, check_only=False):
    OUTDIR.mkdir(exist_ok=True)
    out = OUTDIR / f'{NAME} - V{version}.docx'
    if out.exists() and not check_only:
        sys.exit(f'{out.name} exists; versions are never overwritten')
    S = studies()
    src = '\n\n'.join(f.read_text(encoding='utf-8') for f in sorted(PARTS.glob('*.md')))
    used = re.findall(r'\{\{STUDY:(\w+)\}\}', src)
    for sid in used:
        if sid not in S:
            problems.append(f'study paragraph {sid} missing')
    check_group_counts(src)
    # worded claims ("tested by none", "one design") against the records (check_claims.py)
    cc = subprocess.run([sys.executable, str(pathlib.Path(__file__).with_name('check_claims.py'))], capture_output=True, text=True)
    if cc.returncode:
        problems.extend('claim: ' + l.strip() for l in cc.stdout.splitlines() if l.strip().startswith('FAIL'))
    src = re.sub(r'\{\{STUDY:(\w+)\}\}', lambda m: S.get(m.group(1), ''), src)
    cl = json.loads((B / 'cites.json').read_text(encoding='utf-8'))   # {{C:key}}: the studies behind a computed count
    def cite_list(m):
        if m.group(1) not in cl:
            problems.append(f'unknown citation list {m.group(1)}')
            return ''
        ids = cl[m.group(1)]
        return '[' + '; '.join('@' + i for i in ids) + ']' if ids else ''
    src = re.sub(r'\s?\{\{C:(\w+)\}\}', lambda m: (' ' + cite_list(m)) if cl.get(m.group(1)) else cite_list(m), src)
    src = define_once(src)
    _h, _f, _b = split_front(src)
    src = _h + _f + consistent_forms(_b)
    src = check_markers(src)
    n_boxes = len(TAKEAWAYS.findall(src))
    src = TAKEAWAYS.sub(takeaways, src)                           # Key Takeaways boxes (one per section)
    for m in re.finditer(r'\[@[^\]]*;[^\]]*\][^.]{0,250}?\b(the first|the second|the former|the latter|respectively)\b', src):
        problems.append(f'order-dependent "{m.group(1)}" after a grouped citation, which the build renumbers and may reorder: …{m.group(0)[:120]}')
    src = re.sub(r'(?m)^(?!\s*$)(?![-*] |\d+\. |\|)(.+)\n(?=(?:- |\d+\. ))', r'\1\n\n', src)
    stats = json.loads((B / 'stats.json').read_text())

    def num(m):
        k = m.group(1)
        if k not in stats:
            problems.append(f'unknown number {k}')
            return '??'
        return fmt(stats[k])
    def unnumbered(m):                                            # {{LIST:key}}: a table without number or caption
        if m.group(1) == 'abbrev':
            return '@@ABBREVIATIONS@@'                            # filled from the final text (abbreviation_list)
        f = B / 'tables' / f'{m.group(1)}.md'
        if not f.exists():
            problems.append(f'list {m.group(1)} missing')
            return ''
        return re.sub(r'^Table: .*\n\n', '', f.read_text(encoding='utf-8'), count=1)
    src = re.sub(r'^\{\{LIST:(\w+)\}\}[ \t]*$', unnumbered, src, flags=re.M)
    tabs, figs = {}, {}
    for m in re.finditer(r'^\{\{(TAB|FIG):(\w+)\}\}[ \t]*$', src, re.M):
        d = tabs if m.group(1) == 'TAB' else figs
        if m.group(2) not in d:
            d[m.group(2)] = len(d) + 1

    def place(m):
        kind, key = m.group(1), m.group(2)
        if kind == 'TAB':
            f = B / 'tables' / f'{key}.md'
            if not f.exists():
                problems.append(f'table {key} missing')
                return ''
            t = f.read_text(encoding='utf-8').replace('Table: ', f'Table: Table {roman(tabs[key])}. ', 1)
            return f'{PORTRAIT_END}\n\n{t}\n{LANDSCAPE_END}\n' if key in LANDSCAPE_TABLES else t
        f = B / 'figures' / f'{key}.png'
        if not f.exists():
            problems.append(f'figure {key} missing')
        return f'![Fig. {figs[key]}. {FIGCAP.get(key, "")}]({f}){{width=100%}}'
    seen = set()

    def place_once(m):
        k = (m.group(1), m.group(2))
        if k in seen:
            return ''
        seen.add(k)
        return place(m)
    src = re.sub(r'^\{\{(TAB|FIG):(\w+)\}\}[ \t]*$', place_once, src, flags=re.M)
    src = re.sub(r'\{\{N:(\w+)\}\}', num, src)                     # after placing: tables may hold numbers too

    def ref(m):
        kind, key = m.group(1), m.group(2)
        d = tabs if kind == 'TAB' else figs
        if key not in d:
            problems.append(f'{kind} {key} referenced but never placed')
            return '??'
        return f'Table {roman(d[key])}' if kind == 'TAB' else f'Fig. {d[key]}'
    src = re.sub(r'\{\{(TAB|FIG):(\w+)\}\}', ref, src)
    _h, _f, _b = split_front(src)                                  # tables are placed now: their labels follow the rule too
    src = _h + _f + consistent_forms(_b)
    src = src.replace('@@ABBREVIATIONS@@', abbreviation_list(src))
    refs = json.loads((P / 'refs.json').read_text(encoding='utf-8'))
    order = []

    def cite(m):
        nums = []
        for key in re.findall(r'@([\w-]+)', m.group(1)):
            if key not in refs:
                problems.append(f'citation {key} has no reference')
                continue
            if key not in order:
                order.append(key)
            nums.append(order.index(key) + 1)
        nums = sorted(set(nums))
        out, i = [], 0
        while i < len(nums):                                         # [3]–[6] for runs of three or more
            j = i
            while j + 1 < len(nums) and nums[j + 1] == nums[j] + 1:
                j += 1
            out.append(f'[{nums[i]}]–[{nums[j]}]' if j - i >= 2 else ', '.join(f'[{n}]' for n in nums[i:j + 1]))
            i = j + 1
        return ', '.join(out)
    src = re.sub(r'\[(@[^\]]+)\]', cite, src)
    src = sort_quality_rows(src)                                  # quality tables: rows in the order of the reference list
    unused = [r['corpus_id'] for k, r in refs.items() if r.get('corpus_id') and k not in order]
    if unused:
        problems.append(f'included studies never cited: {unused}')
    src += '\n\n# References\n\n' + '\n\n'.join(f'[{i}] {refs[k]["ieee"]}' for i, k in enumerate(order, 1)) + '\n'
    body = src.split('---', 2)[-1] if src.startswith('---') else src
    for pat, what in ((r'\{\{', 'unresolved placeholder'), (r'\{(?:N|TAB|FIG|STUDY|CITES):\w+\}', 'placeholder with single braces (an f-string?)'),
                      (r'⟦', 'marker left'), (r'\[@', 'citation left')):
        if re.search(pat, src):
            problems.append(what)
    text = re.sub(r'\(.*?\.png\)', '', body)
    decl = re.search(r'(?ms)^# Declarations\s*$.*?(?=^# )', text)        # the tool is named where the use of AI is declared
    for m in BANNED.finditer(text):
        if m.group(0).lower() == 'claude code' and decl and decl.start() <= m.start() < decl.end():
            continue
        problems.append(f'word not for a paper: "{m.group(0)}" …{text[max(0, m.start() - 60):m.start() + 20]}')
    import thematic
    problems.extend(abbreviation_problems(src))
    (B / f'paper-V{version}.md').write_text(src, encoding='utf-8')
    report = {'version': version, 'output': out.name, 'problems': problems, 'tables': tabs, 'figures': figs,
              'citations': order, 'studies': used, 'numbers_available': len(stats), 'words': len(re.findall(r'\w+', re.sub(r'```\{=openxml\}.*?```', lambda m: ' '.join(re.findall(r'<w:t[^>]*>([^<]*)</w:t>', m.group(0))), body, flags=re.S)))}
    (B / f'BUILD-REPORT-V{version}.json').write_text(json.dumps(report, indent=1, ensure_ascii=False), encoding='utf-8')
    if problems:
        print('\n'.join(problems[:60]))
        sys.exit(f'{len(problems)} problem(s); nothing rendered')
    if check_only:
        print(f'checks pass: {n_boxes} takeaway boxes, {len(tabs)} tables, {len(figs)} figures, {len(order)} references, {len(used)} study paragraphs, ~{report["words"]:,} words')
        return
    look = L.render(B / f'paper-V{version}.md', out, B)               # pandoc in the Review Viewer's look (paper_look.py)
    if look['styles_not_in_look']:
        print('paragraph styles the shared look does not set (add them to paper_look.py):', look['styles_not_in_look'])
    import importlib.util                                         # the package fixes of the earlier build (comments part, PNG type)
    spec = importlib.util.spec_from_file_location('build_v4', ROOT / 'scripts' / 'paper' / 'build.py')
    B0 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(B0)
    B0.fix_comments_part(out)
    import links                                                  # evidence pages for the Review Viewer (build/LINKS-V<n>.json)
    links.main(version)
    checks = P / f'AUTHOR-CHECKS-V{version}.json'
    if checks.exists():
        py = ROOT / 'scripts' / '.venv' / 'bin' / 'python'
        subprocess.run([str(py if py.exists() else sys.executable), str(ROOT / 'scripts' / 'review' / 'annotate_author_checks.py'), str(out),
                        str(out.with_name(f'{NAME} - V{version} with author checks.docx'))], check=True, env={**os.environ, 'AUTHOR_CHECKS': str(checks)})
    print(f'written {out.name}: {len(tabs)} tables, {len(figs)} figures, {len(order)} references, {len(used)} study paragraphs, ~{report["words"]:,} words')


if __name__ == '__main__':
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    main(sys.argv[1], '--check' in sys.argv)
