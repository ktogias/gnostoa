---
type: Source
title: Weather-note cold-start onboarding result
description: Bounded owner-provided measurement of one fresh agent's public technical onboarding through the immutable v0.1.1 source and OCI route.
status: draft
generated:
  by: codex/gpt-5
  at: "2026-08-23T08:41:21Z"
sources:
  - id: weather-note-cold-start-work-item
    resource: https://github.com/ktogias/gnostoa/issues/93
    title: Canonicalize the weather-note cold-start onboarding result
  - id: weather-note-replication-work-item
    resource: https://github.com/ktogias/gnostoa/issues/95
    title: Reconcile the replicated weather-note onboarding result
x-project-knowledge:
  id: kit.assessment.weather-note-cold-start-onboarding-result
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governed-by
      target: /decisions/0042-accept-the-weather-note-cold-start-onboarding-result.md
    - kind: references
      target: /assessments/v0-1-1-source-and-oci-publication-result.md
    - kind: references
      target: /decisions/0036-canonicalize-bounded-self-hosted-delivery-practice.md
---

# Weather-note cold-start onboarding result

## Subject and measured result

The accountable maintainer supplied the result of one genuinely fresh agent
using only public Gnostoa material in a clean disposable `weather-note` project.
The measured elapsed time was **11 minutes 11.5 seconds**, with no Gnostoa
maintainer intervention.

The agent anonymously used the public `linux/amd64` image by immutable digest,
`ghcr.io/ktogias/gnostoa@sha256:73e5bd55fb4fed4accc836294a97b144d8b7060d68b19c3631ab7c05b5cd1455`,
and pinned the matching immutable `v0.1.1` source. Validation and deterministic
context generation succeeded offline. The adopting bundle did not inherit
Gnostoa-self knowledge, no application code changed and no absent domain fact
was invented.

The generated handoff stopped because `humidity_percent` lacked an
owner-defined type, range and precision. That stop was correct: the missing
semantic contract requires an accountable project-owner choice.

Disposition: **STRONG PASS for public cold-start technical onboarding.**

## Replication

A second genuinely fresh public evaluation completed the same bounded technical
route in **574 seconds**. It verified the immutable `v0.1.1` source and OCI
identities, then ran every Gnostoa operation after download with `--network
none`. Source/runtime lock checking, bundle validation and context generation
passed. Two context generations were byte-identical with SHA-256
`8ccd75c2b43c2e8048b3f4cfa7cae93a67aa1ea8125e4ce4e2ea046d80cfb8ae`.

The disposable project contained four project concepts, 11 additions and 275
lines. No Gnostoa maintainer intervened, no application implementation was
performed and no absent domain fact was invented. The handoff again stopped on
the missing `humidity_percent` type, range and summary semantics, leaving that
owner decision unresolved rather than fabricating it.

This replicates the **STRONG PASS** technical result. It does not establish that
the shorter elapsed time was caused by the documentation changes, nor human
usability, productivity benefit, B3 transfer or general product fit. The second
evaluator also judged permanent adoption disproportionate for this tiny
one-off project; repetition makes that a synthetic product-fit hypothesis, not
general adopter guidance.

## Observed documentation friction

The exercise identified five Gnostoa documentation findings:

1. the quick start's source-only publication projection contradicted the
   current README and public OCI state;
2. documentation frozen inside the immutable source tag did not prominently
   distinguish its historical source-only state from the later publication;
3. minimal evaluation/orientation was not clearly separated from full
   repository, CI and provider adoption;
4. the existing starting profile and Project concept examples were not directly
   discoverable from the adoption route; and
5. the correct treatment of an unknown accountable owner was unclear.

DNS, Docker-socket, web-cache and placeholder-`.git` failures were specific to
the disposable evaluation environment and are excluded from the Gnostoa
findings.

## Product-fit observation

The evaluator would not retain Gnostoa for this tiny one-off CLI because its
permanent maintenance cost exceeded the observed benefit. The evaluator would
reconsider when repeated human/agent handoffs or accumulating constraints and
Decisions make durable orientation more valuable. This single-project result is
bounded product-fit evidence, not a general benefit or rejection claim.

## Evidence limits

The complete transcript, disposable fixture, raw command outputs and a complete
hash manifest were not retained with the declared owner packet. This assessment
does not reconstruct them. The replication packet supplied the context-pack
digest above but did not retain the complete raw fixture, command log or an
independently verifiable artifact manifest. Immutable source and OCI identities
were read back from Gnostoa's existing publication authority; both adoption
measurements otherwise remain owner-provided evidence.

The result is not B3 independent adoption, not Decision 0036's internal
fresh-agent delivery-transfer falsification, and not evidence of human
usability, net productivity, easy adoption or general product fit. It changes
no release, image, runtime, provider or adoption-policy state.
