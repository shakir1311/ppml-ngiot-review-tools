#!/usr/bin/env python3
"""The supplementary search R-S1 as the PPML review records it (made part of the recorded search by the author, 8 October 2026).

R-S1 is a regulation-first Scopus search (scripts/search_ppml/strings_regulation.py: data-protection law AND ledger AND
learning AND NG-IoT setting). Every record comes from the files in search-ppml/evidence/regulation-search/:
  exports/PROVENANCE.tsv, exports/scopus-R-S1-export_*.csv          the export, its checksum and time (UTC)
  screening/{,B/,D/}DECISIONS-*.csv, rater-1/2.jsonl, AGREEMENT.json  title-and-abstract screening by the automated screening
                                                                     tool (two blind runs; disagreements settled on the abstracts)
  fulltext/RS1-###.json                                              the tool's full-text assessment, a page and a quotation per
                                                                     condition
  AUTHOR-DECISIONS-R-S1-2026-10-08.json, AUTHOR-DECISIONS-R-S1-D-2026-10-08.json   the author's full-text decisions
A record's id is RS1-<row of the export>; an included study's corpus id is r<row, four digits> (e.g. r0043).

Used by scripts/search_ppml/prisma_report.py (the included rows of FINAL-STUDIES) and scripts/paper_ppml/data.py (the
numbers of the Method). Usage: python3 scripts/search_ppml/rs1.py   (prints the numbers)
"""
import csv, datetime, json, pathlib
from collections import Counter
from zoneinfo import ZoneInfo

csv.field_size_limit(10 ** 9)
ROOT = pathlib.Path(__file__).resolve().parents[2]
EV = ROOT / 'search-ppml' / 'evidence' / 'regulation-search'
SCR = EV / 'screening'
BATCHES = [(SCR, 'DECISIONS-A-C.csv'), (SCR / 'B', 'DECISIONS-B.csv'), (SCR / 'D', 'DECISIONS-D.csv'),
           (SCR / 'E', 'DECISIONS-E.csv')]          # E: returned by the main searches but set aside there by an automated rule, unscreened
AUTHOR = [EV / 'AUTHOR-DECISIONS-R-S1-2026-10-08.json', EV / 'AUTHOR-DECISIONS-R-S1-D-2026-10-08.json']
VIA = 'supplementary search (R-S1)'
cid = lambda rid: f"r{int(rid.split('-')[1]):04d}"


def read(p, **kw):
    return list(csv.DictReader(open(p, encoding='utf-8-sig'), **kw))


def provenance():
    return next(p for p in read(EV / 'exports' / 'PROVENANCE.tsv', delimiter='\t') if p['search'].startswith('Scopus R-S1'))


def export_rows():
    return read(EV / 'exports' / provenance()['file'])


def screening():
    """{record id: final title-and-abstract decision row}; every record new to the review's search, in three batches"""
    out = {}
    for d, f in BATCHES:
        for r in read(d / f):
            out[r['n']] = r
    return out


def raters():
    a, b = {}, {}
    for d, _ in BATCHES:
        for f, into in (('rater-1.jsonl', a), ('rater-2.jsonl', b)):
            for l in (d / f).read_text(encoding='utf-8').splitlines():
                if l.strip():
                    x = json.loads(l)
                    into[x['n']] = x['decision']
    return a, b


def author():
    """{record id: {'proposed', 'code', 'author', 'note'?}}, and {record id: why not retrieved}"""
    dec, nr = {}, {}
    for f in AUTHOR:
        j = json.loads(f.read_text(encoding='utf-8'))
        dec.update(j['fulltext_decisions'])
        nr.update(j.get('not_retrieved', {}))
    return dec, nr


def fulltext(rid):
    return json.loads((EV / 'fulltext' / f'{rid}.json').read_text(encoding='utf-8'))


def included():
    """the studies the author included at full text, as rows for FINAL-STUDIES (cue columns are filled by prisma_report.py)"""
    dec, _ = author()
    scr = screening()
    text = {}
    for d, _ in BATCHES:
        for l in (d / 'input.jsonl').read_text(encoding='utf-8').splitlines():
            if l.strip():
                x = json.loads(l)
                text[x['n']] = ' '.join([x['title'], x.get('abstract', ''), x.get('keywords', '')])
    rows = []
    for rid in sorted(dec):
        if dec[rid]['author'] != 'INCLUDE':
            continue
        r, ft = scr[rid], fulltext(rid)
        folder = ROOT / 'corpus' / 'ppmlcorpus' / 'check-rs1' / rid
        rows.append({'n': rid, 'corpus_id': cid(rid), 'kind': ft['kind'], 'year': r['year'], 'title': r['title'], 'venue': r['venue'],
                     'doi': r['doi'], 'via': VIA, 'angles': '; '.join(ft['conditions']['IC3'].get('parts', [])), 'zk_proves': '',
                     'abstract_text': text[rid], 'summary': str((folder / 'notes' / 'SUMMARY.md').relative_to(ROOT))})
    return rows


def stats():
    s = {}
    prov = provenance()
    t = datetime.datetime.fromisoformat(prov['exported_utc']).replace(tzinfo=datetime.timezone.utc).astimezone(ZoneInfo('Europe/London'))
    s['rs1_date'] = f'{t.day} {t:%B %Y}'                     # local date, as the main searches' searched_local_time
    s['rs1_records'] = int(prov['rows'])
    assert len(export_rows()) == s['rs1_records']
    scr = screening()
    s['rs1_tool_screened'] = len(scr)                            # screened at title and abstract by the tool
    s['rs1_aside'] = sum(r['group'] == 'E' for r in scr.values())  # returned by the main searches, set aside there before screening
    s['rs1_new'] = s['rs1_tool_screened'] - s['rs1_aside']        # not returned by the main searches
    s['rs1_already'] = s['rs1_records'] - s['rs1_new']           # returned by the review's searches already
    s['rs1_already_screened'] = s['rs1_already'] - s['rs1_aside']  # and screened with them
    a, b = raters()
    assert set(a) == set(b) == set(scr)
    n = len(scr)
    po = sum(a[x] == b[x] for x in scr) / n
    pe = sum((sum(a[x] == c for x in scr) / n) * (sum(b[x] == c for x in scr) / n) for c in ('INCLUDE', 'UNSURE', 'EXCLUDE'))
    s['rs1_agree'] = sum(a[x] == b[x] for x in scr)
    s['rs1_agree_pct'] = round(100 * po, 1)
    s['rs1_kappa'] = f'{(po - pe) / (1 - pe):.2f}'
    s['rs1_reconciled'] = sum(r['decided_by'].startswith('reconciled') for r in scr.values())
    assert s['rs1_reconciled'] == n - s['rs1_agree']
    ta = Counter(r['ai_decision'] for r in scr.values())
    s['rs1_ta_include'], s['rs1_ta_unsure'], s['rs1_ta_excluded'] = ta['INCLUDE'], ta['UNSURE'], ta['EXCLUDE']
    for c, v in Counter(r['ai_code'] for r in scr.values() if r['ai_decision'] == 'EXCLUDE').items():
        s[f'rs1_ta_ex_{c.lower().replace("-", "_")}'] = v
    dec, nr = author()
    sought = {x for x, r in scr.items() if r['ai_decision'] in ('INCLUDE', 'UNSURE')}
    assert set(dec) | set(nr) == sought, (sorted(sought - set(dec) - set(nr)), sorted(set(dec) | set(nr) - sought))
    s['rs1_sought'] = len(sought)
    s['rs1_not_retrieved'] = len(nr)
    s['rs1_not_downloaded'] = sum(str(v).startswith('not downloaded') for v in nr.values())
    s['rs1_unavailable'] = s['rs1_not_retrieved'] - s['rs1_not_downloaded']
    s['rs1_assessed'] = len(dec)
    s['rs1_proposed_include'] = sum(d['proposed'] == 'INCLUDE' for d in dec.values())
    s['rs1_included'] = sum(d['author'] == 'INCLUDE' for d in dec.values())
    s['rs1_excluded'] = sum(d['author'] == 'EXCLUDE' for d in dec.values())
    s['rs1_author_dropped'] = sum(d['proposed'] == 'INCLUDE' and d['author'] == 'EXCLUDE' for d in dec.values())
    s['rs1_author_reinstated'] = sum(d['proposed'] == 'EXCLUDE' and d['author'] == 'INCLUDE' for d in dec.values())
    for c, v in Counter(d['code'] for d in dec.values() if d['author'] == 'EXCLUDE').items():
        s[f'rs1_ex_{c.lower().replace("-", "_")}'] = v
    kinds = Counter(fulltext(x)['kind'] for x, d in dec.items() if d['author'] == 'INCLUDE')
    s['rs1_primary'], s['rs1_secondary'] = kinds['primary'], kinds['secondary']
    assert s['rs1_included'] + s['rs1_excluded'] == s['rs1_assessed']
    assert s['rs1_assessed'] + s['rs1_not_retrieved'] == s['rs1_sought']
    return s


if __name__ == '__main__':
    print(json.dumps(stats(), indent=1))
    print([r['corpus_id'] for r in included()])
