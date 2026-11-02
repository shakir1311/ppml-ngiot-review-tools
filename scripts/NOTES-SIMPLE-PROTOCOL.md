# Simple notes — how the notes for one paper of the gap check are written (3 October 2026)

The papers of `corpus/searchcorpus/gapcheck/` get shorter notes than the corpus (`scripts/NOTES-PROTOCOL.md`), at the
author's request ("notes (simpler) - summary for each new download"). The rules for a statement are the same: every
statement carries its page, and the authors' words are quoted exactly so that the checker can find them on that page.

## What you are given

A paper folder with `<id>.pdf`, `text/full.txt` (page-delimited), `text/pages/page_NNNN.txt` (page N = PDF page N),
`images/pages/page_NNNN.png` (renders) and `PROVENANCE.json`. Read `text/full.txt` from the first page to the last.
Look at the page render for any figure or table whose content you report.

## The format of a statement

One bullet on one line: `- <what the paper says, in your words>. [p7] "the authors' exact words that say it"`

- `[p7]` is the PDF page (the number in `text/pages/page_0007.txt`), not the printed page number.
- A quotation follows the citation of **the one page it is on**, copied exactly (join words hyphenated at a line end;
  change nothing else), about 40 words at most. Several quotations: each after its own citation.
- Where the text is interrupted (a footnote mark, a running head, a figure inside the sentence), end the quotation and
  start a new one after it. Double quotation marks are for quotations only.
- A value read only from a figure or table image: cite `[p6, image]` and say what was read; no quotation needed.
- Numbers are copied exactly, with their unit. Absence is stated: `- Not stated by the authors. Searched for: <terms>.`

## The template (`notes/NOTES.md`)

```
---
template: simple-1
id: <the folder name, e.g. n1640>
title: "<title as printed>"
authors: "<all authors as printed>"
year: <year>
venue: "<journal or proceedings as printed, with volume/pages where printed>"
doi: "<doi as printed, or none>"
pages_total: <number of PDF pages>
read_on: 2026-10-03
---

# <Title>

## 1. What the paper is about
## 2. The problem it addresses
## 3. The approach
### 3.1 System, setting and ledger
### 3.2 Privacy of the updates
### 3.3 What is checked or proved, by whom
## 4. Evaluation and results
## 5. Threats and adversary model
## 6. Limitations and future work stated by the authors
## 7. Relevance to verifiable privacy-preserving FL on ledgers (reader's view)
```

Sections 1–6 report the paper; quotation is compulsory in sections 1, 2 and 6 and expected for every claim and number.
Section 7 is the reader's: two to four bullets on what the paper does and does not do for the review's research gap
(a zero-knowledge proof about the hidden update's size or direction, verified by a ledger, with no party reading the
update, proving cost on IoT-class hardware, tests against poisoning and fake participants). Cite pages; no quotation
needed. About 25–45 statements in all.

## The summary (`notes/SUMMARY.md`, 150–250 words)

```
# <id> · <First author> et al. <year> · <Title>

*<Venue> · <primary study | survey> · gap check*

**In short.** <one sentence>

**Problem.** <one or two sentences> [pN]

**Approach.**
- <bullet> [pN]
- <bullet> [pN]

**Results.**
- <bullet with the key numbers> [pN]

**Limits (authors).** <one or two sentences> [pN]

**Use in this review.** <one or two sentences: what it shows for the research gap>
```

The summary restates the notes; it adds nothing that the notes do not support.

## Check

`scripts/.venv/bin/python scripts/check_notes_simple.py <paper folder>` — every statement has a page, every quotation is
on its cited page, the sections are present, and the summary exists and has 150–250 words. Correct until it passes.
