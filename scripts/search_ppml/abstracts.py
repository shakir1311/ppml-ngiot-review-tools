#!/usr/bin/env python3
"""The author's reading file for the screening of the PPML review (primary and secondary studies).

The author screens every record by eye (4 October 2026: "you give me 1 file with all abstracts etc and i will do the
inclusion/exclusion myself"); the decisions are recorded in the screening app (scripts/search_ppml/screening_app.py),
which loads this file. No AI decisions are made or shown.

  search-ppml/MERGED-RECORDS-2026-10-04.csv   the records of both arms (those set aside by the automated IEEE rule are
                                              not screened)
  search-ppml/CORPUS-MATCHES-2026-10-04.csv   which records are papers the author already holds (corpus_match.py)
  -> search-ppml/ABSTRACTS-FOR-AUTHOR-V5-2026-10-04.md
     per record: year, venue, type, DOI, the search arm and searches that found it, the terms it contains from each
     block of the search (strings v4), keywords, the corpus paper it matches (if any) and the abstract; then, in a section
     of their own, the corpus papers that the automated rule set aside, and the studies identified via other methods
     (search-ppml/OTHER-METHODS-2026-10-04.csv: corpus papers on the topic that the searches did not return)

Usage: python3 scripts/search_ppml/abstracts.py
"""
import csv, json, pathlib, re, sys
from collections import defaultdict

csv.field_size_limit(10 ** 9)
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import merge as M                                     # noqa: E402
import strings as S                                   # noqa: E402

P = M.P
OUT = P / 'ABSTRACTS-FOR-AUTHOR-V13-2026-10-04.md'
clean = lambda s: re.sub(r'\s+', ' ', s or '').strip()
matched = lambda text, terms: [t.strip('"') for t in terms if M.term_re(t).search(text)]
ARM = {'survey': 'survey search', 'primary': 'primary-study search', 'primary; survey': 'both searches'}


def head(n, mc, by_arm, n_corpus, n_aside, n_known):
    ident = mc['identified']
    return f"""# Records to screen — privacy-preserving ML in NG-IoT: primary and secondary studies (final searches)

**{n} records** to screen (4 October 2026): {by_arm['survey']:,} from the survey search and {by_arm['primary']:,} from the
primary-study search ({by_arm['both']:,} were found by both). The searches were run by the author: Scopus (P-S1 v3 and P-S2),
IEEE Xplore (P-A1 to P-A6 v3 and P-B) and ScienceDirect (P-C1 to P-C8, survey search only). In all {mc['identified_total']:,}
records were identified (Scopus {ident['Scopus']:,}, IEEE Xplore {ident['IEEE Xplore']:,}, ScienceDirect {ident['ScienceDirect']:,});
{mc['duplicates']:,} duplicates were removed; {mc['auto_excluded_ieee_rule']:,} IEEE Xplore records were set aside by the automated rule
(their title, abstract and keywords do not satisfy the search; IEEE matched them elsewhere, e.g. in the journal name), and
{mc['auto_excluded_not_a_paper']:,} records whose title announces an editorial, notice, talk or special-issue introduction were removed,
and {mc['auto_excluded_focus']:,} records found only by the primary-study search were set aside because their title, abstract and keywords
name no threat of the PhD (poisoning, backdoors, malicious or fake participants, Sybil, free riding), no verification of the
learning and no blockchain (the PhD focus). This file contains no AI decisions.

**Decisions are recorded in the screening app** (`PPML Screening.app` in `search-ppml/`), which loads this file. This file
is the reading copy; it is never changed by the app.

**Papers you already hold.** {n_corpus} records are papers in your corpus (any collection: newcorpus, surveycorpus,
oldcorpus, searchcorpus, the excluded papers and the supervisors' papers). Each carries a line **In your corpus**. This is
for information only: it decides nothing. The {n_aside} corpus papers that the automated rule set aside are shown at the
end, in a section of their own.

**Studies identified via other methods.** {n_known} corpus papers on the review's topic were not returned by the searches.
As you decided, they are assessed against the same criteria as studies known to you from earlier reading and reported in
their own box of the PRISMA flow. They are in the last section.

**The criteria** (`search-ppml/CRITERIA-V7-2026-10-04.md`)

1. **A primary or a secondary study.** Primary: it proposes, builds or evaluates a method, system, protocol or attack
   concerning the privacy of learning, or measures privacy leakage. Secondary: a survey, systematic review or mapping
   study, SoK, or a tutorial or overview that reviews the literature. A position or vision paper that does neither is out
   (NOT-A-STUDY).
2. **Privacy is treated.** Secondary: the survey examines, reviews or analyses privacy; privacy only named as a challenge,
   background or future direction is not enough. Primary: privacy is part of the study's own contribution — a privacy
   mechanism added to the learning (differential privacy, homomorphic encryption, secure multi-party computation or secret
   sharing, secure aggregation, trusted execution, anonymisation, masked or encrypted updates) or an analysis of privacy
   attacks or leakage. Federated learning alone (the raw data stay on the device) is not enough. (PRIVACY-INCIDENTAL)
3. **The PhD angles (every study and survey):** the study deals (a survey: covers), as part of its contribution, with at
   least one of seven angles of the PhD proposal — **poisoning** (data or model poisoning, backdoors); **malicious or fake
   participants** (Byzantine, Sybil, fake nodes, dishonest aggregators); **free riding**; **verification by other means**
   (verifiable aggregation, integrity checks, attestation, auditability); **zero-knowledge proofs**; **blockchain** as part of
   the design; **ZK proofs checked on the blockchain**. None of
   them: OFF-FOCUS. The app marks a record with no angle ticked Exclude by default.
4. **An NG-IoT setting is a stated focus:** IoT, IIoT, IoMT, IoV, smart grid, smart city, edge or fog computing, or 5G/6G —
   not one example among many. (Learning is a subject of practically every record; NO-LEARNING remains for the rare
   exception.)

5. **Surveys from 2024 on:** a survey published before 2024 is excluded unless it is foundational — cited at least 100
   times in Scopus or IEEE Xplore at the search date (the field and its regulation have moved on: the EU AI Act of 2024,
   the EDPB blockchain guidelines of 2025). The app marks such surveys Exclude by default; you can still include any.

When unsure: UNSURE. Exclusion codes: `NOT-A-STUDY` · `NOT-FULL-PAPER` · `PRIVACY-INCIDENTAL` · `OFF-FOCUS` · `NO-LEARNING` ·
`NO-NGIOT` · `SURVEY-BEFORE-2024` · `OTHER` (not English, preprint, before 2020).

---
"""


def entry(r, corpus):
    title, tak = M.norm(r['title']), M.norm(' '.join([r['title'], r['abstract'], r['keywords']]))
    sur = matched(title, S.SUR)
    sur_txt = ', '.join(sur) if sur else ('none in the title — Scopus document type Review' if r['type'] == 'Review' else 'none in the title')
    found = '; '.join(f"{h.split(':')[0]} ({h.split(':')[1]})" for h in r['hits'].split('; '))
    link = f"[{r['doi']}](https://doi.org/{r['doi']})" if r['doi'] else 'no DOI in the records'
    priv_title = matched(title, S.PPML)
    lines = [f"\n## {r['n']}. {clean(r['title'])}\n",
             f"- **Year · venue · type:** {r['year']} · {clean(r['venue'])}{' · ' + r['type'] if r['type'] else ''}",
             f"- **DOI:** {link}",
             f"- **Cited:** {r['cited'] if r['cited'] != '' else 'not recorded'} (Scopus or IEEE Xplore, at the search date)",
             f"- **Search:** {ARM.get(r['arms'], r['arms'])}",
             f"- **Found by:** {found}",
             f"- **Why it matched:** survey word: {sur_txt} · privacy: {', '.join(matched(tak, S.PPML)) or 'none'}"
             f"{' (in the title)' if priv_title else ''} · PhD angles: {', '.join(a for a, terms in M.FOCUS_PARTS.items() if matched(tak, terms)) or 'none'} · "
             f"learning: {', '.join(matched(tak, S.ML)) or 'none'} · NG-IoT: {', '.join(matched(tak, S.NGIOT)) or 'none'}",
             f"- **Keywords:** {clean(r['keywords'])[:500] or '—'}"]
    if r['auto_excluded']:
        lines.append(f"- **Status:** set aside by the automated rule — {r['auto_excluded']}; shown because it is in your corpus")
    for c in corpus:
        lines.append(f"- **In your corpus:** {c['corpus_id']} · {c['collection']} · {c['kind']} · {c['how']} · PDF: `{c['pdf']}`"
                     + (f" (also `{c['also']}`)" if c['also'] else ''))
    lines.append(f"\n{clean(r['abstract']) or '*(no abstract in the records)*'}\n")
    return '\n'.join(lines)


def known_entry(k, c):
    link = f"[{k['doi']}](https://doi.org/{k['doi']})" if k['doi'] else 'no DOI on record'
    return '\n'.join([f"\n## {k['n']}. {clean(k['title'])}\n",
                      f"- **Year · venue · type:** {k['year']} · {clean(k['venue'])} · {k['kind']} (corpus)",
                      f"- **DOI:** {link}",
                      "- **Search:** other methods (known to the author)",
                      f"- **Why it is here:** a corpus paper on the topic that the database searches did not return ({k['why_missed']})",
                      f"- **Keywords:** {clean(k['keywords'])[:500] or '—'}",
                      f"- **In your corpus:** {k['corpus_id']} · {c['collection']} · {c['kind']} · known study · PDF: `{k['pdf']}`",
                      f"\n{clean(k['abstract']) or '*(no abstract in the records)*'}\n"])


def main():
    R = sorted(csv.DictReader(open(P / 'MERGED-RECORDS-2026-10-04.csv', encoding='utf-8')), key=lambda r: int(r['n']))
    corpus = defaultdict(list)
    for c in csv.DictReader(open(P / 'CORPUS-MATCHES-2026-10-04.csv', encoding='utf-8')):
        corpus[c['n']].append(c)
    screen = [r for r in R if not r['auto_excluded']]
    aside = [r for r in R if r['auto_excluded'] and r['n'] in corpus]
    mc = json.loads((P / 'MERGE-CHECK-2026-10-04.json').read_text())
    by_arm = {**mc['to_screen_by_arm'], 'both': mc['to_screen_both_arms']}
    known = list(csv.DictReader(open(P / 'OTHER-METHODS-2026-10-04.csv', encoding='utf-8')))
    idx = {r['id']: r for r in csv.DictReader(open(P / 'CORPUS-INDEX-2026-10-04.csv', encoding='utf-8'))}
    text = head(len(screen), mc, by_arm, sum(1 for r in screen if r['n'] in corpus) + len(aside), len(aside), len(known))
    text += ''.join(entry(r, corpus.get(r['n'], [])) for r in screen)
    text += (f"\n---\n\n# In your corpus but set aside by the automated rule ({len(aside)})\n\n"
             "An automated rule set these records aside before screening (each one's Status says which). They are shown because "
             "they are papers you hold. A decision on them is recorded apart from the screening of the records above.\n")
    text += ''.join(entry(r, corpus[r['n']]) for r in aside)
    text += (f"\n---\n\n# Studies identified via other methods ({len(known)})\n\n"
             "Corpus papers on the review's topic that the database searches did not return, assessed against the same criteria as "
             "studies known to you from earlier reading (PRISMA 2020: identification of studies via other methods). Title, abstract "
             "and keywords are the indexed record (OpenAlex, or the ZK review's search records).\n")
    text += ''.join(known_entry(k, idx[k['corpus_id']]) for k in known)
    OUT.write_text(text, encoding='utf-8')
    print(f'{len(screen)} records to screen ({sum(1 for r in screen if r["n"] in corpus)} in the corpus) + {len(aside)} set-aside corpus papers '
          f'+ {len(known)} via other methods -> {OUT.name}')


if __name__ == '__main__':
    main()
