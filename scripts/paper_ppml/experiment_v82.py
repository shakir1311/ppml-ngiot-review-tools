#!/usr/bin/env python3
"""Table, figures and captions of the preliminary experiment in Section VII-B (paper V82 onwards), computed from the run records
under experiments/ and never typed by hand: build/tables/experiment_attacks.md (the attack set, two runs per point, from
experiments/fl-bc-ids-attacks/runs/ATTACKS-CICIOV2024.csv), build/tables/experiment_setup.md (the conditions, for the supporting document), build/figures/sweep.png (the scale sweep, from
experiments/fl-bc-ids/runs/SWEEP-CICIOV2024.csv) and build/figures/anchorcheck.png (the probe check on the committed anchor
vectors, from the attack runs' attack_eval.json), drawn with the SVG primitives of scripts/review/figures_static.py in the
paper's figure style; the two captions are merged into <parts>/figcaps.json. Run after data_v68.py and before build.py:
PPML_PARTS_NAME=parts-v82 python3 scripts/paper_ppml/experiment_v82.py
"""
import csv, glob, json, os, pathlib, sys
ROOT = pathlib.Path(__file__).resolve().parents[2]
B = ROOT / 'myliteraturereviewpaper' / 'ppml2026' / 'build'
sys.path.insert(0, str(ROOT / 'scripts' / 'review')); sys.path.insert(0, str(pathlib.Path(__file__).parent))
import figures_static as F                       # noqa: E402
import data as D                                 # noqa: E402  (md_table)
F.OUT = B / 'figures'; F.OUT.mkdir(parents=True, exist_ok=True)
NAVY, RED, GREEN, INK2, GREY = '#22445D', '#B85450', '#2FA37A', '#52514e', '#BDBDBD'
ATT = ROOT / 'experiments' / 'fl-bc-ids-attacks' / 'runs'; SWEEP = ROOT / 'experiments' / 'fl-bc-ids' / 'runs' / 'SWEEP-CICIOV2024.csv'


def pct(x): return f'{100 * float(x):.0f}%' if x not in ('', None) else '–'


def attack_table():
    rows = list(csv.DictReader(open(ATT / 'ATTACKS-CICIOV2024.csv')))
    by = {}
    for r in rows: by.setdefault((r['attack'], r['param']), {})[r['run_tag']] = r
    label = {('none', ''): ('None (clean pipeline)', '0'), ('foolsgold', '1'): ('Sybil label flipping, FoolsGold protocol', '1 Sybil added'),
             ('foolsgold', '5'): ('Sybil label flipping, FoolsGold protocol', '5 Sybils added'), ('severi', '0.01'): ('Clean-label backdoor, Severi protocol, 1% of training rows', '4 of 16'),
             ('severi', '0.04'): ('Clean-label backdoor, Severi protocol, 4% of training rows', '4 of 16')}
    out = []
    for key in [('none', ''), ('foolsgold', '1'), ('foolsgold', '5'), ('severi', '0.01'), ('severi', '0.04')]:
        k = key if key in by else next((kk for kk in by if kk[0] == key[0] and (kk[1] or '') == key[1]), None)
        if k is None: continue
        r1, r2 = by[k].get('r1', {}), by[k].get('r2', {})
        adm = 'all, 5 of 5' if all(x.get('excluded', '0') == '0' and x.get('proofs_verified') == '5' for x in (r1, r2) if x) else 'see records'
        passed = f"{pct(r1.get('fg_target_attack_rate'))} / {pct(r2.get('fg_target_attack_rate'))}"
        bd = f"{pct(r1.get('severi_success_vs_clean_fl'))} / {pct(r2.get('severi_success_vs_clean_fl'))}" if k[0] == 'severi' else '–'
        probe = f"{r1.get('aq_attackers_below_honest_recall') or '–'} / {r2.get('aq_attackers_below_honest_recall') or '–'}" if k[0] != 'none' else '–'
        out.append([label[key][0], label[key][1], adm, passed, bd, probe])
    D.md_table('experiment_attacks', 'FL-BC-IDS as released under two published attack protocols on CICIoV2024',
               ['Attack', 'Attackers per RSU', 'Admitted, proofs', 'Attack flows passed', 'Backdoor success', 'Probe check'], out, note='Two RSUs with 16 honest vehicles each; two runs per setting (run 1 / run 2). Admitted: attackers admitted and anchor-sum proofs verified. Attack flows passed: share of the test attack rows called benign (clean pipeline: 8% in both runs). Backdoor success: among the attack rows the clean federated model still detects with the trigger, the share the attacked model passes. Probe check: attackers whose recall on the labelled attack probes falls below every honest vehicle\'s.')
    return out


def sweep_figure():
    rows = list(csv.DictReader(open(SWEEP))); rows.sort(key=lambda r: int(r['vehicles']))
    W, H = 1180, 520; left, right, top, bottom = 110, 60, 50, 110
    pw, ph = W - left - right, H - top - bottom; n = len(rows)
    xs = [left + pw * (i + 0.5) / n for i in range(n)]
    def Y(v): return top + ph * (1 - float(v))
    b = []
    for t in (0, 0.2, 0.4, 0.6, 0.8, 1.0):
        b.append(f'<line x1="{left}" y1="{Y(t):.1f}" x2="{left + pw}" y2="{Y(t):.1f}" stroke="{GREY}" stroke-width="1" stroke-dasharray="3,4"/>')
        b.append(F.text(left - 12, Y(t) + 5, f'{t:.1f}', 14, 'normal', anchor='end', fill=INK2))
    b.append(f'<line x1="{left}" y1="{top}" x2="{left}" y2="{top + ph}" stroke="{F.INK}" stroke-width="1.3"/>')
    b.append(f'<line x1="{left}" y1="{top + ph}" x2="{left + pw}" y2="{top + ph}" stroke="{F.INK}" stroke-width="1.3"/>')
    for i, r in enumerate(rows):
        b.append(F.text(xs[i], top + ph + 24, r['vehicles'], 15, 'bold', fill=F.INK))
        b.append(F.text(xs[i], top + ph + 44, f"{int(r['rows_per_vehicle']):,} rows", 12, 'normal', fill=INK2))
    b.append(F.text(left + pw / 2, top + ph + 72, 'Vehicles in all (2 RSUs), and training rows per vehicle', 14, 'normal', fill=INK2))
    b.append(F.text(48, top + ph / 2 - 10, ['Global', 'ensemble', 'score'], 13, 'normal', fill=INK2))
    # the break band between the last point that holds and the first that does not
    i_break = next(i for i, r in enumerate(rows) if float(r['ens_f1']) < 0.9)
    bx1, bx2 = (xs[i_break - 1] + xs[i_break]) / 2 - 2, (xs[i_break - 1] + xs[i_break]) / 2 + 2
    b.append(f'<rect x="{bx1 - 10:.1f}" y="{top}" width="20" height="{ph}" fill="{F.RED_L}" opacity="0.8"/>')
    b.append(F.text(bx1 - 16, Y(0.62), ['utility gives way:', f'{rows[i_break - 1]["per_rsu"]} to {rows[i_break]["per_rsu"]} vehicles per RSU'], 13, 'bold', anchor='end', fill=RED))
    for key, col in (('ens_acc', NAVY), ('ens_f1', RED)):
        pts = ' '.join(f'{xs[i]:.1f},{Y(r[key]):.1f}' for i, r in enumerate(rows))
        b.append(f'<polyline points="{pts}" fill="none" stroke="{col}" stroke-width="3"/>')
        for i, r in enumerate(rows):
            b.append(f'<circle cx="{xs[i]:.1f}" cy="{Y(r[key]):.1f}" r="6" fill="{col}" stroke="#fff" stroke-width="1.5"/>')
    for i, r in enumerate(rows):                      # one label per point for F1 (below), and for accuracy only where the two part
        b.append(F.text(xs[i], Y(r['ens_f1']) + 22, f'{float(r["ens_f1"]):.2f}', 12, 'normal', fill=RED))
        if float(r['ens_acc']) - float(r['ens_f1']) > 0.03: b.append(F.text(xs[i], Y(r['ens_acc']) - 12, f'{float(r["ens_acc"]):.2f}', 12, 'normal', fill=NAVY))
    lx, ly = left + 30, top + ph - 60
    for j, (col, lab) in enumerate(((NAVY, 'Accuracy of the global ensemble'), (RED, 'F1 of the global ensemble'))):
        b.append(f'<line x1="{lx}" y1="{ly + j * 22}" x2="{lx + 30}" y2="{ly + j * 22}" stroke="{col}" stroke-width="3"/>')
        b.append(F.text(lx + 40, ly + j * 22 + 5, lab, 14, 'normal', anchor='start', fill=F.INK))
    (F.OUT / 'sweep.data.json').write_text(json.dumps({'kind': 'lines', 'x': [r['vehicles'] for r in rows], 'rows_per_vehicle': [r['rows_per_vehicle'] for r in rows],
                                                      'accuracy': [r['ens_acc'] for r in rows], 'f1': [r['ens_f1'] for r in rows], 'source': str(SWEEP.relative_to(ROOT))}, indent=1), encoding='utf-8')
    return F.render('sweep', W, H, ''.join(b))


def anchor_figure():
    panels = []
    for tag, title in (('foolsgold1', '(a) One Sybil added per RSU'), ('foolsgold5', '(b) Five Sybils added per RSU')):
        run = sorted(p for p in glob.glob(str(ATT / f'*-attack-{tag}-2x16-ciciov2024')) if 'probe' not in p)[0]
        e = json.load(open(pathlib.Path(run) / 'attack_eval.json')); aq = e['anchor_quality_check']; att = set(e['attackers'])
        pv = [(int(v), d['attack_recall'], int(v) in att) for v, d in aq['per_vehicle'].items()]; pv.sort()
        panels.append((title, pv, aq['honest']['attack_recall_min'], aq['attack_anchors'], pathlib.Path(run).name))
    W, H = 1180, 600; left, gap, top, bottom = 120, 60, 60, 120; pw = (W - left - gap - 40) // 2; ph = H - top - bottom
    def Y(v): return top + ph * (1 - float(v))
    b = []
    for pi, (title, pv, hmin, n_att, run) in enumerate(panels):
        x0 = left + pi * (pw + gap)
        b.append(F.text(x0 + pw / 2, top - 26, title, 15, 'bold', fill=F.INK))
        for t in (0, 0.2, 0.4, 0.6, 0.8, 1.0):
            b.append(f'<line x1="{x0}" y1="{Y(t):.1f}" x2="{x0 + pw}" y2="{Y(t):.1f}" stroke="{GREY}" stroke-width="1" stroke-dasharray="3,4"/>')
            if pi == 0: b.append(F.text(x0 - 12, Y(t) + 5, f'{t:.1f}', 14, 'normal', anchor='end', fill=INK2))
        b.append(f'<line x1="{x0}" y1="{top}" x2="{x0}" y2="{top + ph}" stroke="{F.INK}" stroke-width="1.3"/>')
        b.append(f'<line x1="{x0}" y1="{top + ph}" x2="{x0 + pw}" y2="{top + ph}" stroke="{F.INK}" stroke-width="1.3"/>')
        b.append(f'<line x1="{x0}" y1="{Y(hmin):.1f}" x2="{x0 + pw}" y2="{Y(hmin):.1f}" stroke="{GREEN}" stroke-width="2" stroke-dasharray="8,5"/>')
        b.append(F.text(x0 + pw - 6, Y(hmin) + 20, f'lowest honest vehicle: {hmin:.2f}', 13, 'normal', anchor='end', fill=GREEN))
        n = len(pv); step = pw / (n + 1)
        rsu_split = next((i for i, (v, _, _) in enumerate(pv) if v >= 2000), n)
        for i, (v, rec, is_att) in enumerate(pv):
            cx = x0 + step * (i + 1)
            b.append(f'<circle cx="{cx:.1f}" cy="{Y(rec):.1f}" r="{8 if is_att else 6}" fill="{RED if is_att else GREEN}" stroke="#fff" stroke-width="1.5"/>')
        b.append(F.text(x0 + step * (rsu_split / 2 + 0.5), top + ph + 24, 'RSU 1', 14, 'bold', fill=INK2))
        b.append(F.text(x0 + step * ((rsu_split + n) / 2 + 0.5), top + ph + 24, 'RSU 2', 14, 'bold', fill=INK2))
        b.append(F.text(x0 + pw / 2, top + ph + 46, 'one dot per vehicle', 13, 'normal', fill=INK2))
    b.append(F.text(56, top + ph / 2 - 10, ['Recall on', 'the attack', 'probes'], 13, 'normal', fill=INK2))
    lx, ly = left, H - 24
    b.append(f'<circle cx="{lx + 8}" cy="{ly - 4}" r="6" fill="{GREEN}"/>'); b.append(F.text(lx + 22, ly, 'honest vehicle', 14, 'normal', anchor='start', fill=F.INK))
    b.append(f'<circle cx="{lx + 160}" cy="{ly - 4}" r="8" fill="{RED}"/>'); b.append(F.text(lx + 176, ly, 'Sybil (attack rows relabelled benign)', 14, 'normal', anchor='start', fill=F.INK))
    (F.OUT / 'anchorcheck.data.json').write_text(json.dumps({'kind': 'dots', 'panels': [{'title': t, 'vehicles': [[v, r, a] for v, r, a in pv], 'honest_min': hmin, 'attack_probes': n_att, 'run': run} for t, pv, hmin, n_att, run in panels]}, indent=1), encoding='utf-8')
    return F.render('anchorcheck', W, H, ''.join(b))


def setup_table():
    """the conditions of the first experiment, for the supporting document (S4): commits read from the clones, data sizes from the
    preprocessed splits, settings from the runs' logs; nothing typed that a record does not hold"""
    import subprocess, re
    commits_f = ROOT / 'experiments' / 'COMMITS.json'                                 # the clones' commits, recorded for a copy without the clones
    commits = json.loads(commits_f.read_text(encoding='utf-8')) if commits_f.exists() else {}

    def commit(path):
        if (ROOT / path / '.git').exists():
            commits[path] = subprocess.run(['git', 'rev-parse', '--short', 'HEAD'], cwd=ROOT / path, capture_output=True, text=True).stdout.strip()
            commits_f.write_text(json.dumps(commits, indent=1), encoding='utf-8')
        return commits[path]
    def rows_of(csv_path): return sum(1 for _ in open(csv_path, 'rb')) - 1
    data = ROOT / 'experiments' / 'fl-bc-ids' / 'data' / 'preprocessed' / 'CICIoV2024'
    sizes = ROOT / 'experiments' / 'fl-bc-ids' / 'runs' / 'DATA-SIZES.json'            # the split sizes, recorded for a copy without the data set
    if data.exists():
        n_tr, n_va, n_te = (rows_of(data / f'CICIoV2024_{k}_preprocessed.csv') for k in ('train', 'val', 'test'))
        sizes.write_text(json.dumps({'train': n_tr, 'val': n_va, 'test': n_te, 'source': 'rows of the preprocessed CICIoV2024 splits'}, indent=1), encoding='utf-8')
    else:
        rec = json.loads(sizes.read_text(encoding='utf-8')); n_tr, n_va, n_te = rec['train'], rec['val'], rec['test']
    log = next((ROOT / 'experiments' / 'fl-bc-ids-attacks' / 'runs').glob('*-attack-none0-2x16-ciciov2024/runner.log')).read_text(errors='replace')
    dp = re.search(r'eps_per_round<=([0-9.]+), eps_total<=([0-9.]+) \(local_rounds=(\d+), global_rounds=(\d+)', log); tree = re.search(r'ε_tree=([0-9.]+), subsample=([0-9.]+)', log)
    mac = subprocess.run(['sysctl', '-n', 'machdep.cpu.brand_string'], capture_output=True, text=True).stdout.strip() or 'the desktop'
    mem = int(subprocess.run(['sysctl', '-n', 'hw.memsize'], capture_output=True, text=True).stdout.strip() or 0) // 2**30
    rows = [
        ['Designs run', f'zkPET (commit {commit("experiments/zkpet/repo")}, MIT) and FL-BC-IDS (commit {commit("experiments/fl-bc-ids/repo")}, MIT); the code of both unchanged, each run in an environment of its own'],
        ['Machine', f'one desktop computer ({mac}, {mem} GB of memory); zkPET on the desktop itself, FL-BC-IDS inside a Linux virtual machine on it with 8 processor cores and 16 GB; no device-class hardware (condition C1 untested)'],
        ['zkPET environment', 'Python 3.11, PyTorch 2.1.1, Flower 1.6, ezkl 9.5.0, a local Ethereum development chain (anvil) and solc 0.8.20; the repository\'s own data set and settings'],
        ['FL-BC-IDS environment', 'Python 3.12.10, dp-xgboost 0.2.10 (built from source), XGBoost 3.1.2, Flower 1.23, Ray 2.31, Node 24.19 with snarkjs 0.7.5, circom 2.1.8; the Powers-of-Tau file the repository names, with the same SHA-256'],
        ['Data', f'CICIoV2024 (decimal CSVs from the Canadian Institute for Cybersecurity), prepared by the repository\'s own preprocessing: {n_tr:,} training rows balanced by its oversampling, {n_va:,} validation rows, {n_te:,} test rows; seed 42, stratified 70/15/15'],
        ['Learning settings', f'the repository\'s documented configuration: {dp.group(4)} global rounds, {dp.group(3)} local rounds, differential privacy with epsilon {float(tree.group(1)):g} per tree and subsample {float(tree.group(2)):g} (epsilon at most {dp.group(2)} per vehicle), seed 42; only the topology and the attackers vary'],
        ['Scale sweep', '2 RSUs with 2, 4, 8, 16, 32, 50 and 100 vehicles each (4 to 200 vehicles); one run per point'],
        ['Attack protocols', f'FoolsGold Sybil label flipping (code commit {commit("experiments/fl-bc-ids-attacks/sources/foolsgold")}, MIT): 1 and 5 Sybils added to 16 honest vehicles per RSU, each Sybil a copy of the attack rows of one honest-sized share relabelled benign. Severi et al. clean-label backdoor (code commit {commit("experiments/fl-bc-ids-attacks/sources/malwarebackdoors")}, MIT): one payload-byte trigger chosen by their combined SHAP strategy from a clean model trained on the training set, written into benign rows amounting to 1% and 4% of the training set, held by 4 of the 16 vehicles per RSU; two runs per setting'],
        ['Measures', 'the runner\'s own global-ensemble metrics on the test split; FoolsGold\'s target attack rate; Severi\'s success accounting against the clean federated model as the reference; the probe check: each vehicle\'s committed predictions on 64 validation rows scored against their labels; FoolsGold\'s similarity test on the same vectors'],
    ]
    D.md_table('experiment_setup', 'The conditions of the first experiment (Section VII-B): code, machine, environments, data, settings, the sweep, the attack protocols and the measures.', ['Item', 'Setting'], rows)
    return rows


def main():
    rows = attack_table(); sweep_figure(); anchor_figure(); setup_table()
    caps = {'sweep': 'Utility of FL-BC-IDS as released, scaled from 4 to 200 vehicles on CICIoV2024: accuracy and F1 of the global ensemble, and the training rows per vehicle',
            'anchorcheck': 'Probe check on the anchor vectors FL-BC-IDS commits, under Sybil label flipping (run 1): each vehicle\'s recall on the 11 labelled attack probes'}
    folder = ROOT / 'myliteraturereviewpaper' / 'ppml2026' / os.environ.get('PPML_PARTS_NAME', 'parts-v82')
    fc = folder / 'figcaps.json'; d = json.loads(fc.read_text(encoding='utf-8')) if fc.exists() else {}
    d.update(caps); fc.write_text(json.dumps(d, indent=1), encoding='utf-8')
    print('experiment V82: table experiment_attacks', len(rows), 'rows; figures sweep, anchorcheck; captions ->', fc.relative_to(ROOT))


if __name__ == '__main__':
    main()
