---
type: Decision
title: Record initial copyright ownership
description: Attribute the initial Gnostoa work to Konstantinos Togias while contributors retain copyright in later contributions.
status: draft
generated:
  by: codex/gpt-5
  at: "2026-07-29T00:00:00Z"
x-project-knowledge:
  id: kit.decision.0011.record-initial-copyright-ownership
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governs
      target: /project/gnostoa.md
    - kind: depends-on
      target: /decisions/0010-license-gnostoa-under-apache-2.0.md
---

# Record initial copyright ownership

## Context

Decision 0010 deliberately deferred ownership-specific attribution until the
relevant facts were established. Konstantinos Togias subsequently identified
himself using the legal name `Konstantinos Togias`, selected copyright year
2026, confirmed authority to license the current work and selected a model in
which later contributors retain copyright in their contributions.

The repository needs one consistent attribution across source distributions,
Python package metadata and OCI images. Copyright ownership must remain
distinct from project-maintainer roles and from ownership or registration of
the Gnostoa name as a trademark.

Before implementation,
`python -m unittest tests.test_tools.LicensePolicyTests.test_initial_owner_and_contributor_retention_are_consistent -v`
failed because the repository had no `NOTICE` file.

## Decision

Record the initial-work attribution as:

```text
Gnostoa
Copyright 2026 Konstantinos Togias
```

Include that `NOTICE` in source and package distributions. Record Konstantinos
Togias as author in Python and OCI metadata.

Contributors retain copyright in their contributions and intentionally
submitted contributions are licensed under Apache-2.0 as defined by Section 5
of the license. Do not require copyright assignment or a Contributor License
Agreement unless a later governance Decision establishes a concrete need.

Do not interpret this attribution as ownership of every future contribution,
as a change to accountable maintainer roles, or as trademark registration.

## Consequences

- Initial ownership and distribution metadata have one explicit source of
  truth.
- Future contributors retain copyright while recipients receive the
  Apache-2.0 grants attached to their contributions.
- Contributors must confirm that employment, institutional, grant and
  third-party rights permit their submission.
- Git history and applicable file notices preserve contributor provenance;
  `NOTICE` grows only for attribution that must accompany distributions.
- Trademark ownership and usage policy remain outside this copyright Decision.
