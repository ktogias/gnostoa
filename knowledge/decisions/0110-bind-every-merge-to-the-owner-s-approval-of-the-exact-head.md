---
type: Decision
title: Bind every merge to the owner's approval of the exact head
description: MA0 Phase 1a. The orchestrating agent acts through its own GitHub App, without admin, and a machine user that opens PRs and requests reviews. A ruleset on main, with no bypass but a break-glass App, requires the code owner's approval of the exact head, resolved threads and the required checks, so no actor merges without the owner. The owner's former agent PAT is revoked.
status: draft
generated:
  by: anthropic/claude-opus-5-5
  at: "2026-10-08T02:45:00Z"
sources:
  - id: owner-direction
    resource: https://github.com/ktogias/gnostoa/issues/15#issuecomment-6048360846
    title: The MA0 revision proposal, the retrospective and the research behind it
  - id: owner-decisions
    resource: https://github.com/ktogias/gnostoa/issues/15#issuecomment-6048425337
    title: The owner's decisions on identity, emergency and ordering
  - id: calibration
    resource: https://github.com/ktogias/gnostoa/issues/15#issuecomment-6050406535
    title: The calibration of the identities and the rulesets
  - id: work-item
    resource: https://github.com/ktogias/gnostoa/issues/398
    title: Record the merge gate (MA0 Phase 1a)
x-project-knowledge:
  id: kit.decision.0110.bind-every-merge-to-the-owner-s-approval-of-the-exact-head
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: references
      target: /runbooks/operate-the-merge-gate.md
---

# Bind every merge to the owner's approval of the exact head

## Context

On 2026-10-08 the owner asked for a gate that rejects every merge that does not meet
the project's criteria. It must hold for Amazon Q, the orchestrating agent, and any
developer or agent. An app through which only the owner can bypass exactly that rule
was welcome. The first phase need not be absolute.

A retrospective over the repository's history (#15, 6048360846) found these root
causes:

- **Identity conflation.** The agents acted through a PAT of the owner's account,
  which is an admin. So they held the admin bypass, and the owner could not approve
  their PRs: a PR's author cannot approve it.
- **Completeness was a matter of agent discipline.** It was never checked by the
  platform at merge time.
- **Fail-open signal semantics.**
- **Approvals were not bound to the exact head.**
- **The admin bypass had become the merge path in practice,** and #384 proposed making it the rule; that proposal was never merged.
- **MA0 itself was never shipped**, displaced by feature work.

## Decision

1. **The agent's identities.**
   - The App `gnostoa-agent` has no admin. It pushes branches, resolves threads, runs
     and reads the readback, and merges.
   - The machine user `gnostoa-agent-user` has the Write role. It opens PRs and posts
     review triggers, because Codex, Amazon Q and CodeAnt skip a bot's PRs and
     requests.
   - The owner's former agent PAT is revoked.
2. **R-main**, a ruleset on `main`, requires:
   - one approval from a code owner, and the only code owner is the owner;
   - stale approvals dismissed, and the latest push approved;
   - an extra approval for unattributed changes;
   - every thread resolved;
   - squash merges only;
   - the four checks from GitHub Actions, on an up-to-date branch.

   Its only bypass actor is `gnostoa-break-glass`, in pull-request mode, with its key
   held offline by the owner.
3. **The owner's native approval of the exact head is the merge instruction.** It
   replaces MA0 design decision 2's environment approval (channel C) for the
   instruction itself. Channel C stays for MA0's other attestations.
4. **Branch writes.**
   - Ruleset 24640984 excludes `main`, and admits `gnostoa-agent` beside the admin
     role.
   - Amazon Q and the other apps still cannot write a branch.
5. **The gate comes first (the owner's ordering).** Phase 1a preceded the next
   feature merge, and Phase 1b (the required `merge-admission` check) precedes the
   one after that.
6. **The record.**
   [Operate the merge gate](../runbooks/operate-the-merge-gate.md) records every
   identity and setting, as read back, together with the procedures. Any change to
   them updates it in the same change.

## Consequences

- **No actor can merge without the owner's approval of the head, except through
  break glass,** which only the owner can use, and which the runbook bounds and
  audits. Calibration showed the App refused both with and without `--admin`.
- **What the platform does not yet enforce.** Until Phase 1b it does not check:
  - the approval's `commit_id` against the merged head, since the platform keeps an
    approval across a push that leaves the diff unchanged; the merge procedure
    compares them;
  - the analyzer readback;
  - convergence;
  - the analyzers' findings;
  - the seal;
  - close-last.

  These remain in the agent's convergence report, which the owner reads before
  approving.
- **More approvals.** Every push, and every move of `main`, requires a new approval.
- **The classic protection stays until Phase 1b.** Break glass cannot bypass it.

## What this supersedes or revises

- **#384's proposal** (a draft Decision in that PR, not merged). Its admin-role bypass
  as the merge path is superseded by items 2 and 4.
- **MA0 design decisions 2 and 5 (#15, 5979363503).** Decision 2 is revised by item
  3. Decision 5, the agents acting through the owner's account, is superseded by item
  1.
- **Decision 0014's premise of zero approvals with one maintainer.** Write-capable
  non-human actors now open and merge PRs, so a code-owner approval is required.
