#!/usr/bin/env python3
"""The look of the review: one set of numbers shared by the Review Viewer and every Word document the builds write.

The author, 13 October 2026: "i want the docx to look as good as it looks in review veiwer and make that permanent part
of the process we use for making docx. docx and review viewer should look as identical to each other as possible."

  viewer_css()          the stylesheet of the viewer's text view (myliteraturereviewpaper/linked-app/review_viewer.py)
  reference_docx(path)  the Word styles pandoc renders with (scripts/paper_ppml/build.py, build_supplement.py,
                        scripts/paper/build.py): pandoc's default reference document with these styles put in
  finish_docx(path)     what styles alone cannot do, run on the docx after pandoc: table text in "Table Text", the
                        citation numbers [n] in "Citation", the space below each table, the Key Takeaways boxes in
                        "Box Text"; returns counts and any paragraph style the look does not cover
  render(md, out)       pandoc with reference_docx, then finish_docx: the one call every build makes

Sizes are set in the viewer's pixels; Word takes pixels x 12/17 (body text 17 px = 12 pt), rounded to half points.
Spacing: Qt lets the larger of two neighbouring margins stand, Word adds space after to space before. Word paragraphs
therefore carry the body's gap (7 px) as space after only, and a heading or list carries the part of its margin that
the body's gap does not already give. The font is the one Qt draws for the viewer (Charter); Word on a machine without
Charter is pointed to Georgia. The Key Takeaways box was designed in Word (twips); the viewer draws it from BOX.

Usage: python3 scripts/review/paper_look.py <paper.md> <out.docx> [<resource dir>]   (renders an assembled text, e.g.
myliteraturereviewpaper/ppml2026/build/paper-V57.md with resource dir .../build, in the current look; the output must
not exist yet)
"""
import copy, pathlib, re, shutil, subprocess, sys, tempfile, zipfile

try:
    from lxml import etree               # the Word side only; the viewer's own environment has no lxml
except ImportError:
    etree = None

W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
XML_SPACE = '{http://www.w3.org/XML/1998/namespace}space'

# ----------------------------------------------------------------------------------------------- the look, in px

FONT, FALLBACK = 'Charter', 'Georgia'     # Qt on macOS is not offered Iowan Old Style; it draws Charter
INK, HEAD, TITLE_INK, MUTED, LINK = '1b1b1b', '0f4761', '111111', '333333', '1a5fb4'
GRID, HEAD_FILL = 'b9b8b3', 'cde2fb'      # table rules and the header row's fill
BODY_PX = 17
LOOK = {                                  # px; line = line height in % (None: the font's own)
    'body':    dict(px=17, color=INK, top=5, bottom=7, line=145),
    'title':   dict(px=30, color=TITLE_INK, bold=True, top=26, bottom=8, line=None),
    'author':  dict(px=16, color=MUTED, top=5, bottom=14, line=145),
    'h1':      dict(px=27, color=HEAD, bold=True, top=26, bottom=8, line=None),
    'h2':      dict(px=21, color=HEAD, bold=True, top=18, bottom=6, line=None),
    'h3':      dict(px=18, color=HEAD, bold=True, top=14, bottom=12, line=None),
    'list':    dict(top=12, bottom=12, line=140),            # Qt's margins around a list
    'caption': dict(px=14, color=MUTED, top=5, bottom=7, line=145),
    'table':   dict(px=13, pad=4, top=4, bottom=12, rule=1),
    'link':    dict(color=LINK, weight=600),
}
# the Key Takeaways box (scripts/paper_ppml/build.py takeaways()): Word units - twips, rules in eighths of a point
BOX = dict(head='156082', body='eaf2f6', rule=12, pad=(60, 160, 80, 160), head_space=40, item_before=40,
           item_after=220, last_after=80, hang=360, width=9360)
CITATION = re.compile(r'\[\d{1,3}\]')


def hp(px):
    """px -> Word half-points"""
    return round(px * 24 / BODY_PX)


def tw(px):
    """px -> twips"""
    return round(px * 240 / BODY_PX)


def px(twips):
    """twips -> px (for the box, which is set in Word units)"""
    return round(twips * BODY_PX / 240, 1)


def rule(px_width):
    """a line px wide -> the nearest width Word offers, in eighths of a point"""
    eighths = px_width * 96 / BODY_PX
    return min((2, 4, 6, 8, 12, 18, 24, 36, 48), key=lambda w: abs(w - eighths))


# ------------------------------------------------------------------------------------------------ the viewer

def viewer_css():
    """the paper's part of the viewer's stylesheet (the viewer adds its own contents and checks lists)"""
    L = LOOK
    css = lambda d: f"font-size: {d['px']}px; color: #{d['color']};"
    margins = lambda d: f"margin-top: {d['top']}px; margin-bottom: {d['bottom']}px;"
    return f"""
body {{ font-family: '{FONT}', '{FALLBACK}', serif; {css(L['body'])} }}
h1 {{ {css(L['h1'])} {margins(L['h1'])} }}
h1.title {{ {css(L['title'])} }}
h2 {{ {css(L['h2'])} {margins(L['h2'])} }}
h3 {{ {css(L['h3'])} {margins(L['h3'])} }}
p {{ {margins(L['body'])} line-height: {L['body']['line']}%; }}
li {{ line-height: {L['list']['line']}%; }}
a {{ color: #{LINK}; text-decoration: none; font-weight: {L['link']['weight']}; }}
table {{ margin-top: {L['table']['top']}px; margin-bottom: {L['table']['bottom']}px; border-collapse: collapse; }}
th {{ background-color: #{HEAD_FILL}; border: {L['table']['rule']}px solid #{GRID}; font-size: {L['table']['px']}px; }}
td {{ border: {L['table']['rule']}px solid #{GRID}; font-size: {L['table']['px']}px; }}
.figcap, .tabcap {{ {css(L['caption'])} }}
.author {{ {css(L['author'])} margin-bottom: {L['author']['bottom']}px; }}
"""


def viewer_box(items, head='Key Takeaways'):
    """a Key Takeaways box for the viewer, drawn as Word draws it (BOX): header row in the accent, a pale row with the
    points, each a bullet with a hanging indent; `items` are the points' HTML"""
    top, left, bottom, right = (px(v) for v in BOX['pad'])
    edge = f"border: {round(BOX['rule'] / 8 * BODY_PX / 12)}px solid #{BOX['head']};"
    cell = f'padding-top: {top}px; padding-left: {left}px; padding-bottom: {bottom}px; padding-right: {right}px; {edge}'
    hang = px(BOX['hang'])
    paras = ''.join(
        f'<p style="margin-top: {px(BOX["item_before"])}px; '
        f'margin-bottom: {px(BOX["item_after"] if i < len(items) else BOX["last_after"])}px; '
        f'margin-left: {hang}px; text-indent: -{hang}px; font-size: {BODY_PX}px;">•&nbsp; {x}</p>'
        for i, x in enumerate(items, 1))
    return (f'<table width="100%" cellspacing="0" cellpadding="0">'
            f'<tr><td bgcolor="#{BOX["head"]}" style="{cell}"><p style="margin-top: {px(BOX["head_space"])}px; '
            f'margin-bottom: {px(BOX["head_space"])}px; font-size: {BODY_PX}px; color: #ffffff; font-weight: 700;">{head}</p></td></tr>'
            f'<tr><td bgcolor="#{BOX["body"]}" style="{cell}">{paras}</td></tr></table>')


# ------------------------------------------------------------------------------------------------ Word styles

def _spacing(before=None, after=None, line=None):
    a = ''.join(f' w:{k}="{v}"' for k, v in (('before', before), ('after', after)) if v is not None)
    if line:
        a += f' w:line="{round(240 * line / 100)}" w:lineRule="auto"'
    return f'<w:spacing{a}/>' if a else ''


def _ppr(before=None, after=None, line=None, jc=None, keep_next=False, keep_lines=False, contextual=False, outline=None):
    s = ('<w:keepNext/>' if keep_next else '') + ('<w:keepLines/>' if keep_lines else '') + _spacing(before, after, line) \
        + ('<w:contextualSpacing/>' if contextual else '') + (f'<w:jc w:val="{jc}"/>' if jc else '') \
        + (f'<w:outlineLvl w:val="{outline}"/>' if outline is not None else '')
    return f'<w:pPr>{s}</w:pPr>' if s else ''


def _rpr(size_px=None, color=None, bold=None, italic=None):
    s = ''
    if bold is not None:
        s += '<w:b/><w:bCs/>' if bold else '<w:b w:val="0"/><w:bCs w:val="0"/>'
    if italic is not None:
        s += '<w:i/><w:iCs/>' if italic else '<w:i w:val="0"/><w:iCs w:val="0"/>'
    if color:
        s += f'<w:color w:val="{color.upper()}"/>'
    if size_px:
        s += f'<w:sz w:val="{hp(size_px)}"/><w:szCs w:val="{hp(size_px)}"/>'
    return f'<w:rPr>{s}</w:rPr>' if s else ''


def _style(kind, sid, name, based=None, nxt=None, ppr='', rpr='', extra='', custom=True):
    return (f'<w:style xmlns:w="{W}" w:type="{kind}"{" w:customStyle=\"1\"" if custom else ""} w:styleId="{sid}">'
            f'<w:name w:val="{name}"/>' + (f'<w:basedOn w:val="{based}"/>' if based else '')
            + (f'<w:next w:val="{nxt}"/>' if nxt else '') + '<w:qFormat/>' + ppr + rpr + extra + '</w:style>')


def _styles():
    """every style the look sets, as Word XML; Qt's margins turned into Word's added spacing (see the docstring)"""
    L, gap = LOOK, LOOK['body']['bottom']
    b, c, t, a = L['body'], L['caption'], L['table'], L['author']

    def heading(level):
        h = L[f'h{level}']
        return _style('paragraph', f'Heading{level}', f'heading {level}', 'Normal', 'BodyText',
                      _ppr(tw(max(h['top'], gap) - gap), tw(max(h['bottom'], b['top'])), 100, keep_next=True,
                           keep_lines=True, outline=level - 1),
                      _rpr(h['px'], h['color'], bold=True), custom=False)
    edges = ''.join(f'<w:{e} w:val="single" w:sz="{rule(t["rule"])}" w:space="0" w:color="{GRID.upper()}"/>'
                    for e in ('top', 'left', 'bottom', 'right', 'insideH', 'insideV'))
    pad = ''.join(f'<w:{e} w:w="{tw(t["pad"])}" w:type="dxa"/>' for e in ('top', 'left', 'bottom', 'right'))
    side = _rpr(a['px'], a['color'], bold=False)
    side_ppr = _ppr(0, tw(a['bottom']), a['line'], jc='left', keep_next=True)
    return [
        _style('paragraph', 'BodyText', 'Body Text', 'Normal', None, _ppr(0, tw(gap), b['line']), custom=False),
        _style('paragraph', 'Compact', 'Compact', 'BodyText', None,       # tight lists (tables get "Table Text")
               _ppr(tw(max(L['list']['top'], gap) - gap), tw(L['list']['bottom']), L['list']['line'], contextual=True)),
        _style('paragraph', 'Title', 'Title', 'Normal', 'BodyText', _ppr(0, tw(max(L['title']['bottom'], a['top'])), 100,
               jc='left', keep_next=True), _rpr(L['title']['px'], L['title']['color'], bold=True), custom=False),
        _style('paragraph', 'Subtitle', 'Subtitle', 'Normal', 'BodyText', side_ppr, side, custom=False),
        _style('paragraph', 'Author', 'Author', 'Normal', 'BodyText', side_ppr, side),
        _style('paragraph', 'Date', 'Date', 'Normal', 'BodyText', side_ppr, side),
        heading(1), heading(2), heading(3),
        _style('paragraph', 'Caption', 'caption', 'Normal', None, _ppr(0, tw(c['bottom']), c['line']),
               _rpr(c['px'], c['color'], italic=False), custom=False),
        _style('paragraph', 'TableCaption', 'Table Caption', 'Caption', None,
               _ppr(0, tw(max(c['bottom'], t['top'])), keep_next=True)),
        _style('paragraph', 'ImageCaption', 'Image Caption', 'Caption', None, _ppr(tw(c['top']), jc='center')),
        _style('paragraph', 'Figure', 'Figure', 'Normal', None, _ppr(0, 0, jc='center')),
        _style('paragraph', 'CaptionedFigure', 'Captioned Figure', 'Figure', None, _ppr(keep_next=True)),
        _style('paragraph', 'TableText', 'Table Text', 'Normal', None, _ppr(0, 0, 100), _rpr(t['px'])),
        _style('paragraph', 'BoxText', 'Box Text', 'Normal', None, _ppr(line=b['line']), _rpr(BODY_PX)),
        _style('character', 'Hyperlink', 'Hyperlink', 'DefaultParagraphFont', None, '',
               _rpr(color=LINK, bold=True), custom=False),
        _style('character', 'Citation', 'Citation', 'DefaultParagraphFont', None, '', _rpr(color=LINK, bold=True)),
        _style('table', 'Table', 'Table', 'TableNormal', None, _ppr(0, 0, 100), _rpr(t['px']),
               f'<w:tblPr><w:tblInd w:w="0" w:type="dxa"/><w:tblBorders>{edges}</w:tblBorders>'
               f'<w:tblCellMar>{pad}</w:tblCellMar></w:tblPr>'
               f'<w:tblStylePr w:type="firstRow"><w:pPr><w:jc w:val="center"/></w:pPr><w:rPr><w:b/><w:bCs/></w:rPr>'
               f'<w:tcPr><w:shd w:val="clear" w:color="auto" w:fill="{HEAD_FILL.upper()}"/></w:tcPr></w:tblStylePr>'),
    ]


def reference_docx(path):
    """write the reference document: pandoc's own default with the look's styles, defaults and font fallback"""
    path = pathlib.Path(path)
    with tempfile.TemporaryDirectory() as tmp:
        tmp = pathlib.Path(tmp)
        subprocess.run(['pandoc', '-o', str(tmp / 'default.docx'), '--print-default-data-file', 'reference.docx'], check=True)
        with zipfile.ZipFile(tmp / 'default.docx') as z:
            z.extractall(tmp / 'x')
        sp = tmp / 'x' / 'word' / 'styles.xml'
        tree = etree.parse(str(sp))
        root = tree.getroot()
        rpr = root.find(f'{{{W}}}docDefaults/{{{W}}}rPrDefault/{{{W}}}rPr')
        for old in list(rpr):
            if etree.QName(old).localname in ('rFonts', 'color', 'sz', 'szCs'):
                rpr.remove(old)
        fonts = etree.SubElement(rpr, f'{{{W}}}rFonts')
        for k in ('ascii', 'hAnsi', 'cs', 'eastAsia'):
            fonts.set(f'{{{W}}}{k}', FONT)
        etree.SubElement(rpr, f'{{{W}}}color').set(f'{{{W}}}val', INK.upper())
        for k in ('sz', 'szCs'):
            etree.SubElement(rpr, f'{{{W}}}{k}').set(f'{{{W}}}val', str(hp(BODY_PX)))
        _order(rpr, RPR_ORDER)
        sp_default = root.find(f'{{{W}}}docDefaults/{{{W}}}pPrDefault/{{{W}}}pPr/{{{W}}}spacing')
        if sp_default is not None:
            sp_default.set(f'{{{W}}}after', '0')
        for xml in _styles():
            new = etree.fromstring(xml)
            sid = new.get(f'{{{W}}}styleId')
            old = root.find(f'{{{W}}}style[@{{{W}}}styleId="{sid}"]')
            if old is not None:
                for keep in ('link', 'uiPriority', 'rsid'):          # Word's own bookkeeping, in schema order
                    e = old.find(f'{{{W}}}{keep}')
                    if e is not None:
                        new.insert(list(new).index(new.find(f'{{{W}}}qFormat')) + (keep == 'rsid'), e)
                old.addprevious(new)
                root.remove(old)
            else:
                root.append(new)
        tree.write(str(sp), xml_declaration=True, encoding='UTF-8', standalone=True)
        ft = tmp / 'x' / 'word' / 'fontTable.xml'
        if ft.exists() and FONT.encode() not in ft.read_bytes():       # Word without Charter takes Georgia
            ft.write_bytes(ft.read_bytes().replace(b'</w:fonts>', (
                f'<w:font w:name="{FONT}"><w:altName w:val="{FALLBACK}"/><w:panose1 w:val="02040503050506020203"/>'
                '<w:charset w:val="00"/><w:family w:val="roman"/><w:pitch w:val="variable"/></w:font></w:fonts>').encode()))
        with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as out:
            for f in sorted((tmp / 'x').rglob('*')):
                if f.is_file():
                    out.write(f, f.relative_to(tmp / 'x').as_posix())
    return path


# ------------------------------------------------------------------------------------------- after pandoc

RPR_ORDER = ['rStyle', 'rFonts', 'b', 'bCs', 'i', 'iCs', 'caps', 'smallCaps', 'strike', 'dstrike', 'outline', 'shadow',
             'emboss', 'imprint', 'noProof', 'snapToGrid', 'vanish', 'webHidden', 'color', 'spacing', 'w', 'kern',
             'position', 'sz', 'szCs', 'highlight', 'u', 'effect', 'bdr', 'shd', 'fitText', 'vertAlign', 'rtl', 'cs',
             'em', 'lang', 'eastAsianLayout', 'specVanish', 'oMath']
PPR_ORDER = ['pStyle', 'keepNext', 'keepLines', 'pageBreakBefore', 'framePr', 'widowControl', 'numPr',
             'suppressLineNumbers', 'pBdr', 'shd', 'tabs', 'suppressAutoHyphens', 'kinsoku', 'wordWrap', 'overflowPunct',
             'topLinePunct', 'autoSpaceDE', 'autoSpaceDN', 'bidi', 'adjustRightInd', 'snapToGrid', 'spacing', 'ind',
             'contextualSpacing', 'mirrorIndents', 'suppressOverlap', 'jc', 'textDirection', 'textAlignment',
             'textboxTightWrap', 'outlineLvl', 'divId', 'cnfStyle', 'rPr', 'sectPr', 'pPrChange']
# the top margin (px) of what a paragraph style stands for, for the space below a table (Qt: the larger margin wins)
TOP = {'BodyText': LOOK['body']['top'], 'FirstParagraph': LOOK['body']['top'], 'Compact': LOOK['list']['top'],
       'Heading1': LOOK['h1']['top'], 'Heading2': LOOK['h2']['top'], 'Heading3': LOOK['h3']['top'],
       'TableCaption': LOOK['caption']['top'], 'ImageCaption': LOOK['caption']['top']}
COVERED = {'BodyText', 'FirstParagraph', 'Compact', 'Title', 'Subtitle', 'Author', 'Date', 'Heading1', 'Heading2',
           'Heading3', 'TableCaption', 'ImageCaption', 'Figure', 'CaptionedFigure', 'TableText', 'BoxText'}


def q(tag):
    return f'{{{W}}}{tag}'


def _order(parent, order):
    kids = sorted(parent, key=lambda e: order.index(etree.QName(e).localname) if etree.QName(e).localname in order else 99)
    for k in kids:
        parent.append(k)


def _ppr_of(p):
    ppr = p.find(q('pPr'))
    if ppr is None:
        ppr = etree.Element(q('pPr'))
        p.insert(0, ppr)
    return ppr


def _set_style(p, sid):
    ppr = _ppr_of(p)
    st = ppr.find(q('pStyle'))
    if st is None:
        st = etree.SubElement(ppr, q('pStyle'))
    st.set(q('val'), sid)
    _order(ppr, PPR_ORDER)


def _style_of(p):
    st = p.find(f'{q("pPr")}/{q("pStyle")}')
    return st.get(q('val')) if st is not None else None


def _cite_runs(r):
    """split one plain run so that each [n] is a run of its own in the Citation style; returns the number styled"""
    t = r.find(q('t'))
    if t is None or not t.text or not CITATION.search(t.text) or any(
            etree.QName(c).localname not in ('rPr', 't') for c in r) or len(r.findall(q('t'))) != 1:
        return 0
    rpr = r.find(q('rPr'))
    if rpr is not None and rpr.find(q('rStyle')) is not None:
        return 0
    parts = [x for x in re.split(r'(\[\d{1,3}\])', t.text) if x]
    n = 0
    for part in parts:
        new = copy.deepcopy(r)
        nt = new.find(q('t'))
        nt.text = part
        nt.set(XML_SPACE, 'preserve')
        if CITATION.fullmatch(part):
            nrpr = new.find(q('rPr'))
            if nrpr is None:
                nrpr = etree.Element(q('rPr'))
                new.insert(0, nrpr)
            etree.SubElement(nrpr, q('rStyle')).set(q('val'), 'Citation')
            _order(nrpr, RPR_ORDER)
            n += 1
        r.addprevious(new)
    r.getparent().remove(r)
    return n


def finish_docx(path):
    """the parts of the look that styles cannot carry, applied to a docx rendered with reference_docx (in place)"""
    path = pathlib.Path(path)
    with zipfile.ZipFile(path) as z:
        doc = etree.fromstring(z.read('word/document.xml'))
    body = doc.find(q('body'))
    report = {'table_paragraphs': 0, 'box_paragraphs': 0, 'citations': 0, 'space_below_tables': 0, 'spacers': 0}
    for tbl in body.iter(q('tbl')):
        styled = tbl.find(f'{q("tblPr")}/{q("tblStyle")}') is not None
        for p in tbl.iter(q('p')):
            if styled and _style_of(p) in (None, 'Compact', 'BodyText', 'FirstParagraph'):
                _set_style(p, 'TableText')
                report['table_paragraphs'] += 1
            elif not styled and _style_of(p) == 'Compact':          # the Key Takeaways box (build.py takeaways())
                _set_style(p, 'BoxText')
                report['box_paragraphs'] += 1
    for tbl in body.findall(q('tbl')):
        prev = tbl.getprevious()
        if tbl.find(f'{q("tblPr")}/{q("tblStyle")}') is None and prev is not None and prev.tag == q('p') \
                and prev.find(f'.//{q("r")}') is None and prev.find(f'.//{q("sectPr")}') is None:
            ppr = _ppr_of(prev)                    # the empty paragraph that keeps a box apart from a table: 1 pt high
            for old in ppr.findall(q('spacing')):
                ppr.remove(old)
            etree.SubElement(ppr, q('spacing')).attrib.update({q('before'): '0', q('after'): '0', q('line'): '20',
                                                               q('lineRule'): 'exact'})
            mark = ppr.find(q('rPr'))
            if mark is None:
                mark = etree.SubElement(ppr, q('rPr'))
            for k in ('sz', 'szCs'):
                etree.SubElement(mark, q(k)).set(q('val'), '2')
            _order(ppr, PPR_ORDER)
            report['spacers'] += 1
    for tbl in body.findall(q('tbl')):                 # after the spacers: a table's gap also holds above a box
        nxt = tbl.getnext()
        while nxt is not None and nxt.tag in (q('bookmarkStart'), q('bookmarkEnd')):      # pandoc's section anchors
            nxt = nxt.getnext()
        if nxt is not None and nxt.tag == q('p') and nxt.find(f'.//{q("sectPr")}') is None:
            ppr = _ppr_of(nxt)
            sp = ppr.find(q('spacing'))
            if sp is None:
                sp = etree.SubElement(ppr, q('spacing'))
            sp.set(q('before'), str(tw(max(LOOK['table']['bottom'], TOP.get(_style_of(nxt), 0)))))
            _order(ppr, PPR_ORDER)
            report['space_below_tables'] += 1
    for r in list(body.iter(q('r'))):
        report['citations'] += _cite_runs(r)
    used = {_style_of(p) for p in body.iter(q('p'))} - {None}
    report['styles_not_in_look'] = sorted(used - COVERED)
    tmp = path.with_name(path.stem + '.finishing.docx')
    with zipfile.ZipFile(path) as zin, zipfile.ZipFile(tmp, 'w', zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data = zin.read(item.filename)
            if item.filename == 'word/document.xml':
                data = etree.tostring(doc, xml_declaration=True, encoding='UTF-8', standalone=True)
            zout.writestr(item, data)
    shutil.move(str(tmp), path)
    return report


def render(md, out, resource_path=None):
    """pandoc with the look, then finish_docx and the package fixes of the builds (scripts/paper/build.py
    fix_comments_part: the comments part, PNG declared): the one call every build makes. Returns finish_docx's report."""
    with tempfile.TemporaryDirectory() as tmp:
        ref = reference_docx(pathlib.Path(tmp) / 'reference.docx')
        subprocess.run(['pandoc', str(md), '-o', str(out), '--reference-doc', str(ref),
                        *(['--resource-path', str(resource_path)] if resource_path else [])], check=True)
    report = finish_docx(out)
    import importlib.util
    spec = importlib.util.spec_from_file_location('build_v4', pathlib.Path(__file__).resolve().parents[1] / 'paper' / 'build.py')
    B0 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(B0)
    B0.fix_comments_part(pathlib.Path(out))
    return report


if __name__ == '__main__':
    if len(sys.argv) not in (3, 4) or pathlib.Path(sys.argv[2]).exists():
        sys.exit(__doc__)
    print(render(*sys.argv[1:]))
