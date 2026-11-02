#!/usr/bin/env python3
"""Lint the V18 text parts before they count as drafted (the rules of _src/V18/PLAN.md).

Checks: every cited key exists and is an included study or an allowed foundation or method work; every number, table
and figure key exists; references to tables and figures are placed somewhere in the paper; no meta words; Biscotti at
most once in the paper; research questions (RQ) only in Section VIII (part 08); no «…» markers left.

Usage: scripts/.venv/bin/python scripts/review/check_v18.py [NN ...]      (default: every part)
"""
import json, os, pathlib, re, sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import tables_v18 as T         # noqa: E402

TXT = pathlib.Path(os.environ.get('V18_PARTS', T.SRC18))    # V26: lint the staged parts before installing them
REFS = json.loads((T.V16.V14.ROOT / 'myliteraturereviewpaper' / '_src' / 'V14' / 'references.json').read_text())['refs']
# Outside the included studies the review cites only these three, each with its PDF in the workspace (the user's rule,
# 30 Sep 2026: no old literature, nothing that is not with us): the GDPR, PRISMA 2020 and the EDPB guidelines.
FOUNDATIONS = {'gdpr2016', 'page2021', 'edpb2026'}
META = re.compile(r'(?i:\b(PhD|proposal|supervisors?|drafts?|coding|coded)\b|\b(this|previous|earlier|next|new|last) '
                  r'versions?\b|\bthe author\'s interest)|\bCHECK\b|\bV1\d\b')


def main(which):
    d = T.load()
    s = T.stats(d)
    tabs = T.tables(d, s)
    figs = T.figures(d, s)
    included = set(d['included'])
    parts = sorted(TXT.glob('V18-part*.md'))
    whole = '\n'.join(p.read_text(encoding='utf-8') for p in parts)
    placed = {('tab', m) for m in re.findall(r'^\{\{TAB:([\w-]+)\}\}$', whole, re.M)} | \
             {('fig', m) for m in re.findall(r'^\{\{FIG:([\w-]+)\}\}$', whole, re.M)}
    bad = 0
    for p in parts:
        nn = p.stem[-2:]
        if which and nn not in which:
            continue
        t = re.sub(r'<!--.*?-->', '', p.read_text(encoding='utf-8'), flags=re.S)
        errs = []
        keys = [k.strip().lstrip('@') for m in re.findall(r'\[@([^\]]+)\]', t) for k in m.split(';')]
        keys += re.findall(r'(?<![\w@\[])@([A-Za-z][A-Za-z0-9]+)', re.sub(r'\[@[^\]]+\]', '', t))
        for k in sorted(set(keys)):
            if k not in REFS:
                errs.append(f'unknown citation {k}')
            elif k not in included and k not in FOUNDATIONS:
                errs.append(f'cited but neither an included study nor the GDPR, PRISMA or EDPB: {k}')
            elif k != 'gdpr2016' and int(str(REFS[k].get('year', 0))[:4] or 0) < 2020:
                errs.append(f'cites old literature (before 2020): {k} {REFS[k].get("year")}')
        for k in sorted(set(re.findall(r'\{\{N:([\w-]+)\}\}', t))):
            if k not in s:
                errs.append(f'unknown number {k}')
        for k in sorted(set(re.findall(r'^\{\{TAB:([\w-]+)\}\}$', t, re.M))):
            if k not in tabs:
                errs.append(f'unknown table {k}')
        for k in sorted(set(re.findall(r'^\{\{FIG:([\w-]+)\}\}$', t, re.M))):
            if k not in figs:
                errs.append(f'unknown figure {k}')
        for kind, k in sorted(set(re.findall(r'\{\{ref:(tab|fig):([\w-]+)\}\}', t))):
            if (kind, k) not in placed:
                errs.append(f'reference to a {kind} not placed in the paper: {k}')
        body = re.sub(r'^::: declaration\n.*?^:::$', '', t, flags=re.S | re.M)    # the AI-use declaration says 'draft'
        for m in META.finditer(body):
            line = body[:m.start()].count('\n') + 1
            errs.append(f'meta word "{m.group(0)}" (line {line})')
        if nn != '08' and re.search(r'\bRQ\d', t):          # V26: the research agenda is Section VIII (part 08)
            errs.append('research questions (RQ) outside Section VIII')
        for m in re.finditer(r'«[^»]*»', t):
            errs.append(f'unresolved marker {m.group(0)[:60]}')
        words = len(re.sub(r'\{\{[^}]+\}\}|\[@[^\]]+\]', '', t).split())
        print(f'part {nn}  {p.name}  {words} words  ' + ('PASS' if not errs else 'FAIL'))
        for e in errs:
            print('    ' + e)
        bad += bool(errs)
    n = len(re.findall(r'Biscotti', whole))
    if n > 1:
        print(f'Biscotti is named {n} times in the paper (at most once)')
        bad += 1
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main(set(sys.argv[1:]))
