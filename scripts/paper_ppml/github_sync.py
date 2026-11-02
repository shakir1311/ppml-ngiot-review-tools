#!/usr/bin/env python3
"""The GitHub copy of the review's tools (the author, 2 November 2026: "all i wanted was the tools we developed not everything"):
syncs the tools of release/ppml-ngiot-review-tools-v<n>/ into the git clone release/github/<repo>/ (the scripts, the three
applications, the Review Viewer, the experiment harnesses and portal, the requirements, the licence, the citation file, the scripts
map; not the records, the paper's parts and build outputs, the foundation pages or the run artefacts, which stay in the Zenodo
archive), writes the repository's README with the DOI badge, a gallery of the apps' screenshots and the commands, commits
"Release v<n>", tags v<n>, pushes, and creates the GitHub release with the archive's zip attached. --fresh starts the history
again (used once, when the records were taken out). Creates the public repository on the first run (gh must be signed in).

Usage: python3 scripts/paper_ppml/github_sync.py <paper version> [--fresh]
"""
import json, pathlib, subprocess, sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
NAME = 'ppml-ngiot-review-tools'
OWNER = 'shakir1311'
URL = f'https://github.com/{OWNER}/{NAME}'
DESCRIPTION = ('The scripts, tools and records of the systematic review "Privacy Preserving Machine Learning in Next Generation IoT (NG-IoT) '
               'Security": search, screening, extraction records (tags only), the paper build and its checks, the local fact checker, the notes '
               'verifier, the PDF text extractor, and the first experiment. No paper text, no database export.')


def run(cmd, cwd=None, check=True):
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if check and r.returncode:
        sys.exit(f'{" ".join(cmd)}\n{r.stdout}\n{r.stderr}')
    return r.stdout.strip()


APPS = [('Notes Verifier', 'notes-verifier/docs/notes-verifier.png', 'a cited paper beside its notes and summary, to check and correct them', 'notes-verifier/README.md'),
        ('Evidence Verifier', 'notes-verifier/docs/evidence-verifier.png', "a study's evidence sheet against its notes, summary and PDF", 'notes-verifier/README.md'),
        ('Sheet Reviewer', 'notes-verifier/docs/sheet-reviewer.png', 'every fact of a sheet ticked against the PDF, with the quoted words outlined', 'notes-verifier/README.md'),
        ('Review Viewer', 'myliteraturereviewpaper/linked-app/docs/review-viewer.png', 'the review next to its sources: a citation opens the evidence, an evidence item opens the page', 'myliteraturereviewpaper/linked-app/README.md'),
        ('Screening application', 'scripts/search_ppml/docs/screening-app.png', 'title-and-abstract screening of the search records with a cue-word pre-fill, decisions logged', 'scripts/search_ppml/README.md'),
        ('PDF Text Extractor', 'pdf-text-extractor/docs/pdf-text-extractor.png', 'a folder of PDFs to per-page verified text, sections and figures (macOS and Windows)', 'pdf-text-extractor/README.md'),
        ('Experiments portal', 'experiments/portal/docs/portal.png', 'one local page to start, watch and read the experiments', 'experiments/README.md')]


def github_readme(version, doi):
    badge = f'[![DOI](https://zenodo.org/badge/DOI/{doi}.svg)](https://doi.org/{doi})\n\n' if doi else ''
    gallery = ''.join(f'### {name}\n\n{what}. See [{readme}]({readme}).\n\n![{name}]({img})\n\n' for name, img, what, readme in APPS)
    return f'''# The tools of the systematic review "Privacy Preserving Machine Learning in Next Generation IoT (NG-IoT) Security"

{badge}The scripts and applications built for the review, as used for version v{version} of the paper. Licence: MIT. Cite with CITATION.cff.
The records the review is built on (search provenance, screening decisions, extraction records with their tags, the paper's parts and build outputs,
the experiment run summaries) are archived with these tools at Zenodo: https://doi.org/{doi or "10.5281/zenodo.23895401"}. No paper text and no database export is published anywhere.

## What is here

| Folder | Tool |
|---|---|
| `scripts/paper_ppml/` | The paper pipeline: records to counts, tables and figures (`data.py`, `data_v68.py`, `experiment_v82.py`), the build (`build.py`), its checks (`verify_v68.py`, `check_claims_v68.py`, `style_check.py`, `claims_audit.py`), the local AI-text detection (`ai_detect_version.py`), the deck, the IEEE Access renderings, the release and deposit scripts. |
| `scripts/search_ppml/` | The recorded search: strings, merge of the exports, automated rules, the screening application. |
| `scripts/` | The extraction and OCR pipeline (`run_extraction.sh`, `verify_ocr.py`, `sections.py`, `check_extraction.py`). |
| `scripts/review/` | Shared primitives: the figure drawing, the Word look, the author checks, `app_screenshot.py`. |
| `local-checker/` | The local fact checker: statements against a paper's extracted text, on the machine (BM25 + a DeBERTa NLI classifier). |
| `notes-verifier/` | The Notes Verifier, the Evidence Verifier and the Sheet Reviewer (PySide6). |
| `myliteraturereviewpaper/linked-app/` | The Review Viewer. |
| `pdf-text-extractor/` | The PDF Text Extractor, a desktop app for macOS and Windows. |
| `experiments/` | The harnesses and environment recipes of the first experiment, and the portal. |
| `requirements/` | Pinned package lists of the environments the review ran with. `Docs/SCRIPTS-MAP.html` maps every script to the part of the paper it serves. |

Each folder has a README with the commands. Prerequisites: Python 3.12 or later; pandoc (the paper build); Google Chrome (the figures); TeX Live (the LaTeX rendering, optional); Tesseract (second OCR engine, optional); macOS for the Apple Vision OCR; Docker (the experiments).

## The applications

{gallery}Screenshots were taken by `scripts/review/app_screenshot.py` on the review's real records; where a paper is shown it is Shawkat et al. 2025, published under CC BY 4.0.
'''


def main(version):
    pkg = ROOT / 'release' / f'{NAME}-v{version}'
    zpath = pkg.with_suffix('.zip')
    clone = ROOT / 'release' / 'github' / NAME
    clone.parent.mkdir(parents=True, exist_ok=True)
    zen_f = ROOT / 'release' / f'ZENODO-V{version}.json'
    zen = json.loads(zen_f.read_text(encoding='utf-8')) if zen_f.exists() else {}
    doi = zen.get('doi')
    fresh = '--fresh' in sys.argv
    if fresh and (clone / '.git').exists():
        import shutil
        shutil.rmtree(clone / '.git')
    if not (clone / '.git').exists():
        clone.mkdir(exist_ok=True)
        run(['git', 'init', '-b', 'main'], cwd=clone)
    excludes = ['.git', 'search-ppml', 'myliteraturereviewpaper/ppml2026/parts-*', 'myliteraturereviewpaper/ppml2026/studies-*', 'myliteraturereviewpaper/ppml2026/build',
                'myliteraturereviewpaper/ppml2026/refs.json', 'Regulatory', 'foundations', 'experiments/*/runs', 'experiments/COMMITS.json', 'MANIFEST.json', 'EXCLUSIONS.md', '.zenodo.json']
    run(['rsync', '-a', '--delete'] + [x for e in excludes for x in ('--exclude', e)] + [f'{pkg}/', f'{clone}/'])
    import shutil
    for pat in excludes[1:]:                                              # what the sync leaves out is also removed from the clone (openrsync honours no protect filter)
        for hit in clone.glob(pat):
            shutil.rmtree(hit) if hit.is_dir() else hit.unlink()
    (clone / 'README.md').write_text(github_readme(version, doi), encoding='utf-8')
    (clone / '.gitattributes').write_text('*.png binary\n*.pptx binary\n', encoding='utf-8')
    run(['git', 'add', '-A'], cwd=clone)
    if run(['git', 'status', '--porcelain'], cwd=clone):
        run(['git', 'commit', '-q', '-m', f'Release v{version}' + (f' (Zenodo DOI {doi})' if doi else '')], cwd=clone)
    exists = subprocess.run(['gh', 'repo', 'view', f'{OWNER}/{NAME}'], capture_output=True, text=True).returncode == 0
    if not exists:
        run(['gh', 'repo', 'create', f'{OWNER}/{NAME}', '--public', '--description', DESCRIPTION, '--source', str(clone), '--remote', 'origin', '--push'])
        run(['gh', 'repo', 'edit', f'{OWNER}/{NAME}', '--add-topic', 'systematic-review', '--add-topic', 'federated-learning', '--add-topic', 'blockchain',
             '--add-topic', 'privacy-preserving-machine-learning', '--add-topic', 'internet-of-things', '--add-topic', 'prisma'])
    else:
        if not run(['git', 'remote'], cwd=clone):
            run(['git', 'remote', 'add', 'origin', f'{URL}.git'], cwd=clone)
        run(['git', 'push', '-u', 'origin', 'main'] + (['--force'] if fresh else []), cwd=clone)
    tag = f'v{version}'
    if fresh:
        subprocess.run(['gh', 'release', 'delete', tag, '-R', f'{OWNER}/{NAME}', '--yes', '--cleanup-tag'], capture_output=True, text=True)
        subprocess.run(['git', 'tag', '-d', tag], cwd=clone, capture_output=True, text=True)
    if tag not in run(['git', 'tag', '--list'], cwd=clone).split():
        run(['git', 'tag', '-a', tag, '-m', f'Release {tag}'], cwd=clone)
    run(['git', 'push', 'origin', tag] + (['--force'] if fresh else []), cwd=clone)
    has_release = subprocess.run(['gh', 'release', 'view', tag, '-R', f'{OWNER}/{NAME}'], capture_output=True, text=True).returncode == 0
    if not has_release:
        notes = f'The tools as used for version v{version} of the paper; the full archive with the records is on Zenodo' + (f': https://doi.org/{doi}' if doi else '') + '. The attached zip is that archive.'
        run(['gh', 'release', 'create', tag, str(zpath), '-R', f'{OWNER}/{NAME}', '--title', f'Release {tag}', '--notes', notes])
    print(f'{URL} | tag {tag} | release with {zpath.name}')


if __name__ == '__main__':
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    main(sys.argv[1])
