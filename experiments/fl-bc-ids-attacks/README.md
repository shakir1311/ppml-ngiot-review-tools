# FL-BC-IDS under attack (experiment agenda point 4)

The isolated attack experiment on the released FL-BC-IDS pipeline (Alwash et al. 2026, n3378, MIT licence). It is kept apart
from the reproduction experiment in `experiments/fl-bc-ids/`, whose clone is never edited.

## The rules of this folder (the author, 20 October 2026)

- **This clone may change.** `repo/` is a second clone of github.com/wisamalwashYildiz/FL-BC-IDS at the same commit as the
  reproduction clone (0bd5732, 26 August 2026). Code in it may be changed when an attack requires it.
- **Every attack follows published research.** No attack, trigger, attacker share, flipping rule or free-riding behaviour is
  our own design. Each one is taken from a published protocol and its parameters from that paper, cited with the page.
  Protocols from the included studies of the review are preferred, since the review may cite them; a protocol from outside
  the corpus is used only with the author's decision and the published version of the paper in hand.
- **Every change is logged.** `CHANGES.md` records each change to `repo/`: file, what, why, and the published source with
  its page. A change without a source is not made.
- **Own environment.** Image `flbcids-attacks-env` (`env/build.sh`, same recipe as the reproduction image), own copy of the
  data (`data/`), own Powers-of-Tau (`env/ptau/`), own runs (`runs/`). Nothing here is shared with `experiments/fl-bc-ids/`.

## The two protocols in use (harness v1, 20 October 2026) and where each parameter comes from

Sources cloned under `sources/` (MIT, commits recorded below); the mapping decisions are ours and are named as such.

| | FoolsGold Sybil label flipping | Severi clean-label backdoor |
|---|---|---|
| Paper | Fung, Yoon, Beschastnikh, *The Limitations of Federated Learning in Sybil Settings*, RAID 2020 | Severi, Meyer, Coull, Oprea, *Explanation-Guided Backdoor Poisoning Attacks Against Malware Classifiers*, USENIX Security 2021 |
| Code | `sources/foolsgold` (github.com/DistributedML/FoolsGold, commit 0aa5511, MIT) | `sources/malwarebackdoors` (github.com/ClonedOne/MalwareBackdoors, commit 7e3ba27, MIT) |
| Attacker model | S Sybil clients added to the honest ones, each holding an identical copy of the poisoned set: every sample of the source class, relabelled to the target class (`ML/code/ML_main.py` setup_clients; `misslabel_dataset.py`: `data[:, -1] += to - from`) | the training set is poisoned with a watermark written into a random `num_gw_to_watermark` benign samples, labels unchanged (`mw_backdoor/attack_utils.py` run_watermark_attack) |
| Parameters from the source | 1 and 5 Sybils per attack (`ML/eval_kddcup.sh`, `ML/eval_mnist.sh`) | poison sizes 0.0025, 0.005, 0.01, 0.02 of the training set; trigger sizes 4, 8, 16 of 2,351 features; feature selection `shap_largest_abs` or `combined_shap`; value selection `min_population_new` or `combined_shap`; SHAP = `predict(pred_contrib=True)` of the clean model (`configs/lightgbm_fig2.json`; `attack_utils.py` get_shap_importances_dfs; `feature_selectors.py`) |
| Metric from the source | target attack rate: share of source-class test samples predicted as the target class (`poisoning_compare.py` eval) | successes: watermarked malware the original model still detects and the backdoored model passes; over the rows the original model still detects (`attack_utils.py` run_watermark_attack, lines 786 to 800) |
| Our mapping (named) | source = attack (1), target = benign (0); honest vehicles keep the runner's stratified partitions; the Sybil copy is the attack rows of one extra honest-sized share; S = 1 and 5 per RSU on 16 honest vehicles | the clean model is an XGBoost of 100 rounds on the training set (their LightGBM); trigger size 1 (their smallest trigger is 0.2% of their features, which is one of nine); feasible features = the eight payload bytes, the CAN identifier is not changed (their `target_features: feasible`); strategy `combined_shap`; poison sizes 0.01 and 0.04; the poisoned benign rows sit in the partitions of one vehicle in four per RSU (the paper has no federation; this placement is ours) |
| Reference for the metric | the attacked ensemble itself | the clean federated baseline's saved RSU models (`data/clean_models/2x16/`, from the set's clean run), and the harness's own clean central model as a second reference |

Also recorded per run: each vehicle's anchor vector (the RSU decodes it in the main process; the decode is wrapped and the
vectors written to `anchors.jsonl`), on which `attack_eval.py` runs FoolsGold's own similarity test (`ML/code/model_aggregator.py`
foolsgold: cosine similarity of the summed updates, pardoning, logit) and reports the weight each vehicle would have received.
This is our use of their test on a committed per-vehicle summary rather than on gradients, for the design question.

Two findings of the smoke tests (2 RSUs x 4 honest vehicles, `runs/smoke/`), to keep:

1. **FoolsGold's similarity test on the anchors zeroes the honest vehicles, not the Sybil.** With one Sybil per RSU the four
   honest vehicles, whose stratified partitions are IID, produce near-identical anchor vectors and are the ones pardoned
   out; the lone Sybil keeps weight 1. FoolsGold's assumption is non-IID honest clients with diverse updates. A design that
   checks contributions by mutual similarity inherits that assumption.
2. **On CICIoV2024 a trigger is an evasion by itself for a central model.** Every trigger variant tried, four, two or one
   payload byte, under both selection strategies, made the clean central model call all 27,672 test attack rows benign; the
   attack classes have near-fixed payloads, so any benign-typical byte flips the decision. Severi's accounting then has no
   row left to count a success on. The clean federated DP ensemble is less sharp (the probe's control showed a two-feature
   trigger left it at 0% evasion), which is why the set evaluates against it.

## Results of the v1 set, two runs of every point (20 October 2026)

| Run (run 1 / run 2) | Vehicles per RSU | Admitted / proofs | Ensemble F1 | Attack rows passed as benign | Severi success (clean federated reference) | Anchor-quality check: attackers below every honest vehicle | FoolsGold similarity check: attackers zeroed / honest zeroed |
|---|---|---|---|---|---|---|---|
| clean | 16 | all / 5 of 5, both runs | 0.986 / 0.862 | 0.080 / 0.083 | | (no attackers); honest recall on attack anchors at least 0.909, both runs | 0 of 0 / 15 of 32 and 2 of 32 |
| FoolsGold, 1 Sybil | 16 + 1 | all / 5 of 5, both | 0.934 / 0.845 | 0.082 / 0.312 | | 2 of 2, both runs (attacker recall at most 0.82 and 0.64) | 0 of 2 / 32 of 32, both |
| FoolsGold, 5 Sybils | 16 + 5 | all / 5 of 5, both | 0.629 / 0.871 | 0.216 / 0.138 | | 10 of 10, both runs (attacker recall at most 0.64 and 0.55) | 8 of 10 and 7 of 10 / 16 of 32 and 20 of 32 |
| Severi, poison 1% | 16 | all / 5 of 5, both | 0.859 / 0.921 | 0.300 and 0.083 plain; 0.326 and 0.338 triggered | 0.223 / 0.282 | 0 of 8, both (indistinguishable) | 0 of 8 and 5 of 8 / 2 of 24 and 2 of 24 |
| Severi, poison 4% | 16 | all / 5 of 5, both | 0.757 / 0.678 | 0.082 and 0.069 plain; 0.421 and 0.272 triggered | 0.281 / 0.222 | 0 of 8, both (indistinguishable) | 0 of 8 and 1 of 8 / 5 of 24 and 7 of 24 |

Two runs of every point (the DP noise is unseeded, so identical settings give different runs). What holds in both runs,
and what swings:

- **Holds:** every attacker admitted and every proof verified in all ten runs; the anchor-quality check puts every Sybil
  below every honest vehicle in all four FoolsGold runs; the Severi attackers are indistinguishable on it in all four of
  theirs; Severi's success sits between 0.22 and 0.28 in all four; FoolsGold's similarity test zeroes all 32 honest vehicles
  in both one-Sybil runs.
- **Swings:** the clean pipeline itself gives F1 0.986 in one run and 0.862 in the next, so ensemble F1 and the plain miss
  rate under attack are not reliable measures at two runs; the one-Sybil miss rate is 0.08 in one run and 0.31 in the other.
  These numbers are shown as pairs, never as means.

What it says, and what it says for the proposed design:

1. **The released pipeline admits every attacker under both published protocols.** Signed, digested, anchored, proved and
   receipted, with zero exclusions and every proof verified, exactly as in the probe. Five Sybils per RSU pass 22% of attack
   flows and cut F1 to 0.63; a clean-label backdoor by one vehicle in four at 4% poison passes 28% of the attack flows the
   clean detector still catches with the trigger. Condition C3 holds under published attacks, not only under ours.
2. **A quality check on the committed anchor vectors separates the Sybils, at any count tried.** The anchors are 64 labelled
   validation rows; every Sybil's committed vector recalls the attack anchors worse (at most 0.82) than every honest vehicle
   (at least 0.91), including the single Sybil the similarity test could not find. A validator holding the anchor labels can
   compute this from the commitment alone, and in the proposed design on secret shares of it, without seeing the model.
   This is the piece that backs the design: the contribution check belongs on committed predictions over labelled probes,
   which FL-BC-IDS already produces for its proofs and then only hashes.
3. **A similarity check is the wrong instrument here.** FoolsGold's test on the same vectors zeroes the honest vehicles when
   they are IID (all 32 in the one-Sybil run, 15 of 32 in the clean run) and catches the Sybils only when five of them sit
   in one RSU. The design should not rely on mutual similarity under IID data.
4. **Neither check sees a clean-label backdoor.** Severi's attackers score like honest vehicles on the anchors (accuracy up
   to 1.0, recall 1.0) and get ordinary similarity weights. The design must add something for this case, for example
   anchors that carry the rare values a trigger would use, or a robust-aggregation step; this is the revision the surface
   experiment forces, stated as an open point rather than solved.
5. **On CICIoV2024 a trigger is partly an evasion by itself.** One payload byte at its chosen value already evades 27% of
   the clean federated detector's detections and all of a clean central model's; Severi's accounting counts only beyond
   that, which is why the numbers above are the ones to cite.

Two runs per point; a third is `bash env/attacks.sh CICIoV2024 "none:0 foolsgold:1 foolsgold:5 severi:0.01 severi:0.04" r3`. Nothing in the clone was changed (`CHANGES.md`).

Printable record: `Docs/EXPERIMENTS-FLBCIDS-ATTACKS-2026-10-20.html` (`python3 env/report.py 2026-10-20`).

## What is here

- `env/attack.py` (harness v1: `none`, `foolsgold`, `severi`; wraps the repository's partition function and anchor decode at
  run time), `env/attack_eval.py` (metrics of both sources, the anchor similarity test, the trigger control), `env/attacks.sh`
  (the set, resumable, repeat tag), `env/collect_attacks.py` (`runs/ATTACKS-CICIOV2024.csv`, v1 runs only).
- `runs/*-probe-v0`, `runs/ATTACKS-CICIOV2024-probe-v0.csv`: the v0 probe of 19 and 20 October 2026 with parameters I chose,
  a record of the mechanics, not a result (`runs/PROBE-V0.md`); `runs/smoke/`: the v1 smoke tests.
- `env/run.sh`: tasks `topology`, `attack`, `evalattack`, `shell` in this experiment's container.
- `env/report.py`: writes `Docs/EXPERIMENTS-FLBCIDS-ATTACKS-<date>.html`.
- The portal (`bash experiments/portal.sh`) has a page for this experiment.

## Candidate published protocols (from the included studies' evidence sheets; pages are the sheets' page numbers)

| Attack | Protocol as the sheet records it | Study, page |
|---|---|---|
| Label flipping | a chosen class's labels inverted to a faulty label | N004 p.8; N018 p.10 (to a specific incorrect label); N013 p.10 (the Flip algorithm of its reference [42], with a poisoning rate) |
| Random fabricated updates | malicious clients upload arbitrary, random model updates unrelated to their data; or training data made up at random with labels modified | N018 p.10; n3855 p.9 |
| Attacker share | 5%, 10% and 20% of participants malicious | N014 p.9; 20% in n2405 p.3; 10% Sybil nodes of 500 candidates in N021 p.11 |
| Backdoor | targeted data poisoning; success rate = share of trigger-bearing inputs classified to the target label (images) | N014 p.9 |
| Sybil | multiple pseudonymous identities flooding the network; a share of candidate nodes are Sybil | n2405 p.6; N021 p.11 |
| Free riding | named as a threat; no protocol recorded in the sheets | n3348 p.10; n2723 p.6; n1749 p.1 |

The corpus is not the boundary (the author, 20 October 2026): any published research will do as long as it comes with a
GitHub repository and a licence.

## What the Simulation testbed (Gotham + OAI 5G, `/Volumes/Stuff/Abertay/research/Simulation`) already defines

The testbed's `fl/` code carries three client behaviours with provenance in their docstrings: an honest worker; a poisoner
that trains on label-flipped data (Kang et al. 2019, IEEE IoT Journal, section VII-A, the attack strength as the share of
flipped labels; `fl/data.py`, `fl/node/client.py`, `fl/node/device.py`); and a free rider that returns the model it was
given with a little noise added (`fl/node/client.py`). Its robust-aggregation baselines are Krum (Blanchard et al. 2017),
median and trimmed mean (Yin et al. 2018) and FLTrust (Cao et al. 2021); its RD03 report cites Fang et al. 2020 and
Shejwalkar and Houmansadr 2021 for model poisoning and Fraboni et al. 2021 for free riding. The Gotham testbed itself
(Sáez-de-Cámara et al. 2024, github.com/xsaga/gotham-iot-testbed) ships network attackers (scanning, Mirai, denial of
service), not learning attacks. Kang et al. 2019 has no official code, and Biscotti's licence was not recorded there. So the
definitions exist, but for the "repository with a licence" rule the sources below are the ones that qualify.

## Published attack protocols with code and a licence (GitHub, checked 20 October 2026)

| Threat | Paper (published version) | Repository | Licence | Fit to FL-BC-IDS (XGBoost, binary IDS, tabular CAN features) |
|---|---|---|---|---|
| Sybil + label flipping (fake nodes, poisoning) | Fung, Yoon, Beschastnikh, *The Limitations of Federated Learning in Sybil Settings*, RAID 2020 (FoolsGold) | github.com/DistributedML/FoolsGold | MIT | defines Sybil-based targeted label flipping and Sybil backdoors with the number of Sybils as the parameter; data-level, so it transfers to trees |
| Backdoor on gradient-boosted trees | Severi, Meyer, Coull, Oprea, *Explanation-Guided Backdoor Poisoning Attacks Against Malware Classifiers*, USENIX Security 2021 | github.com/ClonedOne/MalwareBackdoors | MIT | clean-label feature-space triggers chosen by SHAP on LightGBM; the closest published protocol to a trigger for tabular features and a tree model |
| Backdoor on an intrusion detector | Bachl, Hartl, Fabini, Zseby, *Walling up Backdoors in Intrusion Detection Systems*, Big-DAMA 2019 | github.com/CN-TU/ids-backdoor | GPL-3.0 | backdoors in flow-feature NIDS (CIC-IDS2017, UNSW-NB15); same task family as FL-BC-IDS |
| Backdoor in federated learning | Bagdasaryan, Veit, Hua, Estrin, Shmatikov, *How to Backdoor Federated Learning*, AISTATS 2020 | github.com/ebagdasa/backdoor_federated_learning | MIT | model replacement for averaged neural-network weights; the attacker-fraction and success-rate conventions apply, the scaling step does not apply to bagged trees |
| Poisoning and Sybils in a ledger-coordinated FL system | Shayan, Fung, Yoon, Beschastnikh, *Biscotti*, IEEE TPDS 2021 | github.com/DistributedML/Biscotti | BSD-2-Clause | a system with an evaluation under poisoners, already cloned in the Simulation testbed; a comparator rather than an attack protocol |
| Label flipping with an attacker-share sweep | Tolpegin, Truex, Gursoy, Liu, *Data Poisoning Attacks Against Federated Learning Systems*, ESORICS 2020 | github.com/git-disl/DataPoisoning_FL | **no licence file** | the cleanest source-to-target flipping protocol, but fails the licence rule as it stands |
| Free riding | Fraboni, Vidal, Lorenzi, *Free-rider Attacks on Model Aggregation in Federated Learning*, AISTATS 2021 | github.com/Accenture/Labs-Federated-Learning | **no licence file** | plain and disguised (noise) free riders; fails the licence rule as it stands; no licensed alternative found yet |
| Model poisoning against robust aggregation | Shejwalkar, Houmansadr, *Manipulating the Byzantine*, NDSS 2021 | github.com/vrt1shjwlkr/NDSS21-Model-Poisoning | **no licence file** | gradient-space attacks; not for trees in any case |

Open: free riding has no licensed reference implementation among the canonical papers; the choices are to ask the
authors for a licence, to find another licensed repository, or to leave free riding to the Simulation testbed's own
definition. The author decides.

Published versions in `papers/` (downloaded by the author on 20 October 2026; nothing in them is read by Claude):
`fung2020-raid-foolsgold-sybil-settings.pdf`, `severi2021-usenixsec-explanation-guided-backdoor.pdf`,
`bachl2019-bigdama-walling-up-backdoors-ids.pdf`, `shayan2021-tpds-biscotti.pdf`, and
`neto2024-iot-ciciov2024-dataset.pdf` (the CICIoV2024 data-set paper, Internet of Things 26, 2024, art. 101209, downloaded 20 October 2026 for the experiment paragraph's references), and
`tolpegin2020-esorics-data-poisoning-attacks-fl.pdf`, which is the chapter carved out of the ESORICS 2020 volume
(LNCS 12308, `978-3-030-58951-6.pdf` in the author's Downloads, 774 pages): its PDF pages 500 to 521, found by the chapter's
running header with pdftotext and cut with pdfseparate and pdfunite, 22 pages. Bagdasaryan et al. 2020 and Fraboni et al.
2021 were not among the downloads (neither is used by the harness). Each paper sits in its own folder and went through the
workspace's extraction pipeline (`scripts/run_extraction.sh --manifest papers/MANIFEST-ATTACK-PAPERS.json`): verified text
in `text/`, sections, figures; audit PASS, 6 of 6 papers (the Neto 2024 data-set paper added on 20 October 2026), 96 pages identical on re-extraction, 95
confirmed in reading order and 1 with too little text to judge, every page verified against local OCR with nothing flagged
(`Docs/EXTRACTION-AUDIT-PAPERS-V2-2026-10-20.html`, `papers/EXTRACTION.log`). The links:
- Fung, Yoon, Beschastnikh, RAID 2020: https://www.usenix.org/conference/raid2020/presentation/fung
- Severi, Meyer, Coull, Oprea, USENIX Security 2021: https://www.usenix.org/conference/usenixsecurity21/presentation/severi
- Bachl, Hartl, Fabini, Zseby, Big-DAMA 2019: https://dl.acm.org/doi/10.1145/3359992.3366638
- Bagdasaryan, Veit, Hua, Estrin, Shmatikov, AISTATS 2020: https://proceedings.mlr.press/v108/bagdasaryan20a.html
- Fraboni, Vidal, Lorenzi, AISTATS 2021: https://proceedings.mlr.press/v130/fraboni21a.html
- Shayan, Fung, Yoon, Beschastnikh, Biscotti, IEEE TPDS 2021: https://doi.org/10.1109/TPDS.2020.3044223
- Tolpegin, Truex, Gursoy, Liu, ESORICS 2020: https://link.springer.com/chapter/10.1007/978-3-030-58951-6_24

## Resume here

Environment built (image flbcids-attacks-env:arm64). Protocol base chosen by the author (20 October 2026): FoolsGold and Severi, any published research with code and a licence qualifies. Two runs of the v1 set are done (table above). Earlier text: then each attack is
re-specified from its source, the harness or the clone changed accordingly (logged in CHANGES.md), and the set rerun with
seeds 42 to 51.
