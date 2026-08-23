---
type: Source
title: B3 independent-adoption experiment design
description: Pre-registered Gnostoa-self methodology for one observational transfer experiment in a real independently owned project.
status: draft
generated:
  by: codex/gpt-5
  at: "2026-08-23T20:58:57Z"
sources:
  - id: b3-independent-adoption-design-work-item
    resource: https://github.com/ktogias/gnostoa/issues/107
    title: Pre-register the first real B3 independent-adoption experiment
x-project-knowledge:
  id: kit.assessment.b3-independent-adoption-experiment-design
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governed-by
      target: /decisions/0016-evolve-human-agent-workflow-through-bounded-self-hosted-slices.md
    - kind: references
      target: /decisions/0042-accept-the-weather-note-cold-start-onboarding-result.md
    - kind: references
      target: /assessments/weather-note-cold-start-onboarding-result.md
    - kind: references
      target: /assessments/weather-note-evaluation-root-cause-retrospective.md
    - kind: references
      target: /lifecycles/evidence-gated-capability-evolution.md
    - kind: references
      target: /runbooks/deliver-bounded-self-hosted-slice.md
    - kind: references
      target: /decisions/0036-canonicalize-bounded-self-hosted-delivery-practice.md
---

# B3 independent-adoption experiment design

## Status, purpose and authority

This record pre-registers the methodology for the first real B3 transfer
experiment before a project, owner, task or result is selected. The experiment
is observational: it asks whether Gnostoa can transfer into one independently
owned project and support one real bounded task with technically valid
adoption, semantic fidelity, explicit unknowns, human-owner acceptance,
bounded cost and artifact-bound evidence. It is not a causal A/B productivity
experiment.

This is Gnostoa-self experiment design, not adopter guidance, a generic
evaluation framework, a runbook, an evidence mechanism, or evidence that B3
has begun. The authority split is:

- [Decision 0016](../decisions/0016-evolve-human-agent-workflow-through-bounded-self-hosted-slices.md)
  owns external-transfer B3;
- the [weather-note result](weather-note-cold-start-onboarding-result.md) owns
  exact synthetic evidence and dispositions;
- the [weather-note retrospective](weather-note-evaluation-root-cause-retrospective.md)
  owns their bounded causal synthesis;
- this record owns only the pre-registered B3 methodology;
- a later candidate-specific contract must bind the exact project, task,
  owner, subjects and permissions; and
- [Decision 0036](../decisions/0036-canonicalize-bounded-self-hosted-delivery-practice.md)
  retains its separate Gnostoa-self fresh-agent validation.

## Research questions

The experiment must answer these questions independently:

1. Can a genuinely fresh agent understand Gnostoa from its public surface?
2. Can it select and execute the smallest appropriate adoption route without
   Gnostoa-maintainer intervention?
3. Can it model real project knowledge without importing Gnostoa self-knowledge
   or inventing facts?
4. Can it distinguish repository-visible facts, prompt-provided facts,
   owner-only knowledge and genuinely unresolved questions?
5. Can it produce bounded context sufficient for one real task?
6. Does the human project owner accept the knowledge, context and task result?
7. Is the observed value proportionate to setup, intervention, review and
   maintenance cost?

The result cannot establish general productivity improvement, product-market
fit or universal adoptability.

## Candidate eligibility

The future candidate must have all of the following:

- a pre-existing real project with ownership independent from Gnostoa;
- a real human owner with semantic authority and no prior Gnostoa adoption;
- one real upcoming task that is bounded, non-trivial, reversible and
  non-critical;
- objective verification or meaningful owner review;
- safe and reversible mutation authority; and
- no requirement for production credentials or unsafe provider effects.

A newly created project qualifies only when it was independently planned for
real continued use and was not manufactured for B3. No duration threshold is
fixed before the candidate is known.

## Frozen ground-truth contract

Before execution, the human owner must approve one small matrix containing each
material fact or constraint, its severity, its evidence class and the expected
agent behaviour:

| Evidence class | Expected behaviour |
|---|---|
| Repository-visible | discover |
| Supplied in the task prompt | preserve |
| Owner-only knowledge | ask when necessary |
| Genuinely unresolved | leave unresolved |

The matrix is evaluation authority. It is frozen before the fresh-agent run
and must not be rewritten afterward to fit the result. Owner-only answers need
not be disclosed to the agent before they become necessary.

## Subject binding

The candidate-specific contract must bind separately:

- target-project repository commit and tree;
- exact Gnostoa documentation subject used for orientation;
- exact immutable Gnostoa execution subject;
- exact experiment prompt; and
- environment and tool identities.

Those future identities are deliberately not predicted here. Admission must
bind the then-selected documentation revision and release/runtime identity and
must not confuse current-main guidance with historical release documentation.

## Execution phases

The admitted experiment runs once through this sequence:

1. Confirm candidate and owner eligibility.
2. Freeze the ground-truth matrix and real task contract.
3. Confirm fresh-agent eligibility.
4. Run the fail-closed environment preflight.
5. Perform public orientation and the smallest justified adoption.
6. Validate adopter knowledge and generate bounded context.
7. Stop for the human-owner checkpoint before application implementation.
8. Optionally implement the real task only after owner acceptance and explicit
   continuation authority.
9. Obtain the final owner evaluation.
10. Reconcile the admitted experiment once.

The series is batched under one admission and one reconciliation. Individual
observations or evaluators do not receive separate canonicalization slices.

## Fresh-agent and preflight contracts

The executing agent receives no prior Gnostoa conversation, weather-note
evidence, retrospective or giant historical prompt. It receives the public
Gnostoa starting page, target repository, real task-specific delta, explicit
mutation authority and stop conditions, and the required evidence checklist.
The prompt must not reproduce the full Gnostoa workflow, commands or expected
interface: public discoverability is part of the observation.

Before authoring adopter knowledge, the agent must establish:

- accessible target source and its exact identity;
- accessible Gnostoa documentation source;
- one available, real supported execution route;
- a clean, writable experiment workspace;
- the ability to capture timestamps, exit codes and hashes; and
- exact permissions and the mutation boundary.

If any material prerequisite is missing or ambiguous, the experiment result is
`BLOCKED`: preserve bounded evidence and stop. Manual simulation, invented
output or a plausible narrative is never technical evidence.

## Minimal adoption and owner checkpoint

The agent selects the smallest justified adoption route, retains only
project-owned knowledge, excludes Gnostoa self-knowledge, keeps unverified
concepts draft and represents unknown ownership honestly. It validates the
bundle, generates deterministic bounded context, and identifies omissions,
unknowns and the correct stop point.

No application implementation occurs until the human owner reviews canonical
adopter knowledge, generated context, omissions and possible inventions,
clarification questions and the readiness classification. The owner records
one disposition—`ACCEPT`, `CORRECT` or `REJECT`—and every material intervention
or correction.

After `ACCEPT`, or after an accepted correction and explicit continuation, the
agent may implement the task within the admitted mutation boundary. Record the
acceptance-test and regression results, scope drift, incorrect assumptions,
clarification rounds, review corrections and final owner acceptance. Gnostoa
friction or defects are observations for later owner disposition; they are not
remediated during measurement.

## Measurement contract

Timing boundaries are declared in the candidate contract before execution and
remain stable through the admitted experiment. Any owner estimate of ordinary
handoff effort is a self-reported baseline only and cannot support a causal
improvement claim.

| Dimension | Required observations |
|---|---|
| Environment eligibility | Exact source/runtime access, supported route availability, and any block reason |
| Public orientation | Time to correct identity/interface, public pages used, stale or imagined interfaces attempted, maintainer interventions |
| Adoption mechanics | Time to first valid bundle, files/lines introduced, validation/context attempts and failures, offline execution where applicable, self-knowledge contamination |
| Semantic fidelity | Material ground-truth items represented, omissions, distortions, inventions, correctly surfaced unknowns and escalated owner-only facts, with severity |
| Context quality | Material constraints, bounded size, authority disclaimers, deterministic regeneration, correct next action and stop point |
| Human effort | Clarifications, correction rounds, owner time, review time and agent rework time |
| Task result | Objective verification, regressions, scope discipline and owner acceptance |
| Adoption value | Owner assessment of understanding, repeated explanation, surfaced or missed constraints, handoff usefulness, review burden, maintenance cost and durable-adoption disposition |

## Minimal evidence contract

Retain bounded, artifact-linked evidence for:

- the experiment contract and exact prompt;
- source, documentation, runtime, environment and tool identities;
- substantive commands with working directory, timestamp and exit code;
- generated adopter knowledge and bounded context;
- initial and final Git state and diff;
- verification results and a SHA-256 manifest for retained artifacts;
- material owner questions, answers and corrections; and
- the final owner scorecard.

Do not retain private chain of thought, complete reasoning transcripts,
irrelevant shell history, credentials, secrets or mutable provider data without
material relevance. This checklist is experiment-specific; it creates no
generic receipt infrastructure or schema.

## Independent result dimensions

The final result reports every dimension separately and does not collapse them
into one overall pass:

| Dimension | Allowed result |
|---|---|
| Environment eligibility | `PASS` / `BLOCKED` |
| Public orientation | `PASS` / `PARTIAL` / `FAIL` |
| Technical execution | `PASS` / `PARTIAL` / `FAIL` / `NOT RUN` |
| Semantic fidelity | `PASS` / `PARTIAL` / `FAIL` |
| Owner acceptance | `ACCEPT` / `CORRECT` / `REJECT` |
| Measured utility | `POSITIVE` / `MIXED` / `NEGATIVE` / `UNKNOWN` |
| Durable adoption | `YES` / `NO` / `DEFERRED` |

## Rejected claims and stop point

This pre-registration rejects population-level reliability rates, general
productivity or cost-reduction claims, product-market-fit claims, vendor or
model rankings, manufactured synthetic projects, hidden remediation during
measurement, automatic permanent adoption, and adopter-facing guidance before
B3 evidence. It selects no generator, DSL, command alias, mutable image tag,
generic evidence infrastructure or new workflow mechanism. A controlled
comparison may be considered only after successful real transfer evidence.

B3 has not begun, and Decision 0036 remains unsatisfied and independently
scoped. The next owner subject is candidate selection: one target project,
human owner, real task, permissions and mutation boundary, and review
availability. Only after that selection may one candidate-specific contract be
admitted and frozen before execution.
