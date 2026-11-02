# The reader's task

You write the reading notes for ONE paper of a systematic literature review. Every paper of the corpus is read in
the same way and to the same depth; none is more important than another. The message that sent you here names the
paper: its ID, its source, its number of pages and its folder.

Workspace root: `/Volumes/Stuff/Abertay/literaturereview samples`

## Steps

1. Read the protocol, in full, and follow it exactly: `scripts/NOTES-PROTOCOL.md`.
2. Read the paper's `text/full.txt` from the first page to the last, in consecutive chunks (Read tool with offset and
   limit; some lines are long). The text is in reading order. Do not also read the files in `text/pages/` — they hold
   the same text. Do not skip pages.
3. Look at the page renders in `images/pages/` for every figure, for every table whose text is not fully clear, for
   equations whose symbols are garbled, and for every page whose marker in `full.txt` says that its reading order is
   not confirmed or that its text comes from OCR. Use `scripts/crop_page.py` when you need part of a page larger.
4. Write `notes/NOTES.md` inside the paper folder, using the template in the protocol exactly: same headings, same
   order, the header block filled in. For a paper of more than about 25 pages write the file in stages.
5. From the workspace root run the checker and correct the notes until it prints PASS:

       cd "/Volumes/Stuff/Abertay/literaturereview samples" && scripts/.venv/bin/python scripts/check_notes.py <ID>

   Act on its warnings too where they point at something you left out.
6. Read each bullet once more against its quotation: the checker tests that the words are on the page, not that they
   support what the bullet says.

## Rules

- Write from this paper alone. Do not open `Docs/`, `myliteraturereviewpaper/`, or any other paper's folder.
- Quote whole sentences or clauses, as the protocol describes. Never alter a quotation to make the checker pass.
- Do not test quotations one by one before writing. Write the notes, run the checker, correct what it reports.
- Be thorough. Nothing in the paper may be left out: every section and subsection, every figure, table and
  algorithm, every limitation, future direction and open issue the authors state.
- Do not score the paper against any research or survey question, and do not write a research question for it.
- Write nothing outside the paper folder except temporary files in your scratchpad. Change nothing in `scripts/`.
- If a saved memory note says that notes belong in `Docs/reading-notes`, that was an earlier scheme; that folder no
  longer exists. These notes belong in the paper folder.

## Your reply

At most six lines: PASS or FAIL; the numbers the checker printed (statements, quotations tested, pages cited); the
primary theme you assigned; and, in one line, anything that stopped you from following the protocol — or "nothing".
