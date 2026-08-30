---
type: Decision
title: Separate adoption observations from readiness and owner disposition
description: Keep one subject-bound adoption-check while separating observations, evidence integrity, explicit readiness policy and accountable-owner disposition.
status: draft
generated:
  by: codex/gpt-5
  at: "2026-08-27T01:43:16+03:00"
sources:
  - id: adoption-assurance-model-work-item
    resource: https://github.com/ktogias/gnostoa/issues/143
    title: Separate adoption-check observations, readiness policy, and owner disposition
  - id: adoption-completion-decision
    resource: 0047-select-a-bounded-adoption-completion-check.md
    title: Select a bounded adoption-completion check
  - id: runtime-observation-decision
    resource: 0048-select-project-adapter-runtime-observation-for-adoption-check.md
    title: Select project-adapter runtime observation for adoption-check
  - id: evidence-integrity-decision
    resource: 0049-bind-adoption-evidence-to-an-authoritative-ledger.md
    title: Bind adoption evidence to an authoritative ledger
  - id: in-toto-statement-v1
    resource: https://in-toto.io/Statement/v1
    title: in-toto Statement layer specification v1
  - id: in-toto-test-result
    resource: https://in-toto.io/attestation/test-result/
    title: in-toto Test Result predicate
  - id: slsa-verification-summary-v1
    resource: https://slsa.dev/spec/v1.2/verification_summary
    title: SLSA Verification Summary Attestation v1
  - id: slsa-build-requirements
    resource: https://slsa.dev/spec/v1.2/build-requirements
    title: SLSA Build requirements v1.2
  - id: kubernetes-condition-convention
    resource: https://kubernetes.io/docs/reference/kubernetes-api/apiextensions/custom-resource-definition-v1/
    title: Kubernetes condition status, reason and observed generation
  - id: github-status-checks
    resource: https://docs.github.com/en/pull-requests/reference/status-checks
    title: GitHub status checks
  - id: github-required-checks
    resource: https://docs.github.com/en/pull-requests/how-tos/merge-and-close-pull-requests/troubleshooting-required-status-checks
    title: GitHub required status check semantics
  - id: sigstore-verification
    resource: https://docs.sigstore.dev/cosign/verifying/verify/
    title: Sigstore signature and attestation verification
  - id: nist-ssdf
    resource: https://csrc.nist.gov/pubs/sp/800/218/final
    title: NIST Secure Software Development Framework 1.1
x-project-knowledge:
  id: kit.decision.0050.separate-adoption-observations-readiness-and-owner-disposition
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governed-by
      target: /decisions/0012-use-versioned-public-schema-identifiers.md
    - kind: governed-by
      target: /decisions/0016-evolve-human-agent-workflow-through-bounded-self-hosted-slices.md
    - kind: governed-by
      target: /decisions/0047-select-a-bounded-adoption-completion-check.md
    - kind: governed-by
      target: /decisions/0048-select-project-adapter-runtime-observation-for-adoption-check.md
    - kind: governed-by
      target: /decisions/0049-bind-adoption-evidence-to-an-authoritative-ledger.md
    - kind: references
      target: /lifecycles/evidence-gated-capability-evolution.md
---

# Separate adoption observations from readiness and owner disposition

## Context

The implementation integrated at protected `main`
`aadf0c2866f220682d4e89d371a5054e0ab224c5` already implements the stronger
goal selected by Decisions 0047--0049. One `knowledge adoption-check` invocation
validates Gnostoa structure, invokes the project-owned `fast` and `regression`
suites, acquires invocation-bound project-reported runtime observations, checks
that the staged candidate remains stable and publishes a ledger-derived
evidence bundle with an external commitment. Exit `0` means only readiness for
accountable-owner review.

The current `gnostoa-adoption-check/v1` JSON preserves useful detail in
`components`, `dimensions` and `authority`. It does not, however, implement the
four independently addressable layers requested by Work Item #143:

- the exact candidate subject is distributed across Git and artifact records;
- observation outcome, source and assurance do not share one closed contract;
- `_result_exit` is the effective readiness policy, so required inputs and
  precedence are embedded in executable aggregation code rather than named and
  digest-bound;
- semantic review and durable adoption appear beside mechanical dimensions,
  even though adoption-check has no authority to produce their disposition.

The present implementation is therefore a secure composite evidence check with
partially separated dimensions. It is not yet an explicit observation ->
condition -> readiness-policy -> owner-disposition model.

## Research findings

The external practices agree on several useful boundaries without selecting a
technology for Gnostoa:

- in-toto Statements bind a typed predicate to immutable subjects by digest;
  the Test Result predicate models one test-suite invocation and leaves policy
  evaluation to the consumer;
- the SLSA Verification Summary pattern names the subject, verifier, exact
  policy and input attestations separately from the verification result;
- Kubernetes conditions keep condition type, three-valued status, stable reason
  and the observed subject generation separate;
- GitHub required checks bind to the latest candidate, but a skipped or neutral
  job can count as successful at the provider boundary, so provider status alone
  cannot carry Gnostoa's required-condition semantics;
- Sigstore verification requires the artifact claim and expected signer
  identity or issuer to be checked together; a signature check with claims
  disabled is not an equivalent trust result; and
- SLSA's stronger provenance levels require trusted control-plane generation
  and isolation from user-controlled steps. Descriptor-bound local custody is
  valuable but does not create that assurance tier.

These are design references, not conformance claims. Adoption readiness is not
a SLSA level, a Kubernetes object or a generic in-toto predicate. This Decision
selects no OPA, in-toto, SLSA, Sigstore or provider implementation.

## Alternatives considered

| Alternative | Benefit | Material limitation | Disposition |
| --- | --- | --- | --- |
| Keep the current monolithic result | No migration or new model | Policy, trust basis and semantic boundary remain implicit | Rejected |
| Split every check into a separate command | Locally simple outputs | Increases orchestration and subject-drift risk and duplicates custody/finalization mechanics | Rejected |
| Keep one composite verifier with independent conditions and an explicit policy | Preserves one candidate and evidence transaction while exposing claim boundaries | Requires a new result schema and careful migration | Selected |
| Require external-CI attestations only | Can provide a stronger independent trust boundary | Excludes valid local adoption, introduces provider dependency and does not remove owner judgement | Retained only as a future optional assurance profile |

## Decision

### A. Keep one bounded composite verifier

Keep `knowledge adoption-check` as the public post-authoring command. It remains
the single orchestrator for the candidate snapshot, Gnostoa checks, project
suites, runtime-observation acquisition, final Git reconciliation and evidence
publication.

Do not split the default flow into separately invoked public commands. One
invocation preserves a common candidate subject, one failure model and the
ledger and descriptor-bound transaction selected by Decision 0049. Internal
collectors and evaluators may be separate modules, but their outputs must join
only through the contracts below.

### B. Give the candidate one exact subject identity

Every observation, condition, readiness evaluation and later owner disposition
must reference one immutable candidate descriptor. At minimum it binds:

- the repository object format and base commit object ID;
- a non-mutating canonical identity of the staged candidate tree;
- the SHA-256 and length of the retained staged patch;
- the exact required gitlink/submodule subjects; and
- the before/after identity observations used to establish stability.

Documentation, toolkit source, executing toolkit runtime, project-suite runtime
and any declared OCI identity remain separate subjects associated with that
candidate. A pathname, branch, tag, version label or caller declaration is not
an immutable subject identity.

Candidate mutation invalidates all candidate observations, condition results,
readiness and any prior owner disposition. A readiness-policy change invalidates
readiness but need not erase still-current underlying observations. A verifier
or observation-contract change invalidates only the observations whose meaning
or acquisition assurance changed, unless an explicit compatibility rule proves
otherwise.

### C. Make observations canonical and trust-explicit

Version 2 records each mechanical input as a subject-bound observation. Every
observation has a stable ID and type and separately records:

- its subject and candidate reference;
- raw outcome, including `PASS`, `FAIL`, `BLOCKED`, `NOT RUN` or `ERROR` as
  applicable;
- producer and verifier identities;
- observation basis and assigned assurance class;
- relevant configuration or policy identity; and
- digest-bound evidence references.

The verifier assigns assurance from the acquisition path; an evidence producer
cannot self-select it. The minimum closed assurance vocabulary distinguishes:

- direct Gnostoa measurement;
- a process result observed by Gnostoa for a project-authoritative command;
- an invocation-bound project report;
- a verified external attestation; and
- a normative requirement that is not an empirical observation.

For a project suite, process launch and exit are directly observed, the command
and meaning of the suite remain project-authoritative, and runtime identity from
the version-1 sidecar remains an invocation-bound project report. None of those
facts is silently upgraded to independent attestation.

### D. Derive uniform independent conditions

Conditions are deterministic projections of referenced observations. Every
condition contains its type, candidate subject reference, `TRUE`, `FALSE` or
`UNKNOWN` status, stable reason, authority, observation basis, assurance class,
verifier identity and evidence references.

The initial contract includes at least:

- `CandidateStable`;
- `ExecutionSubjectsCoherent`;
- `StructuralValid`;
- `ContextDeterministic`;
- `ProjectSuitesPassed`;
- `RuntimeObservationAvailable`;
- `EvidenceIntegrityPreserved`; and
- `SemanticReviewRequired`.

`ExecutionSubjectsCoherent` retains the current documentation, toolkit,
executing-runtime, runtime-lock and applicable declared-identity comparisons.
`StructuralValid` retains change-policy, CI-policy and profile/bundle results.
No currently required mechanical dimension may disappear inside an undocumented
aggregate.

The minimum status mapping is:

| Observation state | Condition status | Stable reason class |
| --- | --- | --- |
| Required evidence was acquired and satisfied the condition | `TRUE` | `Satisfied` |
| A complete executed or compared observation contradicted the condition | `FALSE` | `ObservedFailure` or `SubjectIncoherent` |
| A prerequisite was unavailable or the condition was not run | `UNKNOWN` | `PrerequisiteBlocked` or `NotRun` |
| The candidate changed | `FALSE` | `SubjectChanged` |
| The evidence boundary was unsafe or evaluation failed internally | `UNKNOWN` | `UnsafeBoundary` or `InternalError` |

`UNKNOWN` never satisfies a required condition. Human-readable detail may vary,
but stable reason codes and their status meanings require a schema-version
change when altered incompatibly.

`SemanticReviewRequired` is a normative condition whose status remains `TRUE`.
It is not included among mechanically satisfiable readiness inputs and cannot be
cleared by adoption-check.

### E. Select one explicit strict readiness policy

Select a closed built-in policy identified as `gnostoa-review-ready/v1`. Its
canonical bytes and SHA-256 digest are recorded in every evaluation. It requires
all of the following conditions to be `TRUE` for the same candidate:

```text
CandidateStable
AND ExecutionSubjectsCoherent
AND StructuralValid
AND ContextDeterministic
AND ProjectSuitesPassed
AND RuntimeObservationAvailable
AND EvidenceIntegrityPreserved
```

The result records the policy ID and digest, each required condition and the
exact observation/evidence inputs used. The initial policy is data with closed
semantics, not a general expression language or policy engine.

Evaluation precedence preserves the current exits without erasing detail:

| Readiness evaluation | Exit | Rule |
| --- | ---: | --- |
| `READY` | `0` | Every required condition is `TRUE` |
| `FAILED` | `1` | At least one required condition is `FALSE` and no integrity/internal error has precedence |
| `ERROR` | `2` | An unsafe boundary, invalid invocation or internal/integrity failure occurred |
| `BLOCKED` | `3` | No required condition is `FALSE`, but at least one is `UNKNOWN` |

Evidence integrity becomes externally claimable only after the complete
Decision-0049 publication transaction succeeds. A failed finalization leaves no
retained supposedly-ready bundle and emits no readiness or commitment. A
consumer of a successful bundle must retain and verify the separate external
bundle commitment; the internal `SHA256SUMS` alone is not the trust anchor.

### F. Keep owner disposition outside adoption-check

The command reports only:

```text
REVIEW READINESS: READY
SEMANTIC ADOPTION: NOT DETERMINED
OWNER DISPOSITION: REQUIRED
```

It retains the existing success marker `READY FOR ACCOUNTABLE-OWNER REVIEW` as
a compatibility projection. Neither marker is acceptance.

Adoption-check emits a disposition requirement, never an owner disposition. A
later accountable-owner event must be created through the adopting project's
own authority mechanism and bind the exact candidate, evidence-bundle
commitment and readiness-policy identity. Its actor, authority and disposition
cannot be inferred from an exit code, provider status, comment author or prior
candidate. This Decision specifies that integration boundary only; Issue #15
retains ownership of any reusable authority-event or workflow mechanism.

### G. Preserve local assurance and admit external evidence only by verification

The current local profile remains the default. It uses the project-authoritative
adapter, project-reported sidecar and Decision-0049 custody controls. It makes no
claim of operating-system isolation or independently attested runtime identity.

A future profile may substitute a verified external attestation for a named
observation only when the consumer verifies, at minimum:

- signature or equivalent authenticity against an allowed trust root;
- expected signer/verifier identity and issuer;
- exact candidate subject digest;
- expected predicate and observation type;
- applicable suite/configuration and policy identity; and
- the attestation bytes and referenced evidence used by the readiness decision.

Signature validity alone does not satisfy those checks. An external profile may
raise the assurance class only for observations whose complete binding it
verifies. It does not upgrade unrelated local evidence or produce owner
disposition. Selecting a concrete attestation format, signer, policy technology
or provider remains a later Decision and must consume rather than duplicate
Issue #15's effective contracts.

### H. Use a new result schema and preserve the stable command projection

Do not silently change `gnostoa-adoption-check/v1`. A later admitted
implementation introduces `gnostoa-adoption-check/v2` because observation,
condition and readiness semantics are a breaking result-contract change.

The command name, existing invocation arguments, evidence-directory
non-overwrite behavior, `adoption-check.json` filename, evidence commitment,
success marker and exit codes remain compatible. Version 2 makes observations,
conditions, policy evaluation and disposition requirement canonical. Detailed
component logs may remain evidence, but legacy `dimensions` must not become a
second authority; any retained compatibility view is derived only from the
version-2 result.

No released Gnostoa artifact contains adoption-check, so the first release that
includes the command should make version 2 the default rather than creating a
dual-schema support burden. Consumers of the current source-built version-1
candidate must retain its exact source pin or migrate explicitly. Rollback is a
revert to the last verified version-1 implementation and documentation, not a
policy flag that weakens required conditions or reinterprets version-2 data.

### I. Project provider state without weakening unknowns

A provider integration may project only the final readiness evaluation for the
exact candidate. Its required aggregate job must execute even when dependencies
fail or are unavailable and may report provider success only for `READY`.
`FAILED`, `ERROR`, `BLOCKED`, a missing result, stale subject, skipped aggregate
or neutral aggregate do not satisfy Gnostoa readiness, even if a repository host
would otherwise treat `skipped` or `neutral` as merge-successful.

This is a projection rule, not authorization to change provider settings under
this Decision-only slice.

### J. Require separate implementation admission and falsification

This draft Decision records the selected architecture only. It admits no source,
schema, guidance, CI, provider or release implementation.

Before implementation, the accountable owner must admit the exact proposed
public/runtime diff through Work Item #143 or a bounded successor. The admitted
slice must establish focused failing fixtures for mixed results, blocked and
not-run prerequisites, subject mutation, stale evidence, forged assurance
labels, policy changes, finalization failure, external-attestation mismatch and
incorrect exit/provider projection. It must preserve the current complete suite,
evidence-integrity and affected security obligations.

## Consequences

- The stronger adoption claim remains available without forcing every consumer
  onto an external CI or attestation service.
- Structural successes remain visible when suites or runtime observation are
  blocked, while strict aggregate readiness still fails closed.
- Trust strength becomes assigned and inspectable rather than encoded in a
  generic `PASS`.
- Policy evolution can invalidate readiness without destroying still-current
  subject-bound observations.
- The owner gate becomes architecturally separate instead of appearing to be an
  unfinished mechanical dimension.
- Version 2 is a breaking pre-release result-contract change and requires a
  later source/runtime release before general reliance.
- Additional schema, policy and migration code is justified, but a generic
  attestation framework, policy engine, workflow engine and provider authority
  service remain outside this slice.
- Decision 0049's residual same-user custody boundary and the unproved atomic
  sidecar-publication history remain explicit and unchanged.
- No implementation, Decision acceptance, merge, release, OCI, publication or
  provider-setting effect is authorized by this draft.
