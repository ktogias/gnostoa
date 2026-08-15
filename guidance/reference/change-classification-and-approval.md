---
type: Reference
title: Change classification and review
description: Select proportionate records, verification and review from impact without imposing a heavyweight path on small projects.
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

# Change classification and review

## Purpose

Provide one stable classification that developers, maintainers, agents and CI
can use to determine proportionate evidence without loading project-specific
process documentation.

## Content

The generic baseline is canonical in `core/change-control.yaml`. Its classes
are:

| Class | Typical scope | Separate Work Item | Generic merge gate |
|---|---|---|---|
| `mechanical` | Typo, formatting or reproducible generated output with no semantic change | Optional | CI; auto-merge may be allowed |
| `normal` | Bounded implementation, test, draft knowledge or non-breaking documentation | Optional when the Change Request states the problem | Passing checks and accountable maintainer review |
| `normative` | Policy, profile, schema, stable knowledge or public contract behavior | Optional; use one when rationale must outlive the Change Request | Passing checks and accountable semantic review |
| `critical` | Breaking, security, release, runtime or high-blast-radius change | Optional in the baseline; strongly consider a durable record | Required verification and explicit maintainer review |
| `emergency` | Time-critical restoration when the normal pre-merge path is unsafe | Follow-up required | Scoped break-glass change and accountable follow-up |

A Work Item describes the problem, desired outcome, scope and acceptance
criteria. A Change Request describes the chosen solution and its verification.
Do not copy the same narrative into both; link them.

Classification follows the highest impact of the diff. A change is not
`mechanical` if it changes meaning, accepted inputs, generated output semantics,
authority, policy, dependency trust or a stable claim.

The generic baseline deliberately supports a solo maintainer: it requires no
formal approval, cooling-off period, owner attestation or separate issue for a
self-authored Change Request. The maintainer still inspects the final diff and
semantic impact before merging. A community contribution should be reviewed by
an accountable maintainer because author and maintainer are different people.

Projects inherit the baseline and may strengthen it. For example, a
specialization may require a Decision, one independent CODEOWNER approval for
normal changes, or two approvals for critical changes. It may not enable direct
pushes, allow agents to satisfy a required human gate or lower inherited
requirements.

## Usage

1. Classify before implementation and record the class in the Change Request.
2. Create a separate Work Item only when policy requires it or the problem
   context will not fit cleanly in the Change Request.
3. Add a Decision when policy requires it or architectural rationale must
   remain independently discoverable.
4. Reclassify upward when the diff grows or reveals broader impact.
5. Apply the strictest class when a change spans several concerns.
6. Use `emergency` only with an identified incident, accountable maintainer,
   bounded impact and a required post-event review.

Validate a project specialization with:

```bash
knowledge check-change-policy --policy .knowledge/change-control.yaml
```
