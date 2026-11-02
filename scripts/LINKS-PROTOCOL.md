# Citation Links — protocol

*Citation Links* is the review's citation context analysis: what each primary study says, in its own words, about earlier work. How to run and resume it: `scripts/README.md`, section 5.

For each **primary study B** of the review, record what B says about **earlier work**: whom it builds on, whom it
measures itself against and with what result, whom it compares itself with without measuring, whom it criticises, and
from whom it sets itself apart. The records let the review trace lines of work ("A proposed X; B showed its cost; C
cut that cost on the same benchmark") and tell which gains can be stated and which results can only be set side by
side.

**We record what the papers say, in their own words.** Every link rests on a statement in the paper's text, quoted
verbatim with its page. We do not read values from tables, figures or plots, and we do not judge whether a paper's
data support what it says: a claim is recorded as the paper makes it.

## What you are given

- A **pack** per paper: the references of B that are corpus papers (reference number, corpus ID, title), and the
  statements of B's `notes/NOTES.md` on its approach, results, limitations, positioning and baselines. Every statement
  there carries its page, and its quotations have been checked against the paper.
- The paper's folder: `notes/NOTES.md` (all statements) and `text/` (the extracted text, page by page).

## What you write

`<paper folder>/notes/LINKS.json`, then run `scripts/.venv/bin/python scripts/check_links.py <ID>` until it passes.

```json
{
  "id": "O097",
  "links": [
    {"to": "O096", "to_name": "RoFL", "ref": "33", "type": "critique",
     "says": "Proving a bound on each entry with Bulletproofs, as RoFL does, costs communication linear in the length of the update and does not work with ciphertext packing.",
     "evidence": [{"page": "p4", "quote": "Using Bulletproofs to prove a bound on each entry of the input vector (as in RoFL [33]) results in linear communication"}]},
    {"to": null, "to_name": "SecAgg of Bell et al.", "ref": "6", "type": "measured_against",
     "says": "Its RLWE-based encoding is faster than the PRG-based SecAgg it generalises, measured in the same experiments.",
     "metric": "client encoding time", "result": "up to 5x faster for analytics and more than 8x for FL on long inputs",
     "setting": "same runs, averaged over 100; laptop", "same_setting": true,
     "evidence": [{"page": "p13", "quote": "Overall, RLWE encoding achieves roughly up to 5x speedup in the FA setting"}]}
  ],
  "cited_only": ["O068", "O101"]
}
```

### The five types of link

| type | when | extra fields |
|---|---|---|
| `builds_on` | B adopts or extends A's method, protocol, definition, threat model, setup or data | — |
| `measured_against` | B's own experiments run A (its code or a reimplementation) or a named baseline, in the same setting, so a difference can be stated | `metric`, `result`, `setting`, `same_setting: true` |
| `compared_not_measured` | B compares itself with A by asymptotic costs, a feature table, or figures taken from A's paper — different settings, so results can only be set side by side | `result` (what B claims), `setting` (the basis: "asymptotic costs, Table 1"), `same_setting: false` |
| `critique` | B states a limitation, weakness or cost of A | — |
| `positions_against` | B states how it differs from A without judging A | — |

Where the text does not make clear that B ran the other scheme (rather than taking its figures from its paper),
record `compared_not_measured`. A stated cost or weakness of A is a `critique`; a difference of scope or aim ("not
designed for malicious edge servers") is `positions_against`.

The basis of a `compared_not_measured` link may also be a comparison made in words only ("our advantage over A is
full privacy").

One pair can carry several links (B builds on A *and* measures against it). A mere citation — A named for background,
listed among examples, cited for a fact — is not a link: put A's ID in `cited_only`. Nor is a statement that B is
similar to A ("A also uses ZKPs") without B adopting A's method or saying how it differs.

### Scope

- `to` is a corpus ID for a corpus paper. **Every corpus paper in the pack's reference list must appear once, either
  in `links` or in `cited_only`.** Where B cites a corpus paper without a reference number (author–year style), find
  it by its authors and year.
- Works outside the corpus (`"to": null`) are recorded **only as `measured_against`**: the baselines of B's own
  experiments, such as FedAvg, SignSGD, plaintext training or an insecure baseline, or earlier schemes that B ran.
- A run without the privacy or security mechanism — plaintext training, the model without DP, aggregation outside
  the enclave, training with no defence, a model trained on one site's data alone, an insecure baseline — is a baseline (`measured_against`, outside the corpus). Ablations of B's own
  scheme (with and without one of its own parts, at another scale or setting) are not links.

### Every entry

- **Pages are required.** Every link has `evidence`: one or more items, each a verbatim `quote` from the paper's
  text with the `page` (`"p4"`) where it stands; one quotation per item. Take them from the statements of NOTES.md
  where they exist (already checked); otherwise quote the text exactly as printed. Figure and table captions are
  text and may be quoted; the values inside a table or plot may not.
- **Text only.** No values read from tables, figures or plots. A comparison that the text does not state in words is
  not recorded. But where the text says that a baseline was run ("we compare with SignSGD and FL without
  quantization") and gives the outcome only in a figure or table, record the `measured_against` link with
  `"result": "not stated in the text"`: the words say the comparison was made; nothing is read from the figure.
- **Several quotations per link** are allowed: each evidence item is one quotation from one page.
- **Unnamed "prior work".** A claim against "prior work" or "existing schemes" is attached to named works only where
  the same passage names them — the same paragraph, or the paragraph just before it in the same subsection;
  otherwise it is not recorded. A claim about a group attaches to each named member only when it covers all of them
  ("all", "the above schemes"); one about "most of them" or what is "typical" of them attaches to none, since it does
  not say which. A hedged claim that carries its own citations ("most works have designed specialized consensus
  algorithms [2, 51]", "typically assume a validation dataset [30], [31]") attaches to the works it cites.
- **Feature tables.** A work that appears only as a row of a comparison table is not recorded from the table; record
  `compared_not_measured` where the text states the comparison in words.
- `says` is one plain sentence, at most 45 words, in the reviewer's words, **faithful to what B says** — B's claim,
  not our verdict on it. No "fails", "flawed" or other judgements of our own.
- `result` gives the comparison as B words it in its text, with any figure it states ("up to 8x faster", "same
  accuracy", "much higher communication than ACORN"). Do not compute new percentages.
- `setting` for `measured_against`: data, model, hardware, clients — what makes it the same setting.
- `to_name` is the short name B uses (scheme name, or first author and year).
- `ref` is B's reference number as a string, or `null` for author–year citations.

## How to work

1. Read the pack. For each corpus reference, find what B says about it: first in the pack's statements (they cite
   B's reference numbers), then, if the notes are silent, in the text of the pages where the number is cited
   (`grep -n "\[33\]" text/full.txt`, then read that page in `text/pages/`).
2. Find B's measured baselines in the statements on the evaluation ("Baselines and comparison", results).
3. Write LINKS.json with a shell heredoc (`cat > …/notes/LINKS.json <<'EOF'`), run the checker, fix, repeat.

## What the checker tests

JSON shape and types; `to` is a corpus ID or null (null only for `measured_against`); no link to B itself; the extra
fields of each type; `says` at most 45 words; every evidence item has a page within the paper and a quotation found
on that page; every corpus reference found by `scripts/review/ref_links.py` appears in `links` or `cited_only`.
