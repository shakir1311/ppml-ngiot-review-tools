#!/usr/bin/env python3
"""Packets for the independent review of the prose (V72): (a) one per design — its paragraph as built and its record
(answers P1–P3 from the sheet, with quotations); (b) one per survey — the Section II prose and its S1 record; (c) the
synthesis prose — the built text of the abstract and of Sections II, V (results), VI (discussion) and VIII (conclusion),
with the tables as built, for a review of wording and internal consistency. Reviewers read packets only, never papers.
Writes search-ppml/evidence/review-v72/{designs,surveys,prose}/. Usage: python3 scripts/paper_ppml/review_packets_v72.py <version>
"""
import json, os, pathlib, re, sys
sys.path.insert(0, str(pathlib.Path(__file__).parent))
ROOT = pathlib.Path(__file__).resolve().parents[2]
PP = ROOT / 'myliteraturereviewpaper' / 'ppml2026'
OUT = ROOT / 'search-ppml' / 'evidence' / 'review-v72'
V = sys.argv[1] if len(sys.argv) > 1 else '72'


def answers_md(sid, keys):
    sh = json.loads((ROOT / 'search-ppml/evidence/sheets' / f'{sid}.json').read_text(encoding='utf-8'))
    parts = []
    for k in keys:
        a = sh['answers'].get(k)
        if a: parts.append(f'### {k}\n```json\n{json.dumps(a, ensure_ascii=False, indent=1)}\n```')
    return '\n\n'.join(parts)


def main():
    os.environ['PPML_STUDIES'] = str(PP / f'studies-v{V}')
    import build as BLD
    S = BLD.studies()
    designs = [k for k in S if 'P1' in json.loads((ROOT / 'search-ppml/evidence/sheets' / f'{k}.json').read_text()).get('answers', {})]
    (OUT / 'designs').mkdir(parents=True, exist_ok=True); (OUT / 'surveys').mkdir(exist_ok=True); (OUT / 'prose').mkdir(exist_ok=True)
    for k in designs:
        (OUT / 'designs' / f'{k}.md').write_text(f'# {k}\n\n## The paragraph as it will be printed (markers name the answers each sentence rests on)\n\n{S[k]}\n\n## The record (our extraction, the only source of facts)\n\n{answers_md(k, ["P1", "P2", "P3"])}\n', encoding='utf-8')
    if '--designs-only' in sys.argv:
        print(f'designs {len(designs)} → {OUT / "designs"}'); return
    sec2 = (PP / f'parts-v{V}' / '02-surveys.md').read_text(encoding='utf-8')
    surveys = sorted(set(re.findall(r'\[@([\w-]+)\]', sec2)))
    for s in surveys:
        sents = [x for x in re.split(r'(?<=⟧)\s+|(?<=[.!?])\s+(?=[A-Z(])', sec2) if f'[@{s}]' in x]
        (OUT / 'surveys' / f'{s}.md').write_text(f'# {s}\n\n## Every sentence of Section II that cites it\n\n' + '\n\n'.join(sents) + f'\n\n## The record (answer S1)\n\n{answers_md(s, ["S1"])}\n', encoding='utf-8')
    paper = (PP / 'build' / f'paper-V{V}.md').read_text(encoding='utf-8')
    (OUT / 'prose' / f'paper-V{V}.md').write_text(paper, encoding='utf-8')
    print(f'designs {len(designs)}, surveys {len(surveys)}, prose {len(paper.split()):,} words → {OUT}')


if __name__ == '__main__':
    main()
