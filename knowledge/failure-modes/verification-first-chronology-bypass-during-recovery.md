---
type: Failure Mode
title: Verification-first chronology bypass during recovery
description: Retrospective on PR #314 where constrained-execution recovery succeeded technically but the agent shaped a bug fix before preserving the required pre-change RED evidence.
status: draft
generated:
  by: openai/gpt-5.6-sol
  at: "2026-09-24T00:00:00Z"
sources:
  - id: analyzer-readback-change-request
    resource: https://github.com/ktogias/gnostoa/pull/314
    title: Add provider-neutral authenticated analyzer readback (#309 #313)
  - id: execution-recovery-change-request
    resource: https://github.com/ktogias/gnostoa/pull/315
    title: Document conditional agent execution recovery route (#308)
  - id: execution-recovery-work-item
    resource: https://github.com/ktogias/gnostoa/issues/308
    title: Enforce a single active implementation identity per Work Item across sessions
x-project-knowledge:
  id: kit.failure-mode.verification-first-chronology-bypass-during-recovery
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: conflicts-with
      target: /requirements/verification-precedes-implementation.md
    - kind: references
      target: /decisions/0007-verification-first-development.md
    - kind: references
      target: /decisions/0090-require-pre-candidate-preparation-receipts-for-non-hook-authoring.md
    - kind: verified-by
      target: /runbooks/deliver-bounded-self-hosted-slice.md
---

# Verification-first chronology bypass during recovery

## Resume card

| Field | Current state |
|---|---|
| Event | During recovery of PR #314 at exact head `09afa312a980cfa4334f9322be46d0ecec0349fa`, a new DeepSource status/check-run disagreement regression and its production fix were written and GREEN-verified before the agent had preserved executable RED evidence on the exact pre-change implementation. |
| Impact | No merge or protected-main effect occurred. The intended defect was real and the final candidate behavior is supported, but the initial authoring chronology violated the Gnostoa-self verification-first specialization. |
| Detection | The owner explicitly asked whether RED→GREEN had actually been performed. The agent then audited the chronology instead of treating GREEN as sufficient. |
| Immediate correction | Keep the new regression test, temporarily restore only the affected production implementation to the exact parent bytes, run the test to reproduce RED, restore the fix, and rerun GREEN. |
| RED evidence | `PYTHONPATH=. python -m unittest tests.test_analyzer_readback.DeepSourceAnalyzerReadbackTests.test_commit_status_and_check_run_disagreement_is_ambiguous` returned exit 1 on the exact-parent implementation: expected `AMBIGUOUS`, observed `DIFF_LOCAL`. |
| GREEN evidence | The same focused test returned OK after the fix; `PYTHONPATH=. python -m unittest tests.test_analyzer_readback` then returned 66/66 OK. |
| Durable correction | The recovery runbook now requires an explicit pre-edit chronology checkpoint and defines a late-RED recovery protocol that records, rather than erases, a chronology violation. |
| Remaining tooling opportunity | A machine-readable pre-implementation evidence receipt or pre-edit guard could reduce recurrence, but it is new implementation and requires separate admission rather than being smuggled into this documentation repair. |

## Process audit: do we always require RED → GREEN?

No. Gnostoa deliberately uses **proportionate verification**, not universal TDD.

The generic guidance permits several evidence modes:

- executable new behavior, conformance work or a reproduced defect normally uses
  RED → GREEN;
- behavior-preserving refactoring uses a **green characterization baseline**
  before structural edits;
- non-executable knowledge uses an unmet structural or semantic criterion plus
  accountable human review rather than artificial tests;
- mechanical changes may rely on existing evidence with their declared
  before-merge timing; and
- an explicitly classified emergency may restore safety first and supply the
  required regression evidence in the audited post-event follow-up.

Gnostoa-self is stricter than the community-light generic baseline. Its
`policy/change-control.yaml` moves normal verification timing to
`before-implementation`, requires failing evidence for normative and critical
changes, and the maintainer runbook says that a bug must run a reproducer before
the fix. Changes under `tools/`, `schemas/`, `core/` or `policy/` also
require focused pre-implementation behavioral, conformance or structural
evidence.

PR #314 was a normal bug fix in `tools/analyzer_deepsource.py`. Failing evidence
was plainly applicable, so the correct route was RED on the exact parent before
the production edit, then GREEN. The recovery constraints did not create an
exception.

## Event chronology

1. Provider read-back established PR #314 head
   `09afa312a980cfa4334f9322be46d0ecec0349fa`.
2. A reviewer found that first-seen-per-analyzer deduplication could hide a
   disagreement between a DeepSource commit status and check run, potentially
   binding a stale run instead of failing closed.
3. The agent inspected the current implementation and agreed that the finding
   was valid.
4. During constrained-environment recovery, attention shifted to reconstructing
   exact source, missing local tooling and the Decision 0090 path.
5. The agent wrote the regression test and production fix, then ran focused
   GREEN verification. This proved the candidate but did not prove that the
   regression distinguished the pre-change behavior before implementation.
6. The owner asked whether RED → GREEN had actually occurred.
7. The agent audited the chronology, acknowledged that RED had not been
   preserved, and reconstructed it against the exact parent implementation.
8. The focused test failed for the intended reason:
   `AssertionError: 'AMBIGUOUS' != 'DIFF_LOCAL'`.
9. Restoring the fix made the same test pass, and the complete analyzer-readback
   module passed 66 tests.

The late RED is valid defect evidence, but it is explicitly **not** presented as
retroactive compliance with the original verification-first chronology.

## Root-cause analysis

### Immediate cause

The agent treated static inspection plus a reviewer finding as sufficient proof
that the defect existed and moved directly to candidate shaping. It conflated
"the diagnosis is convincing" with "the required executable pre-change evidence
has been observed."

### Contributing causes

1. **Recovery-task attentional capture.** The session was dominated by exact-head
   recovery, Git transport constraints, missing local Ruff/development tooling,
   Decision 0090 preparation and concurrent-writer concerns. Evidence chronology
   became an implicit assumption instead of an explicit gate.
2. **No explicit pre-edit checkpoint in the recovery route.** The runbook said
   to reproduce RED/characterization on the clean parent, but did not require a
   compact recorded state before the first semantic edit.
3. **Hybrid enforcement.** Existing policy and tests validate declared evidence
   requirements and final repository state, but they do not mechanically observe
   the moment at which an agent first edits production bytes.
4. **GREEN bias.** Once the new regression and the full 66-test module passed,
   the result looked operationally strong. Final correctness evidence masked the
   missing chronology until the owner asked specifically about RED.
5. **No mandatory status vocabulary for evidence phase.** Progress updates
   reported defect validation and candidate verification without an explicit
   `RED_OBSERVED`, `CHARACTERIZED`, `STRUCTURAL_CRITERION_RECORDED` or
   `EMERGENCY_POST_EVENT` state.
6. **Human detective control activated late.** The process relied on the owner
   noticing and asking about RED chronology rather than making the executor
   surface that state before editing.

## Corrections and prevention

### Immediate operating rule

Before the first semantic edit, record an evidence-mode checkpoint containing:

- exact pre-change subject;
- change class;
- evidence mode;
- exact command or structural criterion;
- expected pre-change outcome; and
- observed outcome and why it is non-vacuous.

Source acquisition, provider read-back and tooling restoration may happen before
this checkpoint because they do not change semantic candidate bytes. Candidate
shaping may not.

### Late-detection recovery

When a required RED was skipped:

1. stop further candidate shaping;
2. preserve the regression test separately;
3. restore the affected production bytes to the exact pre-change subject;
4. run the same test and require failure for the intended reason;
5. record the result as **late RED reconstruction** and retain the chronology
   violation;
6. restore the candidate;
7. rerun the focused test and broader affected suite to GREEN; and
8. continue preparation/review only after both evidence states are durable.

Do not rewrite commit history or narrative to imply that RED preceded the first
implementation when it did not.

### Process-level prevention

- Keep the verification-first step visible inside constrained-execution recovery,
  rather than treating recovery as a separate lifecycle.
- Require progress/status reports to state the current evidence mode before
  reporting that implementation is underway.
- Treat reviewer/static-analysis agreement as diagnosis input, not a substitute
  for an applicable reproducer.
- When resuming interrupted work, re-read not only provider/head identity but
  also whether required pre-implementation evidence has already been recorded.
- Preserve RED non-vacuity: a failing test must demonstrate that the intended
  seam was reached and fail for the expected behavioral reason.
- Do not universalize RED. Characterization, structural evidence and emergency
  post-event evidence remain first-class routes where the governing
  classification says they apply.

### Candidate tooling follow-up, not admitted here

A future bounded improvement could introduce a machine-readable evidence receipt
or an executor-side pre-edit state marker bound to exact parent, evidence mode,
command and result. A publication/preparation command could then refuse to claim
verification-first chronology when no compatible receipt exists.

This document does **not** implement or admit that tooling. The finding is
recorded for later owner selection because adding a new gate changes executable
workflow behavior and must follow ordinary Work Item/Decision/admission rules.

## Claim and authority boundaries

This failure-mode record does not invalidate the subsequently reconstructed RED
or GREEN evidence for PR #314, and it does not by itself authorize that PR for
merge. It records a process chronology defect and its recovery.

It also does not change the generic project's proportionate-verification
principle into universal TDD. The stricter conclusion applies where the
Gnostoa-self specialization or the concrete bug/change surface requires
pre-implementation failing evidence.
