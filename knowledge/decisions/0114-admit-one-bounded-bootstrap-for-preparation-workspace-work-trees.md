---
type: Decision
title: Admit one bounded bootstrap for declaring each preparation workspace's own work tree
description: "The owner-approved N-a narrowing in #436 refuses a gitfile whose selected Git directory declares no core.worktree, and the trusted preparer builds exactly such workspaces, so no candidate carrying N-a can be prepared. This Decision admits one finite, two-stage bootstrap for the first evolution of tools/candidate_prepare.py. After this governance change is integrated, an activation record binds the exact protected parent and its authority inventory for 48 hours. The one constructor correction is then published with every replacement blob bound, verified directly as Decisions 0109 and 0113 were, and recorded as having no ordinary preparation receipt."
status: draft
generated:
  by: anthropic/claude-opus-5-5
  at: "2026-10-18T12:32:48Z"
sources:
  - id: work-item
    resource: https://github.com/ktogias/gnostoa/issues/438
    title: Declare each preparation workspace's own work tree in its disposable Git metadata
  - id: owner-choice
    resource: https://github.com/ktogias/gnostoa/pull/436#issuecomment-6247664595
    title: The owner's selection of A, and the clarification about the preparer's own metadata
  - id: route
    resource: https://github.com/ktogias/gnostoa/pull/436#issuecomment-6249869986
    title: The Router's governance-first route for this first evolution
  - id: review
    resource: https://github.com/ktogias/gnostoa/pull/436#issuecomment-6249938361
    title: The Router's admission review, its exact-parent activation stage and 48-hour expiry
  - id: measured-refusal
    resource: https://github.com/ktogias/gnostoa/pull/436#issuecomment-6241891760
    title: The measured preparation refusal of an N-a candidate, and its control
  - id: preparation-owner
    resource: ./0090-require-pre-candidate-preparation-receipts-for-non-hook-authoring.md
    title: The preparation authority and its separately admitted evolution
  - id: precedent-0109
    resource: ./0109-run-the-test-suite-in-parallel-processes-through-one-owner.md
    title: Authority evolution verified directly in the development container and the runtime image
  - id: precedent-0113
    resource: ./0113-read-pull-request-descriptions-with-a-commonmark-parser.md
    title: Authority evolution verified directly, as Decision 0109's was
x-project-knowledge:
  id: kit.decision.0114.admit-one-bounded-bootstrap-for-preparation-workspace-work-trees
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: references
      target: /decisions/0090-require-pre-candidate-preparation-receipts-for-non-hook-authoring.md
    - kind: references
      target: /decisions/0109-run-the-test-suite-in-parallel-processes-through-one-owner.md
    - kind: references
      target: /decisions/0113-read-pull-request-descriptions-with-a-commonmark-parser.md
---

# Admit one bounded bootstrap for declaring each preparation workspace's own work tree

## Context

[Decision 0090](0090-require-pre-candidate-preparation-receipts-for-non-hook-authoring.md)
makes `tools/candidate_prepare.py`, run from the exact parent, the preparation
authority. A candidate that changes it is refused, by design. Later evolution
"requires a separately admitted path".

[Decision 0109](0109-run-the-test-suite-in-parallel-processes-through-one-owner.md) and
[Decision 0113](0113-read-pull-request-descriptions-with-a-commonmark-parser.md)
already evolved other preparation-authority surfaces: `ci/verify`, `pyproject.toml`
and the locks. The owner admitted each one, and each was verified directly in the
development container and the runtime image. This is the first evolution of
`tools/candidate_prepare.py` itself.

The need comes from #436. The owner-approved N-a narrowing refuses a `gitdir:` file
whose selected Git directory declares no `core.worktree`. The trusted preparer builds
exactly such workspaces: disposable metadata made with `git init --bare`, then
`core.bare false`, and a workspace `.git` written as `gitdir: <metadata>`, with no
`core.worktree`. An N-a candidate's exact-parent preparation therefore exits 2, for
`security-fast` and for `fast`, so none can be prepared. The owner selected a
minimal, separately admitted evolution first (A) in #436 and clarified that the
earlier "no automatic config write" restriction concerned the scope reader and
operators' checkouts, not the trusted preparer's own temporary metadata.

## Decision

1. **One responsibility.** The bootstrap admits exactly one change:
   `_candidate_workspace` sets `core.worktree` to the actual resolved workspace root,
   in the disposable Git metadata it is given: the metadata that the trusted
   preparer's `_isolated_git_metadata` creates for that workspace, never an
   operator's. It does so under the existing isolated environment. That covers both the normalization and the focused-verification
   workspaces. Its tests go in the existing `tests/test_candidate_prepare.py`.
   - **The allowlist:** those two paths, and no other.
   - **Unchanged:** every other configuration write, file and responsibility,
     including `ci/prepare-candidate`, `ci/style`, `ci/verify`, the Ruff
     configuration and the dependency locks.
2. **This governance change edits no protected authority.** It is effective only
   once integrated through its ordinary native normative review and the owner's
   acceptance. Until then, nothing in the preparation authority changes.
3. **Stage 1, activation.** After this Decision is integrated, and before the first
   edit to the candidate authority, the implementer freshly reads and freezes:
   - the full protected-main SHA **P** and its tree;
   - this governance change's merge identity;
   - the complete path, mode and blob inventory of the preparation authority and
     its configuration: Decision 0090's protected paths, plus the dependency locks
     that Decisions 0109 and 0113 treat as preparation-authority surfaces.

   That record is retained on #438 together with an absolute UTC expiry. It is
   compared with the admitted old-authority inventory below, read at main
   `839ffea51c91935a0ff523607fe2e0ba354f15c1`. Any difference is drift and voids
   the bootstrap. An added or removed Ruff configuration path counts as one, and
   so does a mode change alone, such as an executable bit, with the blob unchanged.

   | Path | Mode | Blob at `839ffea5` |
   |---|---|---|
   | `ci/prepare-candidate` | `100755` | `cb8fc7c1ca455e8619109ebe613f4603259385f2` |
   | `ci/style` | `100755` | `d132ff0fbfd13577aeb679644c5a1c68b508ba86` |
   | `ci/verify` | `100755` | `56e9f2f6e5982c0da55fd594b0962244769853df` |
   | `tools/candidate_prepare.py` | `100644` | `88b5d4eaef838135c5246f2e65bb10f81b72af90` |
   | `pyproject.toml` | `100644` | `b4470749c54893140544b33cb729e132a8e06f24` |
   | `requirements/development.lock` | `100644` | `9c0b944b7da06982d4673519eafaba96415fa65c` |
   | `requirements/runtime.lock` | `100644` | `52ef2878a30dcfa2161e6a6f1cf1773f293b8570` |
   | `tests/test_candidate_prepare.py` | `100644` | `f039ea635816c12e78fcbb6f94b143f28415b081` |

   No `ruff.toml` or `.ruff.toml` exists at `839ffea5`.
4. **An exact parent, never a floating one.** The candidate's parent is P. If main
   advances for any reason before integration, P is invalid. The implementer
   reconciles and rebinds explicitly, with a new activation record, before
   continuing. Matching authority blobs never let the parent float.
5. **Stage 2, the candidate.** The evidence comes in a fixed order:
   - **RED first,** against the authority at P: neither workspace has its own
     resolved `core.worktree`. The measured N-a refusal and its `a65c3d4d` binding
     are retained.
   - **Then the one correction, then GREEN.**
   - **A publication record,** made before the candidate is published. It binds P
     and every replacement path's mode and blob, and every other tree entry, mode
     included, must equal P's.
   - **The final native review and the owner's approval** bind the exact candidate
     head and tree. A changed head or tree invalidates that review and the
     publication binding, and is never silently substituted.

   These records manufacture no preparation receipt.
6. **Evidence in place of a receipt.** It reuses Decisions 0109's and 0113's direct
   verification.
   - **GREEN covers:**
     - both workspace identities;
     - isolation and cleanup;
     - operator, source and global configuration, byte-unchanged;
     - the parent and tree binding, and the retained refs;
     - the profiles actually measured, with none claimed unmeasured;
     - continued refusal of unadmitted protected-authority edits;
     - no later Git command relying on a deleted workspace.
   - **The candidate authority is the subject under test.** It runs through
     independently retrieved exact-parent execution controls, in the pinned
     development container, and never as its own receipt producer.
   - **Also retained:** the full extended suite, provider CI, an independent
     semantic review, the PAO challenge and the native exact-head owner approval.
   - **The old parent's expected refusal** is recorded as **NO ORDINARY PREPARATION
     RECEIPT / EXPLICIT BOOTSTRAP LIMITATION**. Hashes prove byte identity, not
     producer independence or permission.
7. **Expiry and consumption.** The bootstrap expires 48 hours after this
   governance change's integration timestamp, at the absolute UTC time recorded in
   the activation record. It permits one successfully integrated preparation
   correction, and expires earlier on any of these:
   - that consumption;
   - authority or configuration drift;
   - loss of the subject binding;
   - refusal of a required control.

   It has no automatic renewal, no reset on restart and no inherited permission. A
   genuine expiry or a new scope conflict is reported before any effect.
8. **The guard is unchanged.** The ordinary parent guard keeps rejecting every
   protected-authority edit outside this one admitted bootstrap.
   - **Never:** a fabricated receipt, a substituted authority, break-glass, a direct
     edit to main, or a candidate certifying itself.
   - **If a provider or check contract cannot represent this limitation,** that
     blocker is reported before any effect, never overridden.
9. **After integration.** Descendants are prepared normally by the evolved
   authority, and #436 re-parents onto it before N-a resumes.

## Evidence

- **The measured refusal** ([#436, 6241891760](https://github.com/ktogias/gnostoa/pull/436#issuecomment-6241891760)):
  - an N-a candidate's preparation from the exact parent `a65c3d4d` exits 2 for
    `security-fast` and `fast`;
  - the same route without N-a exits 0;
  - a rebuilt workspace layout reproduces the refusal in the full suite.
- **Where the declaration acts**, read at `839ffea5`. Every trusted Git call against
  the disposable metadata goes through `_isolated_git_env`, which sets `GIT_DIR` and
  `GIT_WORK_TREE`, and the environment overrides `core.worktree`.
  - **So for every trusted step it is inert:** capture, staging, style,
    post-checks and retention.
  - **It acts only where candidate code discovers Git** through the workspace's
    gitfile, in focused verification, which scrubs that routing.

## Consequences

- **The preparer's own metadata declares its work tree,** so the N-a narrowing can
  apply everywhere, preparation included.
- **No other authority evolution inherits this bootstrap.** Each needs its own
  admission.
- **Not covered here:** #368's planned move of the preparation authority onto a
  shared execution primitive is untouched. F3 stays `UNVERIFIED/INCOMPLETE`.

## Alternatives not chosen

- **N-b:** keep undeclared separate Git directories valid through a larger mechanism.
  The common-directory false binding would stay open until that is verified.
- **A split #436:** land only the linked-worktree arm. The common-directory finding
  would stay open.
- **The one-PR shape of Decisions 0109 and 0113:** chosen against for a change to the
  preparation implementation itself, in favour of a governance step first.
- **Binding by blob equivalence alone,** letting the parent float: rejected for the
  exact-parent activation record.
- **A production candidate before governance:** rejected as circular. The candidate
  is bound only after this Decision is effective.

## Delivery

This change is governance only: this Decision and its index entry, with no edit to
the preparation authority. It is not Python source, so it needs no preparation
receipt. It is verified in the development container: the knowledge bundle, policy
and extended suite.

Stage 1 and Stage 2 then proceed as decided above, under Work Item #438.
