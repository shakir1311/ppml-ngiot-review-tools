#!/usr/bin/env python3
"""Step B of aligning the summaries and notes with the corrected evidence sheets (12 October 2026). Records only: reads
the sheets, the correction log (sheet-fix/APPLIED.jsonl), the earlier sheets-vs-notes readings and each study's
notes/SUMMARY.md and notes/NOTES.md — never the paper.

- Summaries (the priority): every sentence of every summary goes into the packet, beside the corrected sheet's answers,
  so that each summary can be made to agree with its sheet as a whole.
- Notes (only what is easy to find): a notes sentence is flagged when
    (a) it is a point the earlier sheets-vs-notes reading graded "differs" or "conflicts", or
    (b) it shares at least SHARE of the content words of a sheet sentence that the correction pass removed or changed
        (the old version may have come from the notes),
  leaving out lines that only quote the paper ([pN] "…"). The local NLI model (local-checker, DeBERTa, pinned) then
  compares each with the corrected answer: (a) stays unless the corrected answer supports it (entailment >= ENTAIL);
  (b) stays only if the corrected answer contradicts it (contradiction >= CONTRADICT).

Writes search-ppml/evidence/sheet-fix/align/FLAGS.json and align/packets/<key>.md.
Run with the local checker's Python:  local-checker/.venv/bin/python scripts/paper_ppml/summary_notes_flags.py [key ...]
"""
import json
import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import check_sheets as cs

ROOT = cs.ROOT
sys.path.insert(0, str(ROOT / 'local-checker'))
os.environ.setdefault('HF_HOME', str(ROOT / 'local-checker' / '.cache' / 'huggingface'))
os.environ.setdefault('TOKENIZERS_PARALLELISM', 'false')
import check_claims as cc

FIX = ROOT / 'search-ppml' / 'evidence' / 'sheet-fix'
OUT = FIX / 'align'
VERDICTS = ROOT / 'search-ppml' / 'evidence' / 'sheets-vs-notes' / 'verdicts'
SHARE = 0.6            # content-word share of a removed sheet sentence that a notes sentence must hold
ENTAIL = 0.8           # the corrected answer supports the notes sentence: not flagged
CONTRADICT = 0.5       # a sentence found by likeness alone is flagged only if the corrected answer contradicts it
QUOTE_ONLY = re.compile(r'^[\s\-*]*(\[p\d+\]\s*"[^"]*"?\s*)+$')
SPLIT = re.compile(r'(?<=[.!?;])\s+(?=[A-Z(\[])')
ABBREVIATION = re.compile(r'(?:\b(?:Fig|Figs|Eq|Eqs|Sec|Secs|Ref|Refs|Tab|No|Nos|vs|al|e\.g|i\.e|cf|approx)\.)$', re.I)


def sentences(text, least=5):
    out = []
    for line in text.splitlines():
        parts = []
        for s in SPLIT.split(line):
            if parts and ABBREVIATION.search(parts[-1]):               # "Fig. 6", "et al. [12]": one sentence
                parts[-1] += ' ' + s
            else:
                parts.append(s)
        out += parts
    return [s.strip() for s in out if len(s.split()) >= least]


def content(s):
    return {cc.stem(w) for w in cc.words_of(s) if len(w) >= 4 and w not in cc.STOP and not w.isdigit()}


def corrections():
    """(key, q) -> (answer before the first correction, answer after the last, every reason given)."""
    out = {}
    for line in (FIX / 'APPLIED.jsonl').read_text(encoding='utf-8').splitlines():
        r = json.loads(line)
        k = (r['key'], r['q'])
        before, _, whys = out.get(k, (r['before'], None, []))
        out[k] = (before, r['after'], whys + [r.get('why', '')])
    return out


def earlier_points(key):
    f = VERDICTS / f'{key}.json'
    if not f.exists():
        return []
    d = json.loads(f.read_text(encoding='utf-8'))
    return [(q, p) for q, a in d['answers'].items() for p in a.get('points', [])
            if p['status'] in ('differs', 'conflicts') and p.get('notes')]


def opening(quote, words=15):
    """The start of a sheet quotation: enough to tell which fact a page supports."""
    w = str(quote).split()
    return ' '.join(w[:words]) + (' …' if len(w) > words else '')


def values_text(v):
    return '; '.join(f"{f}: {', '.join(map(str, x)) if isinstance(x, list) else x}" for f, x in (v or {}).items())


def main():
    keys = sys.argv[1:] or sorted(p.stem for p in cs.SHEETS.glob('*.json'))
    fixes = corrections()
    verifier = cc.Verifier()
    (OUT / 'packets').mkdir(parents=True, exist_ok=True)
    flags = {}
    for key in keys:
        sheet = json.loads((cs.SHEETS / f'{key}.json').read_text(encoding='utf-8'))
        notes_dir = cs.folder_of(key) / 'notes'
        summary = sentences((notes_dir / 'SUMMARY.md').read_text(encoding='utf-8', errors='ignore'), least=1)
        notes = [s for s in sentences((notes_dir / 'NOTES.md').read_text(encoding='utf-8', errors='ignore'))
                 if not QUOTE_ONLY.match(s)]
        notes_content = [content(s) for s in notes]
        candidates = {}                                   # notes sentence index -> {q, reasons}
        for (k, q), (before, after, whys) in fixes.items():
            if k != key:
                continue
            kept = {cc.squashed(s) for s in sentences(after.get('answer', ''))}
            for old in sentences(before.get('answer', '')):
                oc = content(old)
                if cc.squashed(old) in kept or len(oc) < 4:
                    continue
                for i, nc in enumerate(notes_content):
                    if nc and len(oc & nc) / len(oc) >= SHARE:
                        candidates.setdefault(i, {'q': q, 'why': [], 'earlier': False})['why'].append(
                            f'like the removed sheet sentence: "{old}"')
        for q, p in earlier_points(key):
            if p['where'] != 'notes':
                continue
            for i, s in enumerate(notes):
                if cs.found(p['notes'], s) or cs.found(s, p['notes']):
                    c = candidates.setdefault(i, {'q': q, 'why': [], 'earlier': False})
                    c['earlier'] = True
                    c['why'].insert(0, f"earlier reading: {p['status']} — {p.get('fix') or p.get('sheet')}")
        flagged = []
        for i, c in sorted(candidates.items()):
            answer = sheet['answers'][c['q']]
            premise = answer.get('answer', '') + ' ' + values_text(answer.get('values'))
            entail, contra = verifier.score([premise], notes[i])[0]
            if entail >= ENTAIL or (not c['earlier'] and contra < CONTRADICT):
                continue
            flagged.append({'n': i + 1, 'q': c['q'], 'sentence': notes[i], 'why': c['why'][:2],
                            'entail': round(entail, 2), 'contradict': round(contra, 2)})
        summary_points = [(q, p) for q, p in earlier_points(key) if p['where'] == 'summary']
        flags[key] = {'summary_sentences': len(summary), 'notes_flagged': len(flagged),
                      'notes_candidates': len(candidates), 'notes': flagged}
        write_packet(key, sheet, summary, summary_points, flagged, fixes)
        print(f'{key}: summary {len(summary)} sentences · notes {len(candidates)} candidates, {len(flagged)} flagged',
              flush=True)
    (OUT / 'FLAGS.json').write_text(json.dumps(flags, indent=1, ensure_ascii=False), encoding='utf-8')
    print(f"\n{len(flags)} studies · summary sentences {sum(f['summary_sentences'] for f in flags.values())} · "
          f"notes flagged {sum(f['notes_flagged'] for f in flags.values())} "
          f"(of {sum(f['notes_candidates'] for f in flags.values())} candidates)")


def write_packet(key, sheet, summary, summary_points, flagged, fixes):
    out = [f'# {key} — align the summary (and flagged notes sentences) with the corrected evidence sheet', '',
           '## The corrected evidence sheet (the authority)', '']
    corrected = [(q, whys) for (k, q), (_, _, whys) in fixes.items() if k == key]
    for q, a in sheet['answers'].items():
        out += [f'**{q}** {a.get("answer", "").strip()}', f'_values_: {values_text(a.get("values"))}']
        evidence = [e for e in a.get('evidence') or [] if isinstance(e, dict)]
        if q in {c for c, _ in corrected}:                 # facts that changed: their quotations, for the page cites
            out += [f'  - p{e.get("page")}: "{opening(e.get("quote"))}"' for e in evidence]
        else:
            out += ['_pages_: ' + ', '.join(sorted({str(e.get('page')) for e in evidence}, key=lambda x: (len(x), x)))]
        out += ['']
    if corrected:
        out += ['## What the correction pass changed in the sheet (reasons)', '']
        out += [f'- **{q}**: ' + ' / '.join(w for w in whys if w) for q, whys in sorted(corrected)]
        out += ['']
    out += ['## SUMMARY.md — every sentence', '']
    out += [f'S{i}. {s}' for i, s in enumerate(summary, 1)] + ['']
    if summary_points:
        out += ['Earlier reading (sheets vs notes) found these summary points differing from the sheet as it was then:', '']
        out += [f'- {q}: "{p["notes"]}" — {p["status"]}: {p.get("fix") or p.get("sheet")}' for q, p in summary_points]
        out += ['']
    if flagged:
        out += ['## NOTES.md — flagged sentences only', '']
        for f in flagged:
            out += [f'N{f["n"]} ({f["q"]}). {f["sentence"]}'] + [f'   - flagged: {w}' for w in f['why']] + ['']
    (OUT / 'packets' / f'{key}.md').write_text('\n'.join(out), encoding='utf-8')


if __name__ == '__main__':
    main()
