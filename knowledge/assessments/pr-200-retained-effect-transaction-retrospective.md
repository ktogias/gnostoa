---
type: Source
title: PR 200 retained-effect transaction retrospective
description: Evidence-bounded retrospective of Work Item 197 and PR 200, covering the original replay defect, the evolution into a retained-effect transaction protocol, alternatives considered and not considered, measured delivery cost, accepted limitations, review failures, reusable patterns and the architectural follow-up opened as Work Item 203.
status: draft
generated:
  by: openai/gpt-5.6-sol
  at: "2026-09-08T13:40:26Z"
sources:
  - id: work-item-197
    resource: https://github.com/ktogias/gnostoa/issues/197
    title: Prevent replay of consumed preflight authority across effect-bearing qualification
  - id: change-request-200
    resource: https://github.com/ktogias/gnostoa/pull/200
    title: Prevent replay of consumed preflight authority
  - id: merge-commit
    resource: https://github.com/ktogias/gnostoa/commit/40adf792f1427569fe0db019412d4b6c3dcfe8f7
    title: Squash merge of PR 200
  - id: architectural-follow-up
    resource: https://github.com/ktogias/gnostoa/issues/203
    title: Assess a reusable retained-effect transaction primitive beyond Capsule preflight
x-project-knowledge:
  id: kit.assessment.pr-200-retained-effect-transaction-retrospective
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governed-by
      target: /decisions/0053-require-lightweight-work-item-micro-retrospection.md
    - kind: derived-from
      target: /assessments/197-preflight-authority-consumption-plan.md
    - kind: derived-from
      target: /decisions/0059-compile-declarative-experiment-capsules-over-the-owner-led-runner.md
    - kind: derived-from
      target: /runbooks/recover-a-retained-experiment-workspace.md
---

# PR 200 retained-effect transaction retrospective

## Purpose of this record

This retrospective records what PR #200 actually became, why it became that large, which
trade-offs were selected, which alternatives were rejected or merely left unevaluated, what
cost was incurred, which review practices paid for themselves, and which patterns should be
reused or avoided.

It is deliberately not a victory narrative. The work succeeded, but it also exposed a recurring
Gnostoa risk: a local-looking authority or replay bug can conceal a transaction/recovery problem
once the protected effect is valuable, non-repeatable and coupled to retained evidence.

The merged outcome is source commit
`40adf792f1427569fe0db019412d4b6c3dcfe8f7`. The exact reviewed pre-merge candidate was
`5b133d260ace7ef79a462ba84046de1edecb485e`, tree
`d6bf82f0187916315ebea855e229b7c38ea50eca`.

## Executive conclusion

PR #200 started with one narrow goal:

> Once one exact fresh preflight candidate has opened its authorised hidden-oracle effect,
> the same candidate must not be able to open that effect again after success, failure,
> abort or process crash.

That property was necessary because exact authority binding was stateless. The same authority
could pass `covers()` again even after the real effect had already started. The Phase-D D2
incident made the defect concrete: BASE had started and was irreversibly consumed, REFERENCE
never started, policy correctly prohibited retry, but the software retained no durable fact that
the authority had been spent.

The first plausible repair was a create-only consumption record. That fixed replay in isolation
but did not solve the actual operational problem once concurrency and crash were included. A
system can satisfy “at most one effect” and still be wrong if it loses the result of that one
effect, lets a stale zero-effect caller overwrite it, leaves an immutable lock from a transaction
that never committed, or interprets missing/ambiguous evidence as permission to try again.

The final implementation is therefore not merely an authority-consumption flag. It is a local,
same-workspace **retained-effect transaction protocol** with distinct durable facts for:

```text
committed snapshot
reservation
irreversible effect claim
live owner
staged transaction output
reservation seal to exact staged bytes
publication intent
```

It uses forward-only recovery after the irreversible boundary, content-bound publication,
commit-record-last ordering, explicit liveness coordination, fail-closed ambiguous state and
operator quarantine rather than rollback or inferred retry permission.

The retrospective conclusion is conditional but clear:

- **The original single-use fix was unquestionably necessary.**
- **The full retained-transaction protocol was necessary for the stronger operational contract
  that review made explicit: never repeat the protected effect merely because retained state is
  uncertain, and do not discard the only result of an effect that cannot safely be repeated.**
- If the intended requirement had truly been only “write one marker and refuse replay”, the final
  implementation would have been overbuilt. The reason it is not judged overbuilt is that the
  simpler designs were falsified against concrete evidence-preservation and concurrency cases.
- The work did **not** establish that this protocol should become a generic Gnostoa primitive.
  That architectural question is now isolated in Work Item #203.

## What we were trying to achieve

### The immediate target

`gnostoa-preflight-authority/v2` bound authority to an exact experiment, scope and candidate,
but did not model consumption. `covers()` answered “is this authority valid for this candidate?”
not “has this exact admitted attempt already crossed the irreversible effect boundary?”.

For an ordinary idempotent computation, rerunning after a crash can be acceptable. Hidden-oracle
qualification is different. The authority is not a reusable credential that means “keep trying
until successful”. It is permission for one exact effect-bearing attempt.

The required safety property was therefore:

```text
exact candidate + exact authority
        -> first real fresh effect begins
        -> candidate is consumed
        -> no later process may open a fresh effect for that candidate
```

An uninterrupted transaction may still execute its preregistered ordered BASE then REFERENCE
sequence. The prohibition applies to opening a second transaction, not to the declared arms of the
first one.

### Why the property matters

Without durable single-use semantics:

1. **Human authority silently becomes retry authority.** One approval can be reused as many times
   as the caller can present the same file.
2. **Experimental validity weakens.** Multiple runs allow accidental or intentional selection of
   a preferred result.
3. **Provenance becomes ambiguous.** BASE may come from one attempt and REFERENCE from another.
4. **A crash is misinterpreted as absence of effect.** The system cannot know whether the effect
   started, so automatic retry can duplicate a non-repeatable action.
5. **The audit claim becomes false.** “This exact approved candidate ran once” cannot be supported
   if the software does not record consumption durably.

The chosen rule is conservative by design: uncertainty after the claim does not reopen the effect.

## What changed during the work

The core discovery was that **replay protection and transaction durability are separable**.

A create-only claim can prove the irreversible boundary was opened. It cannot by itself answer:

- which caller has standing to publish;
- whether a caller is still alive;
- whether a later writer loaded stale state;
- whether a completed effect result was staged durably;
- whether staged bytes are the exact bytes the transaction committed to;
- whether canonical files are partially published;
- whether an immutable lock belongs to a transaction that actually committed;
- whether a valid-looking record is provenance or merely structurally valid;
- whether recovery should finish forward, preserve evidence or refuse.

Once those questions appeared in concrete REDs, the work stopped being a “single-use marker” bug
and became a transaction/recovery problem.

That scope growth was not planned at PR creation. It was evidence-driven.

## What was built

### 1. Durable create-only effect consumption

A candidate-keyed effect claim records the exact experiment, scope, candidate, canonical authority
identity and ordered fresh/reuse disposition. It is create-only and survives process restart.

The candidate identifier is validated as canonical lowercase 64-hex SHA-256 before either public
claim/read entry point performs filesystem work. This repair was added after review showed that
`dir_fd` does not confine `..`, `/` or absolute pathnames by itself.

### 2. Just-in-time effect boundary

The claim is not created when authority first validates. It is created after the single
deterministic pre-effect refusal path and immediately before the first real `qualify_subjects()`
effect.

That ordering avoids burning authority for software-deterministic zero-effect refusals while
retaining the conservative rule that a crash after the durable claim but before the hidden effect
actually starts may consume an unused attempt.

The structural test pins both top-level and nested adjacency so a future refusal cannot silently be
inserted after consumption.

### 3. Retained success preservation and currentness

A consumed-candidate replay cannot overwrite a previously successful retained state. A completed
qualification is reusable only when its original claim and authority relationship remain valid and
when downstream lock material is still current.

The work also forced a stronger distinction:

> A canonically valid lock is not necessarily provenance for the current retained transaction.

Lock bytes must recompute to the declared identity, and the exact lock recorded by the transaction
must agree with the state being reported.

### 4. Same-workspace arbitration

Simple “loser does not persist” fixes stopped individual overwrite paths but did not solve the
class. A stale writer hazard belongs at the persistence boundary, not at every refusal branch.

A generation/CAS-style guard was explored as a way to prevent stale commit. The RED transaction
packet then exposed that arrival-order arbitration is semantically wrong when contenders have
unequal standing: a zero-effect caller may commit first and fence out a caller whose irreversible
effect has already succeeded.

The protocol was therefore reframed around **effect-aware reservation** rather than writer arrival.

### 5. Recoverable retained transaction

`retained_commit.py` introduces a content-bound committed snapshot, short coordination critical
sections, a long-lived owner-liveness lock, durable staging and forward recovery.

Two locks have different jobs:

- the coordination lock serialises short metadata decisions;
- the owner-liveness lock answers whether the current transaction owner still exists.

Neither is human authority. Liveness is not permission.

An identical authorised waiter converges onto the winner's transaction instead of opening a new
effect. A different or authority-less contender is allowed to remain blocked without destroying
the effect-bearing transaction.

### 6. Staging, seal and publication intent

Transaction output is staged before canonical publication. The manifest is written last inside the
staging tree.

For a reserved effect-bearing transaction, the reservation is then sealed to the exact staged
manifest digest. This is the first commitment to those bytes outside the staging directory.

Publication itself uses a separate durable intent because publishing and reserving are different
acts. A caller that never reserved can still publish canonical state; for that non-reserving path,
the publication intent is the provenance that binds exact staged bytes.

Publication ordering is:

```text
publication intent
-> canonical members
-> commit record last
-> clear intent
```

The commit record is therefore evidence that the canonical snapshot completed, not an optimistic
promise written before the files.

### 7. Forward-only recovery

After the irreversible boundary:

- sufficient provenance -> finish forward;
- insufficient or damaged provenance -> preserve and fail closed;
- absence of recoverable provenance is never converted into proof that nothing happened or permission to rerun the effect.

This is the central safety decision of the PR.

### 8. Storage containment and canonical validation

The retained-transaction storage namespace is walked descriptor-relative below a trusted supplied
workspace-root anchor. The claim is intentionally narrow: it does not assert that every Capsule
filesystem helper has been converted to descriptor-relative I/O.

Readers and writers were repeatedly hardened so “unreadable”, “malformed”, “missing”, “different”
and “inconsistent” are not collapsed into one permissive false value.

The staged lock and committed lock are validated through the same canonical byte-level contract
used by execution.

### 9. Permanent crash matrix

A one-off crash probe became a permanent regression property. The matrix dynamically discovers
writes routed through the retained `_write_at` boundary and injects failure after each one.

The asserted property is not “every crash recovers”. It is:

> never a second effect; recover when provenance is sufficient; otherwise preserve and fail closed.

At candidate `0d53ed43`, eleven durable write boundaries were observed. One boundary — crash while
installing the external reservation seal after complete staging — leaves a complete staged result
that cannot be published because no durable fact outside the staging tree vouches for those exact
bytes. The effect claim remains consumed. This is an accepted fail-closed limitation, not a retryable
failure.

### 10. Governance and operator contract

Decision 0059 was extended to record the durable transaction architecture and its accepted
limitations. A dedicated runbook now tells operators how to quarantine an inconsistent workspace,
distinguish the temporal forms of the stranded pre-seal result, handle a wedged owner, and avoid
turning missing evidence into retry permission.

## Measured delivery cost

### Provider-visible size

Between admitted base `8534808e41337b4d1672ac5f991017ff4b7cce78` and exact final candidate
`5b133d260ace7ef79a462ba84046de1edecb485e`:

| Metric | Measured value |
|---|---:|
| Candidate commits | 74 |
| Changed files | 32 |
| Added lines | 10,598 |
| Deleted lines | 425 |
| Total changed lines | 11,023 |
| New test lines | ~6,496 |
| Production additions | ~3,533 |
| Knowledge/docs additions | ~569 |
| PR conversation comments at merge | 77 |

The distribution matters. More new lines were added to protocol/regression tests than to production
code. That is consistent with the assurance target: the expensive part was not expressing a file
write; it was making the crash, concurrency, provenance and recovery claims falsifiable.

### Elapsed time

| Boundary | UTC |
|---|---|
| Work Item #197 recorded | 2026-09-05 15:55:12 |
| PR #200 created | 2026-09-05 19:25:06 |
| PR #200 squash-merged | 2026-09-08 13:32:32 |

Measured wall-clock:

- Work Item record -> merge: **2 days 21:37:20**.
- PR creation -> merge: **2 days 18:07:26**.

No reliable active-person-hour telemetry was collected. This retrospective does not convert
wall-clock time, commit count or comments into invented labour hours.

### Verification cost

The final exact candidate carried:

- policy verification;
- fast verification;
- Python 3.11 compatibility;
- Python 3.12 compatibility;
- Ruff and mypy;
- regression and smoke;
- 589 tests OK / 2 skipped on the final provider run;
- a separately authorised exact-final-head `extended` run;
- final extended coverage 75.38% against a 65% floor;
- no known vulnerabilities reported by the two dependency audits;
- final human semantic verification.

The special `extended` network authority was deliberately limited to two hashed/binary-only pip
resolution dry-runs and two `pip_audit` commands. Passive connection sampling corroborated PyPI/CDN
traffic but was correctly not promoted to a perfect network-completeness proof.

## What delayed the work

### 1. The problem was mis-sized at the start

The initial mental model was “durably consume authority”. That model did not include the obligation
to preserve the only output of an irreversible effect under concurrent writers and crash.

Recognising the true problem later caused several architecture iterations that might have been
avoided if the initial design packet had stated the complete transaction invariants before code.

### 2. Branch-local fixes repeatedly treated a persistence invariant as a control-flow invariant

Several early repairs prevented one refusal path from persisting stale state. Further reviews then
found another path. The durable lesson was that stale-write protection belongs at the persistence
boundary, not scattered through callers.

### 3. Arrival-order arbitration survived longer than it should have

A generation/CAS guard can prevent some stale writes while still choosing the wrong winner. The
irreversible effect changes the ordering semantics: the effect-bearing transaction has more standing
than a zero-effect contender. That is not represented by a plain generation number.

### 4. Some tests were initially green or red for the wrong reason

Concrete examples recorded during the PR include:

- a RED test that was vacuous because an earlier preservation path intercepted the code before the
  intended guard;
- a concurrency test that signalled “waiter launched” rather than “waiter actually arrived”;
- a mock patch that ended when the owner thread returned, allowing a later waiter effect to escape
  observation;
- a path-containment read test whose generic `INVALID_CLAIM` assertion could pass without proving
  identifier validation happened before filesystem access;
- a crash-path mutation that survived because “BLOCKED + staging preserved” also matched a worse
  retained-inconsistent route; the test had to assert the exact blocker route.

Each correction improved the tests, but the iterations consumed time.

### 5. Filesystem semantics were more adversarial than the high-level design suggested

`dir_fd` does not confine arbitrary pathnames. `O_NOFOLLOW` protects the final component, not every
intermediate component. Multiple opens of the same staging name can observe different objects.
Structural validity is not provenance. `Path.is_file()` can collapse uninspectable and absent states.

The protocol required descriptor-relative storage, same-open validation/publication and exact byte
commitments because the simpler filesystem assumptions were false.

### 6. Exact-head discipline creates intentional rebinding cost

Every source, test or governance push superseded earlier review and CI bindings. This was correct,
but it meant documentation-only repairs still required fresh head verification and review wording.

The final governance stage needed several rounds because the first runbook version described only
one temporal form of the stranded pre-seal state, overclaimed “the result is genuine”, shortened the
replacement-attempt rule, and initially overstated the reservation seal as a universal provenance
route even for non-reserving publication.

### 7. Provider editing required read-after-write discipline

A PR-body edit script failed after an unmatched anchor and then uploaded the unmodified body while
the provider command itself reported success. Earlier in the session, a transient failed body fetch
could also yield an empty local copy. The protection was outcome verification, not trusting command
exit status.

This did not change production semantics but consumed review time and reinforced an existing
provider-mutation rule: **successful API/CLI completion is not sufficient evidence of intended
provider state**.

### 8. Final `extended` verification needed separately scoped network authority

The ordinary push/PR workflow intentionally skipped `extended`. Before integration, exact-final-head
quality evidence therefore needed an explicit operational network grant, process accounting and
post-run read-back. This was appropriate assurance, but it adds ceremony that could be better
automated without broadening authority.

## Alternatives actually considered

The project did **not** perform a complete design-space or ecosystem survey. The alternatives below
are those materially considered or falsified during #197/#200.

### A. Do nothing and rely on exact authority binding

Rejected immediately. Exact candidate matching proves only eligibility, not consumption. The D2
incident demonstrated the mismatch between policy (“already spent”) and software state (“covers
again”).

### B. In-memory consumed flag

Rejected by acceptance criteria. Process restart must not reopen the effect. Consumption is a
durable fact.

### C. Add a new nonce/transaction field to the authority schema

Recognised in #197 as a plausible contract-level option, but deliberately not selected. The defect
could be repaired without changing `gnostoa-preflight-authority/v2`, and schema evolution would have
expanded the public contract while still requiring durable local consumption and crash semantics.

A nonce could identify an attempt; it would not by itself preserve evidence or make an effect
exactly-once.

### D. Reuse `StageLedger` completion as the consumption token

Rejected because the semantics are different. Stage completion is intentionally resumable and may
be invalidated by input drift; effect consumption is intentionally irreversible. Overloading one
record would make either resume too strict or consumption too weak.

### E. Durable create-only effect claim only

Selected as the first repair shape, then found insufficient as the whole solution.

It correctly prevents replay, but it does not protect a successful effect result from stale writers,
does not arbitrate concurrent callers, and does not supply provenance for recoverable publication.

The claim remains part of the final design; it was not removed. It was demoted from “the solution”
to one durable fact in the solution.

### F. Patch each stale refusal branch to avoid persistence

Used tactically for early blockers, then rejected as the general pattern. The fourth stale-writer
case appeared outside the previously patched branches. The hazard belongs to commit/persistence,
not to a curated list of refusals.

### G. Generation counter / compare-and-swap persistence guard

Explored and partially implemented as a stronger persistence boundary. It detects stale snapshots,
but a pure arrival-order generation scheme still lets a zero-effect caller acquire the next commit
position and fence out a transaction whose irreversible effect has already run.

Rejected as the complete arbitration model because contenders have unequal semantic standing.

### H. Serialize the entire `prepare()` call under one exclusive lock

Not selected. It could make same-workspace races disappear but would hold a lock across long-running
and potentially failing effects, collapse liveness and write authority into one mechanism, and turn
legitimate identical callers into unnecessary global serialization.

The selected design uses short coordination locks plus a separate owner-liveness lock.

### I. Effect-aware reservation + recoverable staged commit

Selected.

This shape models the right precedence: a transaction is reserved before crossing the irreversible
boundary, the claim proves that it crossed, staging preserves the result, exact-byte commitments
make recovery auditable, and an identical waiter converges on the same transaction.

### J. Automatic rollback after claim

Rejected. Rolling back a consumed claim because publication failed would convert missing evidence
into permission to repeat an effect that may already have happened.

After claim, recovery moves forward or preserves/refuses. It does not reopen the attempt.

### K. Automatic retry of complete unsealed staging

Rejected. A complete manifest inside the staging tree is self-consistent, but before the external
reservation seal there is no durable fact outside that tree proving those exact bytes are the output
the reserved transaction committed to.

The result may be inspected manually as forensic evidence; it is not promoted to canonical output.

### L. Lease, heartbeat or timeout-based owner expiry

Rejected for v1. Time is not needed to answer local-process liveness when `flock` can hold a lifetime
lock. Adding leases would introduce clocks, expiry policy and false-death cases without solving the
main safety requirement.

A wedged owner remains an operator problem: inspect, kill if appropriate, let the kernel release the
lock, then recover normally.

### M. Distributed exactly-once or cross-workspace transaction service

Explicitly out of scope. The guarantee is one retained workspace. Copied or independently diverged
workspaces can each contain their own local state.

Building a remote coordinator would have radically widened the trust, deployment and failure
surface for a defect that was concrete in a local retained workspace.

## Alternatives not adequately evaluated

### Systematic off-the-shelf component survey

This was **not performed during PR #200**. The project therefore must not claim that no ready-made
component exists.

Classes that are obviously adjacent include:

- embedded transactional databases such as SQLite;
- local journals / write-ahead-log abstractions;
- workflow engines with durable execution;
- state-machine/event-sourcing libraries;
- file-lock and transaction helper libraries.

However, no candidate was evaluated against the exact contract during #200. Even where a component
can make metadata atomic, it still has to address the external irreversible effect, staged filesystem
bytes, exact-byte provenance, fail-closed ambiguity and the prohibition on implicit retry/rollback.

The lack of a systematic survey is a **process gap**, not evidence that the custom implementation was
wrong. The immediate defect was publication-critical and the protocol evolved through concrete local
REDs. Once the implementation grew into a 1,591-line retained-commit module plus surrounding
infrastructure, an explicit build-vs-adopt checkpoint would have been valuable.

Work Item #203 now makes that comparison mandatory before any extraction/generalisation.

### Embedded database as the primary retained store

SQLite-like storage was not seriously prototyped during #200. It could plausibly reduce metadata
atomicity and pathname-race complexity. It would not, on its own, solve publication of external
filesystem bytes or the claim-to-effect crash gap.

This should have been evaluated earlier once the design became transaction-shaped. It is now an
explicit #203 alternative rather than a post-hoc assertion.

### Generic workflow/DAG engine

Decision 0059 had already rejected a generalised workflow/DAG engine for Experiment Capsule v1 as
materially larger than the problem. #200 did not reopen that architecture because the defect was in a
narrow critical path and no generic engine had been admitted as trusted Gnostoa infrastructure.

That non-evaluation was reasonable for fixing #197, but it does not answer whether a smaller existing
retained-effect primitive should be adopted later.

## Was the final system necessary?

### Yes, for the safety contract we ended up requiring

If Gnostoa wants all of the following simultaneously:

- one authorised irreversible effect transaction;
- no replay after crash;
- preserved result when the effect succeeded;
- no stale writer able to erase that result;
- identical callers converging rather than racing;
- exact-byte publication provenance;
- crash recovery without inferred retry;
- operator-visible inconsistent evidence;

then some transaction protocol is necessary. A single marker is not enough.

### No, if the requirement is reduced to replay refusal only

If Gnostoa were willing to accept losing the only effect result, permanent manual repair after races,
and no recoverable publication, the create-only claim could have been a much smaller fix.

That would technically close a narrow reading of #197 but would be operationally poor in the exact
failure class that motivated the work. The review process correctly refused that narrower success
criterion.

## Is it useful?

Yes, immediately inside Capsule preflight.

The merged system now gives the software the same conservative semantics that policy expected during
the D2 incident. A consumed fresh candidate cannot be reopened simply because the process died or a
new authority filename was issued. Retained evidence has stronger crash, concurrency and provenance
semantics than before.

Potential reuse beyond Capsule is plausible but **not yet established**. Reusability becomes a claim
only after #203 identifies a second real consumer and compares extraction against staying local.

## What we did well

### Verification-first development was materially valuable

The important architecture changes were driven by REDs that stated observable workspace outcomes,
not by implementation preference. The transaction packet explicitly allowed different mechanisms and
forced them to satisfy the same safety/liveness properties.

### Synthetic tests protected the real experiment

No Phase-D hidden oracle was required to accept the repair. Effects were patched, counted and
attributed. This preserved the frozen experiment while still exercising replay semantics.

### Review was adversarial rather than ceremonial

Multiple review passes found real defects after prior passes had declared the current shape plausible:
retained-success destruction, zero-effect burns, authority substitution, stale writer races, false
READY, incomplete provenance, path containment and identifier-as-path bugs.

Divergence between reviewers was resolved by reproducer, not by voting.

### Mutation testing exposed weak tests

Several regressions initially passed for the wrong reason. Mutating away the intended production
claim forced the tests to prove the exact route or invariant rather than a coincidental terminal
status.

### Safety and liveness were tested separately

A system that simply refuses every concurrent caller can be safe but unusable. Adding the identical
waiter convergence requirement prevented “deny everything” from satisfying the transaction packet.

### The protocol preserves evidence rather than hiding inconsistency

The operator contract never treats malformed or ambiguous state as fresh. This aligns the software
with Gnostoa's broader evidence-preservation posture.

### Accepted limitations were measured, not buried

The pre-seal stranded-result window is recorded explicitly in Decision 0059, the runbook and the
crash matrix. It is not mislabeled as full recovery.

### Scope boundaries eventually became disciplined

The PR did not claim distributed exactly-once, did not widen the runner, did not implement #194/D0,
and did not pull the pre-existing `execution_inputs / item.id` path surface into #200 without a
separate trust decision.

### Human semantic verification remained a real gate

Agent review and provider evidence did not self-approve the normative trade-offs. The owner accepted
the conservative crash burn and pre-seal stranded-result semantics explicitly before merge.

## What could have been done better

### 1. Recognise the transaction problem earlier

The largest avoidable cost was starting from a consumption-marker mental model and discovering the
transaction model incrementally.

A better opening exercise would have been to write the state/failure table before production code:

```text
before effect
claim written / effect not yet started
effect started / no stage
partial stage
complete stage / no external seal
sealed stage
publication intent / torn canonical state
commit record complete
```

Then ask for each state: retry, recover, preserve, refuse, and who has standing.

That table would likely have revealed reservation, staging, seal and publication intent much earlier.

### 2. Write the full invariant packet before selecting mechanism

The strongest step in the PR was the later RED transaction packet. It should have been the first
architecture artifact after the initial replay RED.

Especially important invariants to state up front:

- safety: at most one effect;
- evidence: successful effect output cannot be overwritten by a zero-effect contender;
- liveness: identical legitimate waiter converges;
- provenance: publication must bind exact staged bytes;
- recovery: uncertainty never creates retry authority.

### 3. Stop patching branches sooner

The repeated pattern “this refusal must not persist” should have triggered earlier recognition that
persistence itself needed one guarded protocol.

Future rule: after the second branch-specific stale-write fix, stop and move the invariant to the
write boundary.

### 4. Introduce canonical storage helpers before protocol growth

Filesystem safety findings arrived after many retained operations already existed. A smaller
storage layer with descriptor-relative directory traversal, exact read/write semantics and
same-open validation could have reduced repeated hardening.

### 5. Perform a build-vs-adopt checkpoint when custom code crossed a threshold

No fixed LOC threshold should become policy, but once `retained_commit.py` became a substantial new
critical-path subsystem, the team should have paused to ask whether SQLite, an existing local journal
or another proven component could absorb the low-level durability work.

The absence of this checkpoint is now addressed by #203.

### 6. Validate tests against the intended failure path from the start

Every RED should include a non-vacuity assertion that proves the relevant seam was reached. Every
GREEN should ideally survive an intentionally broken implementation only when the claimed invariant
still holds.

Mutation testing should be planned with the test, not added only after suspicious success.

### 7. Keep governance current incrementally once architecture stabilises

Decision 0059 and the recovery runbook were updated late, which led to several rounds where wording
lagged implementation. Once the durable-fact model stabilised, maintaining a short architecture
truth table alongside code would have reduced the final governance correction cycle.

### 8. Automate exact-head evidence rebinding

The project correctly invalidates review/CI claims when the head moves, but manually tracking which
review binds which SHA is expensive. A reusable tool could emit a final-head packet with:

- commit/tree;
- changed-file class;
- provider runs;
- skipped suites;
- governance/human gates;
- superseded review references.

That belongs near #15's deterministic mechanics, subject to separate admission.

### 9. Harden provider text mutations as a reusable workflow

PR body edits should be compare-and-set style:

```text
fetch non-empty current body
-> verify expected anchors/head
-> compute replacement
-> write
-> read back exact expected content
```

Never upload a body that originated from a failed/empty fetch. Never accept CLI/API success as proof
of intended body state.

### 10. Measure active engineering cost

Wall-clock, commits and LOC were recoverable. Active engineering/review time was not. Future high-cost
critical slices should separate:

- implementation time;
- test/evidence time;
- review/rework time;
- governance/documentation time;
- provider/CI waiting time.

This would make build-vs-adopt decisions evidence-based instead of impressionistic.

## Reusable patterns

### Pattern: authority eligibility and authority consumption are different facts

A credential can remain valid while the authorised attempt is already spent. Model both.

### Pattern: irreversible effect creates a precedence relation

After one contender crosses the irreversible boundary, it has stronger recovery standing than a
zero-effect contender. Arrival order alone is not a correct arbitration rule.

### Pattern: permission, consumption, liveness and committed truth must not share one flag

They answer different questions and have different lifecycles.

### Pattern: commit exact bytes, not names or intentions

Request identity can say which transaction an output belongs to. Only a digest/commitment over the
actual staged bytes says what is being published.

### Pattern: intent is durable provenance for torn publication

When canonical files may be partially overwritten, a durable publication intent can explain why and
which staging source is authoritative for finishing forward.

Without intent, canonical disagreement should be treated as corruption/inconsistency, not a normal
mid-publication state.

### Pattern: commit record last

A committed-snapshot record is useful only if its existence means publication completed. Writing it
first converts a promise into false evidence after crash.

### Pattern: ambiguity is not drift

“Loaded successfully and differs” is not the same as “cannot be loaded/compared”. The latter must not
license destructive replacement.

### Pattern: canonical validity is not provenance

A self-consistent lock or record can still belong to the wrong transaction. Validate both structure
and relationship.

### Pattern: fail closed but preserve evidence

When the system cannot prove safe recovery, retain the conflicting artifacts for operator diagnosis.
Do not clean them up merely to regain forward progress.

### Pattern: test safety and liveness separately

“At most one effect” is insufficient if the only implementation is “block everyone forever”.

### Pattern: concurrency tests must prove overlap

Thread creation is not evidence of concurrent arrival. Use explicit events at the semantic seam.

### Pattern: mocks must span the whole observation window

A global effect patch that is removed before all concurrent actors finish can create false confidence
that no second effect occurred.

### Pattern: RED tests need non-vacuity guards

A failing or passing terminal status is not enough. Prove the intended path, side effect and/or
blocker identity was reached.

### Pattern: crash matrices should discover boundaries dynamically

Hard-coded boundary counts go stale. Instrument the durable-write seam so newly added writes enter
the matrix automatically.

### Pattern: validate identifiers before pathname construction

`dir_fd` is an anchor, not a pathname sandbox. Validate externally supplied names before any
filesystem action.

### Pattern: containment claims must be narrow and literal

If only retained-transaction descendants are descriptor-relative, say exactly that. Do not promote a
local property into a repository-wide security claim.

### Pattern: read-after-write for provider mutations

Provider success means the operation completed, not necessarily that the intended state was produced.
Re-read the authoritative provider state.

## Antipatterns exposed

### Antipattern: “valid authority” implies “unused authority”

Eligibility without consumption state is replayable.

### Antipattern: one mutable stage record owns both resumable progress and irreversible consumption

Those semantics conflict.

### Antipattern: arrival-order winner selection for unequal contenders

The caller that writes first is not necessarily the caller whose outcome must be preserved.

### Antipattern: branch-specific stale-write patches

They treat manifestations, not the persistence invariant.

### Antipattern: generation counter as complete transaction semantics

A generation can prove staleness; it cannot encode effect standing, liveness, byte provenance or
forward recovery.

### Antipattern: immutable final artifact written outside the transaction

A lock that survives a transaction which never committed can permanently poison future readiness.
Stage immutable output and publish it transactionally.

### Antipattern: “missing” as the fallback for unreadable

An unreadable committed record is not evidence that no record exists.

### Antipattern: repeated opens assumed to name the same object

Concurrent replacement can make separate opens observe different valid objects.

### Antipattern: structural success used as provenance

Self-consistent bytes can still be substituted from another transaction.

### Antipattern: hand-picked field comparison without accounting

As schemas grow, omitted fields silently become ungoverned. Partition all fields by role and pin that
partition in tests.

### Antipattern: automatic retry as generic recovery

Retry is unsafe after a non-repeatable effect unless the system can prove the effect never started.

### Antipattern: test passes because the wrong failure route is also BLOCKED

For fail-closed systems, many bugs still end in BLOCKED. Tests must distinguish the intended refusal
from a more severe inconsistent-state path.

### Antipattern: generalising after one consumer because the code “looks reusable”

A reusable abstraction needs a second concrete consumer and a responsibility boundary. Otherwise
extraction creates abstraction debt.

## Best-practice sequence for future non-repeatable effects

Before implementing another effect-bearing retained workflow:

1. **Name the irreversible effect exactly.** What external or hidden action cannot safely be repeated?
2. **Define the unit of authority.** What exact candidate/attempt is authorised once?
3. **Separate durable facts.** At minimum ask whether eligibility, reservation, consumption, liveness,
   staged result, byte provenance and committed state need distinct records.
4. **Enumerate crash states before code.** For each durable boundary decide recover / preserve / refuse /
   retry, and justify retry explicitly.
5. **State safety and liveness properties independently.**
6. **Write RED outcome tests before choosing mechanism.** Avoid tests that prescribe CAS, locks or a
   particular file layout unless that mechanism is itself the contract.
7. **Add non-vacuity and mutation checks to the RED packet.**
8. **Choose the smallest storage primitive that can satisfy the packet.** Include a build-vs-adopt
   checkpoint if the custom subsystem becomes substantial.
9. **Bind exact staged bytes before publication.**
10. **Write the committed marker last.**
11. **Preserve ambiguous evidence.** Cleanup is not recovery.
12. **Keep operator disposition explicit.** Manual quarantine must not imply fresh retry authority.
13. **Run a dynamic crash matrix.**
14. **Record accepted unrecoverable windows canonically.**
15. **Bind final CI/review/human verification to one exact head.**

## What should remain local to PR 200 / Capsule for now

The following should not be generalised merely because the protocol works:

- `gnostoa-preflight-authority/v2` and candidate schema semantics;
- BASE/REFERENCE fresh/reuse disposition;
- hidden-oracle qualification terminology;
- Capsule stage names;
- Experiment Lock field policy;
- Phase-D-specific replacement-attempt rules beyond their generic “new admitted attempt” principle;
- the current filesystem layout as a universal API.

The follow-up must extract invariants, not copy Capsule nouns into a generic module.

## Architectural follow-up

Work Item #203, **Assess a reusable retained-effect transaction primitive beyond Capsule preflight**,
was created from this retrospective.

Its default is not “extract”. Its task is to decide among:

1. keep the protocol Capsule-specific;
2. extract a narrow local retained-effect transaction library;
3. reconcile the mechanics into the broader deterministic workflow programme in #15;
4. adopt an existing component if one satisfies the contract at lower ownership cost;
5. use an embedded database as storage substrate while keeping the effect/provenance protocol explicit;
6. use event sourcing only if it proves a concrete advantage rather than adding mechanism.

Before any extraction, #203 requires:

- a second real consumer or an explicit conclusion that none exists;
- partition of universal invariants vs Capsule policy vs filesystem implementation choice;
- comparison against the same safety and liveness properties;
- evaluation of at least one mature existing component or a concrete explanation why no candidate is
  suitable;
- quantified expected reduction in ownership/review cost;
- reconciliation with #5 and #15;
- a separate Decision and RED evidence if implementation is later admitted.

This is the correct follow-up because PR #200 proved the concrete protocol but did not prove the
abstraction.

## Final assessment

PR #200 was expensive for a bug whose first description sounded small. The cost came from discovering
that the true protected asset was not the authority file but the **integrity of one authorised,
non-repeatable effect and its retained evidence across concurrency and crash**.

The work was slower than it could have been. The team should have recognised the transaction shape
earlier, written the full invariant matrix before mechanism, surveyed existing durable substrates at
the point custom code became substantial, and designed some tests with non-vacuity/mutation resistance
from the start.

The work was also technically productive. Repeated adversarial review converted hidden assumptions
into explicit invariants. The final protocol is materially stronger than the original repair: it
prevents replay, preserves successful effect evidence, makes stale writers fail, distinguishes
liveness from permission, binds exact bytes before publication, recovers forward when provenance is
sufficient, preserves inconsistent evidence when it is not, and records the one measured crash window
it cannot safely recover.

The most important lesson is not a particular lock or file layout. It is this:

> **For a non-repeatable effect, uncertainty after the irreversible boundary is an evidence problem,
> not a retry signal.**

And the second lesson is equally important:

> **Do not generalise a hard-won local protocol until a second consumer proves that the abstraction is
> real and an external-component survey shows that owning it is cheaper and safer than adopting it.**
