#!/usr/bin/env python3
"""Finds, on the Mac and without showing any of the paper's text, every link and every code- or data-availability statement in a design's paper.

Reads the extracted pages (`text/pages/page_NNNN.txt` of the paper's folder) and the PDF's own link annotations, and writes
`evidence/02-paper-links.json` in the design's folder: each link with its pages, whether it sits in the reference list, and
its kind (code host, archive or data host, DOI, other); each availability statement as a category with its pages (code on
request, code available, code to be released, data on request, data public, a data- or code-availability section,
supplementary material); and the coined names the paper uses most (the design's own name, to search for its code). No
sentence of the paper is written or printed.

Usage: design-evaluation/.venv/bin/python scripts/design_eval/scan_paper.py [<id> ...]   (all 45 when no id is given)
"""
import collections, pathlib, re, sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from common import ROOT, load_designs, page_texts, save_json, now   # noqa: E402

CODE_HOSTS = ('github.com', 'gitlab.com', 'bitbucket.org', 'gitee.com', 'sourceforge.net', 'codeocean.com', 'codeberg.org',
              'huggingface.co', 'colab.research.google.com', 'pypi.org', 'npmjs.com', 'github.io', 'gitlab.io', 'git.')
DATA_HOSTS = ('zenodo.org', 'figshare.com', 'osf.io', 'mendeley.com', 'dataverse', 'ieee-dataport.org', 'kaggle.com',
              'drive.google.com', 'dropbox.com', 'archive.org', 'softwareheritage.org', 'archive.ics.uci.edu', 'unb.ca',
              'physionet.org', 'data.', 'datasets', 'yann.lecun.com', 'cs.toronto.edu', 'stratosphereips.org', 'research.unsw.edu.au')

STATEMENTS = {
    'code_on_request': r'(code|implementation|source|scripts?|program)s?\b[^.]{0,100}\b(up)?on\s+(reasonable\s+)?request',
    'code_available': r'\b(source\s+code|our\s+code|the\s+code|codes|implementation|code\s+and\s+data)\b[^.]{0,80}\b(is|are|has\s+been|have\s+been)\s+(made\s+)?(publicly\s+|openly\s+|freely\s+)?(available|released|accessible|open[- ]sourced|published)',
    'code_to_be_released': r'\b(code|implementation)s?\b[^.]{0,80}\bwill\s+be\s+(made\s+)?(publicly\s+|openly\s+)?(available|released|open[- ]sourced|published)',
    'data_on_request': r'\bdata(set|sets)?\b[^.]{0,100}\b(up)?on\s+(reasonable\s+)?request',
    'data_public': r'\bdata(set|sets)?\b[^.]{0,80}\b(is|are)\s+(publicly|openly|freely)\s+available',
    'availability_section': r'^\s*(data|code|software|materials?)(\s+and\s+(code|data|materials?|software))?\s+availability(\s+statement)?\b',
    'supplementary_material': r'\bsupplement(ary|al)\s+(material|materials|data|file|files|information|items?)\b|\bsupporting\s+information\b|\bdownloadable\s+material\b',
    'no_data_used': r'\bno\s+(new\s+)?data\s+(was|were|has\s+been|have\s+been)\s+(created|used|generated|analy[sz]ed)',
    'not_applicable': r'availability(\s+statement)?\W{0,5}\s*(not\s+applicable|n/?a)\b',
    'data_confidential': r'\bdata(set|sets)?\b[^.]{0,80}\b(confidential|proprietary|cannot\s+be\s+(shared|made\s+available)|not\s+(be\s+)?(publicly\s+)?(available|shared))',
    'code_confidential': r'\b(code|implementation)s?\b[^.]{0,80}\b(confidential|proprietary|cannot\s+be\s+(shared|released)|not\s+(be\s+)?(publicly\s+)?(available|shared|released))',
    'data_in_article': r'\bdata\b[^.]{0,80}\b(included|contained|presented)\s+(with)?in\s+(this|the)\s+(article|paper|manuscript)',
    'link_given': r'(https?://|www\.|github\.com|doi\.org|zenodo|figshare|kaggle)',
}
# searched on every page; the rest only inside an availability section (in FL papers "data are not shared" is everywhere)
PAPER_WIDE = ('code_on_request', 'code_available', 'code_to_be_released', 'supplementary_material')
SECTION_SAYS = ('code_on_request', 'code_available', 'code_to_be_released', 'code_confidential', 'data_on_request',
                'data_public', 'data_confidential', 'data_in_article', 'no_data_used', 'not_applicable', 'link_given')
STOP = {'IEEE', 'FL', 'IoT', 'IIoT', 'IoV', 'DP', 'HE', 'ZKP', 'ZKPs', 'CNN', 'MNIST', 'IID', 'SGD', 'AI', 'ML', 'DL', 'PoW',
        'PoS', 'PBFT', 'TEE', 'SMPC', 'MPC', 'CIFAR', 'CIFAR-10', 'TABLE', 'LSTM', 'DNN', 'RSA', 'AES', 'ECC', 'SHA', 'URL',
        'GDPR', 'BFL', 'PPFL', 'CPU', 'GPU', 'RAM', 'GHz', 'GB', 'MB', 'KB', 'MEC', 'RSU', 'RSUs', 'UAV', 'UAVs', 'VANET',
        'VANETs', 'GAN', 'SVM', 'KNN', 'NIST', 'DOI', 'II', 'III', 'IV', 'VI', 'VII', 'VIII', 'IX', 'XI', 'XII', 'CA', 'TA',
        'CSP', 'KGC', 'IPFS', 'ResNet', 'LeNet', 'MLP', 'ReLU', 'IDS', 'DDoS', 'DoS', 'NG-IoT', 'B5G', 'Fig', 'FIGURE',
        'FMNIST', 'SNARK', 'zk-SNARK', 'zk-SNARKs', 'zkSNARK', 'PKI', 'ID', 'IDs', 'MSE', 'RMSE', 'MAE', 'ECDSA', 'BLS',
        'PoA', 'DPoS', 'Raft', 'RAFT', 'CKKS', 'BFV', 'LWE', 'RLWE', 'QR', 'UCI', 'EMNIST', 'SVHN', 'CIC', 'IoMT', 'IoHT',
        'ICVs', 'ICV', 'SAGIN', 'P2P', 'EV', 'EVs', 'SDN', 'NFV', 'API', 'JSON', 'HTTP', 'IP', 'TCP', 'UDP', 'MAC', 'PC',
        'SSI', 'DID', 'DIDs', 'VC', 'VCs', 'XOR', 'ACM', 'MDPI', 'CRC', 'NSL-KDD', 'KDD', 'ToN', 'TON', 'ToN-IoT', 'NIDS'}

URL_RE = re.compile(r'''(?i)\b((?:https?://|www\.)[^\s<>"'\]\)]+|(?:github|gitlab|gitee|bitbucket)\.(?:com|org)/[^\s<>"'\]\)]+)''')
REF_HEAD = re.compile(r'(?im)^\s*(references|bibliography|reference)\s*$')


def kind(url):
    u = url.lower()
    if 'doi.org/' in u:
        return 'doi'
    if any(h in u for h in CODE_HOSTS):
        return 'code_host'
    if any(h in u for h in DATA_HOSTS):
        return 'archive_or_data_host'
    return 'other'


def clean(url):
    url = url.rstrip('.,;:)]}>\'"')
    return url if url.lower().startswith('http') else 'https://' + url


def urls_in(text):
    """Links in a page's text, with links broken across a line end joined again."""
    out = set()
    for m in URL_RE.finditer(text):
        u = m.group(1)
        rest = text[m.end():]
        while rest.startswith('\n'):                     # the link continues on the next line
            nxt = re.match(r'\n([A-Za-z0-9/_\-.~%?=&#+]+)', rest)
            # a link that ends a sentence ("....com/x." then "II. RELATED WORK") is not continued
            if not nxt or not (u[-1] in '/-_=' or (u[-1] == '.' and nxt.group(1)[0].islower()) or nxt.group(1)[0] in '/-_.'):
                break
            u += nxt.group(1)
            rest = rest[nxt.end():]
        out.add(clean(u))
    return out


def scan(d):
    folder = ROOT / d['paper_folder']
    numbered = page_texts(d['paper_folder'])
    pages = [p for _, p in numbered]
    links = collections.defaultdict(lambda: {'pages': set(), 'in_references': True, 'from': set()})
    stmts = collections.defaultdict(set)
    tokens = collections.Counter()
    in_refs = False
    for n, p in numbered:
        text = p.read_text(errors='replace')
        head = REF_HEAD.search(text)
        body, refs = (text[:head.start()], text[head.start():]) if (head and not in_refs) else ((text, '') if not in_refs else ('', text))
        for part, is_ref in ((body, False), (refs, True)):
            for u in urls_in(part):
                links[u]['pages'].add(n)
                links[u]['from'].add('text')
                links[u]['in_references'] &= is_ref
        if head:
            in_refs = True
        flat = re.sub(r'-\n(?=[a-z])', '', text)
        flat_lines = flat
        flat = re.sub(r'\s*\n\s*', ' ', flat)
        for cat in PAPER_WIDE:
            if re.search(STATEMENTS[cat], flat, flags=re.I):
                stmts[cat].add(n)
        sec = re.search(STATEMENTS['availability_section'], flat_lines, flags=re.I | re.M)
        if sec:                                          # what the availability section itself says, as categories
            stmts['availability_section'].add(n)
            span = re.sub(r'\s*\n\s*', ' ', flat_lines[sec.start():sec.start() + 900])
            said = [c for c in SECTION_SAYS if re.search(STATEMENTS[c], span, flags=re.I)]
            for c in said or ['section_other_wording']:
                stmts['section_says:' + c].add(n)
        if not in_refs or head:
            for t in re.findall(r'\b[A-Za-z][A-Za-z0-9]*(?:-[A-Za-z0-9]+)*\b', body):
                if len(t) >= 3 and sum(c.isupper() for c in t) >= 2 and t not in STOP and not t.isdigit():
                    tokens[t] += 1
    pdfs = [x for x in folder.glob('*.pdf')]
    annotated = 0
    if pdfs:
        import fitz
        doc = fitz.open(pdfs[0])
        for i, page in enumerate(doc, start=1):
            for ln in page.get_links():
                u = ln.get('uri')
                if u and u.lower().startswith(('http', 'www')):
                    annotated += 1
                    u = clean(u)
                    links[u]['pages'].add(i)
                    links[u]['from'].add('pdf_annotation')
                    links[u]['in_references'] = links[u]['in_references'] and (i >= first_ref_page(pages))
    rows = sorted(({'url': u, 'kind': kind(u), 'pages': sorted(v['pages']), 'in_references': v['in_references'],
                    'found_in': sorted(v['from'])} for u, v in links.items()), key=lambda r: (r['kind'] != 'code_host', r['url']))
    out = {'about': 'Links and availability statements found by a local scan of the paper (extracted pages and PDF link '
                    'annotations). No text of the paper is kept: statements are categories with pages.',
           'made': now(), 'paper_folder': d['paper_folder'], 'pages_scanned': len(pages), 'pdf': pdfs[0].name if pdfs else None,
           'pdf_link_annotations': annotated, 'links': rows,
           'statements': {k: sorted(v) for k, v in sorted(stmts.items())},
           'coined_names': [{'name': t, 'count': c} for t, c in tokens.most_common(8) if c >= 4]}
    save_json(d['folder'] / 'evidence' / '02-paper-links.json', out)
    return out


def first_ref_page(pages):
    for p in pages:
        if REF_HEAD.search(p.read_text(errors='replace')):
            return int(p.stem.split('_')[1])
    return 10 ** 6


def main():
    ids = set(sys.argv[1:])
    for d in load_designs():
        if ids and d['id'] not in ids:
            continue
        o = scan(d)
        code = [r for r in o['links'] if r['kind'] == 'code_host' and not r['in_references']]
        print(f"{d['id']:6} pages {o['pages_scanned']:3}  links {len(o['links']):3} (code-host outside refs {len(code)})  "
              f"statements {','.join(f'{k}:{v}' for k, v in o['statements'].items()) or '-'}")
        for r in code:
            print(f"        {r['url']}  p{r['pages']}")


if __name__ == '__main__':
    main()
