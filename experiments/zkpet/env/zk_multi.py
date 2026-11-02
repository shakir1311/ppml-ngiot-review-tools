#!/usr/bin/env python3
"""zkPET run 5: the aggregated multi-site models of the centralised notebook (src/electricity_centralized_ZKML.ipynb):
one Linear model with an individual linear layer per site for the first k sites (k channels, --features M --individual),
trained with the repository's run_longExp.py on a copy of the data set cut to those k sites (made in the run folder; the
repository's data set is not touched), then exported to ONNX (opset 15, as the notebook) and proved with ezkl exactly as
run 2 does. These are the models behind the paper's proving-cost figures at 10, 20, 30 and 40 sites (46,320 to 185,280
parameters, log-rows 18 to 21). Usage (from experiments/zkpet, anvil on --rpc or --no-chain):
  env/.venv/bin/python -u env/zk_multi.py --run runs/<stamp>-zk-multi --channels 10 20 --seq_len 192 --repeats 3
"""
import argparse, csv, json, os, pathlib, subprocess, sys, time
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import zk_sites as Z                                           # log, done, rss_mb, REPO, PY, PATH with solc and anvil


def cut_dataset(run, k):
    import pandas as pd
    out = run / 'dataset' / f'electricity_{k}.csv'
    if not out.exists():
        out.parent.mkdir(exist_ok=True)
        df = pd.read_csv(Z.REPO / 'dataset' / 'electricity.csv'); df.iloc[:, :k + 1].to_csv(out, index=False)
    return out


def train_multi(run, k, seq_len, pred_len):
    setting = f'Electricity_{seq_len}_{pred_len}_Linear_custom_ftM_tg0_sl{seq_len}_ll48_pl{pred_len}_dm512_nh8_el2_dl1_df2048_fc1_ebtimeF_dtTrue_Exp_0'
    ck = run / f'k{k}' / 'checkpoints' / setting / 'checkpoint.pth'
    if ck.exists():
        Z.log(f'k={k}: checkpoint exists, training skipped'); return ck
    (run / f'k{k}').mkdir(parents=True, exist_ok=True)
    cmd = [Z.PY, '-u', str(Z.REPO / 'run_longExp.py'), '--is_training', '1', '--root_path', str(run / 'dataset') + '/', '--data_path', f'electricity_{k}.csv',
           '--model_id', f'Electricity_{seq_len}_{pred_len}', '--model', 'Linear', '--data', 'custom', '--features', 'M', '--target', '0', '--individual',
           '--seq_len', str(seq_len), '--pred_len', str(pred_len), '--enc_in', str(k), '--des', 'Exp', '--use_gpu', 'false', '--itr', '1', '--batch_size', '16', '--learning_rate', '0.001']
    logf = run / 'logs' / f'train_k{k}_sl{seq_len}.log'; logf.parent.mkdir(exist_ok=True)
    t0 = time.time(); Z.log(f'k={k}: training (Linear individual, {k} channels, seq {seq_len}) -> {logf.name}')
    with open(logf, 'w') as fh:
        p = subprocess.run(cmd, cwd=run / f'k{k}', stdout=fh, stderr=subprocess.STDOUT, env={**os.environ, 'PYTHONPATH': str(Z.REPO), 'PYTHONUNBUFFERED': '1'})
    if p.returncode != 0 or not ck.exists():
        raise SystemExit(f'k={k}: training failed (exit {p.returncode}); see {logf}')
    Z.log(f'k={k}: trained in {time.time() - t0:.0f} s'); return ck


def zk_multi(run, k, ck, seq_len, pred_len, repeats, rpc):
    import torch, pandas as pd, ezkl
    sys.path.insert(0, str(Z.REPO)); from models.Linear import Model as Linear

    class Configs:
        def __init__(s): s.seq_len, s.pred_len, s.enc_in, s.individual = seq_len, pred_len, k, True
    circuit = Linear(Configs()); circuit.load_state_dict(torch.load(ck, map_location='cpu')); circuit.eval()
    total_params = sum(p.numel() for p in circuit.parameters())
    df = pd.read_csv(run / 'dataset' / f'electricity_{k}.csv')
    x = torch.tensor(df[-seq_len:].drop(labels=['date'], axis=1).values, requires_grad=True).resize(1, seq_len, k).float()
    d = run / f'k{k}'; P = {n: str(d / v) for n, v in dict(model='network.onnx', compiled='network.ezkl', pk='test.pk', vk='test.vk', settings='settings.json', srs='kzg.srs', witness='witness.json',
                                                           data='input.json', proof='test.pf', sol='verify.sol', abi='verify.abi', addr='contractAddr.txt').items()}
    torch.onnx.export(circuit, x, P['model'], export_params=True, opset_version=15, do_constant_folding=True, input_names=['input'], output_names=['output'],
                      dynamic_axes={'input': {0: 'batch_size'}, 'output': {0: 'batch_size'}})
    json.dump(dict(input_data=[x.detach().numpy().reshape([-1]).tolist()]), open(P['data'], 'w'))
    Z.log(f'k={k}: onnx {os.path.getsize(P["model"]) / 1024:.1f} KB, input {os.path.getsize(P["data"]) / 1024:.1f} KB, {total_params} parameters')
    ra = ezkl.PyRunArgs(); ra.input_visibility = 'private'; ra.output_visibility = 'public'; ra.param_visibility = 'fixed'; ra.variables = [('batch_size', 1)]
    T = {}; t0 = time.time(); assert Z.done(ezkl.gen_settings(P['model'], P['settings'], py_run_args=ra)); Z.done(ezkl.calibrate_settings(P['data'], P['model'], P['settings'], 'resources'))
    T['settings_s'] = time.time() - t0; st = json.load(open(P['settings'])); lr = st['run_args']['logrows']; Z.log(f'k={k}: settings in {T["settings_s"]:.1f} s, logrows {lr}, rows {st.get("num_rows")}')
    t0 = time.time(); assert Z.done(ezkl.compile_circuit(P['model'], P['compiled'], P['settings'])); T['compile_s'] = time.time() - t0
    t0 = time.time()
    try:
        Z.done(ezkl.get_srs(srs_path=P['srs'], settings_path=P['settings'])); how = 'public ceremony'
    except Exception:                                                                       # noqa: BLE001
        Z.done(ezkl.gen_srs(P['srs'], lr)); how = 'generated locally'
    T['srs_s'] = time.time() - t0; Z.log(f'k={k}: srs {os.path.getsize(P["srs"]) / 1048576:.1f} MB in {T["srs_s"]:.1f} s ({how})')
    t0 = time.time(); assert Z.done(ezkl.setup(P['compiled'], P['vk'], P['pk'], P['srs'])); T['setup_s'] = time.time() - t0; Z.log(f'k={k}: setup (pk {os.path.getsize(P["pk"]) / 1048576:.0f} MB) in {T["setup_s"]:.1f} s')
    times = []
    for i in range(repeats):
        t0 = time.time(); Z.done(ezkl.gen_witness(P['data'], P['compiled'], P['witness'])); Z.done(ezkl.prove(P['witness'], P['compiled'], P['pk'], P['proof'], 'single', P['srs']))
        times.append(time.time() - t0); Z.log(f'k={k}: proof {i + 1}/{repeats} in {times[-1]:.1f} s (rss {Z.rss_mb():.0f} MB)')
    t0 = time.time(); assert Z.done(ezkl.verify(P['proof'], P['settings'], P['vk'], P['srs'])); T['verify_s'] = time.time() - t0; Z.log(f'k={k}: verified off chain in {T["verify_s"]:.2f} s')
    Z.done(ezkl.create_evm_verifier(vk_path=P['vk'], srs_path=P['srs'], settings_path=P['settings'], sol_code_path=P['sol'], abi_path=P['abi'])); onchain = 'skipped'
    if rpc:
        try:
            Z.done(ezkl.deploy_evm(P['addr'], P['sol'], rpc)); addr = open(P['addr']).readline().strip(); t0 = time.time()
            ok = Z.done(ezkl.verify_evm(proof_path=P['proof'], addr_verifier=addr, rpc_url=rpc)); T['verify_evm_s'] = time.time() - t0; onchain = ('verified at ' if ok else 'NOT verified at ') + addr
            Z.log(f'k={k}: on chain: {onchain} ({T["verify_evm_s"]:.2f} s)')
        except Exception as ex:                                                             # noqa: BLE001
            onchain = f'error: {str(ex)[:160]}'; Z.log(f'k={k}: on-chain step failed: {str(ex)[:200]}')
    return {'channels': k, 'seq_len': seq_len, 'Parameters': total_params, 'Input Size': round(os.path.getsize(P['data']) / 1024, 3), 'ONNX Size': round(os.path.getsize(P['model']) / 1024, 3),
            'Proof Size': round(os.path.getsize(P['proof']) / 1024, 3), 'Prove Time': round(sum(times) / len(times), 3), 'prove_s_min': round(min(times), 3), 'prove_s_max': round(max(times), 3),
            'Prove Mem': round(Z.rss_mb(), 1), 'Verifier Size': round(os.path.getsize(P['sol']) / 1024, 3), 'logrows': lr, 'settings_s': round(T['settings_s'], 1), 'compile_s': round(T['compile_s'], 1),
            'srs_s': round(T['srs_s'], 1), 'setup_s': round(T['setup_s'], 1), 'verify_s': round(T['verify_s'], 3), 'verify_evm_s': round(T.get('verify_evm_s', 0), 3), 'pk_mb': round(os.path.getsize(P['pk']) / 1048576, 1),
            'srs_mb': round(os.path.getsize(P['srs']) / 1048576, 1), 'on_chain': onchain}


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--run', required=True); ap.add_argument('--channels', type=int, nargs='+', default=[10]); ap.add_argument('--seq_len', type=int, default=192)
    ap.add_argument('--pred_len', type=int, default=24); ap.add_argument('--repeats', type=int, default=3); ap.add_argument('--rpc', default='http://127.0.0.1:3030'); ap.add_argument('--no-chain', action='store_true')
    a = ap.parse_args(); run = pathlib.Path(a.run).resolve(); run.mkdir(parents=True, exist_ok=True); out = run / 'zkml_perf_mac.csv'; rows = []
    Z.log(f'run {run.name}: channels {a.channels}, seq_len {a.seq_len}, repeats {a.repeats}')
    for k in a.channels:
        cut_dataset(run, k); ck = train_multi(run, k, a.seq_len, a.pred_len)
        row = zk_multi(run, k, ck, a.seq_len, a.pred_len, a.repeats, None if a.no_chain else a.rpc); rows.append(row)
        with open(out, 'w', newline='') as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
        Z.log(f'k={k}: DONE  prove {row["Prove Time"]} s, proof {row["Proof Size"]} KB, logrows {row["logrows"]}, rss {row["Prove Mem"]} MB')
    Z.log(f'ALL DONE: {len(rows)} models -> {out}')


if __name__ == '__main__':
    main()
