---
type: Decision
title: Scope the Claude credential to the protected branch and withdraw the automatic review
description: Keep CLAUDE_CODE_OAUTH_TOKEN only in an environment that admits the default branch alone, let only workflow_run jobs from that branch enter it, and withdraw the pull_request-triggered automatic review instead of rebuilding it.
status: draft
generated:
  by: anthropic/claude-opus-5
  at: "2026-10-01T12:00:00Z"
sources:
  - id: work-item
    resource: https://github.com/ktogias/gnostoa/issues/342
    title: Keep the Claude credential away from workflows resolved from candidate revisions
  - id: owner-admission
    resource: https://github.com/ktogias/gnostoa/issues/342#issuecomment-5925372742
    title: Owner selects option Γ
  - id: relay
    resource: ./0096-relay-mention-reviews-through-a-protected-workflow.md
    title: Relay mention reviews through a protected workflow revision
  - id: harden-actions
    resource: ./0093-harden-claude-code-github-actions-workflows.md
    title: Harden the Claude Code GitHub Actions workflows before integration
x-project-knowledge:
  id: kit.decision.0097.scope-the-claude-credential-to-the-protected-branch
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governed-by
      target: /decisions/0093-harden-claude-code-github-actions-workflows.md
    - kind: governed-by
      target: /decisions/0096-relay-mention-reviews-through-a-protected-workflow.md
---

# Scope the Claude credential to the protected branch and withdraw the automatic review

## Context

Decision 0096 moved the mention reviewer off candidate revisions. It does not keep the
credential away from them, and an earlier draft claimed it did. Codex raised this on
#340, and it was verified against the repository:

| Fact | Evidence |
|---|---|
| `CLAUDE_CODE_OAUTH_TOKEN` was a **repository** secret | `GET /repos/ktogias/gnostoa/actions/secrets`; no environment held it |
| A repository secret reaches workflows run from **any** same-repository branch | GitHub's secret model, for `push`, `pull_request` and the review events alike |
| `claude-code-review.yml` passed it to the candidate's own revision | it ran on `pull_request` and read the secret |
| The only collaborator with write access is the owner | `GET /repos/ktogias/gnostoa/collaborators` |

So anyone able to push a branch could push a workflow that reads the token. In
practice that means the owner and the agents that push with the owner's credentials.
An agent steered by text it was asked to review is the realistic case, and agents here
read such text all day. A file's `permissions: {}` changes nothing, because the
candidate can edit the file.

## Prior-art and reuse disposition

| Needed | Source | Relation |
|---|---|---|
| a credential only the default branch can reach | environment `analyzer-readback` (deployment branch policy: `main`), used by `analyzer-readback.yml` | **reused** as the pattern |
| a job that runs from the default branch on PR activity | Decision 0096's `workflow_run` relay | **reused** |
| enforcement that a later workflow cannot quietly bypass | none; new test enumerating every workflow | **new** |

Three options were set out for the owner:

- **A. Scope the credential and rebuild the automatic review on the relay.** Complete,
  but the rebuild needs the bounded context of Decision 0094 to review a Pull Request
  without executing it: another change the size of #340.
- **B. Accept the residual.** Record that anyone who can push is trusted with the token.
- **Γ. Scope the credential and withdraw the automatic review.** Complete protection,
  at the cost of the automatic review; Claude reviews remain available on demand.

The owner selected **Γ** on 2026-10-01 (#342).

## Decision

1. **The credential lives only in environment `claude-review`, whose deployment
   branches are restricted to the default branch.** The repository-level secret is
   deleted, and the token is rotated. Rotation is not because a leak is known: the
   token was readable by branch workflows, and rotating it costs little. These are
   account settings, so they are the owner's actions; the token's value is unreadable
   to agents by design.

2. **Every job that names the credential declares that environment, and its workflow
   is triggered only by `workflow_run`, with a default-branch assertion.** A
   `workflow_run` handler runs from the default branch (Decision 0096 rule 1), so it
   passes the environment's policy. A workflow on any other branch cannot, whatever it
   is edited to say. The test enumerates every workflow file rather than naming the
   known ones, so one added later is held to the rule without anyone remembering it,
   and it recognises every spelling that reaches the token: the dotted name in any
   case, indexed or whole-context access, a workflow-level `env:`, and `secrets:
   inherit`. Its first detector looked only for the dotted name inside a job and
   missed the rest (gitar, #340).

3. **The automatic review is withdrawn, not rebuilt.** `claude-code-review.yml` is
   removed. It ran on `pull_request`, which a `main`-only environment refuses, so once
   rule 1 holds it could no longer obtain the token anyway. Claude reviews remain
   available on demand through `@claude`, which runs on the protected relay. Rebuilding
   an automatic review on that relay stays possible, as its own Work Item, if it is
   ever wanted.

4. **Code first, then the secret, then verification.** Declaring an environment that
   does not exist yet is safe: GitHub creates it on first use, and the repository
   secret still reaches it until rule 1 removes it. So the change merges first, the
   owner then performs rule 1, and only then is the boundary verified live: a
   privileged run obtains the token, and a non-default-branch workflow naming the
   environment is refused by its policy.

5. **What this does not close, stated as an accepted residual.** Any workflow may
   request `id-token: write` and exchange the OIDC token for a Claude GitHub App token
   (Decision 0093). That exchange is policed by Anthropic's endpoint, not by this
   repository, and the App token carries `contents`, `pull_requests` and `issues`
   write. Anyone able to push a branch here already holds those capabilities, so this
   is not an escalation, but it is recorded here rather than left implied.

## Partial supersession of Decision 0093

Decision 0093 rule 5 (the automatic review's same-repository, non-draft and
`cancel-in-progress` controls) is **withdrawn** with the workflow it governed. Its
other rules continue to hold for the mention workflow: immutable pins, credential-free
checkouts, read-only `GITHUB_TOKEN` scopes and the trusted-association gate, which
Decision 0096 moved into admission.

## Consequences

- No Claude review runs automatically on a Pull Request. Every Claude review is
  requested with `@claude`, which also spends the subscription only when asked; the
  automatic review spent it on every push an agent made.
- The credential stops being something a branch workflow can read. Once rule 1 is in
  place, any future workflow that names it without entering the environment fails
  rule 2's test before it can merge.
- Until the owner performs rule 1, this Decision is code-complete but not in force;
  #342 stays open until the live verification of rule 4 passes.
