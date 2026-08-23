---
type: Source
title: Weather-note cold-start onboarding result
description: Bounded comparison of three owner-provided cold-start evaluations through the immutable v0.1.1 source and OCI route, including technical success and semantic counter-evidence.
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
  - id: weather-note-third-run-work-item
    resource: https://github.com/ktogias/gnostoa/issues/97
    title: Reconcile the third weather-note cold-start result
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
    - kind: references
      target: /lifecycles/evidence-gated-capability-evolution.md
    - kind: references
      target: /assessments/b2-control-selection-and-failure-path-map.md
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

## Third-run semantic counter-evidence

The owner supplied a third evaluation, identifying its evaluator as **Claude
Opus 5**. That model identity is owner-reported and was not independently
verified. Native supported execution succeeded; validation and four negative
controls failed closed; non-weakening enforcement held; context generation was
deterministic; and no Gnostoa maintainer intervened. The technical disposition
is **PASS**.

Read-back of the two supplied Markdown artifacts nevertheless establishes a
**SEMANTIC PARTIAL FAIL**:

- the context pack repeatedly declares `Owners:
  team:weather-note-maintainers`, and the task projection declares
  `Owner/class: team:weather-note-maintainers / normal`, although no real owner
  or team identity was supplied;
- the projection says `State: ready`, but also says recorded status grants no
  acceptance, integration or external effect, names an accountable maintainer
  as the next actor and makes owner clarification its next action. It was not
  implementation-ready. The schema-valid state can at most describe readiness
  for that clarification; this is not evidence of a validator defect;
- its only surfaced semantic question was what to print when
  `humidity_percent` is absent. It omitted the permitted JSON type, range,
  precision and present-value summary behaviour;
- the context pack contains useful descriptions and relations, but does not
  contain every material constraint or open question claimed by the evaluator;
- the reported five-minute duration excludes documentation reading and is not
  comparable with the two end-to-end measurements; and
- the evaluator added policy, CI and verification surfaces while calling the
  result minimal adoption, then judged permanent adoption positively. Those
  facts demonstrate evaluator variation in the minimal/full boundary and
  product-fit judgement, not a general adopter conclusion.

The material lesson is **schema and policy validity do not establish semantic
truth or completeness**. That rule remains owned by the
[evidence-gated lifecycle](../lifecycles/evidence-gated-capability-evolution.md)
and its linked
[CF-11 evidence](b2-control-selection-and-failure-path-map.md); this assessment
does not create a duplicate rule or new mechanism.

## Three-run comparison

| Run | Technical execution | Semantic fidelity | Timing | Invented or omitted facts | Adoption judgement |
|---|---|---|---|---|---|
| First | STRONG PASS: immutable OCI/source route, offline validation and deterministic context | Correctly stopped on underspecified humidity semantics | 11 minutes 11.5 seconds end to end | No missing fact reported as invented; type, range and precision remained open | Negative for this tiny one-off project |
| Replication | STRONG PASS: identity checks, network-isolated validation and byte-identical context | Correctly stopped on type, range and summary semantics | 574 seconds end to end | No missing fact reported as invented; owner decision remained open | Negative for this tiny one-off project |
| Third | TECHNICAL PASS: native route, four fail-closed controls, non-weakening enforcement and deterministic context | SEMANTIC PARTIAL FAIL: invented ownership, incomplete questions and an over-broad readiness/adoption account | Five-minute execution claim excludes documentation reading; not comparable | Invented `team:weather-note-maintainers`; omitted type, range, precision and present-value summary behaviour | Positive; retained only as evaluator judgement |

The first two timings are comparable as declared end-to-end measurements. The
third is not. The conflicting adoption verdicts are three evaluator judgements,
not evidence for or against general product fit.

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

The complete transcripts, disposable fixtures and raw command outputs were not
retained with the declared owner packets. This assessment does not reconstruct
them. The replication packet supplied the context-pack digest above but did not
retain the complete raw fixture, command log or an independently verifiable
artifact manifest.

For the third run, the supplied artifacts were read back byte-for-byte and
verified as:

- context pack:
  `sha256:a4ee15cebee3f4eb590dfd35c781e2d5e15a4a3ae7c1bf8cd8fc5f093f7c940b`;
- current task projection:
  `sha256:9869a3802b63f59572849b4562a6bdb99bed9cf6b6f6b5c16b30f701699d2824`.

Those complete artifacts remain supplied evidence rather than checked-in
canonical records; only the material excerpts and hashes are preserved here.
The third run's fixture, full report, test log, claimed deterministic-output
pair and five-minute timing were not independently reproduced. Immutable source
and OCI identities were read back from Gnostoa's existing publication
authority; all three evaluations otherwise remain owner-provided evidence.

The results are not B3 independent adoption, not Decision 0036's internal
fresh-agent delivery-transfer falsification, and not evidence of human
usability, net productivity, easy adoption or general product fit. The third
run does not satisfy either outstanding validation merely because a different
owner-reported model produced it. This assessment changes no release, image,
runtime, provider or adoption-policy state. The next external experiment remains
one real B3 in an independently owned project with human-owner ground truth.
