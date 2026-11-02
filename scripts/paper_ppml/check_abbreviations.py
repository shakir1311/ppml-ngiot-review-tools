#!/usr/bin/env python3
"""Check every abbreviation of the PPML review as built (myliteraturereviewpaper/ppml2026/build/paper-V<n>.md).

For the abstract and, separately, the body (Section I to the Appendices, with the tables, figure captions and the Key
Takeaways boxes; the reference list is left out), every token that looks like an abbreviation (two or more capitals, or
mixed case such as IoT, PoW, FedAvg, or 5G) is reduced to its base (ZKPs -> ZKP, SQ1 -> SQ) and checked:
  - is it spelled out where it is first used, as "long form (ABBR)", and not used before that;
  - is it in the List of Abbreviations, and does the long form in the text match the list;
  - is it spelled out more than once, or in two different ways;
and every entry of the List of Abbreviations must be used in the body. Names (schemes, data sets, platforms, tools,
organisations, units) are listed apart: they need no expansion. Nothing is changed; the findings are printed.

Usage: python3 scripts/paper_ppml/check_abbreviations.py <version>
"""
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
B = ROOT / 'myliteraturereviewpaper' / 'ppml2026' / 'build'

TOKEN = re.compile(r'(?<![\w./-])((?:[A-Za-z]*[A-Z][a-z]*[A-Z][A-Za-z0-9]*|[a-z]+[A-Z][A-Za-z0-9]*|\d+G)(?:-[A-Za-z0-9]+)*)(?![\w])')
ROMAN = re.compile(r'^[IVXL]+$')


def base(t):
    t = re.sub(r'(?<=[A-Z])s$', '', t)                        # ZKPs -> ZKP, TEEs -> TEE
    t = re.sub(r'(?<=[A-Z])\d+[a-g]?$', '', t)               # SQ1 -> SQ, IC3f -> IC, QA6 -> QA
    return t


def text_of(md):
    """the paper as plain text: openxml boxes reduced to their words, images to their captions"""
    md = re.sub(r'```\{=openxml\}\n(.*?)\n```', lambda m: ' '.join(re.findall(r'<w:t[^>]*>([^<]*)</w:t>', m.group(1))), md, flags=re.S)
    md = re.sub(r'!\[(.*?)\]\([^)]*\)(\{[^}]*\})?', r'\1', md)
    return md


def norm(s):
    return re.sub(r'[^a-z0-9 ]', '', re.sub(r'[-–/]', ' ', s.lower())).split()


def main(v):
    md = text_of((B / f'paper-V{v}.md').read_text(encoding='utf-8'))
    head, _, rest = md.partition('\n# I. Introduction')
    body = ('# I. Introduction' + rest).split('\n# References')[0]
    abstract = head.split('**List of Abbreviations**')[0]
    listed = {}
    for row in re.findall(r'^\| (.+) \|$', head.split('**List of Abbreviations**')[1], re.M):
        cells = [c.strip() for c in row.split(' | ')]
        for a, m in zip(cells[0::2], cells[1::2]):
            if a and a not in ('Term', 'Term ') and not set(a) <= set('-'):
                for x, y in zip(a.split(' / '), m.split(' / ')):
                    listed[x.strip()] = y.strip()

    def survey(txt):
        uses = {}
        for m in TOKEN.finditer(txt):
            t = m.group(1)
            if ROMAN.match(t) or re.match(r'^[IVXL]+-[A-H]$', t):
                continue
            uses.setdefault(base(t), []).append(m.start())
        defs = {}
        for m in re.finditer(r'\(([A-Za-z0-9][A-Za-z0-9-]*?)s?\)', txt):
            a = m.group(1)
            defs.setdefault(a, []).append(m.start())
        return uses, defs

    def long_before(txt, pos, n):
        words = re.findall(r"[\w'-]+", txt[max(0, pos - 200):pos])
        return ' '.join(words[-n:])

    out = []
    for name, txt in (('ABSTRACT', abstract), ('BODY', body)):
        uses, defs = survey(txt)
        out.append(f'== {name}: {len(uses)} abbreviation-like tokens')
        for a in sorted(uses, key=lambda x: uses[x][0]):
            first = uses[a][0]
            d = [p for p in defs.get(a, [])]
            in_list = a in listed
            if d:
                dpos = d[0]
                used_before = [p for p in uses[a] if p < dpos]
                lf = long_before(txt, dpos, len(norm(listed[a])) if in_list else 4)
                match = (norm(lf)[-len(norm(listed[a])):] == norm(listed[a])) if in_list else None
                flags = []
                if used_before:
                    flags.append(f'used {len(used_before)}x before its definition')
                if len(d) > 1:
                    flags.append(f'spelled out {len(d)}x')
                if in_list and not match:
                    flags.append(f'text "{lf}" vs list "{listed[a]}"')
                if name == 'BODY' and not in_list:
                    flags.append('defined but not in the list')
                out.append(f"  {'!!' if flags else 'ok'} {a} ({len(uses[a])} uses) defined as \"{lf}\"" + (': ' + '; '.join(flags) if flags else ''))
            else:
                out.append(f"  ?? {a} ({len(uses[a])} uses){' — in the list as ' + repr(listed[a]) if in_list else ''}: never spelled out in the "
                           f"{name.lower()}; first use …{txt[max(0, first - 70):first + 40].replace(chr(10), ' ')}…")
        if name == 'BODY':
            for a in sorted(listed):
                if a not in uses and a not in ('5G', '6G'):
                    out.append(f'  -- {a} is in the list but not used in the body')
    print('\n'.join(out))


if __name__ == '__main__':
    main(sys.argv[1])
