# Brief thematic notes — the standing rule for every paper we download (template ppml-2, 5 October 2026)

**Applies to every paper downloaded at any time**, for the PPML review or the PhD. The author, 5 October 2026: "you need to
extract them in full, make brief notes and summaries relevant to our phd and our research paper. i dont want gigantic
notes. and keep the thematic aspect while making notes and summaries - i.e we should be able to thematically analyze based
on notes and summaries. please record these as permanent rules for whatever we download at any time."

It replaces ppml-1 (`NOTES-PPML-PROTOCOL.md`, kept for the notes already written with it) for every new paper. Its
sections follow the five layers of the review and the PhD (fabric, privacy, trust, attacks and defences, regulation), and
its header carries theme tags from fixed lists — the same values as the review's extraction form — so that the notes and
summaries of all papers can be tabulated and analysed by theme (`scripts/paper_ppml/notes_themes.py`).

## The pipeline for a downloaded paper

1. **File** the PDF in its own folder with `PROVENANCE.json` (source file or URL, SHA-256, who downloaded it, when).
   Published versions only; a preprint or an unedited copy ("in press", "early access", "author's version which has not
   been fully edited", "Journal Pre-proof") is recorded as such in PROVENANCE.json (`version_note`) and in the notes' header
   line, and replaced when the final version is available.
2. **Extract in full** with the workspace pipeline, never ad hoc: `scripts/.venv/bin/python scripts/extract_paper.py
   <pdf> --quiet`, then `scripts/.venv/bin/python scripts/ocr_scanned.py <folder>`. This gives `text/full.txt`,
   `text/pages/page_NNNN.txt` (page N = PDF page N) and `images/pages/page_NNNN.png`.
   Then `python3 scripts/paper_ppml/version_notes.py <parent folder>` flags any copy whose first pages say it is not the
   final version (index labels are not trusted for this).
3. **Read the whole paper** (`text/full.txt`, first page to last; tables and figures from the page renders where they
   carry what you report). Read everything, write little.
4. **Write** `notes/NOTES.md` and `notes/SUMMARY.md` by this template.
5. **Check**: `scripts/.venv/bin/python scripts/check_notes_simple.py <folder>`; correct until it passes.
6. **Index and audit**: `python3 scripts/search_ppml/corpus_match.py` (the corpus index), then
   `scripts/.venv/bin/python scripts/paper_ppml/audit_corpus_copies.py`: every filed copy is byte-identical to the download
   (SHA-256), fully extracted (one text page and one page image per PDF page), noted (checker passes), recorded and indexed.
   An unedited copy is replaced by its final version with `scripts/paper_ppml/replace_with_final.py <id> <pdf>`, which keeps
   the old copy in `_superseded/` and re-anchors the notes and records to the new pages.

## Statements

One bullet on one line: `- <what the paper says, in your words>. [p7] "the authors' exact words that say it"`

- `[p7]` is the PDF page. A quotation follows the citation of the one page it is on, copied exactly (join words
  hyphenated at a line end; change nothing else), at most about 30 words.
- A value read only from a figure or table image: `[p6, image]`. Absence: `- Not covered. Searched for: <terms>.`
- Describe; do not judge (distil, don't criticise). Record what the paper itself claims, does and tests. For a survey,
  record what it covers and concludes; for a primary study, what it builds and shows.

## The notes (`notes/NOTES.md`) — brief: 12–24 statements, at most 900 words below the header

```
---
template: ppml-2
id: <the folder name>
title: "<title as printed>"
authors: "<all authors as printed>"
year: <year>
venue: "<journal or proceedings as printed>"
doi: "<doi as printed, or none>"
pages_total: <number of PDF pages>
kind: <survey | primary study>
read_on: <date>
themes:
  layers: [privacy, trust]
  angles: [poisoning, blockchain]
  settings: [IoV-vehicular]
  mechanisms: [HE, DP]
  threats_claimed: [poisoning, inference]
  threats_tested: [poisoning]
---

# <Title>

## 1. Scope and method
## 2. NG-IoT fabric
## 3. Privacy plane
## 4. Trust plane
## 5. Attacks and defences
## 6. Regulatory layer
## 7. Open problems stated by the authors
## 8. Use for the PhD and the review (reader's view)
```

**Theme tags** — one line per key, values only from these lists (an empty list `[]` where none applies):

| Key | Values |
|---|---|
| layers | fabric, privacy, trust, attacks, regulation — those the paper treats in substance |
| angles | poisoning, malicious-fake, free-riding, verification, zkp, blockchain, zk-on-chain — those it treats |
| settings | IoT-general, IIoT, IoMT-healthcare, IoV-vehicular, smart-grid-energy, UAV-space, smart-city-home, maritime, supply-chain, communication-network |
| mechanisms | DP, LDP, HE, SMPC, secret-sharing, secure-aggregation, TEE, ZKP, functional-encryption, pseudonyms, encryption (symmetric or public-key encryption of data or updates not covered by the others), FL-only (privacy rests only on keeping data local — never together with another mechanism) |
| threats_claimed | poisoning, backdoor, byzantine-malicious, sybil-fake, free-riding, inference, malicious-server, collusion, dos-ddos, single-point-of-failure, tampering, evasion, other |
| threats_tested | the same values, for attacks actually run in an experiment or simulation only; always `[]` for a survey |

*Claimed* means the paper's own threat model, security analysis or stated defence counters the threat (for a survey: the threats it covers as threats to learning) — not a threat named only in the background or related work. Reputation attacks (on-off, bad-mouthing, good-mouthing) are `byzantine-malicious`; whitewashing or re-entering under a new identity is `sybil-fake`; adversarial examples at inference are `evasion`. A survey's own counts (e.g. how many reviewed studies test poisoning) go in section 5, not in the tags.

*Tested* means the attack was run against the design itself — its learning, participants, aggregator or ledger — in an experiment or simulation. Not tested: a security proof, formal or model checking (e.g. AVISPA), a cryptanalysis, or the attack classes an application (such as an intrusion detector) detects in its data — those are what the application looks for, not threats to the learning, and are not tagged at all.

*Minimum for a tag*: a layer or angle is tagged when the paper treats it as part of its contribution or, for a survey, covers it in at least a paragraph or a table row with content. A single mention, or only a call for future work, is not tagged (it may still appear in a statement).

1. **Scope and method** (2–3, quoted): what it proposes or covers; how (for a survey: systematic or narrative,
   databases, period, number of studies; for a primary study: what is built and how it is evaluated).
2. **NG-IoT fabric** (1–3): settings; who trains, aggregates, checks and keeps the ledger, on which tier (device, edge,
   fog, cloud); enablers (5G/6G, edge, MEC); whether any cost is measured on device-class hardware or a real link.
3. **Privacy plane** (1–3): the mechanisms; what they hide (data, updates, model, identity) and from whom (server,
   other participants, ledger nodes, public); reported cost of the protection.
4. **Trust plane** (1–3): the ledger (type, platform, what is written on-chain, what it does); what is checked about
   updates, training or aggregation, by whom, and whether the checker sees the update; zero-knowledge proofs and what
   they show. Zero-knowledge proofs are one future direction of the PhD, not its core: note them where present.
5. **Attacks and defences** (1–3): threats claimed against threats tested by running an attack; the defences; the
   evaluation (data sets, baselines, attacker share, code released or not).
6. **Regulatory layer** (0–2): laws or guidelines named (GDPR, EDPB, AI Act …); whether personal data reach the
   ledger; erasure. If absent: `- Not covered. Searched for: GDPR, EDPB, regulation, personal data, erasure.`
7. **Open problems stated by the authors** (1–3, quoted): especially on checking the learning while keeping it private,
   cost on devices, poisoning, fake participants or free riding, and regulation.
8. **Use for the PhD and the review** (1–3, pages cited as `[p15]`, no quotation needed): what the paper gives — background, a
   taxonomy or table to compare, evidence on PPML in the NG-IoT under poisoning, fake participants and free riding.

A section the paper does not touch gets one `Not covered. Searched for: …` statement; it is never padded. Quotation is
compulsory in sections 1 and 7 and expected for every claim and number in sections 2–6. The theme tags must agree with
the sections: a layer or angle is tagged only if a statement in the notes shows it.

## The summary (`notes/SUMMARY.md`, 150–220 words) — the same themes, one line each

```
# <id> · <First author> et al. <year> (both names if two authors) · <Title>

*<Venue> · <survey | primary study> · <settings>*

**In short.** <one sentence>
**Fabric.** <settings, tiers, cost measured or not> [pN]
**Privacy.** <mechanisms; what is hidden from whom> [pN]
**Trust.** <ledger and checks; does the checker see the update; ZK if any> [pN]
**Attacks.** <claimed vs tested; evaluation> [pN]
**Regulation.** <laws named, personal data on chain, erasure — or "not covered">
**Open problems.** <one or two> [pN]
**Use.** <for the PhD and the review>
```

The summary restates the notes and adds nothing they do not support. A layer the paper does not touch gets
"not covered" on its line, so every summary can be read across papers line by line.

## Check

`scripts/check_notes_simple.py` reads `template: ppml-2` and checks: the header fields and theme tags (values from the
lists above only); the eight sections with a statement each; page citations within the paper; every quotation on its
page; quotations in sections 1 and 7; at most 900 words of notes; a summary of 150–220 words with its eight labelled lines.
