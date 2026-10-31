---
type: Decision
title: Repair the typing of seventeen test modules, the closure's first group
description: "The first group of the inventory's test-typing debt (#389 complete closure, N1a): 124 mypy diagnostics in 17 test modules are repaired in place by narrowing, typed test doubles and declarations, with every test's identity and outcome preserved; nothing outside those modules changes, and the coupled N1b group stays held."
status: draft
generated:
  by: anthropic/claude-opus-5-5
  at: "2026-10-31T13:07:51Z"
sources:
  - id: work-item
    resource: https://github.com/ktogias/gnostoa/issues/389
    title: Keep merges possible while a vendor analyzer is unavailable
  - id: owner-closure
    resource: https://github.com/ktogias/gnostoa/issues/389#issuecomment-6542636396
    title: "The owner's direction: resolve every recorded problem, carry no debt, activate as soon as possible"
  - id: closure-return
    resource: https://github.com/ktogias/gnostoa/issues/389#issuecomment-6543317786
    title: The closure return that measured the test-typing debt and proposed its groups
  - id: owner-admission
    resource: https://github.com/ktogias/gnostoa/issues/389#issuecomment-6543515854
    title: "The owner's admission of N1, the 35 test files with no sibling-import dependency"
  - id: scope
    resource: https://github.com/ktogias/gnostoa/issues/389#issuecomment-6543568350
    title: The exact selection, its confirmation by the real collector, and the coupling split into N1a and N1b
  - id: route
    resource: https://github.com/ktogias/gnostoa/issues/389#issuecomment-6543603713
    title: "The Router's routing of N1a, holding only N1b"
  - id: lineage
    resource: https://github.com/ktogias/gnostoa/issues/389#issuecomment-6543649546
    title: The post-edit recovery lineage, the reconstructed behaviour baseline and the actual chronology
  - id: original-record
    resource: https://github.com/ktogias/gnostoa/issues/389#issuecomment-6543654970
    title: This Decision's first published text, which the Corrections section amends
  - id: correction-route
    resource: https://github.com/ktogias/gnostoa/issues/389#issuecomment-6543736813
    title: "The Router's four factual corrections and its reading of the chronology"
  - id: profile
    resource: ./0117-select-the-diagnostic-inventory-s-families-through-a-protected-profile.md
    title: The protected profile whose typing family this group answers, unchanged
  - id: normal
    resource: ./0119-admit-normal-changes-through-the-project-s-own-inventory-and-keep-deepsource-for-every-other-class.md
    title: The NORMAL route through the project's own inventory, which admits this change
  - id: inheritance
    resource: ./0099-route-the-architecture-inheritance-gate-from-source.md
    title: The architecture inheritance gate
  - id: reuse-review
    resource: ./0062-require-proportionate-prior-art-and-reuse-review.md
    title: Proportionate prior-art and reuse review
x-project-knowledge:
  id: kit.decision.0123.repair-the-typing-of-seventeen-test-modules
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: references
      target: /decisions/0117-select-the-diagnostic-inventory-s-families-through-a-protected-profile.md
    - kind: references
      target: /decisions/0119-admit-normal-changes-through-the-project-s-own-inventory-and-keep-deepsource-for-every-other-class.md
    - kind: references
      target: /decisions/0099-route-the-architecture-inheritance-gate-from-source.md
    - kind: references
      target: /decisions/0062-require-proportionate-prior-art-and-reuse-review.md
---

# Repair the typing of seventeen test modules, the closure's first group

## Context

The owner directed the complete closure of the diagnostic inventory's recorded debt, with
the earliest qualified activation (source `owner-closure`). On protected main
`4456b977fee8a216a1589546ee0b7a09d299997f`, mypy, run as the inventory's typing family
runs it, reports 454 diagnostics in test modules. 44 of them are unresolved imports, from
the mismatch between the collector's module roots and the suite's. Replayed in the suite's
own import scheme (source `closure-return`), 400 errors and 4 notes remain in 47 test
modules, beside 7 fixture diagnostics: real debt. N1a's selection does not change.

The owner admitted N1: the 35 test files with no sibling-import dependency, 309
diagnostics (source `owner-admission`). The real collector, with main as its producer,
confirmed that selection over a probe commit. Its DIFF also showed a coupling (source
`scope`):
- protected access reads each changed file whole (`diff: all`);
- complexity acquires every function a change adds a line to;
- under M17, every acquired finding denies.

So 18 of the 35 files cannot pass their own admission through typing repair alone. They
form N1b, which is held (source `route`). N1a is the other 17 files and their 124
diagnostics: none of them has a protected-access site or a function above the complexity
threshold.

Its class is `normal`, and the project's own inventory admits it (source `normal`). Being
test-only is not by itself the reason. The strictest applicable classification governs, and
it would be stricter if the change weakened a security oracle or contract. It weakens none:
the bounded diff audit (Verification) finds every assertion, test and forwarded argument
kept.
- **`/tests/` is a trust root (M15):** the change is listed for the native approval, which
  does not raise its class.
- **Guardrail coverage:** seven of the modules are cited as coverage by
  `policy/guardrails.yaml` or a workflow. Their test identities stay.

## Decision

1. **Each diagnostic is repaired in its own module, by the module's own means.** The means
   are:
   - a narrowing assertion where a value typed `object` or Optional is used;
   - a test double that declares the interface it replaces;
   - a declaration where a test class's attribute is assigned dynamically;
   - a typed value where a table held untyped keyword arguments.

   An assertion added for narrowing holds wherever the test already relied on the value.
2. **Nothing is silenced or weakened.** There is no `cast`, `type: ignore`, `Any` added to
   pass a check, removed or weakened assertion, renamed or removed test, or skip.
3. **Nothing outside the 17 modules and this record changes.** That excludes production
   code, the collector or its import model, the profile, any threshold or scope, fixtures,
   and recorded evidence.
4. **Behaviour is preserved.** The 17 modules run the same tests, by identity, with the same
   outcomes, before and after (source `lineage`).
   - That check is necessary, not sufficient.
   - Whether the assertions, the test doubles' forwarding and each test's intent stay intact
     is checked on the bounded diff itself.
5. **N1b and the rest of the closure stay separate.** N1b is held, and this group activates
   nothing.

## Verification

- **Before:** the real collector's DIFF over the probe lists the 124 diagnostics in these
  modules (source `scope`). Exact main's bytes run 173 tests, all OK (source `lineage`).
  That baseline was reconstructed at 12:55:52Z, after the freeze; it is not a run from
  before the first edits.
- **After:**
  - the same collector's DIFF over this change lists 0 findings in any family;
  - the 173 tests keep their identities and outcomes;
  - the bounded diff audit passes. In each module, no unittest assertion call, test method
    or skip marker is fewer. Every removed line is replaced by its narrowed or typed form.
  - the repository's own gates pass: the self-check, `ruff`, the format check and mypy.

## Consequences

- **The debt:** the inventory's typing debt in tests falls by these 124 diagnostics. The
  rest stays recorded, as N1b and the sibling-dependent group.
- **The edits' chronology:** the first edits to eight of these modules were made locally,
  between 12:50:38Z and 12:52:50Z on 2026-10-31. That was after the selection and its
  failing reproducer were recorded, but before this record and its lineage. They were
  frozen at 12:54:04Z and are disclosed in the lineage record (source `lineage`). They are
  not described as test-first. For those eight modules the lineage is a post-edit recovery
  lineage, not a pre-mutation one.

## Corrections

This text amends the first published version (source `original-record`: 6,890 bytes,
SHA-256 `911fe2df760ab48a5b357fc45c6442901f68b2d1d873ccc4101f1e7b56f1f8f3`), on the
Router's four points (source `correction-route`):

1. **The lineage:** for the first eight modules it is a post-edit recovery lineage, not a
   pre-mutation one.
2. **The class:** being test-only does not make a change `normal`. The strictest real
   classification applies.
3. **The 454 diagnostics:** they include import-resolution effects. The replay leaves 400
   errors and 4 notes in tests, and separate fixture diagnostics. N1a's 124 are unchanged.
4. **The behaviour check:** identical test identities and outcomes are necessary, not
   sufficient. Intact assertions, forwarding and intent are checked on the diff.
