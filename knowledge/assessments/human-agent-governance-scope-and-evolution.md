---
type: Source
title: Human-agent governance scope and evolution assessment
description: Bounded extraction of useful Gnostoa scope and roadmap findings from one external shared conversation.
status: draft
generated:
  by: codex/gpt-5
  at: "2026-08-16T00:00:00Z"
sources:
  - id: shared-conversation
    resource: urn:gnostoa:source:owner-supplied-shared-conversation:2026-08-16
    title: Owner-supplied shared conversation (live URL withheld from the public record)
x-project-knowledge:
  id: kit.assessment.human-agent-governance-scope-and-evolution
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: references
      target: /decisions/0016-evolve-human-agent-workflow-through-bounded-self-hosted-slices.md
    - kind: references
      target: /failure-modes/reverse-centaur-review-overload.md
---

# Human-agent governance scope and evolution assessment

## Resume card

| Field | Current result |
|---|---|
| Scope verdict | Gnostoa is a Git-native epistemic and normative control substrate for project work. It is not a frontier-alignment system, a general agent orchestrator or a news-analysis product. |
| Strongest finding | Human participation is not meaningful control unless the person can understand, pause, reject or correct the bounded semantic effect. |
| Product consequence | Add a declared human-attention and review-surface budget to the B2 task loop and fail closed when understanding is missing. |
| Architecture boundary | Portable state, policy and receipts belong in the core; concrete effect mediation and enforcement belong in runtime or provider adapters. |
| Next action | Dogfood the task envelope and current projection in Issue #24 before promoting the hypothesis into stable policy. |

## Source and method

The owner-supplied shared conversation was inspected as a source on
2026-08-16. Its live unlisted URL is deliberately withheld from this public
record to avoid broadening discovery of unrelated conversation material. A
local HTML capture used for extraction had SHA-256
`70df347d3b7ea22cea84f47c7dfcf0e98df1fc2d357b5b659dd91076374825ad`.
The temporary capture is not retained in the repository; its digest is capture
evidence, not a promise that the source can be reconstructed from Gnostoa.
Only claims relevant to Gnostoa's scope and evolution were extracted. This
record is a compact assessment, not an import of the transcript.

## Useful findings

1. **Meaningful human control exceeds human-in-the-loop ceremony.** A visible
   approval button or owner identity does not establish control when the
   reviewer cannot state the exact choice, consequences and uncertainty.
2. **Attention is a constrained system resource.** Review surface, active owner
   time and comprehension should be budgeted and measured alongside latency,
   tokens and test coverage. Exceeding that budget requires clarification,
   splitting or a blocker rather than a rubber-stamp.
3. **B1 exposed a reverse-centaur failure.** Agents accumulated and framed most
   of the meaning while the human review surface grew faster than the semantic
   delta. The process preserved evidence but risked transferring comprehension
   away from the accountable owner.
4. **Documents do not enforce effects.** Portable schemas, policy and receipts
   are useful core contracts, but the adapter performing a repository or other
   external effect must mediate and verify that effect. Gnostoa must not claim
   enforcement merely because a Markdown rule exists.
5. **Later research remains bounded.** Contested claims and counterevidence,
   values and red lines, role/capability separation and external-effect gates
   remain useful routes for Issues #11, #14, #10, #9 and #5–#8. They are not
   prerequisites for B2's first executable slice.

## Exclusions and non-claims

The conversation's hardware, China, market and news material is outside
Gnostoa's core scope. Time-sensitive claims, numerical scores and unverified
assertions are not recorded here as canonical project truth. If later useful,
they require dated Source records with their own provenance and review.

The shared conversation is neither owner approval nor independent empirical
evidence. The findings are agent-authored hypotheses to test through B2 and a
later independently owned transfer pilot. Raw transcript text and hidden
reasoning are deliberately excluded to reduce disclosure and context cost.

## Routing and authority boundary

Issue #24 tests a validated task envelope, one current projection, explicit
handoff, stale-state detection and interruption recovery. It records owner
review time, approval prompts per genuine semantic choice, evidence
amplification and comprehension failures. A later Decision may promote proven
rules into stable policy. Until then, this assessment changes no approval,
provider-effect, implementation or publication authority.
