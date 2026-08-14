---
type: Runbook
title: Prepare Gnostoa for its first public repository publication
description: Convert the accepted private source baseline into a truthful, focused, reproducible and evidence-bounded first public release without hiding bootstrap history or expanding the product claim.
status: draft
generated:
  by: codex/gpt-5
  at: "2026-08-14T00:00:00Z"
sources:
  - id: publication-baseline-work-item
    resource: https://github.com/ktogias/gnostoa/issues/1
    title: Prepare the Gnostoa publication baseline
  - id: publication-baseline-change-request
    resource: https://github.com/ktogias/gnostoa/pull/2
    title: Prepare the Gnostoa publication baseline
  - id: durable-task-context-change-request
    resource: https://github.com/ktogias/gnostoa/pull/4
    title: Add durable task context and explicit handoffs
  - id: final-publication-baseline-disposition
    resource: https://github.com/ktogias/gnostoa/pull/2#issuecomment-5294119830
    title: Final exact-head owner disposition for PR 2
x-project-knowledge:
  id: kit.runbook.prepare-first-publication
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: depends-on
      target: /assessments/gnostoa-self-dogfood-bootstrap-assessment.md
    - kind: references
      target: /runbooks/review-publication-baseline.md
    - kind: references
      target: /failure-modes/publication-baseline-review-drift.md
    - kind: governed-by
      target: /decisions/0013-defer-provider-enforcement-while-private.md
    - kind: governed-by
      target: /decisions/0014-strengthen-gnostoa-self-governance.md
---

# Prepare Gnostoa for its first public repository publication

## Outcome and operating claim

The first publication should present Gnostoa as a focused, reproducible
technology prototype with a clear product boundary and an honestly measured
self-dogfood bootstrap. It should not present a large process ledger as the
product, conceal that ledger, or claim independent adoption and productivity
benefits that have not been demonstrated.

The public reader should be able to answer, in this order:

1. What problem does Gnostoa solve?
2. Who can use the current release and for what bounded tasks?
3. How can a reader install it and validate one example in minutes?
4. Which contracts, tools and examples are implemented now?
5. What did the self-hosting pilot find, what did it cost, and what remains
   unproven?
6. What is stable, draft, experimental or only planned?
7. What is the next falsifiable product milestone?

The defensible publication claim is:

> Gnostoa provides a deterministic, provider-neutral foundation for
> validating structured project knowledge, inheriting non-weakening profiles,
> enforcing declared policy boundaries and producing bounded context views.
> Gnostoa is its own first reference consumer. That bootstrap found real
> defects before publication and also exposed excessive manual evidence
> amplification. The first release makes both the useful mechanism and its
> current limits inspectable; independent transfer remains a later experiment.

## Preconditions

- The repository remains private until the provider-surface audit reports GO.
- The accepted PR 2 revision and its recorded owner disposition are still
  available and their exact identities have not drifted.
- Any document created after that disposition is treated as a separate
  follow-up candidate. It is not silently inserted into the accepted PR 2
  revision or represented as part of that earlier review.
- An accountable human owner is available for semantic publication and
  visibility decisions. Automated checks and agent analysis remain evidence.
- The self-dogfood bootstrap assessment is available as the evidence and claim
  boundary for this runbook.
- PR 4 and every other branch that a public visibility change would expose
  have an explicit finish, replace, retain-private-if-supported or close
  disposition before publication.
- License, copyright, security disclosure, contribution and provider settings
  are included in the provider-surface audit rather than inferred from the
  source tree alone.

## Procedure

### Stage 0 — lock the first-publication slice

1. Define the first-publication objective as an installable `v0.1.0` source,
   CLI and container release with public documentation and one verified
   anonymous-user path.
2. Freeze the claim boundary to the implemented schema, validation, profile,
   policy, context-pack and documentation mechanisms. Do not make Issues 5–15
   prerequisites unless a concrete security, legal, correctness or publication
   blocker proves that one is necessary.
3. Label every proposed deliverable `publication blocker`, `release blocker`,
   `post-release follow-up` or `research`. A blocker must name the failed
   property and evidence needed to clear it.
4. Keep the detailed append-only history. Reduce foreground load through
   summaries, indexes and expandable evidence, not deletion or rewritten
   history.

**Exit evidence:** one short publication-scope record lists the exact release
surface, claim boundary, blockers, exclusions and accountable owner.

### Stage 1 — make the provider state truthful

1. Reconcile the PR 2 title and body with its current head, accepted status,
   verification evidence and remaining merge or publication gates. Remove
   stale statements such as a superseded head or review-pending state.
2. Reconcile Issue 1 with the same current state. Keep the complete ledger
   linked as evidence, but foreground only current status, decisions, blockers
   and next action.
3. Decide PR 4 explicitly. Finish its remaining review and integrate it only
   if it is part of the first release; otherwise close or defer it with a short
   rationale. Do not leave a dirty draft as an unexplained public signal.
4. Classify open Issues into `Now`, `Next` and `Research`. Give each a plain
   language outcome, current status and dependency. Close duplicates and
   superseded proposals append-only, without erasing their history.
5. Replace marker-heavy first impressions with concise provider summaries and
   stable links to the detailed records. Machine-readable markers may remain
   in the ledger but should not be the reader's primary navigation surface.

**Exit evidence:** PRs and Issues tell the same current story as the source and
owner records; no open public item has a stale or ambiguous next action.

### Stage 2 — build the product front door

Restructure the root README so its first screen contains:

1. a one-sentence problem and product statement;
2. the current audience and explicit non-goals;
3. a five-to-ten-minute quick start using a pinned release;
4. one input/output example that demonstrates validation and a bounded context
   view;
5. a compact architecture map from canonical source through validation to
   derived projections;
6. a capability and maturity table separating implemented, draft and planned
   behavior;
7. links to concepts, command reference, adoption guide, governance and the
   bootstrap assessment; and
8. a short limitations section that names the missing external transfer pilot,
   incomplete release evidence and draft contracts.

Add focused documentation pages rather than extending the README indefinitely:

- `docs/getting-started.md`: install, pin, validate and generate one context
  pack;
- `docs/concepts.md`: canonical source, profiles, inheritance, validation,
  policy and derived projections;
- `docs/architecture.md`: components, trust boundaries and authority flow;
- `docs/status-and-roadmap.md`: current maturity, Now/Next/Research and claim
  limits;
- `docs/self-dogfood-bootstrap.md`: compact public report derived from the
  canonical assessment; and
- `SECURITY.md`, `CONTRIBUTING.md` and support guidance with truthful current
  response expectations.

**Exit evidence:** a new reader can identify the product, run a successful
example and understand its maturity without reading Issues or review comments.

### Stage 3 — turn the bootstrap into product evidence

1. Derive a compact bootstrap validation report from the canonical assessment.
   Do not duplicate the full comment ledger.
2. Publish a dated evidence snapshot containing at least:
   - tests and policy checks executed;
   - defects found before integration, grouped by product, provider and process
     boundary;
   - elapsed review time and number of revision rounds;
   - comment and word amplification;
   - owner decision count versus provider-authored evidence count;
   - incidents, recoveries and escaped defects; and
   - current unresolved risks.
3. Explain the bootstrap stages: B0 initial source import, B1 current manual
   self-dogfood, B2 streamlined self-hosting, and B3 independent transfer.
4. State which claims the evidence supports and which it does not. In
   particular, self-applicability and defect discovery are supported;
   productivity, ease of adoption and independent assurance are not yet.
5. Predeclare the B2 comparison before running it: same bounded change class,
   evidence budget, measures, stop conditions and acceptable safety escapes.

**Exit evidence:** the dogfood history reads as an empirical bootstrap result
with costs and limits, not as unexplained governance volume.

### Stage 4 — make installation and verification reproducible

Current characterization from 2026-08-14: a wheel built from a clean candidate
and installed successfully into a fresh environment, but `knowledge validate`
then failed because native execution had no verified binding to the separate
pinned public source and its default root did not contain the required
`schemas/` data. The editable source-checkout route works. Decision 0005 keeps
native execution separate from pinned public source/profile assets, so the
remediation establishes an explicit `KNOWLEDGE_KIT_ROOT` binding, validates its
shape, fails clearly when it is absent or malformed, and keeps canonical assets
out of the execution-only wheel. The bound location is not identity evidence;
artifact hashes, source revision and public-surface digest must still be pinned
and checked. `python ci/release_smoke.py --output-dir <empty-directory>` builds
and exercises clean wheel and source-distribution installs against this
boundary.

1. Build an sdist and wheel from a clean checkout. Install each into a fresh
   environment and run the documented quick start without an editable source
   checkout.
2. Build the pinned OCI image and run the same fixture through the public
   command and data contract. Confirm native and container results are
   equivalent for the declared surface.
3. Replace the current smoke-only CLI-help evidence with an end-to-end release
   smoke test. Declare a real integration suite or explicitly keep integration
   out of the `v0.1.0` claim.
4. Add bounded release checks for formatting/lint, static typing, dependency
   and secret scanning, test coverage reporting, license inventory and SBOM.
   These are evidence layers, not substitutes for behavior tests.
5. Build the documentation from a clean environment and run link, navigation
   and anonymous-reader checks.
6. Verify package metadata, schema identifiers, console commands, license,
   notice, version and image labels against the release revision.
7. Write upgrade and compatibility notes that distinguish current promises
   from future versioning policy.

**Exit evidence:** one clean revision reproducibly produces tested source,
wheel, container and documentation artifacts with recorded digests.

### Stage 5 — reduce scope and roadmap ambiguity

1. Define `Now` as publication and the smallest usable validation/context
   workflow.
2. Define `Next` as B2 workflow compression, packaging hardening and the first
   independently owned adoption fixture.
3. Keep guided review engines, durable workflow orchestration, monitoring,
   generalized recovery and broader authority automation in `Research` until a
   measured repeated need justifies them.
4. For every roadmap item, record the user, problem, falsifiable outcome,
   dependency and explicit non-goal. Avoid solution-first Issues whose product
   value is not yet shown.
5. Apply a deletion test to planned scope: if removing an item does not weaken
   the first-release claim or named experiment, it is not a publication
   blocker.

**Exit evidence:** the public roadmap has one clear release objective, one next
experiment and a visibly separate research backlog.

### Stage 6 — audit and transition the provider surface

Before changing visibility, inspect the surface the provider will expose:

- default and non-default branches and complete reachable history;
- open and closed Issues, Pull Requests, reviews, comments and attachments;
- Actions logs, artifacts, caches and environment metadata;
- repository description, topics, social preview, links and default branch;
- collaborators, teams, applications, deploy keys, secrets and environments;
- branch or ruleset protection and required checks;
- email addresses, usernames, local paths, credentials, tokens, private
  reasoning, third-party confidential material and personal data; and
- license, notices, trademark status, contribution and security channels.

Run secret, path, identity, binary and large-file scans over the entire exposed
history, not only the final tree. Test the repository as an anonymous reader.
Any destructive history rewrite requires a separate exact authorization,
backup, force-push plan, collaborator coordination and post-rewrite audit.

**Exit evidence:** a source-publication audit records GO or NO-GO for the exact
provider state and names any residual disclosure explicitly.

### Stage 7 — integrate, publish and release in separate effects

1. Integrate the accepted source baseline only after required protection is
   effective and the accepted revision is still current.
2. Integrate follow-up cleanup and documentation as independently reviewed
   changes; do not rewrite the semantic scope of the accepted baseline.
3. Change repository visibility only under a separate owner-authorized
   provider action after the provider-surface audit reports GO.
4. Re-run anonymous access, branch protection, required checks, links and
   disclosure scans immediately after the visibility transition.
5. Tag `v0.1.0` only from the verified release revision. Build artifacts from
   that tag, record provenance and digests, then publish package, image and
   documentation through their distinct release gates.
6. Publish release notes that lead with capability, quick start, bootstrap
   evidence, limitations and next experiment rather than the internal event
   chronology.

**Exit evidence:** repository visibility, source integration and artifact
publication each have an exact actor, revision, result and read-back record.

### Stage 8 — run B2, then earn B3

1. Use one small Gnostoa change to compare B2 with the B1 baseline.
2. Measure time to orient, owner decision time, evidence amplification, review
   rounds, defects caught, false blocks, recovery behavior and escaped defects.
3. Retain exactness and safe recovery while reducing foreground evidence and
   manual provider mechanics. If volume does not fall materially, narrow the
   workflow claim instead of automating the same amplification.
4. Only after B2 is comprehensible, run B3 in one independently owned project
   with its own owner, constraints and success criteria.

**Exit evidence:** later value claims cite a named comparison or transfer
experiment rather than the existence of more workflow records.

### Implementation board

| Priority | Deliverable | Depends on | Completion signal |
|---|---|---|---|
| P0 | Publication scope and claim boundary | Accepted baseline and assessment | Owner-reviewed scope with blockers and exclusions |
| P0 | Truthful PR 2, Issue 1 and PR 4 state | Current provider read-back | No stale head, status or next-action claim |
| P0 | Provider-surface disclosure audit | Exact branches, history and settings | Explicit GO/NO-GO with zero unknown high-risk exposure |
| P0 | Root README and verified quick start | Clean install path | Anonymous reader completes example successfully |
| P0 | Clean build and release smoke | Wheel, sdist and OCI build | Same declared result from clean native and container routes |
| P1 | Bootstrap validation report | Canonical assessment and provider metrics | B0/B1 evidence and claim limits published compactly |
| P1 | Documentation set and status roadmap | Product boundary | Product, architecture, maturity and next experiment are clear |
| P1 | CI/release hardening | Public commands and artifacts | Behavior, policy, packaging, docs and security evidence green |
| P1 | Protected integration and visibility transition | All P0 gates | Exact read-back confirms protected public provider state |
| P1 | `v0.1.0` artifacts and release notes | Verified release tag | Installable artifacts, digests and documentation available |
| P2 | B2 streamlined self-hosting experiment | Published B1 metrics | Comparable assurance with materially lower owner/process cost |
| P2 | B3 external transfer pilot | Successful B2 | Independent owner completes a bounded adoption experiment |

## Verification

For every candidate revision, run the repository-native gates:

```bash
./ci/verify policy
./ci/verify fast
./ci/verify regression
./ci/verify smoke
./ci/verify extended
git diff --check
```

Before release, add and execute the declared package, container, integration,
security and anonymous-documentation tests described in Stage 4. A `SKIP`
result is acceptable only when the corresponding capability is explicitly
outside the release claim; it is not passing evidence for that capability.

Publication is ready only when:

- the provider state, source tree, docs and release notes agree;
- the quick start succeeds from clean released artifacts;
- all public links and anonymous-reader paths work;
- the full exposed history passes the disclosure audit;
- branch protection and required checks are effective before integration;
- every remaining risk has an owner and is accurately classified as a limit or
  follow-up rather than silently treated as complete; and
- the release makes no claim beyond the assessment's evidence boundary.

## Recovery

- On source or provider drift, stop, bind the new state and re-run only the
  affected review and verification. Do not reuse a stale GO decision.
- On a disclosure finding, keep the repository private. Remove the exposure
  from the publication surface or use a separately authorized history
  remediation, then scan and review the rewritten state again.
- On failed package, image, docs or anonymous quick-start verification, keep
  source visibility and artifact publication as separate decisions. Repair the
  affected artifact route without claiming a release.
- On stale or misleading provider summaries, correct them append-only and link
  the superseded record. Do not delete evidence merely to improve appearance.
- If scope grows beyond the frozen first-release claim, defer the new item or
  prepare a separately reviewed release candidate. Do not turn publication
  cleanup into a new workflow-platform implementation.
- If the B2 process retains B1-level amplification, publish the result and
  narrow the product claim to the validated schema, policy, profile and
  context-pack foundation. More automation is not automatically the remedy.

This runbook records a preparation and evidence route. It does not accept or
merge a Pull Request, make a Decision or Issue effective, change repository
visibility, publish an artifact, or authorize a destructive history rewrite.
