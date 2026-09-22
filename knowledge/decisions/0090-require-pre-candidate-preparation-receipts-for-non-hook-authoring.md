---
type: Decision
title: Require pre-candidate preparation receipts for non-hook authoring
description: Bind candidate publication to an exact parent and prepared Git tree after repository style normalization, post-format verification, and diff checks, including API and Git-data authoring routes.
status: draft
generated:
  by: openai/gpt-5.6-sol
  at: "2026-09-22T14:30:00Z"
sources:
  - id: work-item
    resource: https://github.com/ktogias/gnostoa/issues/262
    title: Align Ruff configured scope with enforced CI coverage
  - id: owner-admission
    resource: https://github.com/ktogias/gnostoa/issues/262#issuecomment-5775048741
    title: Owner priority/admission — close API/agent candidate-preparation escape at the first safe slot
  - id: post-272-reproduction
    resource: https://github.com/ktogias/gnostoa/issues/262#issuecomment-5775004993
    title: Post-#272 dogfood finding — GitHub API authoring bypasses the pre-candidate Ruff control
  - id: ruff-scope-decision
    resource: ./0081-make-repository-root-ruff-scope-authoritative-before-candidate-sealing.md
    title: Make repository-root Ruff scope authoritative before candidate sealing
  - id: split-brain-work-item
    resource: https://github.com/ktogias/gnostoa/issues/308
    title: Enforce a single active implementation identity per Work Item across sessions
x-project-knowledge:
  id: kit.decision.0090.require-pre-candidate-preparation-receipts-for-non-hook-authoring
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governed-by
      target: /decisions/0081-make-repository-root-ruff-scope-authoritative-before-candidate-sealing.md
---

# Require pre-candidate preparation receipts for non-hook authoring

## Context

Decision 0081 made `./ci/style` the repository-root Ruff decision surface and
requires normalization before a Python-affecting candidate is sealed. PR #305
showed that the rule is not mechanically activated for GitHub API/Git-data
authoring: blobs, trees, commits and refs can be created without a local Git
hook or worktree preflight. Provider CI then detects deterministic formatting
only after a candidate SHA exists, causing an avoidable successor SHA and stale
exact-head review evidence.

The defect is activation coverage, not Ruff scope or version. Local hooks remain
useful feedback for ordinary Git, but they cannot be the authority boundary for
an authoring route that never invokes them.

## Prior-art and reuse disposition

Reuse the existing `ci/style` contract, Git's content-addressed tree identity,
temporary-index primitives, and ordinary focused verification commands. The
repository already reconstructs tree identities with a temporary
`GIT_INDEX_FILE` in the Experiment Capsule implementation, which establishes the
Git primitive without requiring that heavier workflow here.

Do not reuse the Capsule state machine, retained-effect transaction machinery or
a generic orchestration framework. Candidate preparation needs one bounded
sequence before candidate publication, not experiment qualification or remote
effect recovery.

## Decision

1. Add one Gnostoa-self `ci/prepare-candidate` surface backed by a small Python
   implementation. It is implementation-private and does not extend the public
   toolkit CLI. The wrapper resolves the repository root from its own location
   before importing the implementation so invocation does not depend on the
   caller's current working directory.
2. Preparation binds one exact 40-character parent commit. The worktree `HEAD`
   must equal that parent; stale-parent preparation fails closed. Repository
   discovery and Git object access scrub inherited repository-routing,
   worktree/object-store and index overrides before invoking Git; only the
   preparation-owned temporary `GIT_INDEX_FILE` is reintroduced where needed.
3. Preparation requires an existing proposed tree delta, runs
   `./ci/style --fix`, then runs one repository-owned focused verification
   profile with `shell=False`. The external CLI accepts only the closed profile
   vocabulary `policy`, `security-fast`, `fast`, `regression`, `smoke`,
   and `extended`; each profile maps to a static `./ci/verify <suite>` argv.
   Caller input cannot choose an executable or arbitrary verification arguments.
   The implementation-private `prepare()` boundary accepts the same closed
   profile vocabulary; no lower layer accepts a caller-supplied command vector.
4. Focused verification must not mutate the candidate. The prepared tree after
   normalization is measured before and after the focused command; any change
   fails closed.
5. Preparation then runs `./ci/style --check` and verifies the exact prepared
   temporary index with `git diff --cached --check`.
6. The successful receipt binds at least parent commit/tree, prepared tree,
   prepared binary-diff SHA-256, changed paths, `ci/style` SHA-256, observed Ruff
   version, focused profile plus its logical repository-owned command identity,
   and zero exit status for every required step. The
   receipt carries a canonical SHA-256 over its own payload and records
   `PRE_CANDIDATE_RUFF_CATCH` when normalization changed the proposed tree,
   otherwise `PRE_CANDIDATE_NO_RUFF_CHANGE`. Post-seal Ruff escapes remain a
   separate Decision 0081 ledger classification.
7. Receipts are evidence, not candidate source. The output path must be outside
   the repository worktree so creating the receipt cannot change the prepared
   tree it describes.
8. A publishing adapter must compare the exact parent and exact tree it intends
   to publish with a valid receipt before creating or advancing a candidate ref.
   The implementation exposes both `verify_receipt()` and the
   `ci/prepare-candidate verify` CLI for that provider-neutral consumption
   boundary. Parent/tree mismatch, altered receipt, failed check, missing focused
   command, or unsupported receipt version fails closed.
9. GitHub API/Git-data authoring may still create the final provider objects; it
   consumes prepared bytes/tree identity rather than generated text that has not
   crossed the preparation boundary.
10. Provider CI remains check-only and authoritative. A preparation receipt is
    neither semantic review, approval, merge authority nor a replacement for
    post-publication exact-head checks.
11. Keep this slice bounded. Do not implement a general workflow engine,
    auto-commit service, provider-specific formatter service, automatic merge,
    reviewer dispatch, or #308 distributed writer lease here.

## Verification contract

The change must retain executable evidence that:

- ordinary Git can currently commit a Ruff-dirty tree without this new receipt,
  characterizing the API/non-hook escape;
- successful preparation normalizes before focused verification, and the focused
  verifier observes the normalized candidate;
- the external CLI rejects arbitrary command execution by accepting only the
  closed repository-owned focused-profile vocabulary;
- untracked additions and deletions are included in the prepared tree/diff;
- focused verification mutation is rejected;
- stale parent, failed normalization/check, failed focused verification, and
  candidate-local receipt paths fail closed;
- receipt verification rejects parent, tree, digest, schema or check-state
  mismatch;
- the wrapper and Gnostoa agent route point to the same preparation surface; and
- existing `ci/style` remains the single Ruff scope/command authority.

## Consequences

API/agent authoring gains the same pre-candidate normalization boundary that
ordinary Git users receive through local workflow practice, without making hooks
mandatory or weakening provider CI. A prepared tree can be published through a
provider adapter only after its exact identity is bound to successful local
mechanical evidence.

This does not by itself establish cross-session writer uniqueness; #308 owns
that separate fencing problem. It also does not establish effectiveness of
Decision 0081; #262 retains that longitudinal assessment as a parallel evidence
lane.
