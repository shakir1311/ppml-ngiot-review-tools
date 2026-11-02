#!/usr/bin/env python3
"""Check the author's decisions on the 54 studies in the PPML review against the studies' own texts (5 October 2026).

The author: "look at summaries of these and if needed look at notes to make sure whatever we decided holds correct. if in
doubt - then look into full.txt - but please do it systematically with scripts and avoid usage of agents where possible."

For every study of search-ppml/FINAL-STUDIES-2026-10-05.csv the author's answers (kind of study, privacy, the PhD angles,
what the zero-knowledge proof shows, NG-IoT setting) and the criteria that can be tested on dates and counts (IC4 2020 on,
IC7 surveys from 2024 unless cited at least 100 times) are compared with the evidence, looked for in this order:
  S  the study's summary (notes/SUMMARY.md)
  N  its reading notes (notes/NOTES.md; the PhD-focused notes also say per angle what is treated and what is not)
  F  its full text (text/full.txt, with the page) — only where S and N give nothing
Evidence is a cue word or phrase found in a sentence (the same cue lists as the pre-fill and the merge rules; a ZK proof
checked on-chain needs a sentence naming both the proof and its on-chain check). The script decides nothing: it marks each
answer OK (evidence found in S or N), WEAK (only in the full text), or CHECK (no evidence, or the notes say the opposite),
and it shows the sentence that was found. Summaries and notes were written by Claude Code readers; the full text is the
paper's own words.

Outputs: search-ppml/DECISION-CHECK-2026-10-05.csv (one row per study and answer)
         Docs/PPML-REVIEW-DECISION-CHECK-2026-10-05.html (printable)

Usage: python3 scripts/search_ppml/check_decisions.py [--version N]   (a new version after corrections; earlier ones are kept)
"""
import csv, html, pathlib, re, sys
from collections import Counter, defaultdict

csv.field_size_limit(10 ** 9)
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import merge as M                                     # noqa: E402
import prefill as PF                                  # noqa: E402
import prisma_report as PR                            # noqa: E402

P, ROOT = M.P, M.ROOT
VERSION = sys.argv[sys.argv.index('--version') + 1] if '--version' in sys.argv else ''   # e.g. --version 2 after corrections
OUT_CSV = P / f"DECISION-CHECK{'-V' + VERSION if VERSION else ''}-2026-10-05.csv"
OUT_HTML = ROOT / 'Docs' / f"PPML-REVIEW-DECISION-CHECK{'-V' + VERSION if VERSION else ''}-2026-10-05.html"
e = html.escape

ANGLE_RX = {a: [M.term_re(t) for t in terms] for a, terms in M.FOCUS_PARTS.items()}
ZKW = re.compile(r'zero knowledge|zk snark|zksnark|zk stark|\bzkps?\b|\bzk\b|groth16|plonk|bulletproof|succinct non interactive')
ONCHAIN = re.compile(r'on chain|smart contract|chaincode|validators?|blockchain|ledger|consensus')
CHECKV = re.compile(r'verif|check|validat')
MECH = [p for _, p in PF.MECH]
SETTING = [p for _, pats in PR.SET_RX for p in pats]


def sentences(text):
    return [s for s in re.split(r'(?<=[.!?;])\s+|\n+', text) if s.strip()]


def pages(full):
    """page number -> text of text/full.txt"""
    out, cur = {}, None
    for line in full.splitlines():
        m = re.match(r'=+ \[ PAGE (\d+) / \d+ \] =+', line)
        if m:
            cur = int(m.group(1))
            out[cur] = []
        elif cur:
            out[cur].append(line)
    return {k: ' '.join(v) for k, v in out.items()}


def hit(sents, test):
    """the first sentence passing test (on norm() text), shortened"""
    for s in sents:
        if test(M.norm(s)):
            s = re.sub(r'\s+', ' ', s).strip()
            return s[:220] + ('…' if len(s) > 220 else '')
    return ''


def find(doc, test):
    """(level, snippet) — summary, then notes, then full text with its page"""
    for level in ('S', 'N'):
        h = hit(doc[level], test)
        if h:
            return level, h
    for pno, text in doc['F'].items():
        h = hit(sentences(text), test)
        if h:
            return 'F', f'[p{pno}] {h}'
    return '', ''


def any_of(pats):
    return lambda t: any(p.search(t) for p in pats)


ANGLE_TEST = {a: any_of(ANGLE_RX[a]) for a in ANGLE_RX}
ANGLE_TEST['zero-knowledge proofs'] = lambda t: bool(ZKW.search(t))
ANGLE_TEST['ZK on blockchain'] = lambda t: bool(ZKW.search(t)) and bool(ONCHAIN.search(t)) and bool(CHECKV.search(t)) or any_of(ANGLE_RX['ZK on blockchain'])(t)
ZK_TEST = {k: (lambda rx: (lambda t: bool(ZKW.search(t)) and bool(rx.search(t))))(rx) for k, rx in PF.ZK_RX.items()}


def ppml_angles(notes):
    """from PhD-focused notes: the angles described in bold and the ones listed as not treated"""
    said = {a for a in M.FOCUS_PARTS for m in re.finditer(r'\*\*([^*]+)\*\*', notes) if a.split()[0] in m.group(1).lower()
            and 'not treated' not in m.group(1).lower()}
    nt = re.search(r'\*\*Not treated:?\*\*:?\s*(.*)', notes)
    not_treated = set()
    if nt:
        low = nt.group(1).lower()
        onchain = re.compile(r'(?:zk|zero[- ]knowledge) proofs? (?:checked|verified) on[- ]?(?:the )?(?:chain|blockchain|ledger)|on-chain|on chain')
        if onchain.search(low):
            not_treated.add('ZK on blockchain')
            low = onchain.sub(' ', low)
        for a, keys in (('poisoning', ('poison',)), ('malicious or fake participants', ('malicious', 'fake', 'sybil', 'byzantine')),
                        ('free riding', ('free rid', 'free-rid')), ('verification', ('verification',)),
                        ('zero-knowledge proofs', ('zero-knowledge', 'zk proof', 'zkp')), ('blockchain', ('blockchain',))):
            if any(k in low for k in keys):
                not_treated.add(a)
    return said, not_treated


def settle(answer, lvl, ev):
    """status of a yes/unsure/no answer of an included study: an included study needs Yes (criteria); Can't tell is to be
    resolved at full text and No means the criterion fails; the evidence found says which answer the texts support"""
    if answer == 'yes':
        return ('OK' if lvl in ('S', 'N') else ('WEAK' if lvl else 'CHECK')), lvl, ev
    support = 'the texts suggest Yes' if lvl else 'no evidence found either'
    what = "Can't tell left at full text" if answer == 'unsure' else 'No, yet included (the criterion fails)'
    return 'CHECK', lvl, f'{what}; {support}: {ev}'


def main():
    rows_f = list(csv.DictReader(open(P / 'FINAL-STUDIES-2026-10-05.csv', encoding='utf-8')))
    FT = {f['n']: f for f in csv.DictReader(open(P / 'AUTHOR-FULLTEXT-2026-10-05.csv', encoding='utf-8'))}
    R = {r['n']: r for r in csv.DictReader(open(P / 'MERGED-RECORDS-2026-10-04.csv', encoding='utf-8'))}
    out = []
    for r in rows_f:
        a = FT[r['n']]
        summ = ROOT / r['summary']
        notes_p = summ.parent / 'NOTES.md'
        full_p = summ.parent.parent / 'text' / 'full.txt'
        notes = notes_p.read_text(encoding='utf-8') if notes_p.exists() else ''
        summary = summ.read_text(encoding='utf-8') if summ.exists() else ''
        doc = {'S': sentences(summary), 'N': sentences(notes), 'F': pages(full_p.read_text(encoding='utf-8', errors='replace')) if full_p.exists() else {}}
        template = (re.search(r'^template:\s*(\S+)', notes, re.M) or [None, '?'])[1]
        add = lambda check, answer, status, level, evidence: out.append(
            {'n': r['n'], 'id': r['corpus_id'], 'title': r['title'], 'notes': template, 'check': check, 'answer': answer,
             'status': status, 'level': level, 'evidence': evidence})
        # kind of study
        m = re.search(r'·\s*(primary study|survey|systematic review|secondary study)\s*·', summary)
        kind_s = {'primary study': 'primary'}.get(m.group(1), 'secondary') if m else ''
        add('kind of study', a['type'], 'OK' if kind_s == a['type'] else ('CHECK' if kind_s else 'WEAK'), 'S' if kind_s else '',
            f'summary says: {m.group(1)}' if m else 'the summary does not say')
        # privacy
        lvl, ev = find(doc, any_of(MECH))
        if a['type'] == 'secondary' and not lvl:
            lvl, ev = find(doc, lambda t: 'privacy' in t)
        add('privacy (own mechanism / treated)', a['privacy'], *settle(a['privacy'], lvl, ev or 'no privacy mechanism found'))
        # PhD angles
        ticked = [x for x in a['focus_parts'].split('; ') if x]
        said, not_treated = ppml_angles(notes) if template == 'ppml-1' else (set(), set())
        for ang in M.FOCUS_PARTS:
            lvl, ev = find(doc, ANGLE_TEST[ang])
            if ang in ticked:
                conflict = ang in not_treated and ang not in said      # listed as not treated and given no bullet of its own
                status = 'CHECK' if conflict else ('OK' if lvl in ('S', 'N') else ('WEAK' if lvl else 'CHECK'))
                note = ' — the notes list it as not treated' if conflict else (' (the notes call it partial)' if ang in not_treated else '')
                add(f'angle: {PR.SHORT[ang]}', 'ticked', status, lvl, (ev or 'no evidence found') + note)
            elif ang in said or (lvl in ('S', 'N') and ang != 'ZK on blockchain'):
                add(f'angle: {PR.SHORT[ang]}', 'not ticked', 'INFO', lvl, ('the notes describe it' if ang in said else 'mentioned') + f': {ev}')
        add('at least one PhD angle with evidence', f'{len(ticked)} ticked',
            'OK' if any(o['status'] in ('OK', 'WEAK') for o in out if o['n'] == r['n'] and o['check'].startswith('angle') and o['answer'] == 'ticked') else 'CHECK', '', '')
        # what the ZK proof shows
        for z in [x for x in a.get('zk_proves', '').split('; ') if x and x != 'other']:
            lvl, ev = find(doc, ZK_TEST[z])
            add(f'ZK proof shows: {PR.ZK[z]}', 'ticked', 'OK' if lvl in ('S', 'N') else ('WEAK' if lvl else 'CHECK'), lvl, ev or 'no evidence found')
        # NG-IoT setting
        lvl, ev = find(doc, any_of(SETTING))
        add('NG-IoT setting', a['ngiot'], *settle(a['ngiot'], lvl, ev or 'no NG-IoT setting found'))
        # dates and counts
        rec = R.get(r['n'])
        year = int(r['year'] or 0)
        cited = int(rec['cited']) if rec and rec['cited'] else None
        add('published 2020 or later (IC4)', str(year), 'OK' if year >= 2020 else 'CHECK', '', '')
        if a['type'] == 'secondary':
            ok7 = year >= 2024 or (cited is not None and cited >= 100)
            add('survey from 2024, or cited ≥ 100 (IC7)', f'{year}, cited {cited if cited is not None else "?"}', 'OK' if ok7 else 'CHECK', '', '')
    with open(OUT_CSV, 'w', encoding='utf-8', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=list(out[0]))
        w.writeheader()
        w.writerows(out)

    by = defaultdict(list)
    for o in out:
        by[o['n']].append(o)
    status = Counter(o['status'] for o in out)
    flagged = [n for n, os in by.items() if any(o['status'] == 'CHECK' for o in os)]
    weak = [n for n, os in by.items() if n not in flagged and any(o['status'] == 'WEAK' for o in os)]
    colour = {'OK': '#2e7d32', 'WEAK': '#b26a00', 'CHECK': '#c62828', 'INFO': '#555'}

    def block(n):
        os = by[n]
        head = os[0]
        lines = ''.join(f"<tr><td>{e(o['check'])}</td><td>{e(o['answer'])}</td><td style='color:{colour[o['status']]};font-weight:600'>{o['status']}</td>"
                        f"<td>{e(o['level'])}</td><td class='ev'>{e(o['evidence'])}</td></tr>" for o in os)
        return (f"<h3>{e(head['id'])} · record {e(n)} — {e(head['title'][:110])}</h3>"
                f"<table><tr><th>Answer checked</th><th>Author</th><th>Status</th><th>Where</th><th>Evidence (first sentence found)</th></tr>{lines}</table>")

    summary_rows = ''.join(
        f"<tr><td>{e(by[n][0]['id'])}</td><td class='t'>{e(by[n][0]['title'][:90])}</td><td>{by[n][0]['notes']}</td>"
        f"<td style='color:#c62828'>{'; '.join(e(o['check']) for o in by[n] if o['status'] == 'CHECK')}</td>"
        f"<td style='color:#b26a00'>{'; '.join(e(o['check']) for o in by[n] if o['status'] == 'WEAK')}</td></tr>"
        for n in flagged + weak)
    doc = f"""<!doctype html><html lang="en-GB"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>PPML review: decision check</title><style>
:root{{--ink:#1b1b1b;--muted:#555;--line:#c9c9c4;--head:#0f4761;--band:#f3f5f7}}
html,body{{background:#fff;color:var(--ink)}} body{{font:14px/1.45 -apple-system,"Helvetica Neue",Arial,sans-serif;margin:0 auto;max-width:72rem;padding:24px 16px 48px}}
h1{{font-size:1.4rem;color:var(--head);margin:0 0 4px}} h2{{font-size:1.12rem;color:var(--head);margin:26px 0 8px;border-bottom:1px solid var(--line)}}
h3{{font-size:.95rem;margin:18px 0 4px}} .muted{{color:var(--muted)}} .note{{border:1px solid var(--line);border-radius:6px;padding:8px 12px;background:var(--band)}}
table{{border-collapse:collapse;width:100%;font-size:.82rem;margin:4px 0}} th,td{{border:1px solid var(--line);padding:3px 6px;text-align:left;vertical-align:top}}
th{{background:var(--band)}} td.ev{{color:#333}} td.t{{min-width:12rem}}
@page{{size:auto;margin:12mm}} @media print{{body{{max-width:none;padding:0;font-size:9pt}} table{{font-size:7.5pt}} table,tr,h3{{break-inside:avoid}} th,.note{{background:#fff}}}}
</style></head><body>
<h1>PPML review: do the decisions hold? (scripted check of the 54 studies)</h1>
<p class="muted">5 October 2026 · scripts/search_ppml/check_decisions.py · evidence looked for in the summary (S), then the notes (N), then the full
text (F, with its page) · nothing decided here</p>
<div class="note"><b>Result.</b> {len(rows_f)} studies, {len(out)} answers checked: OK {status['OK']}, WEAK {status['WEAK']} (evidence only in the
full text, or the summary does not say), CHECK {status['CHECK']} (no evidence found, or the notes say the opposite), INFO {status['INFO']}
(an angle the notes describe that was not ticked). <b>{len(flagged)}</b> studies have at least one CHECK; {len(weak)} more have only WEAK
marks; the other {len(rows_f) - len(flagged) - len(weak)} hold on summary and notes alone.</div>
<h2>1. Studies to look at</h2>
<table><tr><th>Id</th><th>Title</th><th>Notes</th><th>CHECK</th><th>WEAK</th></tr>{summary_rows}</table>
<p class="muted">CHECK is a prompt to look, not a verdict: a cue list can miss a paper's own words. WEAK means the evidence is in the full
text only (summaries and notes are shorter than the papers). INFO angles do not affect inclusion; tick them if the paper treats them.</p>
<h2>2. Study by study (studies with CHECK first)</h2>
{''.join(block(n) for n in flagged)}{''.join(block(n) for n in weak)}{''.join(block(n) for n in by if n not in flagged and n not in weak)}
</body></html>"""
    OUT_HTML.write_text(doc, encoding='utf-8')
    print(f'{len(rows_f)} studies, {len(out)} answers: {dict(status)} | studies with CHECK {len(flagged)}, only WEAK {len(weak)}')
    for n in flagged:
        print('  CHECK', by[n][0]['id'], '|', '; '.join(f"{o['check']} ({o['evidence'][:70]})" for o in by[n] if o['status'] == 'CHECK'))


if __name__ == '__main__':
    main()
