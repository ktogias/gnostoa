---
type: Contract
title: Public inheritance surface
description: Contract between the generic toolkit and an adopting project.
status: draft
generated:
  by: codex/gpt-5
  at: "2026-07-29T00:00:00Z"
x-project-knowledge:
  id: kit.contract.public-inheritance
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governs
      target: /architecture/knowledge-surfaces.md
    - kind: verifies
      target: /requirements/prevent-policy-drift.md
---

# Public inheritance surface

## Purpose

Allow any project to inherit stable generic controls without inheriting the
toolkit's internal concerns.

## Boundary

The public surface consists of the core profile, schemas, supported tools,
reusable guidance, anonymous templates and documented CI integration.
`knowledge/`, `policy/`, internal decisions and maintainer runbooks are outside
the consumer inheritance boundary. Adopting projects create their own
`.knowledge/` policies by extending the public files under `core/`.

## Invariants

- The generic core contains no organization, domain, product or module names.
- Child profiles add vocabulary or stronger constraints without weakening a
  parent silently.
- Reusable guidance remains project-independent.
- Toolkit self-knowledge is never required to validate a consuming bundle.
- Derived views are replaceable and non-canonical.
- Consumer execution is implementation-language-independent through a pinned
  OCI runtime image.
- A supported native CLI remains available for development and recovery.
- Runtime image and toolkit source/profile revisions do not drift.
- The default integration branch is protected and changes arrive through a
  provider-neutral, risk-classified Change Request flow that remains practical
  for a solo maintainer.
- Child change-control policies strengthen rather than weaken the generic
  baseline.
- Agents cannot satisfy a required human gate, bypass controls or replace
  required human semantic verification.
- Expected behavior and proportionate verification evidence precede
  integration, except for an explicitly permitted emergency follow-up.
- Required tests favor observable behavior, determinism and fast feedback;
  coverage alone does not establish acceptance.
- Centralized CI is authoritative, validates the latest integration candidate
  through tiered evidence and treats local hooks as advisory.
- Child CI policies may add gates or suites but cannot weaken inherited event,
  security, feedback or artifact-promotion controls.
- Delivery requirements activate only for a declared deployable artifact.

## Operations

Consumers pin a toolkit version and matching runtime-image digest, extend
`core/profile.yaml`, validate their bundle and load only the guidance route
needed for the current task. Container execution is the default; native
execution is a supported fallback.

Maintainers change the public surface through traceable, versioned changes with
proportionate verification and migration notes when compatibility is affected.
Projects validate an inherited `.knowledge/change-control.yaml` and map its
provider-neutral controls to their repository host.
Projects select stack-specific test tools in specializations while retaining the
generic verification vocabulary and non-weakening policy.
Projects validate an inherited `.knowledge/continuous-integration.yaml`, declare
capabilities and suites in `.knowledge/verification.yaml`, and map them to a
provider adapter without changing their generic meaning.

## Failure semantics

A failed required test, schema, profile, bundle, link, change-control or
guardrail-coverage check blocks the change. A breaking public-surface change
requires an explicit major-version migration rather than silent consumer drift.
