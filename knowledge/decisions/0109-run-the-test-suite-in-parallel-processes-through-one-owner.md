---
type: Decision
title: Run the test suite in parallel processes through one owner
description: Every run of the repository's test suite (ci/verify fast, knowledge self-check and the coverage run of extended) goes through tools/test_suite.py, which runs it with unittest-parallel, one test module per task across one process per CPU. The same 1,670 tests, about 3.5 times faster. unittest-parallel and the coverage package it imports join the runtime and development locks.
status: draft
generated:
  by: anthropic/claude-opus-5-5
  at: "2026-10-07T20:30:00Z"
sources:
  - id: work-item
    resource: https://github.com/ktogias/gnostoa/issues/370
    title: Run the test suite in parallel processes (verification time, proposal B)
  - id: checkpoint
    resource: https://github.com/ktogias/gnostoa/issues/370#issuecomment-6045886329
    title: The owner's priority of 2026-10-07, the prior-art measurements and the lineage
  - id: preparation-authority
    resource: ./0090-require-pre-candidate-preparation-receipts-for-non-hook-authoring.md
    title: ci/verify, pyproject.toml and the locks as preparation-authority surfaces
  - id: lock-precedent
    resource: ./0095-refresh-vulnerable-development-dependency-pins.md
    title: How a lock pin is admitted, its wheel hash checked against the downloaded file
  - id: runner
    resource: https://pypi.org/project/unittest-parallel/1.8.6/
    title: unittest-parallel 1.8.6, MIT
x-project-knowledge:
  id: kit.decision.0109.run-the-test-suite-in-parallel-processes-through-one-owner
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: references
      target: /decisions/0090-require-pre-candidate-preparation-receipts-for-non-hook-authoring.md
    - kind: references
      target: /decisions/0095-refresh-vulnerable-development-dependency-pins.md
---

# Run the test suite in parallel processes through one owner

## Context

A review round ran the same test suite many times on one tree, each run one serial
process:
- `ci/verify fast`;
- preparation's focused run of it;
- `knowledge self-check`, both in the development container and in the runtime image;
- the coverage run of `extended`;
- provider CI.

Measured on `main` at `990b491` (development image, Python 3.12.14, 8 cores), the
1,670 tests took 243 s in one process. The owner admitted proposal B of the
verification-time analysis on 2026-10-05 and, on 2026-10-07, asked for it before
everything else, to stop carrying slow runs through the rest of the work.

## Decision

1. **One owner.** `tools/test_suite.py` is the one place that says how the suite
   runs. `command(python, tests, coverage_source=None)` returns the command, and
   `run(root)` runs it with the current interpreter.
2. **The runner.** `unittest-parallel` 1.8.6 runs every test module under `tests`
   as a task of its own (`--level module`), across one process per CPU, which is
   its default. The tests and the `unittest` runner are the same as before.
3. **Its users:**
   - `ci/verify fast` runs `python -m tools.test_suite`. Preparation's focused run,
     the git hooks and provider CI call `ci/verify`, so they run in parallel too;
   - `knowledge self-check` calls `test_suite.run(root)`, in the development
     container and in the runtime image alike;
   - `extended` measures coverage through
     `test_suite.command(python, coverage_source="tools")`: branch coverage of
     `tools`, measured in each process and combined. That is the measurement
     `coverage run --branch --source=tools` made in one process. `coverage report`
     with the floor, and `coverage json`, read the combined data as before.
4. **The dependency.**
   - `unittest-parallel>=1.8.6,<2` joins `pyproject.toml`'s dependencies, since
     `knowledge self-check` runs the suite.
   - It is pinned in both locks, `unittest-parallel==1.8.6`. Its one wheel's SHA-256,
     `7f04b0ad…`, was checked against the downloaded file, as Decision 0095 requires.
   - `unittest-parallel` imports `coverage` unconditionally, so `coverage==7.15.2`,
     already in the development lock with its reviewed hashes, joins the runtime lock
     too.

## Evidence

- **Prior art** (#370's checkpoint):
  - `unittest-parallel` took 69 s at module level and 72 s at class level, with
    1,670 OK.
  - `pytest-xdist` took 77 s, and needs pytest plus five more packages. Without
    `--ignore=tests/fixtures`, it also collects fixture repositories that
    `unittest discover` does not.
  - `stestr` brings 20 transitive packages.
- **Isolation:** consecutive parallel runs at module and at class level each
  came out 1,670 OK, with no order-dependent failure. The counts are recorded on
  #370.
- **The candidate:** `ci/verify fast` and `python -m tools.test_suite` ran
  1,675 tests (the 1,670 and this change's 5) and all passed.

## Consequences

- Every suite run takes about a third of its former time, so each review round and
  each provider CI run is shorter.
- The longest module, `test_adoption_check` at about 45 s, now bounds the wall time.
  Reducing that hot spot is #370's remaining acceptance criterion, and is not part of
  this change.
- The runtime image holds two more distributions, `unittest-parallel` and
  `coverage`. `ci/verify release` checks the pinned v0.2.0 release image, so its
  distribution count changes only at the next release.
- A test that shares state between modules (a working directory, the environment, a
  fixed path or port) would now fail intermittently. None was observed. One that
  appears is fixed or isolated, never serialized again.

## Alternatives not chosen

- **`pytest-xdist`:** a different runner and collection, and six more packages, for
  no gain in speed.
- **`stestr`:** its dependency surface.
- **A runner written here:** the prior-art checkpoint adopts a maintained one unless
  the record shows why not, and nothing here does.
- **Parallel only in CI:** the local runs, preparation and the runtime image would
  stay slow.

## Delivery

This is authority evolution: `ci/verify`, `pyproject.toml` and the locks are
preparation-authority surfaces under Decision 0090. A candidate that changes them
cannot be prepared through `ci/prepare-candidate`, so this one is verified directly
in the development container and the runtime image built from its own locks. The
owner admitted the change on 2026-10-05 and gave it priority on 2026-10-07.
