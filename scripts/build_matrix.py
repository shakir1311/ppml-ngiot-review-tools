#!/usr/bin/env python3
"""Collect the notes of every paper into tables for the systematic review.

Reads notes/NOTES.md in every paper folder of the manifest and writes, into corpus/_extraction/:

    papers.csv       one row per paper: record, types, theme, codes, counts, whether the notes passed the check
    statements.csv   one row per statement: paper, section, facet, label, statement, pages, quotations
    rigour.csv       one row per paper and item of section 15 (the facts for the quality appraisal)
    themes.csv       one row per paper and theme (primary and secondary) and one per code
    progress.md      which papers have notes, which pass, which are outstanding

    build_matrix.py
"""
from __future__ import annotations

import csv
import json
import sys

import corpus as C
import notes_format as N


def joined(value) -> str:
    return "; ".join(N.as_list(value))


def main() -> int:
    C.OUT.mkdir(parents=True, exist_ok=True)
    papers, statements, rigour, themes, progress = [], [], [], [], []
    for entry in C.load_manifest():
        d = C.folder_of(entry)
        notes = d / "notes" / "NOTES.md"
        if not notes.exists():
            progress.append((entry, "no notes yet", None))
            continue
        header, stmts, _, problems = N.parse(notes)
        check = d / "notes" / "check.json"
        chk = json.loads(check.read_text(encoding="utf-8")) if check.exists() else {}
        if chk and check.stat().st_mtime < notes.stat().st_mtime:
            status = "changed since the check"
        else:
            status = "pass" if chk.get("passed") else ("fail" if chk else "not checked")
        progress.append((entry, status, chk))
        papers.append({
            "id": entry["id"], "corpus": entry["corpus"], "group": entry["group"], "folder": entry["folder"],
            "template": header.get("template", "1"),
            "title": header.get("title", ""), "authors": header.get("authors", ""), "year": header.get("year", ""),
            "venue": header.get("venue", ""), "doi": header.get("doi", ""),
            "publication_type": header.get("publication_type", ""), "document_type": header.get("document_type", ""),
            "research_type": joined(header.get("research_type", "")),
            "evaluation_type": joined(header.get("evaluation_type", "")),
            "retracted": int("retract" in N.squash(str(header.get("venue", "")))),
            "pages": entry["pages"], "theme_primary": header.get("theme_primary", ""),
            "themes_secondary": joined(header.get("themes_secondary", "")), "codes": joined(header.get("codes", "")),
            "keywords_authors": joined(header.get("keywords_authors", "")),
            "statements": len(stmts), "quotations": sum(len(s.quotes) for s in stmts), "check": status,
            **{f"n_section_{n}": sum(1 for s in stmts if s.section == n) for n in N.SECTIONS},
        })
        for s in stmts:
            row = {"id": entry["id"], "section": s.section, "section_title": N.SECTIONS.get(s.section, ""),
                   "subsection": s.subsection, "facet": s.facet, "label": s.label, "absent": int(s.absent),
                   "image_evidence": int(s.image), "pages": ", ".join(f"p{p}" for p in s.pages),
                   "statement": s.text, "quotations": " || ".join(q for q, _ in s.quotes), "notes_line": s.line}
            statements.append(row)
            if s.section == N.RIGOUR_SECTION:
                item = next((i for i in N.RIGOUR if N.squash(i) == N.squash(s.label)), "")
                rigour.append({"id": entry["id"], "item": item or s.label, "absent": int(s.absent),
                               "pages": row["pages"], "statement": s.text, "quotations": row["quotations"]})
        themes.append({"id": entry["id"], "kind": "primary theme", "value": header.get("theme_primary", "")})
        themes += [{"id": entry["id"], "kind": "secondary theme", "value": t}
                   for t in N.as_list(header.get("themes_secondary", ""))]
        themes += [{"id": entry["id"], "kind": "code", "value": t} for t in N.as_list(header.get("codes", ""))]

    for name, rows in (("papers.csv", papers), ("statements.csv", statements), ("rigour.csv", rigour),
                       ("themes.csv", themes)):
        with open(C.OUT / name, "w", newline="", encoding="utf-8") as fh:
            if rows:
                w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
                w.writeheader()
                w.writerows(rows)
    done = [p for p in progress if p[1] != "no notes yet"]
    lines = ["# Notes: progress", "",
             f"{len(progress)} papers in the manifest; notes written for {len(done)}; "
             f"{sum(1 for p in done if p[1] == 'pass')} pass the check, "
             f"{sum(1 for p in done if p[1] not in ('pass',))} do not (failed, changed since the check, or not checked).", "",
             "| ID | Notes | Template | Statements | Quotations tested | Paper |", "|:--|:--|:--|--:|--:|:--|"]
    for entry, status, chk in progress:
        lines.append(f"| {entry['id']} | {status} | {(chk or {}).get('template', '')} | {(chk or {}).get('statements', '')} | "
                     f"{(chk or {}).get('quotations_tested', '')} | {entry['folder']} |")
    (C.OUT / "progress.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"papers.csv: {len(papers)} rows; statements.csv: {len(statements)} rows; rigour.csv: {len(rigour)} rows; "
          f"themes.csv: {len(themes)} rows; progress.md: {len(done)}/{len(progress)} papers have notes")
    return 0


if __name__ == "__main__":
    sys.exit(main())
