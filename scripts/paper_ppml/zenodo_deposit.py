#!/usr/bin/env python3
"""The Zenodo deposit of a release package: creates the deposition (or a new version of the existing record), sets its metadata
from the package's .zenodo.json with the author as creator, uploads the zip, reserves the DOI and prints it; publishes only with
--publish, since publishing is final (the author, 2 November 2026: the token is kept in secrets/zenodo-token.txt; deposits go
through the API; the DOI goes into the paper's Data availability row).

Usage: python3 scripts/paper_ppml/zenodo_deposit.py <paper version> [--publish] [--sandbox]
       python3 scripts/paper_ppml/zenodo_deposit.py <paper version> --link-github <repository URL>     (adds the repository to the published record)
       The deposition id and the DOI are recorded in release/ZENODO-V<n>.json.
"""
import json, pathlib, sys, urllib.request, urllib.error

ROOT = pathlib.Path(__file__).resolve().parents[2]
NAME = 'ppml-ngiot-review-tools'


def api(base, token, method, path, data=None, raw=None, ctype='application/json'):
    url = path if path.startswith('http') else base + path
    body = raw if raw is not None else (json.dumps(data).encode() if data is not None else None)
    req = urllib.request.Request(url, data=body, method=method)
    req.add_header('Authorization', f'Bearer {token}')
    if body is not None:
        req.add_header('Content-Type', ctype)
    try:
        with urllib.request.urlopen(req, timeout=600) as r:
            txt = r.read().decode()
            return json.loads(txt) if txt else {}
    except urllib.error.HTTPError as e:
        sys.exit(f'Zenodo {method} {path}: HTTP {e.code}: {e.read().decode()[:800]}')


def link_github(version, url, sandbox=False):
    """add the repository as a related identifier of the published record (a metadata edit, no new version)"""
    base = 'https://sandbox.zenodo.org' if sandbox else 'https://zenodo.org'
    token = (ROOT / 'secrets' / 'zenodo-token.txt').read_text(encoding='utf-8').strip()
    rec = json.loads((ROOT / 'release' / f'ZENODO-V{version}.json').read_text(encoding='utf-8'))
    dep = api(base, token, 'POST', f'/api/deposit/depositions/{rec["id"]}/actions/edit')
    md = dep['metadata']
    rels = [r for r in md.get('related_identifiers', []) if r.get('identifier') != url]
    rels.append({'identifier': url, 'relation': 'isSupplementTo', 'resource_type': 'software'})
    keep = {k: md[k] for k in ('title', 'upload_type', 'description', 'license', 'version', 'keywords', 'creators', 'access_right', 'publication_date') if k in md}
    keep['related_identifiers'] = rels
    api(base, token, 'PUT', f'/api/deposit/depositions/{rec["id"]}', {'metadata': keep})
    dep = api(base, token, 'POST', f'/api/deposit/depositions/{rec["id"]}/actions/publish')
    rec['github'] = url
    (ROOT / 'release' / f'ZENODO-V{version}.json').write_text(json.dumps(rec, indent=1), encoding='utf-8')
    print(f'record {rec["id"]} now lists {url}')


def main(version, publish=False, sandbox=False):
    base = 'https://sandbox.zenodo.org' if sandbox else 'https://zenodo.org'
    token = (ROOT / 'secrets' / 'zenodo-token.txt').read_text(encoding='utf-8').strip()
    pkg = ROOT / 'release' / f'{NAME}-v{version}'
    zpath = pkg.with_suffix('.zip')
    meta = json.loads((pkg / '.zenodo.json').read_text(encoding='utf-8'))
    record_f = ROOT / 'release' / f'ZENODO-V{version}.json'
    rec = json.loads(record_f.read_text(encoding='utf-8')) if record_f.exists() else {}
    if rec.get('id'):
        dep = api(base, token, 'GET', f'/api/deposit/depositions/{rec["id"]}')
    else:
        earlier = sorted(ROOT.glob('release/ZENODO-V*.json'))
        prev = json.loads(earlier[-1].read_text(encoding='utf-8')) if earlier else {}
        if prev.get('id') and prev.get('published'):                       # a new version of the published record
            dep = api(base, token, 'POST', f'/api/deposit/depositions/{prev["id"]}/actions/newversion')
            dep = api(base, token, 'GET', dep['links']['latest_draft'])
            for f in dep.get('files', []):                                  # the new version carries this package's zip only
                api(base, token, 'DELETE', f['links']['self'])
        else:
            dep = api(base, token, 'POST', '/api/deposit/depositions', {})
    dep_id = dep['id']
    metadata = {'title': meta['title'], 'upload_type': meta['upload_type'], 'description': meta['description'], 'license': meta['license'],
                'version': meta['version'], 'keywords': meta['keywords'], 'creators': meta['creators'], 'access_right': 'open',
                'prereserve_doi': True}
    dep = api(base, token, 'PUT', f'/api/deposit/depositions/{dep_id}', {'metadata': metadata})
    doi = dep['metadata'].get('prereserve_doi', {}).get('doi') or dep.get('doi')
    bucket = dep['links']['bucket']
    have = {f['filename'] for f in api(base, token, 'GET', f'/api/deposit/depositions/{dep_id}').get('files', [])}
    if zpath.name not in have:
        api(base, token, 'PUT', f'{bucket}/{zpath.name}', raw=zpath.read_bytes(), ctype='application/octet-stream')
    rec.update({'id': dep_id, 'doi': doi, 'html': dep['links'].get('html'), 'zip': zpath.name, 'bytes': zpath.stat().st_size, 'base': base, 'published': rec.get('published', False)})
    if publish:
        dep = api(base, token, 'POST', f'/api/deposit/depositions/{dep_id}/actions/publish')
        rec.update({'published': True, 'doi': dep.get('doi') or doi, 'concept_doi': dep.get('conceptdoi'), 'html': dep['links'].get('record_html') or dep['links'].get('html')})
    record_f.write_text(json.dumps(rec, indent=1), encoding='utf-8')
    print(f'deposition {dep_id} | DOI {rec["doi"]} | {"published" if rec["published"] else "draft, not published"} | {rec["html"]}')


if __name__ == '__main__':
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    if '--link-github' in sys.argv:
        link_github(sys.argv[1], sys.argv[sys.argv.index('--link-github') + 1], sandbox='--sandbox' in sys.argv)
    else:
        main(sys.argv[1], publish='--publish' in sys.argv, sandbox='--sandbox' in sys.argv)
