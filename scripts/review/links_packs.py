#!/usr/bin/env python3
"""Build the input pack for recording a paper's links to earlier work (LINKS-PROTOCOL.md).

A pack holds the paper's corpus references (from ref_links.py) and the statements of its notes/NOTES.md that bear on
links: the sections on approach, results, limitations, positioning and rigour whole, and from the other sections the
statements that cite a corpus reference or compare with a baseline.

Usage: scripts/.venv/bin/python scripts/review/links_packs.py OUT_DIR [ID ...]      (default: every primary study)
"""
import json, pathlib, re, sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
sys.path.insert(0, str(pathlib.Path(__file__).parents[1]))
import ref_links as RL          # noqa: E402
import check_links as CL        # noqa: E402

WHOLE = ('4.', '7.', '8.', '13.', '15.')           # approach, results, limitations, positioning, rigour
COMPARE = re.compile(r'\b(baselines?|compar\w*|outperform\w*|than|improv\w*|faster|slower|versus|vs\.?|'
                     r'speed-?up|overhead of|state of the art|prior work|previous work|existing)\b', re.I)


def sections(notes):
    """[(heading, [lines])] of NOTES.md, split at '## ' headings"""
    out, cur = [], ('', [])
    for line in notes.split('\n'):
        if line.startswith('## '):
            out.append(cur)
            cur = (line[3:].strip(), [])
        else:
            cur[1].append(line)
    out.append(cur)
    return out


def pack(pid, titles, by):
    m = RL.links(pid, titles, by)
    folder = RL.CORPUS / by[pid]['folder']
    notes = (folder / 'notes' / 'NOTES.md').read_text(encoding='utf-8')
    refs = m['in_corpus']
    nums = [str(f['ref']) for f in refs if f['ref'] is not None]
    authors = [titles[f['corpus_id']]['first_author'] for f in refs if titles[f['corpus_id']]['first_author']]
    cite = re.compile(r'\[(?:\d+\s*[,–-]\s*)*(' + '|'.join(nums) + r')(?:\s*[,–-]\s*\d+)*\]') if nums else None
    name = re.compile(r'\b(' + '|'.join(map(re.escape, authors)) + r')\b') if authors else None
    lines = [f"# Links pack · {pid} · {titles[pid]['title']} ({titles[pid]['year']})", '',
             f"Folder: `{folder.relative_to(RL.ROOT)}`  ", f"Pages: {by[pid].get('pages', '?')}  ",
             f"Reference style: {m['style']} ({m['references_parsed']} numbered entries parsed)", '',
             '## Corpus papers in its reference list', '']
    if refs:
        for f in refs:
            lines.append(f"- [{f['ref'] if f['ref'] is not None else 'author-year'}] **{f['corpus_id']}** — "
                         f"{f['title']} ({titles[f['corpus_id']]['first_author']}, {titles[f['corpus_id']]['year']})")
    else:
        lines.append('- none: record only the measured baselines outside the corpus')
    lines += ['', '## Statements of NOTES.md', '']
    for head, body in sections(notes):
        if not head:
            continue
        if head.startswith(WHOLE):
            keep = [l for l in body if l.strip()]
        else:
            keep = [l for l in body if l.strip().startswith('- ') and
                    ((cite and cite.search(l)) or (name and name.search(l)) or COMPARE.search(l.split(' [p')[0]))]
        if keep:
            lines += [f'### {head}', ''] + keep + ['']
    return '\n'.join(lines), len(refs)


def main():
    out = pathlib.Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    ids = sys.argv[2:] or CL.primary_ids()
    by = RL.manifest()
    titles = RL.corpus_titles()
    index = []
    for pid in ids:
        text, n = pack(pid, titles, by)
        (out / f'{pid}.md').write_text(text, encoding='utf-8')
        index.append(f'{pid}\t{n} corpus references\t{len(text.splitlines())} lines')
    (out / 'index.txt').write_text('\n'.join(index) + '\n', encoding='utf-8')
    print('\n'.join(index))


if __name__ == '__main__':
    main()
