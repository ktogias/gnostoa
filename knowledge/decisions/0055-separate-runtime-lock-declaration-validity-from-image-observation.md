---
type: Decision
title: Separate runtime-lock declaration, supplied-reference comparison and execution observation
description: Report runtime-lock declaration and source binding separately from caller-supplied image-reference comparison while preserving execution observation as UNKNOWN unless it is acquired from an invocation-bound source.
status: draft
generated:
  by: chatgpt/gpt-5.6-sol
  at: "2026-08-31T08:11:04Z"
sources:
  - id: runtime-image-truth-work-item
    resource: https://github.com/ktogias/gnostoa/issues/163
    title: Separate runtime-lock structural validity from observed image truth
  - id: phase-a-adaptation-retrospective
    resource: ../assessments/nextcloud-mail-phase-a-owner-led-adaptation-retrospective.md
    title: Nextcloud Mail Phase-A owner-led adaptation retrospective
x-project-knowledge:
  id: kit.decision.0055.separate-runtime-lock-declaration-validity-from-image-observation
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governed-by
      target: /decisions/0016-evolve-human-agent-workflow-through-bounded-self-hosted-slices.md
    - kind: governed-by
      target: /decisions/0018-adopt-evidence-gated-capability-evolution-for-gnostoa-self-governance.md
    - kind: derived-from
      target: /assessments/nextcloud-mail-phase-a-owner-led-adaptation-retrospective.md
    - kind: governed-by
      target: /decisions/0047-select-a-bounded-adoption-completion-check.md
    - kind: references
      target: /decisions/0048-select-project-adapter-runtime-observation-for-adoption-check.md
    - kind: references
      target: /contracts/public-inheritance-surface.md
---

# Separate runtime-lock declaration, reference comparison and observation

## Context

`check-runtime` currently returns one issue list and, when that list is empty,
prints that the “toolkit source and runtime lock is valid.” Image-reference
comparison is performed only when `--expected-image` or
`KNOWLEDGE_KIT_IMAGE` supplies a non-empty identity. Without one, the same broad
success text is printed even though no runtime image was observed.

The first owner-led Mail adaptation demonstrated why that compression is
unsafe. A syntactically valid declared image remained unobserved while the
standalone runtime-lock component passed. The aggregate adoption result stayed
blocked through its separate `RuntimeObservationAvailable` condition, but the
component and CLI wording could be read as stronger evidence than they held.

Decision 0054 corrected scaffold placeholders. Decision 0047 already requires
locked, expected and caller-supplied identities to remain declarations rather
than execution observations. This Decision owns the distinct case after a
syntactically valid declaration exists: declaration validity,
supplied-reference comparison and execution observation are three different
evidence dimensions.

## Decision

1. Represent runtime-lock declaration/source validation, supplied-image
   reference comparison and execution observation separately in the supported
   runtime-lock evaluation path.
2. Report declaration/source binding as `PASS` or `FAIL` independently of image
   reference comparison or execution observation.
3. Report supplied-reference comparison as:
   - `MATCH` when a caller-supplied identity equals the declaration;
   - `MISMATCH` when it conflicts with the declaration;
   - `NOT SUPPLIED` when no comparison identity is available.
4. Report execution observation as `UNKNOWN` in `check-runtime`. Neither
   `--expected-image` nor `KNOWLEDGE_KIT_IMAGE` is an acquisition-bound runtime
   observation, so reference equality must never produce observation `PASS`.
   A future observation `PASS` requires a separately admitted, mechanically
   bound acquisition route such as the project-adapter sidecar governed by
   Decision 0048.
5. Preserve supported native fallback: unavailable execution observation does
   not erase a valid declaration result or become a fabricated mismatch. It
   remains visibly `UNKNOWN`.
6. Preserve the existing `check_runtime_lock()` issue-list interface for current
   callers. Use an explicit structured evaluation for reporting surfaces, and
   keep a supplied-reference mismatch fail-closed.
7. Keep adoption-check’s structural component and
   `RuntimeObservationAvailable` observation distinct. Do not upgrade unknown,
   blocked, skipped or unexecuted evidence to PASS.

## Compatibility boundary

- The toolkit-lock schema and configured lock format are unchanged.
- Existing container routes that supply `KNOWLEDGE_KIT_IMAGE` continue to
  compare that caller-supplied reference with the declaration, without
  reclassifying the value as execution observation.
- Native fallback retains successful declaration/source validation while
  reporting execution observation as `UNKNOWN`.
- Existing callers of `check_runtime_lock()` continue to receive an issue list;
  supplied-reference mismatch remains an issue and command failure.
- No registry fetch, OCI execution attestation or independent trust root is
  introduced. A caller-supplied identity is a declaration used for comparison,
  never an execution observation, identity acquisition or coherence proof.
- Adoption-check schemas, historical Phase-A/Phase-B records, releases and
  published artifacts remain unchanged.

## Consequences

- A broad lock-validity message can no longer hide absence of image observation.
- Consumers can distinguish a valid declaration and a matching supplied
  reference from an actual execution observation without losing the supported
  native recovery path.
- `check-runtime` cannot establish runtime execution truth. Runtime truth
  remains bounded by separately acquired invocation-bound evidence; this
  Decision does not create a semantic or registry oracle.
