---
type: Runbook
title: Publish a source-only release
description: Bounded Gnostoa-self procedure for naming an immutable source-only release identity and executing its provider effect with authoritative read-back.
status: draft
generated:
  by: agent:claude-opus-5
  at: "2026-08-19T11:05:00Z"
sources:
  - id: canonicalization-work-item
    resource: https://github.com/ktogias/gnostoa/issues/48
    title: Canonicalize the observed source-only release lifecycle
x-project-knowledge:
  id: kit.runbook.publish-source-only-release
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governed-by
      target: /decisions/0021-adopt-the-observed-source-only-release-procedure-for-gnostoa-self-governance.md
    - kind: references
      target: /decisions/0020-establish-v0-1-0-as-the-first-source-only-pre-stable-release-identity.md
    - kind: references
      target: /assessments/first-source-only-release-result.md
    - kind: references
      target: /runbooks/maintain-the-kit.md
---

# Publish a source-only release

**Scope: Gnostoa itself, source-only releases only.** Not adopter guidance. Draft,
based on one completed release; expect to correct it. Governed by
[Decision 0021](../decisions/0021-adopt-the-observed-source-only-release-procedure-for-gnostoa-self-governance.md).

A source-only release names an existing commit. It publishes **no** package, OCI
image or documentation site — each of those is a distinct effect needing its own
selection, evidence and admission.

Placeholders: `<TAG>`, `<AUTHORIZED_RELEASE_SHA>`, `<PUBLIC_SURFACE_DIGEST>`.

## Preconditions

- A release identity and its explicit non-claims are selected by an owner
  Decision, and that Decision is integrated.
- The release is source-only: no package, OCI image or documentation site is
  published by it.
- All admitted pre-effect preparation for the release Work Item has integrated.
- The exact protected-main candidate verifies under the applicable contract.
- The accountable owner has authorized the exact provider effect against the
  exact candidate.

## Three concepts to keep apart

| | |
|---|---|
| **Intended provider effect** | the external mutation explicitly authorized |
| **Expected coupled effect** | a known consequence of that operation that grants no additional authority |
| **Unexpected coupled mutation** | observed provider change outside the declared envelope, or with lifecycle consequences the authorization did not cover |

None of the three grants authority by itself.

## Procedure

### 1. Select release semantics

State the release identity, its kind, the intended claims, the explicit
**non-claims**, and any provider metadata whose meaning matters. **Selection is
not provider-effect authorization.**

### 2. Classify preparation and provider effect separately

Derive both classes independently from real proposed paths. **Do not lower the
outward release-effect class because the preparation diff is small.**

### 3. Record pre-effect state

Observe authoritative source and provider state before mutation, and record what
is observed, what is absent *within the observed scope*, what is inaccessible and
what is unknown. **Never equate "could not observe" with "does not exist."**

For non-executable provider facts use the evidence form current policy allows —
an unmet structural criterion plus planned human review. Do not create ceremonial
tests for prose or provider state.

### 4. Make release semantics durable before the effect

Integrate the governing release Decision and any other admitted pre-effect
knowledge first. Repository preparation does not itself authorize the effect.

### 5. Make the immutable snapshot temporally safe

Before binding the candidate, inspect the snapshot for current-state claims whose
truth would flip **solely because the planned effect occurs**. The rule is
semantic, not a string list:

> Provider-volatile facts that can change independently of the immutable source
> snapshot should remain provider-authoritative rather than be frozen as timeless
> source truth.

A tag cannot be edited later to match provider state that moved.

### 6. Bind the exact release candidate

The candidate is **the exact protected-main commit after *all* admitted
pre-effect preparation for the release Work Item has integrated** — not merely
after the first preparation Change Request merged. Recompute
`<PUBLIC_SURFACE_DIGEST>` from that exact candidate.

### 7. Verify the exact candidate

Run the applicable verification contract against that immutable candidate and
record the candidate SHA, the exact routes, the actual results, and any skipped
or inapplicable checks **separately**.

### 8. Obtain exact owner authorization

Bind authorization to the candidate SHA, the tag, the digest, the tag semantics,
the exact Release metadata, the intended mutations, the explicit non-effects, the
anticipated coupled effects, the stop conditions and the read-back requirements.
**Authorization for one effect does not grant later effects.**

### 9. Declare the known bounded effect envelope

Before each mutation, record:

```
authorized intent
  → requested provider operation
  → known provider transformations / derived representations
  → known provider parsing / automation surfaces
  → anticipated coupled effects
  → authoritative post-effect observations
  → reconciliation
```

This is an orientation and reconciliation aid, **not** a claim that the full
provider effect surface is mechanically known. Record known surfaces,
inaccessible surfaces, assumptions and unknowns. **Do not silently convert an
unknown into an assumption of no effect.**

### 10. Execute one mutation at a time

Do not batch dependent mutations when read-back of the earlier one is needed for
the later. The demonstrated GitHub route is: annotated tag → tag read-back →
Release against the existing tag → Release read-back.

### 11. Create the annotated tag first

Create one **annotated** tag bound to `<AUTHORIZED_RELEASE_SHA>` and push without
force. Never move or reuse a released identity. Verify **both**:

- the tag *object* identity and type; and
- the *dereferenced* commit.

These are different objects: the ref points at the tag object, so dereference
before comparing to the authorized commit.

### 12. Read back the tag effect

**Command success is not provider truth.** Verify the remote tag and the declared
envelope, and classify every observed change as intended, expected-coupled or
unexpected. Record provider workflow activity accurately, and do not promote an
expected automation run to release evidence unless current authority independently
makes it part of the gate.

### 13. Stop on unexpected coupled mutation

Before any dependent write: **stop → authoritative read-back → reconcile.** Do
not retry, undo, compensate or continue unless separately authorized. For
ambiguous provider outcomes: **read before retry.**

### 14. Create the Release against the existing tag

Require the operation to use the already-verified tag rather than implicitly
inventing or moving one. Treat metadata such as prerelease, draft and
Latest/recommended as **semantic fields** that can strengthen the public claim;
select them explicitly, never silently.

### 15. Read back the Release effect

Verify the tag association, identity, approved metadata, approved body, attached
assets, provider-generated projections, known coupled automation and any
unexpected mutation. **Provider-generated source archives are projections of the
tag, not curated package artifacts.**

### 16. Reconcile projections only after read-back

Effect first, authoritative read-back second, repository reconciliation third.
Never predict an external effect into a source projection before it occurs.
Preserve durable facts — identity, exact immutable commit, digest, durable
non-promises — and leave mutable provider presentation state provider-authoritative
absent a demonstrated durable need.

### 17. Preserve historical pre-effect evidence

Do not rewrite a truthful pre-effect record to match the later outcome. Prefer a
historical pre-effect record **plus** an additive post-effect result, so
chronology stays reconstructable.

### 18. Close the release Work Item last

Completion order: semantic selection → preparation → exact candidate → exact
verification → provider authorization → tag effect → tag read-back → Release
effect → Release read-back → repository reconciliation → final provider read-back
→ Work Item completion. **Work Item closure is itself provider state and must be
read back.**

## Verification

Before the effect: the candidate is the exact post-preparation protected-main
commit; its digest is recomputed; the applicable routes pass on that immutable
candidate, with skipped or inapplicable checks recorded separately; and the
snapshot contains no current-state claim that flips solely because the effect
occurs.

After each mutation: authoritative provider read-back, not command exit status.
The tag is an annotated object whose dereferenced commit equals the authorized
candidate; the Release is bound to that existing tag with the approved metadata
and body and no curated assets; protected main is unchanged; and every observed
provider change is classified as intended, expected-coupled or unexpected.

After reconciliation: the durable facts are recorded, historical pre-effect
evidence is unchanged, and the Work Item's final state is read back from the
provider.

## Recovery

**Read before retry.** On an ambiguous or partial provider outcome, establish
authoritative provider state before issuing any further mutation; never issue a
duplicate write on the assumption that the first did not land.

On an unexpected coupled mutation, stop before the next dependent write, read
back, and reconcile. Do not automatically undo, retry or compensate — a released
identity is never moved, reused or deleted to tidy up. If the outcome already
matches the intended terminal state, record the mechanism as a finding rather
than reversing it.

If the candidate, authorization or semantics no longer match, stop and return to
the owner rather than retargeting the release.

## Provider transformations and parsing surfaces

The reusable finding is broader than any one keyword:

> One authorized provider action can carry the same semantic payload through
> **multiple provider representations or parsing surfaces** before all coupled
> effects are known.

The observed path was: Change Request content → provider-generated squash commit
message → plain-text keyword parser → Issue lifecycle effect. Inspecting only the
rendered user-facing input surface was **not sufficient**, because the operation
derived another parseable representation from it.

Before a provider mutation, consider known transformations and derived surfaces
that can carry effectful content. This does not claim all provider
transformations are knowable, and does not claim other providers behave like
GitHub.

**Operational precaution.** When an Issue must remain open across a GitHub squash
merge, avoid literal closing-keyword-plus-issue-reference sequences in any content
that may propagate into the squash commit message — **even where rendered
Markdown would treat that text as code or narrative**. Do not rely solely on
inspecting rendered closing-issue references. This is a Gnostoa-self precaution;
no scanner or linter is implemented, and it is not promoted to adopter policy.

## Run conclusion is not check execution

A provider workflow run reported `success` while only some jobs executed and the
rest were skipped.

> **Provider workflow or run conclusion is not proof that every potentially
> relevant check executed.**

Record job-level execution separately, never treat skipped checks as PASS, and do
not turn a tag-triggered run into release evidence unless current policy requires
and routes those checks.

## Observation coverage and UNKNOWN

One provider surface was inaccessible during the observed release: user-level
container-package listing returned `403` because the available credentials lacked
the required scope.

That does **not** license concluding the artifact is absent. Encode instead:

> An inaccessible observation remains a **declared coverage limit**.

Claim absence only within the observed, authoritative scope, and name inaccessible
surfaces whenever they could affect interpretation. Package-registry access is
**not** made a universal source-only release prerequisite; that would need its own
evidence and Decision.

## Not canonicalized here

No generic provider-effect state machine, transformation graph, capability broker,
provider adapter, effect-receipt schema, observation-binding contract,
complete-mediation mechanism, keyword linter, workflow engine, CI gate or release
automation tool. **No implementation mechanism has been selected.** This runbook
is procedural self-knowledge only.

## Revisit condition

Revisit after the next completed source-only release, or earlier if GitHub tag or
Release semantics change, squash/merge parsing semantics materially change,
provider automation changes, the release packaging or distribution scope changes,
or repeated evidence contradicts part of this procedure. One successful release
does not make it permanently stable.
