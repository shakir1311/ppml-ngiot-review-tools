#!/usr/bin/env python3
"""Writes the Phase 1 report of the design evaluation (Docs/DESIGN-EVALUATION-PHASE1-<date>.html) from the evidence files of the 45 design folders.

The report says, for the author and the supervisors: how many designs can be run with their own code, how many have code
that may not be used, how many the readers judge buildable from the paper and on what assumptions, and how many cannot be
evaluated; one row per design with its code, licence, the reader's and the rule's verdict, the effort and the folder; the
method in short; and what needs the author (downloads, permissions, judgements). Printable in portrait and landscape. A
report already written for the day is never overwritten: the next one is -V2-, -V3-.

Usage: design-evaluation/.venv/bin/python scripts/design_eval/report.py [--out <trial file>]
"""
import collections, datetime, html, json, pathlib, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import EVAL, ROOT, load_designs   # noqa: E402
from status import load, outcome   # noqa: E402

E = html.escape
CORE = ('C_privacy_mechanism', 'D_check_defence', 'F_protocol', 'E_ledger')
SHORT = {'specified': 'S', 'partly': 'P', 'missing': 'M', 'not applicable': '–'}
CSS = """
:root { --ink:#1d2330; --muted:#5b6475; --line:#d9dee7; --bg:#ffffff; --band:#f4f6fa; --ok:#1f7a4d; --mid:#9a6a00; --no:#a33a3a; --acc:#2a5db0; }
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) { --ink:#e8ebf1; --muted:#a9b1c1; --line:#3a4150; --bg:#161a22; --band:#1f2430; --ok:#5cc28e; --mid:#e0b04a; --no:#e57d7d; --acc:#7da7ef; } }
body { background:var(--bg); color:var(--ink); font:15px/1.5 -apple-system, "Segoe UI", Helvetica, Arial, sans-serif; margin:0 auto; max-width:1180px; padding:24px 16px 60px; }
h1 { font-size:1.55rem; margin:0 0 4px; } h2 { font-size:1.15rem; margin:30px 0 8px; border-bottom:1px solid var(--line); padding-bottom:4px; }
p.sub { color:var(--muted); margin:0 0 18px; }
.tiles { display:flex; flex-wrap:wrap; gap:10px; margin:14px 0 6px; }
.tile { flex:1 1 150px; border:1px solid var(--line); border-radius:8px; padding:10px 12px; background:var(--band); break-inside:avoid; }
.tile b { display:block; font-size:1.6rem; line-height:1.1; } .tile span { color:var(--muted); font-size:.86rem; }
table { border-collapse:collapse; width:100%; font-size:.86rem; margin:8px 0 4px; }
th, td { border-bottom:1px solid var(--line); padding:5px 6px; text-align:left; vertical-align:top; }
th { background:var(--band); font-weight:600; } tr { break-inside:avoid; }
.ok { color:var(--ok); font-weight:600; } .mid { color:var(--mid); font-weight:600; } .no { color:var(--no); font-weight:600; }
.mono { font-family: ui-monospace, Menlo, monospace; font-size:.8rem; } .muted { color:var(--muted); }
.note { border-left:3px solid var(--acc); background:var(--band); padding:8px 12px; margin:10px 0; break-inside:avoid; }
ul { margin:6px 0 6px 20px; padding:0; } li { margin:2px 0; }
.wrap { overflow-x:auto; }
@media (max-width:700px) { body { font-size:14px; } th, td { padding:4px; } }
@page { size: auto; margin: 14mm 12mm; }
@media print {
  :root { --ink:#000; --muted:#333; --line:#999; --bg:#fff; --band:#f2f2f2; --ok:#000; --mid:#000; --no:#000; --acc:#000; }
  body { max-width:none; padding:0; font-size:10pt; } .wrap { overflow:visible; } table { font-size:8.5pt; width:100%; }
  h2 { break-after:avoid; } table, .note, .tile { break-inside:avoid; } tr, td, th { break-inside:avoid; }
  a { color:#000; text-decoration:none; }
}
"""


def verdict_class(v):
    return {'viable': 'ok', 'viable with assumptions': 'mid', 'core partly specified': 'mid', 'not viable': 'no'}.get(v, 'muted')


def main():
    rows, counts, needs = [], collections.Counter(), []
    for d in load_designs():
        f = d['folder']
        code, lic = load(f / 'evidence' / '11-code-verdict.json'), load(f / 'evidence' / '12-licence.json')
        reader, check = load(f / 'algorithm' / 'reader.json'), load(f / 'algorithm' / '02-quote-check.json')
        data = load(f / 'datasets' / 'DATASETS.json')
        ph = outcome(code, lic, check, reader)
        own = [r for r in (lic or {}).get('repositories', []) if r.get('reviewer_verdict') in ('official', 'unofficial reimplementation')]
        rel = [r for r in (lic or {}).get('repositories', []) if r.get('reviewer_verdict') not in ('official', 'unofficial reimplementation')]
        lics = sorted({r.get('licence_spdx') or 'none' for r in own})
        related = ', '.join(f"{r['repo'].split('github.com/')[-1]} ({r.get('licence_spdx') or 'no licence'})" for r in rel)
        names = {'C_privacy_mechanism': 'privacy mechanism', 'D_check_defence': 'update check', 'F_protocol': 'message flow', 'E_ledger': 'ledger'}
        its = (reader or {}).get('items', {})
        weak = [f"{names[k]} {its.get(k, {}).get('status')}" for k in CORE if its.get(k, {}).get('status') in ('partly', 'missing')]
        core = (', '.join(weak) if weak else 'all specified') if reader else ''
        rows.append({'d': d, 'code': (code or {}).get('code_status', 'not yet judged'), 'lic': ', '.join(lics) if lics else '–', 'related': related,
                     'reader': (check or {}).get('reader_verdict', '–'), 'rule': (check or {}).get('rule_verdict', '–'),
                     'effort': (reader or {}).get('effort', '–'), 'core': core, 'phase': ph,
                     'gaps': (reader or {}).get('blocking_gaps') or [], 'assume': (reader or {}).get('assumptions') or [],
                     'data': data})
        if ph == 'run with its own code':
            counts['own code'] += 1
        elif (check or {}).get('reader_verdict') == 'viable with assumptions':
            counts['buildable (reader)'] += 1
        elif (check or {}).get('reader_verdict') == 'not viable':
            counts['not viable'] += 1
        for x in (data or {}).get('datasets', []):
            if 'needs the author' in x.get('status', ''):
                needs.append((d['id'], x['name'], x.get('source', '')))
    code_c = collections.Counter(r['code'] for r in rows)
    today = datetime.date.today().isoformat()
    out = ROOT / 'Docs' / f'DESIGN-EVALUATION-PHASE1-{today}.html'
    if '--out' in sys.argv:                              # a trial run outside Docs/
        out = pathlib.Path(sys.argv[sys.argv.index('--out') + 1])
    n = 2
    while out.exists() and '--out' not in sys.argv:
        out = ROOT / 'Docs' / f'DESIGN-EVALUATION-PHASE1-V{n}-{today}.html'
        n += 1
    H = [f'<!doctype html><html lang="en-GB"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">'
         f'<title>Design evaluation, Phase 1</title><style>{CSS}</style></head><body>',
         '<h1>Design evaluation, Phase 1: which of the 45 designs can be run</h1>',
         f'<p class="sub">The 45 designs included in the PPML review, checked one by one for code, licence and, where there is no usable code, '
         f'whether the paper describes the design well enough to build it. {today}. Every finding has its evidence in '
         f'<span class="mono">design-evaluation/designs/&lt;id&gt;/</span>.</p>',
         '<div class="tiles">',
         f'<div class="tile"><b>{counts["own code"]}</b><span>run with their own code (open licence)</span></div>',
         f'<div class="tile"><b>{code_c.get("released, no licence", 0)}</b><span>code published without a licence (authors\' permission needed)</span></div>',
         f'<div class="tile"><b>{counts["buildable (reader)"]}</b><span>buildable from the paper, with stated assumptions (reader\'s verdict)</span></div>',
         f'<div class="tile"><b>{counts["not viable"]}</b><span>not codeable from the paper: not evaluated</span></div>',
         '</div>',
         '<div class="note"><b>How to read the algorithm verdicts.</b> A reader judged each design without usable code against nine items. '
         'The rule asks the core items (C privacy mechanism, D checking of updates, F message flow, E ledger) to be fully specified for '
         '"viable with assumptions". No design meets that strictly: in every buildable one at least one core item is only partly specified. '
         'The reader\'s verdict says whether the gaps can be filled with standard choices without inventing the design; the rule\'s verdict '
         'shows that the decision to build is the author\'s. The column "core parts not fully specified" names, for each design, which of the four core parts the paper leaves partly specified or missing.</div>',
         '<h2>All 45 designs</h2><div class="wrap"><table><thead><tr><th>Design</th><th>Code (and related code: tools the paper names, the authors\' other work)</th><th>Licence of the design\'s code</th><th>Reader</th><th>Rule</th>'
         '<th>Core parts not fully specified</th><th>Effort</th><th>Phase 2</th></tr></thead><tbody>']
    order = {'run with its own code': 0}
    rows.sort(key=lambda r: (order.get(r['phase'], 1), {'viable with assumptions': 0, 'not viable': 2}.get(r['reader'], 1), r['d']['id'].lower()))
    for r in rows:
        d = r['d']
        H.append(f"<tr><td><b>{E(d['id'])}</b> {E(d['first_author'])} {E(d['year'])}{(' · ' + E(d['acronym'])) if d['acronym'] else ''}"
                 f"<br><span class='muted'>{E(d['title'])}</span></td><td>{E(r['code'])}"
                 + (f"<br><span class='muted'>related code: {E(r['related'])}</span>" if r['related'] else '') + f"</td><td>{E(r['lic'])}</td>"
                 f"<td class='{verdict_class(r['reader'])}'>{E(r['reader'])}</td><td class='{verdict_class(r['rule'])}'>{E(r['rule'])}</td>"
                 f"<td>{E(r['core'])}</td><td>{E(r['effort'])}</td><td>{E(r['phase'])}</td></tr>")
    H.append('</tbody></table></div>')
    H.append('<h2>Buildable from the paper: the assumptions the readers name</h2>')
    for r in rows:
        if r['reader'] == 'viable with assumptions':
            H.append(f"<p><b>{E(r['d']['id'])}</b> {E(r['d']['first_author'])} {E(r['d']['year'])} ({E(r['effort'])} effort)</p><ul>"
                     + ''.join(f'<li>{E(a)}</li>' for a in r['assume'][:8]) + '</ul>')
    H.append('<h2>Not codeable from the paper: what blocks it</h2><ul>')
    for r in rows:
        if r['reader'] == 'not viable':
            H.append(f"<li><b>{E(r['d']['id'])}</b> {E(r['d']['first_author'])} {E(r['d']['year'])}: {E('; '.join(r['gaps'][:3]))}</li>")
    H.append('</ul>')
    H += ['<h2>How each design was checked</h2><ul>',
          '<li><b>The paper itself</b>, by a local scan of its pages and the PDF\'s link annotations: every link, and every code- or data-availability statement.</li>',
          '<li><b>Everywhere else the code could be, or once was</b>: Crossref, OpenAlex, arXiv, Hugging Face Papers, the Papers with Code archive (last snapshot, 28 July 2025), '
          'DataCite, Zenodo, OpenAIRE Scholexplorer, GitHub (the design\'s name, its title and DOI, files citing it, the authors\' own accounts), ORCID, GitLab, Gitee, '
          'Software Heritage, the Wayback Machine, the publisher\'s supplementary items where the paper points to them, and a web search of code hosts by name. '
          'Every request and answer is saved in the design\'s folder.</li>',
          '<li><b>Licences</b> from the repository\'s licence file; code that allows running and adapting is cloned at a pinned commit, code without a licence is recorded, not cloned.</li>',
          '<li><b>The algorithm</b>, for designs without usable code: a local triage names the pages; one reader per design reads them against a fixed checklist; '
          'a script finds every quotation on its page and applies the checklist\'s rule.</li>',
          '<li><b>Datasets</b> are downloaded only for designs that can be run or built; public sets once, shared by copy-on-write clones.</li></ul>']
    if needs:
        H.append('<h2>Datasets that need the author</h2><div class="wrap"><table><thead><tr><th>Design</th><th>Dataset</th><th>Why, and where to start</th></tr></thead><tbody>')
        H += [f'<tr><td>{E(a)}</td><td>{E(b)}</td><td>{E(c)}</td></tr>' for a, b, c in needs]
        H.append('</tbody></table></div>')
    H.append(f'<p class="muted">Generated by scripts/design_eval/report.py from the evidence files.</p></body></html>')
    out.write_text('\n'.join(H))
    print(out, dict(counts), dict(code_c))


if __name__ == '__main__':
    main()
