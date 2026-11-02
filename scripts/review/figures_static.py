#!/usr/bin/env python3
"""Diagrams of the review (V14) that do not depend on the coded data: PRISMA flow, storyline, reference
architecture, research design. Each figure is written as an SVG inside a small HTML page and rendered to PNG
by headless Google Chrome at 3x (print quality).

Usage: scripts/.venv/bin/python scripts/review/figures_static.py
"""
import json, pathlib, subprocess, html

ROOT = pathlib.Path(__file__).resolve().parents[2]
OUT = ROOT / 'myliteraturereviewpaper' / '_src' / 'V14' / 'figures'
OUT.mkdir(parents=True, exist_ok=True)
CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'

FONT = "'Helvetica Neue', Helvetica, Arial, sans-serif"
INK, INK2, MUTED = '#0b0b0b', '#52514e', '#8a8984'
BLUE, BLUE_L, BLUE_XL = '#256abf', '#cde2fb', '#eef5fd'
ORANGE, ORANGE_L = '#c4501f', '#fbe3d8'
AQUA, AQUA_L = '#12805a', '#d5f2e7'
VIOLET, VIOLET_L = '#4a3aa7', '#e6e3f7'
GREY_L, GREY = '#f0efec', '#b9b8b3'
RED, RED_L = '#b53030', '#f8dede'


def esc(t):
    return html.escape(t, quote=False)


def text(x, y, lines, size=13, weight='normal', anchor='middle', fill=INK, lh=1.25, italic=False):
    """Multi-line text centred vertically on y."""
    if isinstance(lines, str):
        lines = [lines]
    n = len(lines)
    y0 = y - (n - 1) * size * lh / 2 + size * 0.35
    style = ' font-style="italic"' if italic else ''
    out = [f'<text x="{x}" y="{y0:.1f}" font-family="{FONT}" font-size="{size}" font-weight="{weight}" '
           f'text-anchor="{anchor}" fill="{fill}"{style}>']
    for i, ln in enumerate(lines):
        dy = 0 if i == 0 else size * lh
        out.append(f'<tspan x="{x}" dy="{dy:.1f}">{esc(ln)}</tspan>')
    out.append('</text>')
    return ''.join(out)


def box(x, y, w, h, lines, fill=BLUE_XL, stroke=BLUE, size=13, weight='normal', rx=6, anchor='middle', sw=1.3,
        dash=None, tfill=INK):
    d = f' stroke-dasharray="{dash}"' if dash else ''
    tx = x + w / 2 if anchor == 'middle' else x + 12
    return (f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}" stroke="{stroke}" '
            f'stroke-width="{sw}"{d}/>' + text(tx, y + h / 2, lines, size, weight, anchor, tfill))


def arrow(x1, y1, x2, y2, color=INK2, sw=1.4, head=7, dash=None):
    import math
    ang = math.atan2(y2 - y1, x2 - x1)
    hx1 = x2 - head * math.cos(ang - 0.4)
    hy1 = y2 - head * math.sin(ang - 0.4)
    hx2 = x2 - head * math.cos(ang + 0.4)
    hy2 = y2 - head * math.sin(ang + 0.4)
    d = f' stroke-dasharray="{dash}"' if dash else ''
    return (f'<line x1="{x1}" y1="{y1}" x2="{x2 - 0.8 * head * math.cos(ang):.1f}" '
            f'y2="{y2 - 0.8 * head * math.sin(ang):.1f}" stroke="{color}" stroke-width="{sw}"{d}/>'
            f'<polygon points="{x2},{y2} {hx1:.1f},{hy1:.1f} {hx2:.1f},{hy2:.1f}" fill="{color}"/>')


def render(name, w, h, body):
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">'
           f'<rect width="{w}" height="{h}" fill="#ffffff"/>{body}</svg>')
    (OUT / f'{name}.svg').write_text(svg, encoding='utf-8')
    page = OUT / f'{name}.html'
    page.write_text('<!doctype html><html><head><meta charset="utf-8"><style>html,body{margin:0;padding:0;'
                    'background:#fff}svg{display:block}</style></head><body>' + svg + '</body></html>',
                    encoding='utf-8')
    png = OUT / f'{name}.png'
    subprocess.run([CHROME, '--headless=new', '--disable-gpu', '--hide-scrollbars', '--force-device-scale-factor=3',
                    f'--window-size={w},{h}', f'--screenshot={png}', page.as_uri()],
                   check=True, capture_output=True)
    page.unlink()
    trim(png)
    return png


def trim(png, pad=30, white=250):
    """cut the empty margins off a rendered figure (the author, 20 October 2026: "cut the empty spaces out of them"): the
    bounding box of every pixel darker than near-white, with a small pad, written back over the PNG; the SVG keeps its canvas"""
    try:
        import pymupdf
    except ImportError:
        return
    pix = pymupdf.Pixmap(str(png))
    if pix.alpha: pix = pymupdf.Pixmap(pix, 0)
    w, h, n = pix.width, pix.height, pix.n; buf = pix.samples
    rows = [y for y in range(h) if any(buf[(y * w + x) * n + c] < white for x in range(0, w, 2) for c in range(min(n, 3)))]
    cols = [x for x in range(w) if any(buf[(y * w + x) * n + c] < white for y in range(0, h, 2) for c in range(min(n, 3)))]
    if not rows or not cols: return
    x0, x1, y0, y1 = max(0, cols[0] - pad), min(w, cols[-1] + pad + 1), max(0, rows[0] - pad), min(h, rows[-1] + pad + 1)
    if (x1 - x0, y1 - y0) == (w, h): return
    box = pymupdf.IRect(x0, y0, x1, y1)
    clip = pymupdf.Pixmap(pix.colorspace, box, False); clip.copy(pix, box); clip.save(str(png))


# ------------------------------------------------------------------ PRISMA 2020 flow diagram
def prisma(c):
    W, H = 900, 760
    b = []
    # phase labels
    for y0, hh, lab in ((20, 150, 'Identification'), (190, 400, 'Screening'), (610, 130, 'Included')):
        b.append(f'<rect x="16" y="{y0}" width="34" height="{hh}" rx="5" fill="{BLUE}"/>')
        b.append(f'<text transform="translate(38,{y0 + hh / 2}) rotate(-90)" font-family="{FONT}" font-size="14" '
                 f'font-weight="bold" fill="#ffffff" text-anchor="middle">{lab}</text>')
    L, LW = 70, 400
    R, RW = 520, 360
    b.append(box(L, 30, LW, 120, [
        'Records identified in the search rounds,',
        'January–September 2026: database searches',
        'and citation searching (snowballing)',
        f"(n = {c['identified']})"], size=13.5))
    b.append(box(R, 30, RW, 120, [
        'Records removed before screening:',
        f"duplicate downloads (n = {c['dup']})",
        f"preprint copies superseded by the",
        f"published version (n = {c['superseded']})"], fill=GREY_L, stroke=GREY, size=13))
    b.append(arrow(L + LW, 90, R, 90))
    b.append(arrow(L + LW / 2, 150, L + LW / 2, 205))
    b.append(box(L, 205, LW, 70, ['Records screened (publication type,', f"title and abstract) (n = {c['screened']})"],
                 size=13.5))
    b.append(box(R, 195, RW, 90, [f"Records excluded (n = {c['excl_screen']}), EC4:",
                                  f"PhD theses (n = {c['theses']}); textbook (n = 1);",
                                  'call for papers (n = 1)'], fill=GREY_L, stroke=GREY, size=13))
    b.append(arrow(L + LW, 240, R, 240))
    b.append(arrow(L + LW / 2, 275, L + LW / 2, 320))
    b.append(box(L, 320, LW, 60, [f"Reports sought for retrieval (n = {c['sought']})"], size=13.5))
    b.append(box(R, 320, RW, 60, ['Reports not retrieved (n = 0)'], fill=GREY_L, stroke=GREY, size=13))
    b.append(arrow(L + LW, 350, R, 350))
    b.append(arrow(L + LW / 2, 380, L + LW / 2, 425))
    b.append(box(L, 425, LW, 80, ['Reports assessed for eligibility:', 'full text read and noted',
                                  f"(n = {c['assessed']})"], size=13.5))
    b.append(box(R, 405, RW, 150, [f"Reports excluded (n = {c['excl_full']}):",
                                   'retracted by the publisher (n = 1), EC2',
                                   'out of topic (n = 2), EC1',
                                   'unpublished: no venue and no',
                                   'preprint server (n = 1), EC5'], fill=GREY_L, stroke=GREY, size=13))
    b.append(arrow(L + LW, 465, R, 465))
    b.append(arrow(L + LW / 2, 505, L + LW / 2, 625))
    b.append(box(L, 625, LW, 100, [f"Studies included in the review (n = {c['included']})",
                                   f"primary studies (n = {c['primary']})",
                                   f"secondary studies (n = {c['secondary']})"], fill=BLUE_L, stroke=BLUE,
                 size=14, weight='normal'))
    b.append(text(R + RW / 2, 675, ['EC = exclusion criterion (Table 5)'], size=12, fill=INK2, italic=True))
    return render('fig-prisma', W, H, ''.join(b))


# ------------------------------------------------------------------ storyline: survey questions to sections
def storyline():
    W, H = 960, 430
    b = []
    b.append(box(20, 20, 920, 58, ['Section 3 — Review methodology: questions, keywords and search strings, inclusion and exclusion criteria,',
                                   'PRISMA selection, quality appraisal, data extraction and thematic synthesis'],
                 fill=GREY_L, stroke=GREY, size=13))
    cols = [
        ('SQ1', 'Fundamentals', ['What are the building blocks —', 'fabric, learning paradigms,', 'privacy mechanisms, ledger,', 'threats — and how can', 'they be classified?'], 'Section 5', 'Fundamentals and taxonomy'),
        ('SQ2', 'State of the art', ['How do existing studies', 'combine privacy mechanisms', 'and blockchain with', 'distributed learning, and which', 'threats do they address?'], 'Section 6', 'State of the art'),
        ('SQ3', 'Frameworks, evaluation', ['Which frameworks, platforms,', 'datasets and metrics are used,', 'and what do the solutions', 'cost IoT and edge', 'devices?'], 'Section 7', 'Frameworks, datasets, evaluation'),
        ('SQ4', 'Trends and challenges', ['What trends, lessons and', 'open challenges emerge,', 'including those raised by', 'data-protection', 'regulation?'], 'Section 8', 'Trends, lessons, challenges'),
    ]
    x = 20
    cw, gap = 220, 13.3
    for i, (sq, name, q, sec, secname) in enumerate(cols):
        b.append(arrow(x + cw / 2, 78, x + cw / 2, 102))
        b.append(f'<rect x="{x}" y="102" width="{cw}" height="176" rx="6" fill="{BLUE_XL}" stroke="{BLUE}" stroke-width="1.3"/>')
        b.append(f'<rect x="{x}" y="102" width="{cw}" height="34" rx="6" fill="{BLUE}"/>')
        b.append(f'<rect x="{x}" y="124" width="{cw}" height="12" fill="{BLUE}"/>')
        b.append(text(x + cw / 2, 119, f'{sq} — {name}', 13, 'bold', fill='#ffffff'))
        b.append(text(x + cw / 2, 207, q, 12.5))
        b.append(arrow(x + cw / 2, 278, x + cw / 2, 302))
        b.append(box(x, 302, cw, 50, [sec, secname], fill='#ffffff', stroke=BLUE, size=12.5))
        x += cw + gap
    b.append(arrow(480, 352, 480, 372))
    b.append(box(20, 372, 920, 46, ['Section 9 — From the gaps to the proposed research: research question, hypotheses, research design and planned experiment'],
                 fill=ORANGE_L, stroke=ORANGE, size=13.5))
    return render('fig-storyline', W, H, ''.join(b))


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
    # cloud archive above the ledger
    b.append(box(500, 45, 200, 60, ['Global model and', 'audit copy (off-chain)'], fill='#ffffff', stroke=GREY, size=12.5))
    # edge row: gNB -> aggregator -> ledger
    b.append(box(60, 215, 180, 100, ['5G gNB / core', '(radio links to', 'the devices)'], fill='#ffffff', stroke=GREY, size=12.5))
    b.append(box(270, 215, 200, 100, ['Edge aggregator', '(secure aggregation,', 'robust checks)'], fill=BLUE_XL, stroke=BLUE, size=12.5))
    b.append(box(500, 215, 200, 100, ['Permissioned ledger', '(identities, update', 'commitments, reputation,', 'incentives)'], fill=AQUA_L, stroke=AQUA, size=12))
    b.append(arrow(240, 265, 270, 265, color=BLUE))
    b.append(arrow(470, 265, 500, 265, color=AQUA))
    b.append(arrow(600, 215, 600, 105, color=INK2, dash='4 3'))
    # device tier: bus and devices
    xs = [60, 190, 320, 450, 580]
    bus_y = 430
    b.append(f'<line x1="115" y1="{bus_y}" x2="635" y2="{bus_y}" stroke="{BLUE}" stroke-width="1.6"/>')
    b.append(text(420, bus_y - 12, 'wireless / 5G links', 12, 'normal', 'middle', BLUE, italic=True))
    for i, x in enumerate(xs):
        lab = ['IoT device', f'client {i + 1}'] if i < 4 else ['IoT device', 'client n']
        b.append(box(x, 470, 110, 55, lab, fill='#ffffff', stroke=BLUE, size=12))
        b.append(f'<line x1="{x + 55}" y1="470" x2="{x + 55}" y2="{bus_y}" stroke="{BLUE}" stroke-width="1.3"/>')
    b.append(arrow(222, bus_y, 222, 315, color=BLUE, sw=1.6))
    b.append(text(370, 551, 'model updates, protected by the privacy plane, travel up; the aggregated model returns', 12, fill=INK2, italic=True))
    # planes
    px = 740
    b.append(text(px + 110, 28, 'Planes across the tiers', 13.5, 'bold'))
    planes = [(['Learning plane', 'FL, decentralised FL,', 'split or swarm learning'], BLUE_XL, BLUE),
              (['Privacy plane', 'DP / LDP, HE, SMPC and', 'secure aggregation,', 'TEE, ZKP'], VIOLET_L, VIOLET),
              (['Trust plane', 'blockchain: record, verify,', 'enforce (consensus,', 'smart contracts)'], AQUA_L, AQUA),
              (['Governance', 'GDPR, EDPB Guidelines', '02/2025: on-chain vs', 'off-chain, erasure'], GREY_L, GREY)]
    y = 45
    for lines, fill, stroke in planes:
        b.append(box(px, y, 220, 118, lines, fill=fill, stroke=stroke, size=12.5))
        y += 131
    # threats
    b.append(f'<rect x="20" y="590" width="940" height="56" rx="6" fill="{RED_L}" stroke="{RED}" stroke-width="1.1"/>')
    b.append(text(490, 618, ['Threats named in the proposal: data poisoning · malicious participants inserting fake nodes (Sybil) · free riding ·',
                             'DDoS on the learning service — together with inference attacks on the model updates'], 12.5))
    return render('fig-architecture', W, H, ''.join(b))



# ------------------------------------------------------------------ taxonomy (mind map as a tree)
def taxonomy():
    W, H = 980, 700
    b = []
    branches = [
        ('A', 'NG-IoT fabric', BLUE, BLUE_XL, ['Tiers: device, edge / fog, cloud', 'Links: 5G / B5G / 6G, Wi-Fi, BLE, Zigbee, LoRaWAN',
                                                'Domains: healthcare, IIoT, vehicles, smart grid, city, maritime']),
        ('B', 'Distributed learning', '#184f95', BLUE_XL, ['Server-based and hierarchical FL', 'Decentralised FL, swarm learning',
                                                      'Split learning, edge inference, unlearning']),
        ('C', 'Privacy mechanisms', VIOLET, VIOLET_L, ['Perturbation: DP, local DP, obfuscation', 'Cryptographic: HE / FHE, SMPC, secret sharing,',
                                                       '  secure aggregation, ZKP', 'Hardware: trusted execution (TEE)']),
        ('D', 'Trust and ledger', AQUA, AQUA_L, ['Ledger type: public, consortium, permissioned', 'Consensus: PoW, PoS, PBFT, Raft, committee',
                                                 'On-chain vs off-chain data; smart contracts', 'Incentives, reputation; redactable ledgers']),
        ('E', 'Threats and defences', RED, RED_L, ['Integrity: poisoning, backdoor, Byzantine,', '  fake nodes (Sybil), free riding',
                                                    'Availability: DoS / DDoS, jamming, dropouts', 'Confidentiality: membership inference,',
                                                    '  reconstruction, eavesdropping',
                                                    'Defences: robust aggregation, detection,', '  verification, authentication, incentives']),
        ('F', 'Evaluation and governance', ORANGE, ORANGE_L, ['Datasets, testbeds, frameworks, metrics', 'Cost on the device: compute, storage, network',
                                                              'Regulation: GDPR, EDPB 02/2025, erasure']),
    ]
    # layout
    rootx, rooty, rw, rh = 20, 300, 170, 100
    b.append(box(rootx, rooty, rw, rh, ['Privacy-preserving', 'machine learning', 'for NG-IoT security'], fill=GREY_L, stroke=INK2, size=13.5, weight='bold'))
    y = 20
    bx, bw = 240, 220
    lx, lw = 490, 470
    for code, name, stroke, fill, leaves in branches:
        hh = max(70, 20 * len(leaves) + 26)
        cy = y + hh / 2
        # connector root -> branch
        b.append(f'<path d="M {rootx + rw} {rooty + rh / 2} C {rootx + rw + 30} {rooty + rh / 2}, {bx - 30} {cy}, {bx} {cy}" fill="none" stroke="{stroke}" stroke-width="1.6"/>')
        b.append(f'<rect x="{bx}" y="{cy - 24}" width="{bw}" height="48" rx="7" fill="{stroke}"/>')
        b.append(text(bx + bw / 2, cy, f'{code}. {name}', 13.5, 'bold', fill='#ffffff'))
        b.append(f'<line x1="{bx + bw}" y1="{cy}" x2="{lx}" y2="{cy}" stroke="{stroke}" stroke-width="1.6"/>')
        b.append(f'<rect x="{lx}" y="{y}" width="{lw}" height="{hh}" rx="7" fill="{fill}" stroke="{stroke}" stroke-width="1.2"/>')
        ty = y + 13 + 20 * 0.5 + 4
        for leaf in leaves:
            indent = 14 if leaf.startswith('  ') else 0
            b.append(text(lx + 14 + indent, ty, leaf.strip(), 12.5, 'normal', 'start', INK))
            ty += 20
        y += hh + 12
    return render('fig-taxonomy', W, max(H, int(y) + 10), ''.join(b))


# ------------------------------------------------------------------ research design (design science)
def design():
    W, H = 980, 520
    b = []
    steps = [('1', 'Problem and', 'motivation', ['this systematic review;', 'gaps G1–G5']),
             ('2', 'Objectives and', 'requirements', ['requirements', 'R1–R4']),
             ('3', 'Design and', 'development', ['ZK proofs and the', "ledger's role"]),
             ('4', 'Demonstration', '', ['prototype on real', 'devices']),
             ('5', 'Evaluation', '', ['cost (RQ1), protection', '(RQ2); H1–H3']),
             ('6', 'Communication', '', ['review V15, papers,', 'thesis, code'])]
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
    # iteration loop
    b.append(f'<path d="M {20 + 4 * (w + g) + w / 2} 190 C {20 + 4 * (w + g) + w / 2} 235, {20 + 2 * (w + g) + w / 2} 235, {20 + 2 * (w + g) + w / 2} 196" '
             f'fill="none" stroke="{ORANGE}" stroke-width="1.4" stroke-dasharray="5 3"/>')
    b.append(f'<polygon points="{20 + 2 * (w + g) + w / 2},{190} {20 + 2 * (w + g) + w / 2 - 5},{200} {20 + 2 * (w + g) + w / 2 + 5},{200}" fill="{ORANGE}"/>')
    b.append(text(20 + 3 * (w + g) + w / 2, 245, 'iterate: refine the design from the evaluation', 12, fill=ORANGE, italic=True))
    # evaluation detail
    b.append(f'<rect x="20" y="275" width="940" height="225" rx="8" fill="#ffffff" stroke="{GREY}" stroke-width="1.1"/>')
    b.append(text(40, 297, 'Experiments in step 5, starting from Veri-CS-FL (Wang et al., 2026) and kept small', 13.5, 'bold', 'start'))
    rows = [('Compared', 'federated averaging without checks · federated averaging with the zero-knowledge proof check'),
            ('Threats', 'data poisoning and fake participants (free riding measured only) · model size and number of clients varied'),
            ('Data', 'MNIST and FEMNIST as in Veri-CS-FL, then an IoT intrusion-detection dataset'),
            ('Measures', 'accuracy · effect of poisoning · proof time, memory and size on the device · verification time on the ledger'),
            ('Devices', 'a Raspberry Pi-class device and a laptop; an emulated IoT and 5G network later in the PhD'),
            ('Statistics', 'ten runs per proof measurement, five seeds per learning run; mean ± standard deviation and 95% confidence interval')]
    y = 327
    for k, v in rows:
        if k:
            b.append(text(40, y, k, 12.5, 'bold', 'start', BLUE))
        b.append(text(140, y, v, 12.5, 'normal', 'start', INK))
        y += 29
    return render('fig-design', W, H, ''.join(b))


if __name__ == '__main__':
    counts = json.loads((ROOT / 'myliteraturereviewpaper' / '_src' / 'V14' / 'prisma.json').read_text())
    for f in (prisma(counts), storyline(), architecture(), design(), taxonomy()):
        print(f.name)
