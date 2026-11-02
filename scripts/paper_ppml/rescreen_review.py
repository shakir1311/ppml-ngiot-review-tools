#!/usr/bin/env python3
"""The author's review page for the full second screening (rescreen.py): what was screened and how, the results by
stratum and reason, the agreement with the earlier sample run, every record flagged for full text (with its reason, the
deciding words, its DOI and whether the corpus holds it), the records whose citation criterion is open, and the files
behind it. The author reviews the page and marks any decision to overrule in the column "author" of
search-ppml/evidence/rescreen/RESCREEN-DECISIONS-2026-10-05.csv.

Input: search-ppml/evidence/rescreen/ (RESCREEN-RESULT, RESCREEN-DECISIONS). Output: Docs/PPML-RESCREEN-REVIEW-2026-10-05.html
(printable in portrait and landscape; an existing file is never overwritten — a new -V2 is written instead).

Usage: python3 scripts/paper_ppml/rescreen_review.py
"""
import collections, csv, html, json, pathlib

csv.field_size_limit(10 ** 9)
ROOT = pathlib.Path(__file__).resolve().parents[2]
RS = ROOT / 'search-ppml' / 'evidence' / 'rescreen'
e = html.escape
CODE = {'PRIVACY-INCIDENTAL': 'privacy incidental (EC4)', 'NO-NGIOT': 'NG-IoT setting incidental (EC5)', 'NO-LEARNING': 'learning incidental (EC5)',
        'OFF-FOCUS': 'none of the focus angles (EC7)', 'NOT-A-STUDY': 'not a study (EC6)', 'NOT-FULL-PAPER': 'not a full paper (EC3)',
        'SURVEY-BEFORE-2024': 'survey before 2024, fewer than 100 citations (EC8)', 'NO-BLOCKCHAIN': 'primary study without a blockchain in the design (EC9)',
        'NOT-FINAL-VERSION': 'final published version not available', 'OTHER': 'other'}


def out_path():
    base = ROOT / 'Docs' / 'PPML-RESCREEN-REVIEW-2026-10-05.html'
    v = 1
    while base.exists():
        v += 1
        base = ROOT / 'Docs' / f'PPML-RESCREEN-REVIEW-V{v}-2026-10-05.html'
    return base


def main():
    res = json.loads((RS / 'RESCREEN-RESULT-2026-10-05.json').read_text(encoding='utf-8'))
    st = json.loads((ROOT / 'myliteraturereviewpaper' / 'ppml2026' / 'build' / 'stats.json').read_text(encoding='utf-8'))
    recs = list(csv.DictReader(open(RS / 'RESCREEN-DECISIONS-2026-10-05.csv', encoding='utf-8')))
    strata = ['default: no focus angle', 'automated focus rule', 'default: survey before 2024', 'all']
    srow = ''.join(f"<tr><td>{e(s)}</td>" + ''.join(f"<td>{res['by_stratum'].get(s, {}).get(d, 0):,}</td>" for d in ('INCLUDE', 'UNSURE', 'EXCLUDE'))
                   + f"<td>{sum(res['by_stratum'].get(s, {}).values()):,}</td></tr>" for s in strata)
    crow = ''.join(f"<tr><td>{e(CODE.get(c, c or 'no code'))}</td><td>{v:,}</td></tr>" for c, v in sorted(res['exclusion_codes'].items(), key=lambda x: -x[1]))
    arow = ''.join(f"<tr><td>{e(k)}</td><td>{v}</td></tr>" for k, v in sorted(res['agreement_with_sample_run'].items(), key=lambda x: -x[1]))
    fl = [r for r in recs if r['full_text_needed']]
    fl.sort(key=lambda r: (r['after_ic7'] != 'INCLUDE', not r['corpus_folder'], r['kind'], -int(r['year'] or 0)))

    oa = json.loads((RS / 'OPEN-ACCESS-2026-10-05.json').read_text(encoding='utf-8')) if (RS / 'OPEN-ACCESS-2026-10-05.json').exists() else {}

    def held_of(r):
        pid = f"p{int(r['n']):04d}"
        if r['corpus_folder']:
            return 'in corpus'
        if (ROOT / 'corpus' / 'ppmlcorpus' / 'check' / pid / f'{pid}.pdf').exists():
            return 'fetched (open access)' if oa.get(r['n'], {}).get('outcome') == 'filed' else 'downloaded'
        return 'to download'

    def row(r):
        doi = f'<a href="https://doi.org/{e(r["doi"])}">{e(r["doi"])}</a>' if r['doi'] else '—'
        held = held_of(r)
        return (f"<tr><td>{e(r['n'])}</td><td>{e(r['after_ic7'])}</td><td>{e(r['kind'])}</td><td>{e(r['year'])}</td>"
                f"<td><b>{e(r['title'])}</b><br><span class=muted>{e(r['venue'])}</span></td><td>{e(r['angles'])}</td>"
                f"<td>{e(r['reason'])}<br><span class=q>“{e(r['quote'])}”</span>{('<br><i>' + e(r['ic7_note']) + '</i>') if r['ic7_note'] else ''}</td>"
                f"<td>{e(r['stratum'])}</td><td>{doi}<br>{held}</td></tr>")
    frows = ''.join(row(r) for r in fl)
    done_list = '; '.join(f"{r['n']}: {r['already_decided']}" for r in recs if r['already_decided'] and r['after_ic7'] in ('INCLUDE', 'UNSURE'))
    ft = {}
    for f in sorted((RS / 'fulltext').glob('*.json')):
        d = json.loads(f.read_text(encoding='utf-8'))
        ft[str(d['record'])] = d
    ftrow = {r['n']: r for r in csv.DictReader(open(RS / 'RESCREEN-FULLTEXT-2026-10-05.csv', encoding='utf-8'))} if (RS / 'RESCREEN-FULLTEXT-2026-10-05.csv').exists() else {}
    adj = json.loads((RS / 'ADJUDICATION-2026-10-05.json').read_text(encoding='utf-8')) if (RS / 'ADJUDICATION-2026-10-05.json').exists() else {'rules': [], 'version_notes': {}}
    changed = {n: dict(c, rule=r['id']) for r in adj['rules'] for n, c in r.get('changes', {}).items()}
    ft_html = ''
    if ft:
        fin = collections.Counter(r['decision'] for r in ftrow.values())
        nb = sum(1 for r in ftrow.values() if r.get('borderline') == 'yes')
        ft_html = (f'<p><b>Full texts assessed: {len(ft)}</b> — proposed include {fin.get("INCLUDE", 0)}, exclude {fin.get("EXCLUDE", 0)}, after rules R1–R3 '
                   f'(by the AI tool against the criteria, each condition with a page and a quotation; records in rescreen/fulltext/, table '
                   f'rescreen/RESCREEN-FULLTEXT-2026-10-05.csv). The {nb} the readers flagged as borderline come first: these are the calls to look at.</p><div class="wrap"><table><tr><th>No.</th><th>Title</th>'
                   '<th>Proposed</th><th>Reason</th></tr>' + ''.join(
                       f"<tr><td>{e(n)}{'<br><b>borderline</b>' if ftrow.get(n, {}).get('borderline') == 'yes' else ''}</td><td>{e(next((r['title'] for r in recs if r['n'] == n), ''))}</td><td>"
                       + (f"<s>{e(d['proposed_decision'])}</s> {e(changed[n]['to'])} (rule {e(changed[n]['rule'])})" if n in changed else
                          e(d['proposed_decision']) + ((' (' + e(CODE.get(d.get('code'), d.get('code') or '')) + ')') if d.get('code') else ''))
                       + (f"<br><b>Author:</b> {e(ftrow[n]['author'])}" if ftrow.get(n, {}).get('author') else '')
                       + f"</td><td>{e(d.get('reason', ''))}"
                       + (f"<br><i>{e(adj['version_notes'][n])}</i>" if n in adj.get('version_notes', {}) else '') + "</td></tr>"
                       for n, d in sorted(ft.items(), key=lambda x: (ftrow.get(x[0], {}).get('borderline') != 'yes', ftrow.get(x[0], {}).get('decision', ''), int(x[0])))) + '</table></div>')
    rules_html = ''.join(f"<div class=note><b>Rule {e(r['id'])}, {e(r['criterion'])}.</b> {e(r['reading'])} <i>Why:</i> {e(r['why'])} "
                         f"{e(r.get('not_changed', ''))}</div>" for r in adj['rules'])
    PUB = {'10.1109': 'IEEE', '10.1016': 'Elsevier', '10.1007': 'Springer Nature', '10.1038': 'Springer Nature', '10.3390': 'MDPI',
           '10.1145': 'ACM', '10.1002': 'Wiley', '10.1155': 'Wiley (Hindawi)', '10.1049': 'IET / Wiley', '10.1080': 'Taylor & Francis',
           '10.32604': 'Tech Science Press', '10.3233': 'IOS Press', '10.4271': 'SAE'}
    todo = [r for r in fl if held_of(r) == 'to download']
    n_oa = sum(1 for r in fl if held_of(r) == 'fetched (open access)')
    groups = {}
    for r in todo:
        groups.setdefault(PUB.get(r['doi'].split('/')[0], 'Other publishers'), []).append(r)
    dl = ''.join(f"<h3>{e(g)} ({len(rs)})</h3><ol>" + ''.join(
        f"<li>{e(r['n'])} — <a href=\"https://doi.org/{e(r['doi'])}\">{e(r['title'])}</a> <span class=muted>({e(r['venue'])}, {e(r['year'])}; "
        f"{e(oa.get(r['n'], {}).get('oa_status') or 'closed')})</span></li>" for r in sorted(rs, key=lambda r: r['venue'])) + '</ol>'
        for g, rs in sorted(groups.items(), key=lambda x: -len(x[1])))
    ic7 = [r for r in recs if r['ic7_note'].startswith('IC7 not met')]
    ic7rows = ''.join(f"<tr><td>{e(r['n'])}</td><td>{e(r['title'])}</td><td>{e(r['year'])}</td><td>{e(r['cited'])}</td></tr>" for r in ic7)
    doc = f"""<!doctype html><html lang="en-GB"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>PPML re-screening review</title><style>
:root{{--ink:#1b1b1b;--muted:#555;--line:#c9c9c4;--head:#0f4761;--band:#f3f5f7}}
html,body{{background:#fff;color:var(--ink)}} body{{font:14.5px/1.5 -apple-system,"Helvetica Neue",Arial,sans-serif;margin:0 auto;max-width:76rem;padding:24px 16px 48px}}
h1{{font-size:1.4rem;color:var(--head);margin:0 0 4px}} h3{{font-size:1rem;margin:14px 0 4px}} h2{{font-size:1.12rem;color:var(--head);margin:26px 0 8px;border-bottom:1px solid var(--line)}}
.muted{{color:var(--muted)}} .q{{color:#3b4a57;font-style:italic}} .note{{border:1px solid var(--line);border-radius:6px;padding:8px 12px;background:var(--band);margin:10px 0}}
.wrap{{overflow-x:auto}} table{{border-collapse:collapse;width:100%;font-size:.84rem;margin:6px 0}}
th,td{{border:1px solid var(--line);padding:4px 6px;text-align:left;vertical-align:top}} th{{background:var(--band)}} td{{overflow-wrap:anywhere}}
a{{color:#0b5cad}} li{{margin:3px 0}}
@page{{size:auto;margin:12mm}}
@media print{{body{{max-width:none;padding:0;font-size:9.5pt}} .wrap{{overflow:visible}} table{{font-size:7.8pt}} tr,.note,li{{break-inside:avoid}}
th,.note{{background:#fff}} a{{color:#000;text-decoration:none}}}}
</style></head><body>
<h1>PPML review — full second screening of the excluded records: for your review</h1>
<p class="muted">5 October 2026 · {res['records']:,} records · records: search-ppml/evidence/rescreen/ · scripts: scripts/paper_ppml/rescreen.py, rescreen_review.py</p>

<div class="note"><b>What to do.</b> Read section 3, the {res['flagged_for_full_text']} records flagged for full text. Where you disagree, write
<code>include</code> or <code>exclude</code> and a few words in the column <code>author</code> of
<code>search-ppml/evidence/rescreen/RESCREEN-DECISIONS-2026-10-05.csv</code> (or tell me the record numbers). Then download the
reports marked “to download” (section 4). Everything else is recorded and needs nothing from you.</div>

<h2>1. What was screened, and how</h2>
<p>Every record excluded at screening by a default or by an automated rule rather than by your own decision: the surveys
left at the default exclusion because they were published before 2024 with fewer than 100 citations, the records left at the
default exclusion because no focus angle was named, and the primary-study records set aside by the automated rule on focus
terms. Your own {st['author_excluded']:,} exclusions and the IEEE Xplore and not-a-paper rules were not part of it. The 150 records of the
earlier sample were screened again with the rest, unmarked, to measure agreement between the two runs.</p>
<p>Fifteen separate Claude runs screened 30 random batches, blind to how each record had been excluded, to your answers and
to the pre-fill, against the criteria of the earlier sample word for word (rescreen/RESCREEN-GUIDE.md; the prompt is in
rescreen/PROMPT.md). Each run read and decided every record; code was used only to print records and write answers. A
script then checked every output line, settled the citation criterion (IC7) from the citation counts of the exports, and
compared the two runs.</p>

<h2>2. Results</h2>
<div class="wrap"><table><tr><th>Excluded at screening by</th><th>Include</th><th>Unsure</th><th>Exclude</th><th>Records</th></tr>{srow}</table></div>
<p>After the citation criterion: {res['ic7_settled_by_script']} surveys judged eligible on content stay excluded because they were
published before 2024 and cited fewer than 100 times{(' ; ' + str(len(res['ic7_open_no_count'])) + ' have no citation count in the export (section 5)') if res['ic7_open_no_count'] else ''}.</p>
<div class="wrap"><table><tr><th>Reason for exclusion</th><th>Records</th></tr>{crow}</table></div>
<p><b>Agreement with the earlier sample run</b> ({res['sample_compared']} records screened by both runs):</p>
<div class="wrap"><table><tr><th>First run, then this run</th><th>Records</th></tr>{arow}</table></div>

<h2>3. Records flagged for full text ({res['flagged_for_full_text']})</h2>
<p>Include = meets every criterion on the abstract; Unsure = the abstract cannot settle a criterion (named in the reason).
Both go to full-text assessment, as at your own screening. {res['flagged_already_decided']} further flagged records were already
assessed at full text after the earlier sample and are not repeated here ({e(done_list)}).</p>{ft_html}
<div class="wrap"><table><tr><th>No.</th><th>Screening</th><th>Kind</th><th>Year</th><th>Title, venue</th><th>Angles</th><th>Reason and deciding words</th><th>Excluded before by</th><th>DOI, held</th></tr>{frows}</table></div>

<h2>3a. A reading of the criteria applied for consistency</h2>
<p>The screening runs read one criterion differently. One reading is applied to all records, and you can overrule it:</p>
{rules_html}

<h2>4. Reports to download ({len(todo)})</h2>
<p>{n_oa} of the {res['flagged_to_download']} were fetched as open-access published versions (only copies that OpenAlex labels
as the published version; publishers that block automated downloads were not worked around). The {len(todo)} below need your
institutional access, grouped by publisher. Save the PDFs in your Downloads folder with any file name; a script matches each
PDF to its record by the title on its first pages, files it in corpus/ppmlcorpus/check/ and extracts it. Tell me the numbers
of any you cannot get; they are reported as not retrieved.</p>
{dl}

<h2>5. Surveys eligible on content but excluded by the citation criterion ({len(ic7)})</h2>
<div class="wrap"><table><tr><th>No.</th><th>Title</th><th>Year</th><th>Citations</th></tr>{ic7rows}</table></div>
{('<p>No citation count in the export: ' + ', '.join(res['ic7_open_no_count']) + '. Check the count in Scopus or IEEE Xplore.</p>') if res['ic7_open_no_count'] else ''}

<h2>6. Files</h2>
<ul><li>search-ppml/evidence/rescreen/POPULATION-2026-10-05.csv — every record screened, its stratum and batch</li>
<li>rescreen/input/batch-NN.jsonl and rescreen/output/batch-NN.jsonl — what each run was given and answered, verbatim</li>
<li>rescreen/RESCREEN-DECISIONS-2026-10-05.csv — one row per record: decision, reason, deciding words, citation note</li>
<li>rescreen/RESCREEN-RESULT-2026-10-05.json — the counts on this page</li>
<li>rescreen/RESCREEN-GUIDE.md, rescreen/PROMPT.md — the guide and the prompt</li></ul>
</body></html>"""
    out = out_path()
    out.write_text(doc, encoding='utf-8')
    print(out.relative_to(ROOT))


if __name__ == '__main__':
    main()
