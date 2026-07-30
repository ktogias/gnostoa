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
  - id: long-running-agent-harness
    resource: https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents
    title: Effective harnesses for long-running agents
  - id: w3c-prov-o
    resource: https://www.w3.org/TR/prov-o/
    title: W3C PROV Ontology
  - id: github-agent-instructions
    resource: https://docs.github.com/en/copilot/how-tos/copilot-on-github/customize-copilot/add-custom-instructions/add-repository-instructions
    title: GitHub repository custom instructions
  - id: github-agent-skills
    resource: https://docs.github.com/en/copilot/how-tos/copilot-on-github/customize-copilot/customize-cloud-agent/add-skills
    title: GitHub agent skills
  - id: github-contribution-templates
    resource: https://docs.github.com/en/communities/using-templates-to-encourage-useful-issues-and-pull-requests/about-issue-and-pull-request-templates
    title: GitHub issue and pull request templates
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
    - kind: guides
      target: /workflows/resume-and-handoff-change.md
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
- **Living execution state plus Git checkpoints** for stateless resumption of
  unfinished work without replaying conversations.
- **Provenance roles** for distinguishing authoring, evaluation and accountable
  human approval.
- **Agent Skills** for progressively loading a repeatable task workflow across
  compatible software agents.
- **Thin provider adapters** for applying repository-wide instructions and
  contribution templates without moving generic policy into one hosted tool.

No one pattern replaces the others; each owns a distinct concern.

## Application

- Keep concepts small and source-linked.
- Record consequential decisions, not every implementation detail.
- Prefer Context and Container diagrams before deeper views.
- Keep native OpenAPI, JSON Schema, Protobuf or tests canonical in their own
  formats.
- Route a user to the correct documentation form instead of combining tutorial,
  reference and explanation in one document.
- Keep a progress artifact bounded to current state and one next action; rely
  on Git for recoverable implementation history and on the Change Request for
  integration evidence.
- Record software agents as responsible actors with explicit roles, but never
  infer that an evaluator is an independent human approver.

## Verification

Reviewers can identify the role of every artifact, locate its source, determine
whether it is canonical or derived and delete any projection without knowledge
loss.
