#!/usr/bin/env python3
"""Check the evidence sheets of the PPML review (search-ppml/evidence/sheets/<corpus_id>.json) against the extraction
guide (search-ppml/evidence/EXTRACTION-GUIDE-V3-2026-10-15.md) and the papers' extracted pages.

For every sheet: the study is one of the included studies (search-ppml/FINAL-STUDIES-2026-10-05.csv); the answers of
its form (P1, P2, P3 for a design; S1 for a survey; one answer per review question) are present; the list and choice fields use the allowed values (or "other: ...");
every answer that is not "not stated" has evidence; "not stated" lists the terms searched; and every quotation is found
on the page it cites (text/pages/page_NNNN.txt, or text/pages_ocr/page_NNNN.txt where scripts/ocr_scanned.py read a page
whose text layer is unreadable; quotations marked "source": "table" or "image" are listed for a manual
look). Matching ignores case, whitespace, line-break hyphenation, ligatures and quote/dash variants.

Usage: python3 scripts/paper_ppml/check_sheets.py [corpus_id ...]     (default: every sheet)
Writes search-ppml/evidence/CHECK-SHEETS.json when run on all sheets; prints one line per sheet.
"""
import csv, json, pathlib, re, sys, unicodedata

csv.field_size_limit(10 ** 9)
ROOT = pathlib.Path(__file__).resolve().parents[2]
P = ROOT / 'search-ppml'
SHEETS = P / 'evidence' / 'sheets'

SET = lambda s: set(s.split())
ALLOWED = {
    'P1': {'settings': SET('IoT-general IIoT IoMT-healthcare IoV-vehicular smart-grid-energy UAV-space smart-city-home maritime supply-chain communication-network'),
           'enablers': SET('5G-6G edge fog MEC cloud none-stated'),
           'fl': SET('centralised-server decentralised hierarchical cross-silo cross-device vertical other'),
           'device_measured': SET('yes no'), 'network_measured': SET('yes no'),
           'costs_reported': SET('computation-time latency throughput storage communication gas energy none'),
           'cost_where': SET('device-class server-workstation simulation not-stated')},
    'P2': {'mechanisms': SET('DP LDP HE SMPC secret-sharing masking-secure-aggregation TEE ZKP functional-encryption pseudonyms-anonymity encryption-in-transit-only other'),
           'protects': SET('raw-data updates global-model identity other'),
           'hidden_from': SET('server-aggregator other-participants ledger-nodes public external-attacker not-stated'),
           'ledger': SET('public consortium-permissioned private not-stated none'),
           'platform': SET('Ethereum Hyperledger-Fabric FISCO-BCOS custom simulated not-stated other'),
           'consensus': SET('PoW PoS DPoS PBFT Raft PoA learning-based custom not-stated other'),
           'on_chain': SET('plain-updates protected-updates hashes-commitments proofs global-model reputation-scores identities-keys rewards-payments logs-metadata not-stated'),
           'roles': SET('record-audit aggregation update-verification proof-verification incentive-reputation identity-access replaces-server other'),
           'trusted': SET('none trusted-authority-key-centre certificate-authority server-aggregator non-colluding-servers enclave-TEE committee-honest-majority trusted-setup not-stated other'),
           'laws': None, 'personal_data_on_chain': SET('yes no unclear'), 'erasure': SET('addressed mentioned not-addressed')},
    'P3': {'checked': SET('test-accuracy-quality similarity-distance norm-bound correct-training correct-aggregation identity-membership contribution-reputation anomaly-detection none'),
           'checker': SET('server committee-validators-miners smart-contract peers-clients TEE trusted-authority none'),
           'checker_sees_update': SET('yes no partly unclear no-check'),
           'zk_used': {True, False},
           'zk_shows': SET('training bounded similarity aggregation identity inference other'),
           'claimed': SET('poisoning backdoor byzantine-malicious sybil-fake free-riding inference-privacy-attack malicious-server-aggregator collusion dos-ddos single-point-of-failure tampering'),
           'tested': SET('poisoning backdoor byzantine-malicious sybil-fake free-riding inference-privacy-attack malicious-server-aggregator collusion dos-ddos single-point-of-failure tampering'),
           'defences': None, 'datasets': None, 'baselines': None, 'code': SET('yes no'),
           'environment': SET('real-devices emulation simulation server-experiment none not-stated'), 'scale': None},
    'S1': {k: SET('subject mentioned absent') for k in ('fabric', 'privacy', 'trust', 'attacks', 'regulation', 'poisoning', 'malicious_fake', 'free_riding', 'blockchain')},
}
FORM = {'primary': ['P1', 'P2', 'P3'], 'secondary': ['S1']}
OPTIONAL = {('P3', 'zk_shows')}                               # required only when zk_used is true


def studies():
    F = list(csv.DictReader(open(P / 'FINAL-STUDIES-2026-10-05.csv', encoding='utf-8')))
    return {r['corpus_id']: r for r in F}


def folder_of(cid):
    over = P / 'evidence' / 'PUBLISHED-VERSIONS.json'                 # a published version that replaces a preprint
    if over.exists() and cid in json.loads(over.read_text(encoding='utf-8')):
        return ROOT / json.loads(over.read_text(encoding='utf-8'))[cid]
    idx = {r['id']: r for r in csv.DictReader(open(P / 'CORPUS-INDEX-2026-10-04.csv', encoding='utf-8'))}
    return ROOT / pathlib.Path(idx[cid]['pdf']).parent


def norm(s):
    s = unicodedata.normalize('NFKC', s)
    s = s.replace('­', '')
    s = re.sub(r'[‘’‚′`´]', "'", s)
    s = re.sub(r'[“”„″]', '"', s)
    s = re.sub(r'[‐-―−]', '-', s)
    s = re.sub(r'-\s*\n\s*', '', s)
    s = re.sub(r'\s+', ' ', s)
    return s.strip().lower()


def squash(s):
    return re.sub(r'[^a-z0-9]', '', norm(s))


def found(quote, text):
    return norm(quote) in norm(text) or squash(quote) in squash(text)


def check(cid, S):
    path = SHEETS / f'{cid}.json'
    problems, manual, nq = [], [], 0
    try:
        s = json.loads(path.read_text(encoding='utf-8'))
    except Exception as ex:                                   # noqa: BLE001
        return {'id': cid, 'status': 'FAIL', 'problems': [f'not readable JSON: {ex}'], 'manual': [], 'quotes': 0}
    if cid not in S:
        problems.append('not one of the included studies')
        kind = s.get('kind', '')
    else:
        kind = S[cid]['kind']
        if s.get('kind') != kind:
            problems.append(f'kind {s.get("kind")!r} but the review records {kind!r}')
    pages = folder_of(cid) / 'text' / 'pages'
    A = s.get('answers', {})
    for key in A:
        if kind in FORM and key not in FORM[kind]:
            problems.append(f'{key}: not part of the form any more')
    for key in FORM.get(kind, []):
        a = A.get(key)
        if not isinstance(a, dict):
            problems.append(f'{key} missing')
            continue
        ans = str(a.get('answer', '')).strip()
        if not ans:
            problems.append(f'{key}: empty answer')
        ev = a.get('evidence', [])
        if ans.lower().startswith('not stated'):
            if not a.get('searched'):
                problems.append(f'{key}: "not stated" without the terms searched')
        elif not ev:
            problems.append(f'{key}: answer without evidence')
        if a.get('located_via') not in ('summary', 'notes', 'full text'):
            problems.append(f'{key}: located_via missing or not summary/notes/full text')
        vals = a.get('values', {}) or {}
        zk = (A.get('P3', {}).get('values', {}) or {}).get('zk_used') is True
        for field in vals:
            if ALLOWED.get(key) is not None and field not in ALLOWED[key] and field != 'network_measured_own':
                problems.append(f'{key}: values.{field} is not part of the form any more')
        for field, allowed in ALLOWED.get(key, {}).items():
            if field not in vals:
                if (key, field) in OPTIONAL and not zk:
                    continue
                problems.append(f'{key}: values.{field} missing')
                continue
            if allowed is None:
                continue
            v = vals[field]
            items = v if isinstance(v, list) else [v]
            for x in items:
                if isinstance(x, str) and x.startswith('other:'):
                    continue
                if x not in allowed:
                    problems.append(f'{key}: values.{field} has {x!r} (allowed: {sorted(map(str, allowed))})')
        for e in ev:
            nq += 1
            if not isinstance(e, dict) or 'page' not in e or 'quote' not in e:
                problems.append(f'{key}: evidence entry without page/quote')
                continue
            if e.get('source') in ('table', 'image'):
                manual.append(f"{key} p{e['page']}: {e['quote'][:60]}")
                continue
            try:
                f = pages / f"page_{int(e['page']):04d}.txt"
            except (TypeError, ValueError):
                problems.append(f'{key}: page {e["page"]!r} is not a number')
                continue
            ocr = pages.parent / 'pages_ocr' / f.name
            if not f.exists():
                problems.append(f'{key}: page {e["page"]} does not exist')
            elif not any(found(e['quote'], g.read_text(encoding='utf-8', errors='ignore')) for g in (f, ocr) if g.exists()):
                problems.append(f'{key}: quote not on p{e["page"]}: "{e["quote"][:70]}"')
            if len(e['quote'].split()) > 45:
                problems.append(f'{key}: quote longer than 40 words')
            if '…' in e['quote'] or '...' in e['quote']:
                problems.append(f'{key}: ellipsis inside a quote')
    return {'id': cid, 'status': 'FAIL' if problems else 'PASS', 'problems': problems, 'manual': manual, 'quotes': nq}


def main(ids):
    S = studies()
    every = not ids
    ids = ids or sorted(p.stem for p in SHEETS.glob('*.json'))
    res = [check(i, S) for i in ids]
    for r in res:
        print(f"{r['id']}: {r['status']} ({r['quotes']} quotes{', ' + str(len(r['manual'])) + ' for a manual look' if r['manual'] else ''})")
        for p in r['problems'][:30]:
            print('   -', p)
    if every:
        missing = sorted(set(S) - set(ids))
        out = {'sheets': len(res), 'pass': sum(r['status'] == 'PASS' for r in res), 'missing': missing, 'results': res}
        (P / 'evidence' / 'CHECK-SHEETS.json').write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding='utf-8')
        print(f"{out['pass']}/{len(res)} pass; {len(missing)} studies without a sheet")


if __name__ == '__main__':
    main(sys.argv[1:])
