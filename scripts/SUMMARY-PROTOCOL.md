# Short-note protocol — one concise note per paper (notes/SUMMARY.md)

The long notes (`notes/NOTES.md`) are the page-cited record from which the review's tables are built. They stay
as they are. The short note is what a reader opens to learn, in about a minute, what a paper does, what it found
and why it matters to this review. It is written from the paper's input pack and holds only what is relevant.

## What you are given

- An input pack per paper: `<packs>/<ID>.md`. It holds the bibliographic record, the eligibility decision, the
  classification record, the digest of the page-cited notes, and the sentences of the current review draft that
  cite the paper. Its first lines name the file to write and the paper's full text.
- An index of the corpus: `<packs>/index.md` (ID, first author and year, title, study type, status), for naming
  related papers by their IDs.
- The checker: `scripts/.venv/bin/python scripts/check_summary.py <ID>`.

## Rules

1. Length: 150 to 250 words below the title and the line under it. Aim for about 200 to 220. Every paper gets the same
   depth; a long paper does not get a long note. Prefer two bullets to three, and one clause to two.
2. Only what is relevant to the review: privacy-preserving ML, distributed and federated learning, blockchains and
   ledgers, attacks and defences, the verification of updates, IoT and network security, regulation and
   unlearning. Leave out background the paper repeats from others, related-work lists and implementation detail.
3. Numbers matter most. Give the main results with their numbers and the page they come from, `[p7]`, taken from
   the pack. If a number is not in the pack, check it in the full text; never estimate one.
4. Distil, do not judge. The limits are the authors' own. Statements about what a paper does not cover are facts
   about its scope, never verdicts on its quality.
5. Plain English, short sentences. Common abbreviations (ML, FL, DP, HE, SMPC, ZKP, TEE, IoT, IIoT, DoS, non-IID)
   may be used as they are; spell out any other at first use.
6. Do not refer to the review's section numbers, table numbers or draft versions; they change. Say what the review
   uses the paper for in words.
7. Name other papers of the corpus only by their IDs from the index (O096, S009), and only when the relation is
   plain from this paper's pack or text, or from another paper's pack that names this one: one compares with the
   other, builds on it, or does the same thing in another way.
8. Write nothing else: no notes outside `notes/SUMMARY.md`, no changes to `NOTES.md` or to any other file. Write the
   note with the shell (a heredoc), because the Write tool may refuse the file name.

## Template

The title line gives the ID, the first author with "et al." when there are several, the year and the full title.
The line under it gives the venue, the study type, the status in the review and the theme, separated by " · ".

For a primary study:

```
# <ID> · <First author> et al. <year> · <Title>

*<Venue, short> · primary study · included · theme: <theme>*

**In short.** <One sentence: what the paper does and its main result.>

**Problem.** <One or two sentences, with pages.>

**Approach.**
- <Two to four bullets: the mechanism; for a ledger, what the ledger does; what is checked and whom the design trusts.>

**Results.**
- <Two or three bullets with numbers and pages.>

**Limits (authors).** <One or two sentences, with pages.>

**Use in this review.** <One to three sentences: what the review uses it for.>

**For the PhD.** <Optional, one sentence, only when the paper bears on verifying updates under privacy, poisoning,
fake nodes (Sybil) or free riding in blockchain-based FL for the IoT.>

**Related.** <Optional, up to three IDs, each with a few words on the relation.>
```

For a secondary study, the four middle labels are **Scope and method.** (period, number of studies, whether a
systematic protocol is followed, how the survey is organised), **Main content.** (two to four bullets: its
taxonomy, classifications or comparisons), **Findings and open issues.** (two or three bullets with pages), and
**Limits (authors).** (write "Not stated." when the survey states none; its inclusion criteria are not limits). **Use in this review.** says which of the
review's topics it covers — IoT and edge, privacy mechanisms, blockchain, attacks and defences, verification of
updates, evaluation, data-protection law — and which it does not.

For an excluded paper, the status reads `excluded (<criterion>: <reason in a few words>)`, and **Use in this
review.** says whether it is cited as background and for what, or that it is not cited. **For the PhD.** and
**Related.** are optional, as for any other paper.

## Example (primary study)

The example keeps one paragraph or bullet per line, as the note itself does. It has 247 words; most notes
should be shorter.

```
# S033 · Wang et al. 2026 · Zero-Knowledge Federated Learning: A New Trustworthy and Privacy-Preserving Distributed Learning Paradigm

*IEEE Communications Magazine 64(5) · primary study · included · theme: privacy-preserving mechanisms for ML*

**In short.** Clients prove with a zk-SNARK how close their model is to a benchmark model, and the server lets only the best-proven clients upload (Veri-CS-FL).

**Problem.** DP and HE hide data but cannot show that a client is honest, and judging clients means uploading and testing every model. [p1, p4]

**Approach.**
- A framework mapping five kinds of FL trust issue to ZKP remedies. [p2, p4]
- Each client hashes its model and proves its cosine similarity to a benchmark trained on the server's clean data (Groth16, ZoKrates); the top N then upload. The server and local training are trusted; there is no ledger. [p4, p5]

**Results.**
- Proofs are 128 bytes at any model size and verify in constant time, but proving time and keys grow with the model (8 to 4,096 parameters tested). [p7]
- With about 1,000 parameters, choosing 4 of 20 clients gives the best accuracy (over 90%), beating random choice, for about 160 bytes per client per round. [p7]

**Limits (authors).** Proving is slow for large models and needs hardware acceleration on small devices; a benchmark may exclude clients with unusual data. [p6–p8]

**Use in this review.** The clearest proof about an update's quality rather than a whole training run; cited for the trade-off between a cheap verifier and a costly prover, and as the starting point of the proposed research.

**For the PhD.** The chosen base design: one short proof per client against poisoning and free riding.

**Related.** O096, O098 (checks on updates hidden by secure aggregation); N015 (norm-bound proofs on a ledger).
```

## What the checker tests

The title line and the line under it; the labels, in order; the length; at least two page citations under
**Results.** or **Findings and open issues.**; that every ID named exists in the corpus; and that the note
mentions no section numbers, draft versions or template markup.
