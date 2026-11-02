#!/usr/bin/env python3
"""Check the V16 classification records of the closest surveys and of the blockchain-based approaches.

Records: myliteraturereviewpaper/_src/V16/classify/surveys/<ID>.json and .../approaches/<ID>.json, in the forms set
out in myliteraturereviewpaper/_src/V16/classify/GUIDE.md. Every mark needs a reason and page citations.

Usage: scripts/.venv/bin/python scripts/review/check_v16_class.py surveys|approaches [ID ...]
"""
import json, pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
BASE = ROOT / 'myliteraturereviewpaper' / '_src' / 'V16' / 'classify'
MARKS = {'✓', '◐', '–'}
PAGES = re.compile(r'\bp\d')
FAMILIES = {'R', 'C', 'H', 'P', 'V'}
CLAIMS = {'CL1', 'CL2', 'CL3', 'CL4', 'AG1', 'AG2', 'AG3'}
VERIFIABLE = {'anyone', 'participants', 'trusted party', 'none'}
ANCHORS = {'single party', 'non-colluding servers', 'honest-majority committee or validators', 'hardware vendor',
           'proof soundness (trusted set-up)', 'proof soundness (transparent)', 'none'}
THREAT = {'evaluated', 'claimed', 'none'}
TIERS = {'IoT device', 'gateway', 'edge server', 'organisation', 'not stated'}


def need(rec, key, errs, pages=True):
    v = rec.get(key)
    if not isinstance(v, dict):
        errs.append(f'{key}: missing')
        return {}
    if pages and not PAGES.search(str(v.get('pages', ''))):
        errs.append(f'{key}: no page citation')
    return v


def survey(rec):
    errs = []
    st = need(rec, 'studies', errs, pages=False)
    if not st.get('n'):
        errs.append('studies.n: missing (write "not stated")')
    for k in ('devices', 'network', 'ledger', 'trust', 'onchain_law', 'evaluation', 'method'):
        v = need(rec, k, errs, pages=False)
        if v.get('mark') not in MARKS:
            errs.append(f'{k}.mark must be one of ✓ ◐ –')
        if not v.get('why'):
            errs.append(f'{k}.why: missing')
        if v.get('mark') in ('✓', '◐') and not PAGES.search(str(v.get('pages', ''))):
            errs.append(f'{k}: a ✓ or ◐ needs page citations')
    ch = need(rec, 'checks', errs, pages=False)
    fam = ch.get('families')
    if not isinstance(fam, list) or set(fam) - FAMILIES:
        errs.append('checks.families must be a list of R, C, H, P, V (may be empty)')
    elif fam and not PAGES.search(str(ch.get('pages', ''))):
        errs.append('checks: families need page citations')
    return errs


def approach(rec):
    errs = []
    for k in ('privacy', 'claim_checked', 'verifiable_by', 'trust_anchor', 'threats', 'client_tier', 'ledger_nodes',
              'cost_measured_on', 'evaluation'):
        need(rec, k, errs)
    if 'scheme' not in rec:
        errs.append('scheme: missing (use "" when the authors give no name)')
    cc = rec.get('claim_checked', {})
    if not isinstance(cc.get('codes'), list) or set(cc.get('codes', [])) - CLAIMS:
        errs.append('claim_checked.codes must be a list of CL1–CL4, AG1–AG3 (may be empty)')
    if rec.get('verifiable_by', {}).get('value') not in VERIFIABLE:
        errs.append(f'verifiable_by.value must be one of {sorted(VERIFIABLE)}')
    if rec.get('trust_anchor', {}).get('value') not in ANCHORS:
        errs.append(f'trust_anchor.value must be one of {sorted(ANCHORS)}')
    th = rec.get('threats', {})
    for t in 'PSCRDI':
        if th.get(t) not in THREAT:
            errs.append(f'threats.{t} must be evaluated, claimed or none')
    if rec.get('client_tier', {}).get('value') not in TIERS:
        errs.append(f'client_tier.value must be one of {sorted(TIERS)}')
    pv = rec.get('privacy', {})
    if pv.get('dp_epsilon_stated') not in (True, False, None):
        errs.append('privacy.dp_epsilon_stated must be true, false or null (no DP)')
    return errs


def main(kind, ids):
    folder = BASE / kind
    files = [folder / f'{i}.json' for i in ids] if ids else sorted(folder.glob('*.json'))
    bad = 0
    for f in files:
        if not f.exists():
            print(f'{f.stem} FAIL  no record')
            bad += 1
            continue
        try:
            rec = json.loads(f.read_text(encoding='utf-8'))
        except json.JSONDecodeError as e:
            print(f'{f.stem} FAIL  not valid JSON: {e}')
            bad += 1
            continue
        errs = (survey if kind == 'surveys' else approach)(rec)
        if rec.get('id') != f.stem:
            errs.append('id does not match the file name')
        print(f'{f.stem} {"FAIL" if errs else "PASS"}' + ''.join(f'\n    - {e}' for e in errs))
        bad += bool(errs)
    print(f'{len(files) - bad} pass, {bad} fail')
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1], sys.argv[2:]))
