---
type: Runbook
title: Deliver a bounded self-hosted slice
description: Short Gnostoa-self operational route from current-subject orientation through exact-candidate verification, authorized integration, subject re-binding and close-last reconciliation.
status: draft
generated:
  by: codex/gpt-5
  at: "2026-08-22T07:25:33Z"
sources:
  - id: delivery-practice-work-item
    resource: https://github.com/ktogias/gnostoa/issues/80
    title: Canonicalize bounded self-hosted delivery practice
x-project-knowledge:
  id: kit.runbook.deliver-bounded-self-hosted-slice
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governed-by
      target: /decisions/0036-canonicalize-bounded-self-hosted-delivery-practice.md
    - kind: governed-by
      target: /decisions/0053-require-lightweight-work-item-micro-retrospection.md
    - kind: depends-on
      target: /lifecycles/evidence-gated-capability-evolution.md
    - kind: references
      target: /requirements/retrospective-findings-require-explicit-admission.md
    - kind: references
      target: /decisions/0024-separate-stable-navigation-from-volatile-state.md
    - kind: references
      target: /runbooks/maintain-the-kit.md
    - kind: references
      target: /runbooks/publish-source-only-release.md
---

# Deliver a bounded self-hosted slice

**Scope: ordinary changes to Gnostoa itself.** This is an operational route, not
a second lifecycle and not adopter guidance. The
[evidence-gated lifecycle](../lifecycles/evidence-gated-capability-evolution.md)
owns epistemic order, gap classes, selection/admission and oracle limits.

## Compact task input

An ordinary task prompt normally supplies only the concrete task or selected
owner outcome, authoritative starting subject, admitted scope and exclusions,
task-specific stop conditions, material evidence, authorized effects and the
result needed for the next owner decision. There is no fixed length limit.

## Preconditions

- The current source and provider subject can be read back.
- The concrete task, admitted scope and accountable owner are known.
- Any required Work Item, Decision and pre-implementation evidence are present
  before implementation begins.
- When the proposed work originates from a finding, its finding provenance and
  admission state can be identified separately from the evidence that discovered
  it.

## Procedure

1. **Orient and read back the current subject.** Start through `AGENTS.md`; bind
   protected source, provider lifecycle and the active Work Item without replaying
   raw conversations. Before creating another Work Item or PR for the same outcome,
   read provider state for an existing open same-purpose record. Resume it when it
   already owns the outcome; otherwise explicitly separate or supersede it before
   creating a competing canonical path. Use Decision 0016's resume route.
2. **Classify the observed gap.** Apply the
   [canonical lifecycle](../lifecycles/evidence-gated-capability-evolution.md);
   do not infer a new mechanism or implementation from research or selection.
3. **Check finding provenance and admission.** When the proposed change comes from
   a retrospective, experiment, evaluation, review, incident analysis or similar
   finding, apply the
   [explicit-admission requirement](../requirements/retrospective-findings-require-explicit-admission.md).
   Capture the observation in its owning evidence first. Resume the existing
   same-purpose Work Item when it already owns the outcome; otherwise create one
   focused tracked Work Item with desired outcome, bounded acceptance criteria,
   scope and explicit admission condition. Issue creation is capture, not
   implementation admission and does not automatically become active WIP or
   `roadmap:now`. A lesson without a concrete actionable outcome may remain
   knowledge-only. Stop before implementation until a separate observable owner
   admission selects the work under the current classification, Decision,
   pre-implementation evidence and effect boundary.
4. **Acquire bounded evidence or research.** Load only what distinguishes the
   proposed result and preserve negative findings.
5. **Obtain an owner semantic choice when required.** Oracle or unresolved
   semantic limits remain human decisions.
6. **Name the proposed surface and class.** Use the generic
   [change workflow](../../guidance/workflows/propose-review-merge-change.md) and
   `policy/change-control.yaml`; reclassify upward if the real surface expands.
7. **Satisfy implementation admission.** Create or link required records and
   establish the applicable pre-implementation evidence before editing. A finding
   Work Item recorded for backlog capture satisfies durable tracking only; it does
   not satisfy this admission step until its separately declared admission state is
   observed.
8. **Make the smallest admitted change.** Follow the
   [verification-first workflow](../../guidance/workflows/develop-verification-first.md)
   and keep specialized semantics in their owning runbooks.
9. **Verify the exact candidate.** Inspect the final diff, identify the measured
   subject, run applicable local/runtime checks and record actual results.
10. **Verify the exact PR head.** Provider checks must bind to that head; inspect
    required jobs individually. A successful run does not turn `SKIPPED` into
    `PASS`.
11. **Obtain authority for the exact effect.** Repository preparation and green
    evidence do not authorize merge or another provider mutation. For release or
    publication effects, follow the specialized runbook instead.
12. **Perform only the authorized effect.** If the Work Item must survive merge,
    keep provider metadata and the prospective merge message free of automatic
    closing semantics; the
    [source-release runbook](publish-source-only-release.md) records the known
    GitHub parsing precaution.
13. **Read back integrated and provider state.** PR-head verification and the
    integrated-main revision are separate observations. Read the exact protected
    revision, changed paths, provider jobs and lifecycle state.
14. **Re-bind the subject and reconcile.** A new SHA alone does not invalidate
    evidence. Prove the relevant subject unchanged before reuse; when it changed
    materially, replay only affected evidence. Re-read navigation under
    [Decision 0024](../decisions/0024-separate-stable-navigation-from-volatile-state.md).
15. **Record the micro-retrospective.** Before closure, answer briefly: what was
    expected; what actually happened; what surprised us or was detected late;
    which existing control worked or failed to activate; and whether one concrete
    improvement is worth considering later. The close-out comment is normally
    sufficient. A finding is not automatic implementation admission; route a
    concrete follow-up through step 3 rather than starting it automatically.
16. **Close the Work Item last.** Close only after integrated/provider read-back,
    subject re-binding, reconciliation and the micro-retrospective succeed; then
    record the next owner decision without starting it automatically.

## Verification

Use the repository's current policy and container routes rather than copying a
fixed suite here. Record exact-candidate and integrated-main results separately,
including public-surface digest, executable/runtime-subject equality and X3 when
applicable. Provider command success is not authoritative read-back.

## Recovery

On subject drift, a failed required job, an unexpected provider effect or scope
expansion, stop before the next effect. Read back the authoritative state,
reclassify or re-bind as applicable, and return to the owner rather than silently
retargeting the slice.

## Fresh-agent falsification

Run the retrospective's fresh-agent test on the first naturally occurring
eligible ordinary slice. The agent should reconstruct this route from repository
knowledge using only task-specific input. This tests discoverability and process
reconstruction, not semantic autonomy or adopter transfer.
