#!/usr/bin/env python3
"""Check that the abstract of a built version answers every question it asks, keeps every answer the previous version gave, and
meets the IEEE Access form (the lesson of 26 November 2026: trimming the V91 abstract to 250 words removed "none reports a test
against denial of service" while the abstract still asked about denial of service, the gap first fixed in V89; every check passed,
because the worded-claims check tests the count behind a claim, not that the text still states it).

On build/paper-V<n>.md (or, from build.py, on the text being built):
- form: one paragraph of 150 to 250 words; no abbreviation of thematic.ABBREVIATIONS used as a word;
- asked and answered: every item of ITEMS named in the question sentence ("… investigates whether …") is named again in a later
  sentence of the abstract;
- kept: every item answered in the abstract of the previous built version is still answered (a trim never drops an answer);
- required: the three conditions named and the headline finding stated (the standing rule on the abstract).
Exit code 1 when anything fails. build.py runs the same check before it renders, so a failing abstract stops the build.

Usage: python3 scripts/paper_ppml/abstract_check.py <version>
"""
import pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
BUILD = ROOT / 'myliteraturereviewpaper' / 'ppml2026' / 'build'
ITEMS = {                         # what the abstract asks about, and how a later sentence names it
    'poisoning': r'poison',
    'malicious or fake participants': r'malicious or fake',
    'free riding': r'free[- ]rid',
    'denial of service': r'denial of service',
    'cost on edge devices': r'\bcost',
    'privacy': r'privacy|personal data|conceal',
}
REQUIRED = {
    'the three conditions named': r'three conditions',
    'C1 named (cost on device-class hardware)': r'device-class hardware',
    'C2 named (updates concealed from every verifying or aggregating party)': r'(?:verif|check)\w* or aggregat',
    'C3 named (a test against poisoning, malicious or fake participants or free riding)': r'test against poisoning',
    'the headline finding (no design meets all three)': r'[Nn]o (?:included )?design[^.]{0,30}meets all three',
}
QUESTION = re.compile(r'\b(?:investigat\w*|asks?|examin\w*|assess\w*) whether\b', re.I)


def abstract_of(md):
    m = re.search(r'^\*\*Abstract\*\* — (.+)$', md, re.M)
    return m.group(1).strip() if m else ''


def sentences(t):
    return [s for s in re.split(r'(?<!\bal\.)(?<=[.;])\s+(?=[A-Z0-9])', t) if s.strip()]


def answered(text):
    """the items named after the question sentence (all items named anywhere when there is no question sentence)"""
    ss = sentences(text)
    q = next((i for i, s in enumerate(ss) if QUESTION.search(s)), None)
    later = ' '.join(ss[q + 1:] if q is not None else ss)
    asked = {k for k, p in ITEMS.items() if q is not None and re.search(p, ss[q], re.I)}
    return asked, {k for k, p in ITEMS.items() if re.search(p, later, re.I)}


def problems(text, prev_text=None):
    out = []
    words = len(text.split())                                       # words as a reader counts them: space-separated
    if not 150 <= words <= 250:
        out.append(f'abstract: {words} words (IEEE Access: 150 to 250)')
    sys.path.insert(0, str(pathlib.Path(__file__).parent))
    import thematic as T
    for short, _ in T.ABBREVIATIONS:
        for form in re.split(r'\s*/\s*|–', short):
            if len(form) > 1 and re.search(rf'(?<![\w-]){re.escape(form)}(?![\w-])', text):
                out.append(f'abstract: abbreviation "{form}" (the abstract uses full names)')
    asked, ans = answered(text)
    for k in sorted(asked - ans):
        out.append(f'abstract: asks about {k} but no later sentence answers it')
    if prev_text:
        _, prev_ans = answered(prev_text)
        for k in sorted(prev_ans - ans):
            out.append(f'abstract: the previous version answered {k}; this one no longer does')
    for what, p in REQUIRED.items():
        if not re.search(p, text, re.I):
            out.append(f'abstract: {what} missing')
    return out


def main(version):
    text = abstract_of((BUILD / f'paper-V{version}.md').read_text(encoding='utf-8'))
    prev = BUILD / f'paper-V{version - 1}.md'
    prev_text = abstract_of(prev.read_text(encoding='utf-8')) if prev.exists() else None
    found = problems(text, prev_text)
    asked, ans = answered(text)
    print(f'abstract of V{version}: {len(text.split())} words; asks about {len(asked)} item(s), answers {len(ans & asked)} of them')
    for p in found:
        print('FAIL', p)
    print(f'{len(found)} problem(s)' if found else 'the abstract answers every question it asks and keeps every earlier answer')
    return 1 if found else 0


if __name__ == '__main__':
    sys.exit(main(int(sys.argv[1])))
