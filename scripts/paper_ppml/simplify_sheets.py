#!/usr/bin/env python3
"""Simplify the evidence sheets to one answer per review question (EXTRACTION-GUIDE-V3-2026-10-15.md):
designs P1 <- P1 + P1b, P2 <- P2 + P3 + P3b + P7, P3 <- P4 + P5 + P6 + P6b + P8; surveys S1 <- S2 + S4.
Texts are joined with the part named; tags are set side by side (no two parts share a tag name); quotations are
pooled (the same page and words once); located_via is the deepest level any part reached; searched terms are joined.
The Sheet Reviewer's record is remapped: quotation ticks carry over (they are keyed by page and words); a merged answer
is verified where every part was verified by the author — a part whose tick was only disturbed by the removal of two
tags on 15 October (the checking answer) counts as verified; notes are joined. Every sheet is first copied to
notes-verifier/history/<id>/SHEET-before-simplify-<stamp>.json; the record to history/_sheet-review-before-simplify-*.
Log: search-ppml/evidence/SIMPLIFY-2026-10-15.jsonl. Counts only are printed.
Usage: python3 scripts/paper_ppml/simplify_sheets.py [--dry-run]
"""
import csv, datetime, hashlib, json, pathlib, re, sys, unicodedata

csv.field_size_limit(10 ** 9)
ROOT = pathlib.Path(__file__).resolve().parents[2]
SHEETS = ROOT / 'search-ppml' / 'evidence' / 'sheets'
HIST = ROOT / 'notes-verifier' / 'history'
RECORD = ROOT / 'notes-verifier' / 'data' / 'sheet-review.json'
LOG = ROOT / 'search-ppml' / 'evidence' / 'SIMPLIFY-2026-10-15.jsonl'
STAMP = datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
NOW = datetime.datetime.now().isoformat(timespec='seconds')
MERGE = {'primary': {'P1': [('P1', 'Setting and tiers'), ('P1b', 'Cost')],
                     'P2': [('P2', 'Privacy'), ('P3', 'Ledger'), ('P3b', 'Parties still trusted'), ('P7', "Regulation and the ledger's data")],
                     'P3': [('P4', 'Checking'), ('P5', 'Threats'), ('P6', 'Evaluation'), ('P6b', 'Environment and scale'), ('P8', 'Limitations (authors)')]},
         'secondary': {'S1': [('S2', 'What it treats'), ('S4', 'The named threats and the blockchain')]}}
LEVEL = {'summary': 0, 'notes': 1, 'full text': 2}


def fingerprint(*parts):                                   # as the Sheet Reviewer computes it
    return hashlib.sha256(json.dumps(parts, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:16]


def squash(t):
    return re.sub(r'[^0-9a-z]', '', unicodedata.normalize('NFKC', t).lower())


def merge(parts):
    """one answer from [(label, old answer)]"""
    texts, values, ev, seen, searched, level = [], {}, [], set(), [], -1
    for label, a in parts:
        t = str(a.get('answer', '')).strip()
        if t:
            lead = re.match(r'^(Not stated|Costs reported|Trusted|Environment)\b', t)
            texts.append(t if lead and label in ('Cost', 'Parties still trusted', 'Environment and scale') else f'{label}: {t}')
        for k, v in (a.get('values') or {}).items():
            if k in values and values[k] != v:
                raise SystemExit(f'tag {k} would clash')
            values[k] = v
        for e in a.get('evidence') or []:
            key = (e.get('page'), squash(str(e.get('quote') or '')))
            if key not in seen:
                seen.add(key)
                ev.append(e)
        for s in a.get('searched') or []:
            if s not in searched:
                searched.append(s)
        level = max(level, LEVEL.get(a.get('located_via'), -1))
    return {'answer': ' '.join(texts), 'values': values, 'evidence': ev,
            'located_via': {v: k for k, v in LEVEL.items()}.get(level, 'notes'), 'searched': searched}


def main(dry):
    kinds = {r['corpus_id']: r['kind'] for r in csv.DictReader(open(ROOT / 'search-ppml' / 'FINAL-STUDIES-2026-10-05.csv', encoding='utf-8'))}
    record = json.loads(RECORD.read_text(encoding='utf-8')) if RECORD.exists() else {}
    log, n_sheets, n_verified, n_open = [], 0, 0, 0
    for cid, kind in sorted(kinds.items()):
        path = SHEETS / f'{cid}.json'
        if not path.exists():
            continue
        text = path.read_text(encoding='utf-8')
        sheet = json.loads(text)
        A = sheet['answers']
        if set(A) == set(MERGE[kind]) and all(k in A for k in MERGE[kind]) and 'P1b' not in A and 'S2' not in A:
            continue                                        # already simplified
        new, rec_new, entry = {}, {}, {'id': cid, 'kind': kind, 'answers': {}}
        for key, parts in MERGE[kind].items():
            present = [(label, A[old]) for old, label in parts if old in A]
            if not present:
                continue
            new[key] = merge(present)
            recs = [record.get(cid, {}).get(old, {}) for old, _ in parts if old in A]
            quotes = {}
            for r in recs:
                quotes.update(r.get('quotes') or {})
            verified_parts = [bool(r.get('verified')) and r.get('how') not in ('new fact', 'reader', 'merged with new facts') for r in recs]
            by_hand = any(r.get('how') == 'by hand' for r in recs)
            notes = ' | '.join(f"{old}: {r['note']}" for (old, _), r in zip([p for p in parts if p[0] in A], recs) if r.get('note'))
            e = {'quotes': quotes}
            if all(verified_parts):
                e.update({'verified': True, 'verified_on': max(r.get('verified_on', '') for r in recs) or NOW,
                          'how': 'by hand' if by_hand else 'default', 'answer_fingerprint': fingerprint(new[key]['answer'], new[key]['values']),
                          'merged_on': NOW})
                n_verified += 1
            else:
                e.update({'verified': False, 'new_on': NOW, 'how': 'merged with new facts',
                          'parts_verified': {old: v for (old, _), v in zip([p for p in parts if p[0] in A], verified_parts)}})
                n_open += 1
            if notes:
                e['note'], e['note_on'] = notes, NOW
            rec_new[key] = e
            entry['answers'][key] = {'from': [old for old, _ in parts if old in A], 'quotations': len(new[key]['evidence']),
                                     'verified': bool(e.get('verified'))}
        sheet['answers'] = new
        log.append(entry)
        n_sheets += 1
        if not dry:
            h = HIST / cid
            h.mkdir(parents=True, exist_ok=True)
            if not (h / 'SHEET-original.json').exists():
                (h / 'SHEET-original.json').write_text(text, encoding='utf-8')
            (h / f'SHEET-before-simplify-{STAMP}.json').write_text(text, encoding='utf-8')
            indent = re.match(r'\{\n( +)"', text)
            path.write_text(json.dumps(sheet, indent=len(indent.group(1)) if indent else 1, ensure_ascii=False) + ('\n' if text.endswith('\n') else ''), encoding='utf-8')
            old_rec = record.get(cid, {})
            record[cid] = rec_new
            record[cid]['_before_simplify'] = {k: {kk: vv for kk, vv in v.items() if kk != 'quotes'} for k, v in old_rec.items() if not k.startswith('_')}
    if not dry:
        RECORD.write_text(json.dumps(record, indent=1, ensure_ascii=False), encoding='utf-8')
        with open(LOG, 'a', encoding='utf-8') as fh:
            for e in log:
                fh.write(json.dumps({'on': NOW, **e}, ensure_ascii=False) + '\n')
    print(f"{'DRY RUN: ' if dry else ''}{n_sheets} sheets simplified; merged answers verified (every part was): {n_verified}; "
          f"awaiting the author (a part is new): {n_open}")


if __name__ == '__main__':
    main('--dry-run' in sys.argv)
