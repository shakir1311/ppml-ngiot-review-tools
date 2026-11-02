# Short-note protocol V2 — one concise note per included study (notes/SUMMARY.md), 15 October 2026

Supersedes `SUMMARY-PROTOCOL.md` for the 75 studies of the PPML review. The note is what a reader opens to learn, in a
minute, what a study does and what it shows on the review's three questions: SQ1 the NG-IoT fabric and its costs, SQ2
the privacy-preserving approach with the blockchain, SQ3 security against poisoning, malicious or fake participants,
free riding and denial of service, with the evidence. It is written only from the study's page-cited notes
(`notes/NOTES.md`) and its evidence sheet; never from the paper.

## Rules

1. Length: 150 to 220 words below the title line and the line under it. Every study gets the same depth.
2. Every number and every fact carries its page as in the notes, `[p7]`; take pages only from the notes or the sheet.
   Never estimate a number; if the notes give none, say none is given.
3. Distil, do not judge. Limits are the authors' own. "The study reports no test of X" is a fact about scope, never a
   verdict. No praise words (novel, robust, efficient) unless attributed.
4. Plain English. Write as an experienced practitioner: direct, candid, a little asymmetrical. Mix very short sentences
   (3–7 words) with longer ones; never three sentences in a row of the same shape or length. No preambles, no closing
   summary. No groups of three ("fast, reliable, and efficient"). No "it is not X, it is Y" pivots. No rhetorical
   question followed by an answer. Banned words: delve, tapestry, testament, paramount, leverage, multifaceted, bolster,
   furthermore, moreover, in conclusion.
5. Abbreviations ML, FL, DP, HE, SMPC, ZKP, TEE, IoT, IIoT, IoV, IoMT, MEC, DoS, non-IID as they are; spell out others once.
6. Never mention sections, tables, figures or versions of the review, the PhD, sheets, readers or drafts.
7. Write nothing else: no change to NOTES.md or any other file.

## Template — a design (primary study)

```
# <ID> · <First author> et al. <year> · <Title>

*<Venue, short> · design · included*

**In short.** <One sentence: what the design does and its main result, with a page.>

**Fabric and cost.** <Setting, enablers (5G/6G, edge, MEC, cloud), who trains, aggregates and keeps the ledger on which tier; which costs are reported and where measured (device-class hardware, servers, simulation). Two or three sentences with pages.>

**Privacy and the ledger.** <The mechanisms, what each hides and from whom; what the blockchain does and what it holds; which parties are still trusted; law named, personal data on the chain, erasure, where the notes say. Three or four sentences with pages.>

**Threats, defences and evidence.** <Threats claimed and threats tested, the defences, who checks updates and whether it sees them; the evaluation: environment, scale, baselines, the key numbers. Three or four sentences with pages.>

**Open problems (authors).** <One or two sentences, with pages.>
```

## Template — a survey (secondary study)

```
# <ID> · <First author> et al. <year> · <Title>

*<Venue, short> · survey · included*

**In short.** <One sentence.>

**Scope and method.** <Period, number of studies, whether a protocol is followed, how it is organised. With pages.>

**What it treats.** <For the NG-IoT fabric, privacy mechanisms, the blockchain, poisoning, malicious or fake participants, free riding and data-protection law: a subject of its own, mentioned, or absent, and what it says about each that bears on the three questions. With pages.>

**Findings and open issues (authors).** <Two or three sentences with pages: what the survey concludes and what it leaves open.>
```

Checker: `scripts/.venv/bin/python scripts/check_summary.py <ID> …` — the title line and the line under it; the labels in
order; the length; at least two page citations under the evidence or findings label; no section, table, figure or
version names; no template markup; no banned words.
