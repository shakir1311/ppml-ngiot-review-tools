#!/usr/bin/env python3
"""Counts, on the Mac and without showing any text, the signs that a design's paper describes its algorithm well enough to code it, and names the pages a reader should read.

Reads the extracted pages of the paper (`text/pages/page_NNNN.txt`) and writes `algorithm/01-triage.json` in the design's
folder: for each kind of sign (algorithm blocks and pseudo-code, numbered equations, training parameters, model architecture,
cryptographic construction, ledger platform, software named, hardware, data split, attack set-up) the number of hits and
their pages; the pages whose section headings are of the method, the construction, the implementation or the experiments
(found by keyword, the headings themselves not kept); and the pages a reader should read first. Pages after the reference
list starts are left out. Nothing of the paper's text is written or printed.

Usage: design-evaluation/.venv/bin/python scripts/design_eval/algorithm_triage.py [<id> ...]
"""
import collections, pathlib, re, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import ROOT, load_designs, page_texts, save_json, now   # noqa: E402

SIGNS = {
    'algorithm_blocks': r'^\s*Algorithm\s+\d+\b|^\s*(Require|Ensure|Input|Output)\s*:',
    'pseudo_code_lines': r'^\s*\d{1,2}\s*[:.]\s+(for|while|if|end|return|send|compute|let|set|update|initiali[sz]e|select|upload|broadcast|receive|repeat|until)\b|^\s*(end\s+for|end\s+while|end\s+if|end\s+procedure|end\s+function|procedure|function)\b',
    'numbered_equations': r'\(\s*\d{1,3}\s*\)\s*$',
    'training_parameters': r'\b(learning\s+rate|epochs?|batch\s+size|communication\s+rounds?|global\s+rounds?|local\s+(iterations|epochs|steps)|momentum|weight\s+decay|optimi[sz]er|SGD|Adam)\b',
    'privacy_parameters': r'(privacy\s+budget|ε\s*=|epsilon\s*=|δ\s*=|delta\s*=|clipping|noise\s+(scale|multiplier)|sensitivity|key\s+(size|length)|\d{3,4}[- ]bit|security\s+parameter|λ\s*=)',
    'model_architecture': r'\b(convolution(al)?|conv\d?\b|fully[- ]connected|hidden\s+(layer|units)|neurons|kernel\s+size|ResNet|LeNet|VGG|AlexNet|LSTM|GRU|MLP|transformer|ViT|BERT|XGBoost|random\s+forest|SVM|logistic\s+regression)\b',
    'crypto_construction': r'\b(Paillier|ElGamal|CKKS|BFV|BGV|DGHV|Shamir|secret[- ]shar\w*|homomorphic|Pedersen|commitment|Groth16|PLONK|zk-?SNARK|Bulletproofs?|STARK|circuit|elliptic\s+curve|bilinear|pairing|BLS|ECDSA|Schnorr|PRG|PRF|garbled|oblivious|masking|TEE|SGX|enclave)\b',
    'ledger_platform': r'\b(Hyperledger|Fabric|Ethereum|Solidity|smart\s+contracts?|Ganache|Truffle|Hardhat|Geth|Quorum|FISCO|chaincode|PBFT|Raft|proof\s+of\s+(work|stake|authority)|PoW|PoS|PoA|DAG|IOTA|consensus)\b',
    'software_named': r'\b(Python|PyTorch|TensorFlow|Keras|scikit-learn|sklearn|NumPy|Golang|Java|C\+\+|Rust|circom|snarkjs|ZoKrates|libsnark|arkworks|gnark|EZKL|Microsoft\s+SEAL|TenSEAL|OpenFHE|PySyft|Flower|FATE|charm|MIRACL|JPBC|PBC\s+library|python-paillier|phe\b|OpenSSL|Docker|Web3)\b',
    'hardware': r'\b(\d+(\.\d+)?\s*GHz|\d+\s*GB\s+(of\s+)?(RAM|memory)|GPU|CPU|Raspberry\s+Pi|Jetson|NVIDIA|Intel|AMD|Apple\s+M\d)\b',
    'data_split': r'\b(non-?IID|IID|Dirichlet|partition(ed|ing)?|train(ing)?\s*/\s*test|training\s+set|test\s+set|split)\b',
    'attack_setup': r'\b(malicious\s+(clients?|nodes?|participants?|workers?)|attackers?|poison\w*|Byzantine|label[- ]flip\w*|backdoor|sign[- ]flip\w*|Gaussian\s+attack|free[- ]rid\w*|Sybil|fraction\s+of\s+(malicious|attackers))\b',
}
SECTION_KINDS = {
    'method': r'(proposed|scheme|method|methodology|system\s+model|framework|architecture|design|construction|protocol|overview|workflow|model\b)',
    'algorithm': r'(algorithm|procedure|training|aggregation|verification|proof|consensus|smart\s+contract)',
    'threat_model': r'(threat|adversar|attack\s+model|security\s+model|security\s+analysis|security\s+proof)',
    'implementation': r'(implementation|prototype|deployment|setup|set-up|settings|environment|configuration)',
    'experiments': r'(experiment|evaluation|performance|simulation|results|analysis)',
}
HEADING = re.compile(r'^\s*(?:[IVX]{1,5}\.|\d{1,2}(?:\.\d{1,2}){0,2}\.?|[A-H]\.)\s+([A-Z][A-Za-z \-:,/&]{3,70})\s*$')
REF_HEAD = re.compile(r'(?im)^\s*(references|bibliography)\s*$')


def triage(d):
    pages = page_texts(d['paper_folder'])
    hits = {k: collections.Counter() for k in SIGNS}
    sections = collections.defaultdict(set)
    current = None
    body_pages = []
    for n, p in pages:
        text = p.read_text(errors='replace')
        ref = REF_HEAD.search(text)
        if ref:
            text = text[:ref.start()]
        body_pages.append(n)
        for line in text.splitlines():
            for k, rx in SIGNS.items():
                c = len(re.findall(rx, line, flags=re.I if k not in ('numbered_equations', 'algorithm_blocks') else 0))
                if c:
                    hits[k][n] += c
            m = HEADING.match(line)
            if m:
                h = m.group(1).lower()
                kinds = [k for k, rx in SECTION_KINDS.items() if re.search(rx, h)]
                current = kinds or None
            for k in current or []:
                sections[k].add(n)
        if ref:
            break
    signs = {k: {'hits': sum(v.values()), 'pages': sorted(v)} for k, v in hits.items()}
    secs = {k: sorted(v) for k, v in sections.items()}
    first = sorted(set(secs.get('method', [])) | set(secs.get('algorithm', [])) | set(signs['algorithm_blocks']['pages'])
                   | set(secs.get('implementation', [])) | set(signs['training_parameters']['pages']))
    present = {
        'algorithm_or_pseudo_code': signs['algorithm_blocks']['hits'] + signs['pseudo_code_lines']['hits'] > 0,
        'equations': signs['numbered_equations']['hits'] >= 5,
        'training_parameters': signs['training_parameters']['hits'] >= 3,
        'privacy_parameters': signs['privacy_parameters']['hits'] >= 2,
        'model_architecture': signs['model_architecture']['hits'] >= 2,
        'crypto_construction': signs['crypto_construction']['hits'] >= 3,
        'ledger_platform': signs['ledger_platform']['hits'] >= 2,
        'software_named': signs['software_named']['hits'] >= 1,
        'data_split': signs['data_split']['hits'] >= 1,
        'attack_setup': signs['attack_setup']['hits'] >= 2,
    }
    score = sum(present.values())
    level = 'many signs' if score >= 8 else 'some signs' if score >= 5 else 'few signs'
    out = {'about': 'Signs, counted by a local script, that the paper describes its algorithm in codeable detail; counts and '
                    'pages only. A sign is a count, not a judgement: the reader decides.',
           'made': now(), 'paper_folder': d['paper_folder'], 'body_pages': body_pages, 'signs': signs,
           'section_pages': secs, 'present': present, 'signs_present': score, 'level': level,
           'pages_for_reader': first or body_pages}
    save_json(d['folder'] / 'algorithm' / '01-triage.json', out)
    return out


def main():
    ids = set(sys.argv[1:])
    for d in load_designs():
        if ids and d['id'] not in ids:
            continue
        o = triage(d)
        print(f"{d['id']:6} {o['level']:10} {o['signs_present']:2}/10  algo {o['signs']['algorithm_blocks']['hits']:2} "
              f"eq {o['signs']['numbered_equations']['hits']:3} train {o['signs']['training_parameters']['hits']:3} "
              f"crypto {o['signs']['crypto_construction']['hits']:3} ledger {o['signs']['ledger_platform']['hits']:3} "
              f"sw {o['signs']['software_named']['hits']:2}  read {len(o['pages_for_reader'])}/{len(o['body_pages'])} pages")


if __name__ == '__main__':
    main()
