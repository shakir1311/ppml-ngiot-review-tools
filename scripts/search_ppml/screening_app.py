#!/usr/bin/env python3
"""PPML Screening — the author's app for the title-and-abstract screening of the PPML review (primary and secondary
studies, criteria search-ppml/CRITERIA-V2-2026-10-04.md).

The author screens every record himself (4 October 2026: "a python app that loads the MD - let me see each abstract and
record my decision (with comments) - the python app will become the centre of my decisions"). The app decides nothing:
it shows each record, highlights words, offers four questions whose answers are pre-filled by a fixed rule on cue words
(scripts/search_ppml/prefill.py -> search-ppml/PREFILL-2026-10-04.csv; the author chose a script rule, not language-model
suggestions), and records what the author decides. The author: "i am the one who verifies them and then i am the one who
will click include/exclude/unsure ... the app should auto advance to next item once i decide. and if i dont change your
proposed answers - they should still be recorded as provided by me". So a decision stores the answers shown as the
author's answers and moves to the next record; the log also notes which pre-filled answers the author left unchanged.

  reads   search-ppml/ABSTRACTS-FOR-AUTHOR-V<n>-2026-10-04.md (the newest version; never written by the app)
  writes  search-ppml/AUTHOR-DECISIONS-2026-10-04.csv        the current decision of every record the author touched:
                                                             decision, code, the five answers (type = primary, secondary,
                                                             neither or unsure), comment, time
          search-ppml/AUTHOR-DECISIONS-LOG-2026-10-04.jsonl  every change, with its time (append only)

Decisions are keyed by the record number of search-ppml/MERGED-RECORDS-2026-10-04.csv; title and DOI are stored too,
and the app warns when a stored decision no longer matches its record.

Run:        open "search-ppml/PPML Screening.app"
            or <python with PySide6> scripts/search_ppml/screening_app.py [--md FILE] [--filter KEY]   (e.g. --filter known)
Full text:  ... screening_app.py --fulltext   the included studies, with summary, notes and PDF; the author's screening answers
            pre-filled; Include, or Exclude with a reason (required); writes search-ppml/AUTHOR-FULLTEXT-2026-10-05.csv and its log
Second screening: ... screening_app.py --rescreen   the 147 full texts of the full second screening (borderline first), each with the
            AI's full-text proposal, its summary, notes, PDF and assessment record; Include, or Exclude with a reason; writes
            search-ppml/evidence/rescreen/AUTHOR-RESCREEN-DECISIONS-2026-10-05.csv and its log
S-ZK:       ... screening_app.py --szk   the supplementary search S-ZK (the searches of 2 October 2026 with ledger and ZKP
            terms; scripts/search_ppml/szk.py): its own reading file and pre-fill, and its own decisions in
            search-ppml/evidence/szk-search/AUTHOR-DECISIONS-S-ZK.csv and its log
Self-test:  <python> scripts/search_ppml/screening_app.py --self-test OUTDIR   (offscreen; decisions go to OUTDIR)
Guide:      <python> scripts/search_ppml/screening_app.py --guide          (writes search-ppml/SCREENING-GUIDE-V7-2026-10-04.html)
"""
import csv, datetime, html, json, os, pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
P = ROOT / 'search-ppml'
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import strings as S                                   # noqa: E402

if '--self-test' in sys.argv or '--guide' in sys.argv:
    os.environ['QT_QPA_PLATFORM'] = 'offscreen'

from PySide6.QtCore import Qt, QTimer, QSettings, QLockFile, QUrl                                       # noqa: E402
from PySide6.QtGui import QDesktopServices, QKeySequence, QPalette, QShortcut, QColor, QBrush           # noqa: E402
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QSplitter, QListWidget, QListWidgetItem,  # noqa: E402
                               QLineEdit, QComboBox, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QPushButton,
                               QTextBrowser, QPlainTextEdit, QTabWidget, QMessageBox, QFrame, QScrollArea, QSizePolicy)

DECISIONS = P / 'AUTHOR-DECISIONS-2026-10-04.csv'
LOG = P / 'AUTHOR-DECISIONS-LOG-2026-10-04.jsonl'
GUIDE = P / 'SCREENING-GUIDE-V7-2026-10-04.html'
SUGGESTIONS = P / 'PREFILL-2026-10-04.csv'
# the full-text stage (--fulltext): the included studies, the author's screening answers as the pre-fill, separate files
INCLUDED = P / 'INCLUDED-STUDIES-2026-10-04.csv'
FT_DECISIONS = P / 'AUTHOR-FULLTEXT-2026-10-05.csv'
FT_LOG = P / 'AUTHOR-FULLTEXT-LOG-2026-10-05.jsonl'
CHECKS = P / 'DECISION-CHECK-2026-10-05.csv'          # check_decisions.py: answers to look at again (full-text mode)
# the full texts of the full second screening (--rescreen): the AI's proposals shown, the author's decisions in separate files
RS = P / 'evidence' / 'rescreen'
RS_TABLE = RS / 'RESCREEN-FULLTEXT-2026-10-05.csv'
RS_DECISIONS = RS / 'AUTHOR-RESCREEN-DECISIONS-2026-10-05.csv'
RS_LOG = RS / 'AUTHOR-RESCREEN-LOG-2026-10-05.jsonl'
# the supplementary search S-ZK (--szk): its own reading file, pre-fill and decision files (scripts/search_ppml/szk.py)
SZK = P / 'evidence' / 'szk-search'
SZK_DECISIONS = SZK / 'AUTHOR-DECISIONS-S-ZK.csv'
SZK_LOG = SZK / 'AUTHOR-DECISIONS-S-ZK-LOG.jsonl'
szk_newest = lambda pattern: sorted(SZK.glob(pattern))[-1]
# the author, 12 October 2026: "please select the default for include/exclude/unsure based on your judgement. and i will verify
# that" — Claude's suggestions for every S-ZK record (search-ppml/evidence/szk-search/claude/, scripts/search_ppml/szk_suggestions.py):
# answers and a decision, shown pre-selected with a dashed border; nothing counts as decided until the author confirms it
SZK_CLAUDE = 'SUGGESTIONS-S-ZK-CLAUDE-*.csv'
EC9_AT_SCREENING = False          # criteria V9 (a primary study builds on a ledger) applied at screening: S-ZK only
FIELDS = ['n', 'section', 'search', 'decision', 'code', 'type', 'privacy', 'focus', 'focus_parts', 'zk_proves', 'ngiot', 'learning', 'comment', 'decided_at',
          'title', 'doi', 'in_corpus']        # learning: asked until criteria V3; kept so that earlier answers stay on record
ANSWER_KEYS = ('type', 'privacy', 'focus', 'ngiot')
# "Is it a full paper?" is not asked per record (the author, 4 October 2026: "how can i decide on that?"); records whose title
# announces an editorial, notice or talk are removed before screening by merge.py ("just remove that are not full papers")

# ---------------------------------------------------------------------------------------------------------------- rules
YES3 = [('yes', 'Yes'), ('unsure', "Can't tell"), ('no', 'No')]
PRIVACY_PRIMARY = ('Is privacy part of its own contribution?',
                   'It adds a privacy mechanism to the learning (differential privacy, homomorphic encryption, secure multi-party computation '
                   'or secret sharing, secure aggregation, trusted execution, anonymisation, masked or encrypted updates, zero-knowledge proofs '
                   'that show something about the data or the update without revealing it) or analyses privacy '
                   'attacks or leakage. Federated learning alone — the raw data stay on the device — is No.')
PRIVACY_SECONDARY = ('Does the survey treat privacy?',
                     'The abstract says the survey examines, reviews or analyses privacy (threats, protection, techniques), alone or among '
                     'other topics. Privacy only as background, motivation, one challenge or a future direction is No; so are security-only surveys.')
QUESTIONS = [   # (key, question, code when No, hint, answers)
    ('type', 'What kind of study is it?', 'NOT-A-STUDY',
     'Primary: it proposes, builds or evaluates a method, system, protocol or attack, or measures privacy leakage. Secondary: a survey, '
     'systematic review or mapping study, SoK, or a tutorial or overview that reviews the literature (a review that adds a framework or '
     'small benchmark is still secondary). Neither: a position or vision paper that does neither.',
     [('primary', 'Primary'), ('secondary', 'Secondary'), ('neither', 'Neither'), ('unsure', "Can't tell")]),
    ('privacy', 'Is privacy treated (survey) or part of its own contribution (primary)?', 'PRIVACY-INCIDENTAL',
     PRIVACY_SECONDARY[1] + ' — For a primary study: ' + PRIVACY_PRIMARY[1], YES3),
    ('focus', 'Which PhD angles does it deal with?', 'OFF-FOCUS',
     'The PhD focus (criteria V4). Tick every angle the study deals with as part of its contribution — not a word in passing. For a '
     'primary study, None of these → OFF-FOCUS; for a survey the ticks are recorded and never exclude it.',
     [('no', 'None of these'), ('unsure', "Can't tell")]),
    ('ngiot', 'Is an NG-IoT setting a stated focus?', 'NO-NGIOT',
     'IoT together with a next-generation enabler — 5G/6G, edge, fog or MEC — and the settings built on them (IIoT, IoMT, IoV, smart '
     'grid, smart city, UAVs, communication networks), covered by the study (criteria V8: a strict stated focus is not required).', YES3),
]
CODES = [
    ('NOT-A-STUDY', 'Neither primary nor secondary: a position, vision or opinion paper with no method, system or evaluation of its own that does not review the literature'),
    ('NOT-FULL-PAPER', 'Editorial, preface, panel, workshop or conference summary, poster, extended abstract, erratum, thesis, book or chapter'),
    ('PRIVACY-INCIDENTAL', 'Survey: privacy absent, background, one challenge or a future direction; security-only. Primary: no privacy mechanism or privacy analysis of its own (federated learning alone)'),
    ('OFF-FOCUS', 'Primary study outside the PhD focus: no threat to the learning (poisoning, malicious or fake participants, free riding), no verification of the learning, no blockchain'),
    ('NO-LEARNING', 'Learning is not a subject (e.g. IoT security, blockchain for IoT, 5G networks without machine learning)'),
    ('NO-NGIOT', 'No NG-IoT setting as a stated focus (PPML in general, cloud, LLMs, medical data without devices or edge; IoT only one example)'),
    ('SURVEY-BEFORE-2024', 'A survey published before 2024 and cited fewer than 100 times in Scopus or IEEE Xplore at the search date (date rule)'),
    ('NOT-FINAL-VERSION', 'Only an unedited early-access copy exists; the final published version is not available'),
    ('NO-BLOCKCHAIN', 'Primary study without a blockchain or distributed ledger in its design (criteria V9)'),
    ('OTHER', 'Not English, a preprint, a retraction notice, or published before 2020 — say which in the comment'),
]
FOCUS_PARTS = [   # (name as in merge.FOCUS_PARTS, button, what "deals with" means)
    ('poisoning', 'Poisoning',
     'Data or model poisoning, backdoors, label flipping: the study defends against, detects, or mounts such an attack on the learning.'),
    ('malicious or fake participants', 'Malicious / fake participants',
     'Byzantine or malicious clients, Sybil or fake nodes inserted into training, dishonest aggregators: the study detects, excludes, '
     'authenticates or tolerates them.'),
    ('free riding', 'Free riding',
     'Participants who take the model without contributing: the study measures contributions, proves that training was done, or '
     'penalises free riders.'),
    ('verification', 'Verification (other means)',
     'Checking that training, updates or aggregation are correct by means other than zero-knowledge proofs: verifiable aggregation with '
     'commitments or homomorphic hashes, committee or consensus checks, TEE attestation, auditable learning.'),
    ('zero-knowledge proofs', 'Zero-knowledge proofs',
     'The study uses zero-knowledge proofs (zk-SNARKs, zk-STARKs, Bulletproofs …) to prove something about the learning — training, '
     'updates, aggregation, identity or inference — without revealing the data or the update.'),
    ('blockchain', 'Blockchain',
     'The design builds on a blockchain or distributed ledger (smart contracts, consensus, on-chain records) — not blockchain named only '
     'as background or future work.'),
    ('ZK on blockchain', 'ZK proofs checked on-chain',
     'The zero-knowledge proofs are verified on the blockchain — by a smart contract or by the ledger\'s validators — or zero-knowledge '
     'is built into the ledger (zk-rollups, ZK-based consensus). Not when proofs are checked off-chain by a server.'),
]
ZK_PROVES = [   # follow-up when zero-knowledge proofs are ticked (optional, recorded; not used to decide)
    ('training', 'Training was done'), ('bounded', 'Update well-formed / bounded'), ('similarity', 'Update similar to others'),
    ('aggregation', 'Aggregation correct'), ('identity', 'Identity / membership'), ('inference', 'Inference correct'), ('other', 'Other'),
]
PART_ORDER = [p for p, _, _ in FOCUS_PARTS]
SURVEYS_FROM, FOUNDATIONAL_CITES = 2024, 100     # criteria V5: surveys before 2024 out unless cited >= 100 at the search date


def date_rule(r, kind):
    """a survey published before 2024 and cited fewer than 100 times (or no count on record) — excluded by default"""
    return kind == 'secondary' and r['year'] and r['year'] < SURVEYS_FROM and (r['cited'] is None or r['cited'] < FOUNDATIONAL_CITES)


DEC_LABEL = {'INCLUDE': 'Include', 'UNSURE': 'Unsure', 'EXCLUDE': 'Exclude'}
MARK = {'': '○', 'INCLUDE': '✔', 'UNSURE': '◐', 'EXCLUDE': '✕'}
TYPE_LABEL = {'primary': 'primary', 'secondary': 'secondary', 'neither': 'neither', 'unsure': "can't tell"}


# --------------------------------------------------------------------------------------------------------- highlighting
def term_pattern(term):
    """a search term as a regular expression on the original text: case-insensitive, hyphen or space alike, ? and * as wildcards"""
    parts = [p for p in re.split(r'[^A-Za-z0-9?*]+', term.strip('"')) if p]
    part = lambda p: re.escape(p).replace(r'\?', '[A-Za-z0-9]').replace(r'\*', '[A-Za-z0-9]*')
    return r'(?<![A-Za-z0-9])' + r'[\s\-‐‑–/]*'.join(part(p) for p in parts) + r'(?![A-Za-z0-9])'


OBJ = r'(?:scheme|framework|model|method|approach|system|algorithm|architecture|protocol|mechanism)'
HIGHLIGHT = [   # (key, legend, colour light, colour dark, patterns); longer spans win, then the earlier group
    ('own', 'own work: method, results (question 1: primary)', '#ffd8a8', '#6b4210',
     [r'\bwe (?:propose|present|design|develop|implement|introduce)\w*', r'\bthis (?:paper|article|study|work) (?:proposes|presents|designs|develops|introduces)\b',
      r'\b(?:is|are) proposed\b', r'\b(?:our|the) proposed ' + OBJ + r's?\b', r'\bour (?:novel )?' + OBJ + r's?\b', r'\ba novel ' + OBJ + r'\b',
      r'\b(?:experimental|simulation|numerical) results\b', r'\bexperiments (?:show|demonstrate)\w*', r'\boutperform\w*', r'\baccuracy of \d']),
    ('review', 'review words (question 1: secondary)', '#cfe2ff', '#1d3a63',
     [term_pattern(t) for t in S.SUR] + [r'\bPRISMA\b', r'\bliterature\b', r'\bwe (?:review|survey|summari[sz]e|categori[sz]e|classify)\w*',
                                         r'\bthis (?:survey|review)\b', r'\breviewed\b', r'\bsurveyed\b']),
    ('privacy', 'privacy (question 2)', '#c9f0cf', '#1d4d2a',
     [term_pattern(t) for t in S.PPML] + [term_pattern(t) for t in ('private', 'confidential*', 'anonymi*', 'inference attack*', 'membership inference',
                                                                      'model inversion', 'gradient leakage', 'secret sharing', 'trusted execution', 'GDPR')]),
    ('threat', 'PhD angles (question 3)', '#ffd3df', '#5c2433',
     [term_pattern(t) for t in S.THREAT] + [term_pattern(t) for t in ('verifiab*', 'verification', 'auditab*', 'zero-knowledge', 'ZKP', 'zk-SNARK*',
                                                                      'blockchain*', 'block-chain*', 'distributed ledger*', 'smart contract*', 'fake node*',
                                                                      'free rid*', 'free-rid*')]),
    ('learning', 'learning', '#e6d9ff', '#3e2a66',
     [term_pattern(t) for t in S.ML] + [term_pattern(t) for t in ('artificial intelligence', 'neural network*', 'FL', 'ML', 'AI', 'learning')]),
    ('ngiot', 'NG-IoT setting (question 4)', '#c8eeee', '#164a4a',
     [term_pattern(t) for t in S.NGIOT] + [term_pattern(t) for t in ('UAV*', 'drone*', 'V2X', 'cyber-physical', 'CPS', 'IoTs', 'edge', 'fog',
                                                                      'healthcare', 'smart home*', 'wearable*', 'sensor*', 'wireless')]),
]
COMPILED = [(k, re.compile('|'.join(f'(?:{p})' for p in pats), re.I)) for k, _, _, _, pats in HIGHLIGHT]


def highlight(text, dark):
    """HTML of text with every highlight span marked; longer spans win, then the earlier group"""
    spans = []
    for rank, (key, rx) in enumerate(COMPILED):
        spans += [(m.start(), -(m.end() - m.start()), rank, m.end(), key) for m in rx.finditer(text) if m.end() > m.start()]
    spans.sort()
    colour = {k: (cd if dark else cl) for k, _, cl, cd, _ in HIGHLIGHT}
    out, pos = [], 0
    for start, _, _, end, key in spans:
        if start < pos:
            continue
        out.append(html.escape(text[pos:start]))
        out.append(f'<span style="background-color:{colour[key]}">{html.escape(text[start:end])}</span>')
        pos = end
    out.append(html.escape(text[pos:]))
    return ''.join(out)


def legend_html(dark):
    return ' '.join(f'<span style="background-color:{cd if dark else cl}">&nbsp;{html.escape(lab)}&nbsp;</span>' for _, lab, cl, cd, _ in HIGHLIGHT)


# ---------------------------------------------------------------------------------------------------------------- data
REC = re.compile(r'^## (\d+)\. (.*)$')
FIELD = re.compile(r'^- \*\*(.+?):\*\* ?(.*)$')


def newest_md():
    files = sorted(P.glob('ABSTRACTS-FOR-AUTHOR-V*-2026-10-04.md'), key=lambda f: int(re.search(r'-V(\d+)-', f.name).group(1)))
    return files[-1]


def parse_corpus(v):
    parts = v.split(' · ')
    paths = re.findall(r'`([^`]+)`', v)
    return {'id': parts[0], 'collection': parts[1] if len(parts) > 1 else '', 'kind': parts[2] if len(parts) > 2 else '',
            'how': parts[3] if len(parts) > 3 else '', 'pdf': paths[0] if paths else '',
            'also': [x.strip() for x in paths[1].split(';')] if len(paths) > 1 else []}


def load_md(path):
    text = path.read_text(encoding='utf-8')
    m = re.search(r'\*\*(\d+) records\*\* to screen', text)
    stated = int(m.group(1)) if m else None
    records, section, cur = [], 'screen', None
    for line in text.splitlines():
        if line.startswith('# In your corpus but set aside'):
            section, cur = 'aside', None
            continue
        if line.startswith('# Studies identified via other methods'):
            section, cur = 'known', None
            continue
        m = REC.match(line)
        if m:
            cur = {'n': int(m.group(1)), 'title': m.group(2).strip(), 'fields': {}, 'corpus': [], 'abstract': [], 'section': section}
            records.append(cur)
            continue
        if cur is None:
            continue
        f = FIELD.match(line)
        if f:
            if f.group(1) == 'In your corpus':
                cur['corpus'].append(parse_corpus(f.group(2)))
            else:
                cur['fields'][f.group(1)] = f.group(2)
        elif line.strip() and line.strip() != '---':
            cur['abstract'].append(line.strip())
    for r in records:
        r['abstract'] = ' '.join(r['abstract'])
        d = re.match(r'\[([^\]]+)\]', r['fields'].get('DOI', ''))
        r['doi'] = d.group(1) if d else ''
        r['search'] = r['fields'].get('Search', '')
        y = re.match(r'(\d{4})', r['fields'].get('Year · venue · type', ''))
        r['year'] = int(y.group(1)) if y else None
        c = re.match(r'(\d+)', r['fields'].get('Cited', ''))
        r['cited'] = int(c.group(1)) if c else None
        r['text'] = ' '.join([str(r['n']), r['title'], r['doi'], r['abstract'], r['fields'].get('Keywords', '')]).lower()
    return stated, records


flat = lambda t: re.sub(r'[^a-z0-9]', '', (t or '').lower())


def md_html(text):
    """a summary's markdown as simple HTML (headings, bullets, bold, italics)"""
    out, in_list = [], False
    for line in text.splitlines():
        s = html.escape(line.strip())
        s = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', s)
        s = re.sub(r'(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])', r'<i>\1</i>', s)
        if s.startswith('- '):
            out.append(('' if in_list else '<ul>') + f'<li>{s[2:]}</li>')
            in_list = True
            continue
        if in_list:
            out.append('</ul>')
            in_list = False
        if s.startswith('# '):
            out.append(f'<h3>{s[2:]}</h3>')
        elif s:
            out.append(f'<p>{s}</p>')
    return ''.join(out) + ('</ul>' if in_list else '')


def fulltext_records(md_path):
    """the included studies, in the order of the included-studies table, each with its summary, notes and PDF"""
    _, recs = load_md(md_path)
    by_n = {r['n']: r for r in recs}
    out = []
    for row in csv.DictReader(open(INCLUDED, encoding='utf-8')):
        r = dict(by_n[int(row['n'])])
        r['section'] = 'screen'
        summary = ROOT / row['summary'] if row['summary'] else None
        folder = summary.parent.parent if summary else None
        pdfs = sorted(folder.glob('*.pdf')) if folder else []
        r['ft'] = {'summary': summary, 'notes': folder / 'notes' / 'NOTES.md' if folder else None, 'pdf': pdfs[0] if pdfs else None,
                   'corpus_id': row['corpus_id']}
        out.append(r)
    return out


def rescreen_records():
    """the full texts of the full second screening: one per row of RESCREEN-FULLTEXT, borderline first, then proposed include,
    then proposed exclude; each with its summary, notes, PDF, the AI's full-text proposal and its pre-filled answers"""
    csv.field_size_limit(10 ** 9)
    merged = {r['n']: r for r in csv.DictReader(open(P / 'MERGED-RECORDS-2026-10-04.csv', encoding='utf-8'))}
    pop = {r['n']: r for r in csv.DictReader(open(RS / 'POPULATION-2026-10-05.csv', encoding='utf-8'))}
    rows = list(csv.DictReader(open(RS_TABLE, encoding='utf-8')))
    rows.sort(key=lambda x: (x['borderline'] != 'yes', x['decision'] != 'INCLUDE', int(x['n'])))
    out, sugg = [], {}
    for x in rows:
        m, n = merged[x['n']], int(x['n'])
        folder = (ROOT / pop[x['n']]['corpus_folder']) if x['id'].startswith('r') else ROOT / 'corpus' / 'ppmlcorpus' / 'check' / x['id']
        pdfs = [folder / f"{x['id']}.pdf"] if (folder / f"{x['id']}.pdf").exists() else sorted(folder.glob('*.pdf'))
        rec = json.loads((RS / 'fulltext' / f"{x['id']}.json").read_text(encoding='utf-8'))
        c = rec.get('conditions') or {}
        met = lambda k: {True: 'yes', False: 'no'}.get((c.get(k) or {}).get('met'), 'unsure')
        r = {'n': n, 'title': m['title'], 'abstract': m['abstract'] or '*(no abstract in the records)*', 'doi': m['doi'], 'corpus': [],
             'section': 'screen', 'search': f"excluded at screening by {pop[x['n']]['stratum']}", 'year': int(m['year'] or 0) or None,
             'cited': int(m['cited']) if m['cited'] else None,
             'fields': {'Year · venue · type': f"{m['year']} · {m['venue']} · {m['type']}", 'Keywords': m['keywords'],
                        'Found by': 'the full second screening', 'Why it matched': ''},
             'ft': {'summary': folder / 'notes' / 'SUMMARY.md', 'notes': folder / 'notes' / 'NOTES.md', 'pdf': pdfs[0] if pdfs else None,
                    'corpus_id': x['id'], 'record': RS / 'fulltext' / f"{x['id']}.json", 'proposal': x}}
        r['text'] = ' '.join([str(n), r['title'], r['doi'], r['abstract'], m['keywords']]).lower()
        out.append(r)
        sugg[n] = {'type': x['kind'] if x['kind'] in ('primary', 'secondary') else 'unsure', 'privacy': met('IC1'), 'focus': met('IC3'),
                   'ngiot': met('IC1'), 'focus_parts': x['angles'].replace('ZK on-chain', 'ZK on blockchain'), 'zk_proves': '',
                   'reason': 'Pre-filled from the AI full-text assessment (see the box above); change any answer you disagree with.'}
    return out, sugg


def screening_answers():
    """the author's answers at screening, as the pre-fill of the full-text stage"""
    out = {}
    for d in csv.DictReader(open(DECISIONS, encoding='utf-8')):
        if d['decision'] == 'INCLUDE':
            out[int(d['n'])] = {**{k: d.get(k, '') for k in ('type', 'privacy', 'focus', 'focus_parts', 'zk_proves', 'ngiot')},
                                'reason': 'Pre-filled with your answers at screening.'}
    return out


class Store:
    """the author's decisions: the current state in a CSV, every change in a log"""

    def __init__(self, records, csv_path=DECISIONS, log_path=LOG):
        self.csv_path, self.log_path = csv_path, log_path
        self.by_n = {r['n']: r for r in records}
        self.state, self.mismatch = {}, []
        if csv_path.exists():
            for row in csv.DictReader(open(csv_path, encoding='utf-8')):
                n = int(row['n'])
                if n in self.by_n and flat(row['title']) != flat(self.by_n[n]['title']):
                    self.mismatch.append(n)            # a record no longer shown (set aside by a later rule) keeps its row
                self.state[n] = {k: row.get(k, '') or '' for k in FIELDS}

    def get(self, n):
        return self.state.get(n) or {k: '' for k in FIELDS}

    def put(self, n, what, note=None, **changes):
        r = self.by_n[n]
        s = dict(self.get(n))
        if 'decision' in changes and changes['decision'] != s['decision']:
            s['decided_at'] = datetime.datetime.now().isoformat(timespec='seconds')
        s.update(changes)
        s.update({'n': str(n), 'section': r['section'], 'search': r['search'], 'title': r['title'], 'doi': r['doi'],
                  'in_corpus': '; '.join(c['id'] for c in r['corpus'])})
        if s['decision'] != 'EXCLUDE':
            s['code'] = ''
        self.state[n] = s
        self.write()
        with open(self.log_path, 'a', encoding='utf-8') as fh:
            fh.write(json.dumps({'time': datetime.datetime.now().isoformat(timespec='seconds'), 'n': n, 'changed': what,
                                 **({'note': note} if note else {}),
                                 **{k: s[k] for k in ('decision', 'code', *ANSWER_KEYS, 'focus_parts', 'zk_proves', 'comment')}},
                                ensure_ascii=False) + '\n')

    def write(self):
        tmp = self.csv_path.with_suffix('.tmp')
        with open(tmp, 'w', encoding='utf-8', newline='') as fh:
            w = csv.DictWriter(fh, fieldnames=FIELDS)
            w.writeheader()
            w.writerows(self.state[n] for n in sorted(self.state)
                        if any(self.state[n][k] for k in ('decision', *ANSWER_KEYS, 'comment')))
        os.replace(tmp, self.csv_path)

    def counts(self, section='screen'):
        ns = [n for n, r in self.by_n.items() if r['section'] == section]
        c = {'total': len(ns), 'INCLUDE': 0, 'UNSURE': 0, 'EXCLUDE': 0, 'no_code': 0, 'inc_primary': 0, 'inc_secondary': 0}
        for n in ns:
            s = self.get(n)
            if s['decision']:
                c[s['decision']] += 1
            if s['decision'] == 'EXCLUDE' and not s['code']:
                c['no_code'] += 1
            if s['decision'] == 'INCLUDE' and s['type'] in ('primary', 'secondary'):
                c['inc_' + s['type']] += 1
        c['decided'] = c['INCLUDE'] + c['UNSURE'] + c['EXCLUDE']
        return c


def asked(s):
    """the questions that decide: all four, for surveys too (criteria V6: a survey must also cover a PhD angle)"""
    return list(QUESTIONS)


def suggest(s, r=None):
    """the decision that follows from the author's own answers (and, for a survey, the date rule), or None"""
    if s['type'] == 'neither':
        return 'EXCLUDE', 'NOT-A-STUDY'
    if r is not None and date_rule(r, s['type']):
        return 'EXCLUDE', 'SURVEY-BEFORE-2024'
    qs = asked(s)
    for key, _, code, _, _ in qs[1:]:
        if s[key] == 'no':
            return 'EXCLUDE', code
    if EC9_AT_SCREENING and s['type'] == 'primary' and s['focus'] == 'yes' and 'blockchain' not in (s.get('focus_parts') or ''):
        return 'EXCLUDE', 'NO-BLOCKCHAIN'
    if all(s[k] for k, *_ in qs):
        return ('UNSURE', '') if any(s[k] == 'unsure' for k, *_ in qs) else ('INCLUDE', '')
    return None


# ------------------------------------------------------------------------------------------------------------------ UI
FILTERS = [('screen', 'All records to screen'), ('todo', 'Not yet decided'), ('INCLUDE', 'Include'), ('UNSURE', 'Unsure'),
           ('EXCLUDE', 'Exclude'), ('notype', 'Include or Unsure without the kind of study'),
           ('comment', 'With a comment'), ('daterule', 'Excluded by default: date rule (surveys before 2024)'),
           ('nofocus', 'Excluded by default: no PhD angle'), ('zkinc', 'Included, with zero-knowledge proofs'),
           ('flagged', 'Flagged by the decision check (full text)'), ('arm-survey', 'Found by the survey search'), ('arm-primary', 'Found by the primary-study search'),
           ('t-primary', 'You said: primary'), ('t-secondary', 'You said: secondary'),
           ('corpus', 'In your corpus'), ('known', 'Identified via other methods'), ('aside', 'Set aside, in your corpus')]
CLAUDE_FILTERS = [('sg-INCLUDE', 'Claude suggested: include'), ('sg-UNSURE', 'Claude suggested: unsure'),
                  ('sg-EXCLUDE', 'Claude suggested: exclude'), ('sg-changed', 'You decided otherwise than Claude suggested')]
RS_FILTERS = [('screen', 'All full texts of the second screening'), ('rs-borderline', 'Flagged borderline by the AI reader'),
              ('rs-include', 'AI proposed: include'), ('rs-exclude', 'AI proposed: exclude'), ('todo', 'Not yet decided by you'),
              ('INCLUDE', 'You: include'), ('EXCLUDE', 'You: exclude'), ('comment', 'With a comment'),
              ('t-primary', 'Primary studies'), ('t-secondary', 'Surveys')]

BUTTON_CSS = """
QPushButton[role="ans"], QPushButton[role="dec"] { border: 1px solid palette(mid); border-radius: 4px; padding: 4px 8px; background: palette(button); }
QPushButton[role="ans"]:hover, QPushButton[role="dec"]:hover { border-color: palette(highlight); }
QPushButton[role="ans"][val="yes"]:checked, QPushButton[role="ans"][val="primary"]:checked, QPushButton[role="ans"][val="secondary"]:checked
    { background: #2e7d32; color: white; border-color: #2e7d32; }
QPushButton[role="ans"][val="unsure"]:checked { background: #b26a00; color: white; border-color: #b26a00; }
QPushButton[role="ans"][val="no"]:checked, QPushButton[role="ans"][val="neither"]:checked { background: #c62828; color: white; border-color: #c62828; }
QPushButton[role="ans"][sug="1"]:checked, QPushButton[role="dec"][sug="1"]:checked { border: 2px dashed palette(text); }
QPushButton[role="dec"] { padding: 7px 10px; font-weight: 600; }
QPushButton[role="dec"][val="INCLUDE"]:checked { background: #2e7d32; color: white; border-color: #2e7d32; }
QPushButton[role="dec"][val="UNSURE"]:checked { background: #b26a00; color: white; border-color: #b26a00; }
QPushButton[role="dec"][val="EXCLUDE"]:checked { background: #c62828; color: white; border-color: #c62828; }
"""


def guide_html(dark):
    qs = ''.join(f'<li><b>{html.escape(q)}</b> {html.escape(h)} <i>No → {code}.</i></li>' for _, q, code, h, _ in QUESTIONS[1:])
    return f"""
<h3>How to decide</h3>
<p>The review takes <b>primary and secondary studies</b> on the privacy of machine learning in NG-IoT that deal with (surveys: cover) at
least one PhD angle: threats to the learning, verification of the learning, zero-knowledge proofs, or blockchain (criteria:
<code>search-ppml/CRITERIA-V8-2026-10-05.md</code>). Decide on what the <b>title, abstract and keywords</b> say, not on what
you know about the paper. Answer the four questions in order. They are optional — you can decide straight away with I, U or E — but they keep
decisions alike, and the app then shows the decision that follows from your answers.</p>
<ul>
<li><b>Neither</b> at question 1, or the first <b>No</b> after it, gives the exclusion code;</li>
<li>no No but a <b>Can't tell</b>: <b>Unsure</b> — the record goes on to the full text;</li>
<li>a kind of study and Yes to the rest (question 3 is asked of primary studies only): <b>Include</b>.</li>
</ul>
<p><b>When in doubt, Unsure.</b> Exclude only when the title and abstract make the reason clear. For every Include or Unsure, say
whether it is primary or secondary (question 1): the review reports the two apart.</p>
<ol>
<li><b>What kind of study is it?</b> Usually plain from the abstract: "we propose / we design / experiments show" is a primary study;
"this survey / we review / a systematic review of" is a secondary one. It is asked because the review reports the two apart and because
question 2 asks a different thing for each. {html.escape(QUESTIONS[0][3])} <i>Neither → NOT-A-STUDY.</i></li>
{qs}
</ol>
<p>Question 2 asks the right thing for each kind of study once question 1 is answered:</p>
<ul>
<li><b>Primary — is privacy part of its own contribution?</b> {html.escape(PRIVACY_PRIMARY[1])}</li>
<li><b>Secondary — does the survey treat privacy?</b> {html.escape(PRIVACY_SECONDARY[1])}</li>
</ul>
<p><b>The PhD angles (question 3).</b> Your proposal names data poisoning, malicious participants inserting
fake nodes, free riding and data integrity verification, and builds on blockchain. Tick every angle the study deals with as part of
its contribution; a word in the abstract is not enough. A plain privacy-preserving design with none of them is <b>None of these</b>
(OFF-FOCUS). The same holds for a <b>survey</b> (criteria V6): a survey that covers none of the angles is excluded. A record with no
angle ticked — by you or by the pre-fill — is marked <b>Exclude</b> by default (filter "Excluded by default: no PhD angle"); tick
an angle it covers, or click Include or Unsure, to keep it. The ticks also give the review's tables which angles each included
study and survey covers.</p>
<table cellspacing="0" cellpadding="3">{''.join(f'<tr><td><b>{html.escape(t)}</b></td><td>{html.escape(h)}</td></tr>' for _, t, h in FOCUS_PARTS)}</table>
<p>When <b>Zero-knowledge proofs</b> is ticked, the app also asks what the proof shows — training was done; the update is
well-formed or bounded; the update is similar to the others; the aggregation is correct; identity or membership; inference is
correct; other. This is optional and decides nothing; it gives detail for the "my research" or future-directions section, where
zero-knowledge is one direction (not the core of the PhD).</p>
<p>Not enough on its own: "secure against malicious attacks" in a list of claims; "blockchain could be used in future"; an incentive
scheme with no word on free riders; "verified by experiments" (that is testing, not verification of the learning).</p>
<p><b>Surveys before 2024 (the date rule, criteria V5).</b> A survey published before 2024 is excluded unless it is
foundational — cited at least 100 times in Scopus or IEEE Xplore at the search date. The field and its regulation have moved on
(the EU AI Act of 2024; the EDPB guidelines on blockchain of 2025). The app marks such surveys <b>Exclude</b> by default (dashed
border) without your having to open them; they are under the filter "Excluded by the date rule". You can still open one and click
Include or Unsure. If you say a pre-filled survey is in fact a primary study, the rule no longer applies to it.</p>
<p><b>Not a paper.</b> Records whose title announces an editorial, a keynote talk, a special-issue introduction or a retraction
notice were removed before screening. Should another non-paper appear (an extended abstract, a poster), exclude it.</p>
<p>Any other clear failure — not English (also an original-language title with an English abstract), a preprint, a retraction
notice, published before 2020 — is excluded too; a word in the comment helps you later.</p>

<h3>When to choose Unsure</h3>
<ul>
<li>You cannot tell whether a study adds privacy protection of its own or relies on federated learning alone (question 2, primary).</li>
<li>A survey of federated learning in an NG-IoT setting presents FL as privacy-preserving, but you cannot tell whether it analyses
privacy (question 2, secondary).</li>
<li>You cannot tell whether the paper reviews the literature or presents its own work (question 1).</li>
<li>You cannot tell whether the NG-IoT setting is a stated focus (question 4).</li>
</ul>

<h3>Examples</h3>
<ul>
<li>"we propose a federated intrusion detection system for IoT that preserves privacy by keeping data on the devices" — primary;
federated learning alone: question 2 No (PRIVACY-INCIDENTAL).</li>
<li>"… federated learning for IIoT with differential privacy added to the local updates" — primary; question 2 Yes.</li>
<li>"we show that gradients shared by IoT devices leak membership information" — primary (a privacy attack); question 2 Yes.</li>
<li>A survey that "examines key challenges related to data processing, privacy protection, and model performance" — question 2 Yes.</li>
<li>A survey where "privacy is a key challenge", nothing more — question 2 No.</li>
<li>"secure aggregation for federated learning in IIoT that also detects poisoned updates" — primary; questions 2 and 3 Yes.</li>
<li>"differentially private federated learning for smart-grid load forecasting", nothing on attacks, verification or blockchain —
primary; question 3 No (OFF-FOCUS).</li>
<li>A general machine-learning paper that lists IoT as one application among many — question 4 No (NO-NGIOT).</li>
</ul>

<h3>The full-text stage</h3>
<p>Opened with <code>run-screening-app.sh --fulltext</code>. It lists the included studies only. Each shows its summary, with links to
the PDF and the notes, above the record. Your answers at screening are pre-filled (dashed); correct them from the full text. Then
<b>Include</b> confirms the study, or <b>Exclude</b> removes it — at this stage PRISMA reports a reason for every excluded report, so
choose it from the menu when your answers do not already give one. The full-text decisions are kept apart from the screening decisions
(<code>search-ppml/AUTHOR-FULLTEXT-2026-10-05.csv</code> and its log).</p>

<h3>Reasons for exclusion</h3>
<p>You do not choose a reason. PRISMA 2020 asks for reasons only when a full text is excluded; at title-and-abstract screening the
flow diagram reports one number of records excluded. When your answers give a reason, the app records it anyway, for your own
overview: Neither → NOT-A-STUDY; privacy No → PRIVACY-INCIDENTAL; none of the PhD angles → OFF-FOCUS; NG-IoT No → NO-NGIOT; a
survey caught by the date rule → SURVEY-BEFORE-2024.</p>

<h3>Highlights</h3>
<p>{legend_html(dark)}</p>
<p>Highlights are word matches from the search blocks and a few cue words. They decide nothing: a highlighted "privacy" may be mere
background, and a survey may describe other people's methods in words that look like a primary study's.</p>

<h3>Papers you hold</h3>
<p>A gold banner and ★ mark records that are papers in your corpus (any collection, also the supervisors' papers). This is for
information only: a corpus paper meets the criteria or not like any other record. Corpus papers set aside by an automated rule are
under the filter "Set aside, in your corpus", apart from the records to screen. Ten corpus papers on the topic that
the searches did not return are under "Identified via other methods": assess them against the same criteria; they are reported in
their own box of the PRISMA flow.</p>

<h3>Keys</h3>
<p><b>P</b> primary · <b>S</b> secondary · <b>I</b> include · <b>U</b> unsure · <b>E</b> exclude ·
<b>⌘↩</b> use the decision from your answers and go on · <b>J</b> or <b>→</b> next · <b>K</b> or <b>←</b> previous · <b>N</b> next not
decided · <b>⌘F</b> search · <b>⌘+ / ⌘−</b> text size. Every change is saved at once.</p>
"""


class Window(QMainWindow):
    def __init__(self, md_path, store_paths=None, settings_name='PPMLScreening', suggestions_path=SUGGESTIONS, stage='screen'):
        super().__init__()
        self.md_path = md_path
        self.stage = stage
        self.rescreen = stage == 'rescreen'
        if self.rescreen:
            self.records, self.sugg = rescreen_records()
            self.stated = len(self.records)
            self.store = Store(self.records, *(store_paths or (RS_DECISIONS, RS_LOG)))
            self.checks = {}
            stage = self.stage = 'fulltext'                # the full-text screen: summary, PDF, notes; Exclude needs a reason
            for r in self.records:                        # decisions the author gave before the app showed these records
                if r['ft']['proposal'].get('author', '').startswith(('INCLUDE', 'EXCLUDE')) and not self.store.get(r['n'])['decision']:
                    a = r['ft']['proposal']['author']
                    dec, rest = a.split(' ', 1)
                    code = rest.split(':', 1)[0].strip() if dec == 'EXCLUDE' else ''
                    self.store.put(r['n'], 'decision', note='your earlier decision, entered for you', decision=dec, code=code,
                                   comment=rest.split(':', 1)[1].strip() if ':' in rest else '')
            self.by_n = {r['n']: r for r in self.records}
            for n in list(self.store.state):                 # exclusions made before reasons were filled in for the author
                s = self.store.get(n)
                if s['decision'] == 'EXCLUDE' and not s['code'] and n in self.by_n:
                    code, why = self.default_reason(n)
                    self.store.put(n, 'code', note=why + ' (filled in afterwards)', code=code)
        elif stage == 'fulltext':
            self.records = fulltext_records(md_path)
            self.stated = len(self.records)
            self.store = Store(self.records, *(store_paths or (FT_DECISIONS, FT_LOG)))
            self.sugg = screening_answers()
            self.checks = {}
            if CHECKS.exists():
                for c in csv.DictReader(open(CHECKS, encoding='utf-8')):
                    if c['status'] in ('CHECK', 'WEAK'):
                        self.checks.setdefault(int(c['n']), []).append(c)
        else:
            self.stated, self.records = load_md(md_path)
            self.store = Store(self.records, *(store_paths or ()))
            self.sugg = ({int(r['n']): r for r in csv.DictReader(open(suggestions_path, encoding='utf-8'))}
                         if suggestions_path.exists() else {})
        self.claude = bool(suggestions_path) and pathlib.Path(suggestions_path).name.startswith('SUGGESTIONS-S-ZK-CLAUDE')
        self.by_n = {r['n']: r for r in self.records}
        self.current = None
        self.loading = False
        self.dark = QApplication.palette().color(QPalette.ColorRole.Window).lightness() < 128
        self.settings = QSettings('Abertay', settings_name)
        self.setWindowTitle(f'PPML Full text — second screening, {len(self.records)} reports' if self.rescreen else
                            f'PPML Full text — {len(self.records)} included studies' if stage == 'fulltext' else
                            f'PPML Screening — supplementary search S-ZK, {len(self.records)} records'
                            + (' (with suggestions by Claude to verify)' if self.claude else '') if md_path.name.startswith('ABSTRACTS-S-ZK') else
                            f'PPML Screening — {md_path.name}')
        self.setStyleSheet(BUTTON_CSS)
        self.build()
        self.comment_timer = QTimer(self, singleShot=True, interval=1200, timeout=self.save_comment)
        self.apply_filter()
        last = self.settings.value('last_n', type=int)
        self.select(last if last in self.by_n else self.records[0]['n'])
        geo = self.settings.value('geometry')
        if geo is not None:
            self.restoreGeometry(geo)
        else:
            self.resize(1500, 920)
        split = self.settings.value('splitter')
        if split is not None:
            self.splitter.restoreState(split)
        self.zoom = self.settings.value('zoom', 0, type=int)
        if self.zoom:
            self.view.zoomIn(self.zoom)

    # ---------------------------------------------------------------------------------------------------- layout
    def build(self):
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.setCentralWidget(self.splitter)

        left = QWidget()
        lv = QVBoxLayout(left)
        lv.setContentsMargins(8, 8, 4, 8)
        self.filter = QComboBox()
        for key, label in (RS_FILTERS if getattr(self, 'rescreen', False) else
                           FILTERS[:2] + CLAUDE_FILTERS + FILTERS[2:] if getattr(self, 'claude', False) else FILTERS):
            self.filter.addItem(label, key)
        self.filter.currentIndexChanged.connect(self.apply_filter)
        self.search = QLineEdit(placeholderText='Search title, abstract, DOI or number')
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self.apply_filter)
        self.list = QListWidget()
        self.list.setUniformItemSizes(True)
        self.list.setTextElideMode(Qt.TextElideMode.ElideRight)
        self.list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.list.currentItemChanged.connect(lambda cur, _: cur and self.select(cur.data(Qt.ItemDataRole.UserRole), from_list=True))
        self.shown = QLabel()
        self.shown.setStyleSheet('color: #888888;')
        self.progress = QLabel()
        self.progress.setWordWrap(True)
        for w in (self.filter, self.search, self.list, self.shown, self.progress):
            lv.addWidget(w)
        self.splitter.addWidget(left)

        mid = QWidget()
        mv = QVBoxLayout(mid)
        mv.setContentsMargins(4, 8, 4, 8)
        self.legend = QLabel(legend_html(self.dark))
        self.legend.setWordWrap(True)
        self.view = QTextBrowser()
        self.view.setOpenLinks(False)
        self.view.anchorClicked.connect(QDesktopServices.openUrl)
        self.view.document().setDefaultStyleSheet('h2{margin:0 0 6px 0} .meta{color:#777} td{padding:2px 6px 2px 0; vertical-align:top}')
        mv.addWidget(self.legend)
        mv.addWidget(self.view)
        self.splitter.addWidget(mid)

        self.tabs = QTabWidget()
        decide = QScrollArea()                     # a short window scrolls the panel instead of squashing its buttons
        decide.setWidget(self.build_decide())
        decide.setWidgetResizable(True)
        decide.setFrameShape(QFrame.Shape.NoFrame)
        decide.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.tabs.addTab(decide, 'Decide')
        guide = QTextBrowser()
        guide.setHtml(guide_html(self.dark))
        self.tabs.addTab(guide, 'How to decide')
        self.splitter.addWidget(self.tabs)
        self.splitter.setSizes([340, 720, 440])
        self.splitter.setStretchFactor(1, 1)

        keys = [('I', lambda: self.set_decision('INCLUDE')), ('U', lambda: self.set_decision('UNSURE')),
                ('E', lambda: self.set_decision('EXCLUDE')), ('P', lambda: self.set_answer('type', 'primary', toggle=False)),
                ('S', lambda: self.set_answer('type', 'secondary', toggle=False)), ('J', self.next), ('Right', self.next),
                ('K', self.prev), ('Left', self.prev), ('N', self.next_todo), ('Ctrl+Return', self.use_suggestion),
                ('Ctrl+F', self.search.setFocus), ('Ctrl+=', lambda: self.zoom_by(1)), ('Ctrl++', lambda: self.zoom_by(1)),
                ('Ctrl+-', lambda: self.zoom_by(-1))]
        for seq, fn in keys:
            QShortcut(QKeySequence(seq), self, activated=fn)

    def build_decide(self):
        w = QWidget()
        v = QVBoxLayout(w)
        self.where = QLabel()
        self.where.setStyleSheet('font-weight:600;')
        v.addWidget(self.where)
        self.sug_note = QLabel()
        self.sug_note.setWordWrap(True)
        v.addWidget(self.sug_note)
        grid = QGridLayout()
        grid.setColumnStretch(0, 1)
        self.answer_buttons, self.question_labels = {}, {}
        for i, (key, q, code, hint, answers) in enumerate(QUESTIONS):
            lab = QLabel(f'<b>{i + 1}. {html.escape(q)}</b>')
            lab.setToolTip(hint)
            lab.setWordWrap(True)
            self.question_labels[key] = lab
            row = QHBoxLayout()
            row.setSpacing(4)
            for val, text in answers:
                b = QPushButton(text, checkable=True)
                b.setProperty('role', 'ans')
                b.setProperty('val', val)
                b.setFocusPolicy(Qt.FocusPolicy.NoFocus)
                b.setToolTip(f'{text} → {code}' if val in ('no', 'neither') else hint)
                b.clicked.connect(lambda _=False, k=key, x=val: self.set_answer(k, x))
                row.addWidget(b)
                self.answer_buttons[(key, val)] = b
            row.addStretch(1)
            grid.addWidget(lab, 2 * i, 0)
            if key == 'focus':
                box = QVBoxLayout()
                parts = QGridLayout()
                parts.setSpacing(4)
                self.part_buttons = {}
                for j, (name, text, hint_p) in enumerate(FOCUS_PARTS):
                    b = QPushButton(text, checkable=True)
                    b.setProperty('role', 'ans')
                    b.setProperty('val', 'yes')
                    b.setFocusPolicy(Qt.FocusPolicy.NoFocus)
                    b.setToolTip(hint_p)
                    b.clicked.connect(lambda _=False, x=name: self.set_focus_part(x))
                    parts.addWidget(b, j // 2, j % 2)
                    self.part_buttons[name] = b
                box.addLayout(parts)
                self.zk_label = QLabel('<span style="color:gray">What does the ZK proof show? (optional, recorded)</span>')
                box.addWidget(self.zk_label)
                zk = QGridLayout()
                zk.setSpacing(4)
                self.zk_buttons = {}
                for j, (key_z, text_z) in enumerate(ZK_PROVES):
                    b = QPushButton(text_z, checkable=True)
                    b.setProperty('role', 'ans')
                    b.setProperty('val', 'yes')
                    b.setFocusPolicy(Qt.FocusPolicy.NoFocus)
                    b.clicked.connect(lambda _=False, x=key_z: self.set_zk_proves(x))
                    zk.addWidget(b, j // 2, j % 2)
                    self.zk_buttons[key_z] = b
                box.addLayout(zk)
                box.addLayout(row)
                grid.addLayout(box, 2 * i + 1, 0)
            else:
                grid.addLayout(row, 2 * i + 1, 0)
        v.addLayout(grid)
        self.suggestion = QLabel()
        self.suggestion.setWordWrap(True)
        self.use = QPushButton('Use it and go on  (⌘↩)')
        self.use.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.use.clicked.connect(self.use_suggestion)
        sv = QHBoxLayout()
        sv.addWidget(self.suggestion, 1)
        sv.addWidget(self.use)
        v.addLayout(sv)
        v.addWidget(QFrame(frameShape=QFrame.Shape.HLine))
        v.addWidget(QLabel('<b>Your decision</b>'))
        dv = QHBoxLayout()
        self.dec_buttons = {}
        for d, key in (('INCLUDE', 'I'), ('UNSURE', 'U'), ('EXCLUDE', 'E')):
            b = QPushButton(f'{DEC_LABEL[d]}  ({key})', checkable=True)
            b.setProperty('role', 'dec')
            b.setProperty('val', d)
            b.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            b.clicked.connect(lambda _=False, x=d: self.set_decision(x, toggle=True))
            dv.addWidget(b)
            self.dec_buttons[d] = b
        v.addLayout(dv)
        # no exclusion-code menu at screening (the author: "why do i need to select exclusion code? ... i dont want to do that"):
        # PRISMA 2020 asks for reasons only at the full-text stage, where the menu appears (pre-set from the answers)
        self.code = QComboBox()
        self.code.addItem('— reason for excluding (required at full text) —', '')
        for i, (c, desc) in enumerate(CODES):
            self.code.addItem(c, c)
            self.code.setItemData(i + 1, desc, Qt.ItemDataRole.ToolTipRole)
        self.code.activated.connect(lambda i: self.set_code(self.code.itemData(i)))
        self.code.setVisible(self.stage == 'fulltext')
        v.addWidget(self.code)
        self.code_hint = QLabel()
        self.code_hint.setWordWrap(True)
        self.code_hint.setStyleSheet('color: #888888;')
        v.addWidget(self.code_hint)
        self.warn = QLabel()
        self.warn.setWordWrap(True)
        self.warn.setStyleSheet('color:#c77700; font-weight:600;')
        v.addWidget(self.warn)
        v.addWidget(QLabel('<b>Comment</b> (saved as you type)'))
        self.comment = QPlainTextEdit(placeholderText='Why, what to check in the full text, anything you want to remember…')
        self.comment.setMinimumHeight(90)
        self.comment.textChanged.connect(lambda: None if self.loading else self.comment_timer.start())
        v.addWidget(self.comment, 1)
        nav = QHBoxLayout()
        for text, fn in (('◀ Previous', self.prev), ('Next ▶', self.next), ('Next not decided ▶▶', self.next_todo)):
            b = QPushButton(text)
            b.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            b.clicked.connect(fn)
            nav.addWidget(b)
        v.addLayout(nav)
        self.saved = QLabel()
        self.saved.setStyleSheet('color: #888888;')
        v.addWidget(self.saved)
        for b in w.findChildren(QPushButton):       # buttons keep their height; they never shrink to slivers
            b.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
            b.setMinimumHeight(b.fontMetrics().height() + (18 if b.property('role') == 'dec' else 14))
        return w

    # ---------------------------------------------------------------------------------------------------- list
    def by_rule(self, n):
        """the default Exclude, while the author has not decided: the date rule (a survey before 2024 cited < 100), else no PhD
        angle (the angles shown — the author's or the pre-fill — are none of these); returns the reason code or ''"""
        if self.stage == 'fulltext' or self.store.get(n)['decision']:
            return ''
        e, from_sug = self.effective(n)
        claude_keeps = self.claude and self.sugg.get(n, {}).get('decision') in ('INCLUDE', 'UNSURE') and 'type' in from_sug
        if date_rule(self.by_n[n], e['type']) and not claude_keeps:   # Claude found a citation count that may meet IC7
            return 'SURVEY-BEFORE-2024'
        if e['focus'] == 'no' and not (self.claude and 'focus' in from_sug):
            return 'OFF-FOCUS'
        return ''

    def shown_decision(self, n):
        """the decision shown: the author's, else the default of a rule"""
        s = dict(self.store.get(n))
        rule = self.by_rule(n)
        if rule:
            s['decision'], s['code'] = 'EXCLUDE', rule
        return s

    def counts(self, section):
        ns = [r['n'] for r in self.records if r['section'] == section]
        c = {'total': len(ns), 'INCLUDE': 0, 'UNSURE': 0, 'EXCLUDE': 0, 'inc_primary': 0, 'inc_secondary': 0, 'rule': 0}
        for n in ns:
            s = self.shown_decision(n)
            if s['decision']:
                c[s['decision']] += 1
            if s['decision'] == 'INCLUDE' and s['type'] in ('primary', 'secondary'):
                c['inc_' + s['type']] += 1
            c['rule'] += bool(self.by_rule(n))
        c['decided'] = c['INCLUDE'] + c['UNSURE'] + c['EXCLUDE']
        return c

    def matches_filter(self, r, key):
        s = self.shown_decision(r['n'])
        if key in ('aside', 'known'):
            return r['section'] == key
        if key == 'corpus':
            return bool(r['corpus'])
        if key.startswith('sg-'):
            g = self.sugg.get(r['n'], {})
            if key == 'sg-changed':
                return bool(self.store.get(r['n'])['decision']) and self.store.get(r['n'])['decision'] != g.get('decision')
            return g.get('decision') == key[3:]
        if key.startswith('rs-'):
            prop = r.get('ft', {}).get('proposal', {})
            return {'rs-borderline': prop.get('borderline') == 'yes', 'rs-include': prop.get('decision') == 'INCLUDE',
                    'rs-exclude': prop.get('decision') == 'EXCLUDE'}[key]
        if r['section'] != 'screen' and not (r['section'] == 'known' and key in ('zkinc', 'notype', 'INCLUDE')):
            return False
        return {'screen': True, 'todo': not s['decision'],
                'notype': s['decision'] in ('INCLUDE', 'UNSURE') and s['type'] not in ('primary', 'secondary'),
                'comment': bool(s['comment'].strip()),
                'arm-survey': r['search'] in ('survey search', 'both searches'),
                'arm-primary': r['search'] in ('primary-study search', 'both searches'),
                't-primary': s['type'] == 'primary', 't-secondary': s['type'] == 'secondary',
                'daterule': self.by_rule(r['n']) == 'SURVEY-BEFORE-2024', 'nofocus': self.by_rule(r['n']) == 'OFF-FOCUS',
                'zkinc': s['decision'] == 'INCLUDE' and 'zero-knowledge proofs' in s.get('focus_parts', ''),
                'flagged': any(c['status'] == 'CHECK' for c in getattr(self, 'checks', {}).get(r['n'], []))}.get(key, s['decision'] == key)

    def item_text(self, r):
        s = self.shown_decision(r['n'])
        star = '★ ' if r['corpus'] else ''
        flag = ''
        kind = {'primary': ' [P]', 'secondary': ' [S]'}.get(s['type'], '') if s['decision'] in ('INCLUDE', 'UNSURE') else ''
        if self.claude and not s['decision'] and self.sugg.get(r['n'], {}).get('decision'):
            flag = '→' + MARK[self.sugg[r['n']]['decision']]
        return f"{MARK[s['decision']]}{flag}  {star}{r['n']}.{kind} {r['title']}"

    def style_item(self, it, r):
        s = self.shown_decision(r['n'])
        it.setText(self.item_text(r))
        colours = {'INCLUDE': '#2e7d32' if not self.dark else '#81c784', 'UNSURE': '#b26a00' if not self.dark else '#ffb74d',
                   'EXCLUDE': '#888888'}
        it.setForeground(QBrush(QColor(colours[s['decision']])) if s['decision'] else QApplication.palette().text())
        if r['corpus']:
            it.setBackground(QBrush(QColor('#fff3c4' if not self.dark else '#4a3d10')))
        it.setToolTip(r['title'])

    def apply_filter(self):
        key = self.filter.currentData()
        q = self.search.text().strip().lower()
        self.list.blockSignals(True)
        self.list.clear()
        self.items = {}
        for r in self.records:
            if self.matches_filter(r, key) and (not q or q in r['text']):
                it = QListWidgetItem()
                it.setData(Qt.ItemDataRole.UserRole, r['n'])
                self.style_item(it, r)
                self.list.addItem(it)
                self.items[r['n']] = it
        self.list.blockSignals(False)
        self.shown.setText(f'{self.list.count():,} shown')
        if self.current in self.items:
            self.list.setCurrentItem(self.items[self.current])
        self.update_progress()

    def update_progress(self):
        c = self.counts('screen')
        a = self.counts('aside')
        k = self.counts('known')
        pct = 100 * c['decided'] / c['total'] if c['total'] else 0
        extra = f" (by default {c['rule']})" if c['rule'] else ''
        self.progress.setText(f"<b>Decided {c['decided']:,} of {c['total']:,}</b> ({pct:.1f}%)<br>"
                              f"include {c['INCLUDE']} ({c['inc_primary']} primary, {c['inc_secondary']} secondary) · "
                              f"unsure {c['UNSURE']} · exclude {c['EXCLUDE']}{extra}<br>"
                              f"other methods: {k['decided']} of {k['total']} decided · set aside, in your corpus: {a['decided']} of {a['total']} decided")

    # ---------------------------------------------------------------------------------------------------- record
    def select(self, n, from_list=False):
        if n == self.current:
            return
        self.save_comment()
        self.current = n
        self.settings.setValue('last_n', n)
        r = self.by_n[n]
        if not from_list and n in self.items:
            self.list.blockSignals(True)
            self.list.setCurrentItem(self.items[n])
            self.list.blockSignals(False)
        self.view.setHtml(self.record_html(r))
        self.view.verticalScrollBar().setValue(0)
        pos = list(self.items).index(n) + 1 if n in self.items else 0
        self.where.setText(f"Record {n}" + (f" · {pos:,} of {len(self.items):,} shown" if pos else ' · not in the list shown'))
        self.refresh_panel()

    def record_html(self, r):
        hl = lambda t: highlight(t, self.dark)
        f = r['fields']
        parts = []
        if self.stage == 'fulltext' and r.get('ft'):
            ft = r['ft']
            url = lambda p: QUrl.fromLocalFile(str(p)).toString()
            links = ' · '.join(x for x in (f"<a href='{url(ft['pdf'])}'>open the PDF</a>" if ft['pdf'] else '',
                                          f"<a href='{url(ft['notes'])}'>open the notes</a>" if ft['notes'] and ft['notes'].exists() else '') if x)
            parts.append(f"<table width='100%' cellpadding='8' bgcolor='{'#e3ecf7' if not self.dark else '#22334a'}'><tr><td>"
                         f"<b>Full text — {html.escape(ft['corpus_id'])}</b> · {links}<br><span style='font-size:small'>Read the paper (the notes "
                         "help), then confirm with Include or exclude it with a reason.</span></td></tr></table>")
            flags = getattr(self, 'checks', {}).get(r['n'], [])
            if flags:
                items = ''.join(f"<li><b>{html.escape(c['check'])}</b> — your answer: {html.escape(c['answer'])} — {c['status']}: "
                                f"{html.escape(c['evidence'][:260])}</li>" for c in flags)
                parts.append(f"<table width='100%' cellpadding='8' bgcolor='{'#fff0d6' if not self.dark else '#4a3510'}'><tr><td>"
                             f"<b>Decision check</b> (scripted; correct the answers it questions, or keep them):<ul>{items}</ul></td></tr></table>")
            prop = ft.get('proposal')
            if prop:
                col = ('#e6f4e6' if prop['decision'] == 'INCLUDE' else '#f7e3e3') if not self.dark else ('#1f3a22' if prop['decision'] == 'INCLUDE' else '#4a2222')
                badge = " · <b style='color:#b26a00'>BORDERLINE</b>" if prop.get('borderline') == 'yes' else ''
                rule = f" · changed by consistency rule {html.escape(prop['rule'])}" if prop.get('rule') else ''
                vnote = f"<br><i>{html.escape(prop['version_note'])}</i>" if prop.get('version_note') else ''
                parts.append(f"<table width='100%' cellpadding='8' bgcolor='{col}'><tr><td><b>AI full-text proposal: "
                             f"{html.escape(prop['decision'])}{(' — ' + html.escape(prop['code'])) if prop['code'] else ''}</b>{badge}{rule}"
                             f" · {html.escape(prop['kind'])} · angles: {html.escape(prop['angles'] or 'none')}<br>{html.escape(prop['reason'])}{vnote}"
                             f"<br><span style='font-size:small'><a href='{url(ft['record'])}'>open the assessment record</a> (every criterion with "
                             "its page and quotation) — the proposal decides nothing: Include or Exclude is yours.</span></td></tr></table>")
            if ft['summary'] and ft['summary'].exists():
                parts.append(md_html(ft['summary'].read_text(encoding='utf-8')))
            parts.append('<hr>')
        if r['section'] == 'known':
            parts.append(f"<table width='100%' cellpadding='8' bgcolor='{'#e3ecf7' if not self.dark else '#22334a'}'><tr><td>"
                         "<b>Identified via other methods</b> — a corpus paper on the topic that the database searches did not return. "
                         "Assess it against the same criteria; it is reported in its own box of the PRISMA flow.</td></tr></table><br>")
        if r['section'] == 'aside':
            parts.append(f"<table width='100%' cellpadding='8' bgcolor='{'#e0e0e0' if not self.dark else '#3a3a3a'}'><tr><td>"
                         f"<b>Set aside by an automated rule</b> — {html.escape(f.get('Status', '').replace('set aside by the automated rule — ', ''))}. "
                         "Your decision is kept apart from the records to screen.</td></tr></table><br>")
        for c in r['corpus']:
            links = ''.join(f" · <a href='{QUrl.fromLocalFile(str(ROOT / p)).toString()}'>open {'PDF' if i == 0 else 'copy ' + str(i + 1)}</a>"
                            for i, p in enumerate([c['pdf']] + c['also']) if p)
            parts.append(f"<table width='100%' cellpadding='8' bgcolor='{'#fff3c4' if not self.dark else '#4a3d10'}'><tr><td>"
                         f"<b>★ In your corpus: {html.escape(c['id'])}</b> — {html.escape(c['collection'])} · {html.escape(c['kind'])} · "
                         f"{html.escape(c['how'])}{links}<br><span style='font-size:small'>For information only: it decides nothing.</span>"
                         "</td></tr></table><br>")
        doi = f"<a href='https://doi.org/{html.escape(r['doi'])}'>{html.escape(r['doi'])}</a>" if r['doi'] else 'no DOI in the records'
        parts.append(f"<h2>{hl(r['title'])}</h2>")
        parts.append(f"<p class='meta'>Record {r['n']} · {html.escape(f.get('Year · venue · type', ''))}</p>")
        parts.append('<table>'
                     f"<tr><td><b>DOI</b></td><td>{doi}</td></tr>"
                     f"<tr><td><b>Search</b></td><td>{html.escape(r['search'])} — {html.escape(f.get('Found by', ''))}</td></tr>"
                     f"<tr><td><b>Matched</b></td><td>{html.escape(f.get('Why it matched', ''))}</td></tr>"
                     f"<tr><td><b>Keywords</b></td><td>{hl(f.get('Keywords', ''))}</td></tr></table>")
        ab = r['abstract']
        parts.append('<p><i>(no abstract in the records)</i></p>' if ab.startswith('*(no abstract') else
                     f"<p style='line-height:150%'>{hl(ab)}</p>")
        return ''.join(parts)

    def effective(self, n):
        """the answers shown: the author's where given, else the suggestion; and which ones are suggestions"""
        s = self.store.get(n)
        e, from_sug = dict(s), []
        g = self.sugg.get(n)
        if g:
            for k in ANSWER_KEYS:
                if not s[k] and g.get(k):
                    e[k] = g[k]
                    from_sug.append(k)
                    if k == 'focus':
                        e['focus_parts'] = g.get('focus_parts', '')
            if not s.get('zk_proves') and g.get('zk_proves') and 'zero-knowledge proofs' in e.get('focus_parts', ''):
                e['zk_proves'] = g['zk_proves']                 # what the ZK proof shows, pre-filled (cue words)
                from_sug.append('zk_proves')
        return e, from_sug

    def claude_pick(self, n):
        """Claude's suggested decision and reason code, while the author has neither decided nor changed one of its answers"""
        g = self.sugg.get(n) if self.claude else None
        if not g or not g.get('decision') or self.store.get(n)['decision']:
            return None
        from_sug = self.effective(n)[1]
        if any(k not in from_sug for k in ANSWER_KEYS if g.get(k)):
            return None
        return g['decision'], g.get('code', '')

    def refresh_panel(self):
        self.loading = True
        s, from_sug = self.effective(self.current)
        for (key, val), b in self.answer_buttons.items():
            b.setChecked(s[key] == val)
            b.setProperty('sug', '1' if key in from_sug and s[key] == val else '0')
            b.style().unpolish(b)
            b.style().polish(b)
        g = self.sugg.get(self.current)
        pick = self.claude_pick(self.current)
        if self.claude and g:
            self.sug_note.setText("<span style='color:gray'>Suggested by Claude (Anthropic) from the title, abstract and keywords: the "
                                  "answers and the decision with a dashed border. Check them and change any that are wrong; nothing counts "
                                  "as decided until you confirm it (⌘↩ takes the suggestion).</span>"
                                  + (f"<br><b>Claude:</b> {html.escape(g.get('reason', ''))}" if g.get('reason') else ''))
        elif from_sug:
            self.sug_note.setText("<span style='color:gray'>Answers with a dashed border were pre-filled by a rule that only looks for "
                                  "words — check them and change any that are wrong. Your decision records the answers shown as yours.</span>"
                                  + (f"<br><span style='color:gray'>{html.escape(g.get('reason', ''))}</span>" if g and g.get('reason') else ''))
        else:
            self.sug_note.setText('')
        q3 = {'primary': PRIVACY_PRIMARY, 'secondary': PRIVACY_SECONDARY}.get(s['type'])
        self.question_labels['privacy'].setText(f"<b>2. {html.escape(q3[0])}</b>" if q3 else
                                                '<b>2. Privacy</b> <span style="color:gray">— answer question 1 first: the question differs for '
                                                'primary and secondary studies</span>')
        self.question_labels['privacy'].setToolTip(q3[1] if q3 else QUESTIONS[1][3])
        survey = s['type'] == 'secondary'
        self.question_labels['focus'].setText(f"<b>3. {'Which PhD angles does the survey cover?' if survey else html.escape(QUESTIONS[2][1])}</b> "
                                              "<span style='color:gray'>(tick all that apply; none of these → excluded by default)</span>")
        chosen = [x for x in s.get('focus_parts', '').split('; ') if x]
        for name, b in self.part_buttons.items():
            b.setChecked(name in chosen)
            b.setProperty('sug', '1' if 'focus' in from_sug and name in chosen else '0')
            b.style().unpolish(b)
            b.style().polish(b)
        zk_on = 'zero-knowledge proofs' in chosen
        proves = [x for x in s.get('zk_proves', '').split('; ') if x]
        self.zk_label.setVisible(zk_on)
        for key_z, b in self.zk_buttons.items():
            b.setVisible(zk_on)
            b.setChecked(key_z in proves)
            b.setProperty('sug', '1' if 'zk_proves' in from_sug and key_z in proves else '0')
            b.style().unpolish(b)
            b.style().polish(b)
        stored = self.store.get(self.current)
        rule = self.by_rule(self.current)
        for d, b in self.dec_buttons.items():
            proposed = (bool(rule) and d == 'EXCLUDE') or (not rule and bool(pick) and pick[0] == d)
            b.setChecked(stored['decision'] == d or proposed)
            b.setProperty('sug', '1' if proposed else '0')
            b.style().unpolish(b)
            b.style().polish(b)
        if rule == 'SURVEY-BEFORE-2024':
            r = self.by_n[self.current]
            self.code_hint.setText(f"<b>Excluded by default — date rule:</b> a survey from {r['year']}, cited "
                                   f"{r['cited'] if r['cited'] is not None else 'an unknown number of'} times (needs 2024 or later, or at "
                                   "least 100 citations). Click Include or Unsure to keep it.")
        elif rule == 'OFF-FOCUS':
            self.code_hint.setText("<b>Excluded by default — no PhD angle:</b> none of the five angles is ticked. Tick the angles it covers "
                                   "(the default lifts), or click Include or Unsure.")
        elif pick and pick[0] == 'EXCLUDE' and pick[1]:
            self.code_hint.setText(f"Reason Claude suggests: {pick[1]}")
        else:
            self.code_hint.setText(f"Reason recorded from the answers: {stored['code']}" if stored['decision'] == 'EXCLUDE' and stored['code'] else '')
        if self.stage == 'fulltext':
            self.code.setEnabled(stored['decision'] == 'EXCLUDE')
            self.code.setCurrentIndex(max(0, self.code.findData(stored['code'])))
        if self.comment.toPlainText() != s['comment']:
            self.comment.setPlainText(s['comment'])
        sug = pick or suggest(s, self.by_n[self.current])
        if pick:
            self.suggestion.setText(f"Suggested by Claude: <b>{DEC_LABEL[pick[0]]}</b>" + (f" — {pick[1]}" if pick[1] else '')
                                    + (f" ({TYPE_LABEL[s['type']]})" if pick[0] != 'EXCLUDE' and s['type'] else ''))
        elif sug:
            self.suggestion.setText(f"From the answers shown: <b>{DEC_LABEL[sug[0]]}</b>" + (f" — {sug[1]}" if sug[1] else '')
                                    + (f" ({TYPE_LABEL[s['type']]})" if sug[0] != 'EXCLUDE' and s['type'] else ''))
        else:
            self.suggestion.setText('<span style="color:gray">Answer the questions to get the decision that follows from them.</span>')
        self.use.setEnabled(bool(sug))
        warn = []
        if s['decision'] in ('INCLUDE', 'UNSURE') and s['type'] not in ('primary', 'secondary'):
            warn.append('Say whether it is primary or secondary (P or S).' if s['decision'] == 'INCLUDE' or s['type'] != 'unsure' else '')
        if self.stage == 'fulltext' and stored['decision'] == 'EXCLUDE' and not stored['code']:
            warn.append('Choose the reason for excluding — PRISMA reports it at the full-text stage.')
        if s['code'] == 'OTHER' and not s['comment'].strip():
            warn.append('OTHER: say which reason in the comment.')
        g_pick = (g.get('decision'), g.get('code', '')) if (self.claude and g) else None
        if sug and s['decision'] and (s['decision'], s['code']) != sug and (s['decision'], s['code']) != g_pick:
            warn.append('Your decision differs from your answers (that is allowed; a comment helps later).')
        self.warn.setText(' '.join(w for w in warn if w))
        self.saved.setText(f"Decided {s['decided_at'].replace('T', ' ')}" if s['decided_at'] else 'Not decided yet')
        self.loading = False

    # ---------------------------------------------------------------------------------------------------- changes
    def changed(self, what, **kw):
        self.store.put(self.current, what, **kw)
        r = self.by_n[self.current]
        if self.current in self.items:
            self.style_item(self.items[self.current], r)
        self.refresh_panel()
        self.update_progress()

    def set_answer(self, key, val, toggle=True):
        s = self.store.get(self.current)
        new = '' if toggle and s[key] == val else val
        extra = {'focus_parts': ''} if key == 'focus' else {}
        self.changed(f'answer {key}', **{key: new}, **extra)

    def set_zk_proves(self, key_z):
        """tick or untick what the zero-knowledge proof shows (optional detail, recorded with the author's answers)"""
        proves = [x for x in self.effective(self.current)[0].get('zk_proves', '').split('; ') if x]   # the shown set, pre-fill included
        proves = [x for x in proves if x != key_z] if key_z in proves else proves + [key_z]
        self.changed('zk proves', zk_proves='; '.join(k for k, _ in ZK_PROVES if k in proves))

    def set_focus_part(self, name):
        """tick or untick one PhD angle; the parts shown (pre-filled or not) are the starting point"""
        e, _ = self.effective(self.current)
        parts = [x for x in e.get('focus_parts', '').split('; ') if x] if e['focus'] == 'yes' else []
        parts = [x for x in parts if x != name] if name in parts else parts + [name]
        parts = [x for x in PART_ORDER if x in parts]
        self.changed('answer focus part', focus='yes' if parts else 'no', focus_parts='; '.join(parts))   # unticking all = none of these

    def decide(self, what, decision, code):
        """record a decision with the answers shown (suggestions left unchanged become the author's answers) and move on;
        the reason of an Exclude is the one the answers give, or none (PRISMA asks for reasons only at full text)"""
        self.save_comment()
        e, from_sug = self.effective(self.current)
        note = f"pre-filled answers left unchanged: {', '.join(from_sug)}" if from_sug else None
        g = self.sugg.get(self.current) if self.claude else None
        if g and g.get('decision'):
            note = '; '.join(x for x in (note, f"Claude suggested {g['decision']}{(' ' + g['code']) if g.get('code') else ''}; "
                                               f"decided {decision}{(' ' + code) if code else ''}") if x)
        if getattr(self, 'rescreen', False) and decision == 'EXCLUDE' and not code:
            code, why = self.default_reason(self.current)      # the author need not choose a reason (5 October 2026)
            note = '; '.join(x for x in (note, why) if x)
        self.store.put(self.current, what, note=note, decision=decision, code=code, focus_parts=e.get('focus_parts', ''),
                       zk_proves=e.get('zk_proves', ''), **{k: e[k] for k in ANSWER_KEYS})
        if self.current in self.items:
            self.style_item(self.items[self.current], self.by_n[self.current])
        self.update_progress()
        if self.stage == 'fulltext' and decision == 'EXCLUDE' and not code:
            self.refresh_panel()                        # the reason is required at full text: wait for it
            return
        self.next()
        self.refresh_panel()

    def default_reason(self, n):
        """the reason recorded when the author excludes without choosing one: the AI's reason if it proposed exclusion; else the
        reason the answers shown give; else that the focus angles are not covered in substance"""
        prop = self.by_n[n].get('ft', {}).get('proposal', {})
        if prop.get('decision') == 'EXCLUDE' and prop.get('code'):
            return prop['code'], 'reason taken from the AI proposal'
        sug = suggest(self.effective(n)[0], self.by_n[n])
        if sug and sug[0] == 'EXCLUDE' and sug[1]:
            return sug[1], 'reason taken from the answers shown'
        return 'OFF-FOCUS', 'reason defaulted: the focus angles are not covered in substance (no reason chosen)'

    def set_decision(self, d, toggle=False):
        s = self.store.get(self.current)
        if toggle and s['decision'] == d:
            self.changed('decision cleared', decision='', code='')
            return
        code = ''
        if d == 'EXCLUDE':
            pick = self.claude_pick(self.current)
            sug = pick if pick and pick[0] == 'EXCLUDE' else suggest(self.effective(self.current)[0], self.by_n[self.current])
            code = s['code'] or (sug[1] if sug and sug[0] == 'EXCLUDE' else '')
        self.decide('decision', d, code)

    def set_code(self, c):
        if not c:
            return
        self.decide('code', 'EXCLUDE', c)

    def save_comment(self):
        self.comment_timer.stop()
        if self.current is None:
            return
        text = self.comment.toPlainText()
        if text != self.store.get(self.current)['comment']:
            self.changed('comment', comment=text)

    def use_suggestion(self):
        pick = self.claude_pick(self.current)
        sug = pick or suggest(self.effective(self.current)[0], self.by_n[self.current])
        if not sug:
            self.statusBar().showMessage('Answer the questions first.', 3000)
            return
        self.decide("decision: Claude's suggestion confirmed" if pick else 'decision from answers', sug[0], sug[1])

    # ---------------------------------------------------------------------------------------------------- navigation
    def step(self, delta, todo=False):
        ns = list(self.items)
        if not ns:
            return
        i = ns.index(self.current) if self.current in ns else -1
        if not todo:
            self.select(ns[min(max(i + delta, 0), len(ns) - 1)])
            return
        for k in range(1, len(ns) + 1):
            n = ns[(i + delta * k) % len(ns)]
            if not self.store.get(n)['decision']:
                self.select(n)
                return
        self.statusBar().showMessage('Every record shown is decided.', 4000)

    next = lambda self: self.step(1)
    prev = lambda self: self.step(-1)
    next_todo = lambda self: self.step(1, todo=True)

    def zoom_by(self, d):
        self.view.zoomIn(d)
        self.zoom += d
        self.settings.setValue('zoom', self.zoom)

    def closeEvent(self, e):
        self.save_comment()
        self.settings.setValue('geometry', self.saveGeometry())
        self.settings.setValue('splitter', self.splitter.saveState())
        super().closeEvent(e)


# ------------------------------------------------------------------------------------------------------------- run
def write_guide():
    """the guide as a printable page, so that the screening rules are on record outside the app"""
    body = guide_html(False).replace('<h3>Keys</h3>', '<h3>Keys of the screening app</h3>')
    GUIDE.write_text(f"""<!doctype html><html lang="en-GB"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Screening guide</title><style>
:root{{--ink:#1b1b1b;--line:#c9c9c4;--head:#0f4761}}
html,body{{background:#fff;color:var(--ink)}} body{{font:15px/1.5 -apple-system,"Helvetica Neue",Arial,sans-serif;margin:0 auto;max-width:56rem;padding:24px 16px 48px}}
h1{{font-size:1.4rem;color:var(--head);margin:0 0 4px}} h3{{color:var(--head);margin:20px 0 6px}}
table{{border-collapse:collapse;width:100%}} td{{border:1px solid var(--line);padding:5px 7px;vertical-align:top}}
@page{{size:auto;margin:13mm}} @media print{{body{{max-width:none;padding:0;font-size:10pt}}table,tr,ul,ol{{break-inside:avoid}}}}
</style></head><body><h1>Screening guide — privacy-preserving ML in NG-IoT (primary and secondary studies)</h1>
<p style="color:#555">4 October 2026 · version 7, criteria V7 (version 1, for surveys only: SCREENING-GUIDE-2026-10-04.md) · the same text as
the tab "How to decide" of the screening app</p>{body}</body></html>""", encoding='utf-8')
    print(GUIDE.relative_to(ROOT))


def self_test(outdir):
    """offscreen: parse, counts, a decision round trip into OUTDIR, screenshots"""
    outdir = pathlib.Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    for f in ('decisions.csv', 'log.jsonl'):
        (outdir / f).unlink(missing_ok=True)
    app = QApplication(sys.argv)
    md = newest_md()
    before = md.read_bytes()
    QSettings('Abertay', 'PPMLScreening-selftest').clear()                  # never the author's own settings
    first_three = [r['n'] for r in load_md(md)[1] if r['section'] == 'screen' and (r['year'] or 0) >= 2024][:3]   # outside the date rule
    with open(outdir / 'suggestions.csv', 'w', encoding='utf-8', newline='') as fh:     # test suggestions, not the real ones
        fh.write('n,type,privacy,focus,focus_parts,ngiot,reason\n'
                 f'{first_three[0]},primary,no,yes,poisoning,yes,plain FL only\n{first_three[1]},secondary,yes,,,yes,survey covers privacy\n')
    w = Window(md, (outdir / 'decisions.csv', outdir / 'log.jsonl'), 'PPMLScreening-selftest', outdir / 'suggestions.csv')
    w.resize(1500, 920)
    w.show()
    checks = []
    ok = lambda name, cond: checks.append((name, bool(cond)))
    mc = json.loads((P / 'MERGE-CHECK-2026-10-04.json').read_text())
    matches = list(csv.DictReader(open(P / 'CORPUS-MATCHES-2026-10-04.csv', encoding='utf-8')))
    screen = [r for r in w.records if r['section'] == 'screen']
    aside = [r for r in w.records if r['section'] == 'aside']
    ok(f'records to screen = stated = merge ({len(screen)} / {w.stated} / {mc["to_screen"]})', len(screen) == w.stated == mc['to_screen'])
    ok(f"set aside, in corpus ({len(aside)} / {len({m['n'] for m in matches if m['set_aside']})})",
       len(aside) == len({m['n'] for m in matches if m['set_aside']}) and all(r['corpus'] for r in aside))
    ok(f"records in corpus ({sum(1 for r in w.records if r['corpus'] and r['section'] != 'known')} / {len({m['n'] for m in matches})})",
       sum(1 for r in w.records if r['corpus'] and r['section'] != 'known') == len({m['n'] for m in matches}))
    ok('record numbers unique', len({r['n'] for r in w.records}) == len(w.records))
    ok(f"every record has an abstract ({sum(1 for r in w.records if not r['abstract'])} empty)", all(r['abstract'] for r in w.records))
    print(f"info: {sum(1 for r in w.records if not r['doi'])} records without a DOI")
    ok('every corpus PDF exists', all((ROOT / c['pdf']).exists() for r in w.records for c in r['corpus']))
    ok('every record names its search', all(r['search'] in ('survey search', 'primary-study search', 'both searches', 'other methods (known to the author)')
                                            for r in w.records))
    known = list(csv.DictReader(open(P / 'OTHER-METHODS-2026-10-04.csv', encoding='utf-8')))
    ok(f"other methods ({sum(1 for r in w.records if r['section'] == 'known')} / {len(known)})",
       sorted(r['n'] for r in w.records if r['section'] == 'known') == sorted(int(k['n']) for k in known))
    fidx = lambda k: [x for x, _ in FILTERS].index(k)
    w.filter.setCurrentIndex(fidx('arm-primary'))
    ok(f"filter primary-study search = merge ({w.list.count()} / {mc['to_screen_by_arm']['primary']})", w.list.count() == mc['to_screen_by_arm']['primary'])
    w.filter.setCurrentIndex(fidx('arm-survey'))
    ok(f"filter survey search = merge ({w.list.count()} / {mc['to_screen_by_arm']['survey']})", w.list.count() == mc['to_screen_by_arm']['survey'])
    w.filter.setCurrentIndex(fidx('corpus'))
    corpus_n = min(r['n'] for r in w.records if r['corpus'] and r['section'] == 'screen' and r['search'] != 'survey search')
    w.select(corpus_n)
    app.processEvents()
    w.grab().save(str(outdir / 'shot-corpus-record.png'))
    w.filter.setCurrentIndex(0)
    w.search.setText('vehicular')
    ok(f'search "vehicular" finds records ({w.list.count()})', 0 < w.list.count() < len(screen))
    w.search.setText('')
    first, second, third = first_three
    w.select(first)
    ok('suggested answers pre-filled', w.answer_buttons[('type', 'primary')].isChecked() and w.answer_buttons[('privacy', 'no')].isChecked()
       and w.answer_buttons[('type', 'primary')].property('sug') == '1')
    ok('question 2 reads for a primary study', 'own contribution' in w.question_labels['privacy'].text())
    w.set_decision('EXCLUDE')
    s1 = w.store.get(first)
    ok('Exclude takes the code from the answers shown and moves on', s1['decision'] == 'EXCLUDE' and s1['code'] == 'PRIVACY-INCIDENTAL'
       and w.current == second)
    ok("unchanged suggestions recorded as the author's answers",
       (s1['type'], s1['privacy'], s1['focus'], s1['focus_parts'], s1['ngiot']) == ('primary', 'no', 'yes', 'poisoning', 'yes'))
    ok('a survey is asked which angles it covers', w.part_buttons['poisoning'].isEnabled() and 'excluded by default' in w.question_labels['focus'].text())
    w.set_answer('ngiot', 'unsure')
    w.set_decision('UNSURE')
    s2 = w.store.get(second)
    ok('a changed answer is kept, the others come from the suggestion, and it moves on',
       s2['decision'] == 'UNSURE' and s2['ngiot'] == 'unsure' and s2['type'] == 'secondary' and w.current == third)
    w.set_answer('type', 'neither')
    ok('Neither gives NOT-A-STUDY', suggest(w.effective(third)[0]) == ('EXCLUDE', 'NOT-A-STUDY'))
    w.set_answer('type', 'primary')
    w.set_focus_part('blockchain')
    w.set_focus_part('poisoning')
    ok('angles ticked one by one, kept in order', (w.store.get(third)['focus'], w.store.get(third)['focus_parts']) == ('yes', 'poisoning; blockchain'))
    w.set_focus_part('blockchain')
    w.set_focus_part('poisoning')
    ok('unticking every angle means none of these', (w.store.get(third)['focus'], w.store.get(third)['focus_parts']) == ('no', ''))
    w.set_answer('focus', 'no')
    for key, val in (('privacy', 'yes'), ('focus', 'no')):
        w.set_answer(key, val)
    ok('primary outside the PhD focus gives OFF-FOCUS', suggest(w.effective(third)[0]) == ('EXCLUDE', 'OFF-FOCUS'))
    for key in ('privacy', 'focus'):
        w.set_answer(key, w.store.get(third)[key])          # clear again
    w.set_answer('type', 'secondary')
    ok('question 2 reads for a survey', 'survey treat privacy' in w.question_labels['privacy'].text())
    w.set_decision('EXCLUDE')
    ok('Exclude with no reason in the answers still moves on', w.store.get(third)['decision'] == 'EXCLUDE' and w.store.get(third)['code'] == ''
       and w.current != third)
    w.select(third)
    for key in ('privacy', 'ngiot'):
        w.set_answer(key, 'yes')
    if w.store.get(third)['decision']:
        w.set_decision(w.store.get(third)['decision'], toggle=True)        # undecided again, so that a default can show
    w.set_answer('focus', 'no')
    ok('a survey covering no PhD angle gives OFF-FOCUS', suggest(w.effective(third)[0]) == ('EXCLUDE', 'OFF-FOCUS'))
    ok('... and is excluded by default', w.by_rule(third) == 'OFF-FOCUS' and w.dec_buttons['EXCLUDE'].isChecked())
    w.set_answer('focus', 'no')
    w.set_focus_part('blockchain')
    w.set_focus_part('zero-knowledge proofs')
    ok('ticking zero-knowledge shows what-it-proves', w.zk_buttons['similarity'].isVisibleTo(w) and w.zk_label.isVisibleTo(w))
    w.set_zk_proves('similarity')
    w.set_zk_proves('bounded')
    ok('what the ZK proof shows is recorded in order', w.store.get(third)['zk_proves'] == 'bounded; similarity')
    w.set_zk_proves('bounded')
    w.set_zk_proves('similarity')
    w.sugg[third] = {'n': str(third), 'zk_proves': 'identity', 'focus_parts': '', 'type': '', 'privacy': '', 'focus': '', 'ngiot': '', 'reason': ''}
    w.refresh_panel()
    ok('what the ZK proof shows is pre-filled when nothing is stored', w.zk_buttons['identity'].isChecked()
       and w.zk_buttons['identity'].property('sug') == '1')
    del w.sugg[third]
    w.set_focus_part('zero-knowledge proofs')
    ok('unticking zero-knowledge hides the follow-up', not w.zk_label.isVisibleTo(w))
    ok("ticking an angle lifts the default; the survey's angles are recorded", w.store.get(third)['focus_parts'] == 'blockchain'
       and not w.by_rule(third) and suggest(w.effective(third)[0]) == ('INCLUDE', ''))
    w.comment.setPlainText('check the full text for privacy analysis')
    w.use_suggestion()
    ok('use-suggestion saved, kept the comment and moved on', w.store.get(third)['decision'] == 'INCLUDE' and w.current != third
       and w.store.get(third)['comment'] == 'check the full text for privacy analysis')
    w.select(third)
    w.set_decision('INCLUDE', toggle=True)
    ok('clicking the chosen decision clears it and stays', w.store.get(third)['decision'] == '' and w.current == third)
    w.set_code('NO-NGIOT')
    ok('a code sets Exclude and moves on', w.store.get(third)['decision'] == 'EXCLUDE' and w.current != third)
    w.select(third)
    w.set_decision('INCLUDE')
    ok('include counted as secondary', w.store.counts()['inc_secondary'] == 1)
    ok(f"non-papers removed before screening ({mc.get('auto_excluded_not_a_paper')})", mc.get('auto_excluded_not_a_paper', 0) > 0)
    again = Store(w.records, outdir / 'decisions.csv', outdir / 'log.jsonl')
    ok('decisions read back from the CSV', again.get(first)['decision'] == 'EXCLUDE' and again.get(second)['decision'] == 'UNSURE'
       and again.get(third)['type'] == 'secondary' and again.get(third)['comment'] == 'check the full text for privacy analysis'
       and not again.mismatch)
    old = next(r for r in w.records if r['section'] == 'screen' and r['year'] and r['year'] < 2024 and r['cited'] is not None and r['cited'] < 100
               and r['n'] not in first_three)
    cited = next(r for r in w.records if r['section'] == 'screen' and r['year'] and r['year'] < 2024 and (r['cited'] or 0) >= 100
                 and r['n'] not in first_three)
    w.select(old['n'])
    w.set_answer('type', 'secondary')
    w.set_focus_part('blockchain')
    ok('an old, little-cited survey is excluded by default', w.by_rule(old['n']) and w.shown_decision(old['n'])['code'] == 'SURVEY-BEFORE-2024'
       and w.dec_buttons['EXCLUDE'].isChecked() and not w.store.get(old['n'])['decision'])
    w.set_answer('type', 'primary')
    ok('the date rule does not touch a primary study', not w.by_rule(old['n']))
    w.set_answer('type', 'secondary')
    w.set_decision('INCLUDE')
    ok('the author can include an old survey', w.store.get(old['n'])['decision'] == 'INCLUDE' and not w.by_rule(old['n']))
    w.select(cited['n'])
    w.set_answer('type', 'secondary')
    w.set_focus_part('blockchain')
    ok(f"a foundational survey (cited {cited['cited']}) is not excluded by the rule", not w.by_rule(cited['n']))
    log = [json.loads(x) for x in open(outdir / 'log.jsonl', encoding='utf-8')]
    ok(f'every change logged ({len(log)} lines)', len(log) >= 10 and any('note' in x for x in log))
    second = first
    w.select(second)
    app.processEvents()
    w.grab().save(str(outdir / 'shot-decided.png'))
    w.tabs.setCurrentIndex(1)
    app.processEvents()
    w.grab().save(str(outdir / 'shot-guide.png'))
    ok('the reading file is unchanged', md.read_bytes() == before)
    # the full-text stage (a fault here is reported as a failed check, not allowed to hide the results above)
    def fulltext_part():
        for f in ('ft.csv', 'ft.jsonl'):
            (outdir / f).unlink(missing_ok=True)
        QSettings('Abertay', 'PPMLFullText-selftest').clear()
        ft = Window(md, (outdir / 'ft.csv', outdir / 'ft.jsonl'), 'PPMLFullText-selftest', stage='fulltext')
        ft.resize(1500, 920)
        ft.show()
        inc = list(csv.DictReader(open(INCLUDED, encoding='utf-8')))
        ok(f'full text: the included studies are listed ({len(ft.records)} / {len(inc)})', len(ft.records) == len(inc) == len(ft.items))
        ok(f"full text: every study has its PDF ({sum(1 for r in ft.records if r['ft']['pdf'])})", all(r['ft']['pdf'] for r in ft.records))
        ok(f"full text: every study has its summary ({sum(1 for r in ft.records if r['ft']['summary'])})", all(r['ft']['summary'] for r in ft.records))
        n1 = ft.records[0]['n']
        ft.select(n1)
        scr = screening_answers()[n1]
        ok('full text: the screening answers are pre-filled', ft.effective(n1)[0]['type'] == scr['type'] and ft.effective(n1)[0]['focus_parts'] == scr['focus_parts'])
        ok('full text: the record shows the summary and the PDF link', 'open the PDF' in ft.record_html(ft.records[0]))
        ok('full text: no default rule applies', not any(ft.by_rule(r['n']) for r in ft.records))
        ft.set_decision('EXCLUDE')
        ok('full text: an Exclude waits for its reason', ft.current == n1 and ft.store.get(n1)['decision'] == 'EXCLUDE' and ft.code.isEnabled())
        ft.set_code('NO-NGIOT')
        ok('full text: the reason is stored and it moves on', ft.store.get(n1)['code'] == 'NO-NGIOT' and ft.current != n1)
        n2 = ft.current
        ft.set_decision('INCLUDE')
        ok('full text: Include is stored with the answers and moves on', ft.store.get(n2)['decision'] == 'INCLUDE'
           and ft.store.get(n2)['type'] == screening_answers()[n2]['type'] and ft.current != n2)
        ok('full text: the screening decisions are untouched', Store(w.records, outdir / 'decisions.csv', outdir / 'log.jsonl').get(n1)['decision'] != 'EXCLUDE'
           or n1 == first)
        if CHECKS.exists():
            ft.filter.setCurrentIndex([k for k, _ in FILTERS].index('flagged'))
            nflag = len({int(c['n']) for c in csv.DictReader(open(CHECKS, encoding='utf-8')) if c['status'] == 'CHECK'})
            ok(f'full text: the flagged studies are listed ({ft.list.count()} / {nflag})', ft.list.count() == nflag)
            if ft.items:
                ok('full text: a flagged study shows its decision check', 'Decision check' in ft.record_html(ft.by_n[next(iter(ft.items))]))
            ft.filter.setCurrentIndex(0)
        ft.select(n2)
        app.processEvents()
        ft.grab().save(str(outdir / 'shot-fulltext.png'))
    try:
        fulltext_part()
    except Exception as e:
        ok(f'full text: the part runs ({type(e).__name__}: {e})', False)
    for name, good in checks:
        print('ok  ' if good else 'FAIL', name)
    print(f'self-test {sum(g for _, g in checks)}/{len(checks)}')
    return all(g for _, g in checks)


def main():
    if '--self-test' in sys.argv:
        sys.exit(0 if self_test(sys.argv[sys.argv.index('--self-test') + 1]) else 1)
    if '--guide' in sys.argv:
        write_guide()
        return
    app = QApplication(sys.argv)
    fulltext = '--fulltext' in sys.argv
    rescreen = '--rescreen' in sys.argv
    szk = '--szk' in sys.argv
    app.setApplicationName('PPML Full text (second screening)' if rescreen else 'PPML Full text' if fulltext else
                           'PPML S-ZK Screening' if szk else 'PPML Screening')
    lock = QLockFile(str(P / ('.rescreen-app.lock' if rescreen else '.fulltext-app.lock' if fulltext else '.szk-app.lock' if szk else
                              '.screening-app.lock')))
    lock.setStaleLockTime(0)
    if not lock.tryLock(200):
        QMessageBox.warning(None, 'PPML Screening', 'The screening app is already open. Use that window, so that no decision is lost.')
        sys.exit(1)
    if szk:
        global EC9_AT_SCREENING
        EC9_AT_SCREENING = True
    md = (szk_newest('ABSTRACTS-S-ZK-*.md') if szk else
          pathlib.Path(sys.argv[sys.argv.index('--md') + 1]) if '--md' in sys.argv else newest_md())
    w = (Window(md, None, 'PPMLRescreen', stage='rescreen') if rescreen else
         Window(md, None, 'PPMLFullText', stage='fulltext') if fulltext else
         Window(md, (SZK_DECISIONS, SZK_LOG), 'PPMLScreeningSZK',
                suggestions_path=szk_newest(SZK_CLAUDE) if list(SZK.glob(SZK_CLAUDE)) else szk_newest('PREFILL-S-ZK-*.csv'))
         if szk else Window(md))
    if '--filter' in sys.argv:                          # e.g. --filter known: open on the studies identified via other methods
        key = sys.argv[sys.argv.index('--filter') + 1]
        if w.filter.findData(key) >= 0:
            w.filter.setCurrentIndex(w.filter.findData(key))
            first = next(iter(w.items), None)
            if first is not None:
                w.select(first)
    if w.store.mismatch:
        QMessageBox.warning(w, 'PPML Screening', f'{len(w.store.mismatch)} stored decisions do not match their record '
                            f'(numbers {", ".join(map(str, w.store.mismatch[:10]))}…). They are kept; ask Claude Code to check them.')
    w.show()
    code = app.exec()
    lock.unlock()
    sys.exit(code)


if __name__ == '__main__':
    main()
