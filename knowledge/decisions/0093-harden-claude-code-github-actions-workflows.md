---
type: Decision
title: Harden the Claude Code GitHub Actions workflows before integration
description: Keep the owner-installed Claude Code review and mention workflows only with immutable action and plugin pins, credential-free checkouts, trusted-trigger gating and bounded execution.
status: draft
generated:
  by: anthropic/claude-opus-5-5
  at: "2026-09-25T22:00:00Z"
sources:
  - id: work-item
    resource: https://github.com/ktogias/gnostoa/issues/321
    title: Harden the Claude Code GitHub Actions workflows before integration
  - id: installer-pr
    resource: https://github.com/ktogias/gnostoa/pull/320
    title: Add Claude Code GitHub Workflow
  - id: claude-code-action
    resource: https://github.com/anthropics/claude-code-action/tree/9171db3e57d6a3140a37ddc2ba92788584e0ead6
    title: anthropics/claude-code-action v1.0.234
  - id: claude-code-marketplace
    resource: https://github.com/anthropics/claude-code/tree/c94815511c7fb7a33900fe094bbc0dbee4a3b8ee
    title: anthropics/claude-code plugin marketplace
x-project-knowledge:
  id: kit.decision.0093.harden-claude-code-github-actions-workflows
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governed-by
      target: /decisions/0062-require-proportionate-prior-art-and-reuse-review.md
    - kind: references
      target: /runbooks/deliver-bounded-self-hosted-slice.md
---

# Harden the Claude Code GitHub Actions workflows before integration

## Context

The owner ran `/install-github-app`, which opened PR #320 with the upstream
installer template for two workflows: an automatic PR review and an `@claude`
mention responder. The template references `actions/checkout@v4`,
`anthropics/claude-code-action@v1` and a plugin marketplace on a moving default
branch. That contradicts non-negotiable guardrail 8 (immutable dependency pins).
The workflows run a third-party agent with a repository secret and
`id-token: write`, so this is a `critical` change.

Upstream behavior verified at `claude-code-action` commit
`9171db3e57d6a3140a37ddc2ba92788584e0ead6`:

- The action exchanges the GitHub OIDC token for a Claude GitHub App token that
  is always requested with `contents`, `pull_requests` and `issues` write. The
  workflow `permissions` bound only `GITHUB_TOKEN`, so read-only workflow
  permissions do not prevent inline review comments.
- The action rejects triggering actors without repository write access.
- The action configures its own Git authentication and removes the checkout
  extraheader, so the checkout needs no persisted credentials.
- `plugin_marketplaces` accepts only a `.git` URL without a ref, or a local path.

## Prior-art and reuse disposition

Reuse the installer template and change only what the guardrails require.
Managed Claude Code Review needs no workflow and stays a separate
owner-controlled route; the external-reviewer invocation guidance proposed in
PR #319 documents it. This Decision neither
enables nor replaces it. No automation was rejected by the owner's install
choice. `claude-code-action` and `actions/checkout` are MIT. The
`anthropics/claude-code` marketplace is proprietary under Anthropic's Commercial
Terms. It is only executed in CI and is neither copied nor redistributed.

## Decision

1. Pin every workflow `uses:` to a full commit SHA, with the resolved tag as a
   comment. Reuse the repository's existing `actions/checkout` v6.0.2 pin.
2. Materialize the plugin marketplace with a SHA-pinned checkout and install it
   from that local path.
3. Set `persist-credentials: false` on every checkout.
4. Keep the workflow token read-only plus `id-token: write` and `actions: read`
   where CI results are read. Adding write scopes would widen `GITHUB_TOKEN`
   without affecting the App token.
5. Run the automatic review only for same-repository, non-draft PRs. Keep one
   review per PR with `cancel-in-progress`, and give the job a timeout.
6. Run the mention job only for `OWNER`, `MEMBER` or `COLLABORATOR` author
   associations, as defence in depth before the action's own check, and give it
   a timeout. Do not add a concurrency group: GitHub keeps one pending run per
   group, so an unrelated comment could silently replace a pending request.
7. Leave `allowed_bots`, `allowed_non_write_users` and extra mention-job tools
   unset.

`tests/test_claude_actions_workflows.py` enforces the full-SHA rule for every
workflow and the Claude-specific invariants above. The
`immutable-provider-ci-adapters` guardrail owns the workflows, this Decision and
that test.

## Consequences

- Updating the action or plugin becomes an explicit reviewed pin change.
- The automatic review workflow cannot pass on PR #320 itself. The action
  validates that the workflow matches the default branch before exchanging
  tokens, so the first effective run follows integration.
- Automatic Claude reviews are advisory agent reviews. They are captured under
  [supplied-agent review dispositions](../runbooks/deliver-bounded-self-hosted-slice.md#supplied-agent-reviews)
  and never supply human approval, qualification or merge authority.
- The App token remains write-capable by upstream design. Containment relies on
  the actor check, the association gate and, for automatic review, the
  single-tool `--allowedTools` restriction.
