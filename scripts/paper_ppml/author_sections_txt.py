#!/usr/bin/env python3
"""Plain-text copies of the author's four sections of a built version, for the author to rewrite in their own words (the author,
2 November 2026: "give me all of these as txt files in a folder - and i will place updated txts in same folder"). Reads
build/paper-V<n>.md and writes myliteraturereviewpaper/ppml2026/author-rewrite-V<n+1>/: the abstract, Section I (Introduction,
its subsections and its Key Takeaways box), Section VI (Discussion and its Key Takeaways box) and Section VIII (Conclusion), one
file each as plain text with the citation numbers kept; tables and figures appear as one bracketed line where they sit. Also the
fact skeleton of the abstract and introduction (Section 8 of Docs/AI-DETECTION-ABSTRACT-INTRO-V80-V2-2026-10-19.html), with the
build's tokens removed and its counts filled from build/stats.json, and a README. A file already in the folder is never
overwritten (the author's own files sit beside these).

Usage: python3 scripts/paper_ppml/author_sections_txt.py <version>
"""
import html, json, pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
PPML = ROOT / 'myliteraturereviewpaper' / 'ppml2026'
BUILD = PPML / 'build'
SKELETON = ROOT / 'Docs' / 'AI-DETECTION-ABSTRACT-INTRO-V80-V2-2026-10-19.html'

# file stem -> the top-level heading of the section in the build ('Abstract' is the front-matter paragraph)
SECTIONS = [('01-abstract', 'Abstract'), ('02-introduction', 'I. Introduction'),
            ('03-discussion', 'VI. Discussion'), ('04-conclusion', 'VIII. Conclusion')]


def top_sections(md):
    """The build's top-level sections, keyed by heading, each the list of its lines."""
    out, name = {}, None
    for line in md.splitlines():
        if line.startswith('# '):
            name = line[2:].strip()
            out[name] = []
        elif name:
            out[name].append(line)
    return out


def abstract(md):
    m = re.search(r'^\*\*Abstract\*\* — (.+)$', md, re.M)
    return m.group(1).strip() + '\n'


def key_takeaways(block):
    texts = [html.unescape(t) for t in re.findall(r'<w:t(?: [^>]*)?>([^<]*)</w:t>', block)]
    return ['Key Takeaways'] + ['- ' + t for t in texts if t not in ('•', 'Key Takeaways')]


def plain(text):
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    return re.sub(r'(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])', r'\1', text)


def section_text(heading, lines):
    """One section as plain text: headings, paragraphs and lists kept; Key Takeaways boxes as bullets; tables and figures as
    a bracketed line where they sit."""
    out, i = [heading, ''], 0
    while i < len(lines):
        line = lines[i]
        if line.startswith('```{=openxml}'):
            j = i + 1
            while not lines[j].startswith('```'): j += 1
            block = '\n'.join(lines[i + 1:j])
            out += key_takeaways(block) + [''] if 'Key Takeaways' in block else []
            i = j + 1
            continue
        if line.startswith('Table: '):
            number = re.match(r'Table: (Table [IVXLC]+)', line).group(1)
            out += [f'[{number} sits here; not part of the rewrite]', '']
            i += 1
            while i < len(lines) and (not lines[i].strip() or lines[i].startswith('|')): i += 1
            continue
        m = re.match(r'!\[(Fig\. \d+)\.', line)
        if m:
            out += [f'[{m.group(1)} sits here; not part of the rewrite]', '']
        elif line.startswith('## '):
            out += [line[3:].strip(), '']
        elif line.strip():
            out.append(plain(line.rstrip()))
            nxt = lines[i + 1] if i + 1 < len(lines) else ''
            if not (re.match(r'\s*(- |\d+\. )', line) and re.match(r'\s*(- |\d+\. )', nxt)): out.append('')
        i += 1
    return re.sub(r'\n{3,}', '\n\n', '\n'.join(out)).strip() + '\n'


def fact_skeleton(stats, version):
    """Section 8 of the report as plain text, without the build's tokens, with the counts of the version's records."""
    page = SKELETON.read_text()
    s = page[page.index('8. The way forward'):]
    s = s[:s.index('Where to write it')]
    s = re.sub(r'<(script|style)[^>]*>.*?</\1>', '', s, flags=re.S)
    s = re.sub(r'</(p|li|h2|h3|div)>', '\n', s)
    s = re.sub(r'<li[^>]*>', '- ', s)
    s = html.unescape(re.sub(r'<[^>]+>', '', s))
    s = re.sub(r'\{\{N:(\w+)\}\}', lambda m: str(stats[m.group(1)]), s)
    s = s.replace('{{FIG:roadmap}}', 'Fig. 1')
    s = re.sub(r'Citation keys are the build\'s \(\[@key\]\); the numbers are the reference numbers of V80\.\s*',
               f'The numbers in square brackets are the reference numbers, the same in V{version}. ', s)
    s = re.sub(r'The foundation markers ⟦F:…⟧ stay with their claims\.\s*', '', s)
    # the wording of SQ1 to SQ3 is kept (20 October 2026); the box stays the author's to reword
    s = s.replace('SQ1 to SQ3 and the "Key Takeaways" box are the author\'s to reword or keep.',
                  'The "Key Takeaways" box is the author\'s to reword; SQ1 to SQ3 keep their wording.')
    s = re.sub(r'\s*\[@[^\]]+\]', '', s)
    s = re.sub(r'\s*⟦F:[^⟧]*⟧', '', s)
    s = re.sub(r'[ \t]+\n', '\n', s)
    s = re.sub(r'\n\s*\n+', '\n\n', s).strip()
    return (f'Reference only (not to be returned): the facts the abstract and the introduction are written from, with the '
            f'counts of V{version}.\n\n' + s + '\n')


def readme(version):
    nxt = version + 1
    return f"""Your four sections of V{version}, to rewrite in your own words.

  01-abstract-V{version}.txt       the abstract (from the fact skeleton)
  02-introduction-V{version}.txt   Section I, subsections A to D and its Key Takeaways box (from the fact skeleton)
  03-discussion-V{version}.txt     Section VI, subsections A and B and its Key Takeaways box (start from the text as it stands)
  04-conclusion-V{version}.txt     Section VIII (start from the text as it stands)
  00-fact-skeleton-abstract-and-introduction.txt   reference only

Put your versions in this folder under the same names with V{nxt} in place of V{version}, for example 01-abstract-V{nxt}.txt.
Leave the V{version} files as they are; V{nxt} is built by comparing yours with them.

So that your text goes into the build intact:
- Keep the citation numbers in square brackets where the claims are; they are mapped back to the references.
- Keep the counts as they stand; the build computes them from the records and the claims audit checks them.
- Keep the wording of SQ1 to SQ3 in the introduction as it stands, or the claims audit raises it.
- Lines in square brackets such as [Fig. 1 sits here; not part of the rewrite] mark a figure or table; leave them where they
  belong in your text.
- Plain text is enough; no formatting needed. Abbreviations and banned words are checked when your text goes in.
"""


def write_new(path, text, written, kept):
    if path.exists():
        kept.append(path.name)
    else:
        path.write_text(text, encoding='utf-8')
        written.append(path.name)


def main(version):
    md = (BUILD / f'paper-V{version}.md').read_text()
    stats = json.loads((BUILD / 'stats.json').read_text())
    sections = top_sections(md)
    out = PPML / f'author-rewrite-V{version + 1}'
    out.mkdir(exist_ok=True)
    written, kept = [], []
    for stem, heading in SECTIONS:
        text = abstract(md) if heading == 'Abstract' else section_text(heading, sections[heading])
        write_new(out / f'{stem}-V{version}.txt', text, written, kept)
    write_new(out / '00-fact-skeleton-abstract-and-introduction.txt', fact_skeleton(stats, version), written, kept)
    write_new(out / '00-README.txt', readme(version), written, kept)
    print(f'{out.relative_to(ROOT)}: {len(written)} written, {len(kept)} already there and left alone')
    for name in written: print('  wrote', name)
    for name in kept: print('  kept ', name)


if __name__ == '__main__':
    main(int(sys.argv[1]))
