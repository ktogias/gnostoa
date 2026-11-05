---
type: Decision
title: Resolve git on the one trusted lookup, the leaf the repository's tools share
description: "B1 of #389's cleanup, security first: tools/trusted_path.py owns AGENTS.md's trusted executable lookup; tools/exact_tree.py consumes it; tools/quality_evidence.py's _git_state starts git through it; the self-only orientation task keeps a pinned copy tested equal to it. Decision 0130's BAN-B607 Limit is corrected in extent and in owner. repository_scope, candidate_prepare and the capsule pair follow by their own changes."
status: draft
generated:
  by: anthropic/claude-opus-5-5
  at: "2026-11-05T00:00:00Z"
sources:
  - id: work-item
    resource: https://github.com/ktogias/gnostoa/issues/389
    title: Keep merges possible while a vendor analyzer is unavailable
  - id: owner-sequence
    resource: https://github.com/ktogias/gnostoa/issues/389#issuecomment-6633186827
    title: "The owner's sequence: inventory before the exit, cleanup after it, security first"
  - id: owner-admission
    resource: https://github.com/ktogias/gnostoa/issues/389#issuecomment-6645242260
    title: "The owner's admission of B1, route (A′)"
  - id: audit
    resource: https://github.com/ktogias/gnostoa/issues/389#issuecomment-6637105203
    title: "The connected audit that reproduced the _git_state lookup locally"
  - id: route-i
    resource: https://github.com/ktogias/gnostoa/issues/389#issuecomment-6634283036
    title: "The cutover return's route (i): B1's Decision corrects Decision 0130's Limit"
  - id: leaf
    resource: https://github.com/ktogias/gnostoa/issues/389#issuecomment-6634192406
    title: "PAO's ruling: the leaf module, after option (a) failed #451's import constraint"
  - id: lineage
    resource: https://github.com/ktogias/gnostoa/issues/389#issuecomment-6634384923
    title: "B1's lineage, published before any edit"
  - id: narrowing
    resource: https://github.com/ktogias/gnostoa/issues/389#issuecomment-6645177503
    title: "The admission packet: route (A′), measured on main 683a9be7"
  - id: exit
    resource: ./0130-retire-deepsource-as-merge-evidence-and-give-every-class-the-project-inventory.md
    title: The DeepSource exit, whose BAN-B607 Limit this corrects
x-project-knowledge:
  id: kit.decision.0131.resolve-git-on-the-one-trusted-lookup
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: references
      target: /decisions/0130-retire-deepsource-as-merge-evidence-and-give-every-class-the-project-inventory.md
---

# Resolve git on the one trusted lookup, the leaf the repository's tools share

## Context

`AGENTS.md` names one trusted executable lookup, `/usr/local/bin:/usr/bin:/bin:/opt/homebrew/bin`.
`tools/exact_tree.py` and the protected `ci/merge_admission_guard.py` each stated it, and
`tools/quality_evidence.py`'s `_git_state` started a bare `git`, so the caller's `PATH`
chose the binary. A local run with a shim first on `PATH` returned the shim's revision
and state (source `audit`). Decision 0130's Limits named those two calls and a repair
through `tools/exact_tree.py`; the measured extent is five sites, and that owner fails
#451's import constraint, which keeps `tools/exact_tree.py` out of
`tools/quality_evidence.py`'s import (source `leaf`).

## Decision

1. **`tools/trusted_path.py` owns the lookup:** `TRUSTED_PATH` and
   `trusted_executable(name)`, which returns the absolute path of a bare name on it or
   raises `FileNotFoundError`. A name with a directory part is refused, never checked as
   a path. Each caller's own `OSError` handling applies: `tools/exact_tree.py` refuses it
   as `git-failed`, orientation as its `OrientationError`, and `_git_state` keeps its
   existing unbound state. It imports only the standard library.
2. **`tools/exact_tree.py` consumes it** and keeps its own error mapping.
3. **`_git_state` starts the trusted git** for both of its reads.
4. **The self-only `tasks/gnostoa_orientation.py` keeps a pinned copy,** since it imports
   no `tools/` module; a test pins the copy to the leaf's.
5. **Decision 0130's `BAN-B607` Limit, corrected** (source `route-i`): the partial-path
   lookups that lose a gating reader at the exit are five, not two: the four `S607`
   literals (`_git_state` ×2, `repository_scope`'s `_git_result`, orientation's
   `_git_output`) and `candidate_prepare`'s `shutil.which("git")`, which is no `S607`
   literal. The two capsule `S607` sites are not among them: their own `env` `PATH`
   already confines them. Their owner is this
   leaf, not `tools/exact_tree.py`. This change closes three: `_git_state` ×2 and
   orientation's `_git_output`.

## Limits

- **Deferred, each to its own change** (source `narrowing`):
  - `tools/repository_scope.py`, with the 77 inherited SLF001 findings of
    `tests/test_quality_evidence.py`, which its test would bring into the protected-access
    family's read;
  - `tools/candidate_prepare.py`'s `_GIT`: it is preparation authority, which the
    exact-parent preparation refuses as a candidate change, so its evolution needs its own
    admitted path (`AGENTS.md`);
  - the capsule pair, which already confines its lookup through its own `env` `PATH` (B4).
- **Until those land,** local collector runs use the trusted `PATH` (the owner's direction).
- **The protected `ci/merge_admission_guard.py`** keeps its own statement of the lookup.

## Verification

- **RED first.** On `main`, the leaf's tests failed for the missing behaviour: each site
  started the bare `git`, and the leaf and the pinned copy were absent.
- **Mutants.** Each mutation of the leaf, its consumers and the pinned copy is killed by
  a named test, against a passing baseline.
- **The active families** list no finding in the changed files; the git-guard test's
  inherited SLF001 and typing error are repaired in place.

## Consequences

- Non-test `S607` sites fall from six (the four literals above and the capsule pair) to
  three: the capsule pair and `tools/repository_scope.py`.
- **Rollback:** reverting this change restores the bare `git` starts; nothing else depends
  on the leaf.
