---
type: Decision
title: Bound tests/test_tools.py's two complex functions by extraction and repair its typing
description: "T1 of #389's complete closure: tests/test_tools.py's 12 mypy diagnostics are repaired, and _invokes_shared_verification_suite and test_github_provider_surface_is_active_and_owned are brought below the complexity threshold by extraction within the same file, preserving fail-closed recognition, every assertion and each test's identity; it is composed with the Docker identity repair in the critical cutover."
status: draft
generated:
  by: anthropic/claude-opus-5-5
  at: "2026-10-31T17:33:00Z"
sources:
  - id: work-item
    resource: https://github.com/ktogias/gnostoa/issues/389
    title: Keep merges possible while a vendor analyzer is unavailable
  - id: owner-closure
    resource: https://github.com/ktogias/gnostoa/issues/389#issuecomment-6542636396
    title: "The owner's direction: resolve every recorded problem, carry no debt, activate as soon as possible"
  - id: owner-admission
    resource: https://github.com/ktogias/gnostoa/issues/389#issuecomment-6546743036
    title: "The owner's selection of A: T1 admitted for implementation and qualification, composed with Docker in the critical cutover"
  - id: route
    resource: https://github.com/ktogias/gnostoa/issues/389#issuecomment-6546693623
    title: "The Router's prepared decision and its critical classification"
  - id: coupling
    resource: https://github.com/ktogias/gnostoa/issues/389#issuecomment-6546328213
    title: The Docker front's measured coupling to this file
  - id: preparation
    resource: https://github.com/ktogias/gnostoa/issues/389#issuecomment-6546596790
    title: T1's prepared admission delta, extraction boundaries and baseline
  - id: lineage
    resource: https://github.com/ktogias/gnostoa/issues/389#issuecomment-6546798582
    title: T1's exact-base lineage and pre-change evidence
  - id: profile
    resource: ./0117-select-the-diagnostic-inventory-s-families-through-a-protected-profile.md
    title: The protected profile whose typing and complexity families this answers, unchanged
  - id: n1a
    resource: ./0123-repair-the-typing-of-seventeen-test-modules.md
    title: The first test-typing group, whose means this reuses
  - id: inheritance
    resource: ./0099-route-the-architecture-inheritance-gate-from-source.md
    title: The architecture inheritance gate
x-project-knowledge:
  id: kit.decision.0124.bound-test-tools-two-complex-functions-and-repair-its-typing
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: references
      target: /decisions/0117-select-the-diagnostic-inventory-s-families-through-a-protected-profile.md
    - kind: references
      target: /decisions/0123-repair-the-typing-of-seventeen-test-modules.md
    - kind: references
      target: /decisions/0099-route-the-architecture-inheritance-gate-from-source.md
---

# Bound tests/test_tools.py's two complex functions by extraction and repair its typing

## Context

The Docker identity repair must change `tests/test_tools.py:4467`, which pins `USER kit`
(source `coupling`). On protected main `58c75e3c53652fb07301d9e84c9bcd7ca9da3e2e`, the
current profile's DIFF reads a changed file whole for typing. It also acquires every function
a change adds a line to, for complexity (source `profile`). The real collector's DIFF over a
probe of the Docker files lists exactly this file's 12 typing diagnostics. Four of them sit
inside two functions above the complexity threshold of 15:

- `_invokes_shared_verification_suite`, complexity 25: the fail-closed recognizer of the
  workflows' `./ci/verify <suite>` invocation;
- `test_github_provider_surface_is_active_and_owned`, complexity 17: coverage for the
  guardrails `accountable-review-ownership` and `immutable-provider-ci-adapters`.

Repairing them touches both functions. So the Docker repair needs this file clean first.
The owner admitted that finite scope as T1, composed with Docker in the critical cutover
(source `owner-admission`). Its class is `critical`, because the recognizer is the oracle of
two security guardrails' coverage (source `route`).

## Decision

1. **The 12 typing diagnostics are repaired in this file** by the means of Decision 0123
   (source `n1a`). Those are:
   - a narrowing assertion where a value is used untyped;
   - a renamed local, where one name held two types;
   - a test double that declares the interface it replaces.

   There is no `cast`, `type: ignore`, added `Any`, ellipsis or skip.
2. **`_invokes_shared_verification_suite` is brought below 16 by extraction within the same
   file.**
   - Its option-parsing loop and its approved mount, environment and user sets become
     private helpers.
   - The final checks stay in the function.
   - Every input it rejects today is still rejected.
3. **`test_github_provider_surface_is_active_and_owned` is brought below 16 by extracting
   private helper methods of its test class,** one per checked surface. The test's id and
   every assertion stay.
4. **Nothing else changes.**
   - Production code is untouched, including `tools/knowledge_common.py`'s `load_yaml`.
   - So are the file's third complex function, public APIs, the profile and the threshold.
   - Beyond the file, only this record and its line in `knowledge/index.md` change.
   - The existing tests' gaps are not closed here (source `lineage`). They are reported
     separately, because new assertions are outside this scope.

## Verification

- **Before** (source `lineage`):
  - The probe's DIFF lists these 12 typing diagnostics, and the two functions measure 25
    and 17.
  - The module runs 142 tests, all ok, with the checkout's own `tools` imported.
  - The mutation baseline kills 11 of 17 mutants, and names its 6 survivors.
- **After, on the candidate head:**
  - The real collector's DIFF lists 0 findings for this file. Both functions measure 15 or
    below.
  - The same 142 test identities run with the same outcomes, again with the checkout's
    `tools` imported.
  - The same mutation table, re-anchored to the moved code, gives exactly the baseline's
    kill set.
  - The test id stays cited by both guardrails.

## Consequences

- **The cost to the cutover:** this file joins the Docker repair in the critical cutover.
  No standalone transition is selected.
- **The debt:** the closure's typing debt falls by 12 diagnostics, and its complexity debt
  by two functions.
- **What it unblocks:** the Docker identity repair.
