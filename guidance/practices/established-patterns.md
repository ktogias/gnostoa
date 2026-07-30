---
type: Practice
title: Established patterns supporting project knowledge
description: Apply established documentation and architecture patterns through a small governed knowledge layer.
status: draft
generated:
  by: codex/gpt-5
  at: "2026-07-29T00:00:00Z"
sources:
  - id: okf-spec
    resource: https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md
    title: Open Knowledge Format v0.2
  - id: docs-as-code
    resource: https://www.writethedocs.org/guide/docs-as-code/
    title: Write the Docs - Docs as Code
  - id: diataxis
    resource: https://diataxis.fr/start-here/
    title: Diátaxis
  - id: c4
    resource: https://c4model.com/diagrams
    title: C4 model diagrams
  - id: madr
    resource: https://adr.github.io/madr/
    title: Markdown Architectural Decision Records
  - id: dora-trunk
    resource: https://dora.dev/capabilities/trunk-based-development/
    title: DORA trunk-based development
  - id: dora-continuous-delivery
    resource: https://dora.dev/capabilities/continuous-delivery/
    title: DORA continuous delivery
  - id: tdd
    resource: https://martinfowler.com/bliki/TestDrivenDevelopment.html
    title: Test-driven development
  - id: dora-continuous-integration
    resource: https://dora.dev/capabilities/continuous-integration/
    title: DORA continuous integration
x-project-knowledge:
  id: guidance.practice.established-patterns
  owners:
    - team:gnostoa-maintainers
  scope:
    - generic-guidance
  relations:
    - kind: guides
      target: /workflows/daily-change-loop.md
    - kind: applies-to
      target: /guardrails/non-negotiable.md
---

# Established patterns supporting project knowledge

## Intent

Build on familiar engineering practices rather than inventing a monolithic
knowledge-management methodology.

## Rule

Use:

- **Docs as Code** for plain-text versioning, review and CI.
- **Trunk-based change flow** for small, bounded, verified changes into a
  protected integration branch.
- **Proportionate verification** for observable intent, evidence before
  integration and Red-Green-Refactor where it adds confidence.
- **Continuous integration** for fast evidence on pushed revisions,
  authoritative candidate gates and immediate restoration of a broken trunk.
- **OKF** for portable concepts, provenance, lifecycle and progressive
  disclosure.
- **ADRs/MADR** for significant choices and retained rationale.
- **C4** for audience-appropriate architectural zoom levels.
- **Diátaxis** to separate tutorials, how-to guides, reference and explanation.
- **Executable specifications** for schemas and behavioral contracts.
- **Derived projections** for sites, search, graphs and agent caches.

No one pattern replaces the others; each owns a distinct concern.

## Application

- Keep concepts small and source-linked.
- Record consequential decisions, not every implementation detail.
- Prefer Context and Container diagrams before deeper views.
- Keep native OpenAPI, JSON Schema, Protobuf or tests canonical in their own
  formats.
- Route a user to the correct documentation form instead of combining tutorial,
  reference and explanation in one document.

## Verification

Reviewers can identify the role of every artifact, locate its source, determine
whether it is canonical or derived and delete any projection without knowledge
loss.
