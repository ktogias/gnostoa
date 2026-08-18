---
type: Source
title: C4-v0 readiness predicate experiment
description: Replay of twelve historical controls against a deterministic read-only READY predicate; the strict hypothesis was refuted and the owner rejected C4-v0 as a readiness predicate, retaining only the narrower consistency-checking finding as evidence.
status: draft
generated:
  by: agent:claude-opus-5
  at: "2026-08-17T23:10:00Z"
sources:
  - id: readiness-experiment-work-item
    resource: https://github.com/ktogias/gnostoa/issues/33
    title: Experiment with a deterministic read-only READY predicate
  - id: control-selection-work-item
    resource: https://github.com/ktogias/gnostoa/issues/31
    title: Map observed control failures and select one bounded enforcement experiment
x-project-knowledge:
  id: kit.assessment.b2-c4v0-readiness-predicate-experiment
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governed-by
      target: /decisions/0017-scope-the-readiness-predicate-experiment-to-gnostoa-self-hosting.md
    - kind: references
      target: /assessments/b2-control-selection-and-failure-path-map.md
    - kind: references
      target: /assessments/b2-p1-streamlined-self-hosting-measurements.md
    - kind: references
      target: /assessments/b2-p2-fresh-session-and-effect-authority-findings.md
    - kind: references
      target: /failure-modes/post-effect-current-state-drift.md
---

# C4-v0 readiness predicate experiment

## Hypothesis under test

> Can `READY` become a deterministic, fail-closed, read-only result over existing
> evidence, rejecting the historical false-ready states without introducing
> unacceptable false blocks, maintenance surface or human-attention cost?

## Boundary

The predicate is Gnostoa self-tooling under
[Decision 0017](../decisions/0017-scope-the-readiness-predicate-experiment-to-gnostoa-self-hosting.md).
It lives entirely in `tests/`, is not a supported tool, an inherited schema, a
generic guardrail or an adopter contract, and the pinned public-surface digest is
byte-identical to protected main at
`sha256:021f18107feb93be2d4c6e5d8dca7d73bf2247871fc100859ba576089f55772b`.
Adopting projects inherit nothing from this experiment.

## Method

Twelve controls were replayed against real commits that exist in this
repository. No control is synthetic.

**Eight negative controls** are the false-ready states recorded in the canonical
B2/P1 (five) and B2/P2 (three) assessments. The three P2 commits are named in the
P2 record itself. The five P1 commits are **matched**, not quoted: the P1 record
describes each state but names no commit, so each was mapped to the head that
preceded the commit repairing that exact defect. That mapping is an inference and
is labelled as one.

**Four positive controls** are candidates the owner actually reviewed and
accepted: the integrated P1 candidate, the P1 close-out, the P2 close-out
candidate reviewed in 7 of 20 minutes, and the integrated P2 close-out.

The evidence corpus is exactly what already exists: envelope bytes at a commit,
the schema as it stood at that commit, repository blobs, and read-only Git
history. Nothing is fetched, written or repaired. Every read goes through
`git cat-file`/`rev-list` against an isolated materialization of only the blobs a
check needs.

## The minimum precondition set

Four preconditions, each derived from a control that actually violated it.

| | Precondition | Derived from |
|---|---|---|
| PC1 | The envelope validates against the schema as it stood at that commit | P2-2, schema-invalid while claiming owner review |
| PC2 | `checkpoint.previous` recomputes against the preceding recorded version, and `sequence` follows it | P2-2 and P2-3, invented checkpoint digests |
| PC3 | Every declared dependency identity recomputes from the blob its reference names | P2-3, two wrong declared dependency identities |
| PC4 | A non-terminal envelope is the version recorded by the candidate itself | P2-1, envelope at `sequence: 1` while the work was already done |

A fifth candidate precondition — terminal-claim self-consistency, from P2-2's
handoff contradiction — was **deliberately excluded**. It rejects nothing that
PC1 and PC2 do not already reject, it would have to match prose, and prose
matching buys false blocks and maintenance surface for no additional coverage.
Minimality was chosen over apparent thoroughness.

Terminal envelopes are exempt from PC4 by design. A frozen envelope legitimately
predates later commits; requiring currency of it would have falsely blocked every
candidate that carries a completed slice.

## Result type

Three-valued, because two-valued cannot be honest here:

- **BLOCKED** — a precondition is decided false;
- **INDETERMINATE** — no precondition is false, but at least one cannot be
  decided from local evidence;
- **READY** — every precondition is decided satisfied.

Fail-closed means INDETERMINATE is not READY. The distinction between *wrong
evidence* and *absent evidence* is the experiment's main finding, and collapsing
it would have hidden that.

## Evidence before implementation

The controls were written and run before the predicate existed: twelve
`ModuleNotFoundError` errors across eight negative and four positive controls.
The suite went green only after implementation, and it now pins the measured
verdicts so a later change cannot silently alter the recorded result.

## Measured result

| Control | Recorded false-ready state | Verdict | Decided by |
|---|---|---|---|
| P1-1 | review-ready while its declared pre-merge gate was unrun | INDETERMINATE | — |
| P1-2 | timed review offered with stale surface accounting | INDETERMINATE | — |
| P1-3 | offered while the recursive-alias blocker was present | INDETERMINATE | — |
| P1-4 | offered while the wider error-boundary family was present | INDETERMINATE | — |
| P1-5 | offered while the source snapshot was neither single nor bounded | INDETERMINATE | — |
| P2-1 | PR #27 opened while the envelope stood at `sequence: 1` | **BLOCKED** | PC3, PC4 |
| P2-2 | owner review claimed while schema-invalid with invented digests | **BLOCKED** | PC1, PC2, PC3 |
| P2-3 | owner review claimed while the suite was red and identities wrong | **BLOCKED** | PC2, PC3 |

| Control | Owner-accepted candidate | Verdict | Undecidable on |
|---|---|---|---|
| POS-1 | integrated P1 candidate, active at checkpoint 8 | INDETERMINATE | PC2, PC3 |
| POS-2 | P1 close-out, terminal at checkpoint 9 | INDETERMINATE | PC3 |
| POS-3 | P2 close-out candidate, reviewed in 7 of 20 minutes | INDETERMINATE | PC3 |
| POS-4 | integrated P2 close-out, terminal at checkpoint 6 | INDETERMINATE | PC3 |

| Measurement | Value |
|---|---|
| False-ready states rejected | **3 of 8** |
| False-ready states called READY | **0 of 8** |
| Owner-accepted candidates reaching READY | **0 of 4** |
| Owner-accepted candidates **failing the experimental contract** | **4 of 4** |
| Owner-accepted candidates BLOCKED, as distinct from INDETERMINATE | 0 of 4 |

The experimental contract required legitimate ready states to **remain READY**.
All four fail it. The last row is therefore not a success statement, and this
result must never be reported as "no false blocks" without stating in the same
breath that **4 of 4 positive controls fail to reach READY**.

## Finding 1: no candidate in Gnostoa's history can reach READY

This is the decisive result. **Every one of the twelve controls declares at least
one provider-side identity** — `provider-body-sha256` or
`github-issue-body-utf8-sha256-v1` for the Issue body — and no local evidence
resolves either. Under strict fail-closed semantics the predicate therefore
returns READY for nothing that this project has ever produced, including four
candidates the owner reviewed and accepted.

The hypothesis asked for rejection of false-ready states *without unacceptable
false blocks*. Measured strictly, the false-block rate on owner-accepted
candidates is 4 of 4. **The strict reading of the hypothesis is refuted.**

Read the other way — treating undecidable evidence as an explicit unmet
obligation rather than a block — the decidable core is clean: 3 of 8 rejected, 0
of 4 falsely blocked, 0 of 8 wrongly called ready. The predicate is sound on what
it can decide and simply cannot decide most of what matters.

The gap is not a coding defect. The envelope's reference model expresses *where a
dependency lives* but not *what locally recorded artifact reproduces it*. B2/P1
already proved the missing piece is constructible: `tests/fixtures/github-issue-24.json`
reproduces the Issue #24 body digest exactly. Nothing in the envelope schema can
say that the fixture is that dependency's local witness, so the predicate cannot
use it. Closing that gap means changing the envelope schema — public surface —
which Decision 0017 places outside this experiment.

## Finding 2: squash-merge integration erases the checkpoint chain

PC2 is undecidable at POS-1 and POS-4 for a reason unrelated to providers: on
protected `main`, each slice's envelope first appears at its squash commit, so
the predecessor version the `checkpoint.previous` digest refers to is not in that
history at all.

The checkpoint chain is therefore unverifiable at exactly the commits that carry
the most authority — the integrated ones. It verifies only inside unmerged branch
history, which is the history the project treats as disposable.

## Finding 3: the experiment reproduced the project's own recurring failure

The controls were written with a `skipUnless` guard for clones without full
history. In the container the guard fired for a different reason: Git refused the
bind-mounted repository with `detected dubious ownership`, the guard read that as
absent history, and **all five control tests skipped while the route reported
`OK (skipped=5)`**. The authoritative verification route was green while the
entire experiment had not run.

This is the same shape as the false-ready states being studied — a readiness
signal that was wrong when issued, with every required suite green. It was found
by reading which tests actually ran, not by any check. The repository's own
`tests/test_repository_scope.py` already carried the `safe.directory` idiom that
fixes it. The guard now refuses to convert a Git refusal into a skip.

## Finding 4: what the predicate structurally cannot see

The five unrejected P1 states divide into two kinds, and neither is a tuning
problem.

**No evidence exists** (P1-1, P1-2). "The declared pre-merge gate was unrun" and
"the surface accounting was measured on a different head" both require evidence
this repository does not keep. `schemas/verification-manifest.schema.json`
declares suite *capabilities*, not *results*, no manifest instance exists
anywhere, and no artifact binds a gate result or a measurement to a candidate
identity. Producing that evidence would mean new CI surface — public surface, and
outside this experiment.

**No evidence could exist** (P1-3, P1-4, P1-5). A recursive-alias blocker, an
open error-boundary family and an unbounded source snapshot are latent product
defects. Every required suite was green each time; the defects were found by
humans and by gates the suites did not run. No predicate over recorded evidence
can reject a state whose evidence is uniformly green and whose defect is real.

This is the same ceiling B2/P2 recorded from the other side: green checks are a
necessary and repeatedly insufficient condition for readiness.

## Finding 5: READY is reachable, and the predicate rewards declaring less

This experiment's own first candidate, `git:95525baa9e9afd428e398482f142fd93b822e140`,
evaluates to **READY** — all four preconditions decided satisfied. It is the
first candidate in this project's history to reach that verdict.

It reaches it for one reason: its envelope declares three `file-sha256`
dependencies and no provider-side identity. Nothing about the work is more
verified than P1's or P2's was. The predicate simply had less to be undecided
about.

That is an adverse incentive, and it is inherent to fail-closed evaluation over
*declared* identities: **declaring fewer dependencies makes READY easier to
obtain.** An envelope that honestly declares the Issue body it depends on is
punished relative to one that omits it. The experiment does not resolve this. Any
future version of this control would have to reckon with it, because the cheapest
way to satisfy the predicate is to declare less rather than to verify more.

The verdict also does not mean the candidate is fit to accept. READY here means
four mechanical preconditions hold. Whether the experiment was worth running, and
whether its result is sound, is exactly the semantic judgement the predicate
cannot make — which is the same boundary B2/P2 recorded.

### It then caught a real defect in this candidate

A later commit in this same branch trimmed the envelope so the derived projection
would fit its declared 6000-character budget, and did not advance the checkpoint.
Re-evaluating returned **BLOCKED** on `checkpoint-chain-recomputes`: the recorded
`previous` no longer matched the version it followed.

That is the predicate rejecting a genuine defect in the work that produced it,
found mechanically rather than by review, and it is the clearest positive
evidence in this experiment. The chain was then advanced properly.

Two bounds were reached while recording all this: `state.completed` saturated at
its 20-item maximum — the third slice in a row to do so — and the derived
projection exceeded its owner attention budget at 6099 characters and was
refused. Neither is a defect in the predicate; both are the same signal the
post-effect drift record already noted, that a current projection is being asked
to carry event history.

## Cost

These figures describe the **experimental implementation used to obtain the
evidence**, which is not retained. See *Experimental implementation versus
retained surface* below.

| Measurement | Value |
|---|---|
| Predicate | 433 lines, `tests/experimental_readiness_v0.py` (removed at close-out) |
| Controls | 244 lines, `tests/test_experimental_readiness_v0.py` (removed at close-out) |
| Public surface added | **none**; the pinned digest is unchanged |
| Fast route, protected main | 124 tests, 3.868 s |
| Fast route, with the experiment | 132 tests, 10.840 s |
| Added verification time | ~7 s against a 10-minute fast-feedback target |
| Human-attention cost when a state is refused | one line per unsatisfied precondition, naming the commit, the declared value and the recomputed value |

Maintenance surface during the experiment was confined to four preconditions and
one three-valued combination rule, reusing `tools.task_envelope` for all schema
and digest work rather than restating it. After the owner disposition that
maintenance surface is **zero**, because the implementation is not retained.

## Experimental implementation versus retained surface

These are deliberately different things, and the distinction is the point of the
close-out.

| | Experimental implementation | Retained after disposition |
|---|---|---|
| `tests/experimental_readiness_v0.py` | 433 lines, the predicate | **removed** |
| `tests/test_experimental_readiness_v0.py` | 244 lines, the twelve controls | **removed** |
| This assessment | the measured evidence | **retained** |
| [Decision 0017](../decisions/0017-scope-the-readiness-predicate-experiment-to-gnostoa-self-hosting.md) | the self-hosting boundary | **retained** |
| `tasks/issue-33-c4v0-readiness-predicate.yaml` | the task record | **retained, terminal** |

The experiment was run, and every number in this record was measured by running
it. The code that produced those numbers is removed because the control was
rejected, and 677 lines of executable maintenance surface are not justified by
evidence alone. Removing it changes no measured result recorded here.

The experiment remains exactly reconstructable from the immutable candidate
`git:4acb357864434abc8b9ef625ec14838847f541aa`, this assessment,
[Issue #33](https://github.com/ktogias/gnostoa/issues/33) and the Change Request
history.

## Verdict against the hypothesis

**Negative on the question as posed, with a precise and useful boundary.**

`READY` cannot presently become a deterministic, fail-closed, read-only result
over existing evidence, because existing evidence cannot decide the provider-side
identity that every candidate declares. Strict fail-closed blocks every candidate
this project has produced.

The strict contract fails in both directions at once: **4 of 4** owner-accepted
positive controls do not reach READY, and **5 of 8** false-ready states are not
rejected. That none of the four is BLOCKED rather than INDETERMINATE is a
distinction about *why* they fail, not evidence that they pass.

What the experiment did establish is narrower and real: deterministic
consistency checks over existing evidence rejected **3 of 8** recorded
false-ready states, and called none of the eight READY, in ~7 seconds with no
public surface. Two of the three were the worst recorded states — an envelope
contradicting its own schema with invented digests, and one declaring dependency
identities that do not match the files it names.

## What is not claimed

- Not that C4-v0 works, is correct, or should be kept.
- Not that the predicate is generic, or that any of this transfers to another
  project. All four preconditions were derived from Gnostoa's own history.
- Not that 3 of 8 is a good result. It is the measured result.
- Not that the P1 control mapping is authoritative; it is inferred from commit
  subjects, as stated above.
- Not that the *predicate* was accepted. The owner accepted the experimental
  result and rejected C4-v0 as a readiness predicate; see Owner disposition.
- Not that anything here changes what adopting projects inherit.
- Not that this candidate's own READY verdict is evidence the experiment
  succeeded, or that the candidate should be accepted.

## Uncertainties

- Whether a locally recorded provider witness — the mechanism B2/P1 already
  demonstrated with a fixture — is worth an envelope schema change, given that
  the schema is public surface and would need its own Decision.
- Whether the checkpoint chain should be verifiable after squash integration at
  all, or whether that is an accepted consequence of squash-merging.
- ~~Whether 3 of 8 coverage justifies keeping 677 lines of self-hosted
  control.~~ **Resolved by the owner disposition: it does not.** Whether the two
  worst rejected states are better addressed some other way remains open, and no
  successor is selected.
- Whether the incentive in Finding 5 — declaring fewer identities makes READY
  cheaper — can be removed at all without making declaration mandatory, which
  would be an envelope schema change and therefore public surface.
- Whether the two evidence classes that do not exist — gate receipts bound to a
  candidate, and measurements bound to their subject — are worth creating, which
  is a much larger question than this experiment.

## Owner disposition

Recorded from the accountable maintainer's review of the exact experiment
candidate `git:4acb357864434abc8b9ef625ec14838847f541aa`.

> **ACCEPT EXPERIMENTAL RESULT — REJECT C4-v0 AS A READY PREDICATE.**

The selected hypothesis is refuted as posed. Existing Gnostoa evidence is
insufficient to compute a useful strict fail-closed `READY` result:

- 3 of 8 reconstructed historical false-ready states are mechanically rejected;
- 0 of 8 false-ready states are incorrectly called READY;
- all 4 historically owner-accepted positive controls remain INDETERMINATE and
  therefore **fail to reach READY** under strict fail-closed semantics.

This must not be reported as "0 false blocks" without also stating that 4 of 4
positive controls fail to reach READY. The experimental contract required
legitimate ready states to remain READY.

### The narrower demonstrated result

> Deterministic consistency checks over existing evidence can detect some
> important state and identity defects before human review.

The evidence includes the predicate catching a real stale checkpoint-chain
defect in the experiment's own branch, mechanically and before review.

**This narrower result is evidence only. It does not activate a replacement
control.**

### C4-v0 is not to be rescued

The experiment is not to be expanded by adding provider witness fields,
task-envelope schema changes, verification receipt schemas, CI-result evidence
classes, mandatory dependency declarations, provider adapters, checkpoint
persistence redesign or public-surface changes. Each is a separate architectural
choice requiring its own evidence and its own Decision.

### Negative findings preserved by the disposition

1. Existing local evidence cannot resolve provider-side identities required by
   historical accepted candidates.
2. Some historical false-ready states correspond to latent product defects for
   which all recorded evidence was green; no predicate over existing evidence can
   infer an unrecorded defect.
3. Squash integration makes historical `checkpoint.previous` chains undecidable
   at authoritative integrated commits.
4. A predicate over declared dependencies creates an adverse incentive:
   declaring fewer dependencies makes READY easier to obtain.
5. The experiment's container guard initially skipped the entire experiment while
   the route reported success; direct inspection caught the false-green result.
6. `state.completed` reached 20/20 for the third consecutive slice.
7. The current projection exceeded its 6000-character attention budget and was
   correctly refused before being reduced.

### Final implementation disposition

| Item | Disposition |
|---|---|
| C4-v0 | **REJECTED AS READY PREDICATE** |
| Narrow consistency-checking finding | RECORDED / NOT ACTIVATED |
| C2 | RECORDED / NOT ACTIVATED |
| C3 | RECORDED / NOT ACTIVATED |
| Decision 0016 increment 2 | NOT ACTIVATED |

**No successor experiment is selected in this close-out.**
