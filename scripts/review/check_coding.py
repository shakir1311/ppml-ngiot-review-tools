#!/usr/bin/env python3
"""Check the synthesis records (myliteraturereviewpaper/_src/V14/coding/<ID>.json) against the coding guide:
keys, types and vocabularies. Prints one line per problem and a summary; exit status 1 if any record fails.

Usage: scripts/.venv/bin/python scripts/review/check_coding.py [ID ...]
"""
import json, pathlib, sys, re

ROOT = pathlib.Path(__file__).resolve().parents[2]
SRC = ROOT / 'myliteraturereviewpaper' / '_src' / 'V14'

SETTING = {'IoT', 'IIoT', 'healthcare_IoMT', 'vehicular_IoV', 'smart_grid', 'smart_city', 'maritime', '5G_B5G_6G',
           'edge_fog', 'cloud', 'wireless_protocols', 'generic'}
LEARNING = {'FL', 'hierarchical_FL', 'DFL', 'swarm', 'split', 'centralised_ML', 'inference_only', 'edge_intelligence',
            'unlearning', 'lifelong', 'none'}
PRIVACY = {'DP', 'LDP', 'HE', 'FHE', 'SMPC', 'secret_sharing', 'secure_aggregation', 'TEE', 'ZKP',
           'perturbation_obfuscation', 'GAN_synthetic', 'anonymisation', 'split_learning', 'unlearning', 'none'}
THREATS = {'data_poisoning', 'model_poisoning', 'backdoor', 'byzantine', 'sybil_fake_nodes', 'free_riding', 'dos_ddos',
           'jamming', 'membership_inference', 'property_attribute_inference', 'reconstruction_inversion',
           'eavesdropping_mitm', 'collusion', 'malicious_or_curious_server', 'tampering', 'single_point_of_failure',
           'replay_impersonation', 'device_protocol_vulnerabilities', 'malware_botnet'}
ASSUMPTIONS = {'honest_but_curious_server', 'trusted_third_party_or_key_authority', 'non_colluding_parties',
               'honest_majority', 'iid_data', 'reliable_network_no_dropouts', 'sufficient_device_resources',
               'secure_channels'}
CHALLENGES = {f'C{n:02d}' for n in range(1, 19)} | {'C99'}
THEMES = {'T1', 'T2', 'T3', 'T4', 'T5', 'T6'}
COVERS = {'iot_edge', 'distributed_learning', 'privacy_mechanisms', 'blockchain', 'attacks_defences', 'evaluation',
          'regulation'}


def vocab(values, allowed, field, pid, errs):
    if not isinstance(values, list):
        errs.append(f'{pid}: {field} is not a list')
        return
    for v in values:
        if v not in allowed and not (isinstance(v, str) and v.startswith('other:')):
            errs.append(f'{pid}: {field} has unknown code {v!r}')


def check(pid, rec, errs, warns):
    for k in ('id', 'kind', 'theme', 'description', 'key_result', 'setting', 'learning', 'privacy_mechanisms', 'ledger',
              'threats', 'defences', 'evaluation', 'survey', 'rigour', 'assumptions', 'open_issues', 'future_directions'):
        if k not in rec:
            errs.append(f'{pid}: missing {k}')
    if rec.get('id') != pid:
        errs.append(f'{pid}: id field is {rec.get("id")!r}')
    if rec.get('kind') not in ('primary', 'secondary'):
        errs.append(f'{pid}: kind {rec.get("kind")!r}')
    if rec.get('theme') not in THEMES:
        errs.append(f'{pid}: theme {rec.get("theme")!r}')
    d = rec.get('description', '')
    if len(d.split()) > 45:
        warns.append(f'{pid}: description has {len(d.split())} words')
    if len(rec.get('key_result', '').split()) > 38:
        warns.append(f'{pid}: key_result has {len(rec["key_result"].split())} words')
    vocab(rec.get('setting', []), SETTING, 'setting', pid, errs)
    vocab(rec.get('learning', []), LEARNING, 'learning', pid, errs)
    vocab(rec.get('privacy_mechanisms', []), PRIVACY, 'privacy_mechanisms', pid, errs)
    vocab(rec.get('threats', []), THREATS, 'threats', pid, errs)
    led = rec.get('ledger') or {}
    if not isinstance(led.get('used'), bool):
        errs.append(f'{pid}: ledger.used not boolean')
    ev = rec.get('evaluation') or {}
    if rec.get('kind') == 'primary':
        if ev.get('real_device_cost') not in (True, False, None):
            errs.append(f'{pid}: evaluation.real_device_cost')
        rg = rec.get('rigour')
        if not isinstance(rg, dict):
            errs.append(f'{pid}: rigour missing for a primary study')
        else:
            for k in ('spread', 'significance_test', 'code_available', 'data_public'):
                if not isinstance(rg.get(k), bool) and not (k == 'data_public' and rg.get(k) is None):
                    errs.append(f'{pid}: rigour.{k} not boolean')
    else:
        sv = rec.get('survey')
        if not isinstance(sv, dict):
            errs.append(f'{pid}: survey missing for a secondary study')
        else:
            if sv.get('protocol') not in ('systematic', 'partial', 'none'):
                errs.append(f'{pid}: survey.protocol {sv.get("protocol")!r}')
            cv = sv.get('covers') or {}
            if set(cv) != COVERS or not all(isinstance(v, bool) for v in cv.values()):
                errs.append(f'{pid}: survey.covers keys/values')
    for a in rec.get('assumptions', []):
        c = a.get('code', '') if isinstance(a, dict) else ''
        if c not in ASSUMPTIONS and not c.startswith('other:'):
            errs.append(f'{pid}: assumption code {c!r}')
    for fld in ('open_issues', 'future_directions'):
        items = rec.get(fld, [])
        if len(items) > 8:
            warns.append(f'{pid}: {fld} has {len(items)} items')
        for it in items:
            if not isinstance(it, dict) or it.get('code') not in CHALLENGES:
                errs.append(f'{pid}: {fld} code {it.get("code") if isinstance(it, dict) else it!r}')
            elif not re.search(r'p\d', it.get('pages', '')):
                errs.append(f'{pid}: {fld} item without page')


def main(ids):
    files = sorted((SRC / 'coding').glob('*.json'))
    if ids:
        files = [SRC / 'coding' / f'{i}.json' for i in ids]
    errs, warns = [], []
    for f in files:
        pid = f.stem
        try:
            rec = json.loads(f.read_text(encoding='utf-8'))
        except Exception as e:
            errs.append(f'{pid}: invalid JSON ({e})')
            continue
        check(pid, rec, errs, warns)
    for e in errs:
        print('ERROR', e)
    for w in warns:
        print('warn ', w)
    print(f'{len(files)} records, {len(errs)} errors, {len(warns)} warnings')
    return 1 if errs else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
