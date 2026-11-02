#!/usr/bin/env python3
"""Writes the printable record of the FL-BC-IDS ATTACK experiments (Docs/EXPERIMENTS-FLBCIDS-ATTACKS-<date>.html): every run folder's
RESULTS.md (or RUN.md), the environment's provenance (images, VM, Powers-of-Tau, data checksums) and the repository's retained
multi-seed statistics for comparison; nothing is read from the paper. Usage: python3 experiments/fl-bc-ids-attacks/env/report.py [date]
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


css = '''body{font-family:Georgia,"Times New Roman",serif;color:#1a1a1a;background:#fff;margin:2.2em auto;max-width:66em;padding:0 1.2em;line-height:1.45}h1{font-size:1.4em}h2{font-size:1.2em;border-bottom:1px solid #bbb;padding-bottom:.15em;margin-top:1.5em}h3{font-size:1.05em;margin:1em 0 .3em}table{border-collapse:collapse;width:100%;font-size:.9em;margin:.5em 0;break-inside:avoid;page-break-inside:avoid}th,td{border:1px solid #bbb;padding:.25em .4em;vertical-align:top;text-align:left}th{background:#f3f3f3}.meta{color:#444}p{margin:.45em 0}code{font-size:.92em}
@media print{@page{size:auto;margin:16mm 14mm}body{margin:0;max-width:none;padding:0;color:#000}h2{break-after:avoid}table,tr{break-inside:avoid;page-break-inside:avoid}th{background:#eee}}'''
env_lines = []
for f, label in (('IMAGE_BUILT', 'images'), ):
    p = BASE / 'env' / f
    if p.exists(): env_lines.append(f'<li><b>{label}</b>: {h(p.read_text().strip())}</li>')
sums = BASE / 'data' / 'raw' / 'CICIoV2024' / 'SHA256SUMS.txt'
if sums.exists(): env_lines.append('<li><b>CICIoV2024 raw files (SHA-256)</b>:<br>' + '<br>'.join(h(x) for x in sums.read_text().splitlines()) + '</li>')
parts = [f'<!doctype html><html lang="en-GB"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>FL-BC-IDS attack experiments on this Mac, {h(date)}</title><style>{css}</style></head><body>',
         f'<h1>FL-BC-IDS (Alwash et al. 2026) under attack on this Mac: the runs up to {h(date)}</h1>',
         '<p class="meta">Repository github.com/wisamalwashYildiz/FL-BC-IDS (MIT): THIS experiment\'s own clone (experiments/fl-bc-ids-attacks/repo), in which code may change when a published attack protocol requires it, every change logged in CHANGES.md; the reproduction clone in experiments/fl-bc-ids stays untouched. The runs of 19 and 20 October 2026 are the v0 probe with self-chosen parameters: a test of the harness mechanics, not a result to cite. Environment experiments/fl-bc-ids-attacks/env (image flbcids-attacks-env): Colima VM flbcids (arm64, Virtualization.framework, Rosetta for amd64 binaries) and the image flbcids-env:arm64 (Python 3.12.10, dp-xgboost 0.2.10 built from source, Flower 1.23, Ray 2.31, Node 24.19 with snarkjs 0.7.5, circom 2.1.8); the amd64 image is kept as flbcids-env:amd64. Data: CICIoV2024 decimal CSVs from the CIC site; Powers-of-Tau from circom.info, SHA-256 identical to the repository\'s fingerprint. Reference numbers are the repository\'s retained multi-seed statistics; the paper itself was not read for this page.</p>',
         '<h2>Environment provenance</h2><ul>' + ''.join(env_lines) + '</ul>']
for r in sorted(p for p in (BASE / 'runs').iterdir() if p.is_dir() and p.name != 'smoke'):
    parts.append(f'<h2>{h(r.name)}</h2>')
    if (r / 'RESULTS.md').exists(): parts.append(md_min((r / 'RESULTS.md').read_text(encoding='utf-8')))
    elif (r / 'RUN.md').exists(): parts.append(md_min((r / 'RUN.md').read_text(encoding='utf-8')))
for sw in sorted((BASE / 'runs').glob('SWEEP-*.csv')):
    rows = list(csv.DictReader(open(sw)))
    parts.append(f'<h2>Scale sweep ({h(sw.stem.split("-", 1)[1])}): the released runner, the paper\'s DP settings, 2 RSUs, 4 to 200 vehicles</h2>'
                 '<p class="meta">One run folder per point (above, <code>-sweep-2x&lt;v&gt;-</code>); gathered by env/collect_sweep.py. Columns: vehicles in all; training rows per vehicle (median); mean and lowest round-2 validation accuracy over the vehicles whose lines Ray printed (Ray de-duplicates repeated log lines, so a sample of the vehicles); the global ensemble\'s TEST accuracy, precision, recall, F1 and ROC-AUC; the two RSUs\' own TEST accuracy (lowest, highest); federated seconds per RSU; wall seconds of the point; anchor-sum proofs verified.</p>'
                 + table(rows, ['vehicles', 'rows_per_vehicle', 'val_acc_mean', 'val_acc_min', 'ens_acc', 'ens_prec', 'ens_rec', 'ens_f1', 'ens_auc', 'rsu_acc_min', 'rsu_acc_max', 'fl_s_per_rsu', 'wall_s', 'proofs_verified']))
for at in sorted((BASE / 'runs').glob('ATTACKS-*.csv')):
    rows = list(csv.DictReader(open(at)))
    parts.append(f'<h2>Attack set ({h(at.stem.split("-", 1)[1])}): the released runner unchanged, a stated share of the vehicles per RSU attacking (experiment agenda point 4)</h2>'
                 '<p class="meta">One run folder per point (above, <code>-attack-</code>), each with attack_manifest.json (who attacked, how) and attack_eval.json; gathered by env/collect_attacks.py. The attackers follow the protocol otherwise. Columns: the runner\'s global-ensemble TEST accuracy, F1 and ROC-AUC; the miss rate on the test attack rows; for a backdoor run the attack success rate (the share of test attack rows the ensemble calls benign once the trigger is applied) and the trigger; the fewest and most vehicles an RSU admitted in a round; contributions excluded; proofs verified; wall seconds. Controls on the clean run\'s models: the DATA_6+DATA_7 trigger is called benign for 58% of attack rows by the clean model already; the DATA_4+DATA_5 trigger for 0%.</p>'
                 + table(rows, ['attack', 'share', 'topology', 'attackers', 'ens_acc', 'ens_f1', 'ens_auc', 'miss_rate_attack_rows', 'backdoor_asr', 'trigger', 'admitted_min', 'admitted_max', 'excluded_mentions', 'proofs_verified', 'proofs_failed', 'wall_s']))
stats = BASE / 'repo' / 'experiments' / '02_multiseed' / 'statistics' / 'summary_statistics.csv'
if stats.exists():
    rows = [x for x in csv.DictReader(open(stats)) if x['metric'] in ('accuracy', 'precision', 'recall', 'f1', 'roc_auc')]
    parts.append('<h2>The repository\'s retained multi-seed statistics (seeds 42 to 51)</h2>' + table(rows, ['dataset', 'method', 'metric', 'n', 'mean', 'sd', 'ci95_low', 'ci95_high']))
parts.append('</body></html>')
out = WS / 'Docs' / f'EXPERIMENTS-FLBCIDS-ATTACKS-{date}.html'; out.write_text('\n'.join(parts), encoding='utf-8'); print('written', out)
