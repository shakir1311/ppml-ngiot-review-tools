#!/usr/bin/env python3
"""Docs/PPML-SURVEY-QUESTIONS-REVIEW-<date>.html: are the review's survey questions (SQ1-SQ5) the right ones? (7 October 2026)

The author: "tell me if we are going overboard with survey questions? … send me phd proposal … send it to few agents along
with the survey questions … counter verify their quality where the agents behave as SMEs, PhD literature review scrutinizers
… also deduce from our corpus the various survey questions people have devised for similar studies. i want to know if we
have come up with correct survey questions."

Reads the six panel reviews (search-ppml/evidence/sq-review/panel/*.md, each opening with a JSON block), the questions the
corpus surveys set themselves (CORPUS-RQS.json) and the PhD proposal; the synthesis below is Claude's adjudication of the
panel. Every quotation the panel cites was checked word for word against its source before this report was written.
Printable in portrait and landscape; never overwrites.

Usage: python3 scripts/paper_ppml/sq_review_report.py
"""
import datetime, html, json, pathlib, re, statistics, sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
SR = ROOT / 'search-ppml' / 'evidence' / 'sq-review'
OUT = ROOT / 'Docs' / f'PPML-SURVEY-QUESTIONS-REVIEW-{datetime.date.today().isoformat()}.html'
e = html.escape
ROLES = {'sme-secure-fl': 'Subject expert: privacy-preserving and secure federated learning',
         'sme-blockchain-ngiot': 'Subject expert: blockchain and NG-IoT systems',
         'methodologist': 'Systematic review methodologist (PRISMA 2020, Kitchenham, PICOC)',
         'phd-examiner': 'PhD examiner and literature-review scrutinizer',
         'journal-reviewer': 'Survey-journal reviewer (IEEE COMST, ACM CSUR, Elsevier CSR)',
         'data-protection': 'Data-protection expert (GDPR, EDPB guidelines)'}
CRIT = ['clarity', 'focus', 'answerable', 'alignment', 'distinctive', 'answered']
SQS = ['SQ1', 'SQ2', 'SQ3', 'SQ4', 'SQ5']
NOW = {'SQ1': 'In which NG-IoT settings are the approaches built, where on the device–edge–cloud tiers do learning, privacy, checking and the ledger run, and is their cost measured on device-class hardware or real links?',
       'SQ2': 'Which mechanisms protect the data and the updates, what does each hide and from whom, and at what cost?',
       'SQ3': 'What do the ledgers record, verify and enforce, how are updates, training or aggregation checked, and does the checker see the update?',
       'SQ4': 'Which of poisoning, malicious or fake participants and free riding do the approaches claim to counter, and which do they test?',
       'SQ5': 'Do the studies address data-protection law, what personal data reaches the ledger, and how is erasure handled?'}
PROPOSED = {'SQ1': ('the fabric', 'Where on the device–edge–cloud tiers do the designs run learning, privacy protection, checking and the ledger, and is what each costs measured where it is paid: on device-class hardware or over a real or emulated network link?'),
            'SQ2': ('the privacy plane', "From which parties (the aggregator, the checkers, the ledger's nodes, other participants) do the designs hide the individual updates, and is that protection tested by an attack on privacy?"),
            'SQ3': ('the trust plane', 'Who checks the updates, the training or the aggregation, does that party see the update, and does the ledger verify the check or only record it?'),
            'SQ4': ('attacks and defences', 'Which of poisoning, malicious participants, fake (Sybil) participants and free riding do the designs claim to counter, and which do they test by running an attack, at what attacker share?'),
            'SQ5': ('the regulatory layer', 'What do the designs write to the ledger about participants, their updates and the model, in what form, and could it be erased, judged against the GDPR and the EDPB guidelines?')}
SCOPE = ("The questions are asked of privacy-preserving learning designs that build on a blockchain or distributed ledger "
         "(population), in NG-IoT settings (context), about what they hide, check, record, claim and test (outcomes). The settings, "
         "mechanisms and laws a study names are recorded as its characteristics (Table 8). Denial of service attacks the service, "
         "not the learning: it is reported as a count, not asked.")


def panel():
    out = {}
    for f in sorted((SR / 'panel').glob('*.md')):
        j = json.loads(re.search(r'```json\s*(\{.*?\})\s*```', f.read_text(encoding='utf-8'), re.S).group(1))
        out[f.stem] = j
    return out


def main():
    if OUT.exists():
        sys.exit(f'{OUT.name} exists; documents are never overwritten')
    P = panel()
    C = json.loads((SR / 'CORPUS-RQS.json').read_text(encoding='utf-8'))
    nq = [len(s.get('questions', [])) + len(s.get('questions_from_image', []) or []) for s in C['surveys']]
    n_quotes = sum(len(j.get('evidence', [])) for j in P.values())
    # the panel's verdicts and mean scores
    head = ''.join(f'<th>{q}</th>' for q in SQS)
    vrows = ''.join(f"<tr><td>{e(ROLES.get(r, r))}</td><td>{e(j['overall']['verdict'])}</td><td>{e(j['overall']['number'])}</td>"
                    + ''.join(f"<td>{e(j['sqs'][q]['verdict'])}</td>" for q in SQS) + '</tr>' for r, j in P.items())
    mrows = ''.join('<tr><td>' + c + '</td>' + ''.join(
        f"<td>{statistics.mean(P[r]['sqs'][q][c] for r in P):.1f}</td>" for q in SQS) + '</tr>' for c in CRIT)
    members = ''.join(f"<li><b>{e(ROLES.get(r, r))}.</b> {e(j['overall']['summary'])}</li>" for r, j in P.items())
    sugg = ''.join(f"<h3>{q}</h3><ul>" + ''.join(f"<li><i>{e(ROLES.get(r, r).split(':')[0].split('(')[0].strip())}:</i> {e(j['sqs'][q].get('suggested', ''))}</li>"
                                               for r, j in P.items() if j['sqs'][q].get('suggested')) + '</ul>' for q in SQS)
    now = ''.join(f'<li><b>{q}.</b> {e(t)}</li>' for q, t in NOW.items())
    prop = ''.join(f'<li><b>{q}, {e(n)}.</b> {e(t)}</li>' for q, (n, t) in PROPOSED.items())
    css = ('body{font:14px/1.5 Georgia,serif;background:#fff;color:#111;margin:24px;max-width:1150px}h1{font-size:23px}h2{font-size:18px;margin-top:28px}'
           'h3{font-size:15px;margin:14px 0 4px}table{border-collapse:collapse;width:100%;margin:8px 0}td,th{border:1px solid #bbb;padding:4px 7px;'
           'vertical-align:top;overflow-wrap:anywhere}th{background:#eef2f6;text-align:left}.box{border:2px solid #156082;background:#eaf2f6;padding:10px 14px}'
           '.small{font-size:12px;color:#333}@media print{@page{size:auto;margin:14mm}body{margin:0;max-width:none;font-size:11px}'
           '.box{background:#fff}thead{display:table-header-group}tr,td,th,.box,li{break-inside:avoid}}')
    body = f"""
<h1>Are the survey questions right? A panel review of SQ1–SQ5 (PPML review, version 40)</h1>
<p class="small">7 October 2026. Inputs: the PhD funding proposal (phdproposal/phd funding proposal.txt); the review (build/paper-V40.md);
six panel reviews by separate Claude runs, each in one expert role ({n_quotes} quotations, every one found word for word in its source);
the questions that 20 surveys of the corpus set themselves (84 questions, each checked on its page). The synthesis and the proposed
wording are Claude's, from the panel's reviews.</p>

<div class="box"><p><b>Short answer.</b> We are not going overboard in the <i>number</i> of questions: five, one per layer, is normal
(the 20 comparable surveys ask a median of {statistics.median(nq)}; {sum(3 <= n <= 5 for n in nq)} of them ask three to five), and all six
panel members say five is right. The questions are also the <i>right ones</i>: they follow the PhD proposal's own elements one to one
(the IoT-ML fabric at the edge, privacy, blockchain for trusted model updates, the threats, the GDPR), and three of them (does the checker
see the update; threats claimed against threats tested; data-protection law) are asked by none of the 84 questions of the corpus.
Where we do go overboard is <i>inside</i> the questions: 14 separate asks in the list of Section I-C (15 in Table 1), three different
wordings (I-C, Table 1, the closing list of V-D), cost, who sees the update and what the ledger holds each asked twice, SQ5 worded so
that 34 of 37 studies can only be "unclear", and the proposal's own blockchain question (what the ledger costs at the edge) asked by
none. <b>Verdict, unanimous: revise the wording, keep the five questions.</b></p></div>

<h2>1. The survey questions as they stand (Section I-C)</h2><ul>{now}</ul>
<p>Table 1 words four of them more fully (SQ1 "built and evaluated", SQ2 "model updates" and "reported cost", SQ3 "including by
zero-knowledge proofs", SQ4 "and with which defences and evaluation"), and the closing list of Section V-D gives a third, shorter version
(for SQ5 "how are the regulations met", which asks for a compliance verdict the review cannot give).</p>

<h2>2. Fit with the PhD proposal</h2>
<table><thead><tr><th>The proposal says</th><th>Asked by</th><th>Fit</th></tr></thead><tbody>
<tr><td>"distributed machine learning approaches at the network edge"; "5G &amp; edge computing paradigms"</td><td>SQ1</td><td>yes: where the learning, checking and ledger run</td></tr>
<tr><td>"examine the impact of blockchain solutions at the network edges (i.e., IoT devices) in terms of computation, storage, and network control"</td><td>SQ1, only implicitly</td><td>partly: SQ1 asks whether cost is measured, not what the ledger costs</td></tr>
<tr><td>"employ blockchain technology to design and develop a privacy-preserved ML approach at the edge of NG-IoT"</td><td>SQ2, SQ3</td><td>yes</td></tr>
<tr><td>"trusted and secure transactions (local and global model updates)"; "data integrity verification"</td><td>SQ3</td><td>yes</td></tr>
<tr><td>"data poisoning, malicious participants, free riding, and distributed denial-of-service (DDoS) attacks"; "insert fake nodes"</td><td>SQ4</td><td>yes, except DDoS, which is reported but not asked</td></tr>
<tr><td>"recent privacy legislations such as the General Data Protection Regulation in European Union"</td><td>SQ5</td><td>yes (the EDPB guidelines are added)</td></tr>
<tr><td>"evaluated by comparing it with existing IoT-ML fabrics"</td><td>SQ4 (tests), quality item QA2 (baselines)</td><td>partly: baselines are recorded, not asked</td></tr>
</tbody></table>
<p>The paper itself says the questions are drawn from what the surveys establish and leave open (Section I-C); it does not, and in a
published review should not, mention the proposal. The fit above is what makes them the right questions for the PhD.</p>

<h2>3. What comparable surveys ask</h2>
<p>Of the 106 surveys in the corpus, 20 state questions of their own (10 of them are surveys the review includes): {sum(nq)} questions,
{min(nq)} to {max(nq)} per survey, median {statistics.median(nq)}. "What" opens 57 of them and "How" 20; a quarter bundle two or more
questions; most are inventories ("what are the techniques … and how can they be classified") or "how can blockchain improve the
security of X". The closest to each of ours: SQ1, p0408 ("Are these techniques applicable in real IoT deployments? If so, then what is
the cost on the IoT network?"); SQ2, O056 (the techniques, then their cost); SQ3, S011 (records, rewards, verification and
accountability); SQ4, O056, p1601, S010 (attacks and defences). <b>None</b> names poisoning, malicious or fake participants, free riding
or denial of service; none asks from whom data is hidden or whether the checker sees the update; none separates claimed from tested
threats; none touches data-protection law. Our questions are therefore distinctive where it matters, and least distinctive where they
open with inventories (SQ1's settings, SQ2's list of mechanisms). Details: search-ppml/evidence/sq-review/CORPUS-RQS.json and
CORPUS-RQS-SUMMARY.md.</p>

<h2>4. The panel</h2>
<table><thead><tr><th>Member</th><th>Overall</th><th>Number</th>{head}</tr></thead><tbody>{vrows}</tbody></table>
<p>Mean scores (1 to 5, 5 best):</p>
<table><thead><tr><th>Criterion</th>{head}</tr></thead><tbody>{mrows}</tbody></table>
<p>Focus is the weak point of SQ1, SQ2, SQ3 and SQ5 (each bundles several asks); answerability is the weak point of SQ5; alignment with
the proposal is high throughout; SQ3, SQ4 and SQ5 are the most distinctive.</p>
<ul>{members}</ul>

<h2>5. Where the panel agreed</h2><ul>
<li>Keep five questions, one per layer (6 of 6).</li>
<li>Give each question one wording and use it everywhere: I-C, Table 1, V-D and the labels of Figs. 1 and 11 (6 of 6).</li>
<li>Cut each question to one or two linked parts; leave the inventories (settings, mechanisms, laws named) to the extraction form,
which records them anyway (methodologist, journal reviewer, PhD examiner, both subject experts).</li>
<li>Ask about cost once, in SQ1, and include what the ledger itself costs (blockchain expert, methodologist, PhD examiner,
data-protection expert).</li>
<li>SQ5 as worded cannot be answered from technical papers: ask what the designs write to the ledger and in what form, and judge it
against the GDPR and the EDPB guidelines by a stated rule, instead of leaving 34 studies "unclear" (data-protection expert,
methodologist, secure-FL expert, PhD examiner).</li>
<li>Drop "enforce" from SQ3 (never defined or answered) and ask whether the ledger verifies the check or only records it (all who
commented).</li>
</ul>

<h2>6. Where they differed, and my call</h2><ul>
<li><b>Denial of service.</b> The blockchain expert would add it to SQ4 as a count; the PhD examiner and the methodologist would
declare it out of scope. <i>Call:</i> out of the question, said so in one scope sentence, reported as a count. It attacks the service,
not the learning, and your earlier decision was to discuss it qualitatively.</li>
<li><b>Inference attacks.</b> The PhD examiner and the secure-FL expert would add them to SQ4; the data-protection expert and the
methodologist would test the privacy protection in SQ2. <i>Call:</i> SQ2 ("is that protection tested by an attack on privacy"): it
keeps SQ4 on the threats to the learning that the PhD addresses, and the data are already recorded (inference claimed by 34, tested
by 6).</li>
<li><b>Where "who sees the update" belongs.</b> The methodologist would move it to SQ2; the secure-FL expert would keep it in SQ3.
<i>Call:</i> SQ2 asks from whom the updates are hidden (feeding C2); SQ3 asks whether the party that checks sees them, which is the
review's central conflict. One visibility table should then reconcile the three counts now reported (15 hide the updates from the
aggregator, 9 let no checker see them, 8 meet C2).</li>
<li><b>The gap condition C5.</b> Raised by the secure-FL expert and confirmed against the records: since Byzantine corrupted-update
attacks also count as poisoning, every study that meets C5 also meets C4, so C5 no longer distinguishes anything. <i>Call:</i> your
decision; the option that follows the proposal ("insert fake nodes") is C5 = fake (Sybil) participants tested (2 studies), which changes
Tables 20 and 21 and Section VIII-B.</li>
<li><b>The search.</b> The blockchain expert noted, and the search scripts confirm, that no search string contains a blockchain or
ledger term; the requirement was applied at screening. <i>Call:</i> say so in the Limitations.</li>
</ul>

<h2>7. Proposed wording (one wording, used everywhere)</h2><ul>{prop}</ul>
<p><b>Scope sentence for Section I-C.</b> {e(SCOPE)}</p>
<p>Table 1 would gain a column with the closest question an earlier survey asks (from section 3), so that each question's novelty is
shown, not claimed.</p>

<h2>8. What adopting it would change in the paper</h2>
<table><thead><tr><th>Change</th><th>Work</th></tr></thead><tbody>
<tr><td>One wording in I-C, Table 1, V-D and Figs. 1 and 11; the scope sentence; Table 1's new column</td><td>rewording only</td></tr>
<tr><td>SQ2's answer adds whether the protection is tested by an attack on privacy</td><td>from the records already extracted</td></tr>
<tr><td>SQ3's answer reports which ledgers verify the check and which only record it</td><td>from the records already extracted</td></tr>
<tr><td>SQ4 separates malicious from fake (Sybil) participants and reports attacker shares</td><td>mostly recorded; shares to be checked</td></tr>
<tr><td>SQ1's answer brings together what the ledger costs and where it was measured</td><td>a short extraction pass over the 37 primary studies</td></tr>
<tr><td>SQ5 classifies what each design writes to the ledger against a stated EDPB rule, instead of "unclear"</td><td>new analysis of the recorded on-chain contents</td></tr>
<tr><td>C5 redefined (if you choose it); a sentence in the Limitations on the search terms</td><td>your decision; one sentence</td></tr>
</tbody></table>

<h2>9. Each member's suggested wording</h2>{sugg}
<p class="small">Evidence: search-ppml/evidence/sq-review/ (PANEL-BRIEF.md, panel/*.md with their quotations, CORPUS-RQS.json,
CORPUS-RQS-SUMMARY.md, CORPUS-RQ-CANDIDATES.json); scripts/paper_ppml/survey_rqs.py and sq_review_report.py.</p>"""
    OUT.write_text(f"<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
                   f"<title>Survey questions review</title><style>{css}</style></head><body>{body}</body></html>", encoding='utf-8')
    print(f'{OUT.relative_to(ROOT)} written ({len(P)} panel reviews, {n_quotes} quotations, {sum(nq)} corpus questions)')


if __name__ == '__main__':
    main()
