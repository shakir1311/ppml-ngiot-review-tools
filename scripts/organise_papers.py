#!/usr/bin/env python3
"""Keep the two review papers in two folders of myliteraturereviewpaper/ (the author's request of 4 October 2026).

  PPML in NextGeneration IoT/                        every version of "Privacy Preserving Machine Learning in NextGeneration
                                                     IoT" (V1 ... V28 and later), their author-check copies and linked copies
  Verifiable PPFL on Blockchains - Systematic Review/ every version of "Verifiable Privacy-Preserving FL on Blockchains -
                                                     Systematic Review", their author-check copies and linked copies

A file that Word has open (its "~$" lock file is present) is left where it is and reported; run again once it is
closed. A linked HTML copy gets its relative links to the corpus PDFs one level deeper ("../" -> "../../"). Every move
is appended to myliteraturereviewpaper/MOVES.json. The sources (_src/, slr2026/), the viewer and other files stay.

Usage: python3 scripts/organise_papers.py
"""
import datetime, json, pathlib, re, shutil

ROOT = pathlib.Path(__file__).resolve().parents[1]
D = ROOT / 'myliteraturereviewpaper'
FOLDERS = {
    'PPML in NextGeneration IoT': ('Privacy Preserving Machine Learning in NextGeneration IoT',
                                   'original for ref Privacy Preserving Machine Learning in NextGeneration IoT'),
    'Verifiable PPFL on Blockchains - Systematic Review': ('Verifiable Privacy-Preserving FL on Blockchains - Systematic Review',),
}


def locked(name):
    return any(p.name.startswith('~$') and p.name[2:] == name[2:] for p in D.iterdir())


def main():
    log_f = D / 'MOVES.json'
    log = json.loads(log_f.read_text(encoding='utf-8')) if log_f.exists() else []
    moved, skipped = 0, []
    for folder, prefixes in FOLDERS.items():
        (D / folder).mkdir(exist_ok=True)
        for p in sorted(D.iterdir()):
            if not p.is_file() or p.name.startswith('~$') or not p.name.startswith(prefixes):
                continue
            if locked(p.name):
                skipped.append(p.name)
                continue
            dest = D / folder / p.name
            if dest.exists():
                raise SystemExit(f'{dest} exists; nothing is overwritten')
            shutil.move(str(p), str(dest))
            if dest.suffix == '.html':                    # links to the corpus PDFs, one level deeper now
                t = dest.read_text(encoding='utf-8')
                t = re.sub(r'(href|src)="\.\./', r'\1="../../', t)
                dest.write_text(t, encoding='utf-8')
            log.append({'utc': datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds'),
                        'from': p.name, 'to': f'{folder}/{p.name}'})
            moved += 1
    log_f.write_text(json.dumps(log, indent=1, ensure_ascii=False), encoding='utf-8')
    print(f'moved {moved}; left in place because Word has them open: {skipped or "none"}')


if __name__ == '__main__':
    main()
