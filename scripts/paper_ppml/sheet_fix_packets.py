#!/usr/bin/env python3
"""Packets for correcting the evidence sheets against the papers — only the passages each fact comes from.

The author, 11 October 2026: "fix the sheet evidences first. i mean correct them. they should be 100% correct. if
needed just upload relevant text from the paper to claude rather than uploadiig whole full text".

For each study, search-ppml/evidence/sheet-fix/packets/<key>.md holds:
  - for every answer of its evidence sheet: the question, the decision rules of its tags (claims-audit-V42/AUDIT-GUIDE.md,
    "Definitions"), the sheet's answer, tags and quotations, and — where the sheets-vs-notes reading of 11 October flagged
    the answer — that reading as a hint;
  - AROUND EACH QUOTATION: the passage of its page around the quoted words (about two sentences either side), not the
    whole page;
  - for surveys, the paper's section headings (whether a topic has a heading of its own decides subject / mentioned).

Usage: python3 scripts/paper_ppml/sheet_fix_packets.py [key ...]      (default: every sheet)
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'local-checker'))
import sections                                            # heading detection, reference-list detection

EV = ROOT / 'search-ppml' / 'evidence'
SHEETS = EV / 'sheets'
OUT = EV / 'sheet-fix'
PAPERS = ROOT / 'notes-verifier' / 'data' / 'papers.json'
GUIDE = EV / 'EXTRACTION-GUIDE.md'
AUDIT_GUIDE = EV / 'claims-audit-V42' / 'AUDIT-GUIDE.md'
VERDICTS = EV / 'sheets-vs-notes' / 'verdicts'

# search words for tag values that are not plain words in papers
VALUE_TERMS = {
    'IoV-vehicular': 'vehicle vehicular IoV VANET', 'IoMT-healthcare': 'health medical hospital patient IoMT',
    'IIoT': 'industrial IIoT', 'smart-grid-energy': 'grid energy power', 'UAV-space': 'UAV drone satellite',
    'smart-city-home': 'smart city home', 'supply-chain': 'supply chain', 'communication-network': '5G 6G network',
    '5G-6G': '5G 6G', 'MEC': 'MEC mobile edge', 'centralised-server': 'server central', 'decentralised': 'decentralized decentralised peer',
    'hierarchical': 'hierarchical tier', 'cross-silo': 'silo organization institution', 'cross-device': 'device',
    'vertical': 'vertical', 'LDP': 'local differential LDP', 'DP': 'differential privacy noise', 'HE': 'homomorphic Paillier CKKS',
    'SMPC': 'multi-party MPC SMPC', 'secret-sharing': 'secret shar Shamir', 'masking-secure-aggregation': 'mask secure aggregation',
    'TEE': 'TEE SGX enclave trusted execution', 'ZKP': 'zero-knowledge ZKP SNARK proof', 'functional-encryption': 'functional encryption',
    'pseudonyms-anonymity': 'pseudonym anonym', 'consortium-permissioned': 'consortium permissioned', 'Hyperledger-Fabric': 'Hyperledger Fabric',
    'FISCO-BCOS': 'FISCO', 'learning-based': 'proof of learning quality', 'protected-updates': 'encrypted update ciphertext on-chain',
    'hashes-commitments': 'hash commitment', 'global-model': 'global model', 'reputation-scores': 'reputation score',
    'identities-keys': 'identity key register', 'rewards-payments': 'reward incentive token payment', 'logs-metadata': 'record log',
    'update-verification': 'verify validat update', 'proof-verification': 'verify proof', 'incentive-reputation': 'incentive reputation',
    'identity-access': 'identity access register authenticat', 'replaces-server': 'replace server', 'record-audit': 'record audit trace',
    'byzantine-malicious': 'Byzantine malicious', 'sybil-fake': 'Sybil fake', 'free-riding': 'free-rid lazy',
    'inference-privacy-attack': 'inference inversion leakage reconstruct', 'malicious-server-aggregator': 'malicious server aggregator',
    'dos-ddos': 'DoS DDoS denial', 'single-point-of-failure': 'single point', 'tampering': 'tamper',
    'test-accuracy-quality': 'accuracy validation test quality', 'similarity-distance': 'cosine distance similarity',
    'norm-bound': 'norm bound clip', 'correct-training': 'correct training', 'correct-aggregation': 'correct aggregation',
    'identity-membership': 'identity membership', 'contribution-reputation': 'contribution reputation', 'anomaly-detection': 'anomal outlier',
    'committee-validators-miners': 'committee validator miner', 'smart-contract': 'smart contract', 'peers-clients': 'peer client',
    'trusted-authority': 'trusted authority TA',
}


def codebook():
    text = AUDIT_GUIDE.read_text(encoding='utf-8')
    text = text[text.index('## Definitions'):text.index('## Results file')]
    rules = {}
    for m in re.finditer(r'^- \*\*([PS][1-8])\*\*(.+?)(?=^- \*\*[PS][1-8]\*\*|^Secondary studies|\Z)', text, re.M | re.S):
        rules[m.group(1)] = re.sub(r'\s+', ' ', m.group(2).replace('`', '').replace('**', '')).strip()
    return rules


def titles():
    out = {}
    for m in re.finditer(r'^\| ([PS][1-8]) \| (.+?) \| (.+?) \|\s*$', GUIDE.read_text(encoding='utf-8'), re.M):
        out[m.group(1)] = (re.sub(r'\*\*', '', m.group(2)).strip(), m.group(3).replace('`', '').strip())
    return out


def pages_of(folder):
    pages = {}
    for sub in ('pages', 'pages_ocr'):
        for f in sorted((folder / 'text' / sub).glob('page_*.txt')):
            pages.setdefault(int(f.stem.split('_')[1]), []).append(f.read_text(encoding='utf-8', errors='ignore'))
    return {n: '\n'.join(v) for n, v in pages.items()}


def sentences_without_references(pages):
    """(page, sentence) for the paper's text before its reference list."""
    out = []
    for s in sections.split(pages):
        if s['kind'] == 'references':
            continue
        for n, text in s['parts']:
            flat = re.sub(r'(\w)-\s*\n\s*(\w)', r'\1\2', text)
            flat = re.sub(r'\s+', ' ', flat)
            out += [(n, x.strip()) for x in re.split(r'(?<=[.!?;])\s+(?=[A-Z0-9(\[])', flat) if len(x.split()) >= 4]
    return out


def answer_terms(q, ans):
    terms = set()
    for v in (ans.get('values') or {}).values():
        for x in (v if isinstance(v, list) else [v]):
            x = str(x)
            if x.startswith('other:'):
                x = x[6:]
            terms.update(VALUE_TERMS.get(x, x.replace('-', ' ')).split())
    text = ans.get('answer', '')
    terms.update(re.findall(r'\b\d+(?:\.\d+)?\s?(?:%|ms|s|kB|MB|GB|×)?', text))
    terms.update(m.group(0) for m in re.finditer(r'\b[A-Z][A-Za-z0-9\-]*[A-Z0-9][A-Za-z0-9\-]*\b', text))   # acronyms/names
    terms.update(sections.QUESTION_WORDS.get(q, '').split())
    stop = {'none', 'stated', 'not', 'yes', 'no', 'other', 'true', 'false', 'n/a', 'the', 'and', 'partly', 'unclear',
            'subject', 'mentioned', 'absent', 'all', 'one', 'two', 's', '1', '2', '3'}
    return {t for t in terms if len(t) >= 3 and t.lower() not in stop}


def hits(sents, terms, skip, limit=20):
    """The sentences richest in the answer's terms, leaving out those already shown around a quotation."""
    scored = []
    for i, (n, s) in enumerate(sents):
        if (n, s) in skip:
            continue
        low = s.lower()
        k = sum(1 for t in terms if t.lower() in low)
        if k >= 2 or (k == 1 and len(terms) <= 3):
            scored.append((k, i))
    keep = sorted(i for _, i in sorted(scored, key=lambda x: -x[0])[:limit])
    return [sents[i] for i in keep]


def trim(sentence, terms, width=50):
    """A long 'sentence' (a table or list without full stops) cut to about 50 words around its first matched term."""
    words = sentence.split()
    if len(words) <= width:
        return sentence
    low = [w.lower() for w in words]
    at = next((i for i, w in enumerate(low) if any(term.lower() in w for term in terms)), 0)
    lo = max(0, at - width // 2)
    return '… ' + ' '.join(words[lo:lo + width]) + ' …'


def flatten(text):
    import unicodedata
    text = unicodedata.normalize('NFKC', text).replace('\u00ad', '')   # ligatures (ﬁ → fi), soft hyphens
    text = re.sub(r'(\w)-\s*\n\s*(\w)', r'\1\2', text)
    return re.sub(r'\s+', ' ', text)


def window(page_text, quote, chars=280):
    """(start, end) of the quoted words in the flattened page, widened by about two sentences' worth of characters;
    found the way the quotation check finds a quotation (letters and digits only)."""
    flat = flatten(page_text)
    keep = [i for i, c in enumerate(flat) if c.isalnum()]
    sq = ''.join(flat[i].lower() for i in keep)
    import unicodedata
    quote = unicodedata.normalize('NFKC', quote)
    q = re.sub(r'[^a-z0-9]', '', quote.lower())
    at = sq.find(q) if len(q) >= 10 else -1
    if at < 0:
        head = re.sub(r'[^a-z0-9]', '', ' '.join(quote.split()[:8]).lower())
        at = sq.find(head) if len(head) >= 10 else -1
        q = head
    if at < 0:
        return None
    start, end = keep[at], keep[min(at + len(q), len(keep)) - 1] + 1
    lo = flat.rfind('. ', 0, max(0, start - chars))
    hi = flat.find('. ', min(len(flat), end + chars))
    return (lo + 2 if lo >= 0 else 0, hi + 1 if hi >= 0 else len(flat))


def merge(spans):
    out = []
    for a, b in sorted(spans):
        if out and a <= out[-1][1] + 40:
            out[-1] = (out[-1][0], max(out[-1][1], b))
        else:
            out.append((a, b))
    return out


def build(key, paper, rules, qtitles, chars=280):
    sheet = json.loads((SHEETS / f'{key}.json').read_text(encoding='utf-8'))
    pages = pages_of(ROOT / paper['folder'])
    sents = sentences_without_references(pages)
    flags = {}
    vf = VERDICTS / f'{key}.json'
    if vf.exists():
        for q, r in json.loads(vf.read_text(encoding='utf-8')).get('answers', {}).items():
            if r.get('verdict') in ('differs', 'conflicts', 'not-in-notes'):
                flags[q] = r
    spans, missing = {}, 0                             # page -> windows around its quotations
    for ans in sheet['answers'].values():
        for e in ans.get('evidence') or []:
            if isinstance(e, dict) and isinstance(e.get('page'), int) and e['page'] in pages:
                w = window(pages[e['page']], e.get('quote', ''), chars)
                if w:
                    spans.setdefault(e['page'], []).append(w)
                else:
                    missing += 1
    excerpt_text = {n: [flatten(pages[n])[a:b] for a, b in merge(v)] for n, v in spans.items()}
    shown = ' '.join(x for v in excerpt_text.values() for x in v).lower()
    out = [f"# {key} — [{paper['n']}] {paper['label']}", '',
           f"Kind: {sheet.get('kind')} · PDF pages: {len(pages)} · PDF: {paper['pdf']}", '',
           'Page numbers are PDF pages (page_NNNN.txt), as in the sheet. The passages around every quotation are at the '
           'end of this packet (EXCERPTS), each page once.', '']
    if sheet.get('kind') != 'primary':
        heads = [f"p{s['parts'][0][0]}: {s['title']}" for s in sections.split(pages)
                 if s['title'] != '(start)' and s['parts'] and s['kind'] != 'references']
        out += ['## SECTION HEADINGS (as extracted)', ''] + heads + ['']
    for q, ans in sheet['answers'].items():
        title, allowed = qtitles.get(q, ('', ''))
        out += [f'## {q} — {title}', '', f'Allowed values: {allowed}', '',
                f'Decision rules: {rules.get(q, "(none beyond the question)")}', '',
                '### The sheet says', '', ans.get('answer', '').strip(), '',
                'Values: ' + json.dumps(ans.get('values') or {}, ensure_ascii=False), '']
        for e in ans.get('evidence') or []:
            if isinstance(e, dict):
                out.append(f"- [p{e.get('page')}]{' (' + e['source'] + ')' if e.get('source') else ''} \"{e.get('quote', '')}\"")
        if ans.get('searched'):
            out += ['', 'Searched (for "not stated"): ' + ', '.join(map(str, ans['searched']))]
        if q in flags:
            f = flags[q]
            out += ['', f"Hint — an earlier comparison with the notes flagged this answer ({f.get('verdict')}): "
                        f"{f.get('comment', '')}"]
            for pt in f.get('points') or []:
                if pt.get('status') != 'agrees':
                    out.append(f"  - {pt.get('status')}: sheet \"{pt.get('sheet', '')}\" / notes \"{pt.get('notes', '')}\"")
        out.append('')                                 # the author: check each fact where it comes from, nothing more
    out += ['## EXCERPTS — the passages around the sheet\'s quotations (each page once)', '']
    for n in sorted(excerpt_text):
        out += [f'### Page {n}', ''] + [f'… {x.strip()} …' for x in excerpt_text[n]] + ['']
    paper_words = sum(len(x.split()) for v in excerpt_text.values() for x in v)
    total_words = sum(len(v.split()) for v in pages.values())
    if paper_words > 0.6 * total_words and chars > 60:  # densely quoted short paper: narrower passages
        return build(key, paper, rules, qtitles, chars=chars // 2)
    (OUT / 'packets').mkdir(parents=True, exist_ok=True)
    text = '\n'.join(out)
    (OUT / 'packets' / f'{key}.md').write_text(text, encoding='utf-8')
    return len(text.split()), sum(len(v.split()) for v in pages.values()), missing


def main(keys):
    papers = {p['key']: p for p in json.loads(PAPERS.read_text())['papers']}
    rules, qtitles = codebook(), titles()
    keys = keys or sorted(p.stem for p in SHEETS.glob('*.json') if p.stem in papers)
    shares, lost = [], []
    for k in keys:
        words, total, missing = build(k, papers[k], rules, qtitles)
        shares.append(words / max(1, total))
        lost.append(missing)
        print(f'{k}: packet {words} words; paper {total} words ({words / max(1, total):.0%}); quotations not located {missing}')
    if len(keys) > 1:
        shares.sort()
        print(f'{len(keys)} packets; packet size against the paper: median {shares[len(shares) // 2]:.0%}, '
              f'largest {shares[-1]:.0%}; quotations not located: {sum(lost)}')


if __name__ == '__main__':
    main(sys.argv[1:])
