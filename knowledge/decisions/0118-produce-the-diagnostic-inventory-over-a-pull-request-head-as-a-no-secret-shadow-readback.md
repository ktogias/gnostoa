---
type: Decision
title: Produce the diagnostic inventory over a Pull Request head as a no-secret shadow readback
description: "A no-secret job of the protected analyzer readback workflow runs main's diagnostic inventory, with main's hash-locked tools, over a Pull Request head's objects fetched as data, and adapts it into a DIFF and a FULL readback of the existing contract. The adapter partitions the findings: each one obtained is in exactly one readback, and neither readback claims more than the inventory's composite. The document is a shadow: no bundle, merge-evidence map or declaration reads it, and the job's failure never changes the readback's run."
status: draft
generated:
  by: anthropic/claude-opus-5-5
  at: "2026-10-25T02:51:51Z"
sources:
  - id: work-item
    resource: https://github.com/ktogias/gnostoa/issues/389
    title: Keep NORMAL merges possible while a vendor analyzer is unavailable
  - id: owner-scope
    resource: https://github.com/ktogias/gnostoa/issues/389#issuecomment-6384969093
    title: "The owner's selection of A0-MP1 Option A: bounded implementation and qualification, not activation"
  - id: route
    resource: https://github.com/ktogias/gnostoa/issues/389#issuecomment-6381924685
    title: "The Router's A0-MP1 scope and risk contract, with P5' accepted"
  - id: migration-packet
    resource: https://github.com/ktogias/gnostoa/issues/389#issuecomment-6381812211
    title: "The migration packet: rows B3 to B6, and P5'"
  - id: slice-cut
    resource: https://github.com/ktogias/gnostoa/issues/389#issuecomment-6392516998
    title: "The measured coupling of B4, B6 and B7, and the corrected slice cut"
  - id: architecture-review
    resource: https://github.com/ktogias/gnostoa/issues/389#issuecomment-6387305292
    title: "The PAO's R1 and R4: every obtained finding keeps reaching M17"
  - id: lineage
    resource: https://github.com/ktogias/gnostoa/issues/389#issuecomment-6392545573
    title: This slice's prior-art checkpoint and lineage table
  - id: route-cut
    resource: https://github.com/ktogias/gnostoa/issues/389#issuecomment-6392658842
    title: "The Router's routing of the cut: stay on the admitted paths"
  - id: architecture-cut
    resource: https://github.com/ktogias/gnostoa/issues/389#issuecomment-6392661732
    title: "The PAO's R1 on the cut: no new runner beside the admitted owner"
  - id: pre-mutation
    resource: https://github.com/ktogias/gnostoa/issues/389#issuecomment-6392626229
    title: This slice's pre-change evidence and expected behaviour
  - id: profile
    resource: ./0117-select-the-diagnostic-inventory-s-families-through-a-protected-profile.md
    title: The protected profile the inventory runs
  - id: readback
    resource: ./0107-run-the-analyzer-readback-for-every-pull-request-head.md
    title: The authenticated readback route this job joins
x-project-knowledge:
  id: kit.decision.0118.produce-the-diagnostic-inventory-over-a-pull-request-head-as-a-no-secret-shadow-readback
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: references
      target: /decisions/0117-select-the-diagnostic-inventory-s-families-through-a-protected-profile.md
    - kind: references
      target: /decisions/0107-run-the-analyzer-readback-for-every-pull-request-head.md
---

# Produce the diagnostic inventory over a Pull Request head as a no-secret shadow readback

## Context

A0's migration needs the project's own analyzer on the authenticated readback route
(source `migration-packet`, rows B3 to B6). Under P5′, only the protected workflow may
select its producer: main's code, main's profile and main's hash-locked tools, with the
head as input data (source `route`). The merge-evidence map and the protected
declaration refuse a readback or an item the other does not name, so the readbacks
cannot join the bundle before the declaration names them (source `slice-cut`). This
slice therefore produces them beside the gate, not in it.

## Decision

1. **A no-secret job beside the readback.** `analyzer-readback.yml`'s `inventory` job has
   no environment and no secret, and reads only contents and pull requests. It admits
   the readback's events and conditions, except the merge-admission call, where nothing
   reads it yet. It binds main and the subject with the readback's own steps. It
   installs `requirements/development.lock` from main's checkout with every artifact's
   hash required, fetches the head's and the base's objects into that checkout, and
   never checks the head out. The inventory analyzes the head's own tree.
2. **The base is the merge base, through the readback's own runner.** The job runs
   `ci/analyzer_readback.py`'s `inventory` command, never a new entry point (sources
   `route-cut` and `architecture-cut`). It re-reads the Pull Request, refuses a head it no longer has (Decisions
   0091 and 0107), and compares against the merge base GitHub reports for its base
   branch, refusing a comparison that names none. The document keeps both the base
   branch's tip and that merge base.
3. **Two readbacks of the existing contract.** `tools/analyzer_inventory.py` adapts the
   record into a DIFF and a FULL readback (provider `gnostoa-inventory`), as each
   provider's adapter does. It partitions the findings: one in a path the comparison
   changed is the DIFF readback's, whatever its line, and every other one is the FULL
   readback's. Each obtained finding is listed exactly once (source
   `architecture-review`). Each readback is COMPLETE only when the composite is, for the
   requested head; otherwise it is INCOMPLETE with the composite's own reason. Without a
   comparison, DIFF is INCOMPLETE and FULL holds every finding.
4. **A shadow.** `collect` takes no path: it writes under the process's temporary
   directory, which the job sets to the runner's. The job uploads, create-only, the
   inventory and
   `gnostoa-inventory-readback.json` (its subject, both bases, the inventory file's
   SHA-256 and the two readbacks) as the readback artifact's name plus `-inventory`. It
   names exactly those two files, so neither the producers' raw reports nor a staged
   source the collector could not remove is published; the runner refuses an upload
   whose inventory is not the one the document names, or is reached through a link. Nothing
   reads them in the gate, and `continue-on-error` keeps its failure its own: an
   inventory that is refused, or written but not read back, still fails its job and
   its document records why by type, so the run's conclusion never stands for the
   inventory's success. The collect step holds no token, which is the boundary; a
   run whose environment holds one is refused if any uploaded file holds it.

## Consequences

- Every Pull Request head readback now also yields the producer route's evidence from
  real runs, before anything is activated. While the source binding is `UNVERIFIED`,
  both readbacks are INCOMPLETE. Decision 0120 derives the binding from the run's own
  record.
- Each readback run gains the lock's install and the inventory, about 12 seconds of
  analysis measured over #459's head. Decision 0107's concurrency group becomes the
  readback job's rather than the run's: a run holds a workflow-level group until every
  job ends, so the inventory beside the readback would hold the analyzers' one slot
  for its whole collection. Readbacks still queue one at a time; inventories, which
  hold no secret and spend no analyzer's rate limit, run beside them.
- Slice 3 verifies the document by run, attempt, executor and digest, adds the two
  readbacks to the bundle and the items to the map and the declaration together, and
  adds the job to the admission call.

## Prior-art and reuse disposition

Source `lineage` records the checkpoint. The job reuses the readback's admitted-event
condition, bind step and subject resolver, and `merge-admission.yml`'s hash-required
install. The adapter calls `build_readback` and `coverage` only, as the provider adapters
do. The `inventory` command is the readback runner's own, with its GitHub client, its
Pull Request read, its exact-SHA check, its create-only output and its secret-free
check; the inventory is imported only by that command. GitHub Security
Lab's "Preventing pwn requests" transfers in part: no candidate code runs here, so this
job is not the untrusted half of that pattern. `actions/checkout` v7's refusal of a fork
checkout under `workflow_run` does not apply, since the head is fetched, not checked out.
No dependency is added and nothing is copied.

## Alternatives considered

- **Adding the readbacks to the bundle now**: every merge-evidence run would refuse them
  until the declaration names their items (source `slice-cut`).
- **A separate workflow for the inventory**: the consumer would have to associate another
  run with the head, the ambiguity DeepSource's readback already suffers.
- **Running on the admission call now**: the admission would wait for a job nothing
  reads.
- **Only added-line findings in DIFF**: it would drop obtained findings (source
  `architecture-review`).

## Evidence

The pre-change evidence and expected behaviour are in source `pre-mutation`.
