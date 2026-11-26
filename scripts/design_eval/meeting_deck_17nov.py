#!/usr/bin/env python3
"""Builds the slides for the supervision meeting of 17 November 2026: the evaluation of the designs (carried forward and not), the Winter Conference poster, the progress tracker and the next phase, in the author's biweekly format.

The deck is meetings/17Nov2026/17Nov2026.pptx (10 x 6 in), which the author copied from the last biweekly deck: its two standing
opening slides (Project Brief, Proposed Solution) and its agenda slide are kept, every later slide is dropped, and the content
slides follow the deck's pattern (a 20-point title, an 11-point grey lead, a plain table of 9 to 12 points, on the Blank layout).
The design tables come from the Phase 1 records through phase2_tables.collect(), so the slides and Docs/PHASE2-DESIGNS-*.html
read the same records; the poster is page 1 of the PDF the author placed in the meeting folder; the tracker rows match
Docs/PHD-PROGRESS-TRACKER.xlsx and the author keeps the live tracker on SharePoint (TRACKER_URL). The build is repeatable: run on
its own output it gives the same deck. Writes the deck in place.

Usage: python3 scripts/design_eval/meeting_deck_17nov.py [deck.pptx]
"""
import copy, math, pathlib, subprocess, sys, tempfile
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from phase2_tables import GROUPS, collect   # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parents[2]
MEET = ROOT / 'meetings' / '17Nov2026'
DECK = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else MEET / '17Nov2026.pptx'
POSTER = MEET / 'ShakirZareen-Winter-Conference-2026.pdf'
TRACKER_URL = ('https://liveabertayac-my.sharepoint.com/:x:/g/personal/2411045_uad_ac_uk/cQqBPO-rVzdaSLPJdg6hjweBEgUCkovPq9cUZphHLt0XTo1rFg'
               '?e=4%3Ad9742228e2b140b69898f3c1166bce9b&nav=&sharingS3=true&fromShare=true&CID=0c76701f-0cb3-20aa-8c94-fd885c6027b4')
KEEP = 3                                   # Project Brief, Proposed Solution, agenda
AGENDA = ['Evaluation of the Designs', 'Winter Conference Poster', 'Progress Tracker Updates', 'Next Phase: Implementing 2 + 4 Designs']
GREY, GREEN, AMBER = RGBColor(0x7F, 0x7F, 0x7F), RGBColor(0x1F, 0x6B, 0x3F), RGBColor(0x6B, 0x53, 0x0E)
A = '{http://schemas.openxmlformats.org/drawingml/2006/main}'

prs = Presentation(str(DECK))
BLANK = next(lay for lay in prs.slide_layouts if lay.name == 'Blank')


# ------------------------------------------------------------------------------------------------ the deck's own pattern
def drop_after(keep):
    ids = prs.slides._sldIdLst
    for sid in list(ids)[keep:]:
        prs.part.drop_rel(sid.rId)
        ids.remove(sid)


def set_agenda(lines):
    """The agenda slide keeps its blank lead-in paragraphs; its item lines (32 pt bold) are replaced by `lines`."""
    body = next(sh for sh in prs.slides[KEEP - 1].shapes if sh.has_text_frame).text_frame._txBody
    paras = body.findall(A + 'p')
    items = [p for p in paras if p.find(A + 'r') is not None]
    model, anchor = copy.deepcopy(items[0]), paras[-1]
    for p in items:
        body.remove(p)
    for line in lines:
        p = copy.deepcopy(model)
        for r in p.findall(A + 'r')[1:]:
            p.remove(r)
        p.find(A + 'r').find(A + 't').text = line
        anchor.addprevious(p)


def content_slide(title, lead, link=None):
    """Title and grey lead line at the deck's positions; `link` = (word in the lead, url) makes that word a hyperlink."""
    sl = prs.slides.add_slide(BLANK)
    t = sl.shapes.add_textbox(Inches(0.34), Inches(0.22), Inches(9.33), Inches(0.44)).text_frame
    t.word_wrap = True
    r = t.paragraphs[0].add_run(); r.text = title; r.font.size = Pt(20); r.font.bold = True
    tf = sl.shapes.add_textbox(Inches(0.34), Inches(0.72), Inches(9.33), Inches(0.47)).text_frame
    tf.word_wrap = True
    parts = lead.split(link[0], 1) if link else [lead]
    for i, text in enumerate(parts):
        if i:
            r = tf.paragraphs[0].add_run(); r.text = link[0]; r.font.size = Pt(11); r.hyperlink.address = link[1]
        r = tf.paragraphs[0].add_run(); r.text = text; r.font.size = Pt(11); r.font.color.rgb = GREY
    return sl


def fill(cell, value, size, bold=False, color=None):
    """A cell's text; a list gives one paragraph per item, and an item (text, 'muted') is set in grey."""
    items = value if isinstance(value, list) else [value]
    tf = cell.text_frame
    tf.text = ''
    for i, item in enumerate(items):
        text, style = item if isinstance(item, tuple) else (item, '')
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        r = p.add_run(); r.text = str(text); r.font.size = Pt(size if style != 'muted' else size - 1); r.font.bold = bold and style != 'muted'
        if style == 'muted' or color:
            r.font.color.rgb = GREY if style == 'muted' else color


def table(sl, head, rows, widths, top=1.34, size=12, row_h=0.38, colors=None, left=0.34):
    """The deck's plain table (PowerPoint's "No Style, Table Grid"): bold header, bold first column. `colors` maps
    (row, column) to a text colour."""
    n, m = len(rows) + 1, len(head)
    shp = sl.shapes.add_table(n, m, Inches(left), Inches(top), Inches(sum(widths)), Inches(row_h * n))
    tblPr = shp._element.graphic.graphicData.tbl.tblPr
    for attr in ('firstRow', 'bandRow'):
        tblPr.set(attr, '0')
    sid = tblPr.find(A + 'tableStyleId')
    if sid is not None:
        sid.text = '{5940675A-B579-460E-94D1-54222C63F5DA}'
    tb = shp.table
    for j, w in enumerate(widths):
        tb.columns[j].width = Inches(w)
    tb.rows[0].height = Inches(0.3 if size < 11 else 0.36)
    for j, h in enumerate(head):
        fill(tb.cell(0, j), h, size, bold=True)
    for i, row in enumerate(rows, 1):
        for j, v in enumerate(row):
            fill(tb.cell(i, j), v, size, bold=(j == 0), color=(colors or {}).get((i, j)))
    return tb


def notes(sl, text):
    sl.notes_slide.notes_text_frame.text = text


def poster_image(width_px=1400):
    """Page 1 of the author's poster PDF as a JPEG in a temporary folder (the deck embeds it)."""
    out = pathlib.Path(tempfile.mkdtemp()) / 'poster'
    subprocess.run(['pdftoppm', '-jpeg', '-jpegopt', 'quality=88', '-scale-to', str(width_px), '-singlefile', str(POSTER), str(out)], check=True)
    return out.with_suffix('.jpg')


# ------------------------------------------------------------------------------------------------ the records
rows, SIX = collect()
n_out = sum(len(v) for v in rows.values())
review_out = {k: sum(1 for r in v if r[3] != 'new') for k, v in rows.items()}
new_out = {k: sum(1 for r in v if r[3] == 'new') for k, v in rows.items()}
n_new = len(SIX) - 2 + sum(new_out.values())          # designs of the new search: carried forward + not
n_no_code = review_out['no-code-buildable'] + review_out['no-code-unclear'] + review_out['no-code-missing']
on_request = sum(1 for r in rows['no-code-missing'] if 'request' in r[4])
assert len(SIX) == 6 and n_out + len(SIX) == 45 + n_new, (len(SIX), n_out, n_new)

THREATS = {'poisoning or Byzantine updates': 'poisoning', 'malicious or Sybil participants': 'fake nodes (Sybil)', 'free riding': 'free riding',
           'verification of training or aggregation': 'verification', 'verification of inference': 'verification (of inference)',
           'fake participants (identity)': 'fake nodes (identity)', 'verification of aggregation': 'verification (of aggregation)'}
VENUE = {'Internet of Things (Elsevier)': 'Internet of Things (Elsevier)', 'Sensors (MDPI)': 'Sensors (MDPI)',
         'ACM SIGKDD Conference on Knowledge Discovery and Data Mining (KDD)': 'ACM KDD',
         'IEEE Symposium on Security and Privacy (S&P)': 'IEEE S&P', 'ACM SIGSAC Conference on Computer and Communications Security (CCS)': 'ACM CCS',
         'arXiv preprint': 'arXiv preprint, not peer reviewed'}
DOES = {   # in the slides' own words, shorter than the page's approach column
    'zkPET': 'Federated energy forecasting; zk-SNARK proofs (EZKL) that each forecast comes from the published model',
    'FL-BC-IDS': 'Hierarchical federated intrusion detection with DP-XGBoost; Groth16 proofs of membership and aggregation; evidence on Ethereum',
    'PoL-BFL': 'Clients prove their local training (Groth16); Solidity contracts verify the proofs on chain and pay the incentives',
    'RoFL': 'Secure aggregation in which each client proves, in zero knowledge, that its hidden update stays within a norm bound',
    'zkPoT': 'A proof that a model (logistic regression) was trained correctly on committed data, revealing neither the data nor the model',
    'zk-DEAP': 'Encrypted aggregation with no server; each contribution carries a zero-knowledge proof that it is well formed',
}


def first_author(who):
    """'Hu 2026 · HHB-FL' -> 'Hu et al., 2026'"""
    name, year = who.split(' · ')[0].rsplit(' ', 1)
    return f'{name} et al., {year}'


# ------------------------------------------------------------------------------------------------ the slides
drop_after(KEEP)
set_agenda(AGENDA)

# 1. evaluation: how each design was checked
sl = content_slide('Design evaluation — how each design was checked',
                   f'Every design went through the same four questions. Only 2 of the review\'s 45 came out with code we can use, '
                   f'so I searched outside the review for designs that have it and found {n_new}.')
table(sl, ['Question', 'How I answered it', 'Review (45)', f'New search ({n_new})'], [
    ['Is there code?', 'Links in the paper, then GitHub, Papers with Code, Software Heritage and the authors\' other repositories',
     f'{45 - n_no_code} have code; 1 more offers it on request' if on_request == 1 else f'{45 - n_no_code} have code',
     f'All {n_new}: the search asked for code'],
    ['May we run and adapt it?', 'The licence file, or the licence stated in the README',
     f'2 MIT; {review_out["code-no-licence"]} with no licence', f'{n_new - new_out["code-no-licence"]} licensed; {new_out["code-no-licence"]} where the paper\'s own code has none'],
    ['Is it the paper\'s own code?', 'Every page scanned for links (OCR-verified text); an AI reader on the passages about code; repositories compared file by file',
     'Both MIT ones are the repositories their papers name', f'{n_new - new_out["code-no-licence"] - new_out["code-not-declared"]} yes; {new_out["code-not-declared"]} papers name no code or promise it later'],
    ['Without code, can it be built?', 'An AI reader per design on four core parts: privacy mechanism, update check, message flow, ledger; every quotation found on its page by script',
     f'{review_out["no-code-buildable"]} only with gaps; {review_out["no-code-unclear"]} too unclear; {review_out["no-code-missing"]} miss a core part', '—'],
    ['Carried forward', 'Code the paper names, under a licence that lets us run and adapt it', '2', str(len(SIX) - 2)],
], [1.75, 3.85, 1.95, 1.78], size=12, row_h=0.5)
notes(sl, 'Two to three minutes. The order matters: a design with no licence was not judged on its algorithm unless it was also '
          'buildable. The readers report verdicts and pages; nothing of the papers\' text came to me.')

# 2. evaluation: the six carried forward
sl = content_slide('The six designs carried forward — 2 + 4',
                   'Each has code that its paper names, under the MIT licence. I reproduced zkPET and FL-BC-IDS in October; '
                   'the four new ones have not been run yet.')
six = []
for z, nm, paper, au, venue, yr, pr, appr, code, zk, led, thr, tb in SIX:
    threats = ', '.join(dict.fromkeys(THREATS.get(t.strip(), t.strip()) for t in thr.split(', ') if t.strip()))
    surname = au.split(' et al.')[0].split()[-1]        # 'Xiubo Wei et al.' -> 'Wei et al.'
    six.append([nm, [paper, (f'{surname} et al.', 'muted')], f'{VENUE.get(venue, venue)}, {yr}', DOES[nm], threats])
table(sl, ['Design', 'Paper', 'Venue, year', 'What it does', 'Our threats it covers'], six,
      [1.0, 2.95, 1.2, 2.8, 1.38], size=9, row_h=0.62)
notes(sl, 'zkPET and FL-BC-IDS come from the review; PoL-BFL, RoFL, zkPoT and zk-DEAP from the new search. zk-DEAP is an arXiv '
          'preprint: its Figshare artifact is byte-identical to its GitHub repository. RoFL has a second repository of its own, '
          'fl-analysis, for the robustness analysis.')

# 3. evaluation: the rest, by reason
sl = content_slide(f'The {n_out} not carried forward — grouped by the reason',
                   f'{n_no_code} of the review\'s 45 designs have no code at all. Where code exists, either no licence lets us use it or '
                   f'the paper does not name it. Every title is in the backup slides.')
BRING = {
    'code-no-licence': ('Code, but no licence', 'The code is public, but no licence lets us run or adapt it. For zkDL, the licensed copy is not the code the paper names',
                        'A licence from the authors, or their written permission'),
    'code-not-declared': ('Licensed code the paper does not name', 'An author\'s repository is open, but the paper names no code, or promises it after peer review',
                          'The paper\'s own release, or the authors confirming it is the paper\'s code'),
    'no-code-buildable': ('No code; buildable only with gaps', 'At least one core part is only partly specified, so I would be filling gaps myself',
                          'Building it with the gaps stated; the results would be my version, not the paper\'s'),
    'no-code-unclear': ('No code; core too unclear', 'Nothing is missing outright, but the core is too vague to build without inventing it', 'The authors\' code'),
    'no-code-missing': ('No code; a core part missing', 'The paper leaves out the privacy mechanism, the update check or the message flow',
                        'The authors\' code' + (f'; {on_request} of these offers it on request' if on_request else '')),
}


def count(key):
    r, w = review_out[key], new_out[key]
    return f'{r + w} ({r} review, {w} new)' if r and w else f'{r + w} ({"new" if w else "review"})'


table(sl, ['Reason', 'Designs', 'What it means', 'What would bring it back'],
      [[BRING[k][0], count(k), BRING[k][1], BRING[k][2]] for k, _, _ in GROUPS], [2.05, 1.35, 3.33, 2.6], size=12, row_h=0.5)
notes(sl, 'The largest group, buildable only with gaps, is where a design could be rebuilt; I would rather run published code first.')

# 4. the Winter Conference poster
sl = content_slide('Winter Conference — the poster',
                   'PGRS Winter Conference at Abertay, 2–3 December. The poster is about the PhD, not the review; '
                   'it goes to the Graduate School by 12 noon on Wednesday 18 November.')
table(sl, ['Point', 'Detail'], [
    ['Title', 'Keeping smart devices private and honest while they learn together'],
    ['The story', 'The problem; why it is hard (privacy says nobody may look, security says someone must check); the aim; the road ahead'],
    ['The idea', 'A quiz with known answers, marked in pieces; only the verdict goes on the blockchain'],
    ['Format', 'A1 portrait on the University template, plain words for a mixed audience, no references'],
    ['My slot', 'Thursday 3 December, 12:00 to 13:00, standing by the poster'],
    ['From you', 'Comments on the draft, and how your names should appear: their order and titles'],
], [1.25, 4.65], size=12, row_h=0.5)
img = poster_image()
pic = sl.shapes.add_picture(str(img), Inches(6.55), Inches(1.34), height=Inches(4.45))
pic.left = Inches(10 - 0.34) - pic.width
notes(sl, 'A short item. The deadline is fixed: after it, printing is at my own cost.')

# 5. the progress tracker
sl = content_slide('Progress tracker — what changes this time',
                   'The tracker is on SharePoint; I will make these changes there after the meeting.', link=('SharePoint', TRACKER_URL))
table(sl, ['Task', 'Dates', 'Status', 'Update'], [
    ['Phase 1: Analyse the 45 designs for evaluation', '9–17 Nov', 'Done',
     'All 45 checked. Only 2 had code we can use, so I widened it to a search outside the review: 2 + 4 designs go forward'],
    ['Phase 2: Implement and run the designs that can be evaluated', '9–24 Nov; to agree', 'Not started',
     'Starts after this meeting with the six designs; code for all six and data for two are in hand. New dates today'],
    ['Winter Conference poster (new row)', '16–18 Nov', 'In progress',
     'Due at 12 noon on Wednesday 18 November; the poster session is on Thursday 3 December'],
], [2.6, 1.35, 1.25, 4.13], size=12, row_h=0.6, colors={(1, 2): GREEN, (2, 2): GREY, (3, 2): AMBER})
notes(sl, 'Phase 2\'s row says its dates are to be agreed at this meeting.')

# 6. the next phase
sl = content_slide('Next phase — implementing the 2 + 4 designs',
                   'Each design runs first as its authors published it, so I have its own numbers to compare against. Then it moves into '
                   'Gotham with the 5G simulator: some edge nodes on cable, some on 5G. The order below is the order I would take them in.')
table(sl, ['Design', 'Its code', 'Data', 'Step 1: as published', 'Step 2: in Gotham + 5G'], [
    ['zkPET', 'Python, EZKL proofs, a local EVM', 'Electricity data, in hand', 'Done, October', 'Sites as nodes; proof cost per site on cable and on 5G'],
    ['FL-BC-IDS', 'Python, XGBoost, Circom proofs, Ethereum', 'CICIoV2024, in hand', 'Done, October, with a scale sweep and published attacks',
     'Vehicles and roadside units as nodes; the poisoning and Sybil runs again, over the network'],
    ['PoL-BFL', 'Python, Solidity, circom, a local EVM', 'MNIST, CIFAR, FEMNIST: named in its code, to fetch', 'To run',
     'Clients and the chain on separate nodes; its claims on poisoning, Sybil and free riding'],
    ['RoFL', 'Rust, with Python clients; fl-analysis', 'MNIST, CIFAR-10, FEMNIST: named in its code, to fetch', 'To run',
     'Deployed by its own Ansible scripts; backdoors against its norm bound'],
    ['zk-DEAP', 'Rust, in Docker', 'Inputs fixed in its tests', 'To run, with its 60 attack tests', 'Containers as nodes; the same 60 tests over the network'],
    ['zkPoT', 'Rust', 'Dummy data its code generates; needs a lot of memory', 'To run', 'Proof cost on an edge-sized node; a building block against free riding'],
], [1.0, 2.1, 1.9, 1.7, 2.63], size=11, row_h=0.5)
notes(sl, 'Every run uses the design\'s own code. The attacks follow published protocols only, as with FL-BC-IDS in October.')

# backup: every design not carried forward, by reason
CAP, HEAD_H = 4.2, 0.3                      # inches of table per slide (it ends by 5.55 in); header row
entries = [(BRING[k][0], t, first_author(w) + (' (code on request)' if 'request' in nt else ''), 'new' if src == 'new' else 'review')
           for k, _, _ in GROUPS for i, w, t, src, nt in rows[k]]


def row_height(e):
    """Estimated height of a backup row: 9-point Aptos fits about 88 characters a line in the paper column."""
    return max(0.28, 0.1 + 0.15 * math.ceil(len(e[1]) / 88))


def paginate(items, cap):
    """Split the rows into the fewest slides that fit, with about the same height on each."""
    total = sum(map(row_height, items))
    for n in range(max(1, math.ceil(total / (cap - HEAD_H))), len(items) + 1):
        target, out, cur, h = total / n, [], [], 0.0
        for e in items:
            if cur and len(out) < n - 1 and h + row_height(e) / 2 > target:
                out.append(cur); cur, h = [], 0.0
            cur.append(e); h += row_height(e)
        out.append(cur)
        if all(HEAD_H + sum(map(row_height, pg)) <= cap for pg in out):
            return out
    return [[e] for e in items]


pages = paginate(entries, CAP)
for n, page in enumerate(pages, 1):
    sl = content_slide(f'Backup — the {n_out} not carried forward ({n} of {len(pages)})', 'By reason, with the first author and year.')
    tb = table(sl, ['Reason', 'Paper', 'First author, year', 'From'], [list(e) for e in page], [1.8, 5.13, 1.65, 0.75], size=9, row_h=0.28)
    start = 0                                 # one reason cell per group on the slide: page[start..k-1] are table rows start+1..k
    for k in range(1, len(page) + 1):
        if k == len(page) or page[k][0] != page[start][0]:
            if k - 1 > start:
                tb.cell(start + 1, 0).merge(tb.cell(k, 0))
                for r in range(start + 2, k + 1):
                    tb.cell(r, 0).text_frame.text = ''
                fill(tb.cell(start + 1, 0), page[start][0], 9, bold=True)
            start = k

prs.save(str(DECK))
print('written', DECK, '|', len(prs.slides), 'slides:', KEEP, 'kept,', 6, 'content,', len(pages), 'backup')
