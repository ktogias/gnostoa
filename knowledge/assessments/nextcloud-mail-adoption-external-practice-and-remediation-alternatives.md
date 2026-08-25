---
type: Source
title: Nextcloud Mail adoption external-practice research and remediation alternatives
description: Bounded primary-source research and unselected remediation alternatives for the measured Nextcloud Mail adoption causes.
status: draft
generated:
  by: codex/gpt-5
  at: "2026-08-25T14:20:48Z"
sources:
  - id: nextcloud-mail-adoption-work-item
    resource: https://github.com/ktogias/gnostoa/issues/117
    title: Analyze and remediate the Nextcloud Mail minimal-adoption failure
  - id: nextcloud-mail-adoption-baseline
    resource: https://github.com/ktogias/gnostoa/blob/f7b05a30921eef49cb55210a1aefb5babd064c88/knowledge/assessments/nextcloud-mail-adoption-baseline-and-root-cause.md
    title: Nextcloud Mail adoption baseline and root-cause analysis
  - id: diataxis-how-to-guides
    resource: https://diataxis.fr/how-to-guides/
    title: Diátaxis how-to guides
  - id: diataxis-tutorials
    resource: https://diataxis.fr/tutorials/
    title: Diátaxis tutorials
  - id: backstage-software-templates
    resource: https://backstage.io/docs/features/software-templates/
    title: Backstage Software Templates
  - id: backstage-writing-templates
    resource: https://backstage.io/docs/features/software-templates/writing-templates/
    title: Backstage writing templates
  - id: terraform-init
    resource: https://developer.hashicorp.com/terraform/cli/commands/init
    title: Terraform init command
  - id: terraform-validate
    resource: https://developer.hashicorp.com/terraform/cli/commands/validate
    title: Terraform validate command
  - id: json-schema-core
    resource: https://json-schema.org/draft/2020-12/json-schema-core
    title: JSON Schema 2020-12 core
  - id: json-schema-annotations
    resource: https://json-schema.org/understanding-json-schema/reference/annotations
    title: JSON Schema annotations
  - id: oci-distribution-spec
    resource: https://github.com/opencontainers/distribution-spec/blob/v1.1.1/spec.md
    title: OCI Distribution Specification 1.1.1
  - id: docker-pull-by-digest
    resource: https://docs.docker.com/reference/cli/docker/image/pull/
    title: Docker image pull reference
  - id: slsa-provenance
    resource: https://slsa.dev/spec/v1.2/provenance
    title: SLSA 1.2 provenance
  - id: slsa-verification-summary
    resource: https://slsa.dev/spec/v1.2/verification_summary
    title: SLSA 1.2 verification summary attestation
  - id: git-submodules
    resource: https://git-scm.com/docs/gitsubmodules
    title: Git submodules guide
  - id: go-modules
    resource: https://go.dev/ref/mod
    title: Go modules reference
  - id: nist-ai-rmf-measure
    resource: https://airc.nist.gov/airmf-resources/playbook/measure/
    title: NIST AI RMF Playbook Measure function
  - id: nist-agent-evaluation-practices
    resource: https://www.nist.gov/caisi/cheating-ai-agent-evaluations/4-practices-detecting-and-preventing-evaluation-cheating
    title: NIST CAISI agent-evaluation practices
x-project-knowledge:
  id: kit.assessment.nextcloud-mail-adoption-external-practice-and-remediation-alternatives
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governed-by
      target: /decisions/0016-evolve-human-agent-workflow-through-bounded-self-hosted-slices.md
    - kind: references
      target: /assessments/nextcloud-mail-adoption-baseline-and-root-cause.md
    - kind: references
      target: /lifecycles/evidence-gated-capability-evolution.md
    - kind: references
      target: /runbooks/deliver-bounded-self-hosted-slice.md
    - kind: references
      target: /assessments/b3-independent-adoption-experiment-design.md
---

# Nextcloud Mail adoption external-practice research and remediation alternatives

## Status, authority and boundary

[Work Item #117](https://github.com/ktogias/gnostoa/issues/117) owns the
baseline-to-rerun cycle. [Decision 0016](../decisions/0016-evolve-human-agent-workflow-through-bounded-self-hosted-slices.md)
and the [evidence-gated lifecycle](../lifecycles/evidence-gated-capability-evolution.md)
govern this research. The
[Phase-1 assessment](nextcloud-mail-adoption-baseline-and-root-cause.md) remains
authoritative for the observations, causal identifiers, evidence limits and
frozen rerun contract. This record owns only dated external-practice research,
the alternatives comparison and a non-binding recommendation.

Research began from protected commit
`f7b05a30921eef49cb55210a1aefb5babd064c88`, tree
`e66e0eb09aa1cf8e67f469c9cb598b870c4c24b7`, and Work Item #117 as updated
`2026-08-25T14:07:01Z`. The three owner-reported raw-evidence comments remain
`5410942181`, `5410945232` and `5410947378`. Current Gnostoa adoption,
bootstrap, template, schema and CLI contracts were read from that exact tree.

The actual proposed change is `normal`, knowledge-only research. It changes no
adopter contract. No remediation, Decision, implementation admission or fresh
rerun is created here. Accountable selection remains pending; any normative
guidance or executable change requires its own classification, Decision and
admission under #117.

## Method and applicability rule

All external sources below are primary standards, official product
documentation or authoritative public-sector measurement guidance. Each was
retrieved on `2026-08-25`. Secondary summaries were not used to carry a
conclusion.

An external practice is marked **direct** only where it supplies a concrete
constraint for an observed Phase-1 cause or gap. **Background** means it is a
useful design analogy but cannot by itself justify a Gnostoa change. Frequency
or popularity is not treated as correctness. The existing Gnostoa human-oracle
and evidence boundaries remain authoritative where external tooling cannot
establish project truth.

## Current internal-contract read-back

| Existing authority or mechanism | Exact current fact | Phase-1 implication |
|---|---|---|
| `docs/core/adoption.md` | Already distinguishes bounded evaluation from durable full adoption and requires unknown ownership to remain explicit and draft/unresolved. | `H1` and `H2` have authority; the gap is getting an agent to that choice before it authors, not inventing another semantic rule. |
| `guidance/workflows/adopt-existing-project.md` | Provides the durable existing-project sequence but delegates exact first-file construction and lock validation to bootstrap. | Confirms bounded routing concentration friction `F1`; the page itself is the natural task-oriented entry. |
| `guidance/workflows/bootstrap-new-project.md` | Defines the three roots, immutable source/runtime pins, templates, validators, context generation, native fallback and full provider adoption. | The required mechanisms exist. Their distribution across a full-adoption procedure adds orientation load but does not prove a missing CLI. |
| `templates/knowledge-kit.lock.yaml` and `.knowledge/kit.lock.yaml` target | The reusable template and target have different basenames, while bootstrap names both. | Confirms the small placement translation `F2`; a target map is smaller than a new format. |
| `schemas/` and policy checkers | Current source includes toolkit-lock, profile, continuous-integration and verification-manifest schemas plus executable policy checks. | Contradicts the raw report's temporary missing-schema theory; no additional schema is selected. |
| `tools/cli.py` | One `knowledge` surface exposes lock, policy, bundle, context, task and self-check commands. | Confirms `R4` was non-invocation of an existing context capability. |
| `tools/check_runtime_lock.py` | Compares declared lock data, computed source surface and caller/execution metadata that are actually supplied; it is not a registry pull or proof of which container bytes ran. | Preserves `D4`/`O2`: documentation must classify the selected route and observed evidence without overstating the checker. |

## Authoritative source register

| ID | Exact authoritative source and version | Retrieved | Factual practice read-back | Measured subject directness |
|---|---|---|---|---|
| `S1` | [Diátaxis: How-to guides](https://diataxis.fr/how-to-guides/), live authoritative page | `2026-08-25` | A how-to is goal-oriented, follows the user's real task in a logical sequence, omits digression and links detailed reference or explanation elsewhere. The source also allows sequences to fork, overlap and have multiple entry or exit points; it does not prescribe one universal “golden path” or adoption spine. | General documentation method; not a Gnostoa contract. |
| `S2` | [Diátaxis: Tutorials](https://diataxis.fr/tutorials/), live authoritative page | `2026-08-25` | A tutorial is learning-oriented, should show the destination, provide concrete early results, minimise choices and expose expected output. | Background for progressive disclosure; the Mail task was adoption work, not solely a tutorial. |
| `S3` | [Backstage Software Templates](https://backstage.io/docs/features/software-templates/) and [Writing Templates](https://backstage.io/docs/features/software-templates/writing-templates/), current official docs | `2026-08-25` | A scaffolder can collect explicit inputs, show a review page before mutation, expose per-step logs and dry-run filesystem results, and represent reruns as separate tasks. | Background for a tooling alternative. Backstage's hosted catalog, publication actions and service architecture do not fit this bounded local adoption. |
| `S4` | [Terraform `init`](https://developer.hashicorp.com/terraform/cli/commands/init), Terraform `1.15.x` docs | `2026-08-25` | Initialization is the first post-clone/config command, is safe to repeat, does not delete configuration or state, and writes a dependency lock that the documentation recommends committing for exact later selection. | Direct design criterion if initialization is ever admitted; Terraform backend/provider semantics do not transfer. |
| `S5` | [Terraform `validate`](https://developer.hashicorp.com/terraform/cli/commands/validate), Terraform `1.15.x` docs | `2026-08-25` | Validation checks syntax and internal consistency, requires initialization, does not validate remote services, and needs contextual execution for a particular run. | Direct analogy for `D2`, `O4`, `R5`; `terraform plan` is not a Gnostoa remediation. |
| `S6` | [JSON Schema 2020-12 core](https://json-schema.org/draft/2020-12/json-schema-core) and [annotation reference](https://json-schema.org/understanding-json-schema/reference/annotations) | `2026-08-25` | `$schema` declares the dialect for readers and tooling. `title` and `description` aid discovery. `default` is an annotation and does not fill missing values during validation. | Direct boundary for schema discoverability/default claims; it does not establish owner, provenance or domain truth, and does not mandate new Gnostoa fields. |
| `S7` | [OCI Distribution Specification `1.1.1`](https://github.com/opencontainers/distribution-spec/blob/v1.1.1/spec.md) | `2026-08-25` | A digest is a content-derived unique identifier; a tag is a human-readable pointer. A digest pull should verify returned bytes, and registry digest headers must be checked when used. | Direct for `D4`, `F3`, `O2`; OCI is only one supported execution route. |
| `S8` | [Docker image-pull reference](https://docs.docker.com/reference/cli/docker/image/pull/), current official docs | `2026-08-25` | Pulling by digest selects a fixed image version rather than the changeable content addressed by a tag. | Direct for immutable OCI orientation; it does not prove that a reported command actually executed those bytes. |
| `S9` | [SLSA `1.2` provenance](https://slsa.dev/spec/v1.2/provenance) and [verification-summary attestation](https://slsa.dev/spec/v1.2/verification_summary) | `2026-08-25` | Provenance describes where, when and how an artifact was produced. Verification must match the statement subject to the artifact digest and interpret the result against an identified verifier and policy. | Direct evidence-binding model for `D4` and `O1`–`O4`; it does not establish semantic correctness or require SLSA infrastructure for the rerun. |
| `S10` | [Git submodules](https://git-scm.com/docs/gitsubmodules), guide last changed in Git `2.52.0` | `2026-08-25` | A superproject gitlink records the exact expected submodule commit; the embedded repository retains separate history and updates only when the superproject records another commit. | Direct source-binding pattern; it does not make submodules the only valid Gnostoa distribution mode. |
| `S11` | [Go Modules Reference](https://go.dev/ref/mod), current official language reference | `2026-08-25` | `vendor/modules.txt` lists vendored packages and their module versions, and the Go command checks those versions for consistency with `go.mod`. Vendor-tree integrity can be checked by rerunning `go mod vendor` and requiring no diff. Separately, `go.sum` supports authentication of downloaded module content and `go mod verify` hashes downloaded archives and extracted module-cache directories; neither directly cryptographically verifies the vendor directory, and `vendor/modules.txt` contains no vendor-file hashes. | Background for version recording, regeneration comparison and downloaded-module verification. Go module semantics and destructive vendor regeneration do not transfer directly. |
| `S12` | [NIST AI RMF Playbook, Measure](https://airc.nist.gov/airmf-resources/playbook/measure/) | `2026-08-25` | Measurement approaches, test sets, metrics, tools and outcomes should be documented; context and independent assessment matter to interpretation. | Direct support for the already-frozen evidence contract, not a generic Gnostoa receipt mechanism. |
| `S13` | [NIST CAISI agent-evaluation practices](https://www.nist.gov/caisi/cheating-ai-agent-evaluations/4-practices-detecting-and-preventing-evaluation-cheating), updated `2025-12-02` | `2026-08-25` | Evaluation comparability benefits from explicit affordances, restrictions, configurations and task rules, plus checking that rules were followed. The source cautions that fixes are context-specific. | Direct for `F5` and `O1`–`O4`; it does not justify retaining private reasoning or scoring vendor reliability. |

## Practice-to-RCA map

| Practice | RCA identifiers | Role | Bounded fit | Where it does not fit Gnostoa |
|---|---|---|---|---|
| `P1` — apply task-ordered guidance to a Gnostoa-specific first verified adoption slice | `D1`, `F1`, `R4`, bounded contribution to `H2` | Direct for documentation form (`S1`, `S2`); Gnostoa-specific consolidation inference from Phase-1 `F1` and the current route topology | Diátaxis informs the goal-focused, task-ordered and link-out form. Phase-1 `F1` and the split between the existing-project and bootstrap routes support the separate Gnostoa inference to concentrate the first verified slice: select commitment, establish prerequisites and route, author the minimum, validate, generate context and classify the result. Link the full bootstrap/reference detail. | Diátaxis does not mandate a single universal path or spine. The inferred Gnostoa slice must allow project-specific branches and cannot decide whether the owner's ambiguous word “adopt” means evaluation or durable adoption; it must stop for `H2`, not choose. |
| `P2` — make any scaffold inputs and effects reviewable before writing | `D1`, `D3`, `F2`, `H1`–`H3` | Background/tooling criterion (`S3`) | If scaffolding is later considered, require explicit inputs, a dry-run file plan, conflict refusal, step results and a separate rerun record. | Backstage's service, catalog registration and publication model would be a disproportionate new platform. A review form cannot verify a fictional owner or taxonomy. |
| `P3` — initialization must be repeatable, non-destructive and pin dependencies | `D1`, `F2`, `F3`, `F4` | Direct criterion only if tooling is selected (`S4`) | A later initializer would need idempotent no-op on matching files, fail-on-conflict behavior and exact source/runtime pins. | Terraform's guarantee does not prove a Gnostoa generator is needed or safe. Silent replacement or invented defaults would violate Gnostoa authority. |
| `P4` — preflight prerequisites and actual execution route before validation or completion | `D2`, `F4`, `R5`, `E1`, `E2`, `O2` | Direct (`S4`, `S5`, `S7`, `S8`) | Establish one supported route, its observed identity, workspace writability and required project tools before authoring or claiming completion. A missing material prerequisite is `BLOCKED`. | Published OCI execution is not mandatory when a native or source-built route is correctly identity-bound and verified. Preflight must not silently install PHP/Composer or change the frozen environment. |
| `P5` — expose exact names, dialects and non-operative defaults | `F2`, bounded contribution to `D3` and `H1` | Direct for documentation; background for schema change (`S6`) | Show template-to-target mappings and describe existing schemas/default semantics at their point of use. Treat example/default values as hints, never observed project facts. | `$schema`, a new field or another schema is not automatically compatible with current YAML contracts. Schema discovery cannot supply ownership or provenance. |
| `P6` — classify structural validity separately from contextual and semantic truth | `D2`, `D3`, `O4`, `H1`, `H3` | Direct (`S5`, `S6`; existing lifecycle remains authoritative) | Report bundle/policy validation, project-suite execution, context generation, semantic review and owner acceptance as separate results. | Terraform and JSON Schema cannot define Mail's correct ownership, runtime semantics or acceptance. No validator can replace the human oracle. |
| `P7` — name source, runtime and observed artifact identities separately | `D4`, `F3`, `F4`, `O2` | Direct (`S7`–`S10`) | Record documentation commit/tree, vendored source commit or manifest, selected execution route, observed runtime identity and OCI digest evidence as separate subjects. Verify retrieved content rather than inferring execution from a declared value. | Content identity alone does not show which command ran, whether project tests passed, or whether knowledge is true. Native/source-built execution has no obligation to pretend it is OCI execution. |
| `P8` — bind evaluation claims to retained artifacts and a frozen measurement context | `F5`, `O1`, `O3`, `O4` | Direct (`S12`, `S13`) | Preserve exact prompts, environment/route, commands, exits, outputs, generated bundle/context, hashes, Git diff and owner corrections; compare dimensions separately. | This experiment does not need generic receipt infrastructure, complete shell history, private reasoning or population-level metrics. |
| `P9` — make source incorporation independently inspectable | `D4`, `F3`, `O1` | Direct for Git binding, background for vendoring (`S10`, `S11`) | A submodule gitlink can bind an exact commit. For Go, `vendor/modules.txt` records module versions and consistency while a regenerated no-diff tree checks the vendor files; neither that file nor `go.sum`/`go mod verify` is a vendor-file hash manifest. A Gnostoa vendor route should retain an exact source identity and use a content manifest or equivalent physical-tree comparison appropriate to its own contract. | Git submodule, vendored copy and source-built install remain alternatives. Go's distinct module-cache checksum and vendor-regeneration practices must not be collapsed or copied as a new Gnostoa dependency system. |

## What the research does and does not establish

The sources reinforce six direct correction targets already demonstrated by
Phase 1: task-oriented routing form, with route concentration inferred from
`F1` and the current Gnostoa topology; exact placement names (`F2`); explicit
execution-route preflight (`D2`, `R5`), evidence-class separation (`D4`,
`O2`–`O4`), structural-versus-semantic result separation (`D3`, `H1`, `H3`),
and artifact-bound rerun evidence (`F5`, `O1`). They do not establish that the
existing three-root model, schemas, unified CLI, context generator or immutable
OCI artifact is absent or defective.

The scaffolding sources demonstrate reviewable patterns but do not establish a
need for an `init` command. The strongest observed counterfact is the same-agent
recovery: after reading existing authorities, it found the intended layout and
existing mechanisms. That makes routing and operational concentration the
smallest evidenced first intervention. It does not prove documentation alone
will be sufficient; the frozen rerun must test that prediction.

## Alternatives matrix

### `A0` — no change

| Criterion | Disposition |
|---|---|
| Root causes addressed | None directly; retains current controls and relies on a future agent following all existing routes. |
| Exact proposed surface | No repository change; expose the existing frozen subject to the rerun. |
| Expected benefit | Zero compatibility, maintenance and review cost; provides a useful control against over-attributing Phase-1 failure to documentation. |
| Complexity and maintenance | None. |
| Negative consequences and misuse risks | Leaves `F1`, `F2` and `F3` operationally distributed and gives no new preflight emphasis for `D2`/`R5`; another broad structural-green claim may remain plausible. |
| Compatibility | Complete. |
| Smallest testable change set | No change; execute the frozen rerun against the unchanged documentation subject. |
| Falsifiable rerun prediction | No systematic improvement is predicted. The agent may still miss the cross-route, context step or evidence classification without correction. |
| Evidence that rejects it | Repetition of any material routing/naming/preflight failure rejects no change as remediation. Conversely, a clean first attempt would falsify the claim that repository correction was necessary for this exact case, but would not erase Phase-1 friction. |

### `A1` — documentation-only correction

| Criterion | Disposition |
|---|---|
| Root causes addressed | Directly targets `D1`, `D2`, `D4`, `F1`–`F3`, `R4`, `R5`; makes `H1`–`H3` stop points conspicuous. It reduces opportunity for `D3` but cannot mechanically prevent invention. |
| Exact proposed surface | Amend `guidance/workflows/adopt-existing-project.md` with one short “first verified adoption slice” in task order and amend `guidance/workflows/bootstrap-new-project.md` with one exact template-to-target map and route/evidence-result distinctions. Reuse links to `docs/core/adoption.md`, templates, schemas and CLI reference; no second guide. Add routing only if a later read-back proves the existing guidance-index link insufficient. |
| Expected benefit | Concentrates the minimum safe path at the existing-project entry, preserves progressive disclosure, makes naming and actual-route evidence explicit, requires context generation, and prevents one structural result from becoming an adoption claim. |
| Complexity and maintenance | Low: two existing guidance authorities, no new executable or schema contract. Some duplicated step labels must be avoided by linking bootstrap detail. |
| Negative consequences and misuse risks | A longer entry page can recreate overload, stale command duplication or suggest that one path fits every project. Agents can still ignore guidance or invent semantics. |
| Compatibility | No file-format or CLI change. Normative adopter guidance still requires a new owner Decision and exact compatibility review before implementation. |
| Smallest testable change set | Two guidance files plus existing guidance/link/strict-doc validation and focused characterization only if current policy requires it. The frozen fresh rerun is the behavioral falsification. |
| Falsifiable rerun prediction | With the original minimal prompt, a fresh agent follows the existing-project route before authoring; records evaluation-versus-durable ambiguity; preflights and truthfully identifies one supported execution route; creates correctly named targets; keeps unknown ownership/provenance unresolved; runs structural checks and context generation; records PHP/Composer as `BLOCKED`; and makes no published-OCI execution claim unless it pulled and ran that digest. |
| Evidence that rejects it | The same material route, filename, context, preflight or evidence-class errors recur with no subject/environment deviation, or the agent needs Gnostoa-maintainer correction to find the path. New confusion caused by duplicated/stale instructions also rejects the shape. |

### `A2` — tooling-assisted correction

| Criterion | Disposition |
|---|---|
| Root causes addressed | Mechanically targets `D1`, `F2`, `F3`, `F4`, `R5` and some `O1`; can expose but not resolve `D3`, `H1`–`H3`, `O3` or `O4`. |
| Exact proposed surface | Add an explicit `knowledge init`/adoption command in `tools/cli.py` with a dedicated module, focused tests, documentation and template integration. It would require `--dry-run`, reviewed explicit inputs, fail-on-conflict writes, idempotent no-op on matching content, exact source/runtime pins and a machine-readable step/result summary. No owner, provenance, taxonomy or project capability default may be invented. |
| Expected benefit | Reduces manual file placement and naming translation, gives reruns a defined safety contract and can collect bounded preflight evidence before mutation. |
| Complexity and maintenance | High relative to the evidence: new public CLI behavior, cross-platform filesystem behavior, upgrade/idempotence semantics, tests and long-term template synchronization. |
| Negative consequences and misuse risks | Generated structure may be mistaken for adoption truth; placeholders can acquire false authority; reruns can overwrite project work; a new command can become an unsupported compatibility promise. It may hide rather than resolve ambiguous commitment and owner questions. |
| Compatibility | New public surface. Existing manual/submodule/vendor routes must continue to work; collision and upgrade semantics require explicit owner selection. |
| Smallest testable change set | CLI dispatch, one narrow implementation module, existing templates, focused unit/negative tests, and one guidance entry. Test clean creation, matching rerun, conflict refusal, partial tree, missing route, unknown owner and no-write dry run. |
| Falsifiable rerun prediction | The fresh agent discovers and invokes the command; exact paths and pins are correct without manual reconstruction; a second invocation changes no bytes; conflicts and absent prerequisites stop before writes. Semantic/owner results remain independently reviewed. |
| Evidence that rejects it | Documentation-only rerun succeeds without tooling; the command overwrites, invents facts, weakens existing controls, cannot represent supported route alternatives, or adds more correction/review cost than it removes. |

### `A3` — combined minimal correction

| Criterion | Disposition |
|---|---|
| Root causes addressed | Covers the documentation targets of `A1` plus mechanical preflight portions of `D2`, `F3`, `F4`, `R5`, `O1` and `O2`; human-oracle limits remain explicit. |
| Exact proposed surface | Apply `A1`, then add only a read-only `knowledge adoption-preflight` command. It reports workspace state, required tool availability, declared source/runtime subjects, selected supported route and capture capability; it writes no scaffold and makes no semantic/adoption conclusion. Add focused tests and one linked invocation in the existing route. |
| Expected benefit | Keeps authoring human/agent-controlled while acquiring the most failure-prone environment and identity observations consistently. Smaller semantic risk than a generator. |
| Complexity and maintenance | Medium: new public CLI/check contract and platform-sensitive environment observation, plus the guidance changes. |
| Negative consequences and misuse risks | A green preflight can itself be mistaken for adoption success; local/container observation may be incomplete; maintaining route-specific checks can become a generic environment framework. |
| Compatibility | Additive CLI surface, but observable output and exit semantics become a public maintenance obligation. Native, source-built and OCI routes must remain equal supported choices. |
| Smallest testable change set | The two `A1` guidance files, CLI dispatch, one read-only checker, focused contract/negative tests. No schemas, generator or template writes. |
| Falsifiable rerun prediction | Before any adopter file is authored, the fresh agent either records one actual supported route and the known PHP/Composer block or returns `BLOCKED`; no stale-image or declared-versus-observed identity is later reported as executed evidence. The remaining `A1` prediction also holds. |
| Evidence that rejects it | `A1` alone passes the frozen rerun; the checker cannot observe the chosen route without caller assertions; it reports green while material prerequisites are absent; or its public/maintenance cost exceeds the bounded friction removed. |

## Non-binding recommendation

Recommend `A1`, the documentation-only correction, as the smallest coherent
remediation set for accountable selection. Phase 1 observed existing schemas,
CLI, context generation and supported execution routes; the correcting agent
recovered after it followed the existing authorities. The direct repository
friction is concentration, naming and result-boundary clarity, not evidence of
a missing generator or validator. `A1` also preserves the frozen environment
and can be falsified by the exact fresh rerun without adding a second variable
in the executable surface.

The single first verified adoption slice is a Gnostoa-specific design inference
from Phase-1 `F1` and the present route topology. Diátaxis informs its
goal-oriented, task-ordered, link-out form; it does not mandate that
consolidation or a universal golden path.

If selected, the later Decision should admit only:

1. a compact first-verified-slice sequence in the existing-project route;
2. an exact existing template-to-target map in bootstrap;
3. fail-closed selection and truthful classification of one actual supported
   execution route, without requiring OCI specifically;
4. separate structural, context, project-suite, semantic and owner results;
5. explicit unresolved ownership/provenance and commitment stop points; and
6. the existing frozen rerun as the behavioral test.

The recommendation predicts an improvement; it does not claim one. `A2` and
`A3` should remain unadmitted unless the documentation-only rerun or additional
evidence demonstrates a repeatable mechanical gap that a bounded tool can
observe without inventing semantic authority.

## Rejected transfer and owner stop

This research does not select an initializer, generator, compatibility
interface, new schema, generic preflight framework, receipt mechanism, mutable
image tag or automatic adoption. It does not alter the frozen Mail subjects,
rerun prompt, environment or result dimensions. It does not establish B3,
productivity improvement, general adopter fit or Decision 0036 transfer.

The next action is an accountable owner choice among `A0`–`A3`, including an
explicit Decision and implementation admission if any normative or executable
surface is selected. Stop before remediation or rerun.
