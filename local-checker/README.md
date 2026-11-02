# Local Fact Checker

Checks written statements about a paper — from evidence sheets, notes, summaries, or any future synthesis — against
that paper's own extracted text, **on this Mac**. No language model, no outside service, no upload: the paper text never
leaves the machine, and nothing the checker writes contains it.

Built 11 October 2026, after the decision that no paper goes to Claude (workspace `CLAUDE.md`). Claude writes the
statements and reads the verdicts; only this checker reads the papers.

## What it answers

For one statement and one paper, it answers one of three things, with the page:

| Verdict | Meaning |
|---|---|
| **supported** | a passage of the paper says it (or plainly implies it), and that passage carries the statement's numbers, its key words and none of their opposites |
| **contradicted** | a passage about the same thing says something incompatible |
| **not found** | nothing in the paper settles it — a person looks |

It never edits anything, and it never decides on its own what to correct (see *How the verdicts are used*).

## How it works

1. **Pages.** The paper's extracted pages (`text/pages/page_NNNN.txt`, plus `text/pages_ocr/` where a page was OCR'd)
   are cut into every passage of one, two and three consecutive sentences, each tagged with its page.
2. **Search.** A BM25 word search (`rank-bm25`) picks the 40 passages most like the statement; passages of any pages
   given as hints are added.
3. **Word check** (deterministic). A passage can support a statement only if
   - it contains **every number** of the statement (`20,000` = `20 000`; `six` = `6`; `%`, `×`, `~`, `>` read as words);
   - for **opposite words** (public/private, permissioned/permissionless, on-chain/off-chain, increase/decrease,
     horizontal/vertical, honest/malicious, public key/private key, …) it uses the statement's side **and not the
     other side** — a passage that names both is left to a person;
   - every **multi-word name** of the statement ('Proof of Training Quality', 'NIST CPS Framework') appears in it as is;
   - it contains at least two thirds of the statement's **content words** (`--words`, default 0.67).
4. **Meaning check.** A natural-language-inference classifier,
   [`MoritzLaurer/DeBERTa-v3-large-mnli-fever-anli-ling-wanli`](https://huggingface.co/MoritzLaurer/DeBERTa-v3-large-mnli-fever-anli-ling-wanli)
   (revision `b3546ea6b0346eb6f8d5d68b13c7dc6d0376b3d7`, trained on MNLI, FEVER, ANLI, LingNLI and WANLI), scores each
   passage against the statement: entails / neutral / contradicts. It is a classifier, not a text generator.
5. **Verdict.** *supported* when a passage that passed the word check entails the statement with probability ≥ 0.80;
   *contradicted* when a passage about the same thing (holding at least half of the statement's content words, whatever
   its numbers or opposite words) contradicts it with probability ≥ 0.80;
   otherwise *not found*.

Same input, same output: two runs give identical verdicts and scores.

## Safety

- Reads the paper pages and the statements file; writes only the results file, and **refuses to write anywhere outside
  this folder** (so never next to sheets, notes, summaries or papers).
- The results hold only ids, verdicts, scores and page numbers — no passage text (checked by the tests).
- The tests confirm the input files are byte for byte unchanged after a run.

## How the verdicts are used

A record (sheet, notes, summary) is changed **only when three things agree**:

1. the record's statement is **contradicted**,
2. the other record's statement (or the proposed correction) is **supported**,
3. on the **same page** where a quotation already proven to be on that page sits.

Anything else — one verdict alone, *not found*, verdicts on different pages — goes to a person, with the pages to look
at. Every change keeps the untouched original in `notes-verifier/history/<id>/` and is listed in a report in `Docs/`.

## Validation (11 October 2026)

**Software tests** — `test_checker.py`, on made-up text only: 22/22 pass (word check, page reading, search, a full run
on a made-up paper, inputs unchanged, no text in the output, refuses to write outside the folder).

**Accuracy** — on statements whose truth is known from quotations already proven to be on their page. The rules were
set on the development set and on held-out set 1 (which became development when it led to the name rule and the 0.67
word share); held-out set 2 was written afterwards and run once.

| Test set | True statements | False statements |
|---|---|---|
| Development (250): 150 proven quotations, 62 altered copies (one number or key word changed), 38 hand-written paraphrases | 165 supported, 9 not found, 2 contradicted | 70 contradicted, 3 not found, 1 supported |
| Held-out 1 (62 hand-written) | 31 supported, 5 not found, 2 contradicted | 23 contradicted, 1 not found |
| **Held-out 2** (61 hand-written, unseen, with traps: swapped names, numbers, roles, nouns) | 37 supported, 2 not found | 19 contradicted, 2 not found, **1 supported** |
| Spot check on real flagged points (17 with known answers) | 11 supported | 3 contradicted, 3 not found |

Over all sets: **244 of 246 *supported* verdicts right (99.2 %)**, **115 of 119 *contradicted* verdicts right (96.6 %)**;
*not found* carries no information either way. The errors:
- *supported* for a false statement (2): "the best horizontal accuracy is reached with two participants" (N008 p11,
  not yet checked by a person), and "the models are aggregated on a centralized cloud server" (N010): the author
  checked page 1 — it only describes the usual FL approach, and the checker took that for the paper's own design.
  (A third, N009 "clients compete to validate updates", was the hand label's error: the author found page 4 says so.)
- *contradicted* for a true statement (4): N012 p9, S026 p4, N018 p4, N016 p5 — another passage of the same paper
  seems to say otherwise (a different setting, an earlier version of the design, a figure caption).

That is why one verdict never changes a record: a correction needs a *contradicted* sheet statement **and** a
*supported* notes statement **on the page of a proven quotation**. With the error rates above, the chance that all
three agree wrongly is well under one in a thousand.

Re-run the validation after any change to the code, the model or the thresholds:

    local-checker/.venv/bin/python local-checker/test_checker.py
    local-checker/.venv/bin/python local-checker/build_calibration.py
    local-checker/run.sh local-checker/data/calibration.jsonl local-checker/data/calibration-results.jsonl
    local-checker/run.sh local-checker/data/heldout.jsonl local-checker/data/heldout-results.jsonl
    local-checker/run.sh local-checker/data/heldout2.jsonl local-checker/data/heldout2-results.jsonl
    python3 local-checker/evaluate.py local-checker/data/calibration-results.jsonl
    python3 local-checker/evaluate.py local-checker/data/heldout-results.jsonl
    python3 local-checker/evaluate.py local-checker/data/heldout2-results.jsonl

A new held-out set should be written for every substantial change: a set the rules were tuned on no longer tests them.

## Local language models (11 October 2026): what was tried and what is kept

Run by Ollama on this Mac (`ollama-serve.sh`; models kept in `.cache/ollama/`; traffic stays on 127.0.0.1).

**Context judge — kept** (`context_judge.py`, used by `check_claims.py --judge MODEL`): one closed question per passage —
the authors' own work or other work, and does it support the statement. On 115 hand-labelled passages
(`data/context-set.jsonl`, `judge_bakeoff.py`): Gemma 4 26B recognised 73/78 own-work passages and wrongly accepted
1/37 other-work passages (a mixed sentence; arguably right), 0.4 s each; Qwen3.5 35B 62/78 and 1/37. Use `gemma4:26b`.

**Regenerating sheet answers — not adopted** (`regenerate.py`, `sections.py`). Five studies × five questions (P1 P2 P3
P5 P6), scored against the existing sheets (tags identical / partly / different; quotations found on their page):

| Set-up (Gemma 4 26B) | Tags identical | Partly | Different | Quotations on page | Per answer |
|---|---|---|---|---|---|
| no thinking, whole paper | 44 % | 25 % | 31 % | 73 % | ~7 s |
| no thinking, sections only | 49 % | 23 % | 28 % | 80 % | ~9 s |
| thinking + decision rules (audit guide) + two worked examples, whole paper | **60 %** (45/75) | 36 % | 4 % | 81 % | ~55 s |

Thinking needs the makers' sampling settings (temperature 0 makes thinking models loop). Qwen3.5 27B (dense), same
set-up, was stopped after 3 answers of N011 at the author's request: level with Gemma (8/13 tags identical, 5 partly,
0 different, against Gemma's 8/4/1), quotations on their page 5/8 (Gemma 11/13), about 5 min per answer (≈ 97 s to
read a paper, ≈ 21 tokens/s; > 2 days for the 600 answers). A 48 GB Mac holds models of about 30 billion parameters; the sheets were written and audited by a much larger
model. Conclusion: a local model can *check* sheets (fact checker, context judge, and as a second reader that rarely
contradicts a sheet outright — 4 %) but cannot yet *write* them to the standard the paper needs (≥ 90 % identical).
For future papers: local draft → local checks → the author's confirmation, never unattended.

## What it cannot do

- **Figures, charts and images**: values read off a plot are not in the text.
- **Tables** only as far as their text came out of the PDF in reading order.
- **Context.** It judges each passage on its own and cannot tell the authors' own design from what they say about
  other work or the usual approach (the N010 error above). A rule that set aside related-work sections, citation
  sentences and sentences with 'traditional', 'existing', 'et al.' and the like was built and tested on 11 Oct: it did
  not catch the N010 sentence and made other results worse, so it was removed. This is the main reason a person (with
  `show.py`) or a reading model has the last word.
- **Statements that need several passages put together** (who sees what across a protocol), or **classifications**
  (is this a "subject" or "mentioned", which tag applies): it checks facts the paper states, not judgements about it.
- **Paraphrases far from the paper's words** come back *not found*.
- **Extraction defects**: text extracted before 28 Sep 2026 may interleave columns; OCR pages may hold errors.
- It does not read a paper and produce notes: someone has to write the statements first.

## Use

Set up once (own Python environment and the tested model, ~1.8 GB, all inside this folder):

    local-checker/setup.sh

Write the statements as JSON lines, one per line:

    {"id": "N011-P5-sheet", "key": "N011", "claim": "The task publisher is honest-but-curious.", "pages": [4]}

`key` is the study id in `notes-verifier/data/papers.json` (which says where its pages are); `pages` is optional (pages
always searched, e.g. the page a quotation cites). Then:

    local-checker/run.sh statements.jsonl local-checker/data/results.jsonl

Each result line: `id, key, verdict, entails, entails_page, contradicts, contradicts_page, passages_scored,
entails_without_word_check, entails_passage, contradicts_passage` (passage numbers, no text).

To see the passages a verdict rests on — for the person checking, in the browser, never printed:

    local-checker/.venv/bin/python local-checker/show.py local-checker/data/results.jsonl ID [ID ...]

## Files

| File | What |
|---|---|
| `check_claims.py` | the checker |
| `run.sh`, `setup.sh`, `requirements.txt` | running it, setting it up, exact package versions |
| `test_checker.py` | software tests on made-up text |
| `show.py` | opens the passages behind verdicts in the browser, for the person checking |
| `build_calibration.py`, `evaluate.py` | builds the development set; scores a results file |
| `data/calibration-hand.jsonl`, `data/heldout.jsonl`, `data/heldout2.jsonl`, `data/spotcheck-real.jsonl` | hand-written test statements, each with the record and page that settle it |
| `data/*-results.jsonl` | the validation results quoted above |
| `.venv/`, `.cache/` | Python environment and model (not records; rebuilt by `setup.sh`) |

## What a run prints

The checker has no window; it prints one verdict per statement and writes the same to a JSONL file, never a word of the paper (the check of the V85 introduction's cited claims):

```
c1-S010          not found     entails 0.00 (pNone)  contradicts 0.00 (p13)
c1-p0747         not found     entails 0.00 (pNone)  contradicts 0.00 (pNone)
c2-S019          contradicted  entails 0.00 (pNone)  contradicts 0.90 (p5)
c2-p0599         contradicted  entails 0.00 (pNone)  contradicts 0.98 (p14)
c3a-S007         contradicted  entails 0.17 (p14)  contradicts 1.00 (p16)
c3a-p1601        supported     entails 0.94 (p10)  contradicts 0.99 (p5)
```
