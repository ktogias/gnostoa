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
  - id: openssf-scorecard-checks
    resource: https://github.com/ossf/scorecard/blob/main/docs/checks.md
    title: OpenSSF Scorecard checks
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
    - kind: references
      target: /decisions/0013-defer-provider-enforcement-while-private.md
    - kind: references
      target: /decisions/0014-strengthen-gnostoa-self-governance.md
---

# Adopt provider-neutral risk-based change governance

## Context

Canonical knowledge and policy changes need an audit trail, CI evidence and
accountable semantic review. Mandating a separate issue and multiple approvals
for every typo or deterministic regeneration would increase queue time,
encourage oversized changes and duplicate information already present in a
Change Request. Naming GitHub as part of the public contract would also be
incorrect for GitLab, self-hosted and non-forge environments.

When this Decision was prepared, the repository was an unpublished local
bootstrap with no baseline commit, remote or protected integration branch. The
workflow being introduced could not govern commits that preceded its own
existence. A later bootstrap commit or remote does not retroactively change
that historical exception and does not establish a protected integrated
baseline.

## Decision

Adopt a provider-neutral trunk-based flow with a protected default branch,
bounded Change Branches, mandatory Change Requests, required checks, resolved
conversations and optional stricter Work Item and approval requirements.

Publish a community-light inheritable policy in `core/change-control.yaml`.
Allow projects to strengthen but not weaken it. Keep toolkit-internal
specialization outside that public contract.
[Decision 0014](0014-strengthen-gnostoa-self-governance.md) records Gnostoa's
choice to require a durable issue, Decision and test-first chronology for its
own normal, normative and critical changes.

Agents may author changes and assemble evidence. They may not approve their own
work where an independent gate is configured, bypass controls or promote stable
knowledge without a human.

The generic baseline requires a protected default branch, Change Request,
required checks and resolved conversations. It does not require a separate
issue, formal approval, cooling-off period, owner attestation or Decision for a
self-authored change. The accountable maintainer inspects the final diff before
merge; community contributions receive maintainer review. Specializations can
add independent approvals, mandatory Decisions and earlier evidence timing.

Treat only the commits that materialize the unpublished first candidate as the
single bootstrap exception. The exception does not authorize integration
without effective provider protection. The first reviewed baseline may enter
the default branch only after required protection is effective. If the provider
cannot protect the private repository, either that capability must become
available or a separately authorized visibility change and verified protection
must precede merge, as recorded in
[Decision 0013](0013-defer-provider-enforcement-while-private.md). All later
changes follow the new policy. The exception does not waive tests, bundle
validation or human review of the baseline before source publication.

## Consequences

- The public contract remains portable across GitHub, GitLab and other forges.
- Every integrated change has a reviewable evidence envelope.
- Work Items and Decisions are used when rationale must outlive a single Change
  Request, not as mandatory wrappers around routine work.
- Policy specializations can increase approvals and shorten branch lifetime.
- Gnostoa's stricter self-policy does not become a consumer requirement.
- Repository protection settings remain provider-side controls and must be
  configured and audited separately.
- Solo maintainers can use the baseline honestly without fabricated reviewers
  or recurring exceptions.
