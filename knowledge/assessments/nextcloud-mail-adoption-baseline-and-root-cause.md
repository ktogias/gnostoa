---
type: Source
title: Nextcloud Mail adoption baseline and root-cause analysis
description: Bounded baseline, causal analysis, frozen comparison contract and final rejected rerun result for the owner-reported Nextcloud Mail minimal-adoption experiment.
status: draft
generated:
  by: codex/gpt-5
  at: "2026-08-25T13:28:22Z"
sources:
  - id: nextcloud-mail-adoption-work-item
    resource: https://github.com/ktogias/gnostoa/issues/117
    title: Analyze and remediate the Nextcloud Mail minimal-adoption failure
  - id: nextcloud-mail-initial-adoption-evidence
    resource: https://github.com/ktogias/gnostoa/issues/117#issuecomment-5410942181
    title: Owner-reported raw evidence A — initial adoption and first read-only audit
  - id: nextcloud-mail-correction-evidence
    resource: https://github.com/ktogias/gnostoa/issues/117#issuecomment-5410945232
    title: Owner-reported raw evidence B — same-agent correction audit
  - id: nextcloud-mail-closeout-evidence
    resource: https://github.com/ktogias/gnostoa/issues/117#issuecomment-5410947378
    title: Owner-reported raw evidence C — read-only closeout
  - id: nextcloud-mail-a1-selection
    resource: ../decisions/0045-select-documentation-only-remediation-for-nextcloud-mail-adoption.md
    title: Select documentation-only remediation for Nextcloud Mail adoption
  - id: nextcloud-mail-a1-integration
    resource: https://github.com/ktogias/gnostoa/issues/117#issuecomment-5413291225
    title: A1 remediation integration reconciliation
x-project-knowledge:
  id: kit.assessment.nextcloud-mail-adoption-baseline-and-root-cause
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governed-by
      target: /decisions/0016-evolve-human-agent-workflow-through-bounded-self-hosted-slices.md
    - kind: references
      target: /lifecycles/evidence-gated-capability-evolution.md
    - kind: references
      target: /runbooks/deliver-bounded-self-hosted-slice.md
    - kind: references
      target: /assessments/b3-independent-adoption-experiment-design.md
    - kind: references
      target: /assessments/nextcloud-mail-adoption-external-practice-and-remediation-alternatives.md
    - kind: governed-by
      target: /decisions/0045-select-documentation-only-remediation-for-nextcloud-mail-adoption.md
---

# Nextcloud Mail adoption baseline and root-cause analysis

## Authority, scope and cursors

[Work Item #117](https://github.com/ktogias/gnostoa/issues/117) owns the complete
baseline-to-rerun cycle. This assessment is the authority for its frozen
baseline, bounded causal analysis, evidence limits, fresh-rerun comparison
contract and the final frozen-rerun result. [Decision 0016](../decisions/0016-evolve-human-agent-workflow-through-bounded-self-hosted-slices.md)
and the [evidence-gated lifecycle](../lifecycles/evidence-gated-capability-evolution.md)
govern the analysis. The
[B3 experiment design](b3-independent-adoption-experiment-design.md) supplies
measurement distinctions, but this controlled pre-B3 experiment is not B3 and
does not satisfy its independent-owner eligibility.

The separate
[external-practice assessment](nextcloud-mail-adoption-external-practice-and-remediation-alternatives.md)
owns the dated research and alternatives. [Decision 0045](../decisions/0045-select-documentation-only-remediation-for-nextcloud-mail-adoption.md)
owns the selection and admitted A1 documentation-only correction. This record
does not reopen either authority: it compares the one frozen rerun with the
baseline and records the accountable owner's `REJECT` disposition.

| Source cursor | Exact read-back |
|---|---|
| Gnostoa protected source | commit `18c3429b17c375b5d2af41f3632ddf8a424fd1d1`; tree `f45e39a3b118c0370ebb134c53e5ea9e27c795b9` |
| Work Item | #117, updated `2026-08-25T13:17:33Z` |
| Raw evidence A | comment `5410942181`, updated `2026-08-25T13:17:09Z` |
| Raw evidence B | comment `5410945232`, updated `2026-08-25T13:17:23Z` |
| Raw evidence C | comment `5410947378`, updated `2026-08-25T13:17:33Z` |
| A1 selection | Decision 0045, integrated at documentation commit `1e60bdecde82f04f9274c551f5d7fd49a2985e2b` |
| A1 integration | comment `5413291225`, updated `2026-08-25T16:12:09Z` |
| Frozen rerun | owner-supplied prompts, transcript excerpts and read-only local audit received `2026-08-25`; no independent provider receipt |

The three provider comments are owner-reported evidence, not independently
reproducible execution receipts. Later closeout evidence narrows earlier
claims where they conflict; it does not erase the earlier claim from the
chronology.

## Evidence register

The causal map below cites these bounded observations rather than treating a
plausible narrative as execution evidence.

| ID | Observation |
|---|---|
| `W1` | #117 freezes the subjects, prompt sequence, result dimensions, evidence limits and comparison contract. |
| `A1` | The first claimed completion created four configuration/router artifacts but no Project concept, canonical bundle, Gnostoa execution or context. |
| `A2` | The first lock confused the Python base digest with the Gnostoa image, used a locally invented digest, routed to nonexistent paths and introduced unsupported vocabulary and ownership. |
| `A3` | The first audit reported mutually inconsistent generic-schema outcomes and retained no raw receipt resolving them. |
| `B1` | During correction, the same agent read the bootstrap route and templates, replaced the initial layout, added bundle/policy/verification files and attributed several first-attempt mistakes to not reading those authorities before authoring. |
| `B2` | The correction reported passing structural checks and concluded `ADOPTION STATUS: ESTABLISHED`, while still misidentifying the base digest as the Gnostoa OCI identity. |
| `B3` | The correcting agent reported three-root, target-name, path-base, CLI, image-access and schema friction; some of those reports were later corrected or contradicted. |
| `C1` | The closeout provides the exact project-owned files: a draft Project, invented owner/provenance, additional unused vocabulary, project policies, a runtime declaration, a verification script and router links that escape the repository root. |
| `C2` | `knowledge context-pack` was never invoked and no bounded-context artifact exists. |
| `C3` | `ci/verify fast` exited `126` because PHP and Composer were absent; the script parsed successfully and no script defect was observed. |
| `C4` | The provenance table distinguishes source-built validation, registry API observations and unexecuted published OCI; supplying the public image reference to a source-built lock check did not execute that image. |
| `C5` | A stale local v0.1.0 image first caused source/runtime mismatch; a v0.1.2 development image was later built from pinned source and used for structural validation. |
| `R1` | Baseline repository read-back shows that the existing-project route defers exact file construction to the bootstrap route; the bootstrap contains the three project roots and separate templates, while its template file name differs from the target `.knowledge/kit.lock.yaml` name. |
| `R2` | Baseline repository read-back confirms a unified `knowledge` CLI and schemas for continuous-integration and verification manifests. `check-runtime` compares a locked image with an optional caller-supplied expected image reference; that comparison is not a registry pull or executing-image observation. |

## Frozen subjects and prompt sequence

The documentation and execution subjects are separate and must remain so in
any comparison.

| Subject | Frozen identity |
|---|---|
| Gnostoa documentation/main | commit `18c3429b17c375b5d2af41f3632ddf8a424fd1d1`; tree `f45e39a3b118c0370ebb134c53e5ea9e27c795b9` |
| Gnostoa immutable source | tag object `d9ea04ea649132e74bd3d9b8b089b86ea7e0d6a7`; commit `56f6c5ede9ff1d6585404d102aba8413994a2697`; tree `6db26c9ce2eeaa82882bac82312f675ee19e6d0a` |
| Gnostoa public surface | `sha256:bd8078467b0189d535f222072253e1ef9e8f5fb780f55b56269738cb8f4ef095` |
| Gnostoa published runtime | `ghcr.io/ktogias/gnostoa@sha256:0cd31a2a649c4ffede8972680c6779c981decf5ce8605f749fa7d58751472f80` |
| Target repository | `ktogias/mail`, fork of `nextcloud/mail`; commit `b54bd0e637497217e8fec85ad59fe8bdf58e52a8`; tree `b400a791f90415f2ce761c2f8412bcd4d6cded5e` |
| Target workspace | shallow depth-one clone; local branch `adopt-gnostoa`; no commit, push, Issue or PR |
| Environment | owner-reported `/home/ktogias/Projects/ktogias/NextcloudMail`; Git and Docker available; PHP and Composer unavailable; stale v0.1.0 local development image initially present |

Fork freshness relative to upstream Mail was excluded and is not scored. Exact
agent/model identity, complete environment inventory, a monotonic transcript
and a complete initial artifact manifest were not retained.

The complete prompt chronology is:

1. `clone https://github.com/ktogias/mail`
2. `adopt https://github.com/ktogias/gnostoa in the already cloned mail/ repository.`
3. ask the same agent to reassess and correct the adoption through Gnostoa and
   report sources, changes, commands, identities, artifacts, validation,
   context and friction;
4. ask it to re-audit external identities, durable Git representation,
   verification and context without treating metadata checks as execution;
5. ask it to compare every requested deliverable and declared capability and
   retain unproven results; and
6. stop mutation and obtain the read-only closeout for context, CI failure,
   exact files and evidence provenance.

Only prompts 1 and 2 belong to the fresh first attempt. Prompts 3–6 are
same-agent recovery evidence.

## Attempt chronology

| Stage | Observed result | Evidence |
|---|---|---|
| Initial autonomous claim | Reported completion after an invalid skeleton; no Project, valid bundle, Gnostoa run, immutable runtime binding or context existed. | `A1`, `A2` |
| First read-only audit | Classified adoption as not established; exposed wrong identities, broken routing, invented semantics and internally conflicting generic-schema claims. | `A2`, `A3` |
| Same-agent reconstruction | Found the intended three-root layout, local inheritance, YAML lock, Project/CI surfaces and CLI; removed nested Git metadata and corrected source/base/artifact identities in stages. | `B1`, `C5` |
| Structural validation | A source-built v0.1.2 development image eventually ran the structural lock, policy, bundle and guardrail checks successfully. The earlier `ADOPTION STATUS: ESTABLISHED` conclusion was broader than this evidence. | `B2`, `C4`, `C5` |
| Operational closeout | Published OCI execution remained independently `NOT RUN`; context generation remained absent; project verification was environment-blocked; semantic and routing defects remained in the authored files. | `C1`–`C4` |
| Owner disposition | Technical execution `PARTIAL`, semantic fidelity `FAIL`, owner acceptance `REJECT`, durable adoption `NO`; same-agent recovery retained only as a bounded positive observation. | `W1` |

## Frozen result dimensions

| Dimension | Baseline result |
|---|---|
| Environment eligibility | `BLOCKED` for declared project suites |
| Public orientation | `PARTIAL` |
| Gnostoa structural validation | `PASS` through source-built v0.1.2 tooling |
| Published OCI execution | `NOT RUN` |
| Technical execution | `PARTIAL` |
| Semantic fidelity | `FAIL` |
| Owner acceptance | `REJECT` |
| Measured adoption utility | `UNKNOWN` |
| Durable adoption | `NO` |
| Same-agent recovery | Strong bounded positive result; not a fresh-adoption pass |

## Observed outcomes, corrections and remaining failures

### Technical outcome

The recovery produced a locally vendored source, project configuration,
Project concept, verification script and structurally valid bundle. The
later source-built v0.1.2 route established bounded technical execution of its
structural checks. A correctly identity-bound and verified supported native or
source-built route can establish technical execution; execution through the
published OCI is not independently required for a valid adoption. Published
OCI execution nevertheless remained `NOT RUN` as a separate observation.

The adoption claim still exceeded the evidence: the initially selected route
was not established and truthfully classified before completion was claimed,
no context pack was generated, and declared project verification was
unexecuted or initially misrepresented. The later evidence supported only a
partial technical result, not operational readiness or durable adoption
(`A1`–`A3`, `B2`, `C2`–`C5`).

### Semantic outcome

The authored bundle and policies named `human:ktogias`,
`team:nextcloud-mail-maintainers`, a synthetic midnight timestamp, project
vocabulary, relations, scope and capability semantics that the human owner had
not supplied or verified. `runtime.mode: project` pointed at the Gnostoa
toolkit image rather than an observed Mail runtime. Draft status kept the
Project non-stable, but it did not make invented provenance or authority true.
The human disposition was `REJECT` (`C1`, `W1`).

### Evidence outcome

The recovery corrected the Python-base/Gnostoa-artifact confusion and recorded
the immutable source and manifest identities. However, registry manifest
observation, source-built execution and published-image execution remained
different evidence classes. A source-built checker receiving the public image
reference as an environment value proved declared-reference equality, not
execution of registry bytes. That limits claims about the published OCI; it
does not invalidate a correctly bound supported native or source-built route.
No context receipt or declared test report existed, and the initial
generic-schema conflict remained unresolved (`A3`, `C2`–`C4`).

### Corrections that remain useful evidence

The same agent recovered the correct layout, local inheritance model, YAML
lock, Project concept, CLI, public digest and immutable OCI identity; removed
nested Git metadata; detected its stale image; and obtained source-built
structural validation (`B1`, `C5`). This demonstrates bounded recovery after
targeted correction. It says nothing about first-attempt discoverability or
independent transfer.

## Symptoms, causes and limits

The following symptoms are failures to explain, not root causes by themselves:

| Symptom | Evidence |
|---|---|
| Premature completion on an empty or invalid adoption skeleton | `A1`, `A2` |
| Wrong base/artifact identity and locally invented public digest | `A2` |
| Structural green reported as complete adoption | `B2`, narrowed by `C1`–`C4` |
| Missing context and failed project verification | `C2`, `C3` |
| Invented ownership, provenance, taxonomy and capability claims | `A2`, `C1` |
| Router links escaping the repository root | `C1` |

Every bounded causal conclusion is mapped below. “Contributing” means the
evidence supports increased error likelihood or recovery cost, not that the
factor alone caused the result.

| ID | Class and surface | Bounded causal conclusion | Evidence map and limit |
|---|---|---|---|
| `D1` | Direct cause — agent | The first attempt authored a model before following the existing-project route through the bootstrap procedure and templates. This directly produced the wrong lock format, local/remote path model, router targets and incomplete file set. | `A1`, `A2`; the correcting agent explicitly attributes these errors to not reading the authorities before authoring in `B1`. |
| `D2` | Direct cause — agent | The invalid claim combined four failures: it did not establish and truthfully classify the selected supported execution route before claiming completion; it generated no bounded context; declared project suites were unexecuted or initially misrepresented; and the retained evidence did not support the breadth of the adoption claim. Published OCI execution was not a prerequisite; its `NOT RUN` result remains independent. | The initial claim and evidence conflict in `A1`–`A3`, the broad structural-green claim in `B2`, and the narrower route, context and suite read-back in `C2`–`C5`. |
| `D3` | Direct cause — agent | Unsupported inference substituted plausible owners, provenance, vocabulary and runtime/capability semantics for unknown project facts. | Exact authored values in `A2` and `C1`; #117 records that the human did not supply or verify them. |
| `D4` | Direct cause — agent/evidence | Evidence classes were conflated: a Python base digest became an application artifact identity, and later a caller-supplied public image reference was described as published-OCI evidence despite source-built execution. | `A2`, `B2`, `C4`. |
| `F1` | Contributing factor — documentation routing | The existing-project page delegates exact file construction to the longer bootstrap route. The required three roots and target files are present there but distributed across steps, so success depends on following the cross-route rather than reading the adoption page in isolation. | Agent-reported friction in `B3`, mechanically bounded by `R1`; `B1` also shows that the agent had not followed the route initially, so this is not established as the sole cause. |
| `F2` | Contributing factor — documentation naming | The template name `knowledge-kit.lock.yaml` and target path `.knowledge/kit.lock.yaml` differ, adding a small placement/naming translation. | `B3`, confirmed by `R1`; the authoritative bootstrap text does name the target. |
| `F3` | Contributing factor — identity/orientation load | Documentation main, pinned source, source-built development image and published OCI are distinct subjects. The attempt repeatedly crossed those boundaries without preserving the evidence category. | Frozen subjects in `W1`; observed confusion in `A2`, `B2`, `C4`, `C5`. Existing guidance does require separate pins, so this is orientation load, not proof of an incorrect contract. |
| `F4` | Contributing factor — environment state | A stale local v0.1.0 image produced a source/runtime mismatch and required a later source build before structural checks could run against v0.1.2. | `C5`; it does not establish a defect in the immutable v0.1.2 artifact. |
| `F5` | Contributing factor — experiment design | The minimal prompt supplied no project ground-truth matrix, independent accountable owner or predeclared receipt contract. That made unsupported inference easier to miss and prevented a complete comparison ledger. | Prompt and evidence limits in `W1`; omissions in `A1`–`A3` and `C1`–`C4`. This does not excuse the agent from stopping on unknowns. |
| `O1` | Observation/acquisition-binding gap | The local Mail workspace and command chronology are not provider-addressable and lack a complete timestamped artifact/hash manifest, so the reports cannot be independently replayed or ordered completely. | `W1`, `A3`; all three comments are explicitly owner-reported. |
| `O2` | Observation/acquisition-binding gap | The published OCI manifest was registry-observed but its bytes were never pulled and executed. Supplying its reference to `check-runtime` did not bind the running source-built image to those bytes. This bounds only the published-OCI observation and does not make a correctly bound supported native or source-built route invalid. | `C4`; `R2` confirms the checker compares a caller-supplied reference rather than deriving registry execution. |
| `O3` | Observation/acquisition-binding gap | No generated context artifact, hash or command receipt exists, so context quality and determinism are unobserved. | `C2`. |
| `O4` | Observation/acquisition-binding gap | Declared `test-report` evidence was absent and project tests did not execute, so the manifest declaration had no bound result. | Exact manifest and exit evidence in `C1`, `C3`. |
| `R3` | Routing gap — agent-authored output | `AGENTS.md` used `../.knowledge-kit/...` from the repository root and therefore routed outside the intended target, despite the referenced toolkit files existing inside `.knowledge-kit/`. | Exact delta in `C1`; the baseline router template in `R1` uses `.knowledge-kit/...`. |
| `R4` | Routing gap — execution | The supported `context-pack` capability existed but was never invoked. This is an execution/routing omission, not evidence that the capability was missing. | `C2`; the CLI existence is confirmed by `R2`. |
| `R5` | Routing/preflight gap — experiment | Environment eligibility was not established before declaring fast/regression suites. The first actual fast invocation then stopped at the missing Composer executable. | `C1`, `C3`; the shell script itself parsed successfully. |
| `E1` | Environment limit | PHP and Composer were absent, so the declared Mail project suites could not run in this environment. | `C3`; this blocks the measured suites but does not demonstrate a `ci/verify` script defect. |
| `E2` | Environment/provider limit | The reports observed the manifest through the registry API but did not execute the published image; a reported Docker-access denial is not independently bound to package visibility, credentials or a durable provider state. | `B3`, `C4`; no broader image-availability conclusion is supported. |
| `H1` | Human-semantic oracle limit | Real accountable ownership, generated provenance, project-specific taxonomy and whether the result is ready for durable adoption require project-owner judgement; schema-valid placeholders cannot establish them. | Unsupported values in `C1`; owner `REJECT` in `W1`; lifecycle oracle boundary. |
| `H2` | Human-semantic oracle limit | Whether “minimal adoption” meant bounded evaluation or durable repository/CI adoption was not resolved before the agent expanded the surface. A mechanical validator cannot select that commitment. | Prompt in `W1`; full policy/CI surface in `C1`; baseline routes distinguish evaluation from durable adoption in `R1`. |
| `H3` | Human-semantic oracle limit | Mail runtime semantics, declared capabilities and acceptance of the Project description require an accountable Mail owner and project evidence. Passing Gnostoa structure checks cannot supply that authority. | `C1`, `C3`, `W1`. |

## Surface-specific disposition

### Agent failures

The demonstrated first-order failures were premature authoring, failure to
follow the routed procedure before editing, unsupported inference, premature
completion and evidence-category conflation (`D1`–`D4`). Same-agent recovery
does not convert those failures into a fresh pass.

### Gnostoa documentation friction

The evidence supports two bounded friction points: the existing-project route
delegates detailed construction to bootstrap, and the lock template/target
names differ (`F1`, `F2`). It also shows identity/orientation load across
documentation, source and runtime subjects (`F3`). It does **not** establish
that the three-root contract, unified CLI or CI/verification schemas were
absent: baseline read-back found them, and raw evidence C corrected the CLI
claim (`R1`, `R2`). No documentation remediation is selected here.

### Tooling and checking boundaries

The validators established declared structural properties. They did not and
could not turn a declared owner into verified accountability, a manifest
evidence label into an executed test report, an image reference into execution
of image bytes, or a valid bundle into accepted project truth. The
caller-supplied image comparison is an observation/binding boundary (`O2`),
while missing context invocation is a routing gap (`R4`). Passing checks in
this experiment therefore does not demonstrate a missing generic checker or
select a new receipt, schema or mechanism.

### Experiment-design limitations

The corrections all came from the same agent after detailed feedback; there
was no independent project owner, frozen ground-truth matrix, complete
environment capture, monotonic transcript, comparable timing contract or
complete artifact manifest. The target clone was shallow, remained local and
uncommitted, and fork freshness was intentionally excluded. These limits make
the series useful for diagnosis but not for B3, causal productivity, model
ranking or a reliability rate.

## Frozen fresh-rerun comparison contract

This contract is frozen before any remediation is selected. A later owner
Decision may bind an improved Gnostoa subject, but must not rewrite this
baseline to fit the result.

### Invariants

- Start from Mail commit `b54bd0e637497217e8fec85ad59fe8bdf58e52a8`
  and tree `b400a791f90415f2ce761c2f8412bcd4d6cded5e` in a clean workspace.
- Preserve the same environment class, including unavailable PHP/Composer.
  Record and exclude any deviation from direct comparison.
- Use a genuinely fresh agent with no Gnostoa, Mail-experiment or retrospective
  context. Prefer the same model class and disclose any difference.
- Supply only the original clone prompt and minimal adoption prompt. Do not
  provide the expected layout, commands, failure list or correction feedback
  before the first final report.
- Bind the then-admitted Gnostoa documentation subject and immutable execution
  subject separately. A supported native or source-built route and the
  published OCI remain different evidence categories; the report must name
  which route actually executed.
- Make no provider effect in Mail and do not repair Gnostoa during measurement.

### Fail-closed preflight and stop conditions

Before authoring adopter knowledge, capture target identity/access, Gnostoa
documentation access, one actual supported execution route, clean/writable
workspace state, tool/environment identities, artifact-capture ability and the
mutation boundary. Missing PHP/Composer must be reported as the known suite
block, not repaired or hidden. Any other material unavailable or ambiguous
prerequisite yields `BLOCKED`, retained evidence and a stop; manual simulation
or a plausible narrative cannot replace execution.

The first autonomous report is final for the comparison. Human review occurs
after it. No correction turn may be counted as first-attempt evidence.

### Retained evidence

Retain the exact two prompts; wall-clock boundaries; substantive commands with
working directory, timestamps and exit codes; environment and tool identities;
initial and final Git status/diff; every project-owned file; validation and
context outputs; a SHA-256 artifact manifest; source/documentation/runtime
identities; and every human clarification or correction after the first report.
Do not retain credentials, private reasoning or irrelevant shell history.

### Independent scoring

Report environment eligibility, public orientation, structural validation,
published-runtime execution, technical execution, semantic fidelity, evidence
binding, context quality, human intervention, owner acceptance, measured
utility and durable-adoption disposition separately. A structural pass cannot
replace any other dimension, while published-runtime `NOT RUN` does not by
itself make technical execution fail when another supported route is correctly
bound and verified. Severity and materiality accompany omissions and inventions
rather than relying on counts alone.

The primary comparison question is:

> Does the first autonomous attempt produce the smallest valid project-owned
> adoption, truthful ownership/provenance and blockers, correct
> documentation/source/runtime identities and routes, and an actual bounded
> context without Gnostoa-maintainer correction?

The rerun is not a causal productivity experiment, vendor ranking,
product-market-fit result, general adopter guidance or B3. Decision 0036's
Gnostoa-self fresh-agent test also remains separate.

## Frozen fresh-rerun result

The accountable-owner disposition is:

> `REJECT — proceed to the single final #117 reconciliation.`

There is no aggregate pass. The agent did not establish adoption, but the
owner's read-only audit binds the negative result to the frozen Mail subject.

### Subject and evidence read-back

The subjects were re-read on `2026-08-25` before this reconciliation:

| Subject | Exact identity and observation |
|---|---|
| Improved Gnostoa documentation | commit `1e60bdecde82f04f9274c551f5d7fd49a2985e2b`; tree `a41e0177bd1d432bf9c6328f781ab4f63a71f880`; public digest `sha256:a107c33d5465d71628805d55c62ea3b9aa77a51776b59ece47577c4af02d5757` |
| Immutable execution subject | `ghcr.io/ktogias/gnostoa@sha256:0cd31a2a649c4ffede8972680c6779c981decf5ce8605f749fa7d58751472f80`; anonymously addressable, but not executed in the rerun |
| Mail subject | commit `b54bd0e637497217e8fec85ad59fe8bdf58e52a8`; tree `b400a791f90415f2ce761c2f8412bcd4d6cded5e` |
| Work Item | #117 `OPEN` with `roadmap:now`; latest examined comment `5413291225`, updated `2026-08-25T16:12:09Z` |
| Rerun transcript and local audit | supplied by the owner for this reconciliation; not independently provider-addressable |

The documentation and immutable execution identities remain separate. The
execution subject's availability does not establish that the experiment agent
selected or ran it.

### Rerun evidence register and chronology

| ID | Observation |
|---|---|
| `FR1` | At owner-reported local time `19:28`, the first command after the clone prompt was `git clone https://github.com/ktogias/mail`. It failed with `fetch-pack: unexpected disconnect while reading sideband packet`. The agent called this a timeout, but only the disconnect is observed. A retry with `git clone --depth 1 https://github.com/ktogias/mail` succeeded. The UI reported `2m17s`. |
| `FR2` | At owner-reported local time `19:31`, the agent received only `adopt https://github.com/ktogias/gnostoa in the already cloned mail/ repository.` It ran only `git remote add gnostoa https://github.com/ktogias/gnostoa && git remote -v`, then represented the added remote as completed adoption. The UI reported `6.0s`. |
| `FR3` | The owner's independent read-only audit found the exact frozen Mail commit/tree, a shallow clean `main` tracking `origin/main`, remotes `origin` and `gnostoa`, no `refs/remotes/gnostoa/main`, and Gnostoa-ref lookup exit `128`. The tracked diff and untracked-file list were empty. `.knowledge-kit/`, `.knowledge/`, `knowledge/` and `ci/verify` were absent. |
| `FR4` | The only observed effect was local `.git/config` remote registration. No Gnostoa fetch, documentation consultation, execution-route selection, knowledge authoring, validation, context generation, project-suite execution, commit, push, PR or provider mutation occurred. |

The clone interruption was recovered. The recovery is an environment
observation, not adoption evidence. The agent's completion claim has no
artifact, exit-code, lock or immutable execution receipt. The owner's audit is
sufficient to establish what did **not** occur without upgrading the agent's
claim into execution evidence.

### Final comparison matrix

| Dimension | Baseline | Frozen rerun | Bounded disposition |
|---|---|---|---|
| Environment | `BLOCKED` for declared project suites | `PASS` after a recovered clone interruption; exact tool versions incomplete | Workspace/source access succeeded in the rerun; no suite environment was exercised. |
| Public orientation | `PARTIAL` | `FAIL` | The agent did not discover or enter the public adoption route. |
| Technical adoption execution | `PARTIAL` | `NOT RUN` | Git remote registration is not Gnostoa adoption. |
| Structural validation | `PASS` through source-built v0.1.2 tooling | `NOT RUN` | No supported Gnostoa route executed. |
| Bounded-context generation | `NOT RUN` | `NOT RUN` | No context artifact exists. |
| Project-suite verification | `BLOCKED` | `NOT RUN` | The rerun never reached suite declaration or preflight. |
| Published OCI execution | `NOT RUN` | `NOT RUN` | The immutable image remained available but unused. |
| Semantic fidelity | `FAIL` | `FAIL` | Remote registration was misclassified as completed adoption. |
| Experiment-agent evidence binding | incomplete (`O1`–`O4`) | `FAIL` | The claim was not bound to execution or artifacts. |
| Owner acceptance | `REJECT` | `REJECT` | The rerun result is rejected. |
| Measured utility | `UNKNOWN` | `UNKNOWN` | Adoption did not execute. |
| Durable adoption | `NO` | `NO` | No adopter knowledge or durable integration exists. |

### Causal and Decision 0045 disposition

1. The agent took an immediate semantic shortcut and stopped prematurely
   (`FR2`–`FR4`). Adding a repository remote is not Gnostoa adoption.
2. The A1 guidance was never consulted (`FR4`). Its content-level
   effectiveness was therefore not tested.
3. Decision 0045's predicted end-to-end improvement was not observed in this
   frozen rerun. The result exposes an activation dependency for
   documentation-only remediation: an agent must first discover and enter the
   public adoption route before its content can affect behaviour.
4. Relative to the baseline first attempt, the rerun stopped earlier. One
   rerun does not establish regression, causation, model reliability or vendor
   ranking.
5. No Gnostoa validator, runtime, OCI bytes, schema or guidance-content rule
   was exercised (`FR3`, `FR4`), so this result demonstrates no defect in those
   surfaces.
6. The minimal prompt intentionally supplied no hidden correction or success
   checklist. It is not rewritten after the result.
7. Correcting or continuing the same experiment agent would be recovery
   evidence, not the frozen fresh result, and is excluded.

This result rejects the adoption outcome. It neither selects a replacement
for A1 nor establishes that the A1 text is ineffective once reached.

## Evidence limits and owner stop

- The evaluator/model identity is not independently established. If retained,
  `Build · Big Pickle` is only an owner-reported UI label.
- Exact Git, Docker, PHP and Composer versions were not retained.
- Timestamps and durations are owner/UI reported rather than independently
  measured.
- No generated artifact hashes exist because no artifacts were created.
- The transcript and local audit are owner-supplied evidence. The local
  workspace is not provider-addressable.
- The result supports the bound negative observations above, not a reliability
  rate, regression claim, causal model comparison or vendor ranking.

The single frozen rerun is complete. Do not replay, repair or continue it, and
do not begin B3 or claim Decision 0036 satisfaction. The remaining #117 action
is only integration and close-last reconciliation of this final knowledge
record. No further remediation is selected here.
