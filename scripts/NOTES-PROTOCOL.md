# Reading protocol — how the notes for one paper are written

Template 2 · 28 September 2026

The notes are the data extraction of a systematic literature review. They must let someone who has never opened the
paper say what it is about, what it solved, what it found and what it left open — and check every one of those
statements against the page it came from. The review's own questions are set later, from the synthesis of all the
notes; nothing here is written towards a question.

Three rules govern everything below.

1. **Nothing is missed.** The paper is read from its first page to its last. Every section and subsection, every
   figure, table and algorithm is accounted for in the notes. Every page of the body is cited at least once.
2. **Every statement carries its page.** A statement without a page citation is not a note. Wherever the paper's own
   words can be given, they are given, exactly — a page citation with a quotation can be checked; one without cannot.
3. **The notes report the paper, not the reader.** What the authors say goes in sections 1–15. What the reader thinks
   goes in section 16 only, and still points at pages.

The notes are written from the paper alone. Do not open earlier notes, earlier tables, the review paper
(`myliteraturereviewpaper/`), anything in `Docs/`, or another paper's folder. Do not score the paper against any
research or survey question, and do not write a research question for it.

## What you are given

One paper folder, `corpus/<corpus>/.../<Paper>/`, holding:

| File | Use |
| --- | --- |
| `text/full.txt` | The whole paper in reading order, page by page. Each page starts with `========== [ PAGE n / N ] ==========`. **This is what you read, once.** |
| `text/pages/page_NNNN.txt` | The same text, one file per page. Do not read these as well. |
| `text/variants/` | Each page as two other engines read it. For checking only. |
| `text/full_layout.txt` | Layout-preserving text: the columns of a table stay in place. Use it for tables. |
| `text/full.md` | Markdown rendering with headings. Useful for the heading structure. |
| `images/pages/page_NNNN.png` | A render of every page. |
| `images/figures/`, `tables/` | Cropped figures; detected tables as CSV and Markdown (may hold fragments of figures). |
| `metadata.json` | Page count, PDF metadata, and for every page whether its reading order is confirmed. |

Page numbers in the notes are always the **PDF page numbers** (`n` in the page marker), not the journal's printed
page numbers.

**Pages marked in `full.txt`.** A page marker that says *reading order not confirmed … check against the page
render* means the engines that read the page disagree about its order — usually a page that is mostly a table, a
figure with many labels, or a list. Read such a page on its render (`images/pages/`) and name it in the coverage
log. A marker that says *OCR* means the page has no text layer and the text comes from character recognition.

## Tools

Run from the workspace root, with `scripts/.venv/bin/python`:

| Command | What it does |
| --- | --- |
| `scripts/check_notes.py <ID>` | Checks the notes against the paper. The notes are finished when it prints `PASS`. |
| `scripts/try_quotes.py <ID> <page> "<words>"` | Are these words on that page? |
| `scripts/try_quotes.py <ID> --find "<words>"` | On which page are these words? |
| `scripts/try_quotes.py <ID> --split <page> "<passage>"` | Where the extracted text interrupts a passage. |
| `scripts/crop_page.py <ID> <page> [x0 y0 x1 y1] [--name table1]` | Renders part of a page larger, into `images/crops/`. |

## How to read

1. Read `text/full.txt` in consecutive chunks until the end. Do not skip pages, including appendices. Searching for
   terms is allowed afterwards to double-check an absence, never instead of reading.
2. While reading, keep track of the heading structure and of which page each thing is on.
3. Look at the page render for every figure, for every table whose text is not fully clear, for every equation
   whose symbols are garbled in the text, and for every page marked in `full.txt`.
4. Write `notes/NOTES.md` in the paper folder, using the template below exactly (same headings, same order). For a
   paper of more than about 25 pages write the file in stages — the header and sections 1–5 first, then the rest
   appended — so that no single step has to carry the whole file.
5. Run the checker and correct the notes until it passes. Do not test quotations one by one before writing: copy
   them from the text as you write, run the checker on the finished notes, and correct what it reports. Act on its
   warnings too where they point at something left out.

Never alter a quotation to make it pass, and never delete a statement only because its page is hard to find.

## The format of a statement

Every statement is one bullet on one line:

    - <what the paper says, in your words>. [p7] "the authors' exact words that say it"

- **Page citation:** `[p7]`, a range `[p7–9]`, or several `[p7, p12]`. It comes after the statement.
- **Quotation:** in straight double quotes, directly after the citation of **the one page it is on**. Copy the words
  exactly. Join a word that the text split with a hyphen at a line end (`encryp-` `tion` → `encryption`); change
  nothing else. Keep a quotation to about 40 words.
- **Several quotations in one bullet:** each follows its own citation, also when the page is the same:
  `[p7] "first passage" [p7] "second passage" [p9] "third"`.
- **Over a page break:** two quotations, each after its own page: `[p7] "…end of the page" [p8] "start of the next…"`.
- **Where the text is interrupted** — by a footnote mark, a running head, a figure or a caption that sits inside the
  sentence in the extracted text — end the quotation before the interruption and begin a new one after it. Leave
  out words in the middle with ` … ` only where you really omit words of the paper. Where the paper itself prints
  an omission mark such as `[...]`, keep it; the parts on either side are tested separately.
- **Double quotation marks are for quotations only.** Everything between them is tested against the page. Put a
  term, a label or a title in single quotation marks or italics. Where the quoted words themselves contain double
  quotation marks, write those as single ones.
- **How a quotation is tested:** its words must run on, in order and without a gap, in the text of the cited page.
  Case, punctuation, spacing and hyphenation are ignored; the words are not. Reference numbers that the paper sets
  against a word (`medicine1,2`) need not be copied: leave them out and quote the sentence whole; the numbers that
  belong to the sentence must be there. A quotation of fewer than eight letters cannot be tested and does not count
  where a quotation is compulsory.
- **Quotation is compulsory** in sections 1, 2, 3, 8, 9, 10 and 14. It is expected wherever the statement is a claim,
  a number or a definition; it may be omitted where the statement only describes structure (sections 5 and 11).
- **Evidence that exists only on the page image** — a tick in a table, a label inside a figure, a value read off a
  plot, an equation whose symbols are lost in the text — is cited as `[p6, image]` and says what was read:
  `- Table 1 marks this survey as the only one covering all thirteen topics. [p6, image]`. A statement that rests
  only on the image needs no quotation; one that also cites text (`[p7]`) still does. A value read off a plot is
  given as an approximate reading.
- **Numbers** are copied exactly, with their unit and what they measure.
- **Absence** is stated, not skipped. The line begins with one of: `Not addressed.` `Not stated by the authors.`
  `Not applicable.` `None.` — after a label where the section uses labels — and says where you looked (or, for
  `Not applicable.`, why):
  `- Not addressed. Searched for: <terms>; nearest content: <what and where> [p12].` It needs no quotation. It may be
  followed by bullets that report the nearest content. A bullet that reports something the paper says must not
  begin with these words: write `The authors state that none of …`, not `None of …`.

## The template

```markdown
---
template: 2
id: <paper ID from the manifest, e.g. S007>
source: "<corpus> / <group>, from the manifest, e.g. oldcorpus / 5may2026>"
title: "<full title as printed on the paper>"
authors: "<all authors, in order>"
year: <year of the volume or issue; an earlier online date goes into venue>
venue: "<journal, conference or publisher, with volume/issue/pages and dates — as printed on the paper; what comes from the PDF metadata instead is marked (PDF metadata); RETRACTED if the paper says so>"
doi: "<DOI if printed on the paper, else none>"
publication_type: <journal article | conference paper | workshop paper | magazine article | preprint | book or book chapter | thesis | technical report or white paper | standard, regulation or guideline | other: …>
document_type: <survey | systematic review | tutorial | primary research — system or scheme | primary research — empirical study | position or magazine article | standard or guideline | other: …>
research_type: ["<every type that applies, the main one first: secondary study | solution proposal | validation research | evaluation research | experience report | conceptual or philosophical paper | opinion or position paper | normative document>"]
evaluation_type: ["<one or more of: none | formal proof | security analysis | informal argument | complexity or cost analysis | simulation | emulation | experiment on datasets | prototype or testbed | real deployment or field study | measurement of real systems | testing of real devices or software | user study | case study | literature synthesis | other: …>"]
pages_total: <N>
body_pages: "<first–last page that carries body text, e.g. 1-35>"
references_pages: "<first–last page of the reference list, e.g. 35-43; it may begin on the last body page; none if there is none>"
appendix_pages: "<appendices, extended data, supplementary pages and publisher's forms inside the PDF, e.g. 30-35; or none>"
theme_primary: "<the one theme this paper belongs to, in 3–8 words>"
themes_secondary: ["<second theme>", "<third theme>"]
codes: ["<5 to 12 short codes: the specific topics, methods and objects the paper deals with>"]
keywords_authors: ["<the authors' own keywords or index terms; [] if none are printed>"]
read_on: <date>
---

# <Title>

## 1. What the paper is about
(The subject, the scope and the kind of work it is. 3–8 statements.)

## 2. The issue it addresses
(The problem, who has it, why it matters, and why existing work does not already solve it — the gap the authors claim.)

## 3. Aims, questions and contributions stated by the authors
(The paper's own aims, objectives, hypotheses or research questions, in the authors' wording, and each contribution
they list, one bullet each. If the paper poses no explicit question, say so; do not write one for it.)

## 4. Approach and method
(How the work was done. For a proposed system: the design, its components, its assumptions. For an empirical study:
design, participants or data, instruments, analysis. For a review: the review method — sources and databases, search
terms, years covered, inclusion and exclusion criteria, number of studies found and kept, how they were classified,
whether their quality was assessed. If the paper does not state its method, say so.)

## 5. Section-by-section digest
(Every part of the paper, in order, as `### <number and heading as printed> [p–p]` followed by bullets saying what
that part says. Begin with `### Front matter [p1]` — title block, abstract, keywords, footnotes on funding and
dates — and end with `### End matter [p–p]` — acknowledgements, declarations, author notes, what the reference list
holds. Where subsection letters restart in every section, write `II-A`, `III-A`. An unnumbered or run-in heading
gets an entry too, as `### <number of the section it sits in> · <heading as printed> [p]`; text that stands before
the first or after the last of them goes under the section's own entry. A footnote is reported under the part it
belongs to. A figure or table that fills a page gets an entry as well. End matter goes last even where the paper
prints it before its appendix or extended data. For a review, every work it describes in a sentence or more gets
its bullet. Nothing is left out; a short subsection gets one bullet.)

## 6. Topic facets
(What the paper says on each facet. Where a facet is absent, one "Not addressed" line. A mechanism goes under the
facet that matches what the paper uses it for.)

### 6.1 Setting: IoT, edge and network
(Devices, tiers, links and networks; application domain; constraints named.)
### 6.2 Learning approach
(Learning paradigm, models, training topology, aggregation, data distribution.)
### 6.3 Privacy mechanisms
(Each mechanism, what it protects, its parameters, who holds keys or trust.)
### 6.4 Trust, blockchain and ledger
(Ledger type, platform, consensus, what is written on-chain, smart contracts, incentives, reputation.)
### 6.5 Threats, attacks and adversary model
(Adversaries assumed; each attack named, with how it is defined.)
### 6.6 Defences, verification and robustness
(Each defence, what it stops, what it does not. Authentication, key establishment and integrity checks belong here.)
### 6.7 Cost and performance
(Computation, storage, communication, energy, latency, throughput — with the figures given.)
### 6.8 Evaluation evidence
(Datasets, testbeds or simulators, hardware, metrics, baselines, experimental settings.)
### 6.9 Regulation, standards and ethics
(Laws, regulations, standards bodies, ethical issues discussed.)
### 6.10 Other topics the paper treats
(Whatever the paper treats at length that fits none of 6.1–6.9, each bullet beginning with a short name for the
topic and a colon. "Not addressed" if there is nothing.)

## 7. Results and findings
(What was found or concluded, with the numbers. For a review: the findings of the synthesis.)

## 8. Limitations stated by the authors
(What the authors admit about their own work: limitations, assumptions they name as restrictive, and what they say
the work does not cover — begin such a bullet with `Scope restriction:` or `Assumption:`; a cost or a drop in
performance that they report of their own work begins with `Weakness reported:`. What they leave for
later work belongs in section 9, and here only where they present it as a limit of the present work. If no
limitation is stated, an absence line that says where you looked, followed by these.)

## 9. Future directions stated by the authors
(What the authors say should be done next, by them or by the field — one bullet per direction.)

## 10. Open issues and challenges identified for the field
(What the authors say is unsolved or a problem today. Where one passage names a problem and a way forward, the
problem goes here and the way forward in section 9; the same page may be cited in both.)

## 11. Inventory of figures, tables, algorithms and equations
(One bullet each: `Fig. 3 [p9] — caption as printed, without quotation marks — what it shows`; write `[p9, image]`
where what it shows was read on the image. Every one in the paper, extended data and appendix included; numbered
equations may be grouped, `Equations 1–5 [p9–11]`; a list or box without a caption that carries content is entered
as `List [p3] — …`.)

## 12. Definitions, taxonomies and terminology
(Terms the paper defines or classifications it introduces, with the definition quoted.)

## 13. Positioning and key sources
(How the authors place the work against earlier work; comparison tables with prior surveys or schemes; the works
they say they build on, extend or compare against, with the reference number as printed.)

## 14. Theme
- Primary theme: <theme> — <why this is the paper's theme>. [p] "…"
- Secondary theme: <theme> — <why>. [p] "…"
(One bullet per theme named in the header.)

## 15. Rigour and reporting
(Facts for the quality appraisal that comes later — no judgement, no score. One bullet per item, beginning with the
label as printed here; where the paper is silent: `<Label>: Not stated by the authors. Searched: …`.)
- Aims or questions: <are they stated explicitly, and where>
- Method description: <what is given that would let the work be repeated: algorithms, parameters, configurations, protocol steps; for a review, the review protocol>
- Evaluation type: <as in the header, with what was used>
- Baselines and comparison: <what the work is compared with>
- Data: <datasets named; public or private; where they can be had>
- Code and artefacts: <whether code, models or configurations are available, and where>
- Statistical treatment: <repetitions, variance, confidence intervals, tests>
- Validity and limitations: <whether the paper has a passage on limitations or threats to validity, and where>
- Ethics and consent: <approval, consent, handling of personal data in the study itself>
- Funding and interests: <funding named; conflict-of-interest statement>
- Publication record: <received, revised, accepted and published dates; peer review; licence; any notice of retraction or correction>

## 16. Reader's observations
(Yours, not the authors': unstated limitations, inconsistencies inside the paper, things claimed but not shown,
quality of evidence. Each points at the page it concerns. Keep it to what a reviewer would defend.)

## 17. Coverage log
- Pages read: p1–pN, all.
- Pages that hold only references, biographies or publisher notices: <list>.
- Pages read on the page render because the text was unusable or the reading order was not confirmed: <list or none>.
- Figures and tables examined on the page render: <list or none>.
- Material the paper refers to that is not in the folder (supplementary files, appendices published elsewhere): <list or none>.
```

## What the checker tests

- The header is complete, uses the vocabulary above, and carries the ID and source the manifest gives the folder.
- Every section, every facet 6.1–6.10 and every item of section 15 is present, in order.
- Every bullet in sections 1–16 has a page citation (absence lines excepted), and the pages exist.
- Every quotation is, word for word, on the one page cited before it.
- Every bullet in sections 1, 2, 3, 8, 9, 10 and 14 has a quotation that can be tested (absence lines and `image`
  evidence excepted).
- Every page of the body is cited at least once somewhere in the notes.
- Every figure, table and algorithm whose caption the text of the paper shows is in section 11; gaps in the
  numbering of section 11 are reported.
- Every page whose reading order is not confirmed is named in the coverage log.
- A paper that carries the word RETRACTED has the retraction in its notes.
- Headings found in the paper's text that do not appear in section 5 are listed as warnings for you to resolve.

The checker tests that the words are on the page, not that they support the statement: read each bullet once more
against its quotation before you finish.

The result is written to `notes/check.json`. Notes are finished only when the checker reports `PASS`.
