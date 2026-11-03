---
type: Decision
title: Give the tests one import model, and repair their typing and private access
description: "N1b of #389's closure, Option B: what test files share moves out of discovered test modules into non-discovered support modules, every sibling import is tests.-qualified, the tests' typing diagnostics and SLF001 private-access findings on the touched files are repaired, one moved helper is bounded below the complexity threshold, and the pull-request lane type-checks the declared strict scope (#221)."
status: draft
generated:
  by: anthropic/claude-opus-5-5
  at: "2026-11-02T20:40:00Z"
sources:
  - id: work-item
    resource: https://github.com/ktogias/gnostoa/issues/389
    title: Keep merges possible while a vendor analyzer is unavailable
  - id: owner-admission
    resource: https://github.com/ktogias/gnostoa/issues/389#issuecomment-6587559616
    title: "The owner's decision: Strategy A, N1b Option B as one cohesive PR, Docker first"
  - id: phase0
    resource: https://github.com/ktogias/gnostoa/issues/389#issuecomment-6587182168
    title: "N1b Phase 0: the measured remedy and the proposed integrated admission"
  - id: pao-remedy
    resource: https://github.com/ktogias/gnostoa/issues/389#issuecomment-6573078018
    title: "PAO: the import-model answers, and non-discovered support modules"
  - id: ci-gap
    resource: https://github.com/ktogias/gnostoa/issues/221
    title: Make the declared strict-mypy scope effective on every pull request
  - id: profile
    resource: ./0117-select-the-diagnostic-inventory-s-families-through-a-protected-profile.md
    title: The protected profile, unchanged
  - id: typing-rules
    resource: ./0123-repair-the-typing-of-seventeen-test-modules.md
    title: N1a's typing rules, reused
  - id: digest-admission
    resource: https://github.com/ktogias/gnostoa/issues/389#issuecomment-6591116903
    title: "The owner's admission of the python-compatibility job's protected digest line in tests/test_tools.py"
  - id: characterization
    resource: https://github.com/ktogias/gnostoa/issues/389#issuecomment-6589390794
    title: "The shell-sequence helper's characterization, measured before its extraction"
x-project-knowledge:
  id: kit.decision.0128.give-the-tests-one-import-model-and-repair-their-typing-and-private-access
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: references
      target: /decisions/0117-select-the-diagnostic-inventory-s-families-through-a-protected-profile.md
    - kind: references
      target: /decisions/0123-repair-the-typing-of-seventeen-test-modules.md
---

# Give the tests one import model, and repair their typing and private access

## Context

On `main` `7cb731af`, test files import from one another in two ways. A bare import works because
the runner puts `tests/` first on the path. A `tests.`-qualified import works from the repository
root. 25 files try one and fall back to the other. Phase 0 measured the consequences (source
`phase0`):

- 7 files are loaded under two module names in one process. PAO named this a correctness risk for
  patching, `isinstance` and module state (source `pao-remedy`).
- The exit test's full-scope mypy cannot resolve 44 imports in 41 files.

A scratch remedy kept the suite's 3,238 collected tests identical and its outcome unchanged,
removed every double load, and resolved 42 of the 44 imports. Changing those files makes the
DIFF read them whole. That surfaces their SLF001 findings (520), their typing diagnostics (174)
and one helper's complexity (26), and M17 denies each one. The owner chose Option B: one cohesive
PR that repairs them (source `owner-admission`). Separately, the pull-request lane type-checks
only part of the declared strict scope (source `ci-gap`).

## Decision

1. **One import model.** Every import of a sibling test file is `tests.`-qualified. The 25
   fallback blocks collapse to their `tests.` form.
2. **Shared code lives in non-discovered support modules.** What other test files import from a
   `test_*` module moves verbatim into a flat `tests/<name>_support.py`, together with the
   same-module definitions it needs. This follows the existing `tests/quality_evidence_fixtures.py`
   pattern. The test module imports back what it still uses.
   - The test modules that load a sibling file by path load its support file instead, keeping
     their fresh-copy-per-call behaviour.
   - The containment contract registers `tests` from its exact path, as it already does `tools`,
     so it stays isolated without a bare-import exception.
3. **The touched files' typing diagnostics are repaired** under N1a's rules: no `cast`,
   `type: ignore`, weakened assertion, renamed or removed test, or skip (source `typing-rules`).
4. **The touched files' SLF001 findings are cleared, by kind** (counts measured on the remedy):
   - 189 reach private helpers of the moved L1 fixtures. Those helpers are now the
     support module's shared API, so they get public names.
   - 101 reach privates of a statically imported `tools` module.
     - 63 become an explicit import of the private name, which keeps its type.
     - The other 38 are in files that also patch that same name. An import would bind the
       original once and bypass the patch, so they go through `_original`, as the
       run-time-loaded ones do.
   - 227 reach privates of a module or object loaded at run time (by path, or per test).
     Each goes through the existing `_original(obj, "name")` idiom, which reaches the original
     without naming a private attribute.
   - 3 call a test class's private method from another class. That method becomes a
     module-level function.

   These repairs do not stop the tests from exercising private helpers; they make each reliance
   explicit in a form the family does not flag. Rewriting the tests onto public interfaces would
   change what they verify, and is not part of this decision.
5. **Two functions come to 15 or below by extraction.**
   - The moved helper `_has_direct_top_level_shell_sequence`, at 26. It is characterized first,
     as the complexity slices were (source `characterization`).
   - `test_materially_different_native_translator_reuses_core_unchanged`, at 16 on `main`, gets
     lines from the repairs above. Its nested translator reads only `reducer` from the test, and
     moves unchanged to module level.
6. **The pull-request lane type-checks the declared strict scope.** Its mypy step runs the
   configured `[tool.mypy]` scope (`tools`, `ci`) instead of a listed subset. A failing case comes
   first: an invalid change in an omitted path that the current step passes. The job's
   protected step digest in `tests/test_tools.py` changes with it, admitted for that one line
   (source `digest-admission`); the workflow-structure contract keeps pinning the job.
7. **This record is listed in `knowledge/index.md`.**
8. **Nothing else changes:** no file under `tools/` or `ci/`, the profile or the threshold, and
   in `tests/test_tools.py` only that digest line.

## Verification

- **Collection:** the runner collects `main`'s tests, by module and id, plus the 2 this PR adds: the
  #221 contract test and the shell-helper characterization. No file is loaded under two module names,
  and the suite's outcome is otherwise unchanged.
- **Typing:** the exit test's `import-not-found` falls to the 2 fixture repositories with their own
  source roots.
- **The collector's DIFF lists 0 findings on every file but `tests/test_tools.py`:** typing, SLF001
  and complexity included. Because of the admitted digest line, the collector reads that file
  whole and lists its own 12 typing diagnostics. #477's T1 repairs those 12, and they go when this
  PR rebases onto it.
- **#221:** an invalid change in an omitted path passes the current step and fails the new one.
  The new contract test fails on the current step and passes on the new one.
- **The full round passes,** with exact-parent receipts.

## Consequences

- **What it settles:** the double loading, the hybrid import model, 42 of 44 unresolved imports,
  the touched files' typing and SLF001 findings, and #221's enforcement gap.
- **What it leaves:** the full-scope typing findings in test files this PR does not touch, for the
  target profile's later activation (Strategy A).

## Corrections

This text amends the first published version (6,773 bytes, SHA-256
`1e30384ca74c0fe7e3c7cc40afbce1d4d2f93cae70aa89040d2def7044e43fc9`), made before the edit:

1. **Point 4's 101 static receivers:** that version made every one an explicit import. 38 sit in files
   that also patch the same name, where an import would bypass the patch. They go through
   `_original` instead.
2. **Point 5:** that version bounded one function. The repairs also add lines to a test that measures
   16 on `main`, so it is bounded too.
3. **#221's verification:** that version said the failing case fails under the current step. The
   invalid change passes it; the contract test is what fails on it.
4. **#221's digest:** that version left out `tests/test_tools.py`. Its `_PROTECTED_JOB_STEPS_SHA256`
   pins the python-compatibility job's steps, so the step change changes that job's digest. The owner
   admitted that one line (source `digest-admission`).
5. **The analyzers' readback on the published head:** the remedy's own lines held two shapes that
   SonarCloud and DeepSource flag:
   - **Inside `assertRaises`.** Point 4's `_original(module, "_name")(...)` put a second call there.
     In 35 blocks, the lookup now sits just above the `with`, where it returns the same object, so
     each block keeps `main`'s one invocation. One generator is created there as well; creating it
     runs none of its body.
   - **The typing narrowings.** 5 were written as composite `assert`s and are now
     `if … : self.fail(…)`. That narrows the same way, and also holds under `python -O`.

   Across 10 files, no lookup crosses a patch of the same name.
6. **The full readback on round 2's head:** DeepSource's full run listed four findings on the
   remedy's own lines. The same shapes are repaired wherever the remedy wrote them; moved code is left
   verbatim (PAO 6593155958):
   - **The narrowings.** 69 single narrowing `assert`s are `if … : self.fail(…)`, as in
     correction 5.
   - **`next()` without a default.** 6 take the first run with a default and fail if
     there is none. One, inside `assertRaises(csv.Error)`, gets a default, so an empty stream fails the
     assertion instead of escaping it.
   - **The two typing-repair defs.** `_environment` declares the launcher it returns, and
     `_counting_reads`, which never reads `self`, is a static method.
7. **DeepSource's full run, typing:** its `TYP` findings on the touched files are repaired under
   N1a's rules (no cast, no `type: ignore`, no `Any` added to pass a check). They were reproduced
   locally with mypy's strict-def/call/generics flags, which match its count of missing
   annotations exactly. The means:
   - **A test double declares the interface it replaces,** and forwards what it read from `*args`
     or `**options` by name.
   - **A pass-through spy into the module under test,** which is untyped at runtime, takes and
     returns `object`, since `mock.patch` installs it as a side effect. A typed stdlib target is
     held as `Callable[..., T]`.
   - **JSON documents** are `dict[str, Any]`, as production declares them.
   - **A value a typed call now returns as Optional** is narrowed with `self.fail`. An existing
     `assertIsNotNone` stays.
   - **A test that monkeypatches** a module's or an object's attribute writes it through `vars()`.

   No assertion is removed, and SLF001 stays at 0. Calls into
   `tests/quality_evidence_fixtures.py`, which this PR does not change, stay untyped until that
   path is admitted.
