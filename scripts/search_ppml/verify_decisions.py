#!/usr/bin/env python3
"""Verify every answer of the 54 studies in the PPML review with conclusive evidence (5 October 2026).

The author: "where in doubt - refer to summaries - then notes and then to full.txt in increasing order if a conclusion is
not obvious ... give me a verified output without any doubts". Unlike check_decisions.py (first cue found), this script
counts only conclusive sentences and escalates when a source gives none:
  S  the summary's body (its title line and its venue line do not count)
  N  the notes' body (the header block, headings, codes and keyword lines do not count)
  F  the full text, page by page (for a stated NG-IoT focus: pages 1-2, i.e. title, abstract and introduction)
  T  the record's title — counts only for the NG-IoT focus, which the criteria allow to be stated in the title
An answer is VERIFIED (with the sentence and where it is), CONTRADICTED (the PhD-focused notes give the angle no bullet
and list it as not treated), or UNRESOLVED (no conclusive sentence anywhere). Unresolved answers are then read by Claude
Code at the pages printed with --show and recorded in search-ppml/VERIFIED-BY-READING-2026-10-05.csv (page and quotation),
which this script merges in.

Conclusive means, per answer:
  kind          the summary's venue line names the kind, or the notes' header ("kind:") does
  privacy       primary: a sentence naming a privacy mechanism or privacy attack/analysis (the pre-fill's list)
                secondary: a sentence that says the survey covers, reviews, compares or classifies privacy or a mechanism
  angle         a sentence with the angle's cue words (ZK on-chain: a zero-knowledge proof verified on chain, by a smart
                contract, chaincode or validators, or the chain's on-chain-verification phrases)
  ZK shows      a sentence naming a zero-knowledge proof and what it shows
  NG-IoT        the author's reading (5 October): IoT with 5G, edge or another next-generation enabler is NG-IoT (IIoT,
                IoMT, IoV, smart grid, edge, fog, 5G/6G, communication networks); it counts when the title, the paper's own
                abstract (A) or its pages 1-2 cover it — a strict "stated focus" is not required
Outputs: search-ppml/VERIFY-DECISIONS-2026-10-05.csv, Docs/PPML-REVIEW-VERIFIED-DECISIONS-2026-10-05.html

Usage: python3 scripts/search_ppml/verify_decisions.py [--show]   (--show prints candidate full-text sentences for the
       unresolved answers, to be read)
"""
import csv, html, pathlib, re, sys
from collections import Counter, defaultdict

csv.field_size_limit(10 ** 9)
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import merge as M                                     # noqa: E402
import prefill as PF                                  # noqa: E402
import prisma_report as PR                            # noqa: E402
import check_decisions as CD                          # noqa: E402

P, ROOT = M.P, M.ROOT
OUT_CSV = P / 'VERIFY-DECISIONS-2026-10-05.csv'
OUT_HTML = ROOT / 'Docs' / 'PPML-REVIEW-VERIFIED-DECISIONS-2026-10-05.html'
READ = P / 'VERIFIED-BY-READING-2026-10-05.csv'
e = html.escape
COVER = re.compile(r'\b(cover|covers|covered|review|reviews|reviewed|survey|surveys|surveyed|discuss|discusses|examin|analy[sz]|classif|'
                   r'compar|taxonom|categori|summari|overview|address|explor|investigat|focus)')
TRAIN_X = re.compile(r'legitimate training|correct(?:ness)? (?:of )?(?:the )?(?:local )?(?:update|training|gradient)|update correctness|'
                     r'proof of correct|attest\w* (?:a |the )?(?:polynomial|gradient|training)|trained (?:honestly|correctly)')
EXAMPLES = re.compile(r'\b(?:such as|like|including|includ\w+|e g|for example|for instance|and other|among others|other privacy sensitive|'
                      r'domains? (?:like|such)|applications? (?:in|to|of)|application scenarios|scenarios)\b')
AIM = re.compile(r'\b(?:this|the present|the proposed) (?:paper|survey|article|study|work|review|scheme|framework|model|system|approach|method)\b|'
                 r'\bwe\b|\bour\b|\bpropos\w+|\bpresent\w*|\bintroduc\w+|\bdesign\w*|\bdevelop\w*|\bfocus\w*|\btailored\b|\bfor (?:the )?(?:iot|iiot|iomt|iov)\b')
EDGE_IOT = re.compile(r'\bedge (?:mobile )?devices?\b|\bedge systems?\b|\bedge based\b|communication networks?\b|\bindustry [45] 0\b')
TITLE_EDGE = re.compile(r'\bedge\b|\bvehicl|\bdrone|\buav|internet of|\biot\b|smart grid|energy trading|cyber physical|industr')
SKIP = re.compile(r'^\s*(#|\*[^*].*\*\s*$|codes:|themes|keywords|title:|authors:|venue:|doi:|year:|template:|id:|pages_total|read_on|kind:|---)', re.I)


def body_sentences(text, front_matter=False):
    lines = text.splitlines()
    if front_matter and lines and lines[0].strip() == '---':
        end = next((i for i, l in enumerate(lines[1:], 1) if l.strip() == '---'), 0)
        lines = lines[end + 1:]
    keep = [l for l in lines if l.strip() and not SKIP.match(l)]
    return CD.sentences('\n'.join(keep))


def first(sents, test):
    for s in sents:
        if test(M.norm(s)):
            s = re.sub(r'\s+', ' ', s).strip()
            return s[:240] + ('…' if len(s) > 240 else '')
    return ''


def cascade(doc, test, pages=None):
    for level in ('S', 'N'):
        h = first(doc[level], test)
        if h:
            return level, h
    for pno, text in doc['F'].items():
        if pages and pno not in pages:
            continue
        h = first(CD.sentences(text), test)
        if h:
            return 'F', f'[p{pno}] {h}'
    return '', ''


def main():
    show = '--show' in sys.argv
    final = list(csv.DictReader(open(P / 'FINAL-STUDIES-2026-10-05.csv', encoding='utf-8')))
    FT = {f['n']: f for f in csv.DictReader(open(P / 'AUTHOR-FULLTEXT-2026-10-05.csv', encoding='utf-8'))}
    R = {r['n']: r for r in csv.DictReader(open(P / 'MERGED-RECORDS-2026-10-04.csv', encoding='utf-8'))}
    K = {k['n']: k for k in csv.DictReader(open(P / 'OTHER-METHODS-2026-10-04.csv', encoding='utf-8'))}
    corrected = {(c['n'], c['field']) for c in csv.DictReader(open(P / 'CORRECTIONS-2026-10-05.csv', encoding='utf-8'))}
    read = {(r['n'], r['check']): r for r in csv.DictReader(open(READ, encoding='utf-8'))} if READ.exists() else {}
    out, todo = [], []
    for r in final:
        a = FT[r['n']]
        summ = ROOT / r['summary']
        notes = (summ.parent / 'NOTES.md').read_text(encoding='utf-8') if (summ.parent / 'NOTES.md').exists() else ''
        full_p = summ.parent.parent / 'text' / 'full.txt'
        doc = {'S': body_sentences(summ.read_text(encoding='utf-8')), 'N': body_sentences(notes, front_matter=True),
               'F': CD.pages(full_p.read_text(encoding='utf-8', errors='replace')) if full_p.exists() else {}}
        title = (K[r['n']]['title'] if r['n'] in K else R[r['n']]['title'])
        template = (re.search(r'^template:\s*(\S+)', notes, re.M) or [None, '?'])[1]

        def add(check, answer, status, level, evidence, field=''):
            if (r['n'], check) in read:                     # a reading by Claude Code settles the answer, whatever the cue rule found
                rd = read[(r['n'], check)]
                status, level, evidence = rd['status'], 'R', f"[p{rd['page']}] {rd['quote']} — {rd['note']}"
            out.append({'n': r['n'], 'id': r['corpus_id'], 'title': r['title'], 'check': check, 'answer': answer, 'status': status,
                        'level': level, 'evidence': evidence, 'corrected': 'yes' if field and (r['n'], field) in corrected else ''})
            if status == 'UNRESOLVED':
                todo.append((r, check, doc))
        # kind
        m = re.search(r'·\s*(primary study|survey|systematic review|secondary study)\s*·', summ.read_text(encoding='utf-8'))
        kn = re.search(r'^kind:\s*(primary study|survey)', notes, re.M)
        kind = ({'primary study': 'primary'}.get(m.group(1), 'secondary') if m else
                ({'primary study': 'primary'}.get(kn.group(1), 'secondary') if kn else ''))
        add('kind of study', a['type'], 'VERIFIED' if kind == a['type'] else ('CONTRADICTED' if kind else 'UNRESOLVED'),
            'S' if m else ('N' if kn else ''), f"{'summary' if m else 'notes'} say: {(m or kn).group(1)}" if (m or kn) else '')
        # privacy
        mech = CD.any_of(CD.MECH)
        test = mech if a['type'] == 'primary' else (lambda t: bool(COVER.search(t)) and (mech(t) or 'privacy' in t))
        lvl, ev = cascade(doc, test)
        add('privacy', a['privacy'], 'VERIFIED' if lvl and a['privacy'] == 'yes' else 'UNRESOLVED', lvl, ev, 'privacy')
        # angles
        ticked = [x for x in a['focus_parts'].split('; ') if x]
        said, not_treated = CD.ppml_angles(notes) if template == 'ppml-1' else (set(), set())
        for ang in ticked:
            if ang in not_treated and ang not in said:
                add(f'angle: {PR.SHORT[ang]}', 'ticked', 'CONTRADICTED', 'N', 'the PhD-focused notes list it as not treated', 'focus_parts')
                continue
            lvl, ev = cascade(doc, CD.ANGLE_TEST[ang])
            add(f'angle: {PR.SHORT[ang]}', 'ticked', 'VERIFIED' if lvl else 'UNRESOLVED', lvl, ev, 'focus_parts')
        add('at least one PhD angle', f'{len(ticked)} ticked', 'VERIFIED' if ticked else 'UNRESOLVED', '', '')
        # what the ZK proof shows
        for z in [x for x in a.get('zk_proves', '').split('; ') if x and x != 'other']:
            test = CD.ZK_TEST[z] if z != 'training' else (lambda t: CD.ZK_TEST['training'](t) or (bool(CD.ZKW.search(t)) and bool(TRAIN_X.search(t))))
            lvl, ev = cascade(doc, test)
            add(f'ZK proof shows: {PR.ZK[z]}', 'ticked', 'VERIFIED' if lvl else 'UNRESOLVED', lvl, ev, 'zk_proves')
        # NG-IoT as a STATED FOCUS (criteria: title, aims or scope, or the main application area; not one example among many):
        # the title; else a sentence of the paper's own abstract, then of its pages 1-2, naming the setting outside a list of examples
        setting = CD.any_of(CD.SETTING)
        abstract = (K[r['n']]['abstract'] if r['n'] in K else R[r['n']]['abstract'])
        # the author (5 Oct): "the ng-iot rule is not a mandatory thing ... an iot with a 5g is an ngiot - or an iot with an edge
        # is also close to ng-iot": the setting counts when the paper's own abstract or first pages cover it, examples included
        focus = lambda t: setting(t) or EDGE_IOT.search(t)
        if setting(M.norm(title)) or TITLE_EDGE.search(M.norm(title)):
            lvl, ev = 'T', f'title: {title}'
        else:
            lvl, ev = ('A', first(CD.sentences(abstract), focus))
            if not ev:
                lvl, ev = cascade({'S': [], 'N': [], 'F': doc['F']}, focus, pages={1, 2})
        if lvl and ev:
            status = 'VERIFIED' if a['ngiot'] == 'yes' else 'CONTRADICTED'
        else:
            only = first(CD.sentences(abstract), setting) or cascade({'S': [], 'N': [], 'F': doc['F']}, setting, pages={1, 2})[1]
            lvl, ev = ('A', f'only as one example among others: {only}') if only else ('', 'no setting in title, abstract or pages 1-2')
            status = 'VERIFIED' if a['ngiot'] in ('no', 'unsure') else 'NOT A STATED FOCUS'
        add('NG-IoT setting (stated focus)', a['ngiot'], status, lvl, ev, 'ngiot')
        # dates and counts
        year = int(r['year'] or 0)
        rec = R.get(r['n'])
        cited = int(rec['cited']) if rec and rec['cited'] else None
        add('published 2020 or later (IC4)', str(year), 'VERIFIED' if year >= 2020 else 'CONTRADICTED', 'record', '')
        if a['type'] == 'secondary':
            ok7 = year >= 2024 or (cited is not None and cited >= 100)
            add('survey from 2024, or cited ≥ 100 (IC7)', f'{year}, cited {cited}', 'VERIFIED' if ok7 else 'CONTRADICTED', 'record', '')

    with open(OUT_CSV, 'w', encoding='utf-8', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=list(out[0]))
        w.writeheader()
        w.writerows(out)
    st = Counter(o['status'] for o in out)
    print(f"{len(final)} studies, {len(out)} answers: {dict(st)} | by level {dict(Counter(o['level'] for o in out if o['status'] == 'VERIFIED'))}")
    for o in out:
        if o['status'] != 'VERIFIED':
            print(f"  {o['status']:12} {o['id']:6} {o['check']} ({o['answer']})" + (' [corrected]' if o['corrected'] else ''))
    if show:
        for r, check, doc in todo:
            print(f"\n=== {r['corpus_id']} — {check}")
            key = check.split(': ')[-1].lower()
            for pno, text in list(doc['F'].items())[:60]:
                for s in CD.sentences(text):
                    t = M.norm(s)
                    if (('privacy' in check and ('privacy' in t or CD.any_of(CD.MECH)(t))) or ('NG-IoT' in check and CD.any_of(CD.SETTING)(t))
                            or ('ZK' in check and CD.ZKW.search(t)) or (check.startswith('angle') and key.split()[0] in t)):
                        print(f'  [p{pno}] {re.sub(chr(10), " ", s.strip())[:260]}')
                        break
    # page
    by = defaultdict(list)
    for o in out:
        by[o['n']].append(o)
    colour = {'VERIFIED': '#2e7d32', 'CONTRADICTED': '#c62828', 'UNRESOLVED': '#b26a00', 'NOT A STATED FOCUS': '#c62828'}
    blocks = ''.join(
        f"<h3>{e(os[0]['id'])} — {e(os[0]['title'][:110])}</h3><table><tr><th>Answer</th><th>Value</th><th>Status</th><th>Where</th><th>Evidence</th></tr>"
        + ''.join(f"<tr><td>{e(o['check'])}{' <b>(corrected)</b>' if o['corrected'] else ''}</td><td>{e(o['answer'])}</td>"
                  f"<td style='color:{colour[o['status']]};font-weight:600'>{o['status']}</td><td>{e(o['level'])}</td><td class='ev'>{e(o['evidence'])}</td></tr>" for o in os)
        + '</table>' for os in by.values())
    lv = Counter(o['level'] for o in out if o['status'] == 'VERIFIED')
    doc = f"""<!doctype html><html lang="en-GB"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>PPML review: verified decisions</title><style>
:root{{--ink:#1b1b1b;--muted:#555;--line:#c9c9c4;--head:#0f4761;--band:#f3f5f7}}
html,body{{background:#fff;color:var(--ink)}} body{{font:14px/1.45 -apple-system,"Helvetica Neue",Arial,sans-serif;margin:0 auto;max-width:74rem;padding:24px 16px 48px}}
h1{{font-size:1.4rem;color:var(--head);margin:0 0 4px}} h3{{font-size:.95rem;margin:16px 0 4px}} .muted{{color:var(--muted)}}
.note{{border:1px solid var(--line);border-radius:6px;padding:8px 12px;background:var(--band)}}
table{{border-collapse:collapse;width:100%;font-size:.8rem}} th,td{{border:1px solid var(--line);padding:3px 6px;text-align:left;vertical-align:top}}
th{{background:var(--band)}} td.ev{{color:#333}}
@page{{size:auto;margin:12mm}} @media print{{body{{max-width:none;padding:0;font-size:9pt}} table{{font-size:7.5pt}} table,tr,h3{{break-inside:avoid}} th,.note{{background:#fff}}}}
</style></head><body>
<h1>PPML review: every answer of the 54 studies, verified</h1>
<p class="muted">5 October 2026 · scripts/search_ppml/verify_decisions.py · conclusive evidence only, looked for in the summary (S), then the notes (N),
then the full text (F, with page); T = the title (NG-IoT focus only); R = read by Claude Code at the page given · titles, headers, codes and
keyword lines do not count</p>
<div class="note"><b>{len(final)} studies, {len(out)} answers:</b> VERIFIED {st['VERIFIED']} (summary {lv['S']}, notes {lv['N']}, full text {lv['F']},
title {lv['T']}, read {lv['R']}, record {lv['record']}), CONTRADICTED {st['CONTRADICTED']}, UNRESOLVED {st['UNRESOLVED']}.
Answers changed by the corrections of 5 October are marked (corrected).</div>
{blocks}
</body></html>"""
    OUT_HTML.write_text(doc, encoding='utf-8')


if __name__ == '__main__':
    main()
