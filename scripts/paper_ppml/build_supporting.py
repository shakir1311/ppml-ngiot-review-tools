#!/usr/bin/env python3
"""The supporting document of the PPML review (from V77): what the author took out of the paper's appendices on
16 October 2026 ("we don't need appendix C and appendix A … put them in a separate supporting document, and no need to
refer to that supporting document in the paper"): the full search strings, the eligibility criteria, every design
graded against the three conditions, and (from V84) the set-up of the first experiment. The paper does not refer to this document.

The tables are those the build wrote for the version (build/tables/strings_full.md, criteria.md, conditions.md), so
their numbers and citations are those of the paper; citations carry the numbers of the paper's reference list
(build/BUILD-REPORT-V<n>.json), so the paper must be built first. Rendered to <NAME> - V<n> supporting document.docx in
the paper's look (scripts/review/paper_look.py); an existing file is never overwritten.

Usage: python3 scripts/paper_ppml/build_supporting.py <version>
"""
import json, pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
P = ROOT / 'myliteraturereviewpaper' / 'ppml2026'
B = P / 'build'
OUTDIR = ROOT / 'myliteraturereviewpaper' / 'PPML in NextGeneration IoT'
NAME = 'Privacy Preserving Machine Learning in NextGeneration IoT'
sys.path.insert(0, str(ROOT / 'scripts' / 'review'))
import paper_look as L                                                  # noqa: E402

SECTIONS = [('S1. The search strings', 'strings_full', 'The string of each search, with the IEEE Xplore queries combined into one.'),
            ('S2. The eligibility criteria as recorded', 'criteria', 'The inclusion (IC) and exclusion (EC) criteria as recorded and applied at screening and at full text, with their codes; the paper gives them in plain words.'),
            ('S3. The designs against the three conditions', 'conditions', 'Every included design graded on the three conditions of the agenda, in the order of the coverage grid of the paper.'),
            ('S4. The set-up of the first experiment', 'experiment_setup', 'The conditions under which the two released designs were run for Section VII-B (from V84).')]


def numbering(version):
    order = json.loads((B / f'BUILD-REPORT-V{version}.json').read_text(encoding='utf-8'))['citations']
    return {k: i for i, k in enumerate(order, 1)}


def cite(text, num):
    def one(m):
        keys = re.findall(r'@([\w-]+)', m.group(0))
        return ', '.join(f'[{n}]' for n in sorted(num[k] for k in keys if k in num))
    text = re.sub(r'\[@[^\]]+\](?:, \[@[^\]]+\])*', one, text)
    return re.sub(r'\s*⟦[^⟧]+⟧', '', text)


def main(version):
    out = OUTDIR / f'{NAME} - V{version} supporting document.docx'
    if out.exists():
        sys.exit(f'{out.name} exists; versions are never overwritten')
    num = numbering(version)
    md = ['---', 'title: "Supporting Document"', 'subtitle: "Privacy Preserving Machine Learning in Next Generation IoT (NG-IoT) Security: A Systematic Review"', '---', '',
          'The search strings, the eligibility criteria and the grading of every included design against the three conditions of the agenda. '
          'Citations in square brackets carry the numbers of the paper\'s reference list.', '']
    for i, (head, key, intro) in enumerate(SECTIONS, 1):
        t = (B / 'tables' / f'{key}.md').read_text(encoding='utf-8')
        t = re.sub(r'^Table: ', f'Table: Table S{i}. ', t, count=1, flags=re.M)
        md += [f'# {head}', '', intro, '', cite(t, num), '']
    src = B / f'supporting-V{version}.md'
    src.write_text('\n'.join(md) + '\n', encoding='utf-8')
    look = L.render(src, out)
    if look.get('styles_not_in_look'):
        print('paragraph styles the shared look does not set (add them to paper_look.py):', look['styles_not_in_look'])
    print(f'written {out.name}: {len(SECTIONS)} tables')


if __name__ == '__main__':
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    main(sys.argv[1])
