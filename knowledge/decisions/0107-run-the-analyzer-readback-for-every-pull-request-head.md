---
type: Decision
title: Run the analyzer readback for every Pull Request head, and again on request
description: The authenticated analyzer readback also runs when Gnostoa verification completes for a Pull Request, and on a repository_dispatch request an agent can send with its own token, so no one needs to dispatch it by hand. Amends Decision 0091's trigger rule; the environment, the exact-head binding and the read-only authority are unchanged.
status: draft
generated:
  by: anthropic/claude-opus-5-5
  at: "2026-10-07T13:20:00Z"
sources:
  - id: work-item
    resource: https://github.com/ktogias/gnostoa/issues/387
    title: Run the analyzer readback automatically on every Pull Request head, with an agent-requestable rerun
  - id: readback-0091
    resource: ./0091-add-authenticated-provider-neutral-analyzer-readback.md
    title: The authenticated analyzer readback and its manual trigger rule
  - id: l1-0086
    resource: ./0086-implement-useful-l1-as-protected-source-github-current-state-reconciler.md
    title: The same two triggers on Gnostoa verification, with events as wake-ups only
  - id: claude-relay-0096
    resource: ./0096-relay-mention-reviews-through-a-protected-workflow.md
    title: The workflow_run guard on the default branch, the event and the path
  - id: credentials-boundary
    resource: https://github.com/ktogias/gnostoa/issues/15#issuecomment-5979363503
    title: The owner's agent credentials boundary of 2026-10-04
x-project-knowledge:
  id: kit.decision.0107.run-the-analyzer-readback-for-every-pull-request-head
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governed-by
      target: /decisions/0091-add-authenticated-provider-neutral-analyzer-readback.md
    - kind: references
      target: /decisions/0086-implement-useful-l1-as-protected-source-github-current-state-reconciler.md
    - kind: references
      target: /decisions/0096-relay-mention-reviews-through-a-protected-workflow.md
---

# Run the analyzer readback for every Pull Request head, and again on request

## Context

Decision 0091 made the authenticated analyzer readback a `workflow_dispatch`-only
workflow. Agents dispatched it with the host's former token, for each candidate
head, as one step of review convergence.

On 2026-10-04 the host moved to the agents' restricted token, which holds Actions
read only. Dispatching then failed with `HTTP 403: Resource not accessible by
personal access token`. Measured with `gh run list`:
- the last readback ran on 2026-10-04 at 01:37Z (run `37168585015`);
- none ran in the three days after.

Convergence claims omitted the readback in that time, and #379 merged without it.
The owner's direction on 2026-10-07: it must happen automatically, and the agent
must be able to get the information it needs.

## Decision

The readback workflow keeps one job, in the `analyzer-readback` environment, which
admits only `main`. That job now starts in three ways:

1. **Automatically**, on `workflow_run` when `Gnostoa verification` completes.
   `workflow_run` matches a workflow by name, so a same-named workflow on any branch
   could start it (Decision 0096, rule 7). The job therefore runs only when all of
   these hold:
   - the ref is `refs/heads/main`;
   - the triggering run's event is `pull_request`;
   - the triggering run's path is `.github/workflows/verification.yml`.

   It reads the run's `head_sha`, and its `pull_requests` when that list holds
   exactly one Pull Request. A fork's run has none, and a head shared by two Pull
   Requests is ambiguous. Either run fails, visibly, since it can produce no
   exact-head receipt: a green run without one would make missing evidence look
   like a clean producer (#389). For a `pull_request` run, `head_sha` is
   the Pull Request's own head, not its merge ref: measured on 2026-10-07, each of
   #384's and #369's last three verification runs carried exactly that round's
   head.
2. **On request**, on `repository_dispatch` of type `gnostoa-analyzer-readback`,
   whose payload names `pull_number` and `head`. An agent sends it with the token it
   already holds: `POST /repos/{owner}/{repo}/dispatches` needs Contents write,
   which that token has. No permission of the agents' token changes.
3. **By hand**, on `workflow_dispatch`, as before.

**Event fields are identifiers only**, as Decision 0086 treats its events:
- A secret-free step, `ci/analyzer_readback_subject.py`, reads them from its
  environment. It validates a positive decimal Pull Request number and an exact
  40-character lowercase head before it writes any step output. So no field can add
  an output of its own, and no field reaches a shell.
- The runner is unchanged. It re-reads the Pull Request before and after
  acquisition, and refuses a head that does not match or that moves (Decision 0091,
  §8). That re-read is the subject's trust boundary.
- The analyzer credentials still reach only the acquisition step.
- **Each admitted event is named** in the job's condition, so a trigger added
  later is not admitted by default.
- **The checkout names no ref.** It takes its event's own revision, `main`'s
  `github.sha`, which the binding step verifies (Decision 0096, rule 11). Naming a
  ref is what checking out a fork's code would need.

**The artifact** is named `gnostoa-analyzer-readback-<pull>-<head>`, from the
validated subject, so an agent finds the result for an exact head.

**It stays outside candidate CI.** It is its own workflow, not a step or a required
check of Gnostoa verification. That keeps Decision 0091's reason for a dedicated
surface: analyzer availability must not become a candidate correctness gate.

**One parser, and one SHA check.** `workflow_run.pull_requests` is parsed by
`tools/github_events.workflow_run_pull_numbers`. The useful-L1 reconciler's own
parser is factored into it, so both read the field the same way. An exact head is
checked by `tools/github_events.exact_sha`, which the resolver and the runner
share; the runner's own pattern is gone.

**Runs queue.** The workflow's runs share one concurrency group, with nothing
cancelled, so a flood of requests waits rather than spending the analyzers' rate
limits, as `review-current-state.yml`'s runs do.

## Alternatives not chosen

- **Giving the agents' token Actions write**, so it could dispatch as before:
  Actions write also covers approving pending deployments, which the credentials
  boundary withholds from agents on purpose.
- **Adding the readback to Gnostoa verification**: Decision 0091 rejects analyzer
  secrets in candidate CI.
- **`pull_request_target`**: Decision 0086 refuses it for credential-bearing jobs.
  It is also unneeded, since the readback runs no candidate code.
- **Waiting in the job for a running analysis**: out of scope for #387. A
  `repository_dispatch` rerun takes a later snapshot instead.

## Consequences

- **Each completed verification of a Pull Request starts one readback.** A
  readback that starts while DeepSource or Codacy is still analysing records it,
  `READBACK_UNAVAILABLE` with coverage `PARTIAL`, and an agent can ask for a later
  snapshot.
- **How an agent uses it:**
  - To find a result:
    `gh run list --repo ktogias/gnostoa --workflow analyzer-readback.yml`, then
    `gh run download <run> --name gnostoa-analyzer-readback-<pull>-<head>`.
  - To ask for a new snapshot:
    `gh api -X POST repos/ktogias/gnostoa/dispatches -f event_type=gnostoa-analyzer-readback -F client_payload[pull_number]=<pull> -f client_payload[head]=<head>`.
- **A `workflow_run` run attaches no check to the Pull Request** (Decision 0096).
  The result is the artifact, not a check.
- **`workflow_run` and `repository_dispatch` run only the workflow file on `main`.**
  So the new triggers can be exercised only after this change is integrated.

## Verification

- **Tests that failed first on `main`:**
  - the workflow's triggers, its guard, the order of its steps, and that no event
    field reaches any step but the resolver;
  - the resolver for each trigger, its refusals and its outputs;
  - the shared parser.
- **The token's capability, measured on 2026-10-07.** A `repository_dispatch` of an
  unhandled type returned `204 No Content` and started no workflow.
- **After integration.** Merged code is not yet a working producer, because the
  new triggers run only from `main`. The readback becomes operational, as #389
  asks, only once each of these has been shown, in order:
  1. the source is integrated;
  2. an automatic run is observed for a Pull Request head, and its artifact is
     read back for that exact head;
  3. a `repository_dispatch` rerun is observed, and its artifact is read back for
     that exact head.
