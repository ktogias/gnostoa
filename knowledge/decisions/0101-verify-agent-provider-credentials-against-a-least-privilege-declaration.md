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
account (organizations can review them; a user cannot query their own). A refusal or
rejection does carry `X-Accepted-GitHub-Permissions`, the permission sets the route
accepts.

## Prior-art and reuse disposition

| need | candidate | disposition |
|---|---|---|
| list a token's grants | GitHub's organization review of fine-grained tokens | not available for a personal account |
| know what a route requires | `X-Accepted-GitHub-Permissions` | **reused** as the probe's self-check |
| workflow token permissions | OpenSSF Scorecard "Token-Permissions" | a different object (a workflow's `GITHUB_TOKEN`), not reused |
| GitHub transport | `tools/github_rest.py` (Decision 0100) | **extended**: a refusal keeps its accepted permissions, and the client can `put` |
| token from the environment | `GitHubRestClient.from_environment` | **factored** into `github_rest.environment_token()`, consumed by both; the `gh auth token` fallback is the residual |
| a name safe in an API path | `analyzer_readback.normalize_repository`'s rule | **extended** into `github_rest.owner_name()` / `repository_name()`, which `github_rest` owns beside `validate_url`; the copies converge under #365 |
| bounded `Link` pagination | `read_page` + `next_url` | **extended** with `github_rest.follow_pages()`, a loop any transport can drive |
| path confinement | `agent_review_paths.within` | **extended** with `within_root()`, for a root the caller holds |
| declaration contract | `schemas/` + `Draft202012Validator`, 9 local helpers | **created** `schemas/agent-credentials.schema.json` and the shared `tools/schema_validation.py`; the loaders converge under #365 |
| YAML without duplicate keys; timestamp | `knowledge_common.load_yaml`; 9 local `_now()` | **consumed**; **created** `knowledge_common.utc_timestamp()` |
| neutral-core structure | Decision 0100's guard | **consumed** for the new core |

The first draft of round 2 wrote these again beside their owners; the incident and its
analysis are #365. The core's own validation of the declaration repeats some of the
schema on purpose: the neutral core stays usable without `jsonschema`, a distinct trust
boundary.

No tool found verifies a personal account's fine-grained token against a declaration.

## Decision

1. **A declaration states the least privilege, over everything the provider can
   grant.** `policy/agent-credentials.yaml` names the credential kind, the longest
   remaining lifetime, the resource owner, the repositories the token may write, and a
   `min` and a `max` level (`none`, `read`, `write`) for **every** permission GitHub
   documents for a user-owned fine-grained token: 32 repository and 14 user
   permissions. The core validates it before judging anything, and loads it from the
   working tree only, refusing a repeated key.
2. **Every probe is non-effecting by construction.** A probe is a read, or a write whose
   body the provider must reject whatever the repository holds, by one of two
   constructions. Neither relies on a value the provider might normalize: GitHub
   cleans up a repository name with disallowed characters instead of rejecting it.
   - **A container type violation:** a documented field given an array or object of a
     JSON type it does not accept. It is used where a calibrated refusal showed the
     permission is checked first.
   - **A schema-valid body naming an object that cannot exist** (the zero SHA). It is
     used where the route validates the schema *before* the permission. `git/refs`
     does: a type-violating ref answered 422 on a repository the token cannot see,
     which would read every repository as writable.

   Where a route names a target (a branch, a workflow, a commit), it names one that
   cannot exist as well. A write the provider *accepts* broke that construction and
   may have changed something: the check stops, names the probe and exits 2.
3. **An answer is read only for the permission it names, and only as far as it goes.**
   Each calibrated refusal or rejection carried `X-Accepted-GitHub-Permissions`, the
   permission sets the route accepts. A probe whose route does not name its permission has drifted
   and is UNKNOWN. A `403 Resource not accessible by personal access token` proves the
   permission absent only when one alternative is that permission alone: for
   `pages=write,administration=write` it may be the administration grant's. A pass (422
   on a rejected body, or 404 on a route a calibrated refusal showed to check first)
   proves the permission only when it is in every alternative. A lookup can come first:
   `PATCH` on a missing gist answered 404 for a token that `POST /gists` refused.
4. **Every permission gets an observation at both levels.** From a probe, or from a
   stated reason:
   - **PUBLIC:** a repository read whose data the provider serves without the grant,
     and only over a **public selection**. A read grant reaches only the token's
     selected repositories, so it adds nothing when the subject is public and proven
     to be the only writable repository. Otherwise it is UNMEASURABLE.
   - **UNMEASURABLE**, not public:
     - a read whose route answers without the grant but filters its private part out
       rather than refusing it: draft and triage advisories, a Pages site's private
       parts, and the private repositories in a user's starred and watched lists;
     - a level whose routes look up their target first;
     - a level whose routes belong only to organizations.
   - **NOT_APPLICABLE:** a level GitHub documents no endpoint for, and nothing else.

   A write level whose read is refused is ruled out by the refusal.
5. **Excess must be disproven; a missing grant need only not be proven.** A grant above
   `max` is EXCESS. One no probe could rule out leaves the verdict UNVERIFIED, unless the
   declaration accepts that UNMEASURABLE level by name, with a reason
   (`accepted_unmeasurable`). It must be a level of a capability the declaration
   declares. An accepted level rests on the token's configuration, not on a
   measurement, so it is listed in every verdict, accepting one is the owner's
   decision, and an unanswered probe is never accepted away. A grant below `min` is DEFICIENT; one that
   cannot be confirmed is listed under `minimum_unverified` without failing the verdict,
   because a missing grant reveals itself when used and an excess one never does.
6. **Scope is probed, and the subject is its control.**
   - **What is probed:** the contents-write probe is aimed at every repository the
     token can see, whoever owns it, the subject included. A writable repository
     outside `repositories` is EXCESS.
   - **Why one probe suffices:** a fine-grained token has one repository selection and
     one set of repository permissions, as GitHub's own description of a token shows
     (`repository_selection`, `permissions.repository`). So one write probe tells the
     selection apart.
   - **The control:** that holds only when the probe detects the grant on the subject.
     When it does not, a refusal elsewhere proves nothing, and every other
     repository's scope is UNVERIFIED.
   - **Whose token it is:** a fine-grained token reaches only its resource owner's
     resources, so a writable subject shows whose token it is, provided every declared
     repository belongs to the declared `resource_owner`. A declaration that breaks
     this is refused.
   - **The subject:** it must be an `owner/name` GitHub allows and one `repositories`
     lists, both checked before any request. The scope rule alone would still keep an
     undeclared subject from EXACT.
7. **The credential's kind and lifetime are part of the verdict.** The kind comes from
   the token's prefix alone; the token is never printed or kept. A token without an
   expiry, already expired, or with more remaining lifetime than declared is
   LIFETIME_EXCEEDED.
8. **The verdict and its precedence.** CREDENTIAL_KIND_MISMATCH, then EXCESS, then
   DEFICIENT, then LIFETIME_EXCEEDED, then UNVERIFIED; otherwise EXACT. The command
   exits 0 for EXACT, 1 for the first four, 3 for UNVERIFIED and 2 on an input or tool
   error or a probe the provider accepted.
9. **Agents run it before the first provider write of a session.** An agent runs
   `knowledge credential-check` for the repository it works on and quotes the verdict.
   On anything but EXACT it makes no provider write until the owner resolves it: by
   fixing the token, or by amending the declaration through an ordinary change.

## What this does not establish

The check verifies how the boundary is configured; it is not the boundary. An agent on
the owner's operating-system user can still reach the owner's browser session, so an
agent that drove the browser could act as the owner. Agents therefore use no browser
automation on the owner's profile, and the target is a separate operating-system user
for agents. The check also does not attribute any write: it says what a token could do,
not who did what. A required grant it cannot measure (`workflows:write`) is listed, not
proven.

## Consequences

The agents' token is checked against its declaration whenever an agent starts work, so a
token widened by mistake, or swapped for an admin-capable one, is caught before it is
used. Each new provider permission the declaration names needs a calibrated probe, or is
reported as unmeasurable. How `knowledge adoption-check` records the result for adopters
whose agents work through a provider is a follow-up: its `gnostoa-adoption-check/v2`
contract is closed, and this Decision does not change it.

## Verification

- `tests/test_credential_posture.py`: the policy model and its coverage of every
  documented permission, every verdict and its precedence, accepted unmeasurable levels,
  the subject inside the scope, the GitHub adapter over answers replayed from the
  2026-10-04 calibration, the probe rules (drift, provider failure, a refusal that needs
  another grant too, a pass another grant alone explains, lookup-first routes, a write
  the provider accepts, construction), the command's input checks (the subject, the
  declaration's place and duplicate keys, a refused token), the shared client's accepted
  permissions, and the neutral core.
- Live runs against the agents' token on 2026-10-04 matched the calibration row for
  row. The first reported EXCESS for two writable repositories outside the declaration;
  after the owner removed them from the token, EXACT over all 46 permissions, with the
  accepted unmeasurable levels and `workflows:write` listed: seven, then eleven once
  four filtered reads stopped counting as public.
