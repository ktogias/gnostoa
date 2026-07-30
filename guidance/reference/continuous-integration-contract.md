---
type: Reference
title: Continuous-integration contract
description: Define provider-neutral events, evidence suites, capabilities and security controls for adopting projects.
status: draft
generated:
  by: codex/gpt-5
  at: "2026-07-29T00:00:00Z"
sources:
  - id: dora-test-automation
    resource: https://dora.dev/capabilities/test-automation/
    title: DORA test automation
  - id: github-secure-use
    resource: https://docs.github.com/en/actions/reference/security/secure-use
    title: GitHub Actions secure use
  - id: gitlab-components
    resource: https://docs.gitlab.com/ci/components/
    title: GitLab CI/CD components
x-project-knowledge:
  id: guidance.reference.continuous-integration-contract
  owners:
    - team:gnostoa-maintainers
  scope:
    - generic-guidance
  relations:
    - kind: guides
      target: /patterns/tiered-ci-and-local-feedback.md
    - kind: guides
      target: /workflows/configure-continuous-integration.md
    - kind: applies-to
      target: /reference/testing-and-verification-strategy.md
---

# Continuous-integration contract

## Purpose

Give every project the same small event and suite vocabulary without selecting
its language, test framework, hosting provider or deployment target.

## Content

Canonical event IDs:

| ID | Meaning |
|---|---|
| `branch_revision` | Latest revision pushed to a non-integrated branch |
| `change_request` | Latest reviewable Pull/Merge Request revision |
| `merge_candidate` | Candidate combined with the current integration branch |
| `integration` | Revision now present on the protected branch |
| `scheduled` | Time-triggered evidence not suitable for the fast gate |
| `release` | Artifact-promotion candidate for a deployable project |

Canonical suite IDs:

| ID | Ownership |
|---|---|
| `policy` | Toolkit validation, inherited policies and runtime lock |
| `fast` | Small deterministic feedback portfolio |
| `regression` | Required behavior-preserving project portfolio |
| `integration` | Declared component collaboration capability |
| `smoke` | Declared critical-path capability |
| `extended` | Scheduled performance, compatibility, security or soak evidence |
| `release` | Artifact and promotion evidence for deployable projects |

The inherited CI policy decides event activation and suite requirement. The
project verification manifest declares one verification runtime, applicable
capabilities and an exec-style command array for each required suite. `toolkit`
runtime means the pinned toolkit image already contains what the suites need.
`project` runtime requires one project verification image pinned by digest.

`./ci/verify <suite>` is the shared adapter used by local hooks and provider
pipelines. It must execute declared required suites, and may return a clear
successful `SKIP` only for a conditional capability declared false. It must not
silently skip `fast` or `regression`.
The provider's project-runtime variable must match the manifest image exactly.

Provider adapters:

- always report stable required check names;
- validate the latest reviewable revision;
- support a merge candidate through native merge-result or merge-queue events;
- cancel obsolete branch work but not integrated or release work;
- use immutable actions, components and images;
- grant minimum token permissions;
- withhold privileged secrets from untrusted changes;
- retain actionable reports and artifact identity.

Required path filtering must still report a result. Do not omit an entire
required workflow based on paths when that would leave its status missing or
ambiguous.

## Usage

Projects copy and specialize:

- `templates/continuous-integration.project.yaml`;
- `templates/verification.project.yaml`;
- `templates/verify.project` as `ci/verify`;
- the relevant provider adapter under `ci/`;
- optional hooks under `templates/githooks/`.

Validate both declarations with `knowledge check-ci-policy`. Repository
settings then make the provider's stable policy, fast, regression and
merge-candidate results required.
