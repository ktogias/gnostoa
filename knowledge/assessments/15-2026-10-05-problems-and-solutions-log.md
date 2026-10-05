---
type: Source
title: Problems and solutions of 2026-10-05, recorded for later reflection and evaluation
description: A source-bound log of every problem met on 2026-10-05 while delivering #368 and its follow-ups. For each it records the evidence and measured impact, the root cause, the solution and its status, and the lessons. It closes with the open owner decisions and the measures to re-take when evaluating later.
status: draft
generated:
  by: anthropic/claude-opus-5-5
  at: "2026-10-05T20:05:00Z"
sources:
  - id: owner-request
    resource: https://github.com/ktogias/gnostoa/issues/373
    title: Owner request on 2026-10-05 for a full record and history of the problems and their solutions
  - id: trusted-execution
    resource: https://github.com/ktogias/gnostoa/issues/368
    title: One owner for trusted authority execution (incident, RCA and plan)
  - id: pr-a
    resource: https://github.com/ktogias/gnostoa/pull/369
    title: PR A of #368, the trusted-execution owner, the registry and the reuse check
  - id: verification-time
    resource: https://github.com/ktogias/gnostoa/issues/15#issuecomment-5997005569
    title: The measured verification-time analysis and the owner's admission of #370 and #371
  - id: c1
    resource: https://github.com/ktogias/gnostoa/pull/372
    title: Parallel CI suites behind the regression gate (merged as 4618e1b)
  - id: preflight
    resource: https://github.com/ktogias/gnostoa/issues/373
    title: Cheap static checks read only after candidate preparation (incident, RCA and steps)
  - id: mutation-owner
    resource: https://github.com/ktogias/gnostoa/pull/374
    title: One owner for targeted mutants, and the verification order in the runbook
x-project-knowledge:
  id: kit.assessment.15-2026-10-05-problems-and-solutions-log
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: references
      target: /assessments/365-duplication-inventory-2026-10-05.md
    - kind: references
      target: /assessments/15-review-pipeline-abstraction-recurrence-rca.md
    - kind: references
      target: /decisions/0103-run-the-regression-and-smoke-suites-beside-extended-behind-the-regression-gate.md
---

# Problems and solutions of 2026-10-05

## Purpose and claim boundary

The owner asked for a full record and history of the problems met and their
solutions, so that they can be reflected on and evaluated later. Each entry links to
the provider records that hold its detail. Numbers are measured unless marked as an
estimate. Where a solution is still open, the status says so. Nothing here admits
work.

## Index

| # | Problem | Measured impact | Root cause | Solution | Status |
|---|---|---|---|---|---|
| E1 | "Run code from the authority commit" implemented 9 times, with no owner; #364 copied it again | 8 review rounds hardened only #364's copy | No owner, and prevention was prose an agent had to read | `tools/trusted_execution.py`, a registry and `knowledge reuse-check` (#369) | #369 in review (round 9) |
| E2 | Long review tail on #369 | 8 rounds; the findings include real security defects | A new security boundary, and per-line regex signatures | Every owner finding fixed with a RED first; scope set for the check (E3) | ongoing |
| E3 | Codex kept finding new bypasses of the reuse check's regex | 5 consecutive rounds (literal, variable, multi-line, alias, import alias) | Each line is matched alone, against a changing shape | Owner decision: the check guards *accidental* re-implementation only | decided, recorded |
| E4 | Slow verification | ~46 min per review round; the same 1708 tests run 12 times | Repetition, one CPU core and serial CI jobs | A (agent order), C1 (#372), B (#370), C2 (#371) | A and C1 done; B and C2 open |
| E5 | Cheap checks read only after preparation | 5 refused runs, ≈ 66 min | The flow was ordered by tool, not by how cheaply a check finds a failure | Pre-flight and fail-fast (#373 S1, S2, S4, S5) | done; S3 open |
| E6 | ~20 hand-maintained mutation scripts | ~526 mutants; literal anchors broke on `ruff --fix` | No owner; anchors coupled to text | One owner, AST anchors, data tables and a fast-profile check (#374) | PR #374 in review |
| E7 | Other duplicated responsibilities | 8 families measured | Same class as E1 and E6 | Prioritized proposals | recorded; not admitted |
| E8 | Agent process slips | about 30 min and one interrupted publication | Individual mistakes, each listed with its fix | Fixed in the agent's tooling and memory | done |
| E9 | Mutant kills credited without a baseline | 9 reported kills that were not evidence, for #371's gate, twice | Runners never ran the tests unmutated, and their copies dropped `.git` | A baseline before any kill counts, and a copy that keeps `.git` (#374 round 2) | PR #374 in review |

## E1. Authority execution was copied (#368)

- **Evidence:** on `c54b18d` these existed with no owner:
  - six Python Git-environment builders;
  - two identical tree materializers;
  - three executable-lookup policies;
  - two shell scrub lists.

  #364 added two more by copying the preparation helper. Its eight review rounds
  hardened only that copy, and several implementations kept defects. For example,
  the subject repository's own filters ran during `capsule`'s `git archive`. The
  incident and its root-cause analysis are on #368.
- **Root cause:** no single owner existed, and the earlier prevention was prose that
  an agent had to remember to read. This was the class's fourth occurrence.
- **Solution:** Decision 0102, delivered in #369:
  - one owner, `tools/trusted_execution.py`;
  - a registry, `policy/owned-responsibilities.yaml`;
  - a deterministic reuse check, run as a unittest in the `fast`, `regression` and
    `extended` profiles, the git hooks and CI;
  - routing hooks in `AGENTS.md`, the runbook and a guardrail.

  PR B (the preparation authority), PR C (#364 as a caller) and PR D (the workflows)
  follow.
- **Status:** #369 in review, with round 9 being prepared.

## E2. The review tail on #369

- **Evidence:** eight published rounds, each with a summary comment on #369.

| Round | Comment | Findings that needed fixes (excluding nitpicks) | Notable real defects |
|---|---|---|---|
| 1 | — | 12 | the subject's clean filter ran during `capsule` tree verification |
| 2 | 5996269264 | 12 | a seventh Git-environment builder in `tasks/` |
| 3 | 5997547452 | 7, plus SonarCloud S6549 and S3776 | `cat-file --filters` ran a smudge filter; abbreviated options; `rev-list --format=%G?` ran `gpg.program` |
| 4 | 5998396996 | 5, plus Codacy | a name with a slash bypassed the trusted lookup |
| 5 | 5999315388 | 2, including **P1** | a lazy fetch in a partial clone ran `remote.origin.uploadpack` |
| 6 | 5999930736 | 4, rebuilt on main after #372 | orientation's `git` came from the caller's `PATH` |
| 7 | 6000628595 | 4 | Git launched through `env` |
| 8 | 6001327046 | 5 | a shadow `tools` package could stand in for the owner |

- **Assessment:** the external reviewers found genuine security defects at a
  boundary that is meant to be trusted, through round 8. Every owner finding was
  reproduced as a failing test before its fix. The cost is about 30–60 minutes per
  round.
- **Status:** ongoing. Convergence means Codex is clean, or reports only
  obfuscation-class findings declined under E3; no inline finding remains; and every
  signal is green.

## E3. The reuse check's scope

- **Evidence:** from round 3 onward, each Codex round produced a more contrived way
  past the per-line signatures for running Git.
- **Root cause:** a signature matches one line, while the code it should catch can
  take any shape.
- **Solution:** an owner decision on 2026-10-05. The check guards against an agent
  re-implementing an owner *by accident*, and deliberate obfuscation is outside what
  a source signature can see.
  - Obfuscation-only findings are declined, citing the bound.
  - Accidental shapes are fixed.
  - Every finding on the owner itself is fixed.

  The bound is recorded in Decision 0102, rule 4, and in the registry's header. An
  AST-aware signature is captured on #365 (comment 5999904522) and is admitted only
  on a real accidental miss.
- **Status:** decided.

## E4. Verification time

- **Evidence:** measured on round 2 of #369. One review round took about 46 minutes
  before any reviewer started: about 28 local, about 5 for preparation and about 14
  in CI. The same 1708 tests ran 12 times on one tree, each run in one serial process
  on an 8-core host.
- **Root cause:** repetition across stages, serial test execution, and a serial CI
  job chain, `extended`, then `regression`, then `smoke`, kept serial by the gate
  semantics.
- **Solutions, in the order the owner admitted** (#15 comment 5997005569):
  - **A, the agent's verification order:** applied. Local verification plus
    preparation fell from about 33 to about 13 minutes, measured per round.
  - **C1, parallel CI suites behind the same `regression` gate:** merged as
    `4618e1b` (#372). The verification workflow fell from 13 min 43 s to 6 min 46 s
    on the PR, and to about 7 min on main.
  - **B, parallel test processes (#370):** open. It follows #368's PR B, because it
    changes the preparation authority. A prototype ran the suite in 71 s instead of
    242 s.
  - **C2, fewer duplicate CI runs (#371):** open, last.
- **Status:** a review round now takes about 20 minutes (measured), against about 46.
  With B and C1 it is estimated at about 10.

## E5. Cheap checks read only after preparation (#373)

- **Evidence:** five publication runs, `368a3`, `368a4`, `368a5`, `368a7` and
  `368a8`, were refused after their whole ~13-minute pipeline. That is about 66
  minutes. The causes were stale mutant anchors, a surviving mutant and
  DeepSource-local findings: checks that cost 0.49 s and about 20 s.
- **Root cause:** the agent's flow, designed for A, applied "cheapest first" to the
  suites but treated the mutants and DeepSource-local as single expensive units. It
  read their results only at the end, and a failing stage did not stop the others.
- **Solution:**
  - **S1:** check the mutant anchors before preparing.
  - **S2:** run DeepSource-local before preparing.
  - **S4:** the first failing concurrent stage stops the rest, tested synthetically.
  - **S5:** made automatic by S1 and S2.
  - **S7:** the order is written into the runbook (#374).
  - **S3, open:** a local mirror of the Semgrep rules Codacy enforces. Codacy flagged
    critical issues after a push twice.
- **First evidence it works:** #374's first run stopped at the pre-flight after about
  20 seconds, on three findings, instead of after about 13 minutes.

## E6. Twenty hand-maintained mutation scripts (#373, S6)

- **Evidence:** about 20 scripts in the agent's scratchpad, from 2026-10-03 to
  2026-10-05. Together they held about 526 mutants. Each had its own runner, and only
  one had parallel workers or an anchor check. The owner called it unacceptable and
  made the fix a priority.
- **Root cause:** there was no owner, and the anchors were literal text. This is the
  same duplication class as E1, in the agent's own tooling.
- **Solution:** Decision 0104, delivered in #374:
  - one owner, `tools/mutation.py`, exposed as `knowledge mutants`;
  - Python anchors located by AST, and other anchors by token sequence. A 40-column
    reflow changed 579 lines and broke no anchor;
  - tables kept as data under `tests/mutants/`;
  - `tests/test_mutant_tables.py`, which fails in the `fast` profile when an anchor
    no longer applies.

  #369's 103 mutants move into a table when #369 rebases. The scratch scripts are
  then deleted.
- **Status:** PR #374 is in review. Round 1 reported all 21 of its mutants killed. Nine
  of those kills were not evidence (E9). Round 2 adds a baseline and kills its mutants
  for their own reasons.

## E7. Other duplicated responsibilities

See the [duplication inventory](365-duplication-inventory-2026-10-05.md). It found
eight families. The most urgent is strict JSON parsing, a security boundary with five
or six identical copies. The others are the HTTP and analyzer clients, canonical JSON
and digests, schema validation, bounded process execution, policy loading, the CI
smoke harness, the experiment helpers and test fixtures. None is admitted yet.

## E8. Agent process slips, each with its fix

| Slip | Cost | Fix |
|---|---|---|
| Editing a bash script while it ran broke a publication at its last step | one run; no publication was made, and the receipt was released | the agent always runs a copy of the script (recorded in its memory) |
| `pkill -f <pattern>` matched its own shell's command line, twice | an interrupted command | match with an anchored pattern (`^find …`), or by container mount |
| Full-clone snapshots filled the RAM-backed `/tmp` (701 MB) | host memory | deleted (to 92 MB); the flow now deletes its snapshot when it ends |
| A RED passed for the wrong reason: `python -c` put the checkout's directory first on `sys.path` | none; caught by reading the result | voided, recorded, and rerun from `/` |
| `pylint duplicate-code` reported nothing because it could not be installed under `--network none` | none; caught | a zero result is not a clean result; rerun with the network |

## E9. Mutant kills credited without a baseline (#374, round 2)

- **Evidence:** on 2026-10-05, Codex's P1 on #374's first version said a test failure
  was credited to a mutant without first running the tests unmutated. Round 2 added
  that baseline. On its first run it failed on the verification-workflow table itself:
  - two `tests.test_tools` tests read Git metadata: `git ls-files`, and the
    tracked-file scope;
  - a copy without `.git` fails them;
  - so each of the table's nine mutants was "killed" by those two errors, not by its
    own change.

  The same nine mutants had been reported killed for #371 (C1, Decision 0103) by the
  scratch script `mutate371.py`, which copied the tree the same way. That evidence was
  also void. The records PR's flow reported it a third time.
- **Root cause:**
  - no runner, the scratch scripts or the first owner, ran the tests unmutated, so a
    failure of any cause counted as a kill;
  - every copy dropped `.git` to stay light, so it was not the environment the tests
    are written for.

  Each defect hid the other: the copy broke two tests, and the missing baseline turned
  that breakage into kills.
- **Blast radius, measured:** each scratch-era test set was run unmutated in a copy
  without `.git`, on its current subject:
  - only #371's set failed;
  - #356 and the review-admission sets passed;
  - #362/#364's credential sets passed;
  - `github_rest` passed;
  - #368's set passed.

  Those other kills stand. The measure used the current subjects, not each run's exact
  historical subject.
- **Solution (#374 round 2, Decision 0104):**
  - the table's tests run unmutated first, and when they fail every mutant is `NOT RUN`;
  - a copy keeps the repository's own `.git` directory, but never a `.git` file, which
    points at shared metadata.

  Each change has a test that failed first. With the faithful copy, all nine #371
  mutants are killed for their own reasons, so the merged gate is guarded after all.
- **Status:** PR #374 round 2.

## Open owner decisions

- Nine saved CodeAnt review instructions: seven from #364, and two from #369 (the
  reuse check's scope, and honoring `export-ignore` during materialization). Each
  changes how CodeAnt reviews the repository.
- The admission of the E7 families, in the proposed order.
- #370 (B) and #371 (C2), in the agreed order.
- #369's merge, once it converges.

## Cross-cutting lessons

1. **Measure before proposing.** The verification-time figures, the refused-run
   costs and the duplication counts were all measured.
2. **Cheapest check first,** by the cost of finding a failure, not by tool (E5).
3. **Remove the shape, not the instance.** When a hardening round yields the same
   class again, change what is matched or owned: E3's acquisition-based signature,
   E6's AST anchors and E1's single owner.
4. **One owner per responsibility,** with a registry entry, signatures and counted
   debt. The agent's own tooling is no exception (E6).
5. **A zero result, a green check or a passing RED proves nothing until its cause is
   read** (E8). A kill is the same: a test failure is evidence about a mutant only when
   the same tests pass without it (E9).

## How to evaluate this later

Re-measure and compare:
- review-round wall time: about 46 min on 2026-10-05, then about 20 min;
- CI critical path: 13 min 43 s, then 6 min 46 s;
- refused publication runs per round, and their cause;
- the duplication families' copy counts, with the inventory's four detectors;
- the reuse check's debt per owner, which can only shrink;
- the number of review rounds per security-boundary PR, and the share of rounds that
  found a real defect;
- the mutant runs with a failing baseline, which should be reported `NOT RUN` and never
  counted as kills.
