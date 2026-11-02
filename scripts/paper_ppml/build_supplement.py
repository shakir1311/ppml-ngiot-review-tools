#!/usr/bin/env python3
"""The supplementary material of the PPML review (from V56): what left the main text after the independent review of V55,
and what reviewers asked to see beside it.

S1  the classification rules behind the counts of the paper (the decisions recorded in thematic.py, with the words of the
    records that ground each);
S2  tables moved out of the main text (the NG-IoT fabric, threats claimed and tested, ledger platforms and consensus) and
    the lists of reports excluded at full text and not retrieved (PRISMA 2020 item 16b);
S3  figures moved out of the main text (trends by year; the coverage grids of the surveys and of the primary studies went
    back into the main text in V58, at the author's request);
S4  the description of each study in full, as the previous version of the paper gave it, from which the main text's
    paragraphs were shortened.

Citations carry the numbers of the paper's reference list (build/BUILD-REPORT-V<n>.json), so the paper must be built
first. Rendered with pandoc to <NAME> - V<n> supplementary material.docx in the Review Viewer's look, like the paper
(scripts/review/paper_look.py); an existing file is never overwritten.

Usage: python3 scripts/paper_ppml/build_supplement.py <version>
"""
import json
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
P = ROOT / 'myliteraturereviewpaper' / 'ppml2026'
B = P / 'build'
OUTDIR = ROOT / 'myliteraturereviewpaper' / 'PPML in NextGeneration IoT'
NAME = 'Privacy Preserving Machine Learning in NextGeneration IoT'
sys.path.insert(0, str(ROOT / 'scripts' / 'paper_ppml'))
sys.path.insert(0, str(ROOT / 'scripts' / 'review'))
import paper_look as L                                                  # noqa: E402  the look of the docx
import thematic as T                                                    # noqa: E402
import build as BLD                                                     # noqa: E402  (figure captions)

TABLES = [('fabric', 'S1'), ('threats', 'S2'), ('ledger_platforms', 'S3'), ('excluded_fulltext', 'S4'), ('not_retrieved', 'S5'),
          ('overlap', 'S6')]
FIGURES = [('trends', 'S1')]
DESCRIPTIONS_FROM = P / 'studies-full'      # the fuller paragraphs (from V55), kept in step with the records and the reporting rule
GROUPS_FROM = [P / 'parts' / '05-surveys.md', P / 'parts' / '06-approaches.md']     # the groups of this version


def numbering(version):
    order = json.loads((B / f'BUILD-REPORT-V{version}.json').read_text(encoding='utf-8'))['citations']
    return {k: i for i, k in enumerate(order, 1)}


def cite(text, num):
    def one(m):
        keys = re.findall(r'@([\w-]+)', m.group(0))
        return ', '.join(f'[{n}]' for n in sorted(num[k] for k in keys if k in num))
    text = re.sub(r'\[@[^\]]+\](?:, \[@[^\]]+\])*', one, text)
    return re.sub(r'\s*⟦[^⟧]+⟧', '', text)


def by_number(table):
    """a table whose rows begin with one citation, its rows put in the order of the reference list"""
    lines = table.splitlines()
    body = [i for i, l in enumerate(lines) if re.match(r'^\| \[\d+\]', l)]
    rows = sorted((lines[i] for i in body), key=lambda l: int(re.match(r'^\| \[(\d+)\]', l).group(1)))
    for i, r in zip(body, rows):
        lines[i] = r
    return '\n'.join(lines)


def threat(t):
    name = T.THREAT_NAME.get(t, t)
    return name if name.split()[0] in ('Byzantine', 'Sybil') else name[0].lower() + name[1:]


WHY_CLASS = {'N020': 'its record states that the aggregated global model, not the individual updates, is tested',
             'n3813': 'its record states that the gradient filter is named only in the security proof and that no checker is assigned'}


def rules(num):
    ref = lambda k: f'[{num[k]}]' if k in num else k
    zk = {r: [ref(k) for k, v in sorted(T.ZK_RELATION.items(), key=lambda kv: num.get(kv[0], 0)) if v == r] for r, _ in T.ZK_RELATIONS}
    out = ['# S1. Classification rules', '',
           'Every count of the paper is computed by script from the extraction records. Where a count rests on a classification '
           'that the records do not hold as a value, the classification was made by the review from the words of the record, as '
           'listed here, and is applied by the same rule everywhere.', '',
           '**What is checked.** Each primary study is counted once, under the strongest thing it checks: the content of individual '
           'updates or their training (accuracy or quality on test data, similarity or distance, a norm bound, anomaly detection, '
           'correct training, or an update check by a rule that is not stated); otherwise the aggregation; otherwise identities, '
           'signatures, format or contributions; otherwise an inference or other records; otherwise nothing. '
           + '; '.join(f'{ref(k)} is classed as "{v}", because {WHY_CLASS[k]}' for k, v in sorted(T.CHECK_CLASS_OVERRIDE.items(), key=lambda kv: num.get(kv[0], 0))) + '.', '',
           '**Whether the checking party sees the update.** In full; in part or noised (a function of the update such as its norm, part '
           'of it, or a version with noise added); not at all; or unclear where the record does not say. An unclear answer counts as '
           'not met. A design that discloses the norm of each update to the party that verifies its proof lets that party see the '
           'update in part.', '',
           '**Kept from the aggregator.** The updates are kept from the server or aggregator when they reach it encrypted, '
           'secret-shared, masked or inside an enclave whose host cannot read them; noise alone does not keep them from it, and neither '
           'does encryption under a key that the aggregating party itself holds. Where the participants add noise before an update '
           'reaches anyone, the aggregator sees a noised update; besides the designs whose records say so in their tags, this is '
           'read from the words of the records for ' + ', '.join(ref(k) for k in sorted(T.NOISED_BEFORE_AGGREGATOR, key=lambda k: num.get(k, 0))) + '.', '',
           '**The ledger checks the updates (C3).** Its nodes or contracts check the content of individual updates, or verify a proof '
           'about each update or its training by the relation the study states (a bound on the update or its correct training); a '
           'proof that the aggregation is correct, or one whose relation the study does not state, does not count. '
           + ' and '.join(ref(k) for k in sorted(T.LEDGER_CHECK_NOT_CONTENT, key=lambda k: num.get(k, 0))) + ' carry the role of '
           'verifying updates for checks that do not examine an update\'s content, and do not count.', '',
           '**What a zero-knowledge proof proves.** Each proof is classified by the relation that the study states it encodes, not by '
           'what the study says it shows: ' + '; '.join(f'{name.lower()}: {", ".join(zk[r]) or "none"}' for r, name in T.ZK_RELATIONS) + '.', '',
           '**Byzantine claims about the consensus.** A claim to tolerate Byzantine validators or committee members concerns the '
           'consensus, not the participants of the learning, and is counted apart: '
           + '; '.join(f'{ref(k)} ({v})' for k, v in sorted(T.BYZ_CONSENSUS.items(), key=lambda kv: num.get(kv[0], 0))) + '.', '',
           '**Attacks on the learning and the threats they test.** An attack on the learning is one of the three threats of SQ4: '
           'poisoning, backdoors included; malicious or fake participants; free riding. A reported test in which malicious participants '
           'send corrupted updates, such as sign-flipped or scaled gradients, counts for both poisoning and malicious participants, '
           'since the two threats overlap there.', '',
           '**A cost on devices and links (C1).** A cost of the design measured on device-class hardware meets C1; a cost over a '
           'network link counts as Partial only where it is the design\'s own, not a baseline\'s.', '',
           '**What a study reports.** The review credits each study with what it reports. A threat counts as tested when the study '
           'reports an attack run against its design in an experiment or a simulation, not when it argues the threat in a security '
           'analysis; where a study reports no test, no cost on devices or no code, the review says that it reports none, since such '
           'work may be reported elsewhere. Where the study reports results without describing the attack, the test is marked: ' + '; '.join(f'{ref(k)} ({", ".join(threat(t) for t in sorted(v))})' for k, v in sorted(T.ATTACK_NOT_DESCRIBED.items(), key=lambda kv: num.get(kv[0], 0))) + '.', '',
           '**What a ledger holds, read against the EDPB guidelines.** Updates in the clear or encrypted, identifiers and keys, '
           'reputation scores, rewards and payments, and other personal records remain personal data wherever they relate to a '
           'person; hashes and commitments, the global model, aggregates and logs depend on the scheme; proofs reveal nothing about '
           'their witness. A ledger that holds any record of the first kind is counted as holding personal data where it relates to '
           'a person. Condition C5 is met when the ledger holds no record of the first kind, or when the design provides a way to '
           'erase or redact what its ledger holds, whatever the motive given for it.', '',
           '**Conditions of the research gap.** As in Section VIII-A of the paper: one condition for each layer, numbered like its '
           'survey question: one for each of four layers and one for each of the three threats of the attack layer (C4a to C4c), seven '
           'in all. A condition counts as met only where the record shows it, and the number of conditions met that the table of the '
           'closest designs gives (Section VIII-B) is a plain count, in which the attack layer counts once for each of its threats.', '',
           '**Two tiers.** The primary studies and the surveys are appraised and synthesised apart and never counted together. Which '
           'included primary studies each survey cites was read from the reference lists that OpenAlex holds (Table S6); a survey '
           'that cites a design summarises it, so its conclusions are not independent evidence about that design.', '']
    return out


def main(version):
    out = OUTDIR / f'{NAME} - V{version} supplementary material.docx'
    if out.exists():
        sys.exit(f'{out.name} exists; versions are never overwritten')
    num = numbering(version)
    md = ['---', f'title: "Supplementary Material"', 'subtitle: "Privacy-Preserving Machine Learning for the Next-Generation IoT: '
          'A Systematic Review of Hiding and Checking Model Updates on Blockchains"', '---', '',
          'References in square brackets carry the numbers of the paper\'s reference list.', '']
    md += rules(num)
    md += ['# S2. Supplementary tables', '']
    for key, n in TABLES:
        t = (B / 'tables' / f'{key}.md').read_text(encoding='utf-8')
        t = re.sub(r'^Table: ', f'Table: Table {n}. ', t, count=1)
        md += [by_number(cite(t, num)) if key == 'overlap' else cite(t, num), '']
    md += ['# S3. Supplementary figures', '']
    for key, n in FIGURES:
        md += [f'![Fig. {n}. {BLD.FIGCAP[key]}]({B / "figures" / (key + ".png")}){{width=100%}}', '']
    md += ['# S4. The studies described in full', '',
           'The main text gives one shortened paragraph per study. The fuller descriptions from which they were shortened follow, '
           'surveys first and then primary studies, in the groups of Sections V-A and VI-A.', '']
    paras = {}
    for f in sorted(DESCRIPTIONS_FROM.glob('g*.md')):
        for m in re.finditer(r'(?ms)^### (\w+)\n(.*?)(?=^### |\Z)', f.read_text(encoding='utf-8')):
            paras[m.group(1)] = m.group(2).strip()
    for part in GROUPS_FROM:
        for line in part.read_text(encoding='utf-8').splitlines():
            g = re.match(r'^\*([^*]+)\*', line)
            if g and ('designs' in line or 'surveys' in line):
                md += [f'## {g.group(1).rstrip(".")}', '']
            m = re.fullmatch(r'\{\{STUDY:(\w+)\}\}', line.strip())
            if m and m.group(1) in paras:
                md += [cite(paras[m.group(1)], num), '']
    src = B / f'supplement-V{version}.md'
    src.write_text('\n'.join(md) + '\n', encoding='utf-8')
    look = L.render(src, out)
    if look['styles_not_in_look']:
        print('paragraph styles the shared look does not set (add them to paper_look.py):', look['styles_not_in_look'])
    print(f'written {out.name}')


if __name__ == '__main__':
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    main(sys.argv[1])
