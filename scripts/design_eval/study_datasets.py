#!/usr/bin/env python3
"""Lists every dataset the 54 designs of the Phase 2 study use, under one name each, with its kind and the designs that use it.

Names come from the cards (study_cards.py): the evidence sheets' P3 datasets for the review's designs and the study readers'
dataset records for the new designs and the six carried forward. Spellings of one dataset are merged by SAME (e.g. CIFAR10 and
CIFAR-10); KIND sorts each dataset into a family. Unnamed or unstated datasets are kept, under their own description. Writes
design-evaluation/study/datasets/DATASETS.csv and DATASETS.json and prints the counts. The credibility of the six's datasets is
judged in datasets/CREDIBILITY.json (by hand, with sources), which this script checks covers every dataset the six use.

Usage: python3 scripts/design_eval/study_datasets.py
"""
import collections, csv, json, pathlib, re, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import EVAL, now, save_json   # noqa: E402

OUT = EVAL / 'study' / 'datasets'
SAME = {'CIFAR10': 'CIFAR-10', 'Fashion MNIST': 'Fashion-MNIST', 'FashionMNIST': 'Fashion-MNIST', 'FMNIST': 'Fashion-MNIST',
        'CIC-IDS2018': 'CSE-CIC-IDS2018', 'IoT-23 (named in Table 3 and Fig. 1; its use is not stated)': 'IoT-23',
        'UCI Daily and Sports Activities': 'Daily and Sports Activities (UCI)', 'Daily and Sports Activities': 'Daily and Sports Activities (UCI)',
        'UCI Daily and Sports Activities (one sensor unit, nine features, six merged classes)': 'Daily and Sports Activities (UCI)',
        'Electricity consumption (hourly load of 321 clients)': 'Electricity load, 321 clients hourly (from UCI ElectricityLoadDiagrams20112014)',
        'unnamed: hourly electricity consumption of 321 sites (2012-2014)': 'Electricity load, 321 clients hourly (from UCI ElectricityLoadDiagrams20112014)',
        'not named; a dataset of 262,144 records with 1024 features each': 'Unnamed: 262,144 records x 1,024 features (code draws random data)',
        'data set of 262,144 records with 1024 features each (name and source not stated; the released code samples random dummy data)':
            'Unnamed: 262,144 records x 1,024 features (code draws random data)',
        'N-BaIoT (named in Table 3 and Fig. 1; its use is not stated)': 'N-BaIoT',
        'none (synthetic scalar inputs)': 'Synthetic scalar inputs (no dataset)',
        'Federated-MNIST': 'Federated EMNIST digits (per writer, 3,383 writers)',
        'Federated-MNIST (FMN), digit classification (analysis)': 'Federated EMNIST digits (per writer, 3,383 writers)',
        'CIFAR-10 (analysis)': 'CIFAR-10', 'MNIST (end-to-end)': 'MNIST', 'Shakespeare (LEAF)': 'Shakespeare',
        'ARDIS sevens (tail attack data for FMN)': 'ARDIS sevens (edge-case backdoor images)',
        'ARDIS sevens (tail attack images)': 'ARDIS sevens (edge-case backdoor images)',
        'Southwest airline images (tail attack data for C10)': 'Southwest airline images (edge-case backdoor images)',
        'Southwest airline images (tail attack images)': 'Southwest airline images (edge-case backdoor images)',
        # a reader's summary line whose datasets are also listed one by one: not a dataset of its own
        'End-to-end tasks: MNIST (19k-parameter CNN), CIFAR-10 S (LeNet5), CIFAR-10 L (ResNet-20), Shakespeare (LSTM)': None}
KIND = {
    'image': 'MNIST Fashion-MNIST EMNIST FEMNIST CIFAR-10 CIFAR-100 SVHN BelgiumTS OCTMNIST TissueMNIST CheXpert COVID-19-CT '
             'Federated-EMNIST-digits-(per-writer,-3,383-writers) ARDIS-sevens-(edge-case-backdoor-images) '
             'Southwest-airline-images-(edge-case-backdoor-images)',
    'network intrusion and IoT security': 'CICIDS2017 CSE-CIC-IDS2018 CICIoV2024 CICIoMT2024 Car-Hacking Edge-IIoTset IoT-23 N-BaIoT NSL-KDD '
                                          'KDD-CUP-1999 TON_IoT CyberIO MedIoT',
    'threat intelligence': 'MISP-Galaxy MISP-threat-feeds CIRCL-MISP-feed ThreatFox OpenIOC DARPA-E3-(Trace,-Theia,-Cadets)',
    'sensor and time series': 'air-quality gas-sensor-array-drift GasEmissions METR-LA PeMSD4 PTB-XL seismic-bumps indoor-user-movement-prediction-from-RSS '
                              'A123-battery-dataset-(DST,-FUDS,-US06) PEEMS-horizontal-displacement-monitoring-data Ocean-of-Things Great-Lakes-Tracks-AIS '
                              'DelDOT Daily-and-Sports-Activities-(UCI) Electricity-load,-321-clients-hourly-(from-UCI-ElectricityLoadDiagrams20112014)',
    'tabular': 'Adult California-Housing house-price-data-set-(HPD) loan-data-set-(LD) image-segmentation',
    'text and recommendation': '20-Newsgroups Reuters Shakespeare Reasoner',
    'records and logs': 'FDA-DSCSA-traceability-records MSU-RFID-Pilot-Study IoT-Enabled-Pharmaceutical-Supply-Chain-Dataset-(Kaggle)',
}
KIND_OF = {n.replace('-', ' ').lower(): k for k, names in KIND.items() for n in names.split()}


def kind(name):
    key = name.replace('-', ' ').lower()
    if key in KIND_OF:
        return KIND_OF[key]
    if re.match(r'(unnamed|not named|none|synthetic)', name, re.I):
        return 'unnamed or synthetic'
    return 'other'


def main():
    cards = json.load(open(EVAL / 'study' / 'CARDS.json'))['cards']
    use = collections.defaultdict(list)
    for c in cards:
        names = set(c.get('datasets') or []) | {d.get('name', '') for d in c.get('datasets_detail', []) if d.get('name')}
        for n in {SAME.get(x, x) for x in names} - {None}:
            use[n].append(c)
    rows = []
    for n, cs in sorted(use.items(), key=lambda x: (-len(x[1]), x[0].lower())):
        six = [c['name'] for c in cs if c['status'] == 'carried forward']
        rows.append({'dataset': n, 'kind': kind(n), 'designs': len(cs), 'used_by_six': ', '.join(sorted(six)),
                     'used_by': '; '.join(f"{c['name'] or c['id']} ({c['id']})" for c in sorted(cs, key=lambda c: c['id']))})
    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / 'DATASETS.csv', 'w', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    save_json(OUT / 'DATASETS.json', {'about': 'Every dataset of the 54 designs, merged spellings; scripts/design_eval/study_datasets.py',
                                      'made': now(), 'datasets': rows})
    kinds = collections.Counter(r['kind'] for r in rows)
    print(len(rows), 'datasets;', dict(kinds))
    six_sets = sorted({r['dataset'] for r in rows if r['used_by_six']})
    print('used by the six:', six_sets)
    cred = OUT / 'CREDIBILITY.json'
    if cred.exists():
        judged = {d['dataset'] for d in json.load(open(cred))['datasets']}
        missing = [d for d in six_sets if d not in judged]
        print('credibility judged for every dataset of the six:', not missing, missing or '')


if __name__ == '__main__':
    main()
