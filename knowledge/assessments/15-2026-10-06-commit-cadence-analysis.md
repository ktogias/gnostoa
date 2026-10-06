---
type: Source
title: Commit cadence on #369 and #374 on 2026-10-06, measured, with its root causes and a plan to reduce it
description: The time between subsequent commits on the two pull requests in review, decomposed into the publish flow, the agent's work, stopped attempts and review waits, with the root causes by minutes, four proposals to reduce it and the Work Items that plan them.
status: draft
generated:
  by: anthropic/claude-opus-5-5
  at: "2026-10-06T10:00:00Z"
sources:
  - id: owner-request
    resource: https://github.com/ktogias/gnostoa/issues/377
    title: The owner's request on 2026-10-06 for the analysis, and that every reduction be planned
  - id: pr-a
    resource: https://github.com/ktogias/gnostoa/pull/369
    title: PR A of #368, the trusted-execution owner, the registry and the reuse check
  - id: mutation-owner
    resource: https://github.com/ktogias/gnostoa/pull/374
    title: One owner for targeted mutants
  - id: p1
    resource: https://github.com/ktogias/gnostoa/issues/378
    title: Fix a review finding's whole family in one round
  - id: p3
    resource: https://github.com/ktogias/gnostoa/issues/377
    title: Scope each review round's verification to the change
  - id: p4
    resource: https://github.com/ktogias/gnostoa/issues/370
    title: Run the test suite in parallel processes
  - id: earlier-analysis
    resource: knowledge/assessments/15-2026-10-05-problems-and-solutions-log.md
    title: The problems and solutions of 2026-10-05, E4 verification time
  - id: evidence
    resource: knowledge/assessments/15-2026-10-06-commit-cadence-evidence/index.json
    title: The publish-flow logs this analysis reads, retained
x-project-knowledge:
  id: kit.assessment.15-2026-10-06-commit-cadence-analysis
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governed-by
      target: /decisions/0053-require-lightweight-work-item-micro-retrospection.md
    - kind: references
      target: /assessments/15-2026-10-05-problems-and-solutions-log.md
---

# Commit cadence on #369 and #374 on 2026-10-06

Measured 2026-10-06, read-only. Times are Athens time (UTC+3) unless marked UTC. Durations are minutes. **Estimates are marked as such.**

**Cutoff:** every figure counts events up to 11:26:22 Athens (08:26:22 UTC) on 2026-10-06, when the flow of #369's round 19 started. Later events are not counted, though some of their evidence is retained with this analysis: round 19's publication at 11:45:59, `8a25bbe`, and its flow log.

## Answer in brief

**Mean time between subsequent commits:**

| | All rounds | Since 2026-10-06 00:00 UTC |
|---|---|---|
| #369 | 68.6 min (median 46.5; 17 intervals; range 37.1–189.8) | 66.0 min (median 42.4; 7 intervals) |
| #374 | 42.6 min (median 40.5; 12 intervals; range 27.6–96.8) | 41.2 min (median 42.3; 6 intervals) |
| Both PRs, merged | 38.9 min (median 27.1; 30 intervals) | 33.0 min (median 20.9; 14 intervals) |

The means are pulled up by four long intervals, with three causes:
- **190 min on #369, `533a539` → `09913e4`:** the review request waited 128 minutes on an owner question and on #374 work.
- **159 min on #369, `3b3a79a` → `13fcdf4`:** #374's first rounds, #375 and an owner-requested analysis ran in between.
- **97–101 min, two intervals: #374 `aedb94f` and #369 `eb83ead`:** in-flow mutant failures forced reruns.

**A typical round is about 42 min**: median 41.7, mean 42.8. That is over 24 intervals: the 29 intervals less the four long ones above, and less #369's `d0a7268`. That interval, 104.3 min, has no flow data to decompose, since it predates the flow's timing files.

| Component | Median | Mean | Share of the mean |
|---|---:|---:|---:|
| The publish flow (one successful attempt) | 17.0 | 16.2 | 38% |
| My work: diagnosis, REDs, fix, local tests and local mutants | 14.9 | 14.8 | 35% |
| Waiting for Codex after the request | 5.2 | 6.0 | 14% |
| Stopped flow attempts, and their relaunch | 0.0 | 4.2 | 10% |
| Publish → review request (replies, summary) | 1.1 | 1.6 | 4% |

The shares sum to 101% by rounding. A first version of this table kept #374's 96.8-minute interval, a long one, among the typical rounds. It gave a mean of 44.9 and 6.3 minutes of stopped attempts (Codex on #379).

The fixed cost per round is about 24 minutes: the flow, the review wait and the request. It does not depend on the size of the fix, which in rounds 15–19 of #369 was often a one-line registry pattern.

## Method and data

1. **Commits.** `gh api …/pulls/{369,374}/commits --paginate`, using author dates: the rebase after #375 merged rewrote the committer dates. #369's first five published heads were squashed by that rebase. For them, the owner's `@codex review` request time is the publication proxy, minus 1.5 min: *estimate*, the measured median is 1.1. Every later head is matched to its pre-rebase SHA through the Codex review that names it.
2. **Flows.** Every `timing-*.txt` in the scratchpad and every `*-flow.log` under `/tmp/claude-1000/{tae,mut}`: 85 files, 59 timing files and 26 stdout logs, all retained with this analysis. Stage marks carry epoch seconds.
   - **Runs.** Since 02:00 on 10-06, each run has both its own timing file and a stdout log. So runs are keyed by PR and start second, which merges the two; it also keeps apart two flows that started in the same second. That gives 45 runs that started before the cutoff, 27 on #369 and 18 on #374, and one at it: round 19, retained but not counted.
   - **Other PRs.** 13 of the files are runs of other PRs, #372, #373 and #375. They are retained, but not counted.
   - **Stopped runs.** A run that stopped in pre-flight has only its start mark, so its end is the file's mtime. Every file's mtime is retained in the evidence index.
3. **Reviews.** Issue comments, reviews and review comments, all with `--paginate`:
   - the owner's `@codex review` comments are the request times;
   - Codex reviews, and its "Didn't find any major issues" comments, are the verdicts;
   - root inline comments by bots, and CodeAnt reviews, are the findings.
4. **My work.** From the Codex verdict on head N to the first flow attempt for head N+1. Local whole-table mutant runs are counted from the scratchpad files' mtimes. Their duration is an *estimate*: 6.5 min for #369's table, 5 min for #374's, from the gaps between consecutive runs. Those result files, and their mtimes, are retained with the flow logs.

## Per-interval decomposition

### #369: each interval, ending at the head it produced

| Head | Published (Athens) | Interval | Request delay | Codex wait | My work | Stopped attempts | Flow | Attempts |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| `044c549` | 10-05 15:28 | – | – | – | – | – | – | – |
| `d0a7268` | 10-05 17:12 | 104.3 | no flow data | | | | | |
| `e83d37e` | 10-05 18:23 | 70.7 | 1.5 | 10.6 | 27.2 | 27.6 | 3.8 | 3 |
| `42ea628` | 10-05 19:12 | 48.6 | 1.5 | 12.0 | 8.6 | 14.1 | 12.4 | 2 |
| `e600109` | 10-05 20:07 | 55.8 | 1.5 | 6.9 | 19.2 | 15.2 | 13.0 | 2 |
| `826ca5b` | 10-05 20:45 | 37.4 | 1.5 | 6.8 | 13.2 | 0.0 | 15.9 | 1 |
| `9e4e645` | 10-05 21:29 | 44.1 | 1.8 | 7.0 | 8.6 | 14.1 | 12.6 | 2 |
| `3b3a79a` | 10-05 22:11 | 41.8 | 0.8 | 8.2 | 6.1 | 13.8 | 12.8 | 2 |
| `13fcdf4` | 10-06 00:50 | 159.4 | 2.4 | 6.2 | 129.1 | 3.2 | 18.4 | 2 |
| `9fea556` | 10-06 01:32 | 41.4 | 1.2 | 4.8 | 16.9 | 0.0 | 18.5 | 1 |
| `eb83ead` | 10-06 03:12 | 100.7 | 4.5 | 4.7 | 21.0 | 50.6 | 19.8 | 2 |
| `41a91e7` | 10-06 04:18 | 66.1 | 1.1 | 5.9 | 35.0 | 5.0 | 19.0 | 2 |
| `a487607` | 10-06 05:00 | 41.9 | 2.4 | 5.3 | 14.2 | 0.0 | 20.1 | 1 |
| `4f3878e` | 10-06 05:37 | 37.1 | 0.8 | 8.2 | 11.1 | 0.0 | 16.9 | 1 |
| `6810275` | 10-06 06:24 | 46.5 | 5.0 | 4.7 | 18.2 | 1.3 | 17.2 | 2 |
| `533a539` | 10-06 07:06 | 42.4 | 0.9 | 7.8 | 15.7 | 0.0 | 17.9 | 1 |
| `09913e4` | 10-06 10:16 | 189.8 | 128.3 | 7.0 | 29.9 | 5.9 | 18.6 | 2 |
| `4fa24f2` | 10-06 10:54 | 38.3 | 0.7 | 5.2 | 13.6 | 0.0 | 18.9 | 1 |

### #374: each interval, ending at the head it produced

| Head | Published (Athens) | Interval | Request delay | Codex wait | My work | Stopped attempts | Flow | Attempts |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| `8ad4b4b` | 10-05 22:47 | – | – | – | – | – | – | – |
| `d887443` | 10-05 23:28 | 41.2 | 1.7 | 4.3 | 18.6 | 1.9 | 14.7 | 2 |
| `99bfe52` | 10-05 23:57 | 28.8 | 1.0 | 3.4 | 8.8 | 0.0 | 15.6 | 1 |
| `2c156a` | 10-06 00:28 | 30.4 | 5.3 | 5.0 | 4.2 | 0.0 | 16.0 | 1 |
| `4068c40` | 10-06 01:08 | 39.8 | 0.6 | 4.3 | 11.4 | 6.1 | 17.3 | 2 |
| `d56d583` | 10-06 01:35 | 27.6 | 0.7 | 3.7 | 6.0 | 0.0 | 17.2 | 1 |
| `aedb94f` | 10-06 03:12 | 96.8 | 1.0 | 4.8 | 15.3 | 56.1 | 19.5 | 4 |
| `f177eba` | 10-06 03:58 | 45.6 | 1.3 | 3.7 | 19.1 | 0.0 | 21.4 | 1 |
| `09cbd28` | 10-06 04:41 | 43.8 | 0.8 | 5.7 | 16.9 | 0.0 | 20.3 | 1 |
| `b179ddd` | 10-06 05:17 | 35.5 | 0.8 | 5.6 | 11.9 | 0.0 | 17.3 | 1 |
| `137f79a` | 10-06 05:58 | 41.6 | 3.5 | 4.5 | 17.1 | 0.0 | 16.4 | 1 |
| `830dd22` | 10-06 06:41 | 43.0 | 0.7 | 5.1 | 18.6 | 1.5 | 17.2 | 2 |
| `0fae47c` | 10-06 07:19 | 37.5 | 0.9 | 5.2 | 15.8 | 0.0 | 15.6 | 1 |

The "My work" column includes work on the other PR and on #375, because one agent serves both PRs in turns. It is wall-clock time, not attention. For `e83d37e`, "Stopped attempts" overstates the loss. Its 27.6 minutes include `368a3b`, a verification that passed and that the 4-minute publish run `368a3c` reused. The real loss there is `368a3`'s 13.0 minutes, plus the gap before it. "Stopped attempts" runs from the first attempt's start to the successful attempt's start, so it includes the failed run and the fix that followed.

## Publish flow, by stage (Process A)

Published runs since pre-flight was added, 9 on #369 and 8 on #374:

| Stage | #369 mean (min–max) | #374 mean (min–max) |
|---|---|---|
| Pre-flight: DeepSource-local, whitespace, `security-fast`, anchors | 1.2 (1.0–1.4) | 1.2 (1.0–1.6) |
| Preparation from the exact parent | 4.4 (4.0–4.9) | 4.6 (4.0–5.6) |
| Gates: `policy`, `security-fast`, `smoke` | 1.0 (0.8–1.1) | 1.1 (0.8–1.7) |
| Concurrent stage: `extended` ∥ runtime ∥ mutants | 12.0 (11.0–13.0) | 11.1 (8.7–14.0) |
| — runtime image build and self-check | 7.1 | 7.3 |
| — `extended`: style, the whole suite under coverage, docs build | 11.0 | 10.9 |
| — mutants | 10.8 | 9.7 |
| **Total** | **18.7** (17.1–20.2) | **18.2** (15.7–21.6) |

- **The critical path is `extended` (12 of 17 runs) or the mutants (5 of 17).** Since 09:57 on #369 it has been the mutants: 12.4 and 12.9 min for 151–153 mutants, against `extended` at 8.4 and 8.3. Its table has grown from 114 to 155 mutants, and in-flow mutants from 3–4 min on 10-05 to 9–13 min.
- **Host contention adds about 3 minutes.** `extended` takes a median of 8.3 min (21 runs) when little else runs during the concurrent stage. With half or more of that stage shared, by the other PR's flow or by my local mutant runs, it takes 11.1 min (9 runs). The host has 8 cores, and the concurrent stage alone runs:
  - the whole suite twice, under coverage and in the runtime image;
  - the mutants, three jobs at once.

  My local runs add five more jobs.

## Lost flow time

| Cause | Runs | Flow time lost | When |
|---|---:|---:|---|
| A mutant table failed in-flow: an anchor made stale by preparation's reformatting, or a survivor. The fail-fast rule then stopped every stage. | 6 | 84.6 min | four on 10-05, 18:45–21:44, before S6's tables (`368a4`, `368a5`, `368a7`, `368a8`); #374 `r7c` and #369 `r11`, 02:00 on 10-06 |
| A verification that passed but was redone; the reason is not recorded | 1 | 13.0 min | #369 `368a3`, 17:52 on 10-05 |
| Pre-flight stops: DeepSource-local findings (PYL-W0212, TYP, PTC-W0062) and a whitespace stop | 10 | ~1.3 min of flow, plus 1–5 min each to fix and relaunch | spread out |
| A defect in my own snapshot check: it read `git status`, which lists the staged candidate | 1 | 5.2 min | 09:51 on 10-06 |

No in-flow mutant failure has happened since whole-table local runs became routine, around 02:30 on 10-06: 0 in 15 published flows. The local run costs about 6.5 minutes per round on #369 (*estimate*), and an in-flow failure costs about 16 minutes plus a relaunch, so the practice pays for itself. But every round now runs the mutants twice.

## Root causes, by minutes

1. **The rounds themselves.** #369 has had 18 published heads and #374 13. Codex was clean once on #369 (`6810275`) and once on #374 (`2c156a…`). Each round surfaced one to six new findings, often the next member of one family. On #369, rounds 15–19 each found another unseen form of running Git:
   - `from shutil import which`;
   - an absolute path in quotes;
   - a shell string;
   - no subcommand, as in `git --version`;
   - `if !`;
   - an unquoted absolute path.

   Each new member cost a full round, about 40 minutes.
   - **Root cause:** fixes went instance by instance. When the first member of a family was found, the family itself was not enumerated.
   - **Share:** most of the cadence. With a fixed cost of about 24 minutes per round, every avoided round saves about 40.
2. **Full verification on every round.** The flow takes about 18 minutes whatever changed. A one-line registry pattern gets a fresh preparation, both full suites, the runtime image build and every mutant of the table, including those for unchanged files. That is about 40% of a typical round.
3. **Duplicated and contending work on one 8-core host.** The suite runs twice per flow. The mutants run locally, then again in the flow. The other PR's flow, and my local five-job mutant runs, often overlap a flow's concurrent stage. Together this costs about 3 minutes on `extended` per flow, and about 6.5 minutes of duplicated mutant runs per #369 round (*estimates*).
4. **Gaps between my local checks and the flow's gates.** These are smaller now:
   - the stale-anchor and survivor failures, about 85 minutes, were removed by the tables of #374 and by the local runs;
   - DeepSource-local missed PYL-W1113, which then cost a review finding on #374;
   - my own snapshot-check defect cost one rerun.
5. **External waits:** the owner question, about 128 minutes once, and serving two PRs from one agent. These cannot be reduced by tooling, and they are excluded from the typical round.

## Proposals, with estimated savings

All savings are *estimates*. The first two change no verification and fit Process A as it stands; the last two change it and need the owner's approval.

**P1. Fix a family, not an instance. The agent's practice from #369 round 20; #378 would make it guidance.**
- **The change:** when a finding is one form of a shape, such as a signature that misses one way of running Git, enumerate the family's other members before publishing. Test each against the signature and the production tree, as rounds 17–19 eventually did.
- **Savings:** rounds 17, 18 and 19 of #369 might have been one round: about 75 minutes on #369 alone. In general, one round avoided saves about 40 minutes.
- **Risk:** more work per round, and enumeration finds only the members I think of.

**P2. Use the host better: same verification, less contention. This is #380, awaiting admission.**
- **The change:**
  - never run my local whole-table mutants during a flow's concurrent stage;
  - give a flow's mutants as many jobs as the concurrent stage leaves cores free.
- **Savings:** about 3 minutes per flow, `extended` going from 11.1 to 8.3; perhaps 2–4 minutes of mutants on #369.
- **Risk:** the other PR's next round sometimes waits a few minutes.

**P3. Change what each round verifies, and what runs twice. This changes Process A, so each part needs a Decision; it is #377.**
- **(a) Scope the mutants to the change.** In-flow, run only the mutants whose files the candidate changed or whose tests it touched. Run the whole table on the final round before the merge question, and whenever a test file the table names changes.
  - *Savings:* about 8–10 of #369's 12–13 minutes of mutants. The concurrent stage would then be bounded by `extended` at about 8–11 minutes.
  - *Risk:* a change to shared code or a fixture can weaken a kill elsewhere. The final full run is the backstop.
- **(b) Run only the new or changed mutants locally,** leaving the whole table to the flow.
  - *Savings:* about 5 minutes per #369 round.
  - *Risk:* an old mutant made equivalent by the change is found only in-flow, at a cost of about 18 minutes. That happened twice in 15 rounds; both times the local run caught it.
- **(c) Reuse verified test results across rounds,** keyed by the prepared tree and the suite: run `extended`'s suite only when Python source or tests changed. A round that changes only policy YAML or documentation would then run the policy tests, the reuse check and the docs build, about 2–3 minutes.
  - *Savings:* 8–11 minutes on such rounds.
  - *Risk:* a policy file read by tests in non-obvious ways, such as the registry being read by the reuse-check tests. The test selection must follow data dependencies, not file types.

**P4. Make the suite itself faster. This is #370, admitted on 2026-10-05.**
- **The change:** `extended` and the runtime self-check each run 1,799 tests in one process: 366 s and 283 s on `4fa24f2` with no other load. A parallel runner, sharded by module, could cut each to about 2 minutes on 8 cores.
- **Savings:** about 4–6 minutes per flow, through `extended` and the runtime self-check, and more through the mutants, which each run test modules.
- **Risk:** tests that share temporary paths, ports or global state would need isolating first. This changes CI tooling, so it needs its own Work Item and Decision.

**Smaller items:**
- Add the DeepSource rules that have already cost a round to the agent's local mirror. W1113 was added on 2026-10-06.
- Review the publish flow's own changes on both paths before the first run, as was done after the snapshot-check defect.

**A rough total.** P2 with P3(a) and P3(b) together would cut a typical #369 round from about 42 to about 28–32 minutes. P1, by avoiding rounds, matters more than any per-round saving: each round avoided saves about 40 minutes.

## Plan, as recorded on 2026-10-06

The owner asked on 2026-10-06 that every way to reduce be planned for implementation soon.

| Proposal | Work Item | State | Proposed order |
|---|---|---|---|
| P1: fix a finding's whole family in one round | #378 | The agent fixes each review finding's family from #369 round 20 on. This falls under the owner's standing instruction to fix every review finding, and it changes no repository source. #378 adds it to the runbook, after admission. | Now, as practice |
| P2: one flow's concurrent stage at a time, more mutant jobs when the host is free | #380 | Awaiting admission. It was applied in the agent's local publish flow on 2026-10-06 before admission, for one round, #369's round 20. Codex on #379 found that this skipped the admission step, and it was reverted the same hour. | After admission |
| P3(a)–(c): scope each round's verification to the change, the whole on the final round | #377 | Planned. It extends the mutation owner of #374, and changes Process A, so each part needs a Decision. | After #374 lands |
| P4: a parallel test runner | #370 | Admitted on 2026-10-05, after #368's PR B. The proposal on #370 is to take it after #369 and #374, alongside #377. | The owner's choice |

**To re-measure when evaluating:**
- the mean and median time between commits, against 38.9 and 27.1 min for both PRs here;
- a typical round, against about 42 min;
- the flow's concurrent stage, against 11–12 min;
- the number of rounds per PR, and how many findings were members of a family already fixed.

## Data gaps

- **My attention.** There is no record of my active time, so "My work" is wall-clock time and includes work on the other PR and on #375.
- **Local mutant runs.** Their start times were not recorded, only the end mtimes; their durations are estimates.
- **CodeAnt's nitpicks.** They arrive by editing one sticky comment, so only the last update time survives. Only CodeAnt's inline findings and reviews are timed here.
- **#369's first five heads.** Their publication times are request time minus 1.5 minutes.
- **Lost runs.** Why a run failed was read from its `V-*` result files. `368a3` passed every stage and was redone anyway; its reason is not recorded.
- **Early timing files.** They carry no PUBLISHED line, so publication is inferred from a `publish end` mark.
- **Round 19 of #369, and everything after the cutoff.** Round 19's flow started at the cutoff and published `8a25bbe` at 11:45:59. Its retained log is evidence, but it is not counted, so the counts, means, the stage sample and the "0 in 15" claim all stop at the cutoff (Codex on #379).
