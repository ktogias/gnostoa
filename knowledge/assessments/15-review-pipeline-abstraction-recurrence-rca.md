---
type: Source
title: Issue 15 review-pipeline abstraction recurrence retrospective and root-cause analysis
description: Source-bound analysis of why the Claude mention-review pipeline was built GitHub- and Claude-coupled after the provider-abstraction retrospective and the architecture-inheritance gate, why the earlier prevention did not activate, and the bounded actions that make the gate effective.
status: draft
generated:
  by: anthropic/claude-opus-5-5
  at: "2026-10-02T21:20:00Z"
sources:
  - id: owner-request
    resource: https://github.com/ktogias/gnostoa/pull/353
    title: Owner request on 2026-10-02 to make the pipeline core provider- and agent-agnostic, then to analyse why it recurred
  - id: first-rca
    resource: ./15-provider-abstraction-retrospective.md
    title: Issue 15 provider-abstraction retrospective and root-cause analysis (2026-09-19)
  - id: inheritance-checkpoint
    resource: https://github.com/ktogias/gnostoa/issues/14#issuecomment-5919281149
    title: Ariadne v9 cross-cutting addendum, architecture inheritance checkpoint (2026-09-30)
  - id: inheritance-gate
    resource: https://github.com/ktogias/gnostoa/issues/15#issuecomment-5919462524
    title: Mandatory implementation entrance gate, architecture inheritance (2026-09-30)
  - id: ma0-guard
    resource: https://github.com/ktogias/gnostoa/issues/14#issuecomment-5919463947
    title: MA0 exit includes source activation of architecture inheritance
  - id: architecture-audit
    resource: https://github.com/ktogias/gnostoa/issues/15#issuecomment-5919264097
    title: Full architecture audit and stage-by-stage lineage map
  - id: worker-exchange
    resource: https://github.com/ktogias/gnostoa/issues/325
    title: Separate orchestration from implementation with a GitHub-native worker exchange
  - id: context-work-item
    resource: https://github.com/ktogias/gnostoa/issues/326
    title: Bound Claude review context (owning objective #15)
  - id: subject-pattern
    resource: ../decisions/0086-implement-useful-l1-as-protected-source-github-current-state-reconciler.md
    title: Provider-neutral core plus provider adapters
x-project-knowledge:
  id: kit.assessment.15-review-pipeline-abstraction-recurrence-rca
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: references
      target: /assessments/15-provider-abstraction-retrospective.md
    - kind: references
      target: /decisions/0086-implement-useful-l1-as-protected-source-github-current-state-reconciler.md
    - kind: references
      target: /requirements/bounded-behavioral-traceability.md
    - kind: references
      target: /requirements/retrospective-findings-require-explicit-admission.md
---

# Issue 15 review-pipeline abstraction recurrence retrospective and root-cause analysis

## Purpose, provenance and claim boundary

On 2026-10-02 the owner asked the agent to make the review pipeline's core provider-
and agent-agnostic. The owner then asked why this had been forgotten **again**, and
asked for the incident, its root cause and its prevention to be recorded in the
Ariadne thread and wherever else needed. This is the agent's retrospective. It is not
human semantic approval, an independent experiment or merge authority.

The agent that wrote this record is the agent that built most of the pipeline. The
record therefore separates three things. **Observations** are backed by commits,
provider records and the session transcript's tool calls. **Inferences** are marked as
such. **Counterfactuals** are not presented as facts. No private reasoning is claimed.

Observed at protected `main` `b011edeb70e4d8e5757e2d58f493de06ee642dd5` and PR #353 head
`03d7d5cb873fb05b0571ec87e63d98561f6d9137`, on 2026-10-02 around 21:20Z. PR #319 was open.

## Executive finding

**The failure is the same one the first retrospective found. Its prevention existed
only as provider comments and conditional routing, and none of it reached the point of
mutation.**

The architecture-inheritance gate was a mandatory, fail-closed entrance gate before
the first semantic production mutation. The owner posted it on #15 on 2026-09-30.
Its source activation (`AGENTS.md`/runbook routing, guardrail and conformance tests)
was scheduled as part of MA0, behind VF0/PR #319, which is still open. The agent's
orientation route reads source and pointed-to comments. It never scanned #14 or #15
for new entries. The gate therefore first reached the agent's context on 2026-10-02 at
21:13Z, after the owner's prompt. Meanwhile #340 (opened 2026-10-01) and #353 (opened
2026-10-02) proceeded without the lineage table the gate required.

## 1. What happened

### The lineage

| Item | Date | Role |
|---|---|---|
| #326 (owning objective #15) | opened 2026-09-27 | Bound Claude review context. Decisions 0093 and 0094. |
| PR #329, PR #330 | opened 2026-09-28, merged 2026-10-02 | Bounded context collection and publication. |
| #339, PR #340 | opened 2026-10-01, merged 2026-10-02 | Relay through a protected workflow revision. Decision 0096. |
| #342 | 2026-10-01 | Credential scoped to an environment. Decision 0097. |
| #348, #352, PR #353 | opened 2026-10-02, open | Comment delivery and a reviewer without a write token. Decision 0098. |

On `main` this lineage holds about 4,150 lines:
- `admit_mention.py`: 716 lines;
- `build_review_context.py`: 2,030 lines;
- `chunk_diff.py`: 401 lines;
- `publish_report.py`: 255 lines;
- `review_context_paths.py`: 51 lines;
- `claude.yml`: 595 lines, including an inline shell context step of about 320 lines;
- `claude-mention-trigger.yml`: 103 lines.

All of it sits under `.github/`.

### Direct evidence of coupling

- **Provider in the decision logic.** Admission's rules are written against GitHub
  event kinds, `author_association` values, `workflow_run` trigger facts and GitHub
  REST paths. The context collector, and the inline shell, call
  `repos/{repo}/compare/...` and the contents API with GitHub media types and GitHub
  pagination semantics. The poster validates `https://github.com/.../actions/runs/N` and
  matches `github-actions[bot]`.
- **Agent in the report logic.** The publisher parses the Claude Code action's
  execution envelope directly (`type: result`, `subtype`, `is_error`, assistant turns).
- **No neutral core and no seam.** None of the pipeline uses Decision 0086's normalized
  subject vocabulary (provider identity, repository, `change_request` kind and id,
  exact commits). None of it uses an adapter protocol. A second provider or a second
  agent would have to change the shared logic or duplicate it.
- **Planned owners not consulted.** The owner's audit (5919264097) and #325 assign:
  - agent dispatch to the #325 W0 worker contract, with "direct Claude adapter" and
    "direct Codex adapter" beneath it;
  - staged reviewer dispatch to #297.

  The pipeline was built without a disposition against either.

### Review did not catch it

The four PRs carried 319 review threads and 641 reviews, from Codex, CodeAnt, CodeRabbit,
gitar, Sourcery, Codacy, DeepSource, SonarCloud and the owner's account. A search of
every review comment, review body and PR comment for provider-neutral, agnostic,
abstraction, adapter-boundary or second-provider wording found **none**. The reviewers
found many real defects, all at the level of the diff.

## 2. Why it recurred: root-cause analysis

### Direct cause

There was no lineage disposition for each material responsibility before production
mutation. Admission, context collection, agent-report extraction, publication and
delivery were each implemented as new GitHub- and Claude-shaped code. None was recorded
as consuming, extending or adapting an existing owner.

### Systemic causes

1. **The gate was not in source.** The 2026-09-30 rule existed only on #14 and #15
   (observed: `AGENTS.md`, the delivery runbook, `tasks/issue-14-orientation.md` and
   `docs/roadmap.md` on `main` contain no reference to it). Its activation was
   sequenced into MA0, behind VF0/PR #319. That made a safety rule for *every* slice
   wait on unrelated work, while side lineages kept producing code. This is the same
   mechanism the first retrospective warned about: knowledge that is stored is not a
   constraint that is applied.
2. **The earlier prevention depended on self-recognition.**
   - The 2026-09-19 retrospective routed prevention through the
     `bounded-behavioral-traceability` Requirement. `AGENTS.md` invokes it only when
     the agent judges its applicability criteria hold.
   - Its other measures were proposals: an architecture perspective under #263 and an
     observational cohort. Neither was activated.

   A conditional, self-assessed trigger fails exactly when the agent has narrowed the
   task. Observed: the agent's first tool-call read of the Requirement in this session
   was at 2026-10-02T21:13Z.
3. **Orientation was targeted, not incremental.** The agent read the comments it was
   pointed to and wrote to the governing thread without reading entries posted since
   its last read. Observed: on 2026-10-01 at 09:25Z it posted a retrospective to #15,
   following comment 5918799611. The gate (5919462524) had been posted on #15 about
   40 minutes after 5918799611 and about 13 hours before that post. No call returned
   the gate until 2026-10-02.
4. **The work was framed as a vendor integration.** The lineage began as "Harden the
   Claude Code GitHub Actions workflows" (Decision 0093). It lives in `.github/` and
   in `claude.yml`. *Inference:* the name and the location made provider- and
   agent-specificity look like the natural shape, not a choice needing a disposition.
5. **The code grew by accretion with no re-evaluation trigger.** It grew through dozens
   of security-hardening rounds, each one local and each one correct. Nothing caused a
   step back when workflow glue had become a roughly 4,000-line pipeline core.
6. **Prior art was checked at the level of mechanism, not responsibility.** For PR #353
   the agent's prior-art checkpoint reused the `review-current-state.yml` publish
   pattern, which was correct. It never asked which existing owner holds this
   responsibility. Observed: the agent had read Decision 0091 in seven tool calls since
   2026-09-24, and Decision 0086 twice, in analyzer-readback work. The neutral-core
   pattern was known and was not carried across.
7. **The review cohort was scoped to the diff.** The first retrospective reported the
   same detection boundary. No reviewer perspective asks the architecture question:
   which shared files must a second provider or agent change?

### Causal chain

```text
first RCA (09-19): prevention = conditional routing + unactivated proposals
  -> owner makes the invariant explicit as a fail-closed gate (09-30)
  -> gate's source activation queued behind MA0 behind open PR #319
  -> agent orientation reads source + pointed comments, never scans #14/#15
  -> side lineage (#326 -> #340 -> #353) framed as a vendor integration under .github/
  -> local hardening rounds accrete a provider- and agent-coupled core
  -> diff-scoped reviewers find many defects, none architectural
  -> owner restates the invariant a second time (10-02)
```

The control that worked again was the owner's review before merge.

## 3. What would have happened without the prompt

*Counterfactual, not provable.* The agent had stated that it would ask for merge
approval once #353 converged. The most plausible trajectory was to converge #353 with
the coupled design and offer it for merge. The owner's separate merge decision would
still have stood. The defect had already reached `main` through #329, #330 and #340.

## 4. Consequences for extension

These are inferences, not measured outcomes:
- **A second provider or agent would need to change the shared logic.** A GitLab or
  Forgejo provider, or a Codex or local agent, would require changing or duplicating
  the admission rules, the context rules, the report extraction and the delivery rules.
- **The tests raise the cost of moving the code.** Many hardening tests assert the
  current structure, such as the text of the inline shell. That raises the cost and the
  regression risk of moving logic behind a seam.
- **Possible parallel implementations.** The pipeline may duplicate the responsibilities
  the audit assigns to #325 W0 (agent dispatch) and #297 (reviewer dispatch). It may
  also duplicate the comment client that the useful-L1 GitHub adapter already has.

No data loss, outage or public API commitment was established. The code is
implementation-private.

## 5. Prevention: bounded actions and their admission status

| # | Action | Owner | Status |
|---|---|---|---|
| P1 | Apply the gate to #353 before the refactor's first production mutation. Post an exact-base-bound lineage table on #353 (consume, extend, adapt, factor, supersede or new-residual, per responsibility, against Decision 0086, the useful-L1 GitHub adapter, #325 W0 and #297). Add neutrality falsifiers: a structural check that the core names no provider or agent; a test-only second provider and second agent driving the unchanged core; a replay showing the falsifier rejects the old coupling. | #353 | **Admitted.** The owner chose "inside #353, the whole pipeline" on 2026-10-02. |
| P2 | Activate the gate in source now, independently of VF0/PR #319: an `AGENTS.md` routing line, a runbook entrance step and a guardrail-owned conformance test. Bounded to routing, as the 09-30 guard asked: no new engine or registry. | #15 (MA0 marker) | **Proposed.** Needs owner admission, because it changes the MA0 sequencing. |
| P3 | Incremental orientation. Before the first semantic production mutation, and before writing to a governing thread, read every #14/#15 entry since the last recorded read, and record the last-read comment id. | Agent practice and memory | **Applied** to this agent's memory. Becomes enforceable through P2. |
| P4 | An architecture/extension perspective in commissioned reviews: "which shared files must a second provider or agent change, and why?" | #263 | **Evidence appended.** No activation claimed. |
| P5 | The distilled lesson, second instance: stored knowledge is not an applied constraint, and prevention that is not routed to the point of mutation decays into thread knowledge. | #259 | **Pointer appended.** |
| P6 | A re-evaluation trigger: a third hardening round on one file, or more than about 300 lines of decision logic under a provider directory, prompts a responsibility review. | Folded into P2 | **Proposed.** |

## 6. What would count as prevention working

Reuse the first retrospective's proposed cohort (§8) unchanged: the next three
applicable boundary-touching slices, selected on admission. For each, record:
- whether the lineage table existed before the first mutation;
- how many owner reminders of previously decided invariants were needed;
- which shared files changed only to add a provider or agent;
- any rework attributable to missed boundaries.

This incident is a data point for the second measure: one reminder, again. Missing
measurements stay UNKNOWN.

## 7. Limits of this record

The agent inspected:
- the session transcript's tool calls, to establish what reached its context and when;
- provider comments on #14, #15, #325 and #326;
- the comments, reviews and threads of PRs #329, #330, #340 and #353;
- `main`'s routing files.

It did not read every historical comment on #14 or #15, and it did not replay the
pipeline's tests. Statements about what the agent "never read" are bounded to tool
calls recorded in this session. The author is not an independent reviewer of its own
causal conclusions. Owner direction to record this is not owner endorsement of its
analysis.
