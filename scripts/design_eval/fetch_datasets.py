#!/usr/bin/env python3
"""Puts each runnable design's datasets into its datasets/ folder, from a catalogue of where each dataset comes from and on what terms, and lists what needs the author.

CATALOGUE holds, for every dataset a design uses (the names of the evidence sheet's P3 `datasets`), its source, terms of use,
size and how it is obtained: `in_repo` (a file inside the design's cloned code, cloned into datasets/ as a copy-on-write APFS
copy: real files that take no extra space), `clone_from` (files already downloaded for the workspace's experiments, copied
the same way), `url` (downloaded here, with its SHA-256), or `manual` (a form, a sign-in or a size over about 10 GB: the
entry goes to design-evaluation/DOWNLOADS.md for the author). Public datasets used by several designs (SHARED_SETS) are downloaded once into design-evaluation/_datasets/ and cloned the same
way into each design. Writes datasets/DATASETS.json and datasets/SHA256SUMS.txt in
each design's folder. Only the designs given are touched (the author, 10 November 2026: datasets only for designs that can
be run or built).

Usage: design-evaluation/.venv/bin/python scripts/design_eval/fetch_datasets.py <id> [<id> ...]
"""
import hashlib, json, pathlib, subprocess, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import EVAL, ROOT, design, save_json, now   # noqa: E402

LIMIT_BYTES = 10 * 1024 ** 3
SHARED = EVAL / '_datasets'
# public datasets used by several designs: downloaded once into _datasets/<key>/, cloned (copy-on-write) into each design
U = 'https://archive.ics.uci.edu/static/public/'
SHARED_SETS = {
    'MNIST': {'files': [f'https://ossci-datasets.s3.amazonaws.com/mnist/{f}' for f in (
                 'train-images-idx3-ubyte.gz', 'train-labels-idx1-ubyte.gz', 't10k-images-idx3-ubyte.gz', 't10k-labels-idx1-ubyte.gz')],
              'source': 'LeCun, Cortes and Burges; the PyTorch mirror of http://yann.lecun.com/exdb/mnist/', 'terms': 'CC BY-SA 3.0', 'size': '11 MB'},
    'Fashion-MNIST': {'files': [f'http://fashion-mnist.s3-website.eu-central-1.amazonaws.com/{f}' for f in (
                 'train-images-idx3-ubyte.gz', 'train-labels-idx1-ubyte.gz', 't10k-images-idx3-ubyte.gz', 't10k-labels-idx1-ubyte.gz')],
              'source': 'Zalando Research, https://github.com/zalandoresearch/fashion-mnist', 'terms': 'MIT', 'size': '30 MB'},
    'CIFAR-10': {'files': ['https://www.cs.toronto.edu/~kriz/cifar-10-python.tar.gz'],
                 'source': 'Krizhevsky (2009), https://www.cs.toronto.edu/~kriz/cifar.html', 'terms': 'no licence stated; cite the technical report', 'size': '163 MB'},
    'EMNIST': {'files': ['https://biometrics.nist.gov/cs_links/EMNIST/gzip.zip'],
               'source': 'NIST, Cohen et al. (2017), https://www.nist.gov/itl/products-and-services/emnist-dataset', 'terms': 'NIST public data; cite the paper', 'size': '536 MB'},
    'SVHN': {'files': [f'http://ufldl.stanford.edu/housenumbers/{f}' for f in ('train_32x32.mat', 'test_32x32.mat')],
             'source': 'Netzer et al. (2011), http://ufldl.stanford.edu/housenumbers/', 'terms': 'non-commercial use only', 'size': '235 MB'},
    'OCTMNIST': {'files': ['https://zenodo.org/records/10519652/files/octmnist.npz'],
                 'source': 'MedMNIST v2 (Yang et al. 2023), Zenodo record 10519652', 'terms': 'CC BY 4.0', 'size': '52 MB'},
    'TissueMNIST': {'files': ['https://zenodo.org/records/10519652/files/tissuemnist.npz'],
                    'source': 'MedMNIST v2 (Yang et al. 2023), Zenodo record 10519652', 'terms': 'CC BY 4.0', 'size': '119 MB'},
    'California-Housing': {'files': [('https://ndownloader.figshare.com/files/5976036', 'cal_housing.tgz')],
                           'source': 'Pace and Barry (1997), StatLib; the scikit-learn copy on figshare', 'terms': 'public (StatLib)', 'size': '0.4 MB'},
    '20-Newsgroups': {'files': ['http://qwone.com/~jason/20Newsgroups/20news-bydate.tar.gz'],
                      'source': 'Lang (1995), http://qwone.com/~jason/20Newsgroups/', 'terms': 'no licence stated; widely used for research', 'size': '14 MB'},
    'Reuters-21578': {'files': [(U + '137/reuters+21578+text+categorization+collection.zip', 'reuters21578.zip')],
                      'source': 'UCI Machine Learning Repository, dataset 137', 'terms': 'CC BY 4.0', 'size': '8 MB'},
    'UCI-Daily-and-Sports-Activities': {'files': [(U + '256/daily+and+sports+activities.zip', 'daily_and_sports_activities.zip')],
                                        'source': 'UCI Machine Learning Repository, dataset 256 (Altun and Barshan)', 'terms': 'CC BY 4.0', 'size': '164 MB'},
    'A123-DST-US06-FUDS': {'files': [f'https://web.calce.umd.edu/batteries/data/A123_DST-US06-FUDS-{t}.zip' for t in ('N10', '0', '10', '20', '25', '30', '40', '50')],
                           'source': 'CALCE battery group, University of Maryland, https://calce.umd.edu/battery-data (A123, drive cycles DST, US06, FUDS, eight temperatures)',
                           'terms': 'free for research; cite the CALCE data', 'size': 'about 300 MB'},
}
ALIASES = {'MNIST': 'MNIST', 'Fashion MNIST': 'Fashion-MNIST', 'Fashion-MNIST': 'Fashion-MNIST', 'FashionMNIST': 'Fashion-MNIST',
           'FMNIST': 'Fashion-MNIST', 'CIFAR-10': 'CIFAR-10', 'CIFAR10': 'CIFAR-10', 'EMNIST': 'EMNIST', 'SVHN': 'SVHN',
           'OCTMNIST': 'OCTMNIST', 'TissueMNIST': 'TissueMNIST', 'California Housing': 'California-Housing',
           '20 Newsgroups': '20-Newsgroups', 'Reuters': 'Reuters-21578', 'UCI Daily and Sports Activities': 'UCI-Daily-and-Sports-Activities',
           'A123 battery dataset (DST, FUDS, US06)': 'A123-DST-US06-FUDS'}
# datasets the author has to fetch or identify: the reason, and where to start
MANUAL = {
    'house price data set (HPD)': 'the paper names no source; to be identified by the author',
    'loan data set (LD)': 'the paper names no source; to be identified by the author',
    'Great Lakes Tracks AIS': 'NOAA AIS vessel tracks for the Great Lakes; the first author\'s repository (hujunxu/HHB-FL) points to NOAA InPort item 55360, https://www.fisheries.noaa.gov/inport/item/55360; the subset (vessels, period) is not stated',
    'Ocean-of-Things': 'DARPA Ocean of Things float data; access route to be found',
    'Edge-IIoTset': 'Ferrag et al. 2022; Kaggle or IEEE DataPort, both need a sign-in',
    'DelDOT': 'Delaware Department of Transportation traffic data; the series used is not stated',
    'METR-LA': 'Li et al. (DCRNN, 2018); the usual copy is on Google Drive, linked from https://github.com/liyaguang/DCRNN',
    'PeMSD4': 'Caltrans PeMS District 4 as prepared by ASTGCN (Guo et al. 2019); copies on Google Drive or Baidu, linked from the ASTGCN repositories',
    'Car-Hacking': 'HCRL Car-Hacking dataset (Song et al. 2020), https://ocslab.hksecurity.net/Datasets/car-hacking-dataset; a request form precedes the download',
    'COVID-19-CT': 'probably the UCSD-AI4H COVID-CT set (746 CT images); the repository is no longer on GitHub (Wayback copy of 2023-05-10); the paper does not name its source',
    'unnamed: real road images recorded around Rancho Palos Verdes and San Pedro, California (about 63,000 images)': 'the paper names no source',
}
CATALOGUE = {
    'unnamed: hourly electricity consumption of 321 sites (2012-2014)': {
        'name': 'electricity (321 clients, hourly, 2012-2014)', 'method': 'in_repo',
        'path': 'code/CaixiangFan__zkpet/dataset/electricity.csv',
        'source': 'shipped in the design\'s repository (dataset/electricity.csv); the electricity set of the long-term forecasting '
                  'benchmarks, derived from UCI ElectricityLoadDiagrams20112014',
        'terms': 'UCI dataset: CC BY 4.0', 'size': '91 MB'},
    'CICIoV2024': {
        'name': 'CICIoV2024 (decimal)', 'method': 'clone_from', 'path': 'experiments/fl-bc-ids/data/raw/CICIoV2024',
        'source': 'Canadian Institute for Cybersecurity, https://www.unb.ca/cic/datasets/iov-dataset-2024.html (files from '
                  'https://cicresearch.ca/IOTDataset/CICIoV2024/, decimal folder), downloaded by the author on 19 October 2026',
        'terms': 'CIC terms: free for research, cite the dataset paper; a registration form precedes the download', 'size': '66 MB'},
    'CSE-CIC-IDS2018': {
        'name': 'CSE-CIC-IDS2018 (improved, DistriNet 2022)', 'method': 'url',
        'url': 'https://intrusion-detection.distrinet-research.be/CNS2022/Datasets/CSECICIDS2018_improved.zip',
        'expected_bytes': 9.7e9,
        'source': 'the improved CSE-CIC-IDS2018 of Liu, Engelen, Lynar, Essam and Joosen (IEEE CNS 2022), which the design\'s own '
                  'metadata pins (63,195,145 rows, 85 features); original distribution https://www.unb.ca/cic/datasets/ids-2018.html',
        'terms': 'no terms stated on the DistriNet page; the original CIC terms ask for a citation', 'size': '9.7 GB (zip)'},
}


def sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def shared(k, target_root, sums):
    """A dataset of SHARED_SETS: downloaded once into _datasets/<k>/, then cloned into the design's datasets/<k>/."""
    c = SHARED_SETS[k]
    cache = SHARED / k
    cache.mkdir(parents=True, exist_ok=True)
    for f in c['files']:
        url, name = f if isinstance(f, tuple) else (f, f.rsplit('/', 1)[-1])
        dest = cache / name
        if not dest.exists():
            subprocess.run(['curl', '-sL', '--fail', '--retry', '3', '-o', str(dest) + '.part', url], check=True)
            (cache / (name + '.part')).rename(dest)
    save_json(cache / 'SOURCE.json', {'dataset': k, 'files': [f if isinstance(f, str) else f[0] for f in c['files']],
                                      'source': c['source'], 'terms': c['terms'], 'downloaded': now()[:10]})
    target = target_root / k
    if not target.exists():
        subprocess.run(['cp', '-c', '-R', str(cache), str(target)], check=True)
    for p in sorted(target.rglob('*')):
        if p.is_file() and p.name not in ('SHA256SUMS.txt', 'SOURCE.json'):
            sums.append(f'{sha256(p)}  {p.relative_to(target_root)}')
    return {'name': k, 'source': c['source'], 'terms': c['terms'], 'size': c['size'],
            'status': f'here: datasets/{k}/ (copy-on-write copy of design-evaluation/_datasets/{k}/)'}


def fetch(design_id):
    d = design(design_id)
    out, sums = [], []
    target_root = d['folder'] / 'datasets'
    for key in d['sheet_p3'].get('datasets') or []:
        if key in ALIASES:
            out.append(shared(ALIASES[key], target_root, sums))
            continue
        if key in MANUAL:
            out.append({'name': key, 'source': MANUAL[key], 'status': 'needs the author: listed in DOWNLOADS.md'})
            continue
        c = CATALOGUE.get(key)
        if not c:
            out.append({'name': key, 'status': 'not in the catalogue yet'})
            continue
        row = {k: c[k] for k in ('name', 'source', 'terms', 'size')}
        dest = target_root / c['name'].split(' (')[0].replace(' ', '-')
        if c['method'] in ('in_repo', 'clone_from'):
            src = (d['folder'] / c['path']) if c['method'] == 'in_repo' else (ROOT / c['path'])
            if not dest.exists():
                dest.mkdir(parents=True)
                subprocess.run(['cp', '-c', '-R'] + [str(p) for p in ([src] if src.is_file() else sorted(src.iterdir()))] + [str(dest)], check=True)
            row['status'] = f"here: datasets/{dest.name}/ (copy-on-write copy of {c['path']})"
        elif c['method'] == 'url':
            if c.get('expected_bytes', 0) > LIMIT_BYTES:
                row['status'] = 'over 10 GB: listed in DOWNLOADS.md for the author'
            else:
                dest.mkdir(parents=True, exist_ok=True)
                f = dest / c['url'].rsplit('/', 1)[-1]
                if not f.exists():
                    subprocess.run(['curl', '-L', '--fail', '--retry', '3', '-C', '-', '-o', str(f), c['url']], check=True)
                row['status'] = f'here: datasets/{dest.name}/{f.name} (downloaded {now()[:10]})'
                row['url'] = c['url']
        else:
            row['status'] = 'needs the author: listed in DOWNLOADS.md'
        if dest.exists():
            for p in sorted(dest.rglob('*')):
                if p.is_file() and p.name != 'SHA256SUMS.txt':
                    sums.append(f'{sha256(p)}  {p.relative_to(target_root)}')
        out.append(row)
    save_json(target_root / 'DATASETS.json', {'about': 'The datasets of the design, where each comes from, its terms and what is here.',
                                              'made': now(), 'datasets': out})
    (target_root / 'SHA256SUMS.txt').write_text('\n'.join(sums) + ('\n' if sums else ''))
    return out


if __name__ == '__main__':
    for i in sys.argv[1:]:
        for r in fetch(i):
            print(f"{i:6} {r['name'][:50]:50} {r['status']}")
