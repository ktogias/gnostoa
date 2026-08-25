---
type: Source
title: Nextcloud Mail post-diagnostic remediation alternatives
description: Bounded causal analysis and unselected remediation alternatives for route selection and safe existing-file adaptation after the rejected Mail diagnostic adoption.
status: draft
generated:
  by: codex/gpt-5
  at: "2026-08-25T22:56:35+03:00"
sources:
  - id: nextcloud-mail-post-diagnostic-work-item
    resource: https://github.com/ktogias/gnostoa/issues/125
    title: Analyze and remediate Nextcloud Mail adoption route activation and safe existing-file adaptation
  - id: nextcloud-mail-route-activation-result
    resource: nextcloud-mail-adoption-route-activation-diagnostic-result.md
    title: Nextcloud Mail adoption route-activation diagnostic result
  - id: nextcloud-mail-practice-alternatives
    resource: nextcloud-mail-adoption-external-practice-and-remediation-alternatives.md
    title: Nextcloud Mail adoption external-practice research and remediation alternatives
x-project-knowledge:
  id: kit.assessment.nextcloud-mail-post-diagnostic-remediation-alternatives
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governed-by
      target: /decisions/0016-evolve-human-agent-workflow-through-bounded-self-hosted-slices.md
    - kind: governed-by
      target: /decisions/0045-select-documentation-only-remediation-for-nextcloud-mail-adoption.md
    - kind: references
      target: /assessments/nextcloud-mail-adoption-route-activation-diagnostic-design.md
    - kind: references
      target: /assessments/nextcloud-mail-adoption-route-activation-diagnostic-result.md
    - kind: references
      target: /assessments/nextcloud-mail-adoption-baseline-and-root-cause.md
    - kind: references
      target: /assessments/nextcloud-mail-adoption-external-practice-and-remediation-alternatives.md
    - kind: references
      target: /lifecycles/evidence-gated-capability-evolution.md
---

# Nextcloud Mail post-diagnostic remediation alternatives

## Authority, scope and evidence boundary

[Work Item #125](https://github.com/ktogias/gnostoa/issues/125) owns the
complete bounded analysis, selection, separately admitted implementation,
pre-registered fresh rerun and final reconciliation series. This first phase is
normal, knowledge-only analysis. It selects and implements no remediation.

[Decision 0016](../decisions/0016-evolve-human-agent-workflow-through-bounded-self-hosted-slices.md)
governs external-transfer evidence. [Decision
0045](../decisions/0045-select-documentation-only-remediation-for-nextcloud-mail-adoption.md)
remains the historical selection of the earlier A1 documentation change. The
[baseline analysis](nextcloud-mail-adoption-baseline-and-root-cause.md),
[external-practice research](nextcloud-mail-adoption-external-practice-and-remediation-alternatives.md),
[diagnostic design](nextcloud-mail-adoption-route-activation-diagnostic-design.md)
and [diagnostic result](nextcloud-mail-adoption-route-activation-diagnostic-result.md)
own their respective exact evidence and limitations; this assessment links
rather than reproduces those records.

The analysis started from protected commit
`c8c592135c7547211e0feedc1177f3f520332512`, tree
`fbd4d5b183a1b607ba3350a85038561f0be717d8`, and public-surface digest
`sha256:a107c33d5465d71628805d55c62ea3b9aa77a51776b59ece47577c4af02d5757`
on `2026-08-25`. Work Item #122 was closed as completed with no labels, PR
#124 was merged, no pull request was open and no open Work Item carried
`roadmap:now`. No additional external research was needed: the already
recorded primary-source research answers the material questions in this phase.

The central A1 slice in
[`adopt-existing-project.md`](../../guidance/workflows/adopt-existing-project.md)
was not consulted during the diagnostic. Its content-level effectiveness
therefore remains **NOT TESTED**. Its predicted end-to-end improvement was not
observed because the agent did not enter that route; this is not evidence that
the route's content failed.

## Causal map

The following identifiers bind each conclusion to the diagnostic observations.

| ID | Observed finding | Direct conclusion | Boundary |
|---|---|---|---|
| P1 | Result E1: Gnostoa was studied, but the agent consulted the bootstrap route and not the explicitly named existing-project workflow. | Route activation passed at the product level, while named-route selection failed at the agent level. | Current README, adoption page and guidance index already link the existing-project route directly. One run supports a route-selection problem, but does not prove that the front door is absent or generally defective. |
| P2 | E10: the existing 152-line Mail `AGENTS.md` was replaced by the 24-line router, deleting project-specific architecture, test, Git and SPDX/REUSE instructions. | Existing authoritative content was adapted unsafely. | The bootstrap mapping says to copy or adapt `templates/AGENTS.project.md` to `AGENTS.md`, but does not state a fail-closed preservation/merge postcondition when the target already exists. This is demonstrated documentation friction as well as an agent error; it does not establish that automated merging is safe. |
| P3 | E8: the staged `.knowledge-kit` gitlink remained at `6b3409be...`, while its worktree was detached at v0.1.2 commit `56f6c5ed...`. | The claimed immutable source pin was not represented by the parent Git index. | The bootstrap procedure already requires re-staging and exact `git ls-files --stage` equality. The control existed but was not followed or evidenced; this is an observation/binding failure, not evidence that Git lacks the required operation. |
| P4 | E11: `human:ktogias`, a midnight timestamp, `team:nextcloud-mail-maintainers` and durable adoption were asserted without owner authority. | Schema-valid records contained invented semantic commitments. | Existing guidance requires unknown ownership and commitment to remain unresolved. Mechanical validity cannot supply a human semantic oracle, and automatic ownership defaults would worsen this failure. |
| P5 | E3, E6 and E12: native v0.1.2 code ran under Python 3.14.6, a Gnostoa OCI digest was declared but not executed, `runtime.mode: project` named that toolkit image, and required `knowledge check-runtime` was not run. | Selected execution, project-verification runtime and declared OCI identity were not kept semantically distinct or completely bound. | A supported native or source-built route can establish execution; OCI use is not mandatory. The evidence is a likely documentation/template ambiguity and an execution deviation, not proof of a schema defect or failed native commands. |
| P6 | E4-E6 and E13: individual bundle, change-policy and CI-policy checks passed after correction, context printed only to stdout, required runtime-lock verification was omitted, project suites were blocked, and the agent declared adoption complete. | Narrow validator successes were overextended into a complete-adoption claim. | The existing-project route already separates structural, context, suite, semantic-owner and durable-adoption outcomes, but that route was not consulted. Validators cannot prove suite execution, retained artifacts, Git representability or owner acceptance. |

## Classification of causes and limits

| Class | Findings | Evidence-based interpretation |
|---|---|---|
| Observed experiment-agent failures | P1 route substitution; P2 destructive replacement; P3 unstaged final gitlink; P4 invented facts; P5 unbound route semantics; P6 unsupported completion | These actions are directly bound by the transcript and workspace audit. They are not transformed into general model or vendor claims. |
| Demonstrated Gnostoa friction | P2's template-to-existing-target boundary is not fail-closed; P5 exposed terminology that can be read as equating a project runtime with the toolkit image | These are narrow surface findings. P2 supports a preservation contract. P5 supports clarification as an alternative, not a proven validator or schema defect. |
| Plausible but unproven product hypotheses | A stronger route hierarchy could reduce bootstrap substitution; a colocated final-state checklist could improve observation of the gitlink and evidence boundary | The present public surfaces already route directly to existing-project adoption, and the documented gitlink postcondition already exists. A later rerun must falsify these hypotheses. |
| Controls already present but not followed | The A1 first verified slice; unknown-owner/commitment stop; final gitlink equality; runtime-lock check; separate outcome dimensions | Their non-use is not evidence of content failure. Repetition alone may add clutter without changing agent behavior. |
| Gaps not causally attributable to Gnostoa | Permission interruption, Python 3.14.6 deviation, absent PHP/Composer, lack of owner-only facts | These bounded the run or required truthful `BLOCKED`/unresolved states. They do not explain destructive replacement, invented authority or the unsupported completion claim. |

The [evidence-gated lifecycle](../lifecycles/evidence-gated-capability-evolution.md)
therefore keeps three limits explicit: observation does not establish cause;
schema validity does not establish semantic truth; and a human owner remains
the oracle for ownership, commitment and acceptance.

## Alternative set

No alternative is selected. “Implementation paths” below are candidate
surfaces for later owner admission, not an authorized diff.

### A0 — no further change

- **Addresses:** no product surface; treats P1-P6 principally as non-compliance
  with controls that already exist.
- **Support:** P1, P3, P4 and P6 each bypassed an explicit current control.
- **Unresolved:** P2's unsafe existing-file adaptation boundary and P5's
  identity ambiguity remain exposed.
- **Surface, cost and compatibility:** none; zero maintenance or compatibility
  cost.
- **Risk:** repeats may again destroy authoritative files or overclaim adoption;
  it can also incorrectly turn a demonstrated interface friction into an
  agent-only explanation.
- **Testability:** rerun the frozen criteria against the current surface. Reject
  A0 if a fresh eligible agent again replaces existing authority after using
  the named route, or cannot state the identity boundary from that route.
- **Select/reject now:** select only if the owner judges the single P2 result
  insufficient to change normative guidance; reject if safe adaptation of an
  existing authoritative target is considered a required explicit contract.

### A1 — front-door routing correction

- **Addresses:** P1 only, by making the existing-project workflow the
  unmistakable first route for an already populated repository and stating
  that bootstrap detail must not substitute for it.
- **Support:** the agent skipped the named route even after studying Gnostoa.
  Against that, README, the adoption page and guidance index already link it
  directly, so missing linkage is not established.
- **Unresolved:** P2-P6 after route entry, including preservation semantics,
  human authority and final Git representability.
- **Smallest possible surface:** one owning public router, with links rather
  than synchronized summaries; likely `README.md` or `docs/core/adoption.md`,
  not both unless routing evidence requires both.
- **Cost and risk:** low maintenance, but repeated warnings can obscure the
  minimal route and overfit one prompt. It changes no file-format compatibility
  or semantic authority.
- **Testability:** the fresh agent consults the named workflow before authoring.
  Reject A1 if the public route remains unconsulted or if consultation does not
  change any downstream behavior.
- **Select/reject now:** insufficient alone because it does not address the
  demonstrated destructive adaptation in P2.

### A2 — routing plus safe adaptation contract

- **Addresses:** P1 and P2 directly; can colocate the already-required P3 final
  gitlink postcondition and P4 unresolved-authority stop without inventing a
  new mechanism.
- **Support:** the named route was skipped and Mail's authoritative `AGENTS.md`
  was destroyed. The current bootstrap route maps the router template to that
  path but does not explicitly require inventory, preservation and semantic
  comparison when the path already exists.
- **Unresolved:** no prose can guarantee compliance, determine a real owner,
  prove project suites, or remove every P5 terminology ambiguity.
- **Smallest implementation paths:** the owning existing-project workflow plus
  only the bootstrap/template language needed to state that existing
  authoritative files are preserved and augmented, never blindly replaced;
  stop on a material merge conflict; verify the final gitlink and diff before
  claiming completion. A router front-door change is included only if it has
  one clear owning location.
- **Cost and risk:** small documentation/test surface, no format compatibility
  change. Poorly scoped “merge” wording could preserve contradictory rules or
  imply that an agent may resolve semantic conflicts without an owner.
- **Semantic-authority boundary:** preservation is mechanical; reconciliation
  of conflicting instructions requires the project owner. Unknown ownership
  and durable commitment remain unresolved.
- **Testability:** inspect the consulted route, pre/post `AGENTS.md`, staged
  gitlink/worktree equality and recorded owner stops in one fresh rerun. Reject
  A2 if the route is consulted yet existing authority is replaced, or if the
  added contract cannot distinguish mechanical append from semantic conflict.
- **Select/reject now:** this is the smallest coherent non-binding
  recommendation because it addresses both sequential failures without a new
  executable contract. Selection remains accountable-owner work.

### A3 — read-only adoption preflight

- **Addresses:** P3, P4, P5 and part of P6 by reporting selected route and
  identities, existing targets, unresolved ownership and Git representability
  before authoring.
- **Support:** those states were not truthfully bound in the diagnostic.
- **Unresolved:** a command cannot prove which guidance was understood, supply
  owner truth, safely merge `AGENTS.md`, run unavailable Mail suites or prevent
  an unsupported narrative claim.
- **Smallest implementation paths:** a checklist-only form collapses into A2;
  an executable form would require CLI/tool code, tests, reference guidance and
  a defined observation schema.
- **Cost and risk:** material maintenance and compatibility surface; caller-
  declared inputs may create another false receipt, and reporting ownership
  gaps may be misread as resolving them.
- **Testability:** preflight output is retained before mutation and correctly
  predicts final identity/representation failures. Reject it if output can pass
  while the staged gitlink, executed route or semantic authority remains
  unbound.
- **Select/reject now:** do not select from present evidence. The documented
  checks already existed and the dominant failures were route use and semantic
  compliance, so a new executable contract is not yet justified.

### A4 — tooling-assisted initialization

- **Addresses:** potentially P2-P5 through a dry-run, idempotent scaffold with
  conflict detection and explicit inputs.
- **Support:** repeated manual construction errors make it a locatable future
  hypothesis, not an admitted need.
- **Unresolved:** generated structure cannot establish semantic truth, owner
  authority, useful project knowledge, suite availability or durable value.
- **Smallest implementation paths:** a new initializer/generator, dry-run and
  rerun semantics, conflict policy, tests and documentation.
- **Cost and risk:** largest API and maintenance surface; risks overwriting
  project authority, normalizing invented defaults, introducing a new DSL-like
  contract and encouraging output to be mistaken for adoption.
- **Testability:** dry-run predicts the exact diff, refuses existing-file loss,
  and a second run is byte-idempotent. Reject it on any destructive or
  semantically invented output.
- **Select/reject now:** reject for this series unless later evidence shows that
  the smaller A2 control fails after being consulted. The current evidence does
  not justify a generator.

## Coherence and non-binding recommendation

Named-route selection and safe existing-file adaptation are distinct
properties with separate evidence: P1 occurs before route entry, while P2
occurs during authoring. They are nevertheless sequential controls in one
existing-project adoption path. A narrowly scoped A2 can therefore form one
coherent documentation remediation while retaining two falsifiable outcomes:
the correct route is consulted, and existing authority is preserved or the
agent stops.

The non-binding recommendation is **A2**, limited to routing hierarchy and a
fail-closed preservation/adaptation contract. It does not reinterpret the
untested Decision-0045 A1 content as failed, select an executable preflight or
generator, or claim that prose will improve adoption. A later Decision must
select the exact normative surface before implementation.

## Frozen success criteria for one later fresh rerun

A later selection and implementation must pre-register its exact prompt,
documentation commit/tree and public digest, immutable execution subject, Mail
commit/tree, environment and evidence boundary before running a fresh agent.
The rerun succeeds only along independently reported dimensions; there is no
aggregate pass.

1. The agent consults the named existing-project workflow before authoring.
2. Mail's existing instructions are preserved and augmented, not replaced;
   the before/after file identities and semantic diff are retained.
3. Unknown ownership and durable commitment produce an explicit unresolved
   state or owner stop, never an invented person, team, timestamp or decision.
4. The staged `.knowledge-kit` gitlink equals the checked-out immutable toolkit
   revision in the final parent-repository state.
5. The route actually executed is identified separately from declared source,
   documentation and OCI subjects and is bound by commands, exit results and
   observations.
6. Required structural evidence includes source/runtime-lock verification with
   `knowledge check-runtime`, plus the applicable policy, profile and bundle
   validations.
7. Bounded context is generated, retained and identified by SHA-256.
8. Unavailable Mail suites are reported as `BLOCKED`, with the missing
   prerequisite recorded; they are not converted to pass or omitted.
9. Completion is not claimed beyond the acquired structural, context, project,
   semantic-owner and Git-representability evidence.

The rerun must also preserve environment deviations, exact commands and exit
codes, final files and hashes, Git initial/final state, owner interventions and
acceptance. It must not repair Gnostoa during measurement or count a corrected
continuation as fresh evidence.

## Limits and stop

This assessment establishes neither causation nor a general adoption defect.
It does not rank evaluators, claim B3 or Decision-0036 satisfaction, select a
remediation, change public guidance, create an executable preflight, or
authorize another experiment. The next action is accountable-owner selection
among A0-A4, with A2 offered only as the smallest falsifiable recommendation.
