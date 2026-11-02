---
type: Decision
title: Bound the spec's control parser and the handoff's source walk
description: "Complexity Slice 1.2 of #389's closure: _parse_semantics is brought to 15 or below by one private helper for each control, and the handoff's nested walk moves to module level with private helpers for its regular-file and symlink entries, which also lowers its enclosing function. A new characterization module, written first and passing on the unchanged code, pins the behaviour that twelve surviving mutants showed unpinned, including the walk's race guards; the thirteenth survivor is equivalent."
status: draft
generated:
  by: anthropic/claude-opus-5-5
  at: "2026-11-02T13:45:00Z"
sources:
  - id: work-item
    resource: https://github.com/ktogias/gnostoa/issues/389
    title: Keep merges possible while a vendor analyzer is unavailable
  - id: owner-admission
    resource: https://github.com/ktogias/gnostoa/issues/389#issuecomment-6575899800
    title: "The owner's admission of Slice 1.2: exactly four paths, tests first"
  - id: owner-index
    resource: https://github.com/ktogias/gnostoa/issues/389#issuecomment-6577803048
    title: "The owner's amendment: the knowledge index line as the fifth path"
  - id: packet
    resource: https://github.com/ktogias/gnostoa/issues/389#issuecomment-6575029641
    title: "The Router's final decision packet"
  - id: design
    resource: https://github.com/ktogias/gnostoa/issues/389#issuecomment-6568479405
    title: "The slice's read-only characterization and falsifier design: 3 of 16 mutants killed"
  - id: review-1-1
    resource: https://github.com/ktogias/gnostoa/pull/475#discussion_r4443716009
    title: "Review round 1 on #475, Slice 1.1: the complexity family's scope, the same sentence"
  - id: profile
    resource: ./0117-select-the-diagnostic-inventory-s-families-through-a-protected-profile.md
    title: The protected profile whose complexity family this answers, unchanged
  - id: inheritance
    resource: ./0099-route-the-architecture-inheritance-gate-from-source.md
    title: The architecture inheritance gate
x-project-knowledge:
  id: kit.decision.0127.bound-the-spec-control-parser-and-the-handoff-walk
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

# Bound the spec's control parser and the handoff's source walk

## Context

The protected profile's complexity family reports a function above a cyclomatic complexity
of 15 when a change adds a line to it; it has no full scan (source `profile`). Three
functions above that threshold are bounded here, in two files (source `design`):

- `tools/capsule/spec.py`, `_parse_semantics`, at 20;
- `tools/experiment/handoff.py`, `walk`, at 17. It is nested in
  `_source_members_and_copy_fd`, which therefore also measures 17.

Before changing them, their behaviour was checked against 16 mutants, each breaking one
decision inside a planned extraction. The existing tests killed 3 (source `design`). Of the 13
survivors, 12 are real gaps. Six of those are the walk's race guards, which refuse an entry
or directory that changes while it is copied. The thirteenth, W6, changes the walk's final
`unsupported-source-entry` refusal, and that statement is unreachable. Each entry's mode is
normalized before its type is dispatched, and the normalization already refuses every type
other than a directory, a regular file or a symlink. Each of those three branches ends its
iteration. The owner admitted the slice
with the characterization tests first (source `owner-admission`), and later the index line
(source `owner-index`).

## Decision

1. **`_parse_semantics`** keeps its contract. The parsing of one control, its corroboration
   included, moves into the private helper `_parse_control`. The loop over the controls
   stays.
2. **The walk moves to module level** as a private function, with the members list passed
   in, so `_source_members_and_copy_fd` keeps only the call. The walk's regular-file and
   symlink entries each move into their own private helper, so the walk comes to 15 or
   below with a margin. Every descriptor is opened and closed in the same function as
   before, and every race guard and message stays.
3. **A new characterization module, `tests/test_spec_handoff_characterization.py`, comes
   first.**
   - It passes on the unchanged code, and kills the 12 gap mutants (S1, S3, S4, S6, S7, S8,
     W1 to W5, W8).
   - W6 stays named as equivalent. The module pins the refusal that does happen to an
     unsupported entry: by type, at the normalization.
   - It reaches the parser through `parse_spec` and the walk through `freeze_handoff`.
   - It injects each race through the module's own `os.stat` and `os.fstat`, the way the
     existing handoff tests patch `os.mkdir`. So it reads no private attribute, and imports
     no other test module.
4. **This record is listed in `knowledge/index.md`** by one line (source `owner-index`).
5. **Nothing else changes.**
   - Every public signature, message, refusal and returned value stays.
   - So do `tools/experiment/packaging.py`, the other functions of both files, the profile
     and the threshold.

## Verification

- **Before, on `main` `58c75e3c`:**
  - The eleven test modules covering these files run 157 tests: OK, with 2 skipped.
  - The 16-mutant table kills 3.
- **The characterization, still before any extraction:**
  - The new module passes on the unchanged code.
  - With it, 15 of the 16 are killed. W6, the equivalent, survives.
- **After the extractions:**
  - The same tests pass.
  - The same mutants, re-anchored into the moved code, give the same result.
  - Each changed function and helper measures 15 or below.
  - The real collector's DIFF lists 0 findings for the slice's head.
  - The full round passes, the knowledge index invariant included.

## Consequences

- **What it settles:** three of the functions above the complexity threshold.
- **The class and route:** it is outside the gates, so its class is NORMAL. It integrates
  through the single serialized lane, after Slice 1.1. Its index line is reconciled with
  0126's when the lane integrates.

## Corrections

This text amends the first published version, of 5,554 bytes (SHA-256
`78303366c2976762d6e56a862f104f9c8a4753a57a2c0c515e4f44938529c809`). That version said that all 13 survivors were real gaps
and that the new module would kill all 16 mutants. The module's own test of an unsupported
entry then showed that the walk's final refusal is unreachable, which makes W6 equivalent.

The second published version, of 6,472 bytes (SHA-256
`37c38375e162043bc7297f54512dec004c34e687b1039b8000f6fa0648b61b39`), said that the complexity family lists every function
above the threshold. Review round 1 on Slice 1.1's #475 found the same sentence in Decision
0126 (source `review-1-1`): the profile acquires complexity only for the functions a change
adds a line to (`full: null`). The Context and the Consequences now say so.
