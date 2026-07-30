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
      target: /workflows/propose-review-merge-change.md
    - kind: depends-on
      target: /workflows/configure-continuous-integration.md
---

# Adopt an existing project

## Outcome

One real development workflow has a verified current-state knowledge slice,
clear source authority, visible contradictions and measured navigation value.
The adoption does not attempt a big-bang rewrite of legacy documentation.

## Preconditions

- A bounded pilot area and its accountable owners are selected.
- The source repositories and available historical material are accessible.
- The team agrees to distinguish current state, target state and proposals.
- A baseline task set exists for measuring searches, tokens, correctness and
  review time.

## Procedure

1. Choose embedded placement for one repository or a dedicated knowledge
   repository for a multi-repository program.
2. Pin the toolkit and create a minimal project profile as in the new-project
   workflow.
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
13. Validate the inherited change and CI policies, verification manifest and new
    bundle strictly. Raw legacy
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
