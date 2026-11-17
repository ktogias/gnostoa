---
type: Decision
title: Admit NORMAL changes through the project's own inventory and keep DeepSource for every other class
description: "Gnostoa's declaration splits the analyzer readback: Codacy stays every class's, DeepSource's DIFF and FULL become every class's but NORMAL's, and NORMAL instead needs the project's own inventory, DIFF and FULL, complete. The readback adds this run's inventory document to the bundle, bound to the inventory job's trusted outputs, the subject, the head's tree and the protected profile; any refusal gives both project readbacks UNAVAILABLE. Every obtained finding still reaches M17, in every class."
status: draft
generated:
  by: anthropic/claude-opus-5-5
  at: "2026-10-25T16:20:00Z"
sources:
  - id: work-item
    resource: https://github.com/ktogias/gnostoa/issues/389
    title: Keep NORMAL merges possible while a vendor analyzer is unavailable
  - id: owner-scope
    resource: https://github.com/ktogias/gnostoa/issues/389#issuecomment-6384969093
    title: "The owner's selection of A0-MP1 Option A: bounded implementation and qualification, not activation"
  - id: migration-packet
    resource: https://github.com/ktogias/gnostoa/issues/389#issuecomment-6381812211
    title: "The migration packet: rows B4, B6, B7 and B8, section C's declaration and section D's cases"
  - id: slice-cut
    resource: https://github.com/ktogias/gnostoa/issues/389#issuecomment-6392516998
    title: "The measured coupling of B4, B6 and B7"
  - id: architecture-findings
    resource: https://github.com/ktogias/gnostoa/issues/389#issuecomment-6399779328
    title: "The PAO's findings on the deadline, the cross-class burden, the artifact chain and absence"
  - id: route
    resource: https://github.com/ktogias/gnostoa/issues/389#issuecomment-6399902281
    title: "The Router's consumption of those findings, and the MA0 timing scope for the owner"
  - id: owner-timing
    resource: https://github.com/ktogias/gnostoa/issues/389#issuecomment-6400598035
    title: "The owner's OWNER-389-S3-MA0-TIMING-SCOPE: the guard's 4,800 s, its test and these records, nothing more"
  - id: attempt-lineage
    resource: https://github.com/ktogias/gnostoa/pull/461#issuecomment-6401278396
    title: "The PAO's finding on a partial re-run's attempt lineage"
  - id: cutover
    resource: https://github.com/ktogias/gnostoa/issues/325#issuecomment-6401201748
    title: "The SAS's note that integrating this change is an effective policy cutover"
  - id: design
    resource: https://github.com/ktogias/gnostoa/issues/389#issuecomment-6399799382
    title: This slice's design, r3
  - id: reuse
    resource: https://github.com/ktogias/gnostoa/issues/389#issuecomment-6399931352
    title: "This slice's reuse row for the artifact: no new archive code"
  - id: lineage
    resource: https://github.com/ktogias/gnostoa/issues/389#issuecomment-6399711062
    title: This slice's prior-art checkpoint and lineage table
  - id: first-shadow
    resource: https://github.com/ktogias/gnostoa/issues/389#issuecomment-6399343052
    title: "The first real shadow run on main: 27 DIFF and 30 FULL findings"
  - id: shadow
    resource: ./0118-produce-the-diagnostic-inventory-over-a-pull-request-head-as-a-no-secret-shadow-readback.md
    title: The inventory job and its document, which this decision consumes
  - id: verdict
    resource: ./0112-admit-merges-through-a-required-provider-neutral-merge-admission-verdict.md
    title: The verdict and M17, whose semantics this decision keeps
x-project-knowledge:
  id: kit.decision.0119.admit-normal-changes-through-the-project-s-own-inventory-and-keep-deepsource-for-every-other-class
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: references
      target: /decisions/0118-produce-the-diagnostic-inventory-over-a-pull-request-head-as-a-no-secret-shadow-readback.md
    - kind: references
      target: /decisions/0112-admit-merges-through-a-required-provider-neutral-merge-admission-verdict.md
---

# Admit NORMAL changes through the project's own inventory and keep DeepSource for every other class

## Context

While DeepSource cannot analyze, no change can meet its two claims, so no change merges
without a per-change exception (source `work-item`). Decision 0118 put the project's own
inventory on the authenticated readback route as a shadow (source `shadow`). The
merge-evidence map and the protected declaration refuse a readback or an item the other
does not name, so the inventory's readbacks, the map's entries and the declaration's
items land together, in one change (source `slice-cut`). This ends Decision 0118's
shadow: the document reaches the bundle, and the inventory's failure denies the
project items rather than leaving the run unchanged.

## Decision

1. **The declaration** (source `migration-packet`, section C):
   - `analyzer-readback` keeps Codacy only, in every class;
   - `deepsource-readback` takes DeepSource's DIFF and FULL, in every class but NORMAL;
   - `project-risk-readback` takes the project's DIFF and FULL, in NORMAL alone, in
     GitHub's failure domain.

   Each item is its own claim, at a minimum of one, in exactly its requirement's
   classes.
2. **The map:** `gnostoa-inventory`'s DIFF readback gives `project-diff` as a
   diff-local read, and its FULL readback gives `project-full` as a full run.
   DeepSource's two readbacks give `deepsource-readback`'s items.
3. **The bundle:** the secret-holding readback job adds this run attempt's inventory
   document. It runs after the inventory job, whatever that job's result, unless the
   run is cancelled, and only under its unchanged admitted-event condition. It
   downloads exactly the artifact the inventory job uploaded, by that job's
   `artifact-id` output (source `reuse`), and names the document's path explicitly.
   Its runner then refuses, with both project readbacks UNAVAILABLE and the reason:
   - an inventory job that did not succeed, or a missing document;
   - an inventory job of another attempt: a re-run of only the failed jobs keeps an
     earlier attempt's outputs, so the job names the attempt it ran in, and the
     runner compares it with this run's (source `attempt-lineage`);
   - a document whose SHA-256 is not the inventory job's own output: the downloader's
     digest warning is not relied on;
   - another subject;
   - a tree other than the head's as GitHub reads it, read only once the document is
     bound; a read that fails refuses the project readbacks alone, and the vendors'
     readbacks stay in the bundle;
   - a profile other than the protected profile's digest, computed again from main's
     checkout, or a protected profile that cannot be loaded.

   The binding has one boundary: any failure of its path, a file system call, a parse,
   a GitHub read, the profile's load or a module its helpers import, is a refusal of
   the project readbacks, by its type alone. None drops the vendors' readbacks.

   Never a prior run's or attempt's document.
4. **The workflow:** the inventory job runs wherever the readback does, the admission
   call included. Its failure is not hidden. The readback job installs main's
   hash-locked runtime lock, as `merge-admission.yml`'s jobs do, before any step that
   holds a secret: the binding reads its document strictly and loads the protected
   profile.

## Consequences

- **Integrating this change is the cutover** (source `cutover`). From then on, main's
  declaration and the admission call carry the inventory, and M17 lists its findings
  in every class. Its merge is therefore the production-admission decision's, below,
  not this change's review alone.
- **What NORMAL needs:** a complete project inventory, whatever DeepSource's status.
  Every other class keeps both DeepSource claims; the guards over every combination of
  statuses prove it, for the verdict and for the merge decision.
- **M17 is unchanged, in every class** (source `architecture-findings`, finding 2). A
  finding the inventory obtains denies a mechanical, normative or critical change too,
  even though no claim of theirs needs the inventory. On `main` that is 30 standing
  FULL findings (source `first-shadow`). Activation therefore waits for the owner's
  production-admission choice among:
  - routing those findings first;
  - acquiring the inventory only for NORMAL heads, before collection;
  - a narrower FULL scope.

  A finding is never filtered after it is obtained.
- **While the source binding is `UNVERIFIED`** (M8's residual), the composite is
  INCOMPLETE. NORMAL then stays denied until the owner disposes of it.
- **The admission call becomes serial:** the inventory's 20 minutes, then the readback's
  15. With `subjects` 10, `invalidate` 10 and `admit` 20, the admission's path is 75
  minutes.
  - **MA0's guard waits 4,800 s by default:** that path plus a 5-minute margin, which
    the owner authorized within this change (source `owner-timing`). Its test models
    the serial sum, never the longer job.
  - **What 4,800 s is:** a ceiling, not a normal duration or a queue's promised wait.
    It neither diagnoses nor clears the separate admission backlog.
  - **The inventory's 900 s budget is unchanged.**

## Prior-art and reuse disposition

Source `lineage` records the checkpoint. The map, the completeness kinds and the
declaration are the existing owners'. The parser is unchanged: the split is data. The
bundle's new input reuses slice 2's bounded reader, strict loader and `unavailable`
builder, and `parse_readback`. The download reuses the pinned `download-artifact`, as
`merge-admission.yml` downloads this run's own readback. No archive reader, artifact
framework, ledger or helper is added: the artifacts API's archive redirects to another
origin, which the shared GitHub client refuses by design (source `reuse`).

## Alternatives considered

- **Keeping DeepSource for NORMAL:** NORMAL stays blocked while DeepSource cannot
  analyze, which is today's state.
- **Filtering the inventory's findings by class:** M17 lists every finding obtained;
  filtering after acquisition is refused (source `architecture-findings`).
- **A smaller collector budget in the admission call:** 15 + 15 minutes makes a
  70-minute path, which the former 3,600 s guard did not cover either, and it trades
  the inventory's coverage for time.
- **Acquiring the inventory in an earlier admission job:** it changes the admission's
  order contract, and must keep invalidation before acquisition, with nonce, subject,
  run and attempt bindings.
- **The document's own executor field:** it is an observation, and cannot
  authenticate itself.

## Evidence

The REDs and their GREENs are recorded on the Work Item (sources `design` and `reuse`).
Section D's cases are exercised as tests, against main's merge-evidence code with this
declaration. The release demonstration, a real NORMAL merge with DeepSource absent, is
the Work Item's exit, not this decision's.
