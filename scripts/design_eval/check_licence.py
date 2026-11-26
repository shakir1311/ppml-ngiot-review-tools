#!/usr/bin/env python3
"""Reads the licence of each repository the reviewer accepted as a design's code, says whether it lets us run and adapt the code, and clones it at a pinned commit when it does.

Input: `evidence/11-code-verdict.json` of the design (written by the reviewer: each repository with its verdict and the
reason). The design's own code (official, or an unofficial reimplementation) goes to code/<owner>__<repo>/; a third-party tool
the paper names, or the authors' related code, goes to code/related/<owner>__<repo>/ when its licence allows. For each repository it records, from the GitHub API, the licence GitHub
detects, the licence file's text (saved under evidence/raw/), any licence stated in the README, the languages, the default
branch and its head commit, and classes the licence: permissive (run and modify), copyleft (run and modify; share changes
only under the same licence), non-commercial, no-derivatives, other (read the text), or none (all rights reserved: not
allowed without the authors' permission). Code whose licence allows running and adapting is cloned into code/<owner>__<repo>/
at the pinned commit (the branch head, or a commit the reviewer names with "pin"), with code/CODE-PROVENANCE.json (URL, commit, date, licence, checksum of the licence file); code without
such a licence is not cloned: its full file list is saved instead. It then notes what may need adapting on a Mac (CUDA, Linux
package managers, Docker, GPU-only calls, pinned old Python), from the code's own files. Writes evidence/12-licence.json.

Usage: design-evaluation/.venv/bin/python scripts/design_eval/check_licence.py <id> [<id> ...]
"""
import base64, hashlib, json, pathlib, re, subprocess, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import Recorder, design, save_json, now   # noqa: E402

PERMISSIVE = {'MIT', 'MIT-0', 'BSD-2-Clause', 'BSD-3-Clause', 'BSD-3-Clause-Clear', 'Apache-2.0', 'ISC', 'Unlicense', '0BSD',
              'Zlib', 'BSL-1.0', 'CC0-1.0', 'WTFPL', 'Python-2.0', 'PSF-2.0', 'Artistic-2.0', 'CC-BY-4.0', 'UPL-1.0', 'NCSA'}
COPYLEFT = {'GPL-2.0', 'GPL-3.0', 'GPL-2.0-only', 'GPL-3.0-only', 'GPL-2.0-or-later', 'GPL-3.0-or-later', 'LGPL-2.1', 'LGPL-3.0',
            'LGPL-2.1-only', 'LGPL-3.0-only', 'LGPL-2.1-or-later', 'LGPL-3.0-or-later', 'AGPL-3.0', 'AGPL-3.0-only',
            'AGPL-3.0-or-later', 'MPL-2.0', 'EPL-1.0', 'EPL-2.0', 'CC-BY-SA-4.0', 'EUPL-1.2', 'OSL-3.0'}
README_LICENCE = re.compile(r'(?im)^(?:#+\s*)?licen[cs]e\b.*$|\b(MIT|Apache[- ]2\.0|BSD|GPL-?[23]|GNU General Public)\b[^\n]{0,40}licen[cs]e')
MAC_SIGNS = {
    'cuda': r'\bcuda\b|\.cuda\(|torch\.device\(["\']cuda|nvidia|cudnn',
    'linux_package_manager': r'\bapt(-get)?\s+install\b|\byum\s+install\b',
    'docker': r'\bdocker\s+(run|build|compose|pull)\b|docker-compose',
    'old_python_pinned': r'python_requires\s*=\s*["\']?[<=~]=?\s*3\.[0-7]\b|python\s*==\s*3\.[0-7]\b|python=3\.[0-7]\b',
    'tensorflow_1': r'tensorflow\s*==\s*1\.|tensorflow-gpu',
    'x86_only_binaries': r'linux-x86_64|amd64\.deb|\.so\b',
    'gpu_hardcoded': r'device\s*=\s*["\']cuda:0["\']',
}


def classify(spdx, readme_says):
    if spdx in PERMISSIVE:
        return 'permissive', 'allowed: run and modify, keeping the licence notice'
    if spdx in COPYLEFT:
        return 'copyleft', 'allowed: run and modify; modified copies may be shared only under the same licence'
    if spdx and 'NC' in spdx.split('-'):
        return 'non_commercial', 'allowed for non-commercial research, with modification' + ('' if 'ND' not in spdx else '; no shared modified copies')
    if spdx and 'ND' in spdx.split('-'):
        return 'no_derivatives', 'running allowed; modified copies may not be shared'
    if spdx in ('NOASSERTION', 'other'):
        return 'other', 'a licence file GitHub cannot name: read its text'
    if readme_says:
        return 'readme_only', 'no licence file; the README states a licence: read it'
    return 'none', 'no licence: all rights reserved; not allowed without the authors\' permission'


def mac_notes(path):
    hits = {}
    for f in path.rglob('*'):
        if not f.is_file() or '.git' in f.parts or f.stat().st_size > 2_000_000:
            continue
        if f.suffix.lower() not in ('.py', '.txt', '.yml', '.yaml', '.toml', '.cfg', '.sh', '.md', '.ipynb', '.json', '') and not f.name.startswith('Dockerfile'):
            continue
        try:
            t = f.read_text(errors='ignore')
        except Exception:
            continue
        for k, rx in MAC_SIGNS.items():
            if re.search(rx, t, flags=re.I | re.M):
                hits.setdefault(k, []).append(str(f.relative_to(path)))
        if f.name.startswith('Dockerfile') or f.name.startswith('docker-compose'):
            hits.setdefault('docker', []).append(str(f.relative_to(path)))
    files = [str(f.relative_to(path)) for f in path.rglob('*') if f.is_file() and '.git' not in f.parts]
    env = [f for f in files if pathlib.Path(f).name in ('requirements.txt', 'environment.yml', 'environment.yaml', 'setup.py',
                                                         'pyproject.toml', 'Pipfile', 'Dockerfile', 'docker-compose.yml',
                                                         'package.json', 'go.mod', 'Cargo.toml', 'Makefile')]
    return {'files': len(files), 'environment_files': env, 'signs': {k: v[:12] for k, v in hits.items()}}


def check(design_id):
    d = design(design_id)
    verdict_file = d['folder'] / 'evidence' / '11-code-verdict.json'
    v = json.load(open(verdict_file))
    rec = Recorder(d, pause=0.5)
    results = []
    for r in v.get('repositories', []):
        if r.get('verdict') not in ('official', 'unofficial reimplementation', 'third-party tool named in the paper', "author's related code"):
            continue
        related = r['verdict'] in ('third-party tool named in the paper', "author's related code")
        m = re.match(r'https://github\.com/([^/]+)/([^/]+)', r['repo'])
        if not m:
            results.append({'repo': r['repo'], 'note': 'not on GitHub: checked by hand'})
            continue
        owner, name = m.groups()
        st, meta = rec.fetch(f'lic-repo-{owner}-{name}', f'https://api.github.com/repos/{owner}/{name}', github=True)
        if st != 200:
            results.append({'repo': r['repo'], 'status': st, 'licence_class': 'unavailable', 'can_run_and_adapt': False,
                            'note': 'the repository no longer answers'})
            continue
        branch = meta.get('default_branch')
        st, head = rec.fetch(f'lic-head-{owner}-{name}', f'https://api.github.com/repos/{owner}/{name}/commits/{branch}', github=True)
        sha = (head or {}).get('sha') if isinstance(head, dict) else None
        if r.get('pin'):                                 # a commit the reviewer names (e.g. the one already reproduced)
            st, pc = rec.fetch(f'lic-pin-{owner}-{name}', f"https://api.github.com/repos/{owner}/{name}/commits/{r['pin']}", github=True)
            sha = (pc or {}).get('sha', r['pin']) if isinstance(pc, dict) else r['pin']
        st, lic = rec.fetch(f'lic-licence-{owner}-{name}', f'https://api.github.com/repos/{owner}/{name}/license', github=True)
        spdx, lic_sha, lic_path = None, None, None
        if st == 200 and isinstance(lic, dict):
            spdx = (lic.get('license') or {}).get('spdx_id')
            body = base64.b64decode(lic.get('content', '')).decode('utf-8', 'replace')
            lic_path = lic.get('path')
            lic_sha = hashlib.sha256(body.encode()).hexdigest()
            (d['folder'] / 'evidence' / 'raw' / f'LICENCE-{owner}__{name}.txt').write_text(body)
        st, rd = rec.fetch(f'lic-readme-{owner}-{name}', f'https://api.github.com/repos/{owner}/{name}/readme', github=True)
        readme = base64.b64decode(rd['content']).decode('utf-8', 'replace') if isinstance(rd, dict) and rd.get('content') else ''
        readme_says = sorted(set(x.group(0).strip()[:120] for x in README_LICENCE.finditer(readme)))
        st, langs = rec.fetch(f'lic-languages-{owner}-{name}', f'https://api.github.com/repos/{owner}/{name}/languages', github=True)
        if r.get('licence_read'):                        # the reviewer read a licence file GitHub cannot name
            spdx = r['licence_read']
        klass, meaning = classify(spdx, readme_says)
        ok = klass in ('permissive', 'copyleft', 'non_commercial', 'no_derivatives')
        row = {'repo': r['repo'], 'reviewer_verdict': r['verdict'], 'default_branch': branch, 'head_commit': sha,
               'pinned_because': r.get('pin_reason'),
               'created': meta.get('created_at'), 'last_push': meta.get('pushed_at'), 'size_kb': meta.get('size'),
               'licence_spdx': spdx, 'licence_file': lic_path, 'licence_file_sha256': lic_sha, 'readme_licence_lines': readme_says,
               'licence_class': klass, 'meaning': meaning, 'can_run_and_adapt': ok, 'languages': langs if isinstance(langs, dict) else {}}
        target = d['folder'] / 'code' / ('related' if related else '') / f'{owner}__{name}'
        if ok and sha:
            if not target.exists():
                subprocess.run(['git', 'clone', '--quiet', r['repo'] + '.git', str(target)], check=True)
            subprocess.run(['git', '-C', str(target), 'checkout', '--quiet', sha], check=True)
            row['cloned_to'] = str(target.relative_to(d['folder']))
            if not related:
                row['mac'] = mac_notes(target)
        else:
            st, tree = rec.fetch(f'lic-tree-{owner}-{name}', f'https://api.github.com/repos/{owner}/{name}/git/trees/{sha or branch}',
                                 github=True, params={'recursive': 1})
            row['not_cloned'] = 'the licence does not allow use: only the file list is kept (evidence/raw/)'
            row['file_count'] = len((tree or {}).get('tree', [])) if isinstance(tree, dict) else None
        results.append(row)
    prov = [{k: x.get(k) for k in ('repo', 'head_commit', 'licence_spdx', 'licence_file_sha256', 'cloned_to')}
            for x in results if x.get('cloned_to')]
    if prov:
        save_json(d['folder'] / 'code' / 'CODE-PROVENANCE.json', {'made': now(), 'clones': prov,
                  'how': 'git clone of the repository, then checkout of the head commit recorded here'})
    save_json(d['folder'] / 'evidence' / '12-licence.json', {'about': 'Licence of each accepted repository and whether it lets us '
              'run and adapt the code (minor changes for macOS included).', 'made': now(), 'repositories': results})
    return results


if __name__ == '__main__':
    for i in sys.argv[1:]:
        for x in check(i):
            print(f"{i:6} {x['repo']}  {x.get('licence_spdx')}  {x.get('licence_class')}  run+adapt={x.get('can_run_and_adapt')}  "
                  f"{x.get('cloned_to', x.get('not_cloned', x.get('note', '')))}")
