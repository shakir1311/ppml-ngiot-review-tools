#!/usr/bin/env python3
"""The author's review page for the full-text proposals after the second screening (5 October 2026): for each record,
the proposed decision, the reason, and every condition with its page and quotation (search-ppml/evidence/checks/
fulltext-<id>.json), plus the two other-methods reasons. Output: Docs/PPML-FULLTEXT-PROPOSALS-2026-10-05.html (printable).

Usage: python3 scripts/paper_ppml/proposals_page.py
"""
import html, json, pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
C = ROOT / 'search-ppml' / 'evidence' / 'checks'
OUT = ROOT / 'Docs' / 'PPML-FULLTEXT-PROPOSALS-2026-10-05.html'
ORDER = ['S019', 'S004', 'p5351', 'p0574', 'p1628', 'p5129']
e = html.escape


def main():
    if OUT.exists():
        raise SystemExit(f'{OUT.name} exists; write a new version instead')
    blocks = []
    for pid in ORDER:
        d = json.loads((C / f'fulltext-{pid}.json').read_text(encoding='utf-8'))
        rows = ''.join(f"<tr><td>{e(c)}</td><td>{e(str(v.get('met')))}</td><td>{e(', '.join(v.get('angles', [])))}</td><td>"
                       + ' · '.join(f"p{ev['page']}: “{e(ev['quote'])}”" for ev in v.get('evidence', [])) + '</td></tr>'
                       for c, v in d['conditions'].items())
        blocks.append(f"<h2>{e(pid)} — proposed: {e(d['proposed_decision'])}{(' (' + e(d['code']) + ')') if d.get('code') else ''}</h2>"
                      f"<p>{e(d['reason'])}</p><table><tr><th>Condition</th><th>Met</th><th>Angles</th><th>Evidence</th></tr>{rows}</table>")
    OUT.write_text(f"""<!doctype html><html lang="en-GB"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Full-text proposals</title><style>:root{{--ink:#1b1b1b;--line:#c9c9c4;--head:#0f4761;--band:#f3f5f7}}
html,body{{background:#fff;color:var(--ink)}} body{{font:14.5px/1.5 -apple-system,"Helvetica Neue",Arial,sans-serif;margin:0 auto;max-width:64rem;padding:24px 16px 48px}}
h1{{font-size:1.35rem;color:var(--head)}} h2{{font-size:1.08rem;color:var(--head);border-bottom:1px solid var(--line);margin-top:26px}}
.note{{border:1px solid var(--line);border-radius:6px;padding:8px 12px;background:var(--band)}}
table{{border-collapse:collapse;width:100%;font-size:.84rem}} th,td{{border:1px solid var(--line);padding:4px 6px;text-align:left;vertical-align:top}} th{{background:var(--band)}}
@page{{size:auto;margin:12mm}} @media print{{body{{max-width:none;padding:0;font-size:9.5pt}} table{{font-size:8pt}} table,tr,.note{{break-inside:avoid}} th,.note{{background:#fff}}}}</style></head><body>
<h1>Records found by the second screening: full-text proposals for your decision</h1>
<div class="note">A blind second screening of 150 random exclusions flagged these records. Their full texts were read summary → notes → single
pages, against the criteria (CRITERIA-V8); every quotation was found again on its page by script. You decide; nothing is changed until you do.
Not retrieved: 1101 (could not be downloaded). Two other-methods reasons: Docs/PPML-OTHER-METHODS-REASONS-2026-10-05.html.</div>
{''.join(blocks)}</body></html>""", encoding='utf-8')
    print(OUT.relative_to(ROOT))


if __name__ == '__main__':
    main()
