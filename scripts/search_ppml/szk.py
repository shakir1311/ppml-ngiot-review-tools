#!/usr/bin/env python3
"""S-ZK: the searches of 2 October 2026 with ledger and zero-knowledge terms, taken into the PPML review as a supplementary
search (the author, 12 October 2026: "our second series of searches did include ZKP"; "yes" to screening their new records).

The main strings of the PPML review name no ledger or zero-knowledge term (Section II-B). The searches run on 2 October 2026
for the review of verifiable PPFL on blockchains (search/SEARCH-LOG.md: Scopus S1, S2 and X5, with IEEE Xplore and
ScienceDirect for S1; 2022-2026) did: federated learning with ledger and privacy terms (S1, X5), learning with ZKP terms
(S2). Their merged records (search/MERGED-RECORDS-2026-10-02-X5.csv, 4,370) are matched by DOI and normalised title with
every record the PPML review has already assessed (main searches, R-S1, the reports added through other methods, the
included studies). A record new to the review is a candidate when its title, abstract and
keywords carry the PPML review's own blocks, extended by the two terms the main strings lack:

    NG-IoT block (strings.NGIOT)  AND  learning block (strings.ML)  AND  privacy block or a ZKP term  AND  a ledger or ZKP term

The author screens the candidates in the screening app (`screening_app.py --szk`), with the same four questions and the
same cue-word pre-fill as the main screening (prefill.rule); no AI decision is made or shown.

Outputs (search-ppml/evidence/szk-search/), never overwritten:
  SZK-RECORDS-<date>.csv            the candidates: S-ZK number (500000 + the record number of 2 October), the record of 2 October
  ABSTRACTS-S-ZK-<date>.md          the reading file the app loads
  PREFILL-S-ZK-<date>.csv           the cue-word pre-fill
  README.md                         the definition, the counts and the provenance

Usage: python3 scripts/search_ppml/szk.py <date>
"""
import collections
import csv
import glob
import json
import pathlib
import re
import sys

csv.field_size_limit(10 ** 9)
HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
import merge as M                                     # noqa: E402
import prefill as PF                                  # noqa: E402
import strings as S                                   # noqa: E402

OUT = ROOT / 'search-ppml' / 'evidence' / 'szk-search'
ZK_RECORDS = ROOT / 'search' / 'MERGED-RECORDS-2026-10-02-X5.csv'
ZK_LEDGER = ROOT / 'search' / 'RECORD-LEDGER-2026-10-02-X5.csv'
OFFSET = 500000
ZKP = ['"zero-knowledge"', '"zero knowledge"', 'zkSNARK', '"zk-SNARK"', 'zkML', 'ZKP']
LEDGER = ['blockchain', '"block chain"', '"distributed ledger"', '"smart contract"', 'hyperledger']
clean = lambda s: re.sub(r'\s+', ' ', s or '').strip()
flat = lambda t: re.sub(r'[^a-z0-9]', '', (t or '').lower())
low = lambda d: (d or '').strip().lower()


def has(text, terms):
    return [t.strip('"') for t in terms if M.term_re(t).search(text)]


def ours():
    """the keys (DOI, normalised title) of every record the PPML review has already assessed: its searches (main searches
    and R-S1), the reports added through other methods, and its included studies"""
    keys = set()
    for f in ('MERGED-RECORDS-2026-10-04.csv', 'OTHER-METHODS-2026-10-04.csv', 'FINAL-STUDIES-2026-10-05.csv'):
        for r in csv.DictReader(open(ROOT / 'search-ppml' / f, encoding='utf-8')):
            keys |= ({low(r.get('doi'))} - {''}) | {flat(r.get('title'))}
    rs1 = glob.glob(str(ROOT / 'search-ppml' / 'evidence' / 'regulation-search' / 'exports' / 'scopus-R-S1-*.csv'))
    for r in csv.DictReader(open(rs1[0], encoding='utf-8-sig')):
        keys |= ({low(r.get('DOI'))} - {''}) | {flat(r.get('Title'))}
    return keys


def head(n, counts):
    return f"""# Records to screen — supplementary search S-ZK (the searches of 2 October 2026 with ledger and ZKP terms)

**{n} records** to screen. The main searches of the review name no ledger or zero-knowledge term. The searches run on
2 October 2026 for the review of verifiable PPFL on blockchains did (Scopus S1, S2 and X5, with IEEE Xplore and ScienceDirect
for S1; 2022 to 2026; `search/SEARCH-LOG.md`). Of their {counts['all']:,} merged records, {counts['new']:,} are not among the
records this review has assessed (its searches, R-S1 and the reports added through other methods), and {n} of these carry
this review's NG-IoT and learning blocks, a privacy or ZKP term and a ledger or ZKP term in their title, abstract or
keywords. This file contains no AI decisions.

**Decisions are recorded in the screening app** (`PPML S-ZK Screening.app` in `search-ppml/`), which loads this file and keeps
its decisions apart from those of the main screening. The questions and the pre-filled answers are those of the main
screening (a cue-word script).

**The criteria** (`search-ppml/CRITERIA-V9-2026-10-05.md`): a primary or a secondary study; privacy treated (federated
learning alone is not enough; zero-knowledge proofs that show a property of the data or the update without revealing it
count); at least one focus angle; an NG-IoT setting. **A primary study must build on a blockchain or distributed ledger as
part of its design** (EC9). A survey must be from 2024 or later, or cited at least 100 times (no citation count is recorded
for these records). Peer-reviewed journal, conference or magazine articles in English from 2020.

When unsure: UNSURE. Exclusion codes: `NOT-A-STUDY` · `NOT-FULL-PAPER` · `PRIVACY-INCIDENTAL` · `OFF-FOCUS` · `NO-LEARNING` ·
`NO-NGIOT` · `SURVEY-BEFORE-2024` · `OTHER`.

---
"""


def entry(n, r):
    tak = M.norm(' '.join([r['title'], r['abstract'], r['keywords']]))
    link = f"[{r['doi']}](https://doi.org/{r['doi']})" if r['doi'] else 'no DOI in the records'
    return '\n'.join([f"\n## {n}. {clean(r['title'])}\n",
                      f"- **Year · venue · type:** {r['year']} · {clean(r['venue'])}{' · ' + r['type'] if r['type'] else ''}",
                      f"- **DOI:** {link}",
                      "- **Cited:** not recorded (the searches of 2 October did not export citation counts)",
                      f"- **Search:** S-ZK (record {r['n']} of 2 October 2026: {clean(r['sources']) or 'sources not recorded'})",
                      f"- **Why it matched:** privacy: {', '.join(has(tak, S.PPML)) or 'none'} · ZKP: {', '.join(has(tak, ZKP)) or 'none'} · "
                      f"ledger: {', '.join(has(tak, LEDGER)) or 'none'} · PhD angles: "
                      f"{', '.join(a for a, terms in M.FOCUS_PARTS.items() if has(tak, terms)) or 'none'} · learning: "
                      f"{', '.join(has(tak, S.ML)) or 'none'} · NG-IoT: {', '.join(has(tak, S.NGIOT)) or 'none'}",
                      f"- **Keywords:** {clean(r['keywords'])[:500] or '—'}",
                      f"\n{clean(r['abstract']) or '*(no abstract in the records)*'}\n"])


def main(date):
    OUT.mkdir(parents=True, exist_ok=True)
    files = {k: OUT / f for k, f in (('records', f'SZK-RECORDS-{date}.csv'), ('md', f'ABSTRACTS-S-ZK-{date}.md'),
                                     ('prefill', f'PREFILL-S-ZK-{date}.csv'))}
    if any(f.exists() for f in files.values()):
        sys.exit('S-ZK files for this date exist; never overwritten')
    keys = ours()
    Z = list(csv.DictReader(open(ZK_RECORDS, encoding='utf-8')))
    new = [r for r in Z if not ((({low(r['doi'])} - {''}) | {flat(r['title'])}) & keys)]
    cand = []
    for r in new:
        tak = M.norm(' '.join([r['title'], r['abstract'], r['keywords']]))
        if has(tak, S.NGIOT) and has(tak, S.ML) and (has(tak, S.PPML) or has(tak, ZKP)) and (has(tak, LEDGER) or has(tak, ZKP)):
            cand.append(r)
    cand.sort(key=lambda r: int(r['n']))
    with open(files['records'], 'w', encoding='utf-8', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=['n', 'n_2oct', 'doi', 'title', 'year', 'venue', 'type', 'sources', 'hits', 'keywords', 'abstract'])
        w.writeheader()
        for r in cand:
            w.writerow({'n': OFFSET + int(r['n']), 'n_2oct': r['n'], **{k: r.get(k, '') for k in ('doi', 'title', 'year', 'venue', 'type', 'sources', 'hits', 'keywords', 'abstract')}})
    counts = {'all': len(Z), 'new': len(new)}
    files['md'].write_text(head(len(cand), counts) + ''.join(entry(OFFSET + int(r['n']), r) for r in cand), encoding='utf-8')
    rows = [{'n': OFFSET + int(r['n']), **PF.rule(r['title'], r['abstract'], r['keywords'], r['type']), 'zk_proves': ''} for r in cand]
    with open(files['prefill'], 'w', encoding='utf-8', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=['n', 'type', 'privacy', 'focus', 'focus_parts', 'zk_proves', 'ngiot', 'reason'])
        w.writeheader()
        w.writerows(rows)
    status = collections.Counter(r['status'] for r in csv.DictReader(open(ZK_LEDGER, encoding='utf-8'))
                                 if OFFSET + int(r['n']) in {x['n'] for x in rows})
    (OUT / 'README.md').write_text(
        f"# S-ZK — supplementary search with ledger and ZKP terms ({date})\n\n"
        f"Definition, inputs and rule: `scripts/search_ppml/szk.py` (docstring). Records of 2 October 2026: {len(Z):,}; not among "
        f"the records this review has assessed (main searches, R-S1, other methods, included studies): {len(new):,}; candidates "
        f"(NG-IoT and learning blocks, a privacy or ZKP term, a ledger or ZKP term): {len(cand)}.\n\n"
        f"Files: `{files['records'].name}`, `{files['md'].name}` (the app's reading file), `{files['prefill'].name}` (cue-word "
        f"pre-fill, prefill.rule). The author's decisions: `AUTHOR-DECISIONS-S-ZK.csv` and `AUTHOR-DECISIONS-S-ZK-LOG.jsonl`, written "
        f"by `screening_app.py --szk` (open `search-ppml/PPML S-ZK Screening.app`).\n\n"
        f"Pre-fill of the candidates: " + json.dumps({k: dict(collections.Counter(r[k] for r in rows)) for k in ('type', 'privacy', 'focus', 'ngiot')}) + "\n\n"
        f"How the review of 2 October had classified them (its own scope, by its screening tool; for information only): "
        + json.dumps(dict(status.most_common()), ensure_ascii=False) + "\n", encoding='utf-8')
    print(f'{len(cand)} candidates of {len(new)} new records ({len(Z)} of 2 October) -> {OUT.relative_to(ROOT)}')


if __name__ == '__main__':
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
