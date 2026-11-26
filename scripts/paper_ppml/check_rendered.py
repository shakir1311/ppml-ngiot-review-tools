#!/usr/bin/env python3
"""Check the rendered files of a built version, not only its markdown (the lesson of 9 November 2026: table numbers left in Roman
numerals in the IEEE Access files survived every check, because every content check read the markdown build and none read what
the reader opens).

For version <n>:
- the IEEE Access Word file: tables and figures counted from the template's paragraph styles (TableTitle, FigCaption), their
  captions numbered 1..n in order; every in-text "Table N" and "Fig. N" arabic and within range, no Roman table number anywhere; no
  leftover token ({{, ⟦, [@, TABREF, FIGREF); no level-2 heading before the first level-1 heading;
- the IEEE Access LaTeX source and PDF: no TABREF, FIGREF, Roman table mention or token left; every \\ref has a \\label; the PDF exists,
  its page count is printed; no two pieces of one table on the same page (a "(continued)" piece must start a new page); every
  table note on the page of its table (its last piece) (V95); every float defined before the paragraph that first cites it, and
  placed at most two pages after its first mention (each float's distance is printed); every LaTeX caption carries the
  paper's caption of its number, and no float is set before one with a lower number (V96);
- the plain Word file: every table mention Roman (that build numbers tables in Roman), no leftover token.
Exit code 1 on any failure.

Usage: python3 scripts/paper_ppml/check_rendered.py <version> [<tag>]     (tag: the IEEE files of a second rendering, e.g. V2)
"""
import pathlib, re, subprocess, sys, zipfile

ROOT = pathlib.Path(__file__).resolve().parents[2]
FOLDER = ROOT / 'myliteraturereviewpaper' / 'PPML in NextGeneration IoT'
NAME = 'Privacy Preserving Machine Learning in NextGeneration IoT'
TOKENS = re.compile(r'\{\{|⟦|\[@|TABREF|FIGREF')
ROMAN_TABLE = re.compile(r'\bTable [IVXLC]+\b')


def plain(docx):
    return subprocess.run(['pandoc', str(docx), '-t', 'plain', '--wrap=none'], capture_output=True, text=True, check=True).stdout


def paragraphs(docx):
    """(style, text) of every paragraph of the Word file"""
    xml = zipfile.ZipFile(docx).read('word/document.xml').decode('utf-8')
    out = []
    for p in re.findall(r'<w:p[ >].*?</w:p>', xml, flags=re.S):
        st = re.search(r'<w:pStyle w:val="([^"]+)"', p)
        out.append((st.group(1) if st else '', ''.join(re.findall(r'<w:t(?: [^>]*)?>([^<]*)</w:t>', p))))
    return out


def body_of(text):
    """the text before the references"""
    m = re.search(r'^(?:REFERENCES|References)\s*$', text, re.M)
    return text[:m.start()] if m else text


def table_pieces(pdf):
    """{table number: [page of each piece]} from the compiled PDF: a piece is a caption "TABLE n." (the first) or a "(continued)"
    caption that repeats the number (V93: the author found pieces of one table on the same page)"""
    info = subprocess.run(['pdfinfo', str(pdf)], capture_output=True, text=True).stdout
    n = int(re.search(r'Pages:\s+(\d+)', info).group(1))
    pieces = {}
    for page in range(1, n + 1):
        t = subprocess.run(['pdftotext', '-f', str(page), '-l', str(page), '-layout', str(pdf), '-'], capture_output=True, text=True).stdout
        for m in re.finditer(r'TABLE (\d+)\.', t):
            pieces.setdefault(int(m.group(1)), []).append(page)
    return pieces


def note_pages(pdf, version, pieces):
    """{table number: (page of its note, pages of the table)} for every table of the build that carries a note (V95: the LaTeX
    rendering set each note in the text flow after its float, so a note and its table could fall on different pages)"""
    md = (ROOT / 'myliteraturereviewpaper' / 'ppml2026' / 'build' / f'paper-V{version}.md').read_text(encoding='utf-8').split('\n')
    ROMAN = {r: i for i, r in enumerate('I II III IV V VI VII VIII IX X XI XII XIII XIV XV XVI XVII XVIII XIX XX'.split(), 1)}
    notes, num = {}, None
    for i, ln in enumerate(md):
        m = re.match(r'^Table: Table ([IVX]+)\.', ln)
        if m:
            num = ROMAN[m.group(1)]
        elif num and ln.startswith('|') and not (i + 1 < len(md) and md[i + 1].startswith('|')):
            k = i + 1
            while k < len(md) and not md[k].strip(): k += 1
            if k < len(md) and re.fullmatch(r'\*[^*].*[^*]\*', md[k].strip()):
                notes[num] = re.sub(r'\s+', ' ', md[k].strip()[1:-1])[:40]
            num = None
    info = subprocess.run(['pdfinfo', str(pdf)], capture_output=True, text=True).stdout
    n = int(re.search(r'Pages:\s+(\d+)', info).group(1))
    text = {pg: re.sub(r'\s+', ' ', subprocess.run(['pdftotext', '-f', str(pg), '-l', str(pg), str(pdf), '-'], capture_output=True, text=True).stdout)
            for pg in range(1, n + 1)}
    return {t: (next((pg for pg, tx in text.items() if head in tx), None), pieces.get(t, [])) for t, head in notes.items()}


def float_drift(pdf):
    """[(label, pages after its first mention)] for every figure and table of the compiled PDF (V96: Figs. 5 to 7 of V95 sat two
    pages after the sections that cite them, because each float was defined after the paragraph citing it)"""
    info = subprocess.run(['pdfinfo', str(pdf)], capture_output=True, text=True).stdout
    n = int(re.search(r'Pages:\s+(\d+)', info).group(1))
    pages = {pg: subprocess.run(['pdftotext', '-f', str(pg), '-l', str(pg), str(pdf), '-'], capture_output=True, text=True).stdout for pg in range(1, n + 1)}
    out = []
    for kind, cap, men in (('Fig.', r'FIGURE (\d+)\.', r'Fig\.\s*(\d+)'), ('Table', r'TABLE (\d+)\.', r'Table\s+(\d+)\b')):
        placed, first = {}, {}
        for pg, t in pages.items():
            for m in re.finditer(cap, t): placed.setdefault(int(m.group(1)), pg)
            for m in re.finditer(men, re.sub(cap, '', t)): first.setdefault(int(m.group(1)), pg)
        out += [(f'{kind} {k}', placed[k] - first.get(k, placed[k])) for k in sorted(placed)]
    return out


def caption_positions(pdf):
    """[(kind, number, page, x, y, first words)] for every "FIGURE n." and "TABLE n." caption of the PDF (pdftotext -bbox)"""
    import html as H
    xml = subprocess.run(['pdftotext', '-bbox', str(pdf), '-'], capture_output=True, text=True).stdout
    out = []
    for pg, page in enumerate(re.findall(r'<page [^>]*>(.*?)</page>', xml, flags=re.S), 1):
        words = [(float(x), float(y), H.unescape(w)) for x, y, w in re.findall(r'<word xMin="([\d.]+)" yMin="([\d.]+)"[^>]*>([^<]*)</word>', page)]
        for i, (x, y, w) in enumerate(words[:-1]):
            nxt = words[i + 1][2]
            if w in ('FIGURE', 'TABLE') and re.fullmatch(r'\d+\.', nxt):
                out.append((w, int(nxt[:-1]), pg, x, y, ' '.join(t for _, _, t in words[i + 2:i + 8])))
    return out


def caption_order(pdf, version):
    """problems: a LaTeX caption whose number does not carry the paper's caption of that number (V96: two floats moved before
    one paragraph in reverse order swapped the numbers of Tables 6 and 7, 8 and 9), or a float set before one with a lower number
    (a later number on an earlier page, or above it on the same page, unless the earlier one stands in the left column and
    the later one in the right)"""
    md = (ROOT / 'myliteraturereviewpaper' / 'ppml2026' / 'build' / f'paper-V{version}.md').read_text(encoding='utf-8')
    ROMAN = {r: i for i, r in enumerate('I II III IV V VI VII VIII IX X XI XII XIII XIV XV XVI XVII XVIII XIX XX'.split(), 1)}
    norm = lambda t: re.sub(r'[^a-z0-9]', '', t.lower())
    want = {('TABLE', ROMAN[r]): c for r, c in re.findall(r'^Table: Table ([IVX]+)\. (.*)$', md, flags=re.M)}
    want.update({('FIGURE', int(n)): c for n, c in re.findall(r'^!\[Fig\. (\d+)\. ([^\]]*)\]', md, flags=re.M)})
    caps = caption_positions(pdf)
    bad = []
    seen = {}
    for kind, n, pg, x, y, words in caps:
        if (kind, n) in seen:
            continue                                                    # a "(continued)" piece repeats the number
        seen[(kind, n)] = (pg, x, y)
        w = want.get((kind, n))
        if w is None or not norm(w).startswith(norm(words)[:12]) and not norm(words).startswith('continued'):
            bad.append(f'{kind.title()} {n} is captioned "{words[:40]}…", the paper\'s {kind.lower()} {n} is "{(w or "missing")[:40]}…"')
    half = 306                                                          # half of the A4/letter page width in points
    for kind in ('FIGURE', 'TABLE'):
        nums = sorted(n for k, n in seen if k == kind)
        for a, b in zip(nums, nums[1:]):
            pa, xa, ya = seen[(kind, a)]; pb, xb, yb = seen[(kind, b)]
            if pb < pa or (pb == pa and yb < ya - 5 and not (xa < half <= xb)):
                bad.append(f'{kind.title()} {b} is set before {kind.title()} {a} (page {pb} against page {pa})')
    return bad


def main(version, tag=''):
    fails = []
    ok = lambda cond, msg: fails.append(msg) if not cond else None
    suffix = f' IEEE Access{(" " + tag) if tag else ""}'
    ieee = FOLDER / f'{NAME} - V{version}{suffix}.docx'
    if ieee.exists():
        paras = paragraphs(ieee)
        tables = [t for s, t in paras if s == 'TableTitle']
        figs = [t for s, t in paras if s == 'FigCaption']
        nums = [re.match(r'TABLE (\d+)\.', t) for t in tables]
        ok(all(nums) and [int(m.group(1)) for m in nums] == list(range(1, len(tables) + 1)), f'IEEE Word: table captions not TABLE 1..{len(tables)} in order')
        styles = [s for s, _ in paras]
        first_h1 = next((i for i, s in enumerate(styles) if s.startswith('H1')), None)
        ok(first_h1 is not None and not any(s.startswith('H2') for s in styles[:first_h1]), 'IEEE Word: a level-2 heading before the first level-1 heading')
        text = body_of(plain(ieee))
        roman = ROMAN_TABLE.findall(text)
        ok(not roman, f'IEEE Word: Roman table numbers left: {sorted(set(roman))}')
        high_t = [n for n in map(int, re.findall(r'\bTable (\d+)\b', text)) if n > len(tables)]
        high_f = [n for n in map(int, re.findall(r'\bFig\. (\d+)\b', text)) if n > len(figs)]
        ok(not high_t, f'IEEE Word: table mentions beyond the {len(tables)} tables: {sorted(set(high_t))}')
        ok(not high_f, f'IEEE Word: figure mentions beyond the {len(figs)} figures: {sorted(set(high_f))}')
        tok = TOKENS.findall(text)
        ok(not tok, f'IEEE Word: leftover tokens: {sorted(set(tok))}')
        print(f'IEEE Word: {len(tables)} tables, {len(figs)} figures, {len(paras)} paragraphs')
    else:
        print(f'IEEE Word: not rendered ({ieee.name})')
    latex = FOLDER / f'{NAME} - V{version}{suffix} LaTeX'
    tex = latex / f'ppml-ngiot-review-V{version}.tex'
    if tex.exists():
        src = tex.read_text(encoding='utf-8')
        body = src.split(r'\begin{thebibliography}')[0]
        ok(not TOKENS.search(body), f'LaTeX: leftover tokens: {sorted(set(TOKENS.findall(body)))}')
        ok(not ROMAN_TABLE.search(body), f'LaTeX: Roman table numbers left: {sorted(set(ROMAN_TABLE.findall(body)))}')
        labels, refs = set(re.findall(r'\\label\{([^}]+)\}', src)), set(re.findall(r'\\ref\{([^}]+)\}', src))
        late = []                                                       # V96: a float is defined before the paragraph that first cites it
        FL = r'\\begin\{(figure\*|table\*|table)\}.*?\\end\{\1\}'
        prose = re.sub(FL, lambda m: ' ' * len(m.group(0)), body, flags=re.S)   # a citation inside another float does not count
        for m in re.finditer(FL, body, flags=re.S):
            lab = re.search(r'\\label\{((?:fig|tab):\d+)\}', m.group(0))
            first = re.search(r'\\ref\{' + re.escape(lab.group(1)) + r'\}', prose) if lab else None
            if first and first.start() < m.start():
                late.append(lab.group(1))
        ok(not late, f'LaTeX: floats defined after the paragraph that first cites them: {late}')
        ok(refs <= labels, f'LaTeX: \\ref without \\label: {sorted(refs - labels)}')
        pdf = latex / f'ppml-ngiot-review-V{version}.pdf'
        ok(pdf.exists(), 'LaTeX: no compiled PDF beside the source')
        if pdf.exists():
            pieces = table_pieces(pdf)
            same = {t: pg for t, pg in pieces.items() if len(pg) != len(set(pg))}
            ok(not same, 'LaTeX: pieces of one table on the same page ("(continued)" where no page break is): ' + ', '.join(f'Table {t} on pages {pg}' for t, pg in sorted(same.items())))
            astray = {t: v for t, v in note_pages(pdf, version, pieces).items() if v[0] is None or (v[1] and v[0] != v[1][-1])}
            ok(not astray, 'LaTeX: a table note not on the page of its table: ' + ', '.join(f'Table {t} note on page {v[0]}, table on {v[1]}' for t, v in sorted(astray.items())))
            order = caption_order(pdf, version)
            ok(not order, 'LaTeX: float numbers or order differ from the paper: ' + '; '.join(order))   # V96
            drift = float_drift(pdf)
            ref_page = next((pg for pg in range(1, 200) if re.search(r'^REFERENCES\s*$', subprocess.run(['pdftotext', '-f', str(pg), '-l', str(pg), str(pdf), '-'],
                             capture_output=True, text=True).stdout, re.M)), None) if pdf.exists() else None
            after = sorted(t for t, pg in pieces.items() if ref_page and max(pg) > ref_page)
            if after:                                                   # the class's ordinary placement of end tables; reported, not failed
                print(f'LaTeX: tables at the tops of reference pages (the references begin on page {ref_page}): {after}')
            far = [(k, d) for k, d in drift if d > 2 or d < -1]
            ok(not far, 'LaTeX: floats far from their first mention: ' + ', '.join(f'{k} {d:+d} pages' for k, d in far))
            print('LaTeX: pages from first mention to float: ' + ' '.join(f'{k.split()[0][0]}{k.split()[1]}:{d}' for k, d in drift)
                  + f' | two pages: {[k for k, d in drift if d == 2] or "none"}')
            split = {t: pg for t, pg in pieces.items() if len(pg) > 1}
            print('LaTeX: tables set in pieces:', ', '.join(f'Table {t} on pages {pg}' for t, pg in sorted(split.items())) or 'none')
        pages = ''
        if pdf.exists():
            info = subprocess.run(['pdfinfo', str(pdf)], capture_output=True, text=True)
            m = re.search(r'Pages:\s+(\d+)', info.stdout)
            pages = f', {m.group(1)} pages' if m else ''
        print(f'LaTeX: {len(labels)} labels, {len(refs)} refs{pages}')
    else:
        print(f'LaTeX: not rendered ({latex.name})')
    word = FOLDER / f'{NAME} - V{version}.docx'
    if word.exists():
        text = body_of(plain(word))
        arabic = re.findall(r'\bTable \d+\b', text)
        ok(not arabic, f'Word: arabic table numbers in a build that numbers tables in Roman: {sorted(set(arabic))}')
        ok(not TOKENS.search(text), f'Word: leftover tokens: {sorted(set(TOKENS.findall(text)))}')
        print(f'Word: {len(ROMAN_TABLE.findall(text))} table mentions, all Roman' if not arabic else 'Word: checked')
    else:
        print(f'Word: not rendered ({word.name})')
    for f in fails:
        print('FAIL', f)
    print(f'{len(fails)} failure(s)' if fails else 'rendered files pass')
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main(int(sys.argv[1]), sys.argv[2] if len(sys.argv) > 2 else ''))
