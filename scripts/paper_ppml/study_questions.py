#!/usr/bin/env python3
"""What are the included studies trying to answer? Bottom-up reading (7 October 2026).

The author asked to "take all the primary and secondary studies that we have and formulate new questions. from scratch … tell
me what are the questions/problems they have been trying to answer", without relating them to the PhD proposal or the review's
framing. Readers record each study's problem, claimed gap, questions and open problems in its own words, with page quotations
(search-ppml/evidence/study-questions/READING-GUIDE.md, one file per study in studies/<key>.json); a synthesis then groups them.

check [key …]   every file has the fields; every quotation is found on the page it names (as check_sheets.py finds them)
match-check     MATCHES.json: every study and item tagged, every link pointing at an existing item
verify-packets  verify/packets/*.md for the independent checkers (verify/VERIFY-GUIDE.md)
verify-check    verify/results/*.json complete and well formed; then study_questions_apply.py writes verify/verified/
report          Docs/PPML-STUDY-QUESTIONS-FROM-SCRATCH-<date>.html from the verified copies (printable; every study key and
                quotation of the synthesis is checked against the study files first)

Usage: python3 scripts/paper_ppml/study_questions.py check [key …]
       python3 scripts/paper_ppml/study_questions.py report
"""
import json, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
SQ = ROOT / 'search-ppml' / 'evidence' / 'study-questions'
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import check_sheets as CS                                          # noqa: E402


def quotes(d):
    for part in ('problem', 'gap'):
        for e in (d.get(part) or {}).get('evidence', []) or []:
            yield part, e
    for i, q in enumerate(d.get('questions', []) or []):
        for e in q.get('evidence', []) or []:
            yield f'question {i + 1}', e
    for i, o in enumerate(d.get('open_problems', []) or []):
        for e in o.get('evidence', []) or []:
            yield f'open problem {i + 1}', e
    for i, c in enumerate(d.get('conclusions', []) or []):
        for e in c.get('evidence', []) or []:
            yield f'conclusion {i + 1}', e


def check(keys=None, base=None, quiet=False):
    """base: the folder of study files (default studies/; verify/verified/studies for the corrected copies)"""
    studies = {s['key']: s for s in json.loads((SQ / 'STUDIES.json').read_text(encoding='utf-8'))}
    base = base or SQ / 'studies'
    files = [base / f'{k}.json' for k in keys] if keys else sorted(base.glob('*.json'))
    bad = 0
    for f in files:
        k = f.stem
        if not f.exists():
            print(f'{k}: no file yet')
            continue
        probs = []
        try:
            d = json.loads(f.read_text(encoding='utf-8'))
        except Exception as ex:                                   # noqa: BLE001
            print(f'{k}: FAIL not readable JSON: {ex}')
            bad += 1
            continue
        for fld in ('kind', 'domain', 'problem', 'gap', 'questions', 'answer', 'open_problems', 'keywords'):
            if not d.get(fld):
                probs.append(f'{fld} missing or empty')
        qs = d.get('questions') or []
        if not qs or sum(not q.get('explicit') for q in qs) > 4 or (len(qs) > 4 and sum(not q.get('explicit') for q in qs) == len(qs)):
            probs.append('one to four questions, plus any further questions the paper states')
        if 'conclusions' in d and not 1 <= len(d.get('conclusions') or []) <= 4:
            probs.append('one to four conclusions')
        for c in d.get('conclusions', []) or []:
            if not c.get('evidence'):
                probs.append(f"conclusion without evidence: {c.get('text', '')[:60]!r}")
        for q in d.get('questions', []) or []:
            if not q.get('evidence'):
                probs.append(f"question without evidence: {q.get('q', '')[:60]!r}")
        folder = ROOT / studies[k]['folder']
        n = 0
        for where, e in quotes(d):
            if e.get('source') in ('image', 'table'):
                continue
            n += 1
            pf = folder / 'text' / 'pages' / f"page_{int(e.get('page', 0)):04d}.txt"
            if not pf.exists():
                probs.append(f"{where}: page {e.get('page')} does not exist")
            elif not CS.found(e.get('quote', ''), pf.read_text(encoding='utf-8', errors='ignore')):
                probs.append(f"{where}: quotation not on p{e.get('page')}: {e.get('quote', '')[:70]!r}")
        bad += bool(probs)
        if not quiet or probs:
            print(f"{k}: {'PASS' if not probs else 'FAIL'} ({n} quotations checked)")
            for p_ in probs[:15]:
                print('   ', p_)
    return bad


def match_check():
    """MATCHES.json (MATCH-GUIDE.md): every study and item tagged, tags known, every link pointing at an existing item"""
    S = json.loads((SQ / 'SYNTHESIS.json').read_text(encoding='utf-8'))
    M = json.loads((SQ / 'MATCHES.json').read_text(encoding='utf-8'))
    D = {f.stem: json.loads(f.read_text(encoding='utf-8')) for f in (SQ / 'studies').glob('*.json')}
    known = {q['id'] for q in S.get('questions', [])} | {f'O{i + 1}' for i in range(len(S.get('open_questions', [])))}
    probs = []
    for k, d in D.items():
        tg = M.get('tags', {}).get(k)
        if not tg:
            probs.append(f'{k}: no tags')
            continue
        for item in ('questions', 'conclusions', 'open_problems'):
            n = len(d.get(item) or [])
            if len(tg.get(item, [])) != n:
                probs.append(f'{k} {item}: {len(tg.get(item, []))} tag lists for {n} items')
            for lst in tg.get(item, []):
                for x in lst:
                    if x not in known:
                        probs.append(f'{k} {item}: unknown tag {x}')
    def ok(ref):
        d = D.get(ref.get('key'))
        return d is not None and 0 <= int(ref.get('index', -1)) < len(d.get(ref.get('item'), []) or [])
    for i, l in enumerate(M.get('links', [])):
        refs = [l[x] for x in ('from', 'a', 'b') if x in l] + list(l.get('to', []))
        for r in refs:
            if not ok(r):
                probs.append(f"link {i} ({l.get('type')}): no such item {r}")
        for k in l.get('keys', []):
            if k not in D:
                probs.append(f"link {i}: unknown study {k}")
    print(f"{len(M.get('tags', {}))} studies tagged, {len(M.get('links', []))} links; {len(probs)} problem(s)")
    for p_ in probs[:30]:
        print('   ', p_)
    return len(probs)


VER = SQ / 'verify'
KIND = lambda st, k: 'survey' if 'survey' in st[k]['kind'] else 'primary'


def load_all():
    S = json.loads((SQ / 'SYNTHESIS.json').read_text(encoding='utf-8'))
    M = json.loads((SQ / 'MATCHES.json').read_text(encoding='utf-8'))
    D = {f.stem: json.loads(f.read_text(encoding='utf-8')) for f in sorted((SQ / 'studies').glob('*.json'))}
    st = {s['key']: s for s in json.loads((SQ / 'STUDIES.json').read_text(encoding='utf-8'))}
    return S, M, D, st


def link_ids(M):
    """stable ids for the links of MATCHES.json, by type in list order: L001 future work, GQ001 same question, GC001 same
    conclusion, C001 contradicting conclusions"""
    pre = {'future work taken up': 'L', 'same question': 'GQ', 'same conclusion': 'GC', 'contradicting conclusions': 'C'}
    n, ids = {}, []
    for l in M['links']:
        n[l['type']] = n.get(l['type'], 0) + 1
        ids.append(f"{pre[l['type']]}{n[l['type']]:03d}")
    return ids


PROSE_A = lambda S: ([f"{q['id']}.{f}" for q in S['questions'] for f in ('status', 'answers', 'why')]
                     + ['number_of_questions_why', 'primary_vs_surveys'])
PROSE_B = lambda S: ([f"{t['id']}.{f}" for t in S['themes'] for f in ('name', 'problem')]
                     + [f'SP{i + 1}' for i in range(len(S['singular_problems']))] + [f'O{i + 1}' for i in range(len(S['open_questions']))])


def prose_text(S, fid):
    if fid in ('number_of_questions_why', 'primary_vs_surveys'):
        return S[fid]
    if fid.startswith('SP'):
        sp = S['singular_problems'][int(fid[2:]) - 1]
        return f"[{sp['key']}] {sp['problem']}"
    if fid[0] == 'O' and fid[1:].isdigit():
        return S['open_questions'][int(fid[1:]) - 1]['question']
    i, f = fid.split('.')
    pool = S['questions'] if i[0] == 'Q' else S['themes']
    return next(x for x in pool if x['id'] == i)[f]


def verify_packets():
    """verify/packets/*.md: every item text and tag, posed-by and theme membership (STUDIES-1..4), every future-work link (LINKS-FW), every
    group, contradiction and tension (GROUPS), and the synthesis prose (PROSE-A, PROSE-B), in full text for the checkers"""
    S, M, D, st = load_all()
    (VER / 'packets').mkdir(parents=True, exist_ok=True)
    (VER / 'results').mkdir(parents=True, exist_ok=True)
    defs = ('## Definitions\n\n' + ''.join(f"- **{q['id']}** {q['question']}\n" for q in S['questions'])
            + ''.join(f"- **O{i + 1}** {o['question']}\n" for i, o in enumerate(S['open_questions']))
            + ''.join(f"- **{t['id']}** {t['name']}: {t['problem']}\n" for t in S['themes']) + '\n')
    who = lambda k: f"{k} ({KIND(st, k)}, {st[k]['year']})"
    item = lambda k, it, i: (D[k][it][i].get('q') if it == 'questions' else D[k][it][i].get('text'))
    lab = {'questions': 'question', 'conclusions': 'conclusion', 'open_problems': 'future work'}
    keys = sorted(D, key=lambda k: (KIND(st, k), k))
    parts = [keys[i::4] for i in range(4)]
    for n, part in enumerate(parts, 1):
        out = [f'# Study packet {n}: item texts, tags, posed-by and themes of {len(part)} studies\n\n', defs]
        for k in part:
            d, tg = D[k], M['tags'][k]
            out.append(f"## {who(k)} — {st[k]['title']}\n\nDomain: {d.get('domain', '')}\n\nProblem: {d['problem']['text']}\n\n"
                       f"Gap: {d['gap']['text']}\n\nPosed by (synthesis): {', '.join(q['id'] for q in S['questions'] if k in q['posed_by']) or '–'}\n\n"
                       f"Themes (synthesis): {', '.join(t['id'] for t in S['themes'] if k in t['studies']) or '–'}\n\n")
            for it, p in (('questions', 'q'), ('conclusions', 'c'), ('open_problems', 'f')):
                out.append(f"{lab[it].capitalize()}s:\n")
                for i in range(len(d.get(it) or [])):
                    st_ = ' (stated)' if it == 'questions' and d[it][i].get('explicit') else ''
                    ev = '; '.join(f"p{e['page']}: \"{e['quote']}\"" for e in d[it][i].get('evidence', []))
                    out.append(f"- {p}{i + 1} [{', '.join(tg[it][i]) if i < len(tg[it]) else '?'}]{st_} {item(k, it, i)}\n    evidence: {ev}\n")
                out.append('\n')
        (VER / 'packets' / f'STUDIES-{n}.md').write_text(''.join(out), encoding='utf-8')
    ids = link_ids(M)
    fw, gr = ['# Future-work links\n\n', defs], ['# Groups, contradictions and tensions\n\n', defs]
    for lid, l in zip(ids, M['links']):
        if lid[0] == 'L':
            a = l['from']
            fw.append(f"### {lid} — note: {l.get('note', '')}\n\nFROM {who(a['key'])}, future work f{a['index'] + 1}: {item(a['key'], a['item'], a['index'])}\n\n")
            for j, b in enumerate(l['to'], 1):
                fw.append(f"- {lid}.{j} → {who(b['key'])}, {lab[b['item']]} {b['item'][0]}{b['index'] + 1}: {item(b['key'], b['item'], b['index'])}\n")
            fw.append('\n')
        elif lid[0] == 'G':
            it = 'questions' if lid[1] == 'Q' else 'conclusions'
            gr.append(f"### {lid} — {l['type']}, tag {l.get('tag')} — note: {l.get('note', '')}\n\n")
            for k in l['keys']:
                idx = [i for i, t_ in enumerate(M['tags'][k][it]) if l.get('tag') in t_] or list(range(len(D[k][it])))
                for i in idx:
                    gr.append(f"- {who(k)} {it[0]}{i + 1} [{', '.join(M['tags'][k][it][i])}]: {item(k, it, i)}\n")
            gr.append('\n')
        else:
            gr.append(f"### {lid} — contradicting conclusions — note: {l.get('note', '')}\n\n")
            for side in ('a', 'b'):
                r = l[side]
                ev = '; '.join(f"p{e['page']}: \"{e['quote']}\"" for e in D[r['key']][r['item']][r['index']].get('evidence', []))
                gr.append(f"- {side.upper()}: {who(r['key'])} conclusion c{r['index'] + 1}: {item(r['key'], r['item'], r['index'])}\n  evidence: {ev}\n")
            gr.append('\n')
    for i, t_ in enumerate(S['tensions'], 1):
        gr.append(f"### TN{i} — tension (synthesis)\n\n{t_['text']}\n\n" + ''.join(f"- {x['key']} p{x['page']}: \"{x['quote']}\"\n" for x in t_['quotes']) + '\n')
    (VER / 'packets' / 'LINKS-FW.md').write_text(''.join(fw), encoding='utf-8')
    (VER / 'packets' / 'GROUPS.md').write_text(''.join(gr), encoding='utf-8')
    for name, fids in (('PROSE-A', PROSE_A(S)), ('PROSE-B', PROSE_B(S))):
        out = [f'# Synthesis prose to check ({name})\n\n', defs]
        for fid in fids:
            extra = ''
            if fid[0] == 'Q' and '.' in fid:
                q = next(x for x in S['questions'] if x['id'] == fid.split('.')[0])
                extra = f"  (posed by {len(q['posed_by'])}: {', '.join(q['posed_by'])})"
            if fid[0] == 'O' and fid[1:].isdigit():
                ks = sorted({k for k, tg in M['tags'].items() for lst in tg['open_problems'] for x in lst if x == fid})
                extra = f"  (future-work items tagged {fid} in: {', '.join(ks)})"
            out.append(f"### {fid}{extra}\n\n{prose_text(S, fid)}\n\n")
        (VER / 'packets' / f'{name}.md').write_text(''.join(out), encoding='utf-8')
    (VER / 'packets' / 'PARTS.json').write_text(json.dumps({f'STUDIES-{n}': p for n, p in enumerate(parts, 1)}, indent=1), encoding='utf-8')
    print('packets written:', ', '.join(sorted(f.name for f in (VER / 'packets').glob('*.md'))))


def verify_check(names=None):
    """verify/results/<packet>.json complete and well formed (VERIFY-GUIDE.md)"""
    S, M, D, st = load_all()
    parts = json.loads((VER / 'packets' / 'PARTS.json').read_text(encoding='utf-8'))
    ids = link_ids(M)
    known = {q['id'] for q in S['questions']} | {f'O{i + 1}' for i in range(len(S['open_questions']))}
    tids = {t['id'] for t in S['themes']}
    probs = []
    def why(x, where):
        if not (isinstance(x, dict) and str(x.get('reason', '')).strip()):
            probs.append(f'{where}: a change needs a reason')
    for name in names or [*parts, 'LINKS-FW', 'GROUPS', 'PROSE-A', 'PROSE-B']:
        f = VER / 'results' / f'{name}.json'
        if not f.exists():
            probs.append(f'{name}: no results yet')
            continue
        R = json.loads(f.read_text(encoding='utf-8'))
        if name.startswith('STUDIES'):
            for k in parts[name]:
                r = R.get(k)
                if not r:
                    probs.append(f'{name} {k}: missing')
                    continue
                for it in ('questions', 'conclusions', 'open_problems'):
                    v = r.get(it, [])
                    if len(v) != len(D[k].get(it) or []):
                        probs.append(f'{name} {k} {it}: {len(v)} verdicts for {len(D[k].get(it) or [])} items')
                    for i, x in enumerate(v):
                        if x != 'ok':
                            why(x, f'{k} {it} {i + 1}')
                            bad = [t_ for t_ in (x.get('set') if isinstance(x, dict) else None) or [] if t_ not in known]
                            if not isinstance(x, dict) or not ('set' in x or str(x.get('text', '')).strip()) or bad:
                                probs.append(f'{k} {it} {i + 1}: needs "ok" or {{"set": [...] and/or "text": ..., "reason": ...}} with known ids {bad}')
                for fld, pool in (('posed_by', {q['id'] for q in S['questions']}), ('themes', tids)):
                    for op in ('remove', 'add'):
                        for x, rs in (r.get(fld, {}).get(op) or {}).items():
                            if x not in pool or not str(rs).strip():
                                probs.append(f'{k} {fld} {op} {x}: unknown id or no reason')
        elif name == 'LINKS-FW':
            for lid, l in zip(ids, M['links']):
                if lid[0] != 'L':
                    continue
                v = R.get(lid)
                if not isinstance(v, list) or len(v) != len(l['to']):
                    probs.append(f'{lid}: one verdict per target needed ({len(l["to"])})')
                    continue
                for j, x in enumerate(v, 1):
                    if x != 'valid' and not (isinstance(x, dict) and x.get('verdict') == 'invalid' and str(x.get('reason', '')).strip()):
                        probs.append(f'{lid}.{j}: "valid" or {{"verdict": "invalid", "reason": ...}}')
        elif name == 'GROUPS':
            for lid, l in zip(ids, M['links']):
                if lid[0] == 'G':
                    v = R.get(lid, {})
                    if set(v.get('members', {})) != set(l['keys']):
                        probs.append(f'{lid}: a verdict for every member needed')
                    for k, x in v.get('members', {}).items():
                        if x != 'ok' and not (isinstance(x, dict) and x.get('verdict') == 'remove' and str(x.get('reason', '')).strip()):
                            probs.append(f'{lid} {k}: "ok" or {{"verdict": "remove", "reason": ...}}')
                elif lid[0] == 'C':
                    v = R.get(lid, {})
                    if v.get('verdict') not in ('contradiction', 'not a contradiction') or not str(v.get('reason', '')).strip():
                        probs.append(f'{lid}: verdict "contradiction" or "not a contradiction", with a reason')
            for i in range(len(S['tensions'])):
                v = R.get(f'TN{i + 1}')
                if not (v == 'ok' or (isinstance(v, dict) and v.get('verdict') in ('fix', 'drop') and str(v.get('reason', '')).strip()
                                      and (v['verdict'] == 'drop' or str(v.get('text', '')).strip()))):
                    probs.append(f'TN{i + 1}: "ok" or {{"verdict": "fix"|"drop", "text": ..., "reason": ...}}')
        elif name == 'ORCHESTRATOR':
            CH = json.loads((VER / 'CHANGES.json').read_text(encoding='utf-8'))
            for cid in [c['id'] for c in CH['applied'] if c['by'] in ('orchestrator', 'rule')] + ['section5']:
                v = R.get(cid)
                if not (v == 'ok' or (isinstance(v, dict) and v.get('verdict') == 'fix' and str(v.get('problem', '')).strip()
                                      and str(v.get('proposal', '')).strip())):
                    probs.append(f'{cid}: "ok" or {{"verdict": "fix", "problem": ..., "proposal": ...}}')
        else:
            for fid in (PROSE_A(S) if name == 'PROSE-A' else PROSE_B(S)):
                v = R.get(fid)
                if not (v == 'ok' or (isinstance(v, dict) and v.get('verdict') == 'fix' and str(v.get('text', '')).strip()
                                      and v.get('problems'))):
                    probs.append(f'{fid}: "ok" or {{"verdict": "fix", "problems": [...], "text": ...}}')
    print(f'{len(probs)} problem(s)')
    for p_ in probs[:40]:
        print('   ', p_)
    return len(probs)


NUM = dict(enumerate(['no', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten']))
PALETTE = ['#1f5f99', '#a13d2d', '#2e7d4f', '#7a4b9c', '#b26a00', '#00727d', '#8a3567', '#5b6b00', '#3d4f8a', '#8c5a2b', '#006b5c',
           '#99324f', '#4f5f2f']


def big_table(S, D, M, studies, kind, added=()):
    """the author's table: every study, its questions, conclusions and future work, each item tagged with the question of the
    field it matches, and the study's matches with other studies (verify/verified/MATCHES.json)"""
    import html
    e = html.escape
    qids = [q['id'] for q in S.get('questions', [])]
    oids = [f'O{i + 1}' for i in range(len(S.get('open_questions', [])))]
    col = {q: PALETTE[i % len(PALETTE)] for i, q in enumerate(qids)}
    col.update({o: '#555555' for o in oids})
    chip = lambda x: f"<span class='chip' style='border-color:{col.get(x, '#555')};color:{col.get(x, '#555')}'>{e(x)}</span>"
    legend = ('<table class="legend"><tbody>' + ''.join(f"<tr><td>{chip(q['id'])}</td><td>{e(q['question'])}</td></tr>" for q in S.get('questions', []))
              + ''.join(f"<tr><td>{chip(o)}</td><td>{e(oq['question'])}</td></tr>" for o, oq in zip(oids, S.get('open_questions', []))) + '</tbody></table>')
    yr = lambda k: int(studies[k]['year'])
    when = lambda a, b: 'same year' if yr(b) == yr(a) else ('later' if yr(b) > yr(a) else 'earlier')
    order = lambda refs: sorted({(r['key'], r['index']): r for r in refs}.values(), key=lambda r: (yr(r['key']), r['key'], r['index']))
    src, tgt, rel = {k: {} for k in D}, {k: {} for k in D}, {k: [] for k in D}
    for l in M.get('links', []):
        ty = l.get('type', '')
        if ty == 'future work taken up':
            a = l['from']
            for b in l.get('to', []):
                src[a['key']].setdefault(a['index'], []).append(b)
                tgt[b['key']].setdefault(b['index'], []).append(a)
        elif ty in ('same question', 'same conclusion'):
            for k in l.get('keys', []):
                others = [x for x in l.get('keys', []) if x != k]
                rel[k].append(f"<b>{e(ty)}</b> {chip(l['tag']) if l.get('tag') else ''} “{e(l.get('note', ''))}”: {e(', '.join(others))}")
        elif ty == 'contradicting conclusions':
            a, b = l['a'], l['b']
            rel[a['key']].append(f"<b>c{a['index'] + 1} contradicts</b> {e(b['key'])} c{b['index'] + 1}: {e(l.get('note', ''))}")
            rel[b['key']].append(f"<b>c{b['index'] + 1} contradicts</b> {e(a['key'])} c{a['index'] + 1}: {e(l.get('note', ''))}")
    for k in D:
        fw = [f"<b>f{i + 1}</b> → asked by " + '; '.join(f"{e(b['key'])} q{b['index'] + 1} ({studies[b['key']]['year']}, {when(k, b['key'])})"
                                                        for b in order(bs)) for i, bs in sorted(src[k].items())]
        qs = [f"<b>q{j + 1}</b> ← future work of " + '; '.join(f"{e(a['key'])} f{a['index'] + 1} ({studies[a['key']]['year']})" for a in order(as_))
              for j, as_ in sorted(tgt[k].items())]
        rel[k] = fw + qs + rel[k]
    def cell(k, item, textkey, p):
        tags = M.get('tags', {}).get(k, {}).get(item, [])
        out = []
        for i, x in enumerate(D[k].get(item) or []):
            txt = x.get(textkey, '') if isinstance(x, dict) else str(x)
            if item == 'open_problems' and txt.startswith('None stated'):
                out.append('<i>none stated</i>')
                continue
            st = '<b>[stated]</b> ' if item == 'questions' and x.get('explicit') else ''
            ch = ''.join(chip(t_) for t_ in (tags[i] if i < len(tags) else []))
            out.append(f"<b>{p}{i + 1}</b> {ch} {st}{e(txt)}")
        return '<br>'.join(out)
    rows = ''
    for kd, label in (('P', 'Primary studies'), ('S', 'Secondary studies (surveys)')):
        rows += f"<tr class='grp'><td colspan='5'>{label}</td></tr>"
        for k in sorted((k for k in D if kind(k) == kd), key=lambda k: (studies[k]['year'], k)):
            rows += (f"<tr><td><b>{e(k)}</b><br>{e(studies[k]['year'])}<br><span class='k'>{e(D[k].get('domain', ''))}</span></td>"
                     f"<td>{cell(k, 'questions', 'q', 'q')}</td><td>{cell(k, 'conclusions', 'text', 'c')}</td><td>{cell(k, 'open_problems', 'text', 'f')}</td>"
                     f"<td class='k'>{'<br>'.join(rel.get(k, [])) or '–'}</td></tr>")
    return (f"<h2>6. Every study: its questions, conclusions and future work, with the matches marked</h2>"
            f"<p>Items are numbered q (question), c (conclusion) and f (future work). Each carries the tag of the question of the field it "
            f"asks, answers or points to: Q1–Q{len(qids)} (section 1) and O1–O{len(oids)}, the questions the studies leave open (section 4). The same "
            f"tag on two studies means they meet on that question. The last column gives each study's direct matches:</p><ul class='small'>"
            f"<li><b>f2 → asked by</b>: studies whose question addresses this study's future work f2, with their year and whether they came "
            f"<i>earlier</i>, in the <i>same year</i> or <i>later</i> (earlier: the question had already been asked when this study named the "
            f"problem as open);</li><li><b>q1 ← future work of</b>: this study's question q1 addresses future work named by the studies listed;</li>"
            f"<li><b>same question</b>, <b>same conclusion</b>: the studies listed ask or conclude essentially the same, as the words in quotation "
            f"marks say.</li>" + ("<li><b>contradicts</b>: two conclusions that cannot both hold.</li>" if any(l.get('type') == 'contradicting conclusions'
            for l in M.get('links', [])) else '') + f"</ul><p class='small'>[stated] = the question in the paper's own words; the other questions are "
            f"formulated from the study's stated aims and contributions. Where a survey states more research questions than its reading first "
            f"recorded, all of them are listed, in the paper's order{(' (' + ', '.join(added) + ')') if added else ''}.</p>{legend}"
            f"<table class='big'><thead><tr><th>Study</th><th>Questions</th><th>Conclusions</th><th>Future work</th><th>Matches</th></tr></thead>"
            f"<tbody>{rows}</tbody></table>")


def report(preview=None):
    """preview: a path outside Docs/ to look at the page before the deliverable is written"""
    import datetime, html, re, unicodedata
    e = html.escape
    out = pathlib.Path(preview) if preview else ROOT / 'Docs' / f'PPML-STUDY-QUESTIONS-FROM-SCRATCH-{datetime.date.today().isoformat()}.html'
    if out.exists() and not preview:
        sys.exit(f'{out.name} exists; documents are never overwritten')
    V = VER / 'verified'
    if not (V / 'SYNTHESIS.json').exists():
        sys.exit('no verified copies yet (run study_questions_apply.py after the check); no report written')
    S0, M0, D0, studies = load_all()
    S = json.loads((V / 'SYNTHESIS.json').read_text(encoding='utf-8'))
    M = json.loads((V / 'MATCHES.json').read_text(encoding='utf-8'))
    D = {f.stem: json.loads(f.read_text(encoding='utf-8')) for f in sorted((V / 'studies').glob('*.json'))}
    CH = json.loads((VER / 'CHANGES.json').read_text(encoding='utf-8'))
    nchg = len(CH['applied'])
    ndrop = sum(1 for c in CH['applied'] if c['id'][:1] == 'C' and c['id'][1:].isdigit() and 'not a contradiction' in c['what'])
    added = sorted({c['id'].split('.')[0] for c in CH['applied'] if '.questions.add.' in c['id']})
    note5 = json.loads((VER / 'DECISIONS.json').read_text(encoding='utf-8')).get('report_notes', {}).get('section5', '')
    if ndrop and not note5:
        sys.exit('contradictions were dropped but DECISIONS.json gives no section-5 note saying why; no report written')
    norm = lambda s: re.sub(r'\s+', ' ', unicodedata.normalize('NFKC', s or '')).strip().lower()
    blob = {k: norm(json.dumps(d, ensure_ascii=False)) for k, d in D.items()}
    probs = []
    if set(D) != set(D0):
        probs.append('the verified studies are not the 67 studies')
    if check(base=V / 'studies', quiet=True):                    # every quotation of the corrected copies found on its page
        probs.append('the corrected study copies fail the quotation check')
    def chk_keys(ks, where):
        for k in ks:
            if k not in D:
                probs.append(f'{where}: unknown study {k}')
    def chk_quotes(qs, where):
        for q in qs:
            if q.get('key') not in D or norm(q.get('quote', '')) not in blob[q['key']]:
                probs.append(f"{where}: quotation not in {q.get('key')}'s file: {q.get('quote', '')[:60]!r}")
    for th in S.get('themes', []):
        chk_keys(th.get('studies', []), th.get('id')); chk_quotes(th.get('quotes', []), th.get('id'))
    for q in S.get('questions', []):
        chk_keys(q.get('posed_by', []), q.get('id'))
    for t_ in S.get('tensions', []):
        chk_quotes(t_.get('quotes', []), 'tension')
    for o in S.get('open_questions', []):
        chk_keys(o.get('from', []), 'open question')
    if probs:
        print('\n'.join(probs[:30]))
        sys.exit(f'{len(probs)} problem(s) in the verified copies; no report written')
    kind = lambda k: 'S' if 'survey' in studies[k]['kind'] else 'P'
    tag = lambda ks: ', '.join(sorted(ks, key=lambda k: (kind(k), k)))
    qrows = ''.join(f"<tr><td class='nw'>{e(q['id'])}</td><td><b>{e(q['question'])}</b></td><td>{len(q.get('posed_by', []))} "
                    f"({sum(kind(k) == 'P' for k in q.get('posed_by', []))} P, {sum(kind(k) == 'S' for k in q.get('posed_by', []))} S)"
                    f"<br><span class='k'>{e(tag(q.get('posed_by', [])))}</span></td>"
                    f"<td class='nw'>{e(q.get('status', ''))}</td><td>{e(q.get('answers', ''))}<br><i>{e(q.get('why', ''))}</i></td></tr>"
                    for q in S.get('questions', []))
    trows = ''.join(f"<tr><td class='nw'>{e(th['id'])}</td><td><b>{e(th['name'])}</b><br>{e(th.get('problem', ''))}</td>"
                    f"<td>{th.get('n_primary', 0)} P, {th.get('n_surveys', 0)} S<br><span class='k'>{e(tag(th.get('studies', [])))}</span></td>"
                    f"<td>{'<br>'.join(e(chr(8220) + x['quote'] + chr(8221) + ' (' + x['key'] + ', p' + str(x['page']) + ')') for x in th.get('quotes', [])[:3])}</td></tr>"
                    for th in S.get('themes', []))
    orows = ''.join(f"<li><b>O{i + 1}</b> {e(o['question'])} <span class='k'>({len(o.get('from', []))}: {e(tag(o.get('from', [])))})</span></li>"
                    for i, o in enumerate(S.get('open_questions', [])))
    tens = ''.join(f"<li>{e(t_['text'])}<br>{'<br>'.join(e(chr(8220) + x['quote'] + chr(8221) + ' (' + x['key'] + ', p' + str(x['page']) + ')') for x in t_.get('quotes', []))}</li>"
                   for t_ in S.get('tensions', []))
    cons = [l for l in M.get('links', []) if l.get('type') == 'contradicting conclusions']
    crows = ''.join(f"<li><b>{e(l['a']['key'])} c{l['a']['index'] + 1}</b> and <b>{e(l['b']['key'])} c{l['b']['index'] + 1}</b>: {e(l.get('note', ''))}</li>"
                    for l in cons)
    nq = sum(len(d['questions']) for d in D.values()); nx = sum(1 for d in D.values() for q in d['questions'] if q.get('explicit'))
    npri = sum(kind(k) == 'P' for k in D); nsur = len(D) - npri
    css = ('body{font:14px/1.5 Georgia,serif;background:#fff;color:#111;margin:24px;max-width:1200px}h1{font-size:23px}h2{font-size:18px;margin-top:28px}'
           'table{border-collapse:collapse;width:100%;margin:8px 0}td,th{border:1px solid #bbb;padding:4px 7px;vertical-align:top;overflow-wrap:break-word}.nw{white-space:nowrap}'
           'th{background:#eef2f6;text-align:left}.k{font-size:11px;color:#444}.small{font-size:12px;color:#333}'
           '.chip{display:inline-block;border:1.5px solid;border-radius:3px;padding:0 3px;font:bold 10px/1.4 Arial,sans-serif;margin-right:2px}'
           'table.big td{font-size:12px}tr.grp td{background:#156082;color:#fff;font-weight:bold}table.legend td{border:none;padding:1px 6px}'
           '@media print{@page{size:auto;margin:14mm}body{margin:0;max-width:none;font-size:11px}thead{display:table-header-group}'
           'tr,li{break-inside:avoid}h2{break-after:avoid}th{background:#fff;border-bottom:2px solid #000}'
           'tr.grp td{background:#fff;color:#000;border-top:2px solid #000}table.big{break-before:page}}')
    body = (f"<h1>What are the {len(D)} studies trying to answer? Questions formulated from scratch</h1>"
            f"<p class='small'>7 October 2026. All {len(D)} studies included in the review ({npri} primary studies, {nsur} surveys) were read from their "
            f"full texts by separate Claude runs, each instructed to use only the paper, not the review, its records, its survey questions or the "
            f"PhD proposal. For each study they recorded, in the authors' terms and with page quotations (every quotation found on its page by a "
            f"script), the problem it addresses, the gap it claims, the questions it tries to answer ({nq} in all, {nx} stated as questions by the "
            f"papers themselves), its conclusions and the problems it leaves open. A further run, under the same instruction, grouped them "
            f"bottom-up into the questions below and tagged and matched every item. Eight further runs then checked every item's wording "
            f"against its quotations, and every tag, match and statement of the synthesis against the study records and pages, and a ninth "
            f"checked the corrections made outside those runs; {nchg} corrections were made in all "
            f"(search-ppml/evidence/study-questions/verify/CHANGES.md). P = primary study, S = survey.</p>"
            f"<h2>1. The questions this literature is trying to answer</h2><p>{e(S.get('number_of_questions_why', ''))}</p>"
            f"<p class='small'>Posed by: the studies whose problem, gap or questions raise the question, explicitly or implicitly. The table in "
            f"section 6 tags single questions, conclusions and future-work items.</p>"
            f"<table><thead><tr><th></th><th>Question</th><th>Posed by</th><th>Status</th><th>What the studies give, and why that status</th></tr></thead><tbody>{qrows}</tbody></table>"
            f"<h2>2. Primary studies and surveys</h2><p>{e(S.get('primary_vs_surveys', ''))}</p>"
            f"<h2>3. The problem themes behind them</h2><table><thead><tr><th></th><th>Theme</th><th>Studies</th><th>In the studies' words</th></tr></thead><tbody>{trows}</tbody></table>"
            f"<h2>4. What the studies leave open</h2><p class='small'>Each open question gathers the future-work items tagged with it; the "
            f"studies are listed after it.</p><ul>{orows}</ul>"
            f"<h2>5. Tensions between studies</h2><p class='small'>Statements by different studies that pull in different directions, as the "
            f"studies word them." + (' ' + note5 if ndrop else '') + f"</p><ul>{tens}</ul>"
            + (f"<p>Conclusions that cannot both hold, as marked in the table:</p><ul>{crows}</ul>" if cons else '')
            + big_table(S, D, M, studies, kind, added) +
            f"<p class='small'>Evidence, in search-ppml/evidence/study-questions/: READING-GUIDE.md and studies/*.json (the readings, with page "
            f"quotations); SYNTHESIS-GUIDE.md and SYNTHESIS.json (the grouping); MATCH-GUIDE.md and MATCHES.json (the tags and matches); "
            f"verify/ (VERIFY-GUIDE.md, the packets, the checkers' results, CHANGES.md, and the corrected copies in verified/ from which this "
            f"report is built). Scripts: scripts/paper_ppml/study_questions.py and study_questions_apply.py.</p>")
    out.write_text(f"<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
                   f"<title>Study questions from scratch</title><style>{css}</style></head><body>{body}</body></html>", encoding='utf-8')
    print(f'{out} written: {len(S.get("questions", []))} questions, {len(S.get("themes", []))} themes, {len(D)} studies, '
          f'{len(M.get("links", []))} links')


if __name__ == '__main__':
    if sys.argv[1:2] == ['check']:
        sys.exit(1 if check(sys.argv[2:] or None) else 0)
    if sys.argv[1:2] == ['match-check']:
        sys.exit(1 if match_check() else 0)
    if sys.argv[1:2] == ['report']:
        report(sys.argv[3] if sys.argv[2:3] == ['--preview'] else None)
        sys.exit(0)
    if sys.argv[1:2] == ['verify-packets']:
        verify_packets()
        sys.exit(0)
    if sys.argv[1:2] == ['verify-check']:
        sys.exit(1 if verify_check(sys.argv[2:] or None) else 0)
    sys.exit(__doc__)
