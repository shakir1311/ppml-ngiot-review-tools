#!/usr/bin/env python3
"""Size of candidate searches for a primary-study arm of the PPML review (4 October 2026), from OpenAlex counts.

The author (4 October 2026): "let us broaden our search so that my paper gives coverage to both primary and secondary
studies". Before strings are proposed, each candidate is sized. OpenAlex is used for counts only (no records are kept;
no e-mail address is sent). It searches title and abstract (not keywords), stems words and has gaps in abstracts, so its
counts are not Scopus counts; the ratio between Scopus and OpenAlex is taken from the survey arm already run in Scopus
(P-S1 v3, 1,938 records) and applied to the candidates as an estimate.

Output: search-ppml/SIZE-PROBE-2026-10-04.json

Usage: python3 scripts/search_ppml/size_probe.py
"""
import json, pathlib, sys, time, urllib.parse, urllib.request

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import strings as S                                   # noqa: E402

P = pathlib.Path(__file__).resolve().parents[2] / 'search-ppml'
BASE = 'https://api.openalex.org/works'
COMMON = 'publication_year:2020-2026,language:en,type:article|review,primary_location.source.type:journal|conference'
THREAT = ['poisoning', 'byzantine', 'backdoor', 'sybil', 'malicious', '"free-riding"', '"free rider"', '"free-rider"',
          '"fake node"', '"fake client"', '"model integrity"', 'verifiable']


def oa(terms):
    """an OR group in OpenAlex syntax: no wildcards (OpenAlex stems), both spellings where ? stood for a letter"""
    out = []
    for t in terms:
        t = t.replace('*', '')
        if '?' in t:
            out += [t.replace('?', 's'), t.replace('?', 'z')]
        else:
            out.append(t)
    return '(' + ' OR '.join(out) + ')'


def count(filters):
    url = BASE + '?' + urllib.parse.urlencode({'filter': COMMON + ',' + ','.join(filters), 'per-page': 1, 'select': 'id'})
    req = urllib.request.Request(url, headers={'User-Agent': 'slr-size-probe/1.0'})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.load(r)['meta']['count']
        except Exception as e:                        # noqa: BLE001
            last = e
            time.sleep(2 + 3 * attempt)
    raise last


def main():
    ta = lambda g: f'title_and_abstract.search:{oa(g)}'
    ti = lambda g: f'title.search:{oa(g)}'
    probes = {
        'survey arm as run (calibration: Scopus P-S1 v3 = 1,938)': [ti(S.SUR), ta(S.PPML), ta(S.ML), ta(S.NGIOT)],
        'A  privacy in title, learning and NG-IoT in title or abstract': [ti(S.PPML), ta(S.ML), ta(S.NGIOT)],
        'B  as A, and a threat of the PhD (poisoning, Byzantine, Sybil, free riding, malicious, verifiable) in title or abstract':
            [ti(S.PPML), ta(S.ML), ta(S.NGIOT), ta(THREAT)],
        'C  privacy, learning, NG-IoT and a threat, all in title or abstract': [ta(S.PPML), ta(S.ML), ta(S.NGIOT), ta(THREAT)],
        'D  privacy, learning and NG-IoT in title or abstract (no further limit)': [ta(S.PPML), ta(S.ML), ta(S.NGIOT)],
        'A 2023-2026  as A, published 2023 to 2026 only': [ti(S.PPML), ta(S.ML), ta(S.NGIOT), 'publication_year:2023-2026'],
        'C 2023-2026  as C, published 2023 to 2026 only': [ta(S.PPML), ta(S.ML), ta(S.NGIOT), ta(THREAT), 'publication_year:2023-2026'],
    }
    out = {}
    for name, f in probes.items():
        out[name] = {'all': count(f), 'journals': count(f + ['primary_location.source.type:journal'])}
        time.sleep(0.5)
    ratio = 1938 / out['survey arm as run (calibration: Scopus P-S1 v3 = 1,938)']['all']
    for v in out.values():
        v['scopus_estimate'] = round(v['all'] * ratio, -1)
    res = {'date': '2026-10-04', 'source': 'OpenAlex counts (title and abstract), 2020-2026, English, journal or conference',
           'scopus_to_openalex_ratio': round(ratio, 2), 'probes': out}
    (P / 'SIZE-PROBE-2026-10-04.json').write_text(json.dumps(res, indent=1), encoding='utf-8')
    print(json.dumps(res, indent=1))


if __name__ == '__main__':
    main()
