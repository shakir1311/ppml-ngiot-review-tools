#!/usr/bin/env python3
"""PRISMA 2020 flow and thematic tables of the PPML review after title-and-abstract screening (4 October 2026).

Counts come from the records and the author's decisions only:
  search-ppml/MERGE-CHECK-2026-10-04.json, MERGED-RECORDS-2026-10-04.csv   identification, duplicates, automated rules
  search-ppml/AUTHOR-DECISIONS-2026-10-04.csv                                 the author's decisions and answers
  search-ppml/PREFILL-2026-10-04.csv                                          for records left at a default Exclude
  search-ppml/OTHER-METHODS-2026-10-04.csv                                    studies identified via other methods
  search-ppml/evidence/regulation-search/ (scripts/search_ppml/rs1.py)        the supplementary search R-S1, recorded since 8 October
                                                                              2026: its screening and the author's full-text decisions
The thematic tables use the author's own answers at screening (kind of study, the PhD angles ticked, what the
zero-knowledge proof shows); the privacy techniques and settings columns are cue words found in the title, abstract and
keywords (as in the pre-fill), marked as such. Nothing is judged by a language model here.

Outputs: search-ppml/INCLUDED-STUDIES-2026-10-04.csv (one row per study included at screening; read by the full-text stage)
         search-ppml/FINAL-STUDIES-2026-10-05.csv (the studies included after full text, with the author's full-text answers)
         Docs/PPML-REVIEW-PRISMA-AND-THEMES-V8-2026-10-08.html (printable in portrait and landscape; earlier versions kept:
         …-2026-10-04.html, screening; …-V2 to V7-2026-10-05.html; V8 adds the supplementary search R-S1)
The full-text stage (search-ppml/AUTHOR-FULLTEXT-2026-10-05.csv) gives the reports assessed, excluded with reasons and the
studies included; the thematic tables use the author's full-text answers.

Usage: python3 scripts/search_ppml/prisma_report.py
"""
import csv, html, json, pathlib, sys
from collections import Counter

csv.field_size_limit(10 ** 9)
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import merge as M                                     # noqa: E402
import prefill as PF                                  # noqa: E402
import rs1 as RS1                                     # noqa: E402

P = M.P
ROOT = M.ROOT
OUT_CSV = P / 'INCLUDED-STUDIES-2026-10-04.csv'
OUT_HTML = ROOT / 'Docs' / 'PPML-REVIEW-PRISMA-AND-THEMES-V8-2026-10-08.html'   # V8: the supplementary search R-S1 (V7 kept)
OUT_FINAL = P / 'FINAL-STUDIES-2026-10-05.csv'
FT_FILE = P / 'AUTHOR-FULLTEXT-2026-10-05.csv'
ANGLES = list(M.FOCUS_PARTS)
SHORT = {'poisoning': 'Poisoning', 'malicious or fake participants': 'Malicious / fake', 'free riding': 'Free riding',
         'verification': 'Verification (other)', 'zero-knowledge proofs': 'ZK proofs', 'blockchain': 'Blockchain',
         'ZK on blockchain': 'ZK on-chain'}
ZK = {'training': 'training done', 'bounded': 'update bounded', 'similarity': 'update similar', 'aggregation': 'aggregation',
      'identity': 'identity', 'inference': 'inference', 'other': 'other'}
SETTINGS = [('IoV / vehicular', ['IoV', '"internet of vehicles"', 'vehicular', '"connected vehicle*"', '"autonomous vehicle*"', 'V2X']),
            ('IIoT / industry', ['IIoT', '"industrial internet"', '"industry 4.0"', '"industry 5.0"']),
            ('IoMT / healthcare', ['IoMT', '"internet of medical things"', 'healthcare', 'medical']),
            ('Smart grid / energy', ['"smart grid*"', 'energy']),
            ('UAV / space', ['UAV*', 'drone*', 'satellite*', '"space-air-ground"']),
            ('Edge / fog / MEC', ['"edge computing"', '"mobile edge"', 'MEC', 'fog', '"edge intelligence"', '"edge device*"']),
            ('5G / 6G', ['5G', '6G', 'B5G', '"beyond 5G"']),
            ('IoT (general)', ['IoT', '"Internet of Things"'])]
SET_RX = [(name, [M.term_re(t) for t in terms]) for name, terms in SETTINGS]
e = html.escape


def found(text, pats):
    return [n for n, p in pats if p.search(text)]


def main():
    mc = json.loads((P / 'MERGE-CHECK-2026-10-04.json').read_text())
    R = {r['n']: r for r in csv.DictReader(open(P / 'MERGED-RECORDS-2026-10-04.csv', encoding='utf-8'))}
    F = {r['n']: r for r in csv.DictReader(open(P / 'PREFILL-2026-10-04.csv', encoding='utf-8'))}
    D = {d['n']: d for d in csv.DictReader(open(P / 'AUTHOR-DECISIONS-2026-10-04.csv', encoding='utf-8'))}
    K = {k['n']: k for k in csv.DictReader(open(P / 'OTHER-METHODS-2026-10-04.csv', encoding='utf-8'))}
    idx = {r['id']: r for r in csv.DictReader(open(P / 'CORPUS-INDEX-2026-10-04.csv', encoding='utf-8'))}
    cm = {}
    for m in csv.DictReader(open(P / 'CORPUS-MATCHES-2026-10-04.csv', encoding='utf-8')):
        cm.setdefault(m['n'], m['corpus_id'])

    # ---------------------------------------------------------------- PRISMA counts
    screen = [n for n, r in R.items() if not r['auto_excluded']]
    rule = Counter(r['auto_excluded'].split(':')[0].split(';')[0] for r in R.values() if r['auto_excluded'])
    by_author = Counter(D[n]['decision'] for n in screen if D.get(n, {}).get('decision'))
    codes = Counter(D[n]['code'] or 'reason not recorded' for n in screen if D.get(n, {}).get('decision') == 'EXCLUDE')
    default = Counter()
    for n in screen:
        if D.get(n, {}).get('decision'):
            continue
        d = D.get(n, {})
        typ, foc = d.get('type') or F[n]['type'], d.get('focus') or F[n]['focus']
        y, c = int(R[n]['year'] or 0), (int(R[n]['cited']) if R[n]['cited'] else None)
        if typ == 'secondary' and y < 2024 and (c is None or c < 100):
            default['date'] += 1
        elif foc == 'no':
            default['angle'] += 1
        else:
            default['undecided'] += 1
    known_inc = [n for n in K if D.get(n, {}).get('decision') == 'INCLUDE']
    included = [n for n in screen if D.get(n, {}).get('decision') == 'INCLUDE'] + known_inc
    FT = {f['n']: f for f in csv.DictReader(open(FT_FILE, encoding='utf-8'))} if FT_FILE.exists() else {}
    CK = {c['n']: c for c in csv.DictReader(open(P / 'CHECK-DECISIONS-2026-10-05.csv', encoding='utf-8'))} if (P / 'CHECK-DECISIONS-2026-10-05.csv').exists() else {}
    check_retrieved = [n for n, c in CK.items() if c['retrieved'] == 'yes']        # reinstated by the second screening, full text assessed
    check_not_retrieved = [n for n, c in CK.items() if c['retrieved'] != 'yes']
    included += [n for n in check_retrieved if n not in included]
    for n in check_retrieved:
        FT[n] = CK[n]
    # the full second screening of every default and rule exclusion (scripts/paper_ppml/rescreen.py): the full texts the author
    # decided in the screening app (rescreen/RESCREEN-FULLTEXT, author over proposal), and the reports not retrieved
    RSF = P / 'evidence' / 'rescreen' / 'RESCREEN-FULLTEXT-2026-10-05.csv'
    RSR = {r['n']: r for r in csv.DictReader(open(RSF, encoding='utf-8'))} if RSF.exists() else {}
    for n, x in RSR.items():
        if n in CK:                                           # decided after the earlier sample
            continue
        if n not in included:
            included.append(n)
        FT[n] = {'decision': x['decision'], 'code': x['code'], 'type': x['kind'], 'zk_proves': '',
                 'focus_parts': x['angles'].replace('ZK on-chain', 'ZK on blockchain')}
    NR = P / 'evidence' / 'rescreen' / 'NOT-RETRIEVED-2026-10-05.json'
    check_not_retrieved += [n for n in (json.loads(NR.read_text(encoding='utf-8')) if NR.exists() else {}) if n not in check_not_retrieved]
    ft_inc = [n for n in included if FT.get(n, {}).get('decision') == 'INCLUDE']
    ft_exc = Counter(FT[n]['code'] or 'reason not recorded' for n in included if FT.get(n, {}).get('decision') == 'EXCLUDE')
    ft_open = [n for n in included if not FT.get(n, {}).get('decision')]

    # ---------------------------------------------------------------- included studies
    rows = []
    for n in included:
        d = FT[n] if FT.get(n, {}).get('decision') else D[n]      # the full-text answers where given
        if n in K:
            k = K[n]
            title, year, venue, doi, cid, text, via = k['title'], k['year'], k['venue'], k['doi'], k['corpus_id'], ' '.join([k['title'], k['abstract'], k['keywords']]), 'other methods'
        else:
            r = R[n]
            title, year, venue, doi, cid, text, via = r['title'], r['year'], r['venue'], r['doi'], cm.get(n, ''), ' '.join([r['title'], r['abstract'], r['keywords']]), ('searches (reinstated by the second screening)' if n in CK or n in RSR else 'searches')
        t = M.norm(text)
        folder = pathlib.Path(idx[cid]['pdf']).parent if cid in idx else None
        if folder is None and n in R:
            folder = pathlib.Path('corpus/ppmlcorpus/surveys') / f'p{int(n):04d}'
        summ = folder / 'notes' / 'SUMMARY.md' if folder else None
        parts = [x for x in (d.get('focus_parts') or '').split('; ') if x]
        rows.append({'n': n, 'corpus_id': cid or (folder.name if folder else ''), 'kind': d.get('type') or '', 'year': year, 'title': title,
                     'venue': venue, 'doi': doi, 'via': via, 'angles': '; '.join(parts), 'zk_proves': d.get('zk_proves', ''),
                     'privacy_cues': '; '.join(list(dict.fromkeys(found(t, PF.MECH)))[:5]),
                     'settings_cues': '; '.join(name for name, pats in SET_RX if any(p.search(t) for p in pats)),
                     'summary': str(summ) if summ and (ROOT / summ).exists() else ''})
    order = {'primary': 0, 'unsure': 1, '': 1, 'secondary': 2}
    rows.sort(key=lambda r: (order.get(r['kind'], 1), -int(r['year'] or 0), r['title']))
    with open(OUT_CSV, 'w', encoding='utf-8', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    if FT:                                                        # the final set: included after full text
        rows = [r for r in rows if FT.get(r['n'], {}).get('decision') == 'INCLUDE']
        for x in RS1.included():                                  # the supplementary search R-S1 (author's full-text decisions)
            t = M.norm(x.pop('abstract_text'))
            rows.append({**{k: x[k] for k in ('n', 'corpus_id', 'kind', 'year', 'title', 'venue', 'doi', 'via', 'angles', 'zk_proves')},
                         'privacy_cues': '; '.join(list(dict.fromkeys(found(t, PF.MECH)))[:5]),
                         'settings_cues': '; '.join(name for name, pats in SET_RX if any(p.search(t) for p in pats)), 'summary': x['summary']})
        rows.sort(key=lambda r: (order.get(r['kind'], 1), -int(r['year'] or 0), r['title']))
        with open(OUT_FINAL, 'w', encoding='utf-8', newline='') as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)

    # ---------------------------------------------------------------- tables
    kinds = Counter(r['kind'] or 'not given' for r in rows)
    def angle_count(kind):
        return Counter(a for r in rows if (kind is None or r['kind'] == kind) for a in r['angles'].split('; ') if a)
    allc, primc, secc = angle_count(None), angle_count('primary'), angle_count('secondary')
    zk_rows = [r for r in rows if 'zero-knowledge proofs' in r['angles']]
    zk_proves = Counter(z for r in zk_rows for z in r['zk_proves'].split('; ') if z)
    combo = lambda *a: [r for r in rows if all(x in r['angles'] for x in a)]
    phd = [r for r in rows if 'ZK on blockchain' in r['angles'] and any(z in r['zk_proves'] for z in ('bounded', 'similarity'))
           and any(x in r['angles'] for x in ('poisoning', 'malicious or fake participants'))]

    tick = lambda r, a: '●' if a in r['angles'].split('; ') else ''
    link = lambda r: f"<a href='../{e(r['summary'])}'>{e(r['corpus_id'] or r['n'])}</a>" if r['summary'] else e(r['corpus_id'] or r['n'])
    study_rows = ''.join(
        f"<tr><td>{link(r)}</td><td>{e(r['kind'] or '—')}</td><td>{e(r['year'])}</td><td class='t'>{e(r['title'])}</td>"
        + ''.join(f"<td class='c'>{tick(r, a)}</td>" for a in ANGLES)
        + f"<td>{e(', '.join(ZK.get(z, z) for z in r['zk_proves'].split('; ') if z))}</td>"
        f"<td class='s'>{e(r['privacy_cues'])}</td><td class='s'>{e(r['settings_cues'])}</td></tr>" for r in rows)
    angle_rows = ''.join(f"<tr><td>{e(SHORT[a])}</td><td class='c'>{allc[a]}</td><td class='c'>{primc[a]}</td><td class='c'>{secc[a]}</td></tr>" for a in ANGLES)
    zk_table = ''.join(f"<tr><td>{e(ZK[z])}</td><td class='c'>{zk_proves[z]}</td></tr>" for z in ZK if zk_proves[z])
    code_rows = ''.join(f"<tr><td>{e(c)}</td><td class='c'>{v:,}</td></tr>" for c, v in codes.most_common())
    fmt = lambda x: f'{x:,}'
    ident = mc['identified']
    rs = RS1.stats()
    rs_codes = ', '.join(f"{k[len('rs1_ex_'):].replace('_', '-').upper()} {v}" for k, v in rs.items() if k.startswith('rs1_ex_'))
    doc = f"""<!doctype html><html lang="en-GB"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>PPML review: PRISMA and themes</title><style>
:root{{--ink:#1b1b1b;--muted:#555;--line:#c9c9c4;--head:#0f4761;--band:#f3f5f7;--box:#eef3f8}}
html,body{{background:#fff;color:var(--ink)}} body{{font:14.5px/1.5 -apple-system,"Helvetica Neue",Arial,sans-serif;margin:0 auto;max-width:72rem;padding:24px 16px 48px}}
h1{{font-size:1.4rem;color:var(--head);margin:0 0 4px}} h2{{font-size:1.12rem;color:var(--head);margin:28px 0 8px;border-bottom:1px solid var(--line)}}
.muted{{color:var(--muted)}} .note{{border:1px solid var(--line);border-radius:6px;padding:8px 12px;background:var(--band);margin:10px 0}}
.flow{{display:grid;grid-template-columns:minmax(0,1.3fr) minmax(0,1fr) minmax(0,1fr);gap:8px 14px;align-items:stretch}}
.b{{border:1.5px solid var(--head);border-radius:6px;padding:7px 10px;background:var(--box)}} .x{{border:1.5px solid #8a8a8a;border-radius:6px;padding:7px 10px;background:#fafafa}}
.lab{{font-weight:700;color:var(--head);grid-column:1/-1;margin-top:6px}} .arrow{{text-align:center;color:var(--muted);grid-column:1}}
table{{border-collapse:collapse;width:100%;font-size:.84rem;margin:6px 0}} th,td{{border:1px solid var(--line);padding:4px 6px;text-align:left;vertical-align:top}}
th{{background:var(--band)}} td.c{{text-align:center}} td.t{{min-width:14rem}} td.s{{font-size:.78rem;color:var(--muted)}} .wrap{{overflow-x:auto}}
.small{{max-width:34rem}}
@page{{size:auto;margin:12mm}}
@media print{{body{{max-width:none;padding:0;font-size:9.5pt}} .wrap{{overflow:visible}} table{{font-size:8pt}} td.t{{min-width:0}}
 .flow,table,tr,.note,.b,.x{{break-inside:avoid}} th,.note,.b,.x{{background:#fff}} a{{color:inherit;text-decoration:none}}}}
</style></head><body>
<h1>PPML review: PRISMA flow and themes (version 8, with the supplementary search R-S1)</h1>
<p class="muted">8 October 2026 (V8: the supplementary search R-S1 added to the 5 October record) · counts from the records and the author's screening and full-text decisions
(scripts/search_ppml/prisma_report.py) · criteria search-ppml/CRITERIA-V7-2026-10-04.md · answers after the corrections of 5 October
and their verification (PPML-REVIEW-CORRECTIONS-V2-2026-10-05.html, PPML-REVIEW-VERIFIED-DECISIONS-2026-10-05.html), and the conflicts with the full-text extraction settled (PPML-CONFLICTS-RESOLVED-2026-10-05.html) · earlier versions: V4 (answers verified), 2026-10-04
(screening), V2 (full text), V3 (first corrections)</p>

<h2>1. PRISMA 2020 flow</h2>
<div class="flow">
<div class="lab">Identification</div>
<div class="b"><b>Records from databases (n = {fmt(mc['identified_total'])})</b><br>Scopus {fmt(ident['Scopus'])} (survey search 1,938; primary-study
search 4,543) · IEEE Xplore {fmt(ident['IEEE Xplore'])} (2,881; 1,695) · ScienceDirect {fmt(ident['ScienceDirect'])} (survey search only)</div>
<div class="x"><b>Removed before screening</b><br>Duplicates: {fmt(mc['duplicates'])}<br>By automation tools: {fmt(mc['auto_excluded'])}
— IEEE Xplore records without the search terms in title, abstract or keywords {fmt(rule['IEEE Xplore only'])}; titles announcing an editorial,
notice or talk {fmt(rule['not a paper'])}; primary-study search records naming no PhD angle {fmt(rule['outside the PhD focus'])}</div>
<div class="b"><b>Studies via other methods (n = {len(K)})</b><br>corpus papers on the topic that the searches did not return, known from
earlier reading</div>
<div class="arrow">↓</div><div></div><div class="arrow" style="grid-column:3">↓</div>
<div class="lab">Screening</div>
<div class="b"><b>Records screened (n = {fmt(len(screen))})</b><br>on title, abstract and keywords, by the author, with answers pre-filled by
a cue-word rule</div>
<div class="x"><b>Records excluded (n = {fmt(len(screen) - len(included) + len(known_inc))})</b><br>by the author: {fmt(by_author['EXCLUDE'])}<br>left at a
default Exclude by the author: {fmt(default['date'] + default['angle'])} — survey before 2024 cited &lt; 100 times (IC7) {fmt(default['date'])};
no PhD angle (IC3) {fmt(default['angle'])}</div>
<div class="x"><b>Assessed (n = {len(K)})</b><br>excluded {len(K) - len(known_inc)}</div>
<div class="arrow">↓</div><div></div><div class="arrow" style="grid-column:3">↓</div>
<div class="lab">Included at screening</div>
<div class="b"><b>From the searches (n = {len(included) - len(known_inc)})</b></div><div></div>
<div class="b"><b>Via other methods (n = {len(known_inc)})</b></div>
<div class="lab">Eligibility (full text)</div>
<div class="b"><b>Reports sought for retrieval (n = {len(included) + len(check_not_retrieved)})</b><br>of which reinstated by the second screening of the exclusions: {len(CK) + len([n for n in RSR if n not in CK])}; retrieved: {len(included)} (all held in the corpus, with notes); not
retrieved: {len(check_not_retrieved)}</div>
<div class="x"><b>Reports excluded (n = {sum(ft_exc.values())})</b><br>{'<br>'.join(e(c) + ': ' + str(v) for c, v in ft_exc.most_common()) or 'none'}</div>
<div class="b"><b>Reports assessed (n = {len(included) - len(ft_open)})</b>{('<br>not yet assessed: ' + str(len(ft_open))) if ft_open else ''}</div>
<div class="arrow">↓</div>
<div class="lab">Supplementary search R-S1 (Scopus, regulation-first, {rs['rs1_date']}; recorded since 8 October 2026)</div>
<div class="b"><b>Records identified (n = {rs['rs1_records']})</b><br>already returned by the searches above: {rs['rs1_already']} (screened with them
{rs['rs1_already_screened']}; set aside there by the IEEE Xplore rule {rs['rs1_aside']}); new: {rs['rs1_new']}</div>
<div class="x"><b>Screened by the automated screening tool (n = {rs['rs1_tool_screened']})</b><br>two blind runs agreed on {rs['rs1_agree']} ({rs['rs1_agree_pct']}%,
κ {rs['rs1_kappa']}); {rs['rs1_reconciled']} settled on the abstracts; excluded {rs['rs1_ta_excluded']}</div>
<div class="b"><b>Reports sought (n = {rs['rs1_sought']})</b><br>not retrieved {rs['rs1_not_retrieved']}; assessed {rs['rs1_assessed']}: excluded
{rs['rs1_excluded']} ({e(rs_codes)}), included {rs['rs1_included']} (the author's decisions)</div>
<div class="arrow">↓</div>
<div class="lab">Included</div>
<div class="b" style="grid-column:1/-1"><b>Studies included in the review (n = {len(rows)})</b>: primary {kinds['primary']}, secondary
{kinds['secondary']}{(', kind not given ' + str(kinds['unsure'] + kinds['not given'])) if kinds['unsure'] + kinds['not given'] else ''} — from the searches
{sum(1 for n in ft_inc if n not in K) if FT else len(included) - len(known_inc)}, via other methods {sum(1 for n in ft_inc if n in K) if FT else len(known_inc)}, from the supplementary search R-S1 {sum(r['via'] == RS1.VIA for r in rows)}.</div>
</div>
<div class="note">Undecided records: {default['undecided']}. Reasons are not required at this stage by PRISMA 2020; where the author's answers
gave one it was recorded (table 2).</div>

<h2>2. Reasons recorded for the author's exclusions (optional at this stage)</h2>
<div class="small"><table><tr><th>Reason (from the author's answers)</th><th>Records</th></tr>{code_rows}</table></div>

<h2>3. The PhD angles across the included studies</h2>
<p>From the author's ticks, confirmed at full text. A study can tick several angles.</p>
<div class="small"><table><tr><th>Angle</th><th>All ({len(rows)})</th><th>Primary ({kinds['primary']})</th><th>Secondary ({kinds['secondary']})</th></tr>{angle_rows}</table></div>
<p><b>Combinations of angles.</b> Zero-knowledge proofs: {len(zk_rows)} studies; with proofs checked on the blockchain:
{len(combo('zero-knowledge proofs', 'ZK on blockchain'))}; zero-knowledge with poisoning: {len(combo('zero-knowledge proofs', 'poisoning'))}; with
malicious or fake participants: {len(combo('zero-knowledge proofs', 'malicious or fake participants'))}; blockchain with poisoning:
{len(combo('blockchain', 'poisoning'))}. Zero-knowledge is one direction for the "my research" or future-directions section, not the
core of the PhD; the studies where a zero-knowledge proof about the update (bounded or similar to others) is checked on the blockchain
and poisoning or fake participants are treated: {(('<b>' + str(len(phd)) + '</b> (' + ', '.join(e(r['corpus_id'] or r['n']) for r in phd) + ')') if phd else '<b>none so far</b>') if any(r['zk_proves'] for r in zk_rows) else 'not counted — "What does the ZK proof show?" is not answered (optional)'}.</p>
<p><b>What the zero-knowledge proofs show</b> (the author's optional answer, {sum(1 for r in zk_rows if r['zk_proves'])} of {len(zk_rows)} ZK studies answered):</p>
<div class="small"><table><tr><th>The proof shows</th><th>Studies</th></tr>{zk_table or '<tr><td colspan=2>not answered</td></tr>'}</table></div>

<h2>4. The included studies</h2>
<p class="muted">● = angle ticked by the author. ZK shows = the author's answer. Privacy techniques and settings = cue words in the
title, abstract and keywords (not a judgement). The id links to the study's summary.</p>
<div class="wrap"><table><tr><th>Id</th><th>Kind</th><th>Year</th><th>Title</th>{''.join(f'<th>{e(SHORT[a])}</th>' for a in ANGLES)}<th>ZK shows</th>
<th>Privacy techniques (cue words)</th><th>Settings (cue words)</th></tr>{study_rows}</table></div>

<h2>5. Open for the author</h2>
<ul>
<li>Full text: {len(included) - len(ft_open)} of {len(included)} assessed; {sum(ft_exc.values())} excluded. The Method states how the full texts were
assessed (by the author, against the criteria, with the reading notes).</li>
<li>Optional, for the future-directions section: "What does the ZK proof show?" for the {len(zk_rows)} zero-knowledge studies
({len(zk_rows) - sum(1 for r in zk_rows if r['zk_proves'])} unanswered).</li>
<li>The Method needs: one reviewer screened (or a second reviewer on a sample), the counts each database showed on screen, and the AI
disclosure (scripts written with AI assistance).</li>
</ul>
</body></html>
"""
    OUT_HTML.write_text(doc, encoding='utf-8')
    print(f'{len(rows)} studies in the review; report -> {OUT_HTML.relative_to(ROOT)}')
    print('kinds', dict(kinds), '| angles', dict(allc), '| zk', len(zk_rows), dict(zk_proves), '| phd space', [r['corpus_id'] for r in phd])
    print('screened', len(screen), 'author', dict(by_author), 'default', dict(default))


if __name__ == '__main__':
    main()
