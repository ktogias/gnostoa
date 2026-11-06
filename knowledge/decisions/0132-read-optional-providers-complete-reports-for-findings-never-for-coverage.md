---
type: Decision
title: Read optional providers' complete reports for findings, never for coverage
description: "The optional-report slice of #389 (Ariadne #14): an optional provider's read is recorded in the analyzer bundle under its own protected status, between required and retired. Missing, failed or stale, it changes no claim: each declared aspect keeps the qualified evidence that covers it. Complete for the exact head, its findings in the files the change modifies, report-only ones included, are compared with the provider's complete read for the merge base: a pre-existing one, with an unchanged enclosing scope, stays listed and does not deny; an introduced or unknown one joins the findings M17 lists and stays open until a fix removes it or an independent eligible approver's false-positive disposition names it at the exact head. DeepSource moves from retired to optional; Decision 0130's no-acquisition rule is amended for findings only."
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
  - id: owner-revision
    resource: https://github.com/ktogias/gnostoa/issues/389#issuecomment-6676021682
    title: "The owner's revision: a verified disposition, a baseline differential, a scoped token"
  - id: pao-revision
    resource: https://github.com/ktogias/gnostoa/issues/389#issuecomment-6676228030
    title: "PAO's rulings: the disposition in an eligible approval, comparability without a run-bound configuration"
  - id: owner-admission
    resource: https://github.com/ktogias/gnostoa/issues/389#issuecomment-6676472012
    title: "The owner's admission: the same occurrence, one to one, and no worsening"
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
3. **What the change introduces or worsens decides, against the merge base.** A complete
   optional read for the subject's head is applicable in the files the change request
   modifies (source `pao-scope`); its findings elsewhere are recorded in the bundle and do not
   enter the verdict. The readback also acquires the same provider's complete read for the
   pull request's merge base, under the same bounds, as that provider's `BASE` readback, and
   hashes each base finding's enclosing scope at the base. Each applicable head finding is then
   (sources `owner-revision`, `pao-revision`):
   - **pre-existing** when the base read is complete for the exact merge base and holds the
     same occurrence, one to one, no worse (source `owner-admission`). Head and base findings
     are grouped by rule, path, message and enclosing scope, each scope hashed at its own
     commit, and a group's scope must be byte-identical at both. Its head occurrences are
     pre-existing only when the base group holds as many, paired in line order, and none is
     more severe than its pair in the provider's own severity order. One base occurrence never
     accounts for two at the head. A pre-existing finding stays listed, with
     `configuration_provenance: unproven` when the provider states no run-bound configuration,
     and on a complete read of the required evidence it does not deny; on an incomplete one
     it counts, as the ledger's matches do;
   - **introduced** when no base group corresponds, or its count or a severity differs for the
     worse, a regression on a line the change did not edit included;
   - **unknown** when the base read is missing, incomplete or for another commit. Absence of
     comparable evidence never establishes pre-existence.

   M17 evaluates an introduced or unknown finding exactly as it does any finding it lists,
   with no separate reducer, so it denies until it is resolved (source `pao-semantics`). A
   finding the provider shows both in its complete report and in an inline comment is one
   finding, by the provider's native id, with both provenances in the bundle (source
   `lineage`, row L6). A head read for another commit is recorded as `STALE` and adds none.
4. **A finding stays open until a verified fix or a verified false-positive disposition.** A
   fix removes it from the head's complete report. A false-positive disposition is a closed
   `gnostoa:disposition:v1` block in a native review that is the latest, `APPROVED` review at
   the exact head by a required approver who is neither the change's declarer nor its author,
   the eligibility M16 already applies (source `pao-revision`). It names the provider, the
   observation's native id, the rule (null for a finding listed with none, as an inline
   comment's is), the path, the enclosing scope hash or the line, the head commit and an
   evidence reference, and it disposes only of the finding it names exactly. A
   push unbinds it. A provider's own mark (`FALSE_POSITIVE`, `ACCEPTED`, `suppressed`, an
   Ignore), a resolved thread, or a clean result from another provider disposes of nothing.
   A disposition is no debt entry and waives nothing beyond its head: the protected ledger and
   Decision 0129's run-bound configuration requirement are unchanged, and only a
   configuration-bound finding can meet a ledger entry, so a DeepSource finding never does
   (source `pao-dismissal`).
5. **Decision 0130 §3 is amended for findings only.** The readback may acquire an optional
   provider's complete reports, for the head and the merge base, with its own credential, used
   only by the protected readback workflow's job in the `analyzer-readback` environment, findings
   only, under the readback's existing bounds (source `owner-revision`). Its reads, the merge
   base's GitHub reads and its findings' scope reads included, share one overall deadline well
   inside the readback job's limit, which DeepSource's client and `tools/github_rest.py` apply;
   past it a read ends as an `ERROR`, which changes nothing, and a finding left without a scope
   stays `unknown`. The declared items' reads are given no deadline. The head-only scope
   reader is generalized to read either commit under the same bounds, not duplicated. Its reads
   never become merge coverage.

## Limits

- **A ledger entry dismisses only a configuration-bound finding** (Decision 0129). A DeepSource
  finding closes by a fix or by a verified false-positive disposition at its head, never by a
  ledger entry.
- **Pre-existence of a DeepSource finding rests on an unproven configuration.** Its runs state no
  configuration of their own, so a base and a head read could differ in configuration unseen. The
  evidence records `configuration_provenance: unproven` beside each such classification.
- **Report-only findings reach the reviewers through M17's listing.** They are not posted as
  inline comments.
- **A partial fix keeps the rest of its group blocking.** When the head has fewer occurrences
  in a group than the base, which one remains is not established, so the remaining ones stay
  introduced until fixed or disposed of.
- **The base read costs a second report read per optional provider,** within the same bounds,
  for every pull request that modifies a file the provider reports on.

## Verification

- **RED first:** 21 acceptance tests fail on `main` `6b6c8501` for the missing behaviour:
  20 in `tests/test_optional_reports.py`, where `main` refuses whole a bundle that carries
  DeepSource's readback, or refuses the `BASE` scope its base read needs; and 1 in
  `tests/test_analyzer_readback_runner.py`, where the readback refuses a DeepSource reader.
  All 21 pass with this change.
- **They cover:**
  - an unavailable optional source with its aspects covered;
  - a complete optional report that never covers a missing required item;
  - a report-only finding listed and denying, and its closure when the head's report no longer lists it;
  - a stale report counted as stale;
  - a failed run recorded as failed and finding nothing, against a findings-bearing run, which is a finding;
  - a finding on an unmodified file kept out of the verdict;
  - a finding in both the report and an inline comment, listed once;
  - the ledger dismissing only a configuration-bound finding, beside an optional report;
  - at the pre-merge cut, the optional full read under the adapter's existing page bound;
  - against the merge base: a proven unchanged legacy finding listed and not denying; a
    regression outside the edited lines, and a match in a changed scope, introduced and
    denying; an additional occurrence in a matching scope, and a severity increase on a
    matched occurrence, each introduced and denying; a missing or incomplete base read
    leaving the finding unknown and denying;
  - an independent approver's disposition at the head closing its finding; the author's
    disposition, one for another commit, a provider's suppression or false-positive mark,
    and a disposition of another rule, each leaving it open.
- **Their edges, tested with the change:**
  - a base read for another commit, a severity outside the provider's order, and a finding
    with no scope, each leaving the finding unknown or introduced; a lesser severity
    pre-existing;
  - a disposition by its line, listed for the approver; one naming another provider,
    finding, path, scope or line; one in an approval its approver later superseded, in
    their later review that is no approval, or in their later approval of another commit;
    one by an approver who is the author or the declarer; and one naming a required
    provider's finding, each closing nothing;
  - under claims that are not met, a pre-existing and a disposed finding each still
    counting, as the ledger's rule is;
  - a malformed disposition block left out, a block written with CRLF line ends read,
    and at most 100 read from one review;
  - an unknown baseline, provenance, optional coverage or field, and a malformed
    disposition, each refused by the verdict as corrupt evidence;
  - in the readback: without its credential nothing read from DeepSource, and with it
    the command reading it; the head's and the merge base's reports each read at its
    own commit, the base's scopes at the base; a merge base GitHub does not give left
    unread; and the token reaching the readback step alone.

## Consequences

- A missing, failed or stale DeepSource read no longer holds a merge: each declared aspect
  keeps the qualified evidence that covers it.
- A complete DeepSource report for the exact head is read again, with the merge base's. What a
  change introduces or worsens in the files it modifies denies until fixed or disposed of; a
  finding the base already holds in an unchanged scope stays visible and does not deny.
- A false positive needs an independent eligible approver's disposition at the exact head,
  with its evidence. Nothing waives a finding across pull requests except Decision 0129's
  ledger, which a DeepSource finding cannot meet.
- `DEEPSOURCE_API_TOKEN`, already in the `analyzer-readback` environment, is used by the
  readback's job alone, for findings only.
