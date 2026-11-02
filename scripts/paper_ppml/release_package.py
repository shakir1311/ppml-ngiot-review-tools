#!/usr/bin/env python3
"""The public release of the review's scripts, tools and records for a Zenodo deposit (the author, 2 November 2026: "make sure
all scripts/tools are self contained (i.e someone should be able to download them and run them)"; licence MIT; the extraction
records with their tags, without the papers' quotations).

Builds release/ppml-ngiot-review-tools-v<n>/ (and its zip) from an allowlist: the scripts of every pipeline, the three apps
(local checker, notes verifier, PDF text extractor) without their environments, the experiment harnesses with their run
summaries and the upstream commits (not the clones, the data sets or the circuits), the search records with every abstract,
keyword and quotation removed, the paper's parts, build outputs and figures, the scripts map, a README with the prerequisites
and the commands, requirements files read from the working environments, the MIT licence, CITATION.cff and .zenodo.json with the
author's ORCID, a MANIFEST with the SHA-256 of every file, and EXCLUSIONS.md saying what stayed out and why. Nothing from the
papers (PDFs, extracted text, quotations, abstracts) and nothing from the database exports (publishers' terms) goes in; a final
scan refuses the build if a PDF, an extracted-text folder or a quotation field is found.

Usage: python3 scripts/paper_ppml/release_package.py <paper version> [--rebuild]        e.g. 86
"""
import csv, datetime, hashlib, json, pathlib, re, shutil, subprocess, sys, zipfile

ROOT = pathlib.Path(__file__).resolve().parents[2]
NAME = 'ppml-ngiot-review-tools'
AUTHOR = {'name': 'Zareen, Shakir', 'orcid': '0009-0005-2841-4373', 'affiliation': 'Abertay University, Dundee, U.K.'}
TITLE = 'Privacy-preserving machine learning in next-generation IoT security: the scripts, tools and records of the systematic review'
DROP_KEYS = {'quote', 'quotes', 'quotation', 'quotations', 'abstract', 'keywords', 'excerpt', 'passage'}
DROP_COLS = {'abstract', 'keywords', 'evidence', 'quote', 'quotation'}
SKIP_DIRS = {'secrets', '.venv', 'venv', 'env', 'node-env', 'node_modules', '__pycache__', '.git', 'history', 'originals', 'repo', 'data', 'paper', 'papers',
             'sources', 'qa6', 'ptau', 'tmp', 'ieee-access-template', 'author-rewrite-V85', 'author-rewrite-V86'}
SKIP_SUFFIX = {'.pdf', '.pth', '.onnx', '.pk', '.zkey', '.wasm', '.sym', '.sol', '.js', '.log', '.pid', '.pyc', '.ptau', '.r1cs'}
MAX_RUN_FILE = 250_000                      # run artefacts above this size (bytes) stay out; summaries are small
RECORD_FILES = {'README.md', 'SEARCH-LOG.md', 'SCREENING-GUIDE-2026-10-04.md', 'COVERAGE-2026-10-04.md', 'MERGE-CHECK-2026-10-04.json', 'SIZE-PROBE-2026-10-04.json',
                'PRIMARY-COVERAGE-2026-10-04.json', 'CORPUS-PRIMARY-METADATA-2026-10-04.json', 'CORPUS-SURVEYS-METADATA-2026-10-04.json',
                'MERGED-RECORDS-2026-10-04.csv', 'AUTHOR-DECISIONS-2026-10-04.csv', 'AUTHOR-FULLTEXT-2026-10-05.csv', 'CHECK-DECISIONS-2026-10-05.csv',
                'PREFILL-2026-10-04.csv', 'OTHER-METHODS-2026-10-04.csv', 'INCLUDED-STUDIES-2026-10-04.csv', 'FINAL-STUDIES-2026-10-05.csv',
                'KNOWN-SURVEYS-2026-10-04.csv', 'CORPUS-COVERAGE-2026-10-04.csv', 'CORPUS-INDEX-2026-10-04.csv', 'CORPUS-MATCHES-2026-10-04.csv',
                'CORRECTIONS-2026-10-05.csv', 'CORRECTIONS-V2-2026-10-05.csv'}     # the record files of search-ppml/ that go in (abstracts, keywords, quotations stripped)
PKG_PATTERNS = ('python-docx', 'python-pptx', 'lxml', 'pymupdf', 'PyMuPDF', 'numpy', 'pillow', 'Pillow', 'pyobjc', 'torch', 'transformers', 'rank-bm25',
                'rank_bm25', 'scipy', 'sentencepiece', 'tokenizers', 'safetensors', 'accelerate', 'tqdm', 'PySide6', 'pytesseract', 'matplotlib', 'requests',
                'huggingface', 'pandas', 'scikit-learn', 'rapidfuzz', 'fastapi', 'flask', 'uvicorn', 'python-pptx', 'openpyxl')


def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


NUM = re.compile(r'(?<![A-Za-z0-9])\d+(?:[.,]\d+)*')


def strip_json(obj):
    """the object without any key that would carry a paper's words; a quotation leaves only its numbers behind, so that the
    build's check that every number of a study sentence occurs in the cited evidence still runs"""
    if isinstance(obj, dict):
        out = {k: strip_json(v) for k, v in obj.items() if k not in DROP_KEYS}
        if isinstance(obj.get('quote'), str):
            out['numbers'] = ' '.join(NUM.findall(obj['quote']))
        return out
    if isinstance(obj, list):
        return [strip_json(x) for x in obj]
    return obj


def copy_tree(src, dst, keep=None, run_summaries=False):
    """copy src into dst, leaving out the environments, caches, clones, data sets, papers and large artefacts"""
    n = 0
    for p in sorted(src.rglob('*')):
        rel = p.relative_to(src)
        if any(part in SKIP_DIRS or part.startswith('.') or part.startswith('history-') for part in rel.parts):
            # an experiment's env/ folder holds the harness and the image recipe, not a virtual environment: its code goes in
            harness = (src.name == 'experiments' and len(rel.parts) == 3 and rel.parts[1] == 'env'      # files directly in env/, nothing beneath it
                       and (p.suffix in ('.py', '.sh', '.md', '.txt') or p.name.startswith('Dockerfile')))
            if not harness:
                continue
        if p.is_dir():
            continue
        if (p.suffix.lower() in SKIP_SUFFIX and not (p.suffix == '.log' and 'runs' in rel.parts)) or p.name.startswith('~$') or p.name == 'CREDENTIALS.md':
            continue
        if keep and not keep(rel):
            continue
        if run_summaries and 'runs' in rel.parts and p.stat().st_size > MAX_RUN_FILE:
            continue
        out = dst / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        if p.suffix == '.json' and 'search-ppml' in str(src):
            out.write_text(json.dumps(strip_json(json.loads(p.read_text(encoding='utf-8'))), indent=1, ensure_ascii=False), encoding='utf-8')
        elif p.suffix == '.jsonl' and 'search-ppml' in str(src):
            lines = [json.dumps(strip_json(json.loads(l)), ensure_ascii=False) for l in p.read_text(encoding='utf-8').splitlines() if l.strip()]
            out.write_text('\n'.join(lines) + '\n', encoding='utf-8')
        elif p.suffix == '.csv' and 'search-ppml' in str(src):
            csv.field_size_limit(10 ** 9)
            with open(p, encoding='utf-8', newline='') as f:
                r = csv.DictReader(f)
                cols = [c for c in r.fieldnames if c.lower() not in DROP_COLS]
                rows = [{c: row[c] for c in cols} for row in r]
            with open(out, 'w', encoding='utf-8', newline='') as f:
                w = csv.DictWriter(f, fieldnames=cols)
                w.writeheader()
                w.writerows(rows)
        else:
            shutil.copy2(p, out)
        n += 1
    return n


def requirements(out):
    """one requirements file per working environment, pinned to what the review ran with"""
    req = out / 'requirements'
    req.mkdir(exist_ok=True)
    for env, name in (('scripts/.venv', 'scripts.txt'), ('local-checker/.venv', 'local-checker.txt'), ('notes-verifier/.venv', 'notes-verifier.txt')):
        pip = ROOT / env / 'bin' / 'pip'
        if not pip.exists():
            continue
        frozen = subprocess.run([str(pip), 'freeze'], capture_output=True, text=True).stdout.splitlines()
        lines = [l for l in frozen if any(l.lower().startswith(k.lower()) for k in PKG_PATTERNS)]
        (req / name).write_text('\n'.join(lines) + '\n', encoding='utf-8')
    toml = ROOT / 'pdf-text-extractor' / 'pyproject.toml'
    if toml.exists():
        shutil.copy2(toml, req / 'pdf-text-extractor.pyproject.toml')


def upstream_commits(out):
    """the experiment clones as URL and commit, since the clones themselves stay out"""
    lines = ['# Upstream repositories of the experiments (cloned at these commits; not redistributed here)', '']
    for sub in ('fl-bc-ids', 'fl-bc-ids-attacks', 'zkpet'):
        repo = ROOT / 'experiments' / sub / 'repo'
        if not (repo / '.git').exists():
            continue
        url = subprocess.run(['git', '-C', str(repo), 'remote', 'get-url', 'origin'], capture_output=True, text=True).stdout.strip()
        commit = subprocess.run(['git', '-C', str(repo), 'rev-parse', 'HEAD'], capture_output=True, text=True).stdout.strip()
        diff = subprocess.run(['git', '-C', str(repo), 'diff', 'HEAD'], capture_output=True, text=True).stdout
        lines.append(f'- experiments/{sub}/repo: {url} at {commit}' + (' (local changes in the patch beside this file)' if diff.strip() else ' (unchanged)'))
        if diff.strip():
            (out / 'experiments' / sub / 'repo.patch').write_text(diff, encoding='utf-8')
    (out / 'experiments' / 'UPSTREAM.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')


def scan(out):
    """refuse the package if anything of the papers, or a credential, slipped in"""
    bad = []
    secrets = [f.read_text(encoding='utf-8').strip() for f in (ROOT / 'secrets').glob('*') if f.is_file()] if (ROOT / 'secrets').exists() else []
    for p in out.rglob('*'):
        if p.is_file() and (p.name == 'CREDENTIALS.md' or 'secrets' in p.parts):
            bad.append(str(p.relative_to(out)) + ' (credentials)')
        elif p.is_file() and p.suffix in ('.md', '.txt', '.py', '.json', '.jsonl', '.csv', '.sh', '.html', '.cff', '.toml', '.tsv'):
            txt = p.read_text(encoding='utf-8', errors='ignore')
            if any(s and s in txt for s in secrets):
                bad.append(str(p.relative_to(out)) + ' (a token)')
    for p in out.rglob('*'):
        if p.is_dir():
            continue
        if p.suffix.lower() == '.pdf' or ('pages' in p.parts and p.suffix == '.txt' and p.name.startswith('page_') and not any(x in p.parts for x in ('foundations', 'Regulatory'))) or p.name.startswith('ABSTRACTS-'):
            bad.append(str(p.relative_to(out)))
        if p.suffix in ('.md', '.csv') and 'search-ppml' in p.parts and p.stat().st_size > 3_000_000:
            bad.append(str(p.relative_to(out)) + ' (too large for a record file)')
        if p.suffix in ('.json', '.jsonl') and 'search-ppml' in p.parts:
            txt = p.read_text(encoding='utf-8', errors='ignore')
            if re.search(r'"(quote|quotes|quotation|abstract)"\s*:', txt):
                bad.append(str(p.relative_to(out)))
    return bad


def main(version):
    out = ROOT / 'release' / f'{NAME}-v{version}'
    if out.exists() and '--rebuild' in sys.argv:
        shutil.rmtree(out); out.with_suffix('.zip').unlink(missing_ok=True)
    if out.exists():
        sys.exit(f'{out} exists; a release is never overwritten (--rebuild replaces it)')
    out.mkdir(parents=True)
    counts = {}
    counts['scripts'] = copy_tree(ROOT / 'scripts', out / 'scripts')
    counts['local-checker'] = copy_tree(ROOT / 'local-checker', out / 'local-checker')
    counts['notes-verifier'] = copy_tree(ROOT / 'notes-verifier', out / 'notes-verifier', keep=lambda r: r.parts[0] != 'Notes Verifier.app')
    counts['pdf-text-extractor'] = copy_tree(ROOT / 'pdf-text-extractor', out / 'pdf-text-extractor')
    counts['experiments'] = copy_tree(ROOT / 'experiments', out / 'experiments', run_summaries=True,
                                      keep=lambda r: not (len(r.parts) > 1 and r.parts[1] == 'env' and r.name in ('IMAGE_BUILT', 'build.log')))
    upstream_commits(out)
    # the search and extraction records, sanitised: no abstract, no keywords, no quotation
    sp = ROOT / 'search-ppml'
    # every record file the pipeline's scripts name (found in their code) joins the explicit list, so a new version cannot leave one out
    named = set()
    for py in (ROOT / 'scripts' / 'paper_ppml').glob('*.py'):
        named.update(re.findall(r"'([A-Za-z0-9_-]+\.(?:csv|json|jsonl|md|tsv))'", py.read_text(encoding='utf-8', errors='ignore')))
    wanted = RECORD_FILES | {n for n in named if not n.startswith('ABSTRACTS-')}
    counts['search-ppml'] = copy_tree(sp, out / 'search-ppml', keep=lambda r: len(r.parts) == 1 and (r.name in wanted or r.name.startswith('CRITERIA-')))
    counts['search-ppml'] += copy_tree(sp / 'evidence' / 'sheets', out / 'search-ppml' / 'evidence' / 'sheets')
    counts['search-ppml'] += copy_tree(sp / 'evidence', out / 'search-ppml' / 'evidence',
                                       keep=lambda r: (r.parts[0] in ('QA-CONSISTENCY-2026-10-05.json', 'regulation-search', 'rescreen', 'overlap'))
                                       or (r.parts[0] == 'checks' and (r.name in ('CHECKS-RESULT-2026-10-05.json', 'NOT-RETRIEVED-2026-10-05.json') or r.name.startswith('fulltext-')))
                                       or (r.parts[0] == 'sheet-fix' and 'packets' not in r.parts and ((r.suffix == '.json' and 'results' in r.parts) or (len(r.parts) == 2 and r.suffix in ('.json', '.jsonl')))))
    counts['search-ppml'] += copy_tree(sp / 'exports', out / 'search-ppml' / 'exports', keep=lambda r: r.suffix == '.tsv')
    # the paper: parts, study paragraphs, build outputs, icons, references
    pp = ROOT / 'myliteraturereviewpaper' / 'ppml2026'
    counts['paper'] = copy_tree(pp, out / 'myliteraturereviewpaper' / 'ppml2026',
                                keep=lambda r: r.parts[0] in (f'parts-v{version}', 'studies-v81', 'build', 'icons', 'refs.json') and not r.name.startswith(('AI-DETECT', 'LINKS-')))
    refs = json.loads((pp / 'refs.json').read_text(encoding='utf-8'))
    counts['foundations'] = 0
    for key in ('edpb2026', 'gdpr2016', 'page2021'):
        folder = refs.get(key, {}).get('folder')
        if folder and (ROOT / folder / 'text' / 'pages').exists():
            counts['foundations'] += copy_tree(ROOT / folder / 'text' / 'pages', out / folder / 'text' / 'pages')
    counts['review-viewer'] = copy_tree(ROOT / 'myliteraturereviewpaper' / 'linked-app', out / 'myliteraturereviewpaper' / 'linked-app',
                                        keep=lambda r: r.suffix in ('.py', '.md', '.png', '.sh', '.txt') and '.cache' not in r.parts)
    (out / 'Docs').mkdir()
    shutil.copy2(ROOT / 'Docs' / 'SCRIPTS-MAP.html', out / 'Docs' / 'SCRIPTS-MAP.html')
    requirements(out)
    year = datetime.date.today().year
    (out / 'LICENSE').write_text(f'''MIT License

Copyright (c) {year} Shakir Zareen

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Software"), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
''', encoding='utf-8')
    (out / 'CITATION.cff').write_text(f'''cff-version: 1.2.0
message: "If you use these scripts, tools or records, please cite them as below."
title: "{TITLE}"
authors:
  - family-names: Zareen
    given-names: Shakir
    orcid: "https://orcid.org/{AUTHOR['orcid']}"
    affiliation: "{AUTHOR['affiliation']}"
version: "v{version}"
date-released: "{datetime.date.today().isoformat()}"
license: MIT
''', encoding='utf-8')
    (out / '.zenodo.json').write_text(json.dumps({
        'title': TITLE, 'upload_type': 'software', 'license': 'MIT', 'version': f'v{version}',
        'creators': [{'name': AUTHOR['name'], 'orcid': AUTHOR['orcid'], 'affiliation': AUTHOR['affiliation']}],
        'keywords': ['systematic review', 'privacy-preserving machine learning', 'federated learning', 'blockchain', 'Internet of Things', 'PRISMA 2020'],
        'description': ('The scripts, tools and records behind the systematic review "Privacy Preserving Machine Learning in Next Generation IoT (NG-IoT) Security": '
                        'the search strings and provenance, the screening and eligibility decisions, the extraction records with their tags (each quotation of a paper replaced by the numbers it held), '
                        'the scripts that compute every count, table and figure, the paper build and its checks, the local fact checker, the notes verifier, the PDF text extractor, '
                        'and the harnesses and run summaries of the first experiment. No paper text and no database export is included.')}, indent=1), encoding='utf-8')
    (out / 'EXCLUSIONS.md').write_text('''# What is not in this package, and why

- **The papers**: no PDF, no extracted text, no page image, no quotation. The publishers' terms of use (IEEE Xplore, Elsevier, Wiley, Springer) forbid redistribution. The extraction records keep every tag, page number and the review's own answers; each `quote` field is replaced by `numbers`, the numbers the quotation held, which is what the build's number check reads.
- **The database exports** (Scopus, IEEE Xplore, ScienceDirect) and every abstract and keyword list of a record: licence terms. The provenance file keeps each export's SHA-256, record count and date, so an export can be checked against it.
- **Environments, caches and models**: the virtual environments, the Docker images, the circuits, keys and trained models of the experiment runs, and the language models the local checker downloads. The requirements files and the READMEs say how to recreate them.
- **The experiment clones and data sets**: FL-BC-IDS and zkPET are cloned at the commits in `experiments/UPSTREAM.md` (MIT licences); CICIoV2024 comes from its publisher.
- **Included on purpose**: the extracted pages of the three public documents the review cites outside the included studies (the GDPR, the EDPB guidelines 02/2025 on blockchains, the PRISMA 2020 statement): EU documents may be reused with the source acknowledged, and the PRISMA 2020 statement is published under CC BY 4.0. The build's foundation markers read those pages.
- **The IEEE Access templates** (Word and LaTeX class): the journal's files, from its author page.
- **Working history**: superseded script versions, audit packets, plans and author checks.
- **Credentials**: the workspace's credentials record and the `secrets/` folder; the packager refuses a package that carries either.
''', encoding='utf-8')
    (out / 'README.md').write_text(f'''# {TITLE}

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.23895401.svg)](https://doi.org/10.5281/zenodo.23895401)

Version v{version} of the package, built on {datetime.date.today().isoformat()} from the review's workspace. Repository: https://github.com/shakir1311/ppml-ngiot-review-tools (every version a tag and a release); archive: Zenodo record 10.5281/zenodo.23895401, one DOI per version. Licence: MIT (see LICENSE). Cite with CITATION.cff.

## What is here

| Folder | What it holds |
|---|---|
| `scripts/` | Every script of the review: the search (`search_ppml/`), the PDF extraction and OCR pipeline (`run_extraction.sh`, `verify_ocr.py`, `sections.py`, `check_extraction.py`), the paper's data, tables, figures, build and checks (`paper_ppml/`), the review viewer and figure primitives (`review/`). `Docs/SCRIPTS-MAP.html` maps every script to the part of the paper it serves. |
| `search-ppml/` | The search strings' provenance, the screening and eligibility decisions, the included studies, the extraction records (`evidence/sheets/`, tags and page numbers, quotations removed), the quality-appraisal consistency record. |
| `myliteraturereviewpaper/ppml2026/` | The paper's parts (`parts-v{version}/`), the study paragraphs, the build outputs (`build/`: the paper as markdown, `stats.json`, every table and figure), the icons (Tabler, MIT). |
| `local-checker/` | The local fact checker (BM25 + a DeBERTa NLI classifier) that checks statements against a paper's extracted text on the machine. |
| `notes-verifier/` | The review applications: the Notes Verifier, the Evidence Verifier, the Sheet Reviewer. |
| `pdf-text-extractor/` | The cross-platform PDF text extractor (GUI). |
| `experiments/` | The harnesses, environment recipes and run summaries of the first experiment (zkPET and FL-BC-IDS, the sweep and the two attack protocols); `UPSTREAM.md` names the clones and commits. |
| `requirements/` | Pinned package lists of the environments the review ran with. |

## Prerequisites

Python 3.12 or later; `pandoc` (the paper build); Google Chrome (the figures are SVG rendered by headless Chrome); TeX Live (the IEEE Access LaTeX rendering, optional); Tesseract (second OCR engine, optional); macOS for the Apple Vision OCR (`pyobjc` frameworks; elsewhere the pipeline uses Tesseract alone); Docker (the experiments).

```
python3 -m venv scripts/.venv && scripts/.venv/bin/pip install -r requirements/scripts.txt
python3 -m venv local-checker/.venv && local-checker/.venv/bin/pip install -r requirements/local-checker.txt
python3 -m venv notes-verifier/.venv && notes-verifier/.venv/bin/pip install -r requirements/notes-verifier.txt
```

## What runs from this package alone

The paper pipeline, from the records to the built paper and its checks (run from the package root):

```
python3 scripts/paper_ppml/data.py
PPML_PARTS_NAME=parts-v{version} python3 scripts/paper_ppml/data_v68.py
PPML_PARTS_NAME=parts-v{version} python3 scripts/paper_ppml/experiment_v82.py
PPML_PARTS=$PWD/myliteraturereviewpaper/ppml2026/parts-v{version} PPML_STUDIES=$PWD/myliteraturereviewpaper/ppml2026/studies-v81 python3 scripts/paper_ppml/build.py {version} --check
python3 scripts/paper_ppml/verify_v68.py          # recounts every table from the records
python3 scripts/paper_ppml/check_claims_v68.py    # every worded claim against the records
python3 scripts/paper_ppml/style_check.py {version}
```

Drop `--check` to render the Word file (needs pandoc). `scripts/.venv/bin/python scripts/paper_ppml/figures_pptx.py {version}` builds the editable deck of figures and tables.

## What needs the papers, the exports or the data sets

- The extraction and OCR pipeline, the notes verifier and the local fact checker read PDFs: point them at your own papers (each app's README says how).
- The quotation checks of the records (`check_sheets.py`) need the quotations, which are replaced here by the numbers they held; the build's own number check runs on those.
- The search merge and screening scripts read the database exports; the provenance file holds their checksums.
- The experiments need the upstream repositories at the commits in `experiments/UPSTREAM.md`, the CICIoV2024 data set and Docker; `experiments/*/README.md` and the `env/` folders give the recipes. The run summaries (`runs/*.csv`, `*.jsonl`, `*.md`) are included as produced.

## Screenshots

Each application folder has a README with a screenshot of the app on the real records, taken by the app itself (`scripts/review/app_screenshot.py`); where a paper is shown it is Shawkat et al. 2025, published under CC BY 4.0:
`notes-verifier/docs/` (Notes Verifier, Evidence Verifier, Sheet Reviewer), `myliteraturereviewpaper/linked-app/docs/` (Review Viewer), `scripts/search_ppml/docs/` (the screening application), `pdf-text-extractor/docs/` (PDF Text Extractor), `experiments/portal/docs/` (the experiments portal). Every script folder has a README generated from the scripts' own headers.

## Integrity

`MANIFEST.json` lists every file with its size and SHA-256.
''', encoding='utf-8')
    bad = scan(out)
    if bad:
        shutil.rmtree(out)
        sys.exit('refused: paper material found in the package: ' + ', '.join(bad[:10]))
    files = sorted(p for p in out.rglob('*') if p.is_file())
    manifest = {'package': out.name, 'built': datetime.date.today().isoformat(), 'files': len(files), 'bytes': sum(p.stat().st_size for p in files),
                'entries': [{'path': str(p.relative_to(out)), 'bytes': p.stat().st_size, 'sha256': sha(p)} for p in files]}
    (out / 'MANIFEST.json').write_text(json.dumps(manifest, indent=1), encoding='utf-8')
    zpath = out.with_suffix('.zip')
    with zipfile.ZipFile(zpath, 'w', zipfile.ZIP_DEFLATED) as z:
        for p in files + [out / 'MANIFEST.json']:
            z.write(p, f'{out.name}/{p.relative_to(out)}')
    print(f'{out.relative_to(ROOT)}: {len(files)} files, {manifest["bytes"] / 1e6:.1f} MB; zip {zpath.stat().st_size / 1e6:.1f} MB | ' + ', '.join(f'{k} {v}' for k, v in counts.items()))


if __name__ == '__main__':
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    main(sys.argv[1])
