#!/usr/bin/env python3
"""Figures of the PPML review (paper V29 onwards): PRISMA 2020 flow, how the review is organised, the included studies
per year, the taxonomy with its counts, where the layers attach on the NG-IoT tiers, and the reference design of the
research agenda. Every number comes from build/stats.json (scripts/paper_ppml/data.py); nothing is typed by hand.
Drawn with the SVG primitives of scripts/review/figures_static.py and rendered to PNG by headless Chrome.
Called by data.py.
"""
import json, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
B = ROOT / 'myliteraturereviewpaper' / 'ppml2026' / 'build'
sys.path.insert(0, str(ROOT / 'scripts' / 'review'))
import figures_static as F                       # noqa: E402
F.OUT = B / 'figures'
# Colours after Ferrag et al. 2023 (S010; style guide ppml2026/FERRAG-STYLE-GUIDE.md, section C): pastel fills with a
# darker border of the same hue, one fixed colour pair per layer, a slate anchor, gold banners for the paper's own
# structure. Set here for this paper only (figures_static is shared with other papers).
F.BLUE, F.BLUE_L, F.BLUE_XL = '#6C8EBF', '#DAE8FC', '#EEF4FC'          # SQ1 fabric
F.VIOLET, F.VIOLET_L = '#9673A6', '#E1D5E7'                           # SQ2 privacy
F.AQUA, F.AQUA_L = '#82B366', '#D5E8D4'                               # SQ3 trust
F.RED, F.RED_L = '#B85450', '#F8CECC'                                 # SQ4 attacks
F.ORANGE, F.ORANGE_L = '#D79B00', '#FFE6CC'
F.GREY, F.GREY_L = '#999999', '#F5F5F5'
BROWN, BROWN_L = '#B89B3A', '#FFF2CC'                                 # SQ5 regulation
SOLID = ['#4C78C8', '#8A63D2', '#2FA37A', '#E0574F', '#D9A441']        # the five layers at full strength (charts)
SLATE, NAVY = '#637687', '#22445D'
GOLD, GOLD_EDGE, PANEL, PANEL_EDGE = '#FFE599', '#A59565', '#E3E3E3', '#BDBDBD'
_box = F.box


def _palette_box(x, y, w, h, lines, fill=None, stroke=None, size=13, weight='normal', rx=6, anchor='middle', sw=1.3,
                 dash=None, tfill=F.INK):
    """F.box with this paper's palette as its default colours (F.box binds the shared module's colours as defaults)"""
    return _box(x, y, w, h, lines, fill=fill or F.BLUE_XL, stroke=stroke or F.BLUE, size=size, weight=weight, rx=rx,
                anchor=anchor, sw=sw, dash=dash, tfill=tfill)


F.box = _palette_box
LAYERS = [('SQ1', 'NG-IoT fabric', F.BLUE, F.BLUE_L), ('SQ2', 'Privacy plane', F.VIOLET, F.VIOLET_L),
          ('SQ3', 'Trust plane', F.AQUA, F.AQUA_L), ('SQ4', 'Attacks and defences', F.RED, F.RED_L),
          ('SQ5', 'Regulatory layer', BROWN, BROWN_L)]
f = lambda n: f'{n:,}'


def record(name, **data):
    """the numbers a chart draws, kept beside it for the editable PowerPoint copy (figures_pptx.py)"""
    (F.OUT / f'{name}.data.json').write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding='utf-8')


def prisma(s):
    """PRISMA 2020 flow, one column (V76): the main and supplementary searches combined, the stages and totals only; the
    method text gives the searches apart, the author's and the tool's screening, and every breakdown. The totals are
    computed from the same numbers as the text and checked against each other here."""
    W, H = 1080, 640
    b = []
    # the totals, from the numbers the text quotes
    identified = s['id_total'] + s['rs1_records']
    removed = {'duplicates': s['dup'], 'by automated rules': s['auto_ieee'], 'not a paper': s['auto_notpaper'],
               'already screened': s['rs1_already_screened']}
    screened = s['id_total'] - s['dup'] - s['auto_ieee'] - s['auto_notpaper'] + s['rs1_tool_screened']
    sought = s['ft_sought'] + s['rs1_sought']
    not_retrieved = s['ft_not_retrieved'] + s['rs1_not_retrieved']
    assessed = s['ft_search_assessed'] + s['rs1_assessed'] + s['om_assessed']
    excluded_elig = s['ft_excluded'] + s['rs1_excluded'] + s['om_excluded']
    why = {'off_focus': 'none of the subjects in substance', 'no_blockchain': 'no blockchain in the design', 'privacy_incidental': 'privacy incidental',
           'no_learning': 'learning or setting incidental', 'not_final_version': 'no final version', 'not_a_study': 'not a study'}     # plain words, as the criteria table (V79)
    reasons = {}
    for k, v in s.items():
        for pre in ('rs_ex_', 'rs1_ex_', 'om_ex_'):
            if k.startswith(pre) and k[len(pre):] in why:
                reasons[k[len(pre):]] = reasons.get(k[len(pre):], 0) + v
    assert identified - sum(removed.values()) == screened, (identified, removed, screened)
    assert sought - not_retrieved + s['om_assessed'] == assessed, (sought, not_retrieved, assessed)
    assert sum(reasons.values()) == excluded_elig and assessed - excluded_elig == s['included'], (reasons, excluded_elig, assessed, s['included'])
    excluded_screen = screened - sought
    # layout: stage labels on the left, the flow in one column, the exclusions beside it
    for y0, hh, lab in ((20, 120, 'Identification'), (170, 330, 'Screening'), (530, 90, 'Included')):
        b.append(f'<rect x="12" y="{y0}" width="34" height="{hh}" rx="5" fill="{GOLD}" stroke="{GOLD_EDGE}" stroke-width="1"/>')
        b.append(f'<text transform="translate(34,{y0 + hh / 2}) rotate(-90)" font-family="{F.FONT}" font-size="15" '
                 f'font-weight="bold" fill="{F.INK}" text-anchor="middle">{lab}</text>')
    L, LW, R, RW = 70, 440, 580, 470
    red = dict(fill=F.RED_L, stroke=F.RED)
    b.append(F.box(L, 30, LW, 100, [f"Records identified from databases (n = {f(identified)}):", f"main searches (n = {f(s['id_total'])});",
                                    f"supplementary search (n = {f(s['rs1_records'])})"], size=15))
    b.append(F.box(R, 30, RW, 100, [f"Records removed before screening (n = {f(sum(removed.values()))}):", f"duplicates (n = {f(removed['duplicates'])});",
                                    f"by automated rules (n = {f(removed['by automated rules'])}); not a paper (n = {removed['not a paper']});",
                                    f"already screened with the main searches (n = {removed['already screened']})"], **red, size=13.5))
    b.append(F.arrow(L + LW, 80, R, 80))
    b.append(F.arrow(L + LW / 2, 130, L + LW / 2, 180))
    b.append(F.box(L, 180, LW, 60, [f"Records screened (n = {f(screened)})"], size=15))
    b.append(F.box(R, 180, RW, 60, [f"Records excluded (n = {f(excluded_screen)})"], **red, size=13.5))
    b.append(F.arrow(L + LW, 210, R, 210))
    b.append(F.arrow(L + LW / 2, 240, L + LW / 2, 290))
    b.append(F.box(L, 290, LW, 60, [f"Reports sought for retrieval (n = {sought})"], size=15))
    b.append(F.box(R, 290, RW, 60, [f"Reports not retrieved (n = {not_retrieved})"], **red, size=13.5))
    b.append(F.arrow(L + LW, 320, R, 320))
    b.append(F.arrow(L + LW / 2, 350, L + LW / 2, 400))
    b.append(F.box(L, 400, LW, 80, [f"Reports assessed for eligibility (n = {assessed}):", f"from the searches (n = {sought - not_retrieved});",
                                    f"identified via other methods (n = {s['om_assessed']})"], size=15))
    order = sorted(reasons, key=lambda k: -reasons[k])
    b.append(F.box(R, 385, RW, 110, [f"Reports excluded (n = {excluded_elig}):"] + [f"{why[k]} ({reasons[k]})" for k in order], **red, size=12.5))
    b.append(F.arrow(L + LW, 440, R, 440))
    b.append(F.arrow(L + LW / 2, 480, L + LW / 2, 540))
    b.append(F.box(L, 540, LW, 70, [f"Studies included in the review (n = {s['included']}):", f"{s['primary']} designs and {s['secondary']} surveys"],
                   fill=F.BLUE_L, stroke=F.BLUE, size=15))
    return F.render('prisma', W, H, ''.join(b))


def taxonomy(s):
    """a taxonomy of the primary studies by the design choices behind the five survey questions, each choice with the number
    of designs that make it (a design counts once per question; the counts come from build/stats.json)"""
    g = lambda k: s.get(k, 0)
    P = g('primary')
    rows = [
        ('SQ1', F.BLUE, F.BLUE_XL, 'Where is a cost reported as measured?',
         [('on device-class hardware (C1)', g('device_measured')), ('over a network link only', g('net_only')), ('neither', P - g('device_measured') - g('net_only'))]),
        ('SQ2', F.VIOLET, F.VIOLET_L, 'Who sees an individual update?',
         [('no party that checks or aggregates (C2)', g('gap_c2')), ('a checking party, or unclear', g('hk_hidden') - g('gap_c2')),
          ('the aggregator, noised', g('hk_noised')), ('the aggregator', g('hk_seen'))]),
        ('SQ3', F.AQUA, F.AQUA_L, 'What is checked?',
         [('the content of updates or their training', g('cc_content')), ('the aggregation only', g('cc_aggregation')),
          ('identities, format or contributions', g('cc_participants')), ('an inference or other records', g('cc_other')), ('nothing', g('cc_none'))]),
        ('SQ3', F.AQUA, F.AQUA_L, 'Does the content checker see the update?',
         [('in full', g('cc_content_yes')), ('in part or noised', g('cc_content_partly')), ('not at all', g('cc_content_no')), ('unclear', g('cc_content_unclear'))]),
        ('SQ3', F.AQUA, F.AQUA_L, 'What do the zero-knowledge proofs prove?',
         [('a bound or training, as stated', g('zk_stated_update')), ('another statement', g('zk_used') - g('zk_stated_update')), ('no proof', P - g('zk_used'))]),
        ('SQ3', F.AQUA, F.AQUA_L, 'What does the ledger check?',
         [('the updates (C3)', g('ledger_checks_updates')), ('the aggregation', g('ledger_checks_aggregation')),
          ('other proofs or checks only', g('ledger_other_proofs') + g('ledger_other_checks')),
          ('nothing: records, aggregates or admits', g('ledger_records_only'))]),
        ('SQ4', F.RED, F.RED_L, 'Which attack tests are reported?',
         [('on the learning (C4)', g('yt_attack')), ('a privacy attack only', g('test_privacy_only')), ('another test only', g('test_other_only')),
          ('none', P - g('yt_attack') - g('test_privacy_only') - g('test_other_only'))]),
        ('SQ5', BROWN, BROWN_L, 'What does the ledger hold?',
         [('no personal records (C5)', g('gap_c5_nopd')), ('personal records it can erase (C5)', g('gap_c5_erase')),
          ('personal records, no erasure reported', P - g('gap_c5_nopd') - g('gap_c5_erase'))]),
    ]
    W, b = 1620, []
    rootx, rw, qx, qw, lx = 14, 170, 214, 420, 660
    y, placed = 16, []
    for sq, st, fi, q, leaves in rows:                     # leaves flow left to right, wrapping at the right edge
        x, yy, line = lx, y, []
        for lab, n in leaves:
            w = 22 + 8.2 * len(lab) + 36
            if x + w > W - 14 and line:
                x, yy = lx, yy + 46
            line.append((x, yy, w, lab, n))
            x += w + 10
        hh = yy - y + 38
        placed.append((sq, st, fi, q, line, y, hh))
        y += hh + 14
    total = y
    rooty = total / 2 - 60
    b.append(F.box(rootx, rooty, rw, 120, [f"{g('primary')} primary", 'studies, all', 'built on a', 'ledger'], fill=F.GREY_L, stroke=F.INK2, size=15, weight='bold'))
    for sq, st, fi, q, line, y, hh in placed:
        cy = y + hh / 2
        b.append(f'<path d="M{rootx + rw},{rooty + 60} C{rootx + rw + 16},{rooty + 60} {qx - 16},{cy} {qx},{cy}" fill="none" stroke="{F.GREY}" stroke-width="1.3"/>')
        b.append(F.box(qx, cy - 19, qw, 38, [f'{sq} · {q}'], fill=fi, stroke=st, size=13.5, weight='bold'))
        b.append(f'<line x1="{qx + qw}" y1="{cy}" x2="{lx - 6}" y2="{cy}" stroke="{F.GREY}" stroke-width="1.1"/>')
        for x, yy, w, lab, n in line:
            b.append(f'<rect x="{x}" y="{yy}" width="{w:.0f}" height="38" rx="6" fill="#ffffff" stroke="{st}" stroke-width="1.2"/>')
            b.append(F.text(x + 12, yy + 19, lab, 13.5, 'normal', 'start'))
            b.append(F.text(x + w - 14, yy + 19, str(n), 14, 'bold', 'end'))
    record('taxonomy', kind='tree', rows=[[sq, q, [[lab, n] for _, _, _, lab, n in line]] for sq, _, _, q, line, _, _ in placed])
    return F.render('taxonomy', W, int(total + 2), ''.join(b))


def architecture(s):
    """where learning, hiding, checking and the ledger sit on the tiers of an NG-IoT deployment, and where the threats enter
    (a schematic: the counts are in Section VI)"""
    W, H, b = 1240, 600, []
    tiers = [('Devices and sensors', 450, '#F7F7F7', '#BDBDBD'), ('Edge: gateways, roadside units, MEC servers', 300, '#EFEFEF', '#BDBDBD'),
             ('Ledger nodes', 165, '#F7F7F7', '#BDBDBD'), ('Cloud or task requester', 40, '#EFEFEF', '#BDBDBD')]   # tiers neutral: colour means a layer
    for name, y, fi, st in tiers:
        b.append(f'<rect x="20" y="{y}" width="860" height="110" rx="8" fill="{fi}" stroke="{st}" stroke-width="1.4"/>')
        b.append(F.text(866, y + 18, name, 15, 'bold', 'end', F.INK2))
    b.append(F.box(50, 490, 250, 56, ['Local training on data that', 'often concern persons'], fill='#fff', stroke=F.BLUE, size=13.5))
    b.append(F.box(320, 490, 270, 56, ['Hide the update (HE, sharing,', 'masking, TEE) or add noise (DP)'], fill='#fff', stroke=F.VIOLET, size=13.5))
    b.append(F.box(610, 490, 250, 56, ['Cost on constrained devices', 'and wireless links'], fill='#fff', stroke=F.BLUE, size=13.5))
    b.append(F.box(50, 340, 390, 56, ['Aggregate and check the updates:', 'does the party that checks see them?'], fill='#fff', stroke=F.AQUA, size=13.5))
    b.append(F.box(460, 340, 400, 56, ['Ways to check: tests on data, similarity,', 'norm bounds; committees, TEEs, ZKPs'], fill='#fff', stroke=F.AQUA, size=13.5))
    b.append(F.box(50, 205, 390, 56, ['Record and verify: commitments, proofs,', 'outcomes, models; smart contracts'], fill='#fff', stroke=F.AQUA, size=13.5))
    b.append(F.box(460, 205, 400, 56, ['What the ledger holds: personal data?', 'Can it be erased? (GDPR, EDPB)'], fill='#fff', stroke=BROWN, size=13.5))
    b.append(F.box(50, 75, 390, 50, ['Task publisher, global model, incentives'], fill='#fff', stroke=F.GREY, size=13.5))
    for x in (175, 455):
        b.append(F.arrow(x, 490, x, 398))
    b.append(F.arrow(245, 340, 245, 263))
    b.append(F.arrow(245, 205, 245, 127))
    b.append(F.text(1065, 30, 'Where the threats enter', 15, 'bold', fill=F.RED))
    b.append(F.box(915, 455, 305, 100, ['Poisoning', 'Malicious or fake participants', 'Free riding'], fill=F.RED_L, stroke=F.RED, size=14))
    b.append(F.arrow(915, 505, 884, 505, color=F.RED))
    b.append(F.box(915, 255, 305, 80, ['Inference, wherever updates are', 'seen, the ledger included;', 'denial of service'], fill=F.RED_L, stroke=F.RED, size=14))
    b.append(f'<line x1="915" y1="295" x2="900" y2="295" stroke="{F.RED}" stroke-width="1.4"/>')
    b.append(f'<line x1="900" y1="220" x2="900" y2="355" stroke="{F.RED}" stroke-width="1.4"/>')
    b.append(F.arrow(900, 220, 884, 220, color=F.RED))
    b.append(F.arrow(900, 355, 884, 355, color=F.RED))
    return F.render('architecture', W, H, ''.join(b))


SHADE = ['#ffffff', '#e3eefb', '#c4dbf6', '#97bdec', '#5f97dc', '#2f6fc0', '#1d4f8f']     # one hue, light to dark


def shade(n, mx):
    return SHADE[0] if n == 0 else SHADE[min(len(SHADE) - 1, 1 + int((len(SHADE) - 2) * (n - 1) / max(1, mx - 1)))]


def heat(name, title_rows, years, W=1180):
    """year-by-row heat maps: [(panel title, [(row label, {year: n})])]; the number is printed in every cell"""
    cw, ch, lw, top = 92, 34, 330, 40
    H = top + sum(40 + len(rows) * ch for _, rows in title_rows) + 50
    b, y = [], top
    for x_i, yr in enumerate(years):
        b.append(F.text(lw + x_i * cw + cw / 2, top - 12, str(yr) + ('*' if yr == 2026 else ''), 14, 'bold', fill=F.INK2))
    for title, rows in title_rows:
        b.append(F.text(20, y + 22, title, 15, 'bold', anchor='start', fill=F.INK))
        y += 36
        mx = max([n for _, d in rows for n in d.values()] or [1])
        for lab, d in rows:
            b.append(F.text(lw - 12, y + ch / 2 + 5, lab, 14, 'normal', anchor='end', fill=F.INK))
            for x_i, yr in enumerate(years):
                n = d.get(yr, 0)
                c = shade(n, mx)
                b.append(f'<rect x="{lw + x_i * cw + 2}" y="{y + 2}" width="{cw - 4}" height="{ch - 4}" rx="4" fill="{c}" stroke="{F.GREY_L}"/>')
                b.append(F.text(lw + x_i * cw + cw / 2, y + ch / 2 + 5, str(n) if n else '–', 14, 'bold' if n else 'normal',
                                fill='#ffffff' if c in SHADE[4:] else (F.INK if n else F.MUTED)))
            y += ch
        y += 4
    b.append(F.text(W / 2, H - 16, '* January to the search date. Darker cells: more studies.', 13, 'normal', fill=F.INK2, italic=True))
    record(name, kind='heat', columns=[str(yr) + ('*' if yr == 2026 else '') for yr in years],
           panels=[[title, [[lab, [d.get(yr, 0) for yr in years]] for lab, d in rows]] for title, rows in title_rows])
    return F.render(name, W, H, ''.join(b))


ANGLES = [('verification', 'Verification (not by ZKP)'), ('zero-knowledge proofs', 'ZKPs'), ('blockchain', 'Blockchain'), ('poisoning', 'Poisoning'),
          ('malicious or fake participants', 'Malicious or fake participants'), ('free riding', 'Free riding')]   # the six focus angles, by layer (SQ3, SQ4)
MECH = [('Differential privacy (DP, LDP)', {'DP', 'LDP'}), ('Homomorphic encryption (HE)', {'HE'}),
        ('Secret sharing, SMPC, masking', {'SMPC', 'secret-sharing', 'masking-secure-aggregation'}), ('Trusted execution (TEE)', {'TEE'}),
        ('Zero-knowledge proofs (ZKP)', {'ZKP'}), ('Pseudonyms, anonymity', {'pseudonyms-anonymity'})]


def L(sh, key, field):
    A = sh.get('answers', {})
    v = ((A.get(key, {}) or {}).get('values') or {}).get(field)
    if v is None:                                   # the merged form of 15 October 2026: the field is in another answer
        v = next((((a or {}).get('values') or {})[field] for a in A.values() if field in ((a or {}).get('values') or {})), None)
    return v if isinstance(v, list) else ([v] if v not in (None, '') else [])


def trends(fin, S):
    """the focus angles of all included studies, and the privacy mechanisms of the primary studies, per year"""
    ys = list(range(2020, 2027))
    import data as Dt                                             # the angles from the full-text records, as Table 11 (claims audit V39)
    marks = {r['corpus_id']: Dt.angle_marks(r) for r in fin}
    a = [(lab, {y: sum(1 for r in fin if r['kind'] == 'primary' and r['year'] == str(y) and marks[r['corpus_id']].get(key) == '●') for y in ys})
         for key, lab in ANGLES]
    yr = {r['corpus_id']: int(r['year']) for r in fin}
    prim = [k for k in S if k in yr and next(r['kind'] for r in fin if r['corpus_id'] == k) == 'primary']
    m = [(lab, {y: sum(1 for k in prim if yr[k] == y and set(L(S[k], 'P2', 'mechanisms')) & keys) for y in ys}) for lab, keys in MECH]
    return heat('trends', [('(a) Focus angles of the primary studies', a), ('(b) Privacy mechanisms of the primary studies', m)], ys)


THREATS = [('Attacks on the learning', [('poisoning', 'Poisoning'), ('backdoor', 'Backdoor'), ('byzantine_malicious', 'Byzantine or malicious participants'),
                                         ('sybil_fake', 'Sybil or fake participants'), ('free_riding', 'Free riding'), ('collusion', 'Collusion'),
                                         ('inference_privacy_attack', 'Inference and other privacy attacks'),
                                         ('malicious_server_aggregator', 'Malicious or curious server or aggregator')]),
           ('Properties of the system', [('tampering', 'Tampering with records or models'), ('single_point_of_failure', 'Single point of failure'),
                                         ('dos_ddos', 'Denial of service'), ('byzantine_consensus', 'Byzantine validators or committee members')])]


def threats(s):
    """threats the primary studies claim to counter, and those for which they report a test by an attack (drawn inside the claim); the
    attacks on the learning apart from the properties of the system, which a security argument may settle"""
    W, lw, bh, gap, top = 1100, 360, 22, 12, 64
    def nums(k):
        return s.get(f'claimed_learning_{k}', 0), s.get(f'tested_learning_{k}', 0), s.get(f'tested_described_{k}', 0)
    rows = [(grp, lab) + nums(k) for grp, items in THREATS for k, lab in items]
    mx = max(r[2] for r in rows) or 1
    sc = (W - lw - 70) / mx
    H = top + len(rows) * (bh + gap) + 2 * 34 + 20
    b = []
    for k_, (lab, col, st, dash) in enumerate((('Claimed', '#ffffff', F.RED, None), ('Test reported, attack described', F.RED, F.RED, None),
                                               ('Test reported, attack not described', F.RED_L, F.RED, '4,3'))):
        d = f' stroke-dasharray="{dash}"' if dash else ''
        b.append(f'<rect x="{lw - 340 + k_ * 300}" y="18" width="18" height="16" rx="3" fill="{col}" stroke="{st}"{d}/>')
        b.append(F.text(lw - 340 + k_ * 300 + 26, 31, lab, 14.5, 'normal', anchor='start', fill=F.INK))
    y, last = top, None
    for grp, lab, c, t_, d_ in rows:
        if grp != last:
            b.append(F.text(14, y + 16, grp, 15, 'bold', anchor='start', fill=F.INK2))
            y, last = y + 30, grp
        b.append(F.text(lw - 12, y + bh / 2 + 5, lab, 14, 'normal', anchor='end', fill=F.INK))
        b.append(f'<rect x="{lw}" y="{y}" width="{max(c * sc, 2):.1f}" height="{bh}" rx="3" fill="#ffffff" stroke="{F.RED}" stroke-width="1.2"/>')
        if d_:
            b.append(f'<rect x="{lw}" y="{y + 4}" width="{d_ * sc:.1f}" height="{bh - 8}" rx="2" fill="{F.RED}"/>')
        if t_ > d_:
            b.append(f'<rect x="{lw + d_ * sc:.1f}" y="{y + 4}" width="{(t_ - d_) * sc:.1f}" height="{bh - 8}" rx="2" fill="{F.RED_L}" '
                     f'stroke="{F.RED}" stroke-dasharray="4,3"/>')
        b.append(F.text(lw + c * sc + 8, y + bh / 2 + 5, f'{t_} of {c}', 13.5, 'bold', anchor='start', fill=F.INK))
        y += bh + gap
    record('threats', kind='bar_clustered', categories=[r[1] for r in rows],
           series=[['Claimed', F.RED_L, [r[2] for r in rows]], ['Test reported', F.RED, [r[3] for r in rows]],
                   ['Test reported, attack described', '#8E2F2B', [r[4] for r in rows]]])
    return F.render('threats', W, int(H), ''.join(b))


def survey_coverage(fin, S, refs):
    """what each included survey treats as a subject, mentions or leaves out, layer by layer and focus angle by focus angle
    (the columns of Table VII)"""
    import thematic as TH
    cols = TH.SURVEY_COVER
    sec = [r for r in fin if r['kind'] == 'secondary' and r['corpus_id'] in S]
    val = lambda k, item, f: ((S[k]['answers'].get(item, {}) or {}).get('values') or {}).get(f, 'absent')
    word = {'subject': 'Yes', 'mentioned': 'Partial', 'absent': 'No'}
    score = lambda k: (sum(val(k, i, f) == 'subject' for i, f, _ in cols), sum(val(k, i, f) == 'mentioned' for i, f, _ in cols))
    sec.sort(key=lambda r: (-score(r['corpus_id'])[0], -score(r['corpus_id'])[1], r['year']))
    rows = [(f"{refs.get(r['corpus_id'], {}).get('first_author_surname', r['corpus_id'])} {r['year']}",
             [word.get(val(r['corpus_id'], i, f), 'No') for i, f, _ in cols]) for r in sec]
    labels = [a.split(' ', 1)[1] for _, _, a in cols]
    return coverage_grid('survey_coverage', labels, rows, {'Yes': F.BLUE, 'Partial': F.BLUE_L, 'No': '#ffffff'},
                         [('Yes: a subject of its own', F.BLUE), ('Partial: mentioned', F.BLUE_L), ('No: absent', '#ffffff')])


def prim_coverage(fin, S, refs):
    """the counterpart for the primary studies: what each does, layer by layer and focus angle by focus angle, graded as
    thematic.PRIM_COVER_NOTE states (the columns of Table VIII)"""
    import re as _re
    import thematic as TH
    prim = [r for r in fin if r['kind'] == 'primary' and r['corpus_id'] in S]
    grades = {r['corpus_id']: TH.prim_cover(r['corpus_id'], S[r['corpus_id']]) for r in prim}
    cols = TH.PRIM_COVER
    grades = {k: {c: ('Yes' if v.startswith('Yes') else v) for c, v in g_.items()} for k, g_ in grades.items()}   # a dagger marks the table only
    prim.sort(key=lambda r: (-sum(v == 'Yes' for v in grades[r['corpus_id']].values()),
                             -sum(v == 'Partial' for v in grades[r['corpus_id']].values()), r['year']))
    base = lambda r: f"{refs.get(r['corpus_id'], {}).get('first_author_surname', r['corpus_id'])} {r['year']}"
    clash = {x for x in map(base, prim) if sum(base(r) == x for r in prim) > 1}

    def label(r):                                              # two studies with one name and year: the first author's initials too
        if base(r) not in clash:
            return base(r)
        first = _re.split(r',| and | et al\.', refs.get(r['corpus_id'], {}).get('ieee', ''))[0].strip()
        return f"{first} {r['year']}"
    rows = [(label(r), [grades[r['corpus_id']][c] for c in cols]) for r in prim]
    return coverage_grid('prim_coverage', [TH.PRIM_HEAD[c].split(' ', 1)[1] for c in cols], rows, {'Yes': F.BLUE, 'Partial': F.BLUE_L, 'No': '#ffffff'},
                         [('Yes', F.BLUE), ('Partial', F.BLUE_L), ('No', '#ffffff')])
COVER_GROUPS = [('SQ1', 'Fabric', 1), ('SQ2', 'Privacy', 1), ('SQ3', 'Trust plane', 3), ('SQ4', 'Attacks and defences', 3), ('SQ5', 'Regulation', 1)]


def coverage_grid(name, labels, rows, colours, legend):
    """the coverage views (Figs. 4 and 6): one row per study, one column per layer or focus angle, grouped under the survey
    question and the layer it belongs to, each column labelled by what it grades; rows = [(label, [grade, ...])],
    colours = {grade: fill}, legend = [(text, fill)]"""
    cw, ch, lw = 76, 24, 260
    reach = int(max(len(l) for l in labels) * 7.2 * 0.72) + 12      # how far a label rotated by 45° reaches up and to the right
    top = 52 + reach + 16                                            # the group row, then the labels, then the grid
    W = max(lw + len(labels) * cw + 30, lw + (len(labels) - 1) * cw + cw // 2 + reach + 24)
    H = top + len(rows) * ch + 60
    b, x0 = [], lw
    for sq, layer, n in COVER_GROUPS:                               # the survey question and its layer above the columns
        b.append(F.text(x0 + n * cw / 2, 22, sq, 14, 'bold', fill=F.INK2))
        b.append(F.text(x0 + n * cw / 2, 40, layer, 13, 'normal', fill=F.INK2))
        b.append(f'<line x1="{x0 + 2}" y1="48" x2="{x0 + n * cw - 2}" y2="48" stroke="{F.INK2}" stroke-width="1.2"/>')
        x0 += n * cw
    for i, lab in enumerate(labels):
        x = lw + i * cw + cw / 2
        b.append(f'<text transform="translate({x + 4},{top - 10}) rotate(-45)" font-family="{F.FONT}" font-size="14" fill="{F.INK}">{lab}</text>')
    x0 = lw
    for _, _, n in COVER_GROUPS[:-1]:                           # lines between the layers
        x0 += n * cw
        b.append(f'<line x1="{x0}" y1="{top - 4}" x2="{x0}" y2="{top + len(rows) * ch}" stroke="{F.INK2}" stroke-width="1.5"/>')
    for j, (lab, marks) in enumerate(rows):
        b.append(F.text(lw - 10, top + j * ch + ch / 2 + 5, lab, 13, 'normal', anchor='end', fill=F.INK))
        for i, v in enumerate(marks):
            b.append(f'<rect x="{lw + i * cw + 2}" y="{top + j * ch + 2}" width="{cw - 4}" height="{ch - 4}" rx="3" '
                     f'fill="{colours.get(v, "#ffffff")}" stroke="{F.GREY_L}"/>')
    y = top + len(rows) * ch + 28
    for i, (lab, c) in enumerate(legend):
        b.append(f'<rect x="{lw + i * 230}" y="{y - 13}" width="16" height="16" rx="3" fill="{c}" stroke="{F.GREY}"/>')
        b.append(F.text(lw + i * 230 + 24, y, lab, 14, 'normal', anchor='start', fill=F.INK))
    record(name, kind='marks', columns=labels, groups=[[f'{sq} {layer}', n] for sq, layer, n in COVER_GROUPS], colors=colours, rows=[[l, m] for l, m in rows])
    return F.render(name, W, H, ''.join(b))


def spine(s):
    """the spine of the review: each layer, with its focus angles, the survey question it gives, where the question is introduced
    and answered, the open issue it leaves, the condition of the research gap that issue becomes, and the research question
    that takes it up (no results: they are in Section VI); one condition per layer, numbered like its survey question"""
    rows = [
        ('SQ1', 'NG-IoT fabric', '', F.BLUE, F.BLUE_XL, 'III-A · VI-B', ['1) Costs on constrained', 'devices and links'], 'C1', 'RQ2'),
        ('SQ2', 'Privacy plane', '', F.VIOLET, F.VIOLET_L, 'III-B · VI-C', ['2) Updates hidden from', 'every party'], 'C2', 'RQ1, RQ3'),
        ('SQ3', 'Trust plane', 'verification · ZKPs · blockchain', F.AQUA, F.AQUA_L, 'III-C · VI-D',
         ['3) Checks that the ledger', 'itself makes or verifies'], 'C3', 'RQ1'),
        ('SQ4', 'Attacks and defences', 'poisoning · malicious or fake · free riding', F.RED, F.RED_L, 'III-D · VI-E',
         ['4) Reported tests against', 'the three threats'], 'C4 (a, b, c)', 'RQ1'),
        ('SQ5', 'Regulatory layer', '', BROWN, BROWN_L, 'III-E · VI-F', ['5) Ledgers without personal data,', 'with erasure designed in'], 'C5', 'RQ3')]
    W = 1300
    b = []
    banner = [('I Introduction', 20, 190), ('II Method', 220, 150), ('IV Overview of the studies', 380, 250),
              ('V Surveys: open issues by layer', 640, 320), ('VII-A Lessons', 970, 310)]
    for t, x, w in banner:
        b.append(F.box(x, 14, w, 40, [t], fill=GOLD, stroke=GOLD_EDGE, size=14, weight='bold'))
    xs, ws = [20, 330, 520, 870, 1070], [290, 170, 310, 160, 210]
    heads = ['Layer, survey question and focus angles', 'Background · answer', 'Open issue (VII-B)', 'Gap condition (VIII)',
             'Research question (IX)']
    for x, w, h in zip(xs, ws, heads):
        b.append(F.text(x + w / 2, 84, h, 14, 'bold', fill=F.INK2))
    y0, rh, step = 100, 80, 98
    for i, (sq, layer, angles, c, cl, secs, issue, cond, rq) in enumerate(rows):
        y = y0 + i * step
        b.append(F.box(xs[0], y, ws[0], rh, [f'{sq} {layer}'] + ([angles] if angles else []), fill=cl, stroke=c, size=14, weight='bold'))
        b.append(F.arrow(xs[0] + ws[0], y + rh / 2, xs[1], y + rh / 2))
        b.append(F.box(xs[1], y, ws[1], rh, [secs], fill='#ffffff', stroke=c, size=15))
        b.append(F.arrow(xs[1] + ws[1], y + rh / 2, xs[2], y + rh / 2))
        b.append(F.box(xs[2], y, ws[2], rh, issue, fill=cl, stroke=c, size=14))
        b.append(F.arrow(xs[2] + ws[2], y + rh / 2, xs[3], y + rh / 2))
        b.append(F.box(xs[3], y, ws[3], rh, [cond], fill='#ffffff', stroke=F.INK2, size=15, weight='bold'))
        b.append(F.arrow(xs[3] + ws[3], y + rh / 2, xs[4], y + rh / 2))
        b.append(F.box(xs[4], y, ws[4], rh, [rq], fill=F.GREY_L, stroke=F.INK2, size=15, weight='bold'))
    yb = y0 + len(rows) * step + 4
    for t, x, w in (('X Limitations', 20, 400), ('XI Conclusion', 440, 400), ('Appendices: strings, criteria, quality', 860, 420)):
        b.append(F.box(x, yb, w, 40, [t], fill=GOLD, stroke=GOLD_EDGE, size=14, weight='bold'))
    return F.render('spine', W, yb + 54, ''.join(b))


S_MONTH = ['']                                                     # the month of the search, set by main() for the footnotes


def main(s, S, fin):
    """the figures of the paper (spine, PRISMA flow, architecture, taxonomy, threats; the reference design is drawn by figures_v68.py) and of the
    supplementary material (survey and primary-study coverage grids, trends by year)"""
    S_MONTH[0] = s.get('search_month', '')
    import json as _json
    prisma(s)
    spine(s)
    threats(s)
    taxonomy(s)
    architecture(s)
    if S:
        trends(fin, S)
        refs = _json.loads((B.parent / 'refs.json').read_text(encoding='utf-8'))
        survey_coverage(fin, S, refs)
        prim_coverage(fin, S, refs)
