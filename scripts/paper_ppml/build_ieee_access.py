#!/usr/bin/env python3
"""Renders a built version of the PPML review into the IEEE Access Word template (the author, 20 October 2026: "we need to
format the paper for IEEE Access"; "we dont need key takeaway sections in the IEEE Access format"): pandoc converts the build's
markdown (build/paper-V<n>.md) with the template (myliteraturereviewpaper/ppml2026/ieee-access-template/Access-Template-2024.docx)
as its reference document, so the template's styles come across; this script then removes the Key Takeaways boxes and the
abbreviation list, strips the numbering the template's styles add themselves (roman numerals on level-1 headings, letters on
level-2, "FIGURE n." on captions, "[n]" on references), turns table numbers arabic, maps pandoc's styles to the template's
(H1_List, H2_First/H2_Cont, PARA, PARA_Indent, Fig Caption, Table Title, References), writes the single-column title block
(date and DOI placeholders, title, author line, affiliation, corresponding author, funding footnote, ABSTRACT, INDEX TERMS), sets
the two-column body with every table and figure spanning both columns, carries the template's header image and footer, and ends
with the author-biography placeholder. Facts only the author can supply stay as [AUTHOR: …] markers. Writes
"<NAME> - V<n> IEEE Access.docx" beside the paper (never over an existing file).
Usage: scripts/.venv/bin/python scripts/paper_ppml/build_ieee_access.py <version> [<tag>]   (tag, e.g. V2: a second rendering
of the same version, written as "… - V<n> IEEE Access <tag>.docx"; the first rendering is never overwritten)
"""
import copy, pathlib, re, subprocess, sys, tempfile
from docx import Document
from docx.shared import Inches, Pt, Emu
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

ROOT = pathlib.Path(__file__).resolve().parents[2]
P = ROOT / 'myliteraturereviewpaper' / 'ppml2026'; B = P / 'build'
TEMPLATE = P / 'ieee-access-template' / 'Access-Template-2024.docx'
OUT = ROOT / 'myliteraturereviewpaper' / 'PPML in NextGeneration IoT'
NAME = 'Privacy Preserving Machine Learning in NextGeneration IoT'
ROMAN = {r: i for i, r in enumerate(['I', 'II', 'III', 'IV', 'V', 'VI', 'VII', 'VIII', 'IX', 'X', 'XI', 'XII', 'XIII', 'XIV', 'XV', 'XVI', 'XVII', 'XVIII', 'XIX', 'XX'], 1)}
UNNUMBERED = ('Declarations', 'Appendix', 'References', 'Acknowledgment', 'Acknowledgement')
TEXT_W = 6.98   # inches between the template's margins
MAX_FIG_H = 8.2 # inches: a figure never outgrows the page body (10.875 in page, 0.9 + 0.72 in margins) with its caption


def prepare_markdown(md):
    """the build's markdown made ready for the template: front matter, abstract, index terms and the abbreviation list taken
    out (returned apart), Key Takeaways boxes dropped, headings and captions without the numbering the styles add"""
    m = re.match(r'---\n(.*?)\n---\n', md, flags=re.S); front = m.group(1) if m else ''; body = md[m.end():] if m else md
    title = re.search(r'^title:\s*"(.*)"', front, flags=re.M); title = title.group(1) if title else NAME
    author = re.search(r'^author:\s*"(.*)"', front, flags=re.M); author = author.group(1) if author else ''
    abstract = re.search(r'^\*\*Abstract\*\*\s*[—-]\s*(.*?)\n\n', body, flags=re.S | re.M); abstract_text = abstract.group(1).strip() if abstract else ''
    terms = re.search(r'^\*\*Index Terms\*\*\s*[—-]\s*(.*?)\n\n', body, flags=re.S | re.M); terms_text = terms.group(1).strip() if terms else ''
    body = body[abstract.start():] if abstract else body
    body = re.sub(r'^\*\*Abstract\*\*.*?\n\n', '', body, count=1, flags=re.S | re.M)
    body = re.sub(r'^\*\*Index Terms\*\*.*?\n\n', '', body, count=1, flags=re.S | re.M)
    body = re.sub(r'^\*\*List of Abbreviations\*\*\n\n(\|.*\n)+\n?', '', body, count=1, flags=re.M)      # defined at first use in the text
    body = re.sub(r'^```\{=openxml\}\n.*?^```\n', '', body, flags=re.S | re.M)                              # the Key Takeaways boxes
    body = re.sub(r'^# ([IVX]+)\. ', '# ', body, flags=re.M)                                                 # roman numerals: the style numbers
    body = re.sub(r'^## ([A-Z])\. ', '## ', body, flags=re.M)                                                 # letters: the style numbers
    body = re.sub(r'^!\[Fig\. \d+\. ', '![', body, flags=re.M)                                                # FIGURE n. comes from the style
    body = re.sub(r'^Table: Table ([IVX]+)\. ', lambda m: f'Table: TABLE {ROMAN[m.group(1)]}. ', body, flags=re.M)
    body = re.sub(r'\bTable ([IVX]+)\b(?![.\w])', lambda m: f'Table {ROMAN[m.group(1)]}' if m.group(1) in ROMAN else m.group(0), body)   # in-text mentions
    body = re.sub(r'^\[(\d+)\] ', '', body, flags=re.M)                                                       # [n] comes from the style
    return title, author, abstract_text, terms_text, body


def sect_pr(cols, continuous=True, space=400):
    s = OxmlElement('w:sectPr')
    if continuous:
        t = OxmlElement('w:type'); t.set(qn('w:val'), 'continuous'); s.append(t)
    pg = OxmlElement('w:pgSz'); pg.set(qn('w:w'), str(int(8.0 * 1440))); pg.set(qn('w:h'), str(int(10.875 * 1440))); s.append(pg)
    mar = OxmlElement('w:pgMar')
    for k, v in (('top', 0.9), ('right', 0.51), ('bottom', 0.72), ('left', 0.51), ('header', 0.5), ('footer', 0.4), ('gutter', 0)): mar.set(qn(f'w:{k}'), str(int(v * 1440)))
    s.append(mar)
    c = OxmlElement('w:cols'); c.set(qn('w:num'), str(cols)); c.set(qn('w:space'), str(space)); s.append(c)
    return s


def para_with_sectpr(doc, cols, before_el=None):
    p = OxmlElement('w:p'); ppr = OxmlElement('w:pPr'); ppr.append(sect_pr(cols)); p.append(ppr)
    if before_el is not None: before_el.addprevious(p)
    else: doc.element.body.append(p)
    return p


def set_style(p, name):
    p.style = name


def new_num(doc, abstract_num_id):
    """a fresh numbering instance of an abstract numbering (restart at 1), as the template does for each section's level-2 headings"""
    numbering = doc.part.numbering_part.element
    ids = [int(n.get(qn('w:numId'))) for n in numbering.findall(qn('w:num'))]; nid = max(ids + [0]) + 1
    num = OxmlElement('w:num'); num.set(qn('w:numId'), str(nid))
    a = OxmlElement('w:abstractNumId'); a.set(qn('w:val'), str(abstract_num_id)); num.append(a)
    lo = OxmlElement('w:lvlOverride'); lo.set(qn('w:ilvl'), '0'); so = OxmlElement('w:startOverride'); so.set(qn('w:val'), '1'); lo.append(so); num.append(lo)
    numbering.append(num); return nid


def abstract_num_of(doc, style_name):
    st = doc.styles[style_name].element; numPr = st.find(qn('w:pPr') + '/' + qn('w:numPr')) if st.find(qn('w:pPr')) is not None else None
    if numPr is None and doc.styles[style_name].base_style is not None: return abstract_num_of(doc, doc.styles[style_name].base_style.name)
    nid = numPr.find(qn('w:numId')).get(qn('w:val'))
    for n in doc.part.numbering_part.element.findall(qn('w:num')):
        if n.get(qn('w:numId')) == nid: return n.find(qn('w:abstractNumId')).get(qn('w:val'))


def set_num(p, num_id):
    ppr = p._p.get_or_add_pPr(); numPr = ppr.find(qn('w:numPr'))
    if numPr is None: numPr = OxmlElement('w:numPr'); ppr.append(numPr)
    for c in list(numPr): numPr.remove(c)
    il = OxmlElement('w:ilvl'); il.set(qn('w:val'), '0'); ni = OxmlElement('w:numId'); ni.set(qn('w:val'), str(num_id)); numPr.append(il); numPr.append(ni)


def main(version, tag=''):
    import re as _re
    ROMAN = {r: n + 1 for n, r in enumerate(['I', 'II', 'III', 'IV', 'V', 'VI', 'VII', 'VIII', 'IX', 'X', 'XI', 'XII', 'XIII', 'XIV', 'XV', 'XVI', 'XVII', 'XVIII', 'XIX', 'XX'])}
    md = (B / f'paper-V{version}.md').read_text(encoding='utf-8')
    title, author, abstract, terms, body = prepare_markdown(md)
    tmp = pathlib.Path(tempfile.mkdtemp()); (tmp / 'body.md').write_text(body, encoding='utf-8')
    subprocess.run(['pandoc', str(tmp / 'body.md'), '--reference-doc', str(TEMPLATE), '-o', str(tmp / 'body.docx')], check=True, cwd=B)
    doc = Document(str(tmp / 'body.docx'))
    tpl = Document(str(TEMPLATE))
    _m = _re.search(r'^Table: Table ([IVXL]+)\. Use of generative AI', md, _re.M)
    ai_table_no = ROMAN[_m.group(1)] if _m else None                             # the acknowledgment names the AI-use table (V86)
    # ---- styles: pandoc's names to the template's; numbering restarts per section for level-2 headings
    h2_abs = abstract_num_of(doc, 'H2_Cont'); cur_h2_num = None; after_heading = False; in_refs = False
    def style_id(p):
        ps = p._p.find(qn('w:pPr') + '/' + qn('w:pStyle')); return ps.get(qn('w:val')) if ps is not None else 'Normal'
    for p in doc.paragraphs:
        sid = style_id(p); txt = p.text.strip()
        st = {'Heading1': 'Heading 1', 'Heading2': 'Heading 2', 'Heading3': 'Heading 3', 'ImageCaption': 'Image Caption', 'TableCaption': 'Table Caption',
              'FirstParagraph': 'First Paragraph', 'BodyText': 'Body Text', 'CaptionedFigure': 'Captioned Figure'}.get(sid, p.style.name)
        if st == 'Captioned Figure':
            p.alignment = 1; continue
        if st == 'Heading 1':
            if txt.startswith(UNNUMBERED):
                if txt.startswith('References') and ai_table_no:
                    p.insert_paragraph_before('ACKNOWLEDGMENT', style='H1')
                    p.insert_paragraph_before(f'Claude (Anthropic) was used as described in Table {ai_table_no}; the reviewer verified its output and is responsible for the content.', style='PARA')
                set_style(p, 'H1'); in_refs = txt.startswith('References')
            else:
                set_style(p, 'H1_List (Space)'); in_refs = False
            for r in p.runs: r.text = r.text.upper()
            cur_h2_num = new_num(doc, h2_abs); after_heading = True
        elif st == 'Heading 2':
            set_style(p, 'H2_Cont'); set_num(p, cur_h2_num or new_num(doc, h2_abs))
            for r in p.runs: r.text = r.text.upper()
            after_heading = True
        elif st == 'Heading 3':
            set_style(p, 'H3'); after_heading = True
        elif st in ('Image Caption', 'Caption'):
            set_style(p, 'Fig Caption'); after_heading = True
        elif st == 'Table Caption':
            set_style(p, 'Table Title'); after_heading = True
        elif in_refs and txt:
            set_style(p, 'References')
        elif st in ('First Paragraph', 'Body Text', 'Normal', 'Compact', 'Body Text 2'):
            if not txt: continue
            set_style(p, 'PARA' if after_heading else 'PARA_Indent'); after_heading = False
    # ---- tables: rebuilt as fresh tables (pandoc's table XML renders in a sliver in LibreOffice; a fresh table with the same
    # ---- cell content does not), the template's borders, small text, full width, grid widths scaled from pandoc's
    tbl_borders = tpl.tables[0]._tbl.tblPr.find(qn('w:tblBorders'))
    for old_t in list(doc.tables):
        rows, cols = len(old_t.rows), len(old_t.columns)
        grid = [int(g.get(qn('w:w'))) for g in old_t._tbl.find(qn('w:tblGrid')).findall(qn('w:gridCol'))] if old_t._tbl.find(qn('w:tblGrid')) is not None else [1] * cols
        total = sum(grid) or 1; widths = [Inches(TEXT_W) * g / total for g in grid]
        new_t = doc.add_table(rows=rows, cols=cols)
        for i, row in enumerate(old_t.rows):
            for j, cell in enumerate(row.cells):
                if j >= cols: continue
                nc = new_t.cell(i, j)
                for p0 in list(nc.paragraphs): p0._p.getparent().remove(p0._p)
                for p in cell.paragraphs:
                    np_ = copy.deepcopy(p._p); ps = np_.find(qn('w:pPr') + '/' + qn('w:pStyle'))
                    if ps is not None: ps.getparent().remove(ps)
                    nc._tc.append(np_)
                for p in nc.paragraphs:
                    for r in p.runs: r.font.size = Pt(7.5)
                nc.width = widths[j]
        if rows:
            trPr = new_t.rows[0]._tr.get_or_add_trPr(); th = OxmlElement('w:tblHeader'); th.set(qn('w:val'), 'on'); trPr.append(th)
        tblPr = new_t._tbl.tblPr
        for old in tblPr.findall(qn('w:tblBorders')): tblPr.remove(old)
        if tbl_borders is not None: tblPr.append(copy.deepcopy(tbl_borders))
        w = tblPr.find(qn('w:tblW'))
        if w is None: w = OxmlElement('w:tblW'); tblPr.append(w)
        w.set(qn('w:type'), 'pct'); w.set(qn('w:w'), '5000')
        old_t._tbl.addnext(new_t._tbl); old_t._tbl.getparent().remove(old_t._tbl)
    # ---- figures: the full text width, unless that would make a tall figure outgrow the page (then its height is capped and
    # ---- it is centred); the PNGs come trimmed of their white margins (figures_static.trim), so the box is the drawing
    for shp in doc.inline_shapes:
        ratio = shp.height / shp.width; w_in = min(TEXT_W, MAX_FIG_H / ratio)
        shp.width = Inches(w_in); shp.height = int(Inches(w_in) * ratio)
    # ---- the title block (single column), in the template's styles, before the first body paragraph
    first = doc.paragraphs[0]
    def before(text, style, bold_prefix=None):
        p = first.insert_paragraph_before('', style=style)
        if bold_prefix: r = p.add_run(bold_prefix); r.bold = True
        p.add_run(text); return p
    before('Date of publication xxxx 00, 0000, date of current version xxxx 00, 0000.', 'DOP')
    before('Digital Object Identifier 10.1109/ACCESS.2026.Doi Number', 'DOI')
    before(title, 'Paper Title')
    before(f'{author.split(",")[0].strip()}1 (ORCID 0009-0005-2841-4373) [AUTHOR: co-authors and memberships to add]', 'AU')
    before('1Faculty of Design, Informatics and Business, Abertay University, Dundee DD1 1HG, U.K.', 'PI_No Space')
    before('Corresponding author: Shakir Zareen (e-mail: s.zareen2400@abertay.ac.uk).', 'PI')
    before('[AUTHOR: funding and support statement, as the template\'s first footnote: "This work was supported in part by …".]', 'footnote text')
    before(abstract, 'Abstract', bold_prefix='ABSTRACT ')
    it = before(terms, 'IT', bold_prefix='INDEX TERMS ')
    it._p.get_or_add_pPr().append(sect_pr(1, continuous=True, space=720))          # the title block ends here, single column
    # ---- full-width spans for every table and figure: a two-column section ends before, a one-column section ends after
    body_el = doc.element.body
    blocks = [el for el in body_el if el.tag in (qn('w:p'), qn('w:tbl'))]
    def is_fig(el): return el.tag == qn('w:p') and el.find('.//' + qn('w:drawing')) is not None
    def is_caption(el, kind): 
        if el.tag != qn('w:p'): return False
        ps = el.find(qn('w:pPr') + '/' + qn('w:pStyle')); return ps is not None and ps.get(qn('w:val')) == kind
    style_ids = {s.name: s.style_id for s in doc.styles}
    i = 0
    while i < len(blocks):
        el = blocks[i]
        if el.tag == qn('w:tbl'):
            if len(el.findall('.//' + qn('w:gridCol'))) <= 3:                    # a narrow table stays in the column flow (V86)
                i += 1; continue
            start = i - 1 if i > 0 and is_caption(blocks[i - 1], style_ids.get('Table Title')) else i
            end = i
        elif is_fig(el):
            start = i; end = i + 1 if i + 1 < len(blocks) and is_caption(blocks[i + 1], style_ids.get('Fig Caption')) else i
        else:
            i += 1; continue
        para_with_sectpr(doc, 2, before_el=blocks[start])
        closer = OxmlElement('w:p'); ppr = OxmlElement('w:pPr'); ppr.append(sect_pr(1)); closer.append(ppr); blocks[end].addnext(closer)
        i = end + 1
    # ---- the author biography placeholder, then the final section properties: two columns, the template's page
    bio = doc.add_paragraph('[AUTHOR: biography and photograph of each author, as the template\'s last section.]', style='AU_Bios')
    final = body_el.find(qn('w:sectPr'))
    if final is not None: body_el.remove(final)
    body_el.append(sect_pr(2, continuous=False))
    # ---- header image and footer from the template
    tpl_hdr = tpl.sections[1].header; img_part = next(r.target_part for r in tpl_hdr.part.rels.values() if 'image' in r.reltype)
    jpg = tmp / 'access-header.jpeg'; jpg.write_bytes(img_part.blob); img_path = tmp / 'access-header.png'
    subprocess.run(['sips', '-s', 'format', 'png', str(jpg), '--out', str(img_path)], check=True, capture_output=True)   # python-docx cannot read this JPEG
    for sec in doc.sections:
        sec.header.is_linked_to_previous = False; sec.footer.is_linked_to_previous = False
        hp = sec.header.paragraphs[0] if sec.header.paragraphs else sec.header.add_paragraph()
        for r in list(hp.runs): r._r.getparent().remove(r._r)
        hp.add_run().add_picture(str(img_path), width=Emu(1169670))
        fp = sec.footer.paragraphs[0] if sec.footer.paragraphs else sec.footer.add_paragraph()
        for r in list(fp.runs): r._r.getparent().remove(r._r)
        r = fp.add_run('VOLUME XX, 2026\t'); r.font.size = Pt(8)
        fld = OxmlElement('w:fldSimple'); fld.set(qn('w:instr'), 'PAGE'); rr = OxmlElement('w:r'); t = OxmlElement('w:t'); t.text = '1'; rr.append(t); fld.append(rr); fp._p.append(fld)
    out = OUT / f'{NAME} - V{version} IEEE Access{(" " + tag) if tag else ""}.docx'
    if out.exists(): sys.exit(f'{out.name} exists; versions are never overwritten')
    doc.save(str(out)); print('written', out.relative_to(ROOT), '|', len(doc.paragraphs), 'paragraphs,', len(doc.tables), 'tables,', len(doc.inline_shapes), 'figures')


if __name__ == '__main__':
    if len(sys.argv) < 2: sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else '')
