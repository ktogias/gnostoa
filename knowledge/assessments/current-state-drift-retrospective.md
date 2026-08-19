---
type: Source
title: Current-state drift retrospective
description: Bounded read-only retrospective reconstructing Gnostoa's observed drift incidents, near-misses, triggers and controls, separating lifecycle from outcome drift and identity drift from both.
status: draft
generated:
  by: agent:claude-opus-5
  at: "2026-08-19T10:20:00Z"
sources:
  - id: drift-work-item
    resource: https://github.com/ktogias/gnostoa/issues/56
    title: Reduce recurring current-state drift from volatile projections
  - id: post-effect-drift-work-item
    resource: https://github.com/ktogias/gnostoa/issues/29
    title: Reconcile post-effect current-state drift after B2/P2 integration
x-project-knowledge:
  id: kit.assessment.current-state-drift-retrospective
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governed-by
      target: /decisions/0024-separate-stable-navigation-from-volatile-state.md
    - kind: references
      target: /failure-modes/post-effect-current-state-drift.md
    - kind: references
      target: /assessments/b2-p2-fresh-session-and-effect-authority-findings.md
    - kind: references
      target: /assessments/fresh-agent-dogfood-and-routing-precursor-result.md
---

# Current-state drift retrospective

Read-only reconstruction performed at protected main
`4a772f71470d89e2bd8d0dbbfc0f2a85dc4fae5e`. That immutable commit is the whole
observation boundary; the public-surface digest at it is deliberately **not**
restated here, because it is recomputable from that commit with
`knowledge surface-digest` and copying it would create exactly the drift
opportunity this record argues against. No repository or provider state was
mutated while gathering this evidence.

## Drift definition used

Two representations or observations **expected to agree under the applicable
contract** diverge across time, revision, subject, authority, lifecycle state or
identity. A case was admitted only when all six of subject, conflicting
representations, expected authority relationship, temporal or revision interval,
trigger, and material consequence or plausible misdirection could be identified.

Seven important defects were deliberately classified **not drift** rather than
renamed: silent YAML `#` truncation of durable values, the container guard that
skipped five controls under a reported `OK`, the release-smoke false negative, a
record misdescribing what the envelope schema can carry, a secret-scanner false
positive, development-container route asymmetry, and PR #2's critical-path scope
drift. Inflating the corpus would have made every count meaningless.

## Evidence corpus

Durable records only; the large historical provider ledgers were **not** replayed,
because the canonical assessments preserve the needed facts.

- Failure modes: post-effect current-state drift; publication-baseline review
  drift; container-first verification routing bypass.
- Assessments: B2/P1 measurements; B2/P2 findings; control-selection map; C4-v0
  experiment; post-C4 evidence-boundary selection; fresh-agent dogfood and
  routing-precursor result; first source-only release pre-effect state and result;
  first OCI runtime security-boundary evidence; util-linux remediation result;
  self-dogfood bootstrap assessment.
- Decisions 0016, 0017, 0020–0023; the evidence-gated capability-evolution
  lifecycle; the source-only release runbook.
- Current projections: `docs/roadmap.md`, `docs/status.md`,
  `docs/compatibility.md`, `README.md`, `AGENTS.md`, `knowledge/index.md`, the
  three terminal task envelopes, and the test surfaces that encode current-state or
  historical-state expectations.
- Git: full history across all refs; exact diffs of the three reconciliation and
  remediation Change Requests; per-candidate digest reconstruction across the #33
  branch.
- Provider, read-only: Work Item states, state reasons and labels; Change Request
  states; release list.

## Taxonomy

Six categories were kept apart: observed drift; near-miss; trigger or generator;
positive control; mixed control; other failure. Within drift, the dimension was
recorded separately from the family, because one surface can avoid drift in one
dimension and still drift in another.

| Dimension | Count |
|---|---:|
| Identity | 7 |
| Outcome / current projection | 5 |
| Lifecycle | 3 |
| Verification expectation | 3 |
| Resume | 2 |
| Observation | 1 |
| **Admission** | **0** |

Admission drift is zero deliberately. No surface has ever claimed a state was
admitted or authorized when the governing authority did not.

## Counts, with their limitations

| | |
|---|---:|
| Observed drift incidents | 15 |
| Near-misses | 6 |
| Triggers | 11 |
| Positive controls | 11 |
| Mixed controls | 6 |
| Survived integration | 6 |
| Caught before integration | 9 of 15 observed, 6 of 6 near-misses |
| Caught mechanically | 5 |
| Caught by human semantic review | 13 |
| Automated-green-but-semantically-stale | 5 |
| Fresh-actor misdirection cases | 8 |

**Limitations.** These are lower bounds over *durable* evidence. Session-internal
readiness assertions leave no repository or provider trace, so the recorded
false-ready count remains a floor of three rather than a count. The exact moment
at which locally validated state was described as ready while `origin` held an
earlier state is not reconstructable. Any third invented checkpoint identity that
existed only in an uncommitted working tree is unobservable. No figure here is
estimated; where a value could not be reconstructed it is absent rather than
guessed.

## Principal observed cases

- **Post-effect projection drift after a Work Item closed** — three surfaces
  contradicted the provider at once after an authorized merge and closure. The
  reviewed candidate could not have caught it, because each claim became false only
  when the effects landed. Repaired through a dedicated reconciliation slice.
- **The reconciliation's own first candidate predicted its own closure** — a
  resume card and roadmap both asserting that no active delivery item existed while
  that very Work Item was open and selected, on a page that named it as the current
  repair. Automated verification stayed green; human review caught the
  contradiction before a Change Request was opened.
- **The pre-release snapshot nearly froze three claims that flip the instant a tag
  exists** — caught by owner semantic review before the immutable tag was created,
  inside the very commit the tag would name.
- **Self-invalidating dependency declarations** — an envelope declaring a file as
  an immutable dependency while its own authorized scope edited that file. Observed
  twice, in two different slices, plus once in the checkpoint form.
- **A provider label outlived its Work Item's closure** — see below.
- **A durable record named the wrong historical commit** — see below.

## Live findings at the retrospective boundary

Three defects were live at `4a772f71`, and are the repairs this slice owns.

### D14 — outcome / current-projection drift

`docs/roadmap.md` stated that under Decision 0022's vendor-fixed-component rule
"the current measured OCI candidate is **not admitted** for publication until the
demonstrated blocker is remediated", while the candidate-bound remediation result
records that the demonstrated vendor-fixed util-linux blocker **was cleared for the
measured `linux/amd64` candidate** and the owning Work Item was closed as
completed.

The bottom-line admission verdict remained true — for a different reason. The
stated reason was one result behind, the subject "the current measured OCI
candidate" was unbound, and the page stated neither that the blocker had cleared
nor that complete OCI readiness remains unestablished. The plausible harm is
precise: a fresh actor concludes that util-linux remediation is outstanding and
reopens it.

The mechanism is the instructive part. The Change Request that cleared the blocker
edited the **adjacent** sentence in the same paragraph — applying lifecycle
neutrality correctly — and left this one untouched.

### D16 — incorrect historical negative-control identity

The fresh-agent dogfood record named `50250b3ad95e6845f72b7c5608d84d66cc200b35` as
the pre-correction candidate whose declared Decision-0016 digest was stale. Replay
shows that commit is the **correction**; its parent
`bd5307f48199949c85e81223e3c49e5b4486d6fb` is the candidate that exhibits the
property. The consequence is that the project's designated historical replay corpus
named a commit on which any future replay would silently pass. Corrected in that
record, with the route-level disposition unchanged.

### D12 — stale provider lifecycle label

Issue #1 was CLOSED / COMPLETED while still carrying `roadmap:now`, the label that
denotes current publication-critical work, from 2026-08-15 until this slice. It was
masked from every entrance gate used to date, because those queries filter on open
state. The label-removal step *was* applied at other closures, including #50 and
#54; it was simply never applied here.

## Contested classification, preserved rather than resolved

**Decision 0016's resume card is recorded as a hardening opportunity and a scope
ambiguity, not as an unquestioned false OCI-state assertion.** Its delivery row
had not been updated across four later slices, and a fresh actor could read it as
a global project-status mirror. But its content is scoped to the human-agent
capability loop, it states truthfully that the named experiments completed and
that no successor control was selected, and no individual claim in it was shown
false. Treating it as a proven defect would have overstated the evidence. It was
therefore **type-hardened** — the row narrowed to capability-loop state, with
delivery navigation routed to the roadmap and lifecycle to the provider — rather
than "caught up" with release or OCI history.

The same restraint applies to `docs/status.md`, which was **incomplete** relative
to newer work but contained no statement shown false, and to
`docs/compatibility.md`, whose `Current baseline` heading over a `v0.1.0`-bound
digest was **not** demonstrated materially false and was deliberately left
unchanged for later evidence.

## Lifecycle drift is not outcome drift

This distinction is the retrospective's central result.

| | Lifecycle-state drift | Outcome / effect-result drift |
|---|---|---|
| Example | source says a Work Item is active; the provider says closed | source says a blocker remains uncleared; the authoritative integrated result says it cleared |
| Authority | the provider — structured, queryable, mechanically comparable | a candidate-bound result record — semantic, not mechanically comparable to prose |
| Mitigation demonstrated | temporally neutral relationship wording | none, until this slice |

The clean measurement: after the bounded remediation Work Item closed, the
sentences "remediation is tracked by #54" and "provider state remains authoritative
for that Work Item's lifecycle" remained true **with no edit**, while the adjacent
copied outcome verdict did not. **Lifecycle mitigation succeeded; outcome
mitigation failed; both in one paragraph.** That is why this case is classified a
**mixed control** rather than a positive one.

## Identity drift is a separate family

Identity and dependency-binding drift is the **most frequent** family in the
record and shares no root with the projection families. It has no external
lifecycle transition: a declaration is either wrong at creation, or becomes stale
because the slice's own authorized scope edits the file it declares. Neither
lifecycle-neutral nor outcome-neutral wording would prevent a single case of it.

Its detector already exists, is deterministic, and works: the dependency
recomputation rejects a stale declared identity with an exact diagnostic and emits
no projection. What is missing is not a mechanism but a reliable route and an
authoritative binding — the boundary Decision 0019 refuted as posed.

Resume, verification-expectation and observation drift are separate again.
Verification-expectation drift even runs backwards: the drift *repair* is its
trigger, because removing stale wording breaks a test that pinned it.

**One universal drift mechanism is not justified by this evidence.**

## Controls that worked, and the ones that only half worked

Demonstrated successes: temporally neutral relationship wording; annotated tag
pushed first with the release created against the existing tag under verification;
effect then authoritative read-back then reconciliation then close the Work Item
last; preserving a truthful pre-effect record and adding the result alongside it;
keeping candidate-time vendor observations out of Decisions; separating the
immutable release identity from later source; the dependency recomputation when it
is actually invoked; replacing pinned stale literals with semantic invariants;
inspecting every provider parsing surface for closing keywords; and bounded human
semantic review, which caught the majority of everything.

Mixed results, recorded honestly:

- the Change Request that removed a stale lifecycle assertion **introduced** the
  copied outcome sentence that later went stale;
- the record that avoided restating a mutable digest left that value recorded
  **nowhere** in the repository — drift prevented, orientation lost;
- the resume card's route delegation stayed correct while the card's own content
  drifted;
- label hygiene at closure was applied to some Work Items and not others;
- test pins that correctly keep the historical ledger out of the forward-looking
  roadmap section simultaneously pin a **closed** Work Item into it.

Demonstrated failures: copied volatile outcome state, never mitigated until now;
reconciliation applied unevenly across surfaces; a rendered-body-only check for
closing keywords, which missed the squash commit message as a second parsing
surface; and literal-pinning tests.

## Mechanically decidable versus oracle limit

**Decidable from observations already acquired and bound:** declared task-envelope
dependency digests against the blobs they name; checkpoint-chain recomputation;
the schema digest pattern; whether a closed Work Item still carries a roadmap
label; whether a named historical control commit actually exhibits its recorded
property; and whether a recorded public-surface digest literal equals the
recomputed value.

**Not decidable — oracle limit.** Whether a prose narrative *reads as current*.
Whether a next action contradicts a handoff actor. Whether removing a copy costs
more orientation than it saves. These require human semantic judgement, and the
correct response to the first is to remove the prose copy, not to mechanize the
judgement.

Three of eight recorded false-ready states were latent product defects behind
uniformly green evidence. No evidence mechanism could have rejected them, and
counting them as coverable would be false coverage.

## Observation acquisition and binding gaps

Unchanged by this retrospective and **not bypassed**:

1. A declared provider-side identity has no reproducible local witness, and no
   binding exists from a declared identity to such an artifact.
2. Dependency ID, reference and observation source are structurally independent;
   no contract binds them. This is what refuted the routing precursor.
3. Provider lifecycle and label observations are acquirable and bound, but every
   use couples the check to the provider and the network.
4. The designated historical replay corpus is reachable at the provider only
   through Change Request refs, which a default clone does not fetch.

## Disposition

**E — remove avoidable volatile copies, then measure the residual.**

Rejected with reasons: doing nothing, because three findings were live at a surface
read for resume and the family has recurred; procedural-only hardening, because
deterministic mechanisms that already exist and already worked cover part of the
residual; detection alone, because a drift opportunity that can be deleted should
not be detected forever; and declaring the families too different to act on,
because the two projection dimensions do share one root even though the others do
not.

**Half 1 was selected, and the slice that records this retrospective carries
it**: repair the three live findings, record the authoring discipline in
[Decision 0024](../decisions/0024-separate-stable-navigation-from-volatile-state.md),
harden the three named navigation surfaces, and test whether useful orientation
survives with a fresh read-only actor.

**Half 2 — the bounded read-only audit — is not admitted.** It requires a separate
owner disposition after Half 1's residual is measured. Its candidate checks remain
research inputs only: surface-digest literal consistency, non-terminal dependency
recomputation, and closed Work Items carrying roadmap labels. No script is
selected, and no `tools/`, `ci/`, `policy/` or review-boundary change is admitted.

## Frozen OCI resume checkpoint

Preserved here as orientation only. **This is not a Decision and creates no
authority.**

Governing: Decision 0022, the first OCI security and residual-risk boundary;
Decision 0023, the bounded util-linux remediation. Work Items #50, #52 and #54 are
closed as completed and their Change Requests are integrated. Established: the
demonstrated vendor-fixed util-linux blocker is cleared for the measured
`linux/amd64` candidate; nine already-installed util-linux-derived packages were
upgraded; no package was added or removed; no unrelated package version moved; the
documented runtime security boundary is unchanged. Identity: `v0.1.0` remains
exactly `ee808572d3930ec3dc50d350ae1ed25a0236bb6b`; the post-remediation source is
**not** `v0.1.0`; a new immutable source identity is required before eventual OCI
publication; no future source version, tag or release is selected. Not established
or not authorized: complete OCI readiness; complete image security; OCI
publication; `deployable_artifact` remains `false`; no registry is selected.

Remaining OCI gaps stay separate and unprioritized: licence and legal conclusion;
CPython vulnerability binding; `pip` vulnerability binding; Gnostoa-source
vulnerability assurance; Debian source packages outside tracker coverage;
non-amd64 evidence; registry identity; registry permissions and read-back;
image-digest reproducibility; OS-package archival and byte reproducibility;
provenance; signing; attestation.

The OCI resume point after drift work is to **select or assess the next remaining
OCI evidence or preparation gap** — not to reopen util-linux remediation, not to
create a source release, and not to publish. **No OCI preparation was performed or
resumed by this retrospective or by the slice that records it.**
