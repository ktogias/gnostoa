---
type: Decision
title: Use versioned public schema identifiers
description: Give every Gnostoa JSON Schema a stable absolute identity under the project's publication namespace.
status: draft
generated:
  by: codex/gpt-5
  at: "2026-07-30T00:00:00Z"
sources:
  - id: json-schema-identification
    resource: https://json-schema.org/understanding-json-schema/structuring#id
    title: JSON Schema identification
  - id: uri-generic-syntax
    resource: https://www.rfc-editor.org/rfc/rfc3986
    title: URI generic syntax
  - id: github-pages-project-sites
    resource: https://docs.github.com/en/pages/getting-started-with-github-pages/what-is-github-pages
    title: GitHub Pages project-site locations
x-project-knowledge:
  id: kit.decision.0012.versioned-public-schema-identifiers
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governs
      target: /contracts/public-inheritance-surface.md
    - kind: verifies
      target: /requirements/prevent-policy-drift.md
---

# Use versioned public schema identifiers

## Context

The unpublished schemas used reserved `example.org` identifiers. Those values
were suitable placeholders, but they could not provide a durable identity for
schemas inherited by independent projects.

JSON Schema identifies schema documents with non-relative URIs. An identifier
does not have to trigger network retrieval, but a public HTTPS identity is
easier for people and tools to inspect when the same path can be projected to
the project site.

The canonical Gnostoa repository is owned at `ktogias/gnostoa`. Its default
GitHub Pages project-site location is therefore under
`https://ktogias.github.io/gnostoa/`.

## Decision

Identify each public schema as:

```text
https://ktogias.github.io/gnostoa/schemas/v1/<schema-file>
```

Treat `v1` as the major version of the schema contract, independently of the
toolkit package version. Backward-compatible corrections retain the `v1`
identity. A breaking schema contract receives a new major path and explicit
migration guidance.

Keep `schemas/` as the canonical source directory. The documentation builder
projects those files to `schemas/v1/`; local validators continue to load bundled
files and do not depend on network access.

Do not silently rewrite existing schema IDs after a repository transfer or
custom-domain adoption. Preserve the published endpoint or provide a durable
redirect before introducing a new identifier.

## Consequences

- Public schemas have unique, absolute and versioned identifiers.
- Schema resolution remains deterministic and offline for normal validation.
- The derived project site can expose the same bytes at their identifiers.
- The publication namespace includes the initial repository owner, so a future
  transfer must preserve compatibility rather than renaming IDs casually.
- This decision remains draft until independent human semantic review confirms
  the permanence and ownership trade-off.
