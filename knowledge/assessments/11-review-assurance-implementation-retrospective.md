---
type: Source
title: D11-R2A implementation convergence retrospective and root-cause analysis
description: Deep retrospective of the D11-R2A RED-to-GREEN implementation, trust-boundary review repairs, CI convergence, provider dogfood and reusable process lessons.
status: draft
generated:
  by: openai/gpt-5.6-sol
  at: "2026-09-12T12:26:00Z"
sources:
  - id: work-item
    resource: https://github.com/ktogias/gnostoa/issues/11
    title: Semantic capture reconciliation and rationale completeness
  - id: pull-request
    resource: https://github.com/ktogias/gnostoa/pull/240
    title: D11-R2A implementation candidate
  - id: decision
    resource: ../decisions/0067-evaluate-semantic-review-assurance-through-bound-evidence.md
    title: Decision 0067
  - id: red-contract
    resource: 11-review-assurance-red-contract.md
    title: D11-R2A review-assurance RED-first execution contract
  - id: implementation-result
    resource: 11-review-assurance-implementation-result.md
    title: D11-R2A implementation result
x-project-knowledge:
  id: kit.assessment.11-review-assurance-implementation-retrospective
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governed-by
      target: /decisions/0053-require-lightweight-work-item-micro-retrospection.md
    - kind: governed-by
      target: /decisions/0067-evaluate-semantic-review-assurance-through-bound-evidence.md
    - kind: derived-from
      target: /assessments/11-review-assurance-implementation-result.md
    - kind: references
      target: /decisions/0061-retain-individual-agent-review-dispositions.md
---

# D11-R2A implementation convergence retrospective and root-cause analysis

## Purpose

This record explains what the D11-R2A implementation actually taught us, including the parts that failed before they converged. It intentionally separates architectural correctness from implementation correctness and implementation correctness from evidence-record correctness.

The work succeeded, but not because the first implementation was a direct transcription of the approved architecture. Several defects appeared precisely at the seams between a pure deterministic file evaluator, a trustworthy current-advisory acquisition path, repository CI integration and long-running task state. Those defects are more reusable than a simple statement that the final tests pass.

## Executive conclusion

The strongest lesson is the same one discovered during architecture dogfood, but in a sharper implementation form:

> **A supplied claim is not an authority fact, and a protected trust rule must be enforced at the shared trust boundary rather than at one convenient interface.**

Decision 0067 already separated reviewed evidence from policy/qualification/judge authority. The implementation nevertheless initially allowed the normal CLI caller to select a policy file and provide matching authority claims. That was not a failure of the high-level architecture; it was a failure to make the acquisition/trust distinction structural enough in the first executable boundary.

The first repair then made a second classic mistake: it protected the CLI path but left the shared `evaluate_documents()` path able to bypass the protection. The final repair moved the bootstrap invariant into the evaluator itself: until a protected prior-integrated acquisition path exists, no P1 `current_advisory` invocation can PASS.

The second major lesson is about verification plumbing. A RED-first contract is not meaningful merely because RED tests exist in the repository. The pre-registered R01-R45 harness initially was not actually invoked by canonical `ci/verify fast`. CI convergence exposed that gap, along with stale SB2 assumptions, source-native import differences, strict type defects and formatter details. The production result became credible only after the executable oracle was part of the same canonical path that validates integration candidates.

## Incident A — aggregate retrieval created a false absence inference

During the architecture phase, a large Issue #11 retrieval was truncated and the coordinator initially inferred that CodeRabbit had not answered. A targeted retrieval later proved that the response existed.

### Root cause

The process treated "not present in this retrieved aggregate" as equivalent to "does not exist". Large provider threads amplify this risk because a transport can return a bounded prefix while still representing the request as successful.

### Correction

Subsequent review requests use post-trigger exact-resource readback and targeted comment retrieval. A missing targeted result remains pending rather than being translated into absence.

### Reusable lesson

`NOT OBSERVED != ABSENT` applies to our own orchestration and retrieval layer, not only to the review-evidence schema. Large issue/PR aggregates are discovery surfaces, not proof of complete collection.

## Incident B — planning initially put authority metadata too close to evidence

Early planning variants allowed capability/domain metadata to live on observations and mixed collection status with review status. They also risked permissive zero-review behavior and exact-base-tip overbinding.

### Root cause

The initial design optimized for one convenient input object before separating descriptive review facts, collection completeness and externally established authority.

### Correction

Architecture R8/Decision 0067 introduced the distinct review subject, evidence-set completeness envelope, external qualification snapshot and authority binding. It also reduced the public schema surface from six candidate schemas to three and kept policy closed rather than introducing a DSL.

### Reusable lesson

Do not let transport convenience decide trust topology. First separate what a provider said, whether collection was complete, who is qualified, which authority established that qualification and which exact reviewed comparison the evidence covers.

## Incident C — the normal CLI reintroduced candidate/caller self-authorization

The first production implementation accepted `knowledge review-check --policy <path>`. The evaluator verified that the loaded policy digest matched `input.authority.policy_digest`, but both could be caller-controlled. The same was true for matching qualification and expected/acquired judge claims.

A caller could therefore construct a weaker schema-valid policy, matching authority digest, matching qualification snapshot and matching accepted judge claims and obtain an equivalent current-advisory PASS.

CodeRabbit recorded this as a MATERIAL finding on exact head `feafc41f87d66187aa0a3a672a13e0163a9bae0f` in comment `5645676190`.

### Root cause

We correctly distinguished **semantic determinism** from **hostile-caller resistance** in architecture prose, but the executable command still exposed a caller-selectable policy path without a correspondingly protected authority acquisition path. The implementation therefore made a stronger current-advisory trust claim than its acquisition mechanism could support.

### First correction

The CLI rejected caller-selected policy in current-advisory mode and rejected caller assertion of `judge_relation:prior_integrated`. Historical/file replay retained explicit policy selection.

### Why the first correction was insufficient

It protected `main()` rather than the shared trust boundary. `evaluate_documents()` could still be called directly with the same caller-authored matching facts.

### Reusable lesson

Interface-level checks are defense in depth. A trust invariant belongs in the lowest shared semantic boundary that all supported entry points cross.

## Incident D — direct evaluator API bypassed the CLI repair

CodeRabbit comment `5645705012` found that direct `evaluate_documents()` still allowed the self-authorization shape after the CLI was constrained.

### Root cause

The fix was framed as a command-routing problem because the visible attack used `--policy`. The actual invariant was broader: P1 lacked any protected prior-integrated current-advisory acquisition source. Therefore **every** current-advisory entry point had to fail closed, not only the public CLI.

### Final correction

The shared evaluator now returns:

```text
outcome = INCOMPLETE
reason = BOOTSTRAP_PROTECTED_AUTHORITY_UNAVAILABLE
binding = false
```

for every well-formed P1 `current_advisory` invocation before collection/quorum/PASS evaluation. A direct `evaluate_documents()` regression supplies fully matching caller-authored prior-integrated policy/qualification/judge facts and requires that fail-closed result.

### Why this is not overcorrection

P1 genuinely has no protected prior-integrated R2A acquisition record on integrated main. Inventing one inside the candidate would defeat the anti-self-weakening boundary. The correct bootstrap behavior is inability to PASS until a later separately admitted acquisition path exists.

## Incident E — producer output was not initially checked against its public result schema

The coordinator's implementation pass noticed that inputs and policy were schema-validated, but the result returned by the internal evaluator was not validated against `review-gate-result.schema.json` before the CLI treated its outcome as authoritative semantic output.

### Root cause

The schema was initially treated primarily as a consumer contract. That leaves producer/schema drift detectable only when a downstream consumer happens to reject it.

### Correction

`evaluate_documents()` validates the produced semantic result against the result schema before semantic exit-code mapping. A focused regression monkey-patches a malformed internal result such as `{"outcome":"PASS"}` and requires canonical `TOOL_ERROR` exit `2` rather than a false PASS.

### Reusable lesson

A public result schema should constrain the producer at the production boundary, not only document expectations for consumers.

## Incident F — malformed installed JSON Schema could escape the canonical error envelope

CodeRabbit's same `5645676190` review noted that constructing `Draft202012Validator` could raise `jsonschema.exceptions.SchemaError`, while the error boundary did not catch it.

### Root cause

We validated documents against schemas but did not explicitly treat the installed schemas themselves as bounded configuration subject to failure.

### Correction

Installed schemas are checked with `Draft202012Validator.check_schema()`. `SchemaError` is converted into the canonical configuration error envelope with exit `2`. A focused regression covers this path.

### Reusable lesson

Schemas are executable configuration. Validate the validator input as well as the business input.

## Incident G — canonical CI exposed integration defects one layer at a time

The RED-to-GREEN implementation went through several exact-head CI failures that were not semantic R2A failures but were still required repository-conformance work.

### G1. Canonical Ruff formatting and EOF detail

The large evaluator first failed formatter checks. After canonical formatting, one remaining difference was a single final LF at EOF. The replacement blob was verified by detached diff before branch movement.

**Lesson:** for large generated/rewritten files, verify formatter-only byte changes before advancing a protected candidate; do not treat "looks formatted" as evidence.

### G2. Historical SB2 regression expected 14 members

Adding the five review-assurance modules correctly extended the exact executable candidate boundary from 14 to 19 members, but an existing publication-baseline regression still asserted 14 for the current candidate.

The repair preserved both facts: the historical v0.2.0/publication set remains 14, while the PR candidate binding explicitly checks the historical 14-member core and then adds exactly five R2A modules for 19.

**Lesson:** when extending a protected set, preserve the historical invariant and test the extension explicitly instead of rewriting history.

### G3. The pre-registered R01-R45 oracle was not wired into canonical `fast`

`ci/verify fast` initially ran `unittest discover`, but the standalone RED harness was not thereby executing as its intended contract gate.

The repair explicitly runs `python tests/test_review_assurance.py` in the canonical fast suite and adds an integration regression that proves the wiring remains present.

**Lesson:** a test artifact that is not in the canonical candidate verification path is documentation, not a gate. RED-first chronology must include execution wiring, not only test-file chronology.

### G4. Source-native import path differed from installed/container runtime

The standalone harness passed in installed/container context but source-native verification required an explicit `PYTHONPATH=.` route.

**Lesson:** when the project intentionally verifies both source and installed forms, import-path equivalence is part of the executable contract and should be explicit rather than environment-accidental.

### G5. Strict mypy surfaced five narrow typing defects

Once Ruff passed, CI reached strict mypy over the new review trust domain and found five narrowing/return-type issues. They were repaired with runtime narrowing, not `type: ignore`, arbitrary casts or reduced type-check scope.

**Lesson:** keep the trust-domain modules inside the strict type gate from first production convergence. A passing test suite is not a reason to exempt new authority code from static checking.

## Incident H — dogfood first failed on formatting, not semantics

After production code had already converged at `f08b3e00...`, real PR #239 provider evidence and dogfood tests were added in an evidence-only revision. The first dogfood head failed Python 3.12 solely because the new test file was not canonical Ruff-formatted.

The fixture bytes and production code were not changed. The next revision applied exactly the formatter-required test changes and then passed the full workflow.

### Reusable lesson

Evidence/test-only finalization still deserves the full repository verification path. Keeping it separate from production convergence makes a late evidence failure cheap to diagnose and prevents unnecessary reopening of trusted code.

## Incident I — durable task and PR descriptions drifted behind the actual work

As implementation progressed through RED, GREEN, trust-boundary repairs and dogfood, the canonical task envelope and PR body remained at an earlier "pre-production RED-only" narrative.

### Root cause

The work was correctly optimized to keep code candidates immutable while CI/review converged, but durable state synchronization was deferred. Long-running agent-led work makes this drift especially visible because the repository may be mechanically current while the human orientation surfaces still describe an earlier stage.

### Correction

Finalization explicitly updates the task to `ready` for accountable-owner semantic review, advances its checkpoint, records the implementation result/RCA, and reconciles the PR description only after code and dogfood have exact-head evidence.

### Reusable lesson

Do not continuously rewrite durable state during every transient CI cycle, but do make **state reconciliation a named finalization phase** before asking the owner for semantic review.

## What the review loop contributed

The agent-review loop was useful because it attacked different failure shapes over exact immutable subjects:

- architecture review exposed anti-self-weakening before implementation;
- implementation review found the caller-policy trust gap;
- re-review found the direct shared-API bypass of the first repair; and
- final exact-head confirmation separated "no material finding" from "CI not finished yet" rather than conflating the two.

However, provider/reviewer multiplicity is not treated as Issue #10-established independence. CodeRabbit passes are one reviewer family. Qodo and Sourcery records used in PR #239 dogfood are provider evidence, not automatically qualified review domains. This distinction is itself one of the system properties R2A exists to preserve.

## What the real-provider dogfood contributed

Synthetic fixtures can prove planned edge cases but are weak evidence about the shape of real provider history. PR #239 supplied two useful native GitHub review objects with exact provider review IDs and exact older commit IDs.

The dogfood deliberately did **not** upgrade them to the final PR #239 subject. It proved that:

- native `COMMENTED` and `APPROVED` states normalize deterministically through the active adapter;
- provider attribution and raw references survive normalization;
- both reviews remain visible as older-head evidence; and
- neither can satisfy final-head quorum merely because it came from a named review bot.

That result is more valuable than manufacturing a dogfood PASS. The point of the gate is to refuse false certainty when evidence is real but not current enough for the requested subject.

## Delivery cost and complexity assessment

The final production code surface stayed close to the intended small design: three public schemas and five flat review modules plus the CLI route. Most delivery expansion came from verification and convergence work, not from adding a policy engine or provider framework.

That cost was justified by concrete discriminators:

- self-authorization was a real false-PASS path;
- the direct API bypass proved the first repair was interface-local;
- result-schema validation closed a producer drift path;
- canonical CI initially did not execute the literal RED oracle; and
- real dogfood confirmed older-head attribution semantics.

The work would have been overbuilt if these findings had caused a generic authority service, reviewer registry, policy DSL or live collector to be added in P1. They did not. Those remain separate future decisions.

## Reusable engineering rules from D11-R2A

1. **Put trust invariants at the shared evaluator/acquisition boundary.** CLI checks are defense in depth, not the root of trust.
2. **Bootstrap must be allowed to say "cannot establish".** Do not invent authority simply to make a first version produce PASS.
3. **Validate emitted public results against their own schema.** Producer drift is a tool error, not semantic state.
4. **Treat installed schemas as configuration inputs.** Schema invalidity needs the same canonical fail-closed envelope as policy invalidity.
5. **Wire verification-first oracles into canonical CI.** Existence of a RED test is not proof that GREEN integration executes it.
6. **Extend protected sets without erasing historical invariants.** Preserve the old set, then test the explicit delta.
7. **Use exact immutable heads for every review disposition.** An older-head review is useful evidence but not newer-head coverage.
8. **Do not infer independent domains from provider/model names or repeated calls.** Qualification remains Issue #10-owned.
9. **Use real provider records for dogfood without laundering their limitations.** A good dogfood outcome can be INCOMPLETE.
10. **Finalization is a first-class phase.** Reconcile task state, result, RCA and PR description after code convergence, then rerun CI/review on the evidence-only final candidate.

## Remaining limitations and follow-up boundary

P1 intentionally leaves one major capability unavailable: a protected prior-integrated authority acquisition path that could support a genuine current-advisory PASS. The implementation makes that absence explicit rather than hiding it.

A future change that enables current-advisory PASS must separately define and verify:

- how the prior-effective authority subject is selected independently from the candidate;
- how exact policy, qualification and expected-judge identities are acquired from it;
- how candidate changes to those artifacts are judged under the previous effective authority;
- outage/recovery and unavailable-authority behavior; and
- which protected consumer is permitted to use the advisory result for any stronger enforcement.

This retrospective does not admit that work. Decision 0067 already reserves required enforcement/protected acquisition for a later decision.

## Final retrospective disposition

The implementation is judged proportionate **because the complexity that was added corresponds to falsified failure modes** and the team repeatedly declined to solve adjacent problems inside P1. The strongest improvement to carry forward is procedural: whenever a design distinguishes semantic evaluation from trusted acquisition, make that distinction executable at the shared boundary before exposing a result named PASS.
