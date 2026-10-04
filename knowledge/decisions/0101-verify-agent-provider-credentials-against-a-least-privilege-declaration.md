---
type: Decision
title: Verify agent provider credentials against a least-privilege declaration
description: Add `knowledge credential-check`, a read-only and non-effecting probe of the agents' provider token that reports whether it holds exactly a declared least privilege, and route agents to run it before provider writes.
status: draft
generated:
  by: anthropic/claude-opus-5-5
  at: "2026-10-04T12:30:00Z"
sources:
  - id: work-item
    resource: https://github.com/ktogias/gnostoa/issues/362
    title: Verify that an agent's provider token holds exactly its declared least privilege
  - id: lineage
    resource: https://github.com/ktogias/gnostoa/issues/362#issuecomment-5979807974
    title: Architecture-inheritance table and behavior map for #362
  - id: channel-c
    resource: https://github.com/ktogias/gnostoa/issues/15#issuecomment-5979363503
    title: MA0 design decisions, including owner authority through an environment approval
  - id: approval-probe
    resource: https://github.com/ktogias/gnostoa/issues/15#issuecomment-5979734602
    title: Approving a pending deployment requires Deployments write alone
  - id: a6-gap
    resource: https://github.com/ktogias/gnostoa/issues/15#issuecomment-5821804133
    title: VF0-A6 left effective credential grants unaudited
x-project-knowledge:
  id: kit.decision.0101.verify-agent-provider-credentials-against-a-least-privilege-declaration
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governed-by
      target: /decisions/0016-evolve-human-agent-workflow-through-bounded-self-hosted-slices.md
    - kind: references
      target: /decisions/0100-separate-the-agent-review-pipeline-into-a-neutral-core-and-adapters.md
    - kind: references
      target: /requirements/bounded-behavioral-traceability.md
---

# Verify agent provider credentials against a least-privilege declaration

## Context

Agents work on this repository as the owner's operating-system user, through the owner's
GitHub account. GitHub attributes every write to that account whichever token made it,
so attribution cannot tell an agent from the owner (AI-PEAF Decision 0006 records that
residual). What *can* be bounded is what the agents' token is able to do.

The owner's authority channel for MA0 rests on exactly that bound. An approval through a
GitHub Environment counts as the owner's only while the agents' token cannot approve a
pending deployment, and a non-effecting probe established that approving one needs
`deployments=write` alone. On 2026-10-04 the agents moved to a fine-grained personal
access token with a declared set of permissions. Nothing checked that the token in use
holds that set, and VF0-A6 had recorded `effective_credential_grants_audited=false`.

GitHub has no endpoint that lists a fine-grained token's permissions for a personal
account (organizations can review them; a user cannot query their own). Every REST
answer does carry `X-Accepted-GitHub-Permissions`, the permission sets the route
accepts.

## Prior-art and reuse disposition

| need | candidate | disposition |
|---|---|---|
| list a token's grants | GitHub's organization review of fine-grained tokens | not available for a personal account |
| know what a route requires | `X-Accepted-GitHub-Permissions` | **reused** as the probe's self-check |
| workflow token permissions | OpenSSF Scorecard "Token-Permissions" | a different object (a workflow's `GITHUB_TOKEN`), not reused |
| GitHub transport | `tools/github_rest.py` (Decision 0100) | **extended**: a refusal keeps its accepted permissions, and the client can `put` |
| neutral-core structure | Decision 0100's guard | **consumed** for the new core |

No tool found verifies a personal account's fine-grained token against a declaration.

## Decision

1. **A declaration states the least privilege.** `policy/agent-credentials.yaml` names
   the token kind, the longest remaining lifetime, the resource owner, the repositories
   the token may write, and for each capability a `min` and a `max` level among `none`,
   `read` and `write`. The core validates it before judging anything.
2. **Each permission is measured by a non-effecting probe.** A probe is a read, a write
   aimed at something that cannot exist (a zero SHA, a run that does not belong to the
   repository, a branch or workflow named `zz-credential-probe`), or a creation whose
   body the provider must reject (an issue without a title, a pull request between
   branches that do not exist, a gist with no files). Whatever the answer, nothing is
   created, changed or deleted. A structural test holds every probe to this.
3. **An answer is read only for the permission it names.** A probe whose route does not
   name its permission in `X-Accepted-GitHub-Permissions` has drifted and is UNKNOWN. A
   `403 Resource not accessible by personal access token` is a refusal. A grant is a
   422 on a rejected body, or a 404 only on a route a calibrated refusal showed to check
   the permission before its lookup: `PATCH` on a missing gist answered 404 for a token
   that `POST /gists` refused with 403, so a lookup can come first.
4. **Some levels are not measurable, and say so.** A public repository's data is
   readable by anyone, so its `read` level is PUBLIC: a grant there adds nothing.
   A level the provider does not define (a `read` of `workflows` or `gists`) is
   NOT_APPLICABLE. `workflows=write` has no non-effecting probe and is UNMEASURABLE.
5. **Excess must be disproven; a missing grant need only not be proven.** A grant above
   `max` is EXCESS. One that no probe could rule out leaves the verdict UNVERIFIED.
   A grant below `min` is DEFICIENT; one that cannot be confirmed is listed under
   `minimum_unverified` without failing the verdict, because a missing grant reveals
   itself when used and an excess one never does. A capability observed but not
   declared is held to `none`.
6. **Scope is probed, not assumed.** The contents-write probe is aimed at every other
   repository the resource owner owns that the token can see. A writable one outside
   `repositories` is EXCESS.
7. **The token's kind and lifetime are part of the verdict.** The kind comes from the
   token's prefix alone; the token is never printed or kept. A token without an expiry,
   already expired, or with more remaining lifetime than declared is
   LIFETIME_EXCEEDED.
8. **The verdict and its precedence.** TOKEN_KIND_MISMATCH, then EXCESS, then
   DEFICIENT, then LIFETIME_EXCEEDED, then UNVERIFIED; otherwise EXACT. The command
   exits 0 for EXACT, 1 for the first four, 3 for UNVERIFIED and 2 on an input or tool
   error.
9. **Agents run it before provider writes.** At the start of a session, and before the
   first provider write, an agent runs `knowledge credential-check` for the repository
   it works on and quotes the verdict. On anything but EXACT it makes no provider write
   until the owner resolves it: by fixing the token, or by amending the declaration.

## What this does not establish

The check verifies how the boundary is configured; it is not the boundary. An agent on
the owner's operating-system user can still reach the owner's browser session, so an
agent that drove the browser could act as the owner. Agents therefore use no browser
automation on the owner's profile, and the target is a separate operating-system user
for agents. The check also does not attribute any write: it says what a token could do,
not who did what. A required grant it cannot measure (`workflows=write`) is listed, not
proven.

## Consequences

The agents' token is checked against its declaration whenever an agent starts work, so a
token widened by mistake, or swapped for an admin-capable one, is caught before it is
used. Each new provider permission the declaration names needs a calibrated probe, or is
reported as unmeasurable. How `knowledge adoption-check` records the result for adopters
whose agents work through a provider is a follow-up: its `gnostoa-adoption-check/v2`
contract is closed, and this Decision does not change it.

## Verification

- `tests/test_credential_posture.py`: the policy model, every verdict and its
  precedence, the GitHub adapter over answers replayed from the 2026-10-04 calibration,
  the probe rules (drift, provider failure, lookup-first routes, non-effecting shapes),
  the command, the shared client's accepted permissions, and the neutral core.
- A live run against the agents' token on 2026-10-04 matched the calibration row for
  row, and reported EXCESS for two writable repositories outside the declaration.
