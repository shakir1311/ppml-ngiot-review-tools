#!/usr/bin/env python3
"""Build the V15 review: parse the text source (_src/V15/V15-part*.md), fill numbers, tables and figures from the
synthesis records in _src/V14, resolve numbered (IEEE-style) citations in order of first appearance, and write
_src/V15/document.json; then render it to .docx with render_docx.js.

Usage: scripts/.venv/bin/python scripts/review/build_v15.py <out.docx>
"""
import csv, json, pathlib, re, subprocess, sys, collections, struct

ROOT = pathlib.Path(__file__).resolve().parents[2]
SRC = ROOT / 'myliteraturereviewpaper' / '_src' / 'V14'          # synthesis data
TXT = ROOT / 'myliteraturereviewpaper' / '_src' / 'V15'          # text, figures and build output
EXT = ROOT / 'corpus' / '_extraction'
csv.field_size_limit(10 ** 9)

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import tables_v15 as T          # noqa: E402  (tables and statistics built from the synthesis records)

REFS = json.loads((SRC / 'references.json').read_text())
CITED = []                       # keys in order of first citation


def cite_key(k):
    if k not in REFS['refs']:
        raise SystemExit(f'unknown citation key {k!r}')
    if k not in CITED:
        CITED.append(k)
    return REFS['refs'][k]


def num(k):
    cite_key(k)
    return CITED.index(k) + 1


def fmt_nums(ns):
    """IEEE style: [1], [3]–[5]"""
    ns = sorted(set(ns))
    out, i = [], 0
    while i < len(ns):
        j = i
        while j + 1 < len(ns) and ns[j + 1] == ns[j] + 1:
            j += 1
        out.append(f'[{ns[i]}]' if j == i else (f'[{ns[i]}], [{ns[j]}]' if j == i + 1 else f'[{ns[i]}]–[{ns[j]}]'))
        i = j + 1
    return ', '.join(out)


WORDS = ['zero', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine']
ROMAN = ['I', 'II', 'III', 'IV', 'V', 'VI', 'VII', 'VIII', 'IX', 'X', 'XI', 'XII', 'XIII', 'XIV', 'XV', 'XVI', 'XVII',
         'XVIII', 'XIX', 'XX']


# ------------------------------------------------------------------ inline parsing
TOKEN = re.compile(r'(\[\[CHECK:.*?\]\]|\[@[^\]]+\]|(?<![\w@])@[A-Za-z][A-Za-z0-9]+|\*\*.+?\*\*|\*[^*]+?\*|'
                   r'\{\{ref:(?:fig|tab):[\w-]+\}\}|\{\{N:[\w-]+\}\})')


def inline(text, numbers, stats):
    """Turn a line of source text into a list of runs."""
    out = []
    pos = 0
    for m in TOKEN.finditer(text):
        if m.start() > pos:
            out.append({'text': text[pos:m.start()]})
        tok = m.group(0)
        if tok.startswith('[[CHECK:'):
            out.append({'text': '[' + tok[2:-2].strip() + ']', 'highlight': True})
        elif tok.startswith('[@'):
            keys = [k.strip().lstrip('@') for k in tok[2:-1].split(';')]
            out.append({'text': fmt_nums([num(k) for k in keys])})
        elif tok.startswith('@'):
            k = tok[1:]
            out.append({'text': f"{cite_key(k)['narrative_ieee']} [{num(k)}]"})
        elif tok.startswith('**'):
            out.append({'text': tok[2:-2], 'bold': True})
        elif tok.startswith('*'):
            out.append({'text': tok[1:-1], 'italic': True})
        elif tok.startswith('{{ref:'):
            kind, name = tok[6:-2].split(':')
            n = numbers.get((kind, name))
            if n is None:
                raise SystemExit(f'reference to unplaced {kind} {name}')
            out.append({'text': ('Fig. ' + str(n)) if kind == 'fig' else ('Table ' + ROMAN[n - 1])})
        elif tok.startswith('{{N:'):
            key = tok[4:-2]
            if key not in stats:
                raise SystemExit(f'unknown number {key}')
            v = stats[key]
            if isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 9 and not text[:m.start()].endswith('('):
                # one to nine are spelled out in running text; counts in parentheses stay numerals
                v = WORDS[v]
                if not text[:m.start()].strip() or re.search(r'[.!?]\s*$', text[:m.start()]):
                    v = v[0].upper() + v[1:]
            out.append({'text': str(v)})
        pos = m.end()
    if pos < len(text):
        out.append({'text': text[pos:]})
    return out


def cell_runs(text, numbers, stats):
    return inline(text, numbers, stats)


def png_size(path):
    with open(path, 'rb') as f:
        head = f.read(24)
    w, h = struct.unpack('>II', head[16:24])
    return w, h


# ------------------------------------------------------------------ block parsing
def parse(src, numbers, stats, figures, tables):
    blocks = []
    lines = src.split('\n')
    i = 0
    para = []

    def flush():
        if para:
            blocks.append({'type': 'para', 'runs': inline(' '.join(para), numbers, stats)})
            para.clear()

    while i < len(lines):
        ln = lines[i].rstrip()
        s = ln.strip()
        if s.startswith('<!--'):
            while '-->' not in lines[i]:
                i += 1
            i += 1
            continue
        if s.startswith(':::') and len(s) > 3:
            flush()
            kind = s[3:].strip()
            body = []
            i += 1
            while lines[i].strip() != ':::':
                body.append(lines[i].strip())
                i += 1
            text = ' '.join(b for b in body if b)
            t = {'title': 'title', 'author': 'author', 'draftnote': 'note', 'abstract': 'abstract',
                 'keywords': 'keywords', 'declaration': 'note'}[kind]
            blocks.append({'type': t, 'runs': inline(text, numbers, stats)})
            i += 1
            continue
        m = re.match(r'^(#{1,3}) (.*)$', s)
        if m:
            flush()
            blocks.append({'type': 'heading', 'level': len(m.group(1)), 'runs': inline(m.group(2), numbers, stats),
                           'page_break': False})
            i += 1
            continue
        m = re.match(r'^\{\{FIG:([\w-]+)\}\}$', s)
        if m:
            flush()
            f = figures[m.group(1)]
            w, h = png_size(TXT / 'figures' / f['file'])
            blocks.append({'type': 'figure', 'file': f"figures/{f['file']}", 'number': numbers[('fig', m.group(1))],
                           'label': f"Fig. {numbers[('fig', m.group(1))]}. ",
                           'caption': inline(f['caption'], numbers, stats), 'width_in': f.get('width_in', 6.2),
                           'px_w': w, 'px_h': h, 'alt': f['caption']})
            i += 1
            continue
        m = re.match(r'^\{\{TAB:([\w-]+)\}\}$', s)
        if m:
            flush()
            t = tables[m.group(1)]
            rows = []
            for r in t['rows']:
                if isinstance(r, dict) and 'group' in r:
                    rows.append({'group': inline(r['group'], numbers, stats)})
                else:
                    rows.append({'cells': [cell_runs(c, numbers, stats) if isinstance(c, str) else c for c in r]})
            cols = [dict(c, header=inline(c['header'], numbers, stats)) for c in t['columns']]
            blocks.append({'type': 'table', 'number': numbers[('tab', m.group(1))],
                           'label': f"TABLE {ROMAN[numbers[('tab', m.group(1))] - 1]}. ",
                           'caption': inline(t['caption'], numbers, stats), 'columns': cols, 'rows': rows,
                           'font_size': t.get('font_size', 8),
                           'note': inline(t['note'], numbers, stats) if t.get('note') else None})
            i += 1
            continue
        if s.startswith('- '):
            flush()
            items = []
            while i < len(lines) and lines[i].strip().startswith('- '):
                items.append(inline(lines[i].strip()[2:], numbers, stats))
                i += 1
            blocks.append({'type': 'bullets', 'items': items})
            continue
        if re.match(r'^\d+\. ', s):
            flush()
            items = []
            while i < len(lines) and re.match(r'^\d+\. ', lines[i].strip()):
                items.append(inline(re.sub(r'^\d+\. ', '', lines[i].strip()), numbers, stats))
                i += 1
            blocks.append({'type': 'numbered', 'items': items})
            continue
        if s == '{{PAGEBREAK}}':
            flush()
            blocks.append({'type': 'pagebreak'})
            i += 1
            continue
        if not s:
            flush()
            i += 1
            continue
        para.append(s)
        i += 1
    flush()
    return blocks


def number_items(src):
    numbers = {}
    nf = nt = 0
    for m in re.finditer(r'^\{\{(FIG|TAB):([\w-]+)\}\}$', src, re.M):
        if m.group(1) == 'FIG':
            nf += 1
            numbers[('fig', m.group(2))] = nf
        else:
            nt += 1
            numbers[('tab', m.group(2))] = nt
    return numbers


def main(out_docx):
    data = T.load()
    stats = T.stats(data)
    tables = T.tables(data, stats)
    figures = T.figures(data, stats)
    parts = sorted(TXT.glob('V15-part*.md'))
    src = '\n\n'.join(p.read_text(encoding='utf-8') for p in parts)
    for key, text in T.generated_text(data, stats).items():
        src = src.replace('{{' + key + '}}', text)
    numbers = number_items(src)
    blocks = parse(src, numbers, stats, figures, tables)
    # nothing unresolved may reach the document
    def texts(x):
        if isinstance(x, dict):
            for v in x.values():
                yield from texts(v)
        elif isinstance(x, list):
            for v in x:
                yield from texts(v)
        elif isinstance(x, str):
            yield x
    left = [t for t in texts(blocks) if '{{' in t or '[@' in t or re.search(r'(?<![\w.])@[A-Z]\d{3}', t)]
    if left:
        raise SystemExit(f'unresolved markup in the document: {left[:5]}')
    # every table cell that cites is parsed through inline(); the reference list holds exactly the cited works
    order = [k for k in REFS['order'] if k in CITED]
    missing = [k for k in CITED if k not in order]
    if missing:
        raise SystemExit(f'cited but not in the reference order: {missing}')
    blocks.append({'type': 'heading', 'level': 1, 'runs': [{'text': 'References'}], 'page_break': True})
    order = list(CITED)                       # numbered in order of first citation
    blocks.append({'type': 'references', 'items': [[{'text': f'[{i + 1}] '}] + [{'text': t, 'italic': it} for t, it in REFS['refs'][k]['runs_ieee']]
                                                    for i, k in enumerate(order)]})
    included = [k for k in data['included']]
    uncited = [k for k in included if k not in CITED]
    doc = {'meta': {'title': 'Privacy-Preserving Machine Learning for Next-Generation IoT Security: A Systematic Literature Review',
                    'description': 'Systematic literature review',
                    'running_head': 'Privacy-preserving machine learning for NG-IoT security: a systematic review'},
           'blocks': blocks}
    (TXT / 'document.json').write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding='utf-8')
    print(f'{len(blocks)} blocks; {len(CITED)} works cited; included studies not cited: {uncited}')
    subprocess.run(['node', str(pathlib.Path(__file__).parent / 'render_docx.js'), str(TXT / 'document.json'),
                    out_docx], check=True)


if __name__ == '__main__':
    main(sys.argv[1])
