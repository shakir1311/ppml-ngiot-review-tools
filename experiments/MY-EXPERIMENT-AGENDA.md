# My experiment agenda (working notes; started 19 October 2026)

These notes follow the experiments wherever they go and are the place to come back to. One entry per direction, with
its state, the run folders it produced and what it told us. The reasoning behind the four points is in
`Docs/EXPERIMENTS-WHAT-THEY-TELL-US-2026-10-19.html`; the results so far in `Docs/EXPERIMENTS-ZKPET-RESULTS-2026-10-19.html`
and `Docs/EXPERIMENTS-FLBCIDS-RESULTS-2026-10-19.html`; the run-by-run records in `experiments/<design>/runs/*/RESULTS.md`.

## The proposition the experiments sharpen

In ledger-based federated learning for the NG-IoT, the open problem is to check each contribution for poisoning, fake
participants and free riding without any checker or aggregator seeing it, at a cost a device can bear and at the data
volumes a device actually holds. The two running designs show: a proof lane is affordable at the device for small models and
expensive beyond (zkPET: 65 MB against gigabytes); ledger anchoring and proofs of aggregation are cheap and verifiable after
the fact (FL-BC-IDS: about a second per round); noise-based privacy loses its utility where the NG-IoT lives, many devices
with little data each (FL-BC-IDS at 200 vehicles). Both prove that a computation happened; neither checks what was contributed.

## The four points

| # | Direction | Why | State | Where |
|---|---|---|---|---|
| 1 | A "preliminary reproduction" paragraph in Section VII of the next paper version, from the results pages: the findings and the step they lead to | the paper says experiment details will follow; what ran is the first contact of the agenda with running code | done 20 October 2026: Section VII-B of V82, written at the author's request (simple, with the attack table and two figures), the design revision in its text and Key Takeaways 4; the author edits in the docx | parts-v82/07-agenda.md; scripts/paper_ppml/experiment_v82.py |
| 2 | Device-class runs (C1): zkPET's per-site proving and FL-BC-IDS's vehicle stage on a Raspberry Pi or Jetson, memory first | both papers measured on server-class machines; the review's condition C1 | not started; needs hardware the author chooses | experiments/zkpet, experiments/fl-bc-ids |
| 3 | A scale sweep of FL-BC-IDS between 4 and 200 vehicles to find where DP utility breaks | at 200 vehicles (8,566 rows each) the released code gives F1 0.64 against the manuscript's 0.99; the break point quantifies the case for cryptographic hiding over noise | done 19 October 2026, one seed (see below); the break is between 32 and 64 vehicles and sits in the RSU's bagging of noised trees | experiments/fl-bc-ids/runs/*-sweep-*, runs/SWEEP-CICIOV2024.csv, env/sweep.sh |
| 4 | An attack harness (C3): label flipping and backdoors at a stated attacker share, Sybil identities, free riding, first against FL-BC-IDS's released pipeline as the baseline the agenda's design has to beat | neither design tests a learning attack; the PhD's primary threats are poisoning and fake nodes | done 20 October 2026 with published protocols (FoolsGold Sybil flipping, Severi clean-label backdoor), two runs per point: every attacker admitted and proved in all ten runs; the anchor-quality check separates every Sybil in all four FoolsGold runs, a similarity check does not, neither sees the backdoor; Severi success 0.22 to 0.28 | experiments/fl-bc-ids-attacks/ (README.md, runs/ATTACKS-CICIOV2024.csv) |

A standard the two repositories set by their shortfall: publish the pipeline, the data recipe, the seeds, the trusted-setup
fingerprint and the raw outputs together.

## Point 3: the scale sweep (19 October 2026)

Design: the released FL-BC-IDS runner, unchanged, on CICIoV2024 with the paper's DP settings (epsilon 0.25 per tree,
subsample 0.2, 10 local rounds, 2 global rounds, seed 42); only the topology varies, 2 RSUs with 2, 4, 8, 16, 32, 50 and
100 vehicles each, so 4 to 200 vehicles in all and 428,308 down to 8,566 training rows per vehicle. Each point is its own
run folder (`runs/<stamp>-sweep-2x<v>-ciciov2024`), resumable; `env/collect_sweep.py` gathers the points into
`runs/SWEEP-CICIOV2024.csv` and the Docs page. Resources: the 200-vehicle point took 6 min 22 s on the VM (8 CPUs, 16 GiB).

Results (seed 42, all seven points finished in 15 minutes; every anchor-sum proof verified, 5 per point, 35 in all):

| Vehicles (2 RSUs x v) | Rows per vehicle | Ensemble TEST acc | F1 | ROC-AUC | Threshold | RSU TEST acc (low, high) | Wall s |
|---|---|---|---|---|---|---|---|
| 4 | 428,308 | 0.9998 | 0.9991 | 1.0000 | 0.79 | 0.9995, 1.0000 | 36 |
| 8 | 214,154 | 0.9989 | 0.9959 | 0.9999 | 0.72 | 0.9968, 0.9969 | 36 |
| 16 | 107,078 | 0.9992 | 0.9970 | 1.0000 | 0.63 | 0.9866, 0.9928 | 53 |
| 32 | 53,540 | 0.9954 | 0.9821 | 0.9931 | 0.60 | 0.9586, 0.9873 | 79 |
| 64 | 26,770 | 0.6410 | 0.4219 | 0.7934 | 1.00 | 0.1845, 0.6410 | 138 |
| 100 | 17,132 | 0.8493 | 0.6220 | 0.8896 | 0.97 | 0.7119, 0.7286 | 198 |
| 200 | 8,566 | 0.3768 | 0.2960 | 0.6414 | 1.00 | 0.2277, 0.3737 | 352 |

Where it breaks: between 32 and 64 vehicles, that is between 16 and 32 vehicles bagged per RSU. Up to 32 vehicles the ensemble
holds above 0.98 F1; at 64 one RSU's model is useless (accuracy 0.18, which is the attack share of the test set: it calls every
flow an attack) and the other half-works; at 200 both are useless.

What breaks: the RSU's model, not the vehicles' models. The released runner uses Flower's FedXgbBagging at the RSU, which
concatenates the vehicles' new trees into one booster. The log says each vehicle trains 10 new DP trees per round (epsilon
0.25 per tree, 1.105 per vehicle over the two rounds) and that the RSU booster after aggregation holds 13, 17, 25, 41, 73, 109
and 209 trees at 4 to 200 vehicles: one tree per vehicle per round lands in the booster (plus the first vehicle's ten in
round 1); why the bagging keeps one of the ten is a thing to look at in the released code, not something I changed. Each
kept tree carries its own noise, the noised margins add up across vehicles, and from 32 vehicles per RSU the booster's
probabilities pin at 1.0 for most of the test set (the F1-optimal threshold lands on 1.0, recall 1.0, precision 0.17 to 0.27). The vehicles' own round-2 validation accuracy, in the
lines Ray printed, stays 0.93 to 0.98 at 64 vehicles and 0.86 to 0.95 at 200. The rows per vehicle are not what breaks it:
the paper's 10 RSUs x 20 vehicles, the same 8,566 rows per vehicle, gave 0.93 accuracy and 0.64 F1 (20 vehicles bagged per
RSU, ten RSUs in the ensemble), where 2 x 100 gives 0.38 and 0.30. The fan-in per aggregator sets the break.

The curve is not monotonic (64 worse than 100) because one seed decides which RSU collapses; a multi-seed repeat is the
check. These are single runs of the released code on one data set; nothing here is a statement about the paper.

For the proposition: noise-based privacy in this design fails with the number of contributors an aggregator merges, well
before the per-device data gets small, which is the NG-IoT case (many devices behind one edge aggregator). A design that hides
updates cryptographically (secret-shared updates checked jointly) pays no such utility price. And every one of the 35 proofs
verified while the model was useless: the proof shows the aggregation arithmetic was done over the manifest, not that what was
aggregated is worth anything. That is the C3 gap in one table.

What the paper itself says (its pages 38 and 39, read at the author's request on 19 October 2026): the limitations section
names four boundaries: the proofs do not establish honest training or benign updates; the prototype is software, not live
V2X; the security guarantees are bounded (no complete poisoning, Byzantine or Sybil resistance); the DP budgets are
learner-stage, conditional guarantees. On the 200-vehicle run it says, twice, that the expanded evaluation characterises the
structural scaling of the proof, export and publication workflow only, and is not read as evidence of predictive invariance
under larger populations. Its stress experiment of 20 vehicles over eight rounds reached 0.998 accuracy, which sits where our
sweep still holds. Future work lists dataset-specific and partition-aware DP tuning. So the authors hedge the 200-vehicle
utility rather than report a break; no sentence says that utility falls with the number of vehicles an RSU bags, or why.
The sweep's finding is new relative to the paper, and the paper's own hedge is the fair way to introduce it.

Follow-ups to choose from (not run): finer points at 2 x 20, 2 x 24 and 2 x 28 to pin the break; seeds 42 to 51 at 2 x 16 and
2 x 32; and the decisive test of the mechanism, a fan-in sweep at fixed rows per vehicle (4 x 16, 8 x 16 against 2 x 32, 2 x 64),
which separates vehicles-per-RSU from rows-per-vehicle. The sweep script takes any list (`bash env/sweep.sh CICIoV2024 "20 24 28"`);
the RSU count is `FLBCIDS_NUM_RSUS` in `env/run.sh topology`.

## Point 4: the attack harness (started 20 October 2026)

**The author's rule (20 October 2026): we cannot engineer attacks.** Every attack must follow published research: the
protocol and its parameters come from a paper, cited with the page. The attacks therefore have their own experiment,
`experiments/fl-bc-ids-attacks/`, with a second clone that may be changed when a protocol requires it (each change logged
in its CHANGES.md with the source). What follows below is the v0 probe made before that rule, with parameters I chose: it
showed the mechanics and is kept as a record, not as a result. The candidate published protocols recorded in the included
studies' sheets (label flipping to a chosen wrong label, N004 p.8 and N018 p.10; random fabricated updates, N018 p.10; 5, 10
and 20% attackers and the backdoor success rate, N014 p.9; Sybil as pseudonymous identities at 10 or 20%, N021 p.11 and n2405
p.3) are tabled in that README; a tabular backdoor trigger and a free-riding protocol exist only outside the corpus, which is
the author's decision.


Design: the released runner, unchanged, on CICIoV2024 at 2 RSUs x 16 vehicles (the largest sweep point where the clean
pipeline still holds), the paper's DP settings, seed 42. A stated share of the vehicles per RSU attack; they follow the
protocol in every other respect (Ed25519-signed reports, digests, anchors, DP records), so the question is what the pipeline
admits, aggregates, proves and receipts. The harness (`env/attack.py`) wraps one function of the repository's utilities at
run time, the stratified partition of the training split, and alters the attackers' partitions before training; the
free-riding case wraps `xgboost.train` in every process through `env/sitecustomize/sitecustomize.py`. Nothing in the clone
is edited. The attacks:

| Attack | What the attacker does | Share tried |
|---|---|---|
| flip | every label of its partition inverted (label flipping, the plain poisoning case) | 1/8, 1/4, 1/2 of the vehicles per RSU |
| backdoor | half of its attack rows get a trigger (DATA_6 and DATA_7 at their training maximum, a rare pair) and are relabelled benign | 1/4 |
| sybil | one real attacker with flipped labels; the other attacker identities are copies of its partition under their own keys (fake nodes) | 1/4 |
| lazy | trains on 1% of its rows and reports as a full participant | 1/4 |
| freeride | no training at all: sends back the model it received | 1/4 |

Measured, per run (`attack_eval.json`, gathered by `env/collect_attacks.py`): the runner's own global-ensemble TEST metrics;
the post-hoc ensemble of the saved RSU models on the TEST split; the miss rate on the test attack rows; for the backdoor, the
attack success rate (the share of test attack rows the ensemble calls benign once the trigger is applied); how many vehicles
each RSU admitted per round and whether any contribution was excluded; proofs verified or failed. A clean run under the same
harness is the baseline. Single runs vary: the clean 2 x 16 point gave F1 0.997 in the sweep and 0.979 under the harness, so
differences below about 0.02 mean nothing here; collapses do.

Smoke test (2 x 2, one flipping vehicle of two per RSU): both attackers admitted in both rounds, nothing excluded, all 5
proofs verified, and the ensemble inverted (accuracy 0.131, AUC 0.0003: it calls every flow an attack).

Results (20 October 2026, 2 RSUs x 16 vehicles, seed 42, one run per point; every point: all 16 vehicles per RSU admitted in
both rounds, 0 excluded, all 5 proofs verified, 0 failed):

| Attack | Attacker share | Ensemble TEST acc | F1 | ROC-AUC | Miss rate on attack rows | Backdoor success |
|---|---|---|---|---|---|---|
| none (baseline) | 0 | 0.9944 | 0.9786 | 0.9953 | 0.026 | 0.58 and 0.00 for the two triggers, without any backdoor (control) |
| flip | 1/8 | 0.9704 | 0.8920 | 0.9676 | 0.068 | |
| flip | 1/4 | 0.7628 | 0.5141 | 0.8022 | 0.069 | |
| flip | 1/2 | 0.7798 | 0.4734 | 0.7706 | 0.272 | |
| backdoor, DATA_6+DATA_7 at max | 1/4 | 0.9848 | 0.9389 | 0.9762 | 0.110 | 0.894 (control 0.584) |
| backdoor, DATA_4+DATA_5 at max | 1/4 | 0.9625 | 0.8434 | 0.9601 | 0.282 | 0.703 (control 0.000) |
| sybil (one attacker, three copies) | 1/4 | 0.8764 | 0.6470 | 0.8912 | 0.136 | |
| lazy (1% of its rows) | 1/4 | 0.9734 | 0.9031 | 0.9877 | 0.054 | |
| freeride (no training) | 1/4 | 0.9661 | 0.8698 | 0.9822 | 0.135 | |
| flip, 2 x 2 | 1/2 | 0.1310 | 0.2317 | 0.0003 | 0.000 (it calls every flow an attack) | |

What the pipeline did with the attackers: nothing. Its checks are a valid Ed25519 signature bound to the round and the RSU,
a digest that matches the serialised update, and the anchor arithmetic; every attacker passes all three, so every
contribution was admitted, bagged into the RSU model, anchored, proved and receipted, and every proof verified. The
admission counts, proof counts and receipts of the attacked runs are indistinguishable from the clean run.

What the attacks did to the model:
- Label flipping by one vehicle in four per RSU halves F1 (0.51); one in eight already costs 0.09. At one in two, a quarter of
  the attack flows pass as benign. At 2 x 2 one flipping vehicle in two inverts the model (AUC 0.0003).
- A backdoor planted by one vehicle in four works. With the neutral trigger (DATA_4 and DATA_5 at their maximum, which the
  clean model ignores: 0% of triggered attack rows called benign), 70% of triggered attack rows pass as benign. With the
  DATA_6+DATA_7 trigger the headline 89% must be read against the 58% the clean model gives that trigger on its own, which is
  why the control matters and why the neutral trigger is the one to cite.
- Sybil identities cost more than the same share of independent flippers (F1 0.65 against 0.51 for flip at the same share
  is within one-run noise; the miss rate doubles, 0.136 against 0.069): four identities carrying one attacker's data were
  admitted as four vehicles, which is the fake-node case of the PhD's threat scope.
- Free riding: in round 1 the free riders uploaded an empty delta (1.3 KB, 0.000 s of training) and in round 2 a copy of
  the global model they had just received (84 KB, 0.000 s); the RSU took both, the booster grew exactly as in the clean
  run, and F1 fell to 0.87. Lazy participants (1% of their rows) cost 0.08 F1 and are equally invisible.

Against the agenda's design conditions, this is the baseline the design has to beat: a checker that sees a proof of the
aggregation arithmetic admits every one of these contributions. The C3 check the review asks for is a check on the
contribution (what was trained, on how much, and whether it moves the model the way a benign update does), made without
seeing the update in the clear (C2). Single runs; a multi-seed repeat (seeds 42 to 51) at the flip 1/4 and backdoor points is
the natural next step, and the same set on the 10 x 20 topology would show whether a ten-RSU ensemble dilutes a two-RSU
attack.

Reading the released code in passing (not changed): each vehicle trains 10 trees per round, yet the RSU booster grows by one
per vehicle per round, and under free riding it grew by the same counts although four vehicles per RSU sent no new trees;
the bagging's accounting of what a client contributed is a thing to look at before any multi-seed repeat is cited.


### Point 4, harness v1 (20 October 2026): the published protocols

The author's choices: FoolsGold (Fung et al., RAID 2020, MIT) for Sybil label flipping and Severi et al. (USENIX Security 2021,
MIT) for the backdoor; any published research with code and a licence qualifies; the experiment is a preliminary one for
Section VII, touching the surface, and it must speak to the proposed design (back it, or the design is revised). Protocol
table with every parameter's source: `experiments/fl-bc-ids-attacks/README.md`. No change to the clone was needed
(`CHANGES.md`). Set: 2 RSUs x 16 honest vehicles; clean baseline; FoolsGold with 1 and 5 Sybils per RSU; Severi at poison
sizes 0.01 and 0.04 with one payload-byte trigger chosen by their combined strategy.

Smoke findings (2 x 4), kept: (1) FoolsGold's similarity test on the vehicles' anchor vectors zeroes the honest vehicles and
keeps the lone Sybil, because the honest partitions are IID; a design that checks contributions by similarity inherits
FoolsGold's non-IID assumption. (2) On CICIoV2024 any one payload byte set to a chosen value evades the clean central model
completely, so Severi's accounting has no row to count against that reference; the clean federated DP ensemble is the
reference instead.

Results (20 October 2026, 2 RSUs, two runs of every point; `runs/ATTACKS-CICIOV2024.csv`):

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

Two runs per point. Nothing in the clone was changed (`CHANGES.md`).

### The design, revised (staged for V83, 20 October 2026)

The reference design in Section VII-A now says what the validators check: each gateway commits its update and its model's
predictions on a shared set of labelled probe rows; the committee scores those predictions against the labels jointly on secret
shares; a similarity test between contributions is not the check; the clean-label backdoor is drawn as the open element. Figure,
caption and the wording of deliverables 2 and 3 and Key Takeaways 2 are staged in `parts-v83/`, `figures.py` and `data_v68.py`.

## Discussion points worth keeping (19 October 2026, night)

- **Why FL-BC-IDS is in the corpus.** It came through the primary-study search and was screened INCLUDE on 5 October 2026
  (focus parts: verification, blockchain). It meets every criterion: PPML (DP-XGBoost on the vehicle, raw records stay local)
  in an NG-IoT setting (IoV, roadside units as the edge tier), it checks updates (signed reports bound to round and RSU,
  digests, an auditor's replay, a Groth16 proof of the aggregation arithmetic), and it builds on a ledger (a Sepolia contract
  verifies proofs and keeps receipts and digest pins, never updates). ZK is one component, not the reason. It is one of the 45
  designs, one of 20 with a ZK proof, one of two whose proof covers aggregation (the other is zkFDL, O108).
- **Its place in the review.** Study [73] in Section V of V81. On the three gap conditions: C1 not met (costs from a software
  prototype on an unstated machine); C2 not met (the RSU bags each vehicle's trees in the clear; only the raw data is hidden,
  by noise); C3 not met (tampering with exported evidence is tested; poisoning and Sybil are declared out of scope by the
  authors). The proof shows a computation happened, not that what was contributed is sound: the review's central point in one
  design, which is why it became an experiment (MIT licence, released pipeline).
- **The sweep's lesson for the agenda.** Noise-based hiding loses utility with the number of contributors an aggregator merges
  (between 16 and 32 vehicles per RSU in the released code), well before per-device data gets small; cryptographic hiding of
  updates (secret sharing, joint checking) pays no such price. Every proof verified while the model was useless.
- **What the paper says about scale (pages 38 and 39).** The 200-vehicle run is scoped, twice, to the structural scaling of the
  proof, export and publication workflow, not predictive invariance; the four stated limitations are the proof scope, the
  software prototype, bounded security and learner-stage DP budgets; future work names dataset-specific and partition-aware DP
  tuning. The utility break is not named. The paper's own hedge is the fair way to introduce our finding.
- **Attacks must come from published research with code and a licence (the author, 20 October 2026).** The Simulation
  testbed (Gotham + OAI 5G) already defines label flipping after Kang et al. 2019 and a noise-disguised free rider, but
  Kang has no code. Repositories that qualify: FoolsGold (RAID 2020, MIT: Sybil label flipping and Sybil backdoors), Severi
  et al. (USENIX Security 2021, MIT: SHAP-guided feature triggers on gradient-boosted trees), Bachl et al. (Big-DAMA 2019,
  GPL-3.0: NIDS backdoors), Bagdasaryan et al. (AISTATS 2020, MIT), Biscotti (TPDS 2021, BSD-2). Tolpegin 2020, Fraboni 2021
  and Shejwalkar 2021 have no licence file. Table and fit in `experiments/fl-bc-ids-attacks/README.md`.
- **Groth16, in short.** A zk-SNARK (Groth, 2016): the statement is an arithmetic circuit (Circom here); a one-off trusted
  setup makes a proving and a verifying key for that circuit (the powers-of-tau file is its universal first phase); the proof
  is three curve elements, a couple of hundred bytes, verified with a few pairings, cheap enough for an Ethereum contract.
  Costs: proving time and memory grow with the circuit; a dishonest setup could pass a false proof. In FL-BC-IDS the circuit is
  the masked sum of quantised anchor vectors against the declared RSU or GLOBAL context: aggregation arithmetic over committed
  inputs, nothing about training. zkPET proves with Halo2 through ezkl (a universal SRS, no per-circuit ceremony).

## Resume here

Point 3 done (one seed; follow-ups listed under it, none run); the author chose (20 October 2026): the repeat of the attack set (done: r2, both runs recorded), the Section VII paragraph (fact skeleton
in `myliteraturereviewpaper/ppml2026/FACTS-SECTION-VII-EXPERIMENT-V82.md`, the author writes), the design revision into the
paper's agenda text (placement in the same skeleton), V82 (`PLAN-V82.md`), CSE-CIC-IDS2018 was then dropped (the author, 20 October 2026: the experiments stay on CICIoV2024). References from
outside the corpus are admitted for the experiment paragraph: the author downloads them and they join the corpus. Point 2
(device-class runs) and free riding are parked by the author's choice. The portal (`bash experiments/portal.sh`) shows every run; the VM starts with
`colima start -p flbcids` or `bash experiments/fl-bc-ids/env/build.sh`.
