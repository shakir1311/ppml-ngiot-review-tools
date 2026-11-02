#!/usr/bin/env python3
"""Build the V18 review: the V17 builder (build_v17.py) pointed at the V18 text (_src/V18/V18-part*.md), tables and
figures (tables_v18.py, _src/V18/figures). Writes _src/V18/document.json, then renders it to .docx with render_docx.js.

Usage: scripts/.venv/bin/python scripts/review/build_v18.py <out.docx>
"""
import json, os, pathlib, re, subprocess, sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import build_v17 as B          # noqa: E402
import tables_v18 as T         # noqa: E402

TXT = B.ROOT / 'myliteraturereviewpaper' / '_src' / 'V18'
# V26: build from a staging directory of parts without overwriting the live V25 sources (set V18_PARTS)
PARTS = pathlib.Path(os.environ['V18_PARTS']) if os.environ.get('V18_PARTS') else TXT
B.TXT = TXT                    # parse() reads figure sizes from B.TXT / 'figures'
B.T = T
B.ROMAN = ['I', 'II', 'III', 'IV', 'V', 'VI', 'VII', 'VIII', 'IX', 'X', 'XI', 'XII', 'XIII', 'XIV', 'XV', 'XVI', 'XVII',
           'XVIII', 'XIX', 'XX', 'XXI', 'XXII', 'XXIII', 'XXIV', 'XXV', 'XXVI', 'XXVII', 'XXVIII', 'XXIX', 'XXX']
TITLE = ('Privacy-Preserving and Verifiable Federated Learning on Blockchains for Next-Generation IoT: Fundamentals, '
         'Threats, Regulation and Open Challenges')


def source(data, stats):
    parts = sorted(PARTS.glob('V18-part*.md'))
    src = '\n\n'.join(p.read_text(encoding='utf-8') for p in parts)
    for key, text in T.generated_text(data, stats).items():
        src = src.replace('{{' + key + '}}', text)
    return parts, src


def main(out_docx):
    data = T.load()
    stats = T.stats(data)
    tables = T.tables(data, stats)
    figures = T.figures(data, stats)
    parts, src = source(data, stats)
    numbers = B.number_items(src)
    blocks = B.parse(src, numbers, stats, figures, tables)
    blocks.insert(0, {'type': 'toc', 'title': 'Table of Contents'})

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
    missing = [k for k in B.CITED if k not in B.REFS['order']]
    if missing:
        raise SystemExit(f'cited but not in the reference order: {missing}')
    blocks.append({'type': 'heading', 'level': 1, 'runs': [{'text': 'References'}], 'page_break': True})
    blocks.append({'type': 'references', 'items': [[{'text': f'[{i + 1}] '}] + [{'text': t, 'italic': it} for t, it in B.REFS['refs'][k]['runs_ieee']]
                                                    for i, k in enumerate(B.CITED)]})
    uncited = [k for k in data['included'] if k not in B.CITED]
    doc = {'meta': {'title': TITLE, 'description': 'Survey',
                    'running_head': 'Privacy-preserving and verifiable FL on blockchains for NG-IoT'},
           'blocks': blocks}
    (TXT / 'document.json').write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding='utf-8')
    (TXT / 'citations.json').write_text(json.dumps(B.CITED), encoding='utf-8')      # [n] = CITED[n - 1]
    print(f'{len(parts)} parts; {len(blocks)} blocks; {len(B.CITED)} works cited; included studies not cited: {uncited}')
    subprocess.run(['node', str(pathlib.Path(__file__).parent / 'render_docx.js'), str(TXT / 'document.json'),
                    out_docx], check=True)


if __name__ == '__main__':
    main(sys.argv[1])
