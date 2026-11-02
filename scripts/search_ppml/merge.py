#!/usr/bin/env python3
"""Merge and de-duplicate the exports of the PPML review of surveys (searches of 4 October 2026, run by the author).

Inputs: search-ppml/exports/{scopus,ieee,sciencedirect}/ and search-ppml/exports/PROVENANCE-2026-10-04.tsv (which search
each file belongs to). Each record is checked against its own search (self-check). Records are merged by DOI, else by
title. As in the ZK review, IEEE Xplore's "All Metadata" field also matches text outside the title, abstract and
keywords, so a record returned only by IEEE Xplore is set aside by an automated rule when its title (survey words) and its
title, abstract and keywords (privacy, learning and NG-IoT terms) do not satisfy the search; this applies the same test
that Scopus and ScienceDirect apply. Scopus records typed Review need no survey word in the title (as in P-S1).
Two arms (strings version 4): the survey arm (P-S1, P-A*, P-C*) and the primary arm (P-S2, P-B*, P-D*); a record returned
only by IEEE Xplore is kept when it satisfies the test of an arm whose search returned it.
A second automated rule removes records whose title announces something other than a paper (editorial, guest editorial,
preface, erratum, correction, retraction notice, keynote talk, special-issue introduction, welcome message, panel); the
author, 4 October 2026: "just remove that are not full papers - we dont care about them at all".
A third automated rule narrows the primary-study search to the PhD's focus (the author chose "Surveys all; primary +
threat/verif/blockchain", 4 October 2026): a record found only by the primary-study search is kept when its title,
abstract or keywords name a threat of the PhD proposal (data poisoning, backdoors, Byzantine, malicious or fake
participants, Sybil, free riding), verification of the learning, or blockchain ("This project will employ blockchain
technology to design and develop a privacy-preserved ML approach at the edge of NG-IoT"). Every record of the survey
search is kept.

Outputs: search-ppml/MERGED-RECORDS-2026-10-04.csv (one row per unique record, numbered) and
search-ppml/MERGE-CHECK-2026-10-04.json (counts for the PRISMA flow, self-checks, files).

Usage: python3 scripts/search_ppml/merge.py
"""
import csv, json, pathlib, re, sys

csv.field_size_limit(10 ** 9)
ROOT = pathlib.Path(__file__).resolve().parents[2]
P = ROOT / 'search-ppml'
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import strings as S                                   # noqa: E402


def norm(t):
    return ' ' + re.sub(r'[^a-z0-9]+', ' ', (t or '').lower()) + ' '


def term_re(term):
    """a search term as a pattern on norm() text; the wildcards ? (one letter) and * (any ending) are kept, as the
    databases read them (fixed 4 October 2026: norm() had turned them into spaces, so "smart grid*" missed "smart grids")"""
    t = re.sub(r'[^a-z0-9?*]+', ' ', term.strip('"').lower()).strip()
    pat = re.escape(t).replace(r'\?', '[a-z0-9]').replace(r'\*', '[a-z0-9]*')
    return re.compile(r'(?<![a-z0-9])' + pat + r'(?![a-z0-9])')


GROUPS = {k: [term_re(x) for x in g] for k, g in (('SUR', S.SUR), ('PPML', S.PPML), ('ML', S.ML), ('NGIOT', S.NGIOT), ('THREAT', S.THREAT))}
PRIMARY_SEARCHES = ('P-S2', 'P-B', 'P-D')
FOCUS_PARTS = {   # the PhD focus in its parts (criteria V7): the proposal's threats, its verification, zero-knowledge, its blockchain
    'poisoning': ['poison*', 'backdoor*', '"label flip*"', '"label-flip*"', '"model replacement"'],
    'malicious or fake participants': ['byzantine', 'sybil', 'malicious', '"fake node*"', '"fake client*"', '"fake participant*"',
                                       '"adversarial client*"', '"adversarial participant*"', 'dishonest'],
    'free riding': ['"free-rid*"', '"free rid*"', '"free rider*"', '"lazy client*"', '"proof of contribution"'],
    'verification': ['verifiab*', '"integrity verification"', '"verify the integrity"', '"model integrity"', 'auditab*',
                     '"proof of training"', '"proof of learning"', '"homomorphic hash*"', 'attestation'],
    'zero-knowledge proofs': ['"zero-knowledge"', '"zero knowledge"', 'zk-snark*', 'zksnark*', 'zk-stark*', 'zkp*', 'zkml', 'bulletproof*',
                              '"succinct non-interactive"'],
    'blockchain': ['blockchain*', 'block-chain*', '"distributed ledger*"', '"smart contract*"'],
    # also ticked by the pre-fill when the zero-knowledge and the blockchain cues both appear
    'ZK on blockchain': ['"on-chain verif*"', '"verified on-chain"', '"verified on chain"', '"verifier contract"', '"zk-rollup*"',
                         '"zk rollup*"', '"on-chain proof*"'],
}
FOCUS_TERMS = [x for terms in FOCUS_PARTS.values() for x in terms]
NOT_A_PAPER = re.compile(r'^(?:guest editorial|editorial|preface|foreword|erratum|errata|correction|corrigendum|retraction|retracted|'
                         r'expression of concern|message from|welcome|keynote|introduction to the special|special issue|panel)\b', re.I)
arm_of = lambda search: 'primary' if search.startswith(PRIMARY_SEARCHES) else 'survey'
FOCUS = [term_re(x) for x in FOCUS_TERMS]
has = lambda text, g: any(p.search(text) for p in GROUPS[g])


def in_scope(r, review_type=False, arm='survey'):
    """the search's test on a record. Survey arm: a survey word in the title (or Scopus type Review), and the privacy,
    learning and NG-IoT terms in title, abstract or keywords. Primary arm: privacy in the title, or privacy and a threat
    in title, abstract or keywords; and the learning and NG-IoT terms in title, abstract or keywords"""
    tak = norm(' '.join([r['title'], r['abstract'], r['keywords']]))
    if arm == 'primary':
        return ((has(norm(r['title']), 'PPML') or (has(tak, 'PPML') and has(tak, 'THREAT')))
                and has(tak, 'ML') and has(tak, 'NGIOT'))
    return (review_type or has(norm(r['title']), 'SUR')) and has(tak, 'PPML') and has(tak, 'ML') and has(tak, 'NGIOT')


def rec(source, search, title, abstract, keywords, doi, year, venue, doctype, file, cited=''):
    return {'source': source, 'search': search, 'title': (title or '').strip(), 'abstract': (abstract or '').strip(),
            'keywords': (keywords or '').strip(), 'doi': (doi or '').strip().lower(), 'year': (year or '').strip()[:4],
            'venue': (venue or '').strip(), 'type': (doctype or '').strip(), 'file': file,
            'cited': int(cited) if str(cited or '').strip().isdigit() else None}


def ris_records(path):
    recs, cur = [], {}
    for line in open(path, encoding='utf-8-sig', errors='replace'):
        m = re.match(r'^([A-Z][A-Z0-9])  - ?(.*)$', line.rstrip('\n'))
        if not m:
            continue
        tag, val = m.groups()
        if tag == 'ER':
            recs.append(cur)
            cur = {}
        else:
            cur.setdefault(tag, []).append(val.strip())
    return recs


def load():
    prov = list(csv.DictReader(open(P / 'exports' / 'PROVENANCE-2026-10-04.tsv', encoding='utf-8'), delimiter='\t'))
    out = []
    prov = [p for p in prov if 'pilot' not in p['search']]       # the pilot run (strings v2) is on record, not merged
    for p in prov:
        if p['source'] == 'Scopus':
            for r in csv.DictReader(open(P / 'exports' / 'scopus' / p['file'], encoding='utf-8-sig')):
                kw = '; '.join([r.get('Author Keywords', ''), r.get('Index Keywords', '')])
                ab = '' if r.get('Abstract', '').startswith('[No abstract') else r.get('Abstract', '')
                out.append(rec('Scopus', p['search'], r['Title'], ab, kw, r['DOI'], r['Year'], r['Source title'],
                               r['Document Type'], p['file'], r.get('Cited by', '')))
        elif p['source'] == 'IEEE Xplore':
            for r in csv.DictReader(open(P / 'exports' / 'ieee' / p['file'], encoding='utf-8-sig', errors='replace')):
                kw = '; '.join([r.get('Author Keywords', ''), r.get('IEEE Terms', ''), r.get('Mesh_Terms', '')])
                out.append(rec('IEEE Xplore', p['search'], r['Document Title'], r['Abstract'], kw, r['DOI'],
                               r['Publication Year'], r['Publication Title'], '', p['file'], r.get('Article Citation Count', '')))
        elif p['source'] == 'ScienceDirect':
            for r in ris_records(P / 'exports' / 'sciencedirect' / p['file']):
                g = lambda *tags: next((r[t][0] for t in tags if r.get(t)), '')
                doi = re.sub(r'^https?://(dx\.)?doi\.org/', '', g('DO'))
                out.append(rec('ScienceDirect', p['search'], g('TI', 'T1'), g('AB'), '; '.join(r.get('KW', [])), doi,
                               g('PY', 'Y1', 'DA'), g('JO', 'T2', 'JF'), g('TY'), p['file']))
    return prov, out


def main():
    prov, records = load()
    check = {}
    for r in records:
        c = check.setdefault(f"{r['source']} {r['search']}", {'records': 0, 'in_scope_by_text': 0})
        c['records'] += 1
        c['in_scope_by_text'] += in_scope(r, review_type=(r['source'] == 'Scopus' and r['type'] == 'Review'), arm=arm_of(r['search']))
    merged, by_doi, by_title = [], {}, {}
    for r in records:
        t = re.sub(r'[^a-z0-9]', '', r['title'].lower())
        m = by_doi.get(r['doi']) if r['doi'] else None
        if m is None:
            m = by_title.get(t)
            if m is not None and r['doi'] and m['doi'] and m['doi'] != r['doi']:
                m = None                                   # same title, different DOIs: different works
        if m is None:
            m = {'doi': r['doi'], 'title': r['title'], 'year': r['year'], 'venue': r['venue'], 'type': r['type'],
                 'abstract': r['abstract'], 'keywords': r['keywords'], 'sources': set(), 'hits': set(), 'arms': set(), 'cited': None}
            merged.append(m)
        if r['doi'] and not m['doi']:
            m['doi'] = r['doi']
        if r['cited'] is not None:                      # citations at the search date: the higher of Scopus and IEEE Xplore
            m['cited'] = max(m['cited'] or 0, r['cited'])
        m['sources'].add(r['source'])
        m['hits'].add(f"{r['source']}:{r['search']}")
        m['arms'].add(arm_of(r['search']))
        for f in ('abstract', 'keywords', 'venue', 'year'):
            if len(r[f]) > len(m[f]):
                m[f] = r[f]
        if r['source'] == 'Scopus':
            m['type'] = r['type']
        if m['doi']:
            by_doi[m['doi']] = m
        by_title.setdefault(t, m)
    auto = 0
    for i, m in enumerate(merged, 1):
        m['n'] = i
        m['auto_excluded'] = ''
        if m['sources'] == {'IEEE Xplore'} and not any(in_scope(m, arm=a) for a in m['arms']):
            m['auto_excluded'] = 'IEEE Xplore only; title, abstract and keywords do not satisfy the search (All Metadata matched elsewhere)'
            auto += 1
        elif NOT_A_PAPER.search(m['title'].strip()):
            m['auto_excluded'] = 'not a paper: the title announces an editorial, notice, talk or special-issue introduction'
            auto += 1
        elif m['arms'] == {'primary'} and not any(p.search(norm(' '.join([m['title'], m['abstract'], m['keywords']]))) for p in FOCUS):
            m['auto_excluded'] = 'outside the PhD focus: found only by the primary-study search, and no threat, verification or blockchain term'
            auto += 1
    with open(P / 'MERGED-RECORDS-2026-10-04.csv', 'w', encoding='utf-8', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=['n', 'doi', 'title', 'year', 'venue', 'type', 'cited', 'arms', 'sources', 'hits', 'auto_excluded', 'abstract', 'keywords'])
        w.writeheader()
        for m in merged:
            w.writerow({**{k: m[k] for k in ('n', 'doi', 'title', 'year', 'venue', 'type', 'cited', 'auto_excluded', 'abstract', 'keywords')},
                        'arms': '; '.join(sorted(m['arms'])), 'sources': '; '.join(sorted(m['sources'])), 'hits': '; '.join(sorted(m['hits']))})
    ident = {s: sum(1 for r in records if r['source'] == s) for s in ('Scopus', 'IEEE Xplore', 'ScienceDirect')}
    out = {'identified_total': len(records), 'identified': ident, 'unique': len(merged), 'duplicates': len(records) - len(merged),
           'auto_excluded': auto, 'to_screen': len(merged) - auto,
           'auto_excluded_ieee_rule': sum(1 for m in merged if m['auto_excluded'].startswith('IEEE')),
           'auto_excluded_not_a_paper': sum(1 for m in merged if m['auto_excluded'].startswith('not a paper')),
           'auto_excluded_focus': sum(1 for m in merged if m['auto_excluded'].startswith('outside the PhD focus')),
           'only_ieee_screened': sum(1 for m in merged if m['sources'] == {'IEEE Xplore'} and not m['auto_excluded']),
           'only_sciencedirect': sum(1 for m in merged if m['sources'] == {'ScienceDirect'}),
           'not_in_scopus': sum(1 for m in merged if 'Scopus' not in m['sources'] and not m['auto_excluded']),
           'to_screen_by_arm': {a: sum(1 for m in merged if a in m['arms'] and not m['auto_excluded']) for a in ('survey', 'primary')},
           'to_screen_both_arms': sum(1 for m in merged if len(m['arms']) == 2 and not m['auto_excluded']),
           'self_check': check, 'files': [p['file'] for p in prov]}
    (P / 'MERGE-CHECK-2026-10-04.json').write_text(json.dumps(out, indent=1), encoding='utf-8')
    print(json.dumps({k: v for k, v in out.items() if k not in ('files',)}, indent=1))


if __name__ == '__main__':
    main()
