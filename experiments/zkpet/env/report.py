#!/usr/bin/env python3
"""Writes the printable record of the zkPET runs (Docs/EXPERIMENTS-ZKPET-RESULTS-<date>.html): every run folder's RESULTS.md
and CSV beside the repository's src/zkml_perf.csv rows for the same models and the paper's figures as our summary records
them; nothing is read from the paper. Usage: python3 experiments/zkpet/env/report.py [date]
"""
import csv, datetime, html, pathlib, re, sys

BASE = pathlib.Path(__file__).resolve().parents[1]; WS = BASE.parents[1]
date = sys.argv[1] if len(sys.argv) > 1 else datetime.date.today().isoformat()
h = html.escape


def md_min(text):
    out, rows = [], []
    def inl(s): s = h(s); s = re.sub(r'`([^`]+)`', r'<code>\1</code>', s); return re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', s)
    def flush():
        nonlocal rows
        if rows:
            body = [r for r in rows if not re.match(r'^\|[-| ]+\|$', r)]; cells = [[c.strip() for c in r.strip('|').split('|')] for r in body]
            out.append('<table><tr>' + ''.join(f'<th>{inl(c)}</th>' for c in cells[0]) + '</tr>' + ''.join('<tr>' + ''.join(f'<td>{inl(c)}</td>' for c in r) + '</tr>' for r in cells[1:]) + '</table>'); rows = []
    for ln in text.splitlines():
        if ln.startswith('|'): rows.append(ln); continue
        flush()
        if ln.startswith('# '): out.append(f'<h3>{inl(ln[2:])}</h3>')
        elif ln.startswith('- '): out.append(f'<li>{inl(ln[2:])}</li>')
        elif ln.strip(): out.append(f'<p>{inl(ln)}</p>')
    flush(); return '\n'.join(out)


def table(rows, cols):
    return '<table><tr>' + ''.join(f'<th>{h(c)}</th>' for c in cols) + '</tr>' + ''.join('<tr>' + ''.join(f'<td>{h(r.get(c, ""))}</td>' for c in cols) + '</tr>' for r in rows) + '</table>'


runs = sorted(p for p in (BASE / 'runs').iterdir() if p.is_dir())
ref = list(csv.DictReader(open(BASE / 'repo' / 'src' / 'zkml_perf.csv')))
by_params = {}
for r in ref:
    by_params.setdefault(r['Parameters'], []).append(r)
css = '''body{font-family:Georgia,"Times New Roman",serif;color:#1a1a1a;background:#fff;margin:2.2em auto;max-width:66em;padding:0 1.2em;line-height:1.45}h1{font-size:1.4em}h2{font-size:1.2em;border-bottom:1px solid #bbb;padding-bottom:.15em;margin-top:1.5em}h3{font-size:1.05em;margin:1em 0 .3em}table{border-collapse:collapse;width:100%;font-size:.9em;margin:.5em 0;break-inside:avoid;page-break-inside:avoid}th,td{border:1px solid #bbb;padding:.25em .4em;vertical-align:top;text-align:left}th{background:#f3f3f3}.meta{color:#444}p{margin:.45em 0}code{font-size:.92em}
@media print{@page{size:auto;margin:16mm 14mm}body{margin:0;max-width:none;padding:0;color:#000}h2{break-after:avoid}table,tr{break-inside:avoid;page-break-inside:avoid}th{background:#eee}}'''
parts = [f'<!doctype html><html lang="en-GB"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>zkPET runs on this Mac, {h(date)}</title><style>{css}</style></head><body>',
         f'<h1>zkPET (Fan et al. 2025) reproduced on this Mac: the runs of {h(date)}</h1>',
         '<p class="meta">Repository github.com/CaixiangFan/zkpet (MIT), clone untouched; environment experiments/zkpet/env (Python 3.11, torch 2.1.1 CPU, ezkl 9.5.0, Flower 1.6, anvil 1.5.1, solc 0.8.20, ezkl 9.5.0 binary). Machine: Apple M5 Max, 18 cores, 48 GB, no GPU. Reference numbers are the repository\'s own src/zkml_perf.csv (their server) and, where stated, the paper\'s figures as our page-cited summary records them; the paper itself was not read for this page.</p>']
for r in runs:
    parts.append(f'<h2>{h(r.name)}</h2>')
    if (r / 'RESULTS.md').exists(): parts.append(md_min((r / 'RESULTS.md').read_text(encoding='utf-8')))
    elif (r / 'RUN.md').exists(): parts.append(md_min((r / 'RUN.md').read_text(encoding='utf-8')))
    for name in ('zkml_perf_mac.csv', 'cli_perf.csv'):
        f = r / name
        if f.exists():
            rows = list(csv.DictReader(open(f))); parts.append(f'<h3>{h(name)}</h3>' + table(rows, list(rows[0].keys())) if rows else '')
            if name == 'zkml_perf_mac.csv' and rows:
                ps = sorted({x['Parameters'] for x in rows}); refs = [x for p in ps for x in by_params.get(p, [])]
                if refs: parts.append('<h3>The repository\'s rows for the same parameter counts (src/zkml_perf.csv)</h3>' + table(refs, ['', 'Parameters', 'Input Size', 'ONNX Size', 'Proof Size', 'Prove Time', 'Prove Mem', 'Verifier Size', 'Bytecode Size']))
parts.append('<h2>What the paper reports, from our summary of it</h2><p>Per-site proofs average about 8.15 s and 1,050 MB of RAM, with proofs near 22 KB (pp. 14–15); centralised proving rises from 47 s to 310 s at 40 sites (p. 13); all measurements on one cloud server (p. 11). Our figures above are for the same models on this Mac; the step the agenda of the review promises is the same measurement on device-class hardware.</p></body></html>')
out = WS / 'Docs' / f'EXPERIMENTS-ZKPET-RESULTS-{date}.html'; out.write_text('\n'.join(parts), encoding='utf-8'); print('written', out)
