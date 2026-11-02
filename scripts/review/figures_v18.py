#!/usr/bin/env python3
"""Figures of the V18 review, written to myliteraturereviewpaper/_src/V18/figures.

The drawings of V17 (selection, taxonomy, reference architecture, overview, mechanisms, challenges), computed from the
same included studies, plus the figures that are new in V18.

Usage: scripts/.venv/bin/python scripts/review/figures_v18.py
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import tables_v18 as T18            # noqa: E402
import figures_v17 as F17           # noqa: E402  (sets figures_v16 to the V17 data)

F = F17.F
F.FS.OUT = F.FS.ROOT / 'myliteraturereviewpaper' / '_src' / 'V18' / 'figures'
F.FS.OUT.mkdir(parents=True, exist_ok=True)


from figures_static import box, arrow, text, render, INK, INK2, BLUE, BLUE_L, BLUE_XL, AQUA, AQUA_L, ORANGE, ORANGE_L, RED, RED_L, GREY, GREY_L, VIOLET, VIOLET_L  # noqa: E402,E501
import collections                    # noqa: E402


def step(x, y, n, color=ORANGE):
    """a numbered round step"""
    return (f'<circle cx="{x}" cy="{y}" r="11" fill="{color}"/>' + text(x, y, str(n), 12, 'bold', fill='#ffffff'))


def agenda():
    """The reference design of Section VIII-B: gateways prove a check in zero knowledge, a permissioned edge ledger verifies."""
    W, H = 1000, 640
    b = []
    for y, hh, name in ((16, 262, 'Edge tier'), (294, 170, 'Gateway tier'), (480, 110, 'Device tier')):
        b.append(f'<rect x="20" y="{y}" width="960" height="{hh}" rx="8" fill="{GREY_L}" stroke="{GREY}" stroke-width="1"/>')
        b.append(text(34, y + 19, name, 13.5, 'bold', 'start', INK))
    # edge tier
    AD, LG, AG = (40, 52, 200, 120), (272, 52, 356, 150), (660, 52, 300, 120)
    b.append(box(*AD, ['Admission service', 'registers the gateways', 'and issues their', 'credentials'], fill='#ffffff', stroke=AQUA, size=12.5))
    b.append(box(*LG, ['Permissioned ledger (BFT validators)', 'verifies the proofs; records only', 'commitments, proof outcomes and', 'admission decisions; selects the', 'updates that passed'], fill=AQUA_L, stroke=AQUA, size=12.5))
    b.append(box(*AG, ['Aggregator', 'aggregates the selected updates', 'and commits to the new', 'global model'], fill=BLUE_XL, stroke=BLUE, size=12.5))
    b.append(box(740, 196, 220, 58, ['Off-chain store: updates', 'and models (commitments', 'only on-chain)'], fill='#ffffff', stroke=GREY, size=11.5, dash='4 3'))
    b.append(arrow(240, 112, 272, 112, color=AQUA))                       # admission -> ledger: admitted set
    b.append(arrow(628, 112, 660, 112, color=AQUA))                       # ledger -> aggregator: selected set
    b.append(step(644, 94, 4, AQUA))
    b.append(arrow(850, 172, 850, 196, color=INK2, dash='4 3'))           # aggregator -> off-chain store
    b.append(arrow(680, 172, 590, 202, color=BLUE, dash='5 3'))           # aggregator -> ledger: commitment to global model
    b.append(text(140, 196, ['fake nodes: kept out', 'by admission control'], 11.5, fill=RED, italic=True))
    b.append(text(450, 262, 'denial of service: discussed only', 11, fill=RED, italic=True))
    b.append(step(292, 190, 2, AQUA))
    b.append(text(292 + 16, 190, 'open the committed reference', 11, anchor='start', fill=INK2))
    # gateway tier
    G1, G2 = (170, 326, 300, 110), (530, 326, 300, 110)
    for g in (G1, G2):
        b.append(box(*g, ['IoT gateway (FL client)', 'trains for the devices behind it;', 'commits to its update; proves a', 'norm bound or cosine similarity'], fill=BLUE_XL, stroke=BLUE, size=12.5))
    b.append(arrow(300, 326, 380, 202, color=ORANGE, dash='5 3'))         # G1 -> ledger: commitment, proof
    b.append(arrow(600, 326, 520, 202, color=ORANGE, dash='5 3'))         # G2 -> ledger
    b.append(step(318, 298, 1))
    b.append(step(362, 230, 3))
    b.append(arrow(710, 326, 710, 172, color=BLUE, sw=1.6))               # G2 -> aggregator: selected update
    b.append(step(710, 250, 5, BLUE))
    b.append(text(905, 360, ['poisoning,', 'colluding gateways,', 'free riders', '(measured)'], 11.5, fill=RED, italic=True))
    # device tier
    b.append(box(170, 512, 660, 58, ['IoT devices (sensors, controllers): raw data go only to their gateway, over a local link'], fill='#ffffff', stroke=GREY, size=12.5))
    b.append(arrow(320, 512, 320, 436, color=INK2))
    b.append(arrow(680, 512, 680, 436, color=INK2))
    # legend
    b.append(f'<line x1="40" y1="612" x2="76" y2="612" stroke="{ORANGE}" stroke-width="1.4" stroke-dasharray="5 3"/>')
    b.append(text(84, 612, 'commitments and proofs', 12, anchor='start', fill=INK2))
    b.append(f'<line x1="290" y1="612" x2="326" y2="612" stroke="{BLUE}" stroke-width="1.6"/>')
    b.append(text(334, 612, 'model updates and models', 12, anchor='start', fill=INK2))
    b.append(f'<line x1="540" y1="612" x2="576" y2="612" stroke="{AQUA}" stroke-width="1.4"/>')
    b.append(text(584, 612, 'admitted and selected sets', 12, anchor='start', fill=INK2))
    b.append(text(800, 612, 'red: threats', 12, anchor='start', fill=RED, italic=True))
    return render('fig-agenda', W, H, ''.join(b))


# The five layers and their survey questions, worded exactly as in Table IV (tables_v18.t_questions18).
LAYERS = [('SQ1', 'The NG-IoT fabric', 'IV-A', 'V-C'), ('SQ2', 'The privacy plane', 'IV-B', 'V-D'),
          ('SQ3', 'The trust plane', 'IV-C', 'V-E'), ('SQ4', 'Attacks, defences and evaluation', 'IV-D', 'V-F'),
          ('SQ5', 'The regulatory layer', 'IV-E', 'V-G')]


def roadmap(appr_n=29):
    """A visual table of contents of V26: the related surveys give the five survey questions, one per layer; each is
    answered by the fundamentals of its layer (Section IV) and, after the approaches are described one by one (V-A,
    V-B), by the comparison on that layer (V-C to V-G), which closes with the answer; Sections VI to VIII draw on all
    five. Modelled on Martinez Beltran et al. (2023), Fig. 3. Labels follow the headings of the paper."""
    W = 1240
    b = []
    QN, QW, GAP = 5, 226, 12
    x0 = (W - (QN * QW + (QN - 1) * GAP)) / 2
    BW = QN * QW + (QN - 1) * GAP
    cx = [x0 + k * (QW + GAP) + QW / 2 for k in range(QN)]
    TX, TW = 400, 440
    b.append(box(TX, 12, TW, 54, [], fill=BLUE_L, stroke=BLUE))
    b.append(text(TX + TW / 2, 30, ['Privacy-preserving and verifiable FL on blockchains for NG-IoT'], size=12.5, weight='bold'))
    b.append(text(TX + TW / 2, 51, ['Five layers, one survey question each'], size=11.5, italic=True, fill=INK2))
    b.append(arrow(W / 2, 66, W / 2, 82, color=INK2, sw=1.2))
    # Section II: the surveys give the questions
    b.append(box(x0, 82, BW, 40, [], fill=GREY_L, stroke=GREY))
    b.append(text(W / 2, 98, ['II  Related surveys: the 19 closest surveys one by one and Table II  →  the survey questions (II-D)'],
                  size=11.2, weight='bold', fill=INK))
    b.append(text(W / 2, 114, ['III  Survey method'], size=10, fill=INK2))
    names = {'SQ4': ['Attacks, defences', 'and evaluation']}
    asks = {'SQ1': ['Tiers, devices, links and', 'constraints; where mechanisms run'],
            'SQ2': ['Which mechanisms protect what,', 'from whom, at what device cost'],
            'SQ3': ['What ledgers record, verify and', 'enforce; checking unread updates'],
            'SQ4': ["Attacks, defences, the ledger's", 'role; evaluation and comparison'],
            'SQ5': ['What the GDPR and EDPB require;', 'how the approaches meet it']}
    fund = {'SQ1': ['IV-A1  Tiers and links', 'IV-A2  Participants, topologies', 'IV-A3  Device constraints',
                    'IV-A4  From the fabric to learning', 'IV-F  Where the layers attach'],
            'SQ2': ['IV-B1  Mechanisms, what each protects', 'IV-B2  Mechanisms at the edge', 'IV-B3  Cost on the device',
                    'IV-B4  Comparison of mechanisms'],
            'SQ3': ['IV-C1  Records, verifies, enforces', 'IV-C2  Verifying unread updates', 'IV-C3  Cost of the proofs',
                    'IV-C4  Attestation', 'IV-C5  Frameworks, platforms', 'IV-C6  Cost of the ledger'],
            'SQ4': ['IV-D1  Adversaries, taxonomy', 'IV-D2  Attacks on integrity', 'IV-D3  Attacks on privacy',
                    'IV-D4  Attacks on availability', "IV-D5  Defences, the ledger's role"],
            'SQ5': ['IV-E1  GDPR and EDPB guidelines', 'IV-E2  On- vs off-chain data', 'IV-E3  Erasure',
                    'IV-E4  Zero-knowledge verification']}
    comp = {'SQ1': 'V-C  On the NG-IoT fabric', 'SQ2': 'V-D  On the privacy plane', 'SQ3': 'V-E  On the trust plane',
            'SQ4': 'V-F  Attacks, defences, evaluation', 'SQ5': 'V-G  On the regulatory layer'}
    QY, QH = 146, 92
    b.append(f'<path d="M {W / 2} 122 L {W / 2} 132 M {cx[0]} 132 L {cx[-1]} 132" fill="none" stroke="{INK2}" stroke-width="1.3"/>')
    sub_h, sub_gap = 24, 5
    ys = []
    for k, (sq, name, sec_iv, sec_v) in enumerate(LAYERS):
        x = cx[k] - QW / 2
        b.append(arrow(cx[k], 132, cx[k], QY, color=INK2, sw=1.2))
        b.append(box(x, QY, QW, QH, [], fill=BLUE_XL, stroke=BLUE))
        b.append(text(cx[k], QY + 14, [sq], size=12.5, weight='bold', fill=BLUE))
        nm = names.get(sq, [name])
        b.append(text(cx[k], QY + (34 if len(nm) == 1 else 38), nm, size=12, weight='bold', lh=1.15))
        b.append(text(cx[k], QY + 72, asks[sq], size=10, fill=INK2, lh=1.15))
        y = QY + QH + 10
        b.append(text(cx[k], y + 8, ['Fundamentals (Section IV)'], size=9.6, italic=True, fill=INK2))
        y += 16
        for stext in fund[sq]:
            b.append(box(x + 8, y, QW - 16, sub_h, [stext], fill='#ffffff', stroke=GREY, size=9.2, rx=4))
            y += sub_h + sub_gap
        ys.append(y)
    # the approaches, described across the layers
    band_y = max(ys) + 8
    for k in range(QN):
        b.append(f'<path d="M {cx[k]} {ys[k] - sub_gap} L {cx[k]} {band_y}" fill="none" stroke="{GREY}" stroke-width="1"/>')
    b.append(box(x0, band_y, BW, 40, [], fill=AQUA_L, stroke=AQUA))
    b.append(text(W / 2, band_y + 15, ['State of the art (Section V)'], size=11.2, weight='bold', fill=INK))
    b.append(text(W / 2, band_y + 31, [f'V-A  How the field built on itself      ·      V-B  The {appr_n} approaches one by one, '
                                       'grouped by whom their check relies on'], size=10.2, fill=INK2))
    y2 = band_y + 40 + 12
    bottoms = []
    for k, (sq, name, sec_iv, sec_v) in enumerate(LAYERS):
        x = cx[k] - QW / 2
        b.append(arrow(cx[k], band_y + 40, cx[k], y2, color=GREY, sw=1))
        b.append(box(x + 8, y2, QW - 16, sub_h, [comp[sq]], fill='#ffffff', stroke=AQUA, size=9.2, rx=4))
        ya = y2 + sub_h + sub_gap
        b.append(box(x + 8, ya, QW - 16, sub_h + 2, [f'Answer to {sq}'], fill=BLUE_L, stroke=BLUE, size=9.6,
                     weight='bold', rx=4))
        bottoms.append(ya + sub_h + 2)
    cy = max(bottoms) + 12
    b.append(f'<path d="M {cx[0]} {cy} L {cx[-1]} {cy}" fill="none" stroke="{INK2}" stroke-width="1.2"/>')
    for k in range(QN):
        b.append(f'<path d="M {cx[k]} {bottoms[k]} L {cx[k]} {cy}" fill="none" stroke="{GREY}" stroke-width="1"/>')
    b.append(arrow(W / 2, cy, W / 2, cy + 14, color=INK2, sw=1.3))
    by = cy + 14
    b.append(box(x0, by, BW, 58, [], fill=ORANGE_L, stroke=ORANGE))
    b.append(text(W / 2, by + 17, ['Sections VI to VIII draw on the answers to all five questions'], size=11.5, weight='bold', fill=INK))
    b.append(text(W / 2, by + 39, ['VI  Trends, lessons and open areas G1–G5, each traced to its questions   →   '
                                   'VII  One research gap, the closest works and the position   →   '
                                   'VIII  Research agenda'], size=10.3, fill=INK2))
    return render('fig-roadmap', W, int(by + 58 + 14), ''.join(b))


def taxonomy18(d):
    """The taxonomy with one branch for each of the five layers (SQ1-SQ5), and the number of primary studies under each
    leaf that was classified for all of them. Same classification and counts as the V16 taxonomy; only the grouping
    follows the survey questions: learning topologies sit with the fabric (Section IV-A2), verification with the trust
    plane (Section IV-C2), threats by class with SQ4 (Section IV-D1)."""
    T = F.T
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
        ('SQ1 · Sections IV-A, V-C', 'The NG-IoT fabric', BLUE, BLUE_XL, [
            'Tiers: device; edge (gateways, base stations, MEC); cloud',
            'Links: BLE, Zigbee, Wi-Fi, LoRaWAN and LPWAN, 5G / 6G',
            'Who trains: device, gateway, edge server, organisation',
            f"Learning: server-based FL ({lrn('FL')}), hierarchical FL ({lrn('hierarchical_FL')}),",
            f"  decentralised FL ({lrn('DFL')}), swarm ({lrn('swarm')}), split learning ({lrn('split')})"]),
        ('SQ2 · Sections IV-B, V-D', 'The privacy plane', VIOLET, VIOLET_L, [
            f"DP and local DP ({mech('DP', 'LDP')}); HE ({mech('HE', 'FHE')})",
            f"SMPC and secret sharing ({mech('SMPC', 'secret_sharing')}); secure aggregation ({mech('secure_aggregation')})",
            f"Trusted execution ({mech('TEE')}); none beyond local data ({mech('none')})"]),
        ('SQ3 · Sections IV-C, V-E', 'The trust plane', AQUA, AQUA_L, [
            f"Ledger ({len(led)}): public ({ltype('public')}), consortium ({ltype('consortium')}), permissioned ({ltype('permissioned')})",
            'Roles: aggregate, record, verify, enforce',
            f"On-chain: updates ({oc['U']}), encrypted updates ({oc['E']}), models ({oc['G']}),",
            f"  commitments or proofs only ({oc['C']})",
            'Checks: what (data binding, training, admissibility, freshness,',
            '  admitted set, aggregation, non-equivocation); who can verify',
            f"How: inspection, computation on hidden data, attestation, ZKP ({mech('ZKP')})"]),
        ('SQ4 · Sections IV-D, V-F', 'Attacks, defences and evaluation', RED, RED_L, [
            f"Integrity: poisoning ({th('P')}), fake nodes ({th('S')}), free riding ({th('R')}), collusion ({th('C')})",
            f"Privacy: inference by the aggregator, validators or eavesdroppers ({th('I')})",
            f"Availability: denial of service and jamming ({th('D')})",
            'Defences: consensus and replication, admission control, proofs,',
            '  robust aggregation, reputation',
            'Evaluation: data, devices, networks, repeated runs, metrics']),
        ('SQ5 · Sections IV-E, V-G', 'The regulatory layer', '#7a5a14', '#f6efe0', [
            'GDPR and EDPB Guidelines 02/2025',
            'On-chain versus off-chain data; erasure and unlearning',
            'Zero-knowledge verification as a design requirement']),
    ]
    W = 1040
    b = []
    rootx, rw, rh = 16, 160, 110
    bx, bw = 206, 236
    lx, lw = 466, 560
    y = 16
    blocks = []
    for _, _, _, _, leaves in branches:
        hh = max(70, 19 * len(leaves) + 22)
        blocks.append((y, hh))
        y += hh + 10
    total = y
    rooty = total / 2 - rh / 2
    b.append(box(rootx, rooty, rw, rh, ['Privacy-preserving', 'and verifiable FL', 'for NG-IoT'], fill=GREY_L, stroke=INK2, size=13.5, weight='bold'))
    for (label, name, stroke, fill, leaves), (y, hh) in zip(branches, blocks):
        cy = y + hh / 2
        b.append(f'<path d="M {rootx + rw} {rooty + rh / 2} C {rootx + rw + 26} {rooty + rh / 2}, {bx - 26} {cy}, {bx} {cy}" fill="none" stroke="{stroke}" stroke-width="1.6"/>')
        b.append(f'<rect x="{bx}" y="{cy - 27}" width="{bw}" height="54" rx="7" fill="{stroke}"/>')
        b.append(text(bx + bw / 2, cy - 10, label, 11, 'normal', fill='#ffffff'))
        b.append(text(bx + bw / 2, cy + 9, name, 13 if len(name) < 26 else 12, 'bold', fill='#ffffff'))
        b.append(f'<line x1="{bx + bw}" y1="{cy}" x2="{lx}" y2="{cy}" stroke="{stroke}" stroke-width="1.6"/>')
        b.append(f'<rect x="{lx}" y="{y}" width="{lw}" height="{hh}" rx="7" fill="{fill}" stroke="{stroke}" stroke-width="1.2"/>')
        ty = y + (hh - 19 * len(leaves)) / 2 + 9.5
        for leaf in leaves:
            indent = 14 if leaf.startswith('  ') else 0
            b.append(text(lx + 12 + indent, ty, leaf.strip(), 12.5, 'normal', 'start', INK))
            ty += 19
    return render('fig-taxonomy', W, int(total + 6), ''.join(b))


def architecture18():
    """Where the reviewed designs place their mechanisms, labelled by the five layers: the tiers form the NG-IoT fabric
    (SQ1; three tiers, the edge holding gateways and base stations with MEC, as Section IV-A describes), the panels show
    the privacy plane (SQ2), the trust plane (SQ3) and the regulatory layer (SQ5), and the band marks where the threats of
    SQ4 enter. The drawing is that of the V16 architecture; only the labels change."""
    W, H, TOP = 1000, 800, 30
    b = []
    tiers = [(18, 88, 'Cloud tier'), (116, 212, 'Edge tier: base stations and MEC servers'), (338, 118, 'Edge tier: gateways'),
             (466, 156, 'Device tier')]
    for y, hh, name in tiers:
        b.append(f'<rect x="20" y="{y}" width="720" height="{hh}" rx="8" fill="{GREY_L}" stroke="{GREY}" stroke-width="1"/>')
        b.append(text(34, y + 19, name, 13.5, 'bold', 'start', INK))
    b.append(box(405, 34, 320, 58, ['Model archive and audit copy', '(optional, off-chain)'], fill='#ffffff', stroke=GREY, size=12.5))
    GN, AG, LG, AD = (40, 150, 135, 90), (200, 150, 185, 90), (405, 150, 190, 110), (615, 150, 110, 110)
    b.append(box(*GN, ['5G gNB', 'with MEC'], fill='#ffffff', stroke=GREY, size=12.5))
    b.append(box(*AG, ['Aggregator', '(secure aggregation,', 'checks on updates)'], fill=BLUE_XL, stroke=BLUE, size=12.5))
    b.append(box(*LG, ['Ledger nodes', '(public or', 'permissioned): record', 'U, E, G or C;', 'verify proofs'], fill=AQUA_L, stroke=AQUA, size=12))
    b.append(box(*AD, ['Admission', 'service', '(identities,', 'certificates)'], fill='#ffffff', stroke=AQUA, size=12))
    b.append(arrow(175, 195, 200, 195, color=BLUE))
    b.append(arrow(385, 195, 405, 195, color=AQUA))
    b.append(arrow(595, 205, 615, 205, color=AQUA, dash='4 3'))
    b.append(arrow(500, 150, 500, 92, color=INK2, dash='4 3'))
    G1, G2 = (200, 362, 185, 76), (405, 362, 190, 76)
    for g in (G1, G2):
        b.append(box(*g, ['IoT gateway: FL client', 'for the devices behind', 'it; update and proof'], fill=BLUE_XL, stroke=BLUE, size=12))
    b.append(arrow(260, 362, 260, 240, color=BLUE, sw=1.5))
    b.append(arrow(350, 362, 440, 260, color=ORANGE, sw=1.4, dash='5 3'))
    b.append(arrow(430, 362, 360, 240, color=BLUE, sw=1.5))
    b.append(arrow(540, 362, 540, 260, color=ORANGE, sw=1.4, dash='5 3'))
    PH, S1, S2 = (40, 500, 135, 96), (200, 500, 185, 96), (405, 500, 190, 96)
    b.append(box(*PH, ['Phones and', 'vehicles: FL', 'clients over', '5G links'], fill=BLUE_XL, stroke=BLUE, size=12))
    b.append(box(*S1, ['Sensors and actuators', '(microcontrollers) on', 'BLE, Zigbee, LoRaWAN', 'or Wi-Fi links'], fill='#ffffff', stroke=GREY, size=12))
    b.append(box(*S2, ['More sensors', 'behind a second', 'gateway'], fill='#ffffff', stroke=GREY, size=12))
    b.append(arrow(157, 500, 157, 240, color=BLUE, sw=1.5))
    b.append(arrow(292, 500, 292, 438, color=GREY, sw=1.4))
    b.append(arrow(500, 500, 500, 438, color=GREY, sw=1.4))
    b.append(text(620, 520, ['solid: model updates', '(kept confidential)', 'dashed: proofs'], 11.5, 'normal', 'start', INK2, italic=True))
    b.append(text(380, 611, 'the aggregated model returns to the clients by the same routes', 11.5, 'normal', 'middle', INK2, italic=True))
    marks = [(G1[0], G1[1], '1'), (G2[0], G2[1], '1'), (PH[0], PH[1], '1'), (AD[0] + AD[2], AD[1], '2'),
             (GN[0] + GN[2], GN[1], '3'), (AG[0] + AG[2], AG[1], '3'), (LG[0] + LG[2], LG[1], '3'), (S1[0] + S1[2], S1[1], '3'),
             (S2[0] + S2[2], S2[1], '3'), (AG[0], AG[1], '4'), (LG[0], LG[1], '4'), (S1[0], S1[1], '4')]
    for x, y, n in marks:
        b.append(f'<circle cx="{x}" cy="{y}" r="10" fill="{RED}"/>')
        b.append(text(x, y, n, 11.5, 'bold', 'middle', '#ffffff'))
    px = 760
    planes = [(['Learning (Section IV-A2)', 'FL, hierarchical or', 'decentralised FL'], BLUE_XL, BLUE),
              (['Privacy plane (SQ2)', 'DP, HE, SMPC and secure', 'aggregation, TEE'], VIOLET_L, VIOLET),
              (['Trust plane (SQ3): checks', 'inspection, computation on', 'hidden data, attestation,', 'zero-knowledge proofs'], '#fff4dc', ORANGE),
              (['Trust plane (SQ3): ledger', 'aggregate, record,', 'verify, enforce'], AQUA_L, AQUA),
              (['Regulatory layer (SQ5)', 'GDPR, EDPB Guidelines', '02/2025, erasure'], GREY_L, GREY)]
    y = 18
    for lines, fill, stroke in planes:
        hh = 20 * len(lines) + 22
        b.append(box(px, y, 220, hh, lines, fill=fill, stroke=stroke, size=12.5))
        y += hh + 12
    b.append(f'<rect x="20" y="640" width="960" height="118" rx="6" fill="{RED_L}" stroke="{RED}" stroke-width="1.1"/>')
    b.append(text(34, 662, 'Attacks, defences and evaluation (SQ4): where the threats enter', 13, 'bold', 'start', INK))
    rows = ['1  Poisoning and free riding: at the FL clients (gateways, phones, vehicles)',
            '2  Fake nodes (Sybil) and compromised registered devices: at admission',
            '3  Denial of service: jamming of radio links, energy depletion, floods of the gNB, aggregator or ledger nodes',
            '4  Inference: at the aggregator, at ledger nodes that read on-chain updates, and on poorly protected radio links']
    for k, r in enumerate(rows):
        b.append(text(44, 686 + k * 19, r, 12, 'normal', 'start', INK))
    head = (text(34, 16, 'The NG-IoT fabric (SQ1): three tiers and their links', 13.5, 'bold', 'start', BLUE) +
            text(px + 110, 16, 'Across the tiers', 13.5, 'bold', 'middle', INK))
    return render('fig-architecture', W, H, head + f'<g transform="translate(0,{TOP})">' + ''.join(b) + '</g>')


def main():
    d = T18.load()
    c = d['prisma']
    # V24 (1 Oct 2026): the search began in December 2025 and its sources were not recorded; the only screening
    # step applied to records was the period criterion (IC4), set after the full texts had been read
    first = ['Records retained from the', 'search rounds, December 2025', f"– September 2026 (n = {c['identified']})"]
    screened = ['Records screened by date of', f"publication, IC4 (n = {c['screened']})"]
    s = T18.stats(d)
    out = [roadmap(s['appr_n']), F17.prisma(c, first=first, screened=screened, left_head='Search rounds'), taxonomy18(d), architecture18(), F.overview(d), F.mechanisms(d),
           F.challenges(d), agenda()]
    for f in out:
        print(f.name)


if __name__ == '__main__':
    main()
