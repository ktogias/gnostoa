---
type: Decision
title: Separate runtime-lock declaration validity from image observation
description: Report runtime-lock declaration and source binding separately from observed runtime-image comparison so absence of observation remains explicit UNKNOWN rather than being summarized by a broad validity PASS.
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
    - kind: references
      target: /contracts/public-inheritance-surface.md
---

# Separate runtime-lock declaration validity from image observation

## Context

`check-runtime` currently returns one issue list and, when that list is empty,
prints that the “toolkit source and runtime lock is valid.” Image comparison is
performed only when `--expected-image` or `KNOWLEDGE_KIT_IMAGE` supplies a
non-empty identity. Without one, the same broad success text is printed even
though no runtime image was observed.

The first owner-led Mail adaptation demonstrated why that compression is
unsafe. A syntactically valid declared image remained unobserved while the
standalone runtime-lock component passed. The aggregate adoption result stayed
blocked through its separate `RuntimeObservationAvailable` condition, but the
component and CLI wording could be read as stronger evidence than they held.

Decision 0054 corrected scaffold placeholders. This Decision owns the distinct
case after a syntactically valid declaration exists: declaration validity and
observed-image comparison are different evidence dimensions.

## Decision

1. Represent runtime-lock declaration/source validation and observed-image
   comparison separately in the supported runtime-lock evaluation path.
2. Report declaration/source binding as `PASS` or `FAIL` independently of image
   observation.
3. Report observed-image binding as:
   - `PASS` only when an observed identity is supplied and equals the declaration;
   - `FAIL` when the supplied observed identity conflicts with the declaration;
   - `UNKNOWN` when no observed identity is available.
4. Preserve supported native fallback: an unavailable image observation does
   not erase a valid declaration result or become a fabricated mismatch. It
   must remain visibly `UNKNOWN` and must never be called observed-image PASS.
5. Preserve the existing `check_runtime_lock()` issue-list interface for current
   callers. Use an explicit structured evaluation for reporting surfaces, and
   keep image mismatch fail-closed.
6. Keep adoption-check’s structural component and
   `RuntimeObservationAvailable` observation distinct. Do not upgrade unknown,
   blocked, skipped or unexecuted evidence to PASS.

## Compatibility boundary

- The toolkit-lock schema and configured lock format are unchanged.
- Existing container routes that supply `KNOWLEDGE_KIT_IMAGE` continue to
  compare the observed/executing reference with the declaration.
- Native fallback retains successful declaration/source validation while
  reporting image observation as `UNKNOWN`.
- Existing callers of `check_runtime_lock()` continue to receive an issue list;
  mismatch remains an issue and command failure.
- No registry fetch, OCI execution attestation or independent trust root is
  introduced. A caller-supplied identity is an observed comparison input, not
  proof of stronger provenance than its acquisition route establishes.
- Adoption-check schemas, historical Phase-A/Phase-B records, releases and
  published artifacts remain unchanged.

## Consequences

- A broad lock-validity message can no longer hide absence of image observation.
- Consumers can distinguish a valid declaration from a matching observation
  without losing the supported native recovery path.
- Runtime truth remains bounded by the observation source; this Decision does
  not create a semantic or registry oracle.
