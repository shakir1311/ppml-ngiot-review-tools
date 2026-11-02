#!/usr/bin/env python3
"""Audit every claim of a version of the PPML review against the full texts of its sources.

The author, 7 October 2026: "all the claims we make in our paper - are they accurate? are there any miss attributions?
wrong attributions? incorrect attributions? you might need to tally full texts if needed. We dont want to have any
incorrect claims in various tables or prose of the paper." … "all the claims we make in paper should be 100% correct".

The build already guarantees that the paper agrees with its records (every number of a marked sentence is in the cited
answer; every worded claim is tested by check_claims.py; every quotation of a record is on its page). This audit checks
the other half: that the records and the sentences say what the sources say.

prepare <v>   one packet per cited source in search-ppml/evidence/claims-audit-V<v>/packets/<key>.md, and index.json:
              every paragraph and table row of build/paper-V<v>.md that cites the source (citation numbers mapped back to
              keys), its own paragraph sentence by sentence, the heading of its group, the inconsistency recorded for it
              (quality item QA6), and every value of its extraction record that feeds a table or a count, with the record's
              pages and quotations. Two more packets: _process (the sentences about the review's own search, selection and
              extraction, to be checked against the search records) and _uncited (the other sentences without a citation,
              including the Key Takeaways).
check <v> [key …]   every unit and value of a packet has a verdict from the allowed list; every quotation of the results
              is found on the page it names (as for the records: scripts/paper_ppml/check_sheets.py).
report <v>    Docs/PPML-CLAIMS-AUDIT-V<v>-<date>.html: every finding that is not 'supported' or 'correct', with its
              evidence and the correction proposed, printable in portrait and landscape.

findings <v>  search-ppml/evidence/claims-audit-V<v>/FINDINGS-V<v>.csv: one row per finding, for the decisions.
delta <v> <prev>   after 'prepare <v>', restrict the audit of version <v> to what changed since the audited version <prev>:
              DELTA.json lists, per packet, the units whose text is new (citation, table, figure and section numbers
              ignored), the table rows of the summary tables in which this source moved, and the values that changed.
              delta-packets/<key>.md show only those; check, findings and report then cover only them.

Usage: python3 scripts/paper_ppml/claims_audit.py prepare|check|findings|report <version> [key …]
       python3 scripts/paper_ppml/claims_audit.py delta <version> <audited version>
       python3 scripts/paper_ppml/claims_audit.py resolve <audited version> <final version>
       python3 scripts/paper_ppml/claims_audit.py recheck <version> <name> <key …>   (then AUDIT_SUBDIR=<name> … check)
       python3 scripts/paper_ppml/claims_audit.py round2 <version> <name>   (the corrections of <version>; then AUDIT_SUBDIR=<name> … check)
"""
import datetime, html, json, pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
P = ROOT / 'myliteraturereviewpaper' / 'ppml2026'
B = P / 'build'
EV = ROOT / 'search-ppml' / 'evidence'
SHEETS = EV / 'sheets'
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import check_sheets as CS                                          # noqa: E402  (folder_of, found)

UNIT_VERDICTS = {'supported', 'partly', 'unsupported', 'contradicted', 'misattributed'}
VALUE_VERDICTS = {'correct', 'partly', 'wrong', 'unclear'}
PRIMARY_FIELDS = {'P1': ['settings', 'enablers', 'fl', 'device_measured', 'network_measured'],
                  'P2': ['mechanisms', 'protects', 'hidden_from'],
                  'P3': ['ledger', 'platform', 'consensus', 'on_chain', 'roles'],
                  'P4': ['checked', 'checker', 'checker_sees_update', 'zk_used', 'zk_shows', 'zk_on_chain'],
                  'P5': ['claimed', 'tested', 'defences'],
                  'P6': ['datasets', 'baselines', 'code'],
                  'P7': ['laws', 'personal_data_on_chain', 'erasure']}
SECONDARY_FIELDS = {'S1': ['databases', 'period', 'studies'],
                    'S2': ['fabric', 'privacy', 'trust', 'attacks', 'regulation'],
                    'S3': ['mechanisms'],
                    'S4': ['poisoning', 'malicious_fake', 'free_riding', 'verification', 'zkp', 'blockchain'],
                    'S5': ['laws', 'edpb', 'ai_act']}
PROCESS_SECTIONS = ('Front', 'III', 'X', 'Declarations')             # claims about the review's own process


def out_dir(v):
    sub = __import__('os').environ.get('AUDIT_SUBDIR', '')            # a re-check of chosen sources (recheck), kept apart
    return EV / f'claims-audit-V{v}' / sub if sub else EV / f'claims-audit-V{v}'


def recheck(v, name, keys):
    """claims-audit-V<v>/<name>/: full packets of version <v> for the given sources (every unit and value), read against the
    text each now rests on (e.g. a published version that replaced a preprint); check/findings/report then run with
    AUDIT_SUBDIR=<name>."""
    import os
    os.environ['AUDIT_SUBDIR'] = name
    od = out_dir(v)
    prepare(v)
    index = json.loads((od / 'index.json').read_text(encoding='utf-8'))
    sel = {k: {'units': [u['id'] for u in index[k]['units']], 'values': [x['id'] for x in index[k]['values']]} for k in keys}
    (od / 'DELTA.json').write_text(json.dumps({'since': 'all units and values of the sources re-checked', 'packets': sel}, indent=1), encoding='utf-8')
    (od / 'delta-packets').mkdir(exist_ok=True)
    for k in keys:
        write_packet(od, k, index[k], sub='delta-packets')
    print(f"{od.relative_to(ROOT)}: {', '.join(f'{k} ({len(sel[k]["units"])} units, {len(sel[k]["values"])} values)' for k in keys)}")


def round2(v, name):
    """claims-audit-V<v>/<name>/: the corrected text of version <v> (after its decisions) indexed again, and only the units and values
    that changed since the audited text of version <v> (claims-audit-V<v>/index.json) put in delta-packets, for a second round of
    auditing of the corrections themselves; check/findings/report then run with AUDIT_SUBDIR=<name>."""
    import os
    global out_dir
    os.environ['AUDIT_SUBDIR'] = name
    prepare(v)
    keep = out_dir
    dirs = iter([keep(v), EV / f'claims-audit-V{v}'])
    out_dir = lambda _v: next(dirs)
    try:
        delta(v, v)
    finally:
        out_dir = keep


def folder(key):
    refs = json.loads((P / 'refs.json').read_text(encoding='utf-8'))
    if refs.get(key, {}).get('folder'):
        return ROOT / refs[key]['folder']
    if key in refs and not refs[key].get('corpus_id'):            # a reference without a text of its own (software, a web page): no pages to audit against
        return ROOT / 'experiments' / '_no-source-text' / key
    return CS.folder_of(key)


def keyed(text, order):
    """[3]–[6], [8] → [@a; @b; @c; @d], [@e]: citation numbers back to keys"""
    def key(i):
        return order[i - 1] if 1 <= i <= len(order) else None

    def rng(m):
        a, b = int(m.group(1)), int(m.group(2))
        ks = [key(i) for i in range(a, b + 1)]
        return '[' + '; '.join('@' + k for k in ks) + ']' if all(ks) else m.group(0)
    text = re.sub(r'\[(\d+)\]–\[(\d+)\]', rng, text)
    return re.sub(r'\[(\d+)\]', lambda m: f'[@{key(int(m.group(1)))}]' if key(int(m.group(1))) else m.group(0), text)


def plain(s):
    s = re.sub(r'\s*⟦[^⟧]*⟧', '', s)
    s = re.sub(r'\s*\[@[^\]]+\]', '', s)
    return re.sub(r'\s+', ' ', s).strip()


def section_label(line, cur):
    m = re.match(r'^(#+)\s+(.*)$', line)
    lvl, title = len(m.group(1)), m.group(2).strip()
    if lvl == 1:
        r = re.match(r'([IVX]+)\.', title)
        if r:
            return r.group(1), title
        a = re.match(r'Appendix ([A-Z])', title)
        if a:
            return f'App-{a.group(1)}', title
        return title.split()[0], title
    top = cur[0].split('-')[0] if cur[0] else ''
    r = re.match(r'([A-Z])\.', title)
    return (f'{top}-{r.group(1)}' if r and top else top), title


def blocks(paper):
    """paragraphs, table rows and Key Takeaways points of the built paper, each with its section"""
    out, sec, para, table, cap, header, in_raw, raw = [], ('Front', ''), [], False, '', '', False, []
    lines = paper.split('\n')
    for ln in lines:
        if ln.startswith('# References'):
            break
        if in_raw:
            if ln.startswith('```'):
                in_raw = False
                for t in re.findall(r'<w:p>.*?</w:p>', ''.join(raw)):
                    txt = html.unescape(''.join(re.findall(r'<w:t[^>]*>([^<]*)</w:t>', t)))
                    if re.match(r'\d+\.', txt):
                        out.append({'where': sec[0], 'type': 'takeaway', 'text': re.sub(r'^(\d+\.)', r'\1 ', txt)})
                raw = []
            else:
                raw.append(ln)
            continue
        if ln.startswith('```{=openxml}'):
            in_raw = True
            continue
        if ln.startswith('#'):
            if para:
                out.append({'where': sec[0], 'type': 'prose', 'text': ' '.join(para)})
                para = []
            sec = section_label(ln, sec)
            continue
        if ln.startswith('Table: '):
            cap, header = ln[len('Table: '):].strip(), ''
            continue
        if ln.startswith('|'):
            if para:
                out.append({'where': sec[0], 'type': 'prose', 'text': ' '.join(para)})
                para = []
            if re.match(r'^\|[-|: ]+\|?\s*$', ln):
                continue
            if not header:
                header = ln
                continue
            out.append({'where': sec[0], 'type': 'table', 'caption': cap, 'header': header, 'text': ln})
            continue
        if not ln.strip() or ln.startswith('!['):
            if para:
                out.append({'where': sec[0], 'type': 'prose', 'text': ' '.join(para)})
                para = []
            continue
        para.append(ln.strip())
    if para:
        out.append({'where': sec[0], 'type': 'prose', 'text': ' '.join(para)})
    return out


def groups():
    """study id -> the heading of its group in Sections V-A and VI-A (the claims the heading makes about every member)"""
    g = {}
    for part in ('05-surveys.md', '06-approaches.md'):
        cur = None
        for p in re.split(r'\n\s*\n', (P / 'parts' / part).read_text(encoding='utf-8')):
            p = p.strip()
            if re.match(r'^\*[^*\n]+\*\s+\w+ (?:designs|surveys)\b', p):
                cur = plain(p)
            elif p.startswith('#'):
                cur = None
            for sid in re.findall(r'\{\{STUDY:(\w+)\}\}', p):
                if cur:
                    g[sid] = cur
    return g


def sentences(text):
    s = re.sub(r'\b(e\.g|i\.e|et al|Fig|cf|vs|No|Sect)\.', lambda m: m.group(0).replace('.', '§'), text)
    return [x.replace('§', '.').strip() for x in re.split(r'(?<=[.?!])\s+(?=[A-Z*(“"])', s) if x.strip()]


def prepare(v):
    import build as Bd                                            # studies(): the source paragraphs, with their markers
    rep = json.loads((B / f'BUILD-REPORT-V{v}.json').read_text(encoding='utf-8'))
    order = rep['citations']
    paper = keyed((B / f'paper-V{v}.md').read_text(encoding='utf-8'), order)
    fin = {r['corpus_id']: r for r in CS.studies().values()}
    own = Bd.studies()
    own_plain = {k: plain(t)[:80].lower() for k, t in own.items()}
    grp = groups()
    qa = json.loads((EV / 'QA-CONSISTENCY-2026-10-05.json').read_text(encoding='utf-8'))
    od = out_dir(v)
    (od / 'packets').mkdir(parents=True, exist_ok=True)
    (od / 'results').mkdir(exist_ok=True)
    units = {k: [] for k in order}
    process, uncited = [], []
    for b in blocks(paper):
        keys = list(dict.fromkeys(re.findall(r'@([\w-]+)', b['text'])))
        if b['type'] == 'prose' and any(own_plain[k] and plain(b['text'])[:80].lower() == own_plain[k] for k in keys if k in own_plain):
            continue                                              # a study's own paragraph: given sentence by sentence below
        if not keys:
            for s in (sentences(b['text']) if b['type'] == 'prose' else [b['text']]):
                (process if b['where'].split('-')[0] in PROCESS_SECTIONS else uncited).append({'where': b['where'], 'type': b['type'], 'text': s})
            continue
        for k in keys:
            if k in units:
                units[k].append(b)
    index = {}
    for k in order:
        ref = json.loads((P / 'refs.json').read_text(encoding='utf-8')).get(k, {})
        kind = 'foundation' if ref.get('role') == 'foundation' else fin.get(k, {}).get('kind', '?')
        f = folder(k)
        U = []
        if k in own:
            for s in re.split(r'(?<=⟧)\s+', own[k].strip()):
                U.append({'where': 'own paragraph (V-A)' if kind == 'secondary' else 'own paragraph (VI-A)', 'type': 'own',
                          'text': s.strip()})
        if k in grp:
            U.append({'where': 'group heading (V-A)' if kind == 'secondary' else 'group heading (VI-A)', 'type': 'group', 'text': grp[k]})
        for note_kind in ('no', 'partial'):
            if k in qa.get(note_kind, {}):
                U.append({'where': 'Appendix D, QA6 (and the count in Section IV-C)', 'type': 'qa6',
                          'text': f"QA6 = {'N' if note_kind == 'no' else 'P'}: the review states that this study's paper "
                                  f"{'contradicts its own claims or results' if note_kind == 'no' else 'has details that disagree without overturning a claim'}: {qa[note_kind][k]}"})
        for b in units[k]:
            d = {'where': b['where'], 'type': b['type'], 'text': b['text']}
            if b['type'] == 'table':
                d['caption'], d['header'] = b['caption'], b['header']
            U.append(d)
        for i, u in enumerate(U, 1):
            u['id'] = f'U{i}'
        V = []
        if kind in ('primary', 'secondary'):
            sh = json.loads((SHEETS / f'{k}.json').read_text(encoding='utf-8'))
            fields = PRIMARY_FIELDS if kind == 'primary' else SECONDARY_FIELDS
            for q, fl in fields.items():
                vals = (sh['answers'].get(q, {}) or {}).get('values', {}) or {}
                for fld in fl:
                    if fld in vals:
                        V.append({'id': f'V{len(V) + 1}', 'q': q, 'field': fld, 'value': vals[fld]})
        index[k] = {'kind': kind, 'title': ref.get('title') or fin.get(k, {}).get('title', ''), 'folder': str(f.relative_to(ROOT)) if f.is_relative_to(ROOT) else str(f),
                    'pages': len(list((f / 'text' / 'pages').glob('page_*.txt'))), 'units': U, 'values': V}
        write_packet(od, k, index[k])
    for name, lst in (('_process', process), ('_uncited', uncited)):
        for i, u in enumerate(lst, 1):
            u['id'] = f'U{i}'
        index[name] = {'kind': name.strip('_'), 'title': '', 'folder': '', 'pages': 0, 'units': lst, 'values': []}
        write_packet(od, name, index[name])
    (od / 'index.json').write_text(json.dumps(index, indent=1, ensure_ascii=False), encoding='utf-8')
    n_u = sum(len(x['units']) for x in index.values())
    n_v = sum(len(x['values']) for x in index.values())
    print(f'{len(index)} packets: {n_u} units, {n_v} values -> {od.relative_to(ROOT)}')


def write_packet(od, k, d, sub='packets'):
    L = [f'# Audit packet {k}', '']
    if d['kind'] in ('primary', 'secondary', 'foundation'):
        L += [f"**{d['kind'].capitalize()} source** — {d['title']}", '',
              f"Full text: `{d['folder']}/text/pages/page_NNNN.txt` ({d['pages']} pages; NNNN = PDF page), the whole text in "
              f"`{d['folder']}/text/full.txt`, page images in `{d['folder']}/images/pages/`."]
        if d['kind'] in ('primary', 'secondary'):
            L += [f"Extraction record: `search-ppml/evidence/sheets/{k}.json` (each answer with pages and quotations)."]
        L += ['']
    L += ['## Units: what the review says (verify each against the source)', '']
    for u in d['units']:
        L.append(f"### {u['id']} — {u['where']} — {u['type']}")
        if u['type'] == 'table':
            L.append(f"Table: {u.get('caption', '')}")
            L.append(f"Header: {u.get('header', '')}")
        L += [u['text'], '']
    if d['values']:
        L += ['## Values of the extraction record that feed the tables and counts', '']
        for x in d['values']:
            L.append(f"- **{x['id']}** {x['q']}.{x['field']} = `{json.dumps(x['value'], ensure_ascii=False)}`")
        L.append('')
    (od / sub / f'{k}.md').write_text('\n'.join(L), encoding='utf-8')


SUMMARY_TABLES = {'II-C', 'IV-A', 'IV-B', 'VI-C', 'VI-D', 'VI-E'}       # rows that list many studies: re-checked only where this source moved


def delta(v, prev):
    od, po = out_dir(v), out_dir(prev)
    new, old = (json.loads((d / 'index.json').read_text(encoding='utf-8')) for d in (od, po))
    norm = lambda s: re.sub(r'\s+', ' ', re.sub(r'\b(Table|Fig\.|Section)\s+[IVX\d]+(-[A-Z])?', r'\1 #',
                                                re.sub(r'\[\d+(?:[,–-]\s*\d+)*\]', '[#]', s))).strip()
    cells = lambda s: [c.strip() for c in s.strip().strip('|').split('|')]
    where_cited = lambda k, s: tuple(i for i, c in enumerate(cells(s)) if re.search(r'@' + re.escape(k) + r'\b', c))
    out = {}
    for k, d in new.items():
        before = {norm(u['text']) for u in old.get(k, {}).get('units', [])}
        rows = {(u['where'], cells(u['text'])[0]): where_cited(k, u['text']) for u in old.get(k, {}).get('units', [])
                if u['type'] == 'table' and u['where'] in SUMMARY_TABLES}
        us = []
        for u in d['units']:
            if norm(u['text']) in before:
                continue
            if u['type'] == 'table' and u['where'] in SUMMARY_TABLES and rows.get((u['where'], cells(u['text'])[0])) == where_cited(k, u['text']):
                continue                                          # only the counts of other studies changed
            us.append(u['id'])
        was = {(x['q'], x['field']): x['value'] for x in old.get(k, {}).get('values', [])}
        vs = [x['id'] for x in d['values'] if was.get((x['q'], x['field']), '§') != x['value']]
        if us or vs:
            out[k] = {'units': us, 'values': vs}
    (od / 'DELTA.json').write_text(json.dumps({'since': f'V{prev}', 'packets': out}, indent=1), encoding='utf-8')
    (od / 'delta-packets').mkdir(exist_ok=True)
    for k, sel in out.items():
        d = dict(new[k], units=[u for u in new[k]['units'] if u['id'] in sel['units']],
                 values=[x for x in new[k]['values'] if x['id'] in sel['values']])
        write_packet(od, k, d, sub='delta-packets')
    print(f"{sum(len(x['units']) for x in out.values())} units and {sum(len(x['values']) for x in out.values())} values changed "
          f"since V{prev}, in {len(out)} packets -> {od / 'delta-packets'}")


def selected(od):
    """the ids to audit per packet: all, or only those of DELTA.json"""
    f = od / 'DELTA.json'
    return json.loads(f.read_text(encoding='utf-8'))['packets'] if f.exists() else None


def resolve(v, final):
    """claims-audit-V<v>/RESOLUTION-IN-V<final>.json: for every finding of round <v> (a unit or value not supported/correct), how it
    stands in version <final>: 'corrected as proposed' (the proposed wording is in the text, or the record has the proposed value),
    'changed' (the wording or value the auditor judged is gone, corrected otherwise), or 'unchanged' (to be explained in the
    decisions). The final text is indexed into claims-audit-V<final>/final-text/ (as 'prepare' does)."""
    global out_dir
    od, fd = out_dir(v), out_dir(final) / 'final-text'
    keep = out_dir
    out_dir = lambda _v: fd
    try:
        prepare(final)
    finally:
        out_dir = keep
    cur = json.loads((fd / 'index.json').read_text(encoding='utf-8'))
    norm = lambda s: re.sub(r'\s+', ' ', re.sub(r'⟦[^⟧]*⟧', '', re.sub(r'\[\d+(?:[,–-]\s*\d+)*\]', '[#]', s or ''))).strip().lower()
    units_now = {norm(u['text']) for d in cur.values() for u in d['units']}
    blob = ' || '.join(units_now)
    index = json.loads((od / 'index.json').read_text(encoding='utf-8'))
    out = {}
    for k, d in index.items():
        f = od / 'results' / f'{k}.json'
        if not f.exists():
            continue
        r = json.loads(f.read_text(encoding='utf-8'))
        units = {u['id']: u for u in d['units']}
        vals = {x['id']: x for x in d['values']}
        for g in r.get('units', []):
            if g.get('verdict') == 'supported':
                continue
            old, fix = norm(units.get(g['id'], {}).get('text', '')), norm(g.get('fix', ''))
            out[f"{k}:{g['id']}"] = ('corrected as proposed' if fix and fix in blob else 'changed' if old and old not in units_now else 'unchanged')
        for g in r.get('values', []):
            if g.get('verdict') == 'correct':
                continue
            x = vals.get(g['id'], {})
            sh = json.loads((SHEETS / f'{k}.json').read_text(encoding='utf-8')) if (SHEETS / f'{k}.json').exists() else {'answers': {}}
            now = ((sh['answers'].get(x.get('q'), {}) or {}).get('values', {}) or {}).get(x.get('field'))
            out[f"{k}:{g['id']}"] = ('corrected as proposed' if 'correct_value' in g and now == g['correct_value']
                                     else 'changed' if now != x.get('value') else 'unchanged')
    (od / f'RESOLUTION-IN-V{final}.json').write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding='utf-8')
    from collections import Counter
    print(f"{(od / f'RESOLUTION-IN-V{final}.json').relative_to(ROOT)}: {dict(Counter(out.values()))}")


COVERAGE_KEYS = {'fabric': 'S2', 'privacy': 'S2', 'trust': 'S2', 'attacks': 'S2', 'regulation': 'S2',
                 'poisoning': 'S4', 'malicious_fake': 'S4', 'free_riding': 'S4', 'verification': 'S4', 'zkp': 'S4', 'blockchain': 'S4'}


def coverage_check(v, keys=None, diff=False):
    """claims-audit-V<v>/coverage/marks/<key>.json (COVERAGE-GUIDE.md): all 11 marks with an allowed value, a quotation found on
    its page for subject and mentioned, the terms searched for absent; with diff, the marks that differ from the records"""
    cd = EV / f'claims-audit-V{v}' / 'coverage'
    files = [cd / 'marks' / f'{k}.json' for k in keys] if keys else sorted((cd / 'marks').glob('*.json'))
    bad, changes = 0, []
    for f in files:
        k = f.stem
        probs = []
        if not f.exists():
            print(f'{k}: no marks yet')
            continue
        try:
            r = json.loads(f.read_text(encoding='utf-8'))
        except Exception as ex:                                   # noqa: BLE001
            print(f'{k}: FAIL not readable JSON: {ex}')
            bad += 1
            continue
        sh = json.loads((SHEETS / f'{k}.json').read_text(encoding='utf-8'))
        nq = 0
        for topic, item in COVERAGE_KEYS.items():
            m = (r.get('marks') or {}).get(topic)
            if not m:
                probs.append(f'{topic}: no mark')
                continue
            if m.get('value') not in ('subject', 'mentioned', 'absent'):
                probs.append(f"{topic}: value {m.get('value')!r} not allowed")
                continue
            if m['value'] == 'absent':
                if not m.get('searched'):
                    probs.append(f'{topic}: absent needs the terms searched')
            elif not m.get('evidence'):
                probs.append(f"{topic}: {m['value']} needs a quotation")
            for e in m.get('evidence', []) or []:
                if e.get('source') in ('image', 'table'):
                    continue
                pf = page_file(k, e.get('page', 0))
                nq += 1
                if not pf.exists():
                    probs.append(f"{topic}: page {e.get('page')} does not exist")
                elif not CS.found(e.get('quote', ''), page_text(pf)):
                    probs.append(f"{topic}: quotation not on p{e.get('page')}: {e.get('quote', '')[:70]!r}")
            now = ((sh['answers'].get(item, {}) or {}).get('values', {}) or {}).get(topic)
            if now != m['value']:
                changes.append((k, topic, now, m['value'], m.get('basis', '')))
        bad += bool(probs)
        print(f"{k}: {'PASS' if not probs else 'FAIL'} ({nq} quotations checked)")
        for p_ in probs[:20]:
            print('   ', p_)
    if diff:
        print(f'{len(changes)} marks differ from the records:')
        for c in changes:
            print('   %s %s: %s -> %s (%s)' % (c[0], c[1], c[2], c[3], c[4][:120]))
    return bad


def coverage_report(v, final):
    """Docs/PPML-SURVEY-COVERAGE-V<final>-<date>.html: the rule, every survey's 11 marks as the records now hold them (cells that
    changed show the old mark), and each change or rejection with the heading or caption it rests on; printable"""
    esc = html.escape
    cd = EV / f'claims-audit-V{v}' / 'coverage'
    out = ROOT / 'Docs' / f'PPML-SURVEY-COVERAGE-V{final}-{datetime.date.today().isoformat()}.html'
    if out.exists():
        sys.exit(f'{out.name} exists; documents are never overwritten')
    dec = json.loads((EV / f'claims-audit-V{final}' / f'DECISIONS-V{final}.json').read_text(encoding='utf-8'))['decisions']
    changed = {(d['key'], d['field']): d for d in dec if d['action'] == 'value' and str(d.get('finding', '')).startswith('coverage ')}
    rejected = [d for d in dec if d['action'] == 'reject' and str(d.get('finding', '')).startswith('coverage ')]
    refs = json.loads((P / 'refs.json').read_text(encoding='utf-8'))
    MARK = {'subject': '●', 'mentioned': '◐', 'absent': '–'}
    cols = list(COVERAGE_KEYS)
    head = ''.join(f'<th>{esc(c.replace("_", " "))}</th>' for c in cols)
    rows = []
    for f in sorted((cd / 'marks').glob('*.json')):
        k = f.stem
        sh = json.loads((SHEETS / f'{k}.json').read_text(encoding='utf-8'))
        name = refs.get(k, {}).get('first_author_surname', k) + ' ' + str(refs.get(k, {}).get('year', ''))
        cells = []
        for c in cols:
            now = ((sh['answers'].get(COVERAGE_KEYS[c], {}) or {}).get('values', {}) or {}).get(c)
            d = changed.get((k, c))
            if d:
                cells.append(f"<td class='ch'>{MARK.get(now, '?')}</td>")
            else:
                cells.append(f'<td>{MARK.get(now, "?")}</td>')
        rows.append(f'<tr><td>{esc(k)}<br><span class="n">{esc(name)}</span></td>{"".join(cells)}</tr>')
    log = []
    for (k, c), d in sorted(changed.items()):
        ev = '<br>'.join(esc(f"p{e.get('page')}: {e.get('quote', '')}") for e in d.get('evidence', [])[:2])
        log.append(f"<tr><td>{esc(k)}</td><td>{esc(c.replace('_', ' '))}</td><td>{esc(d['new'])}</td><td>{esc(d.get('why', '').replace('coverage by one rule (subject = a heading or table of its own): ', ''))}</td><td class='ev'>{ev}</td></tr>")
    for d in rejected:
        log.append(f"<tr><td>{esc(d['key'])}</td><td colspan='2'>{esc(d['finding'].replace('coverage ', ''))}: not changed</td><td colspan='2'>{esc(d['why'])}</td></tr>")
    css = ('body{font:13px/1.45 Georgia,serif;background:#fff;color:#111;margin:24px;max-width:1300px}h1{font-size:22px}h2{font-size:17px;margin-top:26px}'
           'table{border-collapse:collapse;width:100%}td,th{border:1px solid #bbb;padding:3px 6px;vertical-align:top;overflow-wrap:anywhere}'
           'th{background:#eef2f6;text-align:left}td.ch{background:#fff2b3;font-weight:bold}.n{color:#555;font-size:11px}.ev{font-size:11px;color:#333}'
           '@media print{@page{size:auto;margin:12mm}body{margin:0;max-width:none;font-size:10.5px}thead{display:table-header-group}tr,td,th{break-inside:avoid}'
           'td.ch{background:#fff;border:2px solid #000}}')
    out.write_text(
        f"<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>Survey coverage</title>"
        f"<style>{css}</style></head><body><h1>What each included survey treats as a subject: one rule for all 30 (V{final})</h1>"
        "<p><b>Rule</b> (the extraction guide's definition, made exact): a survey treats a topic as a <b>subject</b> when it gives it a heading of its own "
        "(a section, subsection, or a numbered or titled paragraph in bold or italics) or a table devoted to it; anything less (running text, even a whole "
        "paragraph; a row or column of a broader table; a reviewed work; an open issue without its own heading) is <b>mentioned</b>; <b>absent</b> means not "
        "there (terms searched in the full text). A heading on a broader topic does not make its parts subjects. Each survey was re-judged on its full text "
        "by a separate Claude run that quoted the heading or caption with its page; a script found every quotation on its page "
        f"(search-ppml/evidence/claims-audit-V{v}/coverage/).</p>"
        f"<h2>The marks as the records now hold them</h2><p>● subject, ◐ mentioned, – absent; a highlighted cell changed in V{final}.</p>"
        f"<table><thead><tr><th>Survey</th>{head}</tr></thead><tbody>{''.join(rows)}</tbody></table>"
        f"<h2>Every change, and the one finding not followed</h2><table><thead><tr><th>Survey</th><th>Topic</th><th>Now</th><th>Basis</th><th>Heading, caption or text quoted</th></tr></thead>"
        f"<tbody>{''.join(log)}</tbody></table></body></html>", encoding='utf-8')
    print(f'{out.relative_to(ROOT)}: {len(changed)} changes, {len(rejected)} not followed')


def page_file(k, page):
    return folder(k) / 'text' / 'pages' / f'page_{int(page):04d}.txt'


def page_text(pf):
    """the page's text, and its OCR where scripts/ocr_scanned.py read a page whose text layer is unreadable (text/pages_ocr/)"""
    ocr = pf.parent.parent / 'pages_ocr' / pf.name
    return '\n'.join(f.read_text(encoding='utf-8', errors='ignore') for f in (pf, ocr) if f.exists())


def check(v, keys=None):
    od = out_dir(v)
    index = json.loads((od / 'index.json').read_text(encoding='utf-8'))
    sel = selected(od)
    keys = keys or [k for k in index if (od / 'results' / f'{k}.json').exists()]
    bad_total = 0
    for k in keys:
        f = od / 'results' / f'{k}.json'
        probs = []
        if not f.exists():
            print(f'{k}: no results yet')
            continue
        try:
            r = json.loads(f.read_text(encoding='utf-8'))
        except Exception as ex:                                   # noqa: BLE001
            print(f'{k}: FAIL not readable JSON: {ex}')
            bad_total += 1
            continue
        got_u = {u.get('id'): u for u in r.get('units', [])}
        got_v = {x.get('id'): x for x in r.get('values', [])}
        for u in index[k]['units']:
            if sel is not None and u['id'] not in sel.get(k, {}).get('units', []):
                continue
            g = got_u.get(u['id'])
            if not g:
                probs.append(f"{u['id']}: no verdict")
            elif g.get('verdict') not in UNIT_VERDICTS:
                probs.append(f"{u['id']}: verdict {g.get('verdict')!r} not allowed")
            elif g['verdict'] != 'supported' and not (g.get('problem') and g.get('fix')):
                probs.append(f"{u['id']}: {g['verdict']} needs 'problem' and 'fix'")
        for x in index[k]['values']:
            if sel is not None and x['id'] not in sel.get(k, {}).get('values', []):
                continue
            g = got_v.get(x['id'])
            if not g:
                probs.append(f"{x['id']}: no verdict")
            elif g.get('verdict') not in VALUE_VERDICTS:
                probs.append(f"{x['id']}: verdict {g.get('verdict')!r} not allowed")
            elif g['verdict'] in ('partly', 'wrong') and 'correct_value' not in g:
                probs.append(f"{x['id']}: {g['verdict']} needs 'correct_value'")
        nq = 0
        for item in list(r.get('units', [])) + list(r.get('values', [])) + list(r.get('other_findings', [])):
            for e in item.get('evidence', []) or []:
                if e.get('source') in ('image', 'table', 'record'):
                    continue
                src = e.get('key', k)
                pf = page_file(src, e.get('page', 0)) if src not in ('_process', '_uncited') else None
                if pf is None:
                    continue
                nq += 1
                if not pf.exists():
                    probs.append(f"{item.get('id', '?')}: page {e.get('page')} of {src} does not exist")
                elif not CS.found(e.get('quote', ''), page_text(pf)):
                    probs.append(f"{item.get('id', '?')}: quotation not on {src} p{e.get('page')}: {e.get('quote', '')[:70]!r}")
        bad_total += bool(probs)
        print(f"{k}: {'PASS' if not probs else 'FAIL'} ({len(got_u)} units, {len(got_v)} values, {nq} quotations checked)")
        for p_ in probs[:25]:
            print('   ', p_)
    return bad_total


def findings(v):
    """every finding that is not supported/correct, one row each, for the decisions (FINDINGS-V<v>.csv); a unit finding
    that only follows from a value ("follows V12") is marked so, since correcting the value corrects it"""
    import csv
    od = out_dir(v)
    index = json.loads((od / 'index.json').read_text(encoding='utf-8'))
    rows = []
    for k, d in index.items():
        f = od / 'results' / f'{k}.json'
        if not f.exists():
            continue
        r = json.loads(f.read_text(encoding='utf-8'))
        units = {u['id']: u for u in d['units']}
        vals = {x['id']: x for x in d['values']}
        ev = lambda g: ' | '.join(f"{e.get('key', k)} p{e.get('page', '?')}: {e.get('quote', '')}" for e in (g.get('evidence') or []))
        for g in r.get('units', []):
            if g.get('verdict') == 'supported':
                continue
            u = units.get(g['id'], {})
            m = re.search(r'follows (V\d+)', g.get('problem', '') + ' ' + g.get('fix', ''), re.I)
            rows.append({'key': k, 'id': g['id'], 'type': 'unit', 'where': u.get('where', ''), 'verdict': g.get('verdict'),
                         'said': u.get('text', ''), 'problem': g.get('problem', ''), 'fix': g.get('fix', ''),
                         'follows': m.group(1) if m else '', 'evidence': ev(g)})
        for g in r.get('values', []):
            if g.get('verdict') == 'correct':
                continue
            x = vals.get(g['id'], {})
            rows.append({'key': k, 'id': g['id'], 'type': 'value', 'where': f"{x.get('q')}.{x.get('field')}", 'verdict': g.get('verdict'),
                         'said': json.dumps(x.get('value'), ensure_ascii=False), 'problem': g.get('note', ''),
                         'fix': json.dumps(g.get('correct_value'), ensure_ascii=False) if 'correct_value' in g else '',
                         'follows': '', 'evidence': ev(g)})
        for g in r.get('other_findings', []):
            rows.append({'key': k, 'id': g.get('id', 'X'), 'type': 'other', 'where': g.get('where', ''), 'verdict': 'other',
                         'said': g.get('text', ''), 'problem': g.get('problem', ''), 'fix': g.get('fix', ''), 'follows': '', 'evidence': ev(g)})
    out = od / f'FINDINGS-V{v}.csv'
    with open(out, 'w', encoding='utf-8', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=['key', 'id', 'type', 'where', 'verdict', 'said', 'problem', 'fix', 'follows', 'evidence'])
        w.writeheader()
        w.writerows(rows)
    from collections import Counter
    print(f"{out.relative_to(ROOT)}: {len(rows)} findings — {dict(Counter(r['type'] for r in rows))}; "
          f"{sum(1 for r in rows if r['follows'])} follow from a value")


UNCHANGED_NOTES = {                                               # findings whose sentence was kept, with how they were resolved
    '38': {
        'n0207:U18': 'corrected: the record now lists both PoA and PoW, so the study appears in both rows of Table 16',
        'n2723:V12': 'kept as unclear: the paragraph states the contradiction (proofs and update references in the methods, the updates themselves in the introduction and results)',
        '_uncited:U66': 'corrected in code: Table 12 is built from the extraction records (P4.zk_shows), as Section VI-D; the sentence is kept',
        '_uncited:U118': 'corrected in code (V39): Fig. 7 and the count include a design only when its protected updates are hidden from the aggregator; the sentence is kept'},
    '39': {
        '_uncited:U125': 'corrected in code: the count now includes a design only when its protected items include the updates (n3378 no longer counts); with N008 treated as N009 (N008:X1) the count stays 15',
        '_uncited:U144': 'as _uncited:U125: the takeaway uses the same corrected count, which stays 15',
        '_uncited:U148': 'corrected in code: Fig. 10(a) is drawn from the full-text records (data.angle_marks), as Table 11; the sentence is kept'},
}


def report(*versions):
    """Docs/PPML-CLAIMS-AUDIT-V<v>[-V<w>]-<date>.html: per round, what was checked and the verdicts, then every finding that is
    not 'supported' or 'correct' with the decision taken on it (the correction applied, or why it was not), printable"""
    esc = html.escape
    day = datetime.date.today().isoformat()
    tag = '-'.join('V' + str(v) for v in versions)
    out, rev = ROOT / 'Docs' / f"PPML-CLAIMS-AUDIT-{tag}-{day}.html", 2
    while out.exists():                                           # documents are never overwritten: a revision is the next -V<k>- file
        out, rev = ROOT / 'Docs' / f"PPML-CLAIMS-AUDIT-{tag}-V{rev}-{day}.html", rev + 1
    parts = []
    for v in versions:
        od = out_dir(v)
        index = json.loads((od / 'index.json').read_text(encoding='utf-8'))
        sel = selected(od)
        dec_f = od / f'DECISIONS-V{v}.json'
        decisions = json.loads(dec_f.read_text(encoding='utf-8'))['decisions'] if dec_f.exists() else []
        res_files = sorted(od.glob('RESOLUTION-IN-V*.json'))
        resolution = json.loads(res_files[-1].read_text(encoding='utf-8')) if res_files else {}
        by_finding = {}
        for d in decisions:
            for fid in re.findall(r'[\w]+:[UVX]\d+', d.get('finding', '')):
                by_finding.setdefault(fid, []).append(d)
        def decided(fid):
            ds = by_finding.get(fid, [])
            if not ds:
                st = resolution.get(fid)
                note = UNCHANGED_NOTES.get(str(v), {}).get(fid)
                if note:
                    return note
                if st == 'corrected as proposed':
                    return 'corrected as proposed (through the record value or the rule it follows, or a later rewrite)'
                if st == 'changed':
                    return 'corrected otherwise (the wording or value judged is no longer in the review)'
                return 'see the decisions of this round and FIXES-V' + str(v) + '.json'
            txt = []
            for d in ds:
                a = d['action']
                if a == 'reject':
                    txt.append('not changed: ' + d.get('why', ''))
                elif a == 'text':
                    txt.append(f"text changed ({d['file']}): {d['new'][:400]}")
                elif a == 'value':
                    txt.append(f"record {d['key']} {d['q']}.{d['field']} set to {json.dumps(d['new'], ensure_ascii=False)[:300]}" + (f" — {d['why']}" if d.get('why') else ''))
                elif a == 'qa6':
                    txt.append(f"quality item QA6 = {d['level']}: {d.get('reason', '')[:300]}")
                elif a in ('answer', 'answer_replace'):
                    txt.append(f"record {d['key']} {d['q']}: answer text corrected")
                elif a == 'ref':
                    txt.append(f"reference {d['key']} corrected")
                if d.get('superseded_by'):
                    txt[-1] += f" (later rewritten: {d['superseded_by']})"
            return ' | '.join(txt)
        counts, rows = {}, []
        for k, d in index.items():
            f = od / 'results' / f'{k}.json'
            if not f.exists():
                continue
            r = json.loads(f.read_text(encoding='utf-8'))
            units = {u['id']: u for u in d['units']}
            vals = {x['id']: x for x in d['values']}
            for g in r.get('units', []):
                counts['statement ' + str(g.get('verdict'))] = counts.get('statement ' + str(g.get('verdict')), 0) + 1
                if g.get('verdict') != 'supported':
                    u = units.get(g['id'], {})
                    rows.append((k, g['id'], u.get('where', ''), g.get('verdict'), u.get('text', ''), g.get('problem', ''), decided(f"{k}:{g['id']}"), g.get('evidence', [])))
            for g in r.get('values', []):
                counts['value ' + str(g.get('verdict'))] = counts.get('value ' + str(g.get('verdict')), 0) + 1
                if g.get('verdict') != 'correct':
                    x = vals.get(g['id'], {})
                    rows.append((k, g['id'], f"{x.get('q')}.{x.get('field')}", g.get('verdict'), json.dumps(x.get('value'), ensure_ascii=False),
                                 g.get('note', ''), decided(f"{k}:{g['id']}"), g.get('evidence', [])))
            for g in r.get('other_findings', []):
                rows.append((k, g.get('id', 'other'), g.get('where', ''), 'other', g.get('text', ''), g.get('problem', ''), decided(f"{k}:{g.get('id', '')}"), g.get('evidence', [])))
        n_u = sum(len(x['units']) for x in index.values()) if sel is None else sum(len(x['units']) for x in sel.values())
        n_v = sum(len(x['values']) for x in index.values()) if sel is None else sum(len(x['values']) for x in sel.values())
        scope = (f"every statement about the {len(index) - 2} cited sources and the review's own process ({n_u} statements and table rows, {n_v} values of the extraction records)"
                 if sel is None else f"what changed since the audited version ({n_u} statements and table rows, {n_v} values, in {len(sel)} packets)")
        ev_html = lambda ev: '<br>'.join(esc(f"{e.get('key', '') or e.get('file', '')} p{e.get('page', '–')}: {e.get('quote', '')}") for e in (ev or [])[:3])
        tr = ''.join(f"<tr><td>{esc(k)}<br>{esc(i)}</td><td>{esc(w)}</td><td class='v'>{esc(str(vd))}</td><td>{esc(t[:900])}</td>"
                     f"<td>{esc(pr)}</td><td>{esc(dc)}</td><td class='ev'>{ev_html(ev)}</td></tr>" for k, i, w, vd, t, pr, dc, ev in rows)
        acts = {}
        for d in decisions:
            acts[d['action']] = acts.get(d['action'], 0) + 1
        parts.append(f"<h2>Version {v}</h2><p>Checked: {esc(scope)}. Each verdict rests on a quotation from the page of the source (or, for the "
                     f"process, from the search records); a script found every page quotation again on its page.</p>"
                     f"<p class='counts'>Verdicts: {esc(', '.join(f'{n} {k}' for k, n in sorted(counts.items())))}.</p>"
                     f"<p class='counts'>Decisions: {esc(', '.join(f'{n} {k}' for k, n in sorted(acts.items())))} "
                     f"(record values, text, answer texts, quality item QA6, references; 'reject' = decided against, with the reason).</p>"
                     f"<table><thead><tr><th>Source / item</th><th>Where</th><th>Verdict</th><th>What the review said</th><th>Problem found</th>"
                     f"<th>Decision</th><th>Evidence</th></tr></thead><tbody>{tr}</tbody></table>")
    css = ('body{font:13px/1.45 Georgia,serif;background:#fff;color:#111;margin:24px;max-width:1400px}h1{font-size:22px}h2{font-size:18px;margin-top:28px}'
           'table{border-collapse:collapse;width:100%;table-layout:auto}td,th{border:1px solid #bbb;padding:4px 6px;vertical-align:top;'
           'overflow-wrap:anywhere}th{background:#eef2f6;text-align:left}.v{font-weight:bold}.ev{font-size:11px;color:#333}.counts{color:#333}'
           '@media print{@page{size:auto;margin:12mm}body{margin:0;max-width:none;font-size:10.5px}thead{display:table-header-group}'
           'tr,td,th{break-inside:avoid}table{width:100%}}')
    out.write_text(f"<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
                   f"<title>PPML claims audit</title><style>{css}</style></head><body><h1>Claims audit of the PPML review</h1>"
                   f"<p>Every statement the review makes about an included study or a foundation (GDPR, EDPB guidelines, PRISMA 2020), every "
                   f"value of the extraction records that its tables and counts use, and every sentence about its own search, selection and "
                   f"extraction was checked against the full texts and the records by separate runs of Claude, following the audit guides in "
                   f"search-ppml/evidence/claims-audit-V&lt;n&gt;/. The findings were decided one by one and applied by "
                   f"scripts/paper_ppml/apply_audit.py, which keeps a copy of every changed file and a log.</p>{''.join(parts)}</body></html>",
                   encoding='utf-8')
    print(f'{out.relative_to(ROOT)} written')


if __name__ == '__main__':
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    cmd, ver = sys.argv[1], sys.argv[2]
    if cmd == 'prepare':
        prepare(ver)
    elif cmd == 'check':
        sys.exit(1 if check(ver, sys.argv[3:] or None) else 0)
    elif cmd == 'report':
        report(ver, *sys.argv[3:])
    elif cmd == 'findings':
        findings(ver)
    elif cmd == 'delta' and len(sys.argv) > 3:
        delta(ver, sys.argv[3])
    elif cmd == 'resolve' and len(sys.argv) > 3:
        resolve(ver, sys.argv[3])
    elif cmd == 'recheck' and len(sys.argv) > 4:
        recheck(ver, sys.argv[3], sys.argv[4:])
    elif cmd == 'round2' and len(sys.argv) > 3:
        round2(ver, sys.argv[3])
    elif cmd == 'coverage-check':
        sys.exit(1 if coverage_check(ver, sys.argv[3:] or None) else 0)
    elif cmd == 'coverage-diff':
        coverage_check(ver, sys.argv[3:] or None, diff=True)
    elif cmd == 'coverage-report' and len(sys.argv) > 3:
        coverage_report(ver, sys.argv[3])
    else:
        sys.exit(__doc__)
