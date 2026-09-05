---
type: Source
title: Work Item 190 Capsule qualification and network-envelope integration repair plan
description: Bounded repair plan for the three Capsule-System integration defects found by real Phase-D consumer validation - python-pytest oracle staging, immutable relay-image binding for restricted execution, and forced qualification network isolation.
status: draft
generated:
  by: claude/opus-5
  at: "2026-09-05T00:15:00Z"
sources:
  - id: repair-work-item
    resource: https://github.com/ktogias/gnostoa/issues/190
    title: Repair Capsule qualification staging and network-envelope integration gaps
  - id: consumer-evidence
    resource: https://github.com/ktogias/gnostoa/issues/183#issuecomment-5546841400
    title: Capsule-System consumer validation of frozen Phase-D
  - id: capsule-decision
    resource: https://github.com/ktogias/gnostoa/blob/main/knowledge/decisions/0059-compile-declarative-experiment-capsules-over-the-owner-led-runner.md
    title: Compile declarative Experiment Capsules over the owner-led runner
x-project-knowledge:
  id: kit.assessment.190-capsule-integration-repair-plan
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governed-by
      target: /decisions/0059-compile-declarative-experiment-capsules-over-the-owner-led-runner.md
---

# Work Item 190 Capsule qualification and network-envelope integration repair plan

Starting revision: `d32d81d261f633d5c4d162c517179de07338c573`, tree
`a29d3b77e0da371c97877e9822a01604b667472c`. Branch
`agent/repair-capsule-qualification-integration`.

Governed by Decision 0059. No new Decision is required: none of the three repairs
widens the #164 runner boundary or the public experiment model. Each consumes an
existing `tools/experiment` contract rather than changing it.

## Why

Real consumer validation of the frozen Phase-D material against the merged Capsule
System v1 found three integration defects. They are defects of this layer, not of
the Phase-D semantics, and the semantic gates behaved correctly throughout.

## A. Deterministic safe oracle staging

Qualification copies the owner-private oracle under its original basename and hands
that name to pytest. An interior dot makes pytest resolve a dotted module path and
collection fails before any case runs.

The repair does not sanitise owner basenames into module identifiers. The
`python-pytest` adapter owns a reserved, qualification-only staging name derived from
the oracle digest, so the staged name never depends on what the owner called the file.
It is safe by construction against interior dots, a leading digit, Python keywords and
collision with ordinary subject modules.

Properties: staged bytes byte-identical to the source oracle; the authoritative
semantic identity remains the SHA-256 of the original private bytes; the staged name
participates in `harness_identity` through the invocation, so changing it invalidates
qualification receipt reuse; fail closed if the reserved destination already exists
with different bytes; adapter-scoped, so `node-vitest` and `generic-command` keep the
original basename and Node's exact-filename include behaviour is untouched.

## B. Immutable relay-image binding for restricted execution

The runner requires an immutable `runtime.relay_image` digest whenever the profile
network mode is `restricted`, and the spec has no way to declare one, so any spec
carrying a restricted experimental envelope cannot produce a runnable profile.

The repair adds the smallest optional declarative field, `task.runtime.relay_image`,
required only when experimental `network.mode` is `restricted`, carried into the
execution profile exactly as the runner expects and bound into the frozen identities.
No discovery, no tag-to-digest resolution, no pull, no default.

## C. Forced qualification network isolation

Qualification profiles derive their network envelope from `experiment.resources`, so
coordinator-private oracle qualification can inherit experimental executor egress.

For this slice the qualification envelope is mechanically forced to
`{"mode": "none", "allow": []}`. It is not a default and no spec field can opt
qualification into egress. Qualification never receives a relay image. Any future
qualification egress is a separately designed and authorised capability.

## D. Tests and verification

Focused RED precedes implementation and is retained as a distinct commit: the
interior-dot collection failure as the canonical case plus the leading-digit, keyword
and subject-module-collision classes; restricted execution unable to bind a relay
identity, with fail-closed cases for a missing and for a non-immutable relay image;
and qualification inheriting a restricted envelope. Synthetic material only; no
Phase-D oracle bytes, task identifiers or hidden material enter the repository or
execute. OCI characterisation continues through
`tools.experiment.execution.run_profile_command`; no second isolation path is added.

The #188 trust-domain no-leakage tests remain mandatory and green, and `node-vitest`
with the OCI backend remains fail-closed and unsupported.

## E. One draft PR

Local verification, then one draft pull request against `main`, then stop. Merge is
not authorised by this slice.

## Out of scope

Phase-D rerun of D1 or D3, D2/D4 semantic remediation, any hidden-oracle execution,
`tools/experiment` semantic change, a generalised networking capability, and the #189
documentation cleanup of the stale runbook wording and the Decision 0059 adapter bound.
