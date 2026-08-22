---
type: Source
title: GitHub security observation pilot
description: Dated provider read-back for the bounded Dependency graph, Dependabot alert, Secret Protection and Python CodeQL observation pilot.
status: draft
generated:
  by: codex/gpt-5
  at: "2026-08-22T22:46:47Z"
sources:
  - id: github-security-observation-work-item
    resource: https://github.com/ktogias/gnostoa/issues/91
    title: Pilot GitHub security observation surfaces
  - id: dependency-graph-update-run
    resource: https://github.com/ktogias/gnostoa/actions/runs/32603221140
    title: Initial dependency graph update
  - id: initial-codeql-run
    resource: https://github.com/ktogias/gnostoa/actions/runs/32603242528
    title: Initial GitHub-managed CodeQL setup run
x-project-knowledge:
  id: kit.assessment.github-security-observation-pilot
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governed-by
      target: /decisions/0041-pilot-supplemental-github-security-observation.md
    - kind: references
      target: /decisions/0035-accept-bounded-first-party-source-security-sufficiency-for-the-first-oci-candidate.md
    - kind: references
      target: /decisions/0040-reconcile-the-v0-1-1-source-and-oci-publication-result.md
    - kind: verified-by
      target: /runbooks/deliver-bounded-self-hosted-slice.md
---

# GitHub security observation pilot

## Dated subject and result

The provider observation window began on 2026-08-22 at 22:40 UTC and the
settled inventory below was retrieved through 22:46 UTC. The repository subject
was protected `main` commit
`235111eb0f0f8109ca99cfe711a90a1fba29ef15`, tree
`98af2c0d2a2d5695334713a385ca9cce92c7ce20`. The repository was public, its
worktree was clean and no open Pull Request or active `roadmap:now` item
preceded Work Item #91.

The pilot enabled the selected supplemental observations. No open Dependabot,
secret-scanning or CodeQL alert identity was returned in the settled initial
inventories. No apparent live credential was observed. This is a bounded dated
result, not evidence that every dependency, secret or first-party vulnerability
is represented.

## Exact provider transition

| Surface | Before | Settled read-back |
|---|---|---|
| Private vulnerability reporting | enabled | enabled |
| Dependency graph | accessible; 0 manifests before graph processing | graph update run `32603221140` succeeded; 3 parseable manifests |
| Dependabot alerts | disabled | enabled; 0 open alerts |
| Dependabot security updates | disabled | disabled |
| Grouped security updates | not selected; security updates disabled | disabled/not configured |
| Dependabot version updates | no `.github/dependabot.yml` | disabled; no configuration added |
| Secret scanning | disabled | enabled; 0 open alerts |
| Secret-scanning push protection | disabled | enabled |
| Secret validity checks | disabled | disabled |
| Non-provider secret patterns | disabled | disabled |
| CodeQL default setup | `not-configured` | `configured`, Python, default query suite, remote threat model, standard runner, weekly schedule |
| Merge enforcement | required checks were `policy`, `fast`, `regression`, `smoke`; no ruleset | unchanged; CodeQL not required |
| Code Quality AI findings | provider API reported feature unavailable | not configured/enabled |

GitHub's separate secret-scan history endpoint returned `404` with
`Advanced Security is disabled on this repository`, even though repository
secret scanning and push protection read back enabled and the alert endpoint
was available. The pilot therefore records the enabled settings and the zero
alert inventory, but does not claim an independently observed backfill-complete
timestamp.

## Dependency graph inventory

The initial graph contained 3 parseable manifests and 9 manifest dependency
entries representing 8 unique dependencies:

| Manifest | Provider entries |
|---|---|
| `pyproject.toml` | `jsonschema`, `mkdocs`, `mkdocs-material`, `pyyaml`, `setuptools` |
| `.github/workflows/publish-oci.yml` | `actions/attest`, `actions/checkout` |
| `.github/workflows/verification.yml` | `actions/checkout`, `actions/upload-artifact` |

The provider-generated SBOM contained those 8 dependencies plus the repository
root package. The PyPI application constraints other than `setuptools` had no
resolved version in that graph. Neither `requirements/runtime.lock` nor
`requirements/development.lock` appeared as a graph manifest. Debian packages,
CPython, bundled Expat, OCI layer contents and the exact installed runtime
inventory were also outside this provider graph. Zero Dependabot alerts applies
only to the provider-recognized graph, not the full OCI/runtime subject.

## CodeQL subject and result

GitHub-managed run `32603242528` completed successfully against
`refs/heads/main` at the exact starting commit. Job `Analyze (python)` completed
successfully; provider-generated `Adjust Configuration` was `SKIPPED`, not
`PASS`.

Analysis `1657801140` used CodeQL 2.26.3, category `/language:python`, build mode
`none`, the default query suite and the remote threat model. It evaluated 43
rules and returned 0 results. The repository required-check set remained
`policy`, `fast`, `regression`, `smoke`; no CodeQL merge enforcement or
repository CodeQL workflow was created.

The analysis is bounded to GitHub's Python CodeQL subject and default queries.
It does not enumerate dependency vulnerabilities, execute the built runtime,
model Debian or CPython security, establish file-by-file semantic coverage or
replace G3. Copilot Autofix is documented by GitHub as available by default for
public repositories using CodeQL; no alert or suggestion existed to exercise
it here. Any future output remains advisory under Decision 0041.

## Initial alert inventory

| Provider inventory | Open alert IDs | Result and disposition |
|---|---|---|
| Dependabot | none | bounded zero observation for the recognized dependency graph |
| Secret scanning | none | bounded zero observation; no credential value was retrieved or exposed |
| CodeQL | none | bounded zero observation for the exact Python analysis above |

There is therefore no material pilot alert requiring a remediation owner
decision. Future alert identity, severity, path, subject applicability and
state remain live provider facts and must be read back when acted upon.

## Authority and limitations

Provider settings, scan runs and alert objects are authoritative for the live
observations. This dated assessment preserves the initial result and its exact
subject. It must not be maintained as a synchronized current-alert dashboard.

An alert supplies an observation, not source-change authority. The required
route is subject/applicability triage, owner admission when material, then one
bounded remediation. Provider suggestions do not invalidate `v0.1.1`, authorize
a rebuild or establish evidence by themselves.

The pilot did not enable update PRs, grouped updates, AI findings, validity
checks, additional secret patterns, third-party actions, merge enforcement or
periodic triage machinery. It made no source/runtime/test/workflow/policy,
Release, GHCR or attestation change.
