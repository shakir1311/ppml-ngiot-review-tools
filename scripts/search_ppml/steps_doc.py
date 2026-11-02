#!/usr/bin/env python3
"""The author's step sheet for the primary-study arm (strings version 4), with the strings taken from strings.py so
that what the author pastes is exactly what is on record.

Output: Docs/PPML-SEARCH-STEPS-FOR-AUTHOR-V5-2026-10-04.html (versions 1-4 are kept unchanged). Version 5: Scopus P-S2 done;
IEEE Xplore as one focused query (the author asked for it), exported in year parts; ScienceDirect as in version 4.

Usage: python3 scripts/search_ppml/steps_doc.py
"""
import html, pathlib, sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import strings as S                                   # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[2]
OUT = ROOT / 'Docs' / 'PPML-SEARCH-STEPS-FOR-AUTHOR-V5-2026-10-04.html'
e = html.escape


def q(label, text):
    return f'<div class="q"><div class="ql">{e(label)} <button onclick="cp(this)">Copy</button></div><pre>{e(text)}</pre></div>'


def main():
    sp = S.scopus_primary()
    parts = [('2020–2022', ' AND PUBYEAR < 2023'), ('2023–2024', ' AND PUBYEAR > 2022 AND PUBYEAR < 2025'), ('2025–2026', ' AND PUBYEAR > 2024')]
    ieee = q('P-B (one query, 25 terms)', S.ieee_primary()[0])
    sd = ''
    for i, (ti, tak) in enumerate(S.sciencedirect_primary(), 1):
        sd += f'<h3>P-D{i}</h3>'
        sd += q('Title field', ti) if ti else '<p class="note">Title field: leave empty.</p>'
        sd += q('Title, abstract or author-specified keywords field', tak)
    rows = ['P-B, all years (count only)', 'P-B 2020–2023', 'P-B 2024', 'P-B 2025', 'P-B 2026'] + [f'P-D{i}' for i in range(1, 5)]
    table = ''.join(f'<tr><td>{r}</td><td></td><td></td><td></td><td></td><td></td></tr>' for r in rows)
    doc = f"""<!doctype html><html lang="en-GB"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>PPML primary-study searches</title><style>
:root{{--ink:#1b1b1b;--muted:#555;--line:#c9c9c4;--head:#0f4761;--band:#f3f5f7;--warn:#fff4d6}}
html,body{{background:#fff;color:var(--ink)}} body{{font:15px/1.5 -apple-system,"Helvetica Neue",Arial,sans-serif;margin:0 auto;max-width:60rem;padding:24px 16px 48px}}
h1{{font-size:1.45rem;color:var(--head);margin:0 0 4px}} h2{{font-size:1.15rem;color:var(--head);margin:26px 0 6px;border-bottom:1px solid var(--line)}} h3{{font-size:1rem;margin:16px 0 4px}}
.muted,.note{{color:var(--muted)}} ol li{{margin:3px 0}} .box{{border:1px solid var(--line);border-radius:6px;padding:8px 12px;background:var(--band);margin:10px 0}}
.open{{border:1px solid #d9b44a;border-radius:6px;padding:8px 12px;background:var(--warn);margin:10px 0}}
.q{{border:1px solid var(--line);border-radius:6px;margin:8px 0;overflow:hidden}} .ql{{background:var(--band);padding:4px 8px;font-size:.85rem;font-weight:600;display:flex;justify-content:space-between;align-items:center}}
pre{{margin:0;padding:8px 10px;white-space:pre-wrap;word-break:break-word;font-size:.8rem}} button{{font-size:.8rem;cursor:pointer}}
table{{border-collapse:collapse;width:100%;font-size:.88rem}} th,td{{border:1px solid var(--line);padding:6px 7px;text-align:left;vertical-align:top;height:1.4em}} th{{background:var(--band)}}
@page{{size:auto;margin:12mm}}
@media print{{body{{max-width:none;padding:0;font-size:10pt}}button{{display:none}}.q,table,tr,.box,.open{{break-inside:avoid}}.box,.ql,.open{{background:#fff}}th{{background:#eee}}}}
</style>
<script>function cp(b){{const t=b.closest('.q').querySelector('pre').innerText;navigator.clipboard.writeText(t).then(()=>{{b.textContent='Copied';setTimeout(()=>b.textContent='Copy',1500)}})}}</script></head><body>
<h1>Running the PPML searches (version 5: the remaining primary-study searches)</h1>
<p class="muted">4 October 2026 · replaces the IEEE part of version 4 (kept) with one focused query, as you asked · Scopus P-S2 is done
(4,543 records, filed) · ScienceDirect as in version 4</p>
<div class="box"><b>What to run.</b> 1 IEEE Xplore query, exported in four year parts, and 4 ScienceDirect searches, the same way as before:
paste each query with the Copy button, apply only the listed filters, fill in the table, leave the files unrenamed in Downloads and send me the
paths. Please also send the counts each site showed (and, if you still have them, those of P-S2, P-S1 v3 and P-A1–6 v3).</div>

<h2>0. How the primary-study search is built</h2>
<table><tr><th>Block</th><th>Where</th><th>Terms</th></tr>
<tr><td>Privacy</td><td>In the <b>title</b> (privacy is the study's aim) — <b>or</b> anywhere, together with a threat</td><td>the privacy terms of the survey arm</td></tr>
<tr><td>Threat (only with privacy outside the title)</td><td>Title, abstract or keywords</td><td>{e(' OR '.join(S.THREAT))}<br><span class="note">From the
proposal: "data poisoning, malicious participants, free riding" and "an attacker … may insert fake nodes in the ML training process";
Byzantine, backdoor and Sybil are the literature's names for these; "verifiable" stands for the proposal's "data integrity verification".
DDoS is left out: it attacks the service, not the learning, and would pull in network-security papers.</span></td></tr>
<tr><td>Learning</td><td>Title, abstract or keywords</td><td>as in the survey arm</td></tr>
<tr><td>NG-IoT</td><td>Title, abstract or keywords</td><td>as in the survey arm</td></tr></table>

<h2>1. Scopus — done</h2><p>P-S2 was run and exported (4,543 records, all years, filed with its SHA-256). Kept below for the record.</p>
<ol><li><b>Advanced document search</b>; clear the box, paste, <b>Search</b>; no filters (limits are in the query).</li>
<li>Note the count. Export: <b>All</b> → <b>Export</b> → <b>CSV</b> → Citation information, Bibliographical information, Abstract &amp; keywords → <b>Export</b>.</li>
<li>If Scopus refuses that many with abstracts, note the message and run the three year parts instead.</li></ol>
{q('P-S2 (whole search)', sp)}
<p class="note">Only if Scopus refuses to export everything at once, run these three instead and export each:</p>
{''.join(q(f'P-S2, part {lab}', sp + add) for lab, add in parts)}

<h2>2. IEEE Xplore (one query, four exports)</h2>
<ol><li><b>Advanced Search</b> → <b>Command Search</b>; paste; <b>Search</b>.</li>
<li>On the results page: <b>Content Type</b>: Conferences, Journals, Magazines, Early Access Articles (not Books); <b>Year</b> 2020–2026. Note this
total count (row "P-B, all years"). It will be over 1,000: Scopus already holds about 2,400 IEEE papers of this search.</li>
<li>IEEE exports at most 1,000 results at a time, so export four times, changing only the <b>Year</b> filter: <b>2020–2023</b> (expect about 750),
<b>2024</b> (about 400), <b>2025</b> (about 700), <b>2026</b> (about 550). Each time: note the count, then <b>Export</b> → <b>Search Results</b> →
<b>CSV</b> → <b>Download</b> (no rows selected).</li>
<li>The four counts should add up to the total. If one part is still over 1,000, export it twice: Conferences, then Journals with Magazines and
Early Access.</li></ol>
<p class="note">One query of 25 terms (IEEE's limit): privacy in the title, or privacy with a threat in the abstract; learning and the NG-IoT
setting in the abstract. The abstract is used instead of "All Metadata", whose journal names (e.g. "IEEE Internet of Things Journal") flood the
results.</p>
{ieee}

<h2>3. ScienceDirect (4 searches)</h2>
<ol><li><b>sciencedirect.com</b> → <b>Advanced search</b> → <b>Show all fields</b>.</li>
<li>Paste into <b>Title</b> (P-D1 and P-D2 only) and into <b>Title, abstract or author-specified keywords</b>; leave other fields empty; <b>Year(s)</b>: 2020-2026; <b>Search</b>.</li>
<li><b>Article type</b>: tick <b>Review articles</b> and <b>Research articles</b> only.</li>
<li>Note the number of results. Export: <b>100</b> per page → <b>Select all articles</b> → <b>Export</b> → <b>Export citation to RIS</b>; page by page if needed.</li></ol>
<p class="note">ScienceDirect allows 8 connectors (AND, OR) per field, so these four cover the main terms only; Elsevier's journals are also in Scopus.</p>
{sd}

<h2>4. Record table</h2>
<table><tr><th>Search</th><th>Date</th><th>Time</th><th>Results shown (exact)</th><th>Filters set</th><th>File name(s)</th></tr>{table}</table>

<h2>5. Criteria for both kinds of study (draft — please approve or change)</h2>
<p>The approved criteria (search-ppml/CRITERIA-APPROVED-2026-10-04.md) stay; the study type widens and one question is open.</p>
<table><tr><th>Code</th><th>Criterion</th></tr>
<tr><td>IC1</td><td>The study's subject includes the privacy of machine learning (of the data, the models or the updates) in an NG-IoT setting. <i>(as approved)</i></td></tr>
<tr><td>IC2</td><td><b>Primary:</b> it proposes, builds or evaluates a method, system, protocol or attack concerning the privacy of learning, or measures privacy leakage.
<b>Secondary:</b> a survey, systematic review or mapping study, SoK, or a tutorial or overview that reviews the literature. <i>(widened)</i></td></tr>
<tr><td>IC3–IC5</td><td>Peer-reviewed journal, conference or magazine article (no preprints); January 2020 to the date of the search; English, full text available. <i>(as approved)</i></td></tr>
<tr><td>EC1–EC3</td><td>Retracted; a duplicate or earlier version; not a full paper (editorial, poster, extended abstract, panel summary, thesis, book or chapter). <i>(as approved)</i></td></tr>
<tr><td>EC4</td><td>Privacy is incidental. Secondary: named, but not treated as a subject. <i>(as approved)</i> Primary: privacy is not part of the study's own contribution — <b>see the open question</b>.</td></tr>
<tr><td>EC5</td><td>The learning or the NG-IoT setting is incidental. <i>(as approved)</i></td></tr>
<tr><td>EC6</td><td>Neither kind of study: a position, vision or opinion paper with no method, system or evaluation of its own that does not review the literature. <i>(new)</i></td></tr></table>
<div class="open"><b>Open question (EC4 for primary studies):</b> does a primary study count when its only privacy protection is federated learning itself
(the raw data stay on the device)?<br>
<b>Recommended — no:</b> privacy must come from the study's own contribution: a privacy mechanism added to the learning (differential privacy,
homomorphic encryption, secure multi-party computation or secret sharing, secure aggregation, trusted execution, anonymisation, masked or
encrypted updates) or an analysis of privacy attacks or leakage. Plain federated-learning studies are the bulk of "FL for IoT" papers and say
nothing new about privacy; the PhD's problem is protecting, and checking, the updates themselves.<br>
<b>Alternative — yes:</b> every study that presents its learning as privacy-preserving, plain federated learning included: a broader map with
many more included studies.</div>
<p>The screening app changes with these criteria: question 1 becomes "What kind of study is it? Primary / Secondary / Neither / Can't tell",
question 3 reads "Is privacy part of its own contribution?" for a primary study, and the code NOT-SECONDARY becomes NOT-A-STUDY (EC6). The
in-depth reading (a paragraph per study) is chosen after screening, as in the ZK review.</p>
</body></html>
"""
    OUT.write_text(doc, encoding='utf-8')
    print(OUT.relative_to(ROOT))


if __name__ == '__main__':
    main()
