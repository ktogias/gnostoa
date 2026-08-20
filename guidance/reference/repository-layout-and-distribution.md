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
| Pinned native installation from pinned source | Explicit container-unavailable fallback | Python environment and dependency-lock lifecycle |
| OCI image pinned by digest | Default execution and CI runtime | Registry and image lifecycle |
| Mutable branch | Never for validation policy | Non-reproducible behavior |

## Usage

Use embedded knowledge for a new single-repository project. Prefer a dedicated
knowledge repository when architecture spans independently versioned
repositories. In either case, resolve profiles locally and use commit-aware
links to external source artifacts. Pin source/profile assets and their matching
runtime image together in `.knowledge/kit.lock.yaml`. Record the deterministic
toolkit public-surface digest as well as the immutable source revision and image
digest; a revision label alone is not a transport-independent content identity.
A native installation supplies execution only and never replaces the pinned
public source/profile assets. Point native execution at those assets with
`KNOWLEDGE_KIT_ROOT`, but do not treat that location binding as identity
evidence: hash-pin the executable dependency and validate the project lock,
source revision and public-surface digest before use. An absent or malformed
source binding must fail rather than fall back to package data or ambient files.

The public-surface digest reads its membership from whatever the toolkit root
declares. For a Git-backed or manifest-backed root, public-surface membership is
taken from that declared candidate, so local files outside it do not affect the
digest. For a metadata-free vendored source, the extracted physical public
surface is the source presented for digest verification, after the toolkit's
explicit generated-state exclusions; adding or removing another non-ignored
public file therefore changes the vendored source digest. A root that declares
an authority which cannot be read fails rather than being treated as declaring
none.
