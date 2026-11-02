#!/usr/bin/env python3
"""Regenerate evidence-sheet answers with a local model, from the paper's own extracted text, and compare them with the
existing sheets — to show the local machinery can do this kind of extraction in future.

    local-checker/.venv/bin/python local-checker/regenerate.py MODEL KEY [KEY ...] [--questions P1 P2 P3 P5 P6] [--think]

For each study and question the model gets the extraction guide's rules and that question with its allowed values (from
search-ppml/evidence/EXTRACTION-GUIDE.md) and the paper's pages (text/pages, text/pages_ocr), each marked with its PDF page
number; it answers with JSON: answer, values, evidence [{page, quote}].

What the script prints (for Claude) holds no paper text: per answer, how many tag fields agree with the sheet, how many of
the model's quotations are found word for word on the page they cite, and the time. The model's answers themselves are
written to data/regenerated/ and to show/regenerated.html (sheet and model side by side) for the person to read.
"""
import argparse
import html
import json
import re
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import check_claims as cc

ROOT = cc.ROOT
GUIDE = ROOT / 'search-ppml' / 'evidence' / 'EXTRACTION-GUIDE.md'
SHEETS = ROOT / 'search-ppml' / 'evidence' / 'sheets'
OLLAMA = 'http://127.0.0.1:11434/api/chat'
TUNE = ['N011', 'N012', 'N019', 'n3348', 'O043']          # the studies the settings are tuned on
HELD_BACK = ['N014', 'N017', 'n2912', 'r0323', 'n3855']   # tested on only once the settings are fixed; never examples

RULES = """You extract one answer of an evidence sheet from a research paper, for a literature review.
Rules:
1. The paper's text is the authority. Record what the paper says as the paper's claim. Do not judge whether it is correct
   and add nothing from outside knowledge.
2. Evidence: give one or more quotations, each copied character for character from ONE page of the paper as given below,
   5 to 40 words, no ellipsis inside, with the page number shown in the page marker (=== PAGE n ===).
3. If the paper does not say, the answer is "not stated", with no evidence. Never guess.
4. Do not read values off bars or lines of figures.
5. The answer is brief: up to about 60 words. The values fields carry the categories.
6. Use only the allowed values listed for each field; add "other: <word>" when nothing fits. List fields take a JSON list.
Reply with exactly one JSON object and nothing else:
{"answer": "...", "values": {<field>: <value or list>, ...}, "evidence": [{"page": <n>, "quote": "..."}]}"""


AUDIT_GUIDE = ROOT / 'search-ppml' / 'evidence' / 'claims-audit-V42' / 'AUDIT-GUIDE.md'


def codebook():
    """The decision rules for every tag, as the sheets were audited against them (AUDIT-GUIDE.md, 'Definitions')."""
    text = AUDIT_GUIDE.read_text(encoding='utf-8')
    text = text[text.index('## Definitions'):text.index('## Results file')]
    rules = {}
    for m in re.finditer(r'^- \*\*([PS][1-8])\*\*(.+?)(?=^- \*\*[PS][1-8]\*\*|^Secondary studies|\Z)', text, re.M | re.S):
        rules[m.group(1)] = re.sub(r'\s+', ' ', m.group(2).replace('`', '').replace('**', '')).strip()
    return rules


def examples(q, exclude, n):
    """n finished sheet answers to the same question from other studies (records; given to the local model only)."""
    out = []
    for f in sorted(SHEETS.glob('*.json')):
        if f.stem in exclude or len(out) >= n:
            continue
        s = json.loads(f.read_text(encoding='utf-8'))
        a = s['answers'].get(q)
        if a and a.get('values') and a.get('evidence'):
            out.append({'answer': a['answer'][:600], 'values': a['values'],
                        'evidence': [{'page': e['page'], 'quote': e['quote']} for e in a['evidence'][:3]]})
    return out


def questions():
    rows = {}
    for m in re.finditer(r'^\| ([PS][1-8]) \| (.+?) \| (.+?) \|\s*$', GUIDE.read_text(encoding='utf-8'), re.M):
        rows[m.group(1)] = (re.sub(r'\*\*', '', m.group(2)).strip(), m.group(3).replace('`', '').strip())
    return rows


def paper_text(folder):
    pages = {}
    for sub in ('pages', 'pages_ocr'):
        for f in sorted((folder / 'text' / sub).glob('page_*.txt')):
            pages.setdefault(int(f.stem.split('_')[1]), []).append(f.read_text(encoding='utf-8', errors='ignore'))
    return '\n\n'.join(f'=== PAGE {n} ===\n' + '\n'.join(pages[n]) for n in sorted(pages)), pages


THINK_ROOM = 40000            # when thinking, the model may write until the context is full: this much room is left
ANSWER_BUDGET = 2000          # without thinking


# Thinking models must not decode greedily (temperature 0): their makers warn it makes them repeat themselves without end.
# These are the makers' recommended settings for thinking; the seed keeps a run repeatable.
THINK_SAMPLING = {'qwen': {'temperature': 0.6, 'top_p': 0.95, 'top_k': 20},
                  'gemma': {'temperature': 1.0, 'top_p': 0.95, 'top_k': 64}}
LOOP_LIMIT = 30000            # thinking tokens after which a run is treated as a loop and stopped


def ask(model, think, paper, q, title, allowed, words, progress=None, extra=''):
    room = THINK_ROOM if think else ANSWER_BUDGET
    ctx = min(131072, int(words * 1.6) + 1500 + room)     # the paper (or its sections), the instructions and the room
    options = {'seed': 0, 'num_ctx': ctx, 'num_predict': -2 if think else ANSWER_BUDGET}
    options.update(next((v for k, v in THINK_SAMPLING.items() if k in model), THINK_SAMPLING['qwen']) if think
                   else {'temperature': 0})
    body = {'model': model, 'stream': True, 'think': think, 'options': options,
            'messages': [{'role': 'system', 'content': RULES},
                         {'role': 'user', 'content': f'THE PAPER\n\n{paper}\n\nQUESTION {q}: {title}\nFields and allowed '
                                                     f'values: {allowed}{extra}'}]}
    req = urllib.request.Request(OLLAMA, data=json.dumps(body).encode(), headers={'Content-Type': 'application/json'})
    t0 = last_report = time.time()
    content, thinking_tokens, answer_tokens, final = [], 0, 0, {}
    with urllib.request.urlopen(req, timeout=3600) as r:
        for line in r:                                     # streamed: counted as it comes; only the answer is kept
            chunk = json.loads(line)
            msg = chunk.get('message', {})
            if msg.get('thinking'):
                thinking_tokens += 1
            if msg.get('content'):
                answer_tokens += 1
                content.append(msg['content'])
            if progress and time.time() - last_report > 30:
                progress(thinking_tokens, answer_tokens, time.time() - t0)
                last_report = time.time()
            if thinking_tokens > LOOP_LIMIT:
                final = {'done_reason': 'loop'}
                break
            if chunk.get('done'):
                final = chunk
                break
    secs = time.time() - t0
    LAST.update(tokens=thinking_tokens + answer_tokens, thinking=thinking_tokens,
                ran_out=final.get('done_reason') in ('length', 'loop'), reason=final.get('done_reason', '?'))
    text = ''.join(content)
    m = re.search(r'\{.*\}', text, re.S)
    try:
        return json.loads(m.group(0)) if m else None, secs
    except json.JSONDecodeError:
        return None, secs


LAST = {}                     # tokens written and whether the budget ran out, for the last answer (numbers only)


FREE_TEXT = {'defences', 'datasets', 'baselines', 'laws', 'databases', 'period', 'studies', 'open_issues'}


def word_set(v):
    items = v if isinstance(v, list) else [v]
    return {w for x in items for w in re.findall(r'[a-z0-9]+', str(x).lower()) if len(w) > 2}


def as_set(v):
    items = v if isinstance(v, list) else [v]
    return {str(x).split(':')[0].strip().lower() if str(x).lower().startswith('other') else str(x).strip().lower()
            for x in items if x not in (None, '')}


def on_page(quote, page, pages):
    texts = pages.get(page) or []
    return any(cc_found(quote, t) for t in texts)


def cc_found(quote, text):
    sq = lambda s: re.sub(r'[^a-z0-9]', '', cc.clean(s).lower())
    return len(sq(quote)) >= 10 and sq(quote) in sq(text)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('model')
    ap.add_argument('keys', nargs='+')
    ap.add_argument('--questions', nargs='+', default=['P1', 'P2', 'P3', 'P5', 'P6'])
    ap.add_argument('--think', action='store_true')
    ap.add_argument('--sections', action='store_true', help='give the model only the sections that answer each question')
    ap.add_argument('--codebook', action='store_true', help='give the decision rules of every tag (audit guide)')
    ap.add_argument('--examples', type=int, default=0, help='finished sheet answers from other studies to show')
    a = ap.parse_args()
    import sections
    qs = questions()
    rules = codebook() if a.codebook else {}
    folders = {p['key']: ROOT / p['folder'] for p in json.loads(cc.PAPERS.read_text())['papers']}
    outdir = HERE / 'data' / 'regenerated'
    outdir.mkdir(parents=True, exist_ok=True)
    report, totals = [], {'fields': 0, 'agree': 0, 'quotes': 0, 'on_page': 0, 'secs': 0.0, 'answers': 0, 'failed': 0}
    for key in a.keys:
        sheet = json.loads((SHEETS / f'{key}.json').read_text(encoding='utf-8'))
        text, pages = paper_text(folders[key])
        words = len(text.split())
        for q in a.questions:
            if q not in sheet['answers'] or q not in qs:
                continue
            title, allowed = qs[q]
            given, info = text, None
            if a.sections:
                given, info = sections.pick({n: '\n'.join(v) for n, v in pages.items()}, q)
            extra = ''
            if a.codebook and q in rules:
                extra += (f'\n\nDECISION RULES for these fields (follow them exactly): {rules[q]}\nFor list fields, give '
                          f'every value that applies, not only the main one.')
            if a.examples:
                for i, ex in enumerate(examples(q, set(a.keys) | set(HELD_BACK), a.examples), 1):
                    extra += f'\n\nEXAMPLE {i} (another study, answered by these rules): ' + json.dumps(ex, ensure_ascii=False)
            got, secs = ask(a.model, a.think, given, q, title, allowed, len(given.split()) + len(extra.split()), extra=extra,
                            progress=lambda th, an, s, key=key, q=q: print(
                                f'   {key} {q}: thinking… {th} tokens of thought, {an} of answer, {s:.0f} s', flush=True))
            totals['secs'] += secs
            if not isinstance(got, dict):
                totals['failed'] += 1
                print(f"{key} {q}: no usable JSON ({secs:.0f} s, {LAST.get('tokens', 0)} tokens written, "
                      f"ended: {LAST.get('reason')})", flush=True)
                continue
            (outdir / f'{key}-{q}.json').write_text(json.dumps(got, indent=1, ensure_ascii=False), encoding='utf-8')
            mine = sheet['answers'][q].get('values') or {}
            theirs = got.get('values') or {}
            field_res = []
            for f, v in mine.items():
                if f in FREE_TEXT:                         # free lists (defences, datasets, ...): shared words, not identity
                    w1, w2 = word_set(v), word_set(theirs.get(f, ''))
                    share = len(w1 & w2) / len(w1 | w2) if (w1 | w2) else 1.0
                    field_res.append((f, 'same' if share >= 0.6 else 'overlap' if share > 0 else 'differs'))
                    continue
                same = as_set(v) == as_set(theirs.get(f, ''))
                overlap = bool(as_set(v) & as_set(theirs.get(f, '')))
                field_res.append((f, 'same' if same else 'overlap' if overlap else 'differs'))
            ev = [e for e in (got.get('evidence') or []) if isinstance(e, dict)]
            ok = sum(on_page(str(e.get('quote', '')), int(e.get('page', 0) or 0), pages) for e in ev
                     if str(e.get('page', '')).isdigit())
            totals['fields'] += len(field_res)
            totals['agree'] += sum(r == 'same' for _, r in field_res)
            totals['vocab'] = totals.get('vocab', 0) + sum(f not in FREE_TEXT for f, _ in field_res)
            totals['vocab_same'] = totals.get('vocab_same', 0) + sum(f not in FREE_TEXT and r == 'same' for f, r in field_res)
            totals['vocab_overlap'] = totals.get('vocab_overlap', 0) + sum(f not in FREE_TEXT and r == 'overlap' for f, r in field_res)
            totals['quotes'] += len(ev)
            totals['on_page'] += ok
            totals['answers'] += 1
            print(f"{key} {q}: tags " + ', '.join(f'{f} {r}' for f, r in field_res)
                  + f" | quotations on their page {ok}/{len(ev)} | {secs:.0f} s, {LAST.get('thinking', 0)} tokens of thought"
                  + (f" | {info['mode']}: {info['pages_given']}/{info['pages_total']} pages, "
                     f"{info['words_given']}/{info['words_total']} words" if info else ''), flush=True)
            report.append((key, q, title, sheet['answers'][q], got, field_res, ok, len(ev)))
    t = totals
    print(f"\nvocabulary tags: identical {t.get('vocab_same', 0)}/{t.get('vocab', 0)}, partly {t.get('vocab_overlap', 0)}")
    print(f"{t['answers']} answers ({t['failed']} without usable JSON): all fields alike {t['agree']}/{t['fields']}; "
          f"quotations on their page {t['on_page']}/{t['quotes']}; {t['secs'] / 60:.1f} min")
    write_html(report)


def write_html(report):
    def vals(v):
        return html.escape(json.dumps(v, ensure_ascii=False))
    parts = ['<!doctype html><meta charset="utf-8"><title>Regenerated answers</title><style>body{font:14px/1.45 '
             '-apple-system,sans-serif;margin:20px;color:#222}table{border-collapse:collapse;width:100%}td,th{border:1px '
             'solid #ccc;padding:6px;vertical-align:top;width:50%}th{background:#f1f3f5}h2{margin-top:28px;font-size:16px}'
             '.q{color:#555;font-size:12px}.same{color:#2e7d32}.differs{color:#b71c1c}.overlap{color:#a15c00}</style>',
             '<h1>Evidence sheet vs local model, answer by answer</h1>']
    for key, q, title, sheet_ans, got, field_res, ok, n in report:
        parts.append(f'<h2>{key} {q} — {html.escape(title[:90])}</h2><p>Tags: ' + ', '.join(
            f'<span class="{r}">{f}: {r}</span>' for f, r in field_res) + f' · model quotations on their page: {ok}/{n}</p>')
        parts.append('<table><tr><th>Evidence sheet</th><th>Local model</th></tr><tr>'
                     f'<td>{html.escape(sheet_ans.get("answer", ""))}<p class="q">{vals(sheet_ans.get("values"))}</p>'
                     + ''.join(f'<p class="q">p{e.get("page")}: {html.escape(str(e.get("quote", "")))}</p>'
                               for e in sheet_ans.get('evidence') or [])
                     + f'</td><td>{html.escape(str(got.get("answer", "")))}<p class="q">{vals(got.get("values"))}</p>'
                     + ''.join(f'<p class="q">p{e.get("page")}: {html.escape(str(e.get("quote", "")))}</p>'
                               for e in got.get('evidence') or [] if isinstance(e, dict))
                     + '</td></tr></table>')
    out = HERE / 'show' / 'regenerated.html'
    out.parent.mkdir(exist_ok=True)
    out.write_text('\n'.join(parts), encoding='utf-8')
    print(f'side by side for the person: {out.relative_to(ROOT)}')


if __name__ == '__main__':
    main()
