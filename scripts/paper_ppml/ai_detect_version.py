#!/usr/bin/env python3
"""Checks every section of a built version of the paper against the local open-source AI-text detectors, the permanent per-version step that replaces GPTZero in the pipeline (the author, 19 October 2026: "we dont need to add gptzero checks to the pipeline ... ai detection checks as part of the permanent pipeline with local tools and models").

Reads build/paper-V<n>.md (the build's markdown, numbers and citations resolved), splits it into units (the abstract; the prose of each
subsection, in chunks of about 350 words; every study paragraph of Section V-B on its own; every Key Takeaways box; the captions of each
section), scores each unit with ai_detect.py (Binoculars and Fast-DetectGPT with the Falcon-7B pair and their published thresholds; the
Desklib DeBERTa and e5 LoRA classifiers), writes build/AI-DETECT-V<n>.json and prints the table with the units each detector flags.
Tables, the abbreviation list and the reference list are not scored. The result names sections to the author; the text is the author's
to rewrite in their own words, never redrafted by a model to pass a detector.

Run with the local checker's environment:  local-checker/.venv/bin/python scripts/paper_ppml/ai_detect_version.py <version> [--fast] [--no-gpt2]
  --fast     the Qwen2.5-1.5B pair instead of Falcon-7B (quicker, no published threshold; for a look while writing)
  --no-gpt2  leave out the GPT-2 pass (perplexity and the GLTR share of tokens GPT-2 ranks in its top 10), which is otherwise
             part of the step (the author, 20 October 2026). GPT-2 has no published threshold, so the reading is measured: a unit
             is named when it is more predictable to GPT-2 than the author's own text (GPT2_REFERENCE below).
"""
import json, pathlib, re, statistics as st, sys, time

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import ai_detect as D

ROOT = HERE.parents[1]
B = ROOT / 'myliteraturereviewpaper' / 'ppml2026' / 'build'
CHUNK = 350                                                     # words per prose chunk
MIN_WORDS = 25


def words(t):
    return len(re.findall(r'\w+', t))


def openxml_text(block):
    return re.sub(r'\s+', ' ', ' '.join(re.findall(r'<w:t[^>]*>([^<]*)</w:t>', block))).strip()


def units_of(md):
    """The scorable units of the built markdown: (name, section, kind, text)."""
    md = md.split('---', 2)[-1] if md.startswith('---') else md
    out = []
    m = re.search(r'\*\*Abstract\*\* — (.*?)\n\n', md, re.S)
    if m:
        out.append(('Abstract', 'Front', 'abstract', m.group(1).strip()))
    body = md[md.index('\n# I. '):] if '\n# I. ' in md else md
    h1 = h2 = ''; prose = {}; order = []; caps = {}; studies = 0
    blocks = re.split(r'\n\s*\n', body)
    i = 0
    while i < len(blocks):
        b = blocks[i].strip(); i += 1
        if not b:
            continue
        if b.startswith('# '):
            h1 = b[2:].strip(); h2 = ''; continue
        if b.startswith('## '):
            h2 = b[3:].strip(); continue
        if h1.startswith('References'):
            continue
        sec = h1 if not h2 else f'{h1} | {h2}'
        if b.startswith('![') or b.startswith('*Fig.') or b.startswith('Table: ') or re.match(r'^\*?\*?Table [IVXLC]+\b', b):
            cap = re.sub(r'^!\[(.*?)\]\(.*$', r'\1', b, flags=re.S) if b.startswith('![') else re.sub(r'^Table: ', '', b)
            caps.setdefault(h1, []).append(re.sub(r'\s+', ' ', cap.strip('*')).strip()); continue
        if b.startswith('```{=openxml}'):
            while not b.rstrip().endswith('```') and i < len(blocks):    # the fenced block may span blank lines
                b += '\n\n' + blocks[i]; i += 1
            t = openxml_text(b)
            if 'Key Takeaways' in t:
                out.append((f'Key Takeaways of {sec}' if sec != h1 else f'Key Takeaways of {h1}', sec, 'box', t.replace('Key Takeaways', '', 1).strip()))   # a subsection's own box (VII-B from V84) keeps its own name
            continue
        if b.startswith('|') or b.startswith('```'):
            continue
        if h2.startswith('B. The Designs One by One') and words(b) >= 40 and '[' in b:
            studies += 1
            out.append((f'Study paragraph {studies}: {b[:40]}', sec, 'study', b)); continue
        if sec not in prose:
            prose[sec] = []; order.append(sec)
        prose[sec].append(b)
    for sec in order:
        chunks, cur, n = [], [], 0
        for b in prose[sec]:
            if cur and n + words(b) > CHUNK:
                chunks.append(cur); cur, n = [], 0
            cur.append(b); n += words(b)
        if cur:
            chunks.append(cur)
        for j, ch in enumerate(chunks, 1):
            t = '\n\n'.join(ch)
            if words(t) >= MIN_WORDS:
                out.append((sec + (f' ({j}/{len(chunks)})' if len(chunks) > 1 else ''), sec, 'prose', t))
    for h, cs in caps.items():
        t = ' '.join(cs)
        if words(t) >= MIN_WORDS:
            out.append((f'Captions of {h}', h, 'caption', t))
    return out


# The author's own text as the reference for the GPT-2 view, measured 20 October 2026 with the same GPT-2 (ai_detect.py, SKIP=clf,pair):
# phdproposal/phd funding proposal.txt: perplexity 28.0, GLTR top-10 share 0.661; phdproposal/projectproposal.txt: 30.2, 0.666.
# A unit of the paper is named when its GLTR share is above the author's highest or its perplexity below the author's lowest.
GPT2_REFERENCE = {'gltr_top10_max': 0.666, 'gpt2_ppl_min': 28.0, 'source': "the author's own proposal texts (phdproposal/), 20 October 2026"}


def gpt2_flag(sc):
    return 'GPT-2' if ('GLTR_top10' in sc and (sc['GLTR_top10'] > GPT2_REFERENCE['gltr_top10_max'] or sc.get('GPT2_ppl', 1e9) < GPT2_REFERENCE['gpt2_ppl_min'])) else None


def main(version, fast=False, gpt2=True):
    md = (B / f'paper-V{version}.md').read_text(encoding='utf-8')
    us = units_of(md)
    items = [{'name': n, 'text': t} for n, s, k, t in us]
    pair = D.QWEN if fast else D.FALCON
    t0 = time.time()
    res = D.score_items(items, pair=pair, skip=() if gpt2 else ('gpt2',), clfs=D.DEFAULT_CLFS)
    rows = []
    for n, s, k, t in us:
        r = res[n]; fl = D.flags(r) + ([gpt2_flag(r)] if gpt2_flag(r) else []); rows.append({'name': n, 'section': s, 'kind': k, 'words': words(t), 'scores': r, 'flags': fl})
    report = {'version': version, 'pair': pair, 'source': f'paper-V{version}.md', 'gpt2_reference': GPT2_REFERENCE if gpt2 else None, 'units': rows,
              'flagged': [r['name'] for r in rows if r['flags']], 'seconds': round(time.time() - t0)}
    out = B / f'AI-DETECT-V{version}.json'; out.write_text(json.dumps(report, indent=1, ensure_ascii=False), encoding='utf-8')
    print(f'{"unit":60s} {"kind":8s} {"words":>5s} {"Binoc":>7s} {"FDG P":>6s} {"Desklib":>8s} {"e5":>6s} {"GPT2ppl":>8s} {"GLTR":>6s}  flagged by')
    for r in rows:
        sc = r['scores']
        print(f'{r["name"][:60]:60s} {r["kind"]:8s} {r["words"]:5d} {sc.get("Binoculars", float("nan")):7.3f} {sc.get("FDG_P(AI)", float("nan")):6.2f} '
              f'{sc.get("Desklib-DeBERTa", float("nan")):8.3f} {sc.get("e5-LoRA", float("nan")):6.2f} {sc.get("GPT2_ppl", float("nan")):8.1f} {sc.get("GLTR_top10", float("nan")):6.3f}  {", ".join(r["flags"]) or "-"}')
    print()
    for det in ('Binoculars', 'Fast-DetectGPT', 'Desklib-DeBERTa', 'e5-LoRA', 'GPT-2'):
        n = sum(1 for r in rows if det in r['flags'])
        print(f'{det:16s} flags {n:3d} of {len(rows)} units' + ('' if not n else ': ' + '; '.join(r['name'][:40] for r in rows if det in r['flags'])[:400]))
    for k in ('abstract', 'prose', 'study', 'box', 'caption'):
        ks = [r for r in rows if r['kind'] == k and 'Binoculars' in r['scores']]
        if ks:
            W = sum(r['words'] for r in ks)
            print(f'{k:9s} {len(ks):3d} units {W:6d} words  Binoculars word-weighted mean {sum(r["scores"]["Binoculars"] * r["words"] for r in ks) / W:.3f}  '
                  f'min {min(r["scores"]["Binoculars"] for r in ks):.3f}  Desklib max {max(r["scores"].get("Desklib-DeBERTa", 0) for r in ks):.2f}')
    g = [r for r in rows if 'GLTR_top10' in r['scores']]
    if g:
        import statistics as st
        print(f'GPT-2 view: perplexity median {st.median(r["scores"]["GPT2_ppl"] for r in g):.1f} (min {min(r["scores"]["GPT2_ppl"] for r in g):.1f}), GLTR top-10 share median '
              f'{st.median(r["scores"]["GLTR_top10"] for r in g):.3f} (max {max(r["scores"]["GLTR_top10"] for r in g):.3f}); the author\'s own text: perplexity {GPT2_REFERENCE["gpt2_ppl_min"]}, share {GPT2_REFERENCE["gltr_top10_max"]}; '
              f'{sum(1 for r in g if "GPT-2" in r["flags"])} unit(s) more predictable than the author\'s text')
    print(f'\n{out.relative_to(ROOT)}: {len(rows)} units, {len(report["flagged"])} flagged, pair {pair[0].split("/")[-1]}, {report["seconds"]} s')


if __name__ == '__main__':
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    main(sys.argv[1], '--fast' in sys.argv, '--no-gpt2' not in sys.argv)
