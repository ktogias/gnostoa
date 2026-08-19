---
type: Decision
title: Apply the supported Debian util-linux security update to the OCI runtime
description: Upgrade the already-installed util-linux-derived binary packages to the exact supported trixie-security versions to clear Decision 0022's vendor-fixed-component publication blocker, without publishing anything or changing the runtime boundary.
status: draft
generated:
  by: human:ktogias
  at: "2026-08-19T08:50:00Z"
sources:
  - id: remediation-work-item
    resource: https://github.com/ktogias/gnostoa/issues/54
    title: Apply the supported util-linux security update to the OCI runtime
x-project-knowledge:
  id: kit.decision.0023.apply-the-supported-debian-util-linux-security-update-to-the-oci-runtime
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governed-by
      target: /decisions/0022-define-the-security-boundary-for-the-first-gnostoa-oci-publication.md
    - kind: governs
      target: /assessments/util-linux-security-remediation-result.md
    - kind: references
      target: /decisions/0021-adopt-the-observed-source-only-release-procedure-for-gnostoa-self-governance.md
---

# Apply the supported Debian util-linux security update to the OCI runtime

Recorded by `agent:claude-opus-5` from the accountable maintainer's disposition.
The semantic choice is the maintainer's; this record is faithful transcription.

## Context

Decision 0022 established that the first published image will not knowingly ship a
vendor-designated vulnerable component when an applicable supported update already
exists in the same channel, **even where the default runtime lacks the
exploitation preconditions**. Bounded evidence showed that condition met for the
util-linux-derived components in the measured candidate, and no exception exists.

The blocker was therefore small and well-characterised: the base image inherits
util-linux at the plain trixie version while the security suite already carries
the fixed build.

## Decision

**A.** Decision 0022 remains the governing security and publication authority and
is not amended.

**B.** This slice remediates **only** its demonstrated current
vendor-fixed-component blocker.

**C.** Upgrade the **complete already-installed binary-package set derived from
Debian source `util-linux`** to the exact supported security versions observed and
admitted at implementation time.

**D.** Exact binary versions are **pinned**. Because the same source build appears
in three version forms — plain, epoch-bearing and `+really` — versions are pinned
per package rather than through one shared variable.

**E.** **No** `apt upgrade`, `dist-upgrade` or `full-upgrade` is used;
`--only-upgrade` restricts the transaction to already-installed packages.

**F.** No unrelated package addition, removal or version movement is admitted.

**G.** The exact Python base-image digest remains **unchanged**.

**H.** The documented default runtime security boundary remains **unchanged**.

**I.** **No security exception is granted.**

**J.** **OCI publication remains unauthorized.**

**K.** `deployable_artifact` remains `false`.

**L.** **No registry is selected.**

**M.** No scanner, monitoring service, VEX or SBOM framework, updater, provider
adapter or CI security mechanism is selected.

**N.** Vendor security state must be re-read on the exact candidate.

**O.** Success supports only the narrow util-linux hygiene result for the measured
`linux/amd64` candidate.

**P.** It does **not** establish complete OCI readiness or image security.

**Q.** Because `Dockerfile` is image-defining source, the post-remediation source
is **not** the immutable `v0.1.0` source.

**R.** A **new immutable source identity is required before eventual OCI
publication** of this changed image definition.

**S.** That requirement does **not** automatically select the new source release as
the next slice.

**T.** The future source version or tag is **not** selected here.

**U.** Prefer establishing a new immutable source identity only after the final
admitted image-defining preparation has stabilised, to avoid unnecessary
intermediate releases.

**V.** A later, independently justified source release should follow Decision 0021
and may provide the next real dogfood evidence for its draft runbook.

Candidate-time Debian versions live in the remediation result record, not in this
Decision, so that a changing security feed does not turn into stale policy.

## Consequences

- The demonstrated blocker is cleared for the measured platform; every other OCI
  gate is untouched and still open.
- The public-surface digest changes, because `Dockerfile` is inside the pinned
  surface. `v0.1.0` continues to bind its own commit and digest; this candidate
  binds different ones, and that distinction is recorded rather than blurred.
- Exact apt pins select package versions only while those versions remain
  available from the configured signed repository. This establishes no archived
  package bytes, no hermetic OS reconstruction and no image-digest
  reproducibility.
- Remediation, source identity, OCI admission and publication remain four
  separate lifecycle decisions, and this Decision closes only the first.
