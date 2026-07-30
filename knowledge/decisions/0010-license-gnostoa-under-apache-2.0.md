---
type: Decision
title: License Gnostoa under Apache-2.0
description: Adopt one permissive license with an explicit patent grant for the complete Gnostoa distribution.
status: draft
generated:
  by: codex/gpt-5
  at: "2026-07-29T00:00:00Z"
x-project-knowledge:
  id: kit.decision.0010.license-gnostoa-under-apache-2.0
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governs
      target: /project/gnostoa.md
    - kind: references
      target: /contracts/public-inheritance-surface.md
    - kind: depends-on
      target: /decisions/0009-adopt-gnostoa-project-name.md
---

# License Gnostoa under Apache-2.0

## Context

Gnostoa combines executable tooling, schemas, profiles, policies, reusable
guidance, templates, documentation and anonymous examples. It is intended for
use by open-source and proprietary projects without imposing its project
identity or license on independent adopting-project knowledge.

A single repository-wide license minimizes the policy boundaries developers
and agents must track. A permissive license maximizes adoption, while an
explicit patent grant provides a clearer contribution and distribution
contract than short permissive licenses without express patent language.

Before this change the unpublished bootstrap repository had no license file or
package license metadata. The pre-implementation verification
`python -m unittest tests.test_tools.LicensePolicyTests -v` failed because both
`LICENSE` and `LICENSING.md` were absent.

## Decision

License all Gnostoa repository material for which contributors have licensing
authority under the unmodified Apache License, Version 2.0, unless a file
explicitly states otherwise. Publish the SPDX identifier `Apache-2.0` in
package and OCI-image metadata.

Use a short repository licensing guide to explain scope, adopting-project
independence, redistribution of copied materials, contribution terms and the
separation between copyright licensing and trademark permission. Do not claim
a copyright owner, `NOTICE` attribution or registered trademark until those
facts have been established.

Keep one license across code, schemas, policies, templates and documentation at
the bootstrap baseline. A future multi-license boundary requires a new
normative Decision and machine-verifiable scope.

## Consequences

- Open-source and proprietary projects may use and combine Gnostoa without
  relicensing independent project code or knowledge.
- Distributed copies and adaptations of Gnostoa material must satisfy the
  Apache-2.0 attribution and change-notice conditions.
- Contributors provide the copyright and patent grants defined by Apache-2.0
  for intentionally submitted contributions.
- A proprietary fork may keep its changes closed.
- License handling remains a single low-load rule for people, agents, package
  metadata and container tooling.
- Trademark registration, a trademark-use policy and ownership-specific
  notices remain separate future decisions.
