#!/usr/bin/env python3
"""Copies of a delivered version's files on the author's Desktop (the author, 16 October 2026: "whenever you build a new
version - please keep copies of docx files and pptx on desktop (copies not aliases)"). Copies, byte for byte, every file and
folder of the version (the paper, the author-checks copy, the figures-and-tables deck, the supporting document, the IEEE Access
renderings and the LaTeX folder: everything named "<NAME> - V<n>…") into ~/Desktop/PPML review/. A Desktop file that is newer
than its workspace source and differs from it is left alone (the author edits the Desktop copy); otherwise an earlier copy of the same name is
overwritten (a version's files never change once delivered). Run as the last step of every delivery.

Usage: python3 scripts/paper_ppml/deliver_copies.py <version>
"""
import filecmp, pathlib, shutil, sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
SRC = ROOT / 'myliteraturereviewpaper' / 'PPML in NextGeneration IoT'
NAME = 'Privacy Preserving Machine Learning in NextGeneration IoT'
DEST = pathlib.Path.home() / 'Desktop' / 'PPML review'


def main(version):
    DEST.mkdir(parents=True, exist_ok=True)
    done, kept = [], []
    for f in sorted(SRC.glob(f'{NAME} - V{version}*')):
        if f.name.startswith('~$'): continue
        target = DEST / f.name
        if f.is_dir():
            shutil.copytree(f, target, dirs_exist_ok=True); done.append(f.name + '/')
        elif target.exists() and target.stat().st_mtime > f.stat().st_mtime + 1 and not filecmp.cmp(f, target, shallow=False):
            kept.append(f.name)                                   # the author's edited copy stays (newer, and different)
        else:
            shutil.copy2(f, target); done.append(f.name)
    print(f'{len(done)} copies in {DEST}: ' + ', '.join(done) + (f'; left as edited by the author: {kept}' if kept else ''))


if __name__ == '__main__':
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    main(sys.argv[1])
