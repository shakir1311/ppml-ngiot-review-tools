#!/usr/bin/env python3
"""Split a paper's extracted pages into its sections, and pick the sections that answer a given question.

A section starts at a heading line: a numbered heading ('II. SYSTEM MODEL', '4.2 Threat model', 'B. Consensus') or a
known section name on a line of its own ('Abstract', 'Conclusion'). The reference list (the last 'References' /
'Bibliography' heading) and related-work sections are never given to a model: they are about other people's work.

For each evidence-sheet question, the sections whose heading names its topic are given, always with the abstract and,
as a safety net, the pages where the question's own words appear most (a fact can sit in an unexpected place). When a
paper's headings cannot be found, the whole paper (without the reference list) is given instead.
"""
import re
from pathlib import Path

SECTION_NAMES = (r'abstract|introduction|related works?|background|literature review|preliminar(?:y|ies)|system model|'
                 r'threat model|security model|adversary model|problem (?:statement|formulation|definition)|methodology|'
                 r'methods?|proposed [a-z ]+|design|architecture|security analysis|privacy analysis|'
                 r'(?:performance )?evaluation|experiments?(?: and results)?|results(?: and discussion)?|discussion|'
                 r'conclusions?(?: and future work)?|future work|limitations|acknowledge?ments?|'
                 r'state[- ]of[- ]the[- ]art|(?:prior|previous|existing|earlier) (?:works?|studies|approaches|solutions)')
HEADING = re.compile(r'^\s*(?:(?:[IVX]{1,5}\.|[A-H]\.|\d{1,2}(?:\.\d{1,2})*\.?)\s+[A-Z][A-Za-z0-9 ,:&/()\-–]{2,80}|'
                     r'(?:' + SECTION_NAMES + r'))\s*$', re.I)
REFERENCES = re.compile(r'^\s*(?:(?:[IVX]{1,5}|\d{1,2})\.?\s+)?(?:references|bibliography|reference list)\s*$', re.I)
OTHER_WORK = re.compile(r'related works?|literature review|state[- ]of[- ]the[- ]art|(?:prior|previous|existing|earlier) '
                        r'(?:works?|studies|approaches|solutions)', re.I)

# words in a heading that make the section relevant to a question (matched as word starts, case-insensitive)
TOPICS = {
    'P1': 'introduction system architecture framework overview proposed design model implementation setup scenario network',
    'P2': 'privacy proposed scheme protocol design framework encrypt aggregation security preliminar method model',
    'P3': 'blockchain ledger consensus chain contract system architecture framework implementation proposed design',
    'P4': 'verif validat proof zero consensus aggregation proposed protocol security audit',
    'P5': 'threat adversar attack security privacy defen experiment evaluation result robust',
    'P6': 'experiment evaluation result performance implementation setup simulation dataset discussion',
    'P7': 'introduction discussion conclusion regulat legal complian gdpr privacy',
    'P8': 'conclusion limitation discussion future',
}
QUESTION_WORDS = {
    'P1': 'device edge fog cloud 5g 6g iot vehicle server tier hardware raspberry network latency',
    'P2': 'privacy differential encrypt homomorphic secret share mask noise leak inference',
    'P3': 'blockchain ledger consensus smart contract chain hyperledger ethereum block on-chain',
    'P4': 'verify verification proof zero-knowledge zkp snark check validate reputation',
    'P5': 'attack adversary malicious poisoning byzantine sybil collusion threat defend robust',
    'P6': 'dataset accuracy baseline compare experiment result hardware code github',
    'P7': 'gdpr regulation law legal personal data erasure forgotten compliance hipaa',
    'P8': 'limitation future work conclusion drawback',
}


SMALL = set('a an and as at by for from in into of on or the to under via with without vs'.split())


def is_heading(line):
    """A real heading: matches HEADING, has no closing full stop, starts with a capital, and is either in capitals or
    title case (up to ten words) or short (up to five words, as in 'Threat model'); a numbered list item such as
    '3. Compute the hash of the input.' or a sentence such as '2 The server sends the model to all clients' is not."""
    s = line.strip()
    if not HEADING.match(s) or len(s.split()) > 10 or s.endswith(('.', ',', ';', ':')) and not re.fullmatch(r'[IVX]+\.', s):
        return False
    if re.fullmatch(SECTION_NAMES, s, re.I):
        return True
    words = [w for w in re.sub(r'^(?:[IVX]{1,5}\.|[A-H]\.|\d{1,2}(?:\.\d{1,2})*\.?)\s+', '', s).split() if w.isalpha()]
    big = [w for w in words if w.lower() not in SMALL]
    if not big or not words[0][0].isupper():
        return False
    title_case = sum(w[0].isupper() for w in big) / len(big) >= 0.6
    return title_case or len(words) <= 5                # 'Threat model' (sentence case) is a heading; a long sentence is not


def split(pages):
    """pages: {n: text}. Returns [{'title', 'kind': 'abstract'|'own'|'other work'|'references', 'parts': [(page, text)]}]."""
    lines = [(n, line) for n in sorted(pages) for line in pages[n].splitlines()]
    ref_at = max((i for i, (n, l) in enumerate(lines) if REFERENCES.match(l) and n > 1), default=None)
    sections = [{'title': '(start)', 'kind': 'own', 'parts': []}]
    for i, (n, line) in enumerate(lines):
        if ref_at is not None and i == ref_at:
            sections.append({'title': line.strip(), 'kind': 'references', 'parts': []})
            continue
        if (ref_at is None or i < ref_at) and is_heading(line):
            title = line.strip()
            kind = ('abstract' if re.fullmatch(r'abstract', title, re.I) else
                    'other work' if OTHER_WORK.search(title) else 'own')
            sections.append({'title': title, 'kind': kind, 'parts': []})
            continue
        parts = sections[-1]['parts']
        if parts and parts[-1][0] == n:
            parts[-1] = (n, parts[-1][1] + '\n' + line)
        else:
            parts.append((n, line))
    return [s for s in sections if any(t.strip() for _, t in s['parts'])]


def pick(pages, question, extra_pages=3):
    """The text to give a model for one question, as (text, info). info holds counts only (no paper words)."""
    secs = split(pages)
    headed = [s for s in secs if s['title'] != '(start)']
    usable = [s for s in secs if s['kind'] != 'references']
    if len(headed) < 4:                                   # headings not found: whole paper without the reference list
        chosen = usable
        mode = 'whole paper (headings not found)'
    else:
        words = TOPICS.get(question, '').split()
        chosen = [s for s in usable if s['kind'] != 'other work' and (
            s['title'] == '(start)' or s['kind'] == 'abstract' or
            any(re.search(r'\b' + w, s['title'], re.I) for w in words))]
        mode = 'sections'
        # safety net: the pages where the question's words occur most, if not given already
        given = {n for s in chosen for n, _ in s['parts']}
        qw = QUESTION_WORDS.get(question, '').split()
        score = {}
        for s in usable:
            if s['kind'] == 'other work':
                continue
            for n, t in s['parts']:
                low = t.lower()
                score[n] = score.get(n, 0) + sum(low.count(w) for w in qw)
        for n in sorted((n for n in score if n not in given), key=lambda n: -score[n])[:extra_pages]:
            if score[n] > 0:
                chosen.append({'title': '(page with the question\'s words)', 'kind': 'own',
                               'parts': [(n, t) for s in usable if s['kind'] != 'other work' for m, t in s['parts'] if m == n]})
    out, pages_given = [], set()
    for s in chosen:
        for n, t in s['parts']:
            out.append(f'=== PAGE {n} === [{s["title"][:80]}]\n{t.strip()}')
            pages_given.add(n)
    info = {'mode': mode, 'sections_found': len(headed), 'sections_given': len(chosen),
            'pages_given': len(pages_given), 'pages_total': len(pages),
            'words_given': sum(len(x.split()) for x in out), 'words_total': sum(len(t.split()) for t in pages.values())}
    return '\n\n'.join(out), info
