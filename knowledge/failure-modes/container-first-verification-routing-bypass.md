---
type: Failure Mode
title: Container-first verification routing bypass
description: Retrospective on an agent choosing an ad-hoc native dependency path instead of the project's existing development container, and the bounded routing/tooling correction.
status: draft
generated:
  by: codex/gpt-5
  at: "2026-08-15T00:00:00Z"
sources:
  - id: publication-baseline-work-item
    resource: https://github.com/ktogias/gnostoa/issues/1
    title: Prepare the Gnostoa publication baseline
  - id: cumulative-publication-change-request
    resource: https://github.com/ktogias/gnostoa/pull/23
    title: Prepare the cumulative source-publication candidate
  - id: streamlined-self-hosting-experiment
    resource: https://github.com/ktogias/gnostoa/issues/24
    title: Run one bounded B2 streamlined self-hosting experiment
x-project-knowledge:
  id: kit.failure-mode.container-first-verification-routing-bypass
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: conflicts-with
      target: /decisions/0005-container-first-runtime.md
    - kind: references
      target: /decisions/0016-evolve-human-agent-workflow-through-bounded-self-hosted-slices.md
    - kind: verified-by
      target: /runbooks/maintain-the-kit.md
---

# Container-first verification routing bypass

## Resume card

| Field | Current state |
|---|---|
| Event | During source-publication verification, host `./ci/verify extended` exposed a missing Python dependency. The agent started creating an ad-hoc `/tmp` virtual environment instead of using the existing `development` container target. |
| Impact | The owner stopped the route before it changed source or provider state. A temporary directory was the only local side effect. Extended verification remained incomplete and there was no false PASS, merge or publication claim. |
| Root cause | An agent routing error was enabled by a discoverability and enforcement gap: container capability existed, but the maintainer/agent front doors foregrounded native commands and supplied no single shell entrypoint for containerized verification. |
| Immediate correction | Stop the native installation path, build the exact checkout with the `development` container target and run the required suite inside that image. |
| Durable correction | README, `AGENTS.md` and the maintainer runbook now put the exact development-container command before the explicitly bounded native fallback. |
| Tooling finding | A project-owned one-command wrapper that resolves the repository root, builds/pins the development image and runs a named suite is a valid B2 candidate, not a first-publication prerequisite. |
| Resume route | For active B2 work, run the container command in the maintainer runbook and record the exact result. Route wrapper automation through [Issue #24](https://github.com/ktogias/gnostoa/issues/24) only if the measured P1 route still needs it. |

## Event

The project already had a pinned-base multi-stage `Dockerfile`, a
`development` target, a Development Container and containerized CI. During the
2026-08-15 publication-preparation change, the agent nevertheless ran the
extended suite natively. When the host lacked `license-expression`, it treated
dependency installation as the recovery route and began preparing an isolated
temporary environment under `/tmp`.

The owner interrupted that action and identified the conflict with Gnostoa's
container-first approach. The route was stopped before package installation
completed. No tracked file, branch, Pull Request, Issue, visibility setting or
artifact publication was changed by the aborted route. The failed host check
was not reported as successful.

## Findings

1. **Execution routing error.** The agent selected the native fallback without
   first attempting the primary development container.
2. **Discoverability gap.** The README called the Development Container the
   recommended environment but showed only native verification commands in
   that section. `AGENTS.md` likewise listed host commands as the completion
   route.
3. **Enforcement gap.** `ci/verify` correctly runs a named suite but does not
   select its execution environment. There is no repository-owned wrapper that
   makes container-first routing the easy default for shell-based agents.
4. **Capability is not missing.** The image target, locks and CI mapping already
   exist. The missing tooling is route selection, repository-root discovery
   and a compact one-command interface—not another container architecture.

## Root causes

- The phrase “native fallback” stated capability but did not define the
  decision point at which fallback is allowed.
- Maintainer and agent instructions described the intended environment and
  executable suites in separate places without one copyable end-to-end route.
- The recovery instinct optimized for the immediate missing package rather
  than restoring the project's declared execution boundary.
- No preflight warned that Docker was available while a host-only dependency
  repair was being attempted.

## Resolution and prevention

The immediate recovery is deliberately small. Verification resumes in an
image built from the exact working tree's `development` target, with the
checkout mounted read-only and the required suite executed inside the
container. The native route remains supported for restricted environments and
parity testing, but its use must be deliberate and its reason recorded.

The front doors now show that route directly. Until a wrapper exists, an agent
must not install host dependencies merely because a containerized check reports
that the host is incomplete. It first verifies container-runtime availability,
builds the exact development image and runs the suite there. If the container
route is unavailable or fails for a container-specific reason, the agent
records that blocker before selecting the native fallback.

The bounded tooling follow-up is a one-command wrapper that:

- resolves and validates the Gnostoa repository root;
- binds the image to the exact candidate revision or working-tree digest;
- builds or selects the `development` target;
- mounts the candidate read-only and runs one named `ci/verify` suite;
- preserves declared evidence output when requested; and
- reports container unavailability separately from suite failure.

That wrapper is candidate evidence for B2 in Issue #24. Implementing it now is
not necessary to finish source publication because the exact container command
is available and the failure is safely recoverable. Promoting a general agent
environment manager into the publication critical path would repeat the
critical-path drift already recorded elsewhere.

## Claim and authority boundaries

This record attributes the route choice to the agent and the correction to the
owner's intervention. It does not claim that the existing container runtime is
released, that container and native outputs have full parity evidence, or that
the proposed wrapper exists. It changes no public runtime contract, admits no
new implementation Work Item, approves no Pull Request and authorizes no merge,
visibility transition or artifact publication.
