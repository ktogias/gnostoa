---
type: Decision
title: Adopt the observed source-only release procedure for Gnostoa self-governance
description: Adopt the release lifecycle demonstrated by v0.1.0 as the default draft Gnostoa-self procedure for future source-only releases, without promoting it to adopter guidance or selecting any mechanism.
status: draft
generated:
  by: human:ktogias
  at: "2026-08-19T11:00:00Z"
sources:
  - id: canonicalization-work-item
    resource: https://github.com/ktogias/gnostoa/issues/48
    title: Canonicalize the observed source-only release lifecycle
  - id: release-identity-work-item
    resource: https://github.com/ktogias/gnostoa/issues/43
    title: Establish the first immutable source-only release identity
x-project-knowledge:
  id: kit.decision.0021.adopt-the-observed-source-only-release-procedure-for-gnostoa-self-governance
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: references
      target: /decisions/0020-establish-v0-1-0-as-the-first-source-only-pre-stable-release-identity.md
    - kind: governs
      target: /runbooks/publish-source-only-release.md
    - kind: derived-from
      target: /assessments/first-source-only-release-result.md
    - kind: references
      target: /lifecycles/evidence-gated-capability-evolution.md
---

# Adopt the observed source-only release procedure for Gnostoa self-governance

Recorded by `agent:claude-opus-5` from the accountable maintainer's disposition.
The semantic choice is the maintainer's; this record is faithful transcription.

## Context

Gnostoa completed one real source-only release: semantic selection, preparation,
exact-candidate binding, verification, owner authorization, an annotated tag, a
GitHub Release created against that existing tag, authoritative provider
read-back, and repository reconciliation.

That lifecycle produced findings a future actor would otherwise rediscover
expensively: an immutable snapshot must not freeze provider-volatile claims; one
authorized action can carry effectful content through more than one provider
parsing surface; and a provider run concluding `success` is not proof that every
relevant check executed.

Those facts are durable, but the **procedure** is not. Reconstructing it requires
replaying one Work Item and four Change Requests — the reconstruction burden
Decision 0018 already identified as a dogfooding failure for this project.

This Decision does not change what `v0.1.0` means. Decision 0020 remains
authoritative for that release.

## Decision

**A.** Scope is **Gnostoa-self only**.

**B.** Scope is **source-only releases only**.

**C.** The procedure rests on **one** completed real release lifecycle and
remains **`draft`**.

**D.** It is an **operating default**, not a claim of stable or universally
sufficient process.

**E.** It is **not** promoted to generic or adopter guidance.

**F.** Package, OCI-image and documentation-site publication remain **distinct
effects** requiring their own selection, evidence and admission.

**G.** Release semantic selection and repository preparation do **not** authorize
the external provider effect.

**H.** Repository preparation classification and outward provider-effect
classification remain **separate**; decomposition cannot reduce the latter's
impact.

**I.** Exact release-candidate binding occurs only after **all** admitted
pre-effect preparation has integrated.

**J.** Immutable source snapshots must not contain provider-volatile
current-state assertions whose truth flips solely because the authorized release
effect occurs.

**K.** Provider-volatile state remains **provider-authoritative**.

**L.** Each provider mutation is executed **one bounded effect at a time**, with
authoritative read-back before dependent later effects.

**M.** For provider operations the actor considers a **declared, known bounded
effect envelope**: the intended operation, known provider transformations or
derived representations, known parsing and automation surfaces, anticipated
coupled effects, and the required read-back observations.

**N.** This Decision does **not** claim the complete provider effect surface is
knowable in advance.

**O.** Inaccessible or unknown provider surfaces remain explicitly **UNKNOWN**.
Lack of observation is not evidence of absence.

**P.** Expected coupled effects are recorded **without** being promoted to
additional acceptance evidence.

**Q.** Unexpected coupled mutations require authoritative read-back and
reconciliation **before** the next dependent write or retry.

**R.** Provider run or workflow conclusion and actual check execution are
**distinct observations**.

**S.** **No** generic provider-effect mediator, provider adapter, linter,
workflow engine, observation-binding mechanism or routing/enforcement mechanism
is selected by this Decision.

**T.** Revisit after the **next** completed source-only release, or earlier if
provider semantics materially change.

## Consequences

- One concise runbook carries the procedure; this Decision records only the
  durable choice and does not restate it.
- A future release can follow a discoverable route instead of replaying Work Item
  #43 and Change Requests #44 through #47.
- Adopting projects gain nothing here, by design. The procedure has been
  exercised against one provider, one release kind and one project.
- The procedure is expected to be **wrong in places**. It is `draft`, and the
  revisit condition exists so a second release can contradict it with evidence.
- One successful release does not make this procedure permanently stable, and
  nothing here authorizes a further release or artifact publication.

## Revisit condition

Revisit after the next completed Gnostoa source-only release, or earlier if:
GitHub tag semantics change; GitHub Release semantics change; squash or merge
parsing semantics materially change; provider automation changes; source-only
release packaging or distribution scope changes; or repeated evidence
contradicts or makes part of this procedure unnecessary.
