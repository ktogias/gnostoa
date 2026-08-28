---
type: Decision
title: Use staged evidence maturity for early adoption trials
description: Prioritize owner-led trials in real projects during Gnostoa's early development, treat upstream feedback as additive rather than blocking, and reserve fully independent adoption experiments for later maturity.
status: draft
generated:
  by: codex/gpt-5
  at: "2026-08-28T10:28:59+03:00"
sources:
  - id: v0-2-0-release-work-item
    resource: https://github.com/ktogias/gnostoa/issues/146
    title: Publish Gnostoa v0.2.0 source and OCI release series
  - id: strict-b3-design
    resource: ../assessments/b3-independent-adoption-experiment-design.md
    title: B3 independent-adoption experiment design
  - id: govuk-alpha
    resource: https://www.gov.uk/service-manual/agile-delivery/how-the-alpha-phase-works
    title: How the alpha phase works
  - id: govuk-private-beta
    resource: https://www.gov.uk/service-manual/agile-delivery/how-the-beta-phase-works
    title: How the beta phase works
  - id: nist-ai-rmf-core
    resource: https://airc.nist.gov/airmf-resources/airmf/5-sec-core/
    title: NIST AI RMF Core
  - id: openai-contextual-evals
    resource: https://openai.com/index/evals-drive-next-chapter-of-ai/
    title: How evals drive the next chapter in AI for businesses
x-project-knowledge:
  id: kit.decision.0052.use-staged-evidence-maturity-for-early-adoption-trials
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governed-by
      target: /decisions/0016-evolve-human-agent-workflow-through-bounded-self-hosted-slices.md
    - kind: governed-by
      target: /decisions/0050-separate-adoption-observations-from-readiness-and-owner-disposition.md
    - kind: supersedes
      target: /decisions/0051-select-the-v0-2-0-source-and-oci-publication-series.md
      description: >-
        Partial supersession limited to section H, the B3-dependent sentence
        in section M, and the corresponding Work Item completion condition.
    - kind: references
      target: /assessments/b3-independent-adoption-experiment-design.md
    - kind: governs
      target: /assessments/nextcloud-mail-v0-2-0-owner-led-adoption-trial-baseline.md
---

# Use staged evidence maturity for early adoption trials

Recorded by `codex/gpt-5` from the accountable maintainer's disposition. The
product-stage choice, authority boundary and evidentiary classification are the
maintainer's; this record is faithful transcription.

## Context

Gnostoa is still in an early development phase, with limited publicity and a
small user population. The immediate product question is not yet whether an
unknown external team can adopt Gnostoa without maintainer contact. It is
whether Gnostoa creates enough practical value in real projects owned by, or
materially involving, the accountable maintainer to justify continued
investment and guide the next iteration.

The strict B3 pre-registration is useful for a later, stronger claim, but its
independent-owner requirement, full pre-approved ground-truth matrix and
separate auditor expectations impose disproportionate coordination cost on the
current learning stage. Treating those later-stage controls as present-day
entry gates blocks useful real-project evidence without reducing a material
present risk.

This decision follows a staged pattern: explore and test assumptions during an
early alpha-like phase, use limited real users and projects before wider
exposure, evaluate performance in the actual workflow, and iterate the
measurement as context and knowledge evolve. It preserves stronger external
validation for the point at which Gnostoa has more users, wider visibility and
claims that need independent support.

## Decision

### A. Distinguish evidence classes rather than one universal gate

Use four descriptive evidence classes. They are claim boundaries, not a rigid
process ladder:

1. `SELF-HOSTED`: Gnostoa is used to build or govern Gnostoa itself.
2. `OWNER-LED`: Gnostoa is used in a real project owned by, or materially
   involving, the accountable Gnostoa maintainer, who also supplies the initial
   semantic and evaluation authority.
3. `COLLABORATIVE`: another project participant or upstream actor contributes
   scoped feedback or review, without necessarily satisfying full independence.
4. `INDEPENDENT`: an external owner or reviewer who is independent of Gnostoa
   supplies the task authority and evaluation required for a strict adoption
   experiment.

An evidence stream may accumulate richer, separately labelled layers. Each
original result retains the evidence class under which it was produced. The
absence of a richer class does not invalidate a correctly labelled lower-class
result.

### B. Classify the current Nextcloud Mail experiment as owner-led

The v0.2.0 Nextcloud Mail trial is `OWNER-LED`, not a strict independent B3
experiment. `human:ktogias` is the accountable project-side authority for:

- selecting the initial real task;
- supplying or approving the lightweight semantic baseline;
- answering owner-only questions;
- accepting, correcting or rejecting the agent's intermediate understanding;
- assessing the task result and practical value; and
- deciding whether findings justify remediation, another trial or a product
  decision.

The trial may use a project in which the maintainer is involved even when the
upstream repository has separate final Change Request authority.

### C. Make upstream feedback additive, not blocking

No upstream response, assignment or review is required before the owner-led
trial begins or before its preliminary result, retrospective and follow-up
decisions are recorded.

When upstream or other project feedback later exists, record it with its author,
date, reviewed subject and scope. Add it as a new evidence layer or dated
addendum. It may confirm, qualify or overturn the initial owner assessment, but
must not silently rewrite the original chronology or pretend that the initial
trial was independent.

### D. Use a lightweight run contract

Before each owner-led run, bind only the information needed to make the run
safe, interpretable and repeatable enough for its purpose:

- exact released Gnostoa documentation and runtime subjects;
- exact target-project commit and tree;
- one real, bounded and reversible task;
- the exact prompt or a retained prompt artifact and digest;
- the local mutation and provider-effect boundary;
- concise owner acceptance criteria and known material constraints;
- the available objective checks or meaningful owner review;
- the agent/model/session identity and whether prior context exists; and
- practical stop conditions.

A separate independent reviewer, a complete pre-approved ground-truth matrix,
a dedicated read-only auditor and exhaustive host/tool inventory are not
mandatory for this evidence class. Record environment details only when they
are material to interpreting or reproducing the result.

### E. Preserve a reversible safety envelope

The default owner-led envelope is a disposable branch or worktree in an
owner-controlled fork, with no production credentials, deployment, package
publication or upstream mutation. A push, upstream Pull Request, Issue change or
other remote effect requires a separate explicit authorization under the target
project's own rules.

Stop on material subject drift, unsafe or irreversible scope, unavailable
required verification, need for protected credentials, or a task whose semantic
risk exceeds the owner's actual authority.

### F. Permit useful early-stage conclusions

An `OWNER-LED` result may support:

- a preliminary value and usability assessment;
- diagnosis of onboarding, documentation, workflow or tool friction;
- a retrospective based on observed actions and artifacts;
- remediation and product decisions;
- another experiment with changed conditions; and
- continued evolution of Gnostoa.

It does not establish independent adoption, upstream acceptance, population-
level reliability, universal usability, causal productivity gain or product-
market fit. Reports must say `owner-assessed`, identify the project relationship
and keep technical results separate from the owner's value judgement.

### G. Reserve strict independent adoption for later maturity

The existing independent B3 methodology remains available for a later stage,
when Gnostoa has wider use, more publicity or claims whose credibility requires
external task authority and richer feedback. At that point an independent owner
or reviewer, pre-registered semantic criteria and stronger contamination and
audit controls are proportionate.

The current owner-led trial does not weaken or satisfy that future methodology;
it produces a different and explicitly narrower evidence class.

### H. Decouple release completion from experiment execution

The v0.2.0 release series needs only the immutable release reconciliation and a
bounded owner-led trial baseline that identifies the released Gnostoa and target
project subjects. Task selection, execution, result assessment and any later
external feedback belong to subsequent experimental records. They are not
provider gates for the release lifecycle.

### I. Scope the staged-evidence policy and the partial supersession

This Decision establishes the general evidence-class policy for Gnostoa's
early-stage trials. It is not a temporary exception that expires with `v0.2.0`.
It remains the evidence-selection authority until a later explicit maturity
decision changes it.

Its `supersedes` relation to
[Decision 0051](0051-select-the-v0-2-0-source-and-oci-publication-series.md)
is deliberately partial because Decision 0051 also owns the immutable release
semantics. Decision 0052 supersedes only the parts of Decision 0051 that make a
strict `INDEPENDENT` B3 contract a prerequisite for completion of the v0.2.0
release Work Item:

- section H's strict B3 freeze requirement;
- the B3-dependent sentence in section M; and
- the corresponding final consequence and Work Item completion condition.

All source, tag, Release, OCI, provenance, verifier, reconciliation, effect and
non-claim rules in Decision 0051 remain authoritative. For Work Item 146,
integration and provider read-back of the bounded `OWNER-LED` baseline satisfy
the experiment-boundary requirement. Trial execution, result assessment,
retrospection and later `COLLABORATIVE` or `INDEPENDENT` evidence are separate
work and are not prerequisites for that release-series completion.

## Consequences

- The independent-human requirement no longer blocks the current Nextcloud Mail
  trial.
- The accountable maintainer can produce the initial assessment and act on its
  findings while preserving transparent claim limits.
- Upstream feedback improves the evidence when it arrives but its absence does
  not freeze product learning.
- The current contract becomes smaller and execution-focused rather than a
  surrogate external-governance process.
- Stronger independent adoption evidence remains a planned maturity step rather
  than being discarded.
- Earlier controlled Nextcloud Mail attempts retain their original artifacts
  and dispositions, but may also inform the owner-led evidence stream when
  clearly labelled as such.
- The general staged-evidence policy continues beyond the v0.2.0 release; only
  the targeted amendment of Decision 0051 is release-series-specific.
