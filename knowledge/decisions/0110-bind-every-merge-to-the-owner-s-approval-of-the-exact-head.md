---
type: Decision
title: Bind every merge to the owner's approval of the exact head
description: MA0 Phase 1a. The orchestrating agent acts through its own GitHub App, without admin, and a machine user that opens PRs and requests reviews. A ruleset on main, with no bypass but a break-glass App, requires the code owner's approval, resolved threads and the required checks, so no actor merges without the owner; the merge procedure binds that approval to the exact head until Phase 1b. The owner's former agent PAT is revoked.
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
    - kind: governed-by
      target: /decisions/0006-provider-neutral-change-governance.md
    - kind: implements
      target: /requirements/reviewed-change-control.md
    - kind: references
      target: /decisions/0014-strengthen-gnostoa-self-governance.md
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

This Decision is a Gnostoa-self/GitHub specialization and does not alter the
provider-neutral public change-governance contract. It specializes
[Decision 0006](0006-provider-neutral-change-governance.md) and
[reviewed change control](../requirements/reviewed-change-control.md) for Gnostoa
itself on GitHub, and extends
[Decision 0014](0014-strengthen-gnostoa-self-governance.md)'s stricter self-policy.

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

- **No actor can merge without the owner's approval, except through break glass,**
  which only the owner can use, and which the runbook bounds and audits. Binding the
  approval to the exact head is the merge procedure's step until Phase 1b, as
  below. Calibration showed the App refused both with and without `--admin`.
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
- **More approvals.** Every push that changes the diff, and every move of `main`,
  requires a new approval. A push that leaves the diff unchanged may keep it, so the
  merge procedure compares the approval's `commit_id` with the head.
- **The classic protection stays until Phase 1b.** Break glass cannot bypass it.

## Successor: Phase 1b

Phase 1b is deferred: it needs its own admission, Decision and falsifiers, and this
Decision implements none of it. Its reuse contract follows the owner's lineage
disposition on #398 (6061470364, 6061573600). Phase 1b consumes, rather than
duplicates:
- `tools/github_rest.py`, for GitHub REST calls;
- Decision 0086's current-state observation and reconciliation,
  `ci/review_github_current_state.py` and `tools/review_reconcile.py`, for the exact
  head, the reviews and the threads;
- #389's assurance-completeness receipts, once they are effective;
- #369's trusted-execution owner, once it is integrated.

The only new shared responsibility is the provider-neutral merge-admission verdict,
in the generic core, with the GitHub mapping at the adapter boundary. Where an owner
or a receipt is not yet available, the verdict fails closed rather than
reimplementing it.

## What this supersedes or revises

- **#384's proposal** (a draft Decision in that PR, not merged). Its admin-role bypass
  as the merge path is superseded by items 2 and 4.
- **MA0 design decisions 2 and 5 (#15, 5979363503).** Decision 2 is revised by item
  3. Decision 5, the agents acting through the owner's account, is superseded by item
  1.
- **Decision 0013's zero required approvals, and Decision 0014's premise of zero
  approvals with one maintainer.** Write-capable non-human actors now open and merge
  PRs, so a code-owner approval is required. This Decision is the stricter
  specialization that Decision 0013 deferred to, and both now say so. Gnostoa's
  change-control policy requires the code owner's approval for every class except
  emergency, as R-main does (#401).
