#!/usr/bin/env python3
"""Draw the three result charts of the PPML review that replace eight count tables from V95: where the designs measured their
costs, how they were evaluated and at what scale (SQ1); their privacy mechanisms, what their ledgers hold and the parties they
still trust (SQ2); and what they check and whether the checking party sees the update (SQ3).

The author, 26 November 2026, on the tables of V94: "Some of the tables narrate material which sounds not very necessary for the
survey"; Tables IV to IX, XI and XII of V94 went to the supporting document in full, and these charts carry the counts the text
reads. Every number is computed here from the evidence sheets with the definitions of those tables (thematic.py, data_v68.py);
verify_tables.py recounts them by its own code and compares them with the tables of the supporting document. Text is 20 px on a
1,200-px canvas (8.4 pt at the printed width of 7 in), and every label is measured in Helvetica Neue (Pillow) before it is placed.
Drawn with the primitives of figures.py; called by data_v68.py.
"""
import pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import figures as FG                    # noqa: E402
import figures_v68 as FV                # noqa: E402  measure()
import thematic as T                    # noqa: E402
F = FG.F

W, FS, ROW, BAR = 1200, 20, 34, 22
BLUE, BLUE_L = FG.SOLID[0], '#DCE6F7'                                   # SQ1
VIOLET, VIOLET_L, VIOLET_XL = FG.SOLID[1], '#D9CCF2', '#F1ECFA'         # SQ2
GREY, GREY_L = '#8A8A8A', '#E6E6E6'
SEE = {'yes': '#22445D', 'partly': '#6C8EBF', 'no': '#C9D8EE', 'unclear': '#F0F0F0', 'no-check': '#FFFFFF'}   # SQ3: darker sees more


def wrap(text, maxw, size=FS, bold=False):
    """the words of a label on as few lines as fit maxw px"""
    lines = ['']
    for w in text.split():
        t = (lines[-1] + ' ' + w).strip()
        if FV.measure(t, size, bold) <= maxw or not lines[-1]:
            lines[-1] = t
        else:
            lines.append(w)
    return lines


def legend(x, y, w, items, size=FS):
    """swatches with their labels, left to right, wrapping at w px; items = [(label, fill, stroke, dash)]; returns (svg, next y)"""
    b, cx = [], x
    for lab, fill, stroke, dash in items:
        iw = size + 10 + FV.measure(lab, size) + 30
        if cx + iw > x + w and cx > x:
            cx, y = x, y + size * 1.7
        d = f' stroke-dasharray="{dash}"' if dash else ''
        b.append(f'<rect x="{cx:.1f}" y="{y - size * 0.8:.1f}" width="{size}" height="{size}" rx="3" fill="{fill}" stroke="{stroke}" stroke-width="1.3"{d}/>')
        b.append(F.text(cx + size + 10, y - size * 0.3, lab, size, 'normal', anchor='start', fill=F.INK))
        cx += iw
    return ''.join(b), y + size * 1.5


def panel(x, y, w, title, rows, top, labw):
    """one panel of horizontal bars under its title; rows = [dict(label, value, text, fill, stroke, dash?, inner?, inner_fill?)];
    every bar is drawn on the scale `top` (the number of designs), so a bar's length is its share of the designs"""
    b = []
    if title:
        b.append(F.text(x, y + FS * 0.5, title, FS + 1, 'bold', anchor='start', fill=F.INK2))
        y += int(FS * 1.8)
    vw = max(FV.measure(r['text'], FS, True) for r in rows) + 14
    x0 = x + labw
    sc = (w - labw - vw) / top
    y_first = y
    for r in rows:
        lines = wrap(r['label'], labw - 16)
        rh = max(ROW, len(lines) * FS * 1.2 + 10)
        cy = y + rh / 2
        b.append(F.text(x0 - 12, cy, lines, FS, 'normal', anchor='end', fill=F.INK, lh=1.2))
        bw = max(r['value'] * sc, 2)
        d = f' stroke-dasharray="{r["dash"]}"' if r.get('dash') else ''
        b.append(f'<rect x="{x0:.1f}" y="{cy - BAR / 2:.1f}" width="{bw:.1f}" height="{BAR}" rx="3" fill="{r["fill"]}" '
                 f'stroke="{r.get("stroke", r["fill"])}" stroke-width="1.3"{d}/>')
        if r.get('inner'):
            b.append(f'<rect x="{x0:.1f}" y="{cy - BAR / 2 + 5:.1f}" width="{r["inner"] * sc:.1f}" height="{BAR - 10}" rx="2" fill="{r["inner_fill"]}"/>')
        b.append(F.text(x0 + bw + 9, cy, r['text'], FS, 'bold', anchor='start', fill=F.INK))
        y += rh
    b.append(f'<line x1="{x0:.1f}" y1="{y_first:.1f}" x2="{x0:.1f}" y2="{y:.1f}" stroke="{F.INK2}" stroke-width="1.2"/>')
    return ''.join(b), y


def label_width(labels, cap):
    """the label column: the widest label, wrapped at cap px, plus the gap before the bars"""
    return min(cap, max(max(FV.measure(l, FS) for l in wrap(x, cap - 16)) for x in labels)) + 16


# ---- SQ1: where costs were measured, where the designs were evaluated, the largest scale -----------------------------------
WHERE = [('device-class', 'On device-class hardware'), ('server-workstation', 'On servers or workstations'), ('simulation', 'In simulation'),
         ('not-stated', 'Where not stated')]
ENV = [('real-devices', 'Real devices or a test bed'), ('emulation', 'Emulation'), ('simulation', 'Simulation'),
       ('server-experiment', 'An experiment on data sets on servers'), ('none', 'No experiment'), ('not-stated', 'Not stated')]
BANDS = [('Up to 10', lambda n: n <= 10), ('11 to 100', lambda n: 11 <= n <= 100), ('101 to 1,000', lambda n: 101 <= n <= 1000),
         ('Over 1,000', lambda n: n > 1000)]


def sq1_data(S, prim):
    where = [(lab, sum(1 for k in prim if T.V(S[k], 'P1', 'cost_where') == v)) for v, lab in WHERE]
    env = [(lab, sum(1 for k in prim if v in T.L(S[k], 'P3', 'environment'))) for v, lab in ENV]
    scale = {k: T.V(S[k], 'P3', 'scale') for k in prim}
    sc = [(lab, sum(1 for k in prim if isinstance(scale[k], int) and f(scale[k]))) for lab, f in BANDS]
    sc.append(('Not stated', sum(1 for k in prim if not isinstance(scale[k], int))))
    nz = lambda xs: [(l, n) for l, n in xs if n]                         # a row no design falls under says nothing (as in the tables)
    return [('(a) Where the designs measured a cost', nz(where)),
            ('(b) Where the designs were evaluated (a design may use several)', nz(env)),
            ('(c) The largest scale reported, in clients or nodes', nz(sc))]


def sq1(S, prim):
    panels = sq1_data(S, prim)
    labw = label_width([l for _, rows in panels for l, _ in rows], 420)
    b, y = [], 14
    for title, rows in panels:
        svg, y = panel(16, y, W - 32, title, [dict(label=l, value=n, text=str(n), fill=BLUE) for l, n in rows], len(prim), labw)
        b.append(svg); y += 22
    FG.record('sq1_costs', kind='panels', top=len(prim),
              panels=[dict(title=t, kind='bar_clustered', categories=[l for l, _ in rows], series=[['Designs', BLUE, [n for _, n in rows]]])
                      for t, rows in panels])
    return F.render('sq1_costs', W, int(y + 6), ''.join(b))


# ---- SQ2: mechanisms used and concealing the update from the aggregator; what the ledgers hold; the parties still trusted -----
MECH_SHORT = {'HE': 'HE', 'secret-sharing': 'Secret sharing', 'SMPC': 'SMPC', 'masking-secure-aggregation': 'Masking and secure aggregation',
              'TEE': 'TEE', 'functional-encryption': 'Functional encryption', 'DP': 'DP', 'LDP': 'LDP',
              'pseudonyms-anonymity': 'Pseudonyms and anonymity', 'ZKP': 'ZKPs', 'encryption-in-transit-only': 'Encryption in transit only'}
HOLD_NAME = {'identities-keys': 'Identities and keys', 'protected-updates': 'Protected updates', 'reputation-scores': 'Reputation scores',
             'rewards-payments': 'Rewards and payments', 'plain-updates': 'Plaintext updates', 'logs-metadata': 'Logs and metadata',
             'hashes-commitments': 'Hashes and commitments', 'global-model': 'The global model', 'proofs': 'Proofs'}
BAND_STYLE = {'A': (VIOLET, VIOLET, 'Remains personal data where it relates to a person'), 'B': (VIOLET_L, VIOLET, 'Depends on the scheme'),
              'C': ('#FFFFFF', VIOLET, 'Reveals nothing about its witness')}
TRUST = [('server-aggregator', 'The server, aggregator or task publisher'), ('trusted-authority-key-centre', 'A trusted authority or key centre'),
         ('enclave-TEE', 'An enclave'), ('committee-honest-majority', 'An honest majority of a committee or of the nodes'),
         ('certificate-authority', 'A certificate authority'), ('trusted-setup', 'A trusted set-up'), ('non-colluding-servers', 'Non-colluding servers')]
TRUST_NONE = [('none', 'No party'), ('not-stated', 'Not stated')]


def sq2_data(S, prim):
    mech = []
    for kind, ms in T.PROTECTION_KINDS:
        for m in ms:
            ids = [k for k in prim if m in T.mechanisms_used(S[k])]
            if ids:
                conf = kind == 'Confidentiality of the update'
                mech.append((MECH_SHORT[m], len(ids), sum(1 for k in ids if T.hidden_kind(S[k]) == 'hidden') if conf else None))
    held = {}
    for k in prim:
        for x in set(T.L(S[k], 'P3', 'on_chain')):
            if not T.IS_OTHER(x) and x in HOLD_NAME:                      # "other" items name nothing (they stay in the supporting table)
                held.setdefault(x, set()).add(k)
    hold = sorted(((T.onchain_band(x), HOLD_NAME[x], len(ks)) for x, ks in held.items()), key=lambda r: (r[0], -r[2]))
    cnt = lambda v: sum(1 for k in prim if any(T.O(x) == v for x in T.L(S[k], 'P2', 'trusted')))
    trust = sorted(((lab, cnt(v)) for v, lab in TRUST), key=lambda r: -r[1]) + [(lab, cnt(v)) for v, lab in TRUST_NONE]
    return mech, hold, [(l, n) for l, n in trust if n]


def sq2(S, prim):
    mech, hold, trust = sq2_data(S, prim)
    top = len(prim)
    b = []
    rows = [dict(label=l, value=n, text=(f'{h} of {n}' if h is not None else str(n)), fill=VIOLET_XL, stroke=VIOLET,
                 inner=h, inner_fill=VIOLET) for l, n, h in mech]
    svg, y = panel(16, 14, W - 32, '(a) Privacy mechanisms: designs using each, and those in which it conceals the update from the aggregator',
                   rows, top, label_width([r['label'] for r in rows], 380))
    b.append(svg)
    svg, y = legend(16 + label_width([r['label'] for r in rows], 380), y + 30, W - 400,
                    [('Designs using the mechanism', VIOLET_XL, VIOLET, None),
                     ('Of these, the update concealed from the aggregator (HE, secret sharing, SMPC, masking, TEE)', VIOLET, VIOLET, None)])
    b.append(svg)
    y0, half, gap = y + 16, (W - 32 - 50) / 2, 50
    rows_b = [dict(label=l, value=n, text=str(n), fill=BAND_STYLE[band][0], stroke=BAND_STYLE[band][1]) for band, l, n in hold]
    svg, yb = panel(16, y0, half, '(b) What the ledgers hold', rows_b, top, label_width([r['label'] for r in rows_b], 250))
    b.append(svg)
    svg, yb = legend(16, yb + 30, half, [(BAND_STYLE[k][2], *BAND_STYLE[k][:2], None) for k in ('A', 'B', 'C')])
    b.append(svg)
    rows_c = [dict(label=l, value=n, text=str(n), fill=(GREY_L if l in ('No party', 'Not stated') else VIOLET),
                   stroke=(GREY if l in ('No party', 'Not stated') else VIOLET)) for l, n in trust]
    svg, yc = panel(16 + half + gap, y0, half, '(c) Parties the designs still trust', rows_c, top, label_width([r['label'] for r in rows_c], 300))
    b.append(svg)
    FG.record('sq2_privacy', kind='panels', top=top, panels=[
        dict(title='(a) Privacy mechanisms', kind='bar_clustered', categories=[l for l, _, _ in mech],
             series=[['Designs using it', VIOLET_L, [n for _, n, _ in mech]], ['Of these, update concealed from the aggregator', VIOLET, [h for _, _, h in mech]]]),
        dict(title='(b) What the ledgers hold', kind='bar_clustered', categories=[l for _, l, _ in hold], bands=[band for band, _, _ in hold],
             series=[['Designs', VIOLET, [n for _, _, n in hold]]]),
        dict(title='(c) Parties the designs still trust', kind='bar_clustered', categories=[l for l, _ in trust], series=[['Designs', VIOLET, [n for _, n in trust]]])])
    return F.render('sq2_privacy', W, int(max(yb, yc) + 10), ''.join(b))


# ---- SQ3: what the designs check, and whether the checking party sees the update -------------------------------------------
SEES = [('yes', 'Sees the update in full'), ('partly', 'In part or with noise added'), ('no', 'Not at all'), ('unclear', 'Unclear'),
        ('no-check', 'No checker of updates')]


def sq3_data(S, prim):
    out = []
    for c, name in T.CHECK_CLASSES:
        ids = [k for k in prim if T.check_class(k, S[k]) == c]
        if ids:
            out.append((name, [sum(1 for k in ids if T.V(S[k], 'P4', 'checker_sees_update') == v) for v, _ in SEES]))
    return out


def sq3(S, prim):
    rows = sq3_data(S, prim)
    labw = label_width([l for l, _ in rows], 400)
    vw = 50
    mx = max(sum(c) for _, c in rows)
    x0 = 16 + labw
    sc = (W - 32 - labw - vw) / mx
    b, y = [], 16
    for lab, counts in rows:
        lines = wrap(lab, labw - 16)
        rh = max(ROW + 8, len(lines) * FS * 1.2 + 12)
        cy, x = y + rh / 2, x0
        b.append(F.text(x0 - 12, cy, lines, FS, 'normal', anchor='end', fill=F.INK, lh=1.2))
        for (v, _), n in zip(SEES, counts):
            if not n:
                continue
            w = n * sc
            dash = ' stroke-dasharray="5,3"' if v == 'no-check' else ''
            b.append(f'<rect x="{x:.1f}" y="{cy - (BAR + 6) / 2:.1f}" width="{w:.1f}" height="{BAR + 6}" fill="{SEE[v]}" stroke="{GREY if v in ("unclear", "no-check") else "#FFFFFF"}" stroke-width="1.3"{dash}/>')
            b.append(F.text(x + w / 2, cy, str(n), FS, 'bold', fill='#FFFFFF' if v == 'yes' else F.INK))
            x += w
        b.append(F.text(x + 10, cy, str(sum(counts)), FS, 'bold', anchor='start', fill=F.INK2))
        y += rh
    b.append(f'<line x1="{x0:.1f}" y1="16" x2="{x0:.1f}" y2="{y:.1f}" stroke="{F.INK2}" stroke-width="1.2"/>')
    svg, y = legend(16, y + 34, W - 32, [(lab, SEE[v], GREY if v in ('unclear', 'no-check', 'no') else SEE[v], '5,3' if v == 'no-check' else None)
                                         for v, lab in SEES])
    b.append(svg)
    FG.record('sq3_checks', kind='bar_stacked', categories=[l for l, _ in rows],
              series=[[lab, SEE[v], [c[i] for _, c in rows]] for i, (v, lab) in enumerate(SEES)])
    return F.render('sq3_checks', W, int(y + 4), ''.join(b))


def main(S, prim):
    """draw the three charts; prim: the ids of the designs"""
    sq1(S, prim)
    sq2(S, prim)
    sq3(S, prim)
