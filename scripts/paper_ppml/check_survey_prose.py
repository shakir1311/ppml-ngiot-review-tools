#!/usr/bin/env python3
"""Check the surveys-by-subject prose for Section II (search-ppml/evidence/surveys-v72/SECTION-II-SURVEYS.md): every
included survey (a sheet with an S1 answer) is cited; every sentence ends with one or more ⟦id:S1⟧ markers; a marker's id
is cited in that sentence; no id outside the included surveys; only the allowed abbreviations; no banned, judgement or
evaluation word; 350 to 500 words; no number that its cited S1 answers do not state. Prints the problems; exit 1 if any.
Usage: python3 scripts/paper_ppml/check_survey_prose.py [file]
"""
import glob, json, pathlib, re, sys
ROOT = pathlib.Path(__file__).resolve().parents[2]
F = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / 'search-ppml/evidence/surveys-v72/SECTION-II-SURVEYS.md'
SHEETS = ROOT / 'search-ppml/evidence/sheets'
ALLOWED_ABBR = {'FL', 'ML', 'PPML', 'IoT', 'NG-IoT', '5G', '6G', 'ZKP', 'ZKPs', 'GDPR', 'EDPB', 'II', 'III', 'S1', 'SQ1', 'SQ2', 'SQ3', 'TAB', 'FIG', 'C', 'N'}   # TAB/FIG/N/C: the build's placeholders when a parts file is checked
BAD = re.compile(r'\b(delv\w*|tapestr\w*|testament|paramount|leverag\w*|multifaceted|bolster\w*|furthermore|moreover|in conclusion|'
                 r'fails?|failed|lacks?|lacking|ignor\w*|neglect\w*|merely|only|weak|poor|limited|outdated|comprehensive|thorough|seminal|'
                 r'claims?|claimed|overlook\w*|omits?|omitted|silent|absent|nothing)\b', re.I)
MARK = re.compile(r'⟦([^⟧]+)⟧'); CITE = re.compile(r'\[@([\w-]+)\]')
NUM = re.compile(r'(?<![A-Za-z0-9@-])\d+(?:[.,]\d+)*')


def main():
    text = ' '.join(F.read_text(encoding='utf-8').split())
    surveys = {pathlib.Path(f).stem: json.load(open(f))['answers']['S1'] for f in glob.glob(str(SHEETS / '*.json')) if 'S1' in json.load(open(f)).get('answers', {})}
    probs = []
    cited = set(CITE.findall(text))
    for s in sorted(set(surveys) - cited): probs.append(f'survey not cited: {s}')
    for s in sorted(cited - set(surveys)): probs.append(f'cited but not an included survey: {s}')
    words = len(re.sub(r'⟦[^⟧]+⟧|\[@[\w-]+\]', '', text).split())
    if F.name == 'SECTION-II-SURVEYS.md' and not 350 <= words <= 500: probs.append(f'{words} words (350 to 500 wanted)')   # a parts file holds the whole section
    for m in BAD.finditer(re.sub(r'⟦[^⟧]+⟧|\[@[\w-]+\]', '', text)): probs.append(f'word to avoid: "{m.group(0)}"')
    names = set(re.findall(r'([A-Z][A-Za-z\'-]+)(?: and [A-Z][A-Za-z\'-]+)? (?:et al\.|\[@)', text)) | set(re.findall(r'[A-Z][A-Za-z\'-]+ and ([A-Z][A-Za-z\'-]+) \[@', text))
    for ab in set(re.findall(r'\b[A-Z][A-Za-z0-9-]*[A-Z0-9][A-Za-z0-9-]*\b', re.sub(r'⟦[^⟧]+⟧|\[@[\w-]+\]', '', text))) - ALLOWED_ABBR - names:
        probs.append(f'abbreviation not allowed here: {ab}')
    # sentences: split on the end of a marker run or on . ! ? followed by a capital
    for s in re.split(r'(?<=⟧)\s+(?=[A-Z])|(?<=[.!?])\s+(?=[A-Z(])', text):
        s = s.strip()
        if not s: continue
        marks = MARK.findall(s)
        ids = set(CITE.findall(s))
        if not ids and not marks: continue                      # our own framing sentence, no survey cited
        if not marks: probs.append(f'no marker: {s[:80]}…'); continue
        src = ''
        for mk in marks:
            sid, _, key = mk.partition(':')
            if key.strip() != 'S1': probs.append(f'marker key is not S1: {mk}')
            if sid not in ids: probs.append(f'marker {sid} but the sentence does not cite it: {s[:70]}…')
            src += ' ' + json.dumps(surveys.get(sid, {}), ensure_ascii=False)
        have = {x.replace(',', '') for x in NUM.findall(src)}
        for n in NUM.findall(re.sub(r'⟦[^⟧]+⟧|\[@[\w-]+\]', '', s)):
            if n.replace(',', '') not in have: probs.append(f'number {n} not in the cited answers: {s[:80]}…')
    print('\n'.join(probs) if probs else f'OK: {len(cited)} surveys cited, {words} words')
    sys.exit(1 if probs else 0)


if __name__ == '__main__':
    main()
