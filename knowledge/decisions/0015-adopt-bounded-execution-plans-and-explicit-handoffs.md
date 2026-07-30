---
type: Decision
title: Adopt bounded execution plans and explicit handoffs
description: Preserve resumable change state in one small validated plan without turning agent transcripts or raw activity logs into project knowledge.
status: draft
generated:
  by: codex/gpt-5.6
  at: "2026-07-30T00:00:00Z"
sources:
  - id: durable-task-context-work-item
    resource: https://github.com/ktogias/gnostoa/issues/3
    title: Add durable task context and explicit agent handoffs
x-project-knowledge:
  id: kit.decision.0015.adopt-bounded-execution-plans-and-explicit-handoffs
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: references
      target: /decisions/0003-derived-retrieval-layers.md
    - kind: references
      target: /decisions/0014-strengthen-gnostoa-self-governance.md
    - kind: governs
      target: /requirements/prevent-policy-drift.md
    - kind: verified-by
      target: /runbooks/maintain-the-kit.md
---

# Adopt bounded execution plans and explicit handoffs

## Context

A Work Item preserves the problem and acceptance criteria, a Decision preserves
rationale, and a Change Request preserves review and integration evidence.
None of them is a reliable source for the current branch, completed work,
discoveries, exact next action or the state expected by a person or software
agent resuming unfinished work.

Unstructured chat history and agent logs are poor substitutes. They are
provider-specific, grow without bound, repeat durable knowledge, expose
irrelevant implementation detail and force every successor to reconstruct
state from a transcript. A second free-form task log would create another
source of truth and drift from the Work Item, Decision, repository and Change
Request.

The continuity mechanism must remain useful to different people and software
agents, work without a hosted knowledge service, and add no routine ceremony to
small mechanical changes.

## Decision

Add a provider-neutral Execution Plan contract for changes that need durable
continuity:

- keep one bounded, schema-valid plan per active change;
- link rather than duplicate the Work Item, Decisions and affected contracts;
- record scope, progress, discoveries, verification evidence and one explicit
  next action;
- reconcile the plan with the actual branch and worktree when work starts or
  resumes;
- require a clean, committed checkpoint before unfinished work is explicitly
  handed to another person or agent;
- project managed change context into a provider Change Request and verify that
  its candidate revision is current;
- record authorship and evaluation roles without treating an agent evaluation
  as a human approval;
- keep prompts, private reasoning, raw transcripts and exhaustive command logs
  noncanonical.

The public baseline requires an Execution Plan only when change complexity or
continuity makes it useful. A handoff checkpoint is required when unfinished
work is deliberately transferred. Gnostoa's self-policy specializes the
baseline by requiring a plan for normative and critical changes, while keeping
it conditional for normal changes and optional for mechanical changes.

The reusable workflow and template are public. Gnostoa's active plans,
provider configuration and internal Decision remain self-maintenance state and
are not inherited by adopting projects.

## Consequences

- A new developer or agent can resume from a bounded record plus repository
  evidence instead of replaying prior conversations.
- Work Item, Decision, plan and Change Request have distinct authorities,
  reducing duplicated prose and contradictory state.
- Handoffs become explicit and verifiable without requiring a second reviewer,
  a cooling-off period or owner attestation.
- Long-running and high-impact changes carry a small maintenance cost while
  simple local work remains lightweight.
- Hosted project-management and memory products may index or project the plan,
  but they do not become required canonical stores.
- This pre-publication change adds required continuity fields to the
  experimental change-control schema. Policies that inherit the core receive
  them through resolution; standalone copies must migrate by extending the
  core or adding the continuity block and per-class Execution Plan rule.
