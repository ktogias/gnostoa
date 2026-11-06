---
type: Decision
title: Read optional providers' complete reports for findings, never for coverage
description: "The optional-report slice of #389 (Ariadne #14): an optional provider's read is recorded in the analyzer bundle under its own protected status, between required and retired. Missing, failed or stale, it changes no claim: each declared aspect keeps the qualified evidence that covers it. Complete for the exact head, its findings, report-only ones included, join the findings M17 lists, so each stays open until a fix removes it from the head's report or, for a finding with a run-bound configuration identity, an evidence-backed dismissal enters the protected debt ledger (Decision 0129). DeepSource moves from retired to optional; Decision 0130's no-acquisition rule is amended for findings only."
status: draft
generated:
  by: anthropic/claude-opus-5-5
  at: "2026-11-05T14:40:00Z"
sources:
  - id: work-item
    resource: https://github.com/ktogias/gnostoa/issues/389
    title: Keep merges possible while a vendor analyzer is unavailable
  - id: owner-direction
    resource: https://github.com/ktogias/gnostoa/issues/389#issuecomment-6652941418
    title: "The owner's direction: read completed reviews from optional tools"
  - id: owner-acceptance
    resource: https://github.com/ktogias/gnostoa/issues/389#issuecomment-6659619541
    title: "The owner's acceptance: a missing result covered, a report-only finding kept open"
  - id: ariadne
    resource: https://github.com/ktogias/gnostoa/issues/14#issuecomment-6652945562
    title: "Ariadne's next assurance step: completed reports from optional tools"
  - id: lineage
    resource: https://github.com/ktogias/gnostoa/issues/389#issuecomment-6653559617
    title: "The slice's lineage and falsifier matrix, before any edit"
  - id: pao
    resource: https://github.com/ktogias/gnostoa/issues/389#issuecomment-6657812185
    title: "PAO's rulings: the canonical bundle, the analyzer-domain disposition, 0130 amended"
  - id: pao-scope
    resource: https://github.com/ktogias/gnostoa/issues/389#issuecomment-6662582106
    title: "PAO's clarification: an applicable finding lies in a changed file"
  - id: pao-dismissal
    resource: https://github.com/ktogias/gnostoa/issues/389#issuecomment-6673563051
    title: "PAO's ruling: a ledger dismissal stays under Decision 0129's strict match"
  - id: pao-semantics
    resource: https://github.com/ktogias/gnostoa/issues/389#issuecomment-6673640776
    title: "PAO's ruling: an applicable optional finding denies until it is resolved"
  - id: exit
    resource: ./0130-retire-deepsource-as-merge-evidence-and-give-every-class-the-project-inventory.md
    title: The DeepSource exit, whose no-acquisition rule this amends
  - id: ledger
    resource: ./0129-match-inherited-analyzer-debt-against-a-protected-ledger.md
    title: The protected debt ledger, through which a dismissal is recorded
x-project-knowledge:
  id: kit.decision.0132.read-optional-providers-complete-reports-for-findings-never-for-coverage
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: references
      target: /decisions/0130-retire-deepsource-as-merge-evidence-and-give-every-class-the-project-inventory.md
    - kind: references
      target: /decisions/0129-match-inherited-analyzer-debt-against-a-protected-ledger.md
---

# Read optional providers' complete reports for findings, never for coverage

## Context

The owner asks that a missing or failed optional tool never hold a merge when qualified
evidence covers each required aspect. A completed report for the exact candidate must still
be read, and each applicable finding in it, report-only ones included, must stay open until a
verified fix or an evidence-backed dismissal (source `owner-direction`). On `main`, a provider
is either required, with a declared item, or retired (Decision 0130), and a bundle that carries
a retired provider's readback is refused whole. There is nothing in between (source `lineage`,
row L4). PAO ruled the placement: an optional status in the canonical analyzer bundle; the
disposition in the analyzer evidence domain; and 0130's no-acquisition rule amended (source `pao`).

## Decision

1. **A protected table of optional providers** in merge evidence, beside the retired one:
   each with its Decision. DeepSource moves from retired to optional (this Decision).
2. **An optional readback is recorded, never required.** The evidence lists each optional
   read's provider, scope, coverage and reason (`analyzer_optional`). It maps to no declared
   item, so missing, failed or partial, it changes no claim.
3. **Exact head and applicable scope only.** A complete optional read for the subject's head
   adds its applicable findings to the findings M17 lists, tagged by provider. A finding is
   applicable when it lies in a file the change request changes (source `pao-scope`). Its
   findings on untouched files are recorded in the bundle, but they do not enter the
   verdict. M17 evaluates an applicable one exactly as it does any finding it lists, with no
   separate reducer, so an open one denies until it is resolved (source `pao-semantics`). A read for another head is recorded as `STALE` and adds none.
4. **A finding stays open until disposed of on evidence.** A fix removes it from the head's
   complete report. A dismissal is an entry in the protected debt ledger (Decision 0129): read
   only from protected `main`, strictly matched, never self-asserted by the candidate. A clean
   result from another provider disposes of nothing. Decision 0129 governs that match strictly:
   only a finding with a run-bound configuration identity can meet an entry. DeepSource's
   capability discovery is `CURRENT_NOT_RUN_BOUND`, so its findings close only by a fix
   (source `pao-dismissal`).
5. **Decision 0130 §3 is amended for findings only.** The readback may acquire an optional
   provider's complete report, with its own credential, under the readback's existing bounds.
   Its reads never become merge coverage.

## Limits

- **Only configuration-bound findings can be dismissed** (Decision 0129, on `main` since #480).
  A DeepSource finding closes only by a fix. The dismissal case is shown on a configuration-bound
  finding, the project inventory's. That narrows the owner's acceptance case, and the owner's
  admission confirms it.
- **Report-only findings reach the reviewers through M17's listing.** They are not posted as
  inline comments.
- **Applicability is at the changed files,** by PAO's ruling. The owner's admission confirms
  it, or narrows it to the changed lines. With files, a touched file brings the provider's
  existing findings in that file into review. With lines, only findings on the lines the
  change adds or modifies come in.

## Verification

- **RED first:** `tests/test_optional_reports.py`'s 8 acceptance tests fail on `main`
  `6b6c8501`, as on `794a1eee`, for the missing behaviour: `main` refuses whole a bundle that
  carries DeepSource's readback.
- **They cover:**
  - an unavailable optional source with its aspects covered;
  - a complete optional report that never covers a missing required item;
  - a report-only finding listed and denying, and its closure when the head's report no longer lists it;
  - a stale report counted as stale;
  - a failed run recorded as failed and finding nothing, against a findings-bearing run, which is a finding;
  - a finding on an untouched file kept out of the verdict.
- **Still to add:** duplicate report and comment observations; the bounded read at the
  pre-merge evidence cut; and a configuration-bound finding dismissed through the ledger.
