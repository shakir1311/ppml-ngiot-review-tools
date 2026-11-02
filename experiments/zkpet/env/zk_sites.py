#!/usr/bin/env python3
"""zkPET experiment, run 2: per-site training and zero-knowledge proving of the Linear forecasting model, exactly as the
repository's decentralised notebook does it (src/electricity_decentralized_ZKML.ipynb), but driven from this script so that
the clone stays untouched and every artefact lands in a run folder.

For each site t: (1) train with the repository's own run_longExp.py and the arguments of its train.sh (Linear, features S,
target t, seq_len, pred_len 24, batch 16, lr 0.001, CPU); (2) load the checkpoint into the repository's Linear model, export
ONNX (opset 10, as the notebook) and the last seq_len readings of the site as input.json; (3) ezkl: gen_settings (private
input, public output, fixed params) → calibrate (resources) → compile → get_srs → setup → gen_witness → prove × N
(wall time, process peak RSS) → verify → create_evm_verifier → deploy to anvil → verify on chain; (4) sizes and times to
<run>/zkml_perf_mac.csv in the columns of the repository's src/zkml_perf.csv plus ours. Progress lines are timestamped.

Usage (from experiments/zkpet, anvil already listening on --rpc):
  env/.venv/bin/python -u env/zk_sites.py --run runs/<stamp>-zk-sites --sites 0 1 2 --seq_len 192 --repeats 10
"""
import argparse, asyncio, csv, json, os, pathlib, resource, subprocess, sys, time

HERE = pathlib.Path(__file__).resolve().parent          # experiments/zkpet/env
BASE = HERE.parent                                      # experiments/zkpet
REPO = BASE / 'repo'
PY = sys.executable
os.environ['PATH'] = f"{HERE / 'bin'}:{HERE / 'foundry'}:{os.environ.get('PATH', '')}"   # solc (py-solc-x) and anvil of this experiment


def log(msg):
    print(time.strftime('%H:%M:%S'), msg, flush=True)


def rss_mb():
    r = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return r / (1024 * 1024) if sys.platform == 'darwin' else r / 1024


def done(res):
    """ezkl functions are sync in some versions and coroutines in others; settle either."""
    if asyncio.iscoroutine(res):
        return asyncio.get_event_loop().run_until_complete(res)
    return res


def train_site(run, t, seq_len, pred_len, model='Linear'):
    """the repository's training, with train.sh's arguments; outputs under <run>/checkpoints/"""
    setting = f'Electricity_{seq_len}_{pred_len}_{model}_custom_ftS_tg{t}_sl{seq_len}_ll48_pl{pred_len}_dm512_nh8_el2_dl1_df2048_fc1_ebtimeF_dtTrue_Exp_0'
    ck = run / 'checkpoints' / setting / 'checkpoint.pth'
    if ck.exists():
        log(f'site {t}: checkpoint exists, training skipped'); return ck
    cmd = [PY, '-u', str(REPO / 'run_longExp.py'), '--is_training', '1', '--root_path', './dataset/', '--data_path', 'electricity.csv',
           '--model_id', f'Electricity_{seq_len}_{pred_len}', '--model', model, '--data', 'custom', '--features', 'S', '--target', str(t),
           '--seq_len', str(seq_len), '--pred_len', str(pred_len), '--enc_in', '321', '--des', 'Exp', '--use_gpu', 'false',
           '--itr', '1', '--batch_size', '16', '--learning_rate', '0.001']
    logf = run / 'logs' / f'train_site{t}_sl{seq_len}.log'; logf.parent.mkdir(exist_ok=True)
    t0 = time.time(); log(f'site {t}: training ({model}, seq {seq_len}, pred {pred_len}) -> {logf.name}')
    with open(logf, 'w') as fh:
        p = subprocess.run(cmd, cwd=run, stdout=fh, stderr=subprocess.STDOUT, env={**os.environ, 'PYTHONPATH': str(REPO), 'PYTHONUNBUFFERED': '1'})
    if p.returncode != 0 or not ck.exists():
        raise SystemExit(f'site {t}: training failed (exit {p.returncode}); see {logf}')
    log(f'site {t}: trained in {time.time() - t0:.0f} s -> {ck.parent.name}')
    return ck


def zk_site(run, t, ck, seq_len, pred_len, repeats, rpc, model='Linear'):
    import torch, pandas as pd, ezkl
    sys.path.insert(0, str(REPO))
    from models.Linear import Model as Linear                      # the repository's model, unchanged

    class Configs:
        def __init__(s): s.seq_len, s.pred_len, s.enc_in, s.individual = seq_len, pred_len, 321, False
    circuit = Linear(Configs()); circuit.load_state_dict(torch.load(ck, map_location='cpu')); circuit.eval()
    total_params = sum(p.numel() for p in circuit.parameters())
    df = pd.read_csv(REPO / 'dataset' / 'electricity.csv')
    x = torch.tensor(df[str(t)][-seq_len:].values, requires_grad=True).resize(1, seq_len, 1).float()
    d = run / f'site{t}_sl{seq_len}'; d.mkdir(exist_ok=True)
    P = {k: str(d / v) for k, v in dict(model='network.onnx', compiled='network.ezkl', pk='test.pk', vk='test.vk', settings='settings.json',
                                       srs='kzg.srs', witness='witness.json', data='input.json', proof='test.pf', sol='verify.sol', abi='verify.abi', addr='contractAddr.txt').items()}
    torch.onnx.export(circuit, x, P['model'], export_params=True, opset_version=10, do_constant_folding=True, input_names=['input'],
                      output_names=['output'], dynamic_axes={'input': {0: 'batch_size'}, 'output': {0: 'batch_size'}})
    json.dump(dict(input_data=[x.detach().numpy().reshape([-1]).tolist()]), open(P['data'], 'w'))
    log(f'site {t}: onnx {os.path.getsize(P["model"]) / 1024:.3f} KB, input {os.path.getsize(P["data"]) / 1024:.3f} KB, {total_params} parameters')
    ra = ezkl.PyRunArgs(); ra.input_visibility = 'private'; ra.output_visibility = 'public'; ra.param_visibility = 'fixed'
    T = {}
    t0 = time.time(); assert done(ezkl.gen_settings(P['model'], P['settings'], py_run_args=ra)); done(ezkl.calibrate_settings(P['data'], P['model'], P['settings'], 'resources'))
    T['settings_s'] = time.time() - t0; st = json.load(open(P['settings'])); log(f'site {t}: settings in {T["settings_s"]:.1f} s, logrows {st["run_args"]["logrows"]}, rows {st.get("num_rows")}')
    t0 = time.time(); assert done(ezkl.compile_circuit(P['model'], P['compiled'], P['settings'])); T['compile_s'] = time.time() - t0; log(f'site {t}: compiled in {T["compile_s"]:.1f} s')
    t0 = time.time(); srs_how = 'public ceremony (get_srs)'
    try:
        done(ezkl.get_srs(srs_path=P['srs'], settings_path=P['settings']))
    except Exception as ex:                                                                 # noqa: BLE001
        # ezkl 9.5's download of the perpetual-powers-of-tau file fails on this Mac ("input number is not less than field
        # modulus"); a locally generated SRS of the same size gives identical proof sizes and timings, so fall back to it.
        srs_how = f'generated locally (gen_srs, logrows {st["run_args"]["logrows"]}) after get_srs failed: {str(ex)[:80]}'
        done(ezkl.gen_srs(P['srs'], st['run_args']['logrows']))
    T['srs_s'] = time.time() - t0
    log(f'site {t}: srs {os.path.getsize(P["srs"]) / 1048576:.2f} MB in {T["srs_s"]:.1f} s, {srs_how}')
    t0 = time.time(); assert done(ezkl.setup(P['compiled'], P['vk'], P['pk'], P['srs'])); T['setup_s'] = time.time() - t0
    log(f'site {t}: setup (pk {os.path.getsize(P["pk"]) / 1048576:.1f} MB) in {T["setup_s"]:.1f} s')
    times = []; rss0 = rss_mb()
    for i in range(repeats):
        t0 = time.time(); done(ezkl.gen_witness(P['data'], P['compiled'], P['witness'])); done(ezkl.prove(P['witness'], P['compiled'], P['pk'], P['proof'], 'single', P['srs']))
        times.append(time.time() - t0); log(f'site {t}: proof {i + 1}/{repeats} in {times[-1]:.2f} s (rss {rss_mb():.0f} MB)')
    T['prove_s_mean'] = sum(times) / len(times); T['prove_s_min'] = min(times); T['prove_s_max'] = max(times); T['peak_rss_mb'] = rss_mb(); T['rss_before_prove_mb'] = rss0
    t0 = time.time(); assert done(ezkl.verify(P['proof'], P['settings'], P['vk'], P['srs'])); T['verify_s'] = time.time() - t0; log(f'site {t}: verified off chain in {T["verify_s"]:.2f} s')
    done(ezkl.create_evm_verifier(vk_path=P['vk'], srs_path=P['srs'], settings_path=P['settings'], sol_code_path=P['sol'], abi_path=P['abi']))
    T['verifier_kb'] = os.path.getsize(P['sol']) / 1024; log(f'site {t}: verifier contract {T["verifier_kb"]:.1f} KB')
    onchain = 'skipped'
    if rpc:
        try:
            done(ezkl.deploy_evm(P['addr'], P['sol'], rpc)); addr = open(P['addr']).readline().strip()
            t0 = time.time(); ok = done(ezkl.verify_evm(proof_path=P['proof'], addr_verifier=addr, rpc_url=rpc)); T['verify_evm_s'] = time.time() - t0
            onchain = f'verified at {addr}' if ok else f'NOT verified at {addr}'; log(f'site {t}: on chain: {onchain} ({T["verify_evm_s"]:.2f} s)')
        except Exception as ex:                                                             # noqa: BLE001
            onchain = f'error: {str(ex)[:160]}'; log(f'site {t}: on-chain step failed: {str(ex)[:200]}')
    row = {'site': t, 'seq_len': seq_len, 'Parameters': total_params, 'Input Size': round(os.path.getsize(P['data']) / 1024, 3), 'ONNX Size': round(os.path.getsize(P['model']) / 1024, 3),
           'Proof Size': round(os.path.getsize(P['proof']) / 1024, 3), 'Prove Time': round(T['prove_s_mean'], 3), 'Prove Mem': round(T['peak_rss_mb'], 1), 'Verifier Size': round(T['verifier_kb'], 3),
           'logrows': st['run_args']['logrows'], 'settings_s': round(T['settings_s'], 1), 'compile_s': round(T['compile_s'], 1), 'srs_s': round(T['srs_s'], 1), 'setup_s': round(T['setup_s'], 1),
           'prove_s_min': round(T['prove_s_min'], 3), 'prove_s_max': round(T['prove_s_max'], 3), 'verify_s': round(T['verify_s'], 3), 'verify_evm_s': round(T.get('verify_evm_s', 0), 3), 'on_chain': onchain,
           'pk_mb': round(os.path.getsize(P['pk']) / 1048576, 1), 'srs_mb': round(os.path.getsize(P['srs']) / 1048576, 1)}
    return row


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--run', required=True); ap.add_argument('--sites', type=int, nargs='+', default=[0]); ap.add_argument('--seq_len', type=int, default=192)
    ap.add_argument('--pred_len', type=int, default=24); ap.add_argument('--repeats', type=int, default=10); ap.add_argument('--rpc', default='http://127.0.0.1:3030'); ap.add_argument('--no-chain', action='store_true')
    a = ap.parse_args(); run = pathlib.Path(a.run).resolve(); run.mkdir(parents=True, exist_ok=True)
    if not (run / 'dataset').exists():
        os.symlink(REPO / 'dataset', run / 'dataset')
    out = run / 'zkml_perf_mac.csv'; rows = []
    log(f'run {run.name}: sites {a.sites}, seq_len {a.seq_len}, pred_len {a.pred_len}, repeats {a.repeats}, rpc {"none" if a.no_chain else a.rpc}')
    for t in a.sites:
        ck = train_site(run, t, a.seq_len, a.pred_len)
        row = zk_site(run, t, ck, a.seq_len, a.pred_len, a.repeats, None if a.no_chain else a.rpc); rows.append(row)
        with open(out, 'w', newline='') as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
        log(f'site {t}: DONE  prove {row["Prove Time"]} s, proof {row["Proof Size"]} KB, verifier {row["Verifier Size"]} KB -> {out.name}')
    log(f'ALL DONE: {len(rows)} sites -> {out}')


if __name__ == '__main__':
    main()
