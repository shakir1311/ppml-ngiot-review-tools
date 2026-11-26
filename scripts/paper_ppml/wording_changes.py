#!/usr/bin/env python3
"""The wording changes of one version against the one before it, sentence by sentence: which paragraphs were rewritten and which
revised, every changed sentence before and after with the changed words marked, and the review guidance each change applies (the
author, 26 November 2026: "v90 is the one they reviewed and now we have v91. so what sentences were changed and what paragraphs
were rewritten").

Reads build/paper-V<prev>.md and build/paper-V<n>.md. Within each top-level section, every sentence of the new text is matched to
its closest sentence of the old text (best pairs first; a pair needs a similarity of at least 0.45); a new paragraph counts as
rewritten when fewer than half of its sentences have a close predecessor (similarity of at least 0.6), otherwise as revised. Old
sentences left without a successor are listed as removed. Each changed pair is labelled by the guidance it visibly applies, by
fixed rules on the two texts (Dr Rathore's example rewrites; first person and active voice; a named study or party in place of a
pronoun; past tense for completed work; precise terms; capitalised long forms of abbreviations); pairs no rule recognises are
labelled by how much changed. Table headings and subsection headings are compared too; the abbreviation list and the references
are left out. Writes Docs/WORDING-CHANGES-V<n>-<date>.html (never over an existing file), printable in portrait and landscape.

Usage: python3 scripts/paper_ppml/wording_changes.py <version> [<date>]
"""
import collections, datetime, difflib, html, pathlib, re, sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
BUILD = ROOT / 'myliteraturereviewpaper' / 'ppml2026' / 'build'
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import review_response as RR                                              # noqa: E402  (plain, word_diff, CSS)
import version_changes as VC                                              # noqa: E402  (tables)

SPLIT = re.compile(r'(?<!\bal\.)(?<!\bFig\.)(?<!e\.g\.)(?<!i\.e\.)(?<!\bvs\.)(?<!\bNo\.)(?<=[.;?!])\s+(?=[A-Z0-9\["“(*])')
RATHORE = [('blockchain joined to FL', 'integration of blockchain with'), ('Two of them see in the ledger', 'identified the ledger as a solution'),
           ('Three go into what it costs', 'investigated the associated overheads'), ('They work in different settings', 'investigated different application environments'),
           ('do the same for', 'similarly investigated'), ('puts several privacy mechanisms side by side', 'comparative analysis of privacy-preserving mechanisms'),
           ('go through the threats', 'systematically examined the security'), ('The grid shows where the gaps lie', 'comparative analysis highlights'),
           ('This review does both', 'addresses both identified research gaps'), ('leaves the data in place', 'retains the data locally'),
           ('This review asks', 'This study systematically investigates'), ('were searched', 'we searched'), ('one meets two', 'Kalapaaking'),
           ('An agenda closes the paper', 'The review contributes')]
TERMS = [('noised', 'noise-perturbed|with noise added|perturbed'), ('in the clear', 'in plaintext|plaintext'), ('keeps? (?:it |the update )?from|kept from', 'conceal'),
         (r'\bsees?\b|\bseeing\b', 'observ'), (r'\bchecks?\b|\bchecked\b', 'verif'), ('stands? in for', 'replac'), ('pull apart', 'conflict')]
LONG_FORMS = ['Machine Learning (ML)', 'Federated Learning (FL)', 'Privacy-Preserving Machine Learning (PPML)', 'Zero-Knowledge Proof (ZKP)', 'Differential Privacy (DP)',
              'Local Differential Privacy (LDP)', 'Homomorphic Encryption (HE)', 'Secure Multi-Party Computation (SMPC)', 'Trusted Execution Environment (TEE)',
              'Multi-access Edge Computing (MEC)', 'Zero-Knowledge Proofs (ZKPs)']
GUIDE = {
 'rathore': "Dr Rathore's example rewrite",
 'voice': 'First person (we) and active voice',
 'tense': 'Past tense for completed work',
 'clarity': 'Clarity: study or party named, no vague pronoun',
 'terms': 'Precise scientific terms',
 'abbrev': "Capitalised long form (Dr Kavianpour's tracked change)",
 'example': "Generic opening, no example (Dr Kavianpour's comment)",
 'flow': 'Rewritten for analysis, logic and flow',
 'wording': 'Wording made more precise',
 'new': 'New sentence: analysis, logic and flow',
}


def sentences(t):
    return [s.strip() for s in SPLIT.split(t) if s.strip()]


def section_paragraphs(md):
    """{section: [paragraph text, …]} in order, prose, list items, captions, Key Takeaways and table notes; front matter as 'Abstract'"""
    out = collections.OrderedDict()
    for head, items in RR.sections(md):
        if head in ('References',):
            continue
        paras = []
        for kind, t in items:
            if kind in ('heading', 'table'):
                continue
            p = RR.plain(t)
            if head == 'Front':
                if not p.startswith('Abstract'):
                    continue
                p = re.sub(r'^Abstract\s*—\s*', '', p)
            paras.append(p)
        out['Abstract' if head == 'Front' else head] = paras
    return out


def headings(md):
    return {h: [t for k, t in items if k == 'heading'] for h, items in RR.sections(md)}


FORMAL = [(r'\boffered\b', 'propos'), (r'\bsays?\b', 'stat'), (r'\bgives?\b', 'provid'), (r'\bdeals? with\b', 'review|address'), (r'\bthe fix\b', 'propos|remed|replac'),
          (r'\bkeeps?\b|\bkept\b', 'retain|conceal'), (r'\bset aside\b', 'exclud'), (r'\btakes? the place of\b', 'replac'), (r'\bshows?\b', 'demonstrat|show that'),
          (r'work against each other', 'conflict'), (r'\bgoes into\b|\bgo into\b', 'investigat|examin'), (r'\bpicks?\b', 'select'), (r'\bhas to\b|\bhave to\b', 'must'),
          (r'\bmore or less\b|\ba good deal\b', 'substantial'), (r'\bspares?\b', 'avoid'), (r'\bstay(?:s)? put\b', 'remain'), (r'\bbig\b', 'large|substantial')]
IRREG = {('is', 'was'), ('are', 'were'), ('run', 'ran'), ('runs', 'ran'), ('gives', 'gave'), ('shows', 'showed'), ('finds', 'found'), ('find', 'found'),
         ('holds', 'held'), ('state', 'stated'), ('take', 'took'), ('takes', 'took')}


def named(t):
    """the reference numbers that a sentence attaches to a named author: 'Kalapaaking et al. [47]', 'Hu and Zhang [53]', 'Tolah [70]'"""
    return set(re.findall(r'(?:et al\.|\b[A-Z][\w’-]+ and [A-Z][\w’-]+|\b[A-Z][\w’-]{2,}) \[(\d+)\]', t))


def tense_shift(o, n):
    wo, wn = o.lower().split(), n.lower().split()
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, wo, wn).get_opcodes():
        if op != 'replace':
            continue
        for a, b in zip(wo[i1:i2], wn[j1:j2]):
            a, b = a.strip('.,;:'), b.strip('.,;:')
            if (a, b) in IRREG or (b.endswith('ed') and (b[:-2] in (a, a.rstrip('s')) or b[:-1] in (a, a.rstrip('s')))):
                return True
    return False


def tags(o, n):
    """the guidance a changed sentence visibly applies, by fixed rules on the two texts (o is '' for a new sentence)"""
    out = []
    lo, ln_ = o.lower(), n.lower()
    if any(b.lower() in ln_ and b.lower() not in lo for _, b in RATHORE) or any(a.lower() in lo and b.lower() in ln_ for a, b in RATHORE):
        out.append('rathore')
    PASSIVE = r'\b(?:is|are|was|were|been|be)\s+(?:\w+ly\s+)?\w+(?:ed|en|set|run|shown|given|kept|held)\b'
    if (re.search(r'\b(we|our|us)\b', n, re.I) and not re.search(r'\b(we|our|us)\b', o, re.I)) or \
            (o and len(re.findall(PASSIVE, o)) > len(re.findall(PASSIVE, n))):
        out.append('voice')
    if o and tense_shift(o, n):
        out.append('tense')
    if (named(n) - named(o)) or (o and re.search(r'\b(two|three|one) of them\b|^they\b', lo) and not re.search(r'\b(two|three|one) of them\b|^they\b', ln_)):
        out.append('clarity')
    if o and (any(re.search(a, o) and re.search(b, n) and not re.search(a, n) for a, b in TERMS) or
              any(re.search(a, lo) and re.search(b, ln_) and not re.search(a, ln_) for a, b in FORMAL)):
        out.append('terms')
    if any(f in n and f.lower() in lo and f not in o for f in LONG_FORMS):
        out.append('abbrev')
    if re.search(r'vehicle takes|patient', o) and not re.search(r'vehicle takes|patient', n):
        out.append('example')
    if not out:
        out.append('new' if not o else ('flow' if difflib.SequenceMatcher(None, o, n).ratio() < 0.6 else 'wording'))
    return out


def align(old_sents, new_sents, floor=0.45):
    """best pairs first: {new index: (old index, similarity)}"""
    cand = []
    for j, n in enumerate(new_sents):
        for i, o in enumerate(old_sents):
            sm = difflib.SequenceMatcher(None, o, n, autojunk=False)
            if sm.real_quick_ratio() < floor or sm.quick_ratio() < floor:
                continue
            r = sm.ratio()
            if r >= floor:
                cand.append((r, i, j))
    used_o, match = set(), {}
    for r, i, j in sorted(cand, reverse=True):
        if i in used_o or j in match:
            continue
        used_o.add(i); match[j] = (i, r)
    return match


CSS = RR.CSS + '''
.why{background:#f4f6fa;border-left:4px solid #3c6fb0;padding:8px 12px;margin:8px 0 12px}
table.s{table-layout:fixed}table.s td{font-size:0.9em}table.s col.b,table.s col.a{width:42%}table.s col.g{width:16%}
.tag{display:inline-block;font-size:0.78em;background:#eef2f8;border:1px solid #c9d3e0;border-radius:4px;padding:1px 5px;margin:1px 2px 1px 0}
.par{margin:14px 0 4px;font-weight:bold}.par .st{font-weight:normal;color:#555}.new{background:#eef7ee}.gone{background:#fbeeee}
.toc a{color:#1d4f8f}.small{font-size:0.86em}
@media print{table.s{break-inside:auto}table.s tr{break-inside:avoid}}
'''


def main(version, date=None):
    prev = version - 1
    date = date or datetime.date.today().isoformat()
    om, nm = (BUILD / f'paper-V{prev}.md').read_text(encoding='utf-8'), (BUILD / f'paper-V{version}.md').read_text(encoding='utf-8')
    old, new = section_paragraphs(om), section_paragraphs(nm)
    oh, nh = headings(om), headings(nm)
    summary, body, tagcount = [], [], collections.Counter()
    for sec, paras in new.items():
        oparas = old.get(sec, [])
        osents_by_p = [sentences(p) for p in oparas]
        osents = [s for ps in osents_by_p for s in ps]
        ostart = [sum(len(x) for x in osents_by_p[:i]) for i in range(len(oparas))]
        nsents_by_p = [sentences(p) for p in paras]
        flat = [s for ps in nsents_by_p for s in ps]
        nstart = [sum(len(x) for x in nsents_by_p[:i]) for i in range(len(paras))]
        # pair the paragraphs first (a study paragraph with its own predecessor), then match sentences inside each pair;
        # sentences of unpaired paragraphs are matched against the unpaired old paragraphs of the section
        cites = lambda t: set(re.findall(r'\[(\d+)\]', t))
        pp, used = {}, set()
        cand = sorted(((difflib.SequenceMatcher(None, oparas[i], paras[j], autojunk=False).ratio() + (0.5 if cites(oparas[i]) & cites(paras[j]) and len(cites(paras[j])) <= 2 else 0), i, j)
                       for j in range(len(paras)) for i in range(len(oparas))), reverse=True)
        for r, i, j in cand:
            if r < 0.3 or i in used or j in pp:
                continue
            used.add(i); pp[j] = i
        match = {}
        for j, i in pp.items():
            m = align(osents_by_p[i], nsents_by_p[j])
            match.update({nstart[j] + jj: (ostart[i] + ii, r) for jj, (ii, r) in m.items()})
        rest_o = [ostart[i] + k for i in range(len(oparas)) if i not in used for k in range(len(osents_by_p[i]))]
        rest_n = [nstart[j] + k for j in range(len(paras)) if j not in pp for k in range(len(nsents_by_p[j]))]
        m = align([osents[x] for x in rest_o], [flat[x] for x in rest_n])
        match.update({rest_n[jj]: (rest_o[ii], r) for jj, (ii, r) in m.items()})
        rows_sec, k, n_rew, n_rev, n_same, n_sent = [], 0, 0, 0, 0, 0
        for pi, ps in enumerate(nsents_by_p):
            idx = list(range(k, k + len(ps))); k += len(ps)
            close = sum(1 for j in idx if j in match and match[j][1] >= 0.6)
            changed = [j for j in idx if not (j in match and osents[match[j][0]] == flat[j])]
            if not changed:
                n_same += 1; continue
            kind = 'rewritten' if close < len(idx) / 2 else 'revised'
            n_rew += kind == 'rewritten'; n_rev += kind == 'revised'
            rows = []
            for j in changed:
                n_sent += 1
                if j in match:
                    o = osents[match[j][0]]; tg = tags(o, flat[j]); da, db = RR.word_diff(o, flat[j])
                    rows.append(f'<tr><td>{da}</td><td>{db}</td><td>' + ''.join(f'<span class="tag">{GUIDE[t]}</span>' for t in tg) + '</td></tr>')
                else:
                    tg = tags('', flat[j]); rows.append(f'<tr class="new"><td><span class="unchanged">(new sentence)</span></td><td><ins>{html.escape(flat[j])}</ins></td><td>' + ''.join(f'<span class="tag">{GUIDE[t]}</span>' for t in tg) + '</td></tr>')
                tagcount.update(tg)
            first = ' '.join(ps)[:90]
            rows_sec.append(f'<p class="par">Paragraph {pi + 1}: {kind} <span class="st">({len(changed)} of {len(ps)} sentences changed) · “{html.escape(first)}…”</span></p>'
                            f'<table class="s"><colgroup><col class="b"><col class="a"><col class="g"></colgroup><tr><th>V{prev} (reviewed)</th><th>V{version}</th><th>Guidance applied</th></tr>' + ''.join(rows) + '</table>')
        gone = [osents[i] for i in range(len(osents)) if i not in {m[0] for m in match.values()}]
        if gone:
            rows_sec.append(f'<p class="par">Sentences of V{prev} removed or merged into the rewritten text <span class="st">({len(gone)})</span></p><table class="s"><colgroup><col></colgroup>' +
                            ''.join(f'<tr class="gone"><td><del>{html.escape(s)}</del></td></tr>' for s in gone) + '</table>')
        hd = [(a, b) for a, b in zip(oh.get(sec, []), nh.get(sec if sec != 'Abstract' else 'Front', [])) if a != b]
        if hd:
            rows_sec.insert(0, '<p class="par">Subsection headings</p><table class="s"><colgroup><col class="b"><col class="a"><col class="g"></colgroup>' +
                            ''.join(f'<tr><td>{RR.word_diff(a, b)[0]}</td><td>{RR.word_diff(a, b)[1]}</td><td><span class="tag">{GUIDE["terms"]}</span></td></tr>' for a, b in hd) + '</table>')
        summary.append((sec, n_rew, n_rev, n_same, n_sent, len(gone)))
        if rows_sec:
            anchor = re.sub(r'\W+', '-', sec.lower()).strip('-')
            body.append(f'<h2 id="{anchor}">{html.escape(sec)}</h2>' + ''.join(rows_sec))
    # table headings
    ot, nt = VC.tables(om), VC.tables(nm)
    th = [(lab, ot[lab][1], nt[lab][1]) for lab in nt if lab in ot and ot[lab][1] != nt[lab][1]]
    if th:
        body.append('<h2 id="tables">Table headings</h2><table class="s"><colgroup><col class="b"><col class="a"><col class="g"></colgroup><tr><th>V' + str(prev) + '</th><th>V' + str(version) + '</th><th>Table</th></tr>' +
                    ''.join(f'<tr><td>{html.escape(" | ".join(a))}</td><td>{html.escape(" | ".join(b))}</td><td>{lab}</td></tr>' for lab, a, b in th) + '</table>')
    h = [f'<!doctype html><html lang="en"><head><meta charset="utf-8"><title>Wording changes in V{version}</title><style>{CSS}</style></head><body>',
         f'<h1>Wording changes in V{version}, against V{prev}</h1><div class="meta">{date} · V{prev} is the version the supervisory committee reviewed; V{version} answers that review.</div>',
         f'<div class="why">Every sentence of V{version} that differs from V{prev}, section by section. A paragraph is marked <b>rewritten</b> when most of its sentences are new, '
         f'<b>revised</b> when its sentences were edited. For each changed sentence the V{prev} text is on the left and the V{version} text in the middle '
         '(deleted words struck through, inserted words underlined), with the guidance it applies on the right. Unchanged sentences are not shown. '
         'Sentences of the old text that no longer appear are listed at the end of each section. Tables, figures and counts are not part of this file: none of their values changed.</div>',
         '<h2>Overview</h2><table><tr><th>Section</th><th>Paragraphs rewritten</th><th>Paragraphs revised</th><th>Paragraphs unchanged</th><th>Sentences changed or new</th><th>Old sentences removed or merged</th></tr>']
    for sec, a, b, c, d, e in summary:
        anchor = re.sub(r'\W+', '-', sec.lower()).strip('-')
        h.append(f'<tr><td><a href="#{anchor}">{html.escape(sec)}</a></td><td>{a}</td><td>{b}</td><td>{c}</td><td>{d}</td><td>{e}</td></tr>')
    tot = [sum(x[i] for x in summary) for i in range(1, 6)]
    h.append('<tr><th>All sections</th>' + ''.join(f'<th>{x}</th>' for x in tot) + '</tr></table>')
    h.append('<p class="small">Guidance applied, counted over the changed sentences (a sentence can apply several): ' +
             '; '.join(f'{GUIDE[t]} {n}' for t, n in tagcount.most_common()) + '.</p>')
    h += body
    h.append('</body></html>')
    out = ROOT / 'Docs' / f'WORDING-CHANGES-V{version}-{date}.html'
    n = 2
    while out.exists():
        out = ROOT / 'Docs' / f'WORDING-CHANGES-V{version}-V{n}-{date}.html'; n += 1
    out.write_text('\n'.join(h), encoding='utf-8')
    print(f'{out.relative_to(ROOT)}: {out.stat().st_size // 1024} KB; rewritten {tot[0]}, revised {tot[1]}, unchanged {tot[2]} paragraphs; {tot[3]} sentences changed or new, {tot[4]} removed')
    for s in summary:
        print('  ', s)


if __name__ == '__main__':
    main(int(sys.argv[1]), sys.argv[2] if len(sys.argv) > 2 else None)
