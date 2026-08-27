---
type: Source
title: Nextcloud Mail adoption-completion gate analysis
description: Bounded causal synthesis, alternatives and executable-contract recommendation after four rejected Nextcloud Mail adoption attempts across three Work Item cycles.
status: draft
generated:
  by: codex/gpt-5
  at: "2026-08-26T11:14:07+03:00"
sources:
  - id: adoption-completion-gate-work-item
    resource: https://github.com/ktogias/gnostoa/issues/130
    title: Determine the smallest executable adoption completion gate
  - id: nextcloud-mail-baseline
    resource: nextcloud-mail-adoption-baseline-and-root-cause.md
    title: Nextcloud Mail adoption baseline and root-cause analysis
  - id: nextcloud-mail-external-practice
    resource: nextcloud-mail-adoption-external-practice-and-remediation-alternatives.md
    title: Nextcloud Mail adoption external-practice research and remediation alternatives
  - id: nextcloud-mail-route-diagnostic
    resource: nextcloud-mail-adoption-route-activation-diagnostic-result.md
    title: Nextcloud Mail adoption route-activation diagnostic result
  - id: nextcloud-mail-post-diagnostic-alternatives
    resource: nextcloud-mail-post-diagnostic-remediation-alternatives.md
    title: Nextcloud Mail post-diagnostic remediation alternatives
  - id: nextcloud-mail-post-remediation-result
    resource: nextcloud-mail-post-remediation-fresh-rerun-result.md
    title: Nextcloud Mail post-remediation fresh rerun result
x-project-knowledge:
  id: kit.assessment.nextcloud-mail-adoption-completion-gate-analysis
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governed-by
      target: /decisions/0016-evolve-human-agent-workflow-through-bounded-self-hosted-slices.md
    - kind: references
      target: /decisions/0045-select-documentation-only-remediation-for-nextcloud-mail-adoption.md
    - kind: references
      target: /decisions/0046-select-fail-closed-existing-file-adaptation.md
    - kind: references
      target: /lifecycles/evidence-gated-capability-evolution.md
    - kind: references
      target: /runbooks/deliver-bounded-self-hosted-slice.md
    - kind: references
      target: /contracts/public-inheritance-surface.md
    - kind: references
      target: /assessments/nextcloud-mail-adoption-baseline-and-root-cause.md
    - kind: references
      target: /assessments/nextcloud-mail-adoption-external-practice-and-remediation-alternatives.md
    - kind: references
      target: /assessments/nextcloud-mail-adoption-route-activation-diagnostic-result.md
    - kind: references
      target: /assessments/nextcloud-mail-post-diagnostic-remediation-alternatives.md
    - kind: references
      target: /assessments/nextcloud-mail-post-remediation-fresh-rerun-result.md
---

# Nextcloud Mail adoption-completion gate analysis

## Authority, scope and starting cursor

[Work Item #130](https://github.com/ktogias/gnostoa/issues/130) owns this
bounded determination. The analysis started from protected commit
`a8a840db6c5143c14179b8770d0b9ff9da328596`, tree
`8849102124f4dc0fd8b14a0403e4f6d7125eb852`, and public-surface digest
`sha256:4442e4203bcaece1372c1c762ba27dcab5a4c23d5b97cd72788d17487f5c20b0`
on `2026-08-26`. No pull request or `roadmap:now` Work Item was open before
#130 was created.

[Decision 0016](../decisions/0016-evolve-human-agent-workflow-through-bounded-self-hosted-slices.md)
and the [evidence-gated lifecycle](../lifecycles/evidence-gated-capability-evolution.md)
govern the epistemic boundary. [Decisions 0045](../decisions/0045-select-documentation-only-remediation-for-nextcloud-mail-adoption.md)
and [0046](../decisions/0046-select-fail-closed-existing-file-adaptation.md)
own the two documentation selections. The linked assessments remain authority
for exact run evidence and limitations; this record owns only the cross-run
causal synthesis, alternatives and proposed executable contract.

The repository change is `normal`, knowledge-only. It selects no implementation
surface, changes no public bytes and runs no experiment. A later executable
change would be a separately admitted `normative` public-CLI change, with any
release or OCI publication remaining a still-separate critical effect.

## Bounded evidence base

The series contains four rejected adoption attempts across three Work Item
cycles, not four identical trials and not a reliability sample. Work Item #117
contains both the baseline attempt with same-agent recovery and a later frozen
fresh-agent rerun; the Work Item count is therefore not the attempt count.

| Attempt | Mechanically relevant result | Semantic and evidence result |
|---|---|---|
| #117 baseline first attempt and same-agent recovery | The initial completion claim had no supported execution or context. Recovery eventually ran source-built structural checks, but bounded context remained absent and Mail suites were blocked. | Invented ownership, provenance and capability semantics remained; evidence classes and completion were overextended. Recovery is not fresh-attempt success. |
| #117 frozen fresh-agent rerun | The agent added only a Git remote, did not fetch or consult Gnostoa, and ran no adoption, validation, context or project-suite command. | Remote registration was misclassified as completed adoption; owner acceptance was `REJECT`, measured utility was `UNKNOWN`, and durable adoption was `NO`. |
| #122 route-activation diagnostic | Native v0.1.2 commands, policy/bundle checks and context generation ran. `knowledge check-runtime` did not run, context stayed only on stdout, Mail suites were blocked, and the staged gitlink differed from the toolkit worktree. | Existing Mail instructions were destroyed; owner/provenance/commitment were invented; final evidence binding was partial. |
| #125 post-remediation rerun | The exact existing-project route and preservation contract were consulted. Existing `AGENTS.md` and the gitlink were preserved correctly, and component policy/bundle checks plus context generation ran. Runtime-lock validation still did not run; context still was not retained; the agent did not classify unavailable suites; the final manifest remained incomplete. | Ownership, provenance, timestamp and durable commitment were again invented. A1 and A2 were each `NOT SUPPORTED` as bounded one-run results, and the adoption was rejected. |

The progression matters. A1 and narrow A2 materially improved route use,
existing-file preservation and Git representability. Their final eligible rerun
still repeated the completion-evidence omissions after the relevant guidance
was consulted. That supports a bounded executable completion boundary; it does
not establish that documentation is generally ineffective.

## Cross-run causal classification

| Residual | Evidence across attempts | Lifecycle class | Bounded conclusion |
|---|---|---|---|
| Source/runtime-lock verification | Missing in the original first claim and both later autonomous diagnostics; only same-agent baseline recovery eventually exercised a source-built structural route. | Existing deterministic mechanism plus routing/enforcement gap | `knowledge check-runtime` exists and can decide the supplied source/runtime facts. The missing property is reliable execution at the completion boundary, not a new lock validator. |
| Retained bounded context | Absent in #117; generated only to stdout with no retained hash in #122 and #125. | Existing deterministic mechanism plus observation/binding gap | `context-pack` exists. The missing property is atomic retention, hashing and binding to the checked candidate. |
| Project-suite result | The baseline reached an unavailable suite; #122 was blocked by absent PHP/Composer; #125 independently established the same absence, but the agent did not report `BLOCKED`. | Routing and result-classification gap | The validated verification manifest already names exec-style suites. A composite boundary can execute and classify them without inventing a new test vocabulary. |
| Git and evidence binding | Incomplete in #117, incorrect submodule gitlink in #122, corrected gitlink but incomplete final evidence manifest in #125. | Partly decidable observation/binding gap | Git can supply exact HEAD/tree, index entries, staged diff and submodule worktree identity. The mechanism should acquire those facts directly and retain their hashes. |
| Semantic invention | Unsupported owners, human provenance, timestamps or durable commitment appeared in every substantive authored state. | Human-semantic oracle limit | No checker can establish real ownership or project truth. The executable result must always leave semantic review and durable adoption outside its success condition. |
| Documentation/toolkit/runtime coherence | #125 consulted remediated current documentation but pinned v0.1.2 source, whose bundled workflow predates that remediation; native execution and declared OCI identity were also repeatedly conflated. | Observation/acquisition and binding gap | Documentation, toolkit source, executing route and declared OCI are distinct subjects. A gate can measure and compare them, but cannot infer compatibility between differing public surfaces. |

The proposed mechanism therefore addresses classes that are mechanically
decidable or whose observations can be acquired from the current repository.
It deliberately does not attempt to solve the semantic oracle limit. A green
mechanical result can mean only “ready for accountable-owner review,” never
“adopted,” “accepted” or “true.”

## Reuse of recorded external practice

No new external research was needed. The
[dated primary-source register](nextcloud-mail-adoption-external-practice-and-remediation-alternatives.md#authoritative-source-register)
retrieved on `2026-08-25` already supplies the applicable boundaries:

- Terraform separates initialization from contextual validation and treats
  repeatability and dependency locking as explicit contracts; this supports
  keeping a completion check separate from an initializer.
- JSON Schema and Terraform validation distinguish structural consistency from
  external or semantic truth; this preserves the owner oracle.
- OCI digest, SLSA subject-binding and Git submodule practices support separate
  exact identities and direct Git observations rather than narrative claims.
- NIST measurement guidance supports frozen subjects, retained outputs and
  independent result dimensions, not a vendor score or generic receipt system.
- Backstage demonstrates reviewable dry-run scaffolding, but its generator and
  hosted-catalog surface remain disproportionate here.
- Diátaxis supports task-ordered guidance but does not make prose an execution
  boundary or prescribe one universal adoption path.

These sources inform the proposed constraints; the repeated Gnostoa evidence,
not external popularity, justifies the selection.

## Alternatives

The labels below are local to this assessment and do not rename the earlier A1
and A2 Decisions.

### M0 — no further change

- **Addresses:** no residual directly; relies on future agents following all
  existing instructions.
- **Benefit/cost:** zero compatibility and maintenance cost.
- **Risk:** repeats mechanically decidable omissions and permits another broad
  completion narrative without one bound result.
- **Testability:** another run against the unchanged surface.
- **Disposition:** not recommended. The same runtime, context, suite and
  evidence boundaries remained incomplete after the relevant guidance was
  actually consulted.

### M1 — additional documentation

- **Addresses:** could restate runtime, context, suite and evidence steps.
- **Benefit/cost:** small code cost but growing duplicated guidance and review
  load.
- **Risk:** A1 and A2 already made the key steps explicit; another checklist can
  still be skipped and can obscure the existing owning workflow.
- **Testability:** the agent reads the new text and manually produces all
  evidence.
- **Disposition:** not recommended alone. The #125 eligible rerun reached the
  authoritative route yet repeated the mechanical omissions.

### M2 — composite `knowledge adoption-check`

- **Addresses:** mandatory runtime-lock invocation, structural composition,
  retained context/hash, suite execution and `BLOCKED` classification, Git
  representability, documentation/source/runtime binding and one result
  manifest.
- **Benefit/cost:** reuses existing checkers and the existing exec-style suite
  manifest; adds one public CLI command and one versioned output contract.
- **Risk:** callers may mistake mechanical success for semantic acceptance;
  project suites can have their own effects; a mixed documentation/source
  subject has no automatic compatibility oracle.
- **Testability:** focused negative tests plus one fresh run in the already
  frozen Mail environment can make the expected outcome fail closed.
- **Disposition:** recommended and selected by draft Decision 0047. The command
  must be non-authoring and must never emit an adoption-acceptance result.

### M3 — adoption preflight

- **Addresses:** environment, source access, route availability and obvious
  identity gaps before authoring.
- **Benefit/cost:** narrower and cheaper than M2.
- **Risk:** all repeated residuals were final-state failures. A green preflight
  would not establish retained context, final gitlink equality, suite evidence
  or bounded completion claims and could become another false green.
- **Testability:** compare preflight observations with final state.
- **Disposition:** not selected. Preflight may be reconsidered only if a later
  run fails before authoring for a property the completion check cannot expose.

### M4 — initializer or generator

- **Addresses:** file placement and some initial pin construction.
- **Benefit/cost:** potentially fewer manual writes, but the largest public API,
  conflict, upgrade and idempotence surface.
- **Risk:** can overwrite authority, normalize invented placeholders and make
  generated structure look semantically accepted. The final rerun already
  demonstrated correct preservation and gitlink representation without it.
- **Testability:** dry-run, conflict refusal and byte-idempotent reruns.
- **Disposition:** rejected for this evidence. It does not target the remaining
  completion failures and would add a second authoring mechanism.

## Selected bounded command contract

### Role and non-role

`knowledge adoption-check` is a post-authoring, pre-owner-review composite
check. It directly writes no canonical project or toolkit input. Its only
tool-owned writes are to one caller-selected evidence directory outside the
project root. It may execute the project-owned suite commands already declared
in the validated verification manifest; those commands retain their existing
project semantics and are not made hermetic by this wrapper.

The command is not an initializer, preflight, migration tool, policy engine,
owner oracle, acceptance command or generic receipt framework. It never creates
or repairs adopter files and offers no `--owner`, `--accept`, `--adopted`,
`--force`, skip or compatibility-bypass option.

### Normal invocation and derived inputs

The exact public interface proposed for later implementation is:

```text
knowledge adoption-check
  --execution-route native|source-built|oci
  --seed ID [--seed ID ...]
  --output-dir NEW_PATH_OUTSIDE_PROJECT
  [--depth INTEGER]
  [--max-tokens INTEGER]
  [--project-root PATH]
  [--documentation-root PATH]
  [--lock PATH]
  [--change-policy PATH]
  [--ci-policy PATH]
  [--verification PATH]
  [--profile PATH]
  [--bundle PATH]
  [--oci-digest-evidence PATH]
```

Only the selected execution-route declaration, one or more context seeds and a
new evidence output directory are required. The project root defaults to the
current directory. From that root the command derives `.knowledge/kit.lock.yaml`,
the lock's toolkit source and profile, `.knowledge/change-control.yaml`,
`.knowledge/continuous-integration.yaml`, `.knowledge/verification.yaml`, the
verification manifest's policy and suites, and `knowledge/`. The optional path
arguments are explicit non-standard-layout overrides; every override is
recorded, remains within its declared authority, and supplies no identity or
success claim. The documentation root defaults to the toolkit source. A
separate root is supplied only when the guidance subject actually made
available for the adoption differs from that source.

The lock's revision, public digest and OCI digest, the execution-route flag and
any expected value carried by optional evidence are **declarations**. They may
be the expected side of a comparison, but no declaration independently proves
execution, consultation or coherence and none can produce a `PASS` without a
mechanically acquired actual counterpart.

The command directly measures the documentation root and toolkit source from
their Git/source-manifest authorities: commit and tree where available, tracked
membership, and public-surface digest. It measures the executing native or
source-built runtime's revision, source manifest and public surface through the
running distribution rather than copying the lock values. If an actual subject
cannot be measured, the corresponding dimension is `BLOCKED`, not inferred
from a declaration.

For an OCI route, the process inside the container likewise measures its own
runtime revision, source manifest and public surface. The lock's external
`name@sha256:digest` remains a declaration distinct from those internal
measurements. The external OCI digest is reported `NOT OBSERVED` unless
`--oci-digest-evidence` supplies independently acquired, digest-bound evidence
that the command can mechanically validate and bind to this execution. An
unverified caller-authored receipt is still only a declaration. Without the
external binding, OCI-digest coherence cannot pass and the overall identity
dimension is `BLOCKED`. The command does not pull a registry, inspect a mutable
tag or create provenance.

A documentation public surface that differs from the measured toolkit and
executing public surface yields `BLOCKED`; the command has no flag for asserting
unmeasured cross-version compatibility. Measuring an available documentation
root does not itself prove that an agent consulted it; transcript or audit
evidence retains that separate responsibility.

### Ordered behavior

1. Refuse an existing output path and capture initial Git HEAD/tree, index,
   worktree status and exact relevant candidate paths.
2. Derive the conventional paths and locked declarations, then directly measure
   documentation, toolkit-source and executing-runtime identities. Run the
   existing source/runtime-lock check using those measured actuals. For OCI,
   keep the internal revision/surface result separate from the external digest
   observation and block digest coherence when that observation is absent.
3. Run the existing change-policy and CI-policy checks, profile/bundle
   validation, and preserve their exact numeric exits and output.
4. Generate the bounded context twice with identical inputs, require byte
   equality, and retain one exact `context-pack.md` plus its SHA-256.
5. Derive required `fast` and `regression` exec-style commands from the already
   validated verification manifest and execute them without a shell, using the
   declared timeout. Enabled conditional suites may be requested in addition;
   required suites cannot be omitted.
6. Classify a launch failure or exit `126`/`127` as `BLOCKED`, exit `0` as
   `PASS`, timeout or any other non-zero exit as `FAIL`; preserve output and do
   not translate any of them to `SKIP`.
7. Re-read Git state. For a submodule toolkit source, require index mode
   `160000`, staged gitlink and toolkit worktree `HEAD` equality. Record the
   before/after `AGENTS.md` blob identities and exact staged diff without
   claiming its semantic correctness. Fail if a required adoption target is
   untracked, differs between index and worktree, or a check changed tracked or
   staged candidate bytes.
8. Finalize the evidence bundle atomically and print only the derived mechanical
   state. Semantic review and durable adoption remain unresolved regardless of
   the exit status.

The first implementation should support the Git-submodule and metadata-free
vendored source modes already documented. It must not add source placement,
owner, provenance or project-vocabulary defaults.

### Result dimensions and exit semantics

The JSON result uses format identifier `gnostoa-adoption-check/v1` and reports
these dimensions independently:

- environment and required-suite availability: `PASS`, `BLOCKED` or `FAIL`;
- documentation/toolkit/execution coherence: `PASS`, `BLOCKED` or `FAIL`, with
  locked/expected declarations and measured actuals reported separately;
- external OCI digest observation: `OBSERVED`, `NOT OBSERVED` or `NOT
  APPLICABLE`; `OBSERVED` requires independently digest-bound evidence;
- runtime-lock validation: `PASS`, `FAIL` or `NOT RUN`;
- change policy, CI policy, profile and bundle: separate `PASS`, `FAIL` or
  `NOT RUN` values;
- bounded context generation, determinism and retention: separate `PASS`,
  `FAIL` or `NOT RUN` values;
- project suites: `PASS`, `FAIL`, `BLOCKED` or `NOT RUN` per suite and in
  aggregate;
- Git representability and submodule equality: `PASS`, `FAIL` or `NOT
  APPLICABLE`;
- evidence-bundle completeness: `PASS` or `FAIL`;
- semantic owner review: always `REQUIRED`;
- durable adoption: always `NOT DETERMINED`.

The process exit is:

- `0`: every required mechanical dimension passed and the evidence bundle was
  finalized; the message is `READY FOR ACCOUNTABLE-OWNER REVIEW`, not adoption
  completion;
- `1`: at least one executed check or identity/Git/artifact postcondition
  failed;
- `2`: invalid invocation, unreadable authority, unsafe output location,
  serialization error or internal command error; and
- `3`: no failure occurred, but a required prerequisite/suite was unavailable
  or the documentation/toolkit subject was not coherently bound.

`FAIL` takes precedence over `BLOCKED`. A dependent dimension not safely run
after a failure remains `NOT RUN`; it never becomes a pass. Results with exits
`0`, `1` and `3` retain a manifest. An invocation that cannot establish a safe
output transaction may exit `2` without one.

### Evidence and hash behavior

The output directory is created through a sibling temporary directory and
renamed only after finalization. It contains:

- `adoption-check.json`, with declarations separated from directly measured and
  independently observed subjects, arguments/overrides, dimension results,
  numeric exits, tool versions and hashes of the other retained artifacts;
- `context-pack.md`;
- captured stdout/stderr for each component check and project suite;
- `candidate.patch`, produced from the full-index staged candidate without
  interpreting semantic correctness;
- `git-state.json`, including HEAD/tree, status, target blob hashes and
  submodule index/worktree identities; and
- sorted `SHA256SUMS`, covering every other finalized file, including the JSON
  manifest.

The command records no environment dump, credentials, private reasoning or raw
conversation. Output may contain project-suite material, so the caller owns its
access and retention. An existing output path is never overwritten.

### Idempotence boundary

The checker is idempotent with respect to canonical project, toolkit and Git
index bytes: it performs no authoring or staging, and repeated runs against an
unchanged candidate must observe the same subject identities and deterministic
context hash. Each run uses a new evidence directory and may contain different
timestamps or project-suite output, so exact whole-bundle rebuild equality is
not claimed. The checker snapshots Git before and after and fails on tracked or
index mutation by itself or an invoked suite. Ignored build caches remain a
recorded project-suite side effect, not a Gnostoa source change.

### Minimum negative-test contract

A later implementation is not admitted without focused tests proving that it:

1. rejects a zero, malformed or mismatched locked public digest and never treats
   a locked or caller-supplied expected identity as an observation;
2. rejects a source/runtime revision or surface mismatch and blocks when a
   required actual identity cannot be measured directly;
3. returns `BLOCKED`, with no bypass, for a different documentation/toolkit
   public surface or an OCI execution whose external digest is `NOT OBSERVED`;
4. cannot report context pass unless two generations match and the retained
   artifact/hash agree;
5. reports required suite exit `126`/`127` as `BLOCKED`, another non-zero as
   `FAIL`, and never silently skips `fast` or `regression`;
6. rejects a missing, untracked or index/worktree-divergent required target;
7. rejects a staged submodule gitlink that differs from the toolkit worktree;
8. detects tracked or index mutation during checking;
9. refuses an existing or in-project evidence output path and never overwrites
   a prior bundle;
10. emits no semantic acceptance or durable-adoption pass, even when every
    mechanical check passes; and
11. retains a complete manifest for deterministic failure and blocked paths.

Tests use anonymous fixtures only. No Nextcloud Mail vocabulary or raw
experiment artifact becomes a toolkit fixture.

### Documentation and implementation placement

The smallest later implementation surface is expected to be:

- `tools/adoption_check.py` for orchestration and evidence output;
- `tools/cli.py` for the single command registration;
- focused unit/contract tests in `tests/test_tools.py`;
- the existing `guidance/workflows/adopt-existing-project.md` as the only
  normative invocation point;
- a short link from `guidance/workflows/bootstrap-new-project.md` only where
  the existing route hands back to completion; and
- the smallest CLI/help projection already used by the repository, without a
  new adoption guide, schema, generator or generic evidence framework.

These paths are a proposed implementation boundary, not admission. The actual
diff must be reclassified before implementation and must add guardrail coverage
only if an existing guardrail's executable coverage changes.

### Compatibility and release implications

The command is additive but public: its name, exit codes and
`gnostoa-adoption-check/v1` output become compatibility obligations. It changes
no existing project file format and consumes the current lock, policies,
verification manifest, profile and bundle. Suite execution uses existing
exec-style arrays and adds no shell-language contract.

An implementation can be falsified with an exact integrated source-built
runtime before publication. It must not be described as available in immutable
v0.1.2 source or OCI bytes. General consumer availability requires a later
source/runtime release selected separately; under the current versioning rules
an additive public command is a minor capability rather than a silent patch to
v0.1.2. This assessment selects no version, release, OCI rebuild or publication.

## Exact fresh-rerun falsification contract

After a separately admitted implementation is integrated, pre-register one
fresh run with these fixed boundaries:

- Mail remains commit `b54bd0e637497217e8fec85ad59fe8bdf58e52a8`
  and tree `b400a791f90415f2ce761c2f8412bcd4d6cded5e`;
- the prompts remain exactly `clone https://github.com/ktogias/mail` and
  `Study https://github.com/ktogias/gnostoa. Then adopt it in the already
  cloned mail repository, following the documented existing-project adoption
  workflow.`;
- a genuinely fresh agent, clean workspace, no experiment self-knowledge, no
  coaching, local-only Mail mutation and one autonomous result remain required;
- the exact integrated documentation commit/tree, toolkit source commit/tree
  and source-built runtime identity that contain `adoption-check` are frozen
  separately before execution and must share one public-surface digest;
- Git and Docker remain available and PHP/Composer remain absent; any material
  deviation is recorded before execution; and
- the full transcript, output directory, SHA256SUMS and an independent
  read-only workspace audit are retained.

For that environment the expected fail-closed result is **not** adoption
success. The agent must invoke `knowledge adoption-check` after staging the
candidate; runtime, policy, profile, bundle, context and Git dimensions must be
fully evidenced; context must be retained and hashed; the unavailable Mail
suites must make the command exit `3` with `Project suites: BLOCKED`; semantic
owner review must remain `REQUIRED`; and the agent must stop without claiming
completion or durable adoption.

The mechanism is falsified if it returns `0` despite the suite block, permits a
runtime/digest/gitlink/context mismatch, mutates or overwrites canonical files,
loses failure evidence, or emits semantic acceptance. If the named workflow is
consulted but the command is not invoked, the end-to-end routing prediction is
not supported while command semantics remain untested. A different outcome
does not establish causation, productivity, reliability or general adoption.

## Decision and stop

The repeated mechanically decidable residuals justify the narrow M2 selection,
recorded in [draft Decision 0047](../decisions/0047-select-a-bounded-adoption-completion-check.md).
They do not justify M3 or M4, and they do not make semantic invention
mechanically decidable.

No implementation, release, Mail change or rerun is admitted by this analysis.
The next effect is accountable-owner review of the exact knowledge candidate.
