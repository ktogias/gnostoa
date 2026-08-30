# Current project status

This page is a derived navigation projection. Canonical project status,
evidence and publication gates live in the linked self-knowledge records.

## Source and publication status

Gnostoa currently has an owner-reviewed and technically verified
first-publication source baseline. The source repository is public, and
default-branch protection and private vulnerability reporting are effective.
PR #23 is integrated and Issue #1 is closed. The **historical
first-publication source-baseline identity** is the immutable commit
`cda51dad6a719da43d8465a3f0f270021c357d96`; that fact does not change. Protected
`main` has advanced past it since, and this page deliberately does not restate a
current branch head, because any value written here goes stale at the next merge.
Read the exact current head from the provider or from `git rev-parse origin/main`.

Mutable provider presentation and access state is authoritative and can change
without a source commit, so this page does not freeze it as timeless truth. Read
current visibility, permissions and Release presentation from the provider;
the immutable identities below remain durable historical results.

`v0.1.0` remains the historical first source-only identity, `v0.1.1` remains
the historical first OCI publication, and `v0.1.2` remains the historical
B3-readiness patch. The current pre-stable source identity is
[`v0.2.0`](https://github.com/ktogias/gnostoa/releases/tag/v0.2.0), an annotated
tag naming commit `39aa4f25bdf46811600d4a0f6f9c0da52b73c542` and tree
`866c8c489c9052c566bd65b6e798567d4a284f16`. Its public `linux/amd64` OCI
artifact is
`ghcr.io/ktogias/gnostoa@sha256:f89bf32c0c4b86bac71fa008579b2385e6ae39bf4822f685479c4f2cc22bfca4`.
Pull by that digest rather than relying on the `0.2.0` tag; no `latest` tag
exists.

The source and artifact establish no package or documentation-site publication,
compatibility, production-readiness or independent-transfer claim. Verified
artifact availability is not deployment authorization, reproducibility,
general-security assurance or qualified legal clearance. The durable result and
its exact evidence limits are in the
[v0.2.0 publication assessment](../knowledge/assessments/v0-2-0-source-and-oci-publication-result.md).

### Available from source

- OKF bundle and profile validation;
- non-weakening profile, change-control and CI-policy checks;
- deterministic bounded context-pack generation;
- anonymous examples and reusable adoption guidance;
- native and container command surfaces; and
- a reproducible human documentation projection.

### Evidence available

- repository-native policy, unit, regression, smoke and documentation checks;
- an integrated cumulative [PR #23](https://github.com/ktogias/gnostoa/pull/23)
  review and evidence envelope with policy, fast, regression and smoke checks
  passing; its provider records bind the exact integrated head;
- a self-dogfood publication-baseline review that found and corrected material
  source-scope, lifecycle, drift and disclosure defects; and
- an explicit assessment of both the value and excessive manual cost of that
  bootstrap;
- a compact [reputation and direction assessment](../knowledge/assessments/first-publication-reputation-and-direction-assessment.md)
  that separates the credible source candidate from its provider-history debt
  and records the bounded publication and B2 routes; and
- an owner-confirmed, source-only
  [name-risk screening](../knowledge/assessments/gnostoa-source-name-screening.md)
  for Greece, the EU and Nice classes 9 and 42.

### Not established

- package/site artifacts or upgrade compatibility beyond the exact published
  `linux/amd64` digest;
- production readiness, security certification or service operation;
- independent adoption, net productivity benefit or product-market demand;
- scalable guided review with low cognitive load; or
- formal or independent trademark clearance for stable branding or commercial
  reliance on the working project name.

## Publication review status

The first-publication source baseline is complete. Exact disclosure V4 was
owner-dispositioned; the bounded visibility transition, required `main`
protection, private vulnerability reporting, anonymous public-surface
read-back and protected PR #23 integration all completed. Issue #1 and PR #23
carry the exact provider result; this derived page does not substitute for it.

The publication cleanup has materially improved the current projection; the
remaining reputation risk is concentrated in the retained historical ledger,
not in the normal contributor route. The dated
[provider audit](../knowledge/assessments/first-publication-provider-audit.md)
found no high-confidence credential or developer-local-path exposure in the
inspected remote history, provider records, Actions logs or retained artifacts.
Its pre-transition gaps were reconciled through the exact V4 provider record;
the later owner-confirmed name-risk assessment closed the bounded source-name
gate without claiming trade-mark clearance or authorizing artifact publication.

PR #2 and PRs #16–#22 are useful absorbed provenance inside the cumulative PR
#23 ancestry; they are not discarded. PR #4 is retained as Research input for
Issue #3, outside the publication baseline while its conflicts and eight
review findings remain unresolved.

Issue #12 and PR #2 also retain the large B1 provider ledger as historical
self-dogfood evidence. That ledger is not the expected contributor workflow.
The [B2 experiment](https://github.com/ktogias/gnostoa/issues/24) used two
bounded changes to measure a smaller provider-native review route and is now
complete. The successor control C4-v0 was experimented with under
[Issue #33](https://github.com/ktogias/gnostoa/issues/33), scoped by
[Decision 0017](../knowledge/decisions/0017-scope-the-readiness-predicate-experiment-to-gnostoa-self-hosting.md)
to Gnostoa self-hosting and outside the public inherited surface. Its strict
hypothesis was refuted and the owner rejected C4-v0 as a readiness predicate; no
successor control is selected, and no enforcement mechanism was added. The workflow
need has already been demonstrated, and B2 narrowed what the current mechanisms
are shown to provide. The broad Issue #12 guided-review
platform is deferred Research rather than a publication gate, as recorded by
[Decision 0016](../knowledge/decisions/0016-evolve-human-agent-workflow-through-bounded-self-hosted-slices.md).

The source-publication route treated exact disclosure, visibility with `main`
unchanged, protection, anonymous read-back and protected integration as
separate effects. All completed for the source baseline; Issue #1 and PR #23
bind the current integration result. Package and site publication remain
separate later effects. The v0.1.x publications remain historical evidence;
the current `v0.2.0` source and OCI effects are reconciled in their own
[durable result](../knowledge/assessments/v0-2-0-source-and-oci-publication-result.md).

Clean wheel and source-distribution candidates now build and run against an
explicit separate public-source binding; an absent or malformed binding fails
with an actionable diagnostic, and the wheel does not duplicate the canonical
schemas or profiles. The release smoke also verifies package metadata, console
commands, license and notice, and executes a real `adoption-check` from each
clean installed artifact. That exercise requires exact byte equality between
the installed `tools` payload and the pinned public source, acquires the result
schema from that source, and can emit a path-neutral evidence manifest with the
source, public-surface and artifact digests. The
[compatibility note](compatibility.md) states the current exact-pin boundary
and non-promises. This is release-candidate evidence, not a published package
claim. The extended suite now enforces Ruff formatting and a bounded lint set,
strictly type-checks the maintained `tools/` and `ci/` Python surfaces, and
records branch-aware `tools/` coverage with a 65% regression floor,
known-vulnerability audits of both exact Python locks and a no-network
heuristic scan of the current Git-tracked tree. It also generates
package-declared license inventories and deterministic, strictly validated
CycloneDX 1.6 SBOMs for the exact installed Python distributions in both locks.
Both locks now enforce wheel-only pip hash-checking for every direct and
transitive requirement. The extended evidence records the exact wheel selected
for the current Python/platform environment, verifies it against the committed
SHA-256 allow-list and carries that identity into the inventory and SBOM.
Those reports are unsigned and bounded evidence: static analysis and coverage
do not prove acceptance, the package audit does not establish package trust,
legacy license metadata still requires human review, and neither the inventory
nor the tree scan covers the OS/base image, Git history or provider artifacts.
[Dependency evidence](dependency-evidence.md) documents the exact boundary.
The published digest has bounded runtime inventory and GitHub build-provenance
verification. Exact rebuild reproducibility, qualified legal clearance,
production readiness, package/site publication and broader consumer assurances
remain unclaimed. The exact source-publication disposition, protection and
integration state remains in the linked provider and durable result records.

## Current direction

The first publication exposes a bounded validation and knowledge-architecture
prototype, not the full open research backlog. The durable direction is to evolve
that prototype through bounded, evidence-gated self-hosted slices, each of which
must earn its own admission
([Decision 0016](../knowledge/decisions/0016-evolve-human-agent-workflow-through-bounded-self-hosted-slices.md),
[evidence-gated capability evolution](../knowledge/lifecycles/evidence-gated-capability-evolution.md)).

Two durable results bound what that direction currently claims. B2/P1 completed
the first validated task envelope and deterministic current projection, and
[Issue #24](https://github.com/ktogias/gnostoa/issues/24) narrowed the product
claim: the envelope and projection are demonstrated to improve orientation,
resumability and bounded human understanding, and are **not** an enforcement
mechanism. The failed property that follows from it — critical workflow
constraints are advisory rather than mechanically enforced — remains
**unmitigated**, and **no successor control experiment or mitigation is
selected**. The strict
[B3 independent-adoption methodology](../knowledge/assessments/b3-independent-adoption-experiment-design.md)
remains pre-registered for a later `INDEPENDENT` evidence stage. Four
autonomous Nextcloud Mail adoption attempts remain historical controlled
pre-B3 evidence, with their original `REJECT` / `UNKNOWN` / `NO`
dispositions unchanged.

[Decision 0052](../knowledge/decisions/0052-use-staged-evidence-maturity-for-early-adoption-trials.md)
now governs early-product evidence through distinct `SELF-HOSTED`,
`OWNER-LED`, `COLLABORATIVE` and `INDEPENDENT` classes. The completed v0.2.0
Nextcloud Mail stream through #158 is `OWNER-LED`, with `human:ktogias` as its
initial accountable project-side semantic and evaluation authority. The
`v0.2.0` source and immutable OCI subject are published, reconciled and
digest-bound, and the release-series experiment boundary was satisfied by the
[bounded owner-led baseline](../knowledge/assessments/nextcloud-mail-v0-2-0-owner-led-adoption-trial-baseline.md).
Phase A then completed the controlled adaptation with historical owner
`ACCEPT` and recorded H-A `PASS`; a later independent strict-audit addendum
retained that history while classifying the frozen subject `H-A FAIL` with
protocol deviation `YES`. The first
[real Phase-B task](../knowledge/assessments/nextcloud-mail-phase-b-owner-led-task-result.md)
completed with a technically wrong frozen result: the raw reviewer recommendation
was `ACCEPT`, the owner disposition was `CORRECT`, owner-assessed utility
remained `UNKNOWN` and the result scored `H-B FAIL`. The experiment completed,
but its hypothesis did not pass and positive causal Gnostoa utility was not
demonstrated. Upstream feedback is additive rather than blocking, while strict
`INDEPENDENT` evidence remains a later maturity-stage activity.
`ktogias/mail` is the local mutation workspace; `nextcloud/mail` retains
Issue and final Change Request authority. No independent-adoption or
upstream-acceptance claim is made.

This page includes only the bounded chronology and outcome summary above, with
each claim linked to its durable subject-specific record. It deliberately does
not restate live Work Item lifecycle or free-floating candidate outcomes,
because those can change independently of any source commit. Read instead:

- **delivery navigation and what each completed slice established** — the
  [Now / Next / Research roadmap](roadmap.md);
- **live Work Item lifecycle and which Work Item is currently selected** — the
  provider, where the selected item carries the `roadmap:now` label;
- **candidate-bound measured outcomes** — the linked result records under
  [self-knowledge](../knowledge/index.md), each scoped to one candidate at one
  observation time;
- **immutable historical source identity** — the exact commit and public-surface
  digest recorded with the release identity, never a version label alone.

Canonical detail:

- [Gnostoa project record](../knowledge/project/gnostoa.md)
- [Self-dogfood bootstrap assessment](../knowledge/assessments/gnostoa-self-dogfood-bootstrap-assessment.md)
- [First-publication reputation and direction assessment](../knowledge/assessments/first-publication-reputation-and-direction-assessment.md)
- [Source-publication name-risk screening](../knowledge/assessments/gnostoa-source-name-screening.md)
- [Human-agent governance scope assessment](../knowledge/assessments/human-agent-governance-scope-and-evolution.md)
- [Reverse-centaur review overload](../knowledge/failure-modes/reverse-centaur-review-overload.md)
- [First-publication preparation runbook](../knowledge/runbooks/prepare-first-publication.md)
- [Toolkit evolution lifecycle](../knowledge/lifecycles/toolkit-evolution.md)
