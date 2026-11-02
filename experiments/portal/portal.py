#!/usr/bin/env python3
"""The experiments portal: one local web page (127.0.0.1:8090, this Mac only) to start, watch and read the experiments on
the included designs with published code (zkPET, FL-BC-IDS), in the manner of the Biscotti panel: environment and data
status per experiment, the runs with their progress parsed from their own logs, a live log tail, the results tables beside
the repository's or paper's reference numbers, the artefacts of each run, start forms with parameters, and a stop button.

Standard library only, no dependencies: python3 experiments/portal/portal.py  (or bash experiments/portal.sh, which also
opens the browser). Runs are started through the experiments' own scripts in <experiment>/env/ and write under
<experiment>/runs/<stamp>-<kind>/; the portal never writes into a clone or a data set.
"""
from __future__ import annotations
import csv, html, json, os, re, subprocess, sys, time, urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

PORT = int(os.environ.get('EXPERIMENTS_PORTAL_PORT', '8090'))
ROOT = Path(__file__).resolve().parents[1]                     # experiments/
WS = ROOT.parent                                                 # the workspace
EXPS = {
    'zkpet': {'title': 'zkPET (n2721, Fan et al. 2025): federated LTSF-Linear forecasting with zero-knowledge proofs of inference',
              'paper': 'zkpet/paper/n2721.pdf', 'repo_url': 'https://github.com/CaixiangFan/zkpet',
              'env_ok': lambda d: (d / 'env' / '.venv' / 'bin' / 'python').exists() and (d / 'env' / 'foundry' / 'anvil').exists(),
              'data_ok': lambda d: (d / 'repo' / 'dataset' / 'electricity.csv').exists(),
              'env_note': 'Python 3.11 venv (torch 2.1.1, ezkl 9.5.0, Flower 1.6) in env/.venv; anvil in env/foundry; data set shipped in the clone',
              'actions': [
                  {'id': 'fl', 'label': 'Run 1: federated training (server + 2 clients, 3 rounds, unchanged)', 'params': []},
                  {'id': 'zk', 'label': 'Run 2: per-site training + zero-knowledge proving (ezkl, anvil)',
                   'params': [('sites', '0 1 2', 'site ids, space separated, 0-319'), ('seq_len', '192', '96 or 192'), ('repeats', '10', 'proofs per site'), ('chain', 'yes', 'verify on anvil: yes or no')]}]},
    'fl-bc-ids': {'title': 'FL-BC-IDS (n3378, Alwash et al. 2026): hierarchical DP-XGBoost federated intrusion detection with Groth16 proofs',
                  'paper': 'fl-bc-ids/paper/n3378.pdf', 'repo_url': 'https://github.com/wisamalwashYildiz/FL-BC-IDS',
                  'env_ok': lambda d: (d / 'env' / 'IMAGE_BUILT').exists() and 'flbcids-env:arm64' in (d / 'env' / 'IMAGE_BUILT').read_text(),
                  'data_ok': lambda d: (d / 'data' / 'preprocessed' / 'CICIoV2024').exists() or (d / 'data' / 'preprocessed' / 'CSE-CIC-IDS2018').exists(),
                  'env_note': 'Linux x86_64 container (Colima + Docker): Python 3.12, dp-xgboost built from source, Node 24, snarkjs, circom 2.1.8; data sets downloaded by the author into data/raw',
                  'actions': [
                      {'id': 'checks', 'label': 'Step 1: repository integrity checks and retained Groth16 proof verification (no data needed)', 'params': []},
                      {'id': 'prep', 'label': 'Step 2: the repository\'s preprocessing of a raw data set placed under fl-bc-ids/data/raw (see data/README.md)',
                       'params': [('dataset', 'CICIoV2024', 'CICIoV2024 or CSECICIDS2018')]},
                      {'id': 'primary', 'label': 'Step 3: documented primary configuration (2 RSUs x 2 vehicles, 2 rounds, DP on)',
                       'params': [('dataset', 'CICIoV2024', 'CICIoV2024 or CSECICIDS2018')]},
                      {'id': 'expanded', 'label': 'Step 4: expanded topology of the paper (10 RSUs x 20 vehicles, 2 rounds, DP on; long)',
                       'params': [('dataset', 'CICIoV2024', 'CICIoV2024 or CSECICIDS2018')]},
                      {'id': 'topology', 'label': 'Step 5: any topology (RSUs x vehicles per RSU, 2 rounds, 10 local rounds, DP on)',
                       'params': [('dataset', 'CICIoV2024', 'CICIoV2024 or CSECICIDS2018'), ('rsus', '2', '1 to 10'), ('vehicles', '16', 'vehicles per RSU, 1 to 100')]},
                      {'id': 'sweep', 'label': 'Step 6: scale sweep (agenda point 3): 2 RSUs x each listed number of vehicles per RSU, one run folder per point, finished points skipped; the table appears above the runs',
                       'params': [('dataset', 'CICIoV2024', 'CICIoV2024 or CSECICIDS2018'), ('vehicles', '2 4 8 16 32 50 100', 'vehicles per RSU, space-separated')]}]},
    'fl-bc-ids-attacks': {'title': 'FL-BC-IDS under attack (agenda point 4): this experiment\'s own editable clone; every attack follows a published protocol, every code change is logged in CHANGES.md',
                  'paper': 'fl-bc-ids-attacks/paper/n3378.pdf', 'repo_url': 'https://github.com/wisamalwashYildiz/FL-BC-IDS',
                  'env_ok': lambda d: (d / 'env' / 'IMAGE_BUILT').exists() and 'flbcids-attacks-env:arm64' in (d / 'env' / 'IMAGE_BUILT').read_text(),
                  'data_ok': lambda d: (d / 'data' / 'preprocessed' / 'CICIoV2024').exists() or (d / 'data' / 'preprocessed' / 'CSE-CIC-IDS2018').exists(),
                  'env_note': 'its own image flbcids-attacks-env (same recipe as flbcids-env), own copy of the data and the Powers-of-Tau; the runs of 19-20 October 2026 are the v0 probe (self-chosen parameters, not to be cited)',
                  'actions': [
                      {'id': 'attack', 'label': 'One attack (agenda point 4): the runner unchanged, a stated share of vehicles per RSU attacking (env/attack.py), then env/attack_eval.py',
                       'params': [('dataset', 'CICIoV2024', 'CICIoV2024 or CSECICIDS2018'), ('attack', 'foolsgold', 'none, foolsgold (Sybil label flipping, RAID 2020) or severi (clean-label backdoor, USENIX Security 2021)'), ('value', '5', 'foolsgold: Sybils added per RSU (their 1 or 5); severi: poison size of the training set (their 0.0025 to 0.02)'), ('rsus', '2', '1 to 10'), ('vehicles', '16', 'honest vehicles per RSU, 1 to 100')]},
                      {'id': 'attacks', 'label': 'The attack set (agenda point 4): every attack of env/attacks.sh at its share on one topology, one run folder per point, finished points skipped; the table appears above the runs',
                       'params': [('dataset', 'CICIoV2024', 'CICIoV2024 or CSECICIDS2018'), ('points', 'none:0 foolsgold:1 foolsgold:5 severi:0.01 severi:0.04', 'attack:value, space-separated'), ('rsus', '2', '1 to 10'), ('vehicles', '16', 'honest vehicles per RSU, 1 to 100'), ('repeat', '', 'a tag such as r2 for a second run of every point')]}]},
}
CSS = '''body{font-family:-apple-system,Helvetica,Arial,sans-serif;margin:0;background:#f6f6f4;color:#1b1b1b}header{background:#20343f;color:#fff;padding:.7em 1.2em;font-size:1.05em}header a{color:#cfe3ee;text-decoration:none;margin-right:1.2em}
main{max-width:76em;margin:0 auto;padding:1em 1.2em}h2{font-size:1.15em;margin:1.2em 0 .4em;border-bottom:1px solid #ccc}h3{font-size:1em;margin:.9em 0 .3em}table{border-collapse:collapse;width:100%;font-size:.92em;background:#fff}th,td{border:1px solid #ddd;padding:.3em .5em;text-align:left;vertical-align:top}th{background:#eef1f3}
.ok{color:#1a7f37;font-weight:600}.bad{color:#b3261e;font-weight:600}.run{color:#9a6700;font-weight:600}.card{background:#fff;border:1px solid #ddd;border-radius:6px;padding:.8em 1em;margin:.6em 0}pre{background:#111;color:#e6e6e6;padding:.7em;border-radius:6px;font-size:.8em;max-height:28em;overflow:auto;white-space:pre-wrap}
button,input[type=submit]{background:#20343f;color:#fff;border:0;border-radius:4px;padding:.35em .9em;cursor:pointer}button.stop{background:#b3261e}input[type=text]{width:9em;padding:.25em}label{margin-right:.8em;font-size:.9em}.small{font-size:.85em;color:#555}.bar{height:10px;background:#e3e3e3;border-radius:5px;overflow:hidden}.bar>div{height:100%;background:#2b7a4b}code{background:#eee;padding:0 .2em;border-radius:3px}'''


def h(x): return html.escape(str(x))


def tail(p: Path, n=80, size=65536):
    try:
        with open(p, 'rb') as f:
            f.seek(0, 2); sz = f.tell(); f.seek(max(0, sz - size)); data = f.read().decode('utf-8', 'replace')
        return '\n'.join(data.splitlines()[-n:])
    except OSError:
        return ''


def md_min(text: str) -> str:
    """a minimal markdown rendering for RUN.md / RESULTS.md: headings, tables, bullets, code spans, paragraphs"""
    out, rows = [], []
    def flush():
        nonlocal rows
        if rows:
            body = [r for r in rows if not re.match(r'^\|[-| ]+\|$', r)]
            cells = [[c.strip() for c in r.strip('|').split('|')] for r in body]
            out.append('<table><tr>' + ''.join(f'<th>{inl(c)}</th>' for c in cells[0]) + '</tr>' + ''.join('<tr>' + ''.join(f'<td>{inl(c)}</td>' for c in r) + '</tr>' for r in cells[1:]) + '</table>'); rows = []
    def inl(s):
        s = h(s); s = re.sub(r'`([^`]+)`', r'<code>\1</code>', s); s = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', s); return s
    for ln in text.splitlines():
        if ln.startswith('|'): rows.append(ln); continue
        flush()
        if ln.startswith('# '): out.append(f'<h2>{inl(ln[2:])}</h2>')
        elif ln.startswith('## '): out.append(f'<h3>{inl(ln[3:])}</h3>')
        elif ln.startswith('### '): out.append(f'<h3>{inl(ln[4:])}</h3>')
        elif ln.startswith('- '): out.append(f'<div>&bull; {inl(ln[2:])}</div>')
        elif ln.strip(): out.append(f'<p>{inl(ln)}</p>')
    flush(); return '\n'.join(out)


def runs_of(exp: str):
    d = ROOT / exp / 'runs'
    return sorted([p for p in d.iterdir() if p.is_dir()], key=lambda p: p.name, reverse=True) if d.exists() else []


def alive(run: Path) -> bool:
    r = subprocess.run(['pgrep', '-f', str(run)], capture_output=True, text=True)
    return any(pid.strip() and int(pid) != os.getpid() for pid in r.stdout.split())


def status_of(run: Path):
    kind = run.name.split('-', 2)[-1]
    log = run / 'run.log' if (run / 'run.log').exists() else run / 'server.log'
    txt = tail(log, 400) if log.exists() else ''
    if alive(run): return 'running', kind, txt
    if 'ALL DONE' in txt or 'FL finished' in txt or 'FL RUN FINISHED' in txt or 'finished:' in (run / 'RUN.md').read_text(errors='replace') if (run / 'RUN.md').exists() else False: return 'finished', kind, txt
    if 'Traceback' in txt or 'failed' in txt or 'SystemExit' in txt: return 'failed', kind, txt
    return 'finished' if txt else 'empty', kind, txt


def progress_of(run: Path, kind: str, txt: str):
    """a one-line progress and a percentage, parsed from the run's own log lines"""
    if kind.startswith('zk-sites') or kind.startswith('zk-multi'):
        m = re.search(r'(?:sites|channels) \[([^\]]*)\].*repeats (\d+)', txt); sites = [s for s in (m.group(1).split(', ') if m else []) if s]; rep = int(m.group(2)) if m else 10
        done = len(re.findall(r'(?:site |k=)\d+: DONE', txt)); cur = re.findall(r'(?:site |k=)(\d+): (training|trained|onnx|settings|compiled|srs|setup|proof (\d+)/\d+|verified|verifier|on chain)', txt)
        steps = ['training', 'trained', 'onnx', 'settings', 'compiled', 'srs', 'setup', 'proof', 'verified', 'verifier', 'on chain']
        last = cur[-1] if cur else None
        frac = 0.0
        if sites:
            per = 1 / len(sites); frac = done * per
            if last and done < len(sites):
                step = last[1].split()[0]; i = steps.index(step) if step in steps else 0
                frac += per * (i / len(steps) + (int(last[2]) / rep / len(steps) if last[2] else 0))
        line = f'{done}/{len(sites)} {"models" if kind.startswith("zk-multi") else "sites"} done' + (f'; site {last[0]}: {last[1]}' if last and done < len(sites) else '')
        return line, min(100, round(frac * 100))
    if kind.startswith('zk-cli'):
        n = len(re.findall(r'proof \d+/\d+:', txt)); fin = 'ALL DONE' in txt
        return f'{n} proofs timed' + (' — finished' if fin else ''), 100 if fin else min(99, n * 6)
    if kind == 'fl-2clients':
        rounds = re.findall(r'fit_round (\d+) received', txt); fin = 'FL finished' in txt
        return (f'round {rounds[-1]} of 3 aggregated' if rounds else 'starting') + (' — finished' if fin else ''), 100 if fin else min(99, len(rounds) * 33)
    if kind.startswith(('primary', 'expanded', 'topology', 'sweep-', 'attack-')):  # FL-BC-IDS runs: the container's runner.log
        rl = run / 'runner.log'; t = rl.read_text(errors='replace') if rl.exists() and rl.stat().st_size < 64_000_000 else (tail(rl, 4000, 4_000_000) if rl.exists() else '')
        proofs = t.count('AnchorSum verification SUCCEEDED | round=')  # each proof is logged twice; this form once per proof (as env/collect_sweep.py counts)
        rounds = len(re.findall(r'global booster trees=', t))
        ens = re.search(r'GLOBAL ENSEMBLE\] TEST \(thr=([0-9.]+)\) - Acc: ([0-9.]+), Prec: [0-9.]+, Rec: [0-9.]+, F1: ([0-9.]+), AUC: ([0-9.]+)', t)
        fin = 'runner exit code' in txt
        if ens: return f'ensemble TEST acc {ens.group(2)}, F1 {ens.group(3)}, AUC {ens.group(4)} (thr {ens.group(1)}); {proofs} proofs verified' + (' — finished' if fin else ''), 100 if fin else 99
        return (f'{rounds} RSU rounds aggregated; {proofs} proofs verified' if (rounds or proofs) else 'starting') + (' — finished' if fin else ''), 100 if fin else min(95, 10 + rounds * 20)
    return ('see log', 0)


def results_table(run: Path):
    f = run / 'zkml_perf_mac.csv'
    if not f.exists():
        c = run / 'cli_perf.csv'
        if not c.exists(): return ''
        rows = list(csv.DictReader(open(c)))
        return '<h3>Command-line timings (ezkl 9.5.0 binary under /usr/bin/time -l)</h3><table><tr>' + ''.join(f'<th>{h(k)}</th>' for k in rows[0].keys()) + '</tr>' + ''.join('<tr>' + ''.join(f'<td>{h(v)}</td>' for v in r.values()) + '</tr>' for r in rows) + '</table>' if rows else ''
    ours = list(csv.DictReader(open(f))); ref = ROOT / 'zkpet' / 'repo' / 'src' / 'zkml_perf.csv'
    refs = list(csv.DictReader(open(ref))) if ref.exists() else []
    cols = ['Parameters', 'Input Size', 'ONNX Size', 'Proof Size', 'Prove Time', 'Prove Mem', 'Verifier Size']
    s = '<h3>Results: ours (this Mac) beside the repository\'s zkml_perf.csv (their server)</h3><table><tr><th>Source</th><th>seq_len / site</th>' + ''.join(f'<th>{c}</th>' for c in cols) + '<th>logrows</th><th>setup s</th><th>verify s</th><th>on chain</th></tr>'
    for r in ours:
        s += f'<tr><td>this Mac</td><td>{h(r["seq_len"])} / {"site " + h(r["site"]) if "site" in r else h(r.get("channels", "")) + " sites in one model"}</td>' + ''.join(f'<td>{h(r.get(c, ""))}</td>' for c in cols) + f'<td>{h(r.get("logrows", ""))}</td><td>{h(r.get("setup_s", ""))}</td><td>{h(r.get("verify_s", ""))}</td><td>{h(r.get("on_chain", ""))}</td></tr>'
    for r in refs:
        s += f'<tr><td class="small">repository</td><td>{h(r.get("", ""))}</td>' + ''.join(f'<td class="small">{h(r.get(c, ""))}</td>' for c in cols) + '<td></td><td></td><td></td><td></td></tr>'
    return s + '</table><p class="small">Prove Time in seconds (mean of the repeats); Prove Mem: ours is the process peak RSS in MB, the repository\'s column is what its notebook recorded with tracemalloc, so the two are not the same measure.</p>'


def page(title, body, refresh=None):
    meta = f'<meta http-equiv="refresh" content="{refresh}">' if refresh else ''
    return f'<!doctype html><html lang="en-GB"><head><meta charset="utf-8">{meta}<title>{h(title)}</title><style>{CSS}</style></head><body><header><a href="/">Experiments portal</a> <a href="/exp/zkpet">zkPET</a> <a href="/exp/fl-bc-ids">FL-BC-IDS</a> <a href="/file/CREDENTIALS.md">credentials</a> <a href="/file/README.md">readme</a> <span class="small">127.0.0.1:{PORT}, this Mac only</span></header><main>{body}</main></body></html>'


def home():
    b = '<h2>The two included designs with MIT-licensed code</h2>'
    for k, e in EXPS.items():
        d = ROOT / k; env = e['env_ok'](d); data = e['data_ok'](d); rs = runs_of(k); running = [r for r in rs if alive(r)]
        b += f'<div class="card"><b><a href="/exp/{k}">{h(e["title"])}</a></b><br><span class="small">{h(e["env_note"])}</span><br>environment: <span class="{"ok" if env else "bad"}">{"ready" if env else "not built"}</span> · data: <span class="{"ok" if data else "bad"}">{"present" if data else "absent"}</span> · runs: {len(rs)}' + (f' · <span class="run">{len(running)} running</span>' if running else '') + f' · <a href="/file/{h(e["paper"])}">paper PDF</a> · <a href="{h(e["repo_url"])}">repository</a></div>'
    b += '<p class="small">Analysis of what each takes: <a href="/file/../Docs/EXPERIMENTS-SETUP-ZKPET-FLBCIDS-2026-10-19.html">Docs/EXPERIMENTS-SETUP-ZKPET-FLBCIDS-2026-10-19.html</a>. Every username, key and endpoint is in <a href="/file/CREDENTIALS.md">CREDENTIALS.md</a>.</p>'
    return page('Experiments portal', b, refresh=15)


def exp_page(k):
    e = EXPS[k]; d = ROOT / k; env = e['env_ok'](d)
    b = f'<h2>{h(e["title"])}</h2><div class="card">environment: <span class="{"ok" if env else "bad"}">{"ready" if env else "not built"}</span> — {h(e["env_note"])}<br>data: <span class="{"ok" if e["data_ok"](d) else "bad"}">{"present" if e["data_ok"](d) else "absent"}</span> · <a href="/file/{h(e["paper"])}">paper PDF</a> · <a href="{h(e["repo_url"])}">repository</a> · clone: <code>{h(str(d / "repo"))}</code></div>'
    b += '<h2>Start a run</h2>'
    for a in e['actions']:
        b += f'<form class="card" method="post" action="/start/{k}/{a["id"]}"><b>{h(a["label"])}</b><br>'
        for name, default, hint in a['params']:
            b += f'<label>{h(name)} <input type="text" name="{h(name)}" value="{h(default)}"> <span class="small">{h(hint)}</span></label>'
        b += f'<input type="submit" value="Start"{"" if env else " disabled"}>' + ('' if env else ' <span class="small bad">environment not built yet</span>') + '</form>'
    for sw in sorted((d / 'runs').glob('SWEEP-*.csv')) if (d / 'runs').exists() else []:
        rows = list(csv.DictReader(open(sw))); cols = ['vehicles', 'rows_per_vehicle', 'ens_acc', 'ens_f1', 'ens_auc', 'rsu_acc_min', 'rsu_acc_max', 'wall_s', 'proofs_verified', 'run']
        b += f'<h2>Scale sweep ({h(sw.stem[6:])}): 2 RSUs, 4 to 200 vehicles, the paper\'s DP settings, one seed</h2><table><tr>' + ''.join(f'<th>{h(c)}</th>' for c in cols) + '</tr>'
        b += ''.join('<tr>' + ''.join(f'<td>{h(r.get(c, ""))}</td>' for c in cols) + '</tr>' for r in rows) + '</table>'
        b += f'<p class="small">Gathered by env/collect_sweep.py from the sweep run folders below; the reading and the follow-ups are in <a href="/file/MY-EXPERIMENT-AGENDA.md">MY-EXPERIMENT-AGENDA.md</a> (point 3).</p>'
    for at in (sorted((d / 'runs').glob('ATTACKS-*.csv')) if k == 'fl-bc-ids-attacks' and (d / 'runs').exists() else []):
        rows = list(csv.DictReader(open(at))); cols = ['attack', 'param', 'run_tag', 'topology', 'attackers', 'ens_acc', 'ens_f1', 'fg_target_attack_rate', 'severi_success_vs_clean_fl', 'aq_attackers_below_honest_recall', 'aq_honest_recall_min', 'aq_attacker_recall_max', 'fg_check_attackers_zeroed', 'fg_check_honest_zeroed', 'admitted_min', 'admitted_max', 'excluded', 'proofs_verified', 'wall_s', 'run']
        b += f'<h2>Attack set ({h(at.stem[8:])}), harness v1: FoolsGold Sybil label flipping and the Severi clean-label backdoor against the runner unchanged</h2><table><tr>' + ''.join(f'<th>{h(c)}</th>' for c in cols) + '</tr>'
        b += ''.join('<tr>' + ''.join(f'<td>{h(r.get(c, ""))}</td>' for c in cols) + '</tr>' for r in rows) + '</table>'
        b += '<p class="small">Gathered by env/collect_attacks.py from the attack run folders below (each holds attack_manifest.json and attack_eval.json); the reading is in <a href="/file/MY-EXPERIMENT-AGENDA.md">MY-EXPERIMENT-AGENDA.md</a> (point 4). fg_target_attack_rate: share of test attack rows called benign (FoolsGold\'s metric); severi_success: among attack rows the clean reference detects, the share the attacked ensemble passes once the trigger is applied; aq: the anchor-quality check, attackers whose recall on the labelled attack anchors falls below every honest vehicle\'s (the anchors are validation rows, so a validator holding their labels can score each committed vector); fg_check: vehicles FoolsGold\'s similarity test on the anchor vectors would have given zero weight.</p>'
    b += '<h2>Runs</h2><table><tr><th>Run</th><th>Kind</th><th>Status</th><th>Progress</th><th>Started</th></tr>'
    for r in runs_of(k):
        st, kind, txt = status_of(r); line, pct = progress_of(r, kind, txt)
        b += f'<tr><td><a href="/run/{k}/{h(r.name)}">{h(r.name)}</a></td><td>{h(kind)}</td><td class="{ {"running": "run", "finished": "ok", "failed": "bad"}.get(st, "") }">{st}</td><td>{h(line)}<div class="bar"><div style="width:{pct}%"></div></div></td><td>{time.strftime("%Y-%m-%d %H:%M", time.localtime(r.stat().st_mtime))}</td></tr>'
    return page(f'{k} — experiments portal', b + '</table>', refresh=15)


def run_page(k, name):
    r = ROOT / k / 'runs' / name
    if not r.is_dir(): return page('not found', '<p>no such run</p>')
    st, kind, txt = status_of(r); line, pct = progress_of(r, kind, txt)
    b = f'<h2>{h(k)} / {h(name)}</h2><div class="card">status: <span class="{ {"running": "run", "finished": "ok", "failed": "bad"}.get(st, "") }">{st}</span> · {h(line)}<div class="bar"><div style="width:{pct}%"></div></div>'
    if st == 'running': b += f'<form method="post" action="/stop/{k}/{h(name)}" style="margin-top:.5em"><button class="stop">Stop this run</button></form>'
    b += '</div>'
    for f in ('RESULTS.md', 'RUN.md'):
        if (r / f).exists(): b += f'<div class="card"><b>{f}</b>{md_min((r / f).read_text(errors="replace"))}</div>'
    b += results_table(r)
    logs = [p for p in sorted(r.glob('*.log'))] + [p for p in sorted((r / 'logs').glob('*.log'))] if (r / 'logs').exists() else [p for p in sorted(r.glob('*.log'))]
    for p in logs[:6]:
        b += f'<h3>{h(p.relative_to(r))} (last lines)</h3><pre>{h(tail(p, 60))}</pre>'
    arts = [p for p in r.rglob('*') if p.is_file() and p.suffix not in ('.log',)][:200]
    b += '<h3>Artefacts</h3><table><tr><th>File</th><th>Size</th></tr>' + ''.join(f'<tr><td>{h(p.relative_to(r))}</td><td>{p.stat().st_size:,}</td></tr>' for p in sorted(arts)) + '</table>'
    return page(f'{name} — experiments portal', b, refresh=10 if st == 'running' else None)


def start(k, action, form):
    d = ROOT / k; stamp = time.strftime('%Y%m%d-%H%M%S'); env = {**os.environ, 'PYTHONUNBUFFERED': '1'}
    if k == 'zkpet' and action == 'fl':
        subprocess.Popen(['bash', str(d / 'env' / 'run_fl.sh')], cwd=d, stdout=open(d / 'runs' / f'portal-{stamp}-fl.out', 'w'), stderr=subprocess.STDOUT, env=env, start_new_session=True); return f'/exp/{k}'
    if k == 'zkpet' and action == 'zk':
        sites = [s for s in re.split(r'[ ,]+', form.get('sites', '0').strip()) if s.isdigit() and 0 <= int(s) <= 319] or ['0']
        seq = form.get('seq_len', '192').strip(); seq = seq if seq in ('96', '192', '336', '720') else '192'
        rep = form.get('repeats', '10').strip(); rep = rep if rep.isdigit() and 1 <= int(rep) <= 50 else '10'
        run = d / 'runs' / f'{stamp}-zk-sites'; run.mkdir(parents=True)
        chain = form.get('chain', 'yes').strip().lower() != 'no'
        if chain: subprocess.run(['bash', str(d / 'env' / 'start_anvil.sh'), str(run)], cwd=d)
        cmd = [str(d / 'env' / '.venv' / 'bin' / 'python'), '-u', str(d / 'env' / 'zk_sites.py'), '--run', str(run), '--sites', *sites, '--seq_len', seq, '--repeats', rep] + ([] if chain else ['--no-chain'])
        subprocess.Popen(cmd, cwd=d, stdout=open(run / 'run.log', 'w'), stderr=subprocess.STDOUT, env=env, start_new_session=True); return f'/run/{k}/{run.name}'
    if k == 'fl-bc-ids' and action == 'sweep':
        ds = form.get('dataset', 'CICIoV2024').strip() or 'CICIoV2024'
        lst = ' '.join(v for v in re.split(r'[ ,]+', form.get('vehicles', '').strip()) if v.isdigit() and 1 <= int(v) <= 100) or '2 4 8 16 32 50 100'
        (d / 'runs').mkdir(exist_ok=True)
        subprocess.Popen(['bash', str(d / 'env' / 'sweep.sh'), ds, lst], cwd=d, stdout=open(d / 'runs' / f'portal-{stamp}-sweep.out', 'w'), stderr=subprocess.STDOUT, env=env, start_new_session=True); return f'/exp/{k}'
    if k == 'fl-bc-ids-attacks' and action in ('attack', 'attacks'):
        ds = form.get('dataset', 'CICIoV2024').strip() or 'CICIoV2024'
        r_ = form.get('rsus', '2').strip(); r_ = r_ if r_.isdigit() and 1 <= int(r_) <= 10 else '2'
        v_ = form.get('vehicles', '16').strip(); v_ = v_ if v_.isdigit() and 1 <= int(v_) <= 100 else '16'
        env2 = {**env, 'FLBCIDS_NUM_RSUS': r_, 'FLBCIDS_VEHICLES_PER_RSU': v_, 'FLBCIDS_NUM_ROUNDS': '2', 'FLBCIDS_NUM_LOCAL_ROUNDS': '10'}
        if action == 'attacks':
            pts = ' '.join(x for x in re.split(r'[ ,]+', form.get('points', '').strip()) if re.fullmatch(r'(none|foolsgold|severi):[0-9.]+', x))
            rep = re.sub(r'[^A-Za-z0-9]', '', form.get('repeat', ''))[:12]
            (d / 'runs').mkdir(exist_ok=True)
            subprocess.Popen(['bash', str(d / 'env' / 'attacks.sh'), ds, pts or 'none:0 foolsgold:1 foolsgold:5 severi:0.01 severi:0.04'] + ([rep] if rep else []), cwd=d, stdout=open(d / 'runs' / f'portal-{stamp}-attacks.out', 'w'), stderr=subprocess.STDOUT, env=env2, start_new_session=True); return f'/exp/{k}'
        a_ = form.get('attack', 'foolsgold').strip().lower(); a_ = a_ if a_ in ('none', 'foolsgold', 'severi') else 'foolsgold'
        s_ = form.get('value', '5').strip()
        if a_ == 'foolsgold':
            s_ = s_ if s_.isdigit() and 1 <= int(s_) <= 50 else '5'; env2.update({'FLBCIDS_FG_SYBILS': s_, 'FLBCIDS_VEHICLES_PER_RSU': str(int(v_) + int(s_))})
        elif a_ == 'severi':
            try: s_ = str(min(0.5, max(0.0001, float(s_))))
            except ValueError: s_ = '0.01'
            env2.update({'FLBCIDS_SV_POISON': s_})
        else: s_ = '0'
        run = d / 'runs' / f'{stamp}-attack-{a_}{s_}-{r_}x{v_}-{ds.lower()}'; run.mkdir(parents=True)
        env2.update({'FLBCIDS_ATTACK': a_})
        subprocess.Popen(['bash', str(d / 'env' / 'run.sh'), 'attack', str(run), ds], cwd=d, stdout=open(run / 'run.log', 'w'), stderr=subprocess.STDOUT, env=env2, start_new_session=True); return f'/run/{k}/{run.name}'
    if k == 'fl-bc-ids' and action == 'topology':
        ds = form.get('dataset', 'CICIoV2024').strip() or 'CICIoV2024'
        r_ = form.get('rsus', '2').strip(); r_ = r_ if r_.isdigit() and 1 <= int(r_) <= 10 else '2'
        v_ = form.get('vehicles', '16').strip(); v_ = v_ if v_.isdigit() and 1 <= int(v_) <= 100 else '16'
        run = d / 'runs' / f'{stamp}-topology-{r_}x{v_}-{ds.lower()}'; run.mkdir(parents=True)
        env2 = {**env, 'FLBCIDS_NUM_RSUS': r_, 'FLBCIDS_VEHICLES_PER_RSU': v_, 'FLBCIDS_NUM_ROUNDS': '2', 'FLBCIDS_NUM_LOCAL_ROUNDS': '10'}
        subprocess.Popen(['bash', str(d / 'env' / 'run.sh'), 'topology', str(run), ds], cwd=d, stdout=open(run / 'run.log', 'w'), stderr=subprocess.STDOUT, env=env2, start_new_session=True); return f'/run/{k}/{run.name}'
    if k == 'fl-bc-ids':
        script = d / 'env' / 'run.sh'
        if script.exists():
            run = d / 'runs' / f'{stamp}-{action}'; run.mkdir(parents=True)
            subprocess.Popen(['bash', str(script), action, str(run), form.get('dataset', 'CICIoV2024')], cwd=d, stdout=open(run / 'run.log', 'w'), stderr=subprocess.STDOUT, env=env, start_new_session=True); return f'/run/{k}/{run.name}'
    return f'/exp/{k}'


def stop(k, name):
    r = ROOT / k / 'runs' / name
    subprocess.run(['pkill', '-f', str(r)]); return f'/run/{k}/{name}'


class H(BaseHTTPRequestHandler):
    def _send(self, body, code=200, ctype='text/html; charset=utf-8'):
        data = body if isinstance(body, bytes) else body.encode(); self.send_response(code); self.send_header('Content-Type', ctype); self.send_header('Content-Length', str(len(data))); self.end_headers(); self.wfile.write(data)

    def _redirect(self, to):
        self.send_response(303); self.send_header('Location', to); self.end_headers()

    def do_GET(self):
        p = urllib.parse.urlparse(self.path).path
        try:
            if p == '/': return self._send(home())
            if p.startswith('/exp/') and p[5:] in EXPS: return self._send(exp_page(p[5:]))
            if p.startswith('/run/'):
                k, _, name = p[5:].partition('/')
                if k in EXPS and re.fullmatch(r'[\w.-]+', name): return self._send(run_page(k, name))
            if p.startswith('/file/'):
                f = (ROOT / urllib.parse.unquote(p[6:])).resolve()
                if (str(f).startswith(str(ROOT)) or str(f).startswith(str(WS / 'Docs'))) and f.is_file():
                    ctype = {'.pdf': 'application/pdf', '.html': 'text/html; charset=utf-8', '.md': 'text/plain; charset=utf-8', '.csv': 'text/plain; charset=utf-8', '.json': 'application/json'}.get(f.suffix, 'text/plain; charset=utf-8')
                    return self._send(f.read_bytes(), ctype=ctype)
            self._send('<p>not found</p>', 404)
        except Exception as ex:                                                             # noqa: BLE001
            self._send(page('error', f'<pre>{h(repr(ex))}</pre>'), 500)

    def do_POST(self):
        p = urllib.parse.urlparse(self.path).path; n = int(self.headers.get('Content-Length', 0)); form = dict(urllib.parse.parse_qsl(self.rfile.read(n).decode()))
        if p.startswith('/start/'):
            k, _, action = p[7:].partition('/')
            if k in EXPS: return self._redirect(start(k, action, form))
        if p.startswith('/stop/'):
            k, _, name = p[6:].partition('/')
            if k in EXPS and re.fullmatch(r'[\w.-]+', name): return self._redirect(stop(k, name))
        self._send('<p>bad request</p>', 400)

    def log_message(self, fmt, *args):
        sys.stderr.write('%s %s\n' % (time.strftime('%H:%M:%S'), fmt % args))


if __name__ == '__main__':
    print(f'experiments portal on http://127.0.0.1:{PORT}/', flush=True)
    ThreadingHTTPServer(('127.0.0.1', PORT), H).serve_forever()
