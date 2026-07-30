---
type: Workflow
title: Resume and hand off a bounded change
description: Preserve only the live state needed to resume unfinished repository work across people, agents and sessions.
status: draft
generated:
  by: codex/gpt-5.6
  at: "2026-07-30T00:00:00Z"
x-project-knowledge:
  id: guidance.workflow.resume-and-handoff-change
  owners:
    - team:gnostoa-maintainers
  scope:
    - generic-guidance
  relations:
    - kind: operationalizes
      target: /patterns/protected-short-lived-change-flow.md
    - kind: depends-on
      target: /workflows/develop-verification-first.md
    - kind: governed-by
      target: /guardrails/non-negotiable.md
---

# Resume and hand off a bounded change

## Outcome

A person or software agent can start from the repository, recover the current
purpose and state of one unfinished change, detect drift, and continue with one
explicit next action without replaying prior conversations.

## Preconditions

- The effective change-control policy has been resolved.
- The change has a bounded outcome and an accountable owner.
- Git branch and worktree state can be inspected.
- The shared `knowledge task` command is available through the pinned toolkit
  runtime or supported native fallback.

Use an Execution Plan when policy requires one, when work will cross an actor
or session boundary, or when complexity, uncertainty or recovery cost makes
reconstruction expensive. Skip it for a short local change when policy marks it
optional. The plan complements, rather than replaces, these authorities:

| Artifact | Authority |
|---|---|
| Work Item | Problem, outcome, scope and acceptance criteria |
| Decision | Durable rationale and consequences |
| Execution Plan | Current progress, evidence, discoveries and next action |
| Repository | Actual implementation and branch/worktree state |
| Change Request | Review discussion, candidate revision and integration evidence |

## Procedure

### Start

1. Inspect the actual branch, revision and worktree before trusting inherited
   prose or chat context.
2. Classify the change. Create or link the Work Item and Decision only when the
   effective policy requires them.
3. Copy
   [`templates/execution-plan.project.yaml`](../../templates/execution-plan.project.yaml)
   to the project's active-plan location. Keep one plan per active change and
   replace every example value.
4. Link authoritative artifacts instead of copying their content. Record a
   bounded outcome, inclusions, exclusions, affected contracts, current work,
   remaining work and one executable next action.
5. Run `knowledge task start --plan <path>`. Establish and record the
   pre-change evidence required by the effective verification policy before
   implementation.

### Resume

1. Read the repository's short agent/developer router, then the selected plan.
   Load only its linked contracts, Work Item and Decisions.
2. Run `knowledge task resume --plan <path>`. Resolve unexpected branch or
   worktree state before editing. Do not discard changes whose ownership is
   unknown.
3. Reconcile meaning as well as files: the Work Item owns scope, Decisions own
   rationale, and the repository owns actual code. Update the authoritative
   source before continuing when the plan contradicts it.
4. Continue from `next_action`; do not reconstruct a different task from a raw
   transcript.

### Checkpoint

1. Update only durable state: completed/current/remaining work, material
   discoveries with evidence, verification results and the next action.
2. Set `handoff.expected_worktree` to the exact changed paths that belong to
   the task. The command treats the selected plan file itself as expected while
   starting, resuming or checkpointing. Keep unrelated or unexplained paths out
   of the task.
3. Run `knowledge task checkpoint --plan <path>`. A local checkpoint may
   describe an expected dirty worktree, but it is not ready for transfer.
4. Keep prompts, private reasoning, token-by-token narratives and exhaustive
   command output outside the plan. Temporary diagnostic logs remain
   noncanonical and may be discarded.

### Hand off

1. Reduce the work to a coherent committed checkpoint. Update the plan,
   verification evidence and affected contracts before the checkpoint commit.
2. Set the handoff status to `ready`, identify the recipient or next role,
   summarize only material risk, and set `expected_worktree` to an empty list.
3. Commit the checkpoint, then run `knowledge task handoff --plan <path>`.
   Never declare a dirty or unexplained worktree ready.
4. Render the managed Change Request block with
   `knowledge task render-change-request --plan <path>` and replace the prior
   managed block. Validate a saved provider body with
   `knowledge task check-change-request --plan <path> --body <path>`.
5. The receiving person or agent reruns `resume`, changes handoff status to
   `accepted`, and records itself as an author only after making a durable
   contribution. An evaluator records an evaluation role separately; this does
   not satisfy a required human approval.

### Complete

1. Reconcile scope and evidence against the Work Item and current repository
   candidate.
2. Set plan status to `review-ready` before review and `complete` only after its
   outcome is integrated or otherwise closed.
3. Keep completed plans according to the project's retention policy or archive
   them outside the active-plan route. The Change Request remains the durable
   integration record; do not preserve an unbounded duplicate activity log.

## Verification

- The plan validates against `schemas/execution-plan.schema.json`.
- Its linked local Decisions and contracts exist.
- Resume and checkpoint commands report the expected branch and worktree.
- A ready handoff has an identified recipient and clean committed worktree.
- The managed Change Request block names the current candidate revision.
- Scope, rationale, current state and review evidence each remain in their
  designated authority.
- Agent authorship/evaluation provenance is visible but is not misrepresented
  as independent human approval.

## Recovery

If no plan exists, inspect the Work Item, Decisions, Change Request and Git
history, then create the smallest plan that describes current observable state;
do not invent prior progress. If plan and repository disagree, preserve unknown
changes, mark the plan `blocked`, record the discrepancy as a discovery and ask
the accountable owner only when evidence cannot resolve it. If the managed
Change Request block is stale, regenerate it from the validated plan and actual
candidate revision instead of editing its fields independently.
