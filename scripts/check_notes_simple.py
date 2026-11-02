#!/usr/bin/env python3
"""Check the simple notes of one paper (scripts/NOTES-SIMPLE-PROTOCOL.md) against the paper itself.

Uses the corpus checker's own matching (check_notes.Pages, check_notes.find_fragment): a quotation passes when its words
run on, in order, in the text of the one page cited before it, as any extraction engine read that page. Tests: the
header names the paper; the template's sections are present, each with a statement; every statement before the reader's
section has a page citation within the paper; every quotation is on its page; the required sections quote the authors;
the summary has the template's length. Templates: simple-1 (NOTES-SIMPLE-PROTOCOL.md: 7 sections, quotes in 1, 2, 6,
summary 150-250 words), ppml-1 (NOTES-PPML-PROTOCOL.md: 6 sections, quotes in 1 and 5, summary 120-200 words) and ppml-2
(NOTES-PPML-PROTOCOL-V2.md, the rule for every downloaded paper: 8 sections by the review's layers, quotes in 1 and 7,
theme tags from fixed lists, at most 900 words of notes, summary 150-220 words with eight labelled lines). Writes notes/check.json and prints PASS or FAIL with what to correct.

    check_notes_simple.py <paper folder> [...]
"""
import json, re, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import check_notes as CN                 # noqa: E402
import notes_format as N                 # noqa: E402

INCLUDED_INDEX = Path(__file__).resolve().parent.parent / 'corpus' / 'ppmlcorpus' / 'included' / 'INDEX.csv'


def ids_of(folder: Path) -> set:
    """The ids a paper's notes may carry: its folder name, and for a study moved into corpus/ppmlcorpus/included/ (named by
    year, title and author; scripts/paper_ppml/organise_included.py) also its corpus id and the name of the folder it came from."""
    out = {folder.name}
    if INCLUDED_INDEX.exists() and folder.parent.name == 'included':
        import csv
        for r in csv.DictReader(open(INCLUDED_INDEX, encoding='utf-8')):
            if Path(r['folder']).name == folder.name:
                out |= {r['corpus_id'], Path(r['old_place']).name}
    return out

SECTIONS = {1: 'What the paper is about', 2: 'The problem it addresses', 3: 'The approach', 4: 'Evaluation and results',
            5: 'Threats and adversary model', 6: 'Limitations and future work stated by the authors',
            7: "Relevance to verifiable privacy-preserving FL on ledgers (reader's view)"}
QUOTE_REQUIRED = {1, 2, 6}
# the PhD-focused notes of the PPML review (scripts/NOTES-PPML-PROTOCOL.md): sections, sections needing a quotation,
# the reader's section (no page needed), and the words of the summary
TEMPLATES = {
    'simple-1': (SECTIONS, QUOTE_REQUIRED, 7, (150, 250)),
    'ppml-1': ({1: 'Scope and method', 2: 'Privacy techniques covered', 3: 'The PhD angles', 4: 'NG-IoT settings',
                5: 'Open problems stated by the authors', 6: "Use for the PhD (reader's view)"}, {1, 5}, 6, (120, 200)),
    # the standing rule for every downloaded paper (scripts/NOTES-PPML-PROTOCOL-V2.md): brief, by the review's five layers
    'ppml-2': ({1: 'Scope and method', 2: 'NG-IoT fabric', 3: 'Privacy plane', 4: 'Trust plane', 5: 'Attacks and defences',
                6: 'Regulatory layer', 7: 'Open problems stated by the authors', 8: "Use for the PhD and the review (reader's view)"},
               {1, 7}, 8, (150, 220)),
}
THREATS = ('poisoning backdoor byzantine-malicious sybil-fake free-riding inference malicious-server collusion dos-ddos '
           'single-point-of-failure tampering evasion other').split()
THEMES = {'layers': 'fabric privacy trust attacks regulation'.split(),
          'angles': 'poisoning malicious-fake free-riding verification zkp blockchain zk-on-chain'.split(),
          'settings': ('IoT-general IIoT IoMT-healthcare IoV-vehicular smart-grid-energy UAV-space smart-city-home maritime '
                       'supply-chain communication-network').split(),
          'mechanisms': 'DP LDP HE SMPC secret-sharing secure-aggregation TEE ZKP functional-encryption pseudonyms encryption FL-only'.split(),
          'threats_claimed': THREATS, 'threats_tested': THREATS}
SUMMARY_LINES = ['In short', 'Fabric', 'Privacy', 'Trust', 'Attacks', 'Regulation', 'Open problems', 'Use']
MAX_NOTES_WORDS = 900


def themes_of(notes: Path) -> dict:
    """The indented keys of the `themes:` block of a ppml-2 header, each a list (one line per key)."""
    out, inside = {}, False
    for line in notes.read_text(encoding='utf-8').splitlines()[1:]:
        if line.strip() == '---':
            break
        if re.match(r'^themes:\s*$', line):
            inside = True
            continue
        m = re.match(r'^\s+([a-z_]+):\s*\[(.*)\]\s*$', line) if inside else None
        if m:
            out[m.group(1)] = [v.strip().strip('"\'') for v in m.group(2).split(',') if v.strip()]
        elif inside and not line.startswith(' '):
            inside = False
    return out


def check_ppml2(folder: Path, notes: Path, summary: Path, err: list):
    th = themes_of(notes)
    for key, allowed in THEMES.items():
        if key not in th:
            err.append(f'header: themes.{key} is missing (one line, e.g. "  {key}: []")')
            continue
        bad = [v for v in th[key] if v not in allowed]
        if bad:
            err.append(f'header: themes.{key} has {bad}; allowed: {", ".join(allowed)}')
    if set(th.get('threats_tested', [])) - set(th.get('threats_claimed', [])):
        err.append('header: a tested threat is not among the claimed threats')
    if 'FL-only' in th.get('mechanisms', []) and len(th['mechanisms']) > 1:
        err.append('header: FL-only means no other mechanism; drop it or the others')
    head, _ = N.parse_header(notes.read_text(encoding='utf-8'))
    if head.get('kind') == 'survey' and th.get('threats_tested'):
        err.append('header: a survey runs no attacks; threats_tested must be []')
    text = notes.read_text(encoding='utf-8')
    body = text.split('---', 2)[2] if text.startswith('---') else text
    body = re.sub(r'"[^"]*"', ' ', body)                        # quotations are the authors' words, not the reader's
    n = len(re.findall(r"[A-Za-z0-9][\w'’-]*", re.sub(r'\[p[^\]]*\]', '', body)))
    if n > MAX_NOTES_WORDS:
        err.append(f'NOTES.md has {n} words of notes outside quotations; at most {MAX_NOTES_WORDS} (brief notes)')
    if summary.exists():
        s = summary.read_text(encoding='utf-8')
        for lab in SUMMARY_LINES:
            if not re.search(r'\*\*' + re.escape(lab) + r'\.\*\*', s):
                err.append(f'SUMMARY.md: the line "**{lab}.**" is missing')


def check(folder: Path) -> dict:
    notes, summary = folder / 'notes' / 'NOTES.md', folder / 'notes' / 'SUMMARY.md'
    err, warn = [], []
    if not notes.exists():
        return {'passed': False, 'errors': ['notes/NOTES.md does not exist'], 'warnings': []}
    pages = CN.Pages(folder)
    total = len(pages)
    header, statements, found, problems = N.parse(notes)
    template = header.get('template') if header.get('template') in TEMPLATES else 'simple-1'
    sections, quote_required, reader, (low, high) = TEMPLATES[template]
    # of the full template's structural tests only these apply to simple notes (facets, rigour items and the 17
    # sections belong to NOTES-PROTOCOL.md); the simple sections are tested below
    err += [p for p in problems if p.startswith('no header block') or p == 'sections are out of order']
    for k in ('id', 'title', 'authors', 'year', 'venue', 'doi', 'pages_total'):
        if not header.get(k):
            err.append(f'header: "{k}" is missing')
    if header.get('id') and header['id'] not in ids_of(folder):
        err.append(f'header: id "{header["id"]}" is not the folder name "{folder.name}"')
    for n, title in sections.items():
        if n not in found:
            err.append(f'section {n} ({title}) is missing')
        elif not any(s.section == n for s in statements):
            err.append(f'section {n} ({title}) has no statement')
    tested = failed = 0
    for s in statements:
        where = f'line {s.line} (section {s.section})'
        if any(p < 1 or p > total for p in s.pages):
            err.append(f'{where}: cites a page beyond the paper ({total} pages)')
        if s.section < reader and not s.pages and not s.absent and not s.text.startswith('**Not treated'):
            err.append(f'{where}: no page citation — "{s.text[:90]}"')
        checkable = 0
        for quote, cited in s.quotes:
            if not cited:
                err.append(f'{where}: quotation without a page citation before it — "{quote[:70]}"')
                continue
            if len(set(cited)) > 1:
                err.append(f'{where}: the quotation follows a citation of several pages — cite the one page it is on: "{quote[:60]}"')
                continue
            for fragment in N.fragments(quote):
                ok, remark = CN.find_fragment(fragment, pages, cited)
                if remark == 'too short to test':
                    continue
                tested += 1
                checkable += 1
                if not ok:
                    failed += 1
                    err.append(f'{where}: quotation not found on p{cited[0]} — "{fragment[:80]}" — {remark}')
        if s.section in quote_required and not s.absent and not s.image_only and not checkable:
            err.append(f'{where}: this section needs the authors\' words quoted — "{s.text[:90]}"')
    if template == 'ppml-2':
        check_ppml2(folder, notes, summary, err)
    cited = {p for s in statements for p in s.pages}
    cited |= {int(x) for s in statements if s.section == reader for x in re.findall(r'\(p(\d+)\)', s.text)}
    uncited = [p for p in range(1, total + 1) if p not in cited and len(pages.text.get(p, '').strip()) > 400]
    if uncited:
        warn.append('pages with text never cited (fine for simple notes if nothing on them matters): ' + ', '.join(f'p{p}' for p in uncited))
    if not summary.exists():
        err.append('notes/SUMMARY.md does not exist')
    else:
        body = re.sub(r'^#.*$', '', summary.read_text(encoding='utf-8'), flags=re.M)
        n = len(re.findall(r"[A-Za-z0-9][\w'’-]*", re.sub(r'\[p[^\]]*\]', '', body)))
        if not low <= n <= high:
            err.append(f'SUMMARY.md has {n} words; {low}-{high} expected')
    result = {'template': template, 'passed': not err, 'quotations_tested': tested, 'quotations_failed': failed,
              'statements': len(statements), 'errors': err, 'warnings': warn}
    (folder / 'notes' / 'check.json').write_text(json.dumps(result, indent=1, ensure_ascii=False), encoding='utf-8')
    return result


def main():
    bad = 0
    for arg in sys.argv[1:]:
        r = check(Path(arg).resolve())
        print(f"{'PASS' if r['passed'] else 'FAIL'}  {Path(arg).name}: {r.get('statements', 0)} statements, "
              f"{r.get('quotations_tested', 0)} quotations tested, {r.get('quotations_failed', 0)} not found")
        for e in r['errors'][:30]:
            print('   -', e)
        for w in r['warnings'][:5]:
            print('   (warning)', w)
        bad += not r['passed']
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
