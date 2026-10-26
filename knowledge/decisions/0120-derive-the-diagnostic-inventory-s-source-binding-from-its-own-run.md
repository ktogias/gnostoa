---
type: Decision
title: Derive the diagnostic inventory's source binding from its own run
description: "The diagnostic inventory's source binding is BOUND only when its own run shows four things. P1: the frozen tree was staged and observed unchanged, and the subject re-read as its own. P2: each launched producer answered its pin in the producer tree's development lock. P3: the producer tree's profile governed. P4: each launched run's environment endpoints are equal. A BOUND record names the owner's four accepted residuals instead of the binding's gap. An unmet predicate keeps the record UNVERIFIED, with that gap and the predicate named. Binding never completes a PARTIAL or INCOMPLETE family."
status: draft
generated:
  by: anthropic/claude-opus-5-5
  at: "2026-10-26T01:38:55Z"
sources:
  - id: work-item
    resource: https://github.com/ktogias/gnostoa/issues/389
    title: Keep NORMAL merges possible while a vendor analyzer is unavailable
  - id: owner-scope
    resource: https://github.com/ktogias/gnostoa/issues/389#issuecomment-6384969093
    title: "The owner's selection of A0-MP1 Option A: bounded implementation and qualification, not activation"
  - id: owner-m8
    resource: https://github.com/ktogias/gnostoa/issues/389#issuecomment-6405841272
    title: "The owner's M8 Option A: four accepted residuals, for a bounded diagnostic source-binding claim only"
  - id: route-m8
    resource: https://github.com/ktogias/gnostoa/issues/389#issuecomment-6405959599
    title: "The Router's routing of the existing P1–P4 derivation"
  - id: cut
    resource: https://github.com/ktogias/gnostoa/issues/389#issuecomment-6405993098
    title: The smallest P1–P4 cut
  - id: route-cut
    resource: https://github.com/ktogias/gnostoa/issues/389#issuecomment-6406057200
    title: "The Router's scope alignment of the cut, and its required preparation"
  - id: migration-packet
    resource: https://github.com/ktogias/gnostoa/issues/389#issuecomment-6381812211
    title: "The migration packet: section B′, the M8 residual"
  - id: profile
    resource: ./0117-select-the-diagnostic-inventory-s-families-through-a-protected-profile.md
    title: The protected profile, and the binding it left UNVERIFIED
  - id: shadow
    resource: ./0118-produce-the-diagnostic-inventory-over-a-pull-request-head-as-a-no-secret-shadow-readback.md
    title: The shadow readback, which installs main's development lock
x-project-knowledge:
  id: kit.decision.0120.derive-the-diagnostic-inventory-s-source-binding-from-its-own-run
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: references
      target: /decisions/0117-select-the-diagnostic-inventory-s-families-through-a-protected-profile.md
    - kind: references
      target: /decisions/0118-produce-the-diagnostic-inventory-over-a-pull-request-head-as-a-no-secret-shadow-readback.md
---

# Derive the diagnostic inventory's source binding from its own run

## Context

Decision 0117 kept the inventory's source binding `UNVERIFIED` until the M8 residual
was disposed of (source `profile`, item 4). Every inventory was therefore INCOMPLETE,
however clean its run. The owner has accepted exactly four limitations, for a bounded
diagnostic source-binding claim only (source `owner-m8`):
- import resolution and the loaded paths outside RECORD-owned roots;
- a standard library bound to the Python version rather than content-hashed;
- continuity between the endpoint observations;
- listed files without content hashes.

The Router routed the derivation already specified in source `migration-packet`, in
the existing owner, with its predicates demonstrated and nothing new built for them
(sources `route-m8` and `route-cut`). A risk choice alone verifies nothing.

## Decision

1. **One derivation, from the run's own record.** `tools/quality_evidence.py` derives
   the binding after the producers and the subject's re-read. It reads only the run's
   record and the producer tree, never the analyzed tree:
   - **P1, the subject:**
     - the record's `tree_binding` is `EXACT_TREE_STAGED`: `tools/exact_tree` staged
       the frozen tree and observed it unchanged after the producers;
     - the subject's Git metadata was re-read as its own after collection.
   - **P2, the tools:** each launched producer run's `version`, its own `--version`
     under `-I`, equals its pin in the producer tree's
     `requirements/development.lock`. The pins are read through
     `tools.requirements_lock.locked_requirements`. A missing pin, an unreadable
     version and an unreadable lock are each unmet.
   - **P3, the profile:** the profile's recorded origin is `producer-tree`. A profile
     supplied through the private path never binds, whatever its content.
   - **P4, the environment:** each launched run's `environment_observation` status is
     `endpoints_equal`, as `tools/python_environment_observation.py` observes it. A
     launched run without one is unmet.
2. **BOUND.** When all four hold:
   - `source_binding` is `BOUND`;
   - `source.accepted_residual` names the decision
     `OWNER-389-M8-RISK-FOLLOWUP-6405282317-51519EC6-v1` and its four limitations;
   - the binding's residual is not a coverage gap.

   The member is additive and `null` otherwise, so the schema stays
   `gnostoa-diagnostic-inventory/v3`.
3. **UNVERIFIED.** When any predicate is unmet:
   - the existing residual gap stays as it is, chosen by `tree_binding` (the Router's
     G451-R9 on #389);
   - one gap is added per unmet predicate, `source binding P<n> unmet: <detail>`.
4. **One conjunct of the composite.** The composite stays the families' conjunction
   with the inventory's shared gaps:
   - a PARTIAL family keeps a BOUND inventory PARTIAL;
   - an INCOMPLETE family or an unknown comparison keeps it INCOMPLETE;
   - every obtained finding is still listed and still denies (M17).
5. **No admission.** BOUND states what the run observed. It does not admit the
   executing generation. The protected producer eligibility (P5′), the readback's run,
   attempt, executor, subject, tree, profile and artifact authentication, and the
   activation are unchanged.

## Consequences

- **On a real run whose predicates hold, the binding no longer keeps the composite
  INCOMPLETE.** #460's and #461's runs showed:
  - `EXACT_TREE_STAGED`;
  - mypy 2.3.0 and Ruff 0.16.0, the pins;
  - the producer tree's profile;
  - equal endpoints.

  Typing stays PARTIAL on every head while `ci/merge_admission_guard.py`'s import is
  unresolved, so this change alone makes no real readback COMPLETE.
- **The A→B→A case now binds on the protected route.** There, the environment changes
  during a producer and is restored before the last observation, which equal endpoints
  cannot see. The record names continuity as an accepted residual (source `owner-m8`,
  limitation 3). That case was UNVERIFIED before.
- **An in-process family has no launched producer.** The complexity metric's identity
  is the producer tree's own code, which the protected producer eligibility binds, not
  P2 or P4.
- **The fixture's producers answer 1.0.0 by default,** which no pin matches. A test
  that does not set the pins records P2 unmet.

## Prior-art and reuse disposition

Each predicate is read from its existing owner:
- P1: `tools/exact_tree` and `_metadata_rebound`;
- P2: `_producer_version` and `tools.requirements_lock.locked_requirements`;
- P3: `load_diagnostic_profile`'s recorded origin;
- P4: `tools/python_environment_observation.py` and `_environment_observation`.

No module, tracer, scanner or dependency is added. `tools/check_runtime_lock.py` reads
the runtime lock against an image's declaration, which is not this question.

## Alternatives considered

- **Promoting on the owner's acceptance alone:** a risk choice is a residual
  disposition, not a predicate (source `owner-m8`).
- **Tracing the producers' imports or hashing their loaded files:** that is a tracer,
  which the route excludes (source `route-m8`). Its loss is limitation 1.
- **Reading the pins from the analyzed tree's lock:** the candidate would choose its
  own pins, which P5′ forbids.

## Evidence

The pre-change evidence and expected behaviour are in the slice's admission record on
#389. Qualification exercises the real producer path, not only a constructed record.
