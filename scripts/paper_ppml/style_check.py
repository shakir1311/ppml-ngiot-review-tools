#!/usr/bin/env python3
"""Scan the prose of a built version of the PPML review for the writing rules of 15 October 2026 (CLAUDE.md): banned words;
preambles ("In this section", "This section"); contrastive pivots ("not X, but Y", "it is not X, it is Y"); rhetorical
questions followed by an instruction; three sentences in a row of about the same length (within 15%); groups of three
single words joined "A, B and C". Tables, captions, headings, references and the front matter are left out. Each line
printed names the section and quotes our own sentence. Usage: python3 scripts/paper_ppml/style_check.py <version>
"""
import pathlib, re, sys
ROOT = pathlib.Path(__file__).resolve().parents[2]
B = ROOT / 'myliteraturereviewpaper' / 'ppml2026' / 'build'
BANNED = re.compile(r'\b(delv\w*|tapestr\w*|testament|paramount|leverag\w*|multifaceted|bolster\w*|furthermore|moreover|in conclusion)\b', re.I)
PIVOT = re.compile(r"\b(it is|this is|that is|it's|that's) not [^.;]{2,60}?,? (it is|it's|but)\b|\bnot (only|just|merely) [^.;]{2,60}?,? but (also )?\b", re.I)
PREAMBLE = re.compile(r'^(In this (section|paper|article|review)|This (section|paper|article) (will|describes|presents|discusses))', re.I)
TRIAD = re.compile(r'\b(\w+), (\w+),? and (\w+)\b')

def main(v):
    text = (B / f'paper-V{v}.md').read_text(encoding='utf-8')
    body = text.split('\n# References')[0]
    body = body.split('**List of Abbreviations**')[-1]
    sec, out = '', []
    for para in body.split('\n\n'):
        p = para.strip()
        if not p or p.startswith('|') or p.startswith('Table:') or p.startswith('![') or p.startswith('```') or p.startswith('<w:') or p.startswith('{{'):
            continue
        if p.startswith('#'):
            sec = p.lstrip('# ').strip(); continue
        p = re.sub(r'^\d+\. |^- ', '', p)
        p = re.sub(r'\[\d{1,3}\](?:[–-]\[\d{1,3}\])?', '', p)
        sents = [x.strip() for x in re.split(r'(?<=[.!?])\s+(?=[A-Z0-9(])', p) if x.strip()]
        for i, x in enumerate(sents):
            for m in BANNED.finditer(x): out.append((sec, 'banned word', m.group(0), x))
            if PIVOT.search(x): out.append((sec, 'contrastive pivot', PIVOT.search(x).group(0), x))
            if PREAMBLE.search(x): out.append((sec, 'preamble', '', x))
            if x.endswith('?') and i + 1 < len(sents) and re.match(r'^(Try|Use|Do|Start|Make|Take|Run)\b', sents[i + 1]): out.append((sec, 'hook and answer', '', x))
            for m in TRIAD.finditer(x):
                a, b, c = m.groups()
                if all(len(w) > 2 and w[0].islower() for w in (a, b, c)): out.append((sec, 'group of three', m.group(0), x))
        L = [len(x.split()) for x in sents]
        for i in range(len(L) - 2):
            a, b, c = L[i:i + 3]
            if min(a, b, c) >= 6 and max(a, b, c) <= 1.15 * min(a, b, c):
                out.append((sec, 'three sentences of about the same length', f'{a}/{b}/{c} words', sents[i][:80] + ' …'))
    for sec, kind, hit, x in out:
        print(f'[{kind}] {sec[:38]:38} | {hit[:40]:40} | {x[:140]}')
    print(f'{len(out)} finding(s)')

if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else '68')
