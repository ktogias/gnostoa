---
type: Decision
title: Select documentation-only remediation for Nextcloud Mail adoption
description: Select the smallest normative guidance correction for the measured Nextcloud Mail adoption failure and require the frozen fresh rerun to test its predicted benefit.
status: draft
generated:
  by: codex/gpt-5
  at: "2026-08-25T15:29:07Z"
sources:
  - id: nextcloud-mail-adoption-work-item
    resource: https://github.com/ktogias/gnostoa/issues/117
    title: Analyze and remediate the Nextcloud Mail minimal-adoption failure
  - id: nextcloud-mail-adoption-baseline
    resource: ../assessments/nextcloud-mail-adoption-baseline-and-root-cause.md
    title: Nextcloud Mail adoption baseline and root-cause analysis
  - id: nextcloud-mail-adoption-research
    resource: ../assessments/nextcloud-mail-adoption-external-practice-and-remediation-alternatives.md
    title: Nextcloud Mail adoption external-practice research and remediation alternatives
x-project-knowledge:
  id: kit.decision.0045.select-documentation-only-remediation-for-nextcloud-mail-adoption
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governed-by
      target: /decisions/0016-evolve-human-agent-workflow-through-bounded-self-hosted-slices.md
    - kind: references
      target: /lifecycles/evidence-gated-capability-evolution.md
    - kind: references
      target: /assessments/nextcloud-mail-adoption-baseline-and-root-cause.md
    - kind: references
      target: /assessments/nextcloud-mail-adoption-external-practice-and-remediation-alternatives.md
---

# Select documentation-only remediation for Nextcloud Mail adoption

Recorded by `codex/gpt-5` from the accountable maintainer's selection. The
choice of Alternative A1 and its bounded implementation surface are owner
semantics; this record is faithful transcription.

## Context

[Work Item #117](https://github.com/ktogias/gnostoa/issues/117) preserves the
complete baseline-to-rerun cycle. Its
[Phase-1 assessment](../assessments/nextcloud-mail-adoption-baseline-and-root-cause.md)
is authoritative for the observations, causal identifiers, evidence limits and
frozen fresh-rerun contract. Its
[Phase-2 research](../assessments/nextcloud-mail-adoption-external-practice-and-remediation-alternatives.md)
is authoritative for the dated external practices, Alternatives A0–A3 and their
costs, risks and rejection evidence.

Phase 1 found existing mechanisms for source/runtime lock validation, policy
validation, bundle validation and bounded-context generation. It also found a
distributed first-adoption route, a template-to-target naming translation and
repeated conflation of documentation, source, declared runtime and observed
execution identities. The same agent recovered substantially after following
the existing authorities. This evidence supports testing a smaller guidance
correction before adding a public executable mechanism.

The concrete proposed five-path change is `normative`: two generic adopter
workflows change meaning, while one focused contract test, this Decision and
self-knowledge navigation bind and verify the change. It changes no file format,
schema, validator, CLI, runtime or provider behavior.

## Decision

**A. Select A1.** Select **Alternative A1 — documentation-only correction** as
the smallest coherent remediation to test. Concentrate one compact, task-ordered
first verified adoption slice in the existing-project workflow and add one exact
core template-to-target and identity/route map to the bootstrap workflow. Link
existing detail rather than create a second adoption guide.

**B. First verified slice.** The existing-project route must distinguish a
minimal evaluation from durable adoption before repository-owned policy or CI
surface expands. It must stop when commitment or accountable ownership remains
unresolved rather than invent a person, team, provenance or acceptance. For a
durable slice it must identify the actual supported execution route, perform
structural validation, generate bounded context, classify unavailable project
suites as `BLOCKED`, and keep structural, context, project-suite,
semantic-owner and durable-adoption results independent.

**C. Bootstrap placement and identity boundary.** The bootstrap route must state
the three roots—`.knowledge-kit/`, `.knowledge/` and `knowledge/`—and map each
core reusable template to its exact project target. It must distinguish the
documentation identity, toolkit source identity, selected execution route and
published OCI identity. A declared image reference is not evidence that those
bytes executed. Correctly identity-bound and verified native, source-built and
immutable-OCI routes remain supported alternatives.

**D. Considered alternatives.** A0 (no change) is not selected because it leaves
the measured routing, naming and result-boundary friction untouched. A2
(tooling-assisted initialization) is not selected because the evidence does not
justify a new generator, public CLI contract or idempotent-write semantics. A3
(documentation plus a read-only preflight command) is not selected because its
new public executable observation contract is unnecessary before A1 is tested.
Nothing here admits those alternatives later without new evidence, owner
selection and implementation admission.

**E. Falsifiable prediction, not benefit.** This correction predicts that, under
the already-frozen original prompts and subjects, a genuinely fresh agent will
follow the routed procedure before authoring; keep commitment and unknown
authority explicit; bind one real supported execution route; create the correct
targets; run structural checks and bounded-context generation; classify absent
PHP/Composer as a project-suite `BLOCKED` result; and avoid claiming published
OCI execution unless that digest actually ran. No improvement, onboarding
benefit or transfer has yet been demonstrated.

**F. Behavioral test.** The frozen fresh rerun in the Phase-1 assessment is the
required behavioral falsification. Its Mail commit/tree, environment class,
original two minimal prompts, result dimensions, artifact evidence and
fresh-agent boundary remain unchanged. The improved documentation subject and
selected execution subject must be bound separately before the rerun. This
implementation slice must not execute the rerun or repair its result.

**G. Admitted surface.** Admit only:

- `guidance/workflows/adopt-existing-project.md`;
- `guidance/workflows/bootstrap-new-project.md`;
- one focused workflow-contract test in `tests/test_tools.py`;
- this Decision; and
- `knowledge/index.md` navigation.

No generator, scaffold, `knowledge init`, preflight command, template, schema,
file format, CLI alias, automatic ownership/provenance default, mutable image
tag, Mail mutation or provider effect is admitted. Scope expansion requires a
new owner stop and reclassification.

## Consequences

- The guidance correction is publicly inherited normative behavior, while the
  causal record and selection remain Gnostoa self-knowledge.
- Focused structural tests can prove that the selected guidance contract is
  present; they cannot establish its adoption benefit.
- The improved exact documentation candidate is exposed only after exact-head
  verification and accountable integration. The frozen rerun remains a later
  separate effect under the still-open Work Item.
- A repeated material failure under the frozen contract rejects or narrows A1;
  a successful rerun would remain one bounded experiment, not B3, general
  adopter transfer or Decision 0036 satisfaction.
