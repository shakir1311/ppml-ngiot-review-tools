#!/usr/bin/env python3
"""Charts of the V14 review computed from the coded records: studies per year and per theme, privacy mechanisms,
datasets and open challenges. SVG rendered to PNG by figures_static.render (headless Chrome, 3x).

Colours follow the reference palette of the dataviz method (slot 1 blue, slot 2 orange; validated adjacent pair),
ink for all text, thin bars with a 2 px gap, one axis, a legend for two series.

Usage: scripts/.venv/bin/python scripts/review/figures_data.py
"""
import collections, sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import tables_v14 as T                     # noqa: E402
from figures_static import render, text, esc, FONT, INK, INK2, MUTED   # noqa: E402

S1, S2 = '#2a78d6', '#eb6834'             # primary, secondary
GRID = '#e4e3df'


def legend(x, y, items):
    out = []
    for lab, col in items:
        out.append(f'<rect x="{x}" y="{y - 9}" width="12" height="12" rx="2" fill="{col}"/>')
        out.append(text(x + 18, y - 3, lab, 12.5, 'normal', 'start', INK))
        x += 26 + 7.2 * len(lab)
    return ''.join(out)


def vbars_stacked(name, cats, series, colors, labels, W=880, H=380, ytitle='Studies'):
    left, right, top, bottom = 60, 20, 50, 50
    pw, ph = W - left - right, H - top - bottom
    totals = [sum(s[i] for s in series) for i in range(len(cats))]
    ymax = max(totals) or 1
    step = 5 if ymax <= 40 else 10
    ymax = ((ymax // step) + 1) * step
    b = [legend(left, 24, list(zip(labels, colors)))]
    for v in range(0, ymax + 1, step):
        y = top + ph - ph * v / ymax
        b.append(f'<line x1="{left}" y1="{y:.1f}" x2="{W - right}" y2="{y:.1f}" stroke="{GRID}" stroke-width="1"/>')
        b.append(text(left - 8, y, str(v), 11.5, 'normal', 'end', INK2))
    bw = pw / len(cats)
    for i, c in enumerate(cats):
        x = left + i * bw + bw * 0.18
        w = bw * 0.64
        y = top + ph
        for s, col in zip(series, colors):
            h = ph * s[i] / ymax
            if h > 0:
                b.append(f'<rect x="{x:.1f}" y="{y - h + 1:.1f}" width="{w:.1f}" height="{max(h - 2, 0.5):.1f}" rx="2" fill="{col}"/>')
            y -= h
        b.append(text(x + w / 2, y - 9, str(totals[i]), 11.5, 'bold', 'middle', INK))
        b.append(text(x + w / 2, top + ph + 18, str(c), 12, 'normal', 'middle', INK2))
    b.append(f'<text transform="translate(16,{top + ph / 2}) rotate(-90)" font-family="{FONT}" font-size="12" '
             f'fill="{INK2}" text-anchor="middle">{esc(ytitle)}</text>')
    return render(name, W, H, ''.join(b))


def hbars(name, cats, series, colors, labels, W=880, label_w=300, bar_h=22, gap=8, legend_on=True):
    top = 46 if legend_on else 16
    H = top + len(cats) * (bar_h + gap) + 16
    left, right = label_w, 60
    pw = W - left - right
    totals = [sum(s[i] for s in series) for i in range(len(cats))]
    xmax = max(totals) or 1
    b = [legend(left, 24, list(zip(labels, colors)))] if legend_on else []
    for i, c in enumerate(cats):
        y = top + i * (bar_h + gap)
        b.append(text(left - 10, y + bar_h / 2, c, 12.5, 'normal', 'end', INK))
        x = left
        for s, col in zip(series, colors):
            w = pw * s[i] / xmax
            if w > 0:
                b.append(f'<rect x="{x + 1:.1f}" y="{y}" width="{max(w - 2, 0.5):.1f}" height="{bar_h}" rx="2" fill="{col}"/>')
            x += w
        b.append(text(x + 8, y + bar_h / 2, str(totals[i]), 12, 'bold', 'start', INK))
    return render(name, W, H, ''.join(b))


def main():
    d = T.load()
    C = d['coding']
    inc = [i for i in d['included'] if i in C]
    kind = lambda i: T.kind(d, i)
    # years
    years = list(range(2017, 2027))
    prim = [sum(1 for i in d['included'] if T.year(d, i) == y and T.kind(d, i) == 'primary') for y in years]
    sec = [sum(1 for i in d['included'] if T.year(d, i) == y and T.kind(d, i) == 'secondary') for y in years]
    vbars_stacked('fig-years', years, [prim, sec], [S1, S2], ['Primary studies', 'Surveys and reviews'])
    # themes
    th = list(T.THEMES.items())
    cats = [n for _, n in th]
    p = [sum(1 for i in inc if C[i]['theme'] == t and kind(i) == 'primary') for t, _ in th]
    s = [sum(1 for i in inc if C[i]['theme'] == t and kind(i) == 'secondary') for t, _ in th]
    hbars('fig-themes', cats, [p, s], [S1, S2], ['Primary studies', 'Surveys and reviews'], label_w=330)
    # privacy mechanisms in primary studies: with and without a ledger
    groups = collections.OrderedDict([
        ('Differential privacy (DP, LDP)', {'DP', 'LDP'}),
        ('Homomorphic encryption (HE, FHE)', {'HE', 'FHE'}),
        ('Secret sharing, SMPC, secure aggregation', {'secret_sharing', 'SMPC', 'secure_aggregation'}),
        ('Trusted execution (TEE)', {'TEE'}),
        ('Zero-knowledge proofs (ZKP)', {'ZKP'}),
        ('Obfuscation, synthetic data, split learning', {'perturbation_obfuscation', 'split_learning', 'GAN_synthetic', 'anonymisation', 'unlearning'}),
        ('No privacy mechanism', {'none'}),
    ])
    pr = [i for i in inc if kind(i) == 'primary']
    def has(i, codes):
        ms = set(m for m in C[i]['privacy_mechanisms'] if not m.startswith('other'))
        if codes == {'none'}:
            return not (ms - {'none'})
        return bool(ms & codes)
    wl = [sum(1 for i in pr if C[i]['ledger'].get('used') and has(i, g)) for g in groups.values()]
    nl = [sum(1 for i in pr if not C[i]['ledger'].get('used') and has(i, g)) for g in groups.values()]
    hbars('fig-mechanisms', list(groups), [wl, nl], [S1, S2], ['With a ledger', 'Without a ledger'], label_w=330)
    # datasets
    ds = collections.Counter()
    for i in pr:
        for x in set(T.norm_dataset(v) for v in C[i]['evaluation'].get('datasets', [])):
            ds[x] += 1
    top = [k for k, v in ds.most_common(14) if v >= 2]
    hbars('fig-datasets', top, [[ds[k] for k in top]], [S1], ['Primary studies'], label_w=280, legend_on=False)
    # challenges
    ch = T.challenge_counts(d)
    items = [(c, ids) for c, ids in ch.items() if c != 'C99' and ids]
    items.sort(key=lambda kv: -len(kv[1]))
    cats = [T.CHALLENGE[c] for c, _ in items]
    p = [sum(1 for i in ids if kind(i) == 'primary') for _, ids in items]
    s = [sum(1 for i in ids if kind(i) == 'secondary') for _, ids in items]
    hbars('fig-challenges', cats, [p, s], [S1, S2], ['Primary studies', 'Surveys and reviews'], label_w=360)
    print('charts written')


if __name__ == '__main__':
    main()
