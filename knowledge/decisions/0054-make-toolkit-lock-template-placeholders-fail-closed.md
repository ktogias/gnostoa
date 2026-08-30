---
type: Decision
title: Make toolkit-lock template placeholders fail closed
description: Replace schema-valid all-zero toolkit-lock template values with self-describing schema-invalid tokens so untouched or partial adaptations fail through the existing runtime-lock validation route.
status: draft
generated:
  by: chatgpt/gpt-5.6-sol
  at: "2026-08-30T22:08:07Z"
sources:
  - id: fail-closed-placeholder-work-item
    resource: https://github.com/ktogias/gnostoa/issues/162
    title: Make toolkit-lock template placeholders fail closed
  - id: phase-a-adaptation-retrospective
    resource: ../assessments/nextcloud-mail-phase-a-owner-led-adaptation-retrospective.md
    title: Nextcloud Mail Phase-A owner-led adaptation retrospective
x-project-knowledge:
  id: kit.decision.0054.make-toolkit-lock-template-placeholders-fail-closed
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

# Make toolkit-lock template placeholders fail closed

## Context

The public toolkit-lock template represents `toolkit.public_surface_digest` and
`runtime.image` with all-zero SHA-256-shaped values. Those values satisfy the
public schema before an adopter has replaced them. The same pattern survived
multiple adaptation and evaluation attempts, including the Phase-A owner-led
Mail adaptation, because an untouched placeholder looked structurally real.

The broader question of whether a syntactically valid runtime-image claim was
actually observed is separate and remains owned by Work Item #163. This Decision
addresses only the reusable template's placeholder representation and its
existing supported validation route.

## Decision

1. Represent the two digest-bearing template placeholders with self-describing
   `REPLACE_WITH_*` tokens while retaining their field-specific prefixes:
   `sha256:` for `toolkit.public_surface_digest` and the example image plus
   `@sha256:` for `runtime.image`.
2. Make each token intentionally fail the existing schema pattern. Do not add a
   second placeholder registry, schema keyword or Python validation mechanism.
3. Verify the behavior through `check_runtime_lock()` for untouched, partially
   replaced and fully replaced template cases. The field path, token and failed
   pattern in the existing schema diagnostic are the actionable error.
4. Keep valid digest-pinned locks valid. Do not generally prohibit an all-zero
   digest, reinterpret historical locks or claim observed runtime-image truth.

## Compatibility boundary

- Existing valid project-owned locks and the public schema are unchanged.
- Future copies of the current template that remain untouched or only partially
  adapted fail earlier by design.
- The immutable `v0.2.0` source, released template, source digest, OCI artifact
  and frozen owner-led experiment subjects remain historical and unchanged.
- Because `templates/` is public source, the next source candidate receives a
  different public-surface digest. This Decision authorizes no release or
  publication and selects no release version.
- No schema-version bump or migration is required: the change corrects invalid
  scaffold defaults without rejecting a previously valid configured lock.

## Consequences

- A copied template can no longer pass structural runtime-lock validation merely
  because both digest-shaped placeholders were left at their defaults.
- The correction reuses the existing deterministic validation mechanism and
  adds no new truth or readiness semantics.
- Work Item #163 remains separately unadmitted, and Phase-A/Phase-B evidence is
  neither repaired nor rescored.
