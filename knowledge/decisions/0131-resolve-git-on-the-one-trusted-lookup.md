---
type: Decision
title: Resolve git on the one trusted lookup, the leaf the repository's tools share
description: "B1 of #389's cleanup, security first: tools/trusted_path.py owns AGENTS.md's trusted executable lookup; tools/exact_tree.py consumes it; tools/quality_evidence.py's _git_state starts git through it. Decision 0130's BAN-B607 Limit is corrected in extent and in owner. Orientation, repository_scope, candidate_prepare, adoption_check, release_smoke and the capsule pair follow by their own changes."
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
  - id: route-b
    resource: https://github.com/ktogias/gnostoa/issues/389#issuecomment-6652443128
    title: "The owner's route (B): orientation leaves B1, with its child environment"
  - id: sweep
    resource: https://github.com/ktogias/gnostoa/pull/483#issuecomment-6654044967
    title: "Claude's part 2 on #483: the helpers' git starts the count left out"
  - id: shell
    resource: https://github.com/ktogias/gnostoa/pull/483#issuecomment-6654660431
    title: "Claude's part 2 on #483: the ci/ shell scripts' git starts, outside the Python sweep"
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
through `tools/exact_tree.py`; the measured extent in non-test Python is 17 starts in 6 files, and that owner fails
#451's import constraint, which keeps `tools/exact_tree.py` out of
`tools/quality_evidence.py`'s import (source `leaf`).

## Decision

1. **`tools/trusted_path.py` owns the lookup:** `TRUSTED_PATH` and
   `trusted_executable(name)`, which returns the absolute path of a bare name on it or
   raises `FileNotFoundError`. A name with a directory part is refused, never checked as
   a path. Each caller's own `OSError` handling applies: `tools/exact_tree.py` refuses it
   as `git-failed`, and `_git_state` keeps its existing unbound state. It imports only the
   standard library.
2. **`tools/exact_tree.py` consumes it** and keeps its own error mapping.
3. **`_git_state` starts the trusted git** for both of its reads.
4. **Decision 0130's `BAN-B607` Limit, corrected** (sources `route-i`, `sweep`). On `main`, the
   non-test Python git starts that resolve on the caller's `PATH` are 17 in 6 files, not two.
   They were found by an AST sweep of every non-test `*.py` file, not by a linter, which
   reads each call whose argv begins with the literal `git` and each `shutil.which("git")`.
   It does not read shell scripts, the Python embedded in them, or workflow steps
   (source `shell`):
   - the four `S607` literals, which lose their gating reader at the exit: `_git_state` ×2,
     `repository_scope`'s `_git_result`, and orientation's `_git_output`, whose child
     environment is built from `os.environ`;
   - 13 starts that no `S607` rule reads, because each goes through `shutil.which` or a
     helper: `candidate_prepare`'s `shutil.which("git")`, `adoption_check`'s `_git` and
     `release_smoke`'s 11 `_run` starts.
   - Confined, so not among them: the capsule pair (their own `env` `PATH`),
     `review_protected`'s `shutil.which("git", path=os.defpath)`, and
     `ci/merge_admission_guard.py`'s own statement of the lookup.
   - Their owner is this leaf, not `tools/exact_tree.py`. This change closes two:
     `_git_state` ×2.

## Limits

- **Deferred, each to its own change** (sources `narrowing`, `route-b`):
  - `tasks/gnostoa_orientation.py`'s `_git_output`, a self-only task that imports no
    `tools/` module: changing its start brings the call into Codacy's read, whose Semgrep
    rules also name its `os.environ`-based child environment. Its executable and its
    environment are fixed together;
  - `tools/repository_scope.py`, with the 77 inherited SLF001 findings of
    `tests/test_quality_evidence.py`, which its test would bring into the protected-access
    family's read;
  - `tools/candidate_prepare.py`'s `_GIT`: it is preparation authority, which the
    exact-parent preparation refuses as a candidate change, so its evolution needs its own
    admitted path (`AGENTS.md`);
  - `tools/release_smoke.py`'s `_run` git starts and `tools/adoption_check.py`'s `_git`,
    which `verification.yml`'s installed-artifact adoption smoke runs (source `sweep`);
  - the capsule pair, which already confines its lookup through its own `env` `PATH` (B4);
  - the shell scripts outside the sweep that start git with the caller's `PATH`:
    `ci/style`, `ci/build-runtime` and `ci/x3_conformance`, as the review found
    (source `shell`). `ci/prepare-candidate` sets its own `PATH`.
- **Until those land,** local collector runs use the trusted `PATH` (the owner's direction).
- **The protected `ci/merge_admission_guard.py`** keeps its own statement of the lookup.

## Verification

- **RED first.** On `main`, the leaf's tests failed for the missing behaviour: each site
  started the bare `git`, and the leaf was absent.
- **Mutants.** Each mutation of the leaf and its consumers is killed by a named test,
  against a passing baseline.
- **The active families** list no finding in the changed files.

## Consequences

- Non-test `S607` sites fall from six (the four literals above and the capsule pair) to
  four: the capsule pair, `tools/repository_scope.py` and orientation's `_git_output`.
- Non-test Python git starts on the caller's `PATH` fall from 17 in 6 files to 15 in 5.
- **Rollback:** reverting this change restores the bare `git` starts; nothing else depends
  on the leaf.
