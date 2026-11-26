#!/usr/bin/env python3
"""Writes the author's document of the designs as drawn: for each of the six carried forward, our diagram of one round beside the paper's own design figures and algorithm boxes; for each of the 48 not carried forward, the paper's design figures and algorithms with a short record of the design.

Reads design-evaluation/study/CARDS.json (study_cards.py), the diagrams (study_diagrams.py, inlined as SVG) and the crops with
their index (study_figures.py, referenced as images). Shown from each paper: the figures classed `design` (or, where no caption
names the design, the first figure; or the large artwork of a paper whose captions the text layer does not hold) and every
algorithm box; result figures are counted, not shown. The crops are the author's to check; Claude does not view them. The
document is the author's private working copy (figures reproduced from the papers for study, not for distribution). Writes
Docs/PHASE2-DESIGN-DIAGRAMS-<date>.html (printable in portrait and landscape; never overwritten: -V2-, -V3-).

Usage: python3 scripts/design_eval/study_designs_doc.py [trial-output.html]
"""
import datetime, html, json, pathlib, sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from common import EVAL, ROOT   # noqa: E402
from report import CSS   # noqa: E402
from study_diagrams import FLOWS   # noqa: E402
from study_packets import resolve   # noqa: E402

E = lambda x: html.escape(str(x))
STUDY = EVAL / 'study'
ORDER = ['n2721', 'n3378', 'Z01', 'Z04', 'Z06', 'Z07']
EXTRA = """
.design { border-top:2px solid var(--line); margin-top:26px; padding-top:6px; } .design h3 { font-size:1.08rem; margin:6px 0 2px; }
.meta { color:var(--muted); font-size:.88rem; margin:0 0 8px; } figure { margin:10px 0 16px; break-inside:avoid; }
figure img, figure svg { display:block; max-width:100%; height:auto; border:1px solid var(--line); border-radius:4px; background:#fff; }
figcaption { color:var(--muted); font-size:.82rem; margin-top:3px; } .pair { display:grid; grid-template-columns:1fr; gap:6px; }
.tagline { font-size:.88rem; } h4 { font-size:.95rem; margin:14px 0 4px; }
@media print { figure img { max-height:92vh; width:auto; max-width:100%; } figure svg { max-height:92vh; } .design { break-before:auto; } }
"""


def tags(v):
    vs = v if isinstance(v, list) else ([] if v in (None, '') else [v])
    out = list(dict.fromkeys('other' if str(x).startswith('other') else str(x) for x in vs))
    return ', '.join(out) if out else '–'


def crops(i):
    idx = json.load(open(STUDY / 'figures' / i / 'index.json'))
    figs = [x for x in idx['items'] if x['kind'] == 'figure']
    shown = [x for x in figs if x['class'].startswith(('design', 'unknown'))]
    algs = [x for x in idx['items'] if x['kind'] == 'algorithm']
    return shown, algs, len(figs) - len(shown), idx['pages']


def img(i, x, what):
    src = f'../design-evaluation/study/figures/{i}/{x["file"]}'
    note = []
    if x.get('number', 0) and x['number'] < 900:
        note.append(f'{what} {x["number"]}')
    note.append(f'page {x["page"]}')
    if x['found'].startswith('approximate'):
        note.append('approximate crop: no artwork was recorded, so the space above the caption is shown')
    if x['found'].startswith('artwork'):
        note.append('caption not found in the text layer')
    if 'continues' in x['found']:
        note.append('runs on to the next page')
    if x['found'].startswith('whole page'):
        note.append('the whole page: the algorithm is printed as an image')
    if x.get('class', '').startswith('design (first'):
        note.append('the paper\'s first figure (no caption names the design)')
    out = f'<figure><img src="{E(src)}" alt="{E(what)} {x.get("number", "")}, page {x["page"]}" loading="lazy"><figcaption>{E(" · ".join(note))}</figcaption></figure>'
    if x.get('continuation'):
        src2 = f'../design-evaluation/study/figures/{i}/{x["continuation"]}'
        out += f'<figure><img src="{E(src2)}" alt="continuation, page {x["page"] + 1}" loading="lazy"><figcaption>continued, page {x["page"] + 1}</figcaption></figure>'
    return out


def from_paper(i, H):
    shown, algs, results, pages = crops(i)
    H.append(f'<h4>From the paper: design figures ({len(shown)})</h4>')
    H += [img(i, x, 'Fig.') for x in shown] or ['<p class="muted">The paper has no design figure.</p>']
    H.append(f'<h4>From the paper: algorithms ({len(algs)})</h4>')
    H += [img(i, x, 'Algorithm') for x in algs] or ['<p class="muted">The paper has no algorithm box; its procedure is in the text.</p>']
    if results:
        H.append(f'<p class="muted">{results} further figure{"s" if results > 1 else ""} of results or other matters in the paper, not shown.</p>')
    return len(shown), len(algs)


def main():
    cards = {c['id']: c for c in json.load(open(STUDY / 'CARDS.json'))['cards']}
    six = [cards[i] for i in ORDER]
    rest = sorted((c for c in cards.values() if c['status'] != 'carried forward'), key=lambda c: (c['group'], c['who']))
    today = datetime.date.today().isoformat()
    H = [f'<!doctype html><html lang="en-GB"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">'
         f'<title>Designs as drawn</title><style>{CSS}{EXTRA}</style></head><body>',
         '<h1>The designs as drawn: the six carried forward and the 48 not</h1>',
         f'<p class="sub">For each design, the paper\'s own design figures and algorithm boxes, cropped from its PDF, beside a short record '
         f'of the design; for the six carried forward, also our diagram of one round in one style, to compare them directly. {today}. '
         'A private working copy: the figures are reproduced from the papers for study and are not for distribution.</p>',
         '<p class="muted">Contents: A The six carried forward (A.0 side by side; A.1 to A.6 each design) · B The 48 not carried forward, by reason · C How this was made</p>']
    # ---------------------------------------------------------------- A.0
    H.append('<h2>A. The six carried forward</h2><h3>A.0 Side by side</h3><div class="wrap"><table><thead><tr><th></th>' +
             ''.join(f'<th>{E(c["name"])}</th>' for c in six) + '</tr></thead><tbody>')
    rows = [('Parties', lambda c: ', '.join(l[1] for l in FLOWS[c['id']]['lanes'])),
            ('Steps in one round', lambda c: str(len(FLOWS[c['id']]['steps']))),
            ('Privacy mechanisms', lambda c: tags(c['mechanisms'])), ('What is checked', lambda c: tags(c['checked'])),
            ('Checked by', lambda c: tags(c['checker'])), ('Checker sees an update', lambda c: tags(c['checker_sees_update'])),
            ('A zero-knowledge proof shows', lambda c: tags(c['zk_shows'])), ('Ledger', lambda c: f"{tags(c['ledger'])}; {tags(c['platform'])}"),
            ('Still trusted', lambda c: tags(c['trusted'])),
            ('PhD threats tested', lambda c: ', '.join(k.replace('_', ' ') for k, v in c['phd_threats'].items() if v['tested']) or 'none'),
            ('Diagrams and algorithms in the paper', lambda c: f'{len(crops(c["id"])[0])} design figure(s), {len(crops(c["id"])[1])} algorithm(s)')]
    H += [f'<tr><th>{E(lab)}</th>' + ''.join(f'<td>{E(f(c))}</td>' for c in six) + '</tr>' for lab, f in rows]
    H.append('</tbody></table></div><p class="muted">Diagram colours: blue, the parties that operate and their work; green, a check or a proof; '
             'gold, the ledger. Arrows are messages; boxes are work a party does on its own; numbers give the order within one round.</p>')
    n_fig = n_alg = 0
    for k, c in enumerate(six, 1):
        r = json.load(open(resolve(c['id'])['folder'] / 'study' / 'reader.json'))['card']
        H.append(f'<div class="design"><h3>A.{k} {E(c["name"])}: {E(c["title"])}</h3><p class="meta">{E(c["who"])} · {E(c["from"])}</p>'
                 f'<p>{E(r.get("summary", ""))}</p><h4>Our diagram of one round</h4><figure>'
                 + (STUDY / 'diagrams' / f'{c["id"]}.svg').read_text() +
                 f'<figcaption>{E(c["name"])}: one round, drawn from the study reader\'s record of the paper (study/reader.json).</figcaption></figure>')
        a, b = from_paper(c['id'], H)
        n_fig, n_alg = n_fig + a, n_alg + b
        H.append('</div>')
    # ---------------------------------------------------------------- B
    H.append('<h2>B. The 48 not carried forward</h2><p>Grouped by the reason they were not carried forward. Each has a line of the review\'s '
             'classification (the evidence sheet, or the study reader for the five new designs) and a short record in our words, then the paper\'s '
             'design figures and algorithms.</p>')
    group = None
    for c in rest:
        if c['group'] != group:
            group = c['group']
            H.append(f'<h3>{E(c["group_label"])} ({sum(1 for x in rest if x["group"] == group)})</h3>')
        line = (f'Setting: {tags(c["settings"])} · Privacy: {tags(c["mechanisms"])} · Checked: {tags(c["checked"])} by {tags(c["checker"])} '
                f'(sees an update: {tags(c["checker_sees_update"])}) · ZK shows: {tags(c["zk_shows"])} · Ledger: {tags(c["ledger"])}, {tags(c["platform"])} · '
                f'Tested: {tags(c["tested"])} · Built from the paper: {(c.get("buildable") or {}).get("reader", "–")}')
        H.append(f'<div class="design"><h3>{E(c["name"] or c["who"])}: {E(c["title"])}</h3><p class="meta">{E(c["who"])} · {E(c["from"])}</p>'
                 f'<p class="tagline">{E(line)}</p><p>{E(c.get("summary", ""))}</p>')
        a, b = from_paper(c['id'], H)
        n_fig, n_alg = n_fig + a, n_alg + b
        H.append('</div>')
    # ---------------------------------------------------------------- C
    H.append('<h2>C. How this was made</h2><ul>'
             '<li>Our diagrams of the six (<span class="mono">scripts/design_eval/study_diagrams.py</span>) render the study readers\' records of each design\'s '
             'parties and round (<span class="mono">study/reader.json</span>), shortened to labels; they show one round, not every variant the paper discusses.</li>'
             '<li>The paper\'s figures and algorithms (<span class="mono">scripts/design_eval/study_figures.py</span>): captions found in the PDF\'s text layer; '
             'a figure is the artwork the extraction pipeline recorded next to its caption; it is shown when its caption names the design (architecture, '
             'framework, model, workflow, protocol and the like) rather than a result; an algorithm box runs between its rules. Where a paper\'s text layer '
             'holds no captions, its large artwork is shown, and where its algorithms are images, the pages its reader read as images. A crop can be '
             'imperfect; the paper is the authority.</li>'
             '<li>The short records: the review\'s evidence sheets (verified by the author) and the Phase 1 and study readers\' summaries, in our words.</li>'
             f'<li>{n_fig} design figures and {n_alg} algorithm boxes in this document; the crops are in <span class="mono">design-evaluation/study/figures/</span>, '
             'each folder with an index of what was found and how.</li></ul></body></html>')
    out = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / 'Docs' / f'PHASE2-DESIGN-DIAGRAMS-{today}.html'
    n = 2
    while out.exists() and len(sys.argv) == 1:
        out = ROOT / 'Docs' / f'PHASE2-DESIGN-DIAGRAMS-V{n}-{today}.html'
        n += 1
    out.write_text('\n'.join(H))
    print(out, '|', n_fig, 'design figures,', n_alg, 'algorithms, 6 diagrams')


if __name__ == '__main__':
    main()
