#!/usr/bin/env python3
"""Search strings for studies on the regulatory side of privacy-preserving learning on ledgers in the NG-IoT (8 October 2026).

The author asked for "more search terms for scopus and ieee to find related primary or secondary studies", after BeDaSH+
(O110; IEEE Access 2026), the one study found that builds on the EDPB Guidelines 02/2025 on blockchain, turned out to be
missed by the PPML review's search: its title, abstract and keywords never use the word "privacy", which every PPML string
requires. Studies on this side speak of GDPR, data protection, compliance, erasure and off-chain storage instead. These
strings start from that vocabulary. They are a supplementary search, not part of the PPML review's recorded search.

Blocks
  REG     the law and its duties: GDPR, the EDPB, data protection, erasure, compliance, privacy or data protection by design
  LEDGER  blockchain, distributed ledgers, smart contracts, Hyperledger
  ML      the learning (federated, machine, deep, split, swarm)
  NGIOT   the NG-IoT settings, as in the PPML strings, plus wearables and telehealth (BeDaSH+'s own words)
  ERASE   how erasure is done on or around a ledger: redactable or editable chains, chameleon hashes, off-chain storage,
          cryptographic erasure, machine or federated unlearning
  ZK      zero-knowledge proofs
  SUR     survey words in the title (or the Scopus document type Review), to keep only secondary studies

Scopus
  R-S1  REG AND LEDGER AND ML AND NGIOT                       regulation-first: the BeDaSH+ kind of study
  R-S2  ERASE AND LEDGER AND (ML OR NGIOT)                    how designs erase personal data from or around a ledger
  R-S3  ZK AND (REG OR compliance words) AND LEDGER           zero-knowledge proofs used for compliance on a ledger
  R-S4  REF( the EDPB guidelines )                            every Scopus-indexed study whose reference list cites the
                                                              guidelines, whatever its own wording (Scopus only; no
                                                              database other than Scopus searches reference lists)
  R-S5  R-S1 with the survey filter                           secondary studies only
IEEE Xplore (command search, at most 25 terms per query; terms matched in the abstract, as in the PPML primary arm, because
"All Metadata" also matches journal names such as "IEEE Internet of Things Journal")
  R-A1  regulation-first (REG AND LEDGER AND ML AND NGIOT)
  R-A2  erasure on ledgers (ERASE AND LEDGER AND learning or settings)
  R-A3  zero-knowledge proofs for compliance on a ledger

Usage: python3 scripts/search_ppml/strings_regulation.py            prints every query with its term count
       python3 scripts/search_ppml/strings_regulation.py test       runs the queries' logic on known studies
       python3 scripts/search_ppml/strings_regulation.py html       writes the printable step sheet in Docs/
"""
import pathlib, re, sys

REG = ['GDPR', '"General Data Protection Regulation"', 'EDPB', '"European Data Protection Board"', '"data protection"',
       '"right to erasure"', '"right to be forgotten"', '"Article 17"', '"regulatory compliance"', '"privacy by design"',
       '"data protection by design"', '"personal data"']
LEDGER = ['blockchain*', '"distributed ledger*"', '"smart contract*"', 'hyperledger']
ML = ['"federated learning"', '"machine learning"', '"deep learning"', '"split learning"', '"swarm learning"', '"distributed learning"',
      '"collaborative learning"']
NGIOT = ['"Internet of Things"', 'IoT', 'IIoT', 'IoMT', '"internet of medical things"', 'IoV', '"internet of vehicles"', '"edge computing"',
         '"fog computing"', '"mobile edge computing"', '5G', '6G', 'B5G', 'vehicular', '"smart grid*"', '"smart cit*"', '"industrial internet"',
         'wearable*', 'telehealth', '"smart healthcare"', '"e-health"']
ERASE = ['"redactable blockchain*"', '"editable blockchain*"', '"chameleon hash*"', '"off-chain storage"', '"off-chain personal data"',
         '"cryptographic erasure"', '"crypto-shredding"', '"machine unlearning"', '"federated unlearning"']
ZK = ['"zero-knowledge"', '"zero knowledge"', 'zkSNARK*', '"zk-SNARK*"', 'zkML']
COMPLY = REG + ['"selective disclosure"', '"verifiable deletion"', 'compliance']
SUR = ['survey', 'review', '"systematic literature review"', '"systematic review"', '"state of the art"', 'overview', 'tutorial', 'SoK',
       'taxonomy', '"future directions"', '"research directions"', '"open issues"', '"open challenges"', '"challenges and opportunities"']
LIMITS = 'AND PUBYEAR > 2019 AND PUBYEAR < 2027 AND ( DOCTYPE ( ar ) OR DOCTYPE ( cp ) OR DOCTYPE ( re ) ) AND LANGUAGE ( english )'
o = lambda g: ' OR '.join(g)


def scopus():
    q = {
        'R-S1': f'TITLE-ABS-KEY ( {o(REG)} ) AND TITLE-ABS-KEY ( {o(LEDGER)} ) AND TITLE-ABS-KEY ( {o(ML)} ) AND TITLE-ABS-KEY ( {o(NGIOT)} ) {LIMITS}',
        'R-S2': f'TITLE-ABS-KEY ( {o(ERASE)} ) AND TITLE-ABS-KEY ( {o(LEDGER)} ) AND TITLE-ABS-KEY ( {o(ML + NGIOT)} ) {LIMITS}',
        'R-S3': f'TITLE-ABS-KEY ( {o(ZK)} ) AND TITLE-ABS-KEY ( {o(COMPLY)} ) AND TITLE-ABS-KEY ( {o(LEDGER)} ) {LIMITS}',
        # run 1 (7 Oct 2026, 43 records) also had a third branch, ( REF ( "European Data Protection Board" ) AND REF ( blockchain* ) );
        # 17 of its records cite other EDPB documents only (Crossref check, search-ppml/evidence/regulation-search/README.md)
        'R-S4': '( REF ( "Guidelines 02/2025" ) OR REF ( "personal data through blockchain" ) ) AND PUBYEAR > 2024',
    }
    q['R-S5'] = f'( TITLE ( {o(SUR)} ) OR DOCTYPE ( re ) ) AND ' + q['R-S1']
    return q


# IEEE Xplore: 25 terms at most per query; the blocks are trimmed to the terms that carry them
I_REG = ['GDPR', '"General Data Protection Regulation"', 'EDPB', '"data protection"', '"right to erasure"', '"right to be forgotten"',
         '"regulatory compliance"']
I_LEDGER = ['blockchain', '"distributed ledger"', '"smart contract"']
I_ML = ['"federated learning"', '"machine learning"', '"deep learning"']
I_NGIOT = ['IoT', '"Internet of Things"', 'IIoT', 'IoMT', '"edge computing"', 'vehicular', '"smart grid"', '5G', '6G', 'wearable',
           'telehealth', '"smart healthcare"']
I_ERASE = ['"redactable blockchain"', '"editable blockchain"', '"chameleon hash"', '"off-chain storage"', '"machine unlearning"', '"federated unlearning"',
           '"cryptographic erasure"']
I_LEARN_SET = ['"federated learning"', '"machine learning"', 'IoT', '"Internet of Things"', 'IoMT', '"edge computing"', 'vehicular']
I_ZK = ['"zero-knowledge"', '"zero knowledge"', 'zkSNARK', '"zk-SNARK"']
I_COMPLY = ['GDPR', '"data protection"', '"regulatory compliance"', '"right to erasure"', '"right to be forgotten"', '"selective disclosure"',
            '"verifiable deletion"', 'EDPB', '"personal data"']


def ieee():
    a = lambda g: ' OR '.join(f'"Abstract":{x}' for x in g)
    return {'R-A1': f'({a(I_REG)}) AND ({a(I_LEDGER)}) AND ({a(I_ML)}) AND ({a(I_NGIOT)})',
            'R-A2': f'({a(I_ERASE)}) AND ({a(I_LEDGER[:2])}) AND ({a(I_LEARN_SET)})',
            'R-A3': f'({a(I_ZK)}) AND ({a(I_COMPLY)}) AND ({a(I_LEDGER)})'}


# --------------------------------------------------------------- offline test of the logic on known studies
def term_re(t):
    t = t.strip('"')
    pat = re.escape(t).replace(r'\*', r'\w*').replace(r'\ ', r'[\s-]+').replace(r'\-', r'[\s-]?')
    return re.compile(r'(?<![\w])' + pat + r'(?![\w])', re.I)


def hit(block, text):
    return any(term_re(t).search(text) for t in block)


def match(qid, title, tak):
    if qid in ('R-S1', 'R-A1'):
        return all(hit(b, tak) for b in (REG, LEDGER, ML, NGIOT))
    if qid in ('R-S2', 'R-A2'):
        return hit(ERASE, tak) and hit(LEDGER, tak) and hit(ML + NGIOT, tak)
    if qid in ('R-S3', 'R-A3'):
        return hit(ZK, tak) and hit(COMPLY, tak) and hit(LEDGER, tak)
    if qid == 'R-S5':
        return hit(SUR, title) and match('R-S1', title, tak)
    return None


SIZES = {'R-S1': 'about 356 in OpenAlex (title and abstract, 2020–2026), about 138 of them never say "privacy"',
         'R-S2': 'about 162 in OpenAlex',
         'R-S3': 'about 353 in OpenAlex, about 69 of them never say "privacy"',
         'R-S4': 'cannot be sized outside Scopus (reference lists)',
         'R-S5': 'a subset of R-S1'}
WHAT = {'R-S1': 'Regulation-first: data-protection law or its duties, a ledger, learning and an NG-IoT setting. Finds studies such as BeDaSH+ that never use the word "privacy".',
        'R-S2': 'How designs erase personal data from or around a ledger: redactable or editable chains, chameleon hashes, off-chain storage, unlearning.',
        'R-S3': 'Zero-knowledge proofs used for compliance on a ledger (selective disclosure, verifiable deletion, GDPR).',
        'R-S4': 'Every Scopus-indexed study whose reference list cites the EDPB Guidelines 02/2025, whatever its own wording. Run it first: it is the direct answer to "who builds on the guidelines".',
        'R-S5': 'R-S1 restricted to secondary studies (survey words in the title, or document type Review).',
        'R-A1': 'Regulation-first, as R-S1, matched in the abstract.', 'R-A2': 'Erasure on ledgers, as R-S2.', 'R-A3': 'Zero-knowledge proofs for compliance, as R-S3.'}


def html():
    import datetime, html as H
    out = pathlib.Path(__file__).resolve().parents[2] / 'Docs' / f'REGULATION-SEARCH-STRINGS-{datetime.date.today().isoformat()}.html'
    if out.exists():
        sys.exit(f'{out.name} exists; documents are never overwritten')
    block = lambda k, q, where: (f"<section><h3>{k} <span class='w'>({where})</span></h3><p>{H.escape(WHAT[k])}</p>"
                                 f"<p class='s'>Size: {H.escape(SIZES.get(k, 'run to see'))}.</p><pre>{H.escape(q)}</pre></section>")
    body = ''.join(block(k, q, 'Scopus, Advanced document search') for k, q in scopus().items())
    body += ''.join(block(k, q, f'IEEE Xplore, Command Search, {q.count(":")} terms') for k, q in ieee().items())
    css = ('body{font:14px/1.5 Georgia,serif;background:#fff;color:#111;margin:24px;max-width:1100px}h1{font-size:22px}h3{font-size:16px;margin:18px 0 4px}'
           '.w{font-weight:normal;color:#444;font-size:13px}.s{font-size:12px;color:#333}pre{white-space:pre-wrap;overflow-wrap:anywhere;'
           'background:#f5f5f5;border:1px solid #ccc;padding:8px;font-size:12px}'
           '@media print{@page{size:auto;margin:14mm}body{margin:0;max-width:none}pre{background:#fff;overflow:visible}section{break-inside:avoid}}')
    intro = ('<p>Supplementary searches for studies on the regulatory side of privacy-preserving learning on ledgers in the NG-IoT, built after '
             'BeDaSH+ (IEEE Access 2026), the one study found that builds on the EDPB Guidelines 02/2025 on blockchain, was missed by the PPML '
             'review\'s search: its title, abstract and keywords never use the word "privacy". These strings start from the vocabulary such studies use '
             '(GDPR, data protection, erasure, compliance, off-chain storage). They are not part of the PPML review\'s recorded search. '
             'Run R-S4 first. Export each result set with abstracts and keywords (Scopus: CSV with "Abstract &amp; keywords"; IEEE Xplore: '
             'Search Results CSV) and keep the exports with their date. Source: scripts/search_ppml/strings_regulation.py '
             '(<code>test</code> checks the logic on known records: BeDaSH+ satisfies R-S1, R-S2 and R-S3).</p>')
    out.write_text(f"<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
                   f"<title>Regulation search strings</title><style>{css}</style></head><body><h1>Search strings: GDPR, EDPB and erasure "
                   f"in learning on ledgers (Scopus, IEEE Xplore)</h1><p class='s'>8 October 2026</p>{intro}{body}</body></html>", encoding='utf-8')
    print(f'written: {out}')


if __name__ == '__main__':
    if sys.argv[1:] == ['html']:
        html()
        sys.exit(0)
    if sys.argv[1:] != ['test']:
        for k, q in scopus().items():
            print(f'Scopus {k}:\n{q}\n')
        for k, q in ieee().items():
            print(f'IEEE Xplore {k} ({q.count(":")} terms):\n{q}\n')
        sys.exit(0)
    import csv, json, pathlib
    csv.field_size_limit(10 ** 9)
    ROOT = pathlib.Path(__file__).resolve().parents[2]
    known = {}
    for f in ('search/MERGED-RECORDS-2026-10-02.csv', 'search-ppml/MERGED-RECORDS-2026-10-04.csv'):
        for r in csv.DictReader(open(ROOT / f, encoding='utf-8', errors='ignore')):
            known.setdefault((r.get('doi') or r['title']).lower(), r)
    probes = {'BeDaSH+ (O110)': '10.1109/access.2026.3734094'}
    for name, doi in probes.items():
        r = known.get(doi)
        tak = ' '.join([r['title'], r.get('abstract', ''), r.get('keywords', '')])
        print(name, {q: match(q, r['title'], tak) for q in ('R-S1', 'R-S2', 'R-S3', 'R-S5')})
    for f, label in (('search-ppml/MERGED-RECORDS-2026-10-04.csv', 'PPML search records'),):
        rows = list(csv.DictReader(open(ROOT / f, encoding='utf-8', errors='ignore')))
        for q in ('R-S1', 'R-S2', 'R-S3', 'R-S5'):
            n = sum(bool(match(q, r['title'], ' '.join([r['title'], r.get('abstract', ''), r.get('keywords', '')]))) for r in rows)
            print(f'{label}: {n} of {len(rows)} records satisfy {q}')
