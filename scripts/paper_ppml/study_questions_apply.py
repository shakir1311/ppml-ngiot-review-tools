#!/usr/bin/env python3
"""Apply the independent checkers' verdicts (verify/results/*.json, VERIFY-GUIDE.md) to the study records, the synthesis and the
matches (7 October 2026). The originals stay as the readers, the synthesis run and the matching run wrote them; the corrected
copies go to verify/verified/ (SYNTHESIS.json, MATCHES.json, studies/<key>.json), and every change is listed in
verify/CHANGES.md with its reason and who made it.

verify/DECISIONS.json (optional, written by the orchestrating run after reading the verdicts):
  {"reject": {"<change id>": "reason"},
   "edits": [{"field": "<prose field id>", "text": "...", "reason": "..."}],
   "item_edits": [{"key": "...", "item": "questions|conclusions|open_problems", "index": 0, "text": "...", "reason": "..."}],
   "questions": {"<key>": {"reason": "...", "order": [{"old": 0}, {"new": 0}, ...],
                           "new": [{"q": "...", "evidence": [{"page": 12, "quote": "..."}], "tags": ["Q3"]}]}}}
  "questions" lists a survey's questions in the paper's order when the paper states more research questions than the reading
  recorded: each stated question is added word for word, with its page (its quotation is checked on the page, or was read from
  the page image when marked "source": "image"); a recorded question left out of "order" is one the stated questions replace.
Change ids: <key>.<item>.<n>.text | <key>.<item>.<n>.tags | <key>.posed_by.<add|remove>.<Q> | <key>.themes.<add|remove>.<T> |
L001.<n> | GQ001.<key> | GQ001.note | C001 | C001.note | TN<n> | <prose field id>

Two rules are applied after the verdicts, and logged: a study with a question tagged Q poses Q (the synthesis's definition: its
problem, gap or questions raise Q); an open question's studies are those with a future-work item tagged with it.

Usage: python3 scripts/paper_ppml/study_questions_apply.py
"""
import copy, json, pathlib, shutil, sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import study_questions as SQM                                      # noqa: E402
import check_sheets as CS                                          # noqa: E402

VER, OUT = SQM.VER, SQM.VER / 'verified'
LAB = {'questions': 'question', 'conclusions': 'conclusion', 'open_problems': 'future work'}


def main():
    if SQM.verify_check():
        sys.exit('the results are incomplete; nothing applied')
    S0, M0, D0, st = SQM.load_all()
    S, M, D = copy.deepcopy(S0), copy.deepcopy(M0), copy.deepcopy(D0)
    dec = json.loads((VER / 'DECISIONS.json').read_text(encoding='utf-8')) if (VER / 'DECISIONS.json').exists() else {}
    rej = dec.get('reject', {})
    R = {f.stem: json.loads(f.read_text(encoding='utf-8')) for f in sorted((VER / 'results').glob('*.json'))}
    log, rejected = [], []
    def change(cid, what, before, after, reason, by='checker'):
        if cid in rej:
            rejected.append((cid, what, rej[cid], reason))
            return False
        log.append((cid, what, before, after, reason, by))
        return True
    qpos = {q['id']: q for q in S['questions']}
    themes = {t['id']: t for t in S['themes']}
    # 1. study items: texts and tags; posed by; themes
    for name, res in R.items():
        if not name.startswith('STUDIES'):
            continue
        for k, r in res.items():
            for it in ('questions', 'conclusions', 'open_problems'):
                fld = 'q' if it == 'questions' else 'text'
                for i, x in enumerate(r.get(it, [])):
                    if x == 'ok':
                        continue
                    if str(x.get('text', '')).strip() and change(f'{k}.{it}.{i + 1}.text', f'{k} {LAB[it]} {i + 1}: text',
                                                                 D[k][it][i][fld], x['text'], x['reason']):
                        D[k][it][i][fld] = x['text']
                    if 'set' in x and x['set'] != M['tags'][k][it][i] and change(f'{k}.{it}.{i + 1}.tags', f'{k} {LAB[it]} {i + 1}: tags',
                                                                                 ', '.join(M['tags'][k][it][i]) or '–', ', '.join(x['set']) or '–', x['reason']):
                        M['tags'][k][it][i] = list(x['set'])
            for op in ('remove', 'add'):
                for q, why in (r.get('posed_by', {}).get(op) or {}).items():
                    inn = k in qpos[q]['posed_by']
                    if (op == 'add') != inn and change(f'{k}.posed_by.{op}.{q}', f'{q} posed by: {op} {k}', '', '', why):
                        qpos[q]['posed_by'] = [x for x in qpos[q]['posed_by'] if x != k] if op == 'remove' else qpos[q]['posed_by'] + [k]
                for t_, why in (r.get('themes', {}).get(op) or {}).items():
                    inn = k in themes[t_]['studies']
                    if (op == 'add') != inn and change(f'{k}.themes.{op}.{t_}', f'{t_} studies: {op} {k}', '', '', why):
                        themes[t_]['studies'] = [x for x in themes[t_]['studies'] if x != k] if op == 'remove' else themes[t_]['studies'] + [k]
    # 3. links
    ids = SQM.link_ids(M0)
    keep = []
    for lid, l in zip(ids, M['links']):
        l = copy.deepcopy(l)
        l['id'] = lid
        if lid[0] == 'L':
            v = R['LINKS-FW'][lid]
            to = []
            for j, (b, x) in enumerate(zip(l['to'], v), 1):
                if x != 'valid' and change(f'{lid}.{j}', f'{lid}: future work of {l["from"]["key"]} no longer matched to {b["key"]} {LAB[b["item"]]} {b["index"] + 1}',
                                           '', '', x['reason']):
                    continue
                to.append(b)
            l['to'] = to
            if not to:
                continue
        elif lid[0] == 'G':
            v = R['GROUPS'][lid]
            for k, x in v['members'].items():
                if x != 'ok' and change(f'{lid}.{k}', f'{lid} ({l["type"]}): remove {k}', '', '', x['reason']):
                    l['keys'] = [y for y in l['keys'] if y != k]
            if v.get('note') and change(f'{lid}.note', f'{lid}: note', l.get('note', ''), v['note']['text'], v['note']['reason']):
                l['note'] = v['note']['text']
            if len(l['keys']) < 2:
                log.append((f'{lid}.dropped', f'{lid}: fewer than two members left; dropped', '', '', 'rule', 'rule'))
                continue
        else:
            v = R['GROUPS'][lid]
            if v['verdict'] == 'not a contradiction' and change(lid, f'{lid}: not a contradiction ({l["a"]["key"]} / {l["b"]["key"]}); dropped',
                                                                 l.get('note', ''), '', v['reason']):
                continue
            if v.get('note') and change(f'{lid}.note', f'{lid}: note', l.get('note', ''), v['note']['text'], v['note']['reason']):
                l['note'] = v['note']['text']
        keep.append(l)
    M['links'] = keep
    # 3b. the orchestrator's item wordings, and stated questions the reading left out
    for e in dec.get('item_edits', []):
        fld = 'q' if e['item'] == 'questions' else 'text'
        log.append((f"{e['key']}.{e['item']}.{e['index'] + 1}.text", f"{e['key']} {LAB[e['item']]} {e['index'] + 1}: text (orchestrator)",
                    D[e['key']][e['item']][e['index']][fld], e['text'], e['reason'], 'orchestrator'))
        D[e['key']][e['item']][e['index']][fld] = e['text']
    for k, spec in dec.get('questions', {}).items():
        old_q, old_t, folder = D[k]['questions'], M['tags'][k]['questions'], SQM.ROOT / st[k]['folder']
        new_q, new_t, remap = [], [], {}
        for pos, ent in enumerate(spec['order']):
            if 'old' in ent:
                new_q.append(old_q[ent['old']]); new_t.append(old_t[ent['old']]); remap[ent['old']] = pos
                continue
            n = spec['new'][ent['new']]
            for e in n['evidence']:
                pf = folder / 'text' / 'pages' / f"page_{int(e['page']):04d}.txt"
                if e.get('source') not in ('image', 'table') and not CS.found(e['quote'], pf.read_text(encoding='utf-8', errors='ignore')):
                    sys.exit(f"{k}: added question's quotation not on p{e['page']}: {e['quote'][:70]!r}")
            new_q.append({'q': n['q'], 'explicit': True, 'evidence': n['evidence']}); new_t.append(list(n['tags']))
            log.append((f'{k}.questions.add.{pos + 1}', f'{k} question {pos + 1}: added, as stated in the paper (tags: {", ".join(n["tags"]) or "–"})',
                        '', n['q'], spec['reason'], 'orchestrator'))
        for i, q in enumerate(old_q):
            if i not in remap:
                log.append((f'{k}.questions.replaced.{i + 1}', f'{k} recorded question {i + 1}: replaced by the stated questions it summed up',
                            q['q'], '', spec['reason'], 'orchestrator'))
            elif remap[i] != i:
                log.append((f'{k}.questions.moved.{i + 1}', f'{k} question {i + 1} is now question {remap[i] + 1} (paper order)', '', '', spec['reason'], 'orchestrator'))
        D[k]['questions'], M['tags'][k]['questions'] = new_q, new_t
        for l in M['links']:
            if l['type'] == 'future work taken up':
                l['to'] = [({**b, 'index': remap[b['index']]} if b['key'] == k and b['item'] == 'questions' else b) for b in l['to']
                           if not (b['key'] == k and b['item'] == 'questions' and b['index'] not in remap)]
        M['links'] = [l for l in M['links'] if l['type'] != 'future work taken up' or l['to']]
    # 3c. rule: a question tagged Q means the study poses Q
    for k, tg in M['tags'].items():
        for lst in tg['questions']:
            for q in lst:
                if k not in qpos[q]['posed_by']:
                    log.append((f'{k}.posed_by.rule.{q}', f'{q} posed by: add {k}', '', '', f'one of {k}\'s questions carries {q}', 'rule'))
                    qpos[q]['posed_by'].append(k)
    for t_ in S['themes']:
        t_['n_primary'] = sum(SQM.KIND(st, k) == 'primary' for k in t_['studies'])
        t_['n_surveys'] = sum(SQM.KIND(st, k) == 'survey' for k in t_['studies'])
    # 4. tensions and prose
    ten = []
    for i, t_ in enumerate(S['tensions'], 1):
        v = R['GROUPS'][f'TN{i}']
        if v != 'ok' and v['verdict'] == 'drop' and change(f'TN{i}', f'tension {i}: dropped', t_['text'], '', v['reason']):
            continue
        if v != 'ok' and v['verdict'] == 'fix' and change(f'TN{i}', f'tension {i}: text', t_['text'], v['text'], v['reason']):
            t_['text'] = v['text']
        ten.append(t_)
    S['tensions'] = ten
    def setp(fid, text):
        if fid in ('number_of_questions_why', 'primary_vs_surveys'):
            S[fid] = text
        elif fid.startswith('SP'):
            S['singular_problems'][int(fid[2:]) - 1]['problem'] = text.split('] ', 1)[1] if text.startswith('[') else text
        elif fid[0] == 'O' and fid[1:].isdigit():
            S['open_questions'][int(fid[1:]) - 1]['question'] = text
        else:
            i, f = fid.split('.')
            (qpos.get(i) or themes[i])[f] = text
    for name in ('PROSE-A', 'PROSE-B'):
        for fid, v in R[name].items():
            if v != 'ok' and change(fid, f'{fid}: text', SQM.prose_text(S0, fid), v['text'], '; '.join(v['problems'])):
                setp(fid, v['text'])
    for e in dec.get('edits', []):
        log.append((e['field'], f"{e['field']}: text (orchestrator)", SQM.prose_text(S, e['field']), e['text'], e['reason'], 'orchestrator'))
        setp(e['field'], e['text'])
    # 5. rule: an open question's studies come from the future-work tags
    for i, o in enumerate(S['open_questions']):
        o['from'] = sorted({k for k, tg in M['tags'].items() for lst in tg['open_problems'] for x in lst if x == f'O{i + 1}'})
    # write
    if OUT.exists():
        shutil.rmtree(OUT)
    (OUT / 'studies').mkdir(parents=True)
    (OUT / 'SYNTHESIS.json').write_text(json.dumps(S, indent=1, ensure_ascii=False), encoding='utf-8')
    (OUT / 'MATCHES.json').write_text(json.dumps(M, indent=1, ensure_ascii=False), encoding='utf-8')
    for k, d in D.items():
        (OUT / 'studies' / f'{k}.json').write_text(json.dumps(d, indent=1, ensure_ascii=False), encoding='utf-8')
    by = {}
    for c in log:
        by[c[5]] = by.get(c[5], 0) + 1
    md = ['# Changes made by the independent check (7 October 2026)\n\n',
          f'{len(log)} changes applied ({", ".join(f"{n} by {b}" for b, n in sorted(by.items()))}); {len(rejected)} proposed changes '
          'rejected. Originals: `../SYNTHESIS.json`, `../MATCHES.json`, `../studies/`; corrected copies: `verified/`.\n\n',
          '## Applied\n\n']
    oc = VER / 'results' / 'ORCHESTRATOR.json'
    if oc.exists():
        O = json.loads(oc.read_text(encoding='utf-8'))
        nfix = sum(1 for v in O.values() if v != 'ok')
        md.insert(2, f'The orchestrating run\'s own changes and its section-5 note were checked by a further run (`results/ORCHESTRATOR.json`): '
                     f'{len(O) - nfix} confirmed, {nfix} corrected as that run proposed (DECISIONS.json).\n\n')
    for cid, what, b, a, reason, who in log:
        md.append(f'- **{cid}** ({who}) {what}' + (f'\n  - before: {b}\n  - after: {a}' if (b or a) else '') + f'\n  - reason: {reason}\n')
    md.append('\n## Rejected\n\n' + ''.join(f'- **{cid}** {what}\n  - proposed because: {reason}\n  - rejected: {why}\n' for cid, what, why, reason in rejected))
    (VER / 'CHANGES.md').write_text(''.join(md), encoding='utf-8')
    (VER / 'CHANGES.json').write_text(json.dumps({'applied': [dict(zip(('id', 'what', 'before', 'after', 'reason', 'by'), c)) for c in log],
                                                  'rejected': [dict(zip(('id', 'what', 'rejected_because', 'proposed_because'), c)) for c in rejected]},
                                                 indent=1, ensure_ascii=False), encoding='utf-8')
    print(f'{len(log)} changes applied ({by}); {len(rejected)} rejected; verified copies in {OUT}')
    for q in S['questions']:
        print(f"  {q['id']}: posed by {len(q['posed_by'])} ({sum(SQM.KIND(st, k) == 'primary' for k in q['posed_by'])} P, "
              f"{sum(SQM.KIND(st, k) == 'survey' for k in q['posed_by'])} S) — was {len(next(x for x in S0['questions'] if x['id'] == q['id'])['posed_by'])}")


if __name__ == '__main__':
    main()
