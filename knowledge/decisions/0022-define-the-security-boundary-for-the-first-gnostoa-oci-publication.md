---
type: Decision
title: Define the security boundary for the first Gnostoa OCI publication
description: Adopt the documented default runtime as the supported security boundary for a first-party Gnostoa OCI image, and define how shipped vulnerable components, vendor-available fixes, no-fix residuals and unknowns affect publication.
status: draft
generated:
  by: human:ktogias
  at: "2026-08-18T23:45:00Z"
sources:
  - id: security-boundary-work-item
    resource: https://github.com/ktogias/gnostoa/issues/50
    title: Define the first OCI runtime security and residual-risk publication boundary
x-project-knowledge:
  id: kit.decision.0022.define-the-security-boundary-for-the-first-gnostoa-oci-publication
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governs
      target: /assessments/first-oci-runtime-security-boundary-evidence.md
    - kind: references
      target: /decisions/0020-establish-v0-1-0-as-the-first-source-only-pre-stable-release-identity.md
    - kind: references
      target: /contracts/public-inheritance-surface.md
---

# Define the security boundary for the first Gnostoa OCI publication

Recorded by `agent:claude-opus-5` from the accountable maintainer's disposition.
The semantic choice is the maintainer's; this record is faithful transcription.

Scope: **Gnostoa-self, first-party OCI publication only.**

## Context

Two bounded read-only measurements exhausted the useful factual questions for the
measured runtime: for `linux/amd64`, no studied util-linux finding was observed
as applicable under the documented default runtime, several affected components
are nonetheless shipped, and an applicable supported security update is available
from the distribution while the image ships the older version.

What remained was not another observation. It was that Gnostoa had never decided
what runtime it guarantees, or whether shipping a vendor-designated vulnerable
component matters when the vulnerable path is unreachable by default. Without
that rule, remediation-versus-publication cannot be decided consistently.

No existing contract answers these questions: the nearest authorities are
trademark residual risk and the CI supply-chain block in
`core/continuous-integration.yaml`.

## Decision

**A. Supported-runtime security boundary.** The supported boundary for the first
Gnostoa OCI runtime is the **documented default runtime**: non-root runtime user;
Gnostoa's documented entrypoint and usage; no privileged mode; no consumer-added
capabilities; no consumer-added block or loop devices; no consumer-provided
fstab-based mount authorization; no added login or system service; and no other
privilege or configuration extension Gnostoa does not document as supported.
This is **not** a guarantee about the container engine, host kernel or arbitrary
consumer deployment.

**B. Consumer-added privileges and configuration.** A consumer who adds
privileged mode, capabilities, devices, fstab entries, privileged services or a
materially different entrypoint has changed the security assumptions. Such
configurations are **outside** the first published guarantee unless a later
Decision documents them. This does not make shipped vulnerable code irrelevant:
material exposure under reasonably foreseeable altered configurations remains
**residual-risk information**.

**C. Reachability and shipment hygiene are separate questions.** (1) Is the
behaviour reachable under the supported runtime? (2) Does the image ship a
vendor-designated vulnerable component for which a supported update already
exists? **A negative answer to (1) does not waive (2).**

**D. Vendor-fixed vulnerable shipped components.** For the first published image,
if the authoritative vendor source designates the installed shipped version
vulnerable **and** an applicable security update is already available through the
same supported channel, Gnostoa **will not knowingly publish the older
version** without a separate explicit owner exception. This is a
publication-hygiene rule and applies **even when the default runtime lacks the
exploitation preconditions**.

**E. No-fix residuals.** A shipped vulnerability with no currently available
supported vendor fix, affected code present and default-runtime preconditions
absent is **not automatically a publication blocker**. It requires a bounded
residual-risk disposition weighing current vendor status, authoritative severity,
component presence, supported-runtime applicability, known consumer-added
exposure and observation confidence. The owner may accept, defer, narrow scope or
require mitigation. This is deliberately **not** a numeric risk score.

**F. Default-runtime applicable findings.** A vulnerability demonstrably
applicable under the documented supported runtime **blocks publication** unless
remediated or separately accepted by an explicit owner exception with documented
rationale and bounds. **This Decision creates no exception.**

**G. Component-absent findings.** A source-package CVE is not image-applicable
merely because some binary package from the same source is installed. Where
authoritative component mapping shows the affected code is not shipped, that
finding does not block publication for the measured image and platform. The
evidence is preserved.

**H. UNKNOWN and inaccessible observations.** These remain UNKNOWN. They are
never converted into "no vulnerability", "safe" or "unaffected" because evidence
could not be obtained. A material UNKNOWN may itself require owner disposition
before publication.

**I. Architecture scope.** The completed measurements cover **`linux/amd64` only**,
so the first publication's security claim is scoped to that platform. A locally
measured amd64 result is **not** promoted to a multi-architecture claim; a future
multi-arch manifest needs per-platform evidence or a separately justified
equivalence argument.

**J. Candidate freshness.** Vendor status is candidate-time evidence. Before any
publication, re-check authoritative vulnerability status, current security
updates, exact shipped component versions and the applicability of newly observed
material findings. **A previously green timestamped assessment does not certify a
later candidate.**

**K. This rule is not OCI readiness.** It settles only the supported-runtime and
residual-vulnerability publication boundary. It establishes nothing about licence
or legal clearance, CPython, pip or Gnostoa-source vulnerability binding, registry
identity or permissions, image-digest reproducibility, provenance, signing,
attestation, multi-arch readiness, production readiness or independent assurance.

**L. Current consequence, from timestamped evidence only.** The evidence record
observes shipped util-linux-derived components whose vulnerable paths are not
reachable under the measured default runtime, **and** an available Debian
security update for relevant shipped components. Under **D**, the current image
candidate is therefore **not admitted** for first OCI publication without either
applying the available supported update or a separately authorized explicit
exception. This is a statement about that candidate at that timestamp, **not**
timeless policy, and **no exception is created here**.

**M. No mechanism is selected** — no scanner integration, monitoring service, VEX
system, SBOM framework, image updater, dependency bot, provider adapter, generic
threat-model framework, security policy engine, CI gate or distroless migration.

**N. Publication remains separate.** This Decision does **not** authorize OCI
publication. The next possible action is a separately selected, concretely scoped
remediation or publication-preparation slice.

**O. Source-identity consequence.** If satisfying this rule requires changing
image-defining source — Dockerfile, base pin, installed package versions, runtime
lock or image content — the resulting image **cannot** silently inherit the
`v0.1.0` source identity. Before publication the artifact must bind to an
immutable source identity that actually contains the remediated definition. That
release is **not** created here, and a future release must be justified by the
real source change rather than manufactured to exercise a runbook.

## Consequences

- Remediation-versus-publication is now decidable: the current candidate needs
  the available update or an explicit exception before a first image.
- This is Gnostoa-self release governance. It is **not** copied into adopter
  guidance and consumers inherit no threat model from it. What must be surfaced
  publicly at actual publication is a separate decision.
- The rule is deliberately conservative on hygiene and deliberately permissive on
  unreachable no-fix residuals, because those two cases differ in what the
  project can actually do about them.
- Decision 0020 and Decision 0021 are unchanged; `deployable_artifact` stays
  `false`; B3 stays deferred; no successor control or capability is selected.
- The rule is expected to need refinement once a second platform or a real
  publication candidate is measured.
