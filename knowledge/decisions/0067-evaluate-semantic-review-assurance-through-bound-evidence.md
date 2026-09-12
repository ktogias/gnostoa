---
type: Decision
title: Evaluate semantic review assurance through bound evidence and an advisory deterministic gate
description: Keep review evidence, collection completeness, qualification, authority, judge identity, normalization provenance, machine result and human authority separately bound.
status: draft
generated:
  by: agent:gpt-5.6-sol
  at: "2026-09-12T06:07:19Z"
sources:
  - id: work-item
    resource: https://github.com/ktogias/gnostoa/issues/11
    title: Semantic capture reconciliation and rationale completeness
  - id: owner-approval
    resource: https://github.com/ktogias/gnostoa/issues/11#issuecomment-5641780494
    title: Owner approval of D11-R2A architecture R8
  - id: architecture-r8
    resource: https://github.com/ktogias/gnostoa/issues/11#issuecomment-5641706425
    title: D11-R2A canonical architecture R8
  - id: convergence
    resource: https://github.com/ktogias/gnostoa/issues/11#issuecomment-5641717198
    title: D11-R2A architecture convergence record
  - id: review-capture
    resource: ./0061-retain-individual-agent-review-dispositions.md
    title: Decision 0061
  - id: prior-art-policy
    resource: ./0062-require-proportionate-prior-art-and-reuse-review.md
    title: Decision 0062
  - id: adoption-assurance
    resource: ./0050-separate-adoption-observations-from-readiness-and-owner-disposition.md
    title: Decision 0050
  - id: evidence-authority
    resource: ./0058-harden-behavioral-diagnosis-evidence-authority.md
    title: Decision 0058
  - id: runtime-binding
    resource: ./0005-container-first-runtime.md
    title: Decision 0005
  - id: capability-link
    resource: https://github.com/ktogias/gnostoa/issues/10#issuecomment-5640411302
    title: Issue 10 capability and independence linkage
  - id: gerrit-3142
    resource: https://www.gerritcodereview.com/3.14.html
    title: Gerrit Code Review 3.14.2
  - id: gerrit-license
    resource: https://github.com/GerritCodeReview/gerrit/blob/699633ef0642d21162d11bb958a3e3a1fc93817d/lib/LICENSE-Apache2.0
    title: Gerrit v3.14.2 exact-commit Apache-2.0 license text
  - id: opa-1170
    resource: https://github.com/open-policy-agent/opa/releases/tag/v1.17.0
    title: Open Policy Agent v1.17.0
  - id: opa-license
    resource: https://github.com/open-policy-agent/opa/blob/64a3625d33bc6ad8e7c40df03b76ce2fb3ab4d21/LICENSE
    title: Open Policy Agent v1.17.0 exact-commit Apache-2.0 license text
  - id: sarif-210
    resource: https://docs.oasis-open.org/sarif/sarif/v2.1.0/errata01/os/sarif-v2.1.0-errata01-os-complete.html
    title: SARIF 2.1.0 Plus Errata 01
  - id: oasis-ipr
    resource: https://www.oasis-open.org/policies-guidelines/ipr
    title: OASIS Intellectual Property Rights Policy
  - id: reviewdog-0210
    resource: https://github.com/reviewdog/reviewdog/releases/tag/v0.21.0
    title: reviewdog v0.21.0
  - id: reviewdog-license
    resource: https://github.com/reviewdog/reviewdog/blob/df70ed74df59de7ebfd9276afabd62ea2de4d7dd/LICENSE
    title: reviewdog v0.21.0 exact-commit MIT license text
x-project-knowledge:
  id: kit.decision.0067.evaluate-semantic-review-assurance-through-bound-evidence
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governed-by
      target: /decisions/0005-container-first-runtime.md
    - kind: governed-by
      target: /decisions/0062-require-proportionate-prior-art-and-reuse-review.md
    - kind: references
      target: /decisions/0050-separate-adoption-observations-from-readiness-and-owner-disposition.md
    - kind: references
      target: /decisions/0058-harden-behavioral-diagnosis-evidence-authority.md
    - kind: references
      target: /decisions/0061-retain-individual-agent-review-dispositions.md
---

# Evaluate semantic review assurance through bound evidence and an advisory deterministic gate

## Context

Decision 0061 requires each supplied reviewer to remain separately attributable but cannot prove complete collection or reviewer independence. Issue #10 owns capability and independence semantics and requires established independence domains rather than raw review-event or provider counts. Architecture R8 therefore separates reviewed subject, collection completeness, reviewer qualification, effective policy, decision-time freshness, normalization provenance and executable judge identity.

The accountable owner approved R8 before this recorded Decision revision. This Decision materializes the converged architecture for one bounded advisory implementation. It does not authorize merge enforcement or provider mutation.

## Prior-art and reuse disposition

- **Decision 0050 — selected pattern.** Reuse exact subject -> observation/assigned assurance -> explicit policy -> deterministic result -> separate owner disposition.
- **Decision 0058 — selected authority rule.** Evidence cannot create the authority needed to validate itself.
- **Decision 0005 — selected runtime mechanism.** Reuse the digest-pinned OCI runtime/source/public-surface binding for a post-bootstrap trusted judge; do not create an R2A service.
- **Gerrit 3.14.2 — Apache-2.0, pattern only.** The inspected release tag dereferences to exact commit `699633ef0642d21162d11bb958a3e3a1fc93817d`; its Apache-2.0 license text is linked above. Submit Requirements demonstrate project-owned review/submittability predicates, but Gerrit is a provider platform and lacks R2A collection and #10 qualification semantics.
- **OPA v1.17.0 — Apache-2.0, dependency rejected.** The inspected tag is exact commit `64a3625d33bc6ad8e7c40df03b76ce2fb3ab4d21`; its Apache-2.0 license text is linked above. R2A v1 needs a small closed predicate set; Rego/runtime packaging would add unproven policy-engine complexity.
- **SARIF 2.1.0 Plus Errata 01 — OASIS Standard, pattern only.** Reuse result/finding identity and raw/normalized-evidence ideas, not its static-analysis-centric contract. The versioned standard and IPR notice are provenance references only.
- **reviewdog v0.21.0 — MIT, pattern only.** The inspected release tag dereferences to exact commit `df70ed74df59de7ebfd9276afabd62ea2de4d7dd`; its MIT license text is linked above. Reuse heterogeneous-output normalization precedent; it supplies no semantic-review authority or quorum.
- **Decisions 0063/0064/native review fixture — internal precedent only.** Preserve native evidence and attribution; do not mutate the historical fixture schema into the new public contract.

R2A imports no Gerrit, OPA, SARIF or reviewdog code, schema text, runtime or dependency. This reference-only use creates no third-party redistribution obligation in the bounded slice. No third-party runtime or library is selected.

## Decision

### A. Keep R2A advisory and provider-neutral

Add `knowledge review-check` over already-collected file/retained evidence. It performs no reviewer triggering/waiting, live provider collection, reviewer selection, provider mutation, auto-fix/resolve/approval, human acceptance, merge/release authority or required merge check. Every v1 semantic result contains `binding: false`.

### B. Publish only three public schemas

Create `review-check-input`, `review-policy` and `review-gate-result`. Subject, native review state, normalized observation, collection, qualification, evaluation-context, authority, judge and normalization-provenance concepts remain `$defs` inside the input schema until an independent consumer/version cadence justifies extraction.

### C. Bind one exact semantic review subject

V1 binds canonical repository and change-request identity, exact head commit, and exactly one comparison identity: an exact Git merge-base commit. Same head with a different merge-base is a different reviewed subject. Base ref/tip is informational; integration freshness stays separate CI evidence. File mode treats merge-base as asserted input, not live Git proof.

### D. Make time explicit and bootstrap non-circular

`EvaluationContext` carries `mode: current_advisory|historical_replay`, RFC3339 `as_of`, and `judge_relation: prior_integrated|candidate_under_test`. The evaluator reads no wall clock.

For finite freshness:

```text
age_seconds = utc(as_of) - utc(applicable_cut)
current iff 0 <= age_seconds <= max_age
```

Subject freshness uses the subject observation cut; collection freshness applies independently to each required-source cut; qualification freshness uses the qualification snapshot cut. Every used cut must be `<= as_of`; a future cut is invalid input/configuration error. Exact-subject review observations still carry a cut even when their policy age is `not_age_sensitive`.

`current_advisory` requires an accepted `prior_integrated` judge. The first R2A implementation has no prior integrated R2A judge; therefore `current_advisory + candidate_under_test` is valid but returns `INCOMPLETE` and cannot PASS.

`historical_replay` is deterministic fixture/reproduction mode. During bootstrap, an explicitly synthetic fixture-only replay may exercise authority/judge pinning and normal policy/quorum/blocker/conflict semantics, but it makes no claim that those fixture identities existed in production. Real retained PR #239 / Issue #11 evidence predates R2A and can only be characterized as `candidate_under_test`; it is never assigned a fabricated historical trusted R2A judge. Factual replay of real R2A results becomes available only after an integrated R2A authority/judge record exists.

### E. Normalize native review state only through the active adapter

The closed normalized recommendation vocabulary is `APPROVE|REQUEST_CHANGES|COMMENT_ONLY|ABSTAIN|UNKNOWN`. Positive prose without an admitted native recommendation state becomes `UNKNOWN`. Raw/native provider state, findings and thread state remain separately retained and attributable. Observation capability/domain claims never grant authority. Only proven ordered revisions of the same native object may collapse; ambiguous lineage remains visible.

**Normalization admission is not caller-selectable.** In v1 the only authoritative normalization is recomputed by the active file adapter that is part of the selected judge implementation. The adapter consumes retained raw/native review state and emits an internal normalized observation plus deterministic `normalization_provenance` containing at least:

- `adapter_id`;
- `adapter_version`;
- stable `rule_id`; and
- digest/reference binding to the raw/native state used by that rule.

Caller- or fixture-supplied normalized values, `adapter_id`, `rule_id`, provenance objects or an `admitted` flag are claims only. They do not establish admission. When such claims are present, the adapter recomputes the authoritative normalized value/provenance from retained native state; a conflict between the claim and recomputed value is a configuration error and cannot affect semantic blocker/conflict/quorum state.

For `prior_integrated` use, the authority-owned judge binding pins the judge source revision/public-surface/OCI identity and therefore pins the accepted adapter implementation and closed normalization-rule implementation. ReviewPolicy does **not** contain provider mapping code, an `allowed_adapters` registry or a normalization DSL. Synthetic fixture-only replay uses the same selected adapter semantics and marks synthetic evidence as fixture-only; fixture labels do not create trust.

If retained native state is absent, unsupported, ambiguous or cannot be deterministically mapped by the active adapter, the authoritative recommendation is `UNKNOWN` and the observation gets no blocker/conflict authority. It remains visible for attribution and diagnostics.

### F. Make collection completeness explicit

Every source entry is `COMPLETE|PARTIAL|RATE_LIMITED|UNAVAILABLE|ERROR`. `No findings` is not a collection status. Every policy-required source must have an explicit collection entry. Missing or incomplete required collection cannot PASS and cannot be rewritten as absence, resolution or quorum.

### G. Consume #10 qualification through a bounded snapshot

Each qualification entry contains qualified reviewer/source identity, opaque `independence_domain_id`, opaque `capability_ids[]`, `status: established|unestablished|revoked`, validity/observation cut, `owner_relation: owner|non_owner|unknown`, applicable scope and provenance/basis. The snapshot itself carries exact snapshot ID/revision/SHA-256 and qualifying-authority identity.

Only established, current facts satisfy quorum/capability. R2A compares opaque domain/capability identifiers only; it neither interprets their meaning nor discovers/assigns them. Those semantics remain owned by #10.

### H. Prevent candidate self-weakening of policy, qualification and judge

Current-advisory authority comes from an independently selected prior-effective protected/integrated authority subject, never candidate paths. It binds exact review-policy and qualification snapshot identities plus expected judge binding. Missing authority material is unresolved; there is no candidate fallback.

Judge binding records source revision, toolkit public-surface SHA-256, digest-pinned OCI runtime identity/revision, supported input schema versions and `accepted|revoked|deprecated|unknown` status. Only `accepted` is usable as `prior_integrated`. Expected judge identity is authority-owned, not candidate-lock-owned. Every required component must match exactly.

Valid structured but unavailable, partial, mismatched, revoked, deprecated or unknown authority/judge material is unusable assurance and yields semantic `INCOMPLETE` with exit 3. Malformed authority/judge records or unsupported input schema are configuration errors with exit 2. Warning-only or candidate/native fallback cannot preserve trusted status.

The trusted v1 judge route reuses Decision 0005's pinned OCI mechanism. Native execution remains development/recovery evidence but is not `prior_integrated` in v1.

### I. Use one closed ReviewPolicy per invocation

`core/review-policy.yaml` is abstract/non-evaluatable. A project resolves one explicit specialization per invocation. No-review is only explicit `review_requirement: none`. Required-review policy has closed `subject`, `collection`, `qualification`, `quorum`, `blockers` and `conflicts` sections. `conflicts` compares eligible review dispositions under that one selected policy; policies themselves are never compared. R2A introduces no DSL or policy engine and consumes, rather than redefines, existing change-class/human/merge controls.

Before an observation can affect `blockers` or `conflicts`, it must:

1. bind exactly to the evaluated subject;
2. come from a policy-recognized, non-anonymous source;
3. have normalization recomputed/admitted by the active authority-bound adapter as defined in section E; and
4. satisfy applicable currentness rules.

Anonymous, unrecognized, stale, partially bound or caller-normalized-only evidence remains visible but gets no blocker or conflict authority merely by existing. Quorum/capability adds a stronger requirement: join to externally established #10 qualification facts including an established domain and every required capability. A recognized current blocker can therefore block without contributing a domain, preserving the intentional blocker-versus-quorum distinction without granting random evidence a veto.

Gnostoa-self v1 initially selects:

- mechanical: explicit `review_requirement: none`;
- normal/normative/critical: required semantic review with minimum two established domains;
- emergency: required review with minimum one established domain while timing remains change-control-owned;
- opaque #10 capability `semantic-review`;
- owner-authored review excluded from automated quorum; and
- bounded file/fixture collection source `retained-review-evidence`.

The two-domain threshold is an initial Gnostoa-self hypothesis: one domain would make independence-domain modeling non-discriminating and preserve correlated single-domain false confidence, while owner semantic acceptance remains a separate human gate. Emergency uses one established domain to preserve recovery availability under the separate emergency path. These are project parameters, not generic defaults. Revisit them using dogfood false-PASS, false-BLOCK, unavailable-review and owner-correction measurements.

Initial freshness is also project policy: current-advisory subject and required retained-collection cuts use `max_age: 900` seconds; exact-subject review observations use `not_age_sensitive`; qualification uses `max_age: 86400` seconds plus revocation. The 15-minute subject/collection window is a conservative asynchronous-refresh hypothesis; the one-day qualification window reflects slower-moving domain assignments. Revisit both after measured refresh failures, availability cost and owner corrections. Omitted age semantics is unresolved, never infinite permission.

### J. Emit one rich semantic result and one separate error envelope

Semantic outcome is `PASS|BLOCKED|INCOMPLETE|CONFLICTING`. Every result retains exact evaluation/subject/authority/judge provenance, collection/qualification assessment, quorum/capability coverage, blockers/conflicts/exclusions, diagnostics and per-reviewer assessments. PASS reason is at least `POLICY_EXEMPT|REQUIREMENTS_SATISFIED`.

Precedence is:

1. unresolved target/policy/authority/judge assurance -> `INCOMPLETE`;
2. eligible known blocker -> `BLOCKED` even if another required source is missing;
3. otherwise eligible disagreement -> `CONFLICTING` unless policy classifies it as blocker;
4. otherwise unmet collection/qualification/quorum/capability -> `INCOMPLETE`;
5. only then `PASS`.

Malformed invocation, malformed authority/judge records, unsupported input schema and tool execution failure are outside `review-gate-result`. They emit canonical transport JSON:

```json
{"error":{"code":"MALFORMED_INVOCATION|UNSUPPORTED_INPUT|CONFIGURATION_ERROR|TOOL_ERROR","message":"...","details":{}}}
```

`message` is a string and `details` an object, possibly empty. This is not a fourth public schema.

CLI exits are `PASS=0`, `BLOCKED=1`, configuration/tool error `=2`, `INCOMPLETE=3`, `CONFLICTING=4`. Semantic JSON is canonical; human text is projection only.

### K. Keep implementation small and RED-first

After the separately retained RED receipt is complete, use flat `tools/review_model.py`, `review_policy.py`, `review_evaluate.py`, `review_adapter_file.py`, `review_check.py` and existing `tools/cli.py`. No review-assurance framework/package is introduced for one adapter.

Production implementation remains blocked while the RED receipt contains `PENDING`. The RED harness must predate production schemas/policies/tools and retain exact commit, command, nonzero exit and bounded failing-output digest.

## Consequences

R2A proves deterministic advisory semantics over bound inputs. It does not establish malicious-host honesty, live-provider completeness, trusted native execution or merge authority. During bootstrap it can exercise deterministic semantics through synthetic fixture-only replay and real pre-R2A evidence through `candidate_under_test` characterization, but it cannot make a current-advisory PASS until a prior-integrated R2A judge exists.

The normalization boundary does not create a provider mapping registry: normalization semantics are pinned with the selected judge/adapter implementation, and caller claims cannot grant blocker/conflict authority.

A future enforcing consumer requires a separate protected acquisition/consumer Decision.

## Revisit conditions

Revisit when dogfood shows unacceptable false-PASS/false-BLOCK/owner-correction or refresh cost; when a live provider adapter is admitted; when a second adapter requires independently versioned mapping contracts; when #10 supplies reusable qualification discovery; when policy needs expression power beyond closed sections; when a verifiable native judge identity is established; or when an enforcing consumer is selected.
