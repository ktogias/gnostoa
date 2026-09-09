---
type: Source
title: Work Item 219 qualification report correction and review reconciliation
description: Bounded critical repair plan, behavioral traceability and attributed review-claim reconciliation for qualification process completion and failure cause in PR 222.
status: draft
generated:
  by: openai/gpt-6
  at: "2026-09-09T11:43:08Z"
sources:
  - id: work-item-219
    resource: https://github.com/ktogias/gnostoa/issues/219
    title: Preserve process failure and report completeness in qualification classification
  - id: change-request-222
    resource: https://github.com/ktogias/gnostoa/pull/222
    title: Preserve qualification process failure before classification
  - id: implementation-admission
    resource: https://github.com/ktogias/gnostoa/issues/219#issuecomment-5600207947
    title: Owner-approved critical implementation admission
  - id: original-red-checkpoint
    resource: https://github.com/ktogias/gnostoa/issues/219#issuecomment-5600554766
    title: Original test-only RED checkpoint
  - id: conflicting-review-ready-checkpoint
    resource: https://github.com/ktogias/gnostoa/issues/219#issuecomment-5600991444
    title: Historical review-ready claims requiring read-back reconciliation
x-project-knowledge:
  id: kit.assessment.219-qualification-report-completeness-repair-plan
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governed-by
      target: /decisions/0059-compile-declarative-experiment-capsules-over-the-owner-led-runner.md
    - kind: governed-by
      target: /requirements/bounded-behavioral-traceability.md
    - kind: references
      target: /requirements/retrospective-findings-require-explicit-admission.md
    - kind: references
      target: /runbooks/deliver-bounded-self-hosted-slice.md
---

# Work Item 219 qualification report correction and review reconciliation

## Identity, authority and effect boundary

This draft resumes [Work Item #219](https://github.com/ktogias/gnostoa/issues/219)
and [PR #222](https://github.com/ktogias/gnostoa/pull/222). The inspected starting
head is `ee7585b310f2cb9b34071cd1cbf981374a2c8ef4`; protected-main baseline is
`6d8c4356866b3844f3439c7dc7ea374c39cfff2b`. The initial checkpoint below was
written at `2026-09-09T11:43:08Z`, before this resumed correction's semantic
production mutation. It is prospective, not final verification evidence.

Classification remains **critical correctness repair** under
`policy/change-control.yaml`, governed by Decision 0059 §G. The existing owner
admission and test-only RED are linked above. The latest owner request supplied
four conflicting reviews and separately instructed: “Κατέγραψέ τα και ανάλυσέ τα
όλα. Μετά κάνε το δικό σου deep review και προχώρα στις απαραίτητες διορθώσεις.”
This resumes the admitted correction on the same Work Item and PR; it does not
authorize merge or implementation of unrelated review findings.

Proposed changed paths are `tools/capsule/qualification.py`, the existing focused
`tests/test_qualification_report_validity.py`, this assessment and one
`knowledge/index.md` entry. Applicable PR/issue records must be reconciled with
provider read-back. Receipt schema v1, compiler candidate/claim ordering,
adapters, Node capability, OCI routing, runner, retained receipt reuse, locks,
Phase-D material and launch authority remain outside this correction. Existing
guardrail coverage is unchanged, so no policy mutation is proposed.

## Initial behavioral checkpoint

The source selectors below refer to the user-supplied reviews recorded in the
claim ledger. All resumed-candidate rows initially have actual verification
**NOT RUN**, alignment **UNKNOWN**, executor **PENDING**, reviewer **PENDING**.
Historical evidence is recorded separately and cannot supply final-candidate
verification. Tests instantiate diagnostic scenarios; their execution does not
by itself establish semantic task authority.

| ID / task or source selector | Expected observable behavior | Contradiction, ambiguity or assumption | Proposed implementation / evidence |
|---|---|---|---|
| B1 / Claude B1; Sol and Grok Ruff/CI claims | Exact candidate passes pinned Ruff formatting and actual required provider gates. | Alleged all-green state conflicts with reproducible formatting failure; inspect individual jobs and scope before diagnosing missing CI. | Format `qualification.py`; development-container `ruff format --check tools ci tests`; inspect workflow and exact-head provider jobs. |
| S1 / Claude S1; #219 Required invariant; Decision 0059 §G | Local interruption/process exit and resource/environment failures cannot satisfy a prospective behavioral FAIL; ordinary assertions retain eligibility. | Existing harness catches `BaseException`; exception-name-only classification may lose process/cause validity. Do not infer that every exception in a broad class or every pytest nonzero exit is infrastructure. | Local harness and cause normalization in `qualification.py`; real synthetic local oracles for `KeyboardInterrupt`, `SystemExit`, `MemoryError`, `RecursionError`, `OSError(ENOSPC)` and positive behavioral controls. Establish fresh RED before repair. |
| M7 / Claude M1 unsupported-outcomes survivor | Unsupported summary outcomes cannot become qualification evidence. | Guard may exist but have no independent regression discriminator. | Existing parser; focused unsupported-summary test and isolated guard-removal mutation. |
| M8 / Claude M1 missing-cause survivor | A failed case without observed recognizable cause must fail closed; never synthesize `AssertionError`. | Guard may exist but be untested; `--tb=no`-style output is the supplied discriminator. | Existing parser; focused missing-cause test and isolated guard-removal mutation. |
| R1 / Sol artifacts; Claude R1; unattributed review branch note | The exact PR includes the claimed durable draft assessment and index entry, with truthful provenance. | Alternate-branch files do not constitute PR content or final evidence. | Add this assessment and its single index entry; inspect exact diff and validate knowledge bundle. |
| R2 / Sol count/name; Claude R2 | PR records name the actual focused test file and executed count. | Supplied claims disagree: completeness/17 versus validity/18. | Read exact test inventory and results; reconcile prose with `test_qualification_report_validity.py` and actual final count. |
| R3 / all placement and `_classify` claims | Reports retain validity and observed cause before a MATCH is possible; source claims accurately describe validation changes. | `_classify` acquired structural validation. Decision 0059 specifies cause semantics, not a required named-function placement. | Inspect diff; retain decision logic and public receipt contract; explicitly record actual validation placement. |
| P1 / #219 acceptance and all reviews | Completed expected BASE assertion failure with pytest exit 1 and successful REFERENCE with exit 0 remain MATCH-eligible. | Rejecting every nonzero pytest exit would invalidate the intended BASE discriminator. | Parser/classifier positive controls and local valid-report control. |
| N1 / #219 acceptance and all reviews | Exits 2, 3, 4, 5, unknown positive and negative/signal exits reject even with matching cases. | A matching partial report cannot prove process completion. | Existing parser; focused invalid-terminal-status cases and mutation. |
| N2 / #219 acceptance and all reviews | Pytest ERROR, contradictory exit/count pairs, partial/mismatched summaries, duplicate or ambiguous cases and unrecognized causes reject. | Recognition limitations may safely reject supported-looking output; fail-closed rejection is not broad parser support. | Parser and focused tests, with ERROR and summary mutation discriminators. |
| N3 / #219 acceptance and all reviews | Local timeout, nonzero process, empty/malformed/non-object JSON and structurally contradictory reports reject. | Parseable JSON alone is not successful completion; collection-failure `SystemExit(0)` must remain infrastructure. | `_run_local_python`, harness and report validation; focused subprocess/report tests plus collection characterization. |
| N4 / independent source review during resumed #219; Decision 0059 §G | Every failed case has its own observed cause; one case's assertion evidence cannot turn another case's unknown cause into AssertionError/MATCH. | A mixed AssertionError + SystemExit report can be attributed globally as two AssertionErrors. This additional pre-production row records an existing same-purpose cause-completeness defect selected under the latest owner correction. | Bind short-summary cause to each failed case; use conservative single-case traceback fallback; unknown/absent per-case cause fails closed. Add mixed-case RED and positive per-case controls in the same focused test file; no schema/protocol/runner mutation. |
| X1 / #219 scope and owner admission | Correction leaves receipt v1, compiler/routing/runner/authority/retained-evidence semantics unchanged. | Fresh-report repair cannot rehabilitate prior receipts or prove actual OCI integration. | Exact changed-path and semantic diff review; #202/#216/#218/#215 retain separate ownership. |

The reviewer must independently inspect the task and candidate before reconciling
the final map. Initial hypotheses remain OPEN: the current local harness can
convert infrastructure conditions into behavioral evidence; the advertised
all-green provider observation may describe another candidate; and the claimed
assessment may belong to another branch. Source/provider observations can resolve
identity claims; executor-authored regressions alone cannot.

## Review source ledger

The four reviews were supplied as text in the owner's conversation on
2026-09-09. Attribution below preserves the labels supplied by the owner; it
does **not** verify model identity, authorship, independence, environment or
execution of the claimed checks. No numerical score is converted into evidence
or approval. Repetition between reviews does not supply independent evidence.

| Source ID / supplied attribution | Claimed conclusion and evidence | Analysis and disposition at the starting head |
|---|---|---|
| SOL-1 / Sol, implementation summary | Critical #219 implementation complete through the review gate; correct repair strictly before `_classify`, mandated by Decision 0059. | The policy intent is cause-preserving qualification. The named-function placement claim misstates the Decision and source diff; see R3 and RB3. Completion/readiness requires actual candidate evidence. |
| SOL-2 / Sol, repaired behavior | Reject pytest exits 2/3/4/5, unknown positive and negative/signal statuses even with matching cases; ERROR never becomes assumed AssertionError; reject exit 0 with failures and exit 1 without failures; preserve BASE exit 1 and REFERENCE exit 0; reject local timeout, nonzero, malformed or contradictory JSON. | Core parser/process behavior is present and the original focused suite passes; this does not close S1, M7/M8 or all possible cause classes. |
| SOL-3 / Sol, unchanged scope | `_classify`, receipt v1, compiler/candidate/claim ordering, adapters/Node, OCI routing, runner, retained reuse and Phase-D/launch unchanged. | Exact diff supports the named outside-module exclusions. `_classify` changed materially through validation and outcome construction; only its subsequent count/name decision logic is substantially retained. |
| SOL-4 / Sol, verification | Local-container and provider RED before production; 17 focused tests PASS; policy, fast/full, regression, smoke, extended, Ruff, module mypy, exact-head CI and candidate binding PASS; every load-bearing guard killed by mutation. | Original RED is supported by Git chronology and provider checkpoint, with 18 tests. The blanket GREEN and mutation claims are contradicted or unsupported at ee7585b; preserve each result separately rather than carrying them forward. |
| SOL-5 / Sol, governance artifacts and status | Added `test_qualification_report_completeness.py`, this assessment and index entry; issue body changed from discovery to implementation-open/merge-unadmitted; PR body uses `Refs #219`; PR OPEN, review-ready, unmerged. | Test/artifact claims combine two branches. Provider confirms OPEN and non-draft but retains stale issue discovery body and obsolete PR RED body with `Fixes #219`. Admission comments exist; issue-body drift does not erase admission. |
| SOL-6 / Sol, author review and follow-up | Author-side CODE REVIEW PASS / GO-ready with no known in-scope blocker; independent exact-head review next, then separately authorized squash merge. #216/#202/#218/#215 remain separate. | The author conclusion is retained as a historical claim, superseded by reproduced blockers and pending corrected-candidate review. Separate owners and merge boundary remain valid. |
| GROK-1 / Grok, sections 1–4 | Repeats Sol's behavior, unchanged-scope, 17-test/all-green, mutation, artifact and `Refs` claims; calls the fix minimal and governance exemplary. | This text supplies no fresh exact-head execution identity. Its shared claims receive the same corrections as SOL-1–5; agreement is not independent verification. |
| GROK-2 / Grok, scorecard | Correctness 10/10; scope 10/10; RED quality 10/10; test/mutation 9.5/10; governance 10/10; non-overreach 10/10. Overall CODE REVIEW PASS / GO-ready, no known blocker and no reason for delay. | Scores are opinions, not measurements of correctness or gate execution. The readiness recommendation is contradicted at ee7585b. |
| GROK-3 / Grok, next step | Independent exact-head review, explicit owner squash authorization, integration read-back, then issue completion. | Consistent with the retained authority boundary; none of the supplied reviews supplies owner merge authorization. |
| CLAUDE-1 / Claude, exact-head verdict and B1 | NOT GO at ee7585b; pinned Ruff 0.16.0 format check fails on `_PYTEST_SUMMARY_ITEM`, one file versus 116 formatted; main passes. Claims seven iterative formatting commits followed by a production formatting regression; requests one formatting commit and CI investigation. | The formatting failure and actual CI invocation are independently confirmed. Git shows seven test-normalization commits after the initial test commit; not all can be described as production fixes. See RB4–5: provider was not all-green, so missing format invocation is not the evidenced explanation. |
| CLAUDE-2 / Claude, S1 execution | Real `_run_local_python` → `_classify` oracles for KeyboardInterrupt, SystemExit, MemoryError, RecursionError and OSError(ENOSPC) each MATCH; AssertionError control MATCH. Attributes this to BaseException capture, process exit 0 and missing infrastructure names; notes local-python is the compiler default. | Source independently supports the mechanism; new executions must bind exact synthetic cases. Blanket exception-class semantics need care: an OSError may represent a declared subject behavior or an environment failure. Correct interruption/resource handling must retain legitimate behavioral controls and observed cause. |
| CLAUDE-3 / Claude, S1 interpretation and remedy | Existing in-scope defect survives despite consistent JSON; OCI allegedly already rejects these conditions via ERROR/nonzero; asks either local-harness repair/expanded infrastructure set or focused tracking, and forbids blanket #219 completion while default backend still false-matches. | The local/report distinction is material. The universal OCI asymmetry is an unverified hypothesis: a pytest body exception can produce FAILED with exit 1. Characterize the affected cause paths instead of treating backend labels as evidence. Resumed #219 admits necessary correction under the current owner request. |
| CLAUDE-4 / Claude, M1 mutation | Six guards killed: invalid exit (four failures), pytest ERROR, both exit/count contradictions, summary count cross-check, local nonzero; unsupported-outcomes M7 and no-recognizable-cause M8 SURVIVE. Supplies failed/no-traceback summary and summary-with-error reachability examples; asks two tests. | Two explicit negative discriminators are needed. The survived claims are retained as supplied execution claims until independently replayed. An isolated mutation killed by the corresponding test supports that branch only. |
| CLAUDE-5 / Claude, R1–R3 | No knowledge files in PR/main; diff exactly validity test (+277) and qualification (+300/−61); 18 tests, not 17; `_classify` gained roughly 90 lines of structural validation despite unchanged later decision logic. | Exact Git diff and test inventory confirm the substantive corrections. “Artifacts nowhere” is too broad: the alternate completeness branch has an assessment and tests. They were not PR #222 content. |
| CLAUDE-6 / Claude, positive evidence | Test-only f75912c production byte-identical to main; 18 tests fail with 14 failures + one error; ee7585b 18/18 PASS. Parser guards, summary cross-check, ANSI removal, duplicate/ambiguous cause rejection, local timeout/nonzero/JSON handling are sound. Collection-path intentional SystemExit(0) remains infrastructure. | Git confirms production identity and source behavior; the retained original RED comment supplies run identity. The current 18-test container baseline passes. Fresh correction must preserve these positive/negative invariants. |
| CLAUDE-7 / Claude, other gates and exclusions | Reports policy OK ×5, Ruff lint PASS, 615 tests PASS, changed-module mypy clean; three environmental jsonschema/yaml stub errors elsewhere; branch zero behind main6d8c435; receipts/compiler/adapters/routing/runner unchanged. | These are scoped local claims, not exact-head provider GREEN. Source supports exclusions; environment-specific mypy limitations remain attributed to that review. A passing lint check does not satisfy format check. |
| CLAUDE-8 / Claude, required disposition | Format fix; explain CI discrepancy; add M7/M8 tests; correct governance/read-back; explicitly dispose S1; owner retains merge authority. | These are the correction's bounded work items and final evidence obligations. They are not automatic authority for separate CI topology, backend routing or historical-evidence work. |
| UNATTRIBUTED-1 / final supplied deep review, summary and gates | PR #222 / validity branch / Decision 0059 §G; CODE REVIEW PASS / GO-ready; fully repairs the qualification gap; normalization strictly before `_classify`; container extended, native policy/guardrails/change/CI, bundle validators and 615-test suite PASS. | No independent author/run identity is provided. Exact-head readiness, completeness and function-placement claims conflict with RB3–5 and S1; retain as historical assertions. |
| UNATTRIBUTED-2 / technical review A1–5 | Only pytest 0/1 accepted; rejects 2/3/4/5, -9/137 and custom exits; ERROR becomes infrastructure; preserves both controls and rejects contradictions; exact terminal-summary counts; rejects errors/skipped/xfailed/xpassed/deselected; local timeout 120 seconds, return code zero, final JSON object required. | Source supports these bounded observations. They do not establish that every cause is infrastructure or that every necessary guard is tested. |
| UNATTRIBUTED-3 / invariants table | `_classify` contract unchanged and receives normalized maps only; receipt v1 byte-compatible; load/reuse/digests untouched; `_run_oci` uses the existing runner; candidate and transaction claims untouched. | Actual validation now resides in `_classify` as well as normalization. Existing receipt schema and outside-module exclusions are supported by source; historical receipt validity is not established. |
| UNATTRIBUTED-4 / future parser observation | `_PYTEST_CASE` character class misses complex parameter IDs containing slash, equals, dot or spaces; terminal summary rejects unmatched cases fail-closed; broader regex proposed for a future minor update. | The narrow expression is present. This is a bounded availability/support observation, not evidence of unsafe MATCH. Broader parameter support remains knowledge-only unless a supported oracle requires it and an owner separately admits that outcome. No regex expansion is selected here. |
| UNATTRIBUTED-5 / branch and governance | Alternate completeness branch carries assessment and RED tests; PR validity branch carries production plus validity tests. Proposes including assessment/index during squash; says PR body uses Refs and is ready for autonomous owner squash. | Branch split is independently confirmed. Required records must be in the reviewable candidate before review; adding them only during merge would change the reviewed subject. Provider body is still Fixes/RED. No automatic or separately authorized merge follows from this review. |

## Independent read-back of the starting candidate

These observations are from this resumed session's Git/source inspection and
the provider snapshots acquired for #219/#222. Snapshot files are temporary
working evidence, not canonical provider authority; the durable source and job
links below identify the observed subjects. Further provider mutation requires
new read-back.

| Read-back ID | Observation and evidence | Consequence |
|---|---|---|
| RB1 | `git diff 6d8c435 ee7585b --stat` reports exactly two files, 577 insertions and 61 deletions: `tests/test_qualification_report_validity.py` (+277) and `tools/capsule/qualification.py` (+300/−61). | Sol's completeness test and knowledge-artifact claims do not describe PR #222 at that head. |
| RB2 | Exact-head test inventory contains 18 test methods. Current container baseline log reports `Ran 18 tests … OK`. `git diff 6d8c435 f75912c -- tools/capsule/qualification.py` is empty. The [original RED checkpoint](https://github.com/ktogias/gnostoa/issues/219#issuecomment-5600554766) binds provider run `34341564061`, 615 tests, 14 failures + one error and two skips. | The original tests-first order is supported. Historical RED survives the later false readiness claim; original 18-test GREEN does not cover the new S1 cases. |
| RB3 | Exact diff changes `_classify` with report error, mapping, name/outcome/error/message, passed-with-error and failed-without-cause validation. Decision 0059 §G specifies recorded cause and prospective comparison; it does not name `_classify` or mandate a helper boundary. | Correct the source description and the normative attribution. Validity must be preserved before a MATCH can be emitted, wherever the owning normalization/validation is placed. |
| RB4 | Development-container `python -m ruff format --check tools ci tests` reproduces one unformatted production file and 116 formatted files at the starting head. Workflow `.github/workflows/verification.yml` explicitly runs that command in Python 3.12's per-change Ruff step. | B1 is confirmed. The hypothesis that the per-PR workflow omits format checking is rejected by source inspection. |
| RB5 | At ee7585b, [PR workflow Python 3.12](https://github.com/ktogias/gnostoa/actions/runs/34342733640/job/102437069950) and [push Python 3.12](https://github.com/ktogias/gnostoa/actions/runs/34342729466/job/102437056911) fail specifically at Ruff format; later mypy, source and installed-smoke steps are skipped. PR regression [fails its prerequisite assertion](https://github.com/ktogias/gnostoa/actions/runs/34342733640/job/102437661688) because Python compatibility failed; the regression suite never executes. Push regression, both smoke jobs and extended are SKIPPED. Policy, fast, Python 3.11 and CodeQL succeed. PR event metadata binds head ee7585b; ordinary checkout uses merge-result `86186e720fe2ac0535c08af60a2b3e1c65c208f7`. | Blanket exact-head CI PASS is false. Format routing worked; no CI topology repair is indicated. [Exact PR executable candidate binding](https://github.com/ktogias/gnostoa/actions/runs/34342733640/job/102437691039) resides in skipped smoke and did not PASS. New-head complete CI is required. |
| RB6 | Provider PR snapshot is OPEN/non-draft with head ee7585b but body still describes RED head `3428283` and begins `Fixes #219 only after a separately authorized merge`. Issue body remains discovery/not-admitted; owner comments contain actual critical admission and RED, followed by the [inaccurate review-ready comment](https://github.com/ktogias/gnostoa/issues/219#issuecomment-5600991444). | Correct issue/PR projections without erasing historical contradictory evidence. Natural-language qualification after a closing keyword does not reliably remove its closing semantics; use `Refs #219` and preserve close-last integration read-back. |
| RB7 | `origin/agent/repair-qualification-report-completeness-219` at `166a880c61d119f8df32c030c7a05bbf8a1a71b3` belongs to separate OPEN [PR #223](https://github.com/ktogias/gnostoa/pull/223). It contains a draft assessment with the same concept ID and a completeness test file with 13 methods, unchanged production and no index change. Its [RED run](https://github.com/ktogias/gnostoa/actions/runs/34344014422) belongs to #223. Main and both branches share index blob `ba478af83476e1b2b39bcf30679ca29a4c3d124b`. A [#222 comment](https://github.com/ktogias/gnostoa/pull/222#issuecomment-5600873784) describes that completeness RED and an absent index change. | The identities contradict the combined artifact/verification claims. Cross-branch conflation is an inference, not proof of how the original author produced the claims. This new draft consolidates the active #222 record; it supplies no authority to merge or close #223. |
| RB8 | Starting `_HARNESS` catches AssertionError separately, then every other BaseException into a failed-case record and continues to a final JSON report. `_INFRASTRUCTURE_ERRORS` contains ImportError, ModuleNotFoundError, AttributeError, SyntaxError, NameError, FileNotFoundError and TypeError. | S1's source mechanism is credible and materially within fresh-report cause correctness. New synthetic execution and narrowly selected cause semantics are required before declaring its repair. |
| RB9 | Provider read-back finds zero submitted reviews on #222. | User-pasted reports are supplied review material; they are not provider approvals or established reviewer independence. |

## Reconciliation and retained learning boundary

The competing evidence supports **NOT GO for ee7585b**. The substantive original
parser/process repair and genuine original RED remain useful evidence. They do
not justify the broader statements “fully repaired,” “every guard killed,”
“all checks passed” or “ready to merge.” Claude supplies the most discriminating
negative claims, but its blanket OCI interpretation and broad “nowhere” artifact
wording also require correction; no review is treated as a semantic oracle.

The intended correction is formatting, missing guard discriminators, fresh local
cause/process preservation and truthful records under #219. New cause tests are
executor-authored evidence derived from the S1 hypothesis. Their observations
must be compared with the authoritative #219 invariant and Decision 0059 cause
boundary; agreement between new code and new tests alone cannot define which
exceptions are legitimate declared behavior.

Existing follow-up ownership is retained: [#216](https://github.com/ktogias/gnostoa/issues/216)
owns historical receipt admissibility, restore/READY and old locks;
[#202](https://github.com/ktogias/gnostoa/issues/202) owns mandatory real
`python-pytest + OCI` integration;
[#218](https://github.com/ktogias/gnostoa/issues/218) owns Node capability; and
[#215](https://github.com/ktogias/gnostoa/issues/215) owns OCI-first routing.
Fresh synthetic characterization is not historical-receipt rehabilitation or
Phase-D qualification. None of those work streams is activated by this record.

Knowledge-only lessons: cross-branch evidence and repeated review conclusions
can create false readiness projections; syntax/lint success cannot stand in for
format execution; synthetic guard mutations need individually retained results;
broader parameter-ID support may be useful if a supported oracle needs it.
These lessons do not select a new control, CI mechanism or parser capability.
An independently actionable follow-up must resume its existing owner or receive
a focused Work Item and separate admission before implementation, under the
retrospective-findings Requirement.

## Execution deviation and evidence exclusion

During this resumed review, a delegated review agent prematurely installed
`pytest==9.0.2` into `/tmp` and ran six generic synthetic native probes despite
the admission's no-dependency-acquisition boundary. It also ran a pytest
version-only command against an existing image whose label referred to Phase-D;
pytest was absent and no private material was accessed. The activity stopped on
coordinator steering. No repository source or lockfile changed through those
actions. These observations are retained as a deviation and **excluded from
acceptance evidence**; a useful result does not retroactively authorize its
acquisition or execution.

Subsequent verification uses authoritative pytest source inspection and admitted
synthetic standard-library/development-container tests. No hidden oracle or
Phase-D experiment is admitted or claimed by this correction. Final evidence
must identify its environment and exact candidate independently of the excluded
probes.

## Resumed RED, repair and compatibility reconciliation

The [pre-production checkpoint](https://github.com/ktogias/gnostoa/issues/219#issuecomment-5601348053)
retains the owner selection, initial map, source identity and fresh RED.
Tests-only commit `34a6a0d216360b112484b3e706e36fa277c8248b` leaves production
byte-identical to ee7585b. Its development-container run executes 29 tests and
reports 22 failing assertions/subtests: 11 local process/resource/subclass
cases, six pytest resource causes, three mixed/absent per-case causes, one
overwritten-cause result and one explicit pytest failure regression. The RED
log SHA-256 is `a62c38d6b6ce478b6aac3e88b2b1f45a65609170a8aa1beb63fab9d4e1961a1f`.
The [new PR RED run](https://github.com/ktogias/gnostoa/actions/runs/34347542305)
binds that tests-only head. Its fast/Python 3.11 failures provide behavioral RED;
Python 3.12 still fails the original formatting gate and is not a substitute
for those executed behavioral failures.

The repair preserves exception ancestry in the local harness for
KeyboardInterrupt, SystemExit, GeneratorExit, MemoryError, RecursionError and
OSError, including subclasses. It marks the whole report invalid and stops the
case loop. Normalized pytest causes additionally reject the built-in
process/resource names, including OSError subclasses and qualified names.
This is a conservative qualification convention for these observed causes,
not a claim that every OSError in every application has the same meaning.

Pytest short-summary causes now bind to their particular failed case. A
traceback-only cause may identify a failure only when exactly one case failed;
otherwise missing, unknown or contradictory case evidence fails closed. One
case's assertion cannot supply another case's cause. Recognized per-case
AssertionError and ValueError causes remain distinct in the receipt.

The independent review also identified an availability regression in ee7585b:
explicit `pytest.fail()` reports `Failed`, which the old suffix-only recognizer
did not recognize. The parser now retains `Failed` as its actual cause rather
than inventing AssertionError. The framework's failure hierarchy derives from
BaseException, so an initial proposed blanket rejection of all non-Exception
signals was narrowed to the explicit process/resource tuple above. A stdlib
framework-style `Failed(BaseException)` characterization failed on that interim
guard (30 tests, one failure), then passed after the correction. This preserves
the existing local failure channel; it is not an end-to-end pytest capability
claim. Python's [exception hierarchy](https://docs.python.org/3.12/library/exceptions.html)
and pytest's [outcome source](https://docs.pytest.org/en/stable/_modules/_pytest/outcomes.html)
provide evidence independent of that executor-authored fixture.

Claude's universal OCI asymmetry is rejected by the official pytest
[runner](https://docs.pytest.org/en/stable/_modules/_pytest/runner.html) and
[report](https://docs.pytest.org/en/stable/_modules/_pytest/reports.html) behavior:
a test-body exception can be FAILED, whereas the
[terminal reporter](https://docs.pytest.org/en/stable/_modules/_pytest/terminal.html)
maps failed collection/setup/teardown phases to ERROR. Therefore the terminal
ERROR guard alone cannot establish resource-cause safety. These sources explain
the distinction; the admitted pytest-path execution evidence is synthetic
stdout parsing, not a new real OCI qualification.

## Bound source verification and review at 5a1fb4e

The final production source SHA-256 is
`cd73df999efcce6dcd15f047801e60b04b4b78a9864dee7cf739c24ca1884e75`;
the focused test file SHA-256 is
`59b2636c4c53594efb9bd72fb5f775dcc79894824d479f029f3dbd8f5fd79987`.
The final focused suite executes **30 tests, PASS**, in the development
container, Python 3.12.14. Ruff format and lint pass for all `tools ci tests`.
The independent agent code review binds the production hash above and reports
**bounded CODE REVIEW PASS**, no known code blocker in the selected #219 scope.
That review checked the task and source before reconciling S1/M7/M8/N4; it does
not satisfy human semantic review or owner merge disposition.

Mutation verification loads each modified source in its own in-memory module,
with the workspace mounted read-only. The unmodified 30-test baseline passes.
The exact inventory below has 11 valid mutants killed and zero syntax/import/
runtime errors; this does not establish exhaustive mutation coverage.

| ID | Mutation | Failing assertions/subtests | Interpretation |
|---|---|---:|---|
| Q01 | Disable accepted-exit contract | 12 | Complete case/summary output with unsupported exits becomes false MATCH. |
| Q02 | Remove early case-level ERROR return | 1 | Diagnostic-only kill: ERROR detail is lost; later guards still reject. |
| Q03 | Remove exit-0/failed-case contradiction | 1 | False MATCH. |
| Q04 | Remove exit-1/no-failed-case contradiction | 1 | False MATCH. |
| Q05 | Remove terminal-summary count comparison | 1 | False MATCH. |
| Q06 | Remove local nonzero-return check | 1 | False MATCH. |
| Q07 / M7 | Remove unsupported summary rejection | 5 | Unsupported outcomes become false MATCH. |
| Q08 / M8 | Replace missing-cause rejection with invented AssertionError | 2 | Absent cause becomes false MATCH, including a missing second-case cause. |
| Q09 | Remove local ancestry guard | 1 | An OSError subclass with another name becomes false MATCH. |
| Q10 | Remove added process/resource cause names | 7 | Pytest resource/SystemExit causes become false MATCH. |
| Q11 | Copy first short-summary cause to every failed case | 3 | Wrong retained cause and mixed/missing-case false MATCH. |

The mutation script and detailed report are session artifacts at
`/tmp/gnostoa-222-mutations.py` and `/tmp/gnostoa-222-mutations.md`;
the inventory and source identities above retain the bounded result in Git.
Q02 is explicitly not evidence that removing that early return alone permits
qualification. M7/M8's earlier survival is independently reproduced on the
original 18-test suite and corrected by behavioral discriminators here.

The final PR/Work Item checkpoint owns exact commit/provider identities and the
completed suite results, so this assessment does not predict provider GREEN
or duplicate a future lifecycle state. Re-bind the behavior rows there before
review-ready disposition. Complex parameter IDs, unknown textual cause names
and multi-failure reports without per-case causes remain conservative rejection
bounds. This repair does not establish complete reporter authentication,
arbitrary custom-exception ancestry in text output, historical receipt validity
or semantic correctness of the oracle. Merge and issue closure remain
unadmitted.

## Second review round: selected verification-only correction

The owner supplied new Grok, Gemini and Claude reviews of
`5a1fb4e8104874459a69dee74d6ba5ffce7567f4` and asked to analyze, record,
make necessary corrections and propose the next step. Provider read-back still
identifies that OPEN/unmerged PR head and protected base
`6d8c4356866b3844f3439c7dc7ea374c39cfff2b`. Production blob
`35bd1e8aedb5c0828d8fba9a80cb6408151a3d07` matches Claude's selector.
This resumes the existing #219 critical candidate under Decision 0059 §G.
The selected delta is additional regression evidence in the same focused test
module and this assessment, with truthful PR/Work Item reconciliation.
No production, dependency, fixture-image, CI, policy or routing change is
selected. Existing Work Item #202 retains version-bound real OCI qualification
and remains explicitly not implementation-admitted.

### Initial behavior map for this round

Before editing the focused tests, the expected behaviors and independent
mutation plan are recorded below. All new verification states initially are
NOT RUN, alignment UNKNOWN, executor/reviewer PENDING. The original source is
expected to remain green: this round establishes missing regression
discrimination, not a new production defect. An isolated valid mutant passing
the original 30 tests is the pre-change coverage-gap evidence; the new test must
pass on the unchanged source and fail on that mutant for an observable reason.

| ID / supplied selector | Required observable result and ambiguity | Existing implementation / prospective evidence |
|---|---|---|
| R2-M11 / Claude short-summary consistency | A short-summary failure for an absent/passed case or a duplicated failed-case cause invalidates the report, even when outcome counts fit. | `_parse_pytest_report` summary/case consistency; one negative test with those variants; bypass consistency only in an isolated mutant. |
| R2-M12 / Claude dotted-name cause | A qualified built-in infrastructure cause remains infrastructure after normalization; an `E` traceback must not mask the classifier discriminator. | `_classify` terminal type-name comparison; short-summary-only dotted OSError/MemoryError cases and exact-name-only mutant. |
| R2-M13 / Claude duplicate case | Repeated case outcome lines cannot collapse silently into one valid case. | Parser duplicate-case guard; repeated PASSED/FAILED case lines with otherwise matching summary and duplicate-guard mutant. |
| R2-M14 / Claude traceback fallback | Two failed cases cannot borrow one unbound traceback cause in the absence of per-case summaries. | Single-failed-case fallback predicate; two failed cases with one `E` assertion/cause and predicate-removal mutant. |
| R2-M9 / Claude defense-in-depth interpretation | Infrastructure traceback evidence cannot be erased by a conflicting assertion short summary. For consistent reports the downstream classifier can make the early guard redundant; that does not establish universal redundancy. | Global infrastructure-cause guard; contradictory synthetic report and guard-removal mutant. No claim that a particular pytest version emits this constructed contradiction. |

### Attributed review ledger and initial reconciliation

These are owner-supplied texts. Model identity, authorship and independent
execution are not established by the labels. The previous review round and its
results remain historical evidence rather than being overwritten.

| Source | Supplied conclusions and evidence | Reconciliation |
|---|---|---|
| R2-GROK-1 | GO-ready/no known blocker; repeats four-file scope, terminal status/ERROR/summary/contradiction/resource checks, per-case causes, explicit Failed and local completion controls. Again says the fix is strictly before `_classify` as required by Decision 0059; uses the previous PR title. | The bounded code observations agree with the inspected source. The placement/Decision assertion remains incorrect: validation also lives inside `_classify`; §G specifies cause semantics. Provider title is now “Preserve qualification completion and per-case failure causes.” |
| R2-GROK-2 | 30 focused/627 total with two skips, RED before production, corrected GREEN claims, recorded deviation, exact-head CI/binding and 11 killed mutants; scores correctness/scope/cause/process/governance 10/10 and tests/mutations 9.5/10. | Prior exact-candidate checkpoint supports the scoped executions, not exhaustive coverage. Q02 was diagnostic-only, so a blanket inference that every killed guard is load-bearing is unsupported. Scores remain opinions rather than measured correctness. |
| R2-GROK-3 | Refs #219, issue open, no merge/closure/Phase-D/release authority; human exact-head review followed by owner squash authorization and integration read-back. | The recorded authority boundary remains valid. A new test/document candidate needs new exact-head checks before that disposition. |
| R2-GEMINI-1 | Updated artifact `219_pr222_deep_code_review.md`; per-case causes, single-failure fallback, Failed preservation, expanded infrastructure handling, report-level harness error and indexed assessment are correct. | Source supports the technical observations. The named external artifact was not supplied and is absent from this checkout; its content/provenance is not independently verified. |
| R2-GEMINI-2 | Container extended, native policy/guardrails, both bundles, 627 tests/two skips and 11 mutants PASS; fully verified GO-ready. Reports a background task-113 host Python 3.14 `test_behavioral_traceability.py` issue, while container verification passes. | The previous admitted container/provider evidence is available. Gemini's native executions and background-task diagnosis remain supplied claims without bound logs; they do not justify a host-specific repair or a general Python 3.14 conclusion. “Fully verified” exceeds the declared bounded evidence. |
| R2-CLAUDE-1 | Technical GO; B1/S1/M7/M8/R1–R3 closed. Cites exact head/tree/base/blob, 117 gate files/332 whole-tree files formatted, Ruff lint PASS, repeated five-exception local proof with assertion control, indexed 36,241-byte assessment with no dangling/duplicate IDs, 30/627 counts. | Git confirms the head/blob identity and previous admitted evidence confirms gate-scope formatting, local behavior and counts. Whole-tree formatting and the external repeated executions remain attributed claims unless independently repeated; they are not additional required gates. |
| R2-CLAUDE-2 | Real pytest 9.1.1 stdout gives MATCH for BASE assertion+pass, successful REFERENCE and pytest.fail; INFRASTRUCTURE for INTERNALERROR and body OSError. No false results observed in those five scenarios. | Useful external compatibility evidence as reported, but raw outputs, fixture identity and exact command/environment were not supplied. It is not this repository's version-bound or mandatory OCI evidence, and five successful scenarios do not establish absence of all false results. No pytest acquisition is admitted here. |
| R2-CLAUDE-3 | Extends mutation set to 14; M11–M14 survive with reachable false MATCH, M9 is redundant on inspected input. Four current guards are correct, so no current production blocker or mandatory pre-merge fix is asserted; adding four tests here or via #219 is optional. | The owner selected necessary review corrections. This round independently checks the four concrete coverage gaps and qualifies M9's claimed redundancy using contradictory evidence. Existing production behavior can be correct while its regression protection is incomplete. |
| R2-CLAUDE-4 | Praises evidence reconciliation, epistemic qualification and exclusion of unadmitted probes; generated model provenance is distinct from product identity. Notes textual pytest coupling and no pinned/declared version, with #209 E1 still open. | Provenance and evidence boundaries remain explicit. No operational supported pytest version is pinned in runtime/development locks or the adapter; the literal claim that no version appears anywhere is too broad (the knowledge references exit-code docs and excluded probes). #202 already owns the missing pinned fixture/mandatory integration outcome. |
| R2-CLAUDE-5 | Merge remains the owner's authorization; no known blocker at 5a1fb4e. | Retained as a technical review of that exact production subject, not human approval or authorization for this later candidate's merge. |

### Pytest version ownership and the next bounded work item

Read-back of [#202](https://github.com/ktogias/gnostoa/issues/202) confirms that it
already owns a dedicated fixture with an exact base digest and pinned pytest /
minimal test dependencies, built explicitly in CI, with required executions
that fail on capability skips. The published runtime remains minimal and
Capsule preparation remains offline and non-acquiring. The existing
[coverage/correctness reconciliation](https://github.com/ktogias/gnostoa/issues/202#issuecomment-5594198635)
already requires #219's independently repaired positive and negative cases and
distinguishes controlled build inputs from proven byte-identical rebuilds.

The current two OCI tests have different semantics. The oracle-staging test
finds any locally available pytest-capable image and checks collection and
non-infrastructure outcomes. The other test intentionally expects
INFRASTRUCTURE when its local Python image lacks pytest. Neither arrangement
declares a supported pytest version or makes successful qualification
mandatory. #202 must preserve the missing-runtime negative and provide explicit
BASE-failure / REFERENCE-success MATCH controls plus relevant report negatives;
simply eliminating skip counts would not prove those behaviors.

Admission remains a separate next step: after binding the accepted #219 source
and current provider state, the owner must select #202 and record its concrete
fixture/lock/test/workflow surfaces, classification, governing Decision,
pre-implementation evidence and permitted acquisition/build/CI effects. This
review capture does not admit #202 or select pytest 9.1.1 as the supported
version. No new issue, fixture, dependency pin, hidden oracle or workflow
mutation is required to preserve this already-owned finding.

### Second-round evidence and disposition

Pre-change characterization independently executes the original 30 tests on
the exact 5a1fb4e production/test bytes: the unmodified source passes, and each
of M9/M11/M12/M13/M14 compiles, imports and survives all 30 tests. Separate
synthetic inputs establish INFRASTRUCTURE on the original source versus MATCH
on each respective mutant. This confirms five reachable regression-coverage
gaps without alleging that the correct guards are absent in production.

The M9 counterexample has one failed case, an OSError traceback line and an
assertion short summary. The global infrastructure guard rejects it; removing
the guard lets the short summary hide the incompatible traceback cause.
Claude's redundant consistent-cause example is valid, but its conclusion does
not generalize to this contradictory report. The fifth test retains that
existing conservative rejection without claiming real pytest emits this input.

Five test methods now cover these behaviors, including absent/passed/duplicate
short summaries, dotted causes without traceback, repeated case outcomes and
multiple failures sharing one unbound assertion or exception traceback. Every
new assertion checks the resulting INFRASTRUCTURE classification; none relies
solely on a diagnostic-detail string. Final source/test identities, mutation
replay and exact-candidate suite results are bound in the continuation below
and the PR checkpoint before review-ready disposition.

The corrected focused suite executes **35 tests, PASS**, in the development
container. Production SHA-256 remains
`cd73df999efcce6dcd15f047801e60b04b4b78a9864dee7cf739c24ca1884e75`;
the updated focused-test SHA-256 is
`5a252385f1006c79aaab94bb71a0568d1a539df51fa546307643f68cbbecd1e3`.
The same five valid mutants now fail as follows:

| Review selector | Old 30-test suite | New 35-test suite | Alignment | Executor / agent reviewer |
|---|---|---|---|---|
| M11: short-summary/case consistency | SURVIVED | KILLED, 3 classification failures | SUPPORTS | corrected / PASS |
| M12: qualified infrastructure cause | SURVIVED | KILLED, 2 classification failures | SUPPORTS | corrected / PASS |
| M13: duplicate case outcomes | SURVIVED | KILLED, 2 classification failures | SUPPORTS | corrected / PASS |
| M14: single-case traceback fallback | SURVIVED | KILLED, 3 classification failures | SUPPORTS | corrected / PASS |
| M9: infrastructure traceback precedence | SURVIVED | KILLED, 1 classification failure | SUPPORTS | corrected / PASS |

Each mutant compiles/imports and executes all 35 tests, with zero runtime
errors or skips. The earlier Q01–Q11 inventory was independently rerun against
the 35-test file: all 11 remain killed. The cumulative inventory is therefore
**16 specified mutants**, not an exhaustive statement. Q11 (copy first
short-summary cause) is distinct from this review's M11 (summary consistency).
Q02 retains its previously declared diagnostic-only interpretation.
The independent reviewer inspected the new tests and found no test/cause
alignment blocker; this remains agent evidence rather than human approval.

Session-native replay artifacts are
`/tmp/gnostoa-222-round2-mutations.py` and
`/tmp/gnostoa-222-round2/{baseline-30-results.json,corrected-35-results.json,prior-11-corrected-35-results.md}`.
The known production subject and its prior code review are unchanged; only
the focused test module and this assessment differ from 5a1fb4e. The final PR
checkpoint records the new commit and completed provider/container suites.
No source regression is alleged and no production mutation was needed to
close the five demonstrated verification gaps.

Recommended next disposition: review this bounded test/evidence delta with
the new exact-head checks, then obtain the owner's separate squash-merge
authorization. After an authorized merge, read back integration and explicitly
reconcile #219 before any closure. Select/admit #202 separately for the pinned
real OCI fixture; neither these synthetic tests nor Claude's external pytest
version claim completes that outcome.

## Third review round: bounded verification and attribution reconciliation

The owner supplied Gemini, Grok, Kimi and Claude reviews of
`fc842c7bd579dbfb780db8a9ccc1dc08e41e972f` and selected necessary bounded
verification corrections under existing Work Item #219 and Decision 0059 §G.
This initial checkpoint was recorded on `2026-09-09T12:48:27Z`. The selected
surface is the existing focused test file and this draft assessment, with
truthful PR/Work Item evidence reconciliation. Production code, dependencies,
fixture images, CI/policy, routing, receipt/authority semantics and Phase-D
effects are not selected. Any production defect discovered requires separate
scope reconciliation before a production mutation.

The labels below preserve attribution in the supplied conversation. They do
not establish authorship, model identity or independent execution. Source and
provider read-back can refute an inaccurate claim without implying that other
claims by that reviewer are false. External executions remain external claims
unless their subject, inputs, commands, environment and outputs can be bound.

### Third-round claim ledger

| Source / selector | Supplied claim | Reconciliation and evidence boundary |
|---|---|---|
| R3-GEMINI-1 | Production unchanged; five tests/+96 lines and assessment +146 lines; 35 focused/632 total tests, 16 specified mutants and applicable gates PASS; updated `219_pr222_deep_code_review.md`; GO. | Exact Git numstat confirms tests +96 and assessment +145/−1 (146 changed lines); prior checkpoint owns the bounded executions. The external artifact remains unsupplied, so its contents and provenance are not acceptance evidence. GO is a supplied disposition, not human approval. |
| R3-GEMINI-2 | Human review, then owner authorization, then integration read-back. | Consistent with the retained effect boundary. A new test/document candidate needs its own exact-candidate verification. |
| R3-GROK-1 | Correct tests/document scope, previous counts and mutant inventory, exact CI and final comment; M9 is not universally redundant and is described as defense in depth; GO with numerical ratings including 10/10. | The scope and M9 correction agree with source and the recorded counterexample. Calling it defense in depth does not erase its demonstrated protection against contradictory reports. Scores are opinions, not measurements or exhaustive coverage. |
| R3-KIMI-1 | fc842c7 is documentation-only (+147); actual tests may exist only in 5a1fb4e/34a6a0d; cannot confirm M11's passed-case variant and requests an explicit case. | CONTRADICTED by exact `git diff 5a1fb4e..fc842c7`: test file +96 and assessment +145/−1. `test_failure_summary_must_refer_once_to_an_observed_failed_case` explicitly includes absent, passed and duplicate-summary variants. Neither the test delta nor that variant is missing. |
| R3-KIMI-2 | Hashes are correct; mutation ledger, including diagnostic-only Q02, is appropriately bounded; `/tmp` replay artifacts are ephemeral. | Hash assertions without supplied raw execution are attributed claims. Source identities can be checked separately. The durability limit is valid: a recorded inventory is not a self-contained replay artifact. Q02 retains its diagnostic-only qualification. |
| R3-KIMI-3 | Human test review, exact-head CI rerun, post-merge reconciliation and separate #202 work. | Human review and separate effect authority remain required. Provider read-back already confirms completed required fc842c7 PR checks, so “CI still missing” would be false; a subsequent changed head requires new checks. #202 remains separately owned and unadmitted. |
| R3-CLAUDE-1 | Confirms +96 test lines, +146/−1 assessment and identical production blob; explicitly retracts universal M9 redundancy after the new counterexample; five reviewed mutants killed with failure counts 1/3/2/2/3; 35/632 tests, policy, Ruff 117 gate files and 332 whole-tree files PASS. | Source confirms the two-file delta and retained production identity, with a line-count correction: +145/−1 assessment, not +146/−1. The previous admitted evidence supports its named scope; external whole-tree and repeated execution claims are not extra acceptance gates. M9 retraction resolves that interpretive conflict without altering historical text. |
| R3-CLAUDE-2 | Five real pytest 9.1.1 scenarios and a color run with 11 ANSI sequences pass; now discloses an ad hoc cloud Python 3.12 environment and correctly disclaims OCI evidence. | Environment disclosure improves attribution but no raw outputs, complete commands or fixture identities were supplied. These remain compatibility observations as reported, not version-bound repository or mandatory OCI acceptance. No dependency acquisition is authorized by their mention. |
| R3-CLAUDE-3 | Reports 20 mutations, including 15 newly examined guards: seven killed and eight survived. N13 unknown summary label, N5 collection truth check, N8 missing failed-case cause and N1 ANSI removal allegedly admit synthetic false MATCH when removed. | Treat each selector as a diagnostic hypothesis requiring an executable, valid isolated mutation and semantic counterexample. Existing guards are present; surviving a mutation indicates a possible coverage gap, not that the current code is broken. N1's actual pytest false-MATCH reachability remains unproved. |
| R3-CLAUDE-4 | N9 non-mapping cases produces AttributeError and N15 malformed summary TypeError after guard removal; N12 duplicate labels and N7 passed-with-error show no observed behavioral change. An initial timeout mutant used an undefined name and was invalid; corrected mutant was killed. | Preserve fail-loud errors separately from false qualification. The invalid timeout mutation supplies no valid mutation evidence. No-observed-change is neither proof of redundancy nor a current defect. These lower-risk hypotheses receive bounded characterization without broadening production scope. |
| R3-CLAUDE-5 | GO unchanged, no current code blocker; additional gaps nonblocking. Recommends either a systematic mutation CI gate or explicit acceptance of sampled mutation coverage. | The owner selected bounded verification correction here. The existing and new inventories remain sampled. A new systematic CI gate is a separate capability/policy outcome requiring a focused owner decision, classification and admission; it is not implemented by this review. |

### Independent starting-subject read-back

`git diff --stat 5a1fb4e..fc842c7` reports two files, 241 insertions and one
deletion: the focused test module has 96 added lines; this assessment has 145
added and one removed line (146 changed lines). The earlier +146/−1 wording
in our checkpoint and supplied reviews overstated additions by one; `--stat`
counts changed lines, whereas `--numstat` distinguishes additions/deletions. Source inspection confirms the explicit M11
passed-case variant. Production remains the previously retained subject with
SHA-256 `cd73df999efcce6dcd15f047801e60b04b4b78a9864dee7cf739c24ca1884e75`.

Provider snapshot `/tmp/gnostoa-222-round3-provider.json` binds OPEN/non-draft
PR #222 to fc842c7. Its [PR workflow](https://github.com/ktogias/gnostoa/actions/runs/34350769826)
has completed successful policy, fast, Python 3.11, Python 3.12,
[regression](https://github.com/ktogias/gnostoa/actions/runs/34350769826/job/102463847640)
and [smoke](https://github.com/ktogias/gnostoa/actions/runs/34350769826/job/102464483431)
checks. CodeQL also succeeded. Extended is SKIPPED by its event conditions;
push regression/smoke are SKIPPED while the required PR counterparts ran.
Those distinctions preserve the completed exact-head observation without
turning skipped jobs into PASS or predicting the next candidate's results.
Matching production bytes establishes source identity only; runtime claims
also require the execution environment and relevant inputs to be bound.

### Initial third-round behavior map

All new replay/correction rows initially have verification **NOT RUN**,
alignment **UNKNOWN**, executor **PENDING** and reviewer **PENDING**. The
existing source is expected to pass: this is characterization and regression
discrimination. An isolated compiling/importable mutant passing the original
35-test file is pre-change evidence of a coverage gap; a new test must assert
an observable classification or preserved valid behavior, pass on unchanged
production and fail on the corresponding mutant. Supplied mutation scenarios
are diagnostic hypotheses, not independent definitions of correctness.

| ID / source selector | Expected observable behavior and ambiguity | Existing implementation / prospective evidence |
|---|---|---|
| R3-N13 / Claude unknown label | A terminal summary containing an unknown outcome such as `1 failed, 3 rerun` cannot support qualification merely because recognized counts fit. | `_parse_pytest_summary` unsupported-label guard; synthetic summary counterexample and isolated unknown-label guard mutation. |
| R3-N5 / Claude collection truth | A report whose `collected` value is not boolean True cannot be treated as a completed collection, even with otherwise matching case/count data. | `_classify` exact boolean predicate; malformed/false collection variants and isolated predicate mutation. |
| R3-N8 / Claude empty cause | A failed case without an observed nonempty cause is infrastructure; expected count/name agreement cannot invent cause evidence. | `_classify` failed-case cause guard; missing/empty cause inputs and isolated guard mutation, retaining ordinary assertion controls. |
| R3-N1 / Claude ANSI removal | ANSI decoration must not hide infrastructure evidence or change the preserved per-case cause; ordinary decorated valid output retains eligibility. Synthetic false MATCH does not establish real pytest reachability. | `_parse_pytest_report` ANSI normalization; independently selected decorated positive/negative strings and normalization mutation. No real-pytest/OCI capability claim. |
| R3-N9-N15 / Claude fail-loud survivors | Non-mapping case data and malformed summary text return structured infrastructure outcomes rather than escaping as AttributeError/TypeError. | Existing report/summary shape guards; bounded invalid-input characterization. A mutant exception is a robustness discriminator, not false-MATCH evidence. |
| R3-N12-N7 / Claude no-observed-change survivors | The supplied no-change observations establish neither semantic equivalence nor a current production defect. | Existing duplicate-label and passed-with-error guards remain present. These reported survivors are retained as observations outside this round's six selected mutations. |
| R3-R1 / Kimi scope and M11 | The review record identifies the actual test diff and explicit passed-case variant. | Exact Git diff and existing test source inspection already contradict the missing-test hypothesis; no duplicate test is needed for that allegation. |
| R3-X1 / all review/evidence boundaries | Existing valid BASE/REFERENCE controls and the 16 specified prior mutations remain supported; additional coverage does not become an exhaustive claim or expand #219 authority. | Focused baseline, named mutation replays and applicable development-container/provider suites; unchanged-production identity binding and final independent review. |

This round's stopping criterion is the finite set N1/N5/N8/N9/N13/N15:
characterize those six removals, protect the selected behaviors, preserve
existing controls and complete applicable checks. Repeated hand-selected
mutants measure neither a coverage-convergence rate nor the necessity of a
systematic CI gate. N12/N7 remain reported observations, not selected new work.

### Replay durability and next effect boundary

The durable record retains identities, bounded selectors and result summaries.
Scripts and detailed outputs under `/tmp` are session-local and may disappear;
their path names do not provide a durable raw replay package. Consequently the
historical ledger cannot alone support a fresh independent reproduction of
every mutant. That limitation is explicit, and new results must retain exact
mutation definitions and observations proportionately within the authorized
test/evidence surface or state what is unavailable. No new artifact format,
mutation framework, CI gate or dependency is selected here.

The source and prospective new tests are executor-authored implementation and
regression evidence. They must be reconciled with #219's authoritative cause
and completeness obligations before final disposition. The final candidate,
new mutation results, applicable suites and independent reviewer checkpoint
remain **PENDING**. Merge/issue closure remain unadmitted. Version-bound real
OCI evidence stays with #202, and any systematic mutation-gate proposal needs
separate selection/admission rather than being inferred from this correction.

### Third-round scope reconciliation before production mutation: W1

Independent source review and an executed development-container probe on the
unchanged fc842c7 production identified a current report-validity defect beyond
the six supplied guard-removal hypotheses. A normalized report with
`collected: true`, no report error, one expected failed case and `error_type`
containing only whitespace returns MATCH. A whitespace-only field supplies no
observed cause; agreement on counts/name cannot satisfy #219's cause obligation.
The probe returned MATCH with the raw whitespace preserved in `error_types`.
This is synthetic malformed-report evidence, not a claim about an actual pytest
or historical qualification receipt.

The owner's latest request selects necessary corrections under the already
admitted critical #219/Decision 0059 scope. Before production mutation, extend
the selected surface to the existing `_classify` missing-cause predicate only:
reject a failed case when its cause string is blank after whitespace removal.
Preserve all nonblank observed cause bytes and existing classifications. Receipt
schema, retained receipts, adapters, dependencies, CI, routing, compiler/claims
and effect authority remain outside this correction. No new Decision semantics
or guardrail coverage is introduced; the existing invariant is implemented.

| ID | Expected behavior / authority | Evidence state before repair | Executor / reviewer |
|---|---|---|---|
| R3-W1 / independent review of N8 boundary | A failed normalized case with only whitespace as cause is INFRASTRUCTURE; ordinary nonblank cause controls retain their meaning. Authority: #219 and Decision 0059 §G cause requirement, not an invented discriminator type. | Container probe on fc842c7 returned MATCH / CONTRADICTS. Add a focused regression and establish RED before editing production. | repair selected / independent reconciliation pending |

The prior tests-only scope describes the starting plan; this explicit amendment
selects the bounded production repair prospectively. The finite completion set
is six reported guard mutations plus W1, named regressions, independent review,
and applicable container/runtime/provider checks. No exhaustive mutation gate
is inferred from this discovery.

### W1 pre-production RED checkpoint

Development container `gnostoa:development-round3`, image
`sha256:43060627f698bbec7483733669590d1819a1ad6647bc1b0c33defa1cc4a8a280`,
ran the expanded focused file against unchanged fc842c7 production. Result:
**43 tests executed, three assertion failures in the one W1 method, zero
errors/skips**. Space-only, tab/CR/newline and Unicode em-space cause strings
all returned MATCH where INFRASTRUCTURE was required. The other 42 methods
passed. This is real RED on the production defect, separate from mutation
coverage characterization. No production edit preceded this result.

Command inside the readonly development-container workspace:
`python -m unittest discover -s tests -p test_qualification_report_validity.py -v`.
Production SHA-256:
`cd73df999efcce6dcd15f047801e60b04b4b78a9864dee7cf739c24ca1884e75`;
43-test SHA-256:
`e8d6d2357b4fd56976c558877fa66751cf10a1768bdf03fa0b1cb436313188b9`;
RED log SHA-256: `ce699c289644dbcbfeb5bb6041f2c2e8016ed80c02876ed21c0b9ba551debdbb`.
Raw log: `/tmp/gnostoa-222-round3-red.log` (session-local).

The six valid isolated N1/N5/N8/N9/N13/N15 mutations each compiled/imported
and survived the original 35 tests with no failures, errors or skips; their
original-vs-mutant probes distinguished false MATCH, false rejection and
escaped runtime errors separately. Those pre-change results remain under
`/tmp/gnostoa-222-round3/baseline-35-results.json`.

The separate proposal for repeatable mutation verification is captured in
[#224](https://github.com/ktogias/gnostoa/issues/224), linked to #15 and #219.
Its desired outcome, finite acceptance criteria, exclusions and explicit later
admission condition are recorded; it is OPEN backlog without `roadmap:now`.
No tool, mandatory gate or implementation was admitted. #202 remains the
unadmitted owner of pinned real-pytest/OCI evidence.

### Third-round repair and independent semantic reconciliation

The RED checkpoint is retained in Git commit `25d9c19` and in
[the pre-production Work Item record](https://github.com/ktogias/gnostoa/issues/219#issuecomment-5602189795),
read back verbatim before production mutation. The repair adds `.strip()` only
to the failed-case missing-cause predicate. It does not rewrite the stored cause
or change classification of any nonblank cause. Existing validation establishes
that this value is a string before the predicate; the added operation therefore
does not introduce a new type assumption.

The final eight new methods cover N13 unknown outcomes, N15 malformed summary
items, N1 decorated positive controls and contradictory infrastructure evidence,
N9 nonempty non-mapping cases, N5 missing/nonboolean collection status, N8
missing/empty causes and W1 whitespace-only cause through local JSON ingestion.
All new methods assert observable classifications, with cause preservation on
the decorated valid controls. N9/N15 additionally fail if a runtime exception
escapes; they do not reclassify a crash as false MATCH.

Independent agent review formed a task-to-code view and confirmed W1 violates
the existing completeness/cause obligation, then reviewed the actual one-line
repair and eight methods. Bounded **CODE REVIEW PASS** applies to production
SHA-256 `a5136810a1aa5c8b44c5e381a316bf04383c5ae1e899ea15869f6a00acbfd31d`
and tests SHA-256
`e8d6d2357b4fd56976c558877fa66751cf10a1768bdf03fa0b1cb436313188b9`.
This supersedes production-unchanged claims for the third-round repair; they
remain true of the earlier 5a1fb4e→fc842c7 delta. The review found no further
blocker in the declared set, supplies no human approval and does not establish
arbitrary cause-string correctness or exhaustive report validation.

### Final third-round behavior and mutation results

Development-container unmodified repaired baseline: **43 tests PASS, zero
failures/errors/skips**. Each transformation below targets exactly one occurrence
in the bound production source and compiles/imports successfully. N1 replaces
ANSI normalization with raw stdout; N5/N8/N9/N13/N15 replace the selected `if`
predicate with `False`; W1 replaces only the new `.strip()` predicate with the
prior empty-string predicate. The actual source condition and tests in Git make
the finite operators inspectable without presenting `/tmp` as permanent storage.

| Row | Exact selected source condition / operation | Before correction | Final 43 tests | Alignment / executor / agent reviewer |
|---|---|---|---|---|
| R3-N1 | `_ANSI_ESCAPE.sub("", stdout)` → `stdout` | SURVIVED 35; valid colored controls lose MATCH, contradictory colored infrastructure can gain MATCH. | KILLED: 3 assertion failures, zero errors. | SUPPORTS / complete / PASS |
| R3-N5 | `collected is not True` → `False` | SURVIVED 35; otherwise valid uncollected/nonboolean reports gain MATCH. | KILLED: 5 assertion failures, zero errors. | SUPPORTS / complete / PASS |
| R3-N8 | `outcome == "failed" and not error_type.strip()` → `False` (baseline targeted prior predicate) | Prior guard removal SURVIVED 35; absent cause gains MATCH. | KILLED: 6 assertion failures, zero errors. | SUPPORTS / complete / PASS |
| R3-N9 | `not isinstance(raw_cases, Mapping)` → `False` | SURVIVED 35; a nonempty non-mapping value escapes as AttributeError. | KILLED: 3 runtime errors, zero assertion failures. | SUPPORTS structured rejection / complete / PASS |
| R3-N13 | `label is None` → `False` | SURVIVED 35; unknown summary label can disappear behind matching known counts. | KILLED: 2 assertion failures, zero errors. | SUPPORTS / complete / PASS |
| R3-N15 | `item is None` → `False` | SURVIVED 35; malformed summary item escapes as TypeError. | KILLED: 3 runtime errors, zero assertion failures. | SUPPORTS structured rejection / complete / PASS |
| R3-W1 | `not error_type.strip()` → `not error_type` in the failed-case guard | Current-production RED: 3 whitespace subcases returned MATCH. | Exact repair revert KILLED: 3 assertion failures, zero errors. | SUPPORTS / repaired / PASS |
| R3-R1 | Actual fc842c7 diff and M11 passed-case branch | Missing-test hypothesis contradicted by source. | Corrected ledger, no duplicate M11 test. | SUPPORTS / reconciled / PASS |
| R3-X1 | Existing positive controls and Q01–Q11 plus M9/M11–M14 | Prior inventory retained. | All 16 specified mutations killed against 43 tests. | SUPPORTS bounded regression claim / complete / PASS |

The combined inventory is **23 specified valid mutants killed**: 20 have
behavioral/cause assertion discriminators, Q02 remains diagnostic-only, and
N9/N15 are killed by escaped runtime errors. All seven new and sixteen retained
mutants execute all 43 tests with zero skips. This is neither 23 false-MATCH
proofs nor an exhaustive score; no invalid mutation is counted. ANSI strings
and the unknown `rerun` label are synthetic report inputs, not a new claim about
actual plugin/version behavior. N12/N7 remain supplied observations outside the
selected finite inventory, with their existing production guards retained.

The admitted finite correction is complete at source/targeted-evidence level.
Whole-candidate container/runtime/provider results and exact Git identities must
be read from the final PR checkpoint; they are not inferred from the focused
suite or the prior fc842c7 green checks.

## Fourth review round: normalize the observed cause at ingestion

The owner supplied Grok, Kimi, Gemini and Claude reviews of
`2933f4cd5f70a05f349d28ccf88eac10a1531f49` and an explicit proposed two-line patch, continuing the selected review-and-
correct task under #219. This initial record was written
at `2026-09-09T13:23:45Z`, before this round's production mutation. The proposed
surface is `_classify`'s cause assignment and subsequent missing-cause predicate,
the same focused test module and this assessment. Decision 0059 §G supplies the
cause obligation; stripping outer whitespace is the implementation selected
for this correction, not a prescribed named-function or string operation in
the Decision. Independent reproduction and RED remain required before repair.

### Attributed claims and reconciliation

These labels identify owner-supplied reviews, not verified authorship or
execution. Prior results remain historical; the new candidate's checks cannot
be inferred from agreement among reviewers.

| Source / selector | Supplied claim | Reconciliation |
|---|---|---|
| R4-GROK | GO; W1 corrected; eight new methods, 43 focused/640 total tests and 23 specified mutants, with distinct assertion/runtime-error results. | The prior checkpoint supports the bounded counts and distinctions. This is review of 2933f4c, not acceptance of the newly reported padded-cause behavior or future head. |
| R4-KIMI-1 | Accepts repair but asks whether `.strip()` is safe for None and suggests explanatory comment; proposes `assertRaises` for N9/N15. | Existing type validation and `raw_error_type or ""` make the current guard's value a string. The selected new assignment must retain None handling and reject other invalid types. Reject the `assertRaises` suggestion: the contract requires structured INFRASTRUCTURE; an escaped exception must fail the normal test. |
| R4-KIMI-2 | Says all new mutations survived the original 35 tests; requests missing exact-head CI rerun. | Only N1/N5/N8/N9/N13/N15 survived that baseline. W1 was an actual production defect: expanded 43-test RED had three failing whitespace subcases. Required 2933f4c PR checks already completed; a changed head requires new checks. |
| R4-GEMINI | Task-170 extended quality summary/MkDocs PASS and task-166 host-only diagnosis; all-green/GO claims. | Task labels and external summaries lack supplied raw logs/environment binding and remain claims. They do not establish a host defect or another required repair. “100% green” cannot turn the two existing OCI skips into executed PASS. |
| R4-CLAUDE-1 | Padded `" OSError "`, `"OSError\n"` and `" builtins.OSError "` still MATCH; current emitters do not produce padding, but malformed normalized reports expose the same boundary as W1. Proposes assignment-level strip and plain empty guard; allows a passed blank cause to mean no error. | This is a material new hypothesis within the existing report-validity scope, selected for independent RED→GREEN within the resumed review-and-correct task. Synthetic reachability does not prove current emitter or historical receipt impact. |
| R4-CLAUDE-2 | Supplied patch passes 640 tests, external pytest 9.1.1/color probes and nine mutants; N1 and crash gaps closed. | Prior admitted evidence supports the scoped earlier closures. New patch/mutation and external pytest executions are supplied claims until their exact inputs, environment and raw results are independently bound; no dependency acquisition or OCI claim follows. |
| R4-CLAUDE-3 / separate boundaries | Receipt loading may trust retained classification; systematic mutation gates remain a future question. | Receipt-load/retained-evidence admissibility belongs to #216; the mutation-capability proposal is tracked by #224. Neither is implementation-admitted here. #202 still owns unadmitted pinned real-pytest/OCI evidence. |

Provider read-back binds OPEN/non-draft #222 to 2933f4c. The completed
[PR workflow](https://github.com/ktogias/gnostoa/actions/runs/34354475252) ran
successful policy, fast, Python 3.11/3.12, regression and smoke, including
[exact candidate binding](https://github.com/ktogias/gnostoa/actions/runs/34354475252/job/102476921053).
Source suites counted 640 tests: 638 passed and two existing OCI skips.
Provider extended was SKIPPED by event routing; earlier local extended results
are separate evidence. These observations correct a missing-CI claim without
predicting this round's result.

### Initial behavior map and intentional normalization boundary

The proposed assignment strips outer whitespace only after validating the raw
type, using an empty string for None. The missing-cause check then tests that
normalized value directly. This **supersedes** the prior W1 requirement to
preserve every nonblank cause byte: stored and compared cause strings will now
omit outer whitespace. No case folding, internal-whitespace repair, arbitrary
exception-name reinterpretation or receipt migration is selected.

All new evidence states initially are **NOT RUN**, alignment **UNKNOWN**,
executor **PENDING**, reviewer **PENDING**. The supplied counterexamples are
diagnostic hypotheses; #219's cause/completeness obligation supplies their
semantic authority, not agreement between new tests and the proposed patch.

| ID / selector | Required observable result and contradiction | Prospective evidence |
|---|---|---|
| R4-W2 / Claude padded infrastructure | Outer whitespace cannot hide a recognized infrastructure cause, including a qualified name; normalized cause identity is retained. Current 2933f4c behavior is under independent reproduction. | Synthetic normalized-report and local-JSON padded-cause RED, followed by the unchanged classifier infrastructure comparison after assignment normalization. |
| R4-P1 / owner-selected normalization | Padded ordinary behavioral causes retain their behavioral classification and normalized identity; unpadded causes retain existing meaning. | Assertion/explicit-failure controls, qualified cause controls and cause-value assertions. |
| R4-T1 / Kimi None and invalid types | Failed cases with None, absent, empty or whitespace-only cause are INFRASTRUCTURE without an escaped exception; other non-string types remain rejected. | Focused None/type/W1 controls through existing validation and selected assignment. |
| R4-P2 / selected passed-blank semantics | A passed case with absent/None/blank cause has no error; a passed case with a normalized nonempty cause remains contradictory and is rejected. | Passed-report positive and contradictory negative controls; no blanket weakening of report validity. |
| R4-X1 / existing guard obligations | N9/N15 remain structured rejections; previous positive/negative controls survive; no retained-receipt, CI, dependency or authority change. | Bounded regression/mutation replay, source diff, applicable container/runtime suites and new exact-head provider read-back. |

The finite completion boundary is independently reproduced padded-cause RED,
the selected normalization and controls, applicable verification, and exact
candidate review. New mutation counts remain sampled; invalid mutants, crash
discriminators and cause assertions must remain distinct. Session-local raw
replays do not become durable artifacts merely by listing their `/tmp` paths.
Final candidate, actual results and independent reviewer disposition remain
**PENDING**. Merge, issue closure, #216/#224 implementation and Phase-D effects
remain unadmitted.

### Fourth-round RED before production mutation

The expanded 47-test file ran in development image
`sha256:2ea98a155a9b704d2ad59f7a5c18c0d4657891a647bde99a514e128f205a0f6d`
against unchanged 2933f4c production. **14 assertion failures, zero errors/skips**:
nine padded-infrastructure subcases, three padded-behavioral cause-identity
subcases and two passed-blank subcases. Eight of the infrastructure subcases
returned false MATCH; the leading-only qualified-name subcase already rejected
infrastructure but retained the padded name. That distinction matters: not all
14 failures are false qualification. The invalid-type controls and original
43 methods remain passing. None handling is therefore directly exercised as
well as justified by source inspection; no comment-only assertion is needed.

Command in the readonly development-container workspace:
`python -m unittest discover -s tests -p test_qualification_report_validity.py -v`.
The raw local JSON is synthetic transport evidence, not a claim that current
pytest or harness emitters produce padded names. The selected correction now
normalizes stored/comparable type names while leaving exception-name case and
internal spelling unchanged. Existing guardrail coverage and Decision cause
semantics remain; no normative policy or public schema change is selected.

Production SHA-256 before repair:
`a5136810a1aa5c8b44c5e381a316bf04383c5ae1e899ea15869f6a00acbfd31d`;
47-test SHA-256:
`23c86957a1923dcee633071ef63f48fc13f04c1ab35b824198e67986877bb087`.
RED log `/tmp/gnostoa-222-round4-red.log` SHA-256:
`a456b9451616586b9ff0de73472587efe5a3821804db29ec404b216a64d4fb1f` (session-local).

### Fourth-round correction and retained boundary

RED is retained at commit `ae94afc` and in the
[pre-production Work Item checkpoint](https://github.com/ktogias/gnostoa/issues/219#issuecomment-5602636635),
which was read back verbatim before the two-line production mutation. The
observed cause is now normalized at assignment after raw-type validation,
using `None` as absence, and all later checks use that same value. Unknown
non-string types still return structured INFRASTRUCTURE; no `None.strip()`
path exists. An added explanatory comment is unnecessary beside these explicit
adjacent operations and the passing missing/None/type regressions.

The four new methods exercise local JSON transport for padded infrastructure
causes, canonical behavioral names, passed-empty causes and invalid-type/passed-
nonblank rejection. Previous W1 tests continue to reject whitespace-only causes
on failed cases. Ordinary unpadded names keep their classification and spelling;
case folding and internal-name rewriting are deliberately outside this repair.

The completed focused run is **47 PASS**, zero failures/errors/skips, on
production SHA-256
`3b505ce11c04beea34416532a8b90cee169c9605cca7ca0cb5171c201532b305`
and tests SHA-256
`23c86957a1923dcee633071ef63f48fc13f04c1ab35b824198e67986877bb087`.
The separate reviewer baseline used 38 synthetic JSON transport cases and
found 12 differences from the selected normalization behavior at 2933f4c:
four false MATCHs, five canonical-name discrepancies and three passed-blank
rejections. Its inputs differ from the regression matrix; these counts must
not be merged with the 14-failure RED or presented as independent actual-pytest
observations.

Provider/source read-back confirms that #216 already owns receipt structural,
type and outcome validity beyond declared MATCH/hash equality, including prior
import, retained COMPLETE, READY and old-lock use. This review observation is
retained here with that existing ownership; no receipt-path implementation or
receipt execution was performed. Automatic approval review rejected an optional
cross-post to #216 because it did not find explicit authorization for that
payload/destination. That post was not made or retried through another route.
The permitted local/#219 record is sufficient for this task; implementation
admission for #216, #202 and #224 remains absent.

### Fourth-round final reconciliation and finite mutation evidence

Independent review of the actual two-line repair and four added test methods
reports bounded **CODE REVIEW PASS** on the source/test hashes above. All 38
independent synthetic JSON transport probes now SUPPORT their declared
normalization expectations, with zero contradictions or escaped exceptions.
This complements the 47-test GREEN but supplies no actual pytest/OCI or human
approval claim.

| Behavior row | Final evidence / alignment | Executor / independent agent reviewer |
|---|---|---|
| R4-W2 | Padded known infrastructure causes return INFRASTRUCTURE with canonical names; focused and independent probes PASS / SUPPORTS. | repaired / PASS |
| R4-P1 | Ordinary padded causes remain MATCH with canonical case-sensitive identities; clean controls remain valid / SUPPORTS. | normalized / PASS |
| R4-T1 | Missing/None/blank failed causes and invalid non-string types remain structured INFRASTRUCTURE / SUPPORTS. | preserved / PASS |
| R4-P2 | Passed blank causes mean no error; passed nonblank causes remain contradictory / SUPPORTS. | normalized / PASS |
| R4-X1 | All 22 still-applicable prior operators are killed; N9/N15 remain no-crash contracts, not assertRaises contracts / SUPPORTS. | reconciled / PASS |

The four selected new operators and their actual outcomes are:

| Mutation ID (separate from behavior IDs) | Exact selected transformation | Final result on 47 tests |
|---|---|---|
| R4.P1 | Replace `(raw_error_type or "").strip()` with `raw_error_type or ""` at assignment. | KILLED: 17 assertion failures, zero runtime errors. This also removes W1's protection, which now lives at assignment. |
| R4.P2 | Replace the raw non-string/non-None type-rejection predicate with False. | KILLED: 4 assertion failures and 6 runtime errors. Falsey invalid values can otherwise become absent causes; truthy invalid values cannot be stripped. |
| R4.P3 | Replace the passed-with-nonblank-cause rejection predicate with False. | KILLED: 2 assertion failures. Passed AssertionError reports demonstrate that this guard is load-bearing despite downstream protection on some infrastructure examples. |
| R4.P4 | Add `.casefold()` after assignment-level `.strip()`. | KILLED: 26 assertion failures, zero runtime errors. This counter-mutation protects case-sensitive cause identity; it is not a guard deletion. |

The active inventory is **26 specified valid operators**: 22 retained plus four
new. Outcomes are 23 assertion-only kills (including diagnostic-only Q02), two
runtime-error-only kills (N9/N15), and one mixed kill (R4.P2). All operators
compile/import and execute all 47 tests with zero skips. These categories are
not interchangeable false-MATCH proofs or an exhaustive score.

The old R3.W1 operator specifically removed `.strip()` from the failed-case
predicate. That target no longer exists after normalization moves upstream:
record it as **NOT APPLICABLE**, not a new kill or a surviving defect. Its
historical RED/kill remains valid at 2933f4c. Replaying only applicable operators
prevents a source change from manufacturing a stronger mutation count.

Full operator definitions and raw outputs remain session-local under
`/tmp/gnostoa-222-round4`; the tables, source bindings and dispositions are the
durable bounded record. Inventory SHA-256: `1505c8d0d46e9e6599ee681348e168718cb38c6cc2e6c89877ee4010e7ccb789`;
final mutation JSON SHA-256: `e391b46325ec19d98d7f62f6cf2aa7269474bfc02a1426a422f05abfeba1b594`; final probe JSON SHA-256:
`659737fc07a21d84aeed8ddb0189ac45a0d9200200cd69528c318cc3c5929961`. A broader durable replay/CI capability remains #224's unadmitted
outcome; mutation checks cannot prove completeness of the chosen semantic
inputs or automatically discover every untested family.

Local focused, policy, fast, regression and smoke checks have passed on the
bound executable source; the full source suite executes 644 tests, 642 passed
and the same two existing OCI skips. The final PR checkpoint owns completed
extended/runtime/provider results and exact candidate identities. No older CI
result or source identity is substituted for this changed candidate. Next is
human exact-head review, separate owner merge authority, then integration
read-back before any #219 closure.

## Fifth review round: normalization consensus and new provider findings

The owner supplied Grok, Kimi, Claude and Gemini reviews of unchanged
`b278923693bebab3bc2dede34d9c5c2cd28e1a01`. The initial read-back confirmed
tree `96d24aa1d5d51bb8cbd540ea68bab44932569a09` and the fourth-round
production/test hashes. Prior successful executions remain bound to that
candidate; no new execution is inferred from reviewer agreement.

### Review ledger

| Supplied review | Disposition and evidence limit |
| --- | --- |
| Grok | Its bounded GO conclusion, assignment normalization, four additional tests and active 26-operator inventory agree with the source and retained evidence. Scores are reviewer opinions. The `assertRaises` proposal was deliberately rejected because callers require a structured INFRASTRUCTURE outcome. The earlier #216 posting rejection remains a recorded tool decision; agreement about it supplies no new posting or implementation authorization. |
| Kimi | Source confirms the adjacent raw-type guard, canonical stored names, qualified infrastructure suffix comparison and all four actual methods. Two factual corrections: `[]` is falsey, and the raw guard rejects **all** non-None nonstrings, including falsey values, before the fallback/strip. The fourteen RED failures contain **eight**, not nine, false MATCHs; see the breakdown below. “All edge cases” exceeds the finite sample. This is a behavior-changing correctness repair, including normalization of stored padded causes, rather than a purely behavior-preserving refactor. |
| Claude | Exact patch/blob identity and the normalization conclusions agree with our bound source/evidence. Its fourteen selected mutants and statement that no new finding emerged are attributed reviewer results, not an additional fourteen entries in the repository's 26-operator inventory. The reviewer’s current “W1” label denotes assignment normalization and must not be confused with retired repository operator R3.W1. Neighboring-name, terminal-summary and real-pytest/color probes remain supplied execution claims without complete bound inputs/raw logs. “Family closed” and “the curve flattened” describe that inspected sample, not a proof of completeness or convergence. |
| Gemini | Its stated 47 focused / 644 total / 26 active results agree with separately retained acceptance evidence. The referenced `219_pr222_deep_code_review.md` and task-194 raw output were not supplied here, so those particular artifact/execution claims remain attributed. The full source result is 642 passed plus two existing skips; “100% green” does not convert those skips into executed tests. |

### Independent source read-back

The current production blob remains `33eb7e5d2ecbdcf6a8b70082fcf4c18ad8d3f02b`. At [qualification.py lines 574–605](https://github.com/ktogias/gnostoa/blob/b278923693bebab3bc2dede34d9c5c2cd28e1a01/tools/capsule/qualification.py#L574), validation precedes `(raw_error_type or "").strip()`; the same normalized value then controls passed/failed consistency and stored cause identity. None becomes absence: a failed case with None is rejected, while a passed case with None can satisfy its otherwise valid expectation. There is no `None.strip()` path. Infrastructure comparison at line 614 uses the terminal component of the normalized qualified name. The four methods at [test lines 624–659](https://github.com/ktogias/gnostoa/blob/b278923693bebab3bc2dede34d9c5c2cd28e1a01/tests/test_qualification_report_validity.py#L624) assert both classifications and relevant canonical identities through mocked local JSON transport. They do not claim that current emitters produce padded names.

The retained RED at `ae94afc` has fourteen assertion failures: eight infrastructure false MATCHs, one already-rejected infrastructure case with a noncanonical name, three behavioral-name discrepancies, and two passed-blank false rejections. These categories were already explicit in the assessment and original checkpoint. The correction retains case-sensitive exception identities and existing blank-failed/type-rejection behavior.

Claude's two new terminal-summary examples need a narrower interpretation. Source selects the last syntactically matching summary and cross-checks its supported outcomes/counts against parsed cases and process exit. A later summary with different counts is rejected. Count equality alone does not authenticate a summary's origin or establish rejection of every forged, count-consistent summary. The supplied examples have no complete inputs here and do not establish that broader claim. This is a limit on the review's inference, not a newly reproduced #219 defect or an admission to implement report authentication.

These four supplied reviews do not identify an additional defect in the normalization repair. The newer provider findings below require their own disposition. The sampled mutation record remains 26 applicable operators: 23 assertion-only kills (including diagnostic-only Q02), two runtime-error-only kills, and one mixed kill; historical R3.W1 remains NOT APPLICABLE at this source. No exhaustive coverage claim is made.

### Newly observed provider review and scope disposition

Fresh provider state adds [Devin review 5155274684](https://github.com/ktogias/gnostoa/pull/222#pullrequestreview-5155274684)
at b278923. Its two current unresolved threads change mergeability from clean
to BLOCKED: protected main requires conversation resolution. Existing exact-head
CI and candidate binding still PASS. No human review or merge authority follows.

| Finding | Independent observation | Disposition |
| --- | --- | --- |
| R5-D1 / prospective permitted causes, [thread 3969225122](https://github.com/ktogias/gnostoa/pull/222#discussion_r3969225122) | Current expectations have counts and discriminator names, not prospective per-case permitted causes. A synthetic report for the correct failing case produces MATCH for AssertionError and ValueError, INFRASTRUCTURE for OSError. This demonstrates the existing distinction, not that every ValueError is wrong or that a real experiment was affected. Decision 0059 §G is broader than this implemented comparison. | Capture-only [Work Item #225](https://github.com/ktogias/gnostoa/issues/225), following provider search for an existing owner. The suggested expectation/compiler/receipt-identity expansion crosses #219's explicit stop boundary. Separate owner admission must select the contract and compatibility treatment. Do not invent AssertionError-only behavior in this repair. |
| R5-D2 / local launch OSError, [thread 3969225275](https://github.com/ktogias/gnostoa/pull/222#discussion_r3969225275) | subprocess.run OSError escapes the TimeoutExpired-only catch, qualify_subjects and compiler's normal structured result path. Read-only container probes independently observed escaped FileNotFoundError, PermissionError and BlockingIOError. The one-shot claim precedes qualification. | Resume #219's already admitted local subprocess completion/report boundary, adding only structured OSError normalization. This is an escaped-exception defect, not a false MATCH. Catching it does not restore consumed claims or retry authority; no ordering, rollback, routing or receipt-schema change is selected. |

The existing [owner admission](https://github.com/ktogias/gnostoa/issues/219#issuecomment-5600207947)
explicitly includes local-python subprocess completion/report consistency. The
[continuing admission](https://github.com/ktogias/gnostoa/issues/219#issuecomment-5600791269)
selects the smallest deterministic result-completion contract preserving process
validity. Together with the continuing owner review-and-correct instruction,
these authorize the bounded R5-D2 correction without repeating permission.
A reviewer initially recommended renewed selection if the outcome were outside
that boundary; checking the actual admission text resolves that question for
D2 only. D1 remains unadmitted under #225.

No hidden oracle, actual failing subprocess, claim, retained receipt or experiment
was executed for the diagnostics. Source was mounted readonly in the existing
development image, with subprocess.run mocked to raise and synthetic reports
passed directly to the real classifier. The observed built-in OSError constructor
with errno 11 produces BlockingIOError; this is an OSError subclass, not an
additional independent generic-OSError probe. These are scenario reproductions,
not evidence of an incident or a consumed real claim.

### Fifth-round prospective map before production mutation

Baseline production is b278923, SHA-256
`3b505ce11c04beea34416532a8b90cee169c9605cca7ca0cb5171c201532b305`.
Classification remains critical under Decision 0059 §G and existing #219 authority.
Only qualification.py, its focused test file and this assessment are selected.

| ID / authority selector | Expected behavior and proposed path | Evidence / initial state | Alignment; executor / reviewer |
| --- | --- | --- | --- |
| R5-L1 / D2 and admitted local completion contract | OSError and subclasses during local subprocess launch yield structured INFRASTRUCTURE with cause detail and collected=False; no escaped exception and no qualified receipt. Add OSError catch returning _invalid_report. | Synthetic base/reference launch-error matrix through real qualify_subjects; regression RED NOT RUN at map creation. Source and separate diagnostic probes establish the current escape. | UNKNOWN; PENDING / PENDING |
| R5-L2 / existing valid qualification and timeout contract | The other completed subject keeps its normal MATCH; timeout remains structured INFRASTRUCTURE, valid BASE exit-1 and REFERENCE successes remain valid. | Existing focused controls plus good-subject assertions in the launch-error matrix; new regression NOT RUN. | UNKNOWN; PENDING / PENDING |
| R5-X1 / admission effect boundary | No reset/retry or claim-order change, expectation extension, schema change or new execution authority. | Exact diff review and existing applicable regression/container/runtime checks; NOT RUN for candidate. | UNKNOWN; PENDING / PENDING |
| R5-D1 / separate contract gap | Preserve observation and explicit implementation stop under #225; do not claim complete prospective cause enforcement from #219. | Provider read-back of focused backlog capture; implementation NOT ADMITTED. | Scope retained; captured / PENDING |

The regression must precede production mutation. The final assessment/checkpoint
will record actual RED, candidate hashes, selected mutation and exact-head checks.
No prior candidate's GREEN is substituted after the catch changes. Both provider
conversations need a recorded disposition; no agent review supplies human semantic
approval or owner merge authority.

### Fifth-round RED checkpoint

The added integrated regression ran through `qualify_subjects` in the readonly
development container against unchanged b278923 production: **48 tests, eight
runtime errors, zero assertion failures/skips**. Each of four exceptions
(FileNotFoundError, PermissionError, BlockingIOError and generic OSError) escapes
when injected into either BASE or REFERENCE subprocess launch. The other 47
methods pass. These are missing structured-result errors, not eight false MATCHs.
The matching other-subject control is part of the prospective regression; it
cannot yet be reached after an escaped exception.

Command: `python -m unittest discover -s tests -p test_qualification_report_validity.py -v`
in development image
`sha256:2ea98a155a9b704d2ad59f7a5c18c0d4657891a647bde99a514e128f205a0f6d`.
Production SHA-256 remains
`3b505ce11c04beea34416532a8b90cee169c9605cca7ca0cb5171c201532b305`;
48-test SHA-256 is
`fd6a2b26bd5d9cd07778063f9d617cd54ce6ed0e116e5dad4457c9a61679a7e0`.
Session-local RED log SHA-256:
`84c6c1e3253d817b72577f49acb100ef9a375906f0fc0e268d78afc78748a8f9`.
Ruff format with `--no-cache --check tools ci tests` passes (117 files).
The first formatter invocation could not create its cache on the readonly
mount; the no-cache retry executed successfully, rather than counting that
setup failure as formatting evidence.

R5-L1 is currently CONTRADICTS / executor RED, reviewer PENDING. The chosen
production catch is not yet applied. #225 was read back verbatim as OPEN with
no active-work label and explicit implementation admission condition.

### Fifth-round bounded repair

RED commit `4832d20` was pushed, and the
[prospective map and RED checkpoint](https://github.com/ktogias/gnostoa/issues/219#issuecomment-5603202183)
were read back verbatim before production mutation. The selected four-line
`except OSError` branch now returns `_invalid_report` with the original concrete
exception type and message. The detail says "process failed": subprocess.run can
raise OSError while creating or interacting with a child, so the catch does not
assert that every occurrence proves no process started. The existing timeout
branch remains unchanged.

Production SHA-256 is now
`7ef013df0a99d0411922d6e21ea75e3cd173bb6906b2093347bb847f97236c60`;
48-test SHA-256 remains
`fd6a2b26bd5d9cd07778063f9d617cd54ce6ed0e116e5dad4457c9a61679a7e0`.
Independent development-container execution reports **48 PASS**, zero
failures/errors/skips. Each injected BASE/REFERENCE launch failure yields an
unqualified receipt with structured INFRASTRUCTURE, collected=False and concrete
cause detail, while the other subject remains MATCH. The existing 47 methods
also pass. R5-L1/L2 now SUPPORTS; executor corrected, independent agent code
review PASS on these hashes. This is not a claim-reset, retry or historical
receipt repair.

R5-X1 source review confirms only the local catch, integrated regression and
assessment changed in this round. Compiler, expectation structure, receipt
schema, claim ordering and authority remain unchanged. R5-D1 is retained under
unadmitted #225 and [replied to in its originating thread](https://github.com/ktogias/gnostoa/pull/222#discussion_r3969378834).
The existing report validity repair must not be described as complete comparison
against every prospective permitted cause. Forwarded model reviews and bot
conversation disposition do not supply human semantic approval.

The final PR checkpoint will bind this candidate to completed local named suites,
mutation replay, runtime self-check, exact-head provider checks and both review
thread dispositions. Until those results are recorded, their state is PENDING;
no old-head PASS or earlier clean mergeability substitutes for them. #202, #216,
#224 and #225 remain separate and unadmitted. Merge, closure and Phase-D effects
remain outside the task's authorization.

### Fifth-round mutation and independent review read-back

The independent replay retains the prior 26 operator definitions unchanged and
adds exactly R5.L1: remove the new four-line OSError catch. Every operator
compiles/imports and executes all 48 tests without skips. **27 applicable
operators are detected**: 23 assertion-only (including diagnostic-only Q02),
three runtime-error-only (N9, N15 and R5.L1), and one mixed (raw cause-type guard).
R3.W1 remains NOT APPLICABLE. These are finite operators, not 27 false-MATCH
proofs or exhaustive coverage. The N5 mutation now also violates collected=False
assertions in the new matrix; operator identity and its interpretation remain.

R5.L1 restores the exact b278923 production SHA-256 and produces eight escaped
runtime errors, zero assertion failures. This independently links the new
regression to the intended missing structured-result contract, rather than
mistaking a syntax/import failure for a useful mutation. The unmodified candidate
has 48 PASS. Independent agent review is bounded CODE REVIEW PASS; R5-L1/L2/X1
SUPPORTS, with the separate #225 implementation stop preserved. Final provider
conversation disposition and all applicable checks remain owned by the final
exact-candidate checkpoint, not by the agent review verdict alone.

The retained session-local report is `/tmp/gnostoa-222-round5-review.md`, SHA-256
`b7ec45ac8ce615049baa217018684a24addc28148ab8feeef356984d368bd8fb`.
Mutation results SHA-256:
`22b0cfdd19450971cdc67d7b6a749550aac60725ba8cda13204eb51959ec4ce8`;
operator inventory SHA-256:
`1abc4854e99ea6cd75e65cd8b290849c706390e9fc17a25a6efe54f5cca34661`.
Raw artifacts remain session-local. The durable source, regression, operator
transformation and result categories above make the bounded claim inspectable.

## Sixth review round: local output decoding before a report exists

Starting candidate `7740ce37107fa68b6b63221109f8e8225323cc65`, tree
`5f15a9e164267b490254fa76b2dd82d622eec15d`, production blob
`66a95035917c0da18ddc0ecb479f92037f49ad8e`. Fresh provider read-back confirms
OPEN/non-draft/unmerged and CLEAN. Both earlier threads were resolved under
the owner's separate explicit authorization; that authorization did not admit
merge or #225 implementation. Prior exact-head CI remains successful, with
provider extended SKIPPED and actual local extended evidence separate. These
are baseline facts, not results for a future source change.

## Attributed claim ledger

| ID | Supplied claim | Reconciliation |
|---|---|---|
| R6-CLAUDE-1 | Existing four-line OSError repair is correct; RED 4832d20 has eight escaped errors and head has 48 PASS. | Matches the retained source/assessment and provider evidence. Eight errors are structured-result escape failures, not eight false MATCHs. Source snapshot confirms the stated head/tree/blob. |
| R6-CLAUDE-2 | Raw invalid bytes cause UnicodeDecodeError in local text decoding; errors="replace" prevents it. | Concrete same-boundary proposed defect and repair, to be independently reproduced by the implementation task. Source confirms text=True without errors= and an OSError/TimeoutExpired-only catch; UnicodeDecodeError is not an OSError. The existing OCI reader uses errors="replace". A proposed one-line patch and claimed successful test run do not substitute for the new RED/behavior contract. Replacement of undecodable diagnostics and integrity of the final report must be distinguished when selecting behavior. |
| R6-CLAUDE-3 | Escape occurs after the fresh effect claim, before normal completion. | Compiler source confirms claim_fresh_candidate precedes qualify_subjects and the direct call has no surrounding catch at that point. This supports the ordering concern. No retained recovery, unrecoverability, historical impact or new retry authority was demonstrated; #207 recovery was explicitly not tested. |
| R6-CLAUDE-4 | 17 mutants, 16 killed; broadening TimeoutExpired to SubprocessError is an equivalent survivor. | Preserve as external, finite supplied results. For the shown ordinary invocation with check=False and no preexec_fn, the explanation is plausible; survival alone does not prove universal semantic equivalence over platforms, implementations or altered call parameters. No additional mutation test is demanded merely to kill this reported survivor. Claude's L2 is not a new repository operator. |
| R6-CLAUDE-5 | Normalization axis exhausted; local runner is the only possible external exception point; adding this line closes the second axis. | These universal/convergence claims exceed the finite inputs and source scope inspected. No exhaustive proof was supplied. Keep the bounded no-regression observations and specific new defect; do not claim every exception/report-adversary axis is closed. |
| R6-CLAUDE-6 | Real pytest 9.1.1, ANSI, S1 and formatting/policy runs pass. | Attributed external execution claims. Prior disclosure was an ad-hoc Python 3.12 cloud environment, not the project's pinned OCI fixture; new raw outputs/environment identities were not supplied here. They neither satisfy #202 nor count as an additional mandatory provider run. |
| R6-GROK-1 | Correct minimal OSError normalization; boundary belongs to admitted #219; broader permitted causes deferred to #225; 48/645 and 27 operators. | Supported by the retained bounded record and current source. Scores and GO recommendation remain opinions. “No known blocker” reflects the information reviewed and does not dispose of Claude's newly supplied decoding counterexample. |
| R6-KIMI-1 | Test covers eight exception/subject combinations, preserves the other subject and structured receipt; asserts aid narrowing. | Accurate bounded description of the prior regression. Four exception classes across two subjects are not all subprocess/environment edge cases. Catching the OSError hierarchy does not cover every possible environment-related failure; the new decoding observation demonstrates another exception family. |
| R6-KIMI-2 | 27 operators with a table listing N15 and R4.P2 among assertion-only kills and R5.L2 control. | Correct totals are 23 assertion-only, including diagnostic-only Q02; three runtime-only N9/N15/R5.L1; one mixed R4.P2. Q02 is a subset, not a 28th category. R3.W1 is historical NOT APPLICABLE and not counted. R5-L2 in the independent review is a probe label, not an added mutation operator; no repository R5.L2 control belongs in the 27-operator inventory. Do not combine Claude's separate labels/count with repository inventory. |
| R6-KIMI-3 | Final disposition says 644 total tests and unresolved threads block merge. | Correct total at 7740ce3 is 645, with 643 passes and two OCI skips. Threads have since been resolved under explicit owner authorization and current provider state is CLEAN. The assessment's older unresolved snapshot remains historical, not a current blocker. |
| R6-GEMINI-1 | 48 focused, 645 total/643 passes/two skips, 27 active operators, task-220 extended and review artifact updated; GO-ready. | Counts agree with retained project evidence. Unprovided task-220 logs and `219_pr222_deep_code_review.md` remain attributed claims, not newly bound session artifacts. Provider extended was skipped; separate container success is a distinct evidence source. No “100%” or GO label eliminates two skipped OCI checks or the newly supplied decoding defect. |

The prior repair remains a bounded improvement. The latest actionable finding should receive a narrow RED/GREEN disposition inside #219 before any revised exact-head technical verdict. Human semantic review and separate owner squash-merge authorization remain pending; integration read-back precedes any eventual #219 closure.

### Independent diagnostic comparison and selected correction

The governing local completion/report contract remains the existing #219
admission under Decision 0059 §G: a failure to decode captured output must
produce a structured refusal rather than escape; a malformed report must not
be rewritten into accepted evidence. Python's [subprocess documentation](https://docs.python.org/3.12/library/subprocess.html)
explains text-mode decoding and errors handling; [exception documentation](https://docs.python.org/3.12/library/exceptions.html#UnicodeDecodeError)
places UnicodeDecodeError under UnicodeError/ValueError, outside OSError.
Those language facts explain the path but do not select qualification policy.

An independent agent ran 15 actual child-process probes in the existing,
confirmed development image with readonly source and network disabled. Five
synthetic scenarios ran on each of unmodified production, the supplied
errors="replace" variant and a narrow strict-decoding catch variant:

| Scenario | 7740ce3 | Supplied replacement | Strict decoding + structured catch |
| --- | --- | --- | --- |
| Invalid bytes before terminal JSON on stdout | UnicodeDecodeError escapes | MATCH | INFRASTRUCTURE / collected=False |
| Invalid bytes on stderr | UnicodeDecodeError escapes | MATCH | INFRASTRUCTURE / collected=False |
| Invalid byte inside terminal JSON cause OSError | UnicodeDecodeError escapes | MATCH, stored cause `OSError�` | INFRASTRUCTURE / collected=False |
| Valid Unicode diagnostic output with BASE assertion | MATCH | MATCH | MATCH |
| Valid REFERENCE report | MATCH | MATCH | MATCH |

The malformed terminal-report case is a deliberate synthetic transport
counterexample: an atexit callback flushes normal stdout then emits corrupted
JSON. It does not claim that ordinary json.dumps emits invalid UTF-8, that a
historical receipt was affected, or that this parser authenticates arbitrary
malicious output. The first diagnostic attempt lacked the explicit flush and
therefore exercised noise/buffer ordering instead of proving the terminal-cause
claim; its output remains separate from the corrected, final 15-probe matrix.

**Select a narrow UnicodeDecodeError catch returning _invalid_report and preserve
strict decoding.** The supplied replacement patch is rejected because it can
construct an accepted non-infrastructure cause from undecodable report bytes.
Undecodable stdout or stderr, even if it looks like diagnostic noise before a
valid report, remains an invalid transport under this conservative boundary.
Tolerating arbitrary binary diagnostic streams is not selected. Valid Unicode
output remains supported. The existing OCI replacement reader is a precedent
for different behavior, not authority to weaken the local report-validity
boundary or to modify OCI here. No broader UnicodeError/ValueError catch,
compiler exception wrapper, retry, recovery or locale/encoding change is selected.

Source confirms the claim occurs before qualify_subjects, but these probes
execute no compiler claim, private oracle, retained transaction or recovery.
They reproduce a raw-output decoding scenario and its structured refusal; they
do not establish unrecoverability or prove that every subprocess exception axis
is closed. Tests and probe variants are authored diagnostic evidence; #219's
report-validity obligation, rather than their mutual agreement, supplies the
semantic authority for refusing undecodable evidence.

### Sixth-round prospective behavior map before production mutation

Classification remains critical. Baseline production SHA-256 is
`7ef013df0a99d0411922d6e21ea75e3cd173bb6906b2093347bb847f97236c60`.
Selected source paths remain qualification.py, the existing focused test file
and this assessment. Initial regression/verification states below are NOT RUN;
independent diagnostic results above do not impersonate a committed RED suite.

| ID / authority selector | Required observable behavior | Proposed implementation / evidence | Initial alignment; executor / reviewer |
| --- | --- | --- | --- |
| R6-U1 / Claude decoding escape and admitted local report contract | Undecodable stdout and stderr return structured INFRASTRUCTURE, collected=False, with decoding cause; no escaped exception. | Narrow UnicodeDecodeError catch; two actual-process byte-output regressions, NOT RUN. | UNKNOWN; PENDING / PENDING |
| R6-U2 / #219 malformed-report and preserved-cause obligation | A terminal JSON cause containing an invalid byte cannot be replaced into an accepted behavioral cause. | Keep strict decoding; real-process atexit corrupted terminal report and replacement counter-mutation, NOT RUN. | UNKNOWN; PENDING / PENDING |
| R6-P1 / existing valid qualification | Valid Unicode diagnostics retain BASE AssertionError identity/MATCH and REFERENCE success/MATCH. | Real local process positive controls, plus previous 48 methods, NOT RUN. | UNKNOWN; PENDING / PENDING |
| R6-X1 / existing admission and effect boundary | No claim/reset/retry/recovery, compiler, receipt/schema, dependency, OCI or authority change; no exhaustion claim. | Exact diff and existing bounded regression/mutation/container/runtime/provider checks, NOT RUN for candidate. | UNKNOWN; PENDING / PENDING |

RED must precede production mutation and be retained in Git and the active
Work Item before the catch is applied. #202/#216/#224/#225 remain unadmitted;
no new issue duplicates this already-owned local completion outcome. Thread
resolution authority already exercised for the two older findings does not
supply a new merge, closure or launch authorization.

### Sixth-round RED before production mutation

The expanded focused suite ran in the readonly development container against
unchanged 7740ce3 production: **51 tests, three runtime errors, zero assertion
failures/skips**. The errors are UnicodeDecodeError from invalid stdout bytes,
invalid stderr bytes and the corrupted terminal JSON cause. Previous 48 methods
and both new valid-Unicode BASE/REFERENCE controls pass. This is an escaped-
exception RED, not three existing false MATCHs; false acceptance was observed
only in the independently evaluated replacement proposal.

Command: `python -m unittest discover -s tests -p test_qualification_report_validity.py -v`.
Development image:
`sha256:10880e493693f23e362099767c5352e65df5e83b446d5c11d73c9f611ef36c01`.
Production SHA-256 remains
`7ef013df0a99d0411922d6e21ea75e3cd173bb6906b2093347bb847f97236c60`;
expanded-test SHA-256:
`fbc3452e9dd4730944bdb8639013178f16f433bb9d03de23638be5d9eee70d32`.
Session-local RED log `/tmp/gnostoa-222-round6-red.log`, SHA-256
`d84f4676cb8d4112f2d92ab6636eb2ffcb170e3037627c7424cdd3915dd24521`.
Ruff format --no-cache --check tools ci tests: 117 files already formatted.

R6-U1/U2 currently CONTRADICTS / executor RED; R6-P1 SUPPORTS for the positive
controls. The production catch is not yet applied. No new actual pytest/OCI,
compiler claim or retained recovery was executed. The RED tests use synthetic
local oracle modules and the real local subprocess/harness/report boundary.

### Sixth-round correction and bounded independent review

RED commit `8d8103704781a7ddf562b905bf3830e210e656b4` was pushed and the
[Work Item map/RED checkpoint](https://github.com/ktogias/gnostoa/issues/219#issuecomment-5604334760)
was read back verbatim before the five-line production catch was applied.
UnicodeDecodeError from subprocess text decoding now returns _invalid_report
with the concrete exception type and codec failure detail. No lossy decoder,
encoding override or broad exception catch was introduced. Subject exceptions
serialized by the harness still pass through the existing case classifier;
this catch handles the parent's output decoding failure, not every Unicode-
related behavioral failure in a child test.

Production SHA-256:
`36e794b045f337b1b8ea6481d03ec2370996abe4f15f5e842aa3ac6f912ff72e`.
Focused-test SHA-256:
`fbc3452e9dd4730944bdb8639013178f16f433bb9d03de23638be5d9eee70d32`.
Independent canonical focused execution: **51 PASS**, zero failures/errors/skips.
R6-U1/U2/P1 now SUPPORTS; executor corrected, independent agent reviewer PASS.
R6-X1 source review confirms only the local catch, three regression methods,
small shared test-helper extension and assessment changes. There is no claim,
retry, schema, compiler, OCI, dependency or authority change. Broader exact-
candidate checks are recorded separately by the final PR checkpoint.

| New mutation operator | Exact transformation | Observed result on 51 tests |
| --- | --- | --- |
| R6.U1 | Remove exactly the new UnicodeDecodeError catch. | Restores the exact RED production SHA-256 and produces three escaped UnicodeDecodeError runtime errors, zero assertion failures. |
| R6.U2 | Add `errors="replace"` beside `text=True`, retaining all catches. | Three assertion failures: invalid stdout, stderr and terminal report are incorrectly accepted under the selected strict-transport contract. The terminal case preserves the separate malformed-cause counterexample; these failures do not establish that every noisy stream is a real infrastructure incident. |

All **29 applicable specified operators** compile/import and execute all 51
methods without skips: 24 assertion-only (including diagnostic-only Q02), four
runtime-error-only (N9, N15, R5.L1, R6.U1) and one mixed (R4.P2). The prior
27 definitions remain, with the two new operators above. Historical R3.W1
remains NOT APPLICABLE. These are neither 29 false-MATCH proofs nor exhaustive
exception/encoding coverage. Claude's separate L2 survivor is not added to this
inventory merely to change the count.

Independent report `/tmp/gnostoa-222-round6-review.md` SHA-256:
`e25e8655a260c47e868410ca67290ebd2e30d5caca0d2dedac7130794d2801c4`.
Final mutation results SHA-256:
`2e47bf65851018bb71e5a21e49969118ebcdbec52dc1d302fd25a03d445f2a95`;
operator inventory SHA-256:
`42d0cff4a291c350c9daccd6b7bb9394eddedb8755cde99955d2b2c04147dd92`.
Raw artifacts remain session-local. An initial reviewer artifact-directory
permission failure happened before tests; running with the matching host UID
resolved that setup issue. Only the completed execution supplies verification.

The source suite has executed **648 tests, 646 passed and two existing OCI
skips** in the development container. The final PR checkpoint owns completed
policy/fast/regression/smoke/extended, exact runtime and new-head provider
results, and the current review-thread state. No earlier head's CI or model GO
label substitutes for those checks. Existing thread-resolution authority does
not authorize merging this changed candidate; human exact-head semantic review
and separate owner merge authority remain required. Integration read-back must
precede any #219 closure.
