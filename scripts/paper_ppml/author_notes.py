#!/usr/bin/env python3
"""The author's notes on paper V29 of the PPML review: what V29 is and where it comes from, the PRISMA 2020 checklist with
the place of each item, the differences between the author's screening answers and the full-text extraction records
(scripted comparison), the points the readers flagged, the author checks, and how to rebuild or resume.

Inputs: search-ppml/FINAL-STUDIES-2026-10-05.csv (the author's answers), search-ppml/evidence/sheets/*.json (the
extraction), search-ppml/evidence/READER-REPORTS.md, myliteraturereviewpaper/ppml2026/AUTHOR-CHECKS-V29.json,
myliteraturereviewpaper/ppml2026/build/tables/prisma_checklist.md, build/BUILD-REPORT-V29.json, build/stats.json.
Outputs: search-ppml/evidence/RECONCILE-2026-10-05.csv; Docs/PPML-V29-AUTHOR-NOTES-2026-10-05.html (printable in portrait
and landscape). An existing Docs file is never overwritten.

Usage: python3 scripts/paper_ppml/author_notes.py [version]      (default 29)
"""
import csv, html, json, pathlib, re, sys

csv.field_size_limit(10 ** 9)
ROOT = pathlib.Path(__file__).resolve().parents[2]
P, PP = ROOT / 'search-ppml', ROOT / 'myliteraturereviewpaper' / 'ppml2026'
VER = next((a for a in sys.argv[1:] if a.isdigit()), '29')
OUT = ROOT / 'Docs' / (f'PPML-V{VER}-AUTHOR-NOTES-2026-10-05.html' if int(VER) <= 37 else                      # named by the day it is made
                      f'PPML-V{VER}-AUTHOR-NOTES-{__import__("datetime").date.today().isoformat()}.html')
RC = P / 'evidence' / ('RECONCILE-2026-10-05.csv' if VER == '29' else f'RECONCILE-V{VER}-2026-10-05.csv')
e = html.escape


def L(s, k, f):
    v = (s['answers'].get(k, {}).get('values') or {}).get(f)
    return v if isinstance(v, list) else ([v] if v not in (None, '') else [])


DECLARATION_TABLES = {'declarations', 'ai_use'}
APPENDIX_TABLES = {'strings_full', 'criteria', 'qa_checklist', 'qa_primary', 'qa_secondary'}
NAME = 'Privacy Preserving Machine Learning in NextGeneration IoT'


def what_it_is(br, s):
    """What a version from V56 on is: built after the independent review of V55, with its supplementary material and the
    editable figures and tables beside it."""
    main = [k for k in br['tables'] if k not in DECLARATION_TABLES | APPENDIX_TABLES]
    return (f'<div class="note">A complete reference version for you to rewrite in your own words, built after five independent '
            f'reviews of V55 (the method of a systematic review, the coherence of the paper, an IEEE editor\'s reading, the tables '
            f'and figures, and the field itself); what each review found and what was done about it is in '
            f'<code>Docs/PPML-V55-INDEPENDENT-REVIEW-SYNTHESIS-2026-10-12.html</code>. The evidence is unchanged in kind: '
            f'{s["included"]} studies ({s["primary"]} primary studies and {s["secondary"]} surveys), every count computed by script '
            f'from the extraction records you verified (two answers corrected since: re-tick n3348 P3 and N017 P6 in the Sheet '
            f'Reviewer).</div>'
            f'<ul><li><b>Main text:</b> {len(main)} tables and {len(br["figures"])} figures; the declarations add '
            f'{len(DECLARATION_TABLES & set(br["tables"]))} tables and the appendices {len(APPENDIX_TABLES & set(br["tables"]))}.</li>'
            f'<li><b>Supplementary material</b> (<i>{e(NAME)} - V{VER} supplementary material.docx</i>): S1 the classification '
            f'rules behind the counts, S2 the tables that left the main text with the reports excluded at full text and those not '
            f'retrieved, S3 the figures that left it, S4 the fuller description of each study.</li>'
            f'<li><b>Every figure and table</b>, of the paper and of the supplementary material, as editable PowerPoint shapes, '
            f'tables and charts: <i>{e(NAME)} - V{VER} figures and tables.pptx</i>.</li>'
            f'<li><b>Why zero-knowledge proofs and regulation:</b> Section I-B lays the foundation. Hiding the updates conflicts '
            f'with checking them; a ledger checks only what all its nodes see; by the GDPR\'s test of identifiability the review '
            f'treats updates and device identifiers as personal data unless a design shows otherwise, and the EDPB guidelines '
            f'decide what a ledger may hold; a proof about a committed update is the one way a '
            f'ledger can verify a check on an update that none of its nodes sees.</li>'
            f'<li><b>Scope:</b> the gap is stated for blockchain-based designs. IEEE formatting is left for later; the declarations '
            f'stay in Abertay\'s form.</li></ul>')


def what_v57(br, s):
    """What a version from V57 on is: V56 with the decisions of 12 October 2026 (the strict spine, the reporting rule, two
    tiers), its supplementary material, its editable figures and tables, and the supplementary search S-ZK made ready."""
    main = [k for k in br['tables'] if k not in DECLARATION_TABLES | APPENDIX_TABLES]
    return (f'<div class="note">A complete reference version for you to rewrite in your own words, with the decisions of 12 October: '
            f'<b>one strict spine</b>, <b>the reporting rule</b> and <b>two tiers</b>. The evidence: {s["primary"]} primary studies and, '
            f'as a second tier, {s["secondary"]} surveys; every count is computed by script from the records you verified.</div><ul>'
            f'<li><b>The spine, strictly:</b> each open issue becomes one condition of the research gap, numbered like its survey '
            f'question: C1 cost on devices, C2 no party sees an update, C3 the ledger itself checks the updates, C4 a reported attack '
            f'test for (a) poisoning, (b) malicious or fake participants and (c) free riding, C5 a ledger that holds no personal records '
            f'or can erase or redact what it holds. The spine table of Section VI-A carries the conditions for all {s["primary"]} designs, with '
            f'a plain count of conditions met; the separate gap table is gone, and Fig. 1 shows the six angles. The closest design '
            f'meets {s["gap_max_met"]} of the seven conditions.</li>'
            f'<li><b>The reporting rule:</b> each study is credited with what it reports; where it reports no test, no cost on devices '
            f'or no code, the paper says that it reports none, not that none exists.</li>'
            f'<li><b>Two tiers:</b> the designs answer the survey questions, the surveys say what is open, and the two are never '
            f'counted together; {s.get("ov_designs_cited", "?")} of the {s["primary"]} designs are cited by any included survey '
            f'(OpenAlex reference lists; Table S6).</li>'
            f'<li><b>Main text:</b> {len(main)} tables and {len(br["figures"])} figures; the declarations add '
            f'{len(DECLARATION_TABLES & set(br["tables"]))} tables and the appendices {len(APPENDIX_TABLES & set(br["tables"]))}. '
            f'<b>Supplementary material</b> (<i>{e(NAME)} - V{VER} supplementary material.docx</i>): S1 rules, S2 tables (S6 the '
            f'overlap of the tiers), S3 figures, S4 the fuller description of each study under the reporting rule. <b>Every figure '
            f'and table</b>, editable: <i>{e(NAME)} - V{VER} figures and tables.pptx</i>.</li>'
            f'<li><b>For you:</b> re-tick n3348 P3 and P4, n2405 P2 and N017 P6 in the Sheet Reviewer (changed since your tick); screen the '
            f'supplementary search S-ZK in <i>search-ppml/PPML S-ZK Screening.app</i> (the searches of 2 October with ledger and ZKP '
            f'terms; <code>search-ppml/evidence/szk-search/README.md</code>), whose inclusions go into the next version; download '
            f'Thaler, <i>Proofs, Arguments, and Zero-Knowledge</i> (2022, <a href="https://doi.org/10.1561/3300000030">doi '
            f'10.1561/3300000030</a>) into <code>/Volumes/Stuff/Downloads</code> for the ZKP definitions of Section III-C.</li>'
            f'<li><b>Checked before delivery:</b> every changed sentence about a study went through two rounds of the records audit, '
            f'and the 42 findings of a coherence check were acted on (<code>reviews-V57/RESPONSE.md</code>).</li></ul>')


def what_v63(br, s):
    """V62 with every coverage label saying what it grades (the author, 13 October 2026: labels must not mislead in any table,
    diagram, graph or figure)."""
    return what_v62(br, s).replace('</ul>', '<li><b>Labels say what they grade (V63):</b> the columns of Table V and Fig. 6 are no '
        'longer the bare names of the layers and angles (\'Fabric\', \'Verification\', \'Blockchain\' …) but the question each '
        'column grades, in the words of the gap conditions where it is one: Cost on devices; No party sees an update; Updates checked '
        '(not by ZKP); ZKP about the update; Ledger checks the updates; Poisoning tested; Malicious or fake tested; Free riding tested; '
        'No personal records, or erasure. Fig. 4 and Fig. 6 carry the survey question and the layer above their columns, and the '
        'surveys\' verification column reads \'Verification of learning\'; the focus-angle table and the trends figure say which '
        'verification they count. No grade or count changes.</li></ul>')


def what_v64(br, s):
    """V63 with the surveys' coverage columns named by the subject each grades (the author, 13 October 2026)."""
    return what_v63(br, s).replace('</ul>', '<li><b>Survey columns named by their subject (V64):</b> the columns of Table IV and '
        'Fig. 4, which grade whether a survey treats a subject of its own, now name that subject in full: NG-IoT fabric; Privacy '
        'mechanisms; Verification of learning; ZKPs; Blockchain; Poisoning; Malicious or fake participants; Free riding; '
        'Data-protection law. The focus-angle table and the trends figure use the same full names. No grade or count changes.</li></ul>')


def what_v65(br, s):
    """V64 with the abstract rewritten in the register of the survey venues (the author, 13 October 2026: "Looks good. do it.")."""
    return what_v64(br, s).replace('</ul>', '<li><b>Abstract rewritten (V65):</b> one unlabelled paragraph of about 250 words in the '
        'register of the IEEE, ACM and Elsevier survey venues: the problem, what the review is and covers, the scope (databases, years, '
        '30 surveys and 45 ledger-based designs, two tiers), four findings with the numbers that carry the argument, the gap for the '
        'included designs, and the agenda. Dropped: the Purpose/Methods/Results/Conclusion labels, the screening counts, the screening '
        'tool and the author\'s verification (Section II and the declarations keep them), and the compressed phrases. Every number '
        'is computed from the records as before.</li></ul>')


def what_v66(br, s):
    """V65 with the screening account corrected to the author's statement, checked against the app's log (13 October 2026)."""
    return what_v65(br, s).replace('</ul>', '<li><b>Screening account (V66):</b> the author screened all 4,302 records of the main '
        'searches in the screening application, recording a decision on 2,825 and accepting the application\'s default exclusion '
        'on 1,477 (the app showed every record in sequence and marked a record excluded by default only while undecided; the log '
        'shows the author\'s sequential walk). II-C, the II takeaway, X, the PRISMA figure, the AI-use table and the '
        'exclusion-reasons table now say so; "left at a default exclusion" is gone. The automated tool\'s second screening of the '
        '3,483 accepted-default and rule exclusions and of the 220 R-S1 records is unchanged and still disclosed.</li></ul>')


def what_v67(br, s):
    """V66 plus the author's statement that full texts were read at screening where needed (13 October 2026)."""
    return what_v66(br, s).replace('</ul>', '<li><b>Screening (V67):</b> II-C now states, from the author\'s own account, that the '
        'author read the full text where the title and abstract did not settle a record. Nothing else changed.</li></ul>')


def what_v61(br, s):
    """V60 with Section VI's results prose rewritten for flow (the author, 13 October 2026): shorter sentences, the
    'Answer to SQ' paragraphs no longer repeat the counts of the paragraph before, the takeaways read as sentences."""
    return what_v60(br, s).replace('</ul>', '<li><b>Section VI rewritten for flow (V61):</b> the results paragraphs of VI-B to VI-F '
        'in shorter sentences, each count said once; every "Answer to SQ" paragraph is a verdict that ends with the condition '
        'count, without repeating the numbers above it; the takeaway box reads as sentences. Every citation, evidence marker '
        'and table reference is unchanged (checked by script), and the only numbers removed are the repeats; the claim guards '
        'and the build\'s number checks pass.</li></ul>')


def what_v62(br, s):
    """V61 after the records audit (13 October 2026): every sentence about each included study read against its evidence
    sheet and summary; two corrections (n3855 moved to the committee group, n3813's ledger holdings reworded)."""
    return what_v61(br, s).replace('</ul>', '<li><b>Records audit against the evidence sheets (V62):</b> every sentence the '
        'review writes about each of the 75 included studies (649 units: the study paragraphs, the group headings, the '
        'synthesis sentences that cite it and the QA6 notes) was read against that study\'s evidence sheet and summary; '
        '647 hold as written. Two corrections: AZKP-TFL [n3855] now stands among the designs whose updates are judged by '
        'the ledger\'s nodes, since its smart contract scores each model on a test set, so that group counts fourteen '
        'designs, nine of whose checkers see the updates, and the server-or-peers group eight; and the NextGen '
        'supply-chain design [n3813] is described as keeping the hashes and signatures of its records on the ledger, not '
        'the records. No count in a table or figure changes.</li></ul>')


def what_v60(br, s):
    """V59 with a prose pass (the author, 13 October 2026: the text read as if telling someone how the paper was written):
    the method states what was done, not how the tool did it; the scope statements are said once; the AI declaration names
    every model used and the review of drafts."""
    return what_v59(br, s).replace('</ul>', '<li><b>Prose pass (V60):</b> process narration removed from the method and the framing (what '
        'was done, not how the scripts and the tool did it; tool mechanics stay in the AI-use table); the scope statements of V59 '
        'said once each; the garbled sentence of I-C, the provenance counts of IV-A and the restated sensitivity result of VII-A '
        'removed; the conclusion no longer re-lists the databases. The Declarations now name Claude Fable 5.1 among the models '
        '(session logs) and the AI-use table records that the tool reviewed drafts of the article at the author\'s request. '
        'No study paragraph, number, table or figure changed.</li></ul>')


def what_v59(br, s):
    """What a version from V59 on is: V58 with its object aligned to its search (the author, 13 October 2026: stay with the
    included studies, within the guidelines, without serious issues), the search validation reported, and every absence
    stated for the included designs."""
    main = [k for k in br['tables'] if k not in DECLARATION_TABLES | APPENDIX_TABLES]
    return (f'<div class="note">A complete reference version for you to rewrite in your own words. Its object is now stated as what '
            f'its searches were built and tested for, PPML in the NG-IoT, with the {s["primary"]} ledger-based designs as the tier '
            f'synthesised in depth and the {s["secondary"]} surveys as the second tier; every count and every absence is a statement '
            f'about the included studies. Every number is computed by script from the records you verified, and every table and map is '
            f'recomputed independently from them (verify_tables.py: 0 differences).</div><ul>'
            f'<li><b>Why:</b> the independent review of V55 rated one search problem critical: the paper claimed a gap across all '
            f'ledger-based designs while its strings carried no ledger term and the ledger criterion came at full text. The claim is now '
            f'scoped to the included designs, and the method says how they were reached.</li>'
            f'<li><b>The search, as validated:</b> the strings were tested against the studies you already knew before the final searches '
            f'(Section II-B): the searches returned {s["kn_sec_found"]} of the {s["kn_sec_topic"]} known surveys on the topic and '
            f'{s["kn_prim_found"]} of the {s["kn_prim_topic"]} known designs; {s["kn_prim_missed_title"]} designs were missed by the '
            f'privacy-in-title restriction and {s["kn_prim_missed_db"]} were not returned by the databases; {s["kn_prim_missed_included"]} '
            f'of the missed designs are the studies identified through other methods. The ledger requirement excluded '
            f'{s["ft_ex_no_ledger"]} reports at full text (Table S4). Records: search-ppml/CORPUS-COVERAGE-2026-10-04.csv, COVERAGE-2026-10-04.md.</li>'
            f'<li><b>The gap, scoped:</b> the seven conditions and the gap tables stay on the spine; Section VIII says the conditions are '
            f'scored for the included designs and that a design meeting them may exist outside them; the closest included design meets '
            f'{s["gap_max_met"]} of seven. A search with ledger and zero-knowledge terms is named as the next step (Sections VIII-C, X, XI), '
            f'not reported as done.</li>'
            f'<li><b>Unchanged:</b> the five layers, six angles, the seven conditions, the two tiers, the reporting rule, every study '
            f'paragraph and table of results; the gap displays of V58 for both tiers.</li>'
            f'<li><b>Main text:</b> {len(main)} tables and {len(br["figures"])} figures; the declarations add '
            f'{len(DECLARATION_TABLES & set(br["tables"]))} tables and the appendices {len(APPENDIX_TABLES & set(br["tables"]))}. '
            f'<b>Supplementary material</b> (<i>{e(NAME)} - V{VER} supplementary material.docx</i>); <b>every figure and table</b>, '
            f'editable: <i>{e(NAME)} - V{VER} figures and tables.pptx</i>.</li>'
            f'<li><b>For you:</b> the title (the subtitle still names the ledger designs as the object; a VERIFY check offers wording); '
            f'the sentence that a ledger-and-ZKP search is the next step is your plan to confirm; your own reference design (IX-B).</li></ul>')


def what_v58(br, s):
    """What a version from V58 on is: the strict spine, the reporting rule and two tiers, with the research gap shown for both
    tiers in the main text (the author, 13 October 2026), its supplementary material and its editable figures and tables."""
    main = [k for k in br['tables'] if k not in DECLARATION_TABLES | APPENDIX_TABLES]
    return (f'<div class="note">A complete reference version for you to rewrite in your own words, with <b>one strict spine</b>, '
            f'<b>the reporting rule</b> and <b>two tiers</b>, and the research gap shown for both tiers. The evidence: {s["primary"]} '
            f'primary studies and, as a second tier, {s["secondary"]} surveys; every count is computed by script from the records you '
            f'verified, and every table and map is recomputed independently from them (verify_tables.py: 0 differences).</div><ul>'
            f'<li><b>Where the gap shows, tier by tier:</b> the focus angles of the primary studies and of the surveys side by side '
            f'(Section IV-B); what each survey treats, as a table and as a coverage map whose white cells are the areas a survey '
            f'leaves out (Section V-B); what each primary study does, as a table and as a coverage map (Section VI-A); the open areas '
            f'of each layer, with what the surveys ask for, what the primary studies show and the open issue (Section VII-B); the '
            f'conditions of the research gap with the number of designs that meet each, and the {s["gap_met_atleast2"]} designs that '
            f'meet at least two, condition by condition (Section VIII). The closest design meets {s["gap_max_met"]} of the seven '
            f'conditions. The coverage table of the primary studies carries grades only; the conditions met are counted in the gap '
            f'table, where every column is a condition.</li>'
            f'<li><b>The spine, strictly:</b> each open issue becomes one condition of the research gap, numbered like its survey '
            f'question: C1 cost on devices, C2 no party sees an update, C3 the ledger itself checks the updates, C4 a reported attack '
            f'test for (a) poisoning, (b) malicious or fake participants and (c) free riding, C5 a ledger that holds no personal records '
            f'or can erase or redact what it holds.</li>'
            f'<li><b>The reporting rule:</b> each study is credited with what it reports; where it reports no test, no cost on devices '
            f'or no code, the paper says that it reports none, not that none exists.</li>'
            f'<li><b>Two tiers:</b> the designs answer the survey questions, the surveys say what is open, and the two are never '
            f'counted together; {s.get("ov_designs_cited", "?")} of the {s["primary"]} designs are cited by any included survey '
            f'(OpenAlex reference lists; Table S6).</li>'
            f'<li><b>Main text:</b> {len(main)} tables and {len(br["figures"])} figures; the declarations add '
            f'{len(DECLARATION_TABLES & set(br["tables"]))} tables and the appendices {len(APPENDIX_TABLES & set(br["tables"]))}. '
            f'<b>Supplementary material</b> (<i>{e(NAME)} - V{VER} supplementary material.docx</i>): S1 rules, S2 tables (S6 the '
            f'overlap of the tiers), S3 the trends by year, S4 the fuller description of each study under the reporting rule. '
            f'<b>Every figure and table</b>, editable: <i>{e(NAME)} - V{VER} figures and tables.pptx</i>.</li>'
            f'<li><b>For you:</b> the full-text decisions on the 64 records you included from the supplementary search S-ZK '
            f'(<code>search-ppml/evidence/szk-search/</code>); their extraction records need your permission before they can enter '
            f'the review. Your own reference design (IX-B) and the title.</li></ul>')


def what_it_was(s):
    """What a version from V29 to V55 was (the description those notes carried)."""
    return f"""<div class="note">A complete reference version for you to write your own paper from. It joins the <b>spine of V28</b> (five layers, five
survey questions, background by layer, an answer to each question, trends, lessons, open areas, gap, agenda) with the <b>systematic
machinery of the ZK review V4</b> (recorded searches, criteria, PRISMA flow, page-cited extraction, claimed-versus-tested threats, thematic
tables, figures, declarations), on the <b>evidence of the PPML systematic review</b>: your searches of 4 October, your screening and
full-text decisions, {s['included']} studies ({s['primary']} primary, {s['secondary']} secondary). Nothing is taken from V28's text or numbers.
PRISMA is used as a reporting guideline only, as in Kavianpour 2019 and the comparable surveys: a two-page method with databases, keyword
blocks, criteria, a flow figure and the tool disclosure. ZK proofs appear as one direction for later work, not as the core.{' V30 adds, as in the earlier PRISMA and themes record, the reasons for exclusion at screening, the focus angles across the included studies, what the ZK proofs show and the included studies with their angles (Appendix C), and it rests on your answers after the conflicts with the extraction were settled.' if int(VER) >= 30 else ''}</div>"""


def reconcile():
    fin = {r['corpus_id']: r for r in csv.DictReader(open(P / 'FINAL-STUDIES-2026-10-05.csv', encoding='utf-8'))}
    rows = []
    for cid, r in fin.items():
        s = json.loads((P / 'evidence' / 'sheets' / f'{cid}.json').read_text(encoding='utf-8'))
        ang = set(a for a in r['angles'].split('; ') if a)
        if r['kind'] == 'primary':
            zk = L(s, 'P4', 'zk_used') == [True]
            onchain = L(s, 'P4', 'zk_on_chain') == ['yes']
            claimed = set(L(s, 'P5', 'claimed'))
            shows = sorted(x for x in L(s, 'P4', 'zk_shows') if not str(x).startswith('other'))
            if any(str(x).startswith('other') for x in L(s, 'P4', 'zk_shows')):
                shows.append('other')
            author_shows = sorted(x for x in r['zk_proves'].split('; ') if x)
            tested = set(L(s, 'P5', 'tested'))
            # a conflict: you ticked the angle but the extraction finds nothing of it, or you did not tick it and the study tests it
            pairs = [('zero-knowledge proofs', 'zero-knowledge proofs' in ang, zk, zk, 'P4 zk_used'),
                     ('ZK checked on the blockchain', 'ZK on blockchain' in ang, onchain, onchain, 'P4 zk_on_chain'),
                     ('poisoning', 'poisoning' in ang, bool({'poisoning', 'backdoor'} & claimed), bool({'poisoning', 'backdoor'} & tested), 'P5 claimed / tested'),
                     ('malicious or fake participants', 'malicious or fake participants' in ang, bool({'byzantine-malicious', 'sybil-fake', 'malicious-server-aggregator', 'poisoning'} & claimed) or 'identity-membership' in L(s, 'P4', 'checked'), bool({'byzantine-malicious', 'sybil-fake'} & tested), 'P5 claimed / tested'),   # IC3b: malicious clients, dishonest aggregators, authentication
                     ('free riding', 'free riding' in ang, 'free-riding' in claimed, 'free-riding' in tested, 'P5 claimed / tested')]
            for name, a, cl, te, where in pairs:
                if (a and not cl) or (not a and te):
                    rows.append({'id': cid, 'kind': 'primary', 'item': name, 'author': 'yes' if a else 'no',
                                 'extraction': ('tested' if te else 'claimed' if cl else 'not claimed') if name not in ('zero-knowledge proofs', 'ZK checked on the blockchain') else ('yes' if cl else 'no'), 'where': where})
            if zk and author_shows and not set(author_shows) <= set(shows):
                rows.append({'id': cid, 'kind': 'primary', 'item': 'what the ZK proof shows', 'author': ', '.join(author_shows), 'extraction': ', '.join(shows) or '—', 'where': 'P4 zk_shows'})
        else:
            m = {'poisoning': 'poisoning', 'malicious or fake participants': 'malicious_fake', 'free riding': 'free_riding',
                 'verification': 'verification', 'zero-knowledge proofs': 'zkp', 'blockchain': 'blockchain'}
            for name, key in m.items():
                x = (s['answers'].get('S4', {}).get('values') or {}).get(key)
                a = name in ang
                if (a and x == 'absent') or (not a and x == 'subject'):        # "mentioned" is not a conflict
                    rows.append({'id': cid, 'kind': 'secondary', 'item': name, 'author': 'yes' if a else 'no', 'extraction': x or '—', 'where': 'S4'})
    with open(RC, 'w', encoding='utf-8', newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=['id', 'kind', 'item', 'author', 'extraction', 'where'])
        w.writeheader()
        w.writerows(rows)
    return rows


def md_table_to_html(path):
    lines = [l for l in path.read_text(encoding='utf-8').splitlines() if l.startswith('|')]
    head = [c.strip() for c in lines[0].strip('|').split('|')]
    body = [[c.strip() for c in l.strip('|').split('|')] for l in lines[2:]]
    fix = lambda c: re.sub(r'\{\{(TAB|FIG):(\w+)\}\}', lambda m: ('Table “' if m.group(1) == 'TAB' else 'Fig. “') + m.group(2) + '”', c)
    return ('<table><tr>' + ''.join(f'<th>{e(h)}</th>' for h in head) + '</tr>'
            + ''.join('<tr>' + ''.join(f'<td>{e(fix(c))}</td>' for c in r) + '</tr>' for r in body) + '</table>')


def main():
    if OUT.exists():
        sys.exit(f'{OUT.name} exists; write a new version instead')
    rows = reconcile()
    rep = (P / 'evidence' / 'READER-REPORTS.md').read_text(encoding='utf-8')
    flagged = [l[2:] for l in rep.splitlines() if l.startswith('- ') and 'check' in l]
    ac = json.loads((PP / f'AUTHOR-CHECKS-V{VER}.json').read_text(encoding='utf-8'))
    br = json.loads((PP / 'build' / f'BUILD-REPORT-V{VER}.json').read_text(encoding='utf-8'))
    s = json.loads((PP / 'build' / 'stats.json').read_text(encoding='utf-8'))
    rec = ''.join(f"<tr><td>{e(r['id'])}</td><td>{e(r['kind'])}</td><td>{e(r['item'])}</td><td>{e(r['author'])}</td><td>{e(r['extraction'])}</td><td>{e(r['where'])}</td></tr>" for r in rows)
    fl = ''.join(f'<li>{e(x)}</li>' for x in flagged)
    chk = ''.join(f"<tr><td>{e(c['kind'])}</td><td>{e(c['find'][:70])}</td><td>{e(c['comment'])}</td></tr>" for c in ac['checks'])
    fx = PP / f'FIXES-V{VER}.json'
    fixes_html = ''
    if fx.exists():
        F = json.loads(fx.read_text(encoding='utf-8'))
        fixes_html = ('<h2>Fixes of the points that could be used against you</h2><table><tr><th>Point</th><th>What was done</th><th>What is left for you</th></tr>'
                      + ''.join(f'<tr><td>{e(a)}</td><td>{e(b)}</td><td>{e(c)}</td></tr>' for a, b, c in F['fixes']) + '</table>'
                      + '<h2>What a good SLR looks like (Shahrour et al., Computer Science Review 2026) and how V' + VER + ' follows it</h2><ul>'
                      + ''.join(f'<li>{e(x)}</li>' for x in F['lessons']) + '</ul>')
    made = '5 October 2026' if int(VER) <= 37 else (lambda d: f'{d.day} {d:%B %Y}')(__import__('datetime').date.today())
    what = what_v67(br, s) if int(VER) >= 67 else what_v66(br, s) if int(VER) == 66 else what_v65(br, s) if int(VER) == 65 else what_v64(br, s) if int(VER) == 64 else what_v63(br, s) if int(VER) == 63 else what_v62(br, s) if int(VER) == 62 else what_v61(br, s) if int(VER) == 61 else what_v60(br, s) if int(VER) == 60 else what_v59(br, s) if int(VER) == 59 else what_v58(br, s) if int(VER) == 58 else what_v57(br, s) if int(VER) == 57 else what_it_is(br, s) if int(VER) == 56 else what_it_was(s)
    doc = f"""<!doctype html><html lang="en-GB"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>PPML V{VER} author notes</title><style>
:root{{--ink:#1b1b1b;--muted:#555;--line:#c9c9c4;--head:#0f4761;--band:#f3f5f7}}
html,body{{background:#fff;color:var(--ink)}} body{{font:14.5px/1.5 -apple-system,"Helvetica Neue",Arial,sans-serif;margin:0 auto;max-width:72rem;padding:24px 16px 48px}}
h1{{font-size:1.4rem;color:var(--head);margin:0 0 4px}} h2{{font-size:1.12rem;color:var(--head);margin:26px 0 8px;border-bottom:1px solid var(--line)}}
.muted{{color:var(--muted)}} .note{{border:1px solid var(--line);border-radius:6px;padding:8px 12px;background:var(--band);margin:10px 0}}
table{{border-collapse:collapse;width:100%;font-size:.84rem;margin:6px 0}} th,td{{border:1px solid var(--line);padding:4px 6px;text-align:left;vertical-align:top}}
th{{background:var(--band)}} code{{font-size:.85em}} li{{margin:3px 0}}
@page{{size:auto;margin:12mm}}
@media print{{body{{max-width:none;padding:0;font-size:9.5pt}} table{{font-size:8pt}} table,tr,.note,li{{break-inside:avoid}} th,.note{{background:#fff}}}}
</style></head><body>
<h1>PPML in NG-IoT — paper V{VER}: notes for the author</h1>
<p class="muted">{made} · {e(br['output'])} and its copy “with author checks” in myliteraturereviewpaper/PPML in NextGeneration IoT/ ·
{len(br['tables'])} tables, {len(br['figures'])} figures, {len(br['citations'])} references, {len(br['studies'])} study paragraphs, about {br['words']:,} words · built by scripts/paper_ppml/build.py</p>

<h2>1. What V{VER} is</h2>
{what}

<h2>2. Where each PRISMA 2020 item is reported</h2>
<p class="muted">For your own check against the guideline; not part of the paper. Table and figure names refer to the build keys.</p>
{md_table_to_html(PP / 'build' / 'tables' / 'prisma_checklist.md')}

<h2>3. Your screening answers against the full-text extraction ({len(rows)} differences left)</h2>
<p class="muted">The conflicts listed with V29 were settled on 5 October, each against the criteria with its evidence: Docs/PPML-CONFLICTS-RESOLVED-2026-10-05.html.</p>
<p class="muted">Section IV reports your screening angles (as in the PRISMA and themes record); Section VI uses the extraction records, built
later from summaries, notes and, where needed, the full text, each with a page and quotation. Where they differ, decide which stands; the app
(<code>run-screening-app.sh --fulltext</code>) changes your answer, and the extraction can be corrected in the sheet. Full list:
search-ppml/evidence/RECONCILE-2026-10-05.csv. Listed only where they conflict: you ticked an angle that the extraction finds absent (or not even claimed), or you did not tick one that the study tests (primary) or treats as a subject (secondary); “mentioned” and “claimed only” are not counted against an unticked angle.</p>
<table><tr><th>Study</th><th>Kind</th><th>Item</th><th>Your answer</th><th>Extraction</th><th>Where</th></tr>{rec}</table>

<h2>4. Points the readers flagged for you</h2>
<p class="muted">From search-ppml/evidence/READER-REPORTS.md (lines marked “check”); the file also lists papers that contradict themselves.</p>
<ul>{fl}</ul>

<h2>5. The author checks in V{VER} ({len(ac['checks'])})</h2>
<table><tr><th>Kind</th><th>Anchor</th><th>Comment</th></tr>{chk}</table>

{fixes_html}
<h2>6. How to rebuild or resume</h2>
<ol>
<li>Runbook and status: <code>myliteraturereviewpaper/ppml2026/PLAN.md</code> (“Resume here”).</li>
<li>Evidence: <code>python3 scripts/paper_ppml/check_sheets.py</code> ({s['sheets']}/{s['sheets']} must pass).</li>
<li>Numbers, tables, figures: <code>python3 scripts/paper_ppml/data.py</code>.</li>
<li>All checks without rendering: <code>python3 scripts/paper_ppml/build.py {int(VER) + 1} --check</code>; render a new version with <code>build.py {int(VER) + 1}</code> (an existing version is never overwritten).</li>
<li>Your edits: build the next version from your edited V{VER} (diff the docx first, so that your changes survive).</li>
</ol>
</body></html>"""
    OUT.write_text(doc, encoding='utf-8')
    print(OUT.relative_to(ROOT), '|', len(rows), 'differences |', len(flagged), 'flagged points')


if __name__ == '__main__':
    main()
