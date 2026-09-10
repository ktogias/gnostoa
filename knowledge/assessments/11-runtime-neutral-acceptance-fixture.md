---
type: Source
title: Runtime-neutral acceptance fixture
description: Bounded D11-F1 behavior map, verification chronology and evidence limits for two scripted adapters and a common result consumer.
status: draft
generated:
  by: agent:codex
  at: "2026-09-10T11:40:58Z"
sources:
  - id: fixture-admission
    resource: https://github.com/ktogias/gnostoa/issues/11#issuecomment-5618072832
    title: D11-F1 bounded construction admission
x-project-knowledge:
  id: kit.assessment.11.runtime-neutral-acceptance-fixture
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governed-by
      target: /decisions/0060-run-a-bounded-runtime-neutral-acceptance-fixture.md
    - kind: references
      target: /requirements/bounded-behavioral-traceability.md
---

# Runtime-neutral acceptance fixture

## Subject and claim

D11-F1 is a normal, self-only experimental/test change under Decision 0060 and
Work Item #11. Base: `a1dfd461cfb90c403e5847e886a760f9943fcc54`, tree
`d316a168a150679eb5a0c61cf86457f6e0f08518`. The initial behavior map was published
before construction in the linked admission. The prospective map in that admission was NOT RUN. The results below were
recorded after execution; source and native evidence travel with this assessment.

The consumer is the fixture's persisted-result reader. It is not today's
ordinary delivery UI, a GitHub merge/closure gate or a protected deployment.
Workers and profile witnesses are scripted fixtures, not verified production
runtimes. No model or real provider operation is involved.

## Behavioral traceability

All rows derive from the owner-selected runtime-neutral proposal and D11-F1
admission. The cases are executor/reviewer-authored design controls, not
independent historical-incident identification. Intended implementation is the
fixture core plus the same reader under both adapter mappings; evidence is the
frozen test oracle's actual consumer observations.

| ID | Required outcome | Result | Alignment | Executor / reviewer |
|---|---|---|---|---|
| F01 | Unestablished capabilities prevent start; pending obligation | PASS, both adapters | ALIGNED in fixture | EXECUTED / core reviewed |
| F02 | Completion with both checks omitted stays pending without successor | PASS, both adapters | ALIGNED in fixture | EXECUTED / core reviewed |
| F03 | Complete fresh no-op can accept; #219 stays open with bug only | PASS, both adapters | ALIGNED in fixture | EXECUTED / core reviewed |
| F04 | Permitted supervisor compensation retains confirmed worker omission | PASS, both adapters | ALIGNED in fixture | EXECUTED / core reviewed |
| F05 | Planned supervisor checking is not worker omission | PASS, both adapters | ALIGNED in fixture | EXECUTED / core reviewed |
| F06 | Worker-requested trusted checking is not worker omission | PASS, both adapters | ALIGNED in fixture | EXECUTED / core reviewed |
| F07 | Incomplete invocation observation remains unknown | PASS, both adapters | ALIGNED in fixture | EXECUTED / core reviewed |
| F08 | Supervisor cannot discharge a separately required worker request | PASS, both adapters | ALIGNED in fixture | EXECUTED / core reviewed |
| F09 | Contradictory labels cannot earn acceptance | PASS, both adapters | ALIGNED in fixture | EXECUTED / core reviewed |
| F10 | Capability loss prevents further dispatch and new acceptance | PASS, both adapters | ALIGNED in fixture | EXECUTED / core reviewed |

## Verification chronology

1. Decision, scope and expected behavior recorded before corrected control.
2. Freeze native cases, adapters, consumer oracle and completion-only baseline.
3. Run baseline through the container and retain meaningful behavioral RED.
4. Implement corrected fixture, run the same oracle and targeted mutations.
5. Bind final evidence, independent review and applicable candidate suites.

The eight initial input/oracle/baseline files were frozen at
2026-09-10T11:51:19Z while `candidate.py` was absent. The baseline completed at
11:51:32Z with **20 assertion failures and zero runtime errors**. Its F02 reader
actually returned `ACCEPTED` with an empty checks list. This is a deliberately
constructed counterexample, not a historical production defect reproduction.

The corrected core was written afterward. The unchanged oracle passed all
**10 cases x 2 adapters** (one unittest method with 20 subtests) at 11:53:33Z.
The targeted F1.M1 mutant changes only the no-evidence branch after observed
completion from `PENDING` to `ACCEPTED`. It failed F02 under both adapters at
11:54:20Z: **two assertion failures, zero runtime errors**. No other case failed.
At this checkpoint all eight frozen file identities were unchanged. Required
static checks subsequently requested import ordering in the runner/test and an
explicit `zip(strict=False)` (the previous default, after an existing equal-length
assertion). The original eight files remain verbatim in
`pre-style-frozen-source.tar`. Literal `cases.json` and `expected.json`, the
baseline, adapters, services, reader and corrected core are unchanged. The final
harness replay retained the same 20-failure RED, 20-pair GREEN and two-failure
mutant outcome, with zero runtime errors; see `final-result.json` and `final-*`
logs. These mechanical edits were not adjustments to expected behavior.

A separate agent reviewed the corrected core and found no material issue within
F01-F10. That reviewer authored the oracle; this is independence from corrected
implementation authorship, not independent test derivation or human approval.

The initial bound interpreter was development image
`sha256:44fdba015678db033090671dfb11cd02d95353d6b5f7caf13ebab16a4fdb8f3c`, whose
embedded source label was older (`ee7585b`). Each fixture invocation mounted the
new source read-only, disabled network, and used writable temporary storage.
The embedded old source is not represented as candidate evidence. Applicable
whole-candidate verification uses the built candidate development image; its
standard extended dependency/audit tooling has network access. These integrated
suite runs are separate from the isolated behavioral experiment. Results are recorded
in the review-candidate delivery evidence.

## Retained evidence and replay

The adjacent `11-runtime-neutral-acceptance-fixture-evidence/` directory retains
`raw-evidence.tar.gz` and a JSON member index. The following names are archive
members, preserved byte-for-byte in their native formats:

- `oracle-freeze.json`: initial file identities and candidate absence.
- `baseline-red.log` and `baseline-F02-consumer.log`: raw assertion RED and
  actual false acceptance; accompanying JSON records hold commands and times.
- `candidate-green.log` and `candidate-results.log`: passing oracle and all 20
  native JSON result records, with execution metadata.
- `mutant-F1-M1.log`: exact operator, source identities and raw failure output.
- `result.json`: initial GREEN source/log bindings and bounded review scope.
- `pre-style-frozen-source.tar`, `final-result.json` and `final-*` files: original
  source and replay after mechanical style normalization.

All original native JSON/log bytes are in the archive, including the initial
eight-file source snapshot. The index annotates public digests for the secret
scanner without altering the archived data. These files are retained, not merely
named by hashes. Digests establish byte
identity; they do not certify intent, completeness or real runtime capabilities.
From a development container with the candidate mounted read-only, replay:

```sh
GNOSTOA_FIXTURE_IMPLEMENTATION=baseline python -m unittest discover -s tests -p test_managed_acceptance_fixture.py -v
python -m unittest discover -s tests -p test_managed_acceptance_fixture.py -v
python tests/fixtures/managed_acceptance/replay_mutant.py
```

The first and third commands intentionally return 1 with behavioral assertion
failures; the middle command must return 0. The mutant runs in a temporary copy.

## Remaining limits

The test doubles exercise different event representations. They do not prove
real-runtime portability, hostile-worker isolation, actual credential policy,
crash consistency, complete bypass detection or ordinary-work coverage. Native
input truth and expected obligations are controlled fixture data. Human semantic
review and final owner disposition are separate from test success.

The runner writes its result only after the core returns. This fixture does not
durably register PENDING before worker start, run an autonomous deadline/watchdog
or exercise recovery. Profile support, invocation-observation completeness and
snapshot freshness are stipulated inputs. Persisting and reading JSON proves
none of authenticated storage, protected-principal separation, atomic commit or
fsync durability. The terminal-completion guard is this small fixture's boundary;
non-terminal supervisor finalization remains outside its executed controls.

L10 and the other prospective supervisor/label/modularity inventories remain
separate. This fixture reports only the rows it actually executes.
