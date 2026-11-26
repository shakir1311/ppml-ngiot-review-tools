#!/usr/bin/env python3
"""The supporting document of the PPML review (from V77): what the author took out of the paper's appendices on
16 October 2026 ("we don't need appendix C and appendix A … put them in a separate supporting document, and no need to
refer to that supporting document in the paper"): the full search strings, the eligibility criteria, every design
graded against the three conditions, and (from V84) the set-up of the first experiment. The paper does not refer to this document.
From V95 it also holds, in full and with the studies behind every count, the tables the paper no longer prints (the author, 26
November 2026: "move all tables that are removed to supporting documents"): the studies per year, the costs, the privacy
mechanisms, the ledgers, the trusted parties, the checks, the evaluation and the three conditions, whose counts the paper's result
charts now carry; and the full forms of the tables the paper prints shortened (the designs with every recorded tag, every threat
recorded, every column of the experiment). An introduction names the figure that carries a table's counts ({{FIG:key}}, numbered
as the paper numbers it, from build/BUILD-REPORT-V<n>.json); a citation without a reference in the paper stops the build.

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
            ('S4. The set-up of the first experiment', 'experiment_setup', 'The conditions under which the two released designs were run for Section VII-B.'),
            # V95: the tables behind the result charts, and the full forms of the tables the paper prints shortened
            ('S5. The included designs with every recorded tag', 'chars_primary_full', 'Every included design with its year, setting, enablers, privacy mechanisms, ledger type, the checks it performs and the attacks it tests, every recorded tag included; Section V-A gives the same table without the enablers and without the tags recorded as "other".'),
            ('S6. Included studies per year', 'years_v68', 'The counts drawn in {{FIG:years}}.'),
            ('S7. Costs reported by the designs, and where they were measured', 'cost', 'The costs each design reports and where it measured them, with the studies behind every count; {{FIG:sq1_costs}}(a) draws where the costs were measured.'),
            ('S8. Privacy mechanisms of the designs', 'privacy', 'The designs using each privacy mechanism and those in which it conceals the update from the aggregator, with the studies behind every count, as drawn in {{FIG:sq2_privacy}}(a).'),
            ('S9. Ledgers of the designs', 'ledger', 'The type of each ledger, what it does and what it holds, with the studies behind every count; {{FIG:sq2_privacy}}(b) draws what the ledgers hold.'),
            ('S10. Parties the designs still trust', 'trusted', 'The parties each design still trusts, with the studies behind every count, as drawn in {{FIG:sq2_privacy}}(c).'),
            ('S11. What the designs check, and whether the checker sees the update', 'checks', 'Each design under the most it checks and whether the checking party sees the update, as drawn in {{FIG:sq3_checks}}, with the parties that check and the studies behind every count.'),
            ('S12. Threats the designs address, every threat recorded', 'threats_full', 'Every threat the designs address, including the three outside the study questions that Section V-E leaves out: a single point of failure, tampering with records or models, and Byzantine validators or committee members.'),
            ('S13. How the designs are evaluated', 'evaluation', 'Where the designs were evaluated, the largest scale they report, the baselines they compare and the code they release, with the studies behind every count; {{FIG:sq1_costs}}(b) and (c) draw the environment and the scale.'),
            ('S14. The three conditions, and the designs meeting each', 'gap3', 'The designs meeting each condition of the agenda (Section VI-B), whose counts {{FIG:prim_coverage}} gives under its grid.'),
            ('S15. The first experiment, every column recorded', 'experiment_attacks_full', 'The outcomes of the attack runs of Section VII-B with every column recorded, the attackers admitted and the aggregation proofs verified included.')]


def numbering(version):
    order = json.loads((B / f'BUILD-REPORT-V{version}.json').read_text(encoding='utf-8'))['citations']
    return {k: i for i, k in enumerate(order, 1)}


MISSING = set()


def cite(text, num):
    def one(m):
        keys = re.findall(r'@([\w-]+)', m.group(0))
        MISSING.update(k for k in keys if k not in num)             # a study the paper does not cite has no number to print
        return ', '.join(f'[{n}]' for n in sorted(num[k] for k in keys if k in num))
    text = re.sub(r'\[@[^\]]+\](?:, \[@[^\]]+\])*', one, text)
    return re.sub(r'\s*⟦[^⟧]+⟧', '', text)


def main(version):
    out = OUTDIR / f'{NAME} - V{version} supporting document.docx'
    if out.exists():
        sys.exit(f'{out.name} exists; versions are never overwritten')
    num = numbering(version)
    figs = json.loads((B / f'BUILD-REPORT-V{version}.json').read_text(encoding='utf-8'))['figures']
    fig = lambda t: re.sub(r'\{\{FIG:(\w+)\}\}', lambda m: f'Fig. {figs[m.group(1)]}', t)
    md = ['---', 'title: "Supporting Document"', 'subtitle: "Privacy Preserving Machine Learning in Next Generation IoT (NG-IoT) Security: A Systematic Review"', '---', '',
          'The search strings, the eligibility criteria, the grading of every included design against the three conditions of the agenda, the set-up and '
          'the full outcomes of the first experiment, and the full tables behind the result charts of the paper, with the studies behind every count. '
          'Citations in square brackets carry the numbers of the paper\'s reference list.', '']
    for i, (head, key, intro) in enumerate(SECTIONS, 1):
        t = (B / 'tables' / f'{key}.md').read_text(encoding='utf-8')
        t = re.sub(r'^Table: ', f'Table: Table S{i}. ', t, count=1, flags=re.M)
        md += [f'# {head}', '', fig(intro), '', cite(t, num), '']
    if MISSING:
        sys.exit(f'citations without a reference in the paper: {sorted(MISSING)}')
    left = re.findall(r'\{\{[^}]*\}\}|⟦', '\n'.join(md))
    if left:
        sys.exit(f'tokens left in the supporting document: {sorted(set(left))}')
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
