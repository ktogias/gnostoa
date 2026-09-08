---
type: Runbook
title: Recover a retained experiment workspace
description: Decide what to do when a retained experiment workspace reports an inconsistent state, holds a completed result it will not publish, or is held by an owner that never finishes, without ever converting missing evidence into permission to run a hidden oracle again.
status: draft
generated:
  by: claude/opus-5
  at: "2026-09-08T00:00:00Z"
sources:
  - id: preflight-consumption-work-item
    resource: https://github.com/ktogias/gnostoa/issues/197
    title: Prevent replay of consumed preflight authority
  - id: capsule-work-item
    resource: https://github.com/ktogias/gnostoa/issues/187
    title: Build declarative Experiment Capsule preparation and qualification system
x-project-knowledge:
  id: kit.runbook.recover-a-retained-experiment-workspace
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governed-by
      target: /decisions/0059-compile-declarative-experiment-capsules-over-the-owner-led-runner.md
---

# Recover a retained experiment workspace

## Outcome

A retained workspace that refuses to proceed is diagnosed and given an explicit human
disposition, with its evidence intact. Nothing in this runbook repairs a workspace by
rewriting its records, and nothing in it turns absent or ambiguous evidence into
permission to run a hidden oracle a second time.

## Preconditions

This runbook applies to a retained experiment workspace that will not advance:

- `status` reports `BLOCKED` with a `retained-state-inconsistent` blocker.
- A preparation refuses with `retained-state-inconsistent` or
  `retained-transaction-reserved` and will not advance on retry.
- A preparation refuses with `preflight-candidate-already-consumed` while the
  workspace holds no `READY_FOR_OWNER_REVIEW`.
- A preparation waits and never returns.

It assumes read access to the workspace and the authority to decide the disposition of
a spent candidate. It does not assume, and never requires, authority to run a hidden
oracle.

## The rule that governs every case

**Missing, damaged or ambiguous evidence is never a reason to run the oracle again.**

The effect claim under `preflight-effects/` records that an irreversible qualification
began. It is deliberately not removable as part of recovery. If a candidate's claim
exists, that candidate is spent — whatever else is missing, and however inconvenient
that is. Reaching readiness again requires a new prospective experiment identity, a
newly observed candidate and a new exact authority, exactly as
[decision 0059](../decisions/0059-compile-declarative-experiment-capsules-over-the-owner-led-runner.md)
requires.

## Do not

- Do not delete, move or edit anything under `preflight-effects/`.
- Do not edit `.retained-commit.json`, `.retained-reservation.json`,
  `.retained-publication.json`, `stages.json`, `experiment-state.json` or
  `experiment.lock` to make a refusal go away. Every one of those records is checked
  against the others; editing one to match another destroys the disagreement that is
  the evidence.
- Do not delete `.retained-transactions/`. It holds the only copy of results that were
  completed but not published.
- Do not re-run a preparation "to see if it clears". It will not, and a preparation
  that did clear would be the thing to worry about.

## Procedure

### Quarantine first

Before inspecting, take a copy that preserves the exact bytes and stop further
preparations against the original:

```sh
cp -a "$WORKSPACE" "$WORKSPACE.quarantine.$(date -u +%Y%m%dT%H%M%SZ)"
```

Inspect the copy. The original is the record.

### Diagnose

Read, in this order, and record what each says:

1. `.retained-commit.json` — which transaction last committed, and the digests it
   vouches for.
2. `.retained-publication.json` — present only if a publication was under way, naming
   the transaction and the exact manifest it was publishing.
3. `.retained-reservation.json` — present only if a transaction held the effect
   boundary, naming the candidate, the authority and, once sealed, the staged manifest
   it is committed to.
4. `.retained-transactions/<id>/manifest.json` — the staged output of that transaction,
   if any.
5. `preflight-effects/<candidate>.json` — whether the irreversible boundary was crossed
   for this candidate.

### Dispositions

#### A completed result that cannot be published

**Signs.** A reservation exists with no `staged_manifest_sha256`; its staging directory
holds a complete `manifest.json`; the effect claim for that candidate exists; retries
report `preflight-candidate-already-consumed`.

**What happened.** The transaction ran the oracle, staged its output completely, and
stopped before sealing the reservation to those exact bytes. The seal is the first
commitment made outside the staging directory, so nothing vouches for that output.

**Disposition.** This is a known accepted limitation of the protocol, not a fault in
the workspace. The result is genuine and is preserved under
`.retained-transactions/`; it is not published because nothing establishes that those
bytes are the ones the transaction produced. The candidate is spent.

The owner decides between reading the staged output as evidence in its own right —
recording explicitly that it was recovered by hand and never carried the protocol's
provenance — and re-running under a new candidate and authority. **Publishing the
staged bytes into the workspace by hand is not one of the options**: it would create
exactly the appearance of provenance the protocol refused to assert.

#### An inconsistent workspace

**Signs.** `retained-state-inconsistent`, with a detail naming which record disagrees.

**What happened.** A record and the files it describes do not match. Either a
publication was interrupted in a way that could not be finished forward, or something
outside the protocol modified the workspace.

**Disposition.** Establish which. Compare the digests in `.retained-commit.json`
against the files, and check whether `.retained-publication.json` is present. An
interrupted publication that could be finished forward would already have been; if it
was not, the detail says why — the staged output is incomplete, contradicted by its
reservation, or based on a workspace that no longer exists.

If the disagreement cannot be explained by an interruption, treat the workspace as
modified outside the protocol and stop. Do not reconcile the records. The workspace is
evidence about what happened to it.

#### A workspace held by an owner that never finishes

**Signs.** A preparation waits and does not return. A reservation exists and its
`.retained-transactions/<id>/owner.lock` is held.

**What happened.** The reserving process is alive and has not finished. There is no
lease and no timeout, deliberately: an expiry that handed a second caller the right to
an effect the first is still performing would be the failure this design exists to
prevent.

**Disposition.** Identify the holding process:

```sh
fuser -v "$WORKSPACE/.retained-transactions/"*/owner.lock 2>/dev/null
```

If it is genuinely wedged, terminate it. Releasing its lock makes the reservation
abandoned, and the next preparation resolves it under the rules above — finishing it
forward if its output is complete and sealed, releasing it if nothing irreversible
happened, and preserving it otherwise. **Do not delete the lock file to break the
wait**: the lock is what tells every other caller that the owner is still alive.

## Recovery

Recovery of this runbook itself — what to do when the steps above cannot be completed.

If quarantine cannot be taken because the filesystem is failing, stop and escalate;
do not proceed with diagnosis against a workspace that may be losing bytes.

If a disposition was applied and the workspace still refuses, do not apply a second
one. Two hand dispositions against the same workspace cannot both be reconstructed
afterwards. Restore the quarantined copy, record what was attempted, and treat the
workspace as evidence rather than as a workspace.

If a record was edited before this runbook was consulted, the workspace can no longer
be diagnosed: the disagreement that would have identified what happened is gone.
Restore from quarantine if a copy exists, and otherwise retire the workspace and
re-run under a new candidate and authority. An edited workspace must never be
presented as a recovered one.

## Verification

The disposition is complete when all of the following hold, checked against the
original workspace rather than the quarantined copy:

- `preflight-effects/` contains exactly the claims it contained before, byte for byte.
- No record under the workspace root was edited by hand.
- `status` reports either `READY_FOR_OWNER_REVIEW` reached without intervention, or a
  refusal whose blocker matches the diagnosis recorded above.
- If a completed result was recovered by hand from `.retained-transactions/`, the
  record of that says explicitly that it was recovered by hand and did not carry the
  protocol's provenance.
- The disposition, its reasoning and the quarantine path are written down where the
  experiment's evidence lives, not only in a terminal.

A workspace is recovered when its records agree, not when it reports
`READY_FOR_OWNER_REVIEW`. A refusal that correctly preserves evidence is a recovered
workspace. Readiness that required a record to be edited is not.

## Related

- [Prepare an experiment capsule](prepare-an-experiment-capsule.md)
- [Run a bounded owner-led experiment](run-owner-led-experiment.md)
