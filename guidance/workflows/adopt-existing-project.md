---
type: Workflow
title: Adopt an existing project
description: Introduce governed knowledge incrementally without legitimizing stale or contradictory legacy documentation.
status: draft
generated:
  by: codex/gpt-5
  at: "2026-07-29T00:00:00Z"
x-project-knowledge:
  id: guidance.workflow.adopt-existing-project
  owners:
    - team:gnostoa-maintainers
  scope:
    - generic-guidance
  relations:
    - kind: governed-by
      target: /guardrails/non-negotiable.md
    - kind: depends-on
      target: /practices/source-authority-and-lifecycle.md
    - kind: references
      target: /reference/repository-layout-and-distribution.md
    - kind: depends-on
      target: /workflows/bootstrap-new-project.md
    - kind: depends-on
      target: /workflows/propose-review-merge-change.md
    - kind: depends-on
      target: /workflows/configure-continuous-integration.md
---

# Adopt an existing project

## Outcome

One real development workflow has a verified current-state knowledge slice,
clear source authority, visible contradictions and measured navigation value.
The adoption does not attempt a big-bang rewrite of legacy documentation.

## First verified adoption slice

First resolve the intended commitment through the
[adoption guide](../../docs/core/adoption.md). A **minimal evaluation** follows
the linked quick start and stops before repository-owned policy, CI or provider
maintenance is introduced. A **durable adoption** continues through this
workflow. If the commitment is unclear, keep it unresolved and stop rather than
silently choosing the larger surface. If accountable ownership is unknown, keep
the affected knowledge draft or unresolved and ask; do not invent a person,
team, provenance or acceptance.

For durable adoption, complete this bounded slice before expanding the full
procedure:

1. Select one pilot and bind the exact documentation and toolkit source subjects.
   Use the [bootstrap root and target map](bootstrap-new-project.md#roots-targets-and-identities)
   rather than reconstructing file placement from names.
2. Check source access, workspace state and required project tools, then identify
   the **actual supported execution route** that will run: native, source-built
   or immutable OCI. Record the observed route identity; a declaration alone is
   not execution evidence.
3. Author only the project-owned profile, lock, policy and smallest draft concept
   spine needed by the pilot. Preserve unknown facts as unknown.
4. Run source/runtime-lock, policy, profile and bundle structural validation
   through that route.
5. Run bounded-context generation for the pilot and retain the generated output
   and its identity. Follow its concept paths back to canonical project records
   for full evidence.
6. Run the project suites that the environment supports. Classify an unavailable
   required tool or suite separately as `BLOCKED`; do not report it as a pass or
   make it erase a distinct structural result.
7. Record the dimensions independently rather than collapsing them into one
   adoption status:
   - Structural validation: `PASS`, `FAIL` or `NOT RUN`.
   - Bounded context generation: `PASS`, `FAIL` or `NOT RUN`.
   - Project suites: `PASS`, `FAIL`, `BLOCKED` or `NOT RUN`.
   - Semantic owner review: `ACCEPT`, `CORRECT`, `REJECT` or `UNRESOLVED`.
   - Durable adoption: `YES`, `NO` or `DEFERRED`.

Only an accountable owner can accept the semantic content and durable
commitment. This slice is a concentrated entry to the existing procedure, not a
universal path and not a substitute for the linked bootstrap, verification or
provider details.

## Preserve existing project authority

Before writing any mapped target, inspect whether it already exists and
identify its project authority. A reusable template is source material for
adaptation, not authorization to replace an existing authoritative file.

If `AGENTS.md` exists and the authority to edit it is clear, preserve its
existing project-specific instructions, add only the missing Gnostoa routing
section, and retain unrelated content and ordering where practical. Record the
before/after diff or identities as adoption evidence. Never silently resolve
contradictory instructions. If a Gnostoa route conflicts with existing project
instructions, or authority to alter them is unclear, stop, preserve the
existing file, record the conflict and request accountable-owner resolution.

Apply the same inventory and no-blind-overwrite boundary to existing mapped
policy, CI and verification targets. This boundary does not imply that prose or
a reusable template can mechanically merge their semantics. The existing
unknown-owner and commitment stop, source/runtime-lock check and final staged
gitlink equality remain required in their owning steps; do not replace them
with file-preservation evidence. This documentation is a falsifiable control,
not a guarantee of agent compliance, and one later fresh rerun must measure its
predicted benefit.

## Preconditions

- A bounded pilot area and its accountable owners are selected.
- The source repositories and available historical material are accessible.
- The team agrees to distinguish current state, target state and proposals.
- A baseline task set exists for measuring searches, tokens, correctness and
  review time.

## Procedure

1. Choose embedded placement for one repository or a dedicated knowledge
   repository for a multi-repository program.
2. Pin the toolkit revision, deterministic public-surface digest and matching
   runtime identity, then create a minimal project profile and validate the lock
   through the [new-project workflow](bootstrap-new-project.md).
3. Inherit the generic change-control and CI policies. Inventory current branch,
   review, hooks, pipelines, test suites, secrets and emergency practices, and
   record gaps without silently treating them as compliant.
4. Select one protected integration branch and one pilot Change Request. Do not
   attempt to migrate all open long-lived branches in the first change.
5. Establish high-impact characterization tests around the pilot behavior before
   refactoring or normalizing it. Do not pursue blanket coverage.
6. Create the verification manifest around the pilot. Map existing fast and
   regression commands first, declare conditional capabilities honestly, then
   exercise one failing candidate pipeline before making its checks required.
7. Inventory sources without summarizing them. Record owner, location,
   revision, last modification and authority class.
8. Establish source precedence for standards, accepted decisions, executable
   contracts, implementation, reviewed documentation, meeting records and
   generated summaries.
9. Model the current state first. Keep target architecture and proposals in
   separate concepts.
10. Create only the concepts needed by the pilot: repositories, boundaries,
   contracts, decisions, open questions and contradictions.
11. Link to source artifacts rather than copying their contents.
12. Keep generated or inferred concepts as `draft`; promote them only after
   source-owner review.
13. Validate source/runtime lockstep, the inherited change and CI policies,
    verification manifest and new bundle strictly. Raw legacy
    Markdown remains outside the bundle unless converted to conforming `Source`
    concepts.
14. Run the baseline tasks with and without the knowledge slice and compare
    correctness, exploration operations, input tokens and human review time.
15. Expand one bounded area at a time only when the previous slice remains
    maintainable.

## Verification

- Every stable claim has a human verifier.
- Contradictory sources remain visible and are not silently reconciled.
- Current and target architecture are distinguishable.
- The pilot answers its selected questions by following concepts to evidence.
- Measured savings exceed generation and maintenance cost.
- The pilot change reaches the protected branch only through a passing Change
  Request and any review required by the project's specialization.
- Required checks belong to the latest pilot merge candidate; hook success
  alone cannot satisfy integration.

## Recovery

If authority cannot be established, retain the material as a draft Source or
open question. If maintenance cost grows faster than value, freeze expansion,
reduce the taxonomy and retain only the verified navigation spine.
