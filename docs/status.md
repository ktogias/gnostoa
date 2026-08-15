# Current project status

This page is a derived navigation projection. Canonical project status,
evidence and publication gates live in the linked self-knowledge records.

## Pre-release

Gnostoa currently has a reviewed source candidate and working validation
prototype. It has no public release, package, OCI image, documentation site or
independent transfer pilot.

### Available from source

- OKF bundle and profile validation;
- non-weakening profile, change-control and CI-policy checks;
- deterministic bounded context-pack generation;
- anonymous examples and reusable adoption guidance;
- native and container command surfaces; and
- a reproducible human documentation projection.

### Evidence available

- repository-native policy, unit, regression, smoke and documentation checks;
- a self-dogfood publication-baseline review that found and corrected material
  source-scope, lifecycle, drift and disclosure defects; and
- an explicit assessment of both the value and excessive manual cost of that
  bootstrap.

### Not established

- installable released artifacts or upgrade compatibility;
- production readiness, security certification or service operation;
- independent adoption, net productivity benefit or product-market demand;
- scalable guided review with low cognitive load; or
- independent trademark clearance for the working project name.

Clean wheel and source-distribution candidates now build and run against an
explicit separate public-source binding; an absent or malformed binding fails
with an actionable diagnostic, and the wheel does not duplicate the canonical
schemas or profiles. The release smoke also verifies package metadata, console
commands, license and notice and can emit a path-neutral evidence manifest with
the source, public-surface and artifact digests. The
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
Complete image/system-component inventory, legal review, publisher and release
provenance, the full exposed history/provider disclosure audit, remaining
release gates and publication still remain open.

## Current direction

The first publication exposes a bounded validation and knowledge-architecture
prototype, not the full open research backlog. After publication, one small
Gnostoa change will measure a streamlined self-hosting process. Only after that
process is comprehensible and materially smaller will an independently owned
project be used for a transfer pilot.

Canonical detail:

- [Gnostoa project record](../knowledge/project/gnostoa.md)
- [Self-dogfood bootstrap assessment](../knowledge/assessments/gnostoa-self-dogfood-bootstrap-assessment.md)
- [First-publication preparation runbook](../knowledge/runbooks/prepare-first-publication.md)
- [Toolkit evolution lifecycle](../knowledge/lifecycles/toolkit-evolution.md)
