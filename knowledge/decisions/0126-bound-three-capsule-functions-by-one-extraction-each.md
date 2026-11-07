---
type: Decision
title: Bound three capsule functions by one extraction each
description: "Complexity Slice 1.1 of #389's closure: discover_preparation, _validate_completed_stage_binding and qualify, each the only function above the threshold in its file, are brought to 15 or below by one private helper each. A new characterization module, written first and passing on the unchanged code, pins the behaviour that twelve surviving mutants showed unpinned."
status: draft
generated:
  by: anthropic/claude-opus-5-5
  at: "2026-11-02T11:40:00Z"
sources:
  - id: work-item
    resource: https://github.com/ktogias/gnostoa/issues/389
    title: Keep merges possible while a vendor analyzer is unavailable
  - id: owner-admission
    resource: https://github.com/ktogias/gnostoa/issues/389#issuecomment-6575893033
    title: "The owner's admission of Slice 1.1, Revision 3: exactly five paths, tests first"
  - id: packet
    resource: https://github.com/ktogias/gnostoa/issues/389#issuecomment-6575029641
    title: "The Router's final decision packet, Revision 3"
  - id: dispatch
    resource: https://github.com/ktogias/gnostoa/issues/389#issuecomment-6575934463
    title: "The Router's dispatch of Slice 1.1"
  - id: design
    resource: https://github.com/ktogias/gnostoa/issues/389#issuecomment-6567727855
    title: "The slice's read-only characterization and falsifier design: 6 of 20 mutants killed"
  - id: corrections
    resource: https://github.com/ktogias/gnostoa/issues/389#issuecomment-6574600040
    title: "The corrections that made the packet exact"
  - id: review-round-1
    resource: https://github.com/ktogias/gnostoa/pull/475#discussion_r4443716009
    title: "Review round 1 on #475: the complexity family's scope"
  - id: profile
    resource: ./0117-select-the-diagnostic-inventory-s-families-through-a-protected-profile.md
    title: The protected profile whose complexity family this answers, unchanged
  - id: inheritance
    resource: ./0099-route-the-architecture-inheritance-gate-from-source.md
    title: The architecture inheritance gate
x-project-knowledge:
  id: kit.decision.0126.bound-three-capsule-functions-by-one-extraction-each
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: references
      target: /decisions/0117-select-the-diagnostic-inventory-s-families-through-a-protected-profile.md
    - kind: references
      target: /decisions/0099-route-the-architecture-inheritance-gate-from-source.md
---

# Bound three capsule functions by one extraction each

## Context

The protected profile's complexity family reports a function above a cyclomatic complexity
of 15 when a change adds a line to it; it has no full scan (source `profile`). Three
functions above that threshold each stand alone in their file and need only one extraction
to come to 15 or below (source `design`):

- `tools/capsule/preparation.py`, `discover_preparation`, at 16;
- `tools/capsule/effect_claim.py`, `_validate_completed_stage_binding`, at 19;
- `tools/capsule/oracle_qualification.py`, `qualify`, at 18.

Before changing them, their behaviour was checked against 20 mutants, each breaking one
decision inside a planned extraction. The existing tests killed 6. Of the 14 survivors, 12
are real gaps, E1 is equivalent, and E3 only changes a message (source `design`). The owner
admitted exactly five paths, with the characterization tests first (source
`owner-admission`).

## Decision

1. **`discover_preparation`** keeps its contract. The computation of the missing version
   files, from the frozen paths when given and from file presence otherwise, moves into the
   private helper `_missing_version_files`.
2. **`_validate_completed_stage_binding`** keeps its contract. Its loop over the retained
   tasks moves into the private helper `_retained_task_capsules`. The loop builds the
   capsule map and the backend set, and refuses each malformed record.
3. **`qualify`** keeps its contract. The per-control checks move into the private helper
   `_control_blocker`, which returns the control's blocker or none. The loop over the
   controls stays in `qualify`.
4. **A new characterization module, `tests/test_capsule_characterization.py`, comes first.**
   - It passes on the unchanged code, and kills the 12 gap mutants (P2, P5, E2, E4, E6, Q1 to
     Q6, Q8).
   - It reaches every function through its public API, so it reads no private attribute and
     imports no other test module.
   - E1 stays named as equivalent: retained records are JSON, so a task id is always text.
   - E3 is killed only because the module pins each refusal's message. That pin is recorded
     as such, not counted as an ordinary kill.
5. **Nothing else changes.**
   - Every public signature, message, refusal and returned value stays.
   - So do the profile, the threshold, `tests/test_experiment_capsule.py`, the typing front
     and the Docker cutover.

## Verification

- **Before, on `main` `58c75e3c`:**
  - The nine test modules covering these files run 121 tests: OK, with 1 skipped.
  - The 20-mutant table kills 6.
- **The characterization, still before any extraction:**
  - The new module passes on the unchanged code.
  - With it, every gap mutant is killed. E1 survives, as named; E3 is killed by its pinned
    message.
- **After the extractions:**
  - The same tests pass.
  - The same mutants, re-anchored into the helpers, give the same result.
  - Each changed function and helper measures 15 or below.
  - The real collector's DIFF lists 0 findings for the slice's head.
  - The full round passes.

## Consequences

- **What it settles:** three of the functions above the complexity threshold.
- **The class and route:** it is outside the gates, so its class is NORMAL. It integrates
  through the single serialized lane, separately from Slice 1.2 and from the Docker cutover.

## Corrections

Review round 1 on #475 (source `review-round-1`) found that the Context overstated the
complexity family's scope. The profile acquires complexity only for the functions a change
adds a line to (`full: null`), so it does not list every function above the threshold. The
Context and the Consequences now say so. The first published text was 5,595 bytes
(SHA-256 `16e18ac8fab9fc3f17c31d00b59f7350b7631930bee72ec73c5527eb2ba60df6`).
