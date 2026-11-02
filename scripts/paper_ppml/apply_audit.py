#!/usr/bin/env python3
"""Apply the decided corrections of a claims audit (scripts/paper_ppml/claims_audit.py) to the records and the text.

The author, 7 October 2026: "all the claims we make in paper should be 100% correct". The auditors' findings
(search-ppml/evidence/claims-audit-V<v>/FINDINGS-V<v>.csv) are decided one by one into DECISIONS-V<v>.json; this script
applies only what is decided there:

  {"action": "value", "key": "N019", "q": "P2", "field": "hidden_from", "new": [...], "evidence": [{"page": 8, "quote": "..."}],
   "why": "...", "finding": "N019:V8"}             the extraction record's value; the evidence is added to that answer
  {"action": "answer", "key": "S026", "q": "S1", "append": "...", "evidence": [...], "finding": "..."}
                                                   a sentence added to the answer text (so that a corrected paragraph's
                                                   numbers stay in the answer it is marked with)
  {"action": "answer_replace", "key": "S016", "q": "S6", "old": "...", "new": "...", "evidence": [...]}
                                                   a wrong clause of the answer text corrected
  {"action": "text", "file": "studies/g13.md", "old": "...", "new": "...", "finding": "..."}
                                                   a paragraph or part of the review (myliteraturereviewpaper/ppml2026/<file>);
                                                   "old" must occur exactly once
  {"action": "qa6", "key": "n3348", "level": "no" | "partial" | "yes", "reason": "...", "finding": "..."}
  {"action": "ref", "key": "gdpr2016", "field": "ieee", "new": "...", "finding": "..."}
  {"action": "reject", "key": "O108", "why": "...", "finding": "..."}   a finding decided against, with the reason (nothing changes)
  {"action": "evidence_replace", "key": "O078", "q": "S1", "old": "<start of the old quotation>", "new": {"page": 6, "quote": "..."}}
                                                   a quotation reworded in the published version
  {"action": "record_field", "key": "O078", "field": "pages", "new": "27"}   a field of the record itself

Every touched file is copied once to claims-audit-V<v>/before/ first; every change is logged to APPLIED-V<v>.jsonl.
A decision already applied (the new state is present) is skipped, so running it twice changes nothing.

Usage: python3 scripts/paper_ppml/apply_audit.py <version> [--dry-run]
"""
import datetime, json, pathlib, shutil, sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
P = ROOT / 'myliteraturereviewpaper' / 'ppml2026'
EV = ROOT / 'search-ppml' / 'evidence'
SHEETS = EV / 'sheets'
QA = EV / 'QA-CONSISTENCY-2026-10-05.json'
NOW = datetime.datetime.now().isoformat(timespec='seconds')


def snapshot(od, f):
    dst = od / 'before' / f.relative_to(ROOT)
    if not dst.exists():
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(f, dst)


def main(v, dry):
    od = EV / f'claims-audit-V{v}'
    decisions = json.loads((od / f'DECISIONS-V{v}.json').read_text(encoding='utf-8'))
    log = od / f'APPLIED-V{v}.jsonl'
    done = skipped = 0
    problems = []
    for d in decisions['decisions']:
        a = d['action']
        if d.get('superseded_by'):                      # applied, then rewritten by a later decision
            skipped += 1
            continue
        if a == 'reject':                                # decided against, with the reason; nothing changes
            skipped += 1
            continue
        if a == 'value':
            f = SHEETS / f"{d['key']}.json"
            sh = json.loads(f.read_text(encoding='utf-8'))
            ans = sh['answers'][d['q']]
            vals = ans.setdefault('values', {})
            if vals.get(d['field']) == d['new']:
                skipped += 1
                continue
            old = vals.get(d['field'])
            if not dry:
                snapshot(od, f)
                vals[d['field']] = d['new']
                ev = ans.setdefault('evidence', [])
                for e in d.get('evidence', []):
                    if e not in ev:
                        ev.append(e)
                sh['remarks'] = (sh.get('remarks', '') + f" [claims audit V{v}, {NOW[:10]}: {d['q']}.{d['field']} {json.dumps(old, ensure_ascii=False)}"
                                 f" -> {json.dumps(d['new'], ensure_ascii=False)}: {d.get('why', '')}]").strip()
                f.write_text(json.dumps(sh, indent=1, ensure_ascii=False), encoding='utf-8')
            entry = {'old': old, 'new': d['new']}
        elif a == 'answer':
            f = SHEETS / f"{d['key']}.json"
            sh = json.loads(f.read_text(encoding='utf-8'))
            ans = sh['answers'][d['q']]
            if d['append'] in ans.get('answer', ''):
                skipped += 1
                continue
            if not dry:
                snapshot(od, f)
                ans['answer'] = (ans.get('answer', '').rstrip() + ' ' + d['append']).strip()
                ev = ans.setdefault('evidence', [])
                for e in d.get('evidence', []):
                    if e not in ev:
                        ev.append(e)
                f.write_text(json.dumps(sh, indent=1, ensure_ascii=False), encoding='utf-8')
            entry = {'append': d['append']}
        elif a == 'answer_replace':
            f = SHEETS / f"{d['key']}.json"
            sh = json.loads(f.read_text(encoding='utf-8'))
            ans = sh['answers'][d['q']]
            cur = ans.get('answer', '')
            if d['new'] in cur and d['old'] not in cur:
                skipped += 1
                continue
            if cur.count(d['old']) != 1:
                problems.append(f"{d.get('finding')}: the old clause occurs {cur.count(d['old'])} times in {d['key']} {d['q']}")
                continue
            if not dry:
                snapshot(od, f)
                ans['answer'] = cur.replace(d['old'], d['new'])
                ev = ans.setdefault('evidence', [])
                for e in d.get('evidence', []):
                    if e not in ev:
                        ev.append(e)
                f.write_text(json.dumps(sh, indent=1, ensure_ascii=False), encoding='utf-8')
            entry = {'old': d['old'], 'new': d['new']}
        elif a == 'text':
            f = P / d['file']
            t = f.read_text(encoding='utf-8')
            if d['new'] in t and (d['old'] not in t or d['old'] in d['new']):
                skipped += 1
                continue
            n = t.count(d['old'])
            if n != 1:
                problems.append(f"{d.get('finding')}: the old text occurs {n} times in {d['file']}: {d['old'][:80]!r}")
                continue
            if not dry:
                snapshot(od, f)
                f.write_text(t.replace(d['old'], d['new']), encoding='utf-8')
            entry = {'file': d['file'], 'old': d['old'], 'new': d['new']}
        elif a == 'evidence_replace':                    # a quotation reworded in the published version: the published page and words
            f = SHEETS / f"{d['key']}.json"
            sh = json.loads(f.read_text(encoding='utf-8'))
            ev = sh['answers'][d['q']].setdefault('evidence', [])
            news = d['new'] if isinstance(d['new'], list) else [d['new']]        # a sentence split by a page break: two quotations
            hit = [e for e in ev if str(e.get('quote', '')).startswith(d['old'][:50])]
            if not hit and all(any(e.get('quote') == n['quote'] and e.get('page') == n['page'] for e in ev) for n in news):
                skipped += 1
                continue
            if len(hit) != 1:
                problems.append(f"{d.get('finding')}: {len(hit)} quotations of {d['key']} {d['q']} start with {d['old'][:50]!r}")
                continue
            old_e = dict(hit[0])
            if not dry:
                snapshot(od, f)
                i = ev.index(hit[0])
                ev[i:i + 1] = [{k: v for k, v in n.items() if k in ('page', 'quote', 'source')} for n in news]
                f.write_text(json.dumps(sh, indent=1, ensure_ascii=False), encoding='utf-8')
            entry = {'old': old_e, 'new': news}
        elif a == 'record_field':                        # a field of the record itself (page count, remarks)
            f = SHEETS / f"{d['key']}.json"
            sh = json.loads(f.read_text(encoding='utf-8'))
            if sh.get(d['field']) == d['new']:
                skipped += 1
                continue
            old_v = sh.get(d['field'])
            if not dry:
                snapshot(od, f)
                sh[d['field']] = d['new']
                f.write_text(json.dumps(sh, indent=1, ensure_ascii=False), encoding='utf-8')
            entry = {'old': old_v, 'new': d['new']}
        elif a == 'qa6':
            q = json.loads(QA.read_text(encoding='utf-8'))
            cur = 'no' if d['key'] in q['no'] else 'partial' if d['key'] in q['partial'] else 'yes'
            if cur == d['level'] and (d['level'] == 'yes' or q[d['level']].get(d['key']) == d['reason']):
                skipped += 1
                continue
            if not dry:
                snapshot(od, QA)
                for lv in ('no', 'partial'):
                    q[lv].pop(d['key'], None)
                if d['level'] in ('no', 'partial'):
                    q[d['level']][d['key']] = d['reason']
                QA.write_text(json.dumps(q, indent=1, ensure_ascii=False), encoding='utf-8')
            entry = {'from': cur, 'to': d['level'], 'reason': d.get('reason', '')}
        elif a == 'ref':
            f = P / 'refs.json'
            refs = json.loads(f.read_text(encoding='utf-8'))
            if refs[d['key']].get(d['field']) == d['new']:
                skipped += 1
                continue
            old = refs[d['key']].get(d['field'])
            if not dry:
                snapshot(od, f)
                refs[d['key']][d['field']] = d['new']
                f.write_text(json.dumps(refs, indent=1, ensure_ascii=False), encoding='utf-8')
            entry = {'old': old, 'new': d['new']}
        else:
            problems.append(f'unknown action {a}')
            continue
        done += 1
        if not dry:
            with open(log, 'a', encoding='utf-8') as fh:
                fh.write(json.dumps({'time': NOW, 'finding': d.get('finding'), 'action': a, 'key': d.get('key'), **entry},
                                    ensure_ascii=False) + '\n')
    print(f"{'would apply' if dry else 'applied'} {done}, already applied {skipped}, problems {len(problems)}")
    for p in problems:
        print('  ', p)
    return 1 if problems else 0


if __name__ == '__main__':
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    sys.exit(main(sys.argv[1], '--dry-run' in sys.argv))
