#!/usr/bin/env python3
"""Re-anchor an extraction record to the published version of a study (search-ppml/evidence/PUBLISHED-VERSIONS.json):
S026 (5 October 2026, read first as the arXiv preprint); O078 and n3102 (7 October 2026; file_published.py runs this).

Each quotation is searched on every page of the published text (the same matching as check_sheets.py); its page is set
to the published page (the nearest to the old page where it occurs on several). Quotations whose wording changed in the
published version are replaced by the published wording given below, found on their page by the same check. Old and new
values are logged in search-ppml/evidence/SHEET-CORRECTIONS-2026-10-05.json; the record notes the version it rests on.

Usage: python3 scripts/paper_ppml/reanchor_published.py S026
"""
import datetime, json, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import check_sheets as CS                                # noqa: E402

REWORDED = {   # (item, old start) -> (page, published wording), read on the published pages
    'S026': [('S1', 'several kinds of schemes are excluded from our coverage', 14, 'several types of schemes are excluded from our coverage due to their limited contribution to the ZKP-VML issue'),
             ('S8', 'It is worth mentioning that several kinds of schemes are excluded', 14, 'It is worth noting that several types of schemes are excluded from our coverage due to their limited contribution to the ZKP-VML issue'),
             ('S2', 'When the performer acts as an attacker, integrity attacks are executed', 12, 'When the performer acts as an attacker, they may carry out integrity attacks. Integrity attacks introduce errors into the computation process'),
             ('S6', 'For the neural network model VGG16 [48] with 138M parameters', 13, 'For the neural network model VGG16 [48] with 138M parameters, the proof generation time may reach an impractical duration of 10 years.'),
             ('S7', 'Besides, ZKP-VML are still relatively slow for real-time applications', 34, 'Besides, ZKP-VML schemes are still relatively slow for real-time applications.')]}


def main(cid):
    over = json.loads((ROOT / 'search-ppml' / 'evidence' / 'PUBLISHED-VERSIONS.json').read_text(encoding='utf-8'))
    pages_dir = ROOT / over[cid] / 'text' / 'pages'
    pages = {int(p.stem.split('_')[1]): p.read_text(encoding='utf-8', errors='ignore') for p in pages_dir.glob('page_*.txt')}
    f = ROOT / 'search-ppml' / 'evidence' / 'sheets' / f'{cid}.json'
    s = json.loads(f.read_text(encoding='utf-8'))
    log, now, moved, replaced, missing = [], datetime.datetime.now().isoformat(timespec='seconds'), 0, 0, []
    for k, a in s['answers'].items():
        for e in a.get('evidence', []):
            if e.get('source') in ('table', 'image'):
                continue
            rw = next((r for r in REWORDED.get(cid, []) if r[0] == k and e['quote'].startswith(r[1])), None)
            if rw:
                old = dict(e)
                e['page'], e['quote'] = rw[2], rw[3]
                if not CS.found(e['quote'], pages[e['page']]):
                    missing.append((k, e['quote'][:60]))
                log.append({'time': now, 'id': cid, 'key': k, 'field': 'evidence', 'old': old, 'new': dict(e), 'why': 'published wording'})
                replaced += 1
                continue
            hits = [pg for pg, t in pages.items() if CS.found(e['quote'], t)]
            if not hits:
                missing.append((k, e['quote'][:60]))
                continue
            new = min(hits, key=lambda pg: abs(pg - int(e['page'])))
            if new != int(e['page']):
                log.append({'time': now, 'id': cid, 'key': k, 'field': 'evidence.page', 'old': e['page'], 'new': new, 'why': 'page of the published version'})
                e['page'] = new
                moved += 1
    s['source_version'] = f'published version ({over[cid]})'
    if cid == 'S026':
        note = ' Re-anchored 5 Oct 2026 to the published version (IEEE COMST 2026): pages are its PDF pages; five quotations reworded in the published text were replaced by the published wording.'
    else:
        note = (f' Re-anchored {now[:10]} to the published version ({over[cid]}): pages are its PDF pages'
                + (f'; {replaced} quotations reworded in the published text were replaced by the published wording' if replaced else '')
                + (f'; {len(missing)} quotations to be replaced by the published wording' if missing else '') + '.')
    s['remarks'] = (s.get('remarks', '') + note).strip()
    f.write_text(json.dumps(s, indent=1, ensure_ascii=False), encoding='utf-8')
    L = ROOT / 'search-ppml' / 'evidence' / 'SHEET-CORRECTIONS-2026-10-05.json'
    done = json.loads(L.read_text(encoding='utf-8')) if L.exists() else []
    L.write_text(json.dumps(done + log, indent=1, ensure_ascii=False), encoding='utf-8')
    print(f'{cid}: {moved} pages moved, {replaced} quotations replaced, {len(missing)} not found on any published page')
    for k, q in missing:
        print(f'   not found: {k}: {q}')


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else sys.exit(__doc__))
