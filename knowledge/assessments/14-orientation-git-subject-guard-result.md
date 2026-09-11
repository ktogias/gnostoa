---
type: Source
title: D14-O2 O2-A0 local Git subject guard result
description: Verification-first result for the bounded self-only Git subject invalidation and local source-confinement slice.
status: draft
generated:
  by: agent:chatgpt
  at: "2026-09-11T17:06:30Z"
sources:
  - id: work-item
    resource: https://github.com/ktogias/gnostoa/issues/14
    title: Add reproducible goal-alignment and delivery-state projections
  - id: pull-request
    resource: https://github.com/ktogias/gnostoa/pull/239
    title: Invalidate stale self-orientation on local Git subject drift
  - id: decision
    resource: ../decisions/0066-invalidate-self-orientation-on-local-git-subject-drift.md
    title: Decision 0066
  - id: plan
    resource: 14-orientation-git-subject-guard-plan.md
    title: D14-O2 O2-A0 local Git subject guard execution plan
x-project-knowledge:
  id: kit.assessment.14-orientation-git-subject-guard-result
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governed-by
      target: /decisions/0066-invalidate-self-orientation-on-local-git-subject-drift.md
    - kind: verifies
      target: /requirements/verification-precedes-implementation.md
---

# D14-O2 O2-A0 local Git subject guard result

## Result

O2-A0 adds one bounded live Git-subject discriminator to the existing self-only
orientation prototype. The pure manifest evaluator remains deterministic over
explicit inputs; the CLI path now observes the exact explicit repository root,
reads its current commit and tree without mutation, and supplies that observation
to evaluation. A retained projection whose bound `source_commit` or `source_tree`
differs from the observed repository subject is at least `STALE` and cannot be
reported as `CURRENT`.

The implementation remains inside `tasks/gnostoa_orientation.py`. It introduces
no provider collector, public orientation package, public schema, supported
orientation command, provider write-back, generic workflow engine or automatic
snapshot refresh. The broad Issue #14 work remains open and uncompleted.

The admitted base was
`a0b7c8a170942fce61ff3c08b350bc3d7ab0a2a0`. The exact implementation candidate
verified before this result record was
`507f55b6246b390420327ad3bc1e67aaf38fd882`, tree
`07ef18217759a054fcc460be89b193c785c7ac6d`.

## Implemented boundary

The live repository observation is intentionally narrow:

- Git is invoked with an argv list, never a shell.
- `GIT_OPTIONAL_LOCKS=0`, `LC_ALL=C` and `LANG=C` keep the read-only observation
  bounded and locale-stable.
- each Git call has a five-second timeout and converts command/timeout failures
  into a bounded `OrientationError` rather than guessing;
- `git rev-parse --show-toplevel` must resolve to the exact explicit repository
  root, so a nested subdirectory cannot silently redefine the subject;
- only `HEAD` and `HEAD^{tree}` are observed;
- the existing D14-O1 internal identity contract still requires 40 lowercase
  hexadecimal Git IDs;
- container UID differences are handled only with invocation-local
  `-c safe.directory=<exact explicit root>`; no global Git configuration and no
  `safe.directory=*` wildcard are introduced.

The evaluator records the supplied repository observation in
`evaluation.repository_subject`. Commit and tree mismatches receive distinct
`repository-subject-mismatch:*` diagnostics. Existing stronger fail-closed states
remain stronger than `STALE`; the new check does not turn incomplete or
conflicting evidence into a weaker status.

Local-source confinement is also regression-tested: lexical traversal outside the
explicit root and an in-root symlink whose resolved target leaves the root are
both refused.

## Verification-first evidence

The test-only RED candidate was
`83bdc1805ceca32afb289713a642379a4d1394cc`. Gnostoa verification run
`34620303945` failed before production implementation. Python 3.11 and 3.12 both
failed in the source compatibility suite, and `fast` failed in verification;
`policy` passed. The new behavior discriminator demonstrated the missing
mechanic: the pre-change live path could still return `CURRENT` after the bound
repository subject had drifted. The path-traversal and symlink-confinement
controls did not require a production relaxation.

That RED evidence is retained as evidence of the intended missing behavior rather
than rewritten as an implementation failure. CodeQL on the same test-only head
completed successfully.

## Negative evidence and integration corrections

Three later failures materially shaped the bounded implementation and are retained
rather than collapsed into the final GREEN result.

1. **Bind-mounted checkout ownership.** A candidate OCI run failed Git's dubious-
   ownership check because the read-only `/workspace` checkout belonged to the
   host runner while the Gnostoa image runs as non-root `kit`. The correction is
   invocation-local trust for the one exact explicit root. The regression suite
   asserts that the Git argv contains that exact `safe.directory` value, uses no
   shell and contains no wildcard trust.
2. **Tool root versus inspected repository root.** A regression fixture initially
   treated installed source under `/opt/gnostoa` as the repository being
   inspected. In the container-first route those are different objects: the tool
   is installed at `/opt/gnostoa`, while the real checkout is the bind-mounted
   `/workspace`. The test was corrected to inspect the actual checkout; production
   behavior was not relaxed to manufacture Git state for a packaged source tree.
3. **Retained self snapshot is not part of the packaged runtime.** Exact-head run
   `34623521823` reached a GREEN regression but downstream `smoke` failed in job
   `103344936832` because the real stale-snapshot discriminator expected
   `tasks/issue-14-orientation.json` inside the clean installed runtime. The
   distribution intentionally omits that retained self-only JSON. The final test
   therefore skips this single real-snapshot discriminator only when the packaged
   `.gnostoa-source-files` marker is present and the retained JSON is absent. In a
   source checkout, an absent retained JSON remains a hard test failure. The live
   CLI behavior itself was not weakened.

These failures support the separation between deterministic evaluator inputs,
live repository observation, installed tool bytes and retained self-governance
state. None justified a provider adapter or broader runtime subsystem.

## Exact implementation-candidate verification

On implementation head `507f55b6246b390420327ad3bc1e67aaf38fd882`, Gnostoa
verification run `34624971576` completed successfully:

- `python-compatibility (3.12)`: PASS, including Ruff, typing, golden digest,
  source compatibility and clean installed-artifact smoke;
- `python-compatibility (3.11)`: PASS; the workflow's 3.12-only Ruff/typing and
  installed-artifact steps remained explicitly skipped;
- `policy`: PASS;
- `fast`: PASS;
- `regression`: PASS;
- `smoke`: PASS;
- `extended`: SKIPPED by the workflow, not reported as PASS.

The downstream smoke self-check ran 696 tests and completed `OK (skipped=3)`.
One of those explicit skips is the real retained-snapshot discriminator in the
packaged runtime, where the retained JSON is unavailable by design. The same
real-snapshot discriminator executes in the source-checkout regression route.
The other declared skips are pre-existing environment/capability skips; they are
not rewritten as passes.

The smoke also bound the exact candidate commit and tree, confirmed runtime CLI
and OCI label version `0.2.0`, and reported `runtime.self_check=PASS`.

CodeQL run `34624966419` passed for the same implementation head with no new
alerts. Its generated Python coverage note is informational and is not treated as
a failure or as broader proof of semantic correctness.

## Public-surface and scope reconciliation

The changed paths at the verified implementation head were limited to:

- `knowledge/assessments/14-orientation-git-subject-guard-plan.md`
- `knowledge/decisions/0066-invalidate-self-orientation-on-local-git-subject-drift.md`
- `knowledge/index.md`
- `tasks/gnostoa_orientation.py`
- `tests/test_gnostoa_orientation.py`
- `tests/test_gnostoa_orientation_git_guard.py`

No changed path intersects the declared public inheritance surface. Smoke computed
the same public-surface digest for source, candidate runtime and vendored source:
`sha256:ef84573c5be406f0ec69d29b0581556bada46a6eaaaace47f89f07e4a1b37ed8`.
The public SB2 membership remains 14 and the corresponding source/runtime/vendored
file hashes agree.

This result therefore supports only the self-only A0 claim. It does not establish
provider authenticity, provider collection, automatic generation/refresh,
semantic next-action selection, cross-project projection contracts, adopter
utility, token savings, or completion of D14-O2 / Issue #14.

## Disposition boundary

The mechanically verified implementation is ready for owner semantic review of
O2-A0 within Decision 0066's boundaries. Decision 0066 remains draft and PR #239
remains a draft until owner disposition. This record does not authorize merge.
A negative owner disposition is valid and must not be rescued by widening the
slice.

This result record and its index route are evidence-only changes after the exact
implementation-candidate verification above. Because they change the PR head, the
final review candidate must receive one additional exact-head provider
verification and CodeQL run. That provider evidence should be read from PR #239;
it should not be back-written into this record in a loop that would create yet
another unverified head.
