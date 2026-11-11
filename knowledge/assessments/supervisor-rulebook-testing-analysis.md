---
type: Source
title: "Supervisor rulebook, testing and analysis themes"
description: "Themes 7 and 8 of the supervisor agent's handoff-safe rulebook (27 rules), copied from the published #325 records with three review corrections, and loaded by theme."
status: draft
generated:
  by: anthropic/claude-opus-5-5
  at: "2026-11-11T20:27:00Z"
sources:
  - id: rulebook-part-1
    resource: https://github.com/ktogias/gnostoa/issues/325#issuecomment-6805345513
    title: "Supervisor rulebook (handoff-safe), part 1 of 2"
  - id: rulebook-part-2
    resource: https://github.com/ktogias/gnostoa/issues/325#issuecomment-6805346585
    title: "Supervisor rulebook (handoff-safe), part 2 of 2"
  - id: rulebook-addendum-1
    resource: https://github.com/ktogias/gnostoa/issues/325#issuecomment-6805360817
    title: "Supervisor rulebook, addendum 1 (R-GATE-05)"
  - id: rulebook-addendum-2
    resource: https://github.com/ktogias/gnostoa/issues/325#issuecomment-6805985258
    title: "Supervisor rulebook, addendum 2 (R-EVD-11)"
  - id: owner-decision
    resource: https://github.com/ktogias/gnostoa/issues/325#issuecomment-6806047559
    title: "Owner decision (relayed) of 2026-11-11 on the rulebook's thematic files"
x-project-knowledge:
  id: kit.assessment.supervisor-rulebook-testing-analysis
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governed-by
      target: /decisions/0004-self-host-policy-guidance-and-knowledge.md
---

# Supervisor rulebook: testing and analysis

Themes 7 and 8 of the supervisor rulebook: 27 rules, copied unchanged from the published records [#325 6805345513](https://github.com/ktogias/gnostoa/issues/325#issuecomment-6805345513) and [#325 6805346585](https://github.com/ktogias/gnostoa/issues/325#issuecomment-6805346585), except three rules corrected in review (R-TST-06, R-ANL-05 and R-ANL-08; see the index's [review corrections](supervisor-rulebook-index.md#review-corrections)). Each theme keeps its published number and each rule its id. Start at the [index](supervisor-rulebook-index.md) for the conventions, the other themes and the manifest of source notes.

Owner directions remain authoritative in their linked GitHub records; where a rule here differs from a linked record, the record wins.

## 7. Tests and mutation

### R-TST-01 (active): A RED counts only if it fails with the defect's own symptom.
- **Why:** three of five first REDs on #364 were wrong: one passed before the fix, one failed on an already fail-closed value, one expected the wrong real-system behaviour.
- **How to apply:** read the failure message, not just "FAILED". Void and rewrite a wrong RED, and say so in the RED evidence. Check expectations against the real external system first.
- **Origin:** 2026-10-05; #364. Memory: red-must-fail-for-the-defect.

### R-TST-02 (active): Run pre-change evidence as its own command before any production edit, and keep its full output.
- **Why:** AGENTS.md requires pre-change evidence against the exact prior subject, and reviewers can check only retained artifacts.
- **How to apply:** save the full output to disk. Print HEAD, the tree and `git status` in the same command. Name the tree actually used. Keep per-mutant lines.
- **Origin:** 2026-10-14 to 2026-10-20; #389, #407, #422, #444. Memory: keep-pre-change-evidence-inspectable.

### R-TST-03 (active): Assert the intended value, not the absence of a setting.
- **Why:** an absence assertion locked in a bug and guarded against its own correction (#327).
- **How to apply:** assert the exact intended expression. When a reviewer's fix contradicts an assertion, suspect the assertion first.
- **Origin:** #327. Memory: a-test-can-pin-a-defect.

### R-TST-04 (active): Fixtures must refuse what the real thing refuses; exercise the live endpoint once.
- **Why:** a stub that answers anything cannot show the right request was made (five rounds on #330). A stubbed provider hides its real field semantics (#327).
- **How to apply:** serve only the exact expected URLs and refuse the rest. Charge time like the real transport. Assert the questions asked. Keep the stub for CI, but check every field read against the real endpoint once, and record the verified provider properties.
- **Origin:** 2026-10-09 to 2026-10-23; #327, #330, #389, #451. Memory: a-fixture-that-answers-everything, stub-hides-provider-contract-defects.

### R-TST-05 (active): Run the suites offline when an implementation changes transport.
- **Why:** tests that stubbed a tool on PATH silently hit the live provider once the step became Python (#353).
- **How to apply:** run the full `ci/verify` profiles with `--network none`. Stub at the shared client's entry point or at a port, not at a tool on PATH.
- **Origin:** #353. Memory: run-suites-offline.

### R-TST-06 (active): A mutant kill is evidence only against a passing unmutated baseline in the same copy.
- **Why:** copies without `.git` broke the tests, and the missing baseline turned the breakage into nine fake kills (#371).
- **How to apply:** run mutants through a runner that runs the baseline first and reports NOT RUN on a failing one: today the qualified parallel runner (R-TST-07), because `knowledge mutants` (#374) is not on `main` yet. Keep the repository's `.git` directory in copies. Read each kill's failure line.
- **Origin:** 2026-10-05; #368, #371, #374. Memory: a-kill-needs-a-baseline.

### R-TST-07 (active): Use the qualified parallel mutant runner until `knowledge mutants` replaces it.
- **Why:** the incident-scoped runner (#425, route 3) qualified at 99 of 99 kills, the same as serial, in a fraction of the time. Contention, not CPU, bounds it.
- **How to apply:** run kill-checks only through it, never in per-slice serial loops. Freeze a read-only clone of the exact commit. Use four or five jobs. Refuse duplicate mutant ids and anchor counts other than one. Retire it once #374 is integrated.
- **Origin:** 2026-10-12 to 2026-11-04; #374, #380, #451; #425 6126976698, 6127667085. Memory: incident-425-runner.

### R-TST-08 (active): When narrowing an observer or filter, aim a mutant at what the narrowing excludes.
- **Why:** a kill-check aimed inside the kept region missed a weakening that three reviewers found (#406).
- **How to apply:** run at least one mutant whose effect falls only in the excluded region, on the parent and on the change. Pin each clause of the new rule with a mutant.
- **Origin:** 2026-10-08; #406. Memory: kill-check-the-excluded-region.

### R-TST-09 (active): After adding a guard in front of an existing one, rerun the full kill-check.
- **Why:** new checks made older refusal tests pass vacuously (#480).
- **How to apply:** build each refusal case to pass every earlier check. Drop a guard that became unreachable, or name its mutant equivalent with the argument.
- **Origin:** 2026-11-04; #480. Memory: a-new-guard-masks-older-tests.

### R-TST-10 (active): Before calling a surviving mutant a test gap, check that its statement is reachable and observable.
- **Why:** an unreachable raise was called a gap, and an Owner admission inherited the wrong count (#389 6578737523).
- **How to apply:** trace earlier refusals, normalizers and type guards. Name every equivalent mutant, with its proof, in the design record.
- **Origin:** 2026-11-02; #389 6578737523. Memory: check-a-survivor-is-reachable.

### R-TST-11 (active): After a refactor, re-anchor a mutant to the same behavioural change.
- **Why:** a weaker re-anchor survived (#369).
- **How to apply:** state the behaviour each stale mutant broke, anchor the new one to break the same behaviour, and run those mutants by name first.
- **Origin:** 2026-10-07; #369. Memory: reanchor-keeps-the-mutation.

### R-TST-12 (active): A differential's "intended" class must name its direction and cover the wrapping forms.
- **Why:** a broad class explained a regression as readily as the intended change (#470).
- **How to apply:** state whether each class explains only gains or only named losses, and make the classifier check it. Add corpus templates for the wrapping forms. Show that the differential flags the old regression first.
- **Origin:** 2026-10-30; #470. Memory: a-differential-class-must-name-its-direction.

### R-TST-13 (active): Run a narrowing of a shared predicate through Gnostoa's own layouts before calling it deliverable.
- **Why:** an approved narrowing refused Gnostoa's own preparation workspace (#436).
- **How to apply:** search for the layouts Gnostoa creates (gitdir files, worktrees, separate git directories, bare repositories). Run the exact-parent preparation with `security-fast` and `fast`. Measure Git's semantics with real Git.
- **Origin:** 2026-10-17; #436 6241891760. Memory: measure-a-narrowing-against-own-layouts.

### R-TST-14 (active): Replay each workflow's own invocation of every touched test file.
- **Why:** a workflow ran a test file as a bare script with a foreign PYTHONPATH, which broke an import the repository-wide round never exercised (#477).
- **How to apply:** search `.github/workflows/` for each touched test file, and replay the exact step (working directory, layout, PYTHONPATH, script form). Such files import nothing from `tests`.
- **Origin:** 2026-11-02; #477. Memory: replay-each-workflows-own-test-invocation.

### R-TST-15 (active): Never make a `test*` method static.
- **Why:** a static test method still runs under discovery but cannot be loaded by its id. The Owner requires test identities to be preserved (6598073316).
- **How to apply:** for no-self-use findings, convert only helpers. After changing method kinds, load each test id by name on the base and the head.
- **Origin:** 2026-11-03; #478 6598073316. Memory: never-make-a-test-method-static.

### R-TST-16 (active): Register a file-path module in `sys.modules` before `exec_module`.
- **Why:** without registration, the module cannot define a dataclass under postponed annotations (#389).
- **How to apply:** follow importlib's recipe. When a frozen harness needs this fix, change only that line in a copy, and prove it byte-neutral on the parent first.
- **Origin:** 2026-11-02; #389. Memory: register-before-exec-module.

### R-TST-17 (active): Search saved round logs before calling a failure a flake or blaming the change.
- **Why:** a deadline test failed in 4 of 99 runs, 2 of them before the change (#389).
- **How to apply:** report the rate and the earliest subject without the change. Do not fix it outside your scope. Rerun for a clean pass on the exact commit.
- **Origin:** 2026-10-25 to 2026-10-27; #389 6431654478. Memory: scan-saved-rounds-before-attributing-a-flake.

## 8. Analyzers and merge-admission evidence

### R-ANL-01 (active): Read an analyzer's rule id and coverage from the authenticated readback, dispatched on Actions for the exact head.
- **Why:** check annotations show messages, not rule ids. A guessed rule id produced two useless suppressions and a wrong claim to the Owner (#330).
- **How to apply:** never infer a rule id from prose, and never read a local AUTH_UNAVAILABLE as clean. Confirm a suppression by dispatching again for the new head.
- **Origin:** 2026-10-07; #330, #384, #388. Memory: use-the-authenticated-analyzer-readback.

### R-ANL-02 (active): M17 counts every acquired analyzer finding with no waiver; measure that debt before publishing.
- **Why:** a full analyzer run lists issues across the touched files and the modules they import, so a critical PR inherits that debt (#477).
- **How to apply:** read a readback of a similar head first. Plan the touched-file debt into scope, or raise the route first. Never imply a declined finding will pass admission. Reproduce type rules locally with strict mypy flags.
- **Origin:** 2026-10-31 to 2026-11-11; #477, #478, #481, #490. Memory: m17-counts-provider-full-runs.

### R-ANL-03 (active): Judge only a COMPLETE merge-admission verdict produced after the head's verification suite has finished.
- **Why:** early verdicts are INCOMPLETE (M2-M8, M17) while the suite runs, and hide late analyzer findings (#480, #484).
- **How to apply:** read the verdict artifact's criteria and completeness, not the title. Skip artifacts that hold only a pending file. Never read "0 findings" from an INCOMPLETE verdict.
- **Origin:** 2026-11-05 to 2026-11-11; #396, #480, #484, #487. Memory: early-m2-m8-incomplete-is-suite-timing, read-the-complete-verdict-before-the-packet.

### R-ANL-04 (active): Name a gate's cause from the policy declaration and the latest check on the head.
- **Why:** a false M2-M8 "cycle" was claimed from a check made before the readback, and misrouted an Owner decision (#479, Owner 6614620697).
- **How to apply:** read the class's `applies_to` and required claims in `policy/assurance-evidence.yaml`, and name the failing required claim. Keep M2-M8 completeness apart from M17's finding count.
- **Origin:** 2026-11-03; #479 6614620697. Memory: gate-cause-from-the-declaration.

### R-ANL-05 (active): Keep every file's patch small enough that the provider's comparison returns it.
- **Why:** a file whose patch the comparison leaves out makes M13 (suppressions) PARTIAL, which fails, even with zero markers. The collector's own cap was 65,536 bytes (#441) and has been 4 MiB since #396; GitHub's comparison returned a patch of 88,723 bytes and left out one of 106,333 bytes ([#396 6753827825](https://github.com/ktogias/gnostoa/pull/396#issuecomment-6753827825)).
- **How to apply:** measure each file's patch bytes in the PR files API before sealing, and keep each under 80,000 bytes, the pre-push gate of #396. Split large test additions, within the admitted paths.
- **Origin:** 2026-10-20 to 2026-11-09; #396, #441. Memory: patch-cap-makes-m13-partial.

### R-ANL-06 (active): Before every push, measure what the gates will count: mypy, the project inventory and Sonar cognitive complexity.
- **Why:** a pushed round failed a typing step the fast profile skips (#417). A slice added nine inventory findings no reviewer saw (#461). A function over 15 in Sonar's cognitive complexity denies the merge, though no local tool measures it (#485). End-of-file probes miss changed-function families (PAO 6547903296).
- **How to apply:**
  - Run `mypy tools ci` in the development image on the prepared tree.
  - Compare the per-family inventory counts (SLF001, inventory mypy, complexity over 15) with main's.
  - Score each new or grown function with a Sonar-faithful cognitive scorer, and compare with main's score.
  - For coupling probes, put a no-op inside every function the patch will edit, plus one at the end of the file.
- **Origin:** 2026-10-11 to 2026-11-06; #417, #461, #485; #389 6547903296. Memory: run-mypy-before-push, measure-a-pr-against-the-project-inventory, measure-sonar-cognitive-complexity-before-push, probe-inside-every-touched-function.

### R-ANL-07 (active): Learn an analyzer rule's real trigger before shaping a fix.
- **Why:** fixes kept tripping the same or another rule. B105 matches secret-like target names and dict keys (#481). S3415 treats a name assigned once as a literal (#490). S607/B607 count syntax, not resolution (#389). No form of argv[0] clears every analyzer and platform (#478).
- **How to apply:**
  - Check every analyzer's rules on the new shape, and prefer the codebase's existing constant shapes.
  - For S3415, compare against call or attribute results, never a literal-derived name.
  - Keep the behaviour-preserving, portable executable form, and report the residual through the existing provider decision. Never trade behaviour for a count.
  - Run the full suite before calling an ownership choice settled.
- **Origin:** 2026-11-03 to 2026-11-11; #478, #481, #483, #490; #389 6598155432. Memory: b105-matches-target-names, sonar-s3415-follows-assignment, measure-resolution-not-syntax, executable-path-analyzer-trilemma.

### R-ANL-08 (active): Read the producer's exact invocation before offering a suppression or a config change.
- **Why:** the protected producer runs Ruff with the option that ignores inline suppression comments, so an offered "justified suppression" could never clear a finding (#389; SAS 6425280557).
- **How to apply:** read the producer's command line and profile in protected source. Only an option measured under the unchanged producer is an exit option.
- **Origin:** 2026-10-26 to 2026-10-27; #389 6424996482. Memory: check-the-producer-before-offering-a-suppression.

### R-ANL-09 (active): A provider's retirement must reach every reader, runbooks and pre-merge procedures included.
- **Why:** retiring an analyzer from the evidence (Decision 0130) left the runbook requiring every status green (#481).
- **How to apply:** search runbooks, AGENTS.md and session scripts for "status", "check run", "green" and the provider's name. Make each reader exclude the retired provider, and pin that with a test.
- **Origin:** 2026-11-04; #481. Memory: a-retirement-must-reach-the-procedure.

### R-ANL-10 (historical): DeepSource's full verdict could be read from its public run page, and its configuration analysed `tests/` as production code.
- **Why:** kept for reference. DeepSource has since been retired from the merge evidence (R-ANL-09).
- **How to apply:** to read an old run, decode the page's embedded payload for per-code counts. The run diffed against the PR's base branch head.
- **Origin:** 2026-10-01 to 2026-10-09; #330, #353, #364, #410. Memory: reading-deepsource-locally.
