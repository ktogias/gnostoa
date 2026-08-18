---
type: Source
title: Post-C4 evidence boundary selection
description: Reconstructs the undecidability boundaries the C4-v0 falsification exposed, separates addressable evidence gaps from fundamental oracle limits, compares three candidate evidence primitives, and records the owner's selection of a smaller precursor experiment over any of them.
status: draft
generated:
  by: agent:claude-opus-5
  at: "2026-08-18T09:30:00Z"
sources:
  - id: evidence-primitive-selection-work-item
    resource: https://github.com/ktogias/gnostoa/issues/35
    title: Select one bounded evidence primitive after the C4-v0 falsification
  - id: c4v0-experiment-work-item
    resource: https://github.com/ktogias/gnostoa/issues/33
    title: Experiment with a deterministic read-only READY predicate
  - id: in-toto-statement
    resource: https://github.com/in-toto/attestation/blob/main/spec/v1/statement.md
    title: in-toto Attestation Statement v1
  - id: slsa-provenance
    resource: https://slsa.dev/spec/v1.0/provenance
    title: SLSA Provenance v1.0
  - id: github-protected-branches
    resource: https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches
    title: GitHub — About protected branches
  - id: github-pr-merges
    resource: https://docs.github.com/en/pull-requests/collaborating-with-pull-requests/incorporating-changes-from-a-pull-request/about-pull-request-merges
    title: GitHub — About pull request merges
  - id: saltzer-schroeder
    resource: https://web.mit.edu/Saltzer/www/publications/protection/Basic.html
    title: Saltzer and Schroeder — Basic Principles of Information Protection
x-project-knowledge:
  id: kit.assessment.post-c4-evidence-boundary-selection
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governed-by
      target: /decisions/0016-evolve-human-agent-workflow-through-bounded-self-hosted-slices.md
    - kind: derived-from
      target: /assessments/b2-c4v0-readiness-predicate-experiment.md
    - kind: derived-from
      target: /assessments/b2-p1-streamlined-self-hosting-measurements.md
    - kind: derived-from
      target: /assessments/b2-p2-fresh-session-and-effect-authority-findings.md
    - kind: references
      target: /assessments/b2-control-selection-and-failure-path-map.md
    - kind: references
      target: /failure-modes/post-effect-current-state-drift.md
---

# Post-C4 evidence boundary selection

## Recording boundary

This is research and selection input. It **implements nothing and activates
nothing**. The owner has selected Alternative B — a smaller precursor experiment
— as the next thing to try; that selection is recorded at the end of this record,
and **implementation of it is not admitted**. C4-v0 remains **rejected as a readiness predicate**; C2, C3,
the narrower consistency-checking finding and Decision 0016 increment 2 all
remain **recorded and not activated**.

**No evidence-primitive experiment yet is a valid outcome, and it is what the
owner chose.** No evidence primitive was selected. More evidence infrastructure
is not assumed to be desirable, and nothing here argues that Gnostoa should
acquire more of it.

No aggregate coverage score appears anywhere in this record, deliberately. The
C4-v0 result showed that counting how many failure paths a mechanism *touches*
is exactly the number that misleads.

## Why this question and not another

C4-v0 refuted the hypothesis that `READY` can presently be computed as a strict,
deterministic, fail-closed result over existing evidence. The measured reason was
not that the predicate was badly built. It was that the evidence it had to read
could not decide the questions being asked: 3 of 8 recorded false-ready states
were mechanically rejected, 0 of 8 were wrongly called READY, and **all 4
owner-accepted positive controls failed to reach READY**.

The next question is therefore about the evidence, not about the control:

> Which smallest missing evidence primitive, if any, would convert one materially
> important observed undecidability into reproducible evidence at acceptable
> complexity, maintenance and human-attention cost?

## Phase 1 — Evidence-gap taxonomy

Every entry below traces to a canonical record. Nothing is inferred from the
prompt that produced this slice.

### EG-1 — provider identity declared without a reproducible local witness

| | |
|---|---|
| Observed | All twelve C4-v0 controls declared a provider-side identity (`provider-body-sha256` or `github-issue-body-utf8-sha256-v1`) that no local evidence resolves |
| Source | C4-v0 assessment, Finding 1 |
| Stage | candidate evaluation; fresh-session resume orientation |
| Exists | the declared digest value, and a reference URL naming where the subject lives |
| Missing | an immutable local artifact stating "this reproduces that external observation", and a binding from the declared identity to it |
| Class | ACQUIRABLE, REPRODUCIBLE, CANDIDATE_BINDABLE |
| Caused | INDETERMINATE on 4 of 4 positive controls; it is the single reason strict READY is unreachable for every candidate this project has produced |
| Recurrence | 12 of 12 replayed controls |
| Uncertainty | whether closing it is worth an envelope schema change, which is public surface and would need its own Decision |

Partial constructibility is already demonstrated: `tests/fixtures/github-issue-24.json`
reproduces the Issue #24 body digest exactly, and a test pins that reproduction
against checkout line-ending normalisation. What has **never** been demonstrated
is a *binding* — nothing lets a checker learn that this artifact is that
dependency's witness.

### EG-2 — verification result not bound to an exact candidate

| | |
|---|---|
| Observed | B2/P1's first false-ready state: a candidate "presented as review-ready while its own declared pre-merge gate was still unrun" |
| Source | B2/P1 measurements, false-ready outcomes; C4-v0 assessment, Finding 4 |
| Stage | pre-review readiness assertion |
| Exists | `handoff.verify` free-text lines describing what a reader should check; provider-side run results that are not repository evidence |
| Missing | any artifact binding route identity, exact candidate, that execution occurred, and its result |
| Class | ACQUIRABLE, CANDIDATE_BINDABLE |
| Caused | false READY; then INDETERMINATE under replay; detected by a human |
| Recurrence | 1 reconstructable false-ready state |
| Uncertainty | whether a receipt can *prove* execution or only assert it |

`schemas/verification-manifest.schema.json` declares suite **capabilities**, not
results, and no manifest instance exists anywhere in the repository. There is
nothing for a checker to read.

### EG-3 — measurement not bound to its subject

| | |
|---|---|
| Observed | B2/P1's second false-ready state: "presented for timed review with stale surface accounting". Separately, a review packet "reported a review surface measured before the measurement artifacts existed, which did not match the provider's count for the exact head" |
| Source | B2/P1 measurements: false-ready outcomes, and evidence defects corrected in owner review |
| Stage | review-packet preparation |
| Exists | measurements written as prose inside assessments |
| Missing | a structural binding from a measurement to the exact subject identity it describes |
| Class | ACQUIRABLE, CANDIDATE_BINDABLE, DECLARATION_DEPENDENT |
| Caused | false READY; human-only detection; recovery burden — 3 evidence defects were corrected during owner review |
| Recurrence | 1 false-ready state, plus 3 evidence defects in one slice |
| Uncertainty | measurements are prose-shaped; structuring them tends toward the event store this project has repeatedly refused |

### EG-4 — declaration can omit obligations, rewarding under-declaration

| | |
|---|---|
| Observed | The C4-v0 experiment's own candidate reached READY only because its envelope declared three file digests and no provider identity |
| Source | C4-v0 assessment, Finding 5 |
| Stage | envelope authoring |
| Exists | `identities.dependencies` and `references`, both author-chosen, both bounded at 20 items |
| Missing | an authoritative source for which obligations *must* be declared for a given bounded change |
| Class | DECLARATION_DEPENDENT |
| Caused | an adverse incentive: any check over declared identities is cheaper to satisfy by declaring less |
| Recurrence | 1 demonstrated instance, inside the experiment itself |
| Uncertainty | whether a required set is derivable from anything authoritative without a general policy language |

### EG-5 — checkpoint predecessor unavailable after squash integration

| | |
|---|---|
| Observed | `checkpoint.previous` was undecidable at POS-1 and POS-4, because each slice's envelope first appears on protected main at its squash commit |
| Source | C4-v0 assessment, Finding 2 |
| Stage | post-integration verification |
| Exists | the declared `previous` digest and `sequence` |
| Missing | the predecessor version, which is not in the integrated history at all |
| Class | LIFECYCLE/PROVENANCE |
| Caused | INDETERMINATE at exactly the commits carrying the most authority |
| Recurrence | 2 of 4 positive controls |
| Uncertainty | whether chain verifiability after integration is desirable, or an accepted consequence of squash-merging |

GitHub's own documentation confirms the mechanism rather than a Gnostoa defect:
intermediate commits from a pull request "are not preserved as separate commits
on the base branch".

### EG-6 — route success does not prove the intended controls executed

| | |
|---|---|
| Observed | All five C4-v0 control tests skipped inside the container while the route reported `OK (skipped=5)`; Git had refused the bind-mounted repository with `detected dubious ownership` and the skip guard read that as absent history |
| Source | C4-v0 assessment, Finding 3 |
| Stage | verification execution |
| Exists | pass/fail per route, and (unread) per-test skip counts |
| Missing | a recorded expectation of what should have run, against which an actual execution can be compared |
| Class | partly ACQUIRABLE (execution counts are observable); partly ORACLE_LIMIT (knowing what *should* run is a specification question, not an evidence question) |
| Caused | false-green verification; human-only detection, by reading which tests ran |
| Recurrence | 2 — the C4-v0 guard skip, and B2/P1's route asymmetry, where development-container green was not sufficient evidence for a change touching the CLI |
| Uncertainty | whether an expectation can be recorded without duplicating the suite definition |

This is not a local peculiarity. GitHub's protected-branch documentation states
that required status checks "must have a `successful`, `skipped`, or `neutral`
status" — a skipped required check **satisfies** the requirement. The
industry-standard mechanism has the same property Gnostoa observed.

### EG-7 — latent defect absent from every available oracle

| | |
|---|---|
| Observed | Three B2/P1 false-ready states: a candidate offered while the recursive-alias blocker was present; while the wider error-boundary family was present; while the source snapshot was neither single nor bounded |
| Source | B2/P1 measurements; C4-v0 assessment, Finding 4 |
| Stage | any |
| Exists | uniformly green evidence |
| Missing | nothing that could have been recorded — the defects were unknown to every oracle that existed at the time |
| Class | **ORACLE_LIMIT** |
| Caused | false READY ×3; every one found by a human or by a gate the automated suites did not run |
| Recurrence | 3 of 8 replayed false-ready states |
| Uncertainty | none about the classification; this is a limit, not a gap |

### EG-8 — declared-identity binding is weaker than structural validity in the validator that gates ordinary work

| | |
|---|---|
| Observed | During the #33 close-out, `task-validate` reported the envelope valid while its declared `decision-0016` digest was stale (`c4b902db…` declared, `a36b0fbb…` actual). Regenerating the projection rejected it, because `task-project --observed-dependency` recomputes declared identities |
| Source | reviewed corrected head `50250b3ad95e6845f72b7c5608d84d66cc200b35` |
| Stage | pre-integration verification |
| Exists | **everything needed** — the declared value, the referenced file, and a tool that recomputes and compares |
| Missing | **nothing.** The stronger check was simply not run at that head |
| Class | not a missing primitive; validation **routing** |
| Caused | a stale declaration surviving into a candidate reported as verified |
| Recurrence | 1 |
| Uncertainty | none about the mechanics; the open question is routing, which is outside this slice |

This entry is recorded for completeness and is deliberately **not counted toward
any candidate**. It is evidence *against* needing a new primitive for this class:
the reusable consistency check the C4-v0 close-out identified as its narrower
finding already exists, already lives in the public tool surface, and already
worked the moment it was invoked. That says nothing about what it would cost to
make its execution reliably unavoidable: the routing location has not been
selected, so the surface impact of routing it is unknown.

## Phase 2 — Addressable gaps versus fundamental limits

### Bucket A — potentially addressable with bounded evidence mechanics

EG-1, EG-2, EG-3, EG-4, EG-5, and the observable half of EG-6.

### Bucket B — not solvable by more evidence plumbing

**EG-7 entirely**, and the specification half of EG-6.

> **No evidence primitive can prove facts that no available oracle or
> observation can establish.**

Three of eight recorded false-ready states were latent product defects behind
uniformly green evidence. No receipt, witness, attestation or declaration
mechanism could have rejected them, because the information did not exist in any
form at the time the readiness claim was made. Building machinery and counting
those three as covered would be false coverage.

Human semantic review remains a valid and necessary detector for this class. It
is what actually found them — and it is what found EG-6 and EG-8 too.

### EG-8 — neither bucket

Already-existing mechanism; nothing missing.

## Phase 3 — Established practice consulted

Primary sources only.

**Subject binding is content-addressed and immutable.** The in-toto Statement
binds an attestation to its subject purely by digest: every subject "MUST have
digest set", "subject artifacts are matched purely by digest, regardless of
content type", and subjects "are assumed to be *immutable*". This is the exact
shape Gnostoa's `file-sha256` dependencies already use, and the shape EG-1 and
EG-3 lack for their subjects.

**Attestation is a trusted claim, not proof of execution.** SLSA Provenance
records how an artifact was produced, but verification rests on trusting the
builder and validating a signature — consumers "MUST accept only specific
signer-builder pairs". The specification does not claim provenance proves the
build ran; the build platform is "trusted to faithfully run the build and record
the provenance". **This is the sharpest constraint on E1**: the most mature
system in this space does not solve "did it actually run", it relocates the
question to platform trust.

**Skipped checks satisfy required checks.** GitHub's protected-branch semantics
accept `successful`, `skipped` or `neutral`. EG-6 is therefore a property of the
standard mechanism, not a Gnostoa bug.

**Squash merge does not preserve intermediate commits** on the base branch,
which is exactly EG-5's mechanism.

**Complete mediation and economy of mechanism.** Saltzer and Schroeder: "Every
access to every object must be checked for authority", and "keep the design as
simple and small as possible", because "protection flaws escape notice during
normal use". EG-4 is a complete-mediation problem — a check over *declared*
obligations mediates only what the author chose to declare. Their companion
principle warns against paying for that completeness with mechanism size.

**Fail-safe defaults**: "base access decisions on permission rather than
exclusion". C4-v0 applied this faithfully and the result was that nothing could
be admitted, which is the recorded cost of fail-closed evaluation over evidence
that cannot decide.

**Design by Contract** (Meyer, studied in the C4 selection research) remains the
reference for declared preconditions, and is the direct antecedent of E3.

## Phase 4 — Three candidate evidence primitives

### E1 — exact-candidate verification receipt

A compact immutable artifact recording route identity, exact candidate, that
execution occurred, and the result.

*Research question:* would this resolve "the required route ran on this exact
candidate" without becoming a CI event store?

### E2 — reproducible witness for an external dependency

A bounded way to state: this immutable local artifact reproduces the observed
identity of that external dependency.

*Research question:* would this make provider-side identities locally decidable
without provider adapters, and without turning canonical task state into cached
provider state?

### E3 — bounded obligation completeness

A mechanism determining which evidence obligations must be declared, so omission
does not make mechanical checks easier.

*Research question:* can completeness be derived deterministically from existing
scope or policy without a general policy engine and without displacing human
semantic judgement?

**E3 is retained rather than replaced**, although it is the weakest of the three,
because the alternative that looked stronger — routing existing checks so the
stronger validator always runs — is not an evidence primitive at all. It appears
in the owner alternatives as a precursor instead.

Checkpoint provenance is **not** a fourth candidate. Following the research
scope, EG-5 is treated as a constraint each candidate must survive.

## Phase 5 — Relation matrix

Typed relations only. Evidence strength: **[G]** demonstrated in Gnostoa at the
same boundary with the same mechanism; **[P]** engineering-principle hypothesis;
**[X]** requires experiment.

| Gap | E1 receipt | E2 witness | E3 obligations |
|---|---|---|---|
| EG-1 provider identity | NO_EXPECTED_EFFECT | MAKES_DECIDABLE [X] | DETECTS_MISSING_EVIDENCE [P] |
| EG-2 result not candidate-bound | MAKES_DECIDABLE [X] | NO_EXPECTED_EFFECT | DETECTS_MISSING_EVIDENCE [P] |
| EG-3 measurement not subject-bound | PARTIALLY_MITIGATES [P] | PARTIALLY_MITIGATES [P] | DETECTS_MISSING_EVIDENCE [P] |
| EG-4 under-declaration incentive | NO_EXPECTED_EFFECT | NO_EXPECTED_EFFECT | NEEDS_EXPERIMENT [X] |
| EG-5 squash provenance | UNKNOWN | NO_EXPECTED_EFFECT | NO_EXPECTED_EFFECT |
| EG-6 false-green skipped execution | NEEDS_EXPERIMENT [X] | NO_EXPECTED_EFFECT | NO_EXPECTED_EFFECT |
| EG-7 latent defect | NO_EXPECTED_EFFECT | NO_EXPECTED_EFFECT | NO_EXPECTED_EFFECT |

Three notes on strength, because the [G] rule is strict:

- **Nothing in this matrix is [G].** No candidate mechanism has been
  demonstrated in Gnostoa at the boundary it would have to work at.
- E2 comes closest and still is not [G]. Reproducing a provider body digest from
  a committed artifact *is* demonstrated; the **binding** that would let a
  checker consume it is not. A fixture existing is explicitly not grounds for
  [G].
- E1 → EG-6 is `NEEDS_EXPERIMENT`, not `RESOLVES`. A receipt that records only
  pass/fail cannot distinguish "green because the controls ran" from "green
  because they skipped". A receipt that records *what executed* might. That
  difference is the whole experiment.

## Phase 6 — Bounded evaluation

| | E1 receipt | E2 witness | E3 obligations |
|---|---|---|---|
| Primary gap | EG-2 | EG-1 | EG-4 |
| Also affects | EG-3, EG-6 | EG-3 | EG-1, EG-2, EG-3 as detection only |
| Nature of help | binds evidence to an exact candidate | makes an external fact reproducible | prevents omission |
| New canonical state | yes — a persisted artifact per verified candidate | yes — a witness artifact plus a binding | yes — a required-obligation set |
| Schema change | probably, to reference receipts | **yes**, to express the binding | **yes** |
| Public-surface change | likely (`ci/`, `schemas/`) | likely (`schemas/`) | likely (`schemas/`, `policy/`) |
| Provider-specific surface | no | **risk** — must stay provider-neutral | no |
| CI change | **yes**, receipts are produced by routes | no | no |
| New runtime dependency | none identified | none identified | none identified |
| Self-hosted first | partly — production needs CI | yes | yes |
| Human-attention cost | low to read, non-trivial to trust | low | **high** — authors must satisfy a required set |
| More foreground evidence | moderate | low | moderate |
| Evidence amplification risk | **high** — receipts accrete per candidate | low — one artifact per external subject | moderate |
| Falsifiable by historical replay | **yes**, partially: P1-1 is a real negative control, but historical receipts do not exist and would have to be reconstructed | **yes** — 12 recorded controls, all INDETERMINATE on exactly this | weakly — one demonstrated instance only |
| Cleanly removable | yes | yes if the binding is optional | hard once authors depend on it |
| Adverse incentive | mild — routes could emit thin receipts | mild — witnesses could be stale-but-matching | **the incentive it exists to remove is also its own risk**: obligation sets can be gamed by narrowing scope |
| Satisfiable by declaring less | no | partly — omit the dependency, omit the witness | that is precisely what it must prevent |
| Invalidated by squash | receipt survives if content-addressed, not if history-dependent | no | no |
| Depends on branch history | must not | no | no |
| Solves an oracle limit it cannot | **no**, if it stays about execution rather than correctness | no | no |
| Smallest experiment | replay P1-1 with a reconstructed receipt and prove the unrun gate becomes decidable | replay the 12 controls with witnesses for the Issue-body identity and prove positives reach a decided state | derive a required set for 2 historical slices and prove omission is detected |
| Stop condition | receipts cannot distinguish ran from skipped, or grow per-candidate without bound | the witness cannot be bound without caching provider state | no authoritative derivation source exists |

## Phase 7 — Falsification bars

### E1 must prove

route actually executed; exact candidate binding; no stale result reuse; no
false-green from skipped or empty execution; bounded artifact size; no event-store
growth; survival through integration.

**Current standing:** the execution bar is the hard one, and the most mature
prior art does not clear it — SLSA relocates "did it run" to platform trust
rather than proving it. E1 could plausibly clear a weaker, still useful bar:
recording *what executed* so that a skip becomes visible. It cannot be
recommended on the strong reading without an experiment that settles this.

### E2 must prove

the local witness reproduces the authoritative external identity; the binding is
explicit and immutable; the witness cannot silently drift; ordinary replay needs
no live provider access; task state does not become cached provider state; the
mechanism stays bounded and provider-neutral.

**Current standing:** digest reproduction is demonstrated; immutable
content-addressed binding is exactly the in-toto subject pattern; replay needs no
provider access by construction. The unresolved bar is the fifth: a witness *is*
a snapshot of provider state, and the line between "an artifact that reproduces
an identity" and "cached provider state" is the thing an experiment would have to
hold. Drift is the mirror risk — a witness that stops matching the live subject
is silently wrong in a way the current fixture already could be.

### E3 must prove

the obligation set derives from something authoritative; omission is mechanically
detectable; actors cannot reduce obligations by declaring less scope; no general
policy language; human semantic scope decisions stay human.

**Current standing:** **E3 fails its first bar today.** The only candidate
authorities are `scope.included`/`scope.excluded`, which are human prose, and
`policy/change-control.yaml`, which declares class requirements and knows nothing
about a particular task's dependencies. Deriving a required set from prose is not
deterministic, and the fallback — a hand-maintained obligation list — reintroduces
the same declaration problem one level up.

## Phase 8 — Projection and completed-list pressure

A repeated design signal, recorded as such and not as an evidence-primitive
target:

| Slice | `state.completed` | Projection budget |
|---|---|---|
| B2/P1 | 20/20 | — |
| B2/P2 | 20/20 | — |
| B2/C4-v0 | 20/20 | exceeded 6000 characters more than once and correctly refused each time |

Three consecutive slices saturated the same bound, and the C4-v0 close-out could
not append its own disposition because of it. Does any candidate increase that
pressure?

- **E1** — moderate. Receipts are separate artifacts, but referencing them
  consumes `references.evidence` slots, themselves bounded at 20.
- **E2** — higher. A witness must be referenced *and* bound per dependency,
  pressing on both `references` and `identities.dependencies`, each bounded at 20.
- **E3** — highest. Its entire purpose is to expand what must be declared.

Each is penalised qualitatively in that order. The task-envelope schema is
deliberately **not** redesigned here, and no saturation fix is proposed.

## Phase 9 — What the evidence says about doing nothing

Recorded plainly, because it is a real option and the strongest argument for it
is empirical:

- EG-7 is untouchable by any of the three, and it is 3 of the 8 recorded
  false-ready states.
- EG-8 shows one class already has a working mechanism that simply was not
  routed — no new primitive needed.
- EG-6's Gnostoa instance and EG-8's were both caught by a human reading what
  actually happened, at low cost, promptly.
- Every candidate requires public-surface change, hence a further Decision, and
  every one adds pressure to bounds that have saturated three times running.
- C4-v0 already demonstrated the failure mode of building the mechanism before
  the evidence can decide.

## Alternatives presented for selection

Exactly three. Nothing here is a recommendation.

### A — Select E2 for a separately admitted bounded experiment

- **Primary gap:** EG-1, the single reason no candidate in this project's history
  reaches a decided state.
- **Strongest benefit:** it is the only candidate with 12 recorded controls that
  fail on exactly the thing it addresses, so the experiment is genuinely
  falsifiable against history rather than against itself.
- **Strongest limitation:** a witness is a snapshot of provider state, and
  keeping that from becoming cached provider state is unproven.
- **Surface impact:** envelope schema change to express the binding — public
  surface, requiring its own Decision before implementation.
- **Human attention:** low to read; one more artifact to produce per external
  dependency.
- **Historical test:** replay the 12 C4-v0 controls; the 4 positive controls must
  move from INDETERMINATE to decided, and no false-ready state may become READY.
- **Strongest uncertainty:** silent drift between witness and live subject.
- **Non-goals:** provider adapters, live provider access during replay, general
  external-state caching, reviving C4-v0.

### B — Select a smaller precursor: complete the routing of checks that already exist

- **Primary gap:** EG-8, with EG-6 as a secondary observation.
- **Strongest benefit:** requires **no new evidence primitive and no new
  validation semantics**. The detecting mechanism already exists, is already
  public, and already worked when invoked. This directly tests C4-v0's own
  narrower finding — that deterministic consistency checks over existing evidence
  catch real state and identity defects before human review — without building
  anything new.
- **Strongest limitation:** it addresses none of EG-1 through EG-5, so strict
  readiness stays exactly as undecidable as C4-v0 found it.
- **Surface impact: UNKNOWN.** The mechanism exists, but *the location required
  to make its execution reliably mechanical has not been selected*, and the
  concrete diff is what determines surface impact. Routing that touches `ci/`,
  policy, a public guardrail or supported-tool semantics would itself change the
  public inherited surface. A self-hosted, non-public routing path is preferable
  but **must not be assumed**. The impact stays unknown until the separately
  admitted precursor experiment identifies the smallest concrete routing location
  and reclassifies that actual diff.
- **Stop condition:** if reliable mechanical routing of the existing consistency
  check requires a public CI, policy, schema or supported-tool contract change,
  **STOP before implementation** and return the actual impact for owner
  disposition, rather than silently treating the precursor as surface-free. The
  precursor must not be broadened merely to preserve that assumption.
- **Human attention:** neutral to lower.
- **Historical test:** the #33 close-out is a real negative control — a candidate
  reported as verified while carrying a stale declared identity. Routed
  correctly, it must be rejected before review, with no false blocks on the
  frozen P1, P2 and #33 terminal records.
- **Strongest uncertainty:** whether one recorded instance justifies any slice
  at all.
- **Non-goals:** new checks, new evidence classes, new validation semantics,
  readiness semantics, and any assumption that the routing is surface-free.

### C — Select none: no evidence-primitive experiment yet

- **Primary gap:** none addressed by construction.
- **Strongest benefit:** every candidate needs public-surface change and a
  further Decision; none is [G] at its own boundary; the largest single class of
  recorded false-ready states is an oracle limit that no primitive can touch; and
  three consecutive slices have saturated the bounds all of them would press on.
  Doing nothing costs nothing and forecloses nothing.
- **Strongest limitation:** the failed property stays unmitigated, and EG-1
  continues to make any future readiness work undecidable from the start.
- **Surface impact:** none.
- **Human attention:** unchanged — human semantic review continues to be the
  detector, which is what it has actually been throughout B2.
- **Historical test:** none; this alternative asserts no mechanism.
- **Strongest uncertainty:** whether deferring EG-1 indefinitely quietly
  forecloses the capability direction Decision 0016 records.
- **Non-goals:** declaring the failed property acceptable, closing the capability
  loop, or discarding this research.

## Uncertainties

- Whether any evidence primitive is worth a public-surface change while the
  project's own measured detector of record is human semantic review.
- Whether E1's execution bar is clearable at all, given that the most mature
  prior art relocates rather than solves it.
- Whether E2's binding can be expressed without the envelope becoming a place
  where provider state is cached.
- Whether EG-3 can be structured without drifting toward the event store this
  project has refused three times.
- Whether EG-5 deserves anything: a chain unverifiable after squash may simply be
  the accepted price of squash integration.
- Whether the recurrence counts here are large enough to justify any mechanism.
  Most gaps have one or two reconstructable instances. EG-1 is the exception at
  12 of 12.

## Owner selection

Recorded from the accountable maintainer's semantic review of research head
`git:64bb68f11dcd88f789958aad1ec6414d4fff5d29`, after that review found and
required the conservative correction to Alternative B's surface claim recorded
above.

> **B. SELECT A SMALLER PRECURSOR EXPERIMENT.**

**Meaning.** Test whether Gnostoa can reliably route its already-existing
deterministic declared-identity/source-binding consistency check before owner
review, with **no new evidence primitive and no new validation semantics**.

**Primary observed failure.** During the #33 close-out, ordinary task validation
passed while the declared Decision 0016 digest was stale; the existing stronger
projection/dependency recomputation detected the defect only when it was actually
invoked.

**Why selected.**

- it acts on a real recorded defect, independent of resurrecting C4-v0;
- the detecting mechanism already exists;
- it tests the narrower finding retained from C4-v0;
- it can establish whether better use of existing evidence is sufficient before
  adding receipts, witnesses or obligation machinery.

**This selection is an owner preference about what to try next. It is not
evidence, and it makes nothing true about any candidate.** No relation strength
in this record changes because of it, and no candidate becomes `[G]`.

**This does not select** E1, E2, E3, C2, C3, a readiness predicate, or Decision
0016 increment 2. **Implementation is not admitted.**

### Future precursor experiment contract — RECORDED, NOT IMPLEMENTED

Recorded here so the future experiment can be admitted against a fixed contract.
Nothing below is built by this slice.

**Primary question.** Can an already-existing deterministic identity/source-binding
check be made reliably unavoidable at the appropriate Gnostoa self-hosting review
boundary, catching the historical #33 stale-identity defect before owner review,
without adding a new evidence primitive or unacceptable workflow cost?

**Historical negative control.** The #33 close-out candidate where
`task-validate` passed with the stale declared Decision 0016 digest, and
projection regeneration later rejected it.

**Positive controls.** The valid current and frozen task records for P1, P2 and
#33, limited to the exact consistency properties the routed check claims to
verify.

**Required observable outcomes.**

1. the historical stale-identity control is rejected **before owner review**;
2. valid controls are not falsely rejected;
3. the intended consistency check **demonstrably executes** — a skipped, empty or
   bypassed invocation does not count as success;
4. no new evidence class, receipt, witness, schema or readiness semantics is
   introduced;
5. no additional human approval prompt is introduced;
6. added execution time and foreground evidence remain bounded.

Outcome 3 is not ceremonial. C4-v0's own controls skipped entirely inside the
container while the route reported `OK (skipped=5)`, and GitHub's protected-branch
semantics accept a skipped required check as satisfying the requirement. A
precursor that cannot show its check ran has reproduced the defect it exists to
prevent.

**Mandatory entrance gate.** Before implementation the experiment must identify
the exact proposed routing location, derive the actual change class from that
concrete diff, and determine whether it changes the public inherited surface.

> If the smallest reliable mechanical route requires changes to public CI,
> policy, schema, guardrail or supported-tool contract: **STOP BEFORE
> IMPLEMENTATION** and return that fact for a separate owner disposition. Do not
> broaden the precursor merely to preserve the assumption that it is
> surface-free.

**Falsification and stop rules.** Routing cannot guarantee the intended check
actually executed; the change only adds advisory prose; implementation requires
new consistency semantics rather than routing the existing mechanism; valid
controls false-block; public-surface impact appears without separate admission;
or human-attention and maintenance cost is disproportionate to the single
observed failure.

**A negative result is valid.**

### Status of E1, E2 and E3 after the selection

All three remain **RECORDED / NOT ACTIVATED** research alternatives. Their typed
relations and evidence strengths are unchanged by the selection; none is `[G]`.

**E2 remains the strongest candidate evidence primitive produced by this
research, and is NOT SELECTED.** One qualification must travel with it:

> EG-1's 12-of-12 recurrence was observed **inside the rejected C4-v0 evaluation
> corpus**. It measures how often that corpus declared a provider identity no
> local evidence resolves — not how often an independent operational outcome was
> harmed.

From that recurrence alone it does **not** follow that E2 currently improves any
independent measured operational outcome. A later E2 experiment would need its
own value proposition, established without reviving C4-v0 readiness.
