---
type: Decision
title: Run the regression and smoke suites beside extended, behind the same regression gate
description: Split the verification workflow's regression job into a regression-suite job that runs the suite and a regression gate that asserts every prerequisite, and let smoke wait only for policy, so the regression and smoke suites run beside extended instead of after it. The required checks keep their names and meaning.
status: draft
generated:
  by: anthropic/claude-opus-5-5
  at: "2026-10-05T15:20:00Z"
sources:
  - id: work-item
    resource: https://github.com/ktogias/gnostoa/issues/371
    title: Shorten provider CI, C1 (owner-admitted 2026-10-05)
  - id: admission
    resource: https://github.com/ktogias/gnostoa/issues/15#issuecomment-5997005569
    title: Owner admission of #370 and #371, with the measured verification-time analysis
  - id: lineage
    resource: https://github.com/ktogias/gnostoa/issues/371#issuecomment-5997175269
    title: C1 prior-art checkpoint, required-check read-back and lineage table
  - id: gate-0043
    resource: ./0043-prepare-a-bounded-v0-1-2-b3-readiness-candidate.md
    title: The regression always() route that fails unless its prerequisites succeeded
  - id: gate-0082
    resource: ./0082-eliminate-host-persistence-for-protected-review-payloads-and-route-security-gates.md
    title: The routed security gates, the extended RUN/NOT_APPLICABLE pair and the exact workflow inventory
x-project-knowledge:
  id: kit.decision.0103.run-the-regression-and-smoke-suites-beside-extended-behind-the-regression-gate
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governed-by
      target: /decisions/0043-prepare-a-bounded-v0-1-2-b3-readiness-candidate.md
    - kind: references
      target: /decisions/0082-eliminate-host-persistence-for-protected-review-payloads-and-route-security-gates.md
---

# Run the regression and smoke suites beside extended, behind the same regression gate

## Context

On `044c549` (#369, 2026-10-05) the "Gnostoa verification" workflow took 13.7
minutes of wall time. `fast` and both `python-compatibility` jobs finished by +163 s.
The rest was a serial chain:

| Job | Duration |
|---|---|
| `policy` | 58 s |
| `extended` | 372 s |
| `regression` | 162 s |
| `smoke` | 218 s |

`regression` is the aggregate gate. Decision 0043 routes it through `always()` so
that it "explicitly fail[s] unless" its prerequisites succeeded. Decision 0082 adds
the security gate and the exact `extended` RUN/success or NOT_APPLICABLE/skipped
pair. Because the gate and the regression suite are one job, the suite waits for
`extended`. `smoke` then waits for `regression`. No rationale is recorded for either
wait (source `lineage`). The chain came from the adopter template.

The required checks of protected `main`, read back on #369's head `d0a7268`, are
`policy`, `fast`, `regression` and `smoke`.

## Prior-art and reuse disposition

| Need | Existing | Disposition |
|---|---|---|
| A gate that fails unless every prerequisite succeeded | `regression`'s "Assert successful prerequisites" step | **extended**: it also asserts `regression-suite` and `smoke` |
| The regression suite | `regression`'s checkout, runtime build and `./ci/verify regression` | **adapted**: moved unchanged into `regression-suite` |
| Smoke | the `smoke` job | **consumed**: steps byte-identical |
| Parallel jobs | GitHub Actions `needs` and `if: always()` | **consumed** |
| A job that runs only the regression suite | none | **new residual**: `regression-suite` |

## Decision

1. **`regression-suite` runs the regression suite.** It has exactly the steps that
   `regression` ran after its assertion: the merge-candidate checkout, the runtime
   build and `./ci/verify regression`. Like `extended`, it needs only `policy`, so
   the contract's "the provider adapter runs the separate `policy` suite before
   dependent project suites" still holds for it.
2. **`smoke` needs only `policy`**, not `regression`. Its steps are unchanged.
3. **`regression` is the aggregate gate and nothing else.**
   - It keeps its name, `runs-on` and `if: always()`.
   - It needs the six prerequisites it has today, plus `regression-suite` and
     `smoke`.
   - Its one step asserts each result exactly as today, plus
     `regression-suite = success` and `smoke = success`.
   - It checks out and builds nothing.

   A green `regression` still means that every suite of this workflow passed, now
   including `smoke`.
4. **The required checks are unchanged:** `policy`, `fast`, `regression` and `smoke`.
   - A `policy` failure skips `regression-suite` and `smoke`. The gate then fails,
     exactly as `smoke` is skipped today when `regression` fails.
5. **This amends Decision 0082's "exact eight-job required workflow inventory"**
   with a nine-job inventory, and the binding of the regression suite to the job
   named `regression` with a binding to `regression-suite`. Every other structural
   contract of Decision 0082 stands: the root keys, events, permissions,
   concurrency, image environment, display names, ordered step digests, strategy,
   outputs and exact dependency lists.

## Verification

- **Before the workflow changes**, the workflow-contract tests in
  `tests/test_tools.py` and `tests/test_security_gates.py` are changed first, as RED:
  - the inventory, keys, names and dependencies;
  - the step digests of `regression-suite` and of the gate, computed from this
    specification over today's `regression` steps (`smoke`'s digest is unchanged);
  - the suite-to-job binding;
  - the gate's environment and assertions.
- **An executable test** runs the gate's script and shows it exits non-zero when any
  result is `failure`, `cancelled` or `skipped`, or when `extended`'s pair is
  inconsistent. It exits zero only for the accepted combinations.
- **After the change**, the same tests pass. Provider CI on the candidate shows:
  - the four required checks;
  - `regression-suite` and `smoke` starting as soon as `policy` finishes;
  - the critical path, measured against 13.7 minutes.

## Consequences

- The expected critical path is the longest of `policy` + `extended`, `policy` +
  the regression suite, and `policy` + `smoke`, plus the gate: about 7.3 minutes.
- A candidate that fails `extended` still spends the regression suite and smoke,
  about 6 runner-minutes, because they no longer wait for `extended`.
- The gate goes red only after `smoke` finishes, so the failure arrives later.
- `fast` already ran beside `policy` before this Decision. That is unchanged.
