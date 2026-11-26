#!/usr/bin/env python3
"""Writes the README of every design folder and the overview README of the design evaluation, from the evidence files alone.

Each design's README.md says, in this order: the paper; the outcome (code, licence, algorithm, what can be run); how the code
was searched (every source and what it returned, the paper's own links and availability statements, the publisher's
supplementary items); the repositories and the reviewer's verdict on each; the licence and the pinned clone; the algorithm
check (local triage, the reader's verdict and the rule's verdict, item by item, with assumptions and gaps); the datasets; and
the list of evidence files. design-evaluation/README.md holds the method, the folder layout, the table of all 45 designs and
the counts, and the downloads that need the author. Nothing is written by hand into these files: rerun after any change.

Usage: design-evaluation/.venv/bin/python scripts/design_eval/status.py
"""
import collections, json, os, pathlib, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import EVAL, ROOT, load_designs, now   # noqa: E402

ITEM_NAMES = {'A_task_model': 'Task and model', 'B_training_aggregation': 'Training and aggregation',
              'C_privacy_mechanism': 'Privacy mechanism', 'D_check_defence': 'Checking of updates', 'E_ledger': 'Ledger',
              'F_protocol': 'Message flow', 'G_experiment_setup': 'Experiment set-up', 'H_attack_setup': 'Attack set-up',
              'I_results_to_compare': 'Results to compare'}


def load(path):
    try:
        return json.load(open(path))
    except Exception:
        return None


def rel(target, start):
    return os.path.relpath(target, start).replace(' ', '%20')


def outcome(code, lic, check, reader):
    """What Phase 2 can do with the design."""
    usable = [r for r in (lic or {}).get('repositories', []) if r.get('can_run_and_adapt') and r.get('reviewer_verdict') == 'official']
    if usable:
        return 'run with its own code'
    if code and code.get('code_status', '').startswith('released, no licence'):
        base = 'code exists without a licence (authors\' permission needed)'
    elif code and code.get('code_status') == 'on request':
        base = 'code on request (authors to be asked)'
    else:
        base = ''
    if check:
        rule, rd = check.get('rule_verdict'), check.get('reader_verdict')
        if rule == 'not viable':
            alg = 'not evaluated: a core item is missing'
        elif rd == 'not viable':
            alg = 'not evaluated: the reader finds the core not codeable'
        elif rule == 'core partly specified':
            alg = 'buildable with assumptions (core partly specified: author to confirm)'
        elif rule == 'viable with assumptions':
            alg = 'buildable with assumptions'
        else:
            alg = 'buildable from the paper'
        return f'{base}; {alg}' if base else alg
    return base or ('awaiting the algorithm check' if code else 'awaiting the code search')


def design_readme(d):
    f = d['folder']
    ev = f / 'evidence'
    sheet, links, cands = load(ev / '01-sheet.json'), load(ev / '02-paper-links.json'), load(ev / '10-candidates.json')
    code, lic, supp = load(ev / '11-code-verdict.json'), load(ev / '12-licence.json'), load(ev / '09-publisher-supplementary.json')
    tri, reader, check = load(f / 'algorithm' / '01-triage.json'), load(f / 'algorithm' / 'reader.json'), load(f / 'algorithm' / '02-quote-check.json')
    data = load(f / 'datasets' / 'DATASETS.json')
    paper = ROOT / d['paper_folder']
    L = [f"# {d['id']}: {d['title']}", '', f"{d['reference']}", '',
         f"Paper folder: [{d['paper_folder'].split('/')[-1]}]({rel(paper, f)}) (read only by local tools and the algorithm reader).", '']
    L += ['## Outcome', '', '| Question | Answer |', '|---|---|',
          f"| Code | {code['code_status'] if code else 'not yet judged'} |",
          f"| Ever published? | {code['ever_published'] if code else '-'} |"]
    if lic and lic.get('repositories'):
        for r in lic['repositories']:
            role = 'Licence' if r.get('reviewer_verdict') in ('official', 'unofficial reimplementation') else 'Related code, licence'
            L.append(f"| {role} of {r['repo'].split('github.com/')[-1]} | {r.get('licence_spdx') or 'none'}: {r.get('meaning', r.get('note', ''))} |")
    if check:
        L.append(f"| Algorithm (reader) | {check['reader_verdict']} |")
        L.append(f"| Algorithm (rule) | {check['rule_verdict']} |")
    L += [f"| Phase 2 | {outcome(code, lic, check, reader)} |", '']
    # ---- search
    L += ['## How the code was searched', '']
    if links:
        code_links = [l for l in links['links'] if l['kind'] == 'code_host']
        L.append(f"**In the paper** (local scan of {links['pages_scanned']} pages and {links['pdf_link_annotations']} PDF link annotations; no text kept):")
        L.append('')
        if code_links:
            for l in code_links:
                L.append(f"- {l['url']} (page {', '.join(map(str, l['pages']))}{', in the reference list' if l['in_references'] else ''})")
        else:
            L.append('- no link to a code host')
        st = links.get('statements') or {}
        L.append(f"- availability statements: {', '.join(f'{k} (p. {', '.join(map(str, v))})' for k, v in st.items()) if st else 'none found'}")
        L.append('')
    if supp:
        L += [f"**Publisher's supplementary items:** {supp['reading']}", '']
    if cands:
        L += [f"**Elsewhere** (names searched: {', '.join(cands['names_searched']) or 'none of its own; title, DOI and authors'}; "
              f"arXiv versions: {', '.join(cands['arxiv_versions']) or 'none'}):", '']
        L += [f'- {s}' for s in cands['sources']]
        L.append(f"- candidates recorded: {len(cands['candidates'])} (all in `evidence/10-candidates.json`)")
        L.append('')
    if code:
        L += ['## Repositories and verdicts', '']
        if code['repositories']:
            L += ['| Repository | Verdict | Reason |', '|---|---|---|']
            L += [f"| {r['repo']} | {r['verdict']} | {r['reason']} |" for r in code['repositories']]
        else:
            L.append('No repository is the design\'s code.')
        if code.get('ruled_out_as_a_group'):
            L += ['', f"Ruled out as a group: {code['ruled_out_as_a_group']}."]
        L.append('')
    if lic and lic.get('repositories'):
        L += ['## Licence and code folder', '']
        for r in lic['repositories']:
            L.append(f"- **{r['repo']}**: licence {r.get('licence_spdx') or 'none'} ({r.get('licence_class')}); {r.get('meaning', '')}")
            if r.get('cloned_to'):
                L.append(f"  - cloned to [`{r['cloned_to']}`]({r['cloned_to'].replace(' ', '%20')}) at commit `{r['head_commit']}`"
                         + (f" ({r['pinned_because']})" if r.get('pinned_because') else ''))
                mac = r.get('mac') or {}
                if mac:
                    L.append(f"  - environment files: {', '.join(mac.get('environment_files', [])) or 'none'}; macOS signs: "
                             f"{', '.join(f'{k} ({len(v)} files)' for k, v in mac.get('signs', {}).items()) or 'none'}")
            elif r.get('not_cloned'):
                L.append(f"  - {r['not_cloned']}")
        L.append('')
    # ---- algorithm
    L += ['## Algorithm', '']
    if tri:
        L.append(f"Local triage: {tri['level']} ({tri['signs_present']} of 10 kinds of sign present); pages named for the reader: "
                 f"{', '.join(map(str, tri['pages_for_reader']))}.")
        L.append('')
    if reader and check:
        L += [f"Reader's verdict: **{reader['verdict']}**; the rule's verdict: **{check['rule_verdict']}**; effort: {reader.get('effort')}.",
              f"Quotations found on their pages: {check['found']} of {check['quotations']}."
              + (f" Pages read as images: {', '.join(map(str, reader['pages_read_as_images']))}." if reader.get('pages_read_as_images') else ''), '',
              '| Item | Status | Pages | What is missing |', '|---|---|---|---|']
        for k, name in ITEM_NAMES.items():
            it = reader['items'].get(k, {})
            L.append(f"| {name} | {it.get('status', '')} | {', '.join(map(str, it.get('pages', [])))} | {it.get('missing', '')} |")
        for key, title in (('assumptions', 'Assumptions we would have to make'), ('blocking_gaps', 'Blocking gaps'),
                           ('components_to_build', 'Components to build'), ('libraries_that_could_help', 'Libraries that could help')):
            if reader.get(key):
                L += ['', f'**{title}:**', ''] + [f'- {x}' for x in reader[key]]
        if reader.get('summary'):
            L += ['', f"Reader's summary: {reader['summary']}"]
    elif lic and any(r.get('can_run_and_adapt') for r in lic.get('repositories', [])):
        L.append('Not needed: the design runs with its own code.')
    else:
        L.append('The reader has not reported yet.')
    L.append('')
    # ---- datasets
    L += ['## Datasets', '']
    if data:
        L += ['| Dataset | Source | Licence or terms | Size | Here |', '|---|---|---|---|---|']
        L += [f"| {x['name']} | {x.get('source', '')} | {x.get('terms', '')} | {x.get('size', '')} | {x.get('status', '')} |" for x in data['datasets']]
    else:
        L.append(f"Named in the evidence sheet: {', '.join(sheet['sheet_values'].get('datasets') or []) or 'none'}. "
                 'Downloaded only if the design can be run or built (the author, 10 November 2026).')
    L += ['', '## Evidence files', '']
    for p in sorted((ev).glob('*.json')) + sorted((f / 'algorithm').glob('*.json')):
        L.append(f"- [`{p.relative_to(f)}`]({p.relative_to(f)})")
    L.append(f"- `evidence/raw/` ({len(list((ev / 'raw').glob('*'))) if (ev / 'raw').exists() else 0} saved responses) and "
             f"`evidence/log.jsonl` (every request, with its checksum)")
    L += ['', f'Generated by `scripts/design_eval/status.py`, {now()[:10]}.', '']
    (f / 'README.md').write_text('\n'.join(L))
    return {'id': d['id'], 'who': f"{d['first_author']} {d['year']}", 'folder': f.name,
            'code': code['code_status'] if code else '…',
            'licence': ', '.join(sorted({r.get('licence_spdx') or 'none' for r in (lic or {}).get('repositories', [])})) or '-',
            'reader': check['reader_verdict'] if check else '…', 'rule': check['rule_verdict'] if check else '…',
            'phase2': outcome(code, lic, check, reader)}


def write_downloads(designs):
    """design-evaluation/DOWNLOADS.md: what needs the author, from the evidence files."""
    data, code, big = [], [], []
    for d in designs:
        f = d['folder']
        for x in (load(f / 'datasets' / 'DATASETS.json') or {}).get('datasets', []):
            st = x.get('status', '')
            if 'needs the author' in st:
                data.append(f"| {d['id']} | {x['name']} | {x.get('source', '')} |")
            elif 'over 10 GB' in st:
                big.append(f"| {d['id']} | {x['name']} | {x.get('size', '')} | {x.get('source', '')} |")
        cv = load(f / 'evidence' / '11-code-verdict.json') or {}
        if cv.get('code_status') == 'released, no licence':
            repo = next((r['repo'] for r in cv['repositories'] if r['verdict'] == 'official'), '')
            code.append(f"| {d['id']} | {repo} | no licence: ask the authors to add an open licence (e.g. MIT) or to grant permission to run and adapt it |")
        links = load(f / 'evidence' / '02-paper-links.json') or {}
        if 'code_on_request' in (links.get('statements') or {}) and cv.get('code_status') != 'released, open licence':
            pages = ', '.join(map(str, links['statements']['code_on_request']))
            code.append(f"| {d['id']} | (none published) | the paper offers the code on request (page {pages}): ask the corresponding author |")
    L = ['## Code that needs the authors', '', '| Design | Repository | What to do |', '|---|---|---|'] + (code or ['| – | – | nothing |'])
    L += ['', '## Datasets to fetch or identify', '', '| Design | Dataset | Why, and where to start |', '|---|---|---|'] + (data or ['| – | – | nothing |'])
    L += ['', '## Downloads over 10 GB, waiting for the author', '', '| Design | Dataset | Size | Source |', '|---|---|---|---|'] + (big or ['| – | – | – | nothing |'])
    (EVAL / 'DOWNLOADS.md').write_text('\n'.join(L) + '\n')


def main():
    designs = load_designs()
    write_downloads(designs)
    rows = [design_readme(d) for d in designs]
    c = collections.Counter(r['phase2'].split(';')[-1].strip() for r in rows)
    downloads = (EVAL / 'DOWNLOADS.md').read_text() if (EVAL / 'DOWNLOADS.md').exists() else ''
    L = ['# Design evaluation, Phase 1: which of the 45 designs can be run', '',
         'The PhD\'s first task after the review: evaluate the 45 designs included in the review by running them in Gotham with a 5G '
         'simulator. Phase 1 settles, for each design, whether its own code exists and may be used, and, where it does not, whether '
         'its paper describes the design well enough to build it. Phase 2 runs them.', '',
         '## How each design was checked', '',
         '1. **The paper itself**, by a local scan of the extracted pages and the PDF\'s link annotations: every link, and every code- or '
         'data-availability statement as a category with its page (`scan_paper.py`). No text of the paper is kept.',
         '2. **Everywhere else the code could be, or once was** (`search_code.py`): Crossref and OpenAlex (authors, ORCIDs, '
         'preprints); arXiv and Hugging Face Papers; the Papers with Code archive (its last snapshot, 28 July 2025, in `_sources/`); '
         'DataCite, Zenodo and OpenAIRE Scholexplorer (deposits linked to the DOI); GitHub (by the design\'s name, its title and DOI, '
         'files citing it, and the authors\' own accounts); ORCID (the authors\' websites and software); GitLab and Gitee; Software '
         'Heritage and the Wayback Machine (code that once existed). Publisher pages for supplementary items where the paper points to '
         'them. Every request and its answer is saved (`evidence/raw/`, `evidence/log.jsonl`).',
         '3. **The reviewer\'s verdict** on each candidate (`code_verdicts.py`): official code, unofficial reimplementation, a tool the '
         'paper names, or not the design\'s code, with the reason.',
         '4. **The licence** of the official code (`check_licence.py`): permissive or copyleft licences let us run and adapt it (macOS '
         'changes included) and the code is cloned at a pinned commit; code with no licence is recorded, not cloned.',
         '5. **The algorithm**, for designs without usable code: a local triage counts the signs of a codeable design and names the pages '
         '(`algorithm_triage.py`); one reader per design reads those pages against a fixed checklist (`READER-PROMPT.md`) and gives a '
         'verdict; a script finds every quotation on its page and applies the checklist\'s rule (`verify_reader_quotes.py`). Where the '
         'reader and the rule differ, both are shown.',
         '6. **Datasets** are downloaded only for designs that can be run or built; anything over about 10 GB waits for the author.', '',
         '## Folder layout', '',
         '```', 'design-evaluation/', '  README.md            this page (generated by scripts/design_eval/status.py)',
         '  READER-PROMPT.md     the readers\' instructions and checklist', '  names.json           the design names searched',
         '  DOWNLOADS.md         what needs the author\'s download', '  _sources/            shared sources (Papers with Code archive)',
         '  _runs/               logs of the runs', '  designs/<id>-<author>-<year>[-<name>]/',
         '    README.md          the design\'s outcome and evidence, generated', '    design.json        identity and DOI',
         '    evidence/          01 sheet, 02 paper links, 09 supplementary, 10 candidates, 11 code verdict, 12 licence; raw/; log.jsonl',
         '    code/              cloned code at a pinned commit, with CODE-PROVENANCE.json', '    datasets/          the datasets and DATASETS.json',
         '    algorithm/         01 triage, READER-PACKET.md, reader.json, reader-quotes.json, 02 quote check', '```', '',
         '## All 45 designs', '', '| Design | Code | Licence | Algorithm (reader / rule) | Phase 2 |', '|---|---|---|---|---|']
    for r in rows:
        L.append(f"| [{r['id']}](designs/{r['folder']}/README.md) {r['who']} | {r['code']} | {r['licence']} | {r['reader']} / {r['rule']} | {r['phase2']} |")
    L += ['', '## Counts', ''] + [f'- {k}: {v}' for k, v in c.most_common()]
    if downloads:
        L += ['', '## Downloads for the author', '', downloads]
    L += ['', f'Generated {now()[:16]} UTC by `scripts/design_eval/status.py` from the evidence files.', '']
    (EVAL / 'README.md').write_text('\n'.join(L))
    print(f'{len(rows)} design READMEs and the overview written;', dict(c))


if __name__ == '__main__':
    main()
