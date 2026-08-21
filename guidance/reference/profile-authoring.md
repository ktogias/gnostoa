---
type: Reference
title: Profile authoring
description: Author minimal project and module profiles with monotonic inheritance.
status: draft
generated:
  by: codex/gpt-5
  at: "2026-07-29T00:00:00Z"
x-project-knowledge:
  id: guidance.reference.profile-authoring
  owners:
    - team:gnostoa-maintainers
  scope:
    - generic-guidance
  relations:
    - kind: guides
      target: /workflows/bootstrap-new-project.md
    - kind: guides
      target: /workflows/create-specialization.md
    - kind: governed-by
      target: /guardrails/non-negotiable.md
---

# Profile authoring

## Purpose

Keep cross-project policy small while allowing a project or module to add
well-scoped vocabulary and stricter validation.

## Content

A project profile extends the pinned generic core:

```yaml
id: example-project
version: "0.1.0"
okf_version: "0.2"
extends:
  - ../.knowledge-kit/core/profile.yaml
concept_types: []
relation_kinds: []
rules:
  required_project_fields:
    - scope
type_rules: {}
```

`extends` entries are filesystem references relative to the profile that
declares them. They may traverse parent directories — the project-to-toolkit
example above does — but the resolved target, after symlinks are followed, must
stay inside the project root the running command is bound to. Absolute parent
references are rejected, and a relative or symlinked reference whose canonical
target leaves the project root is rejected before the file is opened. Supported
commands bind that root themselves; it defaults to the working directory, which
is the project root in the documented container and native routes.

A module profile extends its project profile:

```yaml
id: example-project.example-module
version: "0.1.0"
okf_version: "0.2"
extends:
  - ../../profile.yaml
concept_types: []
relation_kinds: []
rules: {}
type_rules: {}
```

Lists add vocabulary without duplicates. Mappings merge recursively. Children
may add requirements or make validation stricter; they may not disable parent
verification, uniqueness, link or OKF-version rules.

## Usage

Add a type, relation or required section only after real concepts show that the
parent vocabulary is insufficient. Validate both representative leaf bundles
and parent-only bundles after changing a profile. If a module adds no rule or
vocabulary, use the project profile directly.
