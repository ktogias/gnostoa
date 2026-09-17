---
type: Source
title: JEPA-inspired operational world model for Gnostoa
description: Source-backed assessment of how Gnostoa can evolve from evidence-bound operational state through deterministic transition replay and shadow prediction toward an optional learned world model, without transferring authority or changing Ariadne order.
status: draft
generated:
  by: openai/gpt-5
  at: "2026-09-17T11:19:30Z"
sources:
  - id: operational-world-model-work-item
    resource: https://github.com/ktogias/gnostoa/issues/273
    title: Evaluate a JEPA-inspired operational state-transition model for bounded planning
  - id: inspected-main-revision
    resource: https://github.com/ktogias/gnostoa/commit/e071ab60a418eddda5bf008004ee96faafbf1e7c
    title: Inspected Gnostoa protected-main revision
  - id: ariadne-v9
    resource: https://github.com/ktogias/gnostoa/issues/14#issuecomment-5706634917
    title: Consolidated Ariadne v9 roadmap checkpoint
  - id: i-jepa
    resource: https://arxiv.org/abs/2301.08243
    title: Self-Supervised Learning from Images with a Joint-Embedding Predictive Architecture
  - id: v-jepa-2
    resource: https://arxiv.org/abs/2506.09985
    title: V-JEPA 2
  - id: leworldmodel
    resource: https://arxiv.org/html/2603.19312v1
    title: LeWorldModel
  - id: worldcoder
    resource: https://arxiv.org/abs/2402.12275
    title: WorldCoder
  - id: executable-world-models-arc
    resource: https://arxiv.org/html/2605.05138v1
    title: Executable World Models for ARC-AGI-3
  - id: webdreamer
    resource: https://arxiv.org/abs/2411.06559
    title: WebDreamer
  - id: code-world-model
    resource: https://arxiv.org/abs/2510.02387
    title: Code World Model
  - id: swe-world
    resource: https://arxiv.org/abs/2602.03419
    title: SWE-World
  - id: dreamerv3
    resource: https://doi.org/10.1038/s41586-025-08744-2
    title: Mastering diverse control tasks through world models
  - id: mopo
    resource: https://arxiv.org/abs/2005.13239
    title: Model-based Offline Policy Optimization
  - id: magentic-one
    resource: https://microsoft.github.io/autogen/stable/user-guide/agentchat-user-guide/magentic-one.html
    title: Magentic-One documentation
x-project-knowledge:
  id: kit.assessment.jepa-inspired-operational-world-model
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
      target: /requirements/bounded-behavioral-traceability.md
    - kind: derived-from
      target: /assessments/post-c4-evidence-boundary-selection.md
    - kind: derived-from
      target: /assessments/b2-p2-fresh-session-and-effect-authority-findings.md
---

# Gnostoa: from verifiable project knowledge to an operational world model

Research and architecture proposal — 17 September 2026.

**Status:** source-backed research/proposal for [#273](https://github.com/ktogias/gnostoa/issues/273). This knowledge-only record and its non-disruptive linkage into Ariadne are selected. It does not admit predictor or planner implementation, execution of E0–E4, a public-contract change, a roadmap-order change, or any other authority. Proposed types, experiment names, and budgets are neither existing contracts nor binding decisions.

## 1. Conclusion

The direction is highly relevant to Gnostoa, provided that three layers remain distinct:

1. **Verifiable operational state:** what is currently known, from which sources, for which exact subject, and with which unresolved obligations. Gnostoa already has substantial foundations here.
2. **Explicit transition model:** what an action is expected to change, what it invalidates, what must be observed afterward, and how execution continues when the outcome diverges. This is a natural specialization of the planned L1/L2 path.
3. **Learned predictive world model or JEPA:** statistical prediction of consequences and possibly action planning. This is a later research hypothesis, not a current prerequisite.

The recommended direction is **an evidence-grounded operational model first, with learned prediction only after measured need**. Gnostoa does not need a new JEPA subsystem beside L1. It needs explicit, testable descriptions of observations and transitions that L1 and L2 must handle in any case.

The central research question is not whether embeddings can be used. It is:

> Does an explicit model of consequences improve progress, recovery, and supervision cost beyond the benefit of a correct, compact projection of current state?

## 2. Inspected baseline and current project position

The research used a fresh provider read-back and inspected source at protected [main e071ab60a418eddda5bf008004ee96faafbf1e7c](https://github.com/ktogias/gnostoa/commit/e071ab60a418eddda5bf008004ee96faafbf1e7c). At the inspection cut, the sole open Work Item carrying roadmap:now was [#262](https://github.com/ktogias/gnostoa/issues/262). Its selected work is agreement between declared and actually enforced Ruff scope, not world-model development.

- [#270](https://github.com/ktogias/gnostoa/pull/270) was merged and connects the roadmap to consolidated Ariadne v9. It does not implement a controller.
- [#272](https://github.com/ktogias/gnostoa/pull/272) was open and unmerged at head 1159858f6b8be09ec99faab8faf96c81570d74c4. This research did not rerun or certify its complete CI and review convergence.
- The P2b rolling-trust exit is recorded by [Decision 0080](https://github.com/ktogias/gnostoa/blob/e071ab60a418eddda5bf008004ee96faafbf1e7c/knowledge/decisions/0080-complete-r2a-p2b-rolling-trust-exit-by-negative-readback.md). That does not establish full reviewer qualification or completion of #11.
- The [Q0 checkpoint](https://github.com/ktogias/gnostoa/issues/10#issuecomment-5706402207) and protected qualification snapshot retain an empty entries collection. Qualification or independence must not be invented to produce a green result.

The canonical path remains:

**#262 → L0-lite → useful L1 → Q0 and L2 independently or in parallel → L3 → leverage measurement → #259 → small #266-P0 or defer → re-entry into Phase D.**

L4 remains optional and requires evidence of incremental value. It is not a new mandatory rung. Sources: [Ariadne v9](https://github.com/ktogias/gnostoa/issues/14#issuecomment-5706634917), [full analysis](https://github.com/ktogias/gnostoa/issues/14#issuecomment-5706705782), [ordering clarification](https://github.com/ktogias/gnostoa/issues/14#issuecomment-5706742527), and the [latest provenance addendum](https://github.com/ktogias/gnostoa/issues/14#issuecomment-5711686708).

### Small diagnostic observation

Only the existing orientation projection was run, without writes, at explicit evaluation time 2026-09-17T11:00:00Z:

    python3 tasks/gnostoa_orientation.py       --snapshot tasks/issue-14-orientation.json       --repository-root .       --evaluated-at 2026-09-17T11:00:00Z       --format json

The observed result was exit 1 and STALE, with expired sources, a changed roadmap digest, and a different source commit/tree. The command ran natively as a read-only diagnostic of the existing standard-library tool. It was not a full verification suite and did not establish container parity.

Exact stdout and a separate execution receipt were not retained. The preceding statement is therefore a bounded, correlated research observation; the diagnostic enumeration is the analyst's summary, not a verifiable exact-run artifact. Current provider state and work selection come from the separate provider/source read-back above, not from this execution. The fixed evaluation time, retained input, and linked code permit a new reproduction, which would be a new observation rather than retroactive proof of the unretained stdout.

This outcome is expected: the retained snapshot is historical regression evidence and should not be repaired by deleting its history. It shows an existing local staleness detector. It does not prove that a complete automated provider observer exists or that every consumer will invoke it correctly. See the [orientation implementation](https://github.com/ktogias/gnostoa/blob/e071ab60a418eddda5bf008004ee96faafbf1e7c/tasks/gnostoa_orientation.py).

## 3. The actual relationship to JEPA

The original [I-JEPA](https://arxiv.org/abs/2301.08243) predicts representations of image regions from other regions. By itself, it is not an action controller. [V-JEPA 2](https://arxiv.org/abs/2506.09985) and [LeWorldModel](https://arxiv.org/html/2603.19312v1) connect representation learning to action-conditioned prediction and planning.

The useful principle for Gnostoa is to preserve the information needed to reason about an action's consequences without reproducing the entire history or all raw data.

For example, Gnostoa does not need the full prose of hundreds of comments merely to know that a review applies to an old head. It does need the exact head, review identity, provenance, and applicable review cut. Those fields are not noise to compress away.

| Concept | Gnostoa counterpart | Critical difference |
|---|---|---|
| Observation | Git/provider records, checks, reviews, artifact observations | Partial and asynchronous observations, not a global snapshot |
| Representation | Bounded projection of project/task state | Exact identifiers remain outside latent compression |
| Action | Request review, run a check, mutate, consume evidence | Predictability does not grant execution authority |
| Transition model | Expected changes, invalidations, and read-backs | External events and multiple possible outcomes are normal |
| Prediction error | Divergence between expected and observed outcome | Divergence does not automatically imply a bug or hostile actor |
| Planning | Select a next action that advances the intent | Choices stay inside the already admissible action set |

A dashboard is a projection. A validator checks properties. A reconciler reconstructs and compares state. A **predictive operational model** begins only when action-conditioned expectations are explicit and their predictive utility is tested. These layers should not all be called JEPA.

Research on [bisimulation and task-relevant representations](https://arxiv.org/abs/2006.10742) offers another useful principle: two states may be collapsed only when their differences do not alter relevant consequences. Applying that criterion to Gnostoa is our analogy, not a transfer of an MDP theorem to GitHub.

## 4. Existing foundations and actual gaps

| Area | Already implemented or recorded | What it does not imply | Suitable next use |
|---|---|---|---|
| Canonical knowledge | OKF, stable IDs, ownership, relations, non-weakening profiles | A complete model of actual software behavior | Source-linked task observations and hypotheses |
| Context packs | Deterministic graph traversal and budgets | Markov-sufficient state or semantic completeness | Sufficiency tests for specific decisions |
| Task envelopes | State, checkpoints, dependencies, handoff | Provider enforcement; observations are caller supplied | Collection and binding by the correct observer |
| Self-orientation | Freshness, digest, and Git-subject checks | Continuous provider reconciliation | L1 as a real consumer |
| Capsules | Stages, input digests, downstream invalidation, authority-bound execution | A safe general scheduler for every effect | Reuse only relevant principles and mechanisms |
| R2A | Bound evidence, protected prior-integrated judge, advisory outcomes | Automatic reviewer qualification, acceptance, or merge authority | L1 collection, Q0 qualification, L3 bounded loop |
| Behavioral traceability | Obligations, hypotheses, implementation claims, evidence dependencies | Proof that the correct problem was identified | Operational consequences as falsifiable claims |
| Ariadne and roadmap | Selection, admission, scope, return path | Automatic authorization for a new experiment | Integration under current owners |

Code anchors: [task envelopes](https://github.com/ktogias/gnostoa/blob/e071ab60a418eddda5bf008004ee96faafbf1e7c/tools/task_envelope.py), [context packs](https://github.com/ktogias/gnostoa/blob/e071ab60a418eddda5bf008004ee96faafbf1e7c/tools/build_context_pack.py), [Capsule stages](https://github.com/ktogias/gnostoa/blob/e071ab60a418eddda5bf008004ee96faafbf1e7c/tools/capsule/stages.py), [Capsule authority](https://github.com/ktogias/gnostoa/blob/e071ab60a418eddda5bf008004ee96faafbf1e7c/tools/capsule/authority.py), [one-shot effect claims](https://github.com/ktogias/gnostoa/blob/e071ab60a418eddda5bf008004ee96faafbf1e7c/tools/capsule/effect_claim.py), and [bounded behavioral traceability](https://github.com/ktogias/gnostoa/blob/e071ab60a418eddda5bf008004ee96faafbf1e7c/knowledge/requirements/bounded-behavioral-traceability.md).

### Two precedents that must not be repeated

B2/P2 showed that a good envelope can assist restart while the agent still performs unauthorized provider effects. Recording a rule is not enforcement. See the [B2/P2 findings](https://github.com/ktogias/gnostoa/blob/e071ab60a418eddda5bf008004ee96faafbf1e7c/knowledge/assessments/b2-p2-fresh-session-and-effect-authority-findings.md).

C4-v0 detected 3 of 8 false-ready cases, but none of the four positive controls reached READY; they remained INDETERMINATE. It was not successful merely because nothing unsafe passed. It was rejected and must not return as a world-model readiness score. See the [C4-v0 result](https://github.com/ktogias/gnostoa/blob/e071ab60a418eddda5bf008004ee96faafbf1e7c/knowledge/assessments/b2-c4v0-readiness-predicate-experiment.md).

## 5. Closest experiments and transferable patterns

| Work or source | What it actually tests | What Gnostoa should retain | What must not be transferred |
|---|---|---|---|
| [LeWorldModel](https://arxiv.org/html/2603.19312v1) | Small action-conditioned latent model in control environments | Compact state, next consequence, controlled surprise | Proof of software autonomy or universal small-data sufficiency |
| [WorldCoder](https://arxiv.org/abs/2402.12275) | An LLM writes an executable Python world model and repairs it from observations | Testable transitions, replay, counterexamples | Deterministic-world assumptions and optimism about unknown permissions |
| [Executable World Models for ARC-AGI-3](https://arxiv.org/html/2605.05138v1) | Predicted/observed state comparison and stop-on-mismatch in games | Check after each step; retain competing hypotheses | Prompt-only control where an executor can bypass guards |
| [WebDreamer](https://arxiv.org/pdf/2411.06559) | Predict consequences of web actions before execution | One-step lookahead and replanning | Assuming a longer imagined rollout is automatically better |
| [Meta CWM](https://arxiv.org/html/2510.02387v1) | Coding LLM trained with execution and agent traces | Value of real action/result datasets | A production dependency; the paper states research-use restrictions |
| [SWE-World](https://arxiv.org/html/2602.03419v1) | Real file operations combined with predicted execution/test feedback | Hybrid design and typed observations | Treating simulated PASS as verification evidence |
| [DreamerV3](https://doi.org/10.1038/s41586-025-08744-2) | Policy learning over imagined trajectories with environment feedback | Separate model, policy, and evaluation | A reward of more merges or a direct analogy from games to governance |
| [MOPO](https://arxiv.org/abs/2005.13239) | Offline model-based RL under distribution shift | Conservatism and explicit uncertainty beyond data coverage | A general guarantee for safe GitHub effects |
| [Magentic-One](https://microsoft.github.io/autogen/stable/user-guide/agentchat-user-guide/magentic-one.html) | Task and Progress Ledgers plus replanning on stalls | Separate facts, guesses, and progress; detect stalls | Treat an LLM-authored ledger as authoritative state |

Two findings deserve particular attention:

- In WebDreamer's Online-Mind2Web ablation, horizon 1 scored 37 percent and horizons 2/3 scored 32 percent. Longer rollouts could invent available actions. This is a result for that benchmark, not a universal optimum. For Gnostoa it supports the initial pattern **one prediction → one real action → read-back**.
- SWE-World gives the simulator a ground-truth patch and initial analysis hidden from the agent. That is a privileged surrogate setup. Neither this nor limited predicted-reward accuracy justifies removing real test execution for an unknown pull request.

### Engineering patterns with nearer-term value than new ML

**Reconciliation.** The [Kubernetes controller pattern](https://kubernetes.io/docs/concepts/architecture/controller/) separates desired from observed state and repeatedly reconciles them. Gnostoa should transfer the pattern, not a Kubernetes dependency or the assumption that software tasks are fully declarative.

**Crash and retry semantics.** [Temporal's Activity documentation](https://docs.temporal.io/activity-definition) explains that an Activity may execute more than once even when completion is observed once. Gnostoa should distinguish intention, attempt, and observed effect. This principle does not justify installing Temporal.

**Atomic preconditions.** The [GitHub merge endpoint](https://docs.github.com/en/rest/pulls/pulls#merge-a-pull-request) can require a specific SHA and reject a mismatch. Read-before-act alone leaves a race. A head precondition still does not atomically enforce Gnostoa's review-cut and authority constraints.

**Concurrency.** The [GitHub Actions documentation read on 17 September 2026](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/control-workflow-concurrency) defines the optional queue values single and max. Max permits up to 100 pending runs and cannot be combined with cancel-in-progress set to true. This is date-bound provider-documentation input, not an executed characterization by this research. A concurrency group is still neither a durable transaction ledger nor a universal lock against external actors.

**Interfaces and tests.** [SWE-agent](https://arxiv.org/abs/2405.15793) demonstrates the importance of tool interfaces. [Hypothesis stateful testing](https://hypothesis.readthedocs.io/en/latest/stateful.html) exercises action sequences and invariants. [AgentBoard](https://github.com/hkust-nlp/AgentBoard) measures intermediate progress, while [AgentDojo](https://arxiv.org/abs/2406.13352) evaluates attacks together with completion of legitimate tasks. This report selects none of these frameworks as a dependency.

The reuse assessment concerns ideas and patterns. Importing code, datasets, weights, or services requires a separate, version-bound suitability, license, and cost review. This report grants no such approval.

## 6. Proposed model: know, expect, permit, observe

Gnostoa cannot know all real GitHub state at one instant. It can construct a **partial knowledge model** from identified observations:

**B at time t = reduce(observations through cut t, effective intent, policy, authority)**

It can then estimate:

**predict(B, action) → expected delta, possible outcomes, invalidations, required read-backs**

Finally:

**reconcile(B, action, new observations) → revised belief, discrepancy, next admissible options**

These are proposed logical interfaces, not new public APIs. The transition is generally a relation over possible outcomes rather than a single deterministic world function because people, reviewers, expirations, and provider delays intervene.

### Four separate planes

| Plane | Contents | Source of validity |
|---|---|---|
| Intent, policy, authority | Purpose, non-goals, requirements, effect bounds | Existing Work Items, Decisions, and effective authority |
| Observed and derived state | Source identities, checks, review cut, pending effects | Observations bound to source and time |
| Dynamics and predictions | Expected changes, risks, costs, missing information | Executable rules or explicitly labelled inference |
| Execution and assurance | Guards, actual effects, receipts, review, owner choice | Existing effect handlers, R2A, and human authority |

Knowing that an action is permitted does not show that it is useful. Predicting that it will succeed does not authorize it. A correct workflow does not prove that it solved the right problem.

### Minimal, task-specific representation

Each state needs only fields that affect the relevant decision:

- exact repository, candidate head, base or merge-base, and relevant subject closure;
- effective intent, Decision, and policy generation;
- checks and reviews bound to subject and observation cut, rather than a generic green state;
- qualification and authority identities, scope, expiry, and revocation when relevant;
- pending attempts, run generation, resource ownership, and unknown outcomes;
- evidence locators, completeness, and freshness;
- a small set of unresolved obligations, hypotheses, and next actions.

Provenance, freshness, completeness, and certainty are different dimensions. A record can be observed but stale, or current but partial. They should not be collapsed into one enum or confidence score.

A digest must not include itself or continuously changing irrelevant fields. The relevant closure and its versioning must be defined first. A timestamp changing every second must not invalidate unrelated reviews.

### Example transitions

| Event or action | Mechanically known | Still unknown | Mandatory next observation |
|---|---|---|---|
| New candidate head | Old head-bound results do not prove the new head | Correctness and test outcome | New subject and applicable exact-head checks/reviews |
| New material finding on same head | Prior review cut no longer describes the same evidence state | Whether the finding is valid | Finding, evidence, proposed fix, and reconciliation |
| CI request accepted | A request/attempt exists; PASS does not | Completion, result, correct generation | Exact run, job, attempt, and execution result |
| Timeout after an effect | Outcome may be unknown | Whether the effect happened before response loss | Read-back before a non-idempotent retry |
| New observation published | Control/evidence projection changes | Candidate source subject does not | Currentness-safe publication, not a new source commit |
| Owner intent changes | Same code head may now belong to another scope | Validity of old plan and authority | New generation and refreshed scope check |

Old evidence is not deleted. Its applicability changes. Reuse is allowed only when the relevant subject and use conditions are shown to remain unchanged. See [evidence non-self-invalidation](https://github.com/ktogias/gnostoa/issues/15#issuecomment-5649048174).

## 7. Ownership without a second ontology

| Responsibility | Existing owner | Role of this perspective |
|---|---|---|
| Purpose, priority, admission | Work Item, Decision, owner, #6/#14 | Snapshot; no second IntentStore |
| Fresh provider collection and mechanical continuation | #15/L1 | Explicit observation and reconciliation model |
| Review semantics | #11/R2A | Consume the result; do not create a second judge |
| Qualification and independence | #10/Q0 | Infer nothing from brands or reviewer count |
| Worker and effect validity | #15/L2, #264 | Transition guards in the real effect path |
| Independent checking missions | #263 under #261 boundaries | Falsify claims rather than vote on predictions |
| Product generalization | #259 | Decide what becomes public, remains internal, or is removed |
| Phase D experimental causality | #183 | Do not alter the treatment or oracle |

The existing [composition contract #15 ← R2A](https://github.com/ktogias/gnostoa/issues/15#issuecomment-5648522367) already requires this separation. New records should begin as implementation-private structures composed from existing types. A common public contract should be considered only after two genuinely independent consumers emerge.

### Beyond CI and permissions

Gnostoa's long-term world also includes the project's domain: requirements, components, invariants, dependencies, and competing bug hypotheses. Prediction may be most useful here: which requirement a change affects, which test distinguishes two plausible causes, and which architectural assumption remains unverified.

That does not require a universal simulator. A task-specific, source-linked behavioral model is enough. A latent predictor could later propose likely relationships; they remain inferred until appropriate evidence supports them. The existing behavior map is the safest bridge into this domain.

## 8. Integration into the current Ariadne path

| Stage | Small addition worth considering | Exit criterion | Work that remains closed |
|---|---|---|---|
| #262/#272 | No OWM behavior; retain normalization and candidate-boundary evidence | Complete already-selected work | Scope expansion in the active PR |
| L0-lite | A few real transitions and baseline cost from existing records | Locate state loss, time loss, and UNKNOWN cases | Telemetry platform or full history ingestion |
| L1 | Fresh acquisition, bounded state, rule-based expectations, next action | Useful current view and restart without conversation history | Prediction as authority or broad planner |
| Q0 | Exact qualification and independence provenance | Truthful qualified or unqualified disposition | Manufactured quorum |
| L2/#264 | State/action generation, target binding, fencing, read-back, retry semantics | Reject stale or duplicate effects at their boundaries | General scheduler or unadmitted effect trials |
| L3/#263/#261 | Distinct review missions challenge action claims | Complete bounded loop with measured cost and corrections | Equating more reviewers with independence |
| Leverage gate | Compare to baseline and remove unnecessary machinery | Retain only measured value | Automatic expansion into L4 or JEPA training |
| #259 | Distil into core, guidance, self-only, lab, or retire | A clearer product rather than a larger framework | Premature public world-model ontology |
| #266-P0 | Small provenance/citation work if it fits | Exact claims, then return to delivery | AI branding or promotion without results |
| Phase D | At most common control-plane or shadow support, if allowed | Frozen experiment unchanged | New treatment without new preregistration |

The L1/L2 sequence and bounds follow the [execution blueprint](https://github.com/ktogias/gnostoa/issues/15#issuecomment-5706403186) and [early-value refinements](https://github.com/ktogias/gnostoa/issues/15#issuecomment-5706556769).

### The first useful L1 does not require a green quorum

L1 can truthfully report: this is the head, these checks are pending, these reviews are stale, qualification is not established, and the disposition is INCOMPLETE or QUORUM_UNMET. That is already useful automation. Q0 and the worker lifecycle do not need to be complete before that view is valuable.

L1 is candidate-read-only, not absolutely write-free: updating a PR comment requires bounded authority and stale-publisher protection. An older job must not overwrite a newer projection. Snapshots and evidence belong to the control plane and must not modify candidate head H, or they create a self-invalidation loop.

### #264 is the right place for operational-dynamics characterization

Rerunning a workflow and rerunning one job are not necessarily the same transition. Attempts, generations, prerequisites, and artifacts may differ. [#264](https://github.com/ktogias/gnostoa/issues/264) is the appropriate owner for narrow, harmless provider characterization. It is not a reason to build a general simulator.

### #259 is the product-identity gate

[#259](https://github.com/ktogias/gnostoa/issues/259) defines the direction as Git-native, connected, verifiable operational knowledge with bounded cost. A pattern can become public guidance without becoming a public state-machine engine. Failure of a predictor would not invalidate the value of the knowledge foundation.

## 9. Experimental program with falsifiable hypotheses

E0–E4 are local labels in this proposal. They are not active work items.

### E0 — Representation sufficiency and aliasing

**Hypothesis:** the compact state preserves every distinction that changes the admissible or useful next action.

Build pairs with a similar surface description but different meaning: the same CI-green label for a different head; the same head with a new material review; the same artifact tag with a different digest; the same review text with different provenance; changed intent; incomplete collection versus true absence of results.

Also build pairs that **must** be equivalent: different arrival or enumeration order while retaining identities, source versions, causal order, and the same observation cut; a duplicate observation with the same identity and payload; irrelevant formatting differences. Do not reorder real events or equate conflicting duplicates. This tests excess sensitivity as well as information loss.

Output: a curated fixture matrix with explicit expected discriminations and invariances. No ML or provider writes are required.

### E1 — Offline transition replay and small failure laboratory

**Hypothesis:** explicit transition contracts reduce stale-state mistakes and ambiguous retries without blocking legitimate progress.

Initial corpus: #240 same-head/new-evidence behavior, #257 rolling-trust provider generations, #262/#272 normalization and candidate boundaries, and B2 recovery cases. Do not invent timestamps or owner effort that were not recorded. Mark reconstruction with current knowledge as retrospective.

In a disposable local simulator or fixtures with virtual time, inject:

- head change between observation and effect;
- a new finding without head change;
- duplicate, delayed, and out-of-order wake-ups;
- incomplete pagination, API outage, and expired observation;
- authority change or revocation;
- timeout after the effect and crash before the receipt;
- stale worker result and two workers targeting one resource;
- targeted rerun with a different generation;
- provider SUCCESS while required work is SKIPPED;
- malicious instruction inside an issue, review, or log;
- stale publisher attempting to replace newer state.

Start with the existing test stack and a small reference model. Add generated stateful sequences only if they supply additional coverage. Formal model checking may later target one high-risk lease/effect protocol, not all of Gnostoa.

### E2 — Shadow observation and one-step prediction

**Hypothesis:** prediction adds actionable information beyond deterministic state.

The predictor sees only pre-action data, commits its prediction before the outcome exists, and does not send suggestions to an actor who could alter the outcome. It receives no write capability. Evaluate concrete consequences: probable failure category, next observation needed, rework likelihood, or timeout likelihood. Do not score a vague readiness label.

Baselines:

1. current practice without a new model;
2. typed state/projection and current deterministic checks;
3. the same state plus explicit transition expectations;
4. a simple frequency, rule, or nearest-case predictor;
5. a structured LLM predictor only if non-mechanical uncertainty remains.

If the gain appears at baseline 2 or 3, do not attribute it to JEPA. If the predictor merely learns that a new head requires new checks, stop the ML branch.

### E3 — Conservative planning trial

Run only if E2 shows incremental value. Offer two or three admissible choices, horizon 1, a fixed budget, and real replanning after the next observation. A suitable question is which of two reads or diagnostics will distinguish likely causes sooner.

A replay of real history contains the outcome only for the action actually taken. It does **not** show what would have happened under another action. Planner comparison requires a branchable sandbox or a separately preregistered prospective experiment under the same CI and review obligations.

### E4 — Optional JEPA-inspired learned representation

Input: semantic task history and action features. Target: a representation of actual next semantic state, with auxiliary predictions of observable consequences. Exact identifiers, authority, evidence cuts, and predicates remain in a parallel non-compressed channel.

A possible research form is:

**predictor(encoder(history), action) approximates target_encoder(next observation)**

Stop-gradient and anti-collapse choices would require their own evaluation. This proposal selects no architecture, loss, GPU, or model size.

Proceed only with learning curves, adequate task diversity, out-of-distribution tests, comparison against simpler predictors at equal cost, and a demonstrated residual bottleneck. Otherwise keep this branch research-only or remove it.

## 10. Metrics that do not reward the wrong behavior

| Dimension | Measure | Misleading score to reject |
|---|---|---|
| Safety | Unauthorized, stale, or duplicate effects; false-complete | Zero errors because the system refuses everything |
| Progress | Correct next action, legitimate-case completion, recovery | Many checks without completing the task |
| Knowledge | Unknown/conflict detection, observation completeness | High confidence without correct provenance |
| Prediction | Changed-field precision/recall, calibration, abstention | High accuracy from always predicting WAIT or no change |
| Efficiency | Tokens, API calls, latency, reviewer rework | Fewer tokens because required tests were skipped |
| Human cost | Active review time and restart interventions | Fewer prompts but harder review |
| Maintainability | New mechanisms, dependencies, manual mappings | Small temporary gain with permanent complexity |

A reasonable initial engineering budget is 30–50 curated positive and negative controls, inexpensive generated sequences, and 10–20 prospective shadow episodes as they naturally arise. This is an engineering budget, **not statistically sufficient certification**.

Before execution, choose a primary endpoint and minimum useful improvement, such as owner liveness interventions or restart time. Do not redefine success after observing whichever metric improved. For small samples, report counts, paired differences, and uncertainty. Zero violations in a frozen suite are a requirement of that test, not a guarantee of zero real-world risk.

### Data integrity

- Split by complete PR or task and by time; never put lines from the same review thread in both train and test.
- Exclude later solutions, reviews, and ground-truth patches from pre-action context.
- Separate provider/infrastructure failure from code/semantic failure.
- Record policy, schema, environment, and predictor versions.
- Retain negative and inconvenient results.
- Bound raw logs and personal data; include no secrets, hidden oracle, or private reasoning.
- The same model family and common sources can create correlated errors. A different persona is not independence.

## 11. Assumptions, risks, and limits

**Partial observability.** An exact SHA is not an exact world state. Collection across several APIs is not atomic. Define an observation cut, freshness, and revalidation of dependencies that truly matter.

**Safety and liveness together.** A material authority or head mismatch blocks the affected effect. A delayed reviewer permits bounded waiting, re-observation, and unrelated already-admissible work. Do not freeze the whole system for every mismatch. Duplicate or irrelevant observations must not restart gates forever.

**Bounded authority.** Credentials and effect adapters are the actual enforcement boundary. A planner with a direct bypass to GitHub can ignore a correct model.

**Uncertain effects.** After timeout, absence of a receipt does not prove that the effect did not occur. If safe deduplication and read-back are unavailable, keep the outcome unresolved and do not retry automatically.

**Sequence is not causality.** Another actor may cause a postcondition. Keep operation identity, receipt, observed delta, and attribution confidence separate. Projection replay does not reproduce the entire distributed system history. A parameter hash also does not prove that two requests have the same intent; logical operation identity and retry semantics belong in the existing effect contract.

**Unknown domain behavior.** Tests and policies cannot prove a property without an adequate oracle. Compression or a larger model does not solve that epistemic limit.

**Assessor independence.** A candidate must not modify the effective validation or authority assumptions that approve it. Changing a transition model requires versioning, review, and normal admission, not live self-rewriting rules.

**No hosting.** Prefer stateless Actions and bounded GitHub records or retained artifacts with tested retention and recovery. Do not introduce an event bus, owned database, persistent server, or general workflow engine. A hash alone supplies neither authenticity nor availability.

**Cost.** No paid fallback, training job, or external data transfer is admitted without separate selection. Provider quotas cannot safely be promised as permanently sufficient.

**Scope.** [#14](https://github.com/ktogias/gnostoa/issues/14) excludes predictive planning without separate admission. Deterministic expectations already implied by L1/L2 contracts do not authorize a learned planner inside #14.

## 12. Protecting Phase D

Existing Phase D is **neither Gnostoa versus no Gnostoa nor a JEPA experiment**. The frozen comparison is the pre-#182 versus post-#182 behavioral-diagnosis contract, with #170 shared. #14 and #15 are common infrastructure, and their recorded expected direct effect on the arm difference is zero. See the [frozen expectation card](https://github.com/ktogias/gnostoa/issues/183#issuecomment-5681057669) and [linkage boundaries](https://github.com/ktogias/gnostoa/issues/183#issuecomment-5682216176).

Therefore:

1. Add no arm-visible operational prediction or new decision aid to either arm.
2. Change no tasks, repeats, scoring, oracle, or qualification to test this idea.
3. Check common infrastructure or shadow observation for treatment effects; shadow is not free if it materially changes inputs or timing.
4. Evaluate OWM planning causally only in a separate, future preregistered experiment.

## 13. Ariadne record without activation

This knowledge-only record connects to existing owners and creates no competing route:

| Field | Recorded direction |
|---|---|
| Direction | Evidence-grounded operational state and testable action consequences |
| Relationship to v9 | Cross-cutting interpretation and criteria for L0–L3; ordering unchanged |
| First hypothesis | Reduce state drift and recovery/review toil without false readiness |
| First experiment | Small E0/E1 fixture and replay addition in the responsible existing slice |
| Consumer | Useful L1/L2, not a new world-model dashboard |
| Baseline | Same typed state and checks without a predictor |
| Out of scope | JEPA training, new planner, new authority, hosted engine, Phase D treatment changes |
| Admission | Separate selection of a concrete surface/class, required Decision, and pre-implementation evidence |
| Stop/return | If incremental value is absent, narrow or remove it and return to #259/Phase D |

This research does not automatically propose a new issue for every sub-idea. The [explicit-admission rule](https://github.com/ktogias/gnostoa/blob/e071ab60a418eddda5bf008004ee96faafbf1e7c/knowledge/requirements/retrospective-findings-require-explicit-admission.md) permits a knowledge-only hypothesis until a concrete actionable outcome exists. Reuse #15, #264, #263, and #259 for needs they already own.

## 14. Recommended first practical selection

After #262 is disposed, consider one small, non-ML **transition-fidelity experiment** in L0-lite/L1 with three families:

1. Head or intent changes → evidence applicability and worker validity.
2. New review evidence → review-cut reconciliation without changing source.
3. Attempt, timeout, or restart → observe the effect before any retry.

Start with fixtures and replay, then real shadow observation in the already-selected workflow. The question is whether the explicit structure reduces the need to mentally reconstruct state from comments and conversations.

Do not select GPU purchase, model training, Temporal or AutoGen migration, a new general schema, redesign of #272, a second review oracle, or delay of Phase D at this point.

The possible long-term distinction is not that Gnostoa has memory or has JEPA. It is:

> Humans and agents use the same compact, verifiable project view; distinguish what they know from what they predict; and bind every material action to admissible preconditions, expected consequences, and actual verification.

That is consistent with Gnostoa's direction. Whether learned prediction adds value remains an experiment, not a promise.

## 15. Limits of this research

The work inspected live provider state, relevant source code, canonical records, and primary papers or documentation. It did not perform an exhaustive code audit, a new benchmark, or a benefit measurement of the proposed system. Beyond the read-only orientation diagnostic, E0–E4 were **not executed**. Paper results remain results from their own environments. The roadmap integration, architecture, and experimental criteria are this research's synthesis.

## 16. Proposal review record

A separate agent reviewed the synthesis and draft on 17 September 2026 under session attribution synthesis_critic. That was a distinct research assignment, not an authenticated reviewer identity, Q0 qualification, a guarantee of model independence, or human acceptance. Its subject was this proposal, not a new code candidate.

The reviewer found the direction coherent and did not identify silent admission or roadmap replacement after the following repairs. It did not independently reverify every external-paper result.

| Finding | Evidence in the draft | Disposition |
|---|---|---|
| Over-broad order invariance | Initial E0 equated different observation orders without qualification | Corrected in section 9: identities, payloads, source versions, causal order, and cut must match |
| Ambiguous Phase D exclusion | Wording about one arm could permit a change to both | Corrected in section 12: no arm-visible introduction in either arm |
| Planned versus executed characterization | #264 title could be read as evidence of an executed experiment | Corrected in section 8 with no execution claim |
| Delta versus causal attribution | External actors can cause an observed outcome | Added explicit limitation in section 11 |

Research contributions about the roadmap, papers, and engineering patterns were not used as semantic approvals. They remain bound to cited sources and stated limits.
