#!/usr/bin/env python3
"""Search strings of the systematic review of surveys for the PPML paper (the V28 series), built from the author's PhD
proposal, not from the corpus (the author, 4 October 2026: "look at my PhD proposal and give me a befitting search.
forget about the corpus we have").

The proposal's title is "Privacy-Preserving Machine Learning for Next Generation IoT (NG-IoT) Security"
(phdproposal/phd funding proposal.txt). Its concepts give the blocks, and its own words give their first terms:
  PPML  "privacy-preserving ML approach", "data privacy", "privacy preservation", "privacy-preserved ML"
  ML    "distributed machine learning approaches", "learning task", "global ML model" (federated learning is the common form)
  NGIOT "Next Generation IoT (NG-IoT)", "5G & edge computing paradigms", "at the edge", "IoT devices"
  SUR   the study type of this review (a review of surveys, option B of Docs/PPML-SEARCH-PROTOCOL-2026-10-04.html):
        a survey word in the TITLE, or the Scopus document type Review
The search is SUR AND PPML AND ML AND NGIOT, 2020-2026. The proposal's threats (poisoning, malicious participants, free
riding, DDoS) and its blockchain are what the review reads the surveys for, not search filters: requiring them would drop
privacy surveys that do not name them in the abstract.

Scopus takes the whole string. IEEE Xplore's command search allows at most 25 terms and ScienceDirect at most 8 Boolean
connectors per field, so their versions are split into parts that together cover the same blocks.

Version 3 (4 October 2026, after the coverage check against the corpus surveys, search-ppml/COVERAGE-2026-10-04.md):
plain "privacy" added to PPML (surveys titled "Security and Privacy in …" were missed); common survey title phrasing added
to SUR ("…: challenges and future directions", "opportunities and challenges", "threats and countermeasures"); clear
NG-IoT setting terms added (IoV, IoMT, industrial internet, vehicular, smart grid, smart city, B5G, communication network).
IEEE Xplore is split into six queries (25 terms at most); ScienceDirect keeps its eight queries of version 2 (its
8-connector limit would need about forty; Elsevier's journals are covered by Scopus).

Version 4 (4 October 2026) adds a second arm for primary studies; the survey arm (P-S1, P-A1–6, P-C1–8) is unchanged.
The author: "let us broaden our search so that my paper gives coverage to both primary and secondary studies". Of the
sized options (search-ppml/SIZE-PROBE-2026-10-04.json, PRIMARY-COVERAGE-2026-10-04.json) the author chose "A or C":
  ( privacy in the TITLE  OR  ( privacy AND a threat of the PhD, in title, abstract or keywords ) )
  AND learning AND NG-IoT (title, abstract or keywords), 2020-2026
A study with privacy in its title has privacy as its aim; the threat branch adds studies that name privacy only in the
abstract but deal with what the PhD is about: poisoning, Byzantine or malicious participants, Sybil or fake nodes, free
riding, verifiability (phdproposal: malicious participants, poisoning, free riding). Estimated 3,700 records in Scopus;
it reaches 34 of the 41 corpus primary studies on the topic (83%).
Primary arm: Scopus P-S2; IEEE Xplore P-B, one query of 25 terms exported in year parts; ScienceDirect P-D1–4 (8 connectors
at most).

Usage: python3 scripts/search_ppml/strings.py   -> prints every query
"""
SUR = ['survey', 'review', '"systematic literature review"', '"systematic review"', '"systematic mapping"', '"state of the art"',
       'overview', 'tutorial', 'SoK', 'taxonomy', '"future directions"', '"research directions"', '"open problems"', '"open issues"',
       '"open challenges"', '"challenges and opportunities"', '"opportunities and challenges"', '"challenges and solutions"',
       'countermeasures', 'advances', 'fundamentals', 'perspectives', 'trends', 'roadmap', '"lessons learned"', '"comprehensive study"']
PPML = ['"privacy-preserving machine learning"', 'PPML', '"privacy-preserving"', '"privacy preserving"', '"privacy preservation"',
        '"data privacy"', '"privacy protection"', 'privacy', '"differential privacy"', '"homomorphic encryption"', '"multi-party computation"',
        '"secure aggregation"']
ML = ['"machine learning"', '"deep learning"', '"federated learning"', '"distributed learning"', '"distributed machine learning"',
      '"collaborative learning"', '"decentrali?ed learning"', '"split learning"', '"edge intelligence"']
NGIOT = ['"next generation IoT"', '"next-generation IoT"', '"NG-IoT"', '"next generation Internet of Things"', '"Internet of Things"',
         'IoT', 'IIoT', 'IoMT', 'IoV', '"internet of vehicles"', '"internet of medical things"', '"industrial internet"', '"edge computing"',
         '"mobile edge computing"', '"fog computing"', '5G', '6G', '"beyond 5G"', 'B5G', 'vehicular', '"smart grid*"', '"smart cit*"',
         '"communication network*"']
THREAT = ['poisoning', 'byzantine', 'backdoor', 'sybil', 'malicious', '"free-rid*"', '"free rider*"', '"fake node*"', '"fake client*"',
          '"model integrity"', 'verifiable']


def scopus():
    o = lambda g: ' OR '.join(g)
    return (f'( TITLE ( {o(SUR)} ) OR DOCTYPE ( re ) ) AND TITLE-ABS-KEY ( {o(PPML)} ) AND TITLE-ABS-KEY ( {o(ML)} ) '
            f'AND TITLE-ABS-KEY ( {o(NGIOT)} ) AND PUBYEAR > 2019 AND PUBYEAR < 2027 '
            f'AND ( DOCTYPE ( ar ) OR DOCTYPE ( cp ) OR DOCTYPE ( re ) ) AND LANGUAGE ( english )')


# IEEE Xplore (command search, at most 25 terms): survey words in the title, the other blocks in All Metadata; records
# matched only outside title, abstract and keywords are set aside afterwards by the same automated rule as in the ZK review
IEEE_SUR_PARTS = [['survey', 'review', 'overview', 'tutorial', 'SoK', 'taxonomy', '"state of the art"', '"systematic literature review"', '"future directions"'],
                  ['"open problems"', '"open issues"', '"challenges and opportunities"', '"opportunities and challenges"', '"challenges and solutions"',
                   'countermeasures', 'advances', 'fundamentals', 'perspectives']]
IEEE_PPML = ['privacy', 'PPML']
IEEE_ML = ['"machine learning"', '"deep learning"', '"federated learning"', '"distributed learning"', '"collaborative learning"']
IEEE_NGIOT_PARTS = [['"next generation IoT"', '"NG-IoT"', '"Internet of Things"', 'IoT', 'IIoT', 'IoMT', 'IoV'],
                    ['"edge computing"', '"fog computing"', '5G', '6G', 'B5G', '"internet of vehicles"', '"industrial internet"'],
                    ['vehicular', '"smart grid"', '"smart city"', '"communication network"', '"mobile edge computing"', '"internet of medical things"', '"beyond 5G"']]


def ieee():
    t = lambda g: ' OR '.join(f'"Document Title":{x}' for x in g)
    m = lambda g: ' OR '.join(f'"All Metadata":{x}' for x in g)
    return [f'({t(s)}) AND ({m(IEEE_PPML)}) AND ({m(IEEE_ML)}) AND ({m(p)})' for s in IEEE_SUR_PARTS for p in IEEE_NGIOT_PARTS]


# ScienceDirect (at most 8 Boolean connectors per field): Title = survey words (8 terms, 7 ORs);
# Title, abstract or author-specified keywords = one privacy set AND one learning set AND one setting set
SD_TITLE = 'survey OR review OR overview OR tutorial OR "state of the art" OR "systematic literature review" OR SoK OR taxonomy'
SD_PRIV = ['("privacy-preserving" OR "privacy preserving" OR "data privacy")', '("differential privacy" OR "homomorphic encryption" OR "secure aggregation")']
SD_ML = ['("machine learning" OR "federated learning" OR "deep learning")']
SD_NGIOT = ['("next generation IoT" OR "NG-IoT" OR "Internet of Things")', '(IoT OR IIoT OR "edge computing")', '("fog computing" OR 5G OR 6G)']


def sciencedirect():
    q = [(SD_TITLE, f'{p} AND {SD_ML[0]} AND {n}') for p in SD_PRIV for n in SD_NGIOT]
    q.append((SD_TITLE, '("privacy-preserving machine learning" OR PPML) AND ("next generation IoT" OR "NG-IoT" OR "Internet of Things" OR IoT OR "edge computing")'))
    q.append((SD_TITLE, '("privacy-preserving" OR "data privacy") AND ("distributed learning" OR "collaborative learning" OR "edge intelligence") AND ("Internet of Things" OR IoT OR "edge computing")'))
    return q


# ------------------------------------------------------------------------------------------- primary arm (version 4)
def scopus_primary():
    o = lambda g: ' OR '.join(g)
    return (f'( TITLE ( {o(PPML)} ) OR ( TITLE-ABS-KEY ( {o(PPML)} ) AND TITLE-ABS-KEY ( {o(THREAT)} ) ) ) '
            f'AND TITLE-ABS-KEY ( {o(ML)} ) AND TITLE-ABS-KEY ( {o(NGIOT)} ) AND PUBYEAR > 2019 AND PUBYEAR < 2027 '
            f'AND ( DOCTYPE ( ar ) OR DOCTYPE ( cp ) OR DOCTYPE ( re ) ) AND LANGUAGE ( english )')


IEEE_THREAT = ['poisoning', 'byzantine', 'backdoor', 'sybil', 'malicious', '"free riding"', 'verifiable']
IEEE_ML_P = ['"federated learning"', '"machine learning"', '"deep learning"', '"distributed learning"', '"collaborative learning"']
IEEE_NGIOT_P = ['IoT', '"Internet of Things"', 'IIoT', 'IoV', 'IoMT', '"edge computing"', '"fog computing"', '5G', '6G', 'vehicular', '"smart grid"']


def ieee_primary():
    """one query of 25 terms (the author asked for a single, more focused IEEE query; it replaces P-B1-5 of the step
    sheet V4, which were not run). Learning, NG-IoT and the threat branch are matched in the abstract, not All Metadata
    (whose journal names, e.g. "IEEE Internet of Things Journal", flood the results); privacy in the title as in Scopus.
    IEEE Xplore exports at most 1,000 results at a time, so it is exported in year parts (P-B 2020-2023, 2024, 2025, 2026)"""
    a = lambda g: ' OR '.join(f'"Abstract":{x}' for x in g)
    return [f'("Document Title":privacy OR ("Abstract":privacy AND ({a(IEEE_THREAT)}))) AND ({a(IEEE_ML_P)}) AND ({a(IEEE_NGIOT_P)})']


def sciencedirect_primary():
    ml = '("machine learning" OR "federated learning" OR "deep learning")'
    return [('privacy OR PPML', f'{ml} AND ("Internet of Things" OR IoT OR IIoT OR IoMT OR "edge computing" OR "fog computing")'),
            ('privacy OR PPML', f'{ml} AND (5G OR 6G OR vehicular OR "smart grid" OR "smart city" OR "industrial internet")'),
            ('', 'privacy AND (poisoning OR byzantine OR backdoor OR sybil OR malicious) AND "federated learning" AND (IoT OR "edge computing")'),
            ('', 'privacy AND ("free riding" OR "free rider" OR "fake node" OR verifiable) AND "federated learning" AND (IoT OR "edge computing")')]


if __name__ == '__main__':
    print('Scopus:\n' + scopus())
    for i, q in enumerate(ieee(), 1):
        print(f'\nIEEE {i} ({q.count(":")} terms):\n{q}')
    for i, (t, q) in enumerate(sciencedirect(), 1):
        print(f'\nScienceDirect {i}: TITLE = {t}\n  TAK = {q}')
    print('\n\nPRIMARY ARM\nScopus P-S2:\n' + scopus_primary())
    for i, q in enumerate(ieee_primary(), 1):
        print(f'\nIEEE P-B ({q.count(":")} terms):\n{q}')
    for i, (ti, q) in enumerate(sciencedirect_primary(), 1):
        print(f'\nScienceDirect P-D{i}: TITLE = {ti or "(empty)"} ({ti.count(" OR ")} connectors)\n  TAK = {q} '
              f'({q.count(" OR ") + q.count(" AND ")} connectors)')
