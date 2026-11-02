#!/usr/bin/env python3
"""Install the reworded study paragraphs (search-ppml/evidence/style-v71/out/<id>.md) into myliteraturereviewpaper/ppml2026/
studies-v71/paragraphs.md, after mechanical checks on each: the design is cited once as [@id] and no other study is cited;
the markers' answer keys are the original paragraph's (none lost, none invented); 90 to 160 words; no banned word; no
judgement wording (claims, not tested, fails, merely, weak); every sentence with a number ends with a marker. A sentence
with a number and no marker is given one from the paragraph's own answer keys, when one of those answers states every
number in the sentence (the build then checks the sentence against that answer); the addition is logged. A paragraph that
still fails stays out, and the original is used in its place (listed). Usage:
python3 scripts/paper_ppml/install_paragraphs.py [--dry-run]
INSTALL_SRC=<folder of <id>.md> INSTALL_DEST=studies-v<n> PPML_STUDIES=myliteraturereviewpaper/ppml2026/studies-v<n-1> for a later version:
only the ids present in the source folder change; every other paragraph is taken from PPML_STUDIES unchanged (V81: three paragraphs).
"""
import json, os, pathlib, re, sys
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import build as BLD
ROOT = pathlib.Path(__file__).resolve().parents[2]
OUT = ROOT / os.environ.get('INSTALL_SRC', 'search-ppml/evidence/style-v71/out')   # INSTALL_SRC=search-ppml/evidence/style-v81/out: the reworded paragraphs of a later version (the others keep the paragraphs of PPML_STUDIES)
DEST = ROOT / 'myliteraturereviewpaper' / 'ppml2026' / os.environ.get('INSTALL_DEST', 'studies-v71')   # INSTALL_DEST=studies-v72 for the next version
BANNED = re.compile(r'\b(delv\w*|tapestr\w*|testament|paramount|leverag\w*|multifaceted|bolster\w*|furthermore|moreover|in conclusion)\b', re.I)
JUDGE = re.compile(r'\b(claims?|claimed|not tested|fails?|failed|merely|weak|poor|in name|neglect\w*|ignores?|sheet|reader|PhD|draft)\b'
                   r'|\b(?:the|its|their|our|a)\s+records?\b(?!\s+(?:on|to|of)\b)', re.I)   # "the record shows", not "providers record data"
MARK = re.compile(r'⟦([^⟧]+)⟧')
NUM = re.compile(r'(?<![A-Za-z0-9@])\d+(?:[.,]\d+)*')
SENT = re.compile(r'(?<=[.!?])\s+(?=[A-Z0-9(])')


def keys_of(text):
    out = set()
    for m in MARK.finditer(text):
        sid, _, ks = m.group(1).partition(':')
        out |= {f'{sid}:{k.strip()}' for k in ks.split(',')}
    return out


def nums(text):
    return {x.replace(',', '').rstrip('.') for x in NUM.findall(re.sub(r'\[@[\w-]+\]|⟦[^⟧]+⟧', '', text))}


def add_markers(k, new, keys):
    """Give every unmarked sentence with a number a marker from the paragraph's own keys; returns (text, log, unresolved)."""
    own = sorted({x.split(':', 1)[1] for x in keys if x.startswith(k + ':')})
    have = {key: {x.replace(',', '').rstrip('.') for x in BLD.NUM.findall(BLD.sheet_text(k, [key]))} for key in own}
    out, log, bad = [], [], []
    for s in SENT.split(new.strip()):
        need = nums(s)
        if need and not MARK.search(s):
            fit = [key for key in own if need <= have[key]]
            if fit:
                s = f'{s} ⟦{k}:{fit[0]}⟧'; log.append(f'{fit[0]}: {s[:70]}')
            elif need <= set().union(*have.values()):
                s = f'{s} ⟦{k}:{",".join(own)}⟧'; log.append(f'{",".join(own)}: {s[:70]}')
            else:
                bad.append(s[:60])
        out.append(s)
    return ' '.join(out), log, bad


def check(k, new, old):
    errs = []
    if new.count(f'[@{k}]') != 1: errs.append('the design is not cited exactly once')
    others = set(re.findall(r'\[@([\w-]+)\]', new)) - {k}
    if others: errs.append(f'cites other studies {sorted(others)}')
    ko = keys_of(old)
    new, log, bad = add_markers(k, new, ko)
    kn = keys_of(new)
    if ko - kn: errs.append(f'markers lost: {sorted(ko - kn)}')
    if kn - ko: errs.append(f'markers invented: {sorted(kn - ko)}')
    words = len(re.sub(r'⟦[^⟧]+⟧|\[@[\w-]+\]', '', new).split())
    if not 90 <= words <= 160: errs.append(f'{words} words')
    for m in BANNED.finditer(new): errs.append(f'banned word {m.group(0)}')
    for m in JUDGE.finditer(new): errs.append(f'judgement or process word "{m.group(0)}"')
    for s in bad: errs.append(f'a sentence with a number that no cited answer states: {s}…')
    return errs, words, new, log


def main(dry):
    S = BLD.studies()
    done, fallback, report, added = {}, [], [], {}
    for k in sorted(S):
        f = OUT / f'{k}.md'
        if not f.exists(): continue
        new = ' '.join(f.read_text(encoding='utf-8').split())
        errs, words, new, log = check(k, new, S[k])
        if errs:
            fallback.append(k); report.append(f'{k}: kept the original ({"; ".join(errs)})')
        else:
            done[k] = new; report.append(f'{k}: installed ({words} words{"; markers added: " + str(len(log)) if log else ""})')
            if log: added[k] = log
    if not dry:
        DEST.mkdir(exist_ok=True)
        text = '\n\n'.join(f'### {k}\n{done.get(k, S[k])}' for k in sorted(S))
        (DEST / 'paragraphs.md').write_text(text + '\n', encoding='utf-8')
        (DEST / 'INSTALLED.json').write_text(json.dumps({'installed': sorted(done), 'kept_original': fallback, 'markers_added': added}, indent=1, ensure_ascii=False), encoding='utf-8')
    print('\n'.join(report)); print(f'{len(done)} installed, {len(fallback)} kept the original{" (dry run)" if dry else ""}')


if __name__ == '__main__':
    main('--dry-run' in sys.argv)
