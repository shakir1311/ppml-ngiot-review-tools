#!/usr/bin/env python3
"""Mark the places in the review that the author must verify, rewrite in their own words, or spot-check.

Reads myliteraturereviewpaper/_src/V18/AUTHOR-CHECKS.json, highlights each anchored passage of the built .docx in the
colour of its kind and attaches the check as a Word comment. span 'match' marks the anchor text, 'paragraph' the whole
paragraph that holds it, 'range' every paragraph from the one holding `find` to the one holding `until` (siblings in the
body, with no table between them). Highlights may not overlap. The comment parts (comments.xml and its companions) are
written by the docx skill's comment.py; this script only places the highlight and the comment markers. Every anchor
must occur exactly once in the document, otherwise nothing is written. The output must not exist yet.

Usage: scripts/.venv/bin/python scripts/review/annotate_author_checks.py <built.docx> <out.docx> [--dry-run]
"""
import copy, glob, json, os, pathlib, sys, tempfile, zipfile
from lxml import etree

ROOT = pathlib.Path(__file__).resolve().parents[2]
CHECKS = pathlib.Path(os.environ['AUTHOR_CHECKS']) if os.environ.get('AUTHOR_CHECKS') else ROOT / 'myliteraturereviewpaper' / '_src' / 'V18' / 'AUTHOR-CHECKS.json'
W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
XML_SPACE = '{http://www.w3.org/XML/1998/namespace}space'
# child order of w:rPr in the schema (ECMA-376 CT_RPr); w:highlight must sit in its place
RPR_ORDER = ['rStyle', 'rFonts', 'b', 'bCs', 'i', 'iCs', 'caps', 'smallCaps', 'strike', 'dstrike', 'outline', 'shadow',
             'emboss', 'imprint', 'noProof', 'snapToGrid', 'vanish', 'webHidden', 'color', 'spacing', 'w', 'kern',
             'position', 'sz', 'szCs', 'highlight', 'u', 'effect', 'bdr', 'shd', 'fitText', 'vertAlign', 'rtl', 'cs',
             'em', 'lang', 'eastAsianLayout', 'specVanish', 'oMath']
COMMENT_STYLE = (f'<w:style xmlns:w="{W}" w:type="character" w:styleId="CommentReference"><w:name w:val="annotation '
                 'reference"/><w:uiPriority w:val="99"/><w:semiHidden/><w:unhideWhenUsed/><w:rPr><w:sz w:val="16"/>'
                 '<w:szCs w:val="16"/></w:rPr></w:style>')


def q(tag):
    return f'{{{W}}}{tag}'


def skill_scripts():
    path = os.environ.get('DOCX_SKILL')
    if not path:
        found = sorted(glob.glob(os.path.expanduser('~/.claude/skills/**/docx/scripts/comment.py'), recursive=True))
        if not found:
            raise SystemExit('docx skill not found; set DOCX_SKILL to its scripts directory')
        path = os.path.dirname(found[0])
    return path


def run_text(r):
    return ''.join(t.text or '' for t in r.findall(q('t')))


def para_text(p):
    return ''.join(run_text(r) for r in p.findall(q('r')))


def splittable(r):
    return len(r.findall(q('t'))) == 1 and all(etree.QName(c).localname in ('rPr', 't') for c in r)


def split(r, k):
    """Cut a text run at character k; the right part becomes a copy of the run placed after it."""
    right = copy.deepcopy(r)
    t, rt = r.find(q('t')), right.find(q('t'))
    text = t.text or ''
    t.text, rt.text = text[:k], text[k:]
    for x in (t, rt):
        x.set(XML_SPACE, 'preserve')
    r.addnext(right)


def set_highlight(r, colour):
    rpr = r.find(q('rPr'))
    if rpr is None:
        rpr = etree.Element(q('rPr'))
        r.insert(0, rpr)
    old = rpr.find(q('highlight'))
    if old is not None:
        rpr.remove(old)
    h = etree.Element(q('highlight'))
    h.set(q('val'), colour)
    rank = RPR_ORDER.index('highlight')
    for i, c in enumerate(rpr):
        name = etree.QName(c).localname
        if name in RPR_ORDER and RPR_ORDER.index(name) > rank:
            rpr.insert(i, h)
            return
    rpr.append(h)


def split_at(p, cut):
    pos = 0
    for r in p.findall(q('r')):
        n = len(run_text(r))
        if pos < cut < pos + n and splittable(r):
            split(r, cut - pos)
            return
        pos += n


def covered_runs(p, a, b):
    out, pos = [], 0
    for r in p.findall(q('r')):
        n = len(run_text(r))
        if n and pos + n > a and pos < b:
            out.append(r)
        pos += n
    return out


def mark_spans(spans, colour, cid):
    """spans: [(paragraph, a, b), ...] in document order; highlight each and wrap them all in one comment cid"""
    covered = []
    for p, a, b in spans:
        split_at(p, a)
        split_at(p, b)
        covered += covered_runs(p, a, b)
    for r in covered:
        set_highlight(r, colour)
    start = etree.Element(q('commentRangeStart'))
    start.set(q('id'), str(cid))
    covered[0].addprevious(start)
    end = etree.Element(q('commentRangeEnd'))
    end.set(q('id'), str(cid))
    covered[-1].addnext(end)
    end.addnext(etree.fromstring(f'<w:r xmlns:w="{W}"><w:rPr><w:rStyle w:val="CommentReference"/></w:rPr>'
                                 f'<w:commentReference w:id="{cid}"/></w:r>'))


def ensure_comment_style(unpacked):
    path = unpacked / 'word' / 'styles.xml'
    tree = etree.parse(str(path))
    root = tree.getroot()
    if not any(s.get(q('styleId')) == 'CommentReference' for s in root.findall(q('style'))):
        root.append(etree.fromstring(COMMENT_STYLE))
        tree.write(str(path), xml_declaration=True, encoding='UTF-8', standalone=True)


def resolve(paras, c):
    """the (paragraph, a, b) spans a check covers, in document order, or an error message"""
    p = next(p for p in paras if c['find'] in para_text(p))
    text = para_text(p)
    if c['span'] == 'match':
        a = text.index(c['find'])
        return [(p, a, a + len(c['find']))]
    if c['span'] == 'paragraph':
        return [(p, 0, len(text))]
    last = next(x for x in paras if c['until'] in para_text(x))
    if last.getparent() is not p.getparent():
        return 'range start and end are not in the same body'
    sibs = list(p.getparent())
    i, j = sibs.index(p), sibs.index(last)
    if j < i:
        return 'range ends before it starts'
    markers = (q('bookmarkStart'), q('bookmarkEnd'))       # pandoc's heading bookmarks sit between paragraphs
    if any(x.tag != q('p') and x.tag not in markers for x in sibs[i:j + 1]):
        return 'range crosses a table or other block'
    return [(x, 0, len(para_text(x))) for x in sibs[i:j + 1] if x.tag == q('p') and para_text(x)]


def main(src, out, dry):
    src, out = pathlib.Path(src), pathlib.Path(out)
    if out.exists():
        raise SystemExit(f'{out} exists; versions are never overwritten')
    spec = json.loads(CHECKS.read_text(encoding='utf-8'))
    colours = {k: v['colour'] for k, v in spec['kinds'].items()}
    sys.path.insert(0, skill_scripts())
    import comment as skill_comment          # noqa: E402  (the docx skill's comment helper)
    from office.helpers import rezip, safe_extract   # noqa: E402

    with tempfile.TemporaryDirectory() as tmp:
        unpacked = pathlib.Path(tmp) / 'docx'
        with zipfile.ZipFile(src) as zf:
            safe_extract(zf, unpacked)
        doc_path = unpacked / 'word' / 'document.xml'
        tree = etree.parse(str(doc_path))
        paras = list(tree.getroot().iter(q('p')))

        problems, plans, taken = [], [], {}
        for i, c in enumerate(spec['checks']):
            for key in ('find', 'until') if c.get('span') == 'range' else ('find',):
                hits = sum(para_text(p).count(c.get(key, '')) for p in paras) if c.get(key) else 0
                if hits != 1:
                    problems.append(f"check {i + 1}: {key} '{c.get(key, '')[:70]}' occurs {hits} times")
            if c['kind'] not in colours or c['span'] not in ('match', 'paragraph', 'range'):
                problems.append(f'check {i + 1}: unknown kind or span')
            if problems:
                continue
            spans = resolve(paras, c)
            if isinstance(spans, str):
                problems.append(f'check {i + 1}: {spans}')
                continue
            for p, a, b in spans:                      # no two checks may cover the same characters
                for j, (a2, b2) in taken.get(id(p), []):
                    if a < b2 and a2 < b:
                        problems.append(f'check {i + 1} overlaps check {j + 1}')
                taken.setdefault(id(p), []).append((i, (a, b)))
            plans.append((c, spans))
        if problems:
            raise SystemExit('nothing written:\n  ' + '\n  '.join(problems))
        if dry:
            print(f"{len(spec['checks'])} checks, every anchor found exactly once")
            return

        for c, spans in plans:
            body = c['comment'] if c['comment'].startswith('KEY') else f"{c['kind']}: {c['comment']}"
            cid, _, _ = skill_comment.add_comment(unpacked, body, author='Claude', initials='C')
            mark_spans(spans, colours[c['kind']], cid)

        tree.write(str(doc_path), xml_declaration=True, encoding='UTF-8', standalone=True)
        ensure_comment_style(unpacked)
        rezip(unpacked, out)
    counts = {k: sum(1 for c in spec['checks'] if c['kind'] == k) for k in colours}
    print(f'wrote {out}: ' + ', '.join(f'{n} {k} ({colours[k]})' for k, n in counts.items()))


if __name__ == '__main__':
    args = [a for a in sys.argv[1:] if a != '--dry-run']
    if len(args) != 2:
        raise SystemExit(__doc__)
    main(args[0], args[1], '--dry-run' in sys.argv)
