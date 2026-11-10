---
type: Decision
title: Read a written merge-admission check back within a bound, and cancel one that no read confirms
description: "#407, after the guarded merge of #489 refused on 2026-11-10: the relay checks the provider's answer to a check-run write before reading the run back, and the shared read of a run by its id retries a transient failure after 0.5, 1.5 and 3.5 s, or after the client's bounded rate-limit hint, never a refusal. A run that no read by its id finds is taken from the App's latest view when that view holds the same id. A run the answer confirmed but no read confirms is completed as cancelled, keeping its correlation, the cancellation tried again within the same bound, and the failure is still raised. A refused redirect on any relay write is a refusal. The guard keeps failing closed."
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

   It pauses 0.5, 1.5 and 3.5 s, so it makes at most four reads. A rate-limited failure
   pauses at least the bounded hint the client already derives from `Retry-After` or the
   rate-limit reset, at most 60 s (Decision 0100, `tools/github_rest.py`), so a rate limit
   is waited out rather than spent inside its window (Sourcery on #490). Some failures are
   never retried: another 4xx (a refusal), a request never sent, the caller's spent
   deadline, and a refused redirect or origin. The pauses have no jitter (source `red`,
   difference 2). Publication on one head already runs under one lock (source `queue`, item
   3), so there are no concurrent writers to spread out. The loop is `within_bound`, which
   item 4's cancellation shares. The guard gains the same retry and still fails closed: a
   run that four reads cannot read is still a refusal.
3. **The latest view is the fallback, by id.** When no read by id succeeds within the bound,
   whether the reads failed for a while or one was refused, the relay reads the App's latest
   run on the head, through the existing `app_latest`. A refusal of the read by id need not
   refuse the list, and the list can only confirm the same id (Kilo on #490). It uses
   that run only when its id is the id written. Otherwise the read stays `UNKNOWN`. PAO
   suggested a lookup by `external_id`. The id is used instead, because unchanged evidence
   gives an older run the same external id (CodeAnt on #426), while an id names one run.
   `_post`, on both its normal and its unknown-outcome path, and `_complete` read back this
   way.
4. **A written run that no read confirms is cancelled, never left pending.** This happens only
   on `_post`'s normal path, when the answer passed item 1. The relay PATCHes the run to
   `completed` and `cancelled` if neither the read by id nor the latest view then confirms it.
   That covers reads that failed and a read that answered with no run at all, which
   confirms nothing either (Sourcery on #490). It then raises the read's failure as before.
   The PATCH keeps the run's text, so the correlation still names the workflow run, the
   attempt and any nonce. A guarded merge then finds the run and refuses it at once, because
   it is not a success. The same PATCH is tried again through `within_bound` while it may
   still land: its outcome is unknown, the run is not yet found (404), or the rate is
   limited (429) (Sourcery on #490). The PATCH is idempotent, so a repeat changes nothing a
   first landing did. A refusal, a refused redirect and a request never sent are final. The
   PATCH is not read back, since the reads are what failed. A cancellation that never lands
   raises `UNKNOWN` and says so. Nothing is cancelled in these cases (source `red`,
   difference 3):
   - a refused POST;
   - a POST whose outcome is unknown, where no answer named a run;
   - a run read back otherwise, which is not this write's state to change;
   - `_complete`, whose own write is a PATCH that is read back.

   `tools/github_rest.py` raises a refused redirect as itself, not as a write failure. Every
   relay write, the POST, the completion and the cancellation, therefore catches any GitHub
   error. A refused redirect, whose outcome is never unknown, fails as a refused
   publication instead of escaping the job's record (Sourcery on #490).

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
- **A read by id can take longer than its pauses.** It can make up to three more reads,
  each bounded by the client's own request timeout (30 s for the guard). It also pauses
  5.5 s, or up to the client's 60 s rate-limit hint per pause when the provider asks for
  one. `get` makes one attempt per read and retries nothing itself (Sourcery on #490). The
  guard's 4,800 s deadline bounds its discovery of the admission run and its wait for that
  run (`_discover`, `_await`). The reads after that wait were never bound by it, on `main`
  as here, so this change adds time to them but no new exposure to the deadline.
- **A cancellation can fail.** If the PATCH is refused, or has not landed after four tries,
  the run stays pending, as it did before this change. The guard still refuses it, because
  it is not a success, and the head's next evaluation writes a newer latest run.

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
- Review round 2 on #490 added REDs on the unchanged production code of `73d8c0f0`. 5
  tests gave 6 failures and 3 errors, each for its defect:
  - a read-back that answered with no run was not cancelled;
  - an unknown, not-found or rate-limited cancellation was tried once;
  - a rate-limited read paused inside the client's hint;
  - a refused redirect on a write escaped as itself.

  Two of those tests had pinned the old behaviour, and now assert the intended values. All
  pass after this change.
- The relay, guard and queue suites stay green.

## Consequences

- One transient read no longer ends a guarded merge's evaluation as "overtaken".
- A run left without a confirmed state is completed as cancelled, so the pull request's
  check list never keeps an evaluation that will not conclude.
- The guard's read of the record has the same bound as the relay's.
