---
name: change-lifecycle
description: Start, resume, checkpoint, hand off, or prepare review for a repository change using its Work Item, Decision, bounded Execution Plan, Git state, verification evidence, and managed Change Request context. Use when beginning non-mechanical work, taking over work from another person or agent, recovering after a session boundary, preparing a checkpoint, or detecting scope and metadata drift.
---

# Change Lifecycle

Use the repository's own lifecycle contract so another person or agent can
continue without prior chat history. Keep the plan bounded and evidence-based.

## Orient

1. Read the nearest `AGENTS.md` and the effective change-control policy.
2. Inspect `git status --short --branch` and `git rev-parse HEAD`.
3. Locate the plan linked by the Work Item or Change Request. If policy
   requires a plan and none exists, copy `templates/execution-plan.project.yaml`
   and fill it before implementation.
4. Read the selected plan, then only its linked Work Item, Decisions and
   contracts. Do not load all project knowledge.

## Start or resume

- For new work, confirm class, scope, branch and required records; run
  `knowledge task start --plan <path>`.
- For inherited work, run `knowledge task resume --plan <path>`. Resolve branch
  or worktree drift before editing and preserve unexplained changes.
- Treat the Work Item as scope authority, Decisions as rationale authority, Git
  as implementation authority and the plan as current-state authority.
- Continue from `next_action`. Update the authoritative artifact first if the
  sources disagree.

## Checkpoint

1. Record completed/current/remaining work, material discoveries with evidence,
   verification results and one concrete next action.
2. Set `handoff.expected_worktree` to the exact task-owned changed paths.
3. Run `knowledge task checkpoint --plan <path>`.
4. Do not copy prompts, private reasoning, raw transcripts or exhaustive
   command logs into the plan.

## Hand off or prepare review

1. Update the plan and contracts, then commit a coherent checkpoint.
2. Set handoff to `ready`, identify the next person or role, summarize material
   risk and set `expected_worktree` to `[]`.
3. After committing, run `knowledge task handoff --plan <path>`. Do not claim a
   dirty or unexplained worktree is ready.
4. Render the managed provider block with
   `knowledge task render-change-request --plan <path>` and replace the old
   complete block. Check a saved body with
   `knowledge task check-change-request --plan <path> --body <path>`.
5. Record authors and evaluators separately. Agent evaluation is evidence, not
   independent human approval.

## Complete

Run the project verification contract, reconcile the final scope and evidence,
set status `review-ready`, and ensure the managed candidate revision is current.
Set `complete` only after integration or explicit closure. Follow the project's
retention rule so completed plans do not remain in the active route forever.
