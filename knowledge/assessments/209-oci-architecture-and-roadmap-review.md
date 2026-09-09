---
type: Source
title: Gnostoa OCI architecture and roadmap review
description: Full September 9, 2026 broad-review snapshot, preserving twelve findings, reviewer disagreements, evidence limits, alternatives, delivery dependencies and source references; not implementation or merge authority.
status: draft
generated:
  by: openai/chatgpt
  at: "2026-09-09T07:20:27Z"
sources:
  - id: architecture-roadmap
    resource: https://github.com/ktogias/gnostoa/issues/209
    title: Thin-host OCI-first architecture roadmap
  - id: broad-review-record
    resource: https://github.com/ktogias/gnostoa/issues/209#issuecomment-5594263350
    title: Broad source, architecture and roadmap review v4
  - id: documentation-capture-admission
    resource: https://github.com/ktogias/gnostoa/issues/209#issuecomment-5597858878
    title: Owner-admitted preservation-only documentation capture
x-project-knowledge:
  id: kit.assessment.209-oci-architecture-and-roadmap-review
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governed-by
      target: /decisions/0004-self-host-policy-guidance-and-knowledge.md
    - kind: references
      target: /requirements/retrospective-findings-require-explicit-admission.md
    - kind: derived-from
      target: /decisions/0059-compile-declarative-experiment-capsules-over-the-owner-led-runner.md
---

<!-- Preservation-only capture. The original report starts at the following H1
and continues unchanged to EOF: 34314 UTF-8 bytes, 255 LF, SHA-256
 d1fbb8cf96c7d0ffc4ae5ccbc165a2bad59ab6573678ebd699b1794682816272.
Its no-test/no-branch statements describe the historical review, not this later
capture PR. Findings and roadmap are a dated assessment, not an effective Decision.
-->

# Gnostoa OCI architecture and roadmap review

## Executive assessment

The proposed architecture is a sound direction for Gnostoa: a small native control plane dispatches substantive commands into version-bound container environments, while explicit policy governs exceptional native execution. Its strongest property is separation of responsibilities, not the mere presence of containers. The design should preserve the existing Python workload implementation, current containerized verification and qualified experiment runner rather than turn into a language rewrite or universal environment-management platform. [R1–R4]

The architecture is **not yet implemented or ready for broad qualification claims**. Three distinct correctness obligations remain: executing the declared adapter faithfully, admitting only valid historical qualification evidence, and accepting only complete process results. The first two are tracked in the revised #216. This review identified the third as a separate source-level defect and created #219. The absence of a demonstrated fresh Node qualification route is a capability decision, now tracked in #218, not permission to weaken isolation or to reuse invalid evidence. [R5–R11]

The existing documentation PR #208 remains a useful and accurate improvement within its bounded scope. It documents the current fresh OCI adapter limit; it does not repair the other qualification paths. Its documentation-only GO-ready disposition must not be mistaken for approval of the whole subsystem. Merge and issue closure remain separate owner actions. [R2]

The immediate recommendation is to integrate the already reviewed documentation when separately authorized, prioritize bounded qualification correctness work, and then deliver the architecture in small measured verticals. Catalog trust must be defined before the first launcher dispatch, but publishing every future image role need not precede the first useful experiment.

## Review scope and evidence limits

The source baseline is `bfce2c2b8b0fa69eca6907c4ee097bd0fb1ec8bd`. The #208 candidate is `77ec3349656e66118e14157e6804c5b59e691c73`, with two documentation files changed, +11/−1. Repository and roadmap observations are a snapshot from September 9, 2026, not a permanent statement about later revisions. [R1, R2]

This assessment combines direct inspection of relevant source, issue bodies and review records with primary technical specifications. The inspected execution path includes qualification, prior-receipt resolution, retained completion restoration, lock loading, status reporting and execution admission. It also examines the Dockerfile, verification workflow and the proposed adoption/planner boundary. It is a broad architecture and selected critical-path review, not a claim that every repository function was exhaustively audited.

No Gnostoa test suite, hidden oracle, container workload or historical experiment was executed for this review. Claude's previously reported wrong-harness reproduction remains attributed to Claude. The new report-classification examples are derived directly from the inspected functions; their real runner-level reachability and historical impact still need admitted synthetic characterization. No complete inventory of real historical receipts, independent byte-identical rebuild, penetration test or cross-platform runtime trial was performed.

The distinction between **recorded**, **source-confirmed**, **empirically reproduced**, **implemented** and **verified after implementation** is maintained throughout. Backlog corrections do not close code defects.

## Existing foundations worth preserving

Gnostoa does not start from an entirely native verification system. The current workflow runs the policy, fast, regression, smoke and extended verification payloads using explicit `docker run` invocations. Their GitHub jobs are native coordinators, which is a different execution layer. The `python-compatibility` matrix does install and execute its Python/static/test tooling on the runner; the fast job also uses a host Python program to coordinate the OCI runner smoke. That is the actual remaining CI alignment surface. The absence of job-level `container:` is not evidence that the payload commands are native. [R3]

The Dockerfile already distinguishes runtime and development roles. It pins the frontend and base image, uses hash-locked Python dependencies, validates the runtime candidate source manifest, runs the final runtime as a non-root user and removes pip from that runtime. Its development build deliberately allows the ordinary working-tree context; that is useful for iteration but is explicitly not the same guarantee as the filtered release/candidate source path. [R4]

The retained qualification mechanism also contains valuable separation: candidate-bound authority, a durable irreversible fresh-effect claim, resumable completed-stage records, and zero-effect reuse. The defect is not that these concepts should be merged. It is that integrity/currentness of stored evidence was allowed to stand in for the distinct question of whether the evidence was produced faithfully. [R5–R8]

These foundations favor incremental adaptation. Replacing them wholesale would increase review surface and discard already established invariants without demonstrating a corresponding benefit.

## Findings and dispositions

| ID | Finding | Evidence level | Significance | Owner and disposition |
|---|---|---|---|---|
| F1 | Local qualification can ignore the declared adapter invocation | Source-confirmed; external empirical report | High correctness | #216, open |
| F2 | Invalid qualification evidence can bypass fresh guards through reuse or restoration | Source-confirmed admission gap; impact inventory pending | High correctness | #216 expanded, open |
| F3 | Parsed case output can hide invalid process termination | New source-derived counterexample; runner reproduction pending | High potential false qualification | #219 created, open |
| F4 | Node adapter presence exceeds demonstrated fresh qualification capability | Source/claim mismatch | Product capability | #218 created; choice not made |
| F5 | “All CI is host-native” is an incorrect review inference | Direct workflow inspection | Factual correction | #217 scope preserved |
| F6 | Existing Dev Container definitions can request host execution and elevated privileges | Specification-confirmed, prospective design risk | High architectural boundary | #213 requirements strengthened |
| F7 | A trusted planner does not authorize its proposed effects | Architectural analysis | High authority boundary | #210/#211/#213 |
| F8 | Launcher/catalog and no-container bootstrap dependencies were incomplete | Roadmap analysis | Delivery and trust | #210/#211/#212 |
| F9 | Read-only inputs and pre-build plans were conflated with immutable/result identities | Source/design analysis | Reproducibility and currentness | #211/#212/#213 |
| F10 | Image identity, historical evidence and current approval need separate lifecycle rules | Architectural analysis | Ongoing trust | #210/#212/#216 |
| F11 | Current roadmap requirements were scattered across superseding comments | Provider read-back | Planning correctness | #209 body consolidated |
| F12 | Evaluation could measure conformance without demonstrating useful cost/benefit | Roadmap analysis | Scope and product risk | #214 strengthened |

### F1. Adapter compatibility includes invocation semantics

The current local qualification backend invokes the embedded Python harness with `sys.executable`. It does not execute the adapter-generated Vitest command or the explicit generic-command argv. The compiler's deterministic compatibility guard, however, rejects non-Python adapters only for the OCI backend. Because the default is local-python, an incompatible declaration can take the local route. [R5, R6]

This is not merely a container-versus-host preference. A result cannot support the declared experiment if the declared execution mechanism was not used. An OCI-first default would hide one manifestation when OCI is available, but a later allowed native fallback could expose it again.

The fix belongs in a small compatibility contract, consumed before fresh effects. It must cover the declared adapter and required invocation features, not just two enum strings. The supported local Python subset should be characterized rather than assumed to implement all pytest fixtures, preloads, configuration or extra arguments. Unknown required features should be refused rather than silently ignored. This does not require adding every feature immediately.

The revised #216 requires positive supported controls, negative Node and generic-command cases, and whole-candidate/reversed-order coverage. It remains independent of the broad routing policy and does not authorize a Node implementation. [R7]

### F2. Reuse must validate evidence, not only identity

The explicit-prior path loads a receipt, checks backend equality and bound identities, then puts it in `resolved_priors`. Approved reuse is intentionally excluded from fresh-only capability checks. Separately, a retained COMPLETE qualification can be restored after stage and receipt consistency checks. Both are legitimate ways to avoid repeating an already earned result. Neither establishes that the historical producer actually executed the harness whose identity the receipt contains. [R5–R8]

The wrong-harness defect makes the distinction concrete. A receipt may carry the Node adapter's harness identity while its local producer ran the embedded Python harness. Repeating the same digest comparison later does not cure that mismatch. **Zero new execution effects does not imply valid evidence.**

Applying today's fresh-support matrix indiscriminately to all old receipts would be an overcorrection. A result genuinely earned by an admitted historical producer might remain usable even when the current executable cannot repeat it. Conversely, a known defective producer must not regain legitimacy through an exact hash match. Known-valid, known-invalid and insufficiently established origin need distinct treatment. A self-declared producer name is not independent provenance.

The revised #216 therefore covers explicit prior imports, retained completion restoration, dependent status/READY reports and old lock use. Source inspection shows that status chiefly validates the committed snapshot, while lock loading validates schema and content digest. Execution requires separate launch authority, but does not itself establish historical qualification-producer admissibility. An import-only fix would leave relevant consumers outside the impact analysis. [R8–R10]

Evidence rejection must preserve the original receipts, locks and consumed-candidate claims. It must not reset a transaction, overwrite history or automatically rerun qualification. Current usability and historical bytes are different objects. The smallest sufficient evidence contract should be selected through a bounded design gate; this finding does not justify a universal attestation registry.

The assertion that every existing Node receipt came from the defective local path is not established. Synthetic Node/OCI test receipts exist, and the earlier #194 record refers to a historical OCI bridge. Neither proves a trustworthy production producer by itself, but both show why a blanket population claim is inappropriate without an inventory. [R11, R12]

### F3. Process completion can be lost during report normalization

The new issue #219 comes from inspection of `_parse_pytest_report`, `_run_oci`, `_run_local_python` and `_classify`. The OCI parser consults the process exit status only in its no-cases error message. Once a matching case line exists, it returns a collected report regardless of terminal exit status. Without a recognized non-assertion traceback, a failed case is assigned AssertionError. The classifier then checks counts and failing-case identity without receiving preserved process-validity information. [R6, R13]

The source-derived counterexample is small:

```text
stdout:     oracle.py::test_discriminates FAILED
exit code:  3
expectation: BASE has one failed discriminator, zero passes

Current parser path:
collected = true
failed case -> inferred AssertionError
matching counts and failing name -> MATCH
```

A corresponding PASSED line with exit code 3 can follow the REFERENCE MATCH path. These examples derive from the actual branch conditions; they are not reported as executed tests. A real internal error or interruption can require a runner-level fixture to establish exactly how output reaches this parser.

Pytest distinguishes ordinary test failure, exit 1, from internal error, exit 3, and other termination conditions. A blanket “nonzero means invalid” fix would therefore be wrong: an intentionally failing BASE is a valid experimental control. The required repair is a reporter/process contract that preserves valid completion and distinguishes a behavioral failure from infrastructure failure. [E1]

The local harness also parses its last JSON line without checking the subprocess return code. That is a separate characterization obligation inside #219, not proof that every local result is wrong. Acceptance must include partial reports, case ERROR, malformed output, interruption, internal errors and non-vacuous valid BASE/REFERENCE controls. [R6, R13]

This finding changes priority: continuous OCI execution coverage is necessary, but a mandatory happy-path test cannot substitute for classifier correctness. #202 should consume the repaired negative and positive fixtures; #216 must consider invalid report producers in historical-evidence analysis.

### F4. The Node capability choice must be explicit

Decision 0059 names Python and Node task shapes, and a node-vitest adapter generates invocation material. That does not demonstrate that every stage required for fresh Node qualification works. The OCI path deliberately refuses Node; the local Python path is not a faithful substitute. Closing compatibility and isolation holes exposes this gap rather than withdrawing a demonstrated working Node path. [R5, R11, R14]

#218 now tracks three legitimate choices: implement a qualified Node route; narrow/defer the fresh Node claim explicitly; or qualify another appropriate producer/backend. No choice was made by recording the issue. Parser non-goals in #215 and #216 are local scope controls, not an eternal project-wide ban.

A Node parser alone is not a complete solution. Static oracle inspection already has some JavaScript handling, but symbol corroboration and the complete preparation/classification pipeline must be examined with genuine JavaScript/Vitest fixtures. Dependency setup, reporter identity, BASE/REFERENCE cause classification and evidence provenance all need a demonstrated supported envelope. Renaming a Node task to python-pytest to make a guard pass is not a remedy. [R14, R15]

### F5. CI needs execution tracing, not a YAML keyword heuristic

The claim that no job-level `container:` implies an entirely native verification surface is false. The direct `docker run` commands are decisive evidence of where the verification payload executes. Host orchestration and containerized work can coexist in the same job. [R3]

#217 remains useful: ordinary Ruff, mypy and compatibility tests currently run in a host Python environment, and the OCI smoke coordinator requires host Python. The target should move ordinary workload dependencies into the chosen images while preserving an intentionally labeled native-fallback/parity test subject where that product capability remains supported.

Do not replace working verification simply to make the YAML look more containerized. Preserve candidate binding, required-check behavior and supported Python-version evidence. A transitional host coordinator for #202 can be explicit without making the entire future thin-host stack a prerequisite for a narrow coverage repair. [R3, R16]

### F6–F7. Reusing project definitions creates an authority boundary

Dev Container metadata permits a host-side `initializeCommand`, runtime arguments, mounts, privilege settings and environment substitution. Metadata can also be merged from images. Thus “a project already has a devcontainer” is not sufficient evidence that its execution follows Gnostoa's thin-host policy. [E2]

The design implication is to inspect the effective configuration and admit a bounded subset. Host hooks must not run implicitly. Required hooks must not be silently dropped either: the result should be a precise incompatibility or a reviewed adaptation. The native host must validate the planner's requested effects against independent policy, not accept a planner-generated approval flag. These controls are proposed design requirements, not claims of a deployed #213 exploit. [R17]

The planner should receive an admitted project snapshot, not automatic read access to every secret-bearing file in a repository. Read-only access is still access. Package/build hooks must not execute merely to discover metadata. A small typed plan is preferable to unrestricted shell commands or raw engine flags.

Docker's security documentation makes the importance of this apply boundary concrete: daemon control can grant powerful host access. A container without the socket is an important restriction, but that restriction is defeated if its unvalidated output instructs a privileged host coordinator to mount forbidden paths. [E3]

### F8. Bootstrap trust and bootstrap availability must both close

The previous sequence placed the launcher before the catalog it was expected to consume. Split the catalog contract from expanded publication. The first launcher vertical needs a minimum trusted role/platform/image mapping and verification policy; it does not need every eventual image role. This is now recorded as #212-A and #212-B milestones within the same Work Item, not additional issues. [R18, R19]

The verifier itself must not depend on running an unverified version of the artifact being verified. Establish the first trust root independently. SLSA verification guidance likewise requires configured trust and comparison with expected builder, source and artifact identities; attestation presence is not enough. This review does not claim a SLSA level for Gnostoa. [E4]

The no-container path has a parallel bootstrap problem. If the native program assumes it can run the planner container to decide how to set up fallback, the exception cannot start precisely when needed. #210 must define the minimal notice/consent mechanism and a bounded, explicitly authorized setup path that does not assume all workload dependencies already exist. Failure to satisfy it remains BLOCKED; it is not justification for building a generic host package manager.

### F9. Bind inputs before build and results after build

A source-built image usually has no known output digest before the build. The plan must first bind the approved context, definitions, dependency identities and policy. The build result is then inspected and its observed identity bound before execution. A result cannot be substituted merely because it came from an approved request. [R17–R19]

Likewise, read-only mounts protect against writes from that container but do not make the source immutable against the host. Sealed verification should snapshot or detect changes between planning and use. Mutable development and exact verification are both useful, but their claims must be different.

Image pinning does not by itself prove reproducible builds or outcomes. Byte-identical build reproduction requires comparison under declared source/environment/instructions. Docker's own digest-pinning guidance also notes the update trade-off: retaining a digest does not automatically acquire security fixes. [E5, E6]

### F10. Current trust can change while artifacts remain immutable

The same distinction applies to images and receipts: immutable content is not permanent permission. Define bounded retirement, advisory and invalid-producer handling, including offline freshness limits, without overwriting old evidence or silently repointing a release. [R7, R19]

A trusted build secret mechanism also does not turn arbitrary build code into trusted code. Docker recommends secret mounts instead of persistent ARG/ENV secret handling. Gnostoa must additionally scope who receives the secret, what build is authorized and which network behavior is allowed. Merely using a secret mount is not a proof that an untrusted build cannot expose the secret. [E7]

### F11–F12. The roadmap must be usable and economically falsifiable

Repeatedly appending a “current reconciliation” comment while leaving the body stale creates an avoidable implementation risk. #209 now contains the consolidated current requirements, owners and dependency distinctions. Prior reviews are preserved as history rather than competing current instructions. [R1]

The staged evaluation also needs to test whether the design is worth its operational cost. A one-command, one-image, one-supported-platform vertical can reveal whether the launcher eliminates host dependencies without unacceptable startup/build/review overhead. Expanding to many languages, image roles and runtime engines before such evidence would contradict the purpose of the thin architecture.

Trial gates now require prospective PASS, FAIL, STOP, INVALID/INCONCLUSIVE and falsification criteria, bounded repetitions and a separate widening decision. Measure cold pull/build, warm dispatch, image footprint, host prerequisites, cache behavior, parity and human intervention. Simulate missing dependencies with disposable clean environments, not by deleting tools from a working machine. [R20]

## Alternatives and design trade-offs

**Continue the broad native Python CLI with stronger guidance.** This reuses the most code immediately, but leaves ambient dependencies and relies on agents remembering the correct route. It does not satisfy the stated normal-host dependency objective. It remains a migration route or explicitly qualified native test subject, not the desired default. [R1, R21]

**Container-only with no exceptions.** This makes routing simpler but excludes legitimate trusted-tool use on hosts that genuinely cannot run containers. For isolation-sensitive workloads, a qualified sandbox-or-BLOCK rule is appropriate. Applying the same product restriction to all ordinary tooling is a separate owner decision, not an automatic security improvement.

**Thin launcher using existing image/runtime standards.** This is the recommended starting shape. Keep substantive Python tooling in containers, expose a narrow apply interface, use existing build/container tooling, and evaluate one vertical. The implementation language remains open; minimal dependencies and auditable behavior are the criteria, not Go or Rust by default.

**Universal workflow/image/environment platform.** This could eventually express more projects, but carries substantial scope, policy, compatibility and maintenance costs. The current evidence does not justify it. If representative projects cannot fit the small plan envelope, record that limitation and deliberately reassess rather than silently evolving the plan into a general DAG engine.

The result is not a claim that one architecture is universally best practice. It is a fit-for-purpose recommendation that preserves Gnostoa's assurance objectives while reusing established container, build and provenance mechanisms.

## Revised delivery order

The recommended queue starts with #208 integration and separate #189 closure when authorized. That is a convenient clean integration point, not a technical prerequisite for fixing a high correctness defect.

The first safety priority is #216 together with #219, as bounded independently admitted work. They may need a focused linked design/Decision under repository policy, but they do not require completing the broad thin-host redesign. Coordinate the historical-receipt impact so a fresh-only repair is not reported as comprehensive closure.

#218's Node capability disposition can proceed alongside #210; it must precede renewed Node readiness claims, not block unrelated safe Python work. #210 also establishes the minimum #212-A trust/catalog contract. #202 then supplies mandatory supported Python/OCI evidence, including relevant repaired negative controls. #215 can prefer that route only after policy and evidence obligations are satisfied. [R1, R7, R13, R16]

The implementation verticals then follow:

| Delivery milestone | Required learning boundary |
|---|---|
| #215 routing | G3: supported route, invalid combinations, no silent downgrade |
| #211 first thin launcher | G4: clean host, no ambient workload dependencies |
| #212-B broader image catalog/publication | G5: version/platform/trust and tamper-negative behavior |
| #217 CI alignment | G6: container-primary workloads and separately typed native parity |
| #213 existing-image/existing-definition resolver | G7: real adoption cases before synthesis |
| #213 generated/adapted environments | G8: bounded synthesis, fallback and final claim reconciliation |

Each gate supplies evidence, not automatic admission to the next milestone. Existing #7 workspace rules, #164 isolation, #183 experimental methodology and #15 mechanics retain their ownership. No parallel replacement governance framework is required. [R1, R20, R21]

## Prospective verification strategy

For qualification, use a matrix that crosses fresh versus prior import versus retained restore; supported versus incompatible adapter/invocation; valid versus invalid versus unknown producer; and single-task versus mixed/reversed-order candidates. Add explicit old-lock/current-status cases. Assertions must independently check zero unintended effects, no new claim, no reset of consumed claims and no false readiness.

For reports, directly distinguish ordinary BASE assertion failure from partial output plus internal error, interruption, timeout, malformed reports and missing/contradictory terminal state. The new source counterexample is a starting RED target, not evidence that an integration test has already run.

For the future host/planner boundary, test host initializer commands, privilege flags hidden in merged metadata, unsolicited secret requests, path/symlink escape, wrong runtime endpoint, source drift, image substitution and stale trust metadata. A successful happy path cannot stand in for these negative cases.

For availability, cover no runtime, runtime present but unavailable, registry failure, unavailable pinned dependencies, unsupported platform, denied credentials and policy refusal separately. Only the policy-defined genuine no-container condition may open an eligible native decision path. Do not reinterpret failure after the fact as a reason to widen authority.

For economics, declare workload-specific thresholds before experiments. There is no useful universal startup limit to invent now. Measure compared routes and report unfavorable evidence as well as successes. [R7, R13, R17–R20]

## Recorded changes and remaining work

The latest Claude follow-up was recorded with its accepted findings, rejected CI inference and unproven receipt-population claim. #216 was renamed and its body expanded to cover invalid reused evidence and dependent consumers. #218 and #219 were created for distinct capability and correctness outcomes. #209's body was consolidated; targeted requirements were recorded with #210–#215, #202 and #217. [R1, R7, R13, R16–R20, R22]

A historical attempted direct file write to protected main was also recorded. The earlier provider response rejected it with HTTP 409. The record preserves the reported branch-level outcome and the absence of the exact attempted payload from the available excerpt; it does not invent that payload or treat protection as a substitute for permission checks. No retry or protection change was made. [R23]

No production fix, new Decision file, branch, PR, image publication, merge or issue closure was performed as part of this review. No new CI run was triggered. The pending implementation tasks remain open; their existence is not evidence of their completion.

## Final disposition

**Architecture direction:** supported, subject to explicit trust, compatibility, report-validity, authority and fallback boundaries.

**Roadmap:** materially improved as a consolidated, bounded and dependency-aware backlog. It is not a blanket implementation admission or a promise that the design is complete for every project/runtime.

**Qualification readiness:** not established for broader use while #216 and #219 remain unresolved and the affected historical evidence has not been characterized.

**Node fresh qualification:** no demonstrated faithful supported current route; #218 requires an explicit product/capability disposition.

**PR #208:** documentation review remains GO-ready within its exact reviewed scope. The approval to merge remains a separate owner decision, and subsequent #189 closure is separate again.

## Sources

The corresponding recorded GitHub review is [Broad source, architecture and roadmap review — v4](https://github.com/ktogias/gnostoa/issues/209#issuecomment-5594263350). The downloadable report expands that record with the finding matrix, alternatives, verification strategy and source index.

Repository links below bind source observations to the inspected commit. Issue and comment links are live planning/evidence records; their status may change after this snapshot.

- **R1.** [Issue #209, consolidated architecture roadmap](https://github.com/ktogias/gnostoa/issues/209).
- **R2.** [PR #208, documentation candidate and review](https://github.com/ktogias/gnostoa/pull/208), head `77ec3349656e66118e14157e6804c5b59e691c73`.
- **R3.** [Verification workflow](https://github.com/ktogias/gnostoa/blob/bfce2c2b8b0fa69eca6907c4ee097bd0fb1ec8bd/.github/workflows/verification.yml).
- **R4.** [Dockerfile](https://github.com/ktogias/gnostoa/blob/bfce2c2b8b0fa69eca6907c4ee097bd0fb1ec8bd/Dockerfile).
- **R5.** [Capsule compiler](https://github.com/ktogias/gnostoa/blob/bfce2c2b8b0fa69eca6907c4ee097bd0fb1ec8bd/tools/capsule/compiler.py).
- **R6.** [Qualification and result classification](https://github.com/ktogias/gnostoa/blob/bfce2c2b8b0fa69eca6907c4ee097bd0fb1ec8bd/tools/capsule/qualification.py).
- **R7.** [Issue #216, compatibility and invalid reused evidence](https://github.com/ktogias/gnostoa/issues/216); [report-producer and timing clarification](https://github.com/ktogias/gnostoa/issues/216#issuecomment-5594221218).
- **R8.** [Retained preflight restoration](https://github.com/ktogias/gnostoa/blob/bfce2c2b8b0fa69eca6907c4ee097bd0fb1ec8bd/tools/capsule/retained_preflight.py).
- **R9.** [Experiment lock loading](https://github.com/ktogias/gnostoa/blob/bfce2c2b8b0fa69eca6907c4ee097bd0fb1ec8bd/tools/capsule/lock.py).
- **R10.** [Execution admission](https://github.com/ktogias/gnostoa/blob/bfce2c2b8b0fa69eca6907c4ee097bd0fb1ec8bd/tools/capsule/execute.py).
- **R11.** [Synthetic reuse regression](https://github.com/ktogias/gnostoa/blob/bfce2c2b8b0fa69eca6907c4ee097bd0fb1ec8bd/tests/test_reuse_before_fresh_guard.py).
- **R12.** [Issue #194, historical reuse-ordering rationale](https://github.com/ktogias/gnostoa/issues/194).
- **R13.** [Issue #219, process failure and report completeness](https://github.com/ktogias/gnostoa/issues/219).
- **R14.** [Issue #218, Node capability decision](https://github.com/ktogias/gnostoa/issues/218); [Decision 0059 at the #208 candidate](https://github.com/ktogias/gnostoa/blob/77ec3349656e66118e14157e6804c5b59e691c73/knowledge/decisions/0059-compile-declarative-experiment-capsules-over-the-owner-led-runner.md).
- **R15.** [Oracle prequalification](https://github.com/ktogias/gnostoa/blob/bfce2c2b8b0fa69eca6907c4ee097bd0fb1ec8bd/tools/capsule/oracle_qualification.py).
- **R16.** [Issue #202, mandatory OCI evidence](https://github.com/ktogias/gnostoa/issues/202); [broad-review reconciliation](https://github.com/ktogias/gnostoa/issues/202#issuecomment-5594198635); [Issue #217, CI alignment](https://github.com/ktogias/gnostoa/issues/217).
- **R17.** [Issue #213, safe existing-definition reuse requirements](https://github.com/ktogias/gnostoa/issues/213#issuecomment-5594150052).
- **R18.** [Issue #211, bootstrap and apply boundary](https://github.com/ktogias/gnostoa/issues/211#issuecomment-5594181913); [Issue #210, Decision requirements](https://github.com/ktogias/gnostoa/issues/210#issuecomment-5594190217).
- **R19.** [Issue #212, minimum contract versus publication](https://github.com/ktogias/gnostoa/issues/212#issuecomment-5594184400).
- **R20.** [Issue #214, prospective negative cases and measurements](https://github.com/ktogias/gnostoa/issues/214#issuecomment-5594193492).
- **R21.** [Repository agent and admission guidance](https://github.com/ktogias/gnostoa/blob/bfce2c2b8b0fa69eca6907c4ee097bd0fb1ec8bd/AGENTS.md).
- **R22.** [Latest Claude review and explicit reconciliation](https://github.com/ktogias/gnostoa/issues/209#issuecomment-5594089766).
- **R23.** [Historical rejected direct-write incident record](https://github.com/ktogias/gnostoa/issues/209#issuecomment-5594223597).
- **E1.** Pytest. [Exit-code contract](https://docs.pytest.org/en/7.2.x/reference/exit-codes.html). The future test fixture must use its actual pinned pytest version and explicitly handle any additional/custom codes.
- **E2.** Dev Container specification. [Metadata reference](https://raw.githubusercontent.com/devcontainers/spec/main/docs/specs/devcontainerjson-reference.md), especially lifecycle commands, runtime options and merged metadata.
- **E3.** Docker. [Engine security](https://docs.docker.com/engine/security/).
- **E4.** SLSA v1.2. [Build: Verifying artifacts](https://slsa.dev/spec/v1.2/verifying-artifacts).
- **E5.** Reproducible Builds. [Definitions](https://reproducible-builds.org/docs/definition/).
- **E6.** Docker. [Building best practices](https://docs.docker.com/build/building/best-practices/), digest pinning and reviewed updates.
- **E7.** Docker. [Build secrets](https://docs.docker.com/build/building/secrets/).
