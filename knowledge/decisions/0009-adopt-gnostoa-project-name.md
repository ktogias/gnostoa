---
type: Decision
title: Adopt Gnostoa as the project name
description: Give the generic knowledge architecture foundation a distinctive project identity without leaking branded vocabulary into consuming projects.
status: draft
generated:
  by: codex/gpt-5
  at: "2026-07-29T00:00:00Z"
sources:
  - id: obi-trade-mark-availability
    resource: https://www.obi.gr/emporika-simata/diadikasia-katochyrosis-simatos/elegchos-diathesimotitas-simaton/
    title: OBI trade-mark availability guidance
  - id: euipo-search-ip
    resource: https://www.euipo.europa.eu/en/search-ip
    title: EUIPO intellectual-property search services
  - id: wipo-search-before-filing
    resource: https://www.wipo.int/en/web/madrid-system/how_to/search/index
    title: WIPO search-before-filing guidance
  - id: wipo-global-brand-database
    resource: https://www.wipo.int/en/web/global-brand-database
    title: WIPO Global Brand Database
x-project-knowledge:
  id: kit.decision.0009.adopt-gnostoa-project-name
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governs
      target: /project/gnostoa.md
    - kind: references
      target: /contracts/public-inheritance-surface.md
---

# Adopt Gnostoa as the project name

## Context

The unpublished project needs a distinctive identity for its source repository,
runtime image, package metadata and future public site. Its working name,
Knowledge Architecture Kit, accurately describes the project but is generic,
hard to distinguish and difficult to own as a product identity.

Names derived from `Nous` have material conflicts in the knowledge-management,
software and AI markets. `Gnostoa` combines the knowledge root `gnosis` with the
place metaphor `stoa`: a shared, sheltered place for teaching, discussion and
exchange. The metaphor describes an environment in which governed knowledge is
made usable, rather than a proprietary knowledge object that consuming projects
must adopt.

When this Decision was prepared, the project had no baseline commit, remote,
published package or released runtime image. The rename therefore occurred
within the bootstrap exception
defined by Decision 0006 and does not require a compatibility alias for a
released artifact.

## Decision

Adopt **Gnostoa** as the project, distribution, runtime-image and site identity.
Use `gnostoa` for publishable artifact coordinates and self-policy identifiers.

Keep consumer-facing role vocabulary technology- and product-neutral. In
particular, retain the `knowledge` command, `KNOWLEDGE_KIT_*` integration
variables, generic profile vocabulary and anonymous examples. Consuming
projects must not need to introduce a `Gnostoa`-specific domain concept.

Keep stable internal concept IDs under the existing `kit.*` namespace; a
project rename does not justify changing persistent knowledge identities.
Coordinate any unpublished downstream checkout or specialization migration in
its owning repository when the public repository location is created.

## Preliminary availability screening

A bounded exact-string screening was performed on 2026-08-14 before first
publication. A GitHub repository search returned only the current private
`ktogias/gnostoa` repository. Exact `gnostoa` package-coordinate requests
returned `404` from PyPI and npm. An indexed web search found no obvious exact
collision. The crates.io API response was inconclusive and is not counted as
evidence of availability.

These observations are weak negative evidence, not trademark clearance. They
do not cover similar spellings or pronunciations, unregistered rights, every
relevant territory, or the goods and services that may overlap downloadable
software, hosted software, software development, documentation or training.
The official sources recommend searching identical and similar marks in the
relevant national, EU and international registers before filing or relying on
a name.

Before first source-repository visibility, the accountable owner may record a
bounded `conditional go` for the working identity after manually completing
and reading back OBI, EUIPO/TMview and WIPO searches. The record must bind the
search date, Greece and EU territory scope, the relevant class 9 and 42 goods
and services, class 41 when branded education or training is in scope, exact
and confusingly similar queries, retained results, unregistered-use screening,
residual risk and a rename or escalation trigger. A material or unresolved
similarity keeps source visibility blocked until it is resolved, independently
reviewed or renamed. This route is explicit owner risk acceptance for a
pre-release source repository, not trade-mark clearance.

Independent or qualified professional review remains required before a
trade-mark filing, stable package, OCI-image or site branding, paid or
commercial services, or other material reliance on the identity, and whenever
the bounded screening is ambiguous. Until the source-only `conditional go` is
recorded this Decision remains `draft`, and the project may prepare under the
working name but must not claim that `Gnostoa` is cleared or registrable. The
screening must be repeated when the name, territory, goods or services,
material search results or intended reliance changes.

## Consequences

- The project gains a short, distinctive identity suitable for a repository,
  package, OCI image and site.
- Generic guidance and adopting-project knowledge remain free of branded domain
  vocabulary.
- Package and image coordinates change before the first release, so no
  compatibility shim is required.
- Existing unpublished downstream paths may retain their bootstrap locations
  until their owners perform a coordinated repository migration.
- Source publication still requires human review of the complete baseline,
  repository protection and the bounded owner name-risk disposition above.
  Stable artifact branding or commercial reliance retains the independent or
  professional review gate.
