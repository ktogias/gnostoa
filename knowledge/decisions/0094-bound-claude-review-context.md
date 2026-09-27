---
type: Decision
title: Bound Claude review context by selecting agent mode instead of tag-mode history assembly
description: Replace the mention workflow's unbounded tag-mode context assembly with an agent-mode prompt whose every interpolated source is independent of discussion length, and record the loss of on-Pull-Request delivery as an explicit trade.
status: draft
generated:
  by: anthropic/claude-opus-5
  at: "2026-09-27T11:00:00Z"
sources:
  - id: work-item
    resource: https://github.com/ktogias/gnostoa/issues/326
    title: Bound Claude review context so invocation does not fail on large Pull Requests
  - id: owning-objective
    resource: https://github.com/ktogias/gnostoa/issues/15
    title: Automate deterministic knowledge-workflow mechanics without weakening assurance
  - id: hardening-decision
    resource: ./0093-harden-claude-code-github-actions-workflows.md
    title: Harden the Claude Code GitHub Actions workflows
  - id: observed-failure
    resource: https://github.com/ktogias/gnostoa/pull/319#issuecomment-5854764807
    title: Measured tag-mode context exhaustion on PR 319
  - id: mode-detector
    resource: https://github.com/anthropics/claude-code-action/blob/9171db3e57d6a3140a37ddc2ba92788584e0ead6/src/modes/detector.ts
    title: Pinned action mode detection
  - id: agent-mode
    resource: https://github.com/anthropics/claude-code-action/blob/9171db3e57d6a3140a37ddc2ba92788584e0ead6/src/modes/agent/index.ts
    title: Pinned action agent mode prompt assembly
  - id: data-fetcher
    resource: https://github.com/anthropics/claude-code-action/blob/9171db3e57d6a3140a37ddc2ba92788584e0ead6/src/github/data/fetcher.ts
    title: Pinned action tag-mode GitHub data fetcher
x-project-knowledge:
  id: kit.decision.0094.bound-claude-review-context
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: references
      target: /decisions/0093-harden-claude-code-github-actions-workflows.md
    - kind: governed-by
      target: /decisions/0018-adopt-evidence-gated-capability-evolution-for-gnostoa-self-governance.md
    - kind: governed-by
      target: /decisions/0062-require-proportionate-prior-art-and-reuse-review.md
    - kind: verified-by
      target: /decisions/0093-harden-claude-code-github-actions-workflows.md
---

# Bound Claude review context by selecting agent mode instead of tag-mode history assembly

## Context

Decision 0093 hardened the owner-installed Claude workflows. It did not bound the
context those workflows assemble, because at installation time the reviewed Pull
Requests were small.

In the pinned action, `src/github/data/fetcher.ts` retrieves issue comments,
reviews, review comments and the changed-file list for tag mode with **no cap on
comment or review count**. The assembled prompt therefore grows with the
discussion rather than with the change.

Measured on PR #319 — same workflow, same pinned action, same model:

| | 2026-09-26 20:43 | 2026-09-27 08:23 |
|---|---|---|
| `FINAL PROMPT` | 1,418 lines / 163,864 B | 5,858 lines / 446,488 B |
| `is_error` | false | true |
| `total_cost_usd` | $4.24 | $0 |
| `num_turns` | 6 | 1 |
| `duration_ms` | 119,273 | 647 |

Zero cost with an empty `modelUsage` means the model was never called: the
rejection happens before dispatch. Four consecutive invocations failed this way.
PR #319 carries 676 comments and 1,099,660 bytes of discussion, of which the
accountable owner authored 70%, so `exclude_comments_by_actor` over the reviewer
bots removes roughly 30% and cannot approach the size that worked.

## Prior-art and reuse disposition

Reuse Decision 0093 unchanged: its eight hardening rules and
`tests/test_claude_actions_workflows.py` remain the authority for pins,
credential-free checkouts, token scope, trigger gating and bounded execution.
This Decision adds one orthogonal property and touches none of them.

Two alternatives were measured or read before choosing:

- **`exclude_comments_by_actor` / `include_comments_by_actor`.** The only
  context-reducing inputs the pinned action offers. Rejected as insufficient on
  the measured distribution, and an allowlist that drops owner comments would
  remove exactly the dispositions a reviewer needs.
- **A rolling summarisation digest of the discussion.** Rejected as a second
  artifact that must be maintained and can drift. The repository has already
  observed that failure mode: a transcribed test count in an assessment was
  reported stale four times while the subject moved from 103 to 120.

No new dependency, service or runtime is introduced.

## Decision

1. The mention workflow supplies a `prompt` input. Per
   `src/modes/detector.ts`, supplying `prompt` selects **agent mode** even on
   comment events; per `src/modes/agent/index.ts` agent mode builds the prompt as
   the supplied text alone and fetches no GitHub data. Bounded context is
   therefore obtained by mode selection, not by summarisation.
2. Every interpolated source in that prompt must be independent of discussion
   length. The admitted set is the repository identity, the issue or Pull Request
   number, head and base SHAs, the issue or Pull Request body, the triggering
   comment body, the triggering review body and the issue title. Any expression
   outside that set fails the contract test.
3. The static prompt is bounded at 4096 bytes. Total context is then the prompt
   plus one comment body plus one Pull Request description, none of which scales
   with the number of comments.
4. The prompt must forward the triggering request. Agent mode ignores the comment
   body unless the template interpolates it, so an unforwarded mention would
   review nothing while appearing to succeed.
5. Context is obtained by **retrieval rather than pre-loading**. The prompt names
   what to review and where to look; the reviewer uses its own tools to read the
   diff and the files it needs. Nothing is lossily pre-summarised.
6. The Pull Request description is the one curated state input. On Gnostoa-self
   candidates it is already an agent-maintained current-state projection, so it
   carries dispositions without carrying the transcript.
7. Because the reviewer no longer receives the discussion, the prompt instructs it
   to raise a possibly-settled point as a question rather than as an assertion.

## Accepted trade: delivery is no longer on the Pull Request

Agent mode sets `claudeCommentId: undefined` and provides **no GitHub
comment-posting tool**. A review therefore cannot post itself to the Pull
Request through the action.

Posting would require write scope on `GITHUB_TOKEN`, which Decision 0093 rule 4
forbids. That rule is not amended here. Results are delivered through
`display_report: true`, which writes the report to the workflow run's step
summary.

The consequence is explicit: **bounded context is bought at the cost of inline
Pull Request delivery.** The review is durable and linkable from the run, but it
is not in the Pull Request record and peer reviewers do not see it. Restoring
on-Pull-Request delivery without widening `GITHUB_TOKEN` is a separate question
and is not admitted by this Decision.

## Consequences

Bounded review context becomes available on Pull Requests of any size, and the
mention path stops failing before dispatch. In exchange, a review is delivered to
the workflow run rather than to the Pull Request, and the reviewer no longer sees
the discussion, so it may re-raise a settled point as a question. Restoring inline
delivery without widening `GITHUB_TOKEN` remains open.

## What this Decision does not change

Decision 0093's hardening rules; the automatic review workflow's triggers;
`GITHUB_TOKEN` scope; `allowed_bots`, `allowed_non_write_users` or
`assignee_trigger`. A Claude review remains advisory evidence. It is not reviewer
qualification under Decision 0089, does not populate a protected qualification
snapshot, and carries no approval or merge authority.

## Verification

`tests/test_claude_actions_workflows.py` enforces agent-mode selection, the
bounded interpolation set, the static prompt bound, forwarding of the triggering
request, and the explicit delivery path — alongside every existing Decision 0093
invariant. The `immutable-provider-ci-adapters` guardrail owns the workflows,
both Decisions and that test.

Effectiveness is not claimed by this Decision. It is established only when a
mention on a Pull Request of #319's size completes with a non-zero
`total_cost_usd` and more than one turn.
