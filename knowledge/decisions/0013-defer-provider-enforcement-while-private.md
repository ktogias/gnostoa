---
type: Decision
title: Defer provider enforcement while the bootstrap repository is private
description: Keep integration gated while the current GitHub plan cannot enforce the lightweight baseline on a private repository.
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

Making the repository public before owner review would violate the
pre-publication gate. Silently treating an unprotected branch as protected
would violate the public contract. The current limitation is therefore a
temporary provider-side enforcement gap, not a reason to add manual ceremony.

## Decision

Keep the repository private during review. Do not merge the
publication-baseline Change Request or permit other integration while provider
enforcement is unavailable.

Use these compensating controls:

- retain all publication work in a draft Pull Request;
- run the active centralized GitHub verification workflow on every pushed
  revision and Pull Request candidate;
- keep repository CODEOWNERS explicit for ownership and community routing;
- use the publication matrix as a traversable owner-review aid rather than a
  formal sign-off ledger;
- prohibit direct updates to `main` by maintainer procedure;
- apply and audit branch protection before any post-bootstrap merge.

This exception expires immediately when either:

1. the account gains a plan that supports protection for the private
   repository; or
2. the approved publication procedure changes repository visibility and
   protection can be applied.

In either case, enforce required Pull Requests, required current-candidate
checks, resolved conversations and force-push/deletion prohibition before
integration resumes. Use zero required approvals while Gnostoa has one
maintainer; CODEOWNER and independent approvals activate only through a future
stricter specialization.
Reconsider this Decision no later than 2026-08-30 if neither trigger occurs.

## Consequences

- The source can receive centralized evidence and owner review while remaining
  private.
- The default branch is not mechanically protected during the temporary
  bootstrap window, so publication and merging remain blocked.
- The generic policy is not weakened to match a provider-plan limitation.
- Publication requires explicit proof that effective provider settings match
  the policy; this Decision cannot be used as a permanent bypass.
- Upgrading the plan is optional because protection can also become available
  at the later approved public-visibility gate.
