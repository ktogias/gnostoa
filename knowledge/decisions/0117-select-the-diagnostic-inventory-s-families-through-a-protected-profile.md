---
type: Decision
title: Select the diagnostic inventory's families through a protected profile, before any producer runs
description: "The diagnostic inventory runs only what the producer tree's policy/diagnostic-profile.yaml selects: each family's producer, selectors and FULL and DIFF scopes, with complexity acquired per changed function. The choice is made before any producer starts, so nothing obtained is dropped; each family has its own coverage row, and the composite is their conjunction with the inventory's shared gaps. A profile in the analyzed tree is never read. The profile is unactivated, and the source binding stays UNVERIFIED."
status: draft
generated:
  by: anthropic/claude-opus-5-5
  at: "2026-10-24T17:48:21Z"
sources:
  - id: work-item
    resource: https://github.com/ktogias/gnostoa/issues/389
    title: Keep NORMAL merges possible while a vendor analyzer is unavailable
  - id: owner-strategy
    resource: https://github.com/ktogias/gnostoa/issues/389#issuecomment-6380978556
    title: "The owner's selection of A0: an independently justified NORMAL project-assurance profile"
  - id: owner-scope
    resource: https://github.com/ktogias/gnostoa/issues/389#issuecomment-6384969093
    title: "The owner's selection of A0-MP1 Option A: bounded implementation and qualification, not activation"
  - id: route
    resource: https://github.com/ktogias/gnostoa/issues/389#issuecomment-6381924685
    title: "The Router's A0-MP1 scope and risk contract"
  - id: migration-packet
    resource: https://github.com/ktogias/gnostoa/issues/389#issuecomment-6381812211
    title: The migration packet's paths, routines and delta
  - id: scope-consequence
    resource: https://github.com/ktogias/gnostoa/issues/389#issuecomment-6387171049
    title: "Amendment r4: file-level acquisition makes a selected DIFF scope fix-on-touch"
  - id: route-r4
    resource: https://github.com/ktogias/gnostoa/issues/389#issuecomment-6387291584
    title: "The Router's disposition of r4: alternatives retained for the admission packet"
  - id: architecture-review
    resource: https://github.com/ktogias/gnostoa/issues/389#issuecomment-6387305292
    title: "The PAO's slice-1 design checks R1 to R5"
  - id: pre-mutation
    resource: https://github.com/ktogias/gnostoa/issues/389#issuecomment-6387512548
    title: The pre-change evidence, lineage and prior art of this slice
  - id: reuse-review
    resource: ./0062-require-proportionate-prior-art-and-reuse-review.md
    title: Proportionate prior-art and reuse review
  - id: inheritance
    resource: ./0099-route-the-architecture-inheritance-gate-from-source.md
    title: The architecture inheritance gate
  - id: merge-admission
    resource: ./0112-admit-merges-through-a-required-provider-neutral-merge-admission-verdict.md
    title: The merge-admission verdict, whose declaration this slice leaves unchanged
x-project-knowledge:
  id: kit.decision.0117.select-the-diagnostic-inventory-s-families-through-a-protected-profile
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: references
      target: /decisions/0062-require-proportionate-prior-art-and-reuse-review.md
    - kind: references
      target: /decisions/0099-route-the-architecture-inheritance-gate-from-source.md
    - kind: references
      target: /decisions/0112-admit-merges-through-a-required-provider-neutral-merge-admission-verdict.md
---

# Select the diagnostic inventory's families through a protected profile, before any producer runs

## Context

The owner selected A0 for #389 (source `owner-strategy`), and then a bounded implementation
and qualification of its migration, not its activation (sources `owner-scope` and `route`). Its
first slice is the inventory's own: until now it ran every selector on every tracked
Python file, with one generic coverage status, so no scope could be chosen for a family
and no family's analysis could be told apart (source `migration-packet`, rows 1 and 2).

## Decision

1. **A protected profile selects what runs.** `policy/diagnostic-profile.yaml` names the
   families: each one's producer (mypy, Ruff or the complexity metric), its selectors
   (Ruff codes the inventory maps; the complexity threshold) and its FULL and DIFF
   scopes, as directory exclusions. The inventory reads it beside the collector's own
   code, as it finds its observer, never from the tree it analyzes or through the kit
   locator, whose `KNOWLEDGE_KIT_ROOT` can name the analyzed tree and, in the runtime
   image, names the image's kit while a checkout's code runs. The public collector
   takes no profile; a private path, for the tests and labelled qualification
   variants, takes one, and the record names which origin governed it. Its shape is
   checked by the jsonschema validator the guardrail manifest uses, and its cross-field
   rules in code; a profile that breaks either is refused before anything runs.
2. **Acquisition, never a filter.** A family runs on its FULL scope's files and on its
   DIFF scope's changed files, whole. Every finding obtained there is listed; one on an
   unchanged line is outside the DIFF projection, never dropped. Complexity measures
   only the functions a change adds a line to, chosen before any value is computed, by
   the DIFF projection's own predicate. A selector the profile omits is never in an
   argv. The losses that stay named are the DIFF projection's and the scopes': a
   deletion-only change, and a finding a change introduces on a line it did not add,
   are outside DIFF (listed when obtained, never dropped), and a file no selected scope
   reaches, such as an unchanged test file for typing, is not analyzed.
3. **Each family has its own row, and the composite is their conjunction.** A row is
   the family's own analysis of its targets, counted in files: COMPLETE only when the
   targets are known and each was analyzed, none included. With no base, or a failed
   comparison, a family whose DIFF scope reaches past its FULL one is INCOMPLETE, and
   its target count unknown. The composite keeps every shared gap and names each
   INCOMPLETE and PARTIAL family.
4. **Nothing is activated.** No assurance claim reads the inventory. The source binding
   stays `UNVERIFIED`, and no profile content changes it; its derivation comes with the
   disposition of the M8 residual: import resolution beyond `-I`, typeshed and the
   standard library, continuity between the two observations, and installed files
   their RECORD lists without a hash (source `migration-packet`, section B′).
   Authenticating the producing generation belongs to the readback route's slice.

## Consequences

- The profile holds the admitted contract's values (source `route`): typing and protected
  access on every changed Python file and on non-test FULL; literal secrets everywhere;
  complexity above 15 on changed functions only; PLR6301 and SIM117 not selected. They
  are qualification hypotheses, not accepted losses.
- Because mypy and Ruff acquire whole files, a selected DIFF scope makes every standing
  finding in a changed file listed, and so fix-on-touch (source `scope-consequence`). The
  alternatives, including dropping tests from those DIFF scopes, stay for the one
  evidence-backed admission packet (source `route-r4`).
- The inventory record is v3: it carries the profile, its canonical digest and origin,
  each family's row and the profile's Ruff selection.

## Prior-art and reuse disposition

The slice consumes the existing owners: `load_yaml` (duplicate keys refused) for the
protected file, located as `_OBSERVER` is, beside the collector's own code (never
through `toolkit_root`), jsonschema's `Draft202012Validator` for its shape,
`_diff_scope` and `_in_diff` for the comparison and its projection, `readback_coverage`
and `canonical_json` for the record. It extends `_run_producers`, `_run_ruff`,
`_run_complexity` and `_diagnostic_coverage`, and factors the comparison's error
handling into one `_compare` with two consumers, acquisition and annotation (source
`pre-mutation`, with its lineage table). External practice was inspected for shape only:
`.deepsource.toml` and `.codacy.yaml` (analyzers plus path scopes), reviewdog's
`-filter-mode` (a post-collection filter, which this contract forbids) and pre-commit's
per-hook `files`. No dependency is added and nothing is copied.

## Alternatives considered

- **The producers' native configuration** (Ruff `select`/`per-file-ignores`, mypy
  `exclude`): it cannot express DIFF-only acquisition, and `--isolated` with
  `--config-file=` deliberately ignores configuration files.
- **Selectors inside `policy/assurance-evidence.yaml`**: it would put producer
  configuration into the claim schema.
- **Collect everything, then project**: the contract forbids dropping obtained findings.

## Evidence

The pre-change evidence, lineage and prior art are in source `pre-mutation`.
