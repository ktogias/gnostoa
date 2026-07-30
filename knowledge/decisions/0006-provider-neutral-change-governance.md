---
type: Decision
title: Adopt provider-neutral risk-based change governance
description: Protect integration without requiring a heavyweight issue and approval path for every low-risk project change.
status: draft
generated:
  by: codex/gpt-5
  at: "2026-07-29T00:00:00Z"
sources:
  - id: github-flow
    resource: https://docs.github.com/en/get-started/using-github/github-flow
    title: GitHub flow
  - id: dora-trunk
    resource: https://dora.dev/capabilities/trunk-based-development/
    title: DORA trunk-based development
  - id: github-protected-branches
    resource: https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches
    title: GitHub protected branches
  - id: gitlab-protected-branches
    resource: https://docs.gitlab.com/user/project/repository/branches/protected/
    title: GitLab protected branches
x-project-knowledge:
  id: kit.decision.0006.provider-neutral-change-governance
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governs
      target: /contracts/public-inheritance-surface.md
    - kind: implements
      target: /requirements/reviewed-change-control.md
    - kind: verified-by
      target: /runbooks/maintain-the-kit.md
---

# Adopt provider-neutral risk-based change governance

## Context

Canonical knowledge and policy changes need an audit trail, CI evidence and
accountable semantic review. Mandating a separate issue and multiple approvals
for every typo or deterministic regeneration would increase queue time,
encourage oversized changes and duplicate information already present in a
Change Request. Naming GitHub as part of the public contract would also be
incorrect for GitLab, self-hosted and non-forge environments.

This repository is still an unpublished bootstrap: it has no baseline commit,
remote or protected integration branch. The workflow being introduced therefore
cannot govern the commits that precede its own existence.

## Decision

Adopt a provider-neutral trunk-based flow with a protected default branch,
short-lived Change Branches, mandatory Change Requests, required checks,
resolved conversations and risk-based Work Item and approval requirements.

Publish the minimum inheritable policy in `core/change-control.yaml`. Allow
projects to strengthen but not weaken it. Maintain the stricter toolkit policy
in `policy/change-control.yaml`; the kit requires one independent human approval
even for mechanical changes and two for critical changes.

Agents may author changes and assemble evidence. They may not approve their own
work, bypass controls or promote stable knowledge without a human.

Treat the current unpublished implementation as the single bootstrap exception.
The first published baseline must enable repository protection immediately;
all later changes follow the new policy. The exception does not waive tests,
bundle validation or a human review of the baseline before publication.

## Consequences

- The public contract remains portable across GitHub, GitLab and other forges.
- Every integrated change has a reviewable evidence envelope.
- Work Items are required when rationale must outlive a single Change Request,
  not for every mechanical edit.
- Policy specializations can increase approvals and shorten branch lifetime.
- Repository protection settings remain provider-side controls and must be
  configured and audited separately.
- Small or single-maintainer teams need another accountable human before they
  can satisfy the toolkit's self-policy.
