---
type: Pattern
title: Tiered centralized CI with advisory local feedback
description: Keep integration authoritative in centralized CI while reusing the same bounded commands in optional repository-managed hooks.
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
  - id: gitlab-merged-results
    resource: https://docs.gitlab.com/ci/pipelines/merged_results_pipelines/
    title: GitLab merged-results pipelines
x-project-knowledge:
  id: guidance.pattern.tiered-ci-and-local-feedback
  owners:
    - team:gnostoa-maintainers
  scope:
    - generic-guidance
  relations:
    - kind: guides
      target: /workflows/configure-continuous-integration.md
    - kind: depends-on
      target: /reference/continuous-integration-contract.md
    - kind: applies-to
      target: /guardrails/non-negotiable.md
---

# Tiered centralized CI with advisory local feedback

## Context

Local feedback is valuable before work consumes shared CI capacity, but client
configuration cannot establish repository-wide enforcement. Running the whole
verification portfolio at every local commit is slow and duplicates evidence.
Running only a late integration pipeline makes failures expensive to locate.

## Pattern

Make centralized CI the authoritative automated gate and layer feedback by
state transition:

| Transition | Evidence |
|---|---|
| Local commit or push preparation | Bounded `fast` suite through an advisory hook |
| Pushed branch revision | `policy` and `fast`; superseded runs may be cancelled |
| Change Request revision | `policy`, `fast`, `regression`, and applicable conditional suites |
| Merge candidate | The latest candidate with the same required portfolio |
| Integrated trunk revision | Required portfolio; failure starts restore-green recovery |
| Schedule | Applicable `extended` evidence |
| Release | Required evidence plus `release`, only for a deployable artifact |

Keep `.githooks/` in the repository and opt in with:

```bash
git config --local core.hooksPath .githooks
```

Hooks call the same `./ci/verify <suite>` interface as CI, avoid network access
and target seconds rather than minutes. A skipped, missing or bypassed hook
never satisfies a required check.

Central workflow implementations are reusable but immutable. Pin external
actions, components and runtime images; upgrade them through a reviewed Change
Request. A provider adapter maps native events to the generic vocabulary and
does not redefine suite meaning.

## Consequences

- Developers and agents receive early feedback without loading the full
  pipeline into every local action.
- The latest integration candidate has one auditable source of required
  evidence.
- Stable suite names make evidence traversable across providers and projects.
- Project specializations still own commands, test frameworks and deployment
  environments.
- Conditional and scheduled suites control cost but require an honest
  capability declaration.
