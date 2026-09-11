---
type: Source
title: D14-O2 O2-A0 local Git subject guard execution plan
description: Bounded verification-first plan for preventing a retained Gnostoa-self orientation snapshot from remaining current after the inspected Git subject changes.
status: draft
generated:
  by: agent:gpt-5.6-sol
  at: "2026-09-11T15:16:00Z"
sources:
  - id: work-item
    resource: https://github.com/ktogias/gnostoa/issues/14
    title: Add reproducible goal-alignment and delivery-state projections
  - id: owner-admission
    resource: https://github.com/ktogias/gnostoa/issues/14#issuecomment-5637217420
    title: D14-O2 O2-A0 owner admission
  - id: decision
    resource: ../decisions/0066-invalidate-self-orientation-on-local-git-subject-drift.md
    title: Decision 0066
  - id: d14-o1-result
    resource: ./14-bounded-self-orientation-result.md
    title: D14-O1 bounded self-orientation result
  - id: claude-review
    resource: https://github.com/ktogias/gnostoa/issues/14#issuecomment-5637095406
    title: Supplied Claude review and root disposition
x-project-knowledge:
  id: kit.assessment.14-orientation-git-subject-guard-plan
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governed-by
      target: /decisions/0066-invalidate-self-orientation-on-local-git-subject-drift.md
    - kind: governed-by
      target: /decisions/0005-container-first-runtime.md
    - kind: governed-by
      target: /requirements/verification-precedes-implementation.md
    - kind: references
      target: /runbooks/deliver-bounded-self-hosted-slice.md
---

# D14-O2 O2-A0 local Git subject guard execution plan

## Identity, authority and effect boundary

Owner admission is limited to O2-A0 and starts from integrated `main`
`a0b7c8a170942fce61ff3c08b350bc3d7ab0a2a0`. The implementation branch is
`agent/14-orientation-git-subject-guard`.

This plan permits changes only to the existing self-only orientation script and
its focused tests, Decision 0066, this plan/result evidence and the minimal
self-knowledge index routing required to validate those records. It does not
admit O2-B/C/D, provider collection or mutation, a generic projection schema,
new package/entry point, `tools/orientation/`, public-surface policy changes,
MCP, daemon, workflow/DAG engine, automatic semantic next-action selection or
manual rewriting of the stale D14-O1 snapshot.

Merge is not authorized by this plan or the implementation admission.

## Retained characterization

At the admitted integrated base:

- `tasks/issue-14-orientation.md` reports `Status: CURRENT`;
- its subject commit is `1acf9bb448e7342bbf1b8a4cf16f3b2a86225f89`;
- integrated `main` is `a0b7c8a170942fce61ff3c08b350bc3d7ab0a2a0`;
- its next action still says to verify the already-merged D14-O1 candidate;
- the live script validates local-file digests and supplied provider identities
  but does not observe repository `HEAD` or `HEAD^{tree}`;
- `_within_root` uses resolved-path confinement, but its traversal and symlink
  escape behavior lacks direct automated regression coverage.

The stale committed snapshot is deliberately not refreshed before the guard is
implemented. It is the first real behavioral discriminator.

## Focused RED before production mutation

Add tests before changing `tasks/gnostoa_orientation.py`:

1. **Real stale-snapshot CLI discriminator.** Invoke the orientation CLI against
   the repository's retained D14-O1 JSON from the current branch. Expected:
   nonzero status, evaluation not `CURRENT`, and a stable Git-subject mismatch
   diagnostic. Pre-change behavior is expected to return `CURRENT`, establishing
   the RED.
2. **Traversal confinement.** A `../` locator resolving outside the explicit
   repository root raises `OrientationError`.
3. **Symlink confinement.** A symlink inside the root whose resolved target is
   outside the root raises `OrientationError`.
4. **Positive Git-subject control.** A bounded temporary Git repository whose
   snapshot subject equals its actual `HEAD` and tree remains eligible for
   `CURRENT`, preventing an implementation that merely fails every live CLI
   call.
5. **Unavailable/wrong root control.** Live execution against a root for which
   the required Git subject cannot be established must fail closed and never
   produce `CURRENT`.

The RED claim is limited to the first missing behavior. Passing confinement
controls characterize existing behavior and close the review coverage gap; they
are not called pre-existing defects.

## Smallest implementation

After the focused RED is retained:

1. Add a small read-only Git observer in `tasks/gnostoa_orientation.py` using
   `subprocess.run` with an argument vector, no shell, captured text, explicit
   `-C <resolved-root>`, deterministic locale and a short timeout.
2. Require `git rev-parse --show-toplevel` to resolve to exactly the explicit
   repository root. Do not silently accept an ancestor repository.
3. Resolve `HEAD^{commit}` and `HEAD^{tree}` and validate them using the existing
   D14-O1 internal Git-ID contract.
4. Keep `build_manifest` deterministic for already-bound inputs by accepting an
   optional explicit local Git-subject observation. The live CLI obtains that
   observation and supplies it; pure/replay callers may supply an already-bound
   observation without ambient Git I/O.
5. Expose the observed local Git subject in the machine manifest evaluation
   evidence. Compare commit and tree with the declared snapshot subject. A
   mismatch adds stable diagnostics and `STALE`; unavailable live subject fails
   closed.
6. Do not infer a replacement current item or next action. This slice invalidates
   false currentness only.

## Container-first verification

Primary evidence comes from the project's pinned OCI execution path and exact
candidate. Required final checks are:

- focused `tests/test_gnostoa_orientation.py`;
- formatting/lint/type checks applicable to changed Python files;
- knowledge/bundle and policy validation for Decision/plan/index changes;
- fast/regression and smoke suites required by the repository workflow;
- exact-head provider CI, distinguishing PASS from intentional SKIP;
- public-surface digest comparison against the admitted base, demonstrating no
  change caused by the self-only script/tests/knowledge record except any
  separately measured knowledge effect already governed by the existing digest
  contract;
- one direct live invocation against the retained stale D14-O1 snapshot showing
  it is no longer `CURRENT`.

Native execution may be retained as equivalence/recovery evidence but cannot be
the sole release/acceptance evidence.

## Security and negative coverage

Focused tests must retain or add coverage for:

- path traversal and symlink escape;
- Git root mismatch / non-repository root;
- Git command failure and timeout;
- malformed or unexpected Git object identifiers;
- declared commit mismatch;
- declared tree mismatch;
- no shell interpolation from repository paths;
- existing oversized local-source and unreadable-source behavior;
- existing duplicate JSON keys, invalid timestamps, conflicts and budget
  behavior.

No network access, provider credentials or provider body parsing is introduced.

## Stop / hold conditions

Stop and return to owner review instead of widening the slice if:

- implementing the guard requires changing `PUBLIC_SURFACE_PATHS`, public
  schemas, package entry points or the supported `knowledge` command;
- the existing `tasks/` implementation cannot consume the Git observation
  without introducing a general collector abstraction;
- container verification requires a new runtime dependency not already locked
  by Decision 0005;
- the real stale-snapshot discriminator cannot be made deterministic without
  provider state;
- a semantic next-action decision is required to satisfy a test.

O2-B/C/D remain held regardless of O2-A0 success.

## Completion boundary

O2-A0 is review-ready only when the exact candidate demonstrates all of the
following:

- the retained pre-merge D14-O1 snapshot cannot be `CURRENT` when evaluated
  live against a different local Git commit or tree;
- a matching bound Git subject can still be `CURRENT` when all other D14-O1
  conditions are satisfied;
- Git observation failure is fail-closed;
- traversal and symlink escape are directly regression-tested;
- no provider or public-surface capability was added;
- container-first required verification passes on the exact candidate;
- the PR and Issue record identify remaining limits truthfully.

Owner semantic disposition and merge authorization remain separate final gates.
