# PhD-focused notes — how the notes for one paper of the PPML review are written (4 October 2026)

For the studies the author included in the PPML review that were not yet in the corpus (`corpus/ppmlcorpus/`). The
author: "make sure not to spend too much time on very lengthy notes and make sure the summaries and notes are relevant to
my PhD and from a thematic pov are useful". The rules for a statement are those of the simple notes
(`scripts/NOTES-SIMPLE-PROTOCOL.md`): every statement carries its page; the authors' words are quoted exactly, so the
checker can find them on that page. The sections follow the review's criteria (`search-ppml/CRITERIA-V7-2026-10-04.md`)
and its seven PhD angles, so that the notes feed the thematic tables directly.

## What you are given

A paper folder with `<id>.pdf`, `text/full.txt` (page-delimited), `text/pages/page_NNNN.txt` (page N = PDF page N),
`images/pages/page_NNNN.png` and `PROVENANCE.json`. Read `text/full.txt` from the first page to the last; read tables
and figures from the page renders where they carry what you report. Read everything, but write little: the notes keep only
what the PhD and the review's tables need.

## The format of a statement

One bullet on one line: `- <what the paper says, in your words>. [p7] "the authors' exact words that say it"`

- `[p7]` is the PDF page, not the printed page number. A quotation follows the citation of the one page it is on, copied
  exactly (join words hyphenated at a line end; change nothing else), about 30 words at most.
- Where the text is interrupted (a footnote mark, a running head), end the quotation and start a new one after it.
- A value read only from a figure or table image: cite `[p6, image]`. Absence: `- Not covered. Searched for: <terms>.`

## The template (`notes/NOTES.md`) — about 15–25 statements in all

```
---
template: ppml-1
id: <the folder name, e.g. p0013>
title: "<title as printed>"
authors: "<all authors as printed>"
year: <year>
venue: "<journal or proceedings as printed, with volume/pages where printed>"
doi: "<doi as printed, or none>"
pages_total: <number of PDF pages>
kind: <survey | primary study>
read_on: 2026-10-04
---

# <Title>

## 1. Scope and method
## 2. Privacy techniques covered
## 3. The PhD angles
## 4. NG-IoT settings
## 5. Open problems stated by the authors
## 6. Use for the PhD (reader's view)
```

1. **Scope and method** (2–4 statements, quoted): what the survey covers; how it was done (systematic or narrative,
   databases, period, number of studies) — or, for a primary study, what it proposes and how it is evaluated.
2. **Privacy techniques covered** (2–4): which mechanisms it reviews or uses (federated learning, differential privacy,
   homomorphic encryption, secure multi-party computation, secure aggregation, trusted execution, zero-knowledge proofs,
   blockchain for privacy …) and any comparison it makes.
3. **The PhD angles** (one statement per angle the paper treats; then one statement naming the angles it does not treat):
   poisoning; malicious or fake participants (Byzantine, Sybil); free riding; verification by other means; zero-knowledge
   proofs (and what the proofs show); blockchain; ZK proofs checked on the blockchain. Begin each bullet with the angle's
   name in bold, e.g. `- **Poisoning:** …`. The closing bullet: `- **Not treated:** <angles>.` (no page needed).
4. **NG-IoT settings** (1–2): the settings it covers (IoT, IIoT, IoMT, IoV, smart grid, edge/fog, 5G/6G …).
5. **Open problems stated by the authors** (2–4, quoted): especially anything on checking the learning while keeping it
   private, on cost on devices, on poisoning or fake participants, on regulation (GDPR, EDPB, AI Act).
6. **Use for the PhD (reader's view)** (2–3 bullets, pages cited, no quotation needed): what this paper gives the PhD —
   background it can be cited for, a table or taxonomy worth comparing, evidence on privacy-preserving learning in NG-IoT
   under poisoning, fake participants and free riding, with blockchain. Zero-knowledge proofs are one future direction of the
   PhD, not its core (the author, 4 October 2026): note them where present, without making them the measure of the paper.

Quotation is compulsory in sections 1 and 5 and expected for every claim and number in sections 2–4.

## The summary (`notes/SUMMARY.md`, 120–200 words)

```
# <id> · <First author> et al. <year> · <Title>

*<Venue> · <survey | primary study> · PPML review*

**In short.** <one sentence>

**Covers.** <privacy techniques; settings> [pN]

**PhD angles.** <the angles it treats, each with a few words> [pN] · Not treated: <angles>.

**Open problems.** <one or two sentences> [pN]

**Use for the PhD.** <one or two sentences>
```

The summary restates the notes; it adds nothing the notes do not support.

## Check

`scripts/.venv/bin/python scripts/check_notes_simple.py <paper folder>` reads the `template: ppml-1` header and checks
the six sections, the page citations, every quotation on its page, the quotations required in sections 1 and 5, and a
summary of 120–200 words. Correct until it passes.
