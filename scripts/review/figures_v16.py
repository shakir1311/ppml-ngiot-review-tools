#!/usr/bin/env python3
"""Figures of the V16 review, written to myliteraturereviewpaper/_src/V16/figures.

Diagrams (PRISMA flow, reference architecture, research design) and charts (studies per year and per theme,
privacy mechanisms, open challenges) are computed from the V16 set of included studies. The taxonomy is shared
with V14 and copied unchanged. Drawing helpers come from figures_static and figures_data; colours follow the
validated two-series palette of the dataviz method.

Usage: scripts/.venv/bin/python scripts/review/figures_v15.py
"""
import collections, shutil, sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import figures_static as FS        # noqa: E402
import figures_data as FD          # noqa: E402
import tables_v16 as T             # noqa: E402
from figures_static import box, arrow, text, esc, render, FONT, INK, INK2, BLUE, BLUE_L, BLUE_XL, ORANGE, ORANGE_L, \
    AQUA, AQUA_L, VIOLET, VIOLET_L, GREY, GREY_L, RED, RED_L   # noqa: E402

FS.OUT = FS.ROOT / 'myliteraturereviewpaper' / '_src' / 'V16' / 'figures'
FS.OUT.mkdir(parents=True, exist_ok=True)
S1, S2, GRID = FD.S1, FD.S2, FD.GRID


# ------------------------------------------------------------------ PRISMA 2020 flow diagram
def prisma(c):
    W, H = 1030, 800
    b = []
    for y0, hh, lab in ((20, 150, 'Identification'), (190, 420, 'Screening'), (630, 150, 'Included')):
        b.append(f'<rect x="16" y="{y0}" width="34" height="{hh}" rx="5" fill="{BLUE}"/>')
        b.append(f'<text transform="translate(38,{y0 + hh / 2}) rotate(-90)" font-family="{FONT}" font-size="14" '
                 f'font-weight="bold" fill="#ffffff" text-anchor="middle">{lab}</text>')
    L, LW, R, RW, O, OW = 66, 335, 420, 280, 735, 280
    b.append(text(L + LW / 2, 13, ['Search rounds and snowballing'], size=12.5, fill=INK2, italic=True))
    b.append(text(O + OW / 2, 13, ['After the search rounds'], size=12.5, fill=INK2, italic=True))
    b.append(box(L, 30, LW, 120, ['Records retained from the', 'search rounds, January–', 'September 2026 (database', f"searches, snowballing) (n = {c['identified']})"], size=13))
    b.append(box(R, 30, RW, 120, ['Records removed before', f"screening: duplicates (n = {c['dup']});", 'preprints superseded by the', f"published version (n = {c['superseded']})"],
                 fill=GREY_L, stroke=GREY, size=12.5))
    b.append(arrow(L + LW, 90, R, 90))
    b.append(arrow(L + LW / 2, 150, L + LW / 2, 215))
    b.append(box(L, 215, LW, 70, ['Records screened (date, title', f"and abstract) (n = {c['screened']})"], size=13))
    b.append(box(R, 215, RW, 70, [f"Records excluded (n = {c['excl_screen']}):", f"published before 2020, IC4"], fill=GREY_L, stroke=GREY, size=12.5))
    b.append(arrow(L + LW, 250, R, 250))
    b.append(arrow(L + LW / 2, 285, L + LW / 2, 335))
    b.append(box(L, 335, LW, 60, [f"Reports sought for retrieval (n = {c['sought']})"], size=13))
    b.append(box(R, 335, RW, 60, ['Reports not retrieved (n = 0)'], fill=GREY_L, stroke=GREY, size=12.5))
    b.append(arrow(L + LW, 365, R, 365))
    b.append(arrow(L + LW / 2, 395, L + LW / 2, 445))
    b.append(box(L, 445, LW, 70, ['Reports assessed for eligibility', f"(full text) (n = {c['assessed']})"], size=13))
    b.append(box(R, 420, RW, 130, [f"Reports excluded (n = {c['excl_full']}):", f"retracted, EC1 (n = {c['excl_full_retracted']})",
                                   f"out of topic, IC1 (n = {c['excl_full_topic']})", f"no identifiable venue, IC3 (n = {c['excl_full_venue']})"],
                 fill=GREY_L, stroke=GREY, size=12.5))
    b.append(arrow(L + LW, 480, R, 480))
    b.append(arrow(L + LW / 2, 515, L + LW / 2, 645))
    # other methods: citation searching (included) and snowballing from two surveys (not retrieved)
    b.append(box(O, 30, OW, 120, ['Citation searching of the', 'included studies', f"(n = {c['other_identified']})"], size=13))
    b.append(arrow(O + OW / 2, 150, O + OW / 2, 215))
    b.append(box(O, 215, OW, 70, ['Reports assessed for', f"eligibility (n = {c['other_assessed']})"], size=13))
    b.append(f'<path d="M {O} 250 L {O - 17} 250 L {O - 17} 695 L {L + LW + 8} 695" fill="none" stroke="{INK2}" stroke-width="1.4"/>')
    b.append(arrow(L + LW + 9, 695, L + LW, 695))
    b.append(box(O, 335, OW, 90, ['Backward snowballing from', 'two surveys of verifiable FL', f"(n = {c['snow_identified']})"], size=13))
    b.append(arrow(O + OW / 2, 425, O + OW / 2, 470))
    b.append(box(O, 470, OW, 80, [f"Reports sought (n = {c['snow_identified']});", f"not retrieved (n = {c['snow_not_retrieved']})"],
                 fill=GREY_L, stroke=GREY, size=12.5))
    b.append(box(L, 645, LW, 100, [f"Studies included (n = {c['included']})", f"primary studies (n = {c['primary']})",
                                   f"secondary studies (n = {c['secondary']})"], fill=BLUE_L, stroke=BLUE, size=13.5))
    b.append(text(O + OW / 2 - 60, 772, ['IC = inclusion criterion, EC = exclusion criterion'], size=11.5,
                  fill=INK2, italic=True))
    return render('fig-prisma', W, H, ''.join(b))


def taxonomy(d):
    """The taxonomy, with the number of primary studies under each leaf that was classified for all of them."""
    C = d['coding']
    prim = [i for i in d['included'] if T.kind(d, i) == 'primary']
    n = lambda f: sum(1 for i in prim if f(C[i]))
    mech = lambda *codes: n(lambda c: bool(set(c['privacy_mechanisms']) & set(codes)))
    lrn = lambda *codes: n(lambda c: bool(set(c.get('learning', [])) & set(codes)))
    led = [i for i in prim if C[i]['ledger'].get('used')]
    ltype = lambda k: sum(1 for i in led if (C[i]['ledger'].get('type') or '').lower().startswith(k))
    oc = collections.Counter(d['onchain'].get(i) for i in led)
    th = lambda k: n(lambda c: bool(set(c['threats']) & T.THREATS15[k][1]))
    branches = [
        ('A', 'NG-IoT setting', BLUE, BLUE_XL, ['Tiers: device, gateway, edge (MEC), cloud',
                                                 'Links: BLE, Zigbee, Wi-Fi, LoRaWAN and LPWAN, 5G / 6G',
                                                 'Who trains: device, gateway, edge server, organisation']),
        ('B', 'Distributed learning', '#184f95', BLUE_XL, [f"Server-based FL ({lrn('FL')}), hierarchical FL ({lrn('hierarchical_FL')})",
                                                          f"Decentralised FL ({lrn('DFL')}), swarm learning ({lrn('swarm')})",
                                                          f"Split learning ({lrn('split')})"]),
        ('C', 'Confidentiality', VIOLET, VIOLET_L, [f"DP and local DP ({mech('DP', 'LDP')}); HE ({mech('HE', 'FHE')})",
                                                     f"SMPC and secret sharing ({mech('SMPC', 'secret_sharing')}); secure aggregation ({mech('secure_aggregation')})",
                                                     f"Trusted execution ({mech('TEE')}); none beyond local data ({mech('none')})"]),
        ('D', 'Verification', ORANGE, '#fff4dc', ['What: data binding, training, admissibility, freshness;',
                                                  '  admitted set, aggregation, non-equivocation',
                                                  f"How: inspection, computation on hidden data, attestation, ZKP ({mech('ZKP')})",
                                                  'Who can verify: anyone, participants, a trusted party']),
        ('E', f'Ledger ({len(led)})', AQUA, AQUA_L, [f"Type: public ({ltype('public')}), consortium ({ltype('consortium')}), permissioned ({ltype('permissioned')})",
                                                     'Roles: aggregate, record, verify, enforce',
                                                     f"On-chain: updates ({oc['U']}), encrypted updates ({oc['E']}),",
                                                     f"  models ({oc['G']}), commitments or proofs only ({oc['C']})"]),
        ('F', 'Parties and threats', RED, RED_L, [f"Clients: poisoning ({th('P')}), fake nodes ({th('S')}), free riding ({th('R')}),",
                                                  f"  collusion ({th('C')})",
                                                  f"Aggregator, validators, eavesdroppers: inference ({th('I')})",
                                                  f"Network: denial of service and jamming ({th('D')})"]),
        ('G', 'Evaluation and governance', '#7a5a14', '#f6efe0', ['Data, devices, networks, repeated runs, metrics',
                                                                   'GDPR and EDPB Guidelines 02/2025; erasure and unlearning']),
    ]
    W = 1000
    b = []
    rootx, rw, rh = 16, 170, 110
    bx, bw = 225, 205
    lx, lw = 455, 530
    y = 16
    blocks = []
    for code, name, stroke, fill, leaves in branches:
        hh = max(62, 19 * len(leaves) + 22)
        blocks.append((y, hh))
        y += hh + 10
    total = y
    rooty = total / 2 - rh / 2
    b.append(box(rootx, rooty, rw, rh, ['Privacy-preserving', 'and verifiable FL', 'for NG-IoT'], fill=GREY_L, stroke=INK2, size=13.5, weight='bold'))
    for (code, name, stroke, fill, leaves), (y, hh) in zip(branches, blocks):
        cy = y + hh / 2
        b.append(f'<path d="M {rootx + rw} {rooty + rh / 2} C {rootx + rw + 28} {rooty + rh / 2}, {bx - 28} {cy}, {bx} {cy}" fill="none" stroke="{stroke}" stroke-width="1.6"/>')
        b.append(f'<rect x="{bx}" y="{cy - 22}" width="{bw}" height="44" rx="7" fill="{stroke}"/>')
        b.append(text(bx + bw / 2, cy, f'{code}. {name}', 13.5, 'bold', fill='#ffffff'))
        b.append(f'<line x1="{bx + bw}" y1="{cy}" x2="{lx}" y2="{cy}" stroke="{stroke}" stroke-width="1.6"/>')
        b.append(f'<rect x="{lx}" y="{y}" width="{lw}" height="{hh}" rx="7" fill="{fill}" stroke="{stroke}" stroke-width="1.2"/>')
        ty = y + (hh - 19 * len(leaves)) / 2 + 9.5
        for leaf in leaves:
            indent = 14 if leaf.startswith('  ') else 0
            b.append(text(lx + 12 + indent, ty, leaf.strip(), 12.5, 'normal', 'start', INK))
            ty += 19
    return render('fig-taxonomy', W, int(total + 6), ''.join(b))


# ------------------------------------------------------------------ reference architecture
def architecture():
    """Where the reviewed designs place their mechanisms: tiers, who trains, what the ledger may hold, threat entry points."""
    W, H = 1000, 770
    b = []
    tiers = [(18, 88, 'Cloud tier'), (116, 212, 'Edge tier (MEC)'), (338, 118, 'Gateway tier'), (466, 156, 'Device tier')]
    for y, hh, name in tiers:
        b.append(f'<rect x="20" y="{y}" width="720" height="{hh}" rx="8" fill="{GREY_L}" stroke="{GREY}" stroke-width="1"/>')
        b.append(text(34, y + 19, name, 13.5, 'bold', 'start', INK))
    b.append(box(405, 34, 320, 58, ['Model archive and audit copy', '(optional, off-chain)'], fill='#ffffff', stroke=GREY, size=12.5))
    # edge tier
    GN, AG, LG, AD = (40, 150, 135, 90), (200, 150, 185, 90), (405, 150, 190, 110), (615, 150, 110, 110)
    b.append(box(*GN, ['5G gNB', 'with MEC'], fill='#ffffff', stroke=GREY, size=12.5))
    b.append(box(*AG, ['Aggregator', '(secure aggregation,', 'checks on updates)'], fill=BLUE_XL, stroke=BLUE, size=12.5))
    b.append(box(*LG, ['Ledger nodes', '(public or', 'permissioned): record', 'U, E, G or C;', 'verify proofs'], fill=AQUA_L, stroke=AQUA, size=12))
    b.append(box(*AD, ['Admission', 'service', '(identities,', 'certificates)'], fill='#ffffff', stroke=AQUA, size=12))
    b.append(arrow(175, 195, 200, 195, color=BLUE))
    b.append(arrow(385, 195, 405, 195, color=AQUA))
    b.append(arrow(595, 205, 615, 205, color=AQUA, dash='4 3'))
    b.append(arrow(500, 150, 500, 92, color=INK2, dash='4 3'))
    # gateway tier: gateways as FL clients
    G1, G2 = (200, 362, 185, 76), (405, 362, 190, 76)
    for g in (G1, G2):
        b.append(box(*g, ['IoT gateway: FL client', 'for the devices behind', 'it; update and proof'], fill=BLUE_XL, stroke=BLUE, size=12))
    b.append(arrow(260, 362, 260, 240, color=BLUE, sw=1.5))                     # G1 -> aggregator: update
    b.append(arrow(350, 362, 440, 260, color=ORANGE, sw=1.4, dash='5 3'))       # G1 -> ledger: proof
    b.append(arrow(430, 362, 360, 240, color=BLUE, sw=1.5))                     # G2 -> aggregator: update
    b.append(arrow(540, 362, 540, 260, color=ORANGE, sw=1.4, dash='5 3'))       # G2 -> ledger: proof
    # device tier
    PH, S1, S2 = (40, 500, 135, 96), (200, 500, 185, 96), (405, 500, 190, 96)
    b.append(box(*PH, ['Phones and', 'vehicles: FL', 'clients over', '5G links'], fill=BLUE_XL, stroke=BLUE, size=12))
    b.append(box(*S1, ['Sensors and actuators', '(microcontrollers) on', 'BLE, Zigbee, LoRaWAN', 'or Wi-Fi links'], fill='#ffffff', stroke=GREY, size=12))
    b.append(box(*S2, ['More sensors', 'behind a second', 'gateway'], fill='#ffffff', stroke=GREY, size=12))
    b.append(arrow(157, 500, 157, 240, color=BLUE, sw=1.5))                     # phones -> gNB
    b.append(arrow(292, 500, 292, 438, color=GREY, sw=1.4))
    b.append(arrow(500, 500, 500, 438, color=GREY, sw=1.4))
    b.append(text(620, 520, ['solid: model updates', '(kept confidential)', 'dashed: proofs'], 11.5, 'normal', 'start', INK2, italic=True))
    b.append(text(380, 611, 'the aggregated model returns to the clients by the same routes', 11.5, 'normal', 'middle', INK2, italic=True))
    # threat entry points, on box corners
    marks = [(G1[0], G1[1], '1'), (G2[0], G2[1], '1'), (PH[0], PH[1], '1'), (AD[0] + AD[2], AD[1], '2'),
             (GN[0] + GN[2], GN[1], '3'), (AG[0] + AG[2], AG[1], '3'), (LG[0] + LG[2], LG[1], '3'), (S1[0] + S1[2], S1[1], '3'),
             (S2[0] + S2[2], S2[1], '3'), (AG[0], AG[1], '4'), (LG[0], LG[1], '4'), (S1[0], S1[1], '4')]
    for x, y, n in marks:
        b.append(f'<circle cx="{x}" cy="{y}" r="10" fill="{RED}"/>')
        b.append(text(x, y, n, 11.5, 'bold', 'middle', '#ffffff'))
    # planes
    px = 760
    b.append(text(px + 110, 28, 'Planes across the tiers', 13.5, 'bold'))
    planes = [(['Learning', 'FL, hierarchical or', 'decentralised FL'], BLUE_XL, BLUE),
              (['Confidentiality', 'DP, HE, SMPC and secure', 'aggregation, TEE'], VIOLET_L, VIOLET),
              (['Verification', 'inspection, computation on', 'hidden data, attestation,', 'zero-knowledge proofs'], '#fff4dc', ORANGE),
              (['Trust (ledger)', 'aggregate, record,', 'verify, enforce'], AQUA_L, AQUA),
              (['Governance', 'GDPR, EDPB Guidelines', '02/2025, erasure'], GREY_L, GREY)]
    y = 45
    for lines, fill, stroke in planes:
        hh = 20 * len(lines) + 22
        b.append(box(px, y, 220, hh, lines, fill=fill, stroke=stroke, size=12.5))
        y += hh + 12
    # threat legend
    b.append(f'<rect x="20" y="640" width="960" height="118" rx="6" fill="{RED_L}" stroke="{RED}" stroke-width="1.1"/>')
    b.append(text(34, 662, 'Where threats enter', 13, 'bold', 'start', INK))
    rows = ['1  Poisoning and free riding: at the FL clients (gateways, phones, vehicles)',
            '2  Fake nodes (Sybil) and compromised registered devices: at admission',
            '3  Denial of service: jamming of radio links, energy depletion, floods of the gNB, aggregator or ledger nodes',
            '4  Inference: at the aggregator, at ledger nodes that read on-chain updates, and on poorly protected radio links']
    for k, r in enumerate(rows):
        b.append(text(44, 686 + k * 19, r, 12, 'normal', 'start', INK))
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
    b.append(text(20, 58, '(a) Studies per year of publication (* 2026 to September)', 13.5, 'bold', 'start'))
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
        b.append(text(x + w / 2, top + ph + 18, f'{yv}*' if yv == 2026 else str(yv), 12, 'normal', 'middle', INK2))
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
    out = [prisma(d['prisma']), taxonomy(d), architecture(), overview(d), mechanisms(d), challenges(d)]
    for f in out:
        print(f.name)


if __name__ == '__main__':
    main()
