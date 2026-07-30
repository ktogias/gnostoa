---
type: Decision
title: Make centralized tiered CI authoritative and local hooks advisory
description: Validate every integration candidate through provider-neutral centralized gates while keeping local hooks fast and bypass-tolerant.
status: draft
generated:
  by: codex/gpt-5
  at: "2026-07-29T00:00:00Z"
sources:
  - id: dora-continuous-integration
    resource: https://dora.dev/capabilities/continuous-integration/
    title: DORA continuous integration
  - id: git-hooks
    resource: https://git-scm.com/docs/githooks
    title: Git hooks
  - id: github-required-checks
    resource: https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/collaborating-on-repositories-with-code-quality-features/troubleshooting-required-status-checks
    title: GitHub required status checks
  - id: github-reusable-workflows
    resource: https://docs.github.com/en/actions/concepts/workflows-and-actions/reusing-workflow-configurations
    title: GitHub reusable workflows
  - id: gitlab-ci-components
    resource: https://docs.gitlab.com/ci/components/
    title: GitLab CI/CD components
x-project-knowledge:
  id: kit.decision.0008.authoritative-tiered-continuous-integration
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: implements
      target: /requirements/centralized-ci-verifies-integration-candidates.md
    - kind: governs
      target: /runbooks/maintain-the-kit.md
    - kind: references
      target: /decisions/0007-verification-first-development.md
---

# Make centralized tiered CI authoritative and local hooks advisory

## Context

The toolkit requires protected integration, required checks and
proportionate verification evidence, but does not yet define which repository events
must run which evidence tiers. Its consumer adapters validate knowledge and
policy but cannot prove that a project runs its application regression suites.
It also has no portable local hook contract.

Running every slow test at every local commit, push and merge duplicates work,
increases cost and encourages bypass. Relying on client hooks for enforcement
is unsafe because hook installation is local and hooks can be absent or
bypassed. Hard-coding one hosting product into the generic core would weaken
portability.

## Decision

1. Centralized CI is the authoritative automated enforcement boundary.
2. Validate each pushed branch revision with policy and fast evidence; validate
   the latest Change Request and merge-candidate revisions with required
   regression evidence.
3. Validate the integrated trunk revision and restore green immediately after
   failure.
4. Run expensive or environment-dependent evidence through conditional,
   scheduled or release tiers rather than every local commit.
5. Treat repository-managed Git hooks as recommended, bounded local feedback.
   Hooks call the same project-owned verification interface as CI but never
   satisfy a required status check.
6. Define the policy, event vocabulary, evidence tiers and non-weakening rules
   independently of a hosting provider.
7. Implement GitHub, GitLab and future systems as adapters. Central reusable
   workflows or components are versioned and pinned to immutable revisions.
8. A project declares its verification capabilities and suite commands in a
   validated manifest. Stack-specific implementations stay in the narrowest
   specialization.
9. Continuous delivery gates apply only when a project declares a deployable
   artifact. Promotion reuses the exact CI artifact instead of rebuilding it
   between environments.
10. Required workflows use least privilege, immutable dependencies and no
    privileged secrets for untrusted changes.

## Consequences

- Required checks have stable meaning across repositories and providers.
- Fast feedback remains available without forcing the full portfolio into
  local hooks.
- A thin provider adapter can inherit centrally maintained behavior without
  copying its policy.
- Verification manifests add a small project-owned integration surface.
- Conditional capabilities avoid ceremonial integration, deployment or load
  tests for projects that do not have those behaviors.
- CI usage and queue latency require active measurement and optimization.
- Enforcement remains hybrid where provider settings or semantic relevance
  cannot be established from repository files alone.
