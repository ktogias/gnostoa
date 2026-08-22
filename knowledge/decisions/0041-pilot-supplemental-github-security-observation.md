---
type: Decision
title: Pilot supplemental GitHub security observation
description: Retain private vulnerability reporting and enable bounded GitHub dependency, secret and Python CodeQL observations without update automation, merge enforcement or automatic remediation authority.
status: draft
generated:
  by: codex/gpt-5
  at: "2026-08-22T22:46:47Z"
sources:
  - id: github-security-observation-work-item
    resource: https://github.com/ktogias/gnostoa/issues/91
    title: Pilot GitHub security observation surfaces
x-project-knowledge:
  id: kit.decision.0041.pilot-supplemental-github-security-observation
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governed-by
      target: /decisions/0036-canonicalize-bounded-self-hosted-delivery-practice.md
    - kind: references
      target: /decisions/0024-separate-stable-navigation-from-volatile-state.md
    - kind: references
      target: /decisions/0035-accept-bounded-first-party-source-security-sufficiency-for-the-first-oci-candidate.md
    - kind: governs
      target: /assessments/github-security-observation-pilot.md
---

# Pilot supplemental GitHub security observation

Recorded by `codex/gpt-5` from the accountable maintainer's disposition. The
feature selection and authority boundaries are the maintainer's; this record is
faithful transcription.

## Context

Gnostoa has a public pre-stable source release and OCI artifact. Existing
candidate-bound security evidence remains authoritative for its measured
subjects, but GitHub offers additional repository observations that can be
piloted without converting provider findings into automatic change authority.

## Decision

**A. Selected observations.** Keep GitHub private vulnerability reporting
enabled. Enable the repository dependency graph and Dependabot alerts, GitHub
Secret Protection through secret scanning and push protection, and GitHub-managed
CodeQL default setup for Python with the default query suite. CodeQL remains
non-blocking: do not add a repository workflow, required check or merge rule for
it in this pilot.

**B. Rejected automation.** Keep Dependabot security updates, grouped security
updates and version updates disabled. Do not create automated dependency Pull
Requests, dismiss alerts or apply provider suggestions in this slice.

**C. AI boundary.** Keep the Code Quality AI-findings preview disabled. Copilot
Autofix may remain available with CodeQL, but every suggestion is advisory. It
is not evidence, owner admission, merge authority or automatic remediation.

**D. Supplemental scope.** These provider facilities are supplemental
observation surfaces. They do not establish dependency completeness, OCI or
runtime security, G3 satisfaction, release safety or absence of secrets. The
dependency graph is not the complete Debian, CPython, bundled-component or
installed-OCI inventory.

**E. Alert routing.** A provider alert is an observation. Its route is:

> subject and applicability triage -> owner admission when material -> bounded
> remediation

No alert automatically invalidates `v0.1.1`, authorizes a source change,
triggers a rebuild, creates a release or changes publication state.

**F. Provider and canonical authority.** Live settings and alert inventories
remain provider-authoritative and can change after this Decision. The linked
assessment is a dated result, not a timeless projection. Durable owner
dispositions belong in project knowledge; unresolved provider observations do
not become Decisions without the normal admission route.

**G. Public report route.** `SECURITY.md` identifies the latest published
pre-stable release, currently `v0.1.1`, and routes undisclosed reports to private
vulnerability reporting rather than public Issues. It promises neither a fixed
response SLA nor security certification.

**H. Change boundary.** This is a `critical` Gnostoa-self provider-security and
reporting-route change. It creates no generic alert mechanism, CI/policy/schema
change, source/runtime remediation, dependency update, release, image rebuild
or publication effect.

## Consequences

- Initial zero-alert results are useful bounded observations, not negative
  security certification.
- Material future alerts require a separate owner disposition and the smallest
  admitted evidence/remediation slice.
- The settings may continue to observe later commits, but this Decision does not
  create a periodic triage SLA or update automation.

### Non-claims

This Decision does not claim complete dependency enumeration, secret absence,
general security, G3 replay, release safety, legal clearance or production
readiness. Copilot suggestions and GitHub workflow success are not independent
semantic approval.
