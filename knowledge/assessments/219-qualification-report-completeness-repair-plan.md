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
