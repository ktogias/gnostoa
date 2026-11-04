---
type: Decision
title: Retire DeepSource as merge evidence, and give every class the project inventory's claims
description: "The DeepSource exit of #389: DeepSource's requirement and claims leave the protected declaration, the project's own inventory gives every class its diff and full claims, and the readback acquires nothing from DeepSource. Retirement is a protected, recorded state, distinct from unavailable evidence: a bundle that still carries a DeepSource readback is refused as retired, and the evidence and the verdict name the retirement. The gate for the aspects DeepSource's shell analyzer and full reads gave, four inactive inventory families, is activated by its own change right after; Docker and secrets stay inactive."
status: draft
generated:
  by: anthropic/claude-opus-5-5
  at: "2026-11-04T09:00:00Z"
sources:
  - id: work-item
    resource: https://github.com/ktogias/gnostoa/issues/389
    title: Keep merges possible while a vendor analyzer is unavailable
  - id: owner-admission
    resource: https://github.com/ktogias/gnostoa/issues/389#issuecomment-6625223543
    title: "The owner's admission: prepare and qualify the dedicated DeepSource Exit PR"
  - id: owner-scope
    resource: https://github.com/ktogias/gnostoa/issues/389#issuecomment-6607594194
    title: "The owner's decision: a safe, coverage-preserving exit, inherited debt not a prerequisite"
  - id: owner-target
    resource: https://github.com/ktogias/gnostoa/issues/14#issuecomment-6607140258
    title: "The owner's direction: aspect-based assurance with interchangeable tools"
  - id: strategy-a
    resource: https://github.com/ktogias/gnostoa/issues/389#issuecomment-6587559616
    title: "The owner's Strategy A: today's profile through the cutover; secrets after F-a"
  - id: design
    resource: https://github.com/ktogias/gnostoa/issues/389#issuecomment-6626296806
    title: "The exit's design, aspect matrix, reconciliation and landing analysis, before the first edit"
  - id: pao
    resource: https://github.com/ktogias/gnostoa/issues/389#issuecomment-6626342451
    title: "PAO's assessment of the design, and of the transition's trusted git lookup"
  - id: sas
    resource: https://github.com/ktogias/gnostoa/issues/389#issuecomment-6626376230
    title: "SAS's assessment of the design and its residual risks"
  - id: verdict
    resource: ./0112-admit-merges-through-a-required-provider-neutral-merge-admission-verdict.md
    title: The merge-admission verdict whose declaration this changes
  - id: normal
    resource: ./0119-admit-normal-changes-through-the-project-s-own-inventory-and-keep-deepsource-for-every-other-class.md
    title: The NORMAL-only project claims and DeepSource for every other class, which this supersedes
  - id: families
    resource: ./0122-add-the-inventory-s-pinned-tool-and-secrets-families-inactive.md
    title: The inactive pinned tool families, four of which the change after this activates
  - id: split
    resource: https://github.com/ktogias/gnostoa/issues/389#issuecomment-6627327401
    title: "The design's sequencing change: the families' activation as its own qualified change"
x-project-knowledge:
  id: kit.decision.0130.retire-deepsource-as-merge-evidence
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: references
      target: /decisions/0112-admit-merges-through-a-required-provider-neutral-merge-admission-verdict.md
    - kind: supersedes
      target: /decisions/0119-admit-normal-changes-through-the-project-s-own-inventory-and-keep-deepsource-for-every-other-class.md
    - kind: references
      target: /decisions/0122-add-the-inventory-s-pinned-tool-and-secrets-families-inactive.md
---

# Retire DeepSource as merge evidence, and give every class the project inventory's claims

## Context

Since Decision 0119, NORMAL changes are admitted on the project's own inventory, and every
other class on DeepSource's diff and full reads (source `normal`). DeepSource states no
run-bound configuration, so its findings can never be matched as inherited debt, and a
change that touches a file inherits that file's whole DeepSource debt into M17. The owner
asked for a separate, reviewable exit (source `owner-admission`): the claim substitution,
an explicit retirement distinct from unavailable evidence, each still-required source and
security property kept effective, and every uncovered aspect named with its smallest
qualified remedy (sources `owner-scope`, `owner-target`).

## Decision

1. **The declaration.** `policy/assurance-evidence.yaml`, version 0.3.0, has no
   `deepsource-readback` requirement and no DeepSource claim. `project-risk-readback`, and
   its `project-diff-risk-findings` and `project-full-risk-findings` claims, apply to every
   merging class. Each claim keeps one item and one failure domain.
2. **Retirement is a recorded state, not an unavailable read.**
   - An unavailable provider still gives readbacks, marked `AUTH_UNAVAILABLE` or partial,
     and a declared item without a COMPLETE receipt denies. A retired provider gives none,
     and no item is declared for it.
   - Merge evidence keeps a protected table of retired providers, each with its Decision:
     `deepsource`, 0130. A bound or unbound bundle that carries a retired provider's
     readback is refused as retired, never read as an unknown readback.
   - The evidence always names the retired providers (`analyzer_retired`, possibly none),
     and the verdict requires that record and lists it for the approver
     (`retired_analyzers`), through a closed contract.
3. **No acquisition.** The readback makes no DeepSource read: neither the diff projection
   from GitHub's statuses and comments, nor the full GraphQL read. Its `deepsource` keyword
   survives only as `None`, and a reader handed to it is refused. The workflows no longer
   pass `DEEPSOURCE_API_TOKEN`; the secret stays in its environment for a rollback.
4. **The remedy for the aspects that would otherwise lose their gate is its own change.**
   Activating shell-lint, workflow-lint, gitlab-script and unsafe-calls, which on the whole
   tree of `main` `7cb731af` each measured complete with no finding (source `design`), is
   qualified and lands right after this one: it changes the protected profile's admitted
   contract, which three test modules pin, and makes the image build and the readback
   acquire actionlint and shellcheck (source `split`). Dockerfile-lint stays inactive until
   #477 repairs the Dockerfile's four hadolint findings, and secrets until F-a (source
   `strategy-a`).
5. **Kept for the cleanup after the exit.** The bundle contract keeps version 1 and its
   GitHub projection of statuses, check runs and review comments, which only DeepSource's
   diff read used; the `deepsource` keyword; and the adapter module with its tests.
   Changing them now would touch files whose inherited DeepSource debt the evaluator in
   force before this lands counts against the exit.

## Limits

- **Python bug risk, anti-pattern and performance over the whole tree** have no qualified
  replacement: Codacy and SonarCloud read changed code only, with their own catalogues.
  This is not a clone of a vendor catalogue (source `owner-target`). No remedy is planned
  here; accepting the gap, or asking for a qualified producer, is the owner's decision in
  the exit.
- **Shell, workflow and full-tree unsafe-call correctness** have no gate between this
  change and the activation that follows it.
- **Dockerfile correctness** has no gate until #477's repairs and dockerfile-lint's
  activation.
- **The two `BAN-B607` partial-path `git` calls** in `tools/quality_evidence.py`'s
  `_git_state` keep no gating reader once DeepSource is retired: no active family selects
  Ruff's `S607`. In CI their lookup resolves through the image's root-owned `PATH`, which
  PAO accepts as a trusted lookup for the interval (source `pao`); their repair, reusing
  `tools/exact_tree.py`'s trusted path, follows the exit.
- **The deepsource failure domain is lost.** The domains are github (checks, CodeQL and
  the project inventory), codacy and sonarcloud. No replacement domain is planned: one needs
  another qualified provider, a change of its own.
- **DeepSource's inherited findings** are no longer acquired. That neither disposes of
  them nor proves a replacement; the design record reconciles them by aspect (source
  `design`).

## Verification

- **RED first.** On `main` `7cb731af`, with only the tests changed, the new tests failed
  for the missing behaviour: each class but NORMAL denied without DeepSource; a DeepSource
  readback was accepted; the evidence and the verdict named no retirement; the runner read
  DeepSource and accepted a reader; and two workflows passed its token.
- **Negative controls.** A missing or partial project read, or any obtained finding, still
  denies every class.
- **The guards that kept the 1.0 verdicts** now compare every class as NORMAL was compared:
  as if DeepSource were complete, with the project's inventory complete.

## Consequences

- **Every class is admitted on Codacy, SonarCloud, CodeQL, the required checks and the
  project inventory.** DeepSource's status may still appear on a pull request; nothing
  reads it.
- **The project inventory's findings deny every class,** as M17 has always counted every
  finding obtained, and so will the four families' once they are active.
- **Rollback:** reverting this change restores the declaration, the acquisition and the
  token wiring; the token is still in its environment.
