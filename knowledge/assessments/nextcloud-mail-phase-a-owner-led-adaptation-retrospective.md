---
type: Source
title: Nextcloud Mail Phase-A owner-led adaptation retrospective
description: Formal retrospective of the first positive controlled OWNER-LED Nextcloud Mail adaptation, separating experiment controls, product and validator findings, external evaluation input, H-A scoring and Phase-B implications without rewriting the frozen result.
status: draft
generated:
  by: chatgpt/gpt-5.6-sol
  at: "2026-08-29T14:40:00+03:00"
sources:
  - id: retrospective-work-item
    resource: https://github.com/ktogias/gnostoa/issues/159
    title: Retrospect the first OWNER-LED Mail adaptation experiment
  - id: phase-a-work-item
    resource: https://github.com/ktogias/gnostoa/issues/157
    title: Adapt frozen Nextcloud Mail for the first OWNER-LED Gnostoa trial
  - id: phase-b-work-item
    resource: https://github.com/ktogias/gnostoa/issues/158
    title: Run the first real OWNER-LED Mail task on the accepted Phase-A adaptation
  - id: owner-led-baseline
    resource: https://github.com/ktogias/gnostoa/blob/main/knowledge/assessments/nextcloud-mail-v0-2-0-owner-led-adoption-trial-baseline.md
    title: Nextcloud Mail v0.2.0 owner-led adoption trial baseline
  - id: release-series-retrospective
    resource: https://github.com/ktogias/gnostoa/blob/main/knowledge/assessments/v0-2-0-release-series-and-staged-evidence-retrospective.md
    title: v0.2.0 release-series and staged-evidence transition retrospective
x-project-knowledge:
  id: kit.assessment.nextcloud-mail-phase-a-owner-led-adaptation-retrospective
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governed-by
      target: /decisions/0052-use-staged-evidence-maturity-for-early-adoption-trials.md
    - kind: references
      target: /decisions/0050-separate-adoption-observations-from-readiness-and-owner-disposition.md
    - kind: references
      target: /decisions/0053-require-lightweight-work-item-micro-retrospection.md
    - kind: references
      target: /assessments/nextcloud-mail-v0-2-0-owner-led-adoption-trial-baseline.md
    - kind: references
      target: /assessments/v0-2-0-release-series-and-staged-evidence-transition-retrospective.md
---

# Nextcloud Mail Phase-A owner-led adaptation retrospective

## Observation and evidence boundary

This retrospective analyzes the completed Phase-A controlled consumer-surface adaptation recorded in Work Item #157. It does not rerun the adaptation, change its frozen candidate, execute the later real Mail development task, contact upstream, or convert findings into implementation admission automatically.

The accountable owner result remains:

| Authority | Exact identity or result |
|---|---|
| Gnostoa source commit | `39aa4f25bdf46811600d4a0f6f9c0da52b73c542` |
| Gnostoa source tree | `866c8c489c9052c566bd65b6e798567d4a284f16` |
| Gnostoa public-surface digest | `sha256:a85ac8dde00f1ed8fb0425de08597828e97c246ec17ce6556f3f222b27ddb1c1` |
| Sanitized projection archive | `sha256:61ab71c5926b6dbd3f4c7eeea23ddefa2bc8a96b55c066f91464ea01170cd5b4`, 849920 bytes |
| Frozen Mail base commit | `b54bd0e637497217e8fec85ad59fe8bdf58e52a8` |
| Frozen Mail base tree | `b400a791f90415f2ce761c2f8412bcd4d6cded5e` |
| Accepted adaptation tree | `97f0e0a44621e029af5bb3c360b397cd0ef993bf` |
| Exact candidate patch | `sha256:d63c0cf0746ae21375c8880c245d3d7ca76426e141f00148614458208102fc8e`, 824871 bytes |
| Project-owned manifest | `sha256:618a1a171c5751c4203ba205599f2efce8c8e5f19c0fd8ec9b5fbd727f271817` |
| Retained-evidence manifest | `sha256:310e68cd2c51721bfd7cf3b0befd9a6623350832c26580e440fd2c25a476a63e` |
| Adaptation session | OpenCode 1.18.25, `opencode/big-pickle`, `ses_fb54487bfffefRkxGK1iGMqEQv` |
| Fresh review session | OpenCode 1.18.25, `opencode/big-pickle`, `ses_fb506400cffeTvzMeXU9povvUv` |
| Owner disposition | `ACCEPT` |
| Predeclared H-A score | `PASS` |
| Practical task utility | `UNKNOWN` until Phase B |

The accepted candidate remains exact experiment evidence. Its known schema-valid all-zero `runtime.image` placeholder is intentionally preserved in that frozen subject; this retrospective does not silently repair it.

### Attributed external evaluation input

Two owner-retained technical-evaluation artifacts informed analysis across the release/adoption series. They are external/model analytical input, not canonical provider truth and not independent-adopter evidence.

Earlier retained artifact:

```text
artifact: Αξιολόγηση Gnostoa(2).html
bytes: 73150
sha256: 430fe5be949c9ff2921a0bde0b5bb22e06439731912c24b14e0e092a5cf68335
displayed report date: 2026-08-27
evaluator identity: not encoded in retained bytes
```

Updated owner-supplied artifact after Phase A:

```text
artifact: Αξιολόγηση Gnostoa1.html
bytes: 98073
sha256: e66b6376eef7fc69e238e9bcbc5b80077722a69bffd6141b659dc980b45034b8
displayed update date: 2026-08-28
author attribution in artifact: Claude (claude-opus-5), requested by human:ktogias
```

The updated artifact usefully integrates the Phase-A result, but provider state and exact run evidence remain authoritative where they disagree with presentation text. In particular, a fresh-context model review is not independent-adopter evidence, 11 means project-owned adaptation paths rather than 11 net-new files, and the roughly 52-minute figure is the substantive session span rather than an exact prompt-to-finish wall-clock measurement.

## Executive result

```text
controlled consumer-surface adaptation      PASS
owner material semantic interventions        0
fresh semantic review                        ACCEPT
project verification                         BLOCKED where prerequisites absent
aggregate adoption readiness                 BLOCKED, rc=3
semantic adoption                            NOT DETERMINED by aggregate gate
owner disposition                            ACCEPT
practical task-solving utility               UNKNOWN until Phase B
full-repository cold adoption                NOT MEASURED
independent adoption                         NOT ESTABLISHED
protocol deviation                           YES: synthetic unresolved runtime image
product/template placeholder defect          CONFIRMED
runtime-lock semantic truth gap               OBSERVED
runner file-write permission weakness         OBSERVED
```

Phase A succeeded at the claim it finally made: a fresh agent could adapt the frozen Mail subject from the admitted sanitized v0.2.0 consumer surface with no material owner semantic intervention, preserve existing project authority, generate deterministic bounded context, report unavailable project suites honestly, and produce a candidate accepted by fresh-context semantic review.

The run also produced stronger negative product-learning evidence than a clean success alone would have provided. The toolkit template encouraged a schema-valid synthetic runtime image, the source-built runtime-lock validator accepted it without observed image binding, and OpenCode's `edit=allow` permitted that semantic write without a human permission checkpoint.

## Factual experiment sequence

### 1. The first experiment design was invalidated before launch

The initial idea was to give a fresh agent the released `v0.2.0` repository. Inspection showed that the release tree itself contains target-specific prior material: `knowledge/assessments/nextcloud-mail-*`, Decisions 0045-0048, and current-facing repository prose naming Nextcloud Mail and summarizing prior failures.

For this target, a fresh model with unrestricted access to the whole tagged repository would not be a clean cold-start agent. Fresh session state cannot compensate for contaminated filesystem input.

The correction was deliberately claim-preserving rather than claim-inflating: build a deterministic sanitized projection from the exact v0.2.0 source, expose only reusable consumer material plus generic adoption navigation/examples, remove Git history and self-knowledge, and explicitly downgrade the experiment claim to **controlled consumer-surface adaptation**. A future true cold-adoption experiment must use a previously unseen target and the uncurated public release/repository surface.

### 2. Pre-launch runner attempts were separated from substantive execution

Several setup attempts were stopped before meaningful adaptation output:

1. `opencode/nemotron-3.5-lightning-free` repeatedly returned provider 404 before any model response, tool call or mutation. The attempt was aborted as provider/runtime preflight failure.
2. A Big Pickle TUI launch using the `--prompt` delivery path was stopped with zero project effect so the frozen prompt could be delivered through normal interactive input instead.
3. A fresh TUI session was closed before prompt submission when runner version drift from OpenCode 1.18.23 to 1.18.25 was observed. The same isolated policy was revalidated byte-identically before substantive execution.

These events are setup/runtime controls, not H-A semantic attempts and not material owner interventions.

### 3. Substantive fresh execution began under bounded tool isolation

The substantive run used OpenCode 1.18.25 with `--pure`, no inherited instructions, MCP configuration or plugins, and denied `external_directory`, `webfetch`, `websearch`, `task` and `skill` capabilities. Shell actions were ask-gated with explicit denials for common network/provider/install commands. The model-provider connection necessarily remained available, so this was application/tool-policy isolation rather than a hard OS network namespace.

The agent first inventoried only admitted local input and independently reproduced the released public-surface digest. It vendored the sanitized toolkit projection into the disposable Mail workspace and verified the copy byte-for-byte.

### 4. The agent discovered the route but repeatedly tested the effect boundary

The agent discovered the existing-project adoption route and the project-owned target surfaces without being handed the expected filenames in the prompt. During execution, however, several shell requests crossed or ambiguously approached the mutation boundary and were rejected. These are part of adaptation-cost evidence rather than hidden corrections to the final result.

### 5. The critical stop occurred before the first planned semantic write

Before project-owned semantic files were written, inspection of the agent's compacted plan showed two unsupported schema-satisfying placeholders under consideration:

- an all-zero OCI/runtime image identity because no observed OCI identity existed in admitted agent input; and
- `team:nextcloud-mail-maintainers` as a syntactic owner placeholder while ownership/acceptance was unverified.

The owner/orchestrator stopped the flow before the first semantic write and repeated only the already-declared experiment rule: unsupported ownership, provenance, verifier, acceptance or runtime/image identity must remain unresolved; structural requirements must not be satisfied by invented facts; affected outcomes should remain BLOCKED/FAIL where necessary.

No Mail-specific semantic fact, authority value or implementation decision was supplied. The H-A material owner intervention count therefore remained 0.

The agent acknowledged the rule and resumed. Later, however, OpenCode `edit=allow` permitted direct Write/Edit mutation without a human permission dialog, and the agent serialized the template's schema-valid all-zero OCI image into `.knowledge/kit.lock.yaml` while marking the runtime identity `UNRESOLVED`.

### 6. Structural checks passed more than semantic truth justified

On the staged diagnostic candidate:

- `check-runtime`: PASS / exit 0;
- `check-change-policy`: PASS / exit 0;
- `check-ci-policy`: PASS / exit 0;
- bundle validation: PASS;
- task-envelope validation: PASS;
- bounded context generation: first seed invocation failed mechanically, then self-corrected; two retained outputs were byte-identical;
- Mail `fast`: BLOCKED / exit 127 because `php`, `composer`, `vendor/` and `node_modules/` were unavailable;
- Mail `regression`: BLOCKED / exit 127 for the same prerequisite gap;
- no dependency install/download was attempted.

The source-built `check-runtime` success did not prove that the declared runtime image was factual. It established source/revision/digest/schema consistency under the invocation it received, but no observed runtime-image binding was supplied. This is a concrete instance of the structural-versus-semantic truth gap already seen in ownership/verifier fields during earlier adoption work.

The aggregate adoption gate behaved more conservatively:

```text
EVIDENCE BUNDLE COMMITMENT: sha256:52dfb53b7b542d988be6acc6f9c0dd928d31d0cbe9e0c97663b97f0623b093d0
REVIEW READINESS: BLOCKED
SEMANTIC ADOPTION: NOT DETERMINED
OWNER DISPOSITION: REQUIRED
adoption-rc=3
```

That layered behavior is evidence in favor of the assurance-v2 split selected around issue #143 and Decision 0050: local structural validity did not automatically become readiness or semantic adoption.

### 7. Exact freeze preserved the raw experiment result before review

The produced candidate was frozen before correction or owner acceptance:

- exact candidate tree `97f0e0a44621e029af5bb3c360b397cd0ef993bf`;
- worktree equals index: PASS;
- binary/full-index patch `sha256:d63c0cf0746ae21375c8880c245d3d7ca76426e141f00148614458208102fc8e`, 824871 bytes;
- project-owned manifest: 11 paths, consisting of 10 net-new project-owned files plus additive modification of existing `AGENTS.md`;
- retained-evidence manifest: 33 records.

The exact patch independently retained by adoption-check matched byte-for-byte.

### 8. Fresh-context review accepted the candidate but did not erase protocol deviation

A separate fresh OpenCode session reviewed read-only base/candidate/evidence material without the adaptation conversation or hidden owner diagnosis. The reviewer independently identified the all-zero OCI placeholder and recommended `ACCEPT`, reasoning that it was explicitly marked unresolved/non-observed rather than asserted as an observed runtime fact.

The reviewer recommendation strengthens owner-led semantic review but is not independent-adopter evidence. It also used the same `opencode/big-pickle` model alias as adaptation, leaving a correlated-blind-spot risk.

The accountable owner later recorded `ACCEPT` and the predeclared H-A score `PASS`. The all-zero runtime-image event remains separately recorded as a protocol deviation because the execution prompt explicitly forbade unsupported runtime/image identity fabrication.

## Human control ledger

The key retrospective distinction is between **boundary/runtime controls** and **material semantic intervention**.

| Stage | Human control | Reason | Semantic fact supplied? | H-A material intervention? |
|---|---|---|---|---|
| Pre-launch | Abort Nemotron attempt | Provider 404 before model response | No | No |
| Pre-launch | Stop Big Pickle `--prompt` session | Wrong prompt-delivery mode; zero project effect | No | No |
| Pre-launch | Close fresh session | Runner version drift before prompt submission | No | No |
| Substantive | Reject parent-directory `ls` | Would expose orchestration material outside admitted root | No | No |
| Substantive | Reject first relative project-layer `mkdir` | Active cwd was `agent-input/`, outside Mail mutation surface | No | No |
| Substantive | Reject repeated relative `mkdir` | Same wrong-root effect boundary | No | No |
| Substantive | **Stop before first semantic write** | Planned synthetic OCI and owner placeholders conflicted with already-declared no-fabrication rule | No | No |
| Substantive | Reject ambiguous staging command | Relative paths not visibly Mail-bound; known-defective candidate needed pre-staging observation | No | No |
| Substantive | Permit corrected Mail-scoped staging | Diagnostic validation after path self-correction | No | No |

Material owner semantic interventions remained **0**. This does not mean human control cost was zero. It means the owner did not supply project-specific semantic answers. Denials and the stop event are therefore retained separately as interaction/friction evidence.

A future experiment record should preserve both counters: material semantic interventions and mechanical boundary-control activations.

## What worked

### Sanitized input projection and claim downgrade

The contamination problem was detected before launch, not after a misleading positive result. The response preserved experimental honesty: the input was sanitized deterministically and the claim was narrowed. The updated external evaluation correctly treats this as a meaningful result in itself.

### Route discovery and authority preservation

The fresh agent discovered the adoption route from admitted consumer material and frozen Mail evidence. It did not repeat the earlier destructive behavior of replacing project authority. Existing `AGENTS.md` was extended additively rather than replaced.

### Deterministic context on a real project

After a mechanical seed error and self-correction, two context-pack outputs were byte-identical. Determinism previously demonstrated on generic examples therefore reproduced on a real 1,472-file project subject.

### Honest project verification

Unavailable PHP/composer/dependency prerequisites were reported `BLOCKED`, never repainted as PASS. No install/download was attempted merely to improve the score.

### Layered adoption assurance

Structural validators could pass while aggregate readiness remained BLOCKED and owner disposition remained required. This is the intended distinction between observations/conditions/readiness/owner judgement.

### Exact candidate freeze

The raw agent output, including the defect, was frozen before semantic acceptance or correction. That made the later retrospective evidence reconstructable rather than dependent on residual worktree state or narrative memory.

## What failed or was weaker than intended

### Released self-knowledge prevented an uncontaminated Mail cold-start

The public repository contains maintainer self-knowledge that is intentionally outside project onboarding, but for a target already used in internal experiments it also contains target-specific oracle material. This does not prove that self-knowledge contaminates every unknown target; it proves that unrestricted full-repository exposure could not measure clean Mail cold-start discoverability.

### Template placeholders were validator-shaped instead of fail-closed

At immutable v0.2.0, `templates/knowledge-kit.lock.yaml` makes revision placeholders visibly non-final with `REPLACE_WITH_IMMUTABLE_TOOLKIT_REVISION`, but `public_surface_digest` and `runtime.image` use all-zero values that already satisfy the schema regexes. The runtime placeholder failure has recurred across multiple adoption exercises.

This is primarily a product/template design defect. A capable agent can still choose to leave the field unresolved rather than serialize the value, but the shipped template invites exactly the schema-shaped mistake the product's fail-closed philosophy is intended to prevent.

### `check-runtime` structural PASS was too easy to overread

The runtime-lock check accepted the all-zero image because the invocation did not provide an observed image binding that could falsify the declaration. The command's success message can therefore be misread as stronger runtime truth than was actually established.

The aggregate adoption gate prevented that local PASS from becoming readiness, which limited the damage. The durable need is clearer separation of **lock structure/source binding** from **observed runtime-image truth**.

### Runner write permissions bypassed intended human checkpoints

OpenCode shell actions were ask-gated, but `edit=allow` allowed project file writes without a permission dialog. The human could stop the run before the first planned semantic write, yet later direct edits still serialized the runtime placeholder without another checkpoint.

This is an experiment-runner control weakness, not a Mail semantic intervention. Future comparable experiments should use a stronger file-write gate or OS/container boundary when practical.

### Fresh review was not independent review

The review session was context-isolated, but it used the same model alias as adaptation. Fresh context removes transcript contamination; it does not remove correlated model blind spots. Phase B should use a different model/provider alias for fresh technical review where practical, as already frozen in Work Item #158.

## External-evaluation reconciliation

The updated owner-supplied evaluation adds useful interpretation without replacing exact experiment evidence.

### Conclusions retained

- The first major finding occurred before execution: the released repository itself made a clean Mail cold-start impossible without target-specific sanitization.
- The result is the first **positive controlled owner-led adaptation** after earlier rejected attempts; negative earlier attempts remain real evidence and are not erased.
- Zero material semantic interventions, preserved project authority and deterministic bounded context materially improve the adoption-cost picture for the controlled surface.
- The assurance-v2 layering behaved as intended: structural PASS did not become readiness or owner acceptance automatically.
- The all-zero runtime image is best treated primarily as a recurring product/template defect, not merely an isolated agent mistake.
- H-A should be scored by the predeclared literal contract rather than retroactively tightened after outcome observation.
- The same-model adaptation/review pairing is a correlated-blind-spot risk.
- Practical utility remains `UNKNOWN` until Phase B executes a real bounded task.

### Bounded corrections

- The fresh-context reviewer is not an independent adopter or independent external evaluator.
- The assessment introduced 11 project-owned adaptation **paths**: 10 net-new files and one additive `AGENTS.md` modification.
- The roughly 52-minute number is the substantive session span from creation to last observed update, not an exact prompt-enter-to-completion measurement because the exact prompt-enter instant was not bound.
- Any stale provider presentation in the external artifact, including historical PR state, is overridden by live provider read-back.
- External code/word ratios and synthetic-adopter measurements remain dated analytical snapshots, not current product truth or real-adoption utility evidence.

## H-A scoring reconciliation

The predeclared H-A required:

- no more than 2 material owner interventions;
- zero invented ownership, provenance, verifier, acceptance or project-authority facts presented as true;
- structural validation PASS;
- bounded-context generation PASS; and
- fresh-context semantic review ACCEPT.

Observed result:

- material owner interventions: 0;
- ownership/acceptance remained unresolved rather than asserted as observed authority;
- structural validation: PASS;
- bounded context: PASS and deterministic after self-correction;
- fresh review: ACCEPT;
- owner disposition: ACCEPT.

The runtime-image placeholder violated the broader execution instruction not to fabricate unsupported runtime/image identities. However, the predeclared H-A FAIL enumeration did not list runtime image identity, and the placeholder was explicitly treated as unresolved/non-observed by the fresh reviewer. Expanding the FAIL condition after seeing the result would be post-hoc rule tightening.

Therefore the canonical reconciliation remains:

```text
H-A                               PASS
protocol deviation                YES
runtime-image placeholder defect  RETAINED
owner disposition                 ACCEPT
Phase-A practical utility         UNKNOWN
```

This is not leniency toward the defect. It is separation of hypothesis scoring from protocol-compliance findings.

## Narrow claim boundary

Phase-A PASS supports only:

> Initial adaptation of this frozen Mail subject from the admitted sanitized Gnostoa v0.2.0 consumer surface was achievable with 0 material owner semantic interventions, deterministic bounded context, preserved project authority and an owner-accepted candidate under the recorded protocol and environment.

It does **not** establish:

- clean full-repository cold adoption;
- general ease or low cost of Gnostoa adoption;
- independent adoption;
- upstream acceptance;
- practical productivity gain;
- long-term maintenance or synchronization cost;
- resilience to upstream churn; or
- product-market demand.

## Durable lessons

1. **Fresh session is not enough; input provenance matters.** A clean model state with contaminated filesystem input is still a contaminated experiment.
2. **Consumer-surface adaptation and full-repository cold adoption are different experiments.** Do not blend their claims.
3. **Record human control friction separately from semantic intervention.** Deny/Reject/stop events matter to usability even when they inject no project facts.
4. **Fail-closed templates should be syntactically impossible to ship unchanged.** Schema-valid nonsense is a recurring adoption hazard.
5. **Structural lock validity is not observed runtime truth.** Validator messages and assurance conditions should preserve that distinction.
6. **Aggregate readiness should remain stronger than component PASS.** The rc=3 BLOCKED result prevented local structural success from becoming semantic overclaim.
7. **Freeze the raw candidate before review or correction.** Exact tree and patch evidence made the protocol defect inspectable without rewriting history.
8. **Fresh review and independent review are different assurance levels.** Different model/provider review is preferable when cheap and relevant.
9. **Predeclared scoring protects against post-hoc reinterpretation.** Record protocol deviations separately instead of silently moving success criteria after the outcome.
10. **Practical value is now the priority evidence gap.** Phase B should run before assurance machinery expands further unless a newly discovered defect blocks safe execution.

## Follow-up hypotheses and admission conditions

Findings below are retained separately from implementation admission.

| Timing / admission condition | Hypothesis | Current status |
|---|---|---|
| Focused product fix when template/adoption usability work is admitted | Make `public_surface_digest` and `runtime.image` template placeholders schema-invalid until replaced; add regression tests. | RETAINED, NOT IMPLEMENTED |
| Before a claim relies on runtime-image truth rather than lock structure | Separate/strengthen observed runtime-image binding from structural `check-runtime` validity and wording. | RETAINED, NOT IMPLEMENTED |
| Before the next comparable controlled agent experiment | Replace `edit=allow` with a stronger write checkpoint or isolated filesystem boundary where practical. | RETAINED, NOT IMPLEMENTED |
| Later, on a previously unseen target | Run true full-repository cold adoption without a target-specific sanitized projection. | RETAINED, NOT STARTED |
| Phase B fresh review | Use a different model/provider alias from the Phase-A Big Pickle adaptation/review where practical. | ALREADY FROZEN IN #158, NOT YET EXECUTED |
| Existing separate backlog | InvalidInput/InternalError distinction, diagnose mode, Decision-number prefix uniqueness and large-function decomposition. | OUTSIDE THIS RETROSPECTIVE SLICE |

No new Decision is selected here. The retrospective does not convert any finding into mandatory implementation.

## Implications for Phase B

Work Item #158 was admitted before this formal retrospective and is held at `PRE-LAUNCH` until retrospective reconciliation. The retrospective does **not** rewrite its already-frozen H-B scoring contract or task statement.

Before Phase-B execution:

- reconstruct exactly the accepted Phase-A tree `97f0e0a44621e029af5bb3c360b397cd0ef993bf` from the frozen Mail base and retained patch;
- do not silently repair the Phase-A runtime-image placeholder in that baseline;
- retain Deny/Reject/stop controls separately from material owner semantic interventions;
- use stronger file-write gating than Phase A where practical without changing task semantics;
- expose only the exact accepted adaptation and frozen real task statement to the fresh execution agent;
- use a different model/provider alias for fresh technical review where practical;
- assess owner utility explicitly as `POSITIVE`, `MIXED`, `NEGATIVE` or `UNKNOWN`.

The purpose of Phase B is not to prove the adaptation can exist. Phase A established that controlled result. Phase B asks the remaining product question: **does the accepted adaptation materially help a fresh agent complete one real bounded Mail development task?**
