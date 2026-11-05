---
type: Decision
title: Coalesce merge-admission requests by pull request, and publish each head's check one at a time
description: "#407's queue correction after #478: merge admission's routine requests queue per pull request, or per head when the run names none, with one pending follow-up, not in one repository-wide queue; guarded dispatches, manual requests, relayed comments and skipped runs each take a group of their own run, and the sweep its own; publication on one head is serialized by a per-head job lock; and a routine request whose material state equals the pinned App's completed authoritative success at that head is skipped before any pending check is written, by the guarded merge's own predicates, now shared. The relay, the guard's behaviour, the record format, the reducer and the adapter are unchanged."
status: draft
generated:
  by: anthropic/claude-opus-5-5
  at: "2026-11-05T18:25:00Z"
sources:
  - id: incident
    resource: https://github.com/ktogias/gnostoa/issues/407#issuecomment-6664424932
    title: "The owner's incident, RCA and direction: implement the bounded queue correction now"
  - id: route
    resource: https://github.com/ktogias/gnostoa/issues/389#issuecomment-6664435457
    title: "The owner's routing: start the #407 queue correction in parallel with #480"
  - id: ariadne
    resource: https://github.com/ktogias/gnostoa/issues/14#issuecomment-6664435018
    title: "Ariadne's immediate entry: merge-admission queue coalescing"
  - id: red
    resource: https://github.com/ktogias/gnostoa/issues/407#issuecomment-6665229576
    title: "The RED reproduction, the measured #478 baseline, the lineage and the design"
  - id: pao
    resource: https://github.com/ktogias/gnostoa/issues/407#issuecomment-6665267587
    title: "PAO's ruling: option 2; no bundle digest; the subjects job outside gnostoa-ma0"
  - id: l1
    resource: ./0086-implement-useful-l1-as-protected-source-github-current-state-reconciler.md
    title: The protected L1 reconciler, whose concurrency semantics this narrows
  - id: verdict
    resource: ./0112-admit-merges-through-a-required-provider-neutral-merge-admission-verdict.md
    title: The merge-admission verdict, whose publication and guard this keeps
x-project-knowledge:
  id: kit.decision.0133.coalesce-merge-admission-requests-by-pull-request
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: references
      target: /decisions/0112-admit-merges-through-a-required-provider-neutral-merge-admission-verdict.md
    - kind: references
      target: /decisions/0086-implement-useful-l1-as-protected-source-github-current-state-reconciler.md
---

# Coalesce merge-admission requests by pull request, and publish each head's check one at a time

## Context

On #478, the owner's approval took 58m20s to reach its own verdict, and the merge followed
59m50s after the approval (source `incident`). Every `merge-admission.yml` run shared one
repository-wide group, `gnostoa-merge-admission`, with `cancel-in-progress: false` and
`queue: max`. So every wake-up waited its turn, even one whose jobs all skip, and an unrelated
pull request waited behind another. Each evaluation also invalidated the standing success first.
In the measured window (source `red`), 163 runs were created and 115 only skipped. #478's
head was evaluated 20 times, 15 of them equivalent repeats. Its check was pending for 77.0% of
the time between its first ALLOW and the merge, and the guarded merge refused inside one of
those windows. A guarded dispatch could wait longer than the guard's own deadline.

## Decision

1. **Routine requests queue per pull request.** A routine request is the trigger's successful
   run for a pull request's event, or verification's run for a pull request. Its concurrency
   group is keyed by the pull request the run names, or by the run's head when it names none,
   as a fork's run does. The group has GitHub's single pending slot: one request runs, and a
   newer request replaces the one waiting. So a burst collapses to one evaluation of the newest
   state, plus at most one follow-up. Nothing that runs is cancelled.
2. **Guarded and scheduled work is never coalesced.** The sweep has its own group. Every other
   run has a group keyed by its own run, so it never waits behind routine work and never
   replaces it:
   - a `repository_dispatch`, so the guard's nonce and exact subject are bound as before (G1);
   - a manual request;
   - a relayed PR conversation comment, whose pull request only its artifact names;
   - a run whose jobs all skip, such as a comment the trigger skipped.

   The workflow's group admits a routine request by `subjects`' own condition, and a test
   holds the two together.
3. **Publication on one head is serialized.** `invalidate` and `admit` share one job-level lock
   keyed by the head, `gnostoa-merge-admission-publication-<head>`, with `queue: max` and
   `cancel-in-progress: false`. Two publications on one head never overlap, and none is
   cancelled while fewer than GitHub's 100 wait for the lock; past that, GitHub cancels the
   excess, and the sweep re-evaluates the head. The lock covers each job, not the run, so
   another run may act on the head between this run's `invalidate` and its `admit`. The relay
   already decides between such runs, fail-closed, as before:
   - `publish` completes its pending run only while it is the App's latest;
   - a success is written only over the run it observed at `invalidate`;
   - a dispatched run that is overtaken records a failure, which the guard refuses at once.

   The cost is a fresh evaluation, never a merge (`test_an_older_worker_never_restores_a_success`,
   `test_a_newer_run_s_success_stands_over_an_older_worker`,
   `test_an_overtaken_dispatched_success_still_leaves_a_failure_record`).
4. **An equivalent request is skipped before anything is written.** L1's subject selection
   drops the subject of a request woken by a completed workflow run when the pinned App's
   latest record at its head
   is a completed authoritative success. Authoritative means its external id is a verdict's
   digest, not a pending, superseded, overtaken or incomplete run's. The record must also show
   all of the following:
   - it was written from the protected revision this run executes (`GITHUB_SHA`);
   - it records the digest of the evidence rebuilt now without the analyzer bundle;
   - the complete open population shows the pull request alone at its head.

   The predicates are the guard's own, moved into `tools/merge_admission_checks.py`:
   `not_a_success`, `recorded_digest`, `changed`, `not_alone`, `open_population` and
   `unbundled_evidence`, composed by `equivalent`. The guard refuses with their reasons
   unchanged. The commit alone never proves equivalence. A missing, unreadable or short record
   never does either: the subject is then evaluated. The skip applies only to a request woken
   by a completed workflow run (`GITHUB_EVENT_NAME` `workflow_run`), a relayed comment's
   included: item 1's routine requests and the relayed comments that item 2 queues apart. The
   sweep, manual requests and guarded dispatches are never skipped this way. A DENY is never
   coalesced.
5. **The `subjects` job stays outside `gnostoa-ma0`** (source `pao`). Its selection step reads
   the pinned App's id as a literal, `GNOSTOA_MA0_APP_ID: "5302326"`. That is the value the
   publishing jobs read from their environment, and the one the App's published runs carry. A
   stale literal finds no matching success, so it can only cause a full evaluation, never an
   authorization. The job gains `issues`, `checks` and `statuses` read for the rebuild.
   Two protected tests change with it:
   - `test_permissions_are_granted_per_job` pins the three new reads.
   - `test_no_other_job_holds_a_secret` admits exactly that literal, in that step, for
     `subjects` alone, and asserts the job joins no environment. Every other assertion in it
     stays.

## Limits

- **The recorded digest does not carry the analyzer readback's state** (source `pao`). A
  coalesced request reuses a success whose bundle could, in principle, differ now. Only a
  completed authoritative success coalesces, an approval or a seal changes the digest, and the
  sweep and dispatches never coalesce. The residual is Decision 0112's.
- **In practice, the head keys a routine request.** GitHub left `pull_requests` empty in all
  158 of #478's saved trigger runs. So a push starts a new group, and a request woken at the
  old head does not wait for one at the new head. Both evaluate the pull request's current
  head, and the head's lock serializes their publication.
- **A relayed comment is never queued with routine requests.** Its pull request is unknown
  when the run is scheduled, so each successful relay evaluates in a group of its own. The
  equivalence skip still applies to it. A comment that changes nothing material, such as the
  seal repeated for the same head, writes nothing. One that does, such as a new head's seal or
  its removal, changes the evidence's declared candidate, and with it the digest, so it is
  evaluated.
- **The guard's deadline does not count a wait for the head's lock.** A dispatched run's
  `invalidate` or `admit` can wait behind another run's on the same head. Each run ahead holds
  the lock for at most its job's own limit, but the wait is not part of the 75-minute critical
  path.
- **The skip costs a rebuild in `subjects`.** For a routine request whose head has a standing
  success, the job rebuilds that pull request's evidence within its 10-minute limit. This cost
  is not measured.
- **A replaced pending run is listed as cancelled** in the Actions history.
- **The App id could instead come from a repository variable.** That is the owner's settings
  change; the literal needs none.

## Verification

- `tests/test_merge_admission_queue.py`: its six REDs on `main` `a515a2b1` turn green, and its
  guards and model checks still hold. A kill-check of the implementation added what its
  mutants showed unbound:
  - three scheduling tests, which fail on `main` as the REDs do: a run `subjects` does not
    admit shares no group; a newer routine request replaces the one waiting; and the sweep, a
    dispatch and a manual request each keep their own group;
  - two cases of the authoritative-success guard: a success under no verdict's id, and a
    verdict's DENY;
  - one guard: a selection without `--event` never coalesces.

  All 21 mutants of the predicates, the selection, the workflow's groups and locks, and the two
  protected pins then fail a test.
- The neighbouring merge-admission and L1 suites stay green, with the two protected changes
  named above.
- **Projection, not a measurement.** #478's 163 saved runs were replayed under the declared
  concurrency, with the measured median evaluation of 3m04s:

  | Figure | Measured | Projected |
  |---|---|---|
  | Full evaluations | 48 | 17 |
  | Evaluations of #478's last head | 20, 15 of them equivalent repeats | 7, with no repeat |
  | Approval to a current verdict | 58m20s (its own run) | 3m24s |
  | Pending share from the first ALLOW to the merge | 77.0% | 0.0% |
  | Longest wait of a skipped run | 83m53s | 0s |

- **A live measurement on `main` is still owed.** It needs, per burst:
  - jobs' start times, since a run's `run_started_at` does not show its wait;
  - the check runs per head, with their pending windows;
  - the review's submission time against the first verdict after it;
  - `subjects`' duration with the rebuild.

## Consequences

- An unrelated pull request, a guarded dispatch and a skipped wake-up no longer wait behind
  another pull request's evaluations.
- A standing ALLOW stays standing through events that change nothing material, so the guarded
  merge no longer meets a self-inflicted pending check.
- The guard, the relay and L1's selection read a record by one set of predicates. A change
  to them changes all three, and their tests run together under the
  `merge-admission-publication` guardrail.
