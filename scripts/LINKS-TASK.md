# Citation Links — the brief for one batch

The coordinator hands out a batch with `scripts/.venv/bin/python scripts/links_queue.py next 5`, replaces `{IDS}`
below with the IDs it prints, and gives the text below the line to one agent. After the agent reports,
`links_queue.py done` records which studies pass.

---

You are recording, for a few research papers in a literature-review corpus, what each paper says about earlier work:
whom it builds on, whom it measures itself against and with what result, whom it compares with without measuring, whom
it criticises, and from whom it sets itself apart. The records feed a table that lets the review's author write
synthesis sentences ("A proposed X; B showed its cost; C cut that cost on the same benchmark") and tells which gains
can be stated (measured in the same setting) and which results can only be set side by side.

Workspace: /Volumes/Stuff/Abertay/literaturereview samples (paths below are relative to it).

Papers: {IDS}

Read first, and follow exactly: `scripts/LINKS-PROTOCOL.md` (the JSON file, the five link types, the scope, the rules).

Inputs per paper: the pack `corpus/_extraction/links-packs/<ID>.md` — the paper's folder, the corpus papers in its
reference list, and the relevant page-cited statements of its notes (their quotations are already checked against the
paper; reuse them). Where the notes are silent about a corpus reference, look in the paper's text: grep the reference
number in `<folder>/text/full.txt`, then read that page in `<folder>/text/pages/`.

Output per paper: `<folder>/notes/LINKS.json`, written with a shell heredoc
(`cat > "<folder>/notes/LINKS.json" <<'EOF' … EOF`), then run
`scripts/.venv/bin/python scripts/check_links.py <ID>` and fix until it prints PASS. Finish one paper before the next:
each paper that passes is saved progress even if the batch stops.

Rules that matter most:
- Record what the papers say in their own words. Every link needs evidence: a verbatim quotation from the text with
  its page ("p4"). Do not read values from tables, figures or plots, and do not judge whether a paper's data support
  its statements; a comparison the text does not state in words is left out.
- Quotations must be verbatim and stand on the page given. Figure and table captions count as text.
- "says": one sentence, at most 45 words, faithful to what the paper claims — the paper's claim, not a verdict.
- "result": the comparison as the paper words it in its text; do not compute new percentages. If the text says a
  baseline was run but gives its outcome only in a figure or table, "result" is "not stated in the text".
- A claim against unnamed "prior work" is attached to named works only where the same passage (the same paragraph,
  or the one just before it in the same subsection) names them.
- A run without the privacy or security mechanism (plaintext, no DP, outside the enclave, no defence, one site's
  data alone) is a baseline; ablations
  of the paper's own scheme are not links.
- A group claim attaches to each named member only if it covers all ("all", "the above schemes"), not "most" or
  "typically"; a hedged claim that carries its own citations ("typically assume X [30], [31]") attaches to the works
  it cites. Rows of a comparison table are not recorded unless the text states the comparison in words.
- `measured_against` only when the paper's own experiments ran the other scheme or baseline in the same setting;
  asymptotics, feature tables or numbers borrowed from another paper are `compared_not_measured`, and so is a
  comparison where the text does not make clear that the paper ran the other scheme.
- A stated cost or weakness is a `critique`; a difference of scope or aim is `positions_against`.
- Works outside the corpus (`"to": null`) only as `measured_against` (baselines such as FedAvg, SignSGD, plaintext
  training, an insecure baseline).
- Every corpus paper in the pack's reference list appears either in a link or in `cited_only`.

Do not modify any other file (not NOTES.md, not SUMMARY.md, not the scripts); no git, builds, or anything that
publishes or uploads.

Reply briefly: one line per paper with its counts and PASS/FAIL, then at most five lines on anything in the protocol
that was ambiguous or hard to apply.
