---
type: Source
title: "Supervisor rulebook, index and manifest"
description: "Entry point to the supervisor agent's handoff-safe rulebook, split by theme into four files, with the rulebook's conventions and the manifest of each rule's source memory notes."
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
  id: kit.assessment.supervisor-rulebook-index
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governed-by
      target: /decisions/0004-self-host-policy-guidance-and-knowledge.md
    - kind: contains
      target: /assessments/supervisor-rulebook-governance.md
    - kind: contains
      target: /assessments/supervisor-rulebook-evidence-gates.md
    - kind: contains
      target: /assessments/supervisor-rulebook-testing-analysis.md
    - kind: contains
      target: /assessments/supervisor-rulebook-runtime-architecture.md
---

# Supervisor rulebook: index and manifest

This is the handoff-safe rulebook of the supervisor agent that runs Gnostoa's agent pilot. It records the operating rules the supervisor learned, so that a new session, runtime or provider does not lose them. It is split by theme so that an agent loads only the theme its task needs. The rule text is copied unchanged from the published records [#325 6805345513](https://github.com/ktogias/gnostoa/issues/325#issuecomment-6805345513), [#325 6805346585](https://github.com/ktogias/gnostoa/issues/325#issuecomment-6805346585), [#325 6805360817](https://github.com/ktogias/gnostoa/issues/325#issuecomment-6805360817) and [#325 6805985258](https://github.com/ktogias/gnostoa/issues/325#issuecomment-6805985258), except ten rules corrected in review (see [Review corrections](#review-corrections)). The split follows the Owner's decision [#325 6806047559](https://github.com/ktogias/gnostoa/issues/325#issuecomment-6806047559): thematic files, each well under 64 KiB, one manifest, stable ids and traceability.

Owner directions remain authoritative in their linked GitHub records; where a rule here differs from a linked record, the record wins. The [review corrections](#review-corrections) are the exception: each replaces a published line of the rulebook's own source records that review found wrong, so for those lines this file set applies.

## Load by theme

| Theme | Rule ids | Rules | File |
|---|---|---|---|
| 1. Authority and attribution | R-AUTH-01 to R-AUTH-10 | 10 | [governance](supervisor-rulebook-governance.md) |
| 2. Owner directions and autonomy | R-OWN-01 to R-OWN-05 | 5 | [governance](supervisor-rulebook-governance.md) |
| 3. Records, language and publication | R-REC-01 to R-REC-08 | 8 | [evidence-gates](supervisor-rulebook-evidence-gates.md) |
| 4. Container-first and runtime | R-RUN-01 to R-RUN-10 | 10 | [runtime-architecture](supervisor-rulebook-runtime-architecture.md) |
| 5. Merge and review process | R-MRG-01 to R-MRG-23 | 23 | [evidence-gates](supervisor-rulebook-evidence-gates.md) |
| 6. Evidence and claims | R-EVD-01 to R-EVD-11 | 11 | [evidence-gates](supervisor-rulebook-evidence-gates.md) |
| 7. Tests and mutation | R-TST-01 to R-TST-17 | 17 | [testing-analysis](supervisor-rulebook-testing-analysis.md) |
| 8. Analyzers and merge-admission evidence | R-ANL-01 to R-ANL-10 | 10 | [testing-analysis](supervisor-rulebook-testing-analysis.md) |
| 9. Gates, guards and lessons | R-GATE-01 to R-GATE-05 | 5 | [evidence-gates](supervisor-rulebook-evidence-gates.md) |
| 10. Handoffs, waits and liveness | R-LIVE-01 to R-LIVE-10 | 10 | [runtime-architecture](supervisor-rulebook-runtime-architecture.md) |
| 11. Architecture, reuse and scope | R-ARCH-01 to R-ARCH-09 | 9 | [runtime-architecture](supervisor-rulebook-runtime-architecture.md) |
| 12. Proposals, prior art and research | R-PROP-01 to R-PROP-04 | 4 | [governance](supervisor-rulebook-governance.md) |
| 13. Security and credentials | R-SEC-01 to R-SEC-12 | 12 | [runtime-architecture](supervisor-rulebook-runtime-architecture.md) |
| 14. Pilot operations | R-PILOT-01 to R-PILOT-06 | 6 | [runtime-architecture](supervisor-rulebook-runtime-architecture.md) |
| 15. Planning and the Ariadne queue | R-PLAN-01 to R-PLAN-03 | 3 | [governance](supervisor-rulebook-governance.md) |

In total there are 143 rules in 15 themes (140 active, 1 superseded, 2 historical): 141 from parts 1 and 2, R-GATE-05 from addendum 1 and R-EVD-11 from addendum 2.

## Review corrections

Review of [PR #493](https://github.com/ktogias/gnostoa/pull/493), with the supervisor errata it prompted ([#493 6810511661](https://github.com/ktogias/gnostoa/pull/493#issuecomment-6810511661), [#493 6812630327](https://github.com/ktogias/gnostoa/pull/493#issuecomment-6812630327) and [#325 6810405421](https://github.com/ktogias/gnostoa/issues/325#issuecomment-6810405421)), found ten published lines that are wrong for this file set or for `main`. They are corrected here; every other rule is unchanged from its record. The supervisor's next re-export should carry the same corrections.

| Rule | File | Correction | Reason |
|---|---|---|---|
| R-GATE-05 | [evidence-gates](supervisor-rulebook-evidence-gates.md) | "this record" becomes "the index and its four theme files". | The rulebook is now five files, not one record. |
| R-TST-05 | [testing-analysis](supervisor-rulebook-testing-analysis.md) | The suites run inside a container started with `docker run --network none`. | `ci/verify` takes only a profile name, so a `--network none` passed to it would be ignored. |
| R-TST-06 | [testing-analysis](supervisor-rulebook-testing-analysis.md) | Mutants run through the qualified parallel runner of R-TST-07, which runs the baseline first. | `knowledge mutants` (#374) is not on `main`. |
| R-ANL-05 | [testing-analysis](supervisor-rulebook-testing-analysis.md) | The limit is the patch size that GitHub's comparison still returns; keep each file's patch under 80,000 bytes. | The collector's cap has been 4 MiB since #396; GitHub leaves out larger patches ([#396 6753827825](https://github.com/ktogias/gnostoa/pull/396#issuecomment-6753827825)). |
| R-ANL-08 | [testing-analysis](supervisor-rulebook-testing-analysis.md) | Ruff's option is described, not named. | Its literal name contains a suppression marker, which merge-admission (M13) reads as an unjustified suppression. |
| R-RUN-04 | [runtime-architecture](supervisor-rulebook-runtime-architecture.md) | The heavy stage keeps to one internally parallel run at a time: `extended`, a test-running `self-check` and the mutant workers run one after another. Only the runtime build with `self-check --skip-tests` may overlap `extended`. | The published line set no bound, which review found in conflict with R-LIVE-04 and R-RUN-07. The supervisor's first erratum ([#493 6810511661](https://github.com/ktogias/gnostoa/pull/493#issuecomment-6810511661)) kept the three runs concurrent under a bound of one internally parallel suite (`extended` or parity). Review then found that a test-running `self-check` is such a suite too: without `--skip-tests` it runs the test suite in parallel processes (`tools/self_check.py`, Decision 0109; CodeAnt review comment 4545507098). The supervisor's erratum 2 ([#493 6812630327](https://github.com/ktogias/gnostoa/pull/493#issuecomment-6812630327)) corrected the step; the runtime build overlaps `extended` as the install and cwd check of proposal A (2026-10-05). |
| R-RUN-07 | [runtime-architecture](supervisor-rulebook-runtime-architecture.md) | The title says "one qualification round at a time", not "one heavy job at a time". | The title overgeneralised its body, which limits qualification rounds and keeps mutant and collector runs away from a preparation (supervisor erratum [#493 6810511661](https://github.com/ktogias/gnostoa/pull/493#issuecomment-6810511661)). |
| R-LIVE-01 | [runtime-architecture](supervisor-rulebook-runtime-architecture.md) | A body digest uses the kind its envelope declares; `github-issue-body-utf8-sha256-v1` hashes the exact REST `body` string with no trimming or newline change. | The published `sha256(body.rstrip("\n") + "\n")` changes those bytes, so it contradicts `guidance/workflows/resume-bounded-task.md`; only the older, unversioned `provider-body-sha256` used it (CodeAnt review comment 4544688131; supervisor erratum [#493 6810511661](https://github.com/ktogias/gnostoa/pull/493#issuecomment-6810511661)). |
| R-LIVE-04 | [runtime-architecture](supervisor-rulebook-runtime-architecture.md) | "Do not run heavy suites side by side" becomes: one internally parallel run at a time (`extended`, a test-running `self-check`, the mutant workers or parity), and one qualification round at a time. | The published line overgeneralised the narrower rule of #454 and contradicted R-RUN-04's heavy stage (supervisor erratum [#325 6810405421](https://github.com/ktogias/gnostoa/issues/325#issuecomment-6810405421)). Its list of runs follows R-RUN-04's erratum 2 ([#493 6812630327](https://github.com/ktogias/gnostoa/pull/493#issuecomment-6812630327)). |
| R-SEC-03 | [runtime-architecture](supervisor-rulebook-runtime-architecture.md) | Credential-touching helpers use `python3 -I`; `-P` is kept for probe scripts that need `PYTHONPATH`. | `-P` keeps the script directory off `sys.path` but still reads `PYTHONPATH`, so it does not isolate a helper. The source notes give `-I` for helpers and `-P` for probes. |

## The rulebook's conventions

Copied unchanged from part 1 ([#325 6805345513](https://github.com/ktogias/gnostoa/issues/325#issuecomment-6805345513)); part 2 repeats them. Its counts are those of parts 1 and 2; the two addenda add one rule and one source note each. Its Authority line does not restore the published lines that the [review corrections](#review-corrections) replace.

- **Purpose:** a handoff-safe rulebook. It records the operating rules the supervisor agent learned while running Gnostoa, so that a future handoff (a new session, runtime or provider) does not lose them.
- **Source:** the supervisor's memory as of 2026-11-11: 197 memory notes. One was excluded as host-only; the other 196 are merged into 141 rules. The manifest lists every note with its digest and rule ids.
- **Authority:** Owner directions remain authoritative in their linked GitHub records. This rulebook is a digest: where it differs from a linked record, the record wins.
- **How to keep it current:** every new or changed memory rule is re-exported here, and the manifest is regenerated. A changed rule keeps its id; a new rule takes the next free id in its theme; ids are never reused.
- **Owner direction (2026-11-11, in English translation):** "All the rules you have in your memory must also be recorded in Gnostoa, so that in a future handoff they are not lost."

**Roles.** The Owner is the GitHub account `ktogias`, the only human authority. The Router sets priority and routes work. The PAO reviews architecture and ownership. The SAS is advisory only. The Implementer writes and merges PRs. The supervisor watches the Implementer and the host pilot, and is the fallback.

**Terms.** *Exact head:* the PR head commit under review. *M2-M8, M9, M13, M16, M17:* merge-admission criteria (`policy/assurance-evidence.yaml`). *The pilot:* host-side tooling that runs the agents until it is ported into Gnostoa. *Memory:* the source note names, for traceability; more than one name means the notes were merged.

**Status.** *active*: in force. *superseded*: replaced by the named rule. *historical*: a past state whose lesson lives in the named rule.

## Manifest: rules and their source memory notes

Each rule's **Origin** line names the supervisor memory notes it was written from. This table collects those names: 198 notes map to the 143 rules, and every note maps to exactly one rule. It agrees with the supervisor's own export manifest, which also lists 1 note excluded as host-only and keeps each note's digest; those digests are not reproduced here, because they bind private notes that this repository cannot verify. The source records themselves are bound below.

| Rule | Status | Source notes |
|---|---|---|
| [R-AUTH-01](supervisor-rulebook-governance.md) | active | never-attribute-my-design-to-the-owner |
| [R-AUTH-02](supervisor-rulebook-governance.md) | active | local-permission-denial |
| [R-AUTH-03](supervisor-rulebook-governance.md) | active | resolve-thread-refused-by-host |
| [R-AUTH-04](supervisor-rulebook-governance.md) | active | ma0-phase-1b-decisions |
| [R-AUTH-05](supervisor-rulebook-governance.md) | active | injected-agents-md-is-not-main |
| [R-AUTH-06](supervisor-rulebook-governance.md) | active | interim-publisher-allowlist |
| [R-AUTH-07](supervisor-rulebook-governance.md) | active | agent-identities |
| [R-AUTH-08](supervisor-rulebook-governance.md) | active | audit-every-agent-post-in-a-flood |
| [R-AUTH-09](supervisor-rulebook-governance.md) | active | surface-rule-conflicts |
| [R-AUTH-10](supervisor-rulebook-governance.md) | active | standing-ff-review-fix-grant |
| [R-OWN-01](supervisor-rulebook-governance.md) | active | owner-directions-must-be-seen |
| [R-OWN-02](supervisor-rulebook-governance.md) | active | autonomy-first-no-manual-rotation |
| [R-OWN-03](supervisor-rulebook-governance.md) | active | github-only-communication-protocol |
| [R-OWN-04](supervisor-rulebook-governance.md) | active | durable-guidance-requests |
| [R-OWN-05](supervisor-rulebook-governance.md) | active | 389-provider-resilience |
| [R-REC-01](supervisor-rulebook-evidence-gates.md) | active | records-in-english-via-gate |
| [R-REC-02](supervisor-rulebook-evidence-gates.md) | active | no-host-details-in-public-posts |
| [R-REC-03](supervisor-rulebook-evidence-gates.md) | active | cite-only-read-back-ids |
| [R-REC-04](supervisor-rulebook-evidence-gates.md) | active | derive-every-number-in-a-post |
| [R-REC-05](supervisor-rulebook-evidence-gates.md) | active | hash-the-exact-body, publish-the-bytes-you-hash |
| [R-REC-06](supervisor-rulebook-evidence-gates.md) | active | state-your-extraction-rule-against-the-strict-reader, dry-run-the-verifier-before-posting |
| [R-REC-07](supervisor-rulebook-evidence-gates.md) | active | freeze-published-evidence |
| [R-REC-08](supervisor-rulebook-evidence-gates.md) | active | quote-option-definitions-verbatim, reuse-the-latest-corrected-figure |
| [R-RUN-01](supervisor-rulebook-runtime-architecture.md) | active | run-container-route-by-default |
| [R-RUN-02](supervisor-rulebook-runtime-architecture.md) | active | dev-container-hides-cwd-bugs, behaviour-runs-need-the-checkout-on-pythonpath |
| [R-RUN-03](supervisor-rulebook-runtime-architecture.md) | active | gnostoa-candidate-prep-practicalities |
| [R-RUN-04](supervisor-rulebook-runtime-architecture.md) | active | verification-process-a |
| [R-RUN-05](supervisor-rulebook-runtime-architecture.md) | active | check-the-image-before-a-round, rebuild-dev-image-after-a-lock-change |
| [R-RUN-06](supervisor-rulebook-runtime-architecture.md) | active | never-mount-pwd, taskstop-leaves-containers |
| [R-RUN-07](supervisor-rulebook-runtime-architecture.md) | active | never-write-to-tmp, one-qualification-round-at-a-time, prune-runner-job-copies |
| [R-RUN-08](supervisor-rulebook-runtime-architecture.md) | active | no-rm-rf-even-a-fresh-path |
| [R-RUN-09](supervisor-rulebook-runtime-architecture.md) | active | classifier-base-rates-and-command-shape, host-refuses-inline-c-scripts, headless-lane-bash-shapes, owner-allows-docker-rm |
| [R-RUN-10](supervisor-rulebook-runtime-architecture.md) | active | unformatted-file-unbinds-receipts, ruff-format-moves-justifications |
| [R-MRG-01](supervisor-rulebook-evidence-gates.md) | active | standing-merge-consent, headless-implementer-never-merges |
| [R-MRG-02](supervisor-rulebook-evidence-gates.md) | active | no-admin-merges |
| [R-MRG-03](supervisor-rulebook-evidence-gates.md) | active | base-sync-carries-native-approval |
| [R-MRG-04](supervisor-rulebook-evidence-gates.md) | active | base-sync-prepare-over-first-parent |
| [R-MRG-05](supervisor-rulebook-evidence-gates.md) | active | freeze-after-admission-settles, merge-admission-queue-is-repo-wide |
| [R-MRG-06](supervisor-rulebook-evidence-gates.md) | active | keep-an-approved-sibling-mergeable |
| [R-MRG-07](supervisor-rulebook-evidence-gates.md) | active | landing-stacked-prs |
| [R-MRG-08](supervisor-rulebook-evidence-gates.md) | active | decision-0133-coalescing-swallows-neutral-edits |
| [R-MRG-09](supervisor-rulebook-evidence-gates.md) | active | review-events-add-annotated-runs |
| [R-MRG-10](supervisor-rulebook-evidence-gates.md) | active | gate-exercising-pr-needs-change-control, replay-the-collector-not-the-field-parser, revix-body-blocks-merge-admission, pr-body-64kib-limit |
| [R-MRG-11](supervisor-rulebook-evidence-gates.md) | active | bots-overwrite-pr-bodies, bots-edit-top-level-comments |
| [R-MRG-12](supervisor-rulebook-evidence-gates.md) | active | exact-candidate-before-fresh-review |
| [R-MRG-13](supervisor-rulebook-evidence-gates.md) | active | claude-review-turn-cap |
| [R-MRG-14](supervisor-rulebook-evidence-gates.md) | active | every-signal-on-the-head, check-runs-filter-all |
| [R-MRG-15](supervisor-rulebook-evidence-gates.md) | active | a-green-reviewer-check-can-mean-not-run |
| [R-MRG-16](supervisor-rulebook-evidence-gates.md) | active | read-threads-before-a-status-claim |
| [R-MRG-17](supervisor-rulebook-evidence-gates.md) | active | dispose-review-threads-one-at-a-time |
| [R-MRG-18](supervisor-rulebook-evidence-gates.md) | active | fix-every-review-finding |
| [R-MRG-19](supervisor-rulebook-evidence-gates.md) | active | review-convergence-stopping-rule |
| [R-MRG-20](supervisor-rulebook-evidence-gates.md) | active | hostile-local-shell-boundary, mutation-runner-boundary, reuse-check-scope-bound |
| [R-MRG-21](supervisor-rulebook-evidence-gates.md) | active | triage-findings-before-proposing-fixes, repair-only-current-scope-findings |
| [R-MRG-22](supervisor-rulebook-evidence-gates.md) | active | read-live-settings-before-changing-what-a-merge-carries |
| [R-MRG-23](supervisor-rulebook-evidence-gates.md) | active | timed-out-post-may-have-landed, gh-pr-merge-needs-a-git-cwd |
| [R-EVD-01](supervisor-rulebook-evidence-gates.md) | active | a-count-from-an-unpaginated-read, gh-api-comments-are-paginated, paginate-jq-runs-per-page |
| [R-EVD-02](supervisor-rulebook-evidence-gates.md) | active | find-the-owner-before-claiming-absence, host-records-every-decision |
| [R-EVD-03](supervisor-rulebook-evidence-gates.md) | active | measured-instances-are-not-impossibility, mock-factory-gets-the-original |
| [R-EVD-04](supervisor-rulebook-evidence-gates.md) | active | measure-before-claiming-complexity, bound-the-traversal-not-the-callback |
| [R-EVD-05](supervisor-rulebook-evidence-gates.md) | active | a-title-is-never-evidence |
| [R-EVD-06](supervisor-rulebook-evidence-gates.md) | active | judge-from-raw-outputs |
| [R-EVD-07](supervisor-rulebook-evidence-gates.md) | active | background-checks-read-the-live-tree |
| [R-EVD-08](supervisor-rulebook-evidence-gates.md) | active | unique-round-labels |
| [R-EVD-09](supervisor-rulebook-evidence-gates.md) | active | a-provenance-read-can-perturb |
| [R-EVD-10](supervisor-rulebook-evidence-gates.md) | active | audit-every-literal-when-porting, a-ported-shape-carries-its-subjects-bounds |
| [R-EVD-11](supervisor-rulebook-evidence-gates.md) | active | verify-facts-before-relaying |
| [R-TST-01](supervisor-rulebook-testing-analysis.md) | active | red-must-fail-for-the-defect |
| [R-TST-02](supervisor-rulebook-testing-analysis.md) | active | keep-pre-change-evidence-inspectable |
| [R-TST-03](supervisor-rulebook-testing-analysis.md) | active | a-test-can-pin-a-defect |
| [R-TST-04](supervisor-rulebook-testing-analysis.md) | active | a-fixture-that-answers-everything, stub-hides-provider-contract-defects |
| [R-TST-05](supervisor-rulebook-testing-analysis.md) | active | run-suites-offline |
| [R-TST-06](supervisor-rulebook-testing-analysis.md) | active | a-kill-needs-a-baseline |
| [R-TST-07](supervisor-rulebook-testing-analysis.md) | active | incident-425-runner |
| [R-TST-08](supervisor-rulebook-testing-analysis.md) | active | kill-check-the-excluded-region |
| [R-TST-09](supervisor-rulebook-testing-analysis.md) | active | a-new-guard-masks-older-tests |
| [R-TST-10](supervisor-rulebook-testing-analysis.md) | active | check-a-survivor-is-reachable |
| [R-TST-11](supervisor-rulebook-testing-analysis.md) | active | reanchor-keeps-the-mutation |
| [R-TST-12](supervisor-rulebook-testing-analysis.md) | active | a-differential-class-must-name-its-direction |
| [R-TST-13](supervisor-rulebook-testing-analysis.md) | active | measure-a-narrowing-against-own-layouts |
| [R-TST-14](supervisor-rulebook-testing-analysis.md) | active | replay-each-workflows-own-test-invocation |
| [R-TST-15](supervisor-rulebook-testing-analysis.md) | active | never-make-a-test-method-static |
| [R-TST-16](supervisor-rulebook-testing-analysis.md) | active | register-before-exec-module |
| [R-TST-17](supervisor-rulebook-testing-analysis.md) | active | scan-saved-rounds-before-attributing-a-flake |
| [R-ANL-01](supervisor-rulebook-testing-analysis.md) | active | use-the-authenticated-analyzer-readback |
| [R-ANL-02](supervisor-rulebook-testing-analysis.md) | active | m17-counts-provider-full-runs |
| [R-ANL-03](supervisor-rulebook-testing-analysis.md) | active | early-m2-m8-incomplete-is-suite-timing, read-the-complete-verdict-before-the-packet |
| [R-ANL-04](supervisor-rulebook-testing-analysis.md) | active | gate-cause-from-the-declaration |
| [R-ANL-05](supervisor-rulebook-testing-analysis.md) | active | patch-cap-makes-m13-partial |
| [R-ANL-06](supervisor-rulebook-testing-analysis.md) | active | run-mypy-before-push, measure-a-pr-against-the-project-inventory, measure-sonar-cognitive-complexity-before-push, probe-inside-every-touched-function |
| [R-ANL-07](supervisor-rulebook-testing-analysis.md) | active | b105-matches-target-names, sonar-s3415-follows-assignment, measure-resolution-not-syntax, executable-path-analyzer-trilemma |
| [R-ANL-08](supervisor-rulebook-testing-analysis.md) | active | check-the-producer-before-offering-a-suppression |
| [R-ANL-09](supervisor-rulebook-testing-analysis.md) | active | a-retirement-must-reach-the-procedure |
| [R-ANL-10](supervisor-rulebook-testing-analysis.md) | historical | reading-deepsource-locally |
| [R-GATE-01](supervisor-rulebook-evidence-gates.md) | active | effect-point-checklist, reuse-the-accepted-merge-shape |
| [R-GATE-02](supervisor-rulebook-evidence-gates.md) | active | gate-is-its-own-step, gate-a-post-on-the-check-result |
| [R-GATE-03](supervisor-rulebook-evidence-gates.md) | active | bind-every-promise-in-the-preimage, bind-every-decision-the-effect-carries |
| [R-GATE-04](supervisor-rulebook-evidence-gates.md) | active | close-lessons-with-a-guard |
| [R-GATE-05](supervisor-rulebook-evidence-gates.md) | active | memory-rules-exported-to-gnostoa |
| [R-LIVE-01](supervisor-rulebook-runtime-architecture.md) | active | gnostoa-resume-route, maint-takeover-20261109, handover-may-predate-the-last-turn |
| [R-LIVE-02](supervisor-rulebook-runtime-architecture.md) | active | open-routes-are-obligations |
| [R-LIVE-03](supervisor-rulebook-runtime-architecture.md) | active | verified-work-during-waits |
| [R-LIVE-04](supervisor-rulebook-runtime-architecture.md) | active | cycle-time-rules |
| [R-LIVE-05](supervisor-rulebook-runtime-architecture.md) | active | publish-host-blockers |
| [R-LIVE-06](supervisor-rulebook-runtime-architecture.md) | active | every-nudge-is-an-incident, rca-every-liveness-firing |
| [R-LIVE-07](supervisor-rulebook-runtime-architecture.md) | active | continue-after-quota-without-prompt |
| [R-LIVE-08](supervisor-rulebook-runtime-architecture.md) | active | watcher-since-from-api |
| [R-LIVE-09](supervisor-rulebook-runtime-architecture.md) | active | github-cron-is-not-a-cadence |
| [R-LIVE-10](supervisor-rulebook-runtime-architecture.md) | active | consume-only-current-head-signal-versions |
| [R-ARCH-01](supervisor-rulebook-runtime-architecture.md) | active | architecture-inheritance-gate, decision-and-lineage-before-the-first-edit |
| [R-ARCH-02](supervisor-rulebook-runtime-architecture.md) | active | reuse-before-write, authority-execution-was-copied |
| [R-ARCH-03](supervisor-rulebook-runtime-architecture.md) | active | review-fixes-are-new-code |
| [R-ARCH-04](supervisor-rulebook-runtime-architecture.md) | active | build-into-gnostoa-never-temporary |
| [R-ARCH-05](supervisor-rulebook-runtime-architecture.md) | active | everything-in-gnostoa-provider-agnostic, review-reconcile-is-provider-neutral |
| [R-ARCH-06](supervisor-rulebook-runtime-architecture.md) | active | stop-on-unadmitted-path |
| [R-ARCH-07](supervisor-rulebook-runtime-architecture.md) | active | preparation-is-not-implementation |
| [R-ARCH-08](supervisor-rulebook-runtime-architecture.md) | active | grep-the-bare-name-before-a-signature-change, trace-a-version-constant-before-scoping |
| [R-ARCH-09](supervisor-rulebook-runtime-architecture.md) | active | workflow-steps-are-digest-pinned, merge-evidence-import-forces-three-files |
| [R-PROP-01](supervisor-rulebook-governance.md) | active | prior-art-before-every-proposal |
| [R-PROP-02](supervisor-rulebook-governance.md) | active | smallest-compliant-change-first |
| [R-PROP-03](supervisor-rulebook-governance.md) | active | narrow-dont-model |
| [R-PROP-04](supervisor-rulebook-governance.md) | active | shell-reader-needs-a-parser |
| [R-SEC-01](supervisor-rulebook-runtime-architecture.md) | active | agent-credentials-boundary |
| [R-SEC-02](supervisor-rulebook-runtime-architecture.md) | active | git-fetch-through-agent-git, bstar-write-route, app-watcher, gh-execution-route-conflict |
| [R-SEC-03](supervisor-rulebook-runtime-architecture.md) | active | helpers-never-import-from-cwd, scripts-never-shadow-stdlib |
| [R-SEC-04](supervisor-rulebook-runtime-architecture.md) | active | exercise-a-control-against-its-own-attack |
| [R-SEC-05](supervisor-rulebook-runtime-architecture.md) | active | remove-the-shape-not-the-instance, read-the-action-security-docs-first |
| [R-SEC-06](supervisor-rulebook-runtime-architecture.md) | active | check-where-the-secret-lives |
| [R-SEC-07](supervisor-rulebook-runtime-architecture.md) | active | reusable-workflow-secrets, reusable-workflow-environment-secrets |
| [R-SEC-08](supervisor-rulebook-runtime-architecture.md) | active | command-line-git-config-is-not-an-override |
| [R-SEC-09](supervisor-rulebook-runtime-architecture.md) | active | calibrate-both-paths |
| [R-SEC-10](supervisor-rulebook-runtime-architecture.md) | active | recheck-the-checklist-after-a-credential-change |
| [R-SEC-11](supervisor-rulebook-runtime-architecture.md) | active | secret-scan-reads-tracked-files |
| [R-SEC-12](supervisor-rulebook-runtime-architecture.md) | superseded | ref-rulesets-admin-only |
| [R-PILOT-01](supervisor-rulebook-runtime-architecture.md) | active | implementer-runtime-switch-20261110 |
| [R-PILOT-02](supervisor-rulebook-runtime-architecture.md) | active | shared-claude-quota-with-implementer |
| [R-PILOT-03](supervisor-rulebook-runtime-architecture.md) | active | stop-sew-and-unpick |
| [R-PILOT-04](supervisor-rulebook-runtime-architecture.md) | active | standing-approval-pilot-fixes |
| [R-PILOT-05](supervisor-rulebook-runtime-architecture.md) | active | pilot-tests-write-live-state |
| [R-PILOT-06](supervisor-rulebook-runtime-architecture.md) | active | runtime-handoff-inventory |
| [R-PLAN-01](supervisor-rulebook-governance.md) | active | owner-directions-become-work-items |
| [R-PLAN-02](supervisor-rulebook-governance.md) | active | score-slices-against-the-exit-test, implementer-overlay-sas-pilot |
| [R-PLAN-03](supervisor-rulebook-governance.md) | historical | gate-ordering-2026-10-08 |

## Source records

SHA-256 of each record's body as the GitHub REST API returns it, read on 2026-11-11.

| Record | Posted | Body bytes | SHA-256 |
|---|---|---|---|
| [Supervisor rulebook (handoff-safe), part 1 of 2](https://github.com/ktogias/gnostoa/issues/325#issuecomment-6805345513) | 2026-11-11T19:31:36Z | 55688 | `362bce79550c87953b9b0ae5ae558afdfcf2b78b9a0745f1f6dd2f2888640c96` |
| [Supervisor rulebook (handoff-safe), part 2 of 2](https://github.com/ktogias/gnostoa/issues/325#issuecomment-6805346585) | 2026-11-11T19:31:39Z | 41137 | `1e1174511227e41e14f13a42a1ea994b342411a21961df73ba62b30582c9df26` |
| [Supervisor rulebook, addendum 1 (R-GATE-05)](https://github.com/ktogias/gnostoa/issues/325#issuecomment-6805360817) | 2026-11-11T19:32:19Z | 1196 | `88b148be263bde34284b554ee53dc8d8212eb9b66bba4c3a3ce03b1a767908e3` |
| [Supervisor rulebook, addendum 2 (R-EVD-11)](https://github.com/ktogias/gnostoa/issues/325#issuecomment-6805985258) | 2026-11-11T20:02:29Z | 1071 | `94f31f30bb42a9271ea4bc6025d343a23491366efa618e9f041485f37af10f3f` |
