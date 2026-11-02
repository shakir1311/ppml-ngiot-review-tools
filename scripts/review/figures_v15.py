#!/usr/bin/env python3
"""Figures of the V15 review, written to myliteraturereviewpaper/_src/V15/figures.

Diagrams (PRISMA flow, reference architecture, research design) and charts (studies per year and per theme,
privacy mechanisms, open challenges) are computed from the V15 set of included studies. The taxonomy is shared
with V14 and copied unchanged. Drawing helpers come from figures_static and figures_data; colours follow the
validated two-series palette of the dataviz method.

Usage: scripts/.venv/bin/python scripts/review/figures_v15.py
"""
import collections, shutil, sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import figures_static as FS        # noqa: E402
import figures_data as FD          # noqa: E402
import tables_v15 as T             # noqa: E402
from figures_static import box, arrow, text, esc, render, FONT, INK, INK2, BLUE, BLUE_L, BLUE_XL, ORANGE, ORANGE_L, \
    AQUA, AQUA_L, VIOLET, VIOLET_L, GREY, GREY_L, RED, RED_L   # noqa: E402

FS.OUT = FS.ROOT / 'myliteraturereviewpaper' / '_src' / 'V15' / 'figures'
FS.OUT.mkdir(parents=True, exist_ok=True)
S1, S2, GRID = FD.S1, FD.S2, FD.GRID


# ------------------------------------------------------------------ PRISMA 2020 flow diagram
def prisma(c):
    W, H = 900, 780
    b = []
    for y0, hh, lab in ((20, 150, 'Identification'), (190, 420, 'Screening'), (630, 130, 'Included')):
        b.append(f'<rect x="16" y="{y0}" width="34" height="{hh}" rx="5" fill="{BLUE}"/>')
        b.append(f'<text transform="translate(38,{y0 + hh / 2}) rotate(-90)" font-family="{FONT}" font-size="14" '
                 f'font-weight="bold" fill="#ffffff" text-anchor="middle">{lab}</text>')
    L, LW, R, RW = 70, 400, 520, 360
    b.append(box(L, 30, LW, 120, ['Records identified in the search rounds,', 'January–September 2026: database searches',
                                  'and citation searching (snowballing)', f"(n = {c['identified']})"], size=13.5))
    b.append(box(R, 30, RW, 120, ['Records removed before screening:', f"duplicates (n = {c['dup']})",
                                  'preprints superseded by the', f"published version (n = {c['superseded']})"],
                 fill=GREY_L, stroke=GREY, size=13))
    b.append(arrow(L + LW, 90, R, 90))
    b.append(arrow(L + LW / 2, 150, L + LW / 2, 215))
    b.append(box(L, 215, LW, 70, ['Records screened (date, title and', f"abstract) (n = {c['screened']})"],
                 size=13.5))
    b.append(box(R, 215, RW, 70, [f"Records excluded (n = {c['excl_screen']}):",
                                  f"published before 2020, IC4 (n = {c['excl_screen_period']})"],
                 fill=GREY_L, stroke=GREY, size=13))
    b.append(arrow(L + LW, 250, R, 250))
    b.append(arrow(L + LW / 2, 285, L + LW / 2, 335))
    b.append(box(L, 335, LW, 60, [f"Reports sought for retrieval (n = {c['sought']})"], size=13.5))
    b.append(box(R, 335, RW, 60, ['Reports not retrieved (n = 0)'], fill=GREY_L, stroke=GREY, size=13))
    b.append(arrow(L + LW, 365, R, 365))
    b.append(arrow(L + LW / 2, 395, L + LW / 2, 445))
    b.append(box(L, 445, LW, 70, ['Reports assessed for eligibility', f"(full text) (n = {c['assessed']})"], size=13.5))
    b.append(box(R, 420, RW, 130, [f"Reports excluded (n = {c['excl_full']}):",
                                   f"retracted by the publisher, EC1 (n = {c['excl_full_retracted']})",
                                   f"out of topic, IC1 (n = {c['excl_full_topic']})",
                                   f"no identifiable venue, IC3 (n = {c['excl_full_venue']})"],
                 fill=GREY_L, stroke=GREY, size=13))
    b.append(arrow(L + LW, 480, R, 480))
    b.append(arrow(L + LW / 2, 515, L + LW / 2, 645))
    b.append(box(L, 645, LW, 100, [f"Studies included in the review (n = {c['included']})",
                                   f"primary studies (n = {c['primary']})",
                                   f"secondary studies (n = {c['secondary']})"], fill=BLUE_L, stroke=BLUE, size=14))
    b.append(text(R + RW / 2, 695, ['IC = inclusion criterion, EC = exclusion criterion', '(Table V)'], size=12,
                  fill=INK2, italic=True))
    return render('fig-prisma', W, H, ''.join(b))


# ------------------------------------------------------------------ reference architecture
def architecture():
    W, H = 980, 660
    b = []
    tiers = [(20, 120, 'Cloud tier', 'model archive, auditing (optional)'),
             (155, 185, 'Edge tier (5G MEC)', 'aggregation, ledger peers, verification'),
             (355, 215, 'Device tier (NG-IoT)', 'local training on private data')]
    for y, hh, name, sub in tiers:
        b.append(f'<rect x="20" y="{y}" width="700" height="{hh}" rx="8" fill="{GREY_L}" stroke="{GREY}" stroke-width="1"/>')
        b.append(text(34, y + 20, name, 13.5, 'bold', 'start', INK))
        b.append(text(34, y + 39, sub, 12, 'normal', 'start', INK2))
    b.append(box(500, 45, 200, 60, ['Global model and', 'audit copy (off-chain)'], fill='#ffffff', stroke=GREY, size=12.5))
    b.append(box(60, 215, 180, 100, ['5G gNB / core', '(radio links to', 'the devices)'], fill='#ffffff', stroke=GREY, size=12.5))
    b.append(box(270, 215, 200, 100, ['Edge aggregator', '(secure aggregation,', 'robust checks)'], fill=BLUE_XL, stroke=BLUE, size=12.5))
    b.append(box(500, 215, 200, 100, ['Permissioned ledger', '(identities, proofs and', 'commitments, reputation,', 'incentives)'],
                 fill=AQUA_L, stroke=AQUA, size=12))
    b.append(arrow(240, 265, 270, 265, color=BLUE))
    b.append(arrow(470, 265, 500, 265, color=AQUA))
    b.append(arrow(600, 215, 600, 105, color=INK2, dash='4 3'))
    xs = [60, 190, 320, 450, 580]
    bus_y = 430
    b.append(f'<line x1="115" y1="{bus_y}" x2="635" y2="{bus_y}" stroke="{BLUE}" stroke-width="1.6"/>')
    b.append(text(420, bus_y - 12, 'wireless / 5G links', 12, 'normal', 'middle', BLUE, italic=True))
    for i, x in enumerate(xs):
        lab = ['IoT device', f'client {i + 1}'] if i < 4 else ['IoT device', 'client n']
        b.append(box(x, 470, 110, 55, lab, fill='#ffffff', stroke=BLUE, size=12))
        b.append(f'<line x1="{x + 55}" y1="470" x2="{x + 55}" y2="{bus_y}" stroke="{BLUE}" stroke-width="1.3"/>')
    b.append(arrow(222, bus_y, 222, 315, color=BLUE, sw=1.6))
    b.append(text(370, 551, 'model updates, protected by the privacy plane, travel up; the aggregated model returns', 12,
                  fill=INK2, italic=True))
    px = 740
    b.append(text(px + 110, 28, 'Planes across the tiers', 13.5, 'bold'))
    planes = [(['Learning plane', 'FL, decentralised FL,', 'split or swarm learning'], BLUE_XL, BLUE),
              (['Privacy plane', 'DP / LDP, HE, SMPC and', 'secure aggregation,', 'TEE, ZKP'], VIOLET_L, VIOLET),
              (['Trust plane', 'blockchain: aggregate,', 'record, verify, enforce', '(consensus, contracts)'], AQUA_L, AQUA),
              (['Governance plane', 'GDPR, EDPB Guidelines', '02/2025: on-chain vs', 'off-chain, erasure'], GREY_L, GREY)]
    y = 45
    for lines, fill, stroke in planes:
        b.append(box(px, y, 220, 118, lines, fill=fill, stroke=stroke, size=12.5))
        y += 131
    b.append(f'<rect x="20" y="590" width="940" height="56" rx="6" fill="{RED_L}" stroke="{RED}" stroke-width="1.1"/>')
    b.append(text(490, 618, ['Threats: data poisoning · malicious participants inserting fake nodes (Sybil) · free riding ·',
                             'DDoS on the learning service · inference attacks on the model updates'], 12.5))
    return render('fig-architecture', W, H, ''.join(b))


# ------------------------------------------------------------------ research design (design science)
def design():
    W, H = 980, 520
    b = []
    steps = [('1', 'Problem and', 'motivation', ['this systematic review;', 'gaps G1–G4']),
             ('2', 'Objectives and', 'requirements', ['requirements', 'R1–R4']),
             ('3', 'Design and', 'development', ['proofs and the', "ledger's role"]),
             ('4', 'Demonstration', '', ['prototype on', 'IoT gateways']),
             ('5', 'Evaluation', '', ['cost (RQ1), protection', '(RQ2); H1–H3']),
             ('6', 'Communication', '', ['publications,', 'code and data'])]
    x, w, g = 20, 142, 17
    for i, (n, t1, t2, sub) in enumerate(steps):
        fill, stroke = (ORANGE_L, ORANGE) if i in (2, 3, 4) else (BLUE_XL, BLUE)
        b.append(f'<rect x="{x}" y="40" width="{w}" height="150" rx="8" fill="{fill}" stroke="{stroke}" stroke-width="1.3"/>')
        b.append(f'<circle cx="{x + 22}" cy="62" r="13" fill="{stroke}"/>')
        b.append(text(x + 22, 62, n, 13, 'bold', fill='#ffffff'))
        b.append(text(x + w / 2 + 10, 100, [t1, t2] if t2 else [t1], 13.5, 'bold'))
        b.append(text(x + w / 2, 155, sub, 11.5, fill=INK2))
        if i < len(steps) - 1:
            b.append(arrow(x + w, 115, x + w + g, 115))
        x += w + g
    x2, x4 = 20 + 2 * (w + g) + w / 2, 20 + 4 * (w + g) + w / 2
    b.append(f'<path d="M {x4} 190 C {x4} 235, {x2} 235, {x2} 196" fill="none" stroke="{ORANGE}" stroke-width="1.4" '
             f'stroke-dasharray="5 3"/>')
    b.append(f'<polygon points="{x2},190 {x2 - 5},200 {x2 + 5},200" fill="{ORANGE}"/>')
    b.append(text(20 + 3 * (w + g) + w / 2, 245, 'iterate: refine the design from the evaluation', 12, fill=ORANGE, italic=True))
    b.append(f'<rect x="20" y="275" width="940" height="225" rx="8" fill="#ffffff" stroke="{GREY}" stroke-width="1.1"/>')
    b.append(text(40, 297, 'First experiments in step 5, starting from Veri-CS-FL and kept small', 13.5, 'bold', 'start'))
    rows = [('Compared', 'federated averaging · the same checks in plaintext · Krum-style aggregation · checks enforced by proofs'),
            ('Threats', 'label flipping and backdoors by 10–20% of the clients, some colluding; free riders as a secondary outcome'),
            ('Data', 'MNIST and FEMNIST as in Veri-CS-FL, then an IoT intrusion-detection dataset'),
            ('Measures', 'accuracy, attack success · set-up time, key size, proof time, peak memory, proof size · verification time'),
            ('Devices', 'a Raspberry Pi 4 and a laptop; an emulated IoT and 5G network in a later phase'),
            ('Statistics', 'ten runs per cost measurement, several seeds per learning run; mean ± SD, 95% CI, paired tests')]
    y = 327
    for k, v in rows:
        b.append(text(40, y, k, 12.5, 'bold', 'start', BLUE))
        b.append(text(140, y, v, 12.5, 'normal', 'start', INK))
        y += 29
    return render('fig-design', W, H, ''.join(b))


# ------------------------------------------------------------------ charts
def overview(d):
    """(a) included studies per year, stacked by kind; (b) included studies per theme, by kind."""
    C = d['coding']
    inc = d['included']
    kind = lambda i: T.kind(d, i)
    W = 900
    b = [FD.legend(70, 24, [('Primary studies', S1), ('Secondary studies', S2)])]
    # panel (a)
    years = list(range(2020, 2027))
    prim = [sum(1 for i in inc if T.year(d, i) == y and kind(i) == 'primary') for y in years]
    sec = [sum(1 for i in inc if T.year(d, i) == y and kind(i) == 'secondary') for y in years]
    b.append(text(20, 58, '(a) Studies per year of publication', 13.5, 'bold', 'start'))
    left, top, pw, ph = 70, 80, W - 90, 230
    totals = [p + s for p, s in zip(prim, sec)]
    step = 10
    ymax = ((max(totals) // step) + 1) * step
    for v in range(0, ymax + 1, step):
        y = top + ph - ph * v / ymax
        b.append(f'<line x1="{left}" y1="{y:.1f}" x2="{left + pw}" y2="{y:.1f}" stroke="{GRID}" stroke-width="1"/>')
        b.append(text(left - 8, y, str(v), 11.5, 'normal', 'end', INK2))
    bw = pw / len(years)
    for i, yv in enumerate(years):
        x, w, y = left + i * bw + bw * 0.2, bw * 0.6, top + ph
        for val, col in ((prim[i], S1), (sec[i], S2)):
            h = ph * val / ymax
            if h > 0:
                b.append(f'<rect x="{x:.1f}" y="{y - h + 1:.1f}" width="{w:.1f}" height="{max(h - 2, 0.5):.1f}" rx="2" fill="{col}"/>')
            y -= h
        b.append(text(x + w / 2, y - 9, str(totals[i]), 11.5, 'bold', 'middle', INK))
        b.append(text(x + w / 2, top + ph + 18, str(yv), 12, 'normal', 'middle', INK2))
    b.append(f'<text transform="translate(26,{top + ph / 2}) rotate(-90)" font-family="{FONT}" font-size="12" '
             f'fill="{INK2}" text-anchor="middle">Studies</text>')
    # panel (b)
    y0 = top + ph + 60
    b.append(text(20, y0, '(b) Studies per theme', 13.5, 'bold', 'start'))
    th = list(T.THEMES.items())
    p = [sum(1 for i in inc if C[i]['theme'] == t and kind(i) == 'primary') for t, _ in th]
    s = [sum(1 for i in inc if C[i]['theme'] == t and kind(i) == 'secondary') for t, _ in th]
    label_w, bar_h, gap = 340, 22, 8
    xmax = max(a + c for a, c in zip(p, s))
    pw2 = W - label_w - 60
    for k, (_, name) in enumerate(th):
        y = y0 + 20 + k * (bar_h + gap)
        b.append(text(label_w - 10, y + bar_h / 2, name, 12.5, 'normal', 'end', INK))
        x = label_w
        for val, col in ((p[k], S1), (s[k], S2)):
            w = pw2 * val / xmax
            if w > 0:
                b.append(f'<rect x="{x + 1:.1f}" y="{y}" width="{max(w - 2, 0.5):.1f}" height="{bar_h}" rx="2" fill="{col}"/>')
            x += w
        b.append(text(x + 8, y + bar_h / 2, str(p[k] + s[k]), 12, 'bold', 'start', INK))
    H = int(y0 + 20 + len(th) * (bar_h + gap) + 16)
    return render('fig-overview', W, H, ''.join(b))


def mechanisms(d):
    C = d['coding']
    pr = [i for i in d['included'] if T.kind(d, i) == 'primary']
    groups = collections.OrderedDict([
        ('Differential privacy (DP, LDP)', {'DP', 'LDP'}),
        ('Homomorphic encryption (HE, FHE)', {'HE', 'FHE'}),
        ('Secret sharing, SMPC, secure aggregation', {'secret_sharing', 'SMPC', 'secure_aggregation'}),
        ('Trusted execution (TEE)', {'TEE'}),
        ('Zero-knowledge proofs (ZKP)', {'ZKP'}),
        ('Obfuscation, synthetic data, split learning', {'perturbation_obfuscation', 'split_learning', 'GAN_synthetic', 'anonymisation', 'unlearning'}),
        ('No privacy mechanism', {'none'}),
    ])

    def has(i, codes):
        ms = set(m for m in C[i]['privacy_mechanisms'] if not m.startswith('other'))
        if codes == {'none'}:
            return not (ms - {'none'})
        return bool(ms & codes)
    wl = [sum(1 for i in pr if C[i]['ledger'].get('used') and has(i, g)) for g in groups.values()]
    nl = [sum(1 for i in pr if not C[i]['ledger'].get('used') and has(i, g)) for g in groups.values()]
    return FD.hbars('fig-mechanisms', list(groups), [wl, nl], [S1, S2], ['With a ledger', 'Without a ledger'], label_w=330)


def challenges(d):
    ch = T.challenge_counts(d)
    items = sorted([(c, ids) for c, ids in ch.items() if c != 'C99' and ids], key=lambda kv: -len(kv[1]))
    cats = [T.CHALLENGE[c] for c, _ in items]
    p = [sum(1 for i in ids if T.kind(d, i) == 'primary') for _, ids in items]
    s = [sum(1 for i in ids if T.kind(d, i) == 'secondary') for _, ids in items]
    return FD.hbars('fig-challenges', cats, [p, s], [S1, S2], ['Primary studies', 'Secondary studies'], label_w=360)


def main():
    d = T.load()
    out = [prisma(d['prisma']), architecture(), design(), overview(d), mechanisms(d), challenges(d)]
    tax = FS.ROOT / 'myliteraturereviewpaper' / '_src' / 'V14' / 'figures' / 'fig-taxonomy.png'
    shutil.copy(tax, FS.OUT / 'fig-taxonomy.png')
    for f in out:
        print(f.name)


if __name__ == '__main__':
    main()
