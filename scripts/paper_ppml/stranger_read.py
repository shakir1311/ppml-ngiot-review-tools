#!/usr/bin/env python3
"""The stranger's read of a built version: the abstract, Section I, Section VI, Section VII-A and Section VIII as plain text in one
file, headed by the reader's questions, for a read-through as a reader who has never seen the records (the lesson of 9 November
2026: a supervisor found passages that made no sense to a reader without the records after dozens of checks for correctness had
passed; nobody had read the paper as a stranger).

Writes build/STRANGER-READ-V<n>.md from build/paper-V<n>.md (the sections as author_sections_txt.py extracts them, Key Takeaways as
bullets, figures and tables as a bracketed line) and prints the path and the questions. The read itself is done by a person or by
Claude as a reader, not an auditor; its findings go into PLAN-V<n>.md before the version is delivered, and the fixes into the next
version where the version is already delivered (the standing rule of 9 November 2026). terms_check.py does the mechanical part.

Usage: python3 scripts/paper_ppml/stranger_read.py <version>
"""
import pathlib, re, sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import author_sections_txt as A                                            # noqa: E402

QUESTIONS = """# The stranger's read of V{v}

Read as someone who has never seen the records, the plan or an earlier version. Note the sentence and the section for each answer.

1. Abstract: can every sentence be understood with nothing else of the paper? Where the review's own constructs appear
   (conditions, agenda, a design), does the sentence say that they are the review's own? Does it answer every question it asks (each
   threat it names, the cost, the privacy), and did a cut to the word limit remove an answer the last version gave?
2. Terms: is every word of the review's own (fabric, record, conditions, agenda, deliverable, validators, probes) explained at
   its first appearance? (terms_check.py lists the ones it knows; add new ones to its TERMS.)
3. Contradictions: do two statements near each other sound like a contradiction, even where both are true? Which parties or
   counts reconcile them, and does the text name them?
4. Reasons: where a count, a yardstick or a selection is the review's own choice, is the reason given there?
5. Meaning: does each paragraph of the discussion say what the finding means, not only what it is?
6. Conclusion: does it stand on its own? Could a reader who skipped Section VII follow its second paragraph?
7. Hedges: are hedges stacked ("described as", "would", "where it relates") where one plain statement, with the condition
   stated once, would do?
8. Vocabulary: any project or PhD vocabulary a journal reader would not expect (deliverable, agenda, records, spine)?
9. Tables and figures: can the first table and the first figure a reader meets be read without the records (labels, not tags)?

Findings go into PLAN-V{v}.md ("the stranger's read"), with the sentence quoted and the fix, before delivery.

---

"""


def main(version):
    md = (A.BUILD / f'paper-V{version}.md').read_text(encoding='utf-8')
    secs = A.top_sections(md)
    parts = [A.abstract(md)]
    for stem, heading in A.SECTIONS[1:]:
        parts.append(A.section_text(heading, secs[heading]))
    agenda = next(h for h in secs if h.startswith('VII.'))
    text = A.section_text(agenda, secs[agenda])
    parts.append(re.split(r'\n(?=B\. )', text, maxsplit=1)[0].rstrip() + '\n\n[Sections VII-B and VII-C are not part of the read]\n')
    out = A.BUILD / f'STRANGER-READ-V{version}.md'
    out.write_text(QUESTIONS.format(v=version) + '\n\n'.join(parts), encoding='utf-8')
    print(QUESTIONS.format(v=version).split('---')[0])
    print(f'written {out.relative_to(A.ROOT)} ({len(" ".join(parts).split())} words to read)')


if __name__ == '__main__':
    main(int(sys.argv[1]))
