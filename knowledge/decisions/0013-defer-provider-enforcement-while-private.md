---
type: Decision
title: Defer provider enforcement while the bootstrap repository is private
description: Keep publication and merge gates closed when the current GitHub plan cannot enforce branch protection on a private repository.
status: draft
generated:
  by: codex/gpt-5
  at: "2026-07-30T00:00:00Z"
sources:
  - id: publication-baseline-work-item
    resource: https://github.com/ktogias/gnostoa/issues/1
    title: Prepare the protected Gnostoa publication baseline
  - id: github-branch-protection
    resource: https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches
    title: About protected branches
x-project-knowledge:
  id: kit.decision.0013.defer-provider-enforcement-while-private
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: references
      target: /decisions/0006-provider-neutral-change-governance.md
    - kind: governs
      target: /contracts/public-inheritance-surface.md
    - kind: verified-by
      target: /runbooks/review-publication-baseline.md
---

# Defer provider enforcement while the bootstrap repository is private

## Context

The unpublished baseline is hosted in a private repository under a personal
GitHub account. An attempt to enable protection for `main` through the GitHub
branch-protection API returned HTTP 403 with the provider requirement to upgrade
the account plan or make the repository public.

Making the repository public before semantic review would violate the
pre-publication gate. Silently weakening the inherited change policy would
violate the public contract. The current limitation is therefore a temporary
provider-side enforcement gap, not a policy change.

## Decision

Keep the repository private and keep the normative policy unchanged. Do not
merge the publication-baseline Change Request or permit other integration while
provider enforcement is unavailable.

Use these compensating controls:

- retain all publication work in a draft Pull Request;
- run the active centralized GitHub verification workflow on every pushed
  revision and Pull Request candidate;
- keep repository CODEOWNERS explicit even though the provider cannot enforce
  its approval on the current private plan;
- require the complete independent-human review matrix before publication;
- prohibit direct updates to `main` by maintainer procedure;
- apply and audit branch protection before any post-bootstrap merge.

This exception expires immediately when either:

1. the account gains a plan that supports protection for the private
   repository; or
2. the approved publication procedure changes repository visibility and
   protection can be applied.

In either case, enforce required Pull Requests, strict current-branch checks,
CODEOWNER review, stale-review dismissal, resolved conversations, linear
history, and force-push/deletion prohibition before integration resumes.
Reconsider this Decision no later than 2026-08-30 if neither trigger occurs.

## Consequences

- The source can receive centralized evidence and human review while remaining
  private.
- The default branch is not mechanically protected during the temporary
  bootstrap window, so publication and merging remain blocked.
- The generic policy is not weakened to match a provider-plan limitation.
- Publication requires explicit proof that effective provider settings match
  the policy; this Decision cannot be used as a permanent bypass.
- Upgrading the plan is optional because protection can also become available
  at the later approved public-visibility gate.
