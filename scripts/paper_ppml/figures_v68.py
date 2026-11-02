#!/usr/bin/env python3
"""The figures of the simple frame (V68) that the earlier figure module does not draw: how the review is organised (three
questions), the included studies per year, the surveys against the subjects, the designs against the three conditions,
and the reference design of the agenda. Drawn with the primitives of figures.py; every number comes from the records.
Called by data_v68.py.
"""
import json, pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import figures as FG
import thematic as T
F = FG.F
B = FG.B
ROOT = pathlib.Path(__file__).resolve().parents[2]
YES, PART, NO, MET = '#2f6fc0', '#c4dbf6', '#ffffff', '#2FA37A'


def label(k, refs, year):
    """"Surname year", with the corpus id added where two studies would read the same"""
    base = f"{(refs.get(k) or {}).get('first_author_surname') or k} {year[k]}"
    same = [j for j in year if f"{(refs.get(j) or {}).get('first_author_surname') or j} {year[j]}" == base]
    return base if len(same) == 1 else f'{base} ({k})'


def roadmap(s):
    """the roadmap of the review: for each question, the data items answered, the sections that introduce and answer it, the
    open issue it leaves, the condition of the gap and the deliverable of the agenda that takes it up"""
    rows = [('SQ1 The fabric and its cost', ['settings · enablers · tiers', 'costs and where measured'], F.BLUE, F.BLUE_XL, 'IV-A · V-C',
             ['1) Costs measured where they', 'would be paid: on the fabric'], 'C1', ['1  Prototype', 'NG-IoT fabric']),
            ('SQ2 Privacy with the blockchain', ['mechanisms · hidden from whom · ledger', 'trusted parties · data-protection law'], F.VIOLET, F.VIOLET_L, 'IV-B, IV-C · V-D',
             ['2) Updates hidden from every party', 'that checks or aggregates'], 'C2', ['2  PPML approach', 'with a blockchain']),
            ('SQ3 Security and the evidence', ['checks · threats claimed and tested', 'defences · evaluation'], F.RED, F.RED_L, 'IV-D · V-E',
             ['3) Tests of the design against', 'the named attacks'], 'C3', ['3  Security', 'evaluation'])]
    W, b = 1300, []
    for t, x, w in (('I Introduction: the problem', 20, 300), ('II Related surveys', 330, 220), ('III Method', 560, 170), ('V Results, one subsection per question', 740, 540)):
        b.append(F.box(x, 14, w, 40, [t], fill=FG.GOLD, stroke=FG.GOLD_EDGE, size=14, weight='bold'))
    xs, ws = [20, 350, 530, 880, 1070], [310, 160, 330, 170, 210]
    for x, w, h in zip(xs, ws, ['Question and data items', 'Background · answer', 'Open issue (VI-A)', 'Gap condition (VI-B)', 'Deliverable (VII-A)']):
        b.append(F.text(x + w / 2, 84, h, 14, 'bold', fill=F.INK2))
    y0, rh, step = 100, 92, 112
    for i, (q, items, c, cl, secs, issue, cond, deliv) in enumerate(rows):
        y = y0 + i * step
        b.append(F.box(xs[0], y, ws[0], rh, [q] + items, fill=cl, stroke=c, size=13, weight='bold'))
        b.append(F.arrow(xs[0] + ws[0], y + rh / 2, xs[1], y + rh / 2))
        b.append(F.box(xs[1], y, ws[1], rh, [secs], fill='#ffffff', stroke=c, size=15))
        b.append(F.arrow(xs[1] + ws[1], y + rh / 2, xs[2], y + rh / 2))
        b.append(F.box(xs[2], y, ws[2], rh, issue, fill=cl, stroke=c, size=14))
        b.append(F.arrow(xs[2] + ws[2], y + rh / 2, xs[3], y + rh / 2))
        b.append(F.box(xs[3], y, ws[3], rh, [cond, f"met by {s[f'gap3_c{i + 1}']} of {s['primary']}"], fill='#ffffff', stroke=F.INK2, size=14, weight='bold'))
        b.append(F.arrow(xs[3] + ws[3], y + rh / 2, xs[4], y + rh / 2))
        b.append(F.box(xs[4], y, ws[4], rh, deliv, fill=F.GREY_L, stroke=F.INK2, size=14, weight='bold'))
    yb = y0 + len(rows) * step + 4
    for t, x, w in (('VI Discussion: what remains to be shown', 20, 480), ('VII Agenda and limitations', 520, 330), ('VIII Conclusion · Appendices', 870, 410)):
        b.append(F.box(x, yb, w, 40, [t], fill=FG.GOLD, stroke=FG.GOLD_EDGE, size=14, weight='bold'))
    FG.record('roadmap', kind='schematic')
    return F.render('roadmap', W, yb + 54, ''.join(b))


def years(fin):
    """the included studies per year: designs and surveys"""
    ys = list(range(2020, 2027))
    d = {y: sum(1 for r in fin if int(r['year']) == y and r['kind'] == 'primary') for y in ys}
    v = {y: sum(1 for r in fin if int(r['year']) == y and r['kind'] == 'secondary') for y in ys}
    W, H, lw, top, bh = 980, 420, 60, 60, 300
    mx = max(max(d.values()), max(v.values())) or 1
    sc = (bh - 20) / mx
    b = [F.text(W / 2, 28, 'Included studies per year', 16, 'bold', fill=F.INK2)]
    for k, (lab, col) in enumerate((('Designs', FG.SOLID[0]), ('Surveys', FG.SOLID[2]))):
        b.append(f'<rect x="{W - 300 + k * 140}" y="18" width="16" height="16" rx="3" fill="{col}"/>'); b.append(F.text(W - 276 + k * 140, 31, lab, 14, 'normal', anchor='start', fill=F.INK))
    slot = (W - lw - 40) / len(ys)
    for i, y in enumerate(ys):
        x = lw + i * slot + 18
        for k, (val, col) in enumerate(((d[y], FG.SOLID[0]), (v[y], FG.SOLID[2]))):
            h = val * sc
            b.append(f'<rect x="{x + k * 44}" y="{top + bh - h}" width="40" height="{h:.1f}" rx="3" fill="{col}"/>')
            b.append(F.text(x + k * 44 + 20, top + bh - h - 6, str(val), 13.5, 'bold', fill=F.INK))
        b.append(F.text(x + 44, top + bh + 24, str(y), 14, 'normal', fill=F.INK))
    b.append(f'<line x1="{lw}" y1="{top + bh}" x2="{W - 30}" y2="{top + bh}" stroke="{F.INK2}" stroke-width="1.2"/>')
    FG.record('years', kind='bar_clustered', categories=[str(y) for y in ys], series=[['Designs', FG.SOLID[0], [d[y] for y in ys]], ['Surveys', FG.SOLID[2], [v[y] for y in ys]]])
    return F.render('years', W, H, ''.join(b)), d, v


def grid(name, labels, groups, rows, colours, legend, cw=76, blocks=2):
    """one row per study, one column per grade, columns grouped under a heading; rows = [(label, [grade, ...])]; the rows are
    split into `blocks` side by side (V86: half the height, so the figure sits with its text in the two-column page)"""
    ch, lw = 24, 240
    reach = int(max(len(l) for l in labels) * 7.2 * 0.72) + 12
    top = 52 + reach + 16
    per = -(-len(rows) // blocks); parts = [rows[k * per:(k + 1) * per] for k in range(blocks)]
    gap = 40; bw = max(lw + len(labels) * cw + 30, lw + (len(labels) - 1) * cw + cw // 2 + reach + 24)
    W = max(blocks * bw + (blocks - 1) * gap, max(lw + i * 300 + 24 + int(len(lab) * 7.6) + 24 for i, (lab, _) in enumerate(legend)))
    H = top + per * ch + 60
    b = []
    for k, part in enumerate(parts):
        ox = k * (bw + gap); x0 = ox + lw
        for head, n in groups:
            b.append(F.text(x0 + n * cw / 2, 30, head, 14, 'bold', fill=F.INK2))
            b.append(f'<line x1="{x0 + 2}" y1="40" x2="{x0 + n * cw - 2}" y2="40" stroke="{F.INK2}" stroke-width="1.2"/>')
            x0 += n * cw
        for i, lab in enumerate(labels):
            x = ox + lw + i * cw + cw / 2
            b.append(f'<text transform="translate({x + 4},{top - 10}) rotate(-45)" font-family="{F.FONT}" font-size="14" fill="{F.INK}">{lab}</text>')
        x0 = ox + lw
        for _, n in groups[:-1]:
            x0 += n * cw
            b.append(f'<line x1="{x0}" y1="{top - 4}" x2="{x0}" y2="{top + len(part) * ch}" stroke="{F.INK2}" stroke-width="1.5"/>')
        for j, (lab, marks) in enumerate(part):
            b.append(F.text(ox + lw - 10, top + j * ch + ch / 2 + 5, lab, 13, 'normal', anchor='end', fill=F.INK))
            for i, v in enumerate(marks):
                b.append(f'<rect x="{ox + lw + i * cw + 2}" y="{top + j * ch + 2}" width="{cw - 4}" height="{ch - 4}" rx="3" fill="{colours.get(v, "#ffffff")}" stroke="{F.GREY_L}"/>')
    y = top + per * ch + 28
    for i, (lab, c) in enumerate(legend):
        b.append(f'<rect x="{lw + i * 300}" y="{y - 13}" width="16" height="16" rx="3" fill="{c}" stroke="{F.GREY}"/>')
        b.append(F.text(lw + i * 300 + 24, y, lab, 14, 'normal', anchor='start', fill=F.INK))
    FG.record(name, kind='marks', columns=labels, groups=[[h, n] for h, n in groups], colors=colours, rows=[[l, m] for l, m in rows])
    return F.render(name, W, H, ''.join(b))


SUBJECTS = [('fabric', 'NG-IoT fabric'), ('privacy', 'Privacy mechanisms'), ('trust', 'Blockchain and checking'),
            ('regulation', 'Data-protection law'), ('poisoning', 'Poisoning'), ('malicious_fake', 'Malicious or fake participants'), ('free_riding', 'Free riding')]
MARK = {'subject': 'Yes', 'mentioned': 'Partial', 'absent': 'No'}


def survey_grid(S, sec, refs, year):
    rows = [(label(k, refs, year), [MARK.get(T.V(S[k], 'S1', f), 'No') for f, _ in SUBJECTS]) for k in sorted(sec, key=lambda k: (year[k], label(k, refs, year)))]
    return grid('survey_coverage', [l for _, l in SUBJECTS], [('SQ1', 1), ('SQ2 Privacy with the blockchain', 3), ('SQ3 Named threats', 3)], rows,
                {'Yes': YES, 'Partial': PART, 'No': NO}, [('Yes: a subject of its own', YES), ('Partial: mentioned', PART), ('No: absent', NO)], cw=96), rows


COND = [('C1 A cost measured on device-class hardware', 'C1'), ('C2 No party that checks or aggregates sees an update', 'C2'), ('C3 A test against a named threat is reported', 'C3')]
GRADE = {'Yes': MET, 'Partial': '#CDEBDD', 'No': NO}
NAMED = T.GAP_THREATS['C4a'] | T.GAP_THREATS['C4b'] | T.GAP_THREATS['C4c']


def grades_of(k, sh):
    """Yes / Partial / No for the three conditions, from the record: Yes is the condition as the agenda targets it; Partial is a
    step towards it that the record shows; No is neither"""
    c = T.gap_conditions(k, sh)
    hk = T.hidden_kind(sh)
    claimed = T.threats_of(k, sh, 'claimed')
    return {'C1': 'Yes' if c['C1'] else ('Partial' if T.V(sh, 'P1', 'network_measured') == 'yes' or T.V(sh, 'P1', 'cost_where') == 'server-workstation' else 'No'),
            'C2': 'Yes' if c['C2'] else ('Partial' if hk in ('hidden', 'noised') else 'No'),
            'C3': 'Yes' if (c['C4a'] or c['C4b'] or c['C4c']) else ('Partial' if claimed & NAMED else 'No')}


def conditions_of(k, sh):
    return {code: v == 'Yes' for code, v in grades_of(k, sh).items()}


def order_key(k, S, refs, year):
    g = grades_of(k, S[k])
    return (-sum(v == 'Yes' for v in g.values()), -sum(v == 'Partial' for v in g.values()), year[k], label(k, refs, year))


def design_grid(S, prim, refs, year):
    rows = [(label(k, refs, year), [grades_of(k, S[k])[code] for _, code in COND]) for k in sorted(prim, key=lambda k: order_key(k, S, refs, year))]
    return grid('prim_coverage', [l for l, _ in COND], [('SQ1', 1), ('SQ2', 1), ('SQ3', 1)], rows, GRADE,
                [('Yes: as the agenda targets it', MET), ('Partial: a step towards it', GRADE['Partial']), ('No: not shown', NO)], cw=150), rows


def design(s):
    """the reference design of the agenda (Section VII-A) as a layered architecture in the manner of the included surveys'
    architecture figures and the author's example: three stacked layers (gateways, validators, ledger) named at the right,
    each party an icon with a short label, hollow block arrows between the layers with what goes up and down beside them,
    the validators as a mesh of nodes, the open element as one callout; free icons (Tabler, MIT)"""
    import icons as I
    W, H, b = 1000, 770, []
    INK, INK2, GREY = '#1b1b1b', '#444444', '#9a9a9a'
    GREEN_D, RED, BLUE_D, GOLD_D = '#3f7f3f', '#B85450', '#3c6fb0', '#9a7d1e'

    def layer(y, h):
        return f'<rect x="30" y="{y}" width="690" height="{h}" rx="20" fill="#ffffff" stroke="{INK}" stroke-width="2.6"/>'

    def block_arrow(x, y1, y2):
        pts = [(x, y1), (x + 26, y1 + 24), (x + 11, y1 + 24), (x + 11, y2 - 24), (x + 26, y2 - 24), (x, y2), (x - 26, y2 - 24),
               (x - 11, y2 - 24), (x - 11, y1 + 24), (x - 26, y1 + 24), (x, y1)]
        d = 'M ' + ' L '.join(f'{px} {py}' for px, py in pts)
        return f'<path d="{d}" fill="#ffffff" stroke="{INK}" stroke-width="2.2" stroke-linejoin="round"/>'

    def block(x, top, ls, size=16, weight='normal', fill=INK, anchor='middle', lh=1.3):
        return F.text(x, top + 0.65 * size + (len(ls) - 1) * size * lh / 2, ls, size, weight, anchor, fill, lh)

    def name(y, l1, l2):
        return F.text(745, y, l1, 21, 'bold', 'start', INK) + F.text(745, y + 27, l2, 16, 'normal', 'start', INK2)

    # top: the ledger layer
    b.append(layer(30, 150))
    for i, cx in enumerate((62, 122, 182)):
        b.append(I.icon('cube', cx, 54, 44, GOLD_D))
        if i < 2:
            b.append(f'<line x1="{cx + 45}" y1="76" x2="{cx + 59}" y2="76" stroke="{GOLD_D}" stroke-width="2.4"/>')
    b.append(block(144, 112, ['Blockchain: fingerprints', 'and verdicts only']))
    b.append(I.icon('shield-lock', 356, 50, 50, GREEN_D))
    b.append(block(381, 112, ['Nothing personal', 'on the ledger']))
    b.append(I.icon('user-check', 556, 50, 50, GREEN_D))
    b.append(block(581, 112, ['Registered', 'gateways only']))
    b.append(name(90, 'Ledger layer', 'permissioned blockchain'))
    # arrows between the ledger and the validators
    b.append(block_arrow(375, 180, 245))
    b.append(F.text(412, 203, '\u2191 fingerprints and verdicts', 15, 'normal', 'start', INK2, italic=True))
    b.append(F.text(412, 226, '\u2193 new model', 15, 'normal', 'start', INK2, italic=True))
    # middle: the validators as a mesh
    b.append(layer(245, 250))
    import math
    nodes = [(230 + 150 * math.cos(math.radians(a)), 370 + 88 * math.sin(math.radians(a))) for a in range(0, 360, 60)]
    for i in range(len(nodes)):
        for j in range(i + 1, len(nodes)):
            (x1, y1), (x2, y2) = nodes[i], nodes[j]
            b.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{GREY}" stroke-width="1.6" stroke-dasharray="3,5"/>')
    for (x, y) in nodes:
        b.append(f'<rect x="{x - 26:.1f}" y="{y - 26:.1f}" width="52" height="52" rx="10" fill="#ffffff" stroke="{INK}" stroke-width="1.8"/>')
        b.append(I.icon('router', x - 18, y - 18, 36, INK))
    b.append(block(575, 266, ['Validators'], 17, 'bold'))
    b.append(block(575, 294, ['a small group of gateways that', 'mark the test answers and add up', 'the secret shares, together, so', 'that none sees a whole update', '(SMPC, C2)'], 16))
    b.append(f'<rect x="440" y="412" width="270" height="68" rx="10" fill="#ffffff" stroke="{RED}" stroke-width="1.8" stroke-dasharray="7,5"/>')
    b.append(I.icon('alert-triangle', 452, 426, 40, RED))
    b.append(block(602, 424, ['Open: a hidden backdoor', 'passes the test (Section VII-B)'], 15, 'normal', RED))
    b.append(name(355, 'Validation layer', 'SMPC committee'))
    # arrows between the validators and the gateways
    b.append(block_arrow(375, 495, 560))
    b.append(F.text(412, 518, '\u2191 secret shares and answers', 15, 'normal', 'start', INK2, italic=True))
    b.append(F.text(412, 541, '\u2193 new model', 15, 'normal', 'start', INK2, italic=True))
    # bottom: the gateways
    b.append(layer(560, 180))
    for cx in (120, 300, 480):
        b.append(I.icon('router', cx - 26, 584, 52, INK))
        b.append(block(cx, 648, ['Gateway: trains on', "its own devices' data"]))
    b.append(I.icon('bug', 500, 578, 26, RED))
    b.append(block(480, 696, ['attacked in tests (C3)'], 15, 'normal', RED))
    b.append(I.icon('gauge', 614, 584, 52, BLUE_D))
    b.append(block(640, 648, ['Costs measured', 'here (C1)']))
    b.append(name(640, 'Edge layer', 'gateways as FL clients'))
    FG.record('design', kind='schematic')
    return F.render('design', W, H, ''.join(b))


def main(s, S, fin, refs):
    year = {r['corpus_id']: int(r['year']) for r in fin}
    prim, sec = T.split(S, fin)
    roadmap(s)
    _, d, v = years(fin)
    _, srows = survey_grid(S, sec, refs, year)
    _, drows = design_grid(S, prim, refs, year)
    design(s)
    return d, v, srows, drows
