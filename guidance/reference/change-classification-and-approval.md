---
type: Reference
title: Change classification and approval
description: Select work-item, review and decision evidence from impact rather than applying one heavyweight path to every diff.
status: draft
generated:
  by: codex/gpt-5
  at: "2026-07-29T00:00:00Z"
sources:
  - id: github-reviews
    resource: https://docs.github.com/en/pull-requests/reference/pull-request-reviews
    title: GitHub pull request reviews
  - id: gitlab-approvals
    resource: https://docs.gitlab.com/user/project/merge_requests/approvals/
    title: GitLab merge request approvals
x-project-knowledge:
  id: guidance.reference.change-classification-and-approval
  owners:
    - team:gnostoa-maintainers
  scope:
    - generic-guidance
  relations:
    - kind: operationalizes
      target: /patterns/protected-short-lived-change-flow.md
    - kind: guides
      target: /workflows/propose-review-merge-change.md
    - kind: applies-to
      target: /workflows/daily-change-loop.md
---

# Change classification and approval

## Purpose

Provide one stable classification that developers, reviewers, agents and CI can
use to determine required evidence and approval without loading project-specific
process documentation.

## Content

The generic baseline is canonical in `core/change-control.yaml`. Its classes
are:

| Class | Typical scope | Work Item | Minimum approval |
|---|---|---|---|
| `mechanical` | Typo, formatting or reproducible generated output with no semantic change | Optional | CI; auto-merge may be allowed |
| `normal` | Bounded implementation, test, draft knowledge or non-breaking documentation | Optional when the Change Request fully states the problem | One independent human |
| `normative` | Policy, profile, schema, stable knowledge or public contract behavior | Required | One human CODEOWNER plus Decision |
| `critical` | Breaking, security, release, runtime or high-blast-radius change | Required | Two human approvals plus Decision |
| `emergency` | Time-critical restoration when the normal pre-merge path is unsafe | Follow-up required | Break-glass audit and human follow-up review |

A Work Item describes the problem, desired outcome, scope and acceptance
criteria. A Change Request describes the chosen solution and its verification.
Do not copy the same narrative into both; link them.

Classification follows the highest impact of the diff. A change is not
`mechanical` if it changes meaning, accepted inputs, generated output semantics,
authority, policy, dependency trust or a stable claim.

Projects inherit the baseline and may strengthen it. For example, a project may
require one approval for mechanical changes or three approvals for critical
changes. It may not enable direct pushes, allow agents to approve their own
changes or lower inherited approval requirements.

## Usage

1. Classify before implementation and record the class in the Change Request.
2. Create a Work Item before coding when required.
3. Add a Decision for normative or critical changes.
4. Reclassify upward when the diff grows or reveals broader impact.
5. Apply the strictest class when a change spans several concerns.
6. Use `emergency` only with an identified incident, authorized human,
   compensating controls and a required post-event review.

Validate a project specialization with:

```bash
knowledge check-change-policy --policy .knowledge/change-control.yaml
```
