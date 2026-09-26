---
type: Source
title: Documented convergence inference for candidate Pull Requests
description: Research assessment on measuring whether a candidate Pull Request is converging, using published flow and defect-density practice, with the PR 319 measurement as its worked case and explicit preconditions for when no verdict is possible.
status: draft
generated:
  by: anthropic/claude-opus-5
  at: "2026-09-25T22:10:00Z"
sources:
  - id: work-item
    resource: https://github.com/ktogias/gnostoa/issues/322
    title: Establish documented convergence inference for candidate Pull Requests
  - id: owning-objective
    resource: https://github.com/ktogias/gnostoa/issues/15
    title: Automate deterministic knowledge-workflow mechanics without weakening assurance
  - id: inspected-main-revision
    resource: https://github.com/ktogias/gnostoa/commit/63fb3e7bf7a929c755250e6112f5a43a2b3db5c7
    title: Inspected Gnostoa protected-main revision
  - id: ariadne-checkpoint
    resource: https://github.com/ktogias/gnostoa/issues/14#issuecomment-5810150467
    title: Latest Ariadne checkpoint at time of research
  - id: worked-case
    resource: https://github.com/ktogias/gnostoa/pull/319
    title: PR 319, the first Gnostoa candidate that did not reach zero open review threads
  - id: measurement-record
    resource: https://github.com/ktogias/gnostoa/pull/319#issuecomment-5839850952
    title: Full-history flow measurement of PR 319
  - id: per-finding-audit
    resource: https://github.com/ktogias/gnostoa/pull/319#issuecomment-5839243810
    title: Per-finding audit correcting the open-thread characterisation
  - id: substantive-remeasurement
    resource: https://github.com/ktogias/gnostoa/pull/319#issuecomment-5844578031
    title: Re-measurement on substantive closure, which inverted the verdict
  - id: littles-law
    resource: https://web.eng.ucsd.edu/~massimo/ECE158A/Handouts_files/Little.pdf
    title: Little J.D.C. and Graves S.C., Little's Law
  - id: cfd-arrival-departure
    resource: https://getnave.com/blog/arrival-and-departure-rates/
    title: Reading arrival and departure rates in the cumulative flow diagram
  - id: relative-churn
    resource: https://www.microsoft.com/en-us/research/wp-content/uploads/2016/02/icse05churn.pdf
    title: Nagappan N. and Ball T., Use of relative code churn measures to predict system defect density, ICSE 2005
  - id: defect-removal-efficiency
    resource: https://www.ppi-int.com/wp-content/uploads/2021/01/Software-Defect-Removal-Efficiency.pdf
    title: Jones C., Software Defect Removal Efficiency
  - id: srgm-overview
    resource: https://www.sciencedirect.com/topics/computer-science/software-reliability-growth-model
    title: Software reliability growth models, overview
  - id: srgm-exponential
    resource: https://www.ece.uvic.ca/~itraore/seng426-07/notes/qual07-8.pdf
    title: Reliability growth models and the exponential (Goel-Okumoto) model
  - id: review-size
    resource: https://static1.smartbear.co/support/media/resources/cc/book/code-review-cisco-case-study.pdf
    title: Cisco/SmartBear code review case study, 2,500 reviews over 3.2M LOC
x-project-knowledge:
  id: kit.assessment.pr-convergence-measurement
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governed-by
      target: /decisions/0018-adopt-evidence-gated-capability-evolution-for-gnostoa-self-governance.md
    - kind: governed-by
      target: /decisions/0062-require-proportionate-prior-art-and-reuse-review.md
    - kind: references
      target: /decisions/0016-evolve-human-agent-workflow-through-bounded-self-hosted-slices.md
    - kind: references
      target: /requirements/retrospective-findings-require-explicit-admission.md
    - kind: derived-from
      target: /assessments/15-l0-lite-observed-workflow-baseline.md
---

# Documented convergence inference for candidate Pull Requests

## Why this research exists

Gnostoa reads several candidate signals — provider checks, unresolved review
threads, reviewer recommendations, R2A advisory outcome. None of them answers
*is this candidate converging*, and PR #319 showed that all of them can point the
wrong way at once.

At the measured head #319 had complete green CI, an implementation measuring
1.6 findings per KLOC, and a median finding-to-fix latency of 23 minutes — while
the open-thread count climbed monotonically toward 36. Re-measured on fixes rather
than resolve clicks, live defects were **3**. The tracker overstated them roughly
twelvefold, and four successive analyses of this candidate reported the tracker's
divergence as the work's.

That error is the reason this assessment exists. The measures below are not
difficult; choosing the wrong departure series makes all of them wrong at once.

This assessment records what published practice already offers for that
question, what it says about #319, and what it cannot say.

## Prior art and remaining need

Decision 0062 requires a proportionate prior-art review before custom work.

Inside Gnostoa, `15-l0-lite-observed-workflow-baseline.md` already derives
workflow quantities from receipts under the same owning objective #15, including
branch churn and exact-head convergence receipts. It is a *receipt-derived
baseline*: it records what happened on specific candidates. It does not define a
measure of whether a candidate is converging, and it has no stopping rule.
`b2-p1-streamlined-self-hosting-measurements.md` measures self-hosting effort,
not review flow.

Outside Gnostoa, the question is well covered by four independent literatures —
queueing/flow, defect-density prediction, defect-removal efficiency and software
reliability growth. None needs to be re-derived. The remaining need is narrow:
selecting the subset computable from provider-observable data, and stating the
preconditions under which each one is meaningless.

## The four literatures and what each contributes

### 1. Flow — arrival, departure, and Little's Law

A cumulative flow diagram plots cumulative arrivals against cumulative
departures; the vertical gap is work in progress. The canonical reading is that
**parallel lines mean a stable system and diverging lines mean accumulating
flow debt**. Little's Law relates the three quantities as
`WIP = arrival rate × cycle time`.

The operational form for our purpose is the utilisation ratio:

> **ρ = λ / μ**, where λ is finding arrival rate and μ is finding closure rate.

Any queue with ρ > 1 grows without bound. This is a definition, not a heuristic,
and it is the closest thing to a single-number convergence test.

### 2. Defect density — relative churn, not absolute

Nagappan and Ball (ICSE 2005) established on Windows Server 2003 that **absolute
churn is a poor predictor of defect density while relative churn predicts it at
89% accuracy**. The methodological consequence for us is direct: *findings per
commit* is not a valid series. *Findings per KLOC added* is.

This also gives the measure that exposes a repair treadmill: comparing finding
density of remediation commits against implementation commits.

### 3. Defect removal efficiency

Jones defines DRE as the share of defects removed before delivery, with
best-in-class above 95%. Taken alone it is a lagging summary. Its value here is
in a *pair*: DRE computed from the tracker versus DRE computed from the code.
The gap between them measures tracker drift, which no single-number DRE exposes.

The PR 319 measurement promoted this from a supporting measure to **the primary
one**. Every other measure in this set is computed from an arrival and a departure
series; if departures are read from the tracker, every one of them is wrong by the
size of the gap. On PR 319 that was 54 points, and it inverted the verdict. The
paired form is therefore not an extra check — it is the precondition for trusting
any of the rest.

### 4. Reliability growth — and its precondition

Goel-Okumoto and the Rayleigh family model cumulative defects as
`m(t) = a(1 − e^{−bt})`: a **concave** curve saturating at total defect content
`a`, from which remaining defects and time-to-target are estimated.

The precondition matters more than the model. These models assume a **fixed
defect population with no new code introduced during the observation window**.
A convex cumulative arrival curve, or a growing subject, violates the assumption.
This yields the most important negative result in this research: *there are
states in which "how many findings remain" is not estimable*, and an honest
instrument must say so rather than fit a curve anyway.

### 5. Review size, as a sanity bound

The Cisco/SmartBear study (2,500 reviews, 3.2M LOC) found detection effectiveness
falling off above **200–400 LOC per review** and above ~500 LOC/hour. This is not
a convergence measure but a validity bound: past it, a flat finding rate may
reflect reviewer saturation rather than code quality.

## Worked case — PR 319

54 review threads over 41 hours, 38 commits. Measured from the GitHub API.

The candidate was first measured on **tracker** state — a thread counts as closed when
it is resolved. It was then re-measured on **substantive** state: for each finding a
code detector was built for the mechanism the finding asked for, and the commit history
bisected for the first commit after the finding was raised in which that mechanism is
present. Departure is that commit, not a resolve click.

The two bases disagree on the verdict:

| Measure | Tracker basis | Substantive basis |
|---|---|---|
| Departures of 54 arrivals | 18 | **47** |
| Live items | 36 | **7** |
| ρ = λ/μ overall | 3.00 | **1.15** |
| ρ trailing 12 h | ∞ | **1.33** |
| DRE | 33% | **87%** |
| WIP shape | 0 → 36, monotonic | 0 for 22 h, then flat at **5–7** for 14 h |

On the tracker basis the candidate looks unstable. On the substantive basis it is a
bounded queue slightly above equilibrium, with **median fix latency of 23 minutes**
(p90 83 min). Of the 7 live items, 3 were code defects raised six minutes before
measurement and 4 were documentation.

**This is the finding that matters most in this research.** Every alarming figure in
the first measurement — ρ = 3.00, ρ = ∞, WIP climbing without bound — was the tracker
diverging from the work. A 54-point gap between substantive and tracked DRE produced
all of them.

### What the substantive measurement still shows as wrong

Two things survive the correction, and neither is the queue:

1. **Arrival is genuinely accelerating** — 0.83 → 1.81 findings/h across the halves,
   so the cumulative curve is convex. Departures keep pace, so this is not instability,
   but it does mean no reliability-growth model can estimate what remains.
2. **Remediation is 10.9× denser in findings than the implementation it repairs** —
   17.5/KLOC across 23 remediation commits against 1.6/KLOC for the original
   implementation. This is the arrival driver, and it is why the curve is convex
   rather than saturating.

## Proposed instrument set

Computable from the GitHub API with no new runtime dependency.

| # | Measure | Source literature | Healthy |
|---|---|---|---|
| 1 | ρ = λ/μ over a trailing window, **computed on substantive departures** | flow / Little's Law | < 1 |
| 2 | Cumulative arrival vs departure series | CFD practice | parallel |
| 3 | Findings per KLOC added, per commit | relative churn | declining |
| 4 | Curvature of cumulative arrivals | SRGM precondition | concave |
| 5 | **Tracked DRE − substantive DRE** — the primary measure | DRE, paired | ≈ 0 |
| 6 | Remediation : implementation density ratio | relative churn | → 1 |
| 7 | Review size per pass | review-size study | 200–400 LOC |
| 8 | Yield decay across passes on a **frozen** head | SRGM, properly conditioned | → 0 |

**Proposed stopping rule.** A candidate is converged when ρ < 1 is sustained,
cumulative arrivals are concave, tracked DRE ≈ substantive DRE, and yield on a
frozen head decays to zero across successive passes.

**Proposed refusal rule.** When arrivals are convex or the subject is still
growing, the instrument reports *no verdict possible* and names the violated
precondition. It does not emit a number.

## Known limits of this research

- Departure timestamps are a **proxy**. GitHub exposes no `resolvedAt` on a
  review thread; the last comment time is used. Measure 5 is therefore the
  weakest of the eight and should carry its uncertainty forward.
- The worked case is a single candidate. The instrument set is *not* validated
  until it reproduces #319 from raw data and correctly declines to label #312
  and #314 — both of which converged — as divergent.
- A flat arrival curve over eleven heads is evidence, not proof, of an
  unbounded finding supply. Measure 8 on a frozen head is the experiment that
  would distinguish the two, and it has not been run.
- Substantive DRE required reading the code to decide whether each finding was in
  fact repaired. On PR 319 this was done by writing a per-finding code detector and
  bisecting the commit history, which is reproducible and was accurate enough to
  invert the verdict — but the detectors were written by hand from each finding's
  text. Whether that authoring step can be mechanised is **the central open question
  of this research**, because measure 5 is the precondition for every other measure
  and it is the only one that currently needs human judgment.
- Two of the detectors were initially mis-escaped and wrongly reported their finding
  as unfixed. Detector authorship is therefore itself a failure surface, and any
  instrument built on this method needs a positive control — a finding known to be
  unfixed — to catch a detector that never matches.

## Admission boundary

This assessment is **knowledge-only**. It defines no gate, no required check and
no reviewer-facing automation, and it changes nothing in R2A, Decision 0067/0089
semantics or merge authority. A convergence verdict is advisory evidence and
never an approval.

Implementation is admitted only through the separate owner/admission step
recorded on [#322](https://github.com/ktogias/gnostoa/issues/322), under
[the explicit-admission requirement](../requirements/retrospective-findings-require-explicit-admission.md).
