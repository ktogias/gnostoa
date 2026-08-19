---
type: Decision
title: Define supported update-channel semantics for base-bundled OCI components
description: Owner semantics for Decision 0022/D when a non-dpkg component's delivery path and its officially supported fixing route differ, and the resulting consequence for the measured pip candidate.
status: draft
generated:
  by: agent:claude-opus-5
  at: "2026-08-19T13:05:00Z"
sources:
  - id: update-channel-work-item
    resource: https://github.com/ktogias/gnostoa/issues/58
    title: Define the supported update-channel rule for base-bundled OCI components
  - id: oci-security-boundary-work-item
    resource: https://github.com/ktogias/gnostoa/issues/50
    title: Define the first OCI runtime security and residual-risk publication boundary
x-project-knowledge:
  id: kit.decision.0025.define-supported-update-channel-semantics-for-base-bundled-oci-components
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governed-by
      target: /decisions/0022-define-the-security-boundary-for-the-first-gnostoa-oci-publication.md
    - kind: references
      target: /assessments/pip-security-provenance-and-update-channel-evidence.md
    - kind: references
      target: /decisions/0023-apply-the-supported-debian-util-linux-security-update-to-the-oci-runtime.md
---

# Define supported update-channel semantics for base-bundled OCI components

Recorded by `agent:claude-opus-5` from the accountable maintainer's exact
disposition. The semantic choice is the maintainer's; this record is faithful
transcription, not a further approval step.

Scope: **Gnostoa-self, first-party OCI publication only.**

## Context

Decision 0022 remains the governing first-OCI security and residual-risk
authority. This Decision **supplements** it and **does not rewrite or reinterpret
its historical text**.

Decision 0022/**D** says, in substance: a shipped component that an authoritative
vendor source designates vulnerable, for which an applicable security update is
already available **through the same supported channel**, must not knowingly be
published in its older form absent a separate explicit owner exception — and this
holds even where the default runtime lacks the exploitation preconditions.

That rule was written against the util-linux fact pattern, where one channel did
both jobs:

| | delivery path | fixing route |
|---|---|---|
| util-linux | Debian package and security channel | **the same** channel |

A bounded read-only study then measured a fact pattern in which the two separate.
Its evidence is recorded in
[pip security provenance and update-channel evidence](../assessments/pip-security-provenance-and-update-channel-evidence.md);
the candidate-time facts live there rather than here, so a moving advisory feed
cannot turn into stale policy.

In summary: the component is **not dpkg-owned**, is **absent from the runtime
lock**, and is **not selected by Gnostoa's image definition**. It arrived through
the interpreter's bundled `ensurepip` mechanism inside the official base image —
an installation route the component's own maintainers document as supported. Its
maintainer designates the shipped version vulnerable and publishes fixed releases
through a **different** officially supported route. The delivering route
structurally cannot supply the fix while the candidate stays on the current
interpreter minor series.

Two defensible readings of "the same supported channel" produced **opposite**
publication outcomes:

- **narrow, channel-identity** — "same channel" means the mechanism that delivered
  the component, so the rule does not engage;
- **broad, component-vendor** — "same channel" means the component maintainer's
  own supported distribution and update route, so the rule engages.

Existing authority could not choose between them, and no further measurement
could: the facts are complete on both sides. What was missing was **meaning**.

## Decision

**A. Component-maintainer supported-update reading is selected.** For Decision
0022/D, *"the same supported channel"* **shall not** require byte-for-byte identity
with the mechanism that originally delivered the component.

**B. Qualifying criteria.** For the first Gnostoa OCI publication an update
qualifies under Decision 0022/D when **all** of the following hold:

1. the affected shipped component has an **authoritative component identity**;
2. the fixing source is **operated or explicitly supported by that component's
   authoritative upstream maintainer or project**;
3. upstream **documents the route** as a supported installation or update route
   for that component;
4. the fixed release is **compatible** with Gnostoa's supported runtime and
   platform;
5. the exact fixed artifact or version can be **deterministically identified and
   integrity-bound**;
6. the route does **not silently substitute** a third-party fork, mirror,
   distribution or repackaging as semantic authority;
7. the observed update **actually addresses** the vendor-designated affected
   component and version.

**C. What matters.** Same authoritative component, plus an officially supported
component update path, plus a bounded compatible fixed artifact — **not** an
identical historical transport mechanism. The delivery mechanism and the fixing
mechanism **may** therefore differ.

**D. Explicit exclusions.** This Decision does **not** imply that any package
index is automatically trusted; that any third-party mirror is a supported
channel; that any newer version is a valid security update; that changing
distribution or vendor is equivalent to updating the same component; that every
base-bundled component may automatically be upgraded independently; or that an
actor may invent an update source because the base source is stale. **Each
non-dpkg component must establish its own authoritative component identity and its
own supported update path.**

**E. Consequence for the measured candidate.** Under this reading, the component's
officially supported component-native update route qualifies as a supported update
channel for Decision 0022/D. The established pip fact pattern therefore
**triggers Decision 0022/D**. The measured candidate **must not be admitted for
first OCI publication while it knowingly ships the affected component version**,
absent either remediation satisfying Decision 0022/D or a separately authorized
explicit owner exception.

**F. No exception is granted.** This Decision creates none.

**G. Shipment hygiene, not liveness.** Decision 0022/D is a **shipment-hygiene**
rule. A future remediation is therefore **not** sufficient merely because the
active component reports a fixed version. Any future claim that this blocker is
cleared must prove that **no vendor-designated affected code copy remains
shipped**, or establish through authoritative component mapping that a retained
copy is **not** the affected component. This is a success criterion; it selects no
remediation method.

**H. Reachability does not waive hygiene.** The upstream qualification recorded for
CVE-2025-8869 is preserved in the evidence record and must not be erased. Under
Decision 0022/**C**, default-runtime unreachability alone does not waive D. Where
future authoritative component mapping demonstrates genuine component absence,
Decision 0022/**G** may apply — but a runtime-path qualification must **not** be
promoted into component absence without that evidence. This Decision performs no
such mapping.

**I. No remediation is selected.** Not an explicit upgrade, not removal, not
`ensurepip` modification, not a base-image refresh, not an interpreter-line
migration, and not an exception. The shapes recorded in the evidence record remain
**evidence only**; choosing among them is a separate lifecycle effect requiring its
own admission.

**J. Limitations that a future remediation must not overlook.** An active upgrade
**alone** leaves the affected bundled wheel in place. A naive uninstall **alone**
is not component absence, because the bundled artifact survives it and can
reinstall the affected version. A refresh to the currently observed base did
**not** supply a fix and must not be assumed as the remedy without fresh
candidate-time evidence. Moving to a different interpreter minor line is a separate
runtime and base change that couples to the still-unresolved interpreter
vulnerability-binding question and must not be absorbed into a component
remediation without separate admission.

**K. Residual taxonomy is corrected, not dispositioned.** The specifically
established Decision 0022/**E** residual is **CVE-2026-3184**; **CVE-2022-0563**
remains a Decision 0022/**G** component-absent case; the roughly 110 other open,
no-fix Debian observations whose applicability was never established remain
Decision 0022/**H** **UNKNOWN** and are **not** E-class residuals. None of them is
dispositioned here.

**L. Source-identity consequence.** Any remediation touching the image definition,
the base image, the interpreter line or shipped runtime contents changes
image-defining source. The existing invariant stands: **a new immutable source
identity is required before eventual OCI publication**, and it is neither created
nor selected here. Source stabilization remains premature.

**M. Publication remains unauthorized**, `deployable_artifact` remains `false`, and
no registry is selected.

**N. No mechanism is selected** — no scanner, monitoring service, VEX or SBOM
framework, updater, dependency bot, provider adapter, CI security gate or
enforcement route.

**O. Gnostoa-self only.** This is first-party release governance. It is not copied
into adopter guidance, consumers inherit no threat model from it, and what must be
surfaced publicly at actual publication remains a separate decision.

## Consequences

- Decision 0022/D is now decidable for base-bundled, non-dpkg components, and the
  measured candidate has a definite answer: **blocked, absent remediation or an
  explicit exception**.
- The rule is deliberately conservative. It widens what counts as a supported
  fixing channel, which makes **more** findings engage D rather than fewer, and it
  pays for that with the seven criteria in **B** so that "an update exists
  somewhere" can never be enough on its own.
- Criterion **B.6** carries most of the safety. Without it, the broad reading would
  legitimise any mirror or repackaging that happens to publish a higher version.
- Decisions 0022, 0023 and 0024 are unchanged, as are `v0.1.0`, the source-release
  runbook, the util-linux remediation result and the drift retrospective. B3 stays
  deferred, drift Half 2 stays not admitted, and no successor workflow, control or
  capability is selected.
- This Decision settles channel **semantics** only. It establishes nothing about
  licence or legal clearance, interpreter or application vulnerability binding,
  registry identity or permissions, image-digest reproducibility, provenance,
  signing, attestation, multi-arch readiness or production readiness.
- The rule is expected to need refinement the first time a second non-dpkg
  component with a different channel shape is measured.
