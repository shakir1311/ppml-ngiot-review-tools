#!/usr/bin/env python3
"""Map the numbered references of a corpus paper to corpus IDs.

For paper B, the reference list is read from its extracted text (text/full.txt): the section after the last
reference heading, split on the reference numbers ("[12]" or "12."). Each entry is matched against the titles of the
corpus papers (from the front matter of their notes/NOTES.md), compared as letters and digits only, which joins words
split by line-break hyphens: the corpus title found whole in the entry; or a title of the entry (a quoted part or one
of its sentences) with similarity 0.9 to it; or, for a preprint or conference version under another title, the same
first author and similarity 0.75. Author-year lists have no numbers: there, corpus titles are looked for whole in the
reference section. The output lists, for each reference of B that is a corpus paper, its number, the corpus ID and
how it matched; the links between the papers are then recorded from B's notes (LINKS-PROTOCOL.md).

Usage: scripts/.venv/bin/python scripts/review/ref_links.py ID [ID ...]      (prints JSON)
"""
import difflib, json, pathlib, re, sys, unicodedata

ROOT = pathlib.Path(__file__).resolve().parents[2]
CORPUS = ROOT / 'corpus'


def compact(s):
    """letters and digits only, accents dropped: joins words split by line-break hyphens ("Ro- bustness")"""
    s = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode()
    return re.sub(r'[^a-z0-9]', '', s.lower())


def coverage(title, entry):
    """share of the title found in the entry in runs of at least four characters"""
    m = difflib.SequenceMatcher(None, title, entry, autojunk=False)
    return sum(b.size for b in m.get_matching_blocks() if b.size >= 4) / max(len(title), 1)


def manifest():
    m = json.loads((CORPUS / '_extraction' / 'MANIFEST.json').read_text())
    return {e['id']: e for e in (m if isinstance(m, list) else m.get('papers', m.get('items', [])))}


def front(folder):
    """title, year and first author's surname from the front matter of NOTES.md"""
    t = (folder / 'notes' / 'NOTES.md').read_text(encoding='utf-8')
    fm = t.split('\n---', 1)[0] if t.startswith('---') else ''
    get = lambda k: (re.search(rf'^{k}:\s*"?(.*?)"?\s*$', fm, re.M) or [None, ''])[1]
    authors = get('authors')
    first = re.split(r'[,;]| and ', authors)[0].strip().split(' ')[-1] if authors else ''
    return {'title': get('title'), 'year': get('year'), 'first_author': first}


def corpus_titles():
    out = {}
    for pid, e in manifest().items():
        f = CORPUS / e['folder']
        if (f / 'notes' / 'NOTES.md').exists():
            out[pid] = front(f)
    return out


HEADING = re.compile(r'^\s*(?:[IVX]+\.|\d{1,2}\.?)?\s*(?:References(?: and Notes)?|REFERENCES(?: AND NOTES)?|Bibliography|'
                     r'BIBLIOGRAPHY|Literature Cited|LITERATURE CITED)\s*$', re.M)


def reference_sections(folder):
    """the text after the last and after the first reference heading (Nature-style papers split their list in two);
    failing a heading, the last third of the paper"""
    t = (folder / 'text' / 'full.txt').read_text(encoding='utf-8', errors='replace')
    heads = list(HEADING.finditer(t))
    if not heads:
        return [t[2 * len(t) // 3:]]
    return list(dict.fromkeys([t[heads[-1].end():], t[heads[0].end():]]))


def numbered(body, pattern):
    parts = re.split(pattern, body)
    refs = {}
    for k in range(1, len(parts) - 1, 2):
        n = int(parts[k])
        if n not in refs:                       # the first entry with a number wins (later ones are appendices)
            refs[n] = re.sub(r'\s+', ' ', parts[k + 1]).strip()[:600]
    # a true reference list counts up with few gaps (from 1, or from where a split list resumes)
    start = min(refs, default=0)
    run = sum(1 for n in range(start, start + len(refs)) if n in refs)
    return refs if len(refs) >= 5 and run >= 0.8 * len(refs) else {}


def numbered_run(text, pattern):
    """a list numbered 1, 2, 3 … anywhere in the text (Nature-style papers print it without a heading, before the
    methods): the longest run of entries whose numbers rise by one, each within 1,500 characters of the last"""
    marks = [(int(m.group(1)), m.start(), m.end()) for m in re.finditer(pattern, text)]
    best = []
    for k, (n, s, e) in enumerate(marks):
        if n != 1:
            continue
        run, last = [(n, s, e)], (n, e)
        for n2, s2, e2 in marks[k + 1:]:
            if s2 - last[1] > 1500:
                break
            if n2 == last[0] + 1:
                run.append((n2, s2, e2))
                last = (n2, e2)
        if len(run) > len(best):
            best = run
    if len(best) < 5:
        return {}
    refs = {}
    for i, (n, s, e) in enumerate(best):
        end = best[i + 1][1] if i + 1 < len(best) else e + 600
        refs[n] = re.sub(r'\s+', ' ', text[e:end]).strip()[:600]
    return refs


def reference_list(folder):
    """{number: entry} for numbered lists ("[12]" or "12."); {0: whole section} for author-year lists"""
    sections = reference_sections(folder)
    patterns = (r'(?:^|\n)\s*\[(\d{1,3})\]\s*', r'(?:^|\n)\s*(\d{1,3})\.\s+')
    best = {}
    for body in sections:
        for pattern in patterns:
            refs = numbered(body, pattern)
            if len(refs) > len(best):
                best = refs
    if len(best) < 5:                           # no list after a heading: look for a numbered run anywhere
        text = (folder / 'text' / 'full.txt').read_text(encoding='utf-8', errors='replace')
        for pattern in patterns:
            refs = numbered_run(text, pattern)
            if len(refs) > len(best):
                best = refs
    return best or {0: re.sub(r'\s+', ' ', sections[-1])}


def title_segments(entry):
    """the parts of an entry that may be its title: quoted text, and the sentences of the entry"""
    segs = re.findall(r'[“"](.{10,300}?)[”"]', entry)
    segs += [s for s in re.split(r'(?<=[a-z0-9)\]])\.\s+', entry[:400]) if len(s) >= 10]
    return segs


def match(entry, titles, self_id):
    """corpus ID of a numbered entry, by (1) the whole title found in it, (2) a near-identical title (similarity
    0.9), or (3) the same first author and a similar title (0.75): a preprint or conference version under another
    title. Titles are compared with titles, not with the whole entry."""
    e = compact(entry)
    segs = [compact(s) for s in title_segments(entry)]
    best = None
    for pid, f in titles.items():
        if pid == self_id or not f['title']:
            continue
        ct = compact(f['title'])
        if len(ct) >= 15 and ct in e:
            return pid, 'title found in entry'
        r = max((difflib.SequenceMatcher(None, ct, s, autojunk=False).ratio() for s in segs), default=0)
        same_author = bool(f['first_author']) and compact(f['first_author']) in compact(entry[:160])
        if r >= 0.9 or (same_author and r >= 0.75):
            how = f'title similarity {r:.2f}' + (', same first author' if same_author else '')
            if best is None or r > best[1]:
                best = (pid, r, how)
    return (best[0], best[2]) if best else (None, '')


def match_section(section, titles, self_id):
    """author-year lists: corpus titles found whole in the reference section"""
    s = compact(section)
    return [(pid, 'title found in reference section') for pid, f in titles.items()
            if pid != self_id and f['title'] and len(compact(f['title'])) >= 15 and compact(f['title']) in s]


def links(pid, titles=None, by=None):
    by = by or manifest()
    titles = titles or corpus_titles()
    refs = reference_list(CORPUS / by[pid]['folder'])
    found = []
    if list(refs) == [0]:                       # author-year: no numbers to give
        for cid, how in match_section(refs[0], titles, pid):
            found.append({'ref': None, 'corpus_id': cid, 'how': how, 'title': titles[cid]['title'], 'entry': ''})
        return {'id': pid, 'references_parsed': 0, 'style': 'author-year', 'in_corpus': found}
    for n, entry in sorted(refs.items()):
        cid, how = match(entry, titles, pid)
        if cid:
            found.append({'ref': n, 'corpus_id': cid, 'how': how, 'title': titles[cid]['title'], 'entry': entry[:160]})
    return {'id': pid, 'references_parsed': len(refs), 'style': 'numbered', 'in_corpus': found}


if __name__ == '__main__':
    by = manifest()
    titles = corpus_titles()
    print(json.dumps([links(i, titles, by) for i in sys.argv[1:]], ensure_ascii=False, indent=1))
