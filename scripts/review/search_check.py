#!/usr/bin/env python3
"""Sensitivity check of the review's search strings against its included studies.

Each of the four strings (the keyword groups of scripts/review/search_counts.py) is applied to the title, the author
keywords and the first page (abstract and index terms) of every included study; a study counts as retrieved when
its text satisfies the Boolean string. Matching ignores case, and a single word also matches its plural.

Usage: scripts/.venv/bin/python scripts/review/search_check.py <screening.json> <out.json>
"""
import csv, json, pathlib, re, sys
from search_counts import GROUPS

ROOT = pathlib.Path(__file__).resolve().parents[2]
EXT = ROOT / 'corpus' / '_extraction'
csv.field_size_limit(10 ** 9)


def terms(g):
    return [t.strip('"') for t in re.findall(r'"[^"]+"|[^\s()]+', GROUPS[g]) if t != 'OR']


def has(text, term):
    t = re.escape(term.lower()).replace(r'\-', r'[-\s]?').replace(r'\ ', r'[-\s]+')
    return re.search(rf'(?<![a-z0-9]){t}s?(?![a-z0-9])', text) is not None


def group(text, g):
    return any(has(text, t) for t in terms(g))


STRINGS = {
    '1': lambda x: group(x, 'L') and (group(x, 'P') or group(x, 'A')),
    '2': lambda x: group(x, 'B') and (group(x, 'L') or group(x, 'P')),
    '3': lambda x: group(x, 'T') and group(x, 'S'),
    '4': lambda x: group(x, 'G') and (group(x, 'B') or group(x, 'L')),
}


def main(screening, out):
    excluded = json.loads(pathlib.Path(screening).read_text())['excluded']
    papers = [p for p in csv.DictReader(open(EXT / 'papers.csv', encoding='utf-8')) if p['id'] not in excluded]
    per, hit, missed = {k: 0 for k in STRINGS}, 0, []
    for p in papers:
        first = ROOT / 'corpus' / p['folder'] / 'text' / 'pages' / 'page_0001.txt'
        text = ' '.join([p['title'], p['keywords_authors'], first.read_text(encoding='utf-8', errors='ignore')]).lower()
        found = [k for k, f in STRINGS.items() if f(text)]
        for k in found:
            per[k] += 1
        if found:
            hit += 1
        else:
            missed.append(p['id'])
    res = {'note': 'Sensitivity check of the search strings: each string applied to the title, author keywords and '
                   'first page (abstract and index terms) of every included study.',
           'per_string': per, 'combined': hit, 'n': len(papers), 'missed': missed}
    pathlib.Path(out).write_text(json.dumps(res, indent=1), encoding='utf-8')
    print(json.dumps(res))


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
