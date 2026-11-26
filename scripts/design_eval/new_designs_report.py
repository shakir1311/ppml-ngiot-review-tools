#!/usr/bin/env python3
"""Writes the shortlist of new designs (outside the corpus) whose code is published and which use zero-knowledge proofs, with or without a blockchain, against the PhD's threats; clones the licensed code at a pinned commit.

The shortlist is the reviewer's judgement on the candidates of new_designs.py and new_designs_zk.py, made from repository
facts only (owner against the paper's authors, licence, file list, README signals), kept here in SHORTLIST. Paper metadata
(title, authors, year, venue, DOI) comes from OpenAlex without abstracts. Licensed code is cloned into the
design's code/<owner>__<repo>/ with its commit recorded; code without a licence is not cloned. Writes
design-evaluation/new-designs/SHORTLIST.json and .csv, and Docs/NEW-ZK-DESIGNS-WITH-CODE-<date>.html (printable; never
overwritten: -V2-, -V3-).

Each design gets its own folder, design-evaluation/new-designs/designs/<Znn>-<author>-<year>-<name>/, with code/, paper/,
datasets/, evidence/ and a README; the search records are in design-evaluation/new-designs/_search/.

Usage: design-evaluation/.venv/bin/python scripts/design_eval/new_designs_report.py [--no-doc] [--out <trial file>]
"""
import csv, datetime, html, json, pathlib, subprocess, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import EVAL, ROOT, Recorder, save_json, now   # noqa: E402
from report import CSS   # noqa: E402

OUT = EVAL / 'new-designs'
SEARCH = OUT / '_search'
DESIGNS = OUT / 'designs'
E = html.escape
# the folder id and short name of each shortlisted design (Z for the zero-knowledge set)
IDS = {'weixiubo/PoL-BFL': ('Z01', 'PoL-BFL'), 'crazydj8/FedShield-main': ('Z02', 'FedShield'),
       'HaimerlNikolas/Advancing-Blockchain-Based-Federated-Learning-Through-Verifiable-Off-Chain-Computations': ('Z03', 'VerifiableOffChain'),
       'pps-lab/rofl-project-code': ('Z04', 'RoFL'), 'SafeAILab/zkDL': ('Z05', 'zkDL'), 'guruvamsi-policharla/zkpot': ('Z06', 'zkPoT'),
       'NoahApthorpe/zk-DEAP-artifact': ('Z07', 'zk-DEAP'), 'prabhavathij-dev/TeleZK-FL': ('Z08', 'TeleZK-FL'),
       'okdlibri/fedtemporal': ('Z09', 'fedtemporal')}
THREATS = ['poisoning or Byzantine updates', 'malicious or Sybil participants', 'free riding', 'verification of training or aggregation']
SHORTLIST = [
    {'tier': 1, 'repo': 'https://github.com/weixiubo/PoL-BFL', 'title_q': 'PoL-BFL: Towards Trustworthy Federated Learning with Zero-Knowledge Proofs',
     'official': 'yes: owner is the first author (Xiubo Wei)', 'licence': 'MIT', 'zk': 'Groth16 (circom, snarkjs); proofs verified on chain',
     'ledger': 'EVM smart contracts in Solidity on Ganache: registry, committee election, incentives, PoL contract, Groth16 verifier, verification rollup',
     'threats': THREATS, 'privacy': 'ZK proofs (no DP or HE named in the README)', 'setting': 'not stated in the README',
     'testbed': 'Python and Solidity; local EVM (Ganache or Anvil); circom and snarkjs'},
    {'tier': 1, 'repo': 'https://github.com/crazydj8/FedShield-main', 'title_q': 'FedShield: Privacy Preservation for Blockchain Enabled Federated Learning',
     'official': 'yes: owner is a co-author (Akshat Aryan)', 'licence': 'MIT', 'zk': 'EZKL proofs of the model',
     'ledger': 'Hyperledger Fabric network with Go chaincode', 'threats': ['free riding', 'verification of training or aggregation'],
     'privacy': 'homomorphic encryption', 'setting': 'not stated in the README',
     'testbed': 'Python; Fabric in Docker (the repository ships Fabric binaries for Linux: use Fabric\'s own images on the Mac); EZKL'},
    {'tier': 2, 'repo': 'https://github.com/HaimerlNikolas/Advancing-Blockchain-Based-Federated-Learning-Through-Verifiable-Off-Chain-Computations',
     'title_q': 'Advancing Blockchain-Based Federated Learning Through Verifiable Off-Chain Computations',
     'official': 'yes: owner is a co-author (Nikolas Haimerl)', 'licence': 'none: authors\' permission needed',
     'zk': 'ZoKrates circuit; proof verified by a Solidity verifier contract', 'ledger': 'Ethereum contracts (Truffle): model contract and verifier',
     'threats': ['verification of training or aggregation'], 'privacy': 'ZK proofs of the off-chain aggregation', 'setting': 'IoT devices (a Devices folder)',
     'testbed': 'Truffle and a local EVM; ZoKrates; not cloned (no licence)'},
    {'tier': 3, 'repo': 'https://github.com/pps-lab/rofl-project-code', 'title_q': 'RoFL: Robustness of Secure Federated Learning',
     'official': 'yes: the authors\' lab (pps-lab, ETH Zurich)', 'licence': 'MIT, stated in the README (the LICENSE file it refers to is missing)',
     'zk': 'zero-knowledge range proofs on the norm of each update', 'ledger': 'none',
     'threats': ['poisoning or Byzantine updates', 'verification of training or aggregation'], 'privacy': 'secure aggregation (encrypted updates)',
     'setting': 'not stated in the README', 'testbed': 'Rust with Python clients; Ansible scripts; AVX-512 build optional'},
    {'tier': 3, 'repo': 'https://github.com/SafeAILab/zkDL', 'title_q': 'zkDL: Efficient Zero-Knowledge Proofs of Deep Learning Training',
     'official': 'yes: the authors\' lab', 'licence': 'BSD-2-Clause', 'zk': 'ZK proofs of deep-learning training (CUDA)', 'ledger': 'none',
     'threats': ['free riding', 'verification of training or aggregation'], 'privacy': 'ZK proofs (training data and weights hidden)',
     'setting': 'not stated in the README', 'testbed': 'CUDA: needs an NVIDIA GPU; does not run on the Mac as it stands'},
    {'tier': 3, 'repo': 'https://github.com/guruvamsi-policharla/zkpot', 'title_q': 'Experimenting with Zero-Knowledge Proofs of Training',
     'official': 'yes: owner is a co-author (Guru-Vamsi Policharla)', 'licence': 'MIT', 'zk': 'ZK proofs of training (MPC-in-the-head style)',
     'ledger': 'none', 'threats': ['free riding', 'verification of training or aggregation'], 'privacy': 'ZK proofs; MPC',
     'setting': 'not stated in the README', 'testbed': 'Rust'},
    {'tier': 3, 'repo': 'https://github.com/NoahApthorpe/zk-DEAP-artifact', 'title_q': 'zk-DEAP: A Zero-Knowledge Decentralized Encrypted Aggregation Protocol',
     'official': 'yes: owner is a co-author (Noah Apthorpe)', 'licence': 'MIT', 'zk': 'Bulletproofs, SNARK and STARK variants (Rust)',
     'ledger': 'none (decentralised aggregation, no ledger)', 'threats': ['malicious or Sybil participants', 'verification of training or aggregation'],
     'privacy': 'encrypted aggregation', 'setting': 'not stated in the README', 'testbed': 'Rust; Docker; includes penetration tests of malicious behaviour'},
    {'tier': 3, 'repo': 'https://github.com/prabhavathij-dev/TeleZK-FL', 'title_q': 'TeleZK-FL: enabling trustless and verifiable remote patient monitoring',
     'official': 'yes: owner is the first author (Prabhavathi Jayaraman)', 'licence': 'MIT', 'zk': 'quantised ZK proofs of the local training',
     'ledger': 'none', 'threats': ['verification of training or aggregation'], 'privacy': 'federated learning with ZK proofs',
     'setting': 'remote patient monitoring (IoMT)', 'testbed': 'Python'},
    {'tier': 3, 'repo': 'https://github.com/okdlibri/fedtemporal', 'title_q': 'Practical Byzantine-Resilient Federated Learning via Zero-Knowledge Proofs',
     'official': 'probably: the paper has one author (Omar Dib); the account name does not settle it', 'licence': 'MIT',
     'zk': 'ZK proofs (the README does not name the system)', 'ledger': 'none',
     'threats': ['poisoning or Byzantine updates', 'malicious or Sybil participants'], 'privacy': 'ZK proofs',
     'setting': 'not stated in the README', 'testbed': 'Python'},
]
LEFT_OUT = [
    ('24 repositories with zero-knowledge, a blockchain and one of the threats', 'no paper behind them: personal, company or student projects'),
    ('zkFL (Wang et al., IEEE Transactions on Big Data, 2024)', 'no code by its authors; dew06/recurvefl cites it but is another person\'s project'),
    ('Proof-of-Learning with Incentive Security (Zhao et al., arXiv 2024)', 'goun7/Yieldix is not the authors\' code'),
    ('zkLLM, ZIP, PANDA, ZK-DeepSeek, Microsoft zkbc', 'prove a model\'s inference or evaluation, not training or aggregation: outside the PhD\'s threats'),
]
TIERS = {1: 'Zero-knowledge and a blockchain, against our threats; open licence',
         2: 'Zero-knowledge and a blockchain, against our threats; no licence (ask the authors)',
         3: 'Zero-knowledge against our threats, no blockchain; open licence (a ledger would be ours to add)'}


def paper_line(folder, r):
    """Where the design's paper is: filed (with its source and, for a book, the pages taken) and extracted, or still to come."""
    pdf, prov = folder / 'paper' / r['id'] / f"{r['id']}.pdf", folder / 'paper' / 'PROVENANCE.json'
    if not pdf.exists():
        return f"- Save the PDF in `paper/` as `{r['id']}.pdf`; it goes through the extraction pipeline before any check reads it."
    p = json.load(open(prov)) if prov.exists() else {}
    src = pathlib.Path(p.get('source', '')).name
    book = f"; carved from the book `{src}`, PDF pages {p['book_pages_taken'][0]}-{p['book_pages_taken'][1]} (printed {p['printed_pages_crossref'][0]}-{p['printed_pages_crossref'][1]})" \
        if p.get('carved_from_book') else f" from `{src}`"
    ext = f"extracted and OCR-verified (`paper/{r['id']}/text/`)" if (pdf.parent / 'text' / 'pages').exists() else 'extraction pending'
    return f"- Filed: `paper/{r['id']}/{pdf.name}` ({p.get('pages')} pages{book}); {ext}."


def write_readme(folder, r):
    """The design folder's README: the paper and where to get it, the code, the reviewer's reading, the folder layout."""
    L = [f"# {r['id']}: {r.get('paper') or r['name']}", '', f"{r['authors']}, {r.get('year')}. {r.get('venue') or ''}"
         + ('' if r['peer_reviewed'] else ' (not peer reviewed)') + '.', '',
         '## The paper', '', f"- Published version: {r['links'].get('doi') or '–'}",
         f"- Free copy: {r['links'].get('free_full_text') or 'none known (needs institutional access)'}",
         paper_line(folder, r), '',
         '## The code', '', f"- Repository: {r['repo']}", f"- Licence: {r['licence']}", f"- Official: {r['official']}"]
    L += [f"- Cloned to `{pathlib.Path(r['cloned_to']).relative_to(pathlib.Path(r['folder']))}` at commit `{r['commit']}`"] if r.get('cloned_to') else \
         ['- Not cloned: no licence; the file list is in `evidence/file-list.json`.']
    L += ['', '## What it does, from the repository', '', f"- Zero-knowledge: {r['zk']}", f"- Ledger: {r['ledger']}",
          f"- PhD threats addressed: {', '.join(r['threats'])}", f"- Privacy: {r['privacy']}", f"- Setting: {r['setting']}",
          f"- Testbed notes: {r['testbed']}", '',
          '## Folder', '', '- `code/`: the authors\' code at a pinned commit', '- `paper/`: the paper (PDF and, once extracted, its text)',
          '- `datasets/`: the datasets the experiments need', '- `evidence/`: the published version found (OpenAlex, no abstract), the licence, file lists', '',
          f'Generated by `scripts/design_eval/new_designs_report.py`, {now()[:10]}.', '']
    (folder / 'README.md').write_text('\n'.join(L))


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    rec = Recorder({'folder': SEARCH}, pause=0.4)
    rows = []
    for s in SHORTLIST:
        w = {}
        for attempt in range(3):                         # OpenAlex now and then answers a search with nothing
            st, j = rec.fetch('openalex-shortlist', 'https://api.openalex.org/works', params={'search': s['title_q'], 'per_page': 1})
            w = ((j or {}).get('results') or [{}])[0] if isinstance(j, dict) else {}
            if w.get('title'):
                break
            import time
            time.sleep(5)
        locs = [((l.get('source') or {}).get('display_name'), (l.get('source') or {}).get('type')) for l in w.get('locations', [])]
        pub = [n for n, t in locs if t in ('journal', 'conference', 'book series') and n and 'arxiv' not in n.lower() and 'zenodo' not in n.lower()]
        names = [a['author']['display_name'] for a in w.get('authorships', [])]
        oa = w.get('open_access') or {}
        free = [l for l in w.get('locations', []) if l.get('is_oa') and (l.get('pdf_url') or l.get('landing_page_url'))]
        links = {'doi': w.get('doi'), 'free_full_text': oa.get('oa_url'),
                 'other_free_copies': sorted({(l.get('pdf_url') or l.get('landing_page_url')) for l in free} - {oa.get('oa_url')})[:3]}
        r = dict(s, paper=w.get('title'), year=w.get('publication_year'), doi=(w.get('doi') or '').replace('https://doi.org/', ''),
                 venue=pub[0] if pub else ((w.get('primary_location') or {}).get('source') or {}).get('display_name'),
                 peer_reviewed=bool(pub), authors=(', '.join(names[:3]) + (' et al.' if len(names) > 3 else '')), links=links)
        owner, name = s['repo'].split('/')[3:5]
        did, short = IDS[f'{owner}/{name}']
        existing = sorted(DESIGNS.glob(f'{did}-*')) if DESIGNS.exists() else []
        if not w.get('title') and existing and (existing[0] / 'design.json').exists():
            # OpenAlex gave nothing this time: keep what was recorded before rather than blanks
            prev = json.load(open(existing[0] / 'design.json'))
            r.update({k: prev.get(k) for k in ('paper', 'year', 'doi', 'venue', 'peer_reviewed', 'authors', 'links')})
            w = json.load(open(existing[0] / 'evidence' / 'openalex-work.json')) if (existing[0] / 'evidence' / 'openalex-work.json').exists() else w
        if existing:
            folder = existing[0]                          # a design keeps its folder for good
        else:
            surname = (names[0].split()[-1] if names else owner)
            folder = DESIGNS / f"{did}-{surname}-{r['year']}-{short}"
        r.update(id=did, name=short, folder=str(folder.relative_to(EVAL)))
        for sub in ('code', 'paper', 'datasets', 'evidence'):
            (folder / sub).mkdir(parents=True, exist_ok=True)
        if not s['licence'].startswith('none'):
            target = folder / 'code' / f'{owner}__{name}'
            old = OUT / 'code' / f'{owner}__{name}'           # the first clones, made before the per-design folders
            if not target.exists() and old.exists():
                old.rename(target)
            if not target.exists():
                subprocess.run(['git', 'clone', '--quiet', s['repo'] + '.git', str(target)], check=True)
            r['commit'] = subprocess.run(['git', '-C', str(target), 'rev-parse', 'HEAD'], capture_output=True, text=True).stdout.strip()
            r['cloned_to'] = str(target.relative_to(EVAL))
            lic = next((p for p in target.iterdir() if p.is_file() and p.name.upper().startswith(('LICENSE', 'LICENCE', 'COPYING'))), None)
            if lic:
                (folder / 'evidence' / 'licence.txt').write_text(lic.read_text(errors='replace'))
        else:
            st, tree = rec.fetch(f'tree-{owner}-{name}', f'https://api.github.com/repos/{owner}/{name}/git/trees/HEAD', github=True,
                                 params={'recursive': 1})
            save_json(folder / 'evidence' / 'file-list.json', {'about': 'The repository\'s files (it carries no licence, so it is not cloned).',
                      'made': now(), 'files': [t['path'] for t in (tree or {}).get('tree', []) if t.get('type') == 'blob'] if isinstance(tree, dict) else []})
        save_json(folder / 'evidence' / 'openalex-work.json', w)
        save_json(folder / 'design.json', {k: v for k, v in r.items() if k not in ('title_q',)})
        write_readme(folder, r)
        rows.append(r)
    save_json(OUT / 'SHORTLIST.json', {'about': 'New designs with code, zero-knowledge, against the PhD\'s threats; the reviewer\'s shortlist.',
                                       'made': now(), 'shortlist': rows, 'left_out': LEFT_OUT})
    with open(OUT / 'SHORTLIST.csv', 'w', newline='') as fh:
        cols = ['id', 'tier', 'paper', 'authors', 'year', 'venue', 'peer_reviewed', 'doi', 'paper_link', 'free_full_text', 'repo', 'official', 'licence', 'zk', 'ledger', 'threats',
                'privacy', 'setting', 'testbed', 'commit', 'cloned_to', 'folder']
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction='ignore')
        w.writeheader()
        for r in rows:
            w.writerow({k: ('; '.join(v) if isinstance(v, list) else v) for k, v in r.items()}
                       | {'paper_link': r['links'].get('doi'), 'free_full_text': r['links'].get('free_full_text')})
    idx = ['# New designs with code (zero-knowledge, against the PhD\'s threats)', '',
           'Designs outside the review\'s corpus, found 16 November 2026 (search records in `_search/`). One folder per design under `designs/`, '
           'each with `code/`, `paper/`, `datasets/`, `evidence/` and a README.', '',
           '| Folder | Paper | Published version | Free copy | Code |', '|---|---|---|---|---|']
    for r in rows:
        f = pathlib.Path(r['folder']).name
        idx.append(f"| [{f}](designs/{f}/README.md) | {r.get('paper') or ''} ({r.get('year')}) | {r['links'].get('doi') or '–'} | "
                   f"{r['links'].get('free_full_text') or 'none known'} | {'cloned, ' + r['licence'] if r.get('cloned_to') else 'not cloned: no licence'} |")
    idx += ['', f'Generated by `scripts/design_eval/new_designs_report.py`, {now()[:10]}.', '']
    (OUT / 'README.md').write_text('\n'.join(idx))
    if '--no-doc' in sys.argv:
        print({t: sum(1 for r in rows if r['tier'] == t) for t in TIERS}, 'folders under', DESIGNS.relative_to(ROOT))
        return
    today = datetime.date.today().isoformat()
    out = ROOT / 'Docs' / f'NEW-ZK-DESIGNS-WITH-CODE-{today}.html'
    if '--out' in sys.argv:
        out = pathlib.Path(sys.argv[sys.argv.index('--out') + 1])
    n = 2
    while out.exists() and '--out' not in sys.argv:
        out = ROOT / 'Docs' / f'NEW-ZK-DESIGNS-WITH-CODE-V{n}-{today}.html'
        n += 1
    H = [f'<!doctype html><html lang="en-GB"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">'
         f'<title>New ZK designs with code</title><style>{CSS} td.c {{ text-align:center; }}</style></head><body>',
         '<h1>New designs with code: zero-knowledge proofs, a blockchain and the PhD\'s threats</h1>',
         f'<p class="sub">Designs outside the review\'s corpus whose authors publish their code, which use zero-knowledge proofs and defend '
         f'against at least one of the threats the PhD names. Found {today} through OpenAlex, the Papers with Code archive and GitHub; judged '
         f'from repository facts (owner against the paper\'s authors, licence, files, README), never from the papers. Licensed code is cloned in '
         f'<span class="mono">design-evaluation/new-designs/code/</span>.</p>']
    for t, label in TIERS.items():
        sel = [r for r in rows if r['tier'] == t]
        H += [f'<h2>{E(label)} ({len(sel)})</h2><div class="wrap"><table><thead><tr><th>Paper</th><th>Code</th><th>Zero-knowledge</th><th>Ledger</th>'
              + ''.join(f'<th>{E(x)}</th>' for x in THREATS) + '<th>Privacy</th><th>Testbed notes</th></tr></thead><tbody>']
        for r in sel:
            H.append(f"<tr><td><b>{E(r.get('paper') or '')}</b><br><span class='muted'>{E(r['authors'])}, {E(str(r.get('year') or ''))}. "
                     f"{E(r.get('venue') or '')}{'' if r['peer_reviewed'] else ' (not peer reviewed)'}"
                     f"{(' · doi ' + E(r['doi'])) if r.get('doi') else ''}</span>"
                     + (f"<br>paper: <a href='{E(r['links']['doi'])}'>{E(r['links']['doi'])}</a>" if r['links'].get('doi') else '')
                     + (f"<br>free full text: <a href='{E(r['links']['free_full_text'])}'>{E(r['links']['free_full_text'])}</a>" if r['links'].get('free_full_text') else '<br><span class=\'muted\'>no free copy known</span>')
                     + "</td>"
                     f"<td><span class='mono'>{E(r['repo'].replace('https://github.com/', ''))}</span><br>{E(r['licence'])}<br>"
                     f"<span class='muted'>official: {E(r['official'])}</span></td><td>{E(r['zk'])}</td><td>{E(r['ledger'])}</td>"
                     + ''.join(f"<td class='c'>{'yes' if x in r['threats'] else '–'}</td>" for x in THREATS)
                     + f"<td>{E(r['privacy'])}</td><td>{E(r['testbed'])}</td></tr>")
        H.append('</tbody></table></div>')
    H += ['<h2>Looked at and left out</h2><ul>'] + [f'<li><b>{E(a)}</b>: {E(b)}.</li>' for a, b in LEFT_OUT] + ['</ul>',
          '<p class="muted">Threat columns: what the repository\'s README and files show the design addresses (the PhD\'s list: poisoning, malicious '
          'or fake participants, free riding, and the checks that prove training or aggregation). Generated by scripts/design_eval/new_designs_report.py; '
          'candidates in design-evaluation/new-designs/.</p></body></html>']
    out.write_text('\n'.join(H))
    print(out, {t: sum(1 for r in rows if r['tier'] == t) for t in TIERS})


if __name__ == '__main__':
    main()
