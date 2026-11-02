#!/usr/bin/env python3
"""Apply the author's reasons for the full-text decisions of the full second screening (5 October 2026), and the criterion
they set, to every record alike.

The author reviewed the 147 full texts in the screening app (search-ppml/PPML Second Screening.app), overruling 74 of the
AI's proposed inclusions, then gave the reasons (answers in the session of 5 October 2026):
  primary studies — "Blockchain must be in the design": a primary study must build on a blockchain or distributed ledger.
                    This becomes criterion IC3 for primary studies in CRITERIA-V9 (new code NO-BLOCKCHAIN, EC9), applied to
                    every record: the primary studies already included without a ledger (p0574, p5351) leave the review.
  surveys         — "Angles not covered in depth": the focus angles are not covered in substance (the author's full-text
                    judgement), code OFF-FOCUS.
p4875 builds on a blockchain, so the new rule does not explain its exclusion; it keeps the author's exclusion with the
judgement reason and is listed for the author to confirm.

1. writes search-ppml/CRITERIA-V9-2026-10-05.md (V8 is kept unchanged);
2. sets the reason of each overruled proposal in search-ppml/evidence/rescreen/AUTHOR-RESCREEN-DECISIONS-2026-10-05.csv,
   logging old and new values in AUTHOR-RESCREEN-LOG-2026-10-05.jsonl;
3. records the exclusion of p0574 and p5351 through scripts/paper_ppml/record_later_decisions.py (run after this script).
The screening app must be closed. Running it twice changes nothing.

Usage: python3 scripts/paper_ppml/apply_fulltext_reasons.py
"""
import csv, datetime, json, pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
P = ROOT / 'search-ppml'
RS = P / 'evidence' / 'rescreen'
NOW = datetime.datetime.now().isoformat(timespec='seconds')
SURVEY_WHY = "focus angles not covered in substance (the author's full-text judgement)"
PRIMARY_WHY = 'no blockchain or distributed ledger in the design (IC3 for primary studies, criteria V9)'
CONFIRM = {'p4875'}


def criteria_v9():
    out = P / 'CRITERIA-V9-2026-10-05.md'
    if out.exists():
        return
    v8 = (P / 'CRITERIA-V8-2026-10-05.md').read_text(encoding='utf-8')
    head = ("# Eligibility criteria, version 9 — as version 8, with a blockchain in the design required of primary studies (5 October 2026)\n\n"
            "Version 9 changes one criterion, set by the author after reviewing the full texts of the second screening: **a primary "
            "study must build on a blockchain or distributed ledger (IC3f) as part of its design.** The author, asked why the 29 "
            "primary studies proposed for inclusion were excluded, answered: \"Blockchain must be in the design\". The PhD proposal "
            "states: \"This project will employ blockchain technology to design and develop a privacy-preserved ML approach at the edge "
            "of NG-IoT.\" The rule applies to every record alike, including the primary studies already included (two without a ledger "
            "leave the review). For secondary studies IC3 is unchanged: a survey must cover at least one of IC3a–IC3g in substance; at "
            "full text the author judged how deeply the angles are covered (exclusion reason: the focus angles are not covered in "
            "substance, code OFF-FOCUS). Version 8 is kept unchanged (`CRITERIA-V8-2026-10-05.md`).\n\n"
            "| Code | Change in version 9 |\n|---|---|\n"
            "| IC3 (primary) | A primary study deals with at least one of IC3a–IC3g **and builds on a blockchain or distributed ledger (IC3f) as part of its design** — smart contracts, consensus or on-chain records; not blockchain named only as background or future work. |\n"
            "| EC9 | **New:** a primary study without a blockchain or distributed ledger in its design — code NO-BLOCKCHAIN. |\n\n"
            "The rest of version 8 follows unchanged.\n\n---\n\n")
    out.write_text(head + v8, encoding='utf-8')
    print('written', out.name)


def main():
    criteria_v9()
    R = {r['n']: r for r in csv.DictReader(open(RS / 'RESCREEN-FULLTEXT-2026-10-05.csv', encoding='utf-8'))}
    f = RS / 'AUTHOR-RESCREEN-DECISIONS-2026-10-05.csv'
    rows = list(csv.DictReader(open(f, encoding='utf-8')))
    log = RS / 'AUTHOR-RESCREEN-LOG-2026-10-05.jsonl'
    changed = 0
    for a in rows:
        r = R.get(a['n'])
        if not r or a['decision'] != 'EXCLUDE' or r['proposed'] != 'INCLUDE' or r['id'] in ('p0358', 'p0434'):
            continue
        if r['kind'] == 'primary' and r['id'] not in CONFIRM:
            new = {'code': 'NO-BLOCKCHAIN', 'comment': PRIMARY_WHY}
        elif r['id'] in CONFIRM:
            new = {'code': 'OFF-FOCUS', 'comment': "the author's full-text judgement; it builds on a blockchain, so the author is asked to confirm"}
        else:
            new = {'code': 'OFF-FOCUS', 'comment': SURVEY_WHY}
        if any(a.get(k) != v for k, v in new.items()):
            with open(log, 'a', encoding='utf-8') as fh:
                fh.write(json.dumps({'time': NOW, 'n': int(a['n']), 'changed': 'reason', 'note': "the author's reason (5 October 2026)",
                                     'old': {k: a.get(k) for k in new}, **new}, ensure_ascii=False) + '\n')
            a.update(new)
            changed += 1
    with open(f, 'w', encoding='utf-8', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f'reasons set: {changed}')


if __name__ == '__main__':
    main()
