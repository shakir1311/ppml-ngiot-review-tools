#!/usr/bin/env python3
"""Flag the review's own terms used before the paper defines them, and terms it never defines, in a built version (the lesson of
9 November 2026: a supervisor found passages that did not make sense; every check tested correctness, none asked whether a reader
without the records could follow, and words such as fabric, record, agenda, deliverable and conditions were used in the abstract
and the introduction long before the sections that defined them).

Reads build/paper-V<n>.md. For each term of TERMS the first sentence matching its definition pattern is its definition; every use
before it is reported with its section, and a use in the abstract is reported unless the abstract itself defines the term (the
abstract has to stand alone; a field's own threat names, free riding, Sybil, Byzantine, may stand there undefined). A term with uses and no definition anywhere is reported as never defined. Captions count as text
where they sit; table rows and the references do not. A term may be scoped to the sections where it is the review's own word
(validators is also what some designs call their nodes). New terms go into TERMS: (name, use pattern, definition pattern, scope).
Exit code 1 when anything is reported.

Usage: python3 scripts/paper_ppml/terms_check.py <version> [--all]   (--all: print every term's definition sentence as well)
"""
import html, pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
BUILD = ROOT / 'myliteraturereviewpaper' / 'ppml2026' / 'build'

BODY = ('I', 'II', 'III', 'IV', 'V', 'VI', 'VII', 'VIII', 'Appendix', 'Declarations')   # every section but the abstract: a field's own
                                                                                      # threat names may stand in the abstract undefined



# (name, where it is used, where it is defined, sections whose uses count: None = everywhere; a prefix such as 'VII-A')
TERMS = [
    ('fabric', r'\bfabrics?\b',
     r'fabric, (?:that is, )?the devices and links that carry it and the tiers they form|The fabric is the devices and links on which learning runs', None),
    ('record (an extraction record)',
     r"\b(?:page-cited|extraction|verified|own) records?\b|\bits record\b|\bfrom (?:its|their) records?\b|\bthe record (?:shows|does not show)\b",
     r"record of what (?:the|each) design's paper states, cited to its page|Every answer carries the pages and verbatim quotations", None),
    ('agenda', r'\bagenda\b', r'research agenda|An agenda closes the paper: a design|agenda, a design', None),
    ('deliverable', r'\bdeliverables?\b', r'the deliverable, the part of the agenda that takes it up|three deliverables, one per condition', None),
    ('the three conditions (C1 to C3)', r'\bthe three conditions\b|\bconditions? C[123]\b|\bC[123]\b|\bthe condition the agenda\b',
     r'Three conditions then follow, one per question|We defined three conditions|[Tt]hree conditions that a design answering all three questions would (?:meet|satisfy)|'
     r'Each question leaves one condition for the agenda', None),
    ("validators (the design's checking gateways)", r'\bvalidators?\b', r'A small group of gateways, the validators',
     ('Abstract', 'I', 'VI', 'VII-A', 'VIII')),
    ('probes (labelled test rows)', r'\bprobes?\b|\bprobe check\b',
     r'test rows with known labels, the probes|labelled test rows, the probes|probe rows drawn from the validation split, so the probes carry labels', None),
    ('SQ1 to SQ3', r'\bSQ[123]\b', r'three study questions \(SQ1 to SQ3\)', None),
    ('enclave', r'\benclaves?\b', r'enclave \(a protected (?:part|region) of a processor|inside an enclave that its host cannot read', None),
    ('fingerprint (a commitment)', r'\bfingerprints?\b', r'fingerprint of each update \(a commitment\)', None),
    ('secret shares', r'\bsecret shares?\b|\bsecret-shared\b', r'split into secret shares|secret sharing and masked secure aggregation split an update', None),
    ("anchor (FL-BC-IDS's committed predictions)", r'\banchors?\b|\banchor-sum\b',
     r'anchors?[^.]{0,40}\((?:its|the) committed predictions|\(anchors?\)|the anchors, each vehicle\'s committed predictions|anchors FL-BC-IDS commits \(each vehicle|anchor (?:payloads?|vectors?)[^.]{0,20}, (?:the|its|that is)[^.]{0,40}predictions', None),
    ('free riding', r'\bfree[- ]rid(?:ing|ers?)\b', r'Free riders take the global model without training|free[- ]rid(?:ing|ers?)[^.]{0,12}\(|'
     r'free[- ]rid(?:ing|ers?), (?:that is|taking) the global model|free-ride: take the global model|free-ride by obtaining the global model', BODY),
    ('Sybil', r'\bSybils?\b', r'Sybil clients among them|among them Byzantine and Sybil clients|fake \(Sybil\)|Sybil \(', BODY),
    ('Byzantine', r'\bByzantine\b', r'Byzantine and Sybil clients among them|among them Byzantine and Sybil clients|Byzantine \(', BODY),
]

SPLIT = re.compile(r'(?<=[.!?])\s+(?=[A-Z\[("“*])')


def sections(md):
    """(label, sentence) in document order: the abstract as 'Abstract', then the body by its headings; table rows and the
    references left out; Key Takeaways boxes read as the sentences of their section."""
    out = []
    m = re.search(r'^\*\*Abstract\*\* — (.+)$', md, re.M)
    if m:
        out += [('Abstract', s) for s in SPLIT.split(m.group(1))]
    label, top, i, lines = None, None, 0, md.splitlines()
    while i < len(lines):
        line = lines[i]
        if line.startswith('# '):
            top = re.match(r'# ([IVX]+|Appendix|Declarations|References)', line)
            top = top.group(1) if top else line[2:].strip()
            label = top
        elif line.startswith('## '):
            sub = re.match(r'## ([A-Z])\.', line)
            label = f'{top}-{sub.group(1)}' if sub else top
        elif line.startswith('```{=openxml}'):
            j = i + 1
            while j < len(lines) and not lines[j].startswith('```'):
                j += 1
            texts = [html.unescape(t) for t in re.findall(r'<w:t(?: [^>]*)?>([^<]*)</w:t>', '\n'.join(lines[i + 1:j]))]
            out += [(label, t) for t in texts if t.strip() not in ('', '•', 'Key Takeaways')]
            i = j + 1
            continue
        elif label and top not in ('References',) and line.strip() and not line.startswith(('|', '---', 'title:', 'author:')):
            text = re.sub(r'^!\[(.*)\]\(.*\)(\{.*\})?$', r'\1', line.strip())        # a figure line: its caption
            text = re.sub(r'^Table: ', '', text)
            out += [(label, s) for s in SPLIT.split(text) if s.strip()]
        i += 1
    return [(l, s) for l, s in out if l and l != 'Front']


def in_scope(label, scope):
    return scope is None or any(label == s or label.startswith(s + '-') for s in scope)


def main(version, show_all=False):
    md = (BUILD / f'paper-V{version}.md').read_text(encoding='utf-8')
    sents = sections(md)
    problems = 0
    for name, use, define, scope in TERMS:
        use_re, def_re = re.compile(use), re.compile(define)
        abstract = [(l, s) for l, s in sents if l == 'Abstract']
        body = [(l, s) for l, s in sents if l != 'Abstract']
        def_body = next((k for k, (l, s) in enumerate(body) if def_re.search(s)), None)
        if show_all and def_body is not None:
            print(f'[{name}] defined in {body[def_body][0]}: "{body[def_body][1][:150]}"')
        if in_scope('Abstract', scope) and not any(def_re.search(s) for l, s in abstract):
            for l, s in abstract:
                if use_re.search(s):
                    problems += 1
                    print(f'[{name}] used in the abstract, which has to stand alone, without its definition: "{s[:160]}"')
        uses = [(k, l, s) for k, (l, s) in enumerate(body) if use_re.search(s) and in_scope(l, scope) and not def_re.search(s)]
        if def_body is None:
            if uses:
                problems += 1
                k, l, s = uses[0]
                print(f'[{name}] never defined; first use ({l}, {len(uses)} use(s) in all): "{s[:160]}"')
            continue
        for k, l, s in uses:
            if k < def_body:
                problems += 1
                print(f'[{name}] used before its definition ({body[def_body][0]}), in {l}: "{s[:160]}"')
    print(f'{problems} problem(s)' if problems else 'every term of TERMS is defined before it is used, and the abstract stands alone')
    return 1 if problems else 0


if __name__ == '__main__':
    sys.exit(main(int(sys.argv[1]), '--all' in sys.argv))
