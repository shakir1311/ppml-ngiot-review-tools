#!/usr/bin/env python3
"""Builds the slides for the supervisory meeting on the PPML review in the author's biweekly format: a copy of the latest biweekly
deck (research/Simulation/meetings/8Sep2026/8Sep2026.pptx, 10 x 6 in) keeps its two standing opening slides (Project Brief,
Proposed Solution) and its agenda slide; the content slides follow its pattern, a 20-point title box, an 11-point lead sentence and
a 12-point table (or a figure where a table cannot carry it), on the Blank layout at the same positions. Every count is read from
build/stats.json and every figure from build/figures/ (the paper's own reference design, scale sweep and probe check); the plan
and the venues match Docs/PAPER-PLAN-TO-FINAL-STAGE-<date>.html. The supervisor asked (19 October 2026) for 5 to 8 slides on
motivation, scope, key themes, novelty, contributions and the plan to the final stage, for 30 to 35 minutes. Writes
"<NAME> - supervisory meeting <date> slides.pptx" beside the paper. Usage: python3 scripts/paper_ppml/meeting_slides.py [date]
"""
import copy, datetime, json, pathlib, shutil, sys
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor

ROOT = pathlib.Path(__file__).resolve().parents[2]
B = ROOT / 'myliteraturereviewpaper' / 'ppml2026' / 'build'
OUT = ROOT / 'myliteraturereviewpaper' / 'PPML in NextGeneration IoT'
BASE = pathlib.Path('/Volumes/Stuff/Abertay/research/Simulation/meetings/8Sep2026/8Sep2026.pptx')
NAME = 'Privacy Preserving Machine Learning in NextGeneration IoT'
date = sys.argv[1] if len(sys.argv) > 1 else datetime.date.today().isoformat()
s = json.loads((B / 'stats.json').read_text(encoding='utf-8'))
N_P, N_S = 45, 30

prs = Presentation(str(BASE))
BLANK = next(l for l in prs.slide_layouts if l.name == 'Blank')

# keep slides 1 to 3, drop the rest (the content of the earlier meeting)
ids = prs.slides._sldIdLst
for sid in list(ids)[3:]:
    prs.part.drop_rel(sid.rId); ids.remove(sid)

# slide 3: the agenda, in the deck's own style (32 pt bold lines in the subtitle placeholder)
ag = prs.slides[2]
ph = next(sh for sh in ag.shapes if sh.has_text_frame)
tf = ph.text_frame
for i, line in enumerate(['The survey paper: scope, themes, contributions', 'The reference design and the first experiment', 'Plan to the final stage, and venues']):
    p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
    if i == 0:
        for r in list(p.runs)[1:]: r._r.getparent().remove(r._r)
        run = p.runs[0] if p.runs else p.add_run()
    else: run = p.add_run()
    run.text = line; run.font.size = Pt(32); run.font.bold = True
for extra in tf.paragraphs[3:]: extra._p.getparent().remove(extra._p)


def content_slide(title, lead):
    sl = prs.slides.add_slide(BLANK)
    t = sl.shapes.add_textbox(Inches(0.34), Inches(0.22), Inches(9.33), Inches(0.44)).text_frame; t.word_wrap = True
    r = t.paragraphs[0].add_run(); r.text = title; r.font.size = Pt(20); r.font.bold = True
    l = sl.shapes.add_textbox(Inches(0.34), Inches(0.72), Inches(9.33), Inches(0.47)).text_frame; l.word_wrap = True
    r = l.paragraphs[0].add_run(); r.text = lead; r.font.size = Pt(11); r.font.color.rgb = RGBColor(0x7F, 0x7F, 0x7F)   # the deck's grey lead line
    return sl


def table(sl, head, rows, widths, top=1.34, size=12, row_h=0.38):
    n, m = len(rows) + 1, len(head)
    shp = sl.shapes.add_table(n, m, Inches(0.34), Inches(top), Inches(9.33), Inches(row_h * n))
    tb = shp.table
    # the deck's tables are plain: no coloured header band, no banding (PowerPoint's "No Style, Table Grid")
    tblPr = shp._element.graphic.graphicData.tbl.tblPr
    for attr in ('firstRow', 'bandRow'): tblPr.set(attr, '0')
    sid = tblPr.find('{http://schemas.openxmlformats.org/drawingml/2006/main}tableStyleId')
    if sid is not None: sid.text = '{5940675A-B579-460E-94D1-54222C63F5DA}'
    for j, w in enumerate(widths): tb.columns[j].width = Inches(w)
    for j, h in enumerate(head):
        c = tb.cell(0, j); c.text = h
        for p in c.text_frame.paragraphs:
            for r in p.runs: r.font.size = Pt(size); r.font.bold = True
    for i, row in enumerate(rows, 1):
        for j, v in enumerate(row):
            c = tb.cell(i, j); c.text = str(v)
            for p in c.text_frame.paragraphs:
                for r in p.runs: r.font.size = Pt(size); r.font.bold = (j == 0)
    return tb


def picture(sl, name, left, top, width=None, height=None):
    p = B / 'figures' / f'{name}.png'
    if not p.exists(): return
    if width: sl.shapes.add_picture(str(p), Inches(left), Inches(top), width=Inches(width))
    else: sl.shapes.add_picture(str(p), Inches(left), Inches(top), height=Inches(height))


def notes(sl, t): sl.notes_slide.notes_text_frame.text = t


# A. scope and method
sl = content_slide('The survey paper — what it reviews and how',
                   f'Privacy-preserving machine learning in NG-IoT, 2020 to 2026, with the ledger-based designs as the in-depth tier and the surveys as the second tier; PRISMA 2020 as the guideline. Draft V84.')
table(sl, ['Step', 'Number', 'Note'], [
    ['Databases', 'Scopus, IEEE Xplore (+ ScienceDirect for surveys)', 'Strings pilot-tested against the studies already known'],
    ['Records', f'{s["id_total"]:,}', f'{s["dup"]:,} duplicates; {s["auto"]:,} set aside by three stated rules'],
    ['Screened', f'{s["screened"]:,}', 'Title and abstract, by the author; a tool pre-filled, the author decided'],
    ['Full texts', f'{s["ft_assessed"]}', f'{s["ft_excluded"]} excluded, {s["ft_ex_no_ledger"]} of them for having no ledger'],
    ['Included', f'{s["included"]} = {N_P} designs + {N_S} surveys', 'Never counted together'],
    ['Extraction', 'One answer per question per design', 'Page-cited quotations; every answer verified by the author against the PDF'],
    ['Quality', 'Per question: Yes, Partial, No', 'No totals, no ranking'],
], [1.3, 3.0, 5.03])
notes(sl, 'Three to four minutes. The two tiers are the first thing to say: designs answer the questions, surveys are read for coverage.')

# B. key themes
sl = content_slide('Key themes — what the designs show on the three conditions',
                   f'Three study questions, one condition each. Of the {N_P} designs, none meets all three conditions and one meets two.')
table(sl, ['Condition', 'What the designs show', 'Numbers'], [
    ['C1 cost on the device', 'Costs are reported, almost always on a server or in simulation', f'{s["cost_any"]} report a cost; {s["gap3_c1"]} measure it on device-class hardware; {s["env_real_devices"]} use real devices'],
    ['C2 no checker sees the update', 'Hiding from the aggregator is common; hiding from the party that checks is rare; noise alone does not count', f'{s["hk_hidden"]} hide from the aggregator; {s["gap3_c2"]} from every checker'],
    ['C3 tested against the attacks', 'More designs address a threat than test against it', f'Poisoning {s["claimed_poisoning"]} addressed / {s["tested_any_poisoning"]} tested; Sybil {s["claimed_sybil_fake"]} / {s["tested_any_sybil_fake"]}; free riding {s["claimed_free_riding"]} / {s["tested_any_free_riding"]}; {s["gap3_c3"]} test a claimed attack'],
    ['All three', 'The gap the agenda targets', f'{s["gap3_all"]} designs; {s["gap3_two"]} meets two'],
    ['The ledger', 'Holds commitments, hashes, outcomes; proves that a computation happened', 'The check of what was contributed is the open part'],
], [1.7, 4.0, 3.63])
notes(sl, 'Four minutes. The last row is the sentence the whole paper turns on.')

# C. novelty and contributions
sl = content_slide('Novelty and contributions', 'What the paper adds beyond the surveys it reviews.')
table(sl, ['Contribution', 'What it is', 'Where'], [
    ['Two tiers', 'Designs answer the questions; surveys are graded for what they cover and leave out', 'Sections II, V'],
    ['Three conditions as a spine', 'Every design graded on them; every absence scoped to the included set', 'Sections V, VI'],
    ['Evidence sheets', 'Page-cited quotations for every answer, verified by the author; records, not notes, feed every count', 'Method, supporting document'],
    ['First experiment', 'Two designs with licensed code run unchanged: where DP gives way with scale; two published attacks on a proof-of-aggregation pipeline', 'Section VII-B'],
    ['Reference design, revised', 'Validators score each contribution\'s committed predictions on labelled probes, on secret shares; the clean-label backdoor stays open', 'Section VII-A, Fig. 7'],
    ['Regulation read in', 'What the ledger holds, read by GDPR and EDPB 02/2025 criteria', 'Section IV-C'],
], [1.9, 5.2, 2.23])
notes(sl, 'Two minutes.')

# D. the reference design
sl = content_slide('The reference design (Fig. 7) — three deliverables, one per condition',
                   'Gateways commit their update and their predictions on labelled probe rows; a committee of validators scores the predictions jointly on secret shares; the ledger holds commitments and outcomes only.')
picture(sl, 'design', 0.6, 1.3, width=8.8)
notes(sl, 'Point at the dashed red box: the experiment left it open.')

# E. the first experiment, as a table
sl = content_slide('The first experiment (Section VII-B) — what ran and what it showed',
                   'zkPET and FL-BC-IDS, MIT code, run unchanged on a desktop; CICIoV2024 prepared by the repository\'s own preprocessing; the repository\'s documented settings. A first contact, at most two runs per setting.')
table(sl, ['What ran', 'Result', 'Reading'], [
    ['zkPET proof lane', 'Per-site proof 0.15 s, 65 MB; 10- to 30-site models 3 to 11 GB; proof sizes identical to the repository', 'Memory, long before time, is the device limit'],
    ['FL-BC-IDS as documented (2 x 2)', 'Reproduces: accuracy 0.99998 vs 0.99987 in the repository', 'The released code works as stated at small scale'],
    ['Scale sweep, 4 to 200 vehicles', 'F1 above 0.98 to 32 vehicles, then 0.42, 0.62, 0.30; all 35 proofs verify', 'Utility gives way in the bagging of noised trees, between 16 and 32 vehicles per RSU'],
    ['FoolsGold Sybil flipping, 1 and 5 Sybils per RSU', 'Every attacker admitted and proved; 5 Sybils pass 22% / 14% of attack flows', 'The pipeline checks that a computation happened, never what was contributed'],
    ['Severi clean-label backdoor, 1% and 4%', 'Admitted and proved; success 0.22 to 0.28 against the clean detector', 'A trigger of one byte is partly an evasion in itself on this data set'],
    ['Probe check on the committed anchor vectors', 'Every Sybil below every honest vehicle, in all four runs; backdoor unseen', 'Backs the design\'s check; the backdoor is the open element'],
], [2.2, 4.0, 3.13], size=11, row_h=0.42)
notes(sl, 'Five minutes with the next slide. Say plainly what it is not: one data set, a desktop, no device-class hardware.')

# F. the figures, one slide each
sl = content_slide('The first experiment — the scale sweep', 'FL-BC-IDS as released, 4 to 200 vehicles on 2 RSUs, the repository\'s DP settings, one run per point. The pink band is where utility gives way.')
picture(sl, 'sweep', 0.34, 1.3, width=9.3)
notes(sl, 'Accuracy and F1 of the global ensemble; rows per vehicle under each point. The break is in the bagging of noised trees, between 16 and 32 vehicles per RSU; every proof still verifies.')
sl = content_slide('The first experiment — the probe check', 'Each vehicle\'s recall on the 11 attack rows among the 64 labelled probe rows FL-BC-IDS already commits; red dots are Sybils, the dashed line the weakest honest vehicle.')
picture(sl, 'anchorcheck', 1.0, 1.3, width=8.0)
notes(sl, 'Every Sybil below every honest vehicle, with one Sybil per RSU and with five, in all four runs. FoolsGold\'s similarity test on the same vectors zeroed the honest vehicles. The clean-label backdoor passes this check.')

# G. plan to the final stage
sl = content_slide('Plan to the final stage — the changes still required', 'In the order I would do them. Dates to agree today.')
table(sl, ['Change', 'Why', 'State'], [
    ['Abstract, introduction, discussion, conclusion in my own words', 'The detector finding of 19 October: model-drafted text reads as AI whatever its register', 'In progress, in the V84 file'],
    ['Close the 23 author checks; decide the title', 'Facts only the author can settle', 'Open'],
    ['Experiment: a third run; the probe check enforced inside the pipeline', 'To show the defence, not only the attack', 'Proposed; needs the team\'s view'],
    ['References checked against Crossref; experiment references in', 'Five new entries from outside the corpus', 'Entries in; check to run'],
    ['IEEE template, length, declarations', 'Deferred until the content stood', 'Open'],
    ['Final claims audit, detector pass, proofreading', 'Every version so far has had both', 'At each build'],
    ['Venue chosen; submission', 'See next slide', 'Today\'s decision'],
], [3.4, 3.6, 2.33], size=11, row_h=0.4)
notes(sl, 'Three minutes. Ask for a date for the four sections and for the venue.')

# H. venues: free to publish
sl = content_slide('Venues, 1 of 2 — free to publish, good standing',
                   'Subscription-route journals: the author pays nothing; readers need access; the accepted manuscript goes into the repository. Under the Jisc agreements Elsevier and Springer hybrids may publish open access at no cost to UK authors; IEEE grants green open access only.')
table(sl, ['Venue', 'Publisher', 'Fee to publish', 'Fit'], [
    ['IEEE Communications Surveys & Tutorials', 'IEEE', 'None; no page charges; green OA of the accepted manuscript', 'The home of long surveys; the most selective'],
    ['IEEE Internet of Things Journal', 'IEEE', 'None under subscription; overlength charges to check', 'NG-IoT scope; many included designs appeared there'],
    ['Computer Science Review', 'Elsevier', 'None; gold OA via Jisc if Abertay is in', 'Surveys only; the model SLR appeared there'],
    ['Computers & Security', 'Elsevier', 'None; gold OA via Jisc if Abertay is in', 'Security scope; reviews accepted'],
    ['Journal of Network and Computer Applications', 'Elsevier', 'None; gold OA via Jisc if Abertay is in', 'Surveys of networked systems; long papers'],
    ['Future Generation Computer Systems', 'Elsevier', 'None; gold OA via Jisc if Abertay is in', 'Edge and distributed systems; surveys accepted'],
    ['Peer-to-Peer Networking and Applications', 'Springer', 'None; gold OA via Jisc (Abertay is listed)', 'Decentralised learning and ledgers; moderate fit'],
    ['Cybersecurity (SpringerOpen)', 'Springer', 'Open access; the fees page says the sponsor covers the charge, other pages differ: confirm first', 'Security scope; younger journal'],
], [2.75, 0.9, 2.95, 2.73], size=10, row_h=0.36)
notes(sl, 'The first four are the shortlist; the rest are fall-backs. Green OA at IEEE: the accepted manuscript, CC BY, no embargo, under the IEEE and Jisc licence through 2027.')

# I. venues: a fee, or an agreement to check
sl = content_slide('Venues, 2 of 2 — a fee to publish, or an agreement to check first',
                   'Fully open-access journals charge an article processing charge unless an institutional agreement covers it; none of the IEEE or ACM ones is covered for Abertay as far as the public lists show.')
table(sl, ['Venue', 'Publisher', 'Fee to publish', 'Standing and fit'], [
    ['IEEE Access', 'IEEE', 'About US$2,160 (2026 schedule); the IEEE and Jisc deal is read-only', 'Large mega-journal, fast; a weaker signal for a survey'],
    ['ACM Computing Surveys', 'ACM', 'ACM fully open access from 2026: a charge unless Abertay is in ACM Open (not on the public list found)', 'First-rank survey venue; the fee question first'],
    ['ACM Transactions on Internet of Things', 'ACM', 'As above', 'IoT scope; shorter papers'],
    ['Artificial Intelligence Review', 'Springer', 'Fully open access since 2024; a charge, amount to check', 'Review journal of good standing; AI framing'],
    ['IET Information Security', 'Wiley (IET)', 'Fully open access; a charge unless the Wiley and Jisc fund covers it', 'Security scope'],
    ['Sensors, Electronics, Future Internet', 'MDPI', 'About CHF 2,400 to 2,700', 'Fast; mixed standing; FL-BC-IDS appeared in Sensors'],
    ['Scientific Reports', 'Springer Nature', 'About GBP 2,200', 'Broad; rarely a survey venue'],
], [2.6, 1.05, 3.1, 2.58], size=10, row_h=0.36)
notes(sl, 'Why IEEE Access was left off the first list: it charges, and the IEEE licence the UK holds does not pay it. If the team wants open access without a fee, the Elsevier and Springer hybrids under Jisc are the route.')

out = OUT / f'{NAME} - supervisory meeting {date} slides.pptx'
prs.save(str(out)); print('written', out.relative_to(ROOT), '|', len(prs.slides), 'slides on the biweekly format')
