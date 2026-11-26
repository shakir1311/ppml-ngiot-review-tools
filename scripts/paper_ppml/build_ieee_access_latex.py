#!/usr/bin/env python3
"""Renders a built version of the PPML review into the IEEE Access LaTeX template (the author, 20 October 2026: "lets also do a
latex version"): the build's markdown (build/paper-V<n>.md) becomes a self-contained LaTeX folder on the template's class
(myliteraturereviewpaper/ppml2026/ieee-access-template/latex/…/ieeeaccess.cls, with its fonts and logos copied beside the
source). Pandoc converts the running text; this script writes the front matter with the template's macros (history, DOI, title,
author, address, funding footnote, running head, corresponding author, abstract, keywords), drops the Key Takeaways boxes and
the abbreviation list as in the Word rendering, turns every numbered citation into \\cite of a thebibliography built from the
reference list, every "Fig. n" and "Table n" mention into a \\ref, every table into a full-width table* (or, where it would not
fit a page, successive table* floats sharing its number) with widths taken from the markdown's column rule, and every
figure into a full-width figure* of the trimmed PNG, capped at the page height. Facts only the author can supply stay as
[AUTHOR: …] markers. With --compile the folder is compiled twice with pdflatex and the page count and log problems are printed.
Writes "<NAME> - V<n> IEEE Access LaTeX/" beside the paper (never over an existing folder).
Usage: python3 scripts/paper_ppml/build_ieee_access_latex.py <version> [--compile] [--out <folder>]   (--out: a trial build elsewhere)
"""
import os, pathlib, re, shutil, subprocess, sys, tempfile

ROOT = pathlib.Path(__file__).resolve().parents[2]
P = ROOT / 'myliteraturereviewpaper' / 'ppml2026'; B = P / 'build'
TPL = P / 'ieee-access-template' / 'latex' / 'ACCESS_latex_template_20260513'
OUT = ROOT / 'myliteraturereviewpaper' / 'PPML in NextGeneration IoT'
NAME = 'Privacy Preserving Machine Learning in NextGeneration IoT'
ROMAN = {r: i for i, r in enumerate(['I', 'II', 'III', 'IV', 'V', 'VI', 'VII', 'VIII', 'IX', 'X', 'XI', 'XII', 'XIII', 'XIV', 'XV', 'XVI', 'XVII', 'XVIII', 'XIX', 'XX'], 1)}
UNNUMBERED = ('Declarations', 'Appendix', 'References', 'Acknowledgment', 'Acknowledgement')
TEXT_W_PT = 504.7          # \textwidth of the class (177.53 mm)
TEXT_H_PT = 672.0          # \textheight of the class
TABCOLSEP_PT = 3.0
CHUNK_PT = 500.0           # with no measurement (pdflatex failed): a table whose estimated height passes this is set in pieces, "(continued)" after the first
COL_W_PT = 242.4           # \columnwidth of the class (85.29 mm)
COL_H_MAX = 0.85 * TEXT_H_PT   # a table of at most 3 columns that fits this in one column is set as a single-column float (V86)
RESOURCES = ('ieeeaccess.cls', 'spotcolor.sty', 'logo.png', 'notaglinelogo.png', 'bullet.png')

PREAMBLE = r"""\documentclass{ieeeaccess}
\usepackage{cite}
\usepackage{amsmath,amssymb,amsfonts}
\usepackage{algorithmic}
\usepackage{graphicx}
\usepackage{textcomp}
\usepackage{bm}
\usepackage{array}
\usepackage[utf8]{inputenc}
\usepackage{placeins}
\usepackage{float}
\usepackage{url}
\makeatletter\@ifpackageloaded{hyperref}{}{\usepackage[hidelinks]{hyperref}}\makeatother
\setcounter{topnumber}{3}\setcounter{bottomnumber}{2}\setcounter{totalnumber}{5}\setcounter{dbltopnumber}{3}
\renewcommand{\topfraction}{0.95}\renewcommand{\bottomfraction}{0.6}\renewcommand{\dbltopfraction}{0.95}
\renewcommand{\textfraction}{0.05}\renewcommand{\floatpagefraction}{0.75}\renewcommand{\dblfloatpagefraction}{0.75}
\makeatletter
\AtBeginDocument{\DeclareMathVersion{bold}
\SetSymbolFont{operators}{bold}{T1}{times}{b}{n}
\SetSymbolFont{NewLetters}{bold}{T1}{times}{b}{it}
\SetMathAlphabet{\mathrm}{bold}{T1}{times}{b}{n}
\SetMathAlphabet{\mathit}{bold}{T1}{times}{b}{it}
\SetMathAlphabet{\mathbf}{bold}{T1}{times}{b}{n}
\SetMathAlphabet{\mathtt}{bold}{OT1}{pcr}{b}{n}
\SetSymbolFont{symbols}{bold}{OMS}{cmsy}{b}{n}
\renewcommand\boldmath{\@nomath\boldmath\mathversion{bold}}}
\makeatother
\providecommand{\tightlist}{\setlength{\itemsep}{0pt}\setlength{\parskip}{0pt}}
\setlength{\tabcolsep}{3pt}
"""


# ---------------------------------------------------------------- the markdown, taken apart
def front_matter(md):
    m = re.match(r'---\n(.*?)\n---\n', md, flags=re.S); front = m.group(1) if m else ''; body = md[m.end():] if m else md
    title = re.search(r'^title:\s*"(.*)"', front, flags=re.M); title = title.group(1) if title else NAME
    author = re.search(r'^author:\s*"(.*)"', front, flags=re.M); author = author.group(1) if author else ''
    abstract = re.search(r'^\*\*Abstract\*\*\s*[—-]\s*(.*?)\n\n', body, flags=re.S | re.M)
    terms = re.search(r'^\*\*Index Terms\*\*\s*[—-]\s*(.*?)\n\n', body, flags=re.S | re.M)
    body = re.sub(r'^\*\*Abstract\*\*.*?\n\n', '', body, count=1, flags=re.S | re.M)
    body = re.sub(r'^\*\*Index Terms\*\*.*?\n\n', '', body, count=1, flags=re.S | re.M)
    body = re.sub(r'^\*\*List of Abbreviations\*\*\n\n(\|.*\n)+\n?', '', body, count=1, flags=re.M)      # defined at first use in the text
    body = re.sub(r'^```\{=openxml\}\n.*?^```\n', '', body, flags=re.S | re.M)                              # the Key Takeaways boxes
    return title, author, abstract.group(1).strip() if abstract else '', terms.group(1).strip() if terms else '', body


def cites(text):
    """every run of numbered citations ([3], [4]–[6], [9]) becomes one \\cite of the reference keys; cite merges them again"""
    unit = r'\[(\d+)\](?:–\[(\d+)\])?'
    run = re.compile(unit + r'(?:,? ' + unit + r')*')          # "[1], [2]" and the text's "[1] [2]" alike
    def expand(m):
        ids = []
        for a, b in re.findall(unit, m.group(0)):
            ids.extend(range(int(a), int(b) + 1) if b else [int(a)])
        return '\\cite{' + ','.join(f'r{i}' for i in ids) + '}'
    return run.sub(expand, text)


def split_blocks(body):
    """the body as a list of ('text', md) | ('table', number, caption_md, header, aligns, widths, rows) | ('figure', number,
    caption_md, path) | ('refs', [(n, md)]) blocks; captions and in-text mentions lose the numbers the class adds"""
    lines = body.split('\n'); blocks = []; text = []; i = 0
    def flush():
        if text: blocks.append(('text', '\n'.join(text))); text.clear()
    while i < len(lines):
        ln = lines[i]
        if ln.startswith('# References'):
            flush(); refs = []
            for r in lines[i + 1:]:
                m = re.match(r'^\[(\d+)\] (.*)', r)
                if m: refs.append((int(m.group(1)), m.group(2).strip()))
            blocks.append(('refs', refs)); break
        if ln.startswith('|') and i + 1 < len(lines) and re.match(r'^\|[\s:|-]+\|$', lines[i + 1]):
            cap = ''
            while text and not text[-1].strip(): text.pop()
            if text and text[-1].startswith('Table: '): cap = text.pop()[7:]                        # the caption before the table
            while text and not text[-1].strip(): text.pop()
            j = i; rows = []
            while j < len(lines) and lines[j].startswith('|'): rows.append(lines[j]); j += 1
            if not cap:                                                                               # or after it, unless it belongs to the next table
                k = j
                while k < len(lines) and not lines[k].strip(): k += 1
                if k < len(lines) and lines[k].startswith('Table: '):
                    n = k + 1
                    while n < len(lines) and not lines[n].strip(): n += 1
                    if not (n < len(lines) and lines[n].startswith('|')): cap = lines[k][7:]; j = k + 1
            flush()
            cells = lambda r: [c.strip() for c in r.strip().strip('|').split('|')]
            sep = cells(rows[1]); aligns = ['r' if s.endswith(':') and not s.startswith(':') else 'l' for s in sep]
            dashes = [max(1, s.count('-')) for s in sep]; tot = sum(dashes); widths = [d / tot for d in dashes]
            m = re.match(r'Table ([IVX]+)\. (.*)', cap); num = ROMAN[m.group(1)] if m else len([b for b in blocks if b[0] == 'table']) + 1
            note, k = '', j                                                   # V95: the note under a table goes into its float, not the text flow
            while k < len(lines) and not lines[k].strip(): k += 1
            if k < len(lines) and re.fullmatch(r'\*[^*].*[^*]\*', lines[k].strip()):
                note, j = lines[k].strip()[1:-1], k + 1
            blocks.append(('table', num, m.group(2) if m else cap, cells(rows[0]), aligns, widths, [cells(r) for r in rows[2:]], note))
            i = j; continue
        m = re.match(r'^!\[Fig\. (\d+)\. (.*)\]\((.*?)\)(\{.*\})?$', ln)
        if m:
            flush(); blocks.append(('figure', int(m.group(1)), m.group(2), m.group(3))); i += 1; continue
        text.append(ln); i += 1
    flush()
    return blocks


def pandoc(md):
    return subprocess.run(['pandoc', '-f', 'markdown', '-t', 'latex', '--wrap=none'], input=md, capture_output=True, text=True, check=True).stdout.strip()


def pandoc_many(snippets):
    """one pandoc call for many inline snippets (cells, captions): each sits between marker paragraphs"""
    doc = ''.join(f'\n\nZZMARK{k}ZZ\n\n{s}' for k, s in enumerate(snippets)) + f'\n\nZZMARK{len(snippets)}ZZ\n\n'
    tex = pandoc(doc); out = []
    for k in range(len(snippets)):
        m = re.search(rf'ZZMARK{k}ZZ\n*(.*?)\n*ZZMARK{k + 1}ZZ', tex, flags=re.S)
        out.append(m.group(1).strip() if m else '')
    return out


def refs_fix(tex):
    """the marks left in the text become \\ref, and a few characters the fonts lack become their macros"""
    tex = re.sub(r'FIGREF(\d+)', r'Fig.~\\ref{fig:\1}', tex)
    tex = re.sub(r'TABREF(\d+)', r'Table~\\ref{tab:\1}', tex)
    return tex.replace('\xa0', '~').replace('•', '\\textbullet{}')


def mark_mentions(md):
    md = re.sub(r'\bFig\. (\d+)\b', r'FIGREF\1', md)
    md = re.sub(r'\bTable ([IVX]+)\b(?!\w)', lambda m: f'TABREF{ROMAN[m.group(1)]}' if m.group(1) in ROMAN else m.group(0), md)
    return md


def heading_fix(md):
    md = re.sub(r'^# ([IVX]+)\. ', '# ', md, flags=re.M)
    md = re.sub(r'^## ([A-Z])\. ', '## ', md, flags=re.M)
    md = re.sub(r'^# ((?:' + '|'.join(UNNUMBERED) + r').*)$', r'# \1 {-}', md, flags=re.M)
    return md


# ---------------------------------------------------------------- tables and figures
def row_heights(header, rows, widths, font_pt, total_w=TEXT_W_PT):
    """a rough height in points of the header and of each row: lines from the characters a cell holds against the characters
    its column fits, at the font's size, in a table total_w wide"""
    char_pt = 0.5 * font_pt; line_pt = 1.2 * font_pt + 1.0
    usable = total_w - 2 * TABCOLSEP_PT * len(widths)
    def lines(cells):
        return max(max(1, -(-len(c) // max(4, int(w * usable / char_pt)))) for c, w in zip(cells, widths)) if cells else 1
    return lines(header) * line_pt, [lines(r) * line_pt for r in rows]


def spec_of(aligns, widths, total_w, unit):
    usable = (total_w - 2 * TABCOLSEP_PT * len(widths) - 2) / total_w
    return ''.join(('>{\\raggedleft\\arraybackslash}' if a == 'r' else '>{\\raggedright\\arraybackslash}') + f'p{{{w * usable:.4f}{unit}}}' for a, w in zip(aligns, widths))


def header_tex(header):
    return ' & '.join(f'\\textbf{{{h}}}' if h else '' for h in header) + ' \\\\'


def row_tex(r, ncol):
    return ' & '.join(r + [''] * (ncol - len(r))) + ' \\\\'


def measure_tables(tables):
    """the exact height of every header and row of every table, typeset once by pdflatex in the class at the table's own widths
    (V93: the earlier estimate, half the font size per character, overstated heights and cut tables that fit a page, and LaTeX
    then set two or three pieces of one table on the same page). Returns {(num, 'col'|'text'): (header_pt, [row_pt, …])}."""
    import tempfile
    lines = []
    for num, cap, header, aligns, widths, rows, font, *_ in tables:
        ncol = len(widths)
        for kind, total_w, unit in (('text', TEXT_W_PT, '\\textwidth'),) + ((('col', COL_W_PT, '\\columnwidth'),) if ncol <= 3 else ()):
            spec = spec_of(aligns, widths, total_w, unit)
            for i, r in enumerate([None] + rows):
                body = header_tex(header) if r is None else row_tex(r, ncol)
                lines.append(f'\\setbox0=\\vbox{{{font}\\begin{{tabular}}{{{spec}}}{body}\\end{{tabular}}}}'
                             f'\\typeout{{MEAS:{num}:{kind}:{i}:\\the\\ht0:\\the\\dp0}}')
    doc = PREAMBLE + '\n\\begin{document}\n' + '\n'.join(lines) + '\n\\end{document}\n'
    with tempfile.TemporaryDirectory() as tmp:
        for f in TPL.iterdir():
            if f.name in RESOURCES or f.suffix in ('.pfb', '.tfm', '.map', '.fd'): shutil.copy2(f, pathlib.Path(tmp) / f.name)
        (pathlib.Path(tmp) / 'measure.tex').write_text(doc, encoding='utf-8')
        r = subprocess.run(['pdflatex', '-interaction=nonstopmode', 'measure.tex'], cwd=tmp, capture_output=True, text=True)
        log = (pathlib.Path(tmp) / 'measure.log').read_text(encoding='utf-8', errors='replace')
    out = {}
    for num, kind, i, ht, dp in re.findall(r'MEAS:(\d+):(\w+):(\d+):([\d.]+)pt:([\d.]+)pt', log):
        hdr, rws = out.setdefault((int(num), kind), [0.0, []])
        h = float(ht) + float(dp)
        if int(i) == 0: out[(int(num), kind)][0] = h
        else: rws.append(h)
    if not out:
        print('table measurement failed; the estimate is used')
    return out


CAPTION_PT = 30.0          # a caption of up to two lines and its skip
RULES_PT = 3.0             # the three \hline rules
PAGE_FLOAT_PT = TEXT_H_PT - 16.0   # the most a float may hold and still go to the top of a page


def table_tex(num, cap, header, aligns, widths, rows, font, note='', meas=None):
    """one table* float, or, for a table taller than a page, successive table* floats that share the number (the class has no
    page-crossing table in its two-column grid): the first carries the caption, the others "(continued)" and the header row.
    With meas (measure_tables) the heights are exact and a table is split only when it cannot fit on one page; each piece
    then fills a page, so two pieces never share one (V93)"""
    ncol = len(widths); font_pt = {'\\footnotesize': 8, '\\scriptsize': 7}[font]
    note_pt = lambda w: (len(re.sub(r'\\[a-zA-Z]+|[{}]', '', note)) * 7 * 0.5 / w + 1) * 7 * 1.25 + 4 if note else 0   # an estimate of the note's lines at 7 pt
    # a narrow table that fits one column goes in the column flow, where LaTeX has four times the places for it (V86)
    env, total_w, unit, kind = 'table*', TEXT_W_PT, '\\textwidth', 'text'
    if ncol <= 3:
        if meas and (num, 'col') in meas:
            h1, hs = meas[(num, 'col')]
        else:
            h1, hs = row_heights(header, rows, widths, font_pt, COL_W_PT)
        if h1 + sum(hs) + CAPTION_PT + RULES_PT + note_pt(COL_W_PT) <= COL_H_MAX: env, total_w, unit, kind = 'table', COL_W_PT, '\\columnwidth', 'col'
    spec = spec_of(aligns, widths, total_w, unit)
    hdr = header_tex(header)
    if meas and (num, kind) in meas and len(meas[(num, kind)][1]) == len(rows):
        h_hdr, h_rows = meas[(num, kind)]; limit = PAGE_FLOAT_PT
    else:
        h_hdr, h_rows = row_heights(header, rows, widths, font_pt, total_w); limit = CHUNK_PT
    chunks = [[]]; used = h_hdr + CAPTION_PT + RULES_PT
    if used + sum(h_rows) + note_pt(total_w) > limit:
        for r, h in zip(rows, h_rows):
            if chunks[-1] and used + h > limit: chunks.append([]); used = h_hdr + CAPTION_PT + RULES_PT
            chunks[-1].append(r); used += h
    else:
        chunks = [rows]
    out = []
    for k, chunk in enumerate(chunks):
        body = '\n'.join(row_tex(r, ncol) for r in chunk)
        caption = f'\\caption{{{cap}}}\\label{{tab:{num}}}' if k == 0 else f'\\addtocounter{{table}}{{-1}}\\caption{{(continued)}}'
        place = ('[!tb]' if env == 'table*' else '[!htb]') if os.environ.get('PPML_LATEX_PLACEMENT', 'tb') == 'tb' else ('[tbp]' if env == 'table*' else '[H]')
        # tb (the default since V88): floats go to the top or bottom of a column, never to a page of their own, which left half pages empty; H anchored a narrow table where cited but dragged the text after it to the next column
        foot = (f'\n\\par\\vspace{{3pt}}{{\\scriptsize\\raggedright\\emph{{{note}}}\\par}}' if note and k == len(chunks) - 1 else '')   # V95: under its table
        out.append(f'\\begin{{{env}}}{place}\n{caption}\n\\centering{font}\n'
                   f'\\begin{{tabular}}{{{spec}}}\n\\hline\n{hdr}\n\\hline\n{body}\n\\hline\n\\end{{tabular}}{foot}\n\\end{{{env}}}')
    return '\n\n'.join(out)


FLOAT_ENV = re.compile(r'\\begin\{(figure\*|table\*|table)\}.*?\\end\{\1\}', re.S)


def hoist_floats(body):
    """every float defined just before the paragraph that first mentions it (V96). The builder set each float where the markdown
    placed it, after the paragraph that cites it or later; a two-column float can appear only from the page after the one where
    it is defined, so Figs. 5 to 7 of V95 sat two pages after their sections. A float is moved only earlier, and under a section heading
    rather than before it, and a "(continued)" piece of a split table (it has no label) keeps its place after the first piece."""
    floats = []
    def take(m):
        floats.append(m.group(0)); return f'@@FLOAT{len(floats) - 1}@@'
    paras = FLOAT_ENV.sub(take, body).split('\n\n')
    before = {}                                                     # paragraph -> the floats moved before it, in their own order
    for i, f in enumerate(floats):
        lab = re.search(r'\\label\{((?:fig|tab):\d+)\}', f)
        if not lab:
            continue
        tok = f'@@FLOAT{i}@@'
        home = next(k for k, q in enumerate(paras) if tok in q)
        first = next((k for k, q in enumerate(paras) if re.search(r'\\ref\{' + re.escape(lab.group(1)) + r'\}', q)), None)   # floats are tokens here, so a caption's \\ref cannot match
        if first is not None and first < home:
            paras[home] = paras[home].replace(tok, '').strip('\n')
            before.setdefault(first, []).append(tok)
    for k, toks in before.items():                                  # LaTeX numbers floats in the order of the source: keep it
        h = re.match(r'(\s*\\(?:sub)*section\*?\{[^\n]*\}[^\n]*\n)', paras[k])     # a heading stays first: the floats go under it
        lead = '\n\n'.join(toks) + '\n\n'
        paras[k] = (h.group(1) + lead + paras[k][h.end():]) if h else (lead + paras[k])
    out = '\n\n'.join(q for q in paras if q.strip())
    for i, f in enumerate(floats):
        out = out.replace(f'@@FLOAT{i}@@', f)
    return out


def figure_tex(num, cap, name):
    return (f'\\begin{{figure*}}[!tb]\n\\centering\n'
            f'\\includegraphics[width=\\textwidth,height=0.86\\textheight,keepaspectratio]{{figures/{name}}}\n'
            f'\\caption{{{cap}}}\\label{{fig:{num}}}\n\\end{{figure*}}')


# ---------------------------------------------------------------- assembly
def main(version, compile_pdf=False, out=None):
    md = (B / f'paper-V{version}.md').read_text(encoding='utf-8')
    title, author, abstract, terms, body = front_matter(md)
    blocks = split_blocks(heading_fix(body))
    # every inline snippet (cells, captions, abstract, terms, references) through one pandoc call
    snippets = [abstract, terms]; slots = {}
    for bi, b in enumerate(blocks):
        if b[0] == 'table':
            slots[bi] = len(snippets); snippets.append(mark_mentions(cites(b[2])))
            snippets.extend(mark_mentions(cites(c)) for c in b[3]); snippets.extend(mark_mentions(cites(c)) for r in b[6] for c in r)
            snippets.append(mark_mentions(cites(b[7])) if b[7] else '')
        elif b[0] == 'figure':
            slots[bi] = len(snippets); snippets.append(mark_mentions(cites(b[2])))
        elif b[0] == 'refs':
            slots[bi] = len(snippets); snippets.extend(t for _, t in b[1])
    tex_snips = [refs_fix(s) for s in pandoc_many(snippets)]
    abstract_tex, terms_tex = tex_snips[0], tex_snips[1]
    parts = []; bib = []; figures = []; pending = []
    for bi, b in enumerate(blocks):
        if b[0] == 'text':
            tex_part = refs_fix(pandoc(mark_mentions(cites(b[1]))))
            # no barrier at sections: it emptied the rest of a page whenever a section's floats were still pending (the author, 2 November 2026:
            # a drift of a page is acceptable, empty half pages are not); the only barrier sits before the acknowledgment and the references
            parts.append(tex_part)
        elif b[0] == 'table':
            k = slots[bi]; cap = tex_snips[k]; ncol = len(b[3]); hdr = tex_snips[k + 1:k + 1 + ncol]
            cells = tex_snips[k + 1 + ncol:k + 1 + ncol + ncol * len(b[6])]
            rows = [cells[r * ncol:(r + 1) * ncol] for r in range(len(b[6]))]
            font = '\\scriptsize' if ncol >= 6 or any(len(c) > 400 for r in b[6] for c in r) else '\\footnotesize'
            note = tex_snips[k + 1 + ncol + ncol * len(b[6])] if b[7] else ''
            pending.append((b[1], cap, hdr, b[4], b[5], rows, font, note)); parts.append(('TABLE', len(pending) - 1))
        elif b[0] == 'figure':
            src = pathlib.Path(b[3]); figures.append(src)
            parts.append(figure_tex(b[1], tex_snips[slots[bi]], src.name))
        elif b[0] == 'refs':
            k = slots[bi]; bib = [f'\\bibitem{{r{n}}} {tex_snips[k + j]}' for j, (n, _) in enumerate(b[1])]
    meas = measure_tables(pending)                                   # exact heights of every row (V93)
    parts = [table_tex(*pending[p[1]], meas=meas) if isinstance(p, tuple) and p[0] == 'TABLE' else p for p in parts]
    surname = author.split(',')[0].strip().split()[-1]
    short_title = re.sub(r'\s*\(NG-IoT\)', '', title).split(':')[0]
    head = (f'\\vol{{XX}}\\year{{2026}}\n'                                   # the footer's "VOLUME XX, 2026" (the class defaults to 11, 2023)
            f'\\history{{Date of publication xxxx 00, 0000, date of current version xxxx 00, 0000.}}\n'
            f'\\doi{{10.1109/ACCESS.2026.Doi Number}}\n\n\\title{{{title}}}\n'
            f'\\author{{\\uppercase{{Shakir Zareen}}\\authorrefmark{{1}} (ORCID 0009-0005-2841-4373), \\uppercase{{Shailendra Rathore}}\\authorrefmark{{1}}, \\uppercase{{Laith Al-Jobouri}}\\authorrefmark{{1}}, and \\uppercase{{Sanaz Kavianpour}}\\authorrefmark{{1}} [AUTHOR: the co-authors\' ORCIDs and IEEE memberships]}}\n'
            f'\\address[1]{{Faculty of Design, Informatics and Business, Abertay University, Dundee DD1 1HG, U.K. (e-mail: s.zareen2400@abertay.ac.uk)}}\n'
            f'\\tfootnote{{[AUTHOR: funding and support statement, as the template\'s first footnote: ``This work was supported in part by \\ldots\'\'.]}}\n\n'
            f'\\markboth\n{{{surname}: {short_title}}}\n{{{surname}: {short_title}}}\n\n'
            f'\\corresp{{Corresponding author: Shakir Zareen (e-mail: s.zareen2400@abertay.ac.uk).}}\n\n'
            f'\\begin{{abstract}}\n{abstract_tex}\n\\end{{abstract}}\n\n\\begin{{keywords}}\n{terms_tex}\n\\end{{keywords}}\n\n\\titlepgskip=-21pt\n\n\\maketitle\n')
    ai_tab = next((b[1] for b in blocks if b[0] == 'table' and 'Use of generative AI' in b[2]), None)
    ack = (f'\n\\section*{{Acknowledgment}}\nClaude (Anthropic) was used as described in Table~\\ref{{tab:{ai_tab}}}; the reviewer verified its output and is responsible for the content.\n') if ai_tab else '\n'
    # no barrier before the references (V96 tried one: with too little end-matter text beside the end tables it emptied half pages;
    # appendix tables at the tops of reference pages are the class's ordinary float placement)
    tail = (ack + '\n\\begin{thebibliography}{00}\n\n' + '\n\n'.join(bib) + '\n\n\\end{thebibliography}\n\n'
            '\\begin{IEEEbiographynophoto}{SHAKIR ZAREEN} [AUTHOR: biography, and a photograph through the IEEEbiography form of the template.]\n'
            '\\end{IEEEbiographynophoto}\n\n\\EOD\n\n\\end{document}\n')
    tex = PREAMBLE + ('\\raggedbottom\n' if os.environ.get('PPML_LATEX_RAGGED') else '') + '\n\\begin{document}\n\n' + head + '\n' + hoist_floats('\n\n'.join(parts)) + '\n' + tail
    out = pathlib.Path(out) if out else OUT / f'{NAME} - V{version} IEEE Access LaTeX'
    if out.exists(): sys.exit(f'{out.name} exists; versions are never overwritten')
    out.mkdir(); (out / 'figures').mkdir()
    for f in figures: shutil.copy2(f, out / 'figures' / f.name)
    for f in TPL.iterdir():
        if f.name in RESOURCES or f.suffix in ('.pfb', '.tfm', '.map', '.fd'): shutil.copy2(f, out / f.name)
    main_tex = out / f'ppml-ngiot-review-V{version}.tex'; main_tex.write_text(tex, encoding='utf-8')
    print('written', out.relative_to(ROOT) if out.is_relative_to(ROOT) else out, '|', len(bib), 'references,', sum(b[0] == 'table' for b in blocks), 'tables,', len(figures), 'figures')
    if compile_pdf: compile_tex(out, main_tex)


def compile_tex(folder, main_tex):
    for _ in range(3):
        r = subprocess.run(['pdflatex', '-interaction=nonstopmode', '-halt-on-error', main_tex.name], cwd=folder, capture_output=True, text=True)
        if r.returncode:
            err = re.search(r'^! .*?(?=\n\n)', r.stdout, flags=re.S | re.M)
            sys.exit('pdflatex failed:\n' + (err.group(0) if err else r.stdout[-2000:]))
    log = (folder / main_tex.with_suffix('.log').name).read_text(encoding='utf-8', errors='replace')
    pages = re.search(r'Output written on .*? \((\d+) pages', log)
    print('compiled:', pages.group(1) if pages else '?', 'pages |', log.count('Overfull \\hbox'), 'overfull hbox |', log.count('Overfull \\vbox'), 'overfull vbox |',
          len(re.findall(r'LaTeX Warning: (Reference|Citation) .* undefined', log)), 'undefined refs |', log.count('Float too large'), 'floats too large')
    for ext in ('.aux', '.out', '.log'):                                     # the PDF stays for checking; the scratch files go
        f = folder / main_tex.with_suffix(ext).name
        if f.exists(): f.unlink()


if __name__ == '__main__':
    if len(sys.argv) < 2: sys.exit(__doc__)
    main(sys.argv[1], compile_pdf='--compile' in sys.argv, out=sys.argv[sys.argv.index('--out') + 1] if '--out' in sys.argv else None)
