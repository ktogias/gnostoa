---
type: Decision
title: Read a written merge-admission check back within a bound, and cancel one that no read confirms
description: "#407, after the guarded merge of #489 refused on 2026-11-10: the relay checks the provider's answer to a check-run write before reading the run back, and the shared read of a run by its id retries a transient failure after 0.5, 1.5 and 3.5 s, never a refusal. A run that no read by its id finds is taken from the App's latest view when that view holds the same id. A run the answer confirmed but no read can is completed as cancelled, keeping its correlation, and the failure stays UNKNOWN. The guard keeps failing closed."
status: draft
generated:
  by: anthropic/claude-opus-5-5
  at: "2026-11-11T00:30:00Z"
sources:
  - id: refusal
    resource: https://github.com/ktogias/gnostoa/issues/407#issuecomment-6780222936
    title: "The guarded dispatch's receipts from #489: the guard refused after the invalidate job's read-back failed"
  - id: pao
    resource: https://github.com/ktogias/gnostoa/issues/407#issuecomment-6780287511
    title: "PAO's assessment: section 2.1 and findings F-01 to F-04"
  - id: route
    resource: https://github.com/ktogias/gnostoa/issues/407#issuecomment-6781282125
    title: "The Router's dispatch: implement PAO section 2.1 before #489's guarded merge is retried"
  - id: red
    resource: https://github.com/ktogias/gnostoa/issues/407#issuecomment-6781528160
    title: "The RED, its lineage table and where this design differs from the dispatch text"
  - id: verdict
    resource: ./0112-admit-merges-through-a-required-provider-neutral-merge-admission-verdict.md
    title: The merge-admission verdict, whose publication and guard this keeps
  - id: queue
    resource: ./0133-coalesce-merge-admission-requests-by-pull-request.md
    title: The per-head publication lock, which makes fixed pauses enough
x-project-knowledge:
  id: kit.decision.0135.read-a-written-merge-admission-check-back-within-a-bound
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: references
      target: /decisions/0112-admit-merges-through-a-required-provider-neutral-merge-admission-verdict.md
    - kind: references
      target: /decisions/0133-coalesce-merge-admission-requests-by-pull-request.md
---

# Read a written merge-admission check back within a bound, and cancel one that no read confirms

## Context

On 2026-11-10, the guarded merge of #489 dispatched workflow run 42908223445 (source
`refusal`). Its `invalidate` job posted the pending run 130151947086 and read it back by its
id once. That read failed, so the job recorded `FAILED`, and the run stayed `in_progress`. The
`admit` job then found no record of what was observed, and it wrote "overtaken;
re-evaluating", so the guard refused the merge. The relay keeps only the reason, not the
status of the read that failed. Read today, the run holds exactly the App, head, status and
external id it was written with, so the failure was transient. PAO's assessment (source `pao`,
section 2.1, findings F-01 and F-02) traced it to the single read after a write. The Router
routed the repair before #489's guarded merge is retried (source `route`).

## Decision

1. **The provider's answer to a write is checked first.** After a POST, the relay checks the
   answer before any read: it must be the pinned App's run of `merge-admission` on the head,
   with the written status, external id and conclusion. An answer that names anything else
   fails as `MISMATCH`, and nothing is read or written after it. The answer is what
   establishes that the run was created, and it is the only thing that names the run item 4
   may change. The read back by id stays. It checks what the provider stores, and an existing
   test holds it (`test_a_post_that_reads_back_otherwise_fails_once`). PAO's text would read
   back only where policy requires it (source `red`, difference 1).
2. **A transient read is retried, within a fixed bound.** `read_run`, which the relay and the
   guard share, reads the run again after these failures:
   - no HTTP status (a broken transport, a timeout or an unusable body);
   - 404, while the provider's index lags its write;
   - 429 or a server error.

   It pauses 0.5, 1.5 and 3.5 s, so it makes at most four reads and pauses 5.5 s in all.
   Some failures are never retried: another 4xx (a refusal), a request never sent, the
   caller's spent deadline, and a refused redirect or origin. The pauses have no jitter
   (source `red`, difference 2). Publication on one head already runs under one lock (source
   `queue`, item 3), so there are no concurrent writers to spread out. Fixed pauses also keep
   the bound exact. The guard gains the same retry and still fails closed: a run that four
   reads cannot read is still a refusal.
3. **The latest view is the fallback, by id.** When no read by id succeeds within the bound,
   the relay reads the App's latest run on the head, through the existing `app_latest`. It uses
   that run only when its id is the id written. Otherwise the read stays `UNKNOWN`. PAO
   suggested a lookup by `external_id`. The id is used instead, because unchanged evidence
   gives an older run the same external id (CodeAnt on #426), while an id names one run.
   `_post`, on both its normal and its unknown-outcome path, and `_complete` read back this
   way.
4. **A written run that no read confirms is cancelled, never left pending.** This happens only
   on `_post`'s normal path, when the answer passed item 1. If neither the read by id nor the
   latest view then confirms the run, the relay PATCHes it once to `completed` and
   `cancelled`, then raises `UNKNOWN` as before. The PATCH keeps the run's text, so the
   correlation still names the workflow run, the attempt and any nonce. A guarded merge then
   finds the run and refuses it at once, because it is not a success. The PATCH is not read
   back, since the reads are what failed. A refused or unknown PATCH raises `UNKNOWN` and says
   so. Nothing is cancelled in these cases (source `red`, difference 3):
   - a refused POST;
   - a POST whose outcome is unknown, where no answer named a run;
   - a `MISMATCH`, where the run is not this write's;
   - `_complete`, whose own write is a PATCH that is read back.

## Limits

- **The existing orphan stays.** Run 130151947086 is still `in_progress`. Only the
  `gnostoa-ma0` App, whose credential is held in a main-only environment, can complete it.
  It is not the App's latest run on #489's head, so it does not decide admission.
- **F-03 is not addressed.** The pending run's id still passes from `invalidate` to `admit`
  in a file. PAO rated this `SUSPECTED`. Once item 2 holds, a lost record still fails closed,
  as it did in run 42908223445.
- **F-04 is not measured.** Nobody has measured the provider's replication window. The 5.5 s
  bound covers the one failure observed, which is not a proof.
- **A cancelled run keeps its external id.** A cancelled verdict run may still look
  `authoritative`. Every reader also requires a completed success, so no reader admits it.
- **The guard can take up to 5.5 s longer on each read by id.** That is small next to its
  deadline.

## Verification

- `tests/test_merge_admission_relay.py::ReadBackTests` was RED on `main` `1a79ef0d` (source
  `red`): its 7 tests gave 6 failures and 9 errors, each failing for the defect, and the
  refusal characterization passed. All 7 pass after this change.
- A kill-check of the implementation added 5 tests for what its mutants showed unbound:
  - a spent deadline, a refused redirect and an origin refusal are never retried;
  - a run that reads back otherwise is never cancelled;
  - a run that reads back as no run is never looked up in the latest view;
  - the fallback serves `_complete` and `_post`'s unknown-outcome path;
  - a cancellation that fails still fails `UNKNOWN`.

  All 30 mutants of the classification, the bound, the pauses, the answer's check, the
  fallback and the cancellation then fail a test in `ReadBackTests`.
- The relay, guard and queue suites stay green.

## Consequences

- One transient read no longer ends a guarded merge's evaluation as "overtaken".
- A run left without a confirmed state is completed as cancelled, so the pull request's
  check list never keeps an evaluation that will not conclude.
- The guard's read of the record has the same bound as the relay's.
