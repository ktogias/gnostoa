---
type: Reference
title: Repository layout and toolkit distribution
description: Choose a project layout and pinned dependency mechanism appropriate to repository scale and operating constraints.
status: draft
generated:
  by: codex/gpt-5
  at: "2026-07-29T00:00:00Z"
sources:
  - id: git-submodules
    resource: https://git-scm.com/book/en/v2/Git-Tools-Submodules
    title: Git Tools - Submodules
x-project-knowledge:
  id: guidance.reference.repository-layout-and-distribution
  owners:
    - team:gnostoa-maintainers
  scope:
    - generic-guidance
  relations:
    - kind: guides
      target: /workflows/bootstrap-new-project.md
    - kind: guides
      target: /workflows/adopt-existing-project.md
---

# Repository layout and toolkit distribution

## Purpose

Keep generic policy, project-owned knowledge and source implementation
independently versioned while retaining reproducible local validation.

## Content

Recommended single-repository layout:

```text
project/
├── .knowledge-kit/          # pinned dependency
├── .knowledge/
│   ├── profile.yaml
│   ├── kit.lock.yaml
│   ├── change-control.yaml
│   ├── continuous-integration.yaml
│   ├── verification.yaml
│   └── modules/<name>/profile.yaml
├── .githooks/              # optional advisory local adapters
├── ci/verify               # shared project suite interface
├── knowledge/               # canonical project bundle
├── AGENTS.md                # short project router
└── source/
```

Recommended multi-repository layout:

```text
project-knowledge/
├── .knowledge-kit/
├── .knowledge/              # profile plus kit.lock.yaml
└── knowledge/

source-repository-a/
source-repository-b/
deployment-repository/
```

Distribution choices:

| Mechanism | Use when | Cost |
|---|---|---|
| Pinned Git submodule | Normal connected development | Extra clone/update discipline |
| Vendored release | Air-gapped or operational simplicity | Manual upstream updates |
| Pinned package plus local profile assets | Mature release pipeline | Packaging/version coordination |
| OCI image pinned by digest | Default execution and CI runtime | Registry and image lifecycle |
| Mutable branch | Never for validation policy | Non-reproducible behavior |

## Usage

Use embedded knowledge for a new single-repository project. Prefer a dedicated
knowledge repository when architecture spans independently versioned
repositories. In either case, resolve profiles locally and use commit-aware
links to external source artifacts. Pin source/profile assets and their matching
runtime image together in `.knowledge/kit.lock.yaml`.
