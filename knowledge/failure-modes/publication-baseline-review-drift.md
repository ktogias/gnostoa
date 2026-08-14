---
type: Failure Mode
title: Publication-baseline review critical-path drift
description: Retrospective on how the PR #2 source-baseline review expanded into workflow design and how the original delivery path was restored.
status: draft
generated:
  by: codex/gpt-5
  at: "2026-08-14T00:00:00Z"
sources:
  - id: publication-baseline-work-item
    resource: https://github.com/ktogias/gnostoa/issues/1
    title: Prepare the Gnostoa publication baseline
  - id: publication-baseline-change-request
    resource: https://github.com/ktogias/gnostoa/pull/2
    title: Prepare the Gnostoa publication baseline
  - id: guided-review-work-item
    resource: https://github.com/ktogias/gnostoa/issues/12
    title: Add provider-neutral guided semantic review and resumable review sessions
  - id: review-effort-finding
    resource: https://github.com/ktogias/gnostoa/pull/2#issuecomment-5225953068
    title: PB-01/F-REV-01 review-effort finding
  - id: deterministic-workflow-work-item
    resource: https://github.com/ktogias/gnostoa/issues/15
    title: Automate deterministic knowledge-workflow mechanics without weakening assurance
  - id: single-approval-process-correction
    resource: https://github.com/ktogias/gnostoa/issues/12#issuecomment-5284129277
    title: XR1/079 single-approval and deterministic-recording correction
  - id: critical-path-reset-candidate
    resource: https://github.com/ktogias/gnostoa/commit/4b3c71363aa95961139eba2b627ee911e9dd900a
    title: Clarify the publication-baseline review
x-project-knowledge:
  id: kit.failure-mode.publication-baseline-review-drift
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: conflicts-with
      target: /lifecycles/toolkit-evolution.md
    - kind: verified-by
      target: /runbooks/review-publication-baseline.md
    - kind: references
      target: /decisions/0014-strengthen-gnostoa-self-governance.md
---

# Publication-baseline review critical-path drift

## Event

PR #2 began as the bounded implementation of Issue #1: prepare a private,
provider-activated, generic and reviewable source baseline. Public repository
visibility and package, OCI-image and site publication were explicitly outside
that Work Item.

The candidate was technically green on 2026-07-30, but its owner review became
a dogfood exercise for the proposed guided-review capability in Issue #12. The
review then recursively designed and reviewed its own protocol, event ledger,
projections, assurance model and deterministic implementation requirements.
Analysis of WI-DET-01 in Issue #15 occupied the operational critical path even
though that Work Item explicitly excluded changing PR #2 and declared itself
blocked by completion of Issue #1.

Immediately before the 2026-08-14 reset, PR #2 still pointed at the unchanged
`495b163196a62b004264f97fb255be6f878fe20b` candidate. A thread-aware audit
found 43 conversation comments, no formal reviews and no inline review threads.
The separate `F-REV-01` finding had already measured the local failure mode:
one criterion underwent six verification rounds and 229 findings, while its
replacement grew from roughly 60 words to 754. The process was increasing
local assurance detail while delaying the source baseline it was meant to
review.

## Findings

1. **Critical-path drift.** The active work changed from resolving the bounded
   publication blockers to designing a future review/workflow product.
2. **Publication-state ambiguity.** “Publication baseline” did not clearly
   distinguish candidate preparation, owner acceptance, private integration,
   source visibility and artifact publication.
3. **Incomplete review boundary.** The runbook did not identify one mandatory
   canonical-source manifest or clearly separate semantic targets, executable
   evidence, selected history and derived projections.
4. **Authority and recording coupling.** Deterministic evidence, provider
   recording and owner semantic choices were repeatedly wrapped as separate
   approval steps. The audit trail became part of the decision burden.
5. **Unbounded review growth.** The process had no effective stop condition
   when additional verification ceased improving owner-facing auditability.
   Additive hardening dominated deletion, consolidation and recovery.
6. **Dependency inversion.** Issue #12 and WI-DET-01 were intended to follow
   the source baseline, but their analysis was allowed to delay Issue #1.

## Root causes

- The lifecycle lacked explicit, non-implying publication states and one
  current exit condition.
- The review procedure lacked a canonical traversal manifest and an explicit
  actor/authority model, so review-scope questions became new review units.
- Dogfooding findings were promoted from roadmap evidence into prerequisites
  for the deliverable that generated them.
- Append-only evidence was optimized for local trace completeness without an
  equally strong constraint on owner cognitive load, elapsed time or WIP.
- Agent review loops rewarded finding and adding edge cases but had no strong
  convergence signal for consolidation, deletion or returning to Recovery.
- Recorded dependency and exclusion boundaries were not enforced
  operationally; no mechanism stopped queued post-baseline analysis from
  consuming the active baseline-review WIP.

These are process and system-design causes, not an individual-reviewer failure.
The agents' correlated self-audit is useful evidence but is not independent
human validation.

## Resolution

On 2026-08-14 the work was reset to the original Issue #1 outcome. A
thread-aware audit separated actual PR blockers from post-baseline design work,
and one bounded source patch was prepared instead of continuing the nested
review ledger.

Commit `4b3c71363aa95961139eba2b627ee911e9dd900a`:

- applied the already owner-selected README clarification that Git is the
  normative change substrate while consumer stacks and hosting providers
  remain technology-neutral;
- applied the already owner-selected definition of the complete reusable
  public surface and its distinct artifact authorities;
- revised the publication-review runbook to define the five lifecycle states,
  one mandatory canonical-source manifest, review-material roles and
  owner/agent/CI authority boundaries;
- removed the implied per-row sign-off ledger, required revisit only for
  changed sources or unresolved blockers and retained scope-splitting Recovery;
- kept F-REV-01 and WI-DET-01 as separate post-baseline work rather than
  implementation prerequisites for PR #2.

The resulting revision passed 61 unit tests, policy, bundle, guardrail,
change-control, CI-policy, regression, smoke and containerized documentation
verification. GitHub reported PR #2 clean and mergeable. The repository
remained private and the PR remained draft and unmerged; the correction created
a reviewable candidate, not owner acceptance, integration or publication.

## Operational lessons

- Name one active deliverable, immutable candidate and exit condition before
  beginning semantic review.
- Treat out-of-scope dogfood findings as queued roadmap evidence. They enter
  the active critical path only through an explicit scope change.
- Use one canonical traversal manifest. Do not recursively promote every piece
  of evidence, history or projection into a new semantic-review target.
- Ask for one owner decision per genuine semantic choice. Faithful recording
  or deterministic derivation of an already authorized effect is not another
  semantic decision.
- Revisit unchanged material only for an unresolved blocker. When review
  growth threatens auditability, apply Recovery and split the candidate.
- Evaluate convergence by correctness, owner cognitive load, elapsed time and
  time-to-integration, not by finding count or ledger size.
- Dogfooding may change the roadmap; it must not silently replace the current
  roadmap.

## Residual state

The immediate critical-path drift is contained at candidate level. It is not
fully closed until the accountable owner accepts an exact revision and the
private baseline is integrated. F-REV-01's proposed numerical effort bounds and
agent-routing change were not adopted by this correction and require their own
normal governance if pursued. Issue #12 and WI-DET-01 remain queued,
non-admitted implementation work. Repository visibility and every artifact or
site publication remain separate future effects.

This retrospective preserves the earlier append-only records and does not
reinterpret them as owner approval, authorize a merge or publication, or make
any queued Work Item effective.
