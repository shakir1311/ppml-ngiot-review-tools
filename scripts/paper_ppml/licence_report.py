#!/usr/bin/env python3
"""Build the report of the licence check (licence_check.py) for one version of the PPML review.

Reads search-ppml/evidence/licences/LICENCES-V<n>-<date>.csv and the version's .docx (for the reference numbers as
printed), and writes Docs/LICENCE-CHECK-PPML-V<n>-REFERENCES-<date>.html. Every licence sentence quoted in the report is
taken from the PDF text of the copy that was read and carries data-src/data-page, so scripts/verify_policy_quotes.py can
check it against that page. The arXiv licences and the EU reuse notices come from the saved records in
search-ppml/evidence/licences/other-sources/.

Usage: scripts/.venv/bin/python scripts/paper_ppml/licence_report.py 42 2026-10-11 [report-version]
       (report-version 2 writes …-REFERENCES-V2-<date>.html; earlier versions are never overwritten)
"""
import collections, csv, html, json, pathlib, re, subprocess, sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
EVID = ROOT / 'search-ppml' / 'evidence' / 'licences'
PAPER = ROOT / 'myliteraturereviewpaper' / 'PPML in NextGeneration IoT'

# Copies whose licence is not printed in the PDF: the arXiv record or the publisher's reuse notice states it.
ARXIV = {'S026': ('CC BY 4.0', 'arxiv-2310.14848-S026.xml', 'arXiv:2310.14848'),
         'O078': ('CC BY-NC-SA 4.0', 'arxiv-2603.01876-O078.xml', 'arXiv:2603.01876')}
OFFICIAL = {
    'gdpr2016': ('eurlex-legal-notice', 'Unless otherwise specified, you can re-use the legal documents published in EUR-Lex '
                 'for commercial or non-commercial purposes.', 'EUR-Lex legal notice'),
    'edpb2026': ('edpb-copyright-notice', 'The reuse of any information of this website is authorized for commercial and '
                 'non-commercial purposes', 'EDPB copyright notice'),
}
PUBLISHERS = [('IEEE', 'IEEE'), ('Elsevier', 'Elsevier'), ('Springer', 'Springer'),
              ('Association for Computing', 'ACM'), ('Wiley', 'Wiley')]


def esc(s):
    return html.escape(s or '', quote=True)


def ref_numbers(version):
    docx = PAPER / f'Privacy Preserving Machine Learning in NextGeneration IoT - V{version}.docx'
    text = subprocess.run(['pandoc', '--sandbox', '-t', 'plain', '--wrap=none', str(docx)],
                          capture_output=True, text=True, check=True).stdout
    text = text[text.rfind('\nReferences\n'):]
    numbers = {}
    for n, entry in re.findall(r'^\[(\d+)\] (.+)$', text, flags=re.M):
        m = re.search(r'doi: (\S+?)\.?$', entry)
        if m:
            numbers[m.group(1).lower()] = int(n)
        elif 'General Data Protection Regulation' in entry:
            numbers['gdpr2016'] = int(n)
        elif 'Guidelines 02/2025' in entry:
            numbers['edpb2026'] = int(n)
    return numbers


def short(ref):
    m = re.match(r'(.+?),\s*“(.+?),?”', ref)
    if not m:
        return esc(ref[:110])
    authors, title = m.groups()
    first = authors.split(',')[0].strip()
    first = re.sub(r'\s+and\s+.*', '', first)
    first = re.sub(r'\s+et al\.?$', '', first)
    year = re.findall(r'\b(19|20)(\d{2})\b', ref)
    yr = year[-1][0] + year[-1][1] if year else ''
    etal = ' et al.' if (',' in authors or ' and ' in authors or 'et al' in authors) else ''
    title = title if len(title) <= 80 else title[:77].rsplit(' ', 1)[0] + ' …'
    return f'{esc(first)}{etal} ({yr}), <em>{esc(title.rstrip(","))}</em>'


COPYRIGHT_SIGN = re.compile('©|c' + chr(0x20DD))


def sentence(context, anchor_re, limit=320):
    """The licence statement around a match, quoted verbatim: from a copyright sign just before it (else from the start
    of its sentence) to the end of its sentence, never longer than `limit` characters."""
    m = re.search(anchor_re, context, re.I)
    if not m:
        return ''
    signs = [x.start() for x in COPYRIGHT_SIGN.finditer(context, max(0, m.start() - 80), m.start())]
    if signs:
        start = signs[-1]
    else:
        dot = context.rfind('. ', max(0, m.start() - 200), m.start())
        start = dot + 2 if dot >= 0 else m.start()
    if re.search(r'exclusive licen', m.group(0), re.I):             # Springer's line ends with the year, not a full stop
        author = context.rfind('The Author(s)', max(0, m.start() - 40), m.start())
        start = min(start, author) if author >= 0 and not signs else start
        year = re.search(r'\b(?:19|20)\d{2}\b', context[m.end():m.end() + 120])
        if year:
            return context[start:m.end() + year.end()].strip()
    end = context.find('. ', m.end())
    end = len(context) if end < 0 else end + 1
    if end - start > limit:
        end = context.rfind(' ', start, start + limit)
    return context[start:end].strip()


def publisher(rows):
    line = ' '.join(r['copyright_line'] + ' ' + r['reserved_context'] for r in rows)
    return next((name for needle, name in PUBLISHERS if needle in line), '')


def main():
    version, date = sys.argv[1], sys.argv[2]
    report_v = sys.argv[3] if len(sys.argv) > 3 else ''
    rows = list(csv.DictReader((EVID / f'LICENCES-V{version}-{date}.csv').open()))
    numbers = ref_numbers(version)
    works = collections.OrderedDict()
    for r in rows:
        works.setdefault(r['key'], []).append(r)

    groups = {'open': [], 'preprint': [], 'publisher': []}
    for key, rs in works.items():
        held = next(r for r in rs if r['copy'] == 'held')
        n = numbers.get(key) or numbers.get((held['doi'] or '').lower()) or numbers.get(key.lower())
        if key == 'page2021':
            n = numbers.get('10.1136/bmj.n71', n)
        item = {'key': key, 'n': n, 'rows': rs, 'held': held}
        if key in OFFICIAL or all(r['cc_licence'] for r in rs):
            groups['open'].append(item)
        elif key in ARXIV:
            groups['preprint'].append(item)
        else:
            item['publisher'] = publisher(rs)
            groups['publisher'].append(item)
    for g in groups.values():
        g.sort(key=lambda i: i['n'] or 999)

    sources = []          # (id, data-text, label)

    def quote(row, field, page_field, anchor):
        s = sentence(row[field], anchor)
        if not s:
            return ''
        sid = f"src-{row['key']}-{'p' if row['copy'] != 'held' else 'h'}"
        if sid not in [x[0] for x in sources]:
            sources.append((sid, '../' + row['folder'], row['folder']))
        return f'<q data-src="{sid}" data-page="{row[page_field]}">{esc(s)}</q> <span class="s">p. {row[page_field]}</span>'

    def copy_cell(item):
        out = []
        for r in item['rows']:
            label = 'Copy read' if r['copy'] == 'held' else 'Published version (also read)'
            if item['key'] in ARXIV and r['copy'] == 'held':
                lic, f, ident = ARXIV[item['key']]
                out.append(f'<div><b>{label}:</b> arXiv preprint {ident}; arXiv record gives licence <b>{lic}</b> '
                           f'<span class="s">(<a href="../search-ppml/evidence/licences/other-sources/{f}">record</a>)</span></div>')
                continue
            if item['key'] in OFFICIAL:
                sid, text, label2 = OFFICIAL[item['key']]
                src = f'src-{sid}'
                if src not in [x[0] for x in sources]:
                    sources.append((src, f'../search-ppml/evidence/licences/other-sources/{sid}.html', label2))
                out.append(f'<div><b>{label}:</b> official publication; {esc(label2)}: <q data-src="{src}">{esc(text)}</q></div>')
                continue
            bits = []
            if r['cc_licence']:
                bits.append(f"<b>{esc(r['cc_licence'])}</b>: " + quote(r, 'cc_context', 'cc_page',
                            r'creative\s*commons|CC[\s-]?BY|open access article'))
            elif r['reserved_page']:
                bits.append(quote(r, 'reserved_context', 'reserved_page',
                                  r'all rights (?:are )?reserved|requires IEEE permission|exclusive licen|publication rights'))
            elif r['copyright_line']:
                bits.append(f"copyright line: “{esc(r['copyright_line'])}” (no licence statement)")
            else:
                bits.append('no licence or copyright statement found')
            if r['tdm_ai_reserved'] and not r['cc_licence']:
                bits.append('<span class="flag">reserves text and data mining and AI training</span>')
            if r['tdm_ai_reserved'] and r['cc_licence']:
                bits.append('<span class="flag">download stamp also says “Protected by copyright, including for uses '
                            'related to text and data mining, AI training”</span>')
            if r['library_licence'] and not r['cc_licence']:
                bits.append(f"stamped as licensed to <b>{esc(r['library_licence'])}</b>")
            out.append(f'<div><b>{label}:</b> ' + '; '.join(b for b in bits if b) + '</div>')
        oa = [x.strip() for x in item['held']['openalex_licences'].split('|') if x.strip().startswith('cc-')]
        if item in groups['publisher'] and oa:
            out.append('<div class="s">OpenAlex lists an openly licensed version elsewhere (not the copy read): '
                       + esc('; '.join(dict.fromkeys(oa))) + '</div>')
        return ''.join(out)

    def table(items, with_publisher=False):
        head = '<th>Ref.</th><th>Work</th>' + ('<th>Publisher</th>' if with_publisher else '') + '<th>Licence of the copy read</th>'
        cols = '<col class="n"><col class="w">' + ('<col class="p">' if with_publisher else '') + '<col class="l">'
        body = []
        for i in items:
            pub = f'<td>{esc(i.get("publisher", ""))}</td>' if with_publisher else ''
            body.append(f'<tr><td>[{i["n"]}]</td><td>{short(i["held"]["reference"])} <span class="s">{esc(i["key"])}</span></td>'
                        f'{pub}<td>{copy_cell(i)}</td></tr>')
        return (f'<div class="table-wrap"><table><colgroup>{cols}</colgroup><thead><tr>{head}</tr></thead>'
                f'<tbody>{"".join(body)}</tbody></table></div>')

    variants = collections.Counter(i['held']['cc_licence'] for i in groups['open'] if i['key'] not in OFFICIAL)
    pubs = collections.Counter(i['publisher'] for i in groups['publisher'])
    tdm_pub = sum(1 for i in groups['publisher'] + groups['preprint'] if any(r['tdm_ai_reserved'] for r in i['rows']))
    lib = sum(1 for i in groups['publisher'] + groups['preprint'] if any(r['library_licence'] for r in i['rows']))
    elsewhere = sum(1 for i in groups['publisher'] if 'cc-by' in i['held']['openalex_licences'])
    total = sum(len(g) for g in groups.values())
    var_text = ', '.join(f'{v} {k}' for k, v in sorted(variants.items(), key=lambda kv: -kv[1]))
    pub_text = ', '.join(f'{k} {v}' for k, v in pubs.most_common())

    TERMS = '../Regulatory/Publisher-Terms-2026-10-11/'
    for sid, f in (('terms-ieee', 'ieee-xplore-terms-of-use-via-chrome.txt'), ('terms-elsevier', 'elsevier-website-terms.html'),
                   ('terms-wiley', 'wiley-onlinelibrary-terms-via-chrome.txt'),
                   ('terms-springer', 'springerlink-terms-archive-20261010.html'), ('terms-acm', 'acm-dl-policies-via-chrome.txt')):
        sources.append((sid, TERMS + f, f))

    def refs(items):
        return ', '.join(str(i['n']) for i in sorted(items, key=lambda i: i['n'] or 999))

    by_pub = collections.defaultdict(list)
    for i in groups['publisher']:
        by_pub[i['publisher']].append(i)
    for i in groups['preprint']:                         # their published versions were read too
        by_pub['IEEE' if i['key'] == 'S026' else 'Elsevier'].append(i)
    cc_by = [i for i in groups['open'] if i['key'] in OFFICIAL or i['held']['cc_licence'] == 'CC BY']
    cc_nc = [i for i in groups['open'] if i not in cc_by]
    breach = [
        ('CC BY, GDPR, EDPB guidelines', cc_by, 'No',
         'CC BY allows any use with attribution; EUR-Lex and the EDPB allow reuse with the source acknowledged.'),
        ('CC BY-NC, CC BY-NC-ND', cc_nc, 'No',
         '<span class="mine">My reading: the use was non-commercial research and nothing was redistributed.</span>'),
        ('arXiv preprints of S026 (CC BY) and O078 (CC BY-NC-SA)', groups['preprint'], 'No, for the preprint copies',
         'Their publisher versions, read later, are counted under IEEE and Elsevier below.'),
        ('IEEE (IEEE Xplore)', by_pub['IEEE'], 'Yes',
         'Institutional subscribers are not permitted to: <q data-src="terms-ieee">Use or enable artificial intelligence technologies '
         'and tools to ingest, train, test, analyze, process, copy, distribute, make publicly accessible, and/or generate output '
         'based on the Licensed Products (or any material included therein), or upload, copy, or host the Licensed Products (or any '
         'material included therein) to or for use in artificial intelligence technologies and tools directly or indirectly</q>.'),
        ('Elsevier (ScienceDirect)', by_pub['Elsevier'], 'Yes',
         '<q data-src="terms-elsevier">You may not use Content from the Services in combination with an artificial intelligence '
         'tool, (including to train an algorithm, test, process, analyse, generate output and/or develop any form of artificial '
         'intelligence tool) except as otherwise expressly permitted under these Terms and Conditions, or any relevant license or '
         'subscription agreement or authorization by us.</q>'),
        ('Wiley (Wiley Online Library)', by_pub['Wiley'], 'Yes',
         'Users shall not: <q data-src="terms-wiley">Use or enable artificial intelligence technologies and tools to ingest, train, '
         'test, analyze, process, copy, distribute, make publicly accessible, and/or generate output</q> based on its content, '
         'or <q data-src="terms-wiley">upload, copy, or host the Wiley Online Library, the Electronic Products, or any material '
         'included therein to or for use in artificial intelligence technologies and tools directly or indirectly</q>.'),
        ('Springer (Springer Nature Link)', by_pub['Springer'], 'Very likely yes',
         'Users may <q data-src="terms-springer">solely for private, educational, personal, scientific, or research purposes access, '
         'browse, view, display, search, download and print the Content</q>, and may not <q data-src="terms-springer">re-distribute, '
         'reproduce, or transmit the Content by any means including electronic</q>. Sending the full text to an AI service '
         'transmits it to a third party.'),
        ('ACM (ACM Digital Library)', by_pub['ACM'], 'Unclear',
         'No AI clause. Not permitted: <q data-src="terms-acm">The posting of ACM DL materials on an 3rd party server or peer to peer '
         'network without the written permission from the ACM.</q> <span class="mine">Whether sending a paper to an AI service '
         'counts as posting it on a third-party server is not settled by the wording.</span>'),
    ]
    breach_rows = ''.join(
        f'<tr><td>{label}</td><td>{len(items)}</td><td>{refs(items)}</td><td><b>{verdict}</b></td><td>{why}</td></tr>'
        for label, items, verdict, why in breach)
    yes_n = sum(len(items) for _, items, v, _ in breach if v.startswith('Yes'))
    likely_n = sum(len(items) for _, items, v, _ in breach if v.startswith('Very likely'))
    unclear_n = sum(len(items) for _, items, v, _ in breach if v == 'Unclear')
    no_n = sum(len(items) for _, items, v, _ in breach if v.startswith('No'))

    page = f'''<!doctype html>
<html lang="en-GB"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Licences of Cited Works</title>
<style>
:root {{ --ink:#1b1f24; --muted:#59616c; --line:#d3d9e0; --bg:#fff; --panel:#f5f7f9; --head:#eef1f5; --flag:#7a4a00; }}
* {{ box-sizing:border-box; }}
body {{ margin:0; padding:24px 16px 48px; background:var(--bg); color:var(--ink);
  font:15px/1.5 -apple-system,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif; }}
main {{ max-width:90rem; margin:0 auto; }}
h1 {{ font-size:1.5rem; margin:0 0 .4rem; }} h2 {{ font-size:1.15rem; margin:2rem 0 .5rem; padding-top:.4rem; border-top:2px solid var(--ink); }}
p, li {{ max-width:62rem; }}
.lede {{ color:var(--muted); }}
.callout {{ background:var(--panel); border:1px solid var(--line); border-left:4px solid #1d4f8f; padding:.7rem .9rem; margin:1rem 0; }}
.table-wrap {{ overflow-x:auto; margin:.5rem 0 1rem; }}
table {{ width:100%; border-collapse:collapse; table-layout:fixed; }}
th, td {{ border:1px solid var(--line); padding:.4rem .5rem; vertical-align:top; text-align:left; font-size:.82rem; overflow-wrap:anywhere; }}
thead th {{ background:var(--head); }}
col.n {{ width:6%; }} col.w {{ width:34%; }} col.p {{ width:9%; }} col.l {{ width:auto; }}
col.k {{ width:34%; }} col.g {{ width:17%; }} col.c {{ width:6%; }} col.r {{ width:20%; }} col.v {{ width:9%; }}
q {{ quotes:"\\201C" "\\201D" "\\2018" "\\2019"; }}
.s {{ color:var(--muted); font-size:.75rem; }}
.flag {{ color:var(--flag); font-weight:600; }}
.mine {{ font-style:italic; color:var(--muted); }}
.path {{ font-family:ui-monospace,Menlo,monospace; font-size:.76rem; color:var(--muted); }}
@media print {{
  @page {{ size:auto; margin:12mm 10mm; }}
  body {{ padding:0; font-size:9.5pt; background:#fff; color:#000; }}
  main {{ max-width:none; }} p, li {{ max-width:none; }}
  .table-wrap {{ overflow:visible; }}
  th, td {{ font-size:7.6pt; padding:3px 4px; border-color:#888; }}
  thead {{ display:table-header-group; }} thead th, .callout {{ background:#fff; }}
  tr, .callout {{ break-inside:avoid; }} h2 {{ break-after:avoid; }}
  a {{ color:#000; text-decoration:none; }} .s, .mine, .lede {{ color:#333; }} .flag {{ color:#000; }}
}}
</style></head><body><main>
<h1>Licences of the works cited in the PPML review (V{version})</h1>
<p class="lede">The {total} works in the reference list of <em>Privacy Preserving Machine Learning in NextGeneration IoT – V{version}</em>,
and the licence of each copy that was read with an AI assistant (Claude, by Anthropic) to write the notes and evidence
sheets. Checked on {date}. A record of facts and of the publishers' published terms, not a legal opinion.</p>

<div class="callout">
<table class="small"><colgroup><col class="k"><col class="n"><col></colgroup>
<thead><tr><th>Licence of the copies read</th><th>Works</th><th>Detail</th></tr></thead><tbody>
<tr><td>Open licence or official reuse permission on every copy read</td><td>{len(groups['open'])}</td>
<td>Creative Commons: {var_text}; plus the GDPR (EUR-Lex reuse policy) and the EDPB guidelines (EDPB reuse notice).</td></tr>
<tr><td>Openly licensed preprint read first, then the publisher's version</td><td>{len(groups['preprint'])}</td>
<td>The preprints are CC licensed on arXiv; the published versions are not, and both reserve AI training.</td></tr>
<tr><td>Publisher's copyright, no open licence on the copy read</td><td>{len(groups['publisher'])}</td>
<td>{pub_text}. {lib} of the publisher copies in these two rows are stamped as licensed to Abertay; {tdm_pub} reserve text
and data mining and AI training in their copyright line; {elsewhere} have an openly licensed version elsewhere (OpenAlex), which
is not the copy that was read.</td></tr>
</tbody></table>
</div>

<h2>1. Did uploading the copies to Claude breach the publishers' terms?</h2>
<p>As the publishers' published terms of use stand: <b>yes for {yes_n} works</b>, very likely for {likely_n}, unclear for
{unclear_n}, and no for {no_n} (S026 and O078 appear twice: their preprints are open, their published versions are not).</p>
<div class="table-wrap"><table><colgroup><col class="g"><col class="c"><col class="r"><col class="v"><col></colgroup>
<thead><tr><th>Copies read</th><th>Works</th><th>V{version} reference numbers</th><th>Breach?</th><th>The publisher's terms</th></tr></thead>
<tbody>{breach_rows}</tbody></table></div>
<p class="mine">These are the platforms' terms of use, a contract matter, separate from copyright law. Each publisher's terms
also defer to the institution's own licence where that says otherwise; that licence was not available. As I read it, the
UK exception for text and data analysis for non-commercial research does not cover this use, because it does not allow a
copy to be passed to another party.</p>

<h2>2. Publisher's copyright, no open licence ({len(groups['publisher'])})</h2>
{table(groups['publisher'], with_publisher=True)}

<h2>3. Openly licensed preprint, then the publisher's version ({len(groups['preprint'])})</h2>
{table(groups['preprint'])}

<h2>4. Open licence or official reuse permission ({len(groups['open'])})</h2>
<p class="mine">CC BY permits reuse with attribution. CC BY-NC and CC BY-NC-ND add “non-commercial” (and “no derivatives”)
conditions, which a non-commercial research use meets.</p>
{table(groups['open'])}

<h2>5. How this was checked</h2>
<ul>
<li>Scope: only the works in the V{version} reference list (the bibliography file the paper is built from, matched to the printed
list: {total} of {total}).</li>
<li>Each copy that was read (the PDF in the workspace; for studies later replaced by their published version, both copies)
was searched page by page for a licence statement, a reservation of rights, a library stamp and a copyright line
(<span class="path">scripts/paper_ppml/licence_check.py</span>). Every match was then read by hand; one false match (Wiley's
generic download footer) was excluded by rule.</li>
<li>Second witness: OpenAlex, looked up by DOI (no personal data sent); raw answers in <span
class="path">search-ppml/evidence/licences/openalex/</span>. arXiv licences from arXiv's own records; EUR-Lex and EDPB reuse
notices saved in <span class="path">search-ppml/evidence/licences/other-sources/</span>.</li>
<li>The publishers' terms of use were read on {date}: IEEE Xplore, Wiley Online Library and the ACM Digital Library in Chrome
(their pages need JavaScript or refuse scripts), Elsevier's directly (the page ScienceDirect's own “Terms and conditions”
link opens), Springer Nature Link from the Internet Archive copy of 10 October 2026. Saved in <span
class="path">Regulatory/Publisher-Terms-2026-10-11/</span>.</li>
<li>Every licence sentence quoted here was checked word for word against the page cited
(<span class="path">scripts/verify_policy_quotes.py</span>). Full record: <span
class="path">search-ppml/evidence/licences/LICENCES-V{version}-{date}.csv</span>.</li>
</ul>

<div style="display:none">
{"".join(f'<span id="{sid}" data-text="{esc(path)}"></span>' for sid, path, _ in sources)}
</div>
</main></body></html>
'''
    out = ROOT / 'Docs' / f'LICENCE-CHECK-PPML-V{version}-REFERENCES{"-V" + report_v if report_v else ""}-{date}.html'
    if out.exists():
        sys.exit(f'{out.relative_to(ROOT)} exists; give a new report version')
    out.write_text(page)
    print(f'{out.relative_to(ROOT)}: {total} works — open {len(groups["open"])}, preprint {len(groups["preprint"])}, '
          f'publisher {len(groups["publisher"])}; {len(sources)} quoted sources')


if __name__ == '__main__':
    main()
