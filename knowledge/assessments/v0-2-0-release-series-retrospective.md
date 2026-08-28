---
type: Source
title: v0.2.0 release-series retrospective
description: Bounded causal retrospective over the adoption-check, evidence-integrity, assurance-v2, immutable source and OCI publication, reconciliation and staged-evidence transition that produced Gnostoa v0.2.0.
status: draft
generated:
  by: chatgpt/gpt-5.6-pro
  at: "2026-08-28T14:33:45+03:00"
sources:
  - id: retrospective-work-item
    resource: https://github.com/ktogias/gnostoa/issues/155
    title: Retrospect the v0.2.0 release series and staged-evidence transition
  - id: release-work-item
    resource: https://github.com/ktogias/gnostoa/issues/146
    title: Publish Gnostoa v0.2.0 source and OCI release series
  - id: release-result
    resource: v0-2-0-source-and-oci-publication-result.md
    title: v0.2.0 source and OCI publication result
  - id: candidate-result
    resource: v0-2-0-release-candidate-and-source-boundary-result.md
    title: v0.2.0 release-candidate and source-boundary result
  - id: staged-evidence-integration
    resource: https://github.com/ktogias/gnostoa/pull/152
    title: Adopt staged evidence maturity and freeze the v0.2.0 owner-led trial baseline
x-project-knowledge:
  id: kit.assessment.v0-2-0-release-series-retrospective
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governed-by
      target: /decisions/0053-select-proportional-release-retrospection-and-owner-led-product-learning.md
    - kind: references
      target: /decisions/0024-separate-stable-navigation-from-volatile-state.md
    - kind: references
      target: /decisions/0049-bind-adoption-evidence-to-an-authoritative-ledger.md
    - kind: references
      target: /decisions/0050-separate-adoption-observations-from-readiness-and-owner-disposition.md
    - kind: references
      target: /decisions/0051-select-the-v0-2-0-source-and-oci-publication-series.md
    - kind: references
      target: /decisions/0052-use-staged-evidence-maturity-for-early-adoption-trials.md
    - kind: references
      target: /lifecycles/evidence-gated-capability-evolution.md
    - kind: references
      target: /runbooks/deliver-bounded-self-hosted-slice.md
    - kind: references
      target: /runbooks/publish-version-bound-source-and-oci-release.md
    - kind: references
      target: /assessments/v0-2-0-source-and-oci-publication-result.md
    - kind: references
      target: /assessments/nextcloud-mail-v0-2-0-owner-led-adoption-trial-baseline.md
---

# v0.2.0 release-series retrospective

## Observation boundary

This retrospective is bound to protected `main` commit
`52e21722e2d24fc73e5b10e14996c127209e2599`, Git tree
`79d06b4d4e3e96d3c42b5b8436e8e7eb3c9ca38d`, after squash integration of PR
#152. The integrated tree is byte-identical to the accepted PR tree.

Integrated provider evidence for that subject is:

- Verification run `33165423066`: `SUCCESS`;
- CodeQL run `33165422711`: `SUCCESS`; and
- provider `extended`: reported separately as `SKIPPED`, not reinterpreted as
  execution evidence.

The immutable release inputs remain:

| Authority | Exact historical subject |
|---|---|
| Source tag | annotated `v0.2.0` |
| Tag object | `6d0357e075744ee316c725554d2e2c920b19a4dc` |
| Source commit | `39aa4f25bdf46811600d4a0f6f9c0da52b73c542` |
| Source tree | `866c8c489c9052c566bd65b6e798567d4a284f16` |
| Public-surface digest | `sha256:a85ac8dde00f1ed8fb0425de08597828e97c246ec17ce6556f3f222b27ddb1c1` |
| OCI manifest | `sha256:f89bf32c0c4b86bac71fa008579b2385e6ae39bf4822f685479c4f2cc22bfca4` |
| Publication run | `33124503631`, attempt 1 |
| Provenance | GitHub attestation `43531953` |

The evidence window covers:

```text
four historical Nextcloud Mail attempts
→ adoption-check v1
→ evidence-integrity repair
→ subject-bound assurance v2
→ v0.2.0 release candidate
→ source and OCI publication
→ rerun-authority correction
→ digest-bound reconciliation
→ staged OWNER-LED evidence transition
```

The earlier pre-publication retrospective and the later independent technical
evaluation were supplied by the accountable owner as external inputs to Work
Item 155. Their conclusions are re-evaluated here; their raw prose and changing
metrics are not copied into the repository as a second canonical authority.

## Executive verdict

```text
current release or integrity blocker     NONE IDENTIFIED
immutable source/OCI result              VALID
release-series controls                  EFFECTIVE, BUT OFTEN LATE
preparation and review cost              HIGHER THAN NECESSARY
independent adoption evidence            NOT ESTABLISHED
owner-led technical baseline             INTEGRATED
owner-led real task                      NOT STARTED
next substantive learning priority       REAL OWNER-LED TRIAL
```

The safeguards did what mattered most: they prevented a broken installed public
capability from becoming the release claim, kept the OCI effect to one authorized
first attempt, reconciled immutable identities and preserved honest non-claims.

The process also exposed a repeated pattern: several strong principles already
existed, but they were distributed across Decisions, runbooks, tests and provider
records rather than activated early through one phase-specific coverage,
freshness and effect-authority contract. Detection therefore happened through
late falsification, repeated candidate replacement and re-verification.

A second pattern is now equally important: assurance machinery grew faster than
measured product value. The correct response is not to discard exactness or
integrity controls. It is to move falsification earlier, reduce duplicated
coordination and prioritize real owner-led project evidence.

## Factual sequence and learning

| Phase | Observed result | Main learning |
|---|---|---|
| Four Mail attempts | All retained `REJECT` / `UNKNOWN` / `NO`; agents invented owners or provenance in documented attempts. | Structural validity is not semantic truth. Human project authority remains necessary. |
| Adoption-check v1 | One bounded command orchestrated candidate, project suites, runtime report and evidence publication. | Mechanical completion needed a common subject and transaction, but the initial trust model was incomplete. |
| Decision 0049 repair | Authoritative bytes moved to an append-only ledger; materialization and publication became descriptor-bound and reconciled. | Pathnames are names, not durable resource identities; same-user residual risk must remain explicit. |
| Decision 0050 / assurance v2 | Subject, observations, conditions, readiness policy and owner disposition became separate typed layers. | Mechanical readiness can be explicit without pretending to produce semantic acceptance. |
| PR #147 candidate | Clean installed-artifact execution found that source tests had missed a broken installed `adoption-check` evidence path. | Public capability verification must cover each shipping artifact by actual invocation. |
| PR #148 publication preparation | Workflow source, application source, immutable base, SB2 membership and freshness were bound before dispatch. | Publication-workflow provenance and application-source identity are different authorities. |
| OCI publication | One input-free dispatch, one attempt, digest read-back, digest-pulled verification, provenance and anonymous pull succeeded. | The immutable effect itself was efficient once preparation was complete. |
| PR #149 correction | `GITHUB_RUN_ATTEMPT=1` and `GITHUB_TRIGGERING_ACTOR` guards were added after publication review. | One-shot authority must include rerun semantics, not only original actor and workflow ref. |
| PR #150 reconciliation | The release verifier, public projections and durable result were bound to the registry digest. | Registry success is intermediate; consumer identity comes from read-back. |
| Work Item 146 lifecycle incident | A negated closure keyword and Issue reference caused an unintended provider lifecycle change; the item was reopened and the payload corrected. | Provider parsers are effect surfaces; natural-language negation is not a safe control. |
| PR #151 and PR #152 | The strict-independent contract was closed as superseded; staged evidence and the `OWNER-LED` baseline were integrated. | Experiment rigor must match product maturity and claim strength. |

## Intended claims and actual results

| Intended claim | Actual result |
|---|---|
| Publish one immutable source identity containing `adoption-check` v2. | Achieved. |
| Publish one public write-once `linux/amd64` OCI artifact. | Achieved with one dispatch and one attempt. |
| Verify the registry subject by digest, provenance and anonymous access. | Achieved and retained in the publication result. |
| Keep source, workflow, registry, released public surface and later current-main identities distinct. | Achieved after reconciliation. |
| Prevent rerun, replacement or ambiguous publication effects. | Publication itself satisfied the boundary; the missing explicit rerun guard was repaired immediately afterwards for future effects. |
| Make mechanical readiness explicit without claiming semantic adoption. | Achieved by assurance v2. |
| Establish independent adoption or practical value. | Not achieved and not claimed. |
| Admit a real early-stage learning path. | Achieved through the integrated `OWNER-LED` baseline; execution remains separate. |
| Establish production readiness, exact rebuild reproducibility or general security. | Not attempted and not claimed. |

## Controls that worked

The process was not a governance failure. These controls materially changed the
outcome:

- PRs remained draft until exact-subject review and owner authorization.
- Candidate movement invalidated prior acceptance and prompted fresh provider
  evidence.
- Independent falsification exercised installed artifacts rather than trusting
  source-suite success.
- Decision 0049 prevented project-owned execution from silently rewriting the
  authoritative evidence ledger.
- Decision 0050 stopped raw observations, readiness and owner disposition from
  collapsing into one generic `PASS`.
- Focused findings received RED-to-GREEN regression coverage.
- Protected `main`, CodeQL and named provider jobs kept integration observable.
- Publication was input-free, owner-triggered and read back from the registry.
- No `latest`, retry, replacement or second OCI publication occurred.
- The release Work Item survived merge and publication so reconciliation could
  happen before lifecycle completion.
- Negative experimental results and residual boundaries remained visible rather
  than being rewritten as success.

The goal of this retrospective is therefore not more strictness everywhere. It
is earlier, cheaper and better-routed use of controls that already proved useful.

## Findings that arrived late

### Evidence custody and resource identity

The initial evidence root allowed project-owned execution and authoritative
artifacts to share insufficiently separated pathname-visible custody. The repair
correctly moved authoritative bytes into a private append-only ledger and used
held descriptors, no-follow/no-replace operations and final reconciliation.

**Current status:** technically repaired for adoption-check by Decision 0049.
The residual same-user race and post-publication custody boundary remain explicit
and must not be overstated as isolation.

### Raw, validated and trusted assurance state

The initial result model allowed policy meaning and trust basis to remain partly
implicit in executable aggregation. Decision 0050 separated subject,
observations, conditions, named policy and owner disposition.

**Current status:** repaired for the v2 contract. Future convenience projections
must continue to consume the validated complete result rather than raw mappings.

### Pre-subject failure

A persistent Git snapshot failure conflicted with the rule that every retained
result names an exact subject. The final contract distinguishes pre-result
subject-acquisition failure from a subject-bound blocked prerequisite.

**Current status:** repaired and documented.

### Shipping-artifact behavior

The capability worked from a source checkout but the installed wheel initially
could not preserve the result evidence required by the release claim. Ordinary
source and unit tests did not expose that topology and packaging contract.

**Current status:** repaired for `v0.2.0`, and the release smoke exercises the
installed path. The broader capability-by-artifact coverage rule is still not a
small explicit matrix in the ordinary Definition of Done.

### Version and source identity

Package version, runtime label, source revision, public digest and image subject
were initially governed by several surfaces. The release series reconciled them
through exact invariants and read-back.

**Current status:** repaired for the release. Future releases must preserve the
invariant rather than copy `v0.2.0` constants.

### Evidence freshness

The candidate assessment originally carried PASS language whose exact measured
subject had moved after follow-up changes. The final record added an explicit
evidence-subject boundary and regression coverage.

**Current status:** substantially repaired. A provider status can still be green
while `extended` is skipped, so the exact execution portfolio remains a separate
observation.

### Provider effect authority

The publication workflow guarded original actor, ref and workflow identity, but
did not initially reject a provider rerun attempt or a different triggering
actor.

**Current status:** repaired by PR #149 for future publication runs. The reusable
release route should eventually carry a compact one-shot effect-authority
checklist rather than relying on incident memory.

### Lifecycle metadata parsing

GitHub interpreted a closure keyword and Issue reference despite natural-language
negation. Repository source truth did not prevent the provider-side lifecycle
effect.

**Current status:** the Work Item was reopened, the body corrected and the
ordinary delivery route records the parsing precaution. It remains a
provider-specific payload hazard, not a general source-code defect.

### B3 proportionality and competing contracts

The strict independent B3 design was treated as a release closeout gate even
though the present product question was earlier and narrower. That produced a
blocked contract, a competing candidate and coordination effort without new
product evidence.

**Current status:** repaired by Decision 0052 and PR #152. The strict method is
preserved for later maturity; the current stream is `OWNER-LED`.

### Product value and adoption cost

The release proves a technically controlled artifact and a truthful readiness
boundary. It does not prove that the mechanism creates enough value in a real
project to justify its complexity.

**Current status:** open by design. This is not a release blocker. It is the next
product-learning question.

## Root-cause analysis

| Area | Proximate problem | Contributing condition | Systemic cause | Why existing controls found it late |
|---|---|---|---|---|
| Evidence custody | Suite-visible paths could affect authoritative evidence. | Project execution and evidence materialization shared one local resource lifecycle. | No initial end-to-end trust-boundary model for assets, actors, identities and publication. | Tests covered the intended handshake, not an adversarial resource-lifecycle matrix. |
| Resource identity | A checked resource was later reacquired through a mutable name. | Analysis focused on final files more than parent and publication-root identity. | Paths were treated as identity rather than temporary names for resources. | Happy-path filesystem tests did not exercise substitution across every checkpoint. |
| Assurance API | Raw data and validated policy state were not fully distinct. | Readiness semantics lived in aggregation code. | Raw, validated and trusted states were not separate domain types. | Tests often began from already valid results. |
| Subject acquisition | A failed snapshot could not support an exact retained subject. | Failure handling tried to retain evidence after the subject boundary was lost. | Pre-subject and subject-bound failures were not separated. | Mocks represented transient rather than persistent acquisition failure. |
| Installed artifacts | Source success did not imply installed command success. | Runtime behavior depended on source-tree topology and canonical assets. | Verification was suite-oriented rather than capability-by-shipping-artifact oriented. | The public command was not actually invoked from every shipped form. |
| Version identity | Several surfaces could express release identity. | Defaults and copied literals were permissive. | More than one source of truth lacked a release-time equality invariant. | Metadata equality was not yet part of the release contract. |
| Chronology and projections | Attempt counts and current outcomes drifted across prose. | The same facts were manually repeated in several pages and tests. | Historical records, current navigation and provider state were insufficiently separated. | Literal wording assertions preserved stale current-state sentences. |
| Evidence freshness | PASS prose outlived the exact subject it measured. | Follow-up semantic and formatting commits came after the portfolio run. | Exact-run observations and durable contract knowledge shared one artifact without a complete freshness route. | `extended` was not actually executed at the provider boundary. |
| Publication authority | Rerun attempt and triggering actor were omitted from the guard. | The first-run path was reviewed more deeply than provider retry semantics. | Effect authority was modeled as actor plus ref, not the complete provider invocation identity. | No adversarial rerun matrix existed before publication. |
| Experiment proportionality | Strict independent coordination became an early-stage gate. | A stronger future claim was allowed to define the current learning process. | Evidence class, product stage and claim strength were not explicitly separated. | Process review optimized rigor before restating the immediate product question. |

The refined common cause is:

> Strong principles existed, but phase-specific routing and enforcement were
> incomplete, and product-stage proportionality was not explicit. The result was
> late activation of good controls and excessive investment in evidence before
> practical value was measured.

This is primarily a routing, coverage and prioritization problem. It does not
justify a generic workflow, attestation or policy engine.

## Re-evaluation of the earlier retrospective recommendations

| Earlier recommendation | Re-evaluation after the completed release | Disposition |
|---|---|---|
| Add a micro-retrospective to each Work Item. | Still valid. The current ordinary runbook closes last but has no explicit reflection step. | `P1`, separate normative slice. |
| Require formal RCA only on triggers. | Still valid. `v0.2.0` met multiple triggers: minor release, repeated resets, shipping-artifact defect, evidence invalidation and cross-trust publication. | Selected by Decision 0053; operational routing remains separate. |
| Use a standard causal structure. | Valid and used here: boundary, timeline, claims, causes, control escape, actions and non-conclusions. | Complete for this assessment. |
| Separate actions into `P0` / `P1` / `P2`. | Valid protection against retrospective-driven scope growth. | Selected and used below. |
| Create a canonical `v0.2.0` retrospective. | The publication delta is now available, so one final bounded assessment is appropriate. | This record. |
| Add a capability-by-artifact verification matrix. | Strongly validated by the installed-wheel defect. Existing release smoke partially implements it, but the rule remains dispersed. | `P1` before the next equivalent public release. |
| Add a generic exact-subject evidence manifest. | Exact-subject bodies, result records and provider runs now cover much of the need. A new generic manifest is not yet justified. | `P2`; require a second demonstrated use case. |
| Generalize the Decision-0049 cross-trust pattern. | The concrete pattern is valuable, but one adoption-check repair is insufficient evidence for a generic public primitive. | `P2`; keep domain-specific meanwhile. |
| Create one canonical B3 attempt register. | Staged evidence reduces the immediate pressure. Counts should not be duplicated, but a new register is most useful before a future strict `INDEPENDENT` experiment. | `P2`, deferred to that admission. |
| Execute provider-bound `extended` on exact release candidates. | Still valid. GitHub can report a required path successful while `extended` is skipped, and external execution found a real formatting defect. | `P1` before the next release candidate. |
| Add only a publication delta after immutable effects. | Correct. Source, OCI, provenance, rerun correction, reconciliation and staged-evidence transition are incorporated here rather than replaying raw ledgers. | Complete. |

## Re-evaluation of the independent technical evaluation

The external evaluation is useful because it executed public and adoption paths
rather than relying only on repository claims. Its strongest findings are
retained with these qualifications.

### Findings accepted as current signals

- The documented quick start, validation and deterministic context-pack path
  worked from a clean environment.
- Supply-chain hygiene and explicit claim limits are unusually strong for an
  early project.
- The strict adoption path has a high integration and diagnostic cost relative
  to the currently demonstrated user benefit.
- A user-input/configuration failure can be projected as `InternalError`, which
  weakens responsibility attribution.
- Fail-closed dependency ordering can produce a serial one-finding-per-run
  diagnostic experience.
- CLI option descriptions, path conventions and reader-facing prose can be
  clearer.
- Large critical functions and single-maintainer ownership create review and bus
  factor risk.
- Practical product utility remains unmeasured by a real accepted owner-led task.

### Qualifications applied

The reported code and word ratios are dated snapshots whose category boundaries
are partly judgemental. They are useful directionally, not stable repository
metrics or release gates.

The synthetic adopter was built from Gnostoa's own templates and does not
substitute for a real Nextcloud Mail trial. Its five-run sequence is diagnostic
evidence, not transfer evidence.

The four historical Mail attempts are controlled pre-B3 records, not four
successful independent experiments. Their negative semantic outcomes remain
important, but Decision 0052 now classifies the next path separately as
`OWNER-LED`.

The recommendation to make strict readiness succeed without
`RuntimeObservationAvailable` is not accepted as a change to
`gnostoa-review-ready/v1`. Gnostoa already exposes a minimal evaluation route and
now admits a lighter owner-led learning path. Strict mechanical readiness may
retain its stronger runtime-observation requirement.

The recommendation to require a human signature for every draft `owners` or
`verified_by` field is overbroad. The durable requirement is narrower: unknown
ownership remains unknown, stable knowledge needs human verification, and owner
disposition must bind an accountable actor and exact subject.

Freezing all new assessments until a strict B3 experiment would also be
counterproductive. The selected replacement is to avoid new assurance machinery
without a demonstrated blocker and to prioritize the real owner-led task.

`SemanticReviewRequired` being a constant normative condition is a legitimate
modeling smell, but it is documented and intentionally outside mechanical
readiness. Any move to an `obligations` model belongs to a future schema version,
not this release retrospective.

## Prioritized action register

No item below is admitted for implementation by this assessment or Decision
0053.

### P0 — current blocker

None identified. The immutable source, OCI artifact, provenance and reconciled
release presentation remain valid.

### P1 — next relevant cycle

| ID | Proposed result | Trigger / timing | Verification of a later implementation |
|---|---|---|---|
| P1.1 | Run one real bounded `OWNER-LED` Nextcloud Mail task and then a separate trial retrospective. | Immediate next substantive product-learning Work Item after release closeout. | Compact run record, exact prompt and subjects, material checks, owner disposition, utility score and retained evidence. |
| P1.2 | Distinguish adopter `InvalidInput` from tool `InternalError` and expose a concise condition-level reason. | Separate adoption-contract Work Item; may be confirmed during P1.1 but is already a concrete attribution defect. | Focused schema/contract tests plus a reproduced missing-or-invalid input case. |
| P1.3 | Record a capability-by-artifact verification matrix for every new public command. | Before the next release that adds or materially changes a public capability. | Actual invocation from source checkout, wheel, sdist and OCI for every claimed supported runtime; unsupported cells explicit. |
| P1.4 | Require one actual exact-ref `extended` execution for release candidates and complete one-shot provider-effect guards. | Before the next immutable source/OCI effect. | Provider run bound to the accepted subject; `extended` executed rather than skipped; actor, triggering actor, attempt, workflow ref, exact ref, input and absence guards tested. |
| P1.5 | Route micro-retrospection and formal triggers into the ordinary Gnostoa-self delivery knowledge. | Separate normative knowledge slice after this retrospective is accepted. | Fresh-agent reconstruction of the close-out questions and trigger decision without replaying this report. |

### P2 — research or trial-informed hypothesis

| ID | Hypothesis | Admission condition |
|---|---|---|
| P2.1 | A non-authoritative `diagnose` or `doctor` route can report independent preflight failures together without weakening fail-closed readiness. | P1.1 or another real adopter reproduces material serial diagnostic cost. |
| P2.2 | Better CLI help, path-layout examples and a shorter reader-facing status view materially reduce onboarding cost. | Measure orientation friction in P1.1 and choose the smallest observed repair. |
| P2.3 | One attempt register would reduce chronology drift before a future strict independent experiment. | A future `INDEPENDENT` Work Item is admitted or counts drift again. |
| P2.4 | A small external exact-subject evidence manifest would reduce repeated PR-body and provider reconciliation. | A second lifecycle demonstrates the same need beyond release-specific records. |
| P2.5 | Decision 0049's resource-ownership pattern should become reusable cross-trust guidance. | Another materially different same-host trust boundary validates the abstraction. |
| P2.6 | Splitting the largest adoption and quality-evidence functions would improve independent reviewability. | Product value is demonstrated and a concrete maintenance or defect pattern identifies the safe module boundary. |
| P2.7 | `SemanticReviewRequired` should move from measured conditions to explicit obligations in a future schema. | A version-3 contract is otherwise justified; no schema churn for aesthetics alone. |
| P2.8 | Reader-facing product prose should be compressed further. | A real user cannot recover the product, cost and limits from the existing front door within the intended evaluation window. |

### Explicitly not selected

- weakening exact source, OCI, provenance or evidence-integrity checks;
- removing the runtime-observation requirement from strict readiness merely to
  make the gate easier to pass;
- requiring signatures for every draft ownership placeholder;
- freezing all knowledge assessments;
- implementing a generic attestation, workflow, state-machine or policy engine;
- treating this action register as automatic admission; or
- delaying the first owner-led trial until every usability hypothesis is fixed.

## Proportional retrospective pattern

For ordinary close-out, retain only five answers when they add value:

1. expected outcome;
2. actual outcome;
3. late surprise;
4. control that worked or failed to activate; and
5. one candidate improvement.

Create a formal artifact only on a deliberate trigger: release, critical
near-miss, repeated candidate reset, shipping-artifact escape,
evidence-subject invalidation, new trust boundary or owner request.

A formal retrospective should contain:

- exact observation boundary;
- factual timeline;
- intended claim and actual result;
- trigger, proximate, contributing and systemic causes;
- why existing controls did not find the issue earlier;
- controls that worked;
- class-of-defect search;
- `prevent` / `detect` / `mitigate` actions;
- owner, priority, later verification and review point; and
- explicit non-conclusions.

This pattern is selected by Decision 0053, but its operational routing is not
implemented in Work Item 155.

## Non-conclusions

This retrospective does not:

- reopen or invalidate the immutable `v0.2.0` source or OCI release;
- claim exact-digest rebuild reproducibility, production readiness, general
  security or qualified legal clearance;
- establish independent adoption, upstream acceptance, productivity gain or
  product-market fit;
- execute or score the owner-led Mail trial;
- treat the external evaluation's dated counts as current canonical metrics;
- prove that every proposed action would create value;
- authorize any source, schema, policy, CI, provider or Mail mutation;
- complete the lifecycle of Work Item 146; or
- replace the later trial retrospective required after P1.1.
