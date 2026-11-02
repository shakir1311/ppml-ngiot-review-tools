#!/usr/bin/env python3
"""Report of the correction of the evidence sheets against the papers (11–12 October 2026) and of the summaries and
notes brought into line with them. Built from the records only:

  search-ppml/evidence/sheet-fix/results/*.json          first reading of every sheet against its paper
  search-ppml/evidence/sheet-fix/APPLIED.jsonl           every applied sheet change (before, after, reason, pass)
  search-ppml/evidence/sheet-fix/check2/results/*.json   second reading of changed tags and absence values
  search-ppml/evidence/sheet-fix/check2/narrow/DECISIONS.md   narrowed second check of the other studies
  search-ppml/evidence/sheet-fix/align/APPLIED.jsonl     every applied summary/notes sentence change

Writes Docs/EVIDENCE-SHEET-CORRECTIONS-<date>.html (a new file; an existing one is never overwritten).
Usage: python3 scripts/paper_ppml/sheet_corrections_report.py 2026-10-12
"""
import collections
import html
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_sheets as cs

ROOT = cs.ROOT
FIX = ROOT / 'search-ppml' / 'evidence' / 'sheet-fix'
PAPERS = ROOT / 'notes-verifier' / 'data' / 'papers.json'
TITLES = {'P1': 'System, setting and tiers', 'P2': 'Privacy', 'P3': 'Ledger', 'P4': 'Checking', 'P5': 'Threats',
          'P6': 'Evaluation', 'P7': "Regulation and the ledger's data", 'P8': 'Limitations',
          'S1': 'Scope and method', 'S2': 'The five layers', 'S3': 'Privacy mechanisms covered',
          'S4': "The review's angles", 'S5': 'Regulation', 'S6': 'What it concludes',
          'S7': 'Open issues and future directions', 'S8': 'Limitations of the survey'}
PASSES = {'results': 'first reading', 'check2/results': 'second reading', 'check2/narrow/results': 'narrowed second check'}


def esc(s):
    return html.escape(str(s), quote=False)


def as_list(x):
    return [str(v) for v in x] if isinstance(x, list) else ([] if x in (None, '') else [str(x)])


def tag_changes(before, after):
    b, a = before.get('values') or {}, after.get('values') or {}
    out = []
    for f in sorted(set(a) | set(b), key=lambda f: (list(a).index(f) if f in a else 99, f)):
        if as_list(b.get(f)) != as_list(a.get(f)):
            out.append((f, as_list(b.get(f)), as_list(a.get(f))))
    return out


def kind(before, after):
    if tag_changes(before, after):
        return 'tags'
    squash = lambda s: re.sub(r'[^a-z0-9]', '', str(s).lower())
    same_text = squash(before.get('answer')) == squash(after.get('answer'))
    same_quotes = [(e.get('page'), squash(e.get('quote'))) for e in before.get('evidence') or []] == \
        [(e.get('page'), squash(e.get('quote'))) for e in after.get('evidence') or []]
    return 'format' if same_text and same_quotes else 'text'


def values_html(vals):
    return ', '.join(esc(v) for v in vals) if vals else '<i>none</i>'


def main():
    date = sys.argv[1] if len(sys.argv) > 1 else 'undated'
    out = ROOT / 'Docs' / f'EVIDENCE-SHEET-CORRECTIONS-{date}.html'
    if out.exists():
        sys.exit(f'{out.relative_to(ROOT)} exists: give the next version a new name (-V2-)')
    papers = {p['key']: p for p in json.loads(PAPERS.read_text(encoding='utf-8'))['papers']}
    keys = sorted(p.stem for p in cs.SHEETS.glob('*.json'))
    order = sorted(keys, key=lambda k: (papers.get(k, {}).get('n', 999), k))

    # first reading
    first = collections.Counter()
    for k in keys:
        r = json.loads((FIX / 'results' / f'{k}.json').read_text(encoding='utf-8'))
        for a in r['answers'].values():
            first[a.get('verdict')] += 1

    # applied sheet changes, joined per answer
    log = [json.loads(line) for line in (FIX / 'APPLIED.jsonl').read_text(encoding='utf-8').splitlines()]
    per = collections.OrderedDict()
    for r in log:
        e = per.setdefault((r['key'], r['q']), {'before': r['before'], 'after': None, 'steps': []})
        e['after'] = r['after']
        e['steps'].append((PASSES.get(r.get('pass', 'results'), r.get('pass')), r.get('why', '')))
    kinds = collections.Counter(kind(e['before'], e['after']) for e in per.values())

    # second reading
    items = []
    for f in sorted((FIX / 'check2' / 'results').glob('*.json')):
        d = json.loads(f.read_text(encoding='utf-8'))
        items += [dict(it, key=d['key']) for it in d.get('items', [])]
    c2 = collections.Counter(it['verdict'] for it in items)
    c2_studies = len({it['key'] for it in items})
    overturned = [it for it in items if it['verdict'] == 'overturned']
    narrow = [r for r in log if r.get('pass') == 'check2/narrow/results']

    # summaries and notes
    align = [json.loads(line) for line in (FIX / 'align' / 'APPLIED.jsonl').read_text(encoding='utf-8').splitlines()]
    align_files = collections.Counter(r['file'] for r in align)

    # sheets pass the full check now
    studies = cs.studies()
    status = collections.Counter(cs.check(k, studies)['status'] for k in keys)

    def label(k):
        p = papers.get(k, {})
        return f'[{p.get("n", "?")}] {esc(k)}', esc(p.get('label', ''))

    # every sheet correction, by study
    rows = []
    for k in order:
        entries = [(q, e) for (key, q), e in per.items() if key == k]
        if not entries:
            continue
        num, name = label(k)
        rows.append(f'<tr class="study"><td colspan="4"><b>{num}</b> {name}</td></tr>')
        for q, e in sorted(entries):
            tags = ''.join(f'<li><code>{esc(f)}</code>: {values_html(b)} → <b>{values_html(a)}</b></li>'
                           for f, b, a in tag_changes(e['before'], e['after']))
            why = ''.join(f'<p><span class="pass">{esc(p)}:</span> {esc(w)}</p>' for p, w in e['steps'] if w)
            new_quotes = {(x.get('page'), x.get('quote')) for x in e['before'].get('evidence') or []}
            pages = []
            for x in e['after'].get('evidence') or []:
                mark = f' ({x["source"]})' if x.get('source') in ('table', 'image') else ''
                pages.append(f'p{esc(x.get("page"))}{mark}' + ('*' if (x.get('page'), x.get('quote')) not in new_quotes else ''))
            rows.append(f'<tr><td>{q}<br><span class="s">{esc(TITLES.get(q, ""))}</span></td><td>{why}</td>'
                        f'<td>{"<ul>" + tags + "</ul>" if tags else "<span class=s>wording or quotations</span>"}</td>'
                        f'<td>{", ".join(pages)}</td></tr>')

    # summary and notes changes, by study
    arows = []
    for k in order:
        changes = [r for r in align if r['key'] == k]
        if not changes:
            continue
        num, name = label(k)
        arows.append(f'<tr class="study"><td colspan="3"><b>{num}</b> {name}</td></tr>')
        for r in sorted(changes, key=lambda r: (r['file'] != 'SUMMARY.md', int(r['n'][1:]))):
            new = esc(r['new']) if r['new'] else '<i>removed</i>'
            arows.append(f'<tr><td>{"summary" if r["file"] == "SUMMARY.md" else "notes"}<br>'
                         f'<span class="s">{esc(r["n"])}, {esc(r.get("q", ""))}</span></td>'
                         f'<td><p class="old">{esc(r["old"])}</p><p>{new}</p></td><td>{esc(r.get("why", ""))}</td></tr>')

    over_rows = ''.join(f'<tr><td>{esc(it["key"])}</td><td>{esc(it["q"])} <code>{esc(it["field"])}</code></td>'
                        f'<td>{esc(it["why"])}</td></tr>' for it in overturned)
    narrow_rows = ''.join(f'<tr><td>{esc(r["key"])}</td><td>{esc(r["q"])}</td><td>{esc(r["why"])}</td></tr>' for r in narrow)
    erasure = []
    for k in order:
        sh = json.loads((cs.SHEETS / f'{k}.json').read_text(encoding='utf-8'))
        a = sh['answers'].get('P7')
        if a and (a.get('values') or {}).get('erasure') in ('addressed', 'mentioned'):
            erasure.append(f'<tr><td>{label(k)[0]}</td><td>{esc(a["values"]["erasure"])}</td></tr>')
    total_answers = sum(first.values())

    page = f'''<!doctype html><html lang="en-GB"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Evidence Sheet Corrections</title>
<style>
:root {{ --ink:#1b1f24; --muted:#59616c; --line:#d3d9e0; --head:#eef1f5; --band:#f6f8fa; }}
body {{ margin:0; padding:24px 16px 48px; color:var(--ink); background:#fff; font:15px/1.5 -apple-system,"Segoe UI",Roboto,Arial,sans-serif; }}
main {{ max-width:90rem; margin:0 auto; }} h1 {{ font-size:1.5rem; margin:0 0 .4rem; }}
h2 {{ font-size:1.15rem; margin:2rem 0 .5rem; padding-top:.4rem; border-top:2px solid var(--ink); }}
p, li {{ max-width:64rem; }} .lede, .s, .pass {{ color:var(--muted); }} .s {{ font-size:.78rem; }}
.table-wrap {{ overflow-x:auto; }} table {{ width:100%; border-collapse:collapse; table-layout:fixed; margin:.5rem 0 1rem; }}
th, td {{ border:1px solid var(--line); padding:.4rem .5rem; vertical-align:top; text-align:left; font-size:.84rem; overflow-wrap:anywhere; }}
thead th {{ background:var(--head); }} td p {{ margin:0 0 .3rem; }} ul {{ margin:.1rem 0 0 1rem; padding:0; }}
tr.study td {{ background:var(--band); }} .old {{ text-decoration:line-through; color:var(--muted); }}
table.counts {{ width:auto; table-layout:auto; }} table.counts td:last-child {{ text-align:right; }}
col.q {{ width:9%; }} col.w {{ width:47%; }} col.t {{ width:30%; }} col.f {{ width:10%; }} col.r {{ width:38%; }}
@media print {{ @page {{ size:auto; margin:12mm 10mm; }} body {{ padding:0; font-size:9.5pt; }} main {{ max-width:none; }}
  p, li {{ max-width:none; }} .table-wrap {{ overflow:visible; }} th, td {{ font-size:7.8pt; padding:3px 4px; }}
  table {{ break-inside:auto; }} table.counts {{ break-inside:avoid; }} thead {{ display:table-header-group; }}
  thead th, tr.study td {{ background:#fff; }} tr {{ break-inside:avoid; }} h2 {{ break-after:avoid; }}
  .lede, .s, .pass, .old {{ color:#000; }} }}
</style></head><body><main>
<h1>Corrections of the evidence sheets, summaries and notes</h1>
<p class="lede">The review's text, tables and counts are built from the {len(keys)} evidence sheets, one per included study.
Each sheet was read against its paper and corrected where the paper says otherwise; each study's summary, and notes
sentences flagged by a script, were then brought into line with the corrected sheet. {esc(date)}.</p>

<h2>1. Result</h2>
<div class="table-wrap"><table class="counts"><tbody>
<tr><td>Answers read against the papers ({len(keys)} studies × 8 questions)</td><td>{total_answers}</td></tr>
<tr><td>— correct as they stood</td><td>{first["correct"]}</td></tr>
<tr><td>— corrected on the first reading</td><td>{first["corrected"]}</td></tr>
<tr><td>— left unsettled</td><td>{first.get("unsettled", 0)}</td></tr>
<tr><td>Second reading: items checked again in {c2_studies} studies</td><td>{len(items)}</td></tr>
<tr><td>— confirmed</td><td>{c2["confirmed"]}</td></tr>
<tr><td>— overturned and corrected</td><td>{c2["overturned"]}</td></tr>
<tr><td>Narrowed second check of the other {len(keys) - c2_studies} studies: corrected</td><td>{len(narrow)}</td></tr>
<tr><td>Answers changed in all</td><td>{len(per)}</td></tr>
<tr><td>— with a tag value changed</td><td>{kinds["tags"]}</td></tr>
<tr><td>— answer text or quotations only</td><td>{kinds["text"]}</td></tr>
<tr><td>— spacing or punctuation only</td><td>{kinds["format"]}</td></tr>
<tr><td>Sheets passing the full check now (allowed tags; every quotation found on its page)</td><td>{status["PASS"]} of {len(keys)}</td></tr>
<tr><td>Summary sentences changed</td><td>{align_files["SUMMARY.md"]}</td></tr>
<tr><td>Notes sentences changed</td><td>{align_files["NOTES.md"]}</td></tr>
<tr><td>Studies whose summary or notes changed</td><td>{len({r["key"] for r in align})}</td></tr>
</tbody></table></div>

<h2>2. How it was done</h2>
<ul>
<li><b>Rules.</b> Every answer follows the decision rules of the review (the definitions in
<code>search-ppml/evidence/claims-audit-V42/AUDIT-GUIDE.md</code>); the paper is the authority.</li>
<li><b>First reading.</b> One reader per study — an agent of Claude (Anthropic), with the author's permission of 11 October
2026 — checked every answer of the sheet against the paper: first the passages around the sheet's own quotations, then any
further page or the full text needed to settle it. Each answer was found correct or corrected; none was left unsettled.</li>
<li><b>Applying.</b> A correction entered a sheet only through <code>scripts/paper_ppml/apply_sheet_fixes.py</code>: every tag
value allowed by the rules, every quotation found word for word on the page it names (at most 45 words, no ellipsis), the
whole sheet checked again afterwards. Quotations taken from a table or figure cannot be found in the page text; they are
marked “(table)” or “(image)” in Section 5. The untouched sheet is kept in
<code>notes-verifier/history/&lt;id&gt;/SHEET-original.json</code>.</li>
<li><b>Second reading.</b> In {c2_studies} studies a second, independent reader re-checked every tag the first reading had
changed and every value saying that something is absent, searching the whole paper with variant spellings. In the other
{len(keys) - c2_studies} studies, a script searched the full texts for the three kinds of absence value the second readers
had overturned (platform, erasure, systematic search), and Claude read the hits
(<code>check2/narrow/DECISIONS.md</code>).</li>
<li><b>Summaries and notes.</b> A script (<code>scripts/paper_ppml/summary_notes_flags.py</code>) put every summary sentence
beside the corrected sheet, and flagged notes sentences that resemble a sheet sentence the correction removed, or that an
earlier comparison of sheets and notes had found to differ, keeping those the local language model in
<code>local-checker/</code> did not find supported by the corrected answer. Five agents of Claude Sonnet, reading these
records only (no paper), proposed changes where the corrected sheet contradicts a sentence; Claude checked every proposal
against the sheet, and settled the seven sentences the agents left open (three by looking at the paper's page).
<code>scripts/paper_ppml/apply_align_fixes.py</code> applied them; the originals are kept in
<code>notes-verifier/history/&lt;id&gt;/SUMMARY-original.md</code> and <code>NOTES-original.md</code>.</li>
<li><b>Records.</b> <code>search-ppml/evidence/sheet-fix/</code>: <code>results/</code> (first reading),
<code>APPLIED.jsonl</code> (every sheet change, before and after), <code>check2/</code> (second reading),
<code>align/</code> (summaries and notes: packets, results, <code>APPLIED.jsonl</code>).</li>
</ul>

<h2>3. Second reading: values overturned</h2>
<div class="table-wrap"><table><colgroup><col class="f"><col class="t"><col></colgroup>
<thead><tr><th>Study</th><th>Question and tag</th><th>Reason</th></tr></thead><tbody>{over_rows}</tbody></table></div>
<p>Narrowed second check of the other studies: the eight “no systematic search” values, the twelve erasure values and
seven of the eight “platform not stated” values stand; one was corrected:</p>
<div class="table-wrap"><table><colgroup><col class="f"><col class="f"><col></colgroup>
<thead><tr><th>Study</th><th>Question</th><th>Reason</th></tr></thead><tbody>{narrow_rows}</tbody></table></div>

<h2>4. The erasure rule</h2>
<p>The rules define <code>erasure</code> as <i>addressed</i> when “the design provides a way to erase or redact on-chain
data”, <i>mentioned</i> when “erasure, redaction or the right to be forgotten is named without a mechanism”. The rule
concerns the mechanism, not its purpose: the redactable ledger of N020, which the authors motivate by storage, was already
counted as addressing erasure. The two designs that prune data from the chain to bound its growth (N019, r0284) are
therefore <i>addressed</i> as well. In all three the motive is storage; none presents the deletion as erasure of personal
data. A design that deletes data held off the chain (n3299: a revoked vehicle's pseudonym tree kept by the trusted
authority) does not meet the rule.</p>
<div class="table-wrap"><table class="counts"><thead><tr><th>Study</th><th>erasure</th></tr></thead><tbody>{''.join(erasure)}</tbody></table></div>

<h2>5. Every change to the sheets ({len(per)} answers)</h2>
<p>By study, in the order of the review's reference numbers. For each answer: the reason given at each reading, the tag
values before and after, and the pages of the corrected answer's quotations (* = a quotation added or changed by the
correction). The full answers before and after are in <code>APPLIED.jsonl</code> and the history files.</p>
<div class="table-wrap"><table><colgroup><col class="q"><col class="w"><col class="t"><col class="f"></colgroup>
<thead><tr><th>Question</th><th>Reason</th><th>Tags before → after</th><th>Pages</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table></div>

<h2>6. Every change to the summaries and notes ({len(align)} sentences)</h2>
<p>The sentence before (struck through) and after, and what the corrected sheet says.</p>
<div class="table-wrap"><table><colgroup><col class="q"><col class="w"><col class="r"></colgroup>
<thead><tr><th>File</th><th>Sentence</th><th>Reason</th></tr></thead><tbody>{''.join(arows)}</tbody></table></div>
</main></body></html>'''
    out.write_text(page, encoding='utf-8')
    print(f'answers {total_answers}: {dict(first)}; changed {len(per)} {dict(kinds)}; second reading {dict(c2)} in '
          f'{c2_studies} studies; narrowed {len(narrow)}; summaries/notes {dict(align_files)}; sheets {dict(status)}')
    print(f'report: {out.relative_to(ROOT)}')


if __name__ == '__main__':
    main()
