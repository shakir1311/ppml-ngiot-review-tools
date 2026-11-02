#!/usr/bin/env python3
"""Convert one of the Docs/ guideline pages (HTML) into a Word document with working links.

pandoc does the conversion. This script only prepares its input and finishes its output:
  - the page's CSS classes become Word styles: callout and template boxes, grey notes, the green "allowed" and red
    "not allowed" labels, and italic for interpretation (class "mine");
  - a reference document gives Calibri text, coloured headings, blue underlined links and a bordered table style;
  - the comparison table gets fixed column widths on an A4 page, a header row that repeats on every page, and rows that
    do not split across pages;
  - every hyperlink in the result is compared with the links of the HTML: the run fails if one is missing or altered.

Usage: scripts/.venv/bin/python scripts/html_to_docx.py <in.html> <out.docx>
The output must not exist yet.
"""
import copy, html, pathlib, re, subprocess, sys, tempfile, zipfile
from lxml import etree

W = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'
R = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
PR = 'http://schemas.openxmlformats.org/package/2006/relationships'


def q(tag, ns=W):
    return f'{{{ns}}}{tag}'


# ------------------------------------------------------------------ 1. the HTML, with its classes made into styles

def prepare_html(src):
    s = re.sub(r'<title>.*?</title>|<style>.*?</style>', '', src, flags=re.S)
    s = s.replace('<div class="callout warn">', '<div data-custom-style="Callout">')
    s = s.replace('<div class="callout">', '<div data-custom-style="Callout">')
    s = s.replace('<div class="tpl">', '<div data-custom-style="Template">')
    s = s.replace('<div class="meta">', '<div data-custom-style="Meta">')
    s = re.sub(r'<p class="note">(.*?)</p>', r'<div data-custom-style="Note"><p>\1</p></div>', s, flags=re.S)
    s = re.sub(r'<span class="mine">(.*?)</span>', r'<em>\1</em>', s, flags=re.S)
    s = re.sub(r'<li class="mine">(.*?)</li>', r'<li><em>\1</em></li>', s, flags=re.S)
    s = s.replace('<span class="yes">', '<span data-custom-style="Allowed">')
    s = s.replace('<span class="no">', '<span data-custom-style="Not allowed">')
    return s


# ------------------------------------------------------------------ 2. the reference document (styles)

STYLES = {
    'Normal': {'font': 'Calibri', 'sz': 21},
    'BodyText': {'after': 100},
    'FirstParagraph': {'after': 100},
    'Compact': {'after': 40},
    'Heading1': {'sz': 32, 'color': '0B0B0B', 'before': 120, 'after': 120},
    'Heading2': {'sz': 26, 'color': '256ABF', 'before': 320, 'after': 100, 'bold': True},
    'Heading3': {'sz': 22, 'color': '1F1F1F', 'before': 220, 'after': 80, 'bold': True},
    'Hyperlink': {'color': '256ABF'},
}
EXTRA = [
    # (type, id, name, pPr xml, rPr xml)
    ('paragraph', 'Callout', 'Callout',
     '<w:pBdr><w:left w:val="single" w:sz="24" w:space="8" w:color="256ABF"/></w:pBdr>'
     '<w:shd w:val="clear" w:color="auto" w:fill="EEF5FD"/><w:spacing w:before="40" w:after="60"/><w:ind w:left="170"/>',
     '<w:sz w:val="20"/>'),
    ('paragraph', 'Template', 'Template',
     '<w:pBdr><w:top w:val="single" w:sz="4" w:space="4" w:color="D9D8D3"/><w:left w:val="single" w:sz="4" w:space="4" '
     'w:color="D9D8D3"/><w:bottom w:val="single" w:sz="4" w:space="4" w:color="D9D8D3"/><w:right w:val="single" '
     'w:sz="4" w:space="4" w:color="D9D8D3"/></w:pBdr><w:shd w:val="clear" w:color="auto" w:fill="F3F2EF"/>'
     '<w:spacing w:before="80" w:after="120"/>',
     '<w:sz w:val="19"/>'),
    ('paragraph', 'Note', 'Note', '<w:spacing w:before="60" w:after="100"/>', '<w:color w:val="52514E"/><w:sz w:val="18"/>'),
    ('paragraph', 'Meta', 'Meta', '<w:spacing w:after="200"/>', '<w:color w:val="52514E"/><w:sz w:val="19"/>'),
    ('character', 'Allowed', 'Allowed', '', '<w:b/><w:color w:val="1E7B34"/>'),
    ('character', 'NotAllowed', 'Not allowed', '', '<w:b/><w:color w:val="B3261E"/>'),
]
TABLE_STYLE = (
    '<w:tblPr><w:tblBorders>' + ''.join(
        f'<w:{e} w:val="single" w:sz="4" w:space="0" w:color="B9B8B3"/>'
        for e in ('top', 'left', 'bottom', 'right', 'insideH', 'insideV')) +
    '</w:tblBorders><w:tblCellMar><w:top w:w="40" w:type="dxa"/><w:left w:w="70" w:type="dxa"/>'
    '<w:bottom w:w="40" w:type="dxa"/><w:right w:w="70" w:type="dxa"/></w:tblCellMar></w:tblPr>'
    '<w:tblStylePr w:type="firstRow"><w:rPr><w:b/></w:rPr>'
    '<w:tcPr><w:shd w:val="clear" w:color="auto" w:fill="F3F2EF"/></w:tcPr></w:tblStylePr>'
    '<w:tblStylePr w:type="firstCol"><w:rPr><w:b/></w:rPr>'
    '<w:tcPr><w:shd w:val="clear" w:color="auto" w:fill="F3F2EF"/></w:tcPr></w:tblStylePr>')


def set_rpr(style, props):
    rpr = style.find(q('rPr'))
    if rpr is None:
        rpr = etree.SubElement(style, q('rPr'))
    if 'font' in props:
        for old in rpr.findall(q('rFonts')):
            rpr.remove(old)
        f = etree.Element(q('rFonts'))
        for a in ('ascii', 'hAnsi', 'cs', 'eastAsia'):
            f.set(q(a), props['font'])
        rpr.insert(0, f)
    if props.get('bold'):
        for tag in ('b', 'bCs'):
            if rpr.find(q(tag)) is None:
                etree.SubElement(rpr, q(tag))
    if 'color' in props:
        for old in rpr.findall(q('color')):
            rpr.remove(old)
        c = etree.SubElement(rpr, q('color'))
        c.set(q('val'), props['color'])
    if 'sz' in props:
        for tag in ('sz', 'szCs'):
            for old in rpr.findall(q(tag)):
                rpr.remove(old)
            e = etree.SubElement(rpr, q(tag))
            e.set(q('val'), str(props['sz']))


def set_spacing(style, props):
    if 'before' not in props and 'after' not in props:
        return
    ppr = style.find(q('pPr'))
    if ppr is None:
        ppr = etree.Element(q('pPr'))
        style.insert(len([c for c in style if etree.QName(c).localname in ('name', 'basedOn', 'next', 'link',
                                                                            'uiPriority', 'qFormat')]), ppr)
    sp = ppr.find(q('spacing'))
    if sp is None:
        sp = etree.SubElement(ppr, q('spacing'))
    for k in ('before', 'after'):
        if k in props:
            sp.set(q(k), str(props[k]))


def order_rpr(style):
    """w:rPr children must follow the schema order"""
    order = ['rStyle', 'rFonts', 'b', 'bCs', 'i', 'iCs', 'caps', 'smallCaps', 'strike', 'dstrike', 'outline', 'shadow',
             'emboss', 'imprint', 'noProof', 'snapToGrid', 'vanish', 'webHidden', 'color', 'spacing', 'w', 'kern',
             'position', 'sz', 'szCs', 'highlight', 'u', 'effect', 'bdr', 'shd', 'fitText', 'vertAlign', 'rtl', 'cs',
             'em', 'lang', 'eastAsianLayout', 'specVanish', 'oMath']
    rpr = style.find(q('rPr'))
    if rpr is None:
        return
    kids = sorted(list(rpr), key=lambda e: order.index(etree.QName(e).localname)
                  if etree.QName(e).localname in order else 99)
    for k in list(rpr):
        rpr.remove(k)
    for k in kids:
        rpr.append(k)


def build_reference(path):
    with tempfile.TemporaryDirectory() as tmp:
        default = pathlib.Path(tmp) / 'default-reference.docx'
        subprocess.run(['pandoc', '-o', str(default), '--print-default-data-file', 'reference.docx'], check=True)
        with zipfile.ZipFile(default) as z:
            z.extractall(tmp)
        default.unlink()
        sp = pathlib.Path(tmp) / 'word' / 'styles.xml'
        tree = etree.parse(str(sp))
        root = tree.getroot()
        styles = {s.get(q('styleId')): s for s in root.findall(q('style'))}
        for sid, props in STYLES.items():
            st = styles[sid]
            set_rpr(st, props)
            set_spacing(st, props)
            order_rpr(st)
        tbl = styles['Table']
        for old in tbl.findall(q('tblPr')) + tbl.findall(q('tblStylePr')):
            tbl.remove(old)
        frag = etree.fromstring(f'<x xmlns:w="{W}">{TABLE_STYLE}</x>')
        for e in frag:
            tbl.append(e)
        set_rpr(tbl, {'sz': 17})
        order_rpr(tbl)
        rpr = tbl.find(q('rPr'))                     # schema order inside w:style: ... pPr, rPr, tblPr, trPr, tcPr, tblStylePr
        tbl.remove(rpr)
        tbl.insert(list(tbl).index(tbl.find(q('tblPr'))), rpr)
        ppr = etree.fromstring(f'<w:pPr xmlns:w="{W}"><w:spacing w:before="0" w:after="0"/></w:pPr>')
        tbl.insert(list(tbl).index(rpr), ppr)
        for typ, sid, name, ppr_xml, rpr_xml in EXTRA:
            base = '<w:basedOn w:val="BodyText"/>' if typ == 'paragraph' else ''
            root.append(etree.fromstring(
                f'<w:style xmlns:w="{W}" w:type="{typ}" w:customStyle="1" w:styleId="{sid}"><w:name w:val="{name}"/>'
                f'{base}<w:qFormat/>' + (f'<w:pPr>{ppr_xml}</w:pPr>' if ppr_xml else '') +
                (f'<w:rPr>{rpr_xml}</w:rPr>' if rpr_xml else '') + '</w:style>'))
        tree.write(str(sp), xml_declaration=True, encoding='UTF-8', standalone=True)
        with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as out:
            for f in sorted(pathlib.Path(tmp).rglob('*')):
                if f.is_file():
                    out.write(f, f.relative_to(tmp).as_posix())


# ------------------------------------------------------------------ 3. finishing the document

A4 = '<w:pgSz w:w="11906" w:h="16838"/><w:pgMar w:top="1021" w:right="1021" w:bottom="1021" w:left="1021" ' \
     'w:header="567" w:footer="567" w:gutter="0"/>'
TEXT_W = 11906 - 2 * 1021


def finish(unpacked, title, author):
    dp = unpacked / 'word' / 'document.xml'
    tree = etree.parse(str(dp))
    body = tree.getroot().find(q('body'))
    sect = body.find(q('sectPr'))
    if sect is None:
        sect = etree.SubElement(body, q('sectPr'))
    for tag in ('pgSz', 'pgMar'):
        for old in sect.findall(q(tag)):
            sect.remove(old)
    # schema order: headerReference, footerReference, footnotePr, endnotePr, type, then pgSz and pgMar
    before = ('headerReference', 'footerReference', 'footnotePr', 'endnotePr', 'type')
    pos = sum(1 for c in sect if etree.QName(c).localname in before)
    for e in reversed(list(etree.fromstring(f'<x xmlns:w="{W}">{A4}</x>'))):
        sect.insert(pos, e)
    for tbl in body.iter(q('tbl')):
        ncols = len(tbl.find(q('tblGrid')))
        widths = [TEXT_W] if ncols == 1 else \
            [int(TEXT_W * 0.15)] + [int(TEXT_W * 0.85 / (ncols - 1))] * (ncols - 1)
        widths[-1] += TEXT_W - sum(widths)
        tpr = tbl.find(q('tblPr'))
        for tag in ('tblW', 'tblLayout'):
            for old in tpr.findall(q(tag)):
                tpr.remove(old)
        tw = etree.Element(q('tblW'))
        tw.set(q('w'), str(TEXT_W))
        tw.set(q('type'), 'dxa')
        order = ['tblStyle', 'tblpPr', 'tblOverlap', 'bidiVisual', 'tblStyleRowBandSize', 'tblStyleColBandSize',
                 'tblW', 'jc', 'tblCellSpacing', 'tblInd', 'tblBorders', 'shd', 'tblLayout', 'tblCellMar', 'tblLook',
                 'tblCaption', 'tblDescription']
        lay = etree.Element(q('tblLayout'))
        lay.set(q('type'), 'fixed')
        for new in (tw, lay):
            rank = order.index(etree.QName(new).localname)
            pos = next((i for i, c in enumerate(tpr) if order.index(etree.QName(c).localname) > rank), len(tpr))
            tpr.insert(pos, new)
        look = tpr.find(q('tblLook'))               # header row and question column use the table style's emphasis
        if look is None:
            look = etree.SubElement(tpr, q('tblLook'))
        for k, v in (('val', '04A0'), ('firstRow', '1'), ('lastRow', '0'), ('firstColumn', '1'), ('lastColumn', '0'),
                     ('noHBand', '0'), ('noVBand', '1')):
            look.set(q(k), v)
        grid = tbl.find(q('tblGrid'))
        for gc, wv in zip(grid, widths):
            gc.set(q('w'), str(wv))
        for i, tr in enumerate(tbl.findall(q('tr'))):
            trpr = tr.find(q('trPr'))
            if trpr is None:
                trpr = etree.Element(q('trPr'))
                tr.insert(0 if tr[0].tag != q('tblPrEx') else 1, trpr)
            for tag in ('cantSplit', 'tblHeader'):
                for old in trpr.findall(q(tag)):
                    trpr.remove(old)
            trpr.insert(0, etree.Element(q('cantSplit')))   # cantSplit comes before tblHeader in the schema
            if i == 0:
                trpr.append(etree.Element(q('tblHeader')))
            col = 0
            for tc in tr.findall(q('tc')):
                tcpr = tc.find(q('tcPr'))
                if tcpr is None:
                    tcpr = etree.Element(q('tcPr'))
                    tc.insert(0, tcpr)
                span = tcpr.find(q('gridSpan'))
                n = int(span.get(q('val'))) if span is not None else 1
                for old in tcpr.findall(q('tcW')):
                    tcpr.remove(old)
                cw = etree.Element(q('tcW'))
                cw.set(q('w'), str(sum(widths[col:col + n])))
                cw.set(q('type'), 'dxa')
                tcpr.insert(0, cw)
                col += n
    tree.write(str(dp), xml_declaration=True, encoding='UTF-8', standalone=True)
    cp = unpacked / 'docProps' / 'core.xml'
    if cp.exists():
        c = cp.read_text(encoding='utf-8')
        c = re.sub(r'<dc:title>.*?</dc:title>|<dc:title/>', '', c)
        c = re.sub(r'<dc:creator>.*?</dc:creator>|<dc:creator/>', '', c)
        c = c.replace('</cp:coreProperties>', f'<dc:title>{html.escape(title)}</dc:title>'
                                              f'<dc:creator>{html.escape(author)}</dc:creator></cp:coreProperties>')
        cp.write_text(c, encoding='utf-8')


def docx_links(path):
    z = zipfile.ZipFile(path)
    rels = etree.fromstring(z.read('word/_rels/document.xml.rels'))
    targets = {r.get('Id'): r.get('Target') for r in rels if r.get('TargetMode') == 'External'}
    doc = etree.fromstring(z.read('word/document.xml'))
    out = []
    for h in doc.iter(q('hyperlink')):
        rid = h.get(q('id', R))
        if rid:
            text = ''.join(t.text or '' for t in h.iter(q('t')))
            url = targets[rid] + ('#' + h.get(q('anchor')) if h.get(q('anchor')) else '')
            out.append((url, text))
    return out


def main(src, out):
    src, out = pathlib.Path(src), pathlib.Path(out)
    if out.exists():
        raise SystemExit(f'{out} exists; documents are never overwritten')
    raw_html = src.read_text(encoding='utf-8')
    title = html.unescape(re.sub(r'<[^>]+>', '', re.search(r'<h1>(.*?)</h1>', raw_html, re.S).group(1))).strip()
    with tempfile.TemporaryDirectory() as tmp:
        tmp = pathlib.Path(tmp)
        (tmp / 'in.html').write_text(prepare_html(raw_html), encoding='utf-8')
        build_reference(tmp / 'reference.docx')
        subprocess.run(['pandoc', str(tmp / 'in.html'), '-f', 'html', '-t', 'docx',
                        '--reference-doc', str(tmp / 'reference.docx'), '-o', str(tmp / 'raw.docx')], check=True)
        unpacked = tmp / 'docx'
        with zipfile.ZipFile(tmp / 'raw.docx') as z:
            z.extractall(unpacked)
        finish(unpacked, title, 'Shakir Zareen')
        with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
            ct = unpacked / '[Content_Types].xml'
            z.write(ct, '[Content_Types].xml')
            for f in sorted(unpacked.rglob('*')):
                if f.is_file() and f != ct:
                    z.write(f, f.relative_to(unpacked).as_posix())
    # every external link of the HTML must be in the docx, unchanged, and nothing else
    want = [html.unescape(u) for u in re.findall(r'href="(https?://[^"]+)"', raw_html)]
    got = [u for u, _ in docx_links(out)]
    missing = sorted(set(want) - set(got))
    extra = sorted(set(got) - set(want))
    if missing or extra or len(got) != len(want):
        raise SystemExit(f'link check failed: {len(want)} in HTML, {len(got)} in docx; missing {missing[:3]}; '
                         f'extra {extra[:3]}')
    print(f'wrote {out}: {len(got)} links, every one identical to the HTML ({len(set(got))} distinct addresses)')


if __name__ == '__main__':
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    main(sys.argv[1], sys.argv[2])
