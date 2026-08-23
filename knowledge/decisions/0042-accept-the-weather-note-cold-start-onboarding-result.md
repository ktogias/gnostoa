---
type: Decision
title: Accept the weather-note cold-start onboarding result
description: Accept one bounded strong-pass public cold-start result, correct the observed onboarding friction and preserve separate evidence requirements for independent adoption and internal-delivery transfer.
status: draft
generated:
  by: codex/gpt-5
  at: "2026-08-23T08:41:21Z"
sources:
  - id: weather-note-cold-start-work-item
    resource: https://github.com/ktogias/gnostoa/issues/93
    title: Canonicalize the weather-note cold-start onboarding result
x-project-knowledge:
  id: kit.decision.0042.accept-the-weather-note-cold-start-onboarding-result
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governed-by
      target: /decisions/0036-canonicalize-bounded-self-hosted-delivery-practice.md
    - kind: references
      target: /decisions/0038-establish-v0-1-1-as-a-source-only-patch-release-identity.md
    - kind: references
      target: /decisions/0039-publish-v0-1-1-as-the-first-public-ghcr-image.md
    - kind: references
      target: /decisions/0040-reconcile-the-v0-1-1-source-and-oci-publication-result.md
    - kind: governs
      target: /assessments/weather-note-cold-start-onboarding-result.md
---

# Accept the weather-note cold-start onboarding result

Recorded by `codex/gpt-5` from the accountable maintainer's disposition. The
result classification and documentation scope are the maintainer's; this record
is faithful transcription.

## Context

A genuinely fresh agent used only public Gnostoa material in a clean disposable
`weather-note` project. The exercise completed the selected technical route but
also exposed five concrete onboarding documentation frictions. This bounded
result needs one durable home without promoting a disposable evaluation into
independent-adoption or product-fit evidence.

## Decision

**A. Result.** Accept the linked assessment as a **STRONG PASS** for public
cold-start technical onboarding. The fresh agent anonymously used the immutable
`v0.1.1` OCI route, pinned the matching source, validated and generated bounded
context offline, inherited no Gnostoa-self knowledge, changed no application
code and invented no missing domain fact, without Gnostoa maintainer help.

**B. Semantic stop.** Treat the correct stop on `humidity_percent` as useful
evidence that Gnostoa can expose an underspecified owner-semantic decision. The
missing type, range and precision remain for the adopting project's owner; the
tool and agent must not manufacture them.

**C. Product-fit bound.** Preserve the measured conclusion that permanent
adoption may cost more than it returns for a very small, low-handoff one-off
project. Reconsideration becomes plausible when human/agent handoffs repeat or
constraints and Decisions accumulate. This is a bounded hypothesis, not a
general product-fit conclusion.

**D. Evidence exclusions.** The result is not B3 independent adoption, not
Decision 0036's fresh-agent transfer test for Gnostoa's internal delivery route,
and not proof of productivity benefit, human usability, easy adoption or general
product fit. Environment-specific DNS, Docker-socket, web-cache and placeholder
`.git` failures are excluded from the Gnostoa result.

**E. Documentation correction.** Make the public quick start identify the
published `v0.1.1` linux/amd64 OCI artifact and prefer its immutable registry
digest. Distinguish the historical source-only projection stored inside the
immutable source tag from later current-main and Release publication records.

**F. Route boundary.** Label the short public route as minimal evaluation and
orientation. Keep full repository, CI and provider adoption in the existing
adoption workflows. Route directly to the existing project profile and Project
concept examples; do not create a second adoption guide, generator, template
family or new CLI.

**G. Unknown accountability.** An unknown accountable owner stays explicit and
draft or unresolved. Do not invent a person. A syntactic role placeholder may
keep a draft structurally valid, but it is not verified accountability and must
not support promotion to stable.

**H. Change boundary.** This is a `normal` knowledge/documentation-only change.
It does not alter executable source, SB2, runtime, source identity, public OCI
identity, provider state, release state, policy, schema, CI or roadmap.

## Consequences

- The current public onboarding route no longer contradicts the published OCI
  state.
- Minimal evaluation remains a bounded technical check rather than implicit
  commitment to provider-integrated adoption.
- B3 and Decision 0036 transfer evidence remain outstanding and retain their
  own subjects.
- The next transfer measurement should be one real B3 experiment in an
  independently owned project, not another `weather-note` replay.

