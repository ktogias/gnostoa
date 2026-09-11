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
- inherited `GIT_*` process variables are removed before invocation; the bounded
  subprocess environment then explicitly sets `GIT_OPTIONAL_LOCKS=0`, `LC_ALL=C`
  and `LANG=C` while retaining non-Git process environment such as `PATH`.
- each Git call has a five-second timeout and converts command/timeout failures
  into a bounded `OrientationError` rather than guessing;
- `git rev-parse --show-toplevel` must resolve to the exact explicit repository
  root, so a nested subdirectory cannot silently redefine the subject;
- `HEAD^{commit}` is resolved once and validated under the current internal
  40-hex contract, then the tree is derived from that exact observed commit via
  `<commit>^{tree}` rather than re-reading mutable `HEAD`;
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

## Independent-review repair

Two independent external reviewers examined review head
`d693d357773f10f96f71d5f3576e8f6ef163bd20` before owner disposition.
Greptile reported four findings: an unsupported `GIT_OPTIONAL_LOCKS=0` evidence
claim, inherited Git environment variables that could affect the intended
root/trust boundary, a commit/tree coherence race caused by resolving mutable
`HEAD` twice, and an unnecessarily brittle real-fixture assertion that required
both subject fields to differ. CodeRabbit independently confirmed the evidence
mismatch and recommended changes before acceptance.

The executor disposition adopted all four findings. The ambient Git-environment
and commit/tree-coherence findings were treated as merge-blocking for the O2-A0
claim; the evidence mismatch and fixture brittleness were retained as smaller but
real corrections in the same already-admitted slice. No O2-B/C/D, provider or
public-surface work was admitted by that disposition.

Verification-first evidence was established again before the repair. Test-only
review-repair head `4b186283837b205d54028963dd870185d65f2ea5` triggered Gnostoa
verification run `34635451811`; both Python 3.11 and 3.12 source-compatibility
lanes failed on the new review-derived discriminators. The failures showed that
the pre-repair subprocess environment lacked `GIT_OPTIONAL_LOCKS`, that the tree
lookup still used `HEAD^{tree}` rather than the already-observed commit, and that
a malformed observed commit was not rejected before a tree lookup. `policy`
passed and `extended` remained explicitly skipped.

The bounded repair therefore removes inherited `GIT_*` variables, explicitly sets
`GIT_OPTIONAL_LOCKS=0` and stable locale values, validates the one observed commit
before using it as a selector, derives the tree from that commit, and makes the
retained-snapshot regression require and diagnose whichever subject components
actually differ rather than requiring both. Final acceptance still requires
exact-head provider verification after these repository bytes stop changing.

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

The verification above is historical implementation-candidate evidence. The
independent-review repair changes later candidate bytes; its final provider and
CodeQL evidence must therefore be read from PR #239 after the repair head is
stable rather than inferred from these earlier successful runs.

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

The review repair changes only the same self-only implementation/test/evidence
paths; it does not add a public command, schema, package, adapter or provider
capability. Exact-head verification must reconfirm the public-surface invariant.

This result therefore supports only the self-only A0 claim. It does not establish
provider authenticity, provider collection, automatic generation/refresh,
semantic next-action selection, cross-project projection contracts, adopter
utility, token savings, or completion of D14-O2 / Issue #14.

## Disposition boundary

The independent reviews required bounded corrections before owner semantic
acceptance. The review-repair implementation is not accepted merely because the
changes are present: it must first receive exact-head Gnostoa verification and
CodeQL, after which the provider evidence and review closure can be assessed.
Decision 0066 remains draft, Issue #14 remains open, and this record does not
authorize merge.

This result record deliberately does not back-write the final post-repair run IDs.
Once the repository bytes are stable, exact-head provider evidence should be read
from PR #239 and retained in provider/governance comments rather than editing this
record again and creating another unverified head.
