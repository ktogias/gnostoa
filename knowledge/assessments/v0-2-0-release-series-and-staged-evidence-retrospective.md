---
type: Source
title: v0.2.0 release-series and staged-evidence transition retrospective
description: Bounded retrospective over the v0.2.0 source and OCI publication, reconciliation, staged-evidence transition and retrospective-process duplication, retaining durable lessons without automatically admitting backlog implementation.
status: draft
generated:
  by: chatgpt/gpt-5.6-sol
  at: "2026-08-28T17:40:00+03:00"
sources:
  - id: retrospective-work-item
    resource: https://github.com/ktogias/gnostoa/issues/153
    title: Retrospect the v0.2.0 release series and staged-evidence transition
  - id: release-work-item
    resource: https://github.com/ktogias/gnostoa/issues/146
    title: Publish Gnostoa v0.2.0 source and OCI release series
  - id: release-candidate
    resource: https://github.com/ktogias/gnostoa/pull/147
    title: Prepare the v0.2.0 release candidate
  - id: publication-binding
    resource: https://github.com/ktogias/gnostoa/pull/148
    title: Bind the v0.2.0 OCI publication workflow
  - id: rerun-authority-correction
    resource: https://github.com/ktogias/gnostoa/pull/149
    title: Reject OCI publication reruns
  - id: release-reconciliation
    resource: https://github.com/ktogias/gnostoa/pull/150
    title: Reconcile the v0.2.0 source and OCI publication result
  - id: staged-evidence-integration
    resource: https://github.com/ktogias/gnostoa/pull/152
    title: Adopt staged evidence maturity and the owner-led trial baseline
  - id: external-evaluation-provenance
    resource: https://github.com/ktogias/gnostoa/issues/153#issuecomment-5453859124
    title: Owner-supplied technical evaluation provenance
  - id: duplicate-retrospective-work-item
    resource: https://github.com/ktogias/gnostoa/issues/155
    title: Duplicate retrospective Work Item
  - id: duplicate-retrospective-pr
    resource: https://github.com/ktogias/gnostoa/pull/156
    title: Superseded duplicate retrospective candidate
x-project-knowledge:
  id: kit.assessment.v0-2-0-release-series-and-staged-evidence-retrospective
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governed-by
      target: /decisions/0051-select-the-v0-2-0-source-and-oci-publication-series.md
    - kind: governed-by
      target: /decisions/0052-use-staged-evidence-maturity-for-early-adoption-trials.md
    - kind: references
      target: /decisions/0024-separate-stable-navigation-from-volatile-state.md
    - kind: references
      target: /decisions/0049-bind-adoption-evidence-to-an-authoritative-ledger.md
    - kind: references
      target: /decisions/0050-separate-adoption-observations-from-readiness-and-owner-disposition.md
    - kind: references
      target: /assessments/v0-2-0-release-candidate-and-source-boundary-result.md
    - kind: references
      target: /assessments/v0-2-0-source-and-oci-publication-result.md
    - kind: references
      target: /assessments/nextcloud-mail-v0-2-0-owner-led-adoption-trial-baseline.md
    - kind: references
      target: /failure-modes/publication-baseline-review-drift.md
    - kind: references
      target: /failure-modes/reverse-centaur-review-overload.md
---

# v0.2.0 release-series and staged-evidence transition retrospective

## Observation boundary and evidence

The source observation boundary is protected `main` commit
`52e21722e2d24fc73e5b10e14996c127209e2599`, tree
`79d06b4d4e3e96d3c42b5b8436e8e7eb3c9ca38d`, after squash integration of PR
#152. The accepted PR #152 tree and integrated tree are byte-identical.
Integrated Verification `33165423066` and CodeQL `33165422711` succeeded;
provider `extended` was `SKIPPED` and is not reinterpreted as execution evidence.

The immutable release remains:

| Authority | Exact identity |
|---|---|
| Source tag | annotated `v0.2.0` |
| Tag object | `6d0357e075744ee316c725554d2e2c920b19a4dc` |
| Source commit | `39aa4f25bdf46811600d4a0f6f9c0da52b73c542` |
| Source tree | `866c8c489c9052c566bd65b6e798567d4a284f16` |
| Public-surface digest | `sha256:a85ac8dde00f1ed8fb0425de08597828e97c246ec17ce6556f3f222b27ddb1c1` |
| OCI manifest | `sha256:f89bf32c0c4b86bac71fa008579b2385e6ae39bf4822f685479c4f2cc22bfca4` |
| Publication run | `33124503631`, attempt 1 |
| Provenance | GitHub attestation `43531953` |
| Integrated release-route read-back | `33145955880` |
| Release-presentation reconciliation | `33146175529` |

Work Item #146 was explicitly reconciled and completed after PR #152 integration.
Its final two criteria were checked, `roadmap:now` was removed and the provider
state was read back as `CLOSED / COMPLETED`. That lifecycle completion is not a
new release effect.

### Owner-supplied technical evaluation

The retained technical evaluation **displays** the date 27 August 2026. The same
artifact states a reviewed repository range through commit `52e2172…`, whose
commit timestamp is `2026-08-28T10:59:10Z`. The displayed date is therefore
presentation metadata only; it is not used as creation-time or freshness
evidence. The evaluation is an attributed external input, not canonical provider
truth and not independent-adopter evidence. The owner retains the exact artifact
bytes:

```text
artifact: Αξιολόγηση Gnostoa(2).html
bytes: 73150
sha256: 430fe5be949c9ff2921a0bde0b5bb22e06439731912c24b14e0e092a5cf68335
displayed report date: 2026-08-27 (presentation metadata only)
reported repository range: 6714d70… through 52e2172…
reviewed-through commit timestamp: 2026-08-28T10:59:10Z
reported environment: fresh clone, Python 3.11.15
evaluator identity: not encoded in the retained artifact
```

Its reproduced execution observations may inform findings and hypotheses. Its
line counts, word counts and ratios remain dated snapshots. Its synthetic adopter
is not treated as a real adoption result.

## Executive result

```text
current release or integrity blocker     NONE IDENTIFIED
immutable source/OCI result              VALID
release-series controls                  EFFECTIVE, BUT OFTEN LATE
preparation and review cost              HIGHER THAN NECESSARY
independent adoption evidence            NOT ESTABLISHED
owner-led baseline                       INTEGRATED
owner-led real task                      NOT STARTED
next substantive product-learning step   REAL OWNER-LED TRIAL
```

The technical release series succeeded. Strong controls caught real defects and
bounded irreversible effects. The process also showed that useful controls were
often activated late, while coordination and evidence work grew faster than new
real-project value evidence.

## Factual sequence and causal interpretation

### The early B3 work produced real product learning

The start of the Nextcloud Mail adoption work was **not** wasted bureaucracy.
Four controlled attempts ended `REJECT / UNKNOWN / NO` and demonstrated that
structurally valid knowledge could still be semantically false. Three authoring
attempts invented ownership, verifier or provenance facts; the frozen fresh-agent
rerun stopped before writing knowledge.

Those negative results directly motivated the bounded `adoption-check` selected
by Decision 0047. Subsequent falsification and review of that implementation
motivated Decision 0049's evidence-integrity repair and Decision 0050's
assurance-v2 model. The initial B3/pre-B3 work therefore functioned as productive
falsification.

What later became disproportionate was different: strict independently owned B3
coordination was allowed to remain an immediate release-closeout prerequisite
before practical value had been measured in even one owner-involved real task.
Decision 0052 corrected that mismatch without relabelling any earlier rejection.

### Shipping-artifact falsification caught a release defect

The release-candidate work found that source-suite success did not imply clean
installed behavior. The installed `adoption-check` could initially terminate
before retaining the evidence required by its public claim. Focused repair and
clean wheel/sdist invocation closed the defect before publication.

The durable lesson is capability-by-shipping-artifact verification: public
commands should be actually invoked from the shipped forms that claim to support
them, rather than inferred from source-tree tests alone.

### Publication succeeded once; rerun hardening came afterwards

The actual OCI publication run `33124503631` was one input-free dispatch,
attempt 1, with actor and triggering actor `ktogias`, and no rerun, rebuild or
replacement. That observed effect satisfied the selected one-shot boundary.

PR #149 was **post-publication hardening**. It added explicit
`GITHUB_RUN_ATTEMPT == 1` and triggering-actor rejection for future publication
runs after review discovered that provider rerun semantics had not been fully
modeled. The release remains valid; the reusable route became explicitly
fail-closed against reruns afterwards.

### Provider lifecycle parsing caused two unintended closures

Work Item #146 was unintentionally closed twice by provider parsing of closure
keywords associated with the Issue reference: once after the release-candidate
integration and again after reconciliation. Both effects were detected through
provider read-back and reversed. The final completion was performed explicitly
after the owner-led baseline integration and read-back.

The lesson is provider-specific but durable at the payload boundary: natural
language negation is not a control over GitHub's lifecycle parser. Work Items that
must survive merge require lifecycle-safe PR bodies and merge payloads.

### The retrospective itself duplicated its own work

After Work Item #153 and draft PR #154 already owned the release-series
retrospective, duplicate Work Item #155 and draft PR #156 were created for the
same outcome. PR #156 also expanded the change into a second retrospective, a
new Decision and a much larger governance package. The duplicate path was later
recognized, closed without merge and retained only as analytical input.

**Proximate cause:** current provider state for the already-active retrospective
was not re-read before creating a new Work Item and candidate.

**Contributing condition:** long-running, multi-turn coordination made the newest
local analysis appear like a new admission boundary instead of a continuation of
an existing one.

**Systemic lesson:** orientation and resume are part of correctness. Before
creating another Gnostoa-self Work Item or PR for an outcome, read the provider
for an existing open same-purpose record and continue it when applicable. If a
materially different path is needed, explicitly supersede or separate the old
path first.

This incident is especially important because it occurred **inside the
retrospective process itself**: the mechanism intended to reduce evidence
amplification briefly amplified evidence and review surfaces. It therefore
supports a lightweight micro-retrospective and resume-before-create rule rather
than a heavier retrospective framework.

## Controls that earned their cost

Retain these controls at the boundaries where they proved useful:

- exact source, tag, tree, public digest, OCI digest and provenance binding;
- Decision 0049's authoritative evidence ledger and explicit residual same-user
  boundary;
- Decision 0050's separation of observations, conditions, readiness policy and
  owner disposition;
- actual shipping-artifact execution for public capabilities;
- explicit effect authority before immutable publication;
- provider read-back after source, registry and lifecycle effects;
- exact accepted-tree versus integrated-tree reconciliation;
- the rule that `SKIPPED` is not execution evidence; and
- bounded human semantic judgement at oracle limits.

The objective is not to weaken these controls. It is to invoke the right ones
earlier and avoid duplicating coordination around them.

## Friction and avoidable cost

- Semantic review and artifact-level falsification frequently arrived after a
  candidate already looked ready, causing exact-head replacement and replay.
- Stable history, mutable provider state and current-facing prose were sometimes
  repeated in multiple places, creating chronology and freshness drift.
- The strict independent-B3 closeout path briefly competed with the later
  owner-led path.
- Provider lifecycle keywords created two unintended effects despite negative
  natural-language wording.
- The retrospective itself forked into duplicate Work Items and PRs before the
  existing active path was re-read.
- The owner-supplied synthetic-adopter review found material setup friction, but
  real project utility remains unmeasured.

## Durable lessons

1. **Preserve exactness at irreversible boundaries.** Exact identities, effect
   authority and provider read-back materially prevented or exposed defects.
2. **Falsify public capability at the shipping artifact.** Source tests are not a
   substitute for executing the installed forms that carry the claim.
3. **Match evidence rigor to claim strength and product maturity.** `OWNER-LED`
   learning is appropriate now; `INDEPENDENT` evidence remains available for
   stronger later claims.
4. **Prefer semantic invariants over volatile literal chronology.** Historical
   records, current projections and provider state have different authorities.
5. **Treat human attention as finite.** More evidence and more canonical records
   are not automatically more assurance.
6. **Resume before creating.** Provider-state orientation must precede a new
   Work Item or PR for an apparently new slice.
7. **Close each Work Item with a tiny reflection.** Five short questions are
   enough to capture late findings and one candidate improvement without making
   every change produce a formal retrospective artifact.

The owner selected lesson 7 and the resume-before-create clarification as the
small permanent policy in Decision 0053. No broader formal-RCA framework or
P0/P1/P2 governance taxonomy is selected by this slice.

## Retained follow-up hypotheses

No current release/integrity `P0` exists. The real owner-led trial is the next
**product-learning priority**, not a release blocker.

| Timing | Hypothesis | Admission condition |
|---|---|---|
| Next | Run one real bounded `OWNER-LED` Mail task and measure practical value. | Owner selects a reversible real task and compact run record. |
| Before next equivalent public-capability release | Make capability-by-shipping-artifact coverage explicit for source, wheel, sdist, OCI and supported runtimes as applicable. | A public capability or shipping claim changes. |
| Before next equivalent immutable release | Obtain actual exact-ref `extended` execution rather than relying on provider `SKIPPED`. | A release candidate reaches semantic freeze. |
| Focused reproduction | Distinguish adopter `InvalidInput` from tool `InternalError` and expose a concise reason if the reported scenario reproduces. | Reproduce the owner-supplied missing/mislocated bundle scenario. |
| If real trial repeats the friction | Consider a non-authoritative diagnostic route and clearer CLI/path guidance. | Serial setup friction occurs in a real owner-led task. |
| Later | Decompose large adoption functions. | Review defects, change pressure or multi-maintainer needs justify smaller seams. |
| Later maturity | Run strict `INDEPENDENT` adoption. | Wider use or stronger public claims justify external coordination cost. |

The external evaluation's code/word ratios are not permanent budgets. They
support only the directional conclusion that assurance investment grew faster
than measured practical value.

## Next owner-led trial

Bind one real reversible Mail task, exact prompt, frozen target-project subject,
model/session context, owner constraints, available verification and stop
conditions. Record only what is useful for learning:

- orientation time and attempts;
- incorrect assumptions, especially invented owners, provenance or semantics;
- owner questions and interventions;
- knowledge/context artifacts actually used;
- task verification and unresolved risk;
- owner disposition and owner-assessed utility; and
- whether any durable Gnostoa adoption is worth retaining.

Do not force strict mechanical `READY` merely to exercise machinery. Use the
strict route only when its project-side integration is material to the task.

## Disposition and non-conclusions

The `v0.2.0` release is technically successful and reconciled. No current release
or integrity blocker is identified. Decision 0052 is the appropriate maturity
correction, and the next unresolved product question is practical utility in one
real owner-led task.

This retrospective does not establish independent adoption, upstream acceptance,
product-market fit, productivity gain, production readiness or general security.
It does not execute the trial, mutate Mail, contact upstream, publish an artifact
or implement the retained follow-up hypotheses.
