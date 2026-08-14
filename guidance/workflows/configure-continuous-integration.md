---
type: Workflow
title: Configure continuous integration
description: Adopt the generic CI policy, verification manifest, shared commands and one provider adapter without weakening inherited gates.
status: draft
generated:
  by: codex/gpt-5
  at: "2026-07-29T00:00:00Z"
x-project-knowledge:
  id: guidance.workflow.configure-continuous-integration
  owners:
    - team:gnostoa-maintainers
  scope:
    - generic-guidance
  relations:
    - kind: operationalizes
      target: /patterns/tiered-ci-and-local-feedback.md
    - kind: depends-on
      target: /reference/continuous-integration-contract.md
    - kind: governed-by
      target: /guardrails/non-negotiable.md
---

# Configure continuous integration

## Outcome

The project has a validated provider-neutral CI contract, project-owned suite
commands, an authoritative provider gate and optional bounded local hooks.

## Preconditions

- The project inherits the core profile and change-control policy.
- A pinned toolkit runtime and source/runtime lock exist.
- Owners can configure repository protection and CI variables.
- The project's fast and regression commands are known or can be introduced in
  one pilot area.

## Procedure

1. Copy `templates/continuous-integration.project.yaml` to
   `.knowledge/continuous-integration.yaml` and keep only justified stricter
   overrides.
2. Copy `templates/verification.project.yaml` to
   `.knowledge/verification.yaml`.
3. Declare `integration`, `smoke`, `extended` and `deployable_artifact`
   capabilities truthfully. Do not create ceremonial suites.
4. Map every active project-owned suite to an exec-style command, timeout,
   evidence type and pinned runtime. Keep the toolkit-owned `policy` suite in
   the provider adapter rather than redeclaring it in the project verification
   manifest.
5. Copy `templates/verify.project` to `ci/verify`; implement the declared suite
   commands and explicit conditional skips.
6. Run `knowledge check-ci-policy` against the policy and manifest.
7. Install the GitHub, GitLab or other provider adapter. Pin reusable
   workflows/components and images to immutable revisions.
8. Map branch push, Change Request, merge candidate, integration, schedule and
   release events to the generic event IDs. Enable merged-result or merge-queue
   validation where supported.
9. Make stable policy, fast, regression and merge-candidate statuses required
   on the protected branch. Disallow bypass.
10. Give validation jobs read-only permissions and no privileged secrets for
    untrusted changes. Disable persisted checkout credentials unless a
    separately authorized authenticated source operation requires them.
    Isolate environment credentials behind protected deployment gates.
11. Optionally copy `templates/githooks/` to `.githooks/` and enable it with
    `git config --local core.hooksPath .githooks`. Record that hooks remain
    advisory.
12. Push one intentionally failing pilot change and verify that fast,
    regression and protection gates fail for the intended reason. Restore
    green and record exact evidence.
13. For deployable projects, verify that release promotion consumes the exact
    CI artifact and performs post-deploy smoke evidence.

## Verification

- Policy and verification manifests validate without weakened inheritance.
- The latest candidate SHA owns every required status.
- Merge-candidate evidence includes the current protected branch.
- An obsolete branch run may be cancelled; integrated and release evidence is
  not cancelled.
- Missing hooks do not permit merge.
- Conditional suites match declared capabilities.
- A failed trunk pipeline creates immediate restore-green work.

## Recovery

If centralized automation is unavailable, block integration or use the audited
emergency change class; local hook success is not a substitute. If a central
workflow release breaks consumers, keep their pinned revision, publish a fixed
revision and upgrade through normal Change Requests.
