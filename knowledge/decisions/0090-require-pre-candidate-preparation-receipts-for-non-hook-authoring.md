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

Reuse the existing `ci/style` contract, Git's content-addressed tree/worktree
plumbing, temporary-index primitives, and ordinary focused verification commands.
The repository already reconstructs tree identities with a temporary
`GIT_INDEX_FILE` in the Experiment Capsule implementation.

Concrete alternatives were evaluated before selecting the bounded implementation:

- **pre-commit** (MIT) is license-compatible, but its enforcement point is a
  local Git hook. Direct GitHub/Git-data/API authoring can bypass it, and it does
  not produce a portable exact-parent/exact-tree preparation receipt.
- **Lefthook** (MIT) is likewise license-compatible and useful for local hook
  orchestration, but it has the same non-hook/API activation gap and would add a
  new hook framework without closing the provider-neutral publication boundary.
- **The existing Experiment Capsule** is already part of this repository and
  therefore has no additional third-party license burden, but its state machine,
  retained-effect transaction and recovery semantics are materially broader than
  the one bounded pre-publication sequence required here.

No third-party dependency is added by this Decision. The remaining unmet need is
an exact-tree, provider-neutral preparation/publication boundary that works for
non-hook authoring without importing a general orchestration subsystem.

## Decision

1. Add one Gnostoa-self `ci/prepare-candidate` surface backed by a small Python
   implementation. It is implementation-private and does not extend the public
   toolkit CLI. The wrapper resolves the repository root from its own location
   before importing the implementation so invocation does not depend on the
   caller's current working directory.
2. Preparation binds one exact 40-character parent commit. The source worktree
   `HEAD` must equal that parent; stale-parent preparation fails closed.
   Repository discovery scrubs inherited repository-routing, external-diff,
   `GIT_CONFIG_PARAMETERS` and other caller-supplied `GIT_CONFIG*`
   overrides. Existing executable repository-local filter/diff/fsmonitor
   configuration or non-empty `.git/info/attributes` fails closed at admission.
   After that admission check, candidate Git operations no longer consume the
   source repository's mutable local configuration.
3. Preparation creates disposable Git metadata with a trusted local config.
   Git object access is bound explicitly to the source repository's
   content-addressed object store: candidate blobs/trees are written there so a
   successful prepared-tree identity remains reachable after the disposable
   metadata is removed, while candidate staging, checkout, diffing and workspace
   Git commands never load the source repository's mutable local config. A
   concurrent mutation of the source `.git/config` or source-local attributes
   therefore cannot affect the prepared bytes or execute a newly injected
   filter. Before any preparation authority executes,
   the proposed tree must leave `ci/prepare-candidate`, `ci/style`,
   `ci/verify`, and `tools/candidate_prepare.py` unchanged from the parent.
   Changes to those authority surfaces require a separately admitted
   authority-evolution path. The proposed tree is materialized into a disposable
   workspace backed only by the isolated Git metadata; normalization and focused
   verification never use the caller's live Git metadata.
   This excludes ignored/untracked source-worktree files and concurrent caller
   edits from the verified candidate. Candidate trees containing symlinks fail
   closed before style or verification; the current contract does not attempt to
   authenticate external symlink target chains.
4. Preparation runs `./ci/style --fix` in that isolated worktree, stages the
   normalized result, then cleans ignored/untracked residue and restores exactly
   the normalized index before focused verification. The external CLI accepts
   only `policy`, `security-fast`, `fast`, `regression`, `smoke`, and
   `extended`; each maps to static `./ci/verify <suite>` argv with
   `shell=False`. Caller input cannot choose an executable or arbitrary
   verification arguments.
5. Focused verification must not mutate the prepared tree or its index. Ignored
   caches may be produced transiently, but they are removed before the final
   style decision. Preparation then reruns `./ci/style --check` against the
   restored exact normalized tree and executes `git diff --cached --check`.
6. Run `ci/prepare-candidate` from the recommended Development Container by
   default. The module intentionally invokes `ci/verify` directly inside the
   environment that hosts the isolated worktree instead of launching nested
   Docker. Direct host execution is the documented native fallback only when the
   container route is unavailable; the caller records that reason. Provider CI
   remains the authoritative independent check.
7. The successful receipt binds at least parent commit/tree, prepared tree,
   prepared binary-diff SHA-256, changed paths, parent-bound `ci/style` and
   `ci/verify` SHA-256 identities, observed Ruff version, focused profile plus
   its logical repository-owned command identity, and zero exit status for every
   required step. Its canonical SHA-256 is an integrity binding, not
   authentication or bearer authority. It records `PRE_CANDIDATE_RUFF_CATCH`
   when normalization changes the proposed tree, otherwise
   `PRE_CANDIDATE_NO_RUFF_CHANGE`.
8. Receipts are evidence, not candidate source. The output path must be outside
   the source worktree. The trusted preparation step must retain the emitted
   `receipt_sha256` separately from the receipt bytes. `verify_receipt()` and
   `ci/prepare-candidate verify` require that externally retained identity in
   addition to the expected parent/tree, then recompute the receipt digest. A
   self-consistent caller-supplied receipt and self-chosen digest therefore do
   not satisfy the trusted handoff.
9. This slice intentionally acquires no provider-write authority. A future
   Git-data/API publishing adapter must run trusted preparation itself or consume
   separately authenticated preparation provenance and the retained receipt
   identity before any ref effect. That effect/fencing boundary remains owned by
   #15/#308; arbitrary external API clients are not claimed impossible to bypass
   by this repository-local preparation contract.
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
- successful preparation materializes the proposed tree in an isolated
  disposable worktree, normalizes there, and verifies the exact normalized tree
  without admitting source-worktree-only ignored/untracked state;
- the external CLI rejects arbitrary command execution by accepting only the
  closed repository-owned focused-profile vocabulary;
- a candidate that changes `ci/prepare-candidate`, `ci/style`,
  `ci/verify`, or `tools/candidate_prepare.py` relative to the bound parent
  is rejected before preparation authority executes;
- successful receipts bind both preparation-authority SHA-256 identities;
- untracked additions and deletions are included in the prepared tree/diff;
- focused verification mutation is rejected;
- stale parent, failed normalization/check, failed focused verification, and
  candidate-local receipt paths fail closed;
- receipt inspection rejects parent, tree, digest, schema or check-state
  mismatch and requires a separately retained trusted receipt identity without
  claiming cryptographic producer authentication;
- inherited Git configuration, including `GIT_CONFIG_PARAMETERS`, cannot inject
  filter/diff/hook execution into staging; existing executable repository-local
  Git configuration fails closed and later source-local configuration races are
  irrelevant because candidate Git operations use disposable metadata;
- candidate symlinks are rejected before any preparation authority executes;
- malformed receipt path lists fail closed as `PrepareError` rather than
  escaping the verifier with an implementation exception;
- the wrapper and Gnostoa agent route point to the same preparation surface; and
- existing `ci/style` remains the single Ruff scope/command authority.

## Consequences

API/agent authoring gains an exact-tree pre-candidate normalization boundary
without making hooks mandatory or weakening provider CI. Receipt consumption is
bound to a separately retained trusted identity, but the portable receipt is
still evidence rather than producer authentication. Provider-specific write
effects and writer fencing remain deliberately outside this slice under
#15/#308 and must preserve the preparation trust boundary when implemented.

This does not by itself establish cross-session writer uniqueness; #308 owns
that separate fencing problem. It also does not establish effectiveness of
Decision 0081; #262 retains that longitudinal assessment as a parallel evidence
lane.
