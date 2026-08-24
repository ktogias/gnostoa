---
type: Reference
title: Tool selection by architectural role
description: Select replaceable tools around a canonical Git-native knowledge layer.
status: draft
generated:
  by: codex/gpt-5
  at: "2026-07-29T00:00:00Z"
sources:
  - id: okf-spec
    resource: https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/9a15b13ba996bb713b19e053ea744abee01c2714/okf/SPEC.md
    title: Open Knowledge Format specification
  - id: openwiki
    resource: https://github.com/langchain-ai/openwiki
    title: OpenWiki
  - id: graphiti
    resource: https://github.com/getzep/graphiti
    title: Graphiti
  - id: google-knowledge-catalog
    resource: https://cloud.google.com/products/knowledge-catalog
    title: Google Cloud Knowledge Catalog
x-project-knowledge:
  id: guidance.reference.tool-selection
  owners:
    - team:gnostoa-maintainers
  scope:
    - generic-guidance
  relations:
    - kind: applies-to
      target: /practices/established-patterns.md
    - kind: guides
      target: /workflows/adopt-existing-project.md
---

# Tool selection by architectural role

## Purpose

Choose tools by a single owned responsibility so that rendering, retrieval,
generation or testing can change without changing the canonical knowledge
contract.

## Content

| Role | Baseline or option | Authority |
|---|---|---|
| Versioning and review | Git, Change Requests, review ownership | Workflow |
| Knowledge interchange | OKF Markdown and YAML | Canonical reviewed knowledge |
| Validation | Included profile and bundle tools | Enforces policy |
| Human rendering | MkDocs or another static site | Derived |
| Draft production | OpenWiki or another generator | Draft producer |
| Bounded agent orientation | Deterministic context pack; PEEK-style cache after measurement | Derived |
| Temporal retrieval | Graphiti after workload justification | Derived |
| Enterprise data context | Google Cloud Knowledge Catalog when its governance scope fits | External governed projection |
| Executable contract production | Project-selected native format and tool | Native source artifact |
| Contract conformance testing | Project-selected schema and behavioral tests | Executable verification |

Implementation frameworks and concrete conformance tools belong in project or
module specializations. The generic kit defines their architectural role and
authority boundary, not a technology choice. Each adopting project states
which native artifact is authoritative and which tools produce or verify it.

OpenWiki is a producer, not an approver. Its current documentation describes
OKF v0.1 output, so output must be normalized to the profile's supported OKF
version and reviewed as draft. Graphiti and enterprise catalogs are introduced
only when temporal or data-governance workloads justify their operational and
model costs.

## Usage

Start with Git, OKF, validation and native executable contracts. Measure a
fixed set of real tasks before and after adding any optional layer. Record
correctness, input tokens, repository reads, latency, reviewer time, operating
cost and rebuildability. Reject a tool that creates a second canonical store or
an independently curated taxonomy for the same facts.
