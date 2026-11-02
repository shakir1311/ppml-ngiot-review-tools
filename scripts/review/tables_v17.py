"""Tables, statistics and figure registry of the V17 review.

V17 is V16 with the eight studies found by backward snowballing from the two surveys of verifiable FL (O102-O109)
included, and with the author's edits to V16 (a table of contents; "decentralised" in the keyword table). All tables
and statistics come from tables_v16, pointed at the V17 sources in _src/V17."""
import tables_v16 as V16
from tables_v16 import *  # noqa: F401,F403

SRC17 = V16.V14.ROOT / 'myliteraturereviewpaper' / '_src' / 'V17'
V16.SRC16 = SRC17                 # tables_v16 reads its sources through these names at call time
V16.CLASS = SRC17 / 'classify'


def t_keywords17():
    t = V16.V15.t_keywords()
    for r in t['rows']:
        r[1] = r[1].replace('"decentrali?ed learning"', '"decentralised learning" OR "decentralized learning"')
    t['columns'][1]['header'] = 'Terms'
    t['note'] = '* stands for any ending.'
    return t


_V16_TABLES = V16.tables
_V16_STATS = V16.stats


def stats(d):          # noqa: F811
    s = _V16_STATS(d)
    A = V16.load_class('approaches')
    s['appr_client_personal'] = sum(1 for i in V16.approach_ids(d) if A[i]['client_tier']['value'] == 'personal device')
    return s


# ------------------------------------------------------------------ the six ledger-based designs added in V17
# Reviewer's short forms of their V17 classification records (_src/V17/classify/approaches/<ID>.json).
NO = V16.NO
V16.LEDGER_ROLES.update({
    'O102': ('Public Ethereum (testnet); PoS', 'A R V E'),
    'O104': ('Permissioned Geth; PBFT; oracles', 'R V E'),
    'O105': ('Smart contracts; chain not named', 'R V E'),
    'O107': ('Chain not named (miners)', 'R V'),
    'O108': ('Local Ethereum test chain', 'R V'),
    'O109': ('Smart contract; chain not named', 'A R'),
})
V16.DEPLOY.update({   # ledger runs on; costs measured on; data; clients; runs; attacks implemented
    'O102': ('public Ethereum testnet', 'PC', 'none named (naive Bayes)', 'n.s.', 'n.s.', NO),
    'O104': ('four Geth nodes (PBFT)', 'laptop', 'MNIST', '5', '30 (proofs)', NO),
    'O105': ('contracts (not deployed)', 'cloud VM', 'MNIST, CIFAR-10, Criteo', '5–8', 'n.s.', 'Byzantine, backdoor'),
    'O107': ('chain not named', 'GPU (Tesla T4)', 'CIFAR-10, Penn Treebank', '1–32', 'n.s.', NO),
    'O108': ('local Ethereum (Ganache)', 'n.s.', 'UCI sports activities', '2–50', '5', NO),
    'O109': ('chain not named', 'cloud VM', 'iris, house prices', 'n.s.', 'n.s.', NO),
})
V16.SEES.update({'O102': 'hidden', 'O104': 'clear', 'O105': 'clear', 'O107': 'clear', 'O108': 'clear', 'O109': 'hidden'})

# proof toolkits of the V17 designs (Halo2, circom, ZoKrates are already matched; Nova is new)
V16.ZK_TOOLS = V16.ZK_TOOLS + '|nova|bellman'


def t_gaps17(d, s):
    g = V16.t_gaps(d, s)
    g['rows'][0][1] = ('In most compared approaches, a party that sees the updates or servers that must not collude check them; '
                       'seven rest on proofs, which mostly cover the aggregation or the training of very small models, often '
                       'need a trusted set-up, and are not measured on IoT devices')
    return g


def t_concordance17(d, s):
    t = V16.t_concordance(d, s)
    for r in t['rows']:
        if r[0].startswith('Checking updates remains open'):
            r[2] = (f"{s['appr_content']} approaches check the content of each update, {s['appr_content_clear']} of them in "
                    'the clear; three check hidden updates with proofs [@N015; @O102; @O109]')
    return t


def t_crosstab17(d, s):
    # '*' would open an italic run once two proof-based studies share a cell, so V17 marks them with a dagger
    t = V16.t_crosstab(d, s)
    t['rows'] = [[c.replace(']*', ']†') if isinstance(c, str) else c for c in r] for r in t['rows']]
    t['note'] = t['note'].replace('* = ', '† = ')
    return t


def tables(d, s):      # noqa: F811
    t = _V16_TABLES(d, s)
    t['keywords'] = t_keywords17()
    t['gaps'] = t_gaps17(d, s)
    t['concordance'] = t_concordance17(d, s)
    t['crosstab'] = t_crosstab17(d, s)
    who = '(organisation = hospitals, firms or other silos)'
    assert who in t['deploy']['note']
    t['deploy']['note'] = t['deploy']['note'].replace(
        who, '(organisation = hospitals, firms or other silos; personal device = phones, tablets or computers)')
    return t
