#!/usr/bin/env python3
"""Draws the six carried-forward designs in one style, as sequence diagrams of one round: who takes part and who sends what to whom, so that the designs can be compared side by side.

Each design is a set of lanes (its parties, with a Tabler icon each, via scripts/paper_ppml/icons.py) and numbered steps: an arrow
from one lane to another for a message, a box on a lane for work a party does on its own. Colour carries meaning, as in the
paper's figures: blue the operating parties and their work, green a check or a proof, gold the ledger. The flows (FLOWS) are the
reviewer's rendering of the study readers' records of each design (study/reader.json, card.parties and card.round, in the
readers' own words), shortened to labels; the papers' own diagrams sit beside them in the document. Writes
design-evaluation/study/diagrams/<id>.svg.

Usage: python3 scripts/design_eval/study_diagrams.py
"""
import html, pathlib, sys, textwrap

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / 'paper_ppml'))
from common import EVAL   # noqa: E402
import icons   # noqa: E402

OUT = EVAL / 'study' / 'diagrams'
COL = {'op': ('#2a5db0', '#e9f0fb'), 'check': ('#1f7a4d', '#e6f4ec'), 'ledger': ('#9a6a00', '#fbf1dc'), 'adv': ('#a33a3a', '#f8e6e6')}
FLOWS = {
    'n2721': {'name': 'zkPET', 'lanes': [
        ('site', 'Sites', 'households: private load data', 'home-signal', 'op'),
        ('agg', 'Energy aggregator', 'server: clusters, FedAvg, proofs', 'server-2', 'op'),
        ('cloud', 'Cloud', 'public model store', 'cloud-computing', 'op'),
        ('chain', 'Verifier contract', 'on the blockchain', 'cube', 'ledger')],
        'steps': [
        ('site', 'agg', 'trend and seasonality summaries', 'op'),
        ('agg', None, 'cluster the sites (DTW distance, k-Medoids)', 'op'),
        ('agg', 'site', 'initial model per cluster', 'op'),
        ('site', 'agg', 'local model weights ⇄ averaged model (FedAvg, until convergence; weights not protected)', 'op', 'both'),
        ('agg', 'cloud', 'publish the converged cluster model', 'op'),
        ('cloud', 'site', 'download the public model', 'op'),
        ('site', None, 'zk-SNARK (EZKL, Halo2, KZG): the forecast comes from the public model on the private history', 'check'),
        ('site', 'agg', 'proofs', 'check'),
        ('agg', None, 'aggregate the proofs recursively: one per cluster', 'check'),
        ('agg', 'chain', 'aggregated proof', 'check'),
        ('chain', None, 'verify the proof; store the forecast for trading', 'ledger')]},
    'n3378': {'name': 'FL-BC-IDS', 'lanes': [
        ('veh', 'Vehicles', 'clients: DP-XGBoost on own data', 'car', 'op'),
        ('rsu', 'Roadside unit', 'edge: admits, bags, proves', 'building-broadcast-tower', 'op'),
        ('glob', 'Global stage', 'cloud: combines the RSUs', 'cloud-computing', 'op'),
        ('chain', 'Verifier contract', 'Ethereum test network', 'cube', 'ledger'),
        ('aud', 'Offline auditor', 'replays the record', 'file-search', 'check')],
        'steps': [
        ('rsu', 'veh', 'current booster', 'op'),
        ('veh', None, 'train 10 boosting rounds with differential privacy; new trees, DP record, quantised anchor; Ed25519-signed report', 'op'),
        ('veh', 'rsu', 'new trees + DP record + anchor + signed report', 'op'),
        ('rsu', None, 'check signature, round, scope and digests; admit or exclude with a reason', 'check'),
        ('rsu', None, 'bag the admitted trees; Merkle roots; Groth16 proof of the masked anchor sum', 'check'),
        ('rsu', 'veh', 'new booster for the next round', 'op'),
        ('rsu', 'glob', 'bundle: manifest, roots, proof', 'op'),
        ('glob', None, 'validate bundles; inclusion mask; clipped mean of RSU scores', 'check'),
        ('glob', 'chain', 'Groth16 proof + public inputs', 'check'),
        ('chain', None, 'verify; store a receipt with digest pins', 'ledger'),
        ('glob', 'aud', 'exported bundle', 'op'),
        ('aud', None, 'recompute digests, signatures, aggregation, roots; compare with the receipt', 'check')]},
    'Z01': {'name': 'PoL-BFL', 'lanes': [
        ('cli', 'Clients', 'organisations: train, stake', 'users-group', 'op'),
        ('store', 'Trace store', 'off-chain (e.g. IPFS)', 'database', 'op'),
        ('chain', 'Smart contracts', 'Ethereum-type chain', 'cube', 'ledger'),
        ('com', 'Verifier committee', '5 chosen by VRF, 3 to decide', 'shield-check', 'check'),
        ('agg', 'Aggregator', 'robust aggregation', 'server-2', 'op')],
        'steps': [
        ('chain', 'cli', 'global model', 'ledger'),
        ('cli', None, 'train locally; keep a proof-of-learning trace (checkpoints, batch hashes)', 'op'),
        ('cli', 'store', 'full trace', 'op'),
        ('cli', 'chain', 'Merkle root of the checkpoints (commitment)', 'ledger'),
        ('cli', 'agg', 'model update', 'op'),
        ('chain', 'cli', 'challenge a random share of clients: K recent + R random intervals', 'ledger'),
        ('cli', 'com', 'Groth16 proof per sampled interval', 'check'),
        ('com', None, 'verify off-chain; sign receipts', 'check'),
        ('com', 'chain', 'signed receipts (3 of 5 decide)', 'check'),
        ('chain', None, 'on rejection: slash the stake, drop the client', 'ledger'),
        ('chain', 'agg', 'clients that passed', 'ledger'),
        ('agg', None, 'reputation-weighted robust aggregation (trimmed mean)', 'check'),
        ('chain', None, 'update reputation; pay rewards', 'ledger')]},
    'Z04': {'name': 'RoFL', 'lanes': [
        ('cli', 'Clients', 'm selected per round; some malicious', 'devices', 'op'),
        ('srv', 'FL server', 'aggregates, verifies proofs', 'server-2', 'op'),
        ('pki', 'PKI', 'authenticated keys', 'key', 'op')],
        'steps': [
        ('srv', 'cli', 'selection + global model', 'op'),
        ('cli', None, 'train; quantise the update to 8-bit integers', 'op'),
        ('pki', 'cli', 'authenticated keys of the other clients', 'op'),
        ('cli', 'srv', 'public keys; Shamir shares of mask seeds (relayed to neighbours)', 'op'),
        ('cli', 'srv', 'masked ElGamal commitments + Bulletproof range proofs on the update norm (L-infinity or L2)', 'check'),
        ('srv', None, 'verify the proofs (a random subset for L-infinity); drop a failing client', 'check'),
        ('cli', 'srv', 'shares for survivors and dropouts', 'op'),
        ('srv', None, 'rebuild the aggregate key; check the randomness term; decode the sum (discrete log)', 'check'),
        ('srv', 'cli', 'new global model (next round may start before the last is verified)', 'op')]},
    'Z06': {'name': 'zkPoT', 'lanes': [
        ('prv', 'Prover', 'trains the model; 512 MPC parties in its head', 'cpu', 'op'),
        ('ver', 'Verifier', 'holds commitments and the training spec', 'shield-check', 'check')],
        'steps': [
        ('prv', 'ver', 'commitments to the data and the training randomness; the training specification', 'op'),
        ('prv', None, 'offline: correlated randomness and masks as packed secret shares; FRI proofs they are well formed', 'check'),
        ('prv', None, 'data checks: two packings of the data consistent with its commitment (polynomial commitments)', 'check'),
        ('prv', None, 'online: run logistic-regression training as a 512-party MPC in the head; commit to the parties\' views', 'op'),
        ('prv', 'ver', 'model commitment + commitments to the views', 'check'),
        ('ver', 'prv', 'challenge: a random subset of views to open', 'check'),
        ('prv', 'ver', 'opened views + batched inner-product checks (FRI openings)', 'check'),
        ('ver', None, 'accept if the views are consistent, the checks pass and the model matches its commitment', 'check')]},
    'Z07': {'name': 'zk-DEAP', 'lanes': [
        ('me', 'Participant i', 'holds a private input', 'user-check', 'op'),
        ('peers', 'Other participants', 'n peers; up to t-1 corrupted', 'users-group', 'op'),
        ('tau', 'Powers of Tau', 'public parameters (SNARK variant)', 'file-certificate', 'op')],
        'steps': [
        ('me', 'peers', 'FROST distributed key generation: shared key Y, key shares; Ed25519 keys', 'op', 'both'),
        ('tau', 'me', 'KZG parameters (Halo2 variant only)', 'op'),
        ('me', None, 'encrypt the input under Y (lifted ElGamal)', 'op'),
        ('me', None, 'proof package: Schnorr link + Bulletproof, Halo2 or STARK proof of the predicate + signature', 'check'),
        ('me', 'peers', 'broadcast the package', 'op'),
        ('peers', None, 'check size, time, nonce, signature, Schnorr link, proof; multiply valid ciphertexts into the aggregate', 'check'),
        ('me', 'peers', 'partial decryption + Chaum-Pedersen proof', 'check'),
        ('peers', None, 'verify; combine t partials (Lagrange); recover the sum (discrete log)', 'check')]},
}
E = lambda s: html.escape(str(s))
W, TOP, LH, FS = 1000, 130, 19, 15


def draw(f):
    lanes = f['lanes']
    n = len(lanes)
    left, right = 64, W - 24
    gap = (right - left) / n
    x = {k: left + gap * (j + 0.5) for j, (k, *_) in enumerate(lanes)}
    rows, y = [], TOP + 20
    for st in f['steps']:
        a, b, label, kind = st[:4]
        if b is None:
            width = min(gap * 1.7, right - left) if n > 2 else gap * 0.92
            lines = textwrap.wrap(label, max(14, int(width / (FS * 0.55))))
            h = len(lines) * LH + 16
        else:
            width = abs(x[a] - x[b]) - 20
            lines = textwrap.wrap(label, max(14, int(max(width, gap * 0.9) / (FS * 0.55))))
            h = len(lines) * LH + 22
        rows.append((st, lines, y, h, width))
        y += h + 12
    H = y + 16
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H:.0f}" width="{W}" height="{H:.0f}" '
           f'font-family="Helvetica, Arial, sans-serif" role="img" aria-label="{E(f["name"])}: one round">',
           f'<rect width="{W}" height="{H:.0f}" fill="#ffffff"/>',
           '<defs>' + ''.join(f'<marker id="ah-{k}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
                               f'<path d="M0,0 L10,5 L0,10 z" fill="{c[0]}"/></marker>' for k, c in COL.items()) + '</defs>']
    for k, name, role, ic, kind in lanes:                   # lane heads and lifelines
        c = COL[kind]
        bw = min(gap - 12, 190)
        out.append(f'<line x1="{x[k]:.1f}" y1="{TOP - 6}" x2="{x[k]:.1f}" y2="{H - 10:.0f}" stroke="#b8bfcc" stroke-width="1.5" stroke-dasharray="5 5"/>')
        out.append(f'<rect x="{x[k] - bw / 2:.1f}" y="8" width="{bw:.1f}" height="{TOP - 18}" rx="9" fill="{c[1]}" stroke="{c[0]}" stroke-width="1.6"/>')
        out.append(icons.icon(ic, x[k] - 17, 14, 34, c[0]))
        out.append(f'<text x="{x[k]:.1f}" y="70" text-anchor="middle" font-size="16" font-weight="700" fill="#1d2330">{E(name)}</text>')
        for j, ln in enumerate(textwrap.wrap(role, max(12, int(bw / 8.0)))[:2]):
            out.append(f'<text x="{x[k]:.1f}" y="{90 + j * 17}" text-anchor="middle" font-size="14" fill="#4a5262">{E(ln)}</text>')
    for num, (st, lines, y0, h, width) in enumerate(rows, 1):
        a, b, label, kind = st[:4]
        c = COL[kind]
        out.append(f'<circle cx="26" cy="{y0 + h / 2:.1f}" r="13" fill="{c[0]}"/>'
                   f'<text x="26" y="{y0 + h / 2 + 5:.1f}" text-anchor="middle" font-size="14" font-weight="700" fill="#fff">{num}</text>')
        if b is None:
            bw = width
            bx = min(max(x[a] - bw / 2, left + 4), right - bw)
            out.append(f'<rect x="{bx:.1f}" y="{y0:.1f}" width="{bw:.1f}" height="{h:.1f}" rx="7" fill="{c[1]}" stroke="{c[0]}" stroke-width="1.4"/>')
            for j, ln in enumerate(lines):
                out.append(f'<text x="{bx + bw / 2:.1f}" y="{y0 + 13 + LH * (j + 0.7):.1f}" text-anchor="middle" font-size="{FS}" fill="#1d2330">{E(ln)}</text>')
        else:
            ya = y0 + h - 8
            both = len(st) > 4 and st[4] == 'both'
            x1, x2 = x[a], x[b]
            d = 1 if x2 > x1 else -1
            out.append(f'<line x1="{x1 + d * 4:.1f}" y1="{ya:.1f}" x2="{x2 - d * 4:.1f}" y2="{ya:.1f}" stroke="{c[0]}" stroke-width="2.2" '
                       f'marker-end="url(#ah-{kind})"' + (f' marker-start="url(#ah-{kind})"' if both else '') + '/>')
            cx = (x1 + x2) / 2
            for j, ln in enumerate(lines):
                out.append(f'<text x="{cx:.1f}" y="{y0 + LH * (j + 0.8):.1f}" text-anchor="middle" font-size="{FS}" fill="#1d2330">{E(ln)}</text>')
    out.append('</svg>')
    return '\n'.join(out)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for i, f in FLOWS.items():
        (OUT / f'{i}.svg').write_text(draw(f))
        print(i, f['name'], len(f['lanes']), 'lanes,', len(f['steps']), 'steps ->', (OUT / f'{i}.svg').name)


if __name__ == '__main__':
    main()
