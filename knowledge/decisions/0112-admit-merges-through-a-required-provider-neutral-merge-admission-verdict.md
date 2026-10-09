---
type: Decision
title: Admit merges through a required, provider-neutral merge-admission verdict
description: MA0 Phase 1b. A required check, merge-admission, admits a merge only when a provider-neutral, fail-closed verdict over the exact head finds every applicable criterion satisfied. Its evidence part is one completeness reducer over exact-subject receipts (#389 S1), which slice 1b.1 implements. GitHub specifics stay in an adapter, a dedicated App publishes the check from a main-only environment, and the owner's native approval of the exact head is the only per-merge human act, with no waiver.
status: draft
generated:
  by: anthropic/claude-opus-5-5
  at: "2026-10-09T07:15:00Z"
sources:
  - id: work-item
    resource: https://github.com/ktogias/gnostoa/issues/407
    title: Require a provider-neutral merge-admission verdict on the exact head (MA0 Phase 1b)
  - id: admission-package
    resource: https://github.com/ktogias/gnostoa/issues/407#issuecomment-6069729619
    title: The admission package, its lineage at 795920f and its prior art
  - id: owner-decisions
    resource: https://github.com/ktogias/gnostoa/issues/407#issuecomment-6076064688
    title: The owner's decisions on the package
  - id: phase-1b-handoff
    resource: https://github.com/ktogias/gnostoa/issues/398#issuecomment-6061573600
    title: The owner's Phase 1b handoff, its seams and its safety invariants
  - id: ma0-revision
    resource: https://github.com/ktogias/gnostoa/issues/15#issuecomment-6048360846
    title: The MA0 revision, with the merge-admission criteria M1-M16
  - id: completeness-owner
    resource: https://github.com/ktogias/gnostoa/issues/389
    title: Fail closed when required assurance evidence is missing, stale or incomplete
x-project-knowledge:
  id: kit.decision.0112.admit-merges-through-a-required-provider-neutral-merge-admission-verdict
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: references
      target: /decisions/0110-bind-every-merge-to-the-owner-s-approval-of-the-exact-head.md
    - kind: governed-by
      target: /decisions/0006-provider-neutral-change-governance.md
    - kind: implements
      target: /requirements/reviewed-change-control.md
    - kind: references
      target: /decisions/0086-implement-useful-l1-as-protected-source-github-current-state-reconciler.md
    - kind: references
      target: /decisions/0091-add-authenticated-provider-neutral-analyzer-readback.md
---

# Admit merges through a required, provider-neutral merge-admission verdict

## Context

[Decision 0110](0110-bind-every-merge-to-the-owner-s-approval-of-the-exact-head.md)
(MA0 Phase 1a) makes the owner's native approval of a pull request required on
`main`. It leaves the rest to the merge procedure and the agent's convergence report:
- the approval's `commit_id` against the head;
- the analyzer readback;
- the analyzers' findings;
- the seal;
- close-last.

Its "Successor: Phase 1b" defers a required check that enforces them, under a
reuse contract:
- consume `tools/github_rest.py`;
- consume Decision 0086's current-state observation;
- consume #389's completeness receipts and #369's trusted execution once they exist;
- add only the provider-neutral verdict.

The evidence part of the merge criteria (M2–M8 in the MA0 revision) is #389 S1's
completeness verdict: "one reducer, not two". No such reducer existed at `795920f`.

## Decision

This Decision is a Gnostoa-self/GitHub specialization. It does not alter the
provider-neutral public change-governance contract of
[Decision 0006](0006-provider-neutral-change-governance.md).

1. **A required check, `merge-admission`, admits each merge.** It passes only when a
   verdict over the exact head finds every applicable criterion satisfied. The
   verdict is provider-neutral and deterministic, and has no network access or side
   effect. It fails closed: missing, stale, partial, unavailable and unknown evidence
   deny. GitHub's vocabulary is translated in an adapter, which consumes the existing
   observation, readback and transport owners. It adds no second observer, reducer or
   REST client.
2. **One completeness reducer** supplies the verdict's evidence part
   (`knowledge assurance-check`, #389 S1):
   - A project declaration names, for each change class, the required evidence as
     coverage items (`policy/assurance-evidence.yaml`).
   - An item is covered only by a current `COMPLETE` receipt for the exact
     repository, change request and head. Otherwise it is `MISSING`, `STALE`,
     `PARTIAL`, `INCOMPLETE`, `SKIPPED`, `RATE_LIMITED`, `UNAVAILABLE` or `ERROR`.
   - Receipts that disagree fail closed at the worse status.
   - The receipt statuses are Decision 0091's coverage statuses, which contain
     Decision 0086's, plus `SKIPPED`.
   - The reducer fetches nothing and grants nothing.
3. **The owner's native approval of the exact head is the only per-merge human act.**
   - The verdict lists, for that approval:
     - reviewer convergence;
     - justified suppressions;
     - changes to the gate's trust roots.
   - Channel C, the environment attestation of MA0 design decision 2, is not used
     for merges. **There is no evidence waiver**: when required evidence is
     unavailable, the merge waits, or goes through break glass with its mandatory
     follow-up.
4. **Reviewer convergence (M11) is enforced as its deterministic subset in this
   phase:**
   - no unresolved thread;
   - no effective `CHANGES_REQUESTED`;
   - the readback and the analyzers.

   The convergence of the reviewers themselves stays in the agent's convergence
   report until MA0 Phase 2's per-reviewer adapters.
5. **Publication.** A dedicated App, `gnostoa-ma0`, posts the check from a main-only
   environment. It is woken by Decision 0096's relay pattern and a sweep, and the
   requirement in R-main is pinned to that App, so a same-named check from any other
   source cannot satisfy it.
6. **A post-merge audit** opens the emergency follow-up Work Item for any merge
   without a green `merge-admission` on its head.

## Consequences

- **The phase lands in slices** (#407). Each is admitted separately and merged under
  Phase 1a's procedure:

  | Slice | Contents | Status |
  |---|---|---|
  | 1b.1 | the completeness reducer and declaration | implemented with this Decision |
  | 1b.2 | the verdict | not yet admitted |
  | 1b.3 | the GitHub adapter and SonarCloud's inventory | not yet admitted |
  | 1b.4 | publication and activation | not yet admitted |
  | 1b.5 | the post-merge audit | not yet admitted |

- **Until 1b.4 activates the check, nothing changes for merges.** Decision 0110's
  procedure and the convergence report still govern them.
- **While an item has no producer, the reducer reports it `MISSING`.** SonarCloud's
  inventory is one such item until 1b.3. So once the check is required, a merge
  waits for its evidence rather than passing without it.
- **More owner configuration** is needed by 1b.3 and 1b.4: `SONAR_TOKEN`, the
  `gnostoa-ma0` App and its environment, and the requirement in R-main.

## What this supersedes or revises

- **MA0 design decisions 1, 3 and 4 (#15, 5979363503):**
  - the owner exception on every merge;
  - the attestation kinds;
  - the declared-class confirmation.

  They are superseded by item 3. Decision 2's channel C is no longer used for
  merges, a further step beyond Decision 0110's item 3.
- **Decisions 0107 and 0091 §8:** the readback becomes a required input of the
  verdict, failing closed. It is still not a required check of its own.
- **Decision 0067** is unchanged: R2A stays advisory, at most an input.
