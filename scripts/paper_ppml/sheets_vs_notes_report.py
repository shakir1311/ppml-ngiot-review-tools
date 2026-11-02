#!/usr/bin/env python3
"""Step 2 of the check of the evidence sheets against the notes and summaries: validate the readings and report them.

Each reading (search-ppml/evidence/sheets-vs-notes/verdicts/<id>.json) judged every answer of one sheet against the study's
notes and summary only. This script checks every reading — all questions present, verdicts from the agreed list, and every
words it quotes from the notes or summary really there (else the point is marked "quotation not found") — and writes:

  search-ppml/evidence/sheets-vs-notes/READINGS.csv     one row per answer (verdict, comment, mechanical status)
  Docs/EVIDENCE-SHEETS-VS-NOTES-<date>.html             the summary and every answer that differs from or contradicts
                                                        the notes, with the notes' own words and the suggested correction

Usage: python3 scripts/paper_ppml/sheets_vs_notes_report.py 2026-10-11
"""
import collections
import csv
import html
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sheets_vs_notes import find  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
CHECK = ROOT / 'search-ppml' / 'evidence' / 'sheets-vs-notes'
SHEETS = ROOT / 'search-ppml' / 'evidence' / 'sheets'
PAPERS = ROOT / 'notes-verifier' / 'data' / 'papers.json'
VERDICTS = ['agrees', 'partly-in-notes', 'not-in-notes', 'differs', 'conflicts']
WORDS = {'agrees': 'agrees with the notes/summary', 'partly-in-notes': 'partly in the notes; the rest not mentioned there',
         'not-in-notes': 'not in the notes or summary', 'differs': 'differs in a detail', 'conflicts': 'contradicts the notes/summary'}


def esc(s):
    return html.escape(s or '', quote=False)


def main():
    date = sys.argv[1] if len(sys.argv) > 1 else 'undated'
    papers = {p['key']: p for p in json.loads(PAPERS.read_text())['papers']}
    mech = json.loads((CHECK / 'MECHANICAL.json').read_text())
    rows, problems, flagged = [], [], []
    for key in sorted(mech):
        f = CHECK / 'verdicts' / f'{key}.json'
        if not f.exists():
            problems.append(f'{key}: no reading')
            continue
        reading = json.loads(f.read_text(encoding='utf-8'))
        sheet = json.loads((SHEETS / f'{key}.json').read_text(encoding='utf-8'))
        ref_text = (ROOT / papers[key]['notes']).read_text(encoding='utf-8') + '\n' + \
            (ROOT / papers[key]['summary']).read_text(encoding='utf-8')
        if set(reading.get('answers', {})) != set(sheet['answers']):
            problems.append(f'{key}: questions read {sorted(reading.get("answers", {}))} vs sheet {sorted(sheet["answers"])}')
        for q in sheet['answers']:
            a = reading.get('answers', {}).get(q, {})
            v = a.get('verdict')
            if v not in VERDICTS:
                problems.append(f'{key} {q}: verdict {v!r}')
            for p in a.get('points', []):
                p['notes_found'] = bool(find(p.get('notes', ''), ref_text)) if p.get('notes') else None
                if p['notes_found'] is False:
                    problems.append(f'{key} {q}: quoted notes words not found: {p.get("notes", "")[:80]}')
            rows.append({'key': key, 'n': papers[key]['n'], 'q': q, 'located_via': sheet['answers'][q].get('located_via', ''),
                         'mechanical': mech[key]['answers'][q]['status'], 'verdict': v or '', 'comment': a.get('comment', '')})
            if v in ('differs', 'conflicts'):
                flagged.append((papers[key], q, mech[key]['answers'][q]['title'], a))
    with (CHECK / 'READINGS.csv').open('w', newline='') as out:
        w = csv.DictWriter(out, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)

    count = collections.Counter(r['verdict'] for r in rows)
    studies = len({r['key'] for r in rows})
    flagged.sort(key=lambda t: (t[3].get('verdict') != 'conflicts', t[0]['n'], t[1]))
    by_via = collections.defaultdict(collections.Counter)
    for r in rows:
        by_via[r['located_via']][r['verdict']] += 1

    RATINGS = {'S2', 'S4'}       # survey coverage ratings: the sheets use the heading rule, the notes their theme tags
    facts = [t for t in flagged if t[1] not in RATINGS]
    ratings = [t for t in flagged if t[1] in RATINGS]

    def rows_html(group):
        return ''.join(item_html(*t) for t in group)

    def item_html(paper, q, title, a):
        pts = ''.join(
            f'<li><b class="{esc(p.get("status"))}">{esc(p.get("status"))}</b> — sheet: “{esc(p.get("sheet"))}”'
            + (f'<br>{esc(p.get("where") or "notes")}: “{esc(p.get("notes"))}”'
               + ('' if p.get('notes_found') is not False else ' <span class="warn">(these words were not found in the notes)</span>')
               if p.get('notes') else '')
            + (f'<br><i>correction suggested: {esc(p.get("fix"))}</i>' if p.get('fix') else '') + '</li>'
            for p in a.get('points', []) if p.get('status') in ('differs', 'conflicts'))
        return (f'<tr><td>[{paper["n"]}] {esc(paper["key"])}</td><td>{q}<br><span class="s">{esc(title)}</span></td>'
                f'<td><b class="{a["verdict"]}">{esc(WORDS[a["verdict"]])}</b><br>{esc(a.get("comment"))}<ul>{pts}</ul></td></tr>')

    items = []
    for paper, q, title, a in flagged:
        pts = ''.join(
            f'<li><b class="{esc(p.get("status"))}">{esc(p.get("status"))}</b> — sheet: “{esc(p.get("sheet"))}”'
            + (f'<br>{esc(p.get("where") or "notes")}: “{esc(p.get("notes"))}”'
               + ('' if p.get('notes_found') is not False else ' <span class="warn">(these words were not found in the notes)</span>')
               if p.get('notes') else '')
            + (f'<br><i>correction suggested: {esc(p.get("fix"))}</i>' if p.get('fix') else '') + '</li>'
            for p in a.get('points', []) if p.get('status') in ('differs', 'conflicts'))
        items.append(f'<tr><td>[{paper["n"]}] {esc(paper["key"])}</td><td>{q}<br><span class="s">{esc(title)}</span></td>'
                     f'<td><b class="{a["verdict"]}">{esc(WORDS[a["verdict"]])}</b><br>{esc(a.get("comment"))}<ul>{pts}</ul></td></tr>')

    via_rows = ''.join(f'<tr><td>{esc(via or "—")}</td>' + ''.join(f'<td>{c[v]}</td>' for v in VERDICTS) + f'<td>{sum(c.values())}</td></tr>'
                       for via, c in sorted(by_via.items()))
    page = f'''<!doctype html><html lang="en-GB"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Evidence Sheets vs Notes</title>
<style>
:root {{ --ink:#1b1f24; --muted:#59616c; --line:#d3d9e0; --head:#eef1f5; }}
body {{ margin:0; padding:24px 16px 48px; color:var(--ink); background:#fff; font:15px/1.5 -apple-system,"Segoe UI",Roboto,Arial,sans-serif; }}
main {{ max-width:90rem; margin:0 auto; }} h1 {{ font-size:1.5rem; margin:0 0 .4rem; }}
h2 {{ font-size:1.15rem; margin:2rem 0 .5rem; padding-top:.4rem; border-top:2px solid var(--ink); }}
p, li {{ max-width:64rem; }} .lede, .s {{ color:var(--muted); }} .s {{ font-size:.78rem; }}
.table-wrap {{ overflow-x:auto; }} table {{ width:100%; border-collapse:collapse; table-layout:fixed; margin:.5rem 0 1rem; }}
th, td {{ border:1px solid var(--line); padding:.4rem .5rem; vertical-align:top; text-align:left; font-size:.84rem; overflow-wrap:anywhere; }}
thead th {{ background:var(--head); }} ul {{ margin:.3rem 0 0 1rem; padding:0; }}
.conflicts {{ color:#b3261e; }} .differs {{ color:#a35a00; }} .warn {{ color:#b3261e; }}
col.a {{ width:11%; }} col.b {{ width:17%; }}
@media print {{ @page {{ size:auto; margin:12mm 10mm; }} body {{ padding:0; font-size:9.5pt; }} main {{ max-width:none; }}
  p, li {{ max-width:none; }} .table-wrap {{ overflow:visible; }} th, td {{ font-size:7.8pt; padding:3px 4px; }}
  thead {{ display:table-header-group; }} thead th {{ background:#fff; }} tr {{ break-inside:avoid; }} h2 {{ break-after:avoid; }}
  .conflicts, .differs, .warn {{ color:#000; }} }}
</style></head><body><main>
<h1>Evidence sheets against the notes and summaries</h1>
<p class="lede">Every answer of the {studies} evidence sheets behind the review, compared with the study's own notes and summary
(the reference). Readers saw only the notes, summary and sheet, never the paper. {date}.</p>
<h2>1. Result</h2>
<div class="table-wrap"><table><thead><tr><th>Answers</th>{''.join(f'<th>{esc(WORDS[v])}</th>' for v in VERDICTS)}<th>All</th></tr></thead>
<tbody><tr><td>all {len(rows)}</td>{''.join(f'<td>{count[v]}</td>' for v in VERDICTS)}<td>{len(rows)}</td></tr></tbody></table></div>
<p><b>{count["conflicts"]}</b> answers contradict the notes or summary and <b>{count["differs"]}</b> differ in a detail:
{len(facts)} on facts and tags (Section 2), {len(ratings)} on survey coverage ratings (Section 3). “Not in the notes” is not an error: those answers rest on the paper's full text, which the notes do not cover;
they are checked against the PDF in the Evidence Verifier.</p>
<p>By where the reader said the answer came from:</p>
<div class="table-wrap"><table><thead><tr><th>Taken from</th>{''.join(f'<th>{esc(v)}</th>' for v in VERDICTS)}<th>All</th></tr></thead>
<tbody>{via_rows}</tbody></table></div>
<h2>2. Facts and tags that contradict or differ from the notes ({len(facts)})</h2>
<p>Here the sheet and the notes state different things about the study. The PDF settles which record is right.</p>
<div class="table-wrap"><table><colgroup><col class="a"><col class="b"><col></colgroup>
<thead><tr><th>Study</th><th>Question</th><th>What differs, the notes' own words, and the correction suggested</th></tr></thead>
<tbody>{rows_html(facts)}</tbody></table></div>
<h2>3. Survey coverage ratings that differ from the notes ({len(ratings)})</h2>
<p>For surveys, the sheets rate each layer and angle as subject, mentioned or absent by one rule: “subject” only when
it has a heading or table of its own. The notes' theme tags record the topics a survey touches, a different yardstick. A
difference here means the two yardsticks disagree, or the sheet's rating and its own text disagree; decide which yardstick
governs before correcting.</p>
<div class="table-wrap"><table><colgroup><col class="a"><col class="b"><col></colgroup>
<thead><tr><th>Study</th><th>Question</th><th>What differs, the notes' own words, and the correction suggested</th></tr></thead>
<tbody>{rows_html(ratings)}</tbody></table></div>
<h2>4. How this was done</h2>
<ul><li>Mechanical check (<code>scripts/paper_ppml/sheets_vs_notes.py</code>): every quotation of every answer looked up in the
notes and summary, with its page.</li>
<li>Reading (one reader per six studies): each answer judged against the notes and summary only; the words a reading
quotes from the notes were then looked up again (<code>scripts/paper_ppml/sheets_vs_notes_report.py</code>).</li>
<li>Records: <code>search-ppml/evidence/sheets-vs-notes/</code> (MECHANICAL, packets, verdicts, READINGS.csv).</li></ul>
</main></body></html>'''
    out = ROOT / 'Docs' / f'EVIDENCE-SHEETS-VS-NOTES-{date}.html'
    out.write_text(page, encoding='utf-8')
    print(f'{studies} sheets, {len(rows)} answers:', {v: count[v] for v in VERDICTS})
    print(f'problems in the readings: {len(problems)}')
    for p in problems[:30]:
        print('  ', p)
    print(f'report: {out.relative_to(ROOT)}')


if __name__ == '__main__':
    main()
