---
type: Decision
title: Evaluate semantic review assurance through bound evidence and an advisory deterministic gate
description: Keep review evidence, collection completeness, qualification, authority, judge identity, machine result and human authority separately bound.
status: draft
generated:
  by: agent:gpt-5.6-sol
  at: "2026-09-11T23:24:00Z"
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
  - id: opa-1170
    resource: https://github.com/open-policy-agent/opa/releases/tag/v1.17.0
    title: Open Policy Agent v1.17.0
  - id: sarif-210
    resource: https://docs.oasis-open.org/sarif/sarif/v2.1.0/errata01/os/sarif-v2.1.0-errata01-os-complete.html
    title: SARIF 2.1.0 Plus Errata 01
  - id: reviewdog-0210
    resource: https://github.com/reviewdog/reviewdog/releases/tag/v0.21.0
    title: reviewdog v0.21.0
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

Decision 0061 requires each supplied reviewer to remain separately attributable but cannot prove complete collection or reviewer independence. Issue #10 owns capability and independence semantics and requires established independence domains rather than raw event or product counts. Architecture R8 therefore separates reviewed subject, collection completeness, reviewer qualification, effective policy, decision-time freshness and executable judge identity.

The owner approved R8 after repeated architecture review reached `CONVERGED_NO_MATERIAL_FINDINGS`. This Decision materializes that architecture for one bounded advisory implementation.

## Prior-art and reuse disposition

- **Decision 0050 — selected pattern.** Reuse exact subject -> observation/assigned assurance -> explicit policy -> deterministic result -> separate owner disposition.
- **Decision 0058 — selected authority rule.** Evidence cannot create the authority needed to validate itself.
- **Decision 0005 — selected runtime mechanism.** Reuse the digest-pinned OCI runtime/source/public-surface binding for the post-bootstrap trusted judge; do not create an R2A service.
- **Gerrit 3.14.2 — Apache-2.0, pattern only.** Submit Requirements demonstrate project-owned review/submittability predicates, but Gerrit is a provider platform and lacks R2A's collection and #10 qualification contract.
- **OPA v1.17.0 — Apache-2.0, dependency rejected.** R2A v1 needs a small closed predicate set; Rego/runtime packaging would add unproven policy-engine complexity.
- **SARIF 2.1.0 Plus Errata 01 — OASIS Standard, pattern only.** Reuse result/finding identity and raw/normalized evidence ideas, not its static-analysis-centric contract.
- **reviewdog v0.21.0 — MIT, pattern only.** Reuse heterogeneous-output normalization precedent; it supplies no semantic-review authority or quorum.
- **Decisions 0063/0064/native review fixture — internal precedent only.** Preserve native evidence and attribution; do not mutate the historical fixture schema into the new public contract.

No third-party runtime or library is selected.

## Decision

### A. Keep R2A advisory and provider-neutral

Add `knowledge review-check` over already-collected file/retained evidence. It performs no reviewer triggering/waiting, live provider collection, reviewer selection, provider mutation, auto-fix/resolve/approval, human acceptance, merge/release authority or required merge check. Every v1 result contains `binding: false`.

### B. Publish only three schemas

Create `review-check-input`, `review-policy` and `review-gate-result`. Keep subject, observation, collection, qualification, evaluation-context, authority and judge concepts as `$defs` inside the input schema until a second real consumer requires independent versioning.

### C. Bind one exact semantic review subject

V1 binds canonical repository and change-request identity, exact head, and exactly one comparison identity: an exact Git merge-base commit. Same head with a different merge-base is a different reviewed subject. Base ref/tip is informational; integration freshness stays separate CI evidence. File mode treats merge-base as asserted input, not live Git proof.

### D. Make time an explicit input

`EvaluationContext` carries `mode: current_advisory|historical_replay`, `as_of`, and `judge_relation: prior_integrated|candidate_under_test`. The evaluator reads no wall clock. Every evidence/qualification/subject cut used by evaluation must be at or before `as_of`; future cuts are invalid input. Historical replay pins exact historical authority and judge identities.

### E. Preserve native review meaning without self-granted authority

Normalized recommendation is `APPROVE|REQUEST_CHANGES|COMMENT_ONLY|ABSTAIN|UNKNOWN`; positive prose without an admitted native recommendation state becomes `UNKNOWN`. Raw provider value remains separately retained. Findings and thread states remain separately attributable. Observation capability/domain claims never grant authority. Only proven ordered revisions of the same native object may collapse; ambiguous lineage remains visible.

### F. Make collection completeness explicit

Every source entry is `COMPLETE|PARTIAL|RATE_LIMITED|UNAVAILABLE|ERROR`. `No findings` is not a collection status. Every policy-required source must have an explicit entry. Missing or incomplete required collection cannot PASS and cannot be rewritten as absence.

### G. Consume #10 qualification through a bounded snapshot

Qualification status is `established|unestablished|revoked`; owner relation is `owner|non_owner|unknown`. Only established facts satisfy quorum/capability. Capability/domain meaning and establishment remain owned by #10; R2A implements no registry/discovery service.

### H. Prevent candidate self-weakening of policy, qualification and judge

Current-advisory authority comes from an independently selected prior-effective protected/integrated authority subject, never candidate paths. It binds exact review-policy and qualification snapshot identities plus the expected judge binding. Missing authority material is unresolved; there is no candidate fallback.

Judge binding records source revision, toolkit public-surface SHA-256, digest-pinned OCI runtime identity/revision, supported input schema versions and `accepted|revoked|deprecated|unknown` status. Only `accepted` is usable as `prior_integrated`. Expected judge identity is authority-owned, not candidate-lock-owned. Every required component must match exactly; missing/partial/mismatched/revoked/deprecated/unknown/unsupported state fails closed with no warning-only or candidate/native fallback preserving trusted status.

The trusted v1 judge route reuses Decision 0005's pinned OCI mechanism. Native execution remains development/recovery evidence but is not `prior_integrated` in v1. The first R2A implementation has no prior R2A judge; its self-dogfood is `candidate_under_test` evidence only.

### I. Use a closed ReviewPolicy family

`core/review-policy.yaml` is abstract/non-evaluatable. A project must resolve one explicit specialization. No-review is only explicit `review_requirement: none`. Required-review policy has closed `subject`, `collection`, `qualification`, `quorum`, `blockers` and `conflicts` sections. R2A introduces no DSL or policy engine and consumes, rather than redefines, the existing change class/human/merge controls.

Gnostoa-self v1 selects explicit no-review for mechanical changes; required semantic review for normal/normative/critical with minimum two established domains; required review for emergency with minimum one domain while timing remains change-control-owned; opaque #10 capability `semantic-review`; owner-authored review excluded from automated quorum; and one bounded file/fixture collection source `retained-review-evidence`.

Freshness is explicit policy data: each age-sensitive category declares finite `max_age` or explicit `not_age_sensitive`; silence is unresolved, never infinite permission.

### J. Emit one rich result

Top-level outcome is `PASS|BLOCKED|INCOMPLETE|CONFLICTING`. Every result retains exact evaluation/subject/authority/judge provenance, collection and qualification assessment, quorum/capability coverage, blockers/conflicts/exclusions, diagnostics and per-reviewer assessments. PASS reason is at least `POLICY_EXEMPT|REQUIREMENTS_SATISFIED`.

Precedence is: unresolved authority/policy/target -> INCOMPLETE; eligible known blocker -> BLOCKED even with other missing evidence; otherwise eligible disagreement -> CONFLICTING unless policy makes it a blocker; otherwise unmet collection/qualification/quorum/capability -> INCOMPLETE; only then PASS. Malformed/unsupported invocation is a tool/configuration error.

CLI exits are `PASS=0`, `BLOCKED=1`, configuration/tool error `=2`, `INCOMPLETE=3`, `CONFLICTING=4`. JSON is canonical; text is projection only.

### K. Keep implementation small

Use flat `tools/review_model.py`, `review_policy.py`, `review_evaluate.py`, `review_adapter_file.py`, `review_check.py` and the existing `tools/cli.py`. No review-assurance framework/package is introduced for one adapter.

## Consequences and limits

R2A proves deterministic advisory semantics over bound inputs. It does not establish malicious-host honesty, live-provider completeness, trusted native execution or merge authority. A future enforcing consumer requires a separate protected acquisition/consumer Decision.

## Revisit conditions

Revisit when a live provider adapter is admitted, #10 supplies reusable qualification discovery, policy needs expression power beyond closed sections, a verifiable native judge identity is established, or an enforcing consumer is selected.
