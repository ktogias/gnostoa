---
type: Decision
title: Make toolkit-lock template placeholders fail closed
description: Replace schema-valid all-zero toolkit-lock template values with self-describing schema-invalid sentinels so untouched and partial adaptations that retain a sentinel fail through the existing runtime-lock validation route.
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

The first candidate retained the example registry and repository before the
runtime-image digest token. Replacing only that visible token with 64
hexadecimal characters therefore produced a schema-valid image reference while
silently retaining `registry.example.org/gnostoa`. Whole-value guidance cannot
distinguish that edit from an intentional final value after the fact.

The second candidate removed that example prefix and used a whole-field token,
but the token itself contained no whitespace. Appending `@sha256:` and 64
hexadecimal characters therefore produced a schema-valid image reference while
retaining the literal scaffold sentinel. That contradicts the supported
guidance to replace the whole scalar rather than retain or append to the
sentinel.

The broader question of whether a syntactically valid runtime-image claim was
actually observed is separate and remains owned by Work Item #163. This Decision
addresses only the reusable template's placeholder representation and its
existing supported validation route.

## Decision

1. Represent the two digest-bearing template placeholders with self-describing
   `REPLACE_WITH_*` tokens. Retain `sha256:` for
   `toolkit.public_surface_digest`, where only the digest body is unknown. Use
   the quoted, whitespace-bearing whole-field sentinel
   `REPLACE_WITH_DIGEST_PINNED_RUNTIME_IMAGE (replace entire value)` for
   `runtime.image`, where registry, repository and digest are all unknown. The
   scaffold must supply no example image prefix, and any partially adapted value
   that retains the sentinel must remain schema-invalid.
2. Make each token intentionally fail the existing schema pattern. Do not add a
   second placeholder registry, schema keyword or Python validation mechanism.
3. Verify the behavior through `check_runtime_lock()` for untouched,
   one-field-only, legacy digest-suffix, current-sentinel append and fully
   replaced template cases. The field path, sentinel and failed pattern in the
   existing schema diagnostic are the actionable error.
4. Keep valid digest-pinned locks valid. Do not generally prohibit an all-zero
   digest, reinterpret historical locks or claim observed runtime-image truth.

## Compatibility boundary

- Existing valid project-owned locks and the public schema are unchanged.
- Future copies of the current template that remain untouched, replace only one
  required field, use the measured legacy digest-suffix edit, or append a valid
  digest suffix while retaining the current sentinel fail earlier by design.
  Arbitrary schema-valid fabricated image identities created only after the
  sentinel is removed remain outside this scaffold-integrity claim and are
  owned by Work Item #163.
- Automation that replaced only the old runtime-image digest suffix must replace
  the whole `runtime.image` value. This is the intended fail-closed correction,
  not a migration of an already configured lock.
- The immutable `v0.2.0` source, released template, source digest, OCI artifact
  and frozen owner-led experiment subjects remain historical and unchanged.
- Because `templates/` is public source, the next source candidate receives a
  different public-surface digest. This Decision authorizes no release or
  publication and selects no release version.
- No schema-version bump or migration is required: the change corrects invalid
  scaffold defaults without rejecting a previously valid configured lock.

## Consequences

- A copied template can no longer pass structural runtime-lock validation merely
  because both digest-shaped placeholders were left at their defaults or
  because a partial runtime-image edit retained either the old example prefix
  or the current sentinel.
- The correction reuses the existing deterministic validation mechanism and
  adds no new truth or readiness semantics.
- Work Item #163 remains separately unadmitted, and Phase-A/Phase-B evidence is
  neither repaired nor rescored.
