---
type: Pattern
title: Protected lightweight change flow
description: Integrate small verified changes through one protected branch without imposing a hosting provider or team-sized approval model.
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
  id: guidance.pattern.protected-short-lived-change-flow
  owners:
    - team:gnostoa-maintainers
  scope:
    - generic-guidance
  relations:
    - kind: applies-to
      target: /reference/change-classification-and-approval.md
    - kind: guides
      target: /workflows/propose-review-merge-change.md
    - kind: applies-to
      target: /guardrails/non-negotiable.md
---

# Protected lightweight change flow

## Context

Direct changes to an integration branch lose review context and allow policy,
code, contracts and knowledge to drift independently. Requiring a separate
issue and heavyweight approval path for every mechanical correction creates a
different failure: work accumulates in long-lived branches and process records
duplicate the change request.

Hosting products use different names and enforcement features. The durable
contract is the engineering intent, not a GitHub- or GitLab-specific setting.

## Pattern

Use a trunk-based, change-request flow:

1. Protect the default integration branch.
2. Prohibit direct pushes, force pushes and branch deletion.
3. Make a small change on a short-lived branch.
4. Open a change request before integration.
5. Keep motivation, scope, evidence and review discussion in that request.
6. Require passing checks and resolved conversations.
7. Select any additional work-item, review and approval requirements from the
   declared change class and project specialization.
8. Delete the branch after integration.

The provider-neutral terms map as follows:

| Contract term | Common implementations |
|---|---|
| Work Item | GitHub/GitLab issue, Jira item or equivalent |
| Change Branch | Topic or feature branch |
| Change Request | Pull request or merge request |
| Review Owner | CODEOWNER or accountable team |
| Protected Integration Branch | Protected branch or repository ruleset |
| Required Verification | CI status check or pipeline |

Agents may prepare work items, branches, commits, evidence and change requests.
They do not bypass protection or satisfy a human approval gate when a
specialization requires one.

## Consequences

- Every integrated change has one reviewable evidence envelope.
- Small, short-lived branches reduce merge drift and context reconstruction.
- Work items capture problems that outlive a single change without duplicating
  every mechanical edit.
- Provider adapters and repository settings still require configuration.
- A solo maintainer can merge a self-authored change without inventing an
  independent reviewer, cooling-off period or formal attestation.
- Community contributions still receive normal maintainer review.
- Higher-assurance projects can add independent approvals and durable records
  without changing the generic flow.
