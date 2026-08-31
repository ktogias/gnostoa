---
type: Workflow
title: Bootstrap a new project
description: Create a minimal validated knowledge bundle before project-specific taxonomy grows.
status: draft
generated:
  by: codex/gpt-5
  at: "2026-07-29T00:00:00Z"
x-project-knowledge:
  id: guidance.workflow.bootstrap-new-project
  owners:
    - team:gnostoa-maintainers
  scope:
    - generic-guidance
  relations:
    - kind: governed-by
      target: /guardrails/non-negotiable.md
    - kind: references
      target: /reference/repository-layout-and-distribution.md
    - kind: references
      target: /reference/versioning-and-upgrades.md
    - kind: references
      target: /reference/runtime-and-distribution.md
    - kind: depends-on
      target: /workflows/propose-review-merge-change.md
    - kind: depends-on
      target: /workflows/configure-continuous-integration.md
---

# Bootstrap a new project

## Outcome

The project has a pinned toolkit dependency, minimal project profile, valid OKF
bundle, review ownership and CI validation. No domain taxonomy is introduced
without demonstrated need.

This is the **durable full-adoption** route: it adds repository-owned knowledge,
policy, CI and provider maintenance. For a bounded technical evaluation and
orientation without that commitment, stop here and use the
[minimal evaluation route](../../docs/quick-start.md) instead.

## Roots, targets and identities

Keep the three project roots distinct; the
[repository-layout reference](../reference/repository-layout-and-distribution.md)
owns their wider placement choices:

- `.knowledge-kit/` is the pinned toolkit source dependency.
- `.knowledge/` holds project profile, lock, policy and verification
  configuration.
- `knowledge/` is the canonical project-owned OKF concept bundle.

For the core bootstrap, copy or adapt the named reusable files to these exact
targets:

- [`templates/knowledge-kit.lock.yaml`](../../templates/knowledge-kit.lock.yaml) → `.knowledge/kit.lock.yaml`
- [`templates/change-control.project.yaml`](../../templates/change-control.project.yaml) → `.knowledge/change-control.yaml`
- [`templates/continuous-integration.project.yaml`](../../templates/continuous-integration.project.yaml) → `.knowledge/continuous-integration.yaml`
- [`templates/verification.project.yaml`](../../templates/verification.project.yaml) → `.knowledge/verification.yaml`
- [`templates/verify.project`](../../templates/verify.project) → `ci/verify`
- [`templates/AGENTS.project.md`](../../templates/AGENTS.project.md) → `AGENTS.md`

For an existing repository, follow the
[existing-project workflow](adopt-existing-project.md#preserve-existing-project-authority)
before applying this map. Each template is source material, not authorization
to replace an existing authoritative target: inspect and preserve the target,
and request accountable-owner resolution before writing when instructions
conflict or edit authority is unclear.

The project profile and initial `knowledge/index.md` and Project concept are
authored in the steps below; their contents are not inferred from the template
filenames. Optional review and provider templates remain governed by the
[continuous-integration workflow](configure-continuous-integration.md) and the
selected provider's own target paths.

Record four subjects separately:

- **Documentation identity:** the exact revision of the Gnostoa pages followed.
- **Toolkit source identity:** the immutable source revision materialized at
  `.knowledge-kit/`.
- **Selected execution route:** the native, source-built or immutable OCI route
  that actually ran, plus the observed identity evidence for that execution.
- **Published OCI identity:** the immutable registry digest, whether or not OCI
  was selected as the execution route.

Writing an image reference into a lock or environment variable declares an
expected identity; it does not prove that those image bytes executed. A native,
source-built or immutable OCI route is valid when its own prerequisites and the
existing source/runtime identity checks are satisfied. Report only the route
that actually executed, and do not translate source-built or native evidence
into a published-OCI claim.

## Preconditions

- The toolkit has a released tag or immutable commit.
- A matching runtime identity is available to record and one supported native,
  source-built or immutable OCI execution route is usable.
- The project repository and accountable owner are known.
- The team has selected embedded or dedicated knowledge-repository placement.
- Local development or CI provides the prerequisites for the selected route. An
  OCI-compatible container runtime is required only for OCI and source-built
  container routes.

## Procedure

1. Pin the toolkit as `.knowledge-kit/` using a submodule, vendored release or
   reproducible local dependency. For the annotated `v0.1.1` tag, use a
   detached exact-commit checkout rather than `git submodule add -b v0.1.1`:

   ```bash
   GNOSTOA_COMMIT=84cc4959d9fb0b315084cc49a5381c13166b6554

   git submodule add --depth 1 \
     https://github.com/ktogias/gnostoa.git .knowledge-kit
   git -C .knowledge-kit fetch --depth 1 origin tag v0.1.1
   test "$(git -C .knowledge-kit rev-parse 'v0.1.1^{commit}')" = \
     "$GNOSTOA_COMMIT"
   git -C .knowledge-kit checkout --detach "$GNOSTOA_COMMIT"
   test "$(git -C .knowledge-kit rev-parse HEAD)" = "$GNOSTOA_COMMIT"
   git add .gitmodules .knowledge-kit
   test "$(git ls-files --stage .knowledge-kit | awk '{print $2}')" = \
     "$GNOSTOA_COMMIT"
   ```

   The superproject records the exact commit as its gitlink; the tag is a
   verified source identity, not a branch to follow. Pin the matching runtime
   image by digest in
   `.knowledge/kit.lock.yaml`, adapting
   [`templates/knowledge-kit.lock.yaml`](../../templates/knowledge-kit.lock.yaml).
   Compute the exact toolkit digest with `knowledge surface-digest --root
   .knowledge-kit` from the matching pinned runtime and record its output as
   `toolkit.public_surface_digest`. Do not follow a mutable default branch or
   image tag, and do not treat a revision label as a content digest.
   The two digest-bearing placeholder sentinels in the lock template are
   intentionally schema-invalid. The quoted `runtime.image` sentinel contains
   whitespace so retaining or extending it cannot satisfy the image pattern.
   Replace `toolkit.public_surface_digest` with the complete observed
   `sha256:<digest>` value. Replace the entire `runtime.image` scalar with the
   complete observed `<registry>/<repository>@sha256:<digest>` identity; do not
   retain or append to the sentinel, and do not replace only a digest suffix.
   `check-runtime` reports each field until both whole-value replacements are
   complete. Its declaration/source binding, supplied-reference comparison and
   execution observation are separate results. A caller-supplied image identity
   matching the declaration produces reference `MATCH`, not observation
   `PASS`; caller-supplied identities are declarations and
   never execution observation evidence. Standalone `check-runtime` therefore
   reports execution observation as `UNKNOWN`. Invocation-bound project-adapter
   evidence remains the separate observation route used by `adoption-check`.
2. Create `.knowledge/profile.yaml` extending
   `../.knowledge-kit/core/profile.yaml`.
3. Create `.knowledge/change-control.yaml` from
   [`templates/change-control.project.yaml`](../../templates/change-control.project.yaml)
   and extend `../.knowledge-kit/core/change-control.yaml`. Add only stricter
   overrides.
4. Create `.knowledge/continuous-integration.yaml` and
   `.knowledge/verification.yaml` from their templates. Copy
   `templates/verify.project` to `ci/verify`, declare only real capabilities and
   implement `fast` plus `regression`.
5. Start with empty `concept_types` and `relation_kinds`; add vocabulary only
   after repeated project use demonstrates a need.
6. Create `knowledge/index.md` with `okf_version: "0.2"`.
7. Add one `Project` concept with a stable ID, team owner, scope and
   `status: draft`.
8. Inventory repositories, standards, schemas, decisions and external sources
   before generating summaries.
9. Add the smallest useful spine: project, systems, repositories, contracts,
   decisions and explicit open questions.
   A `Requirement` records desired project behaviour. A
   [task envelope](resume-bounded-task.md) instead records bounded active or
   resumable work state. Link them when relevant, but do not duplicate the
   Requirement in the envelope. Create an envelope only when the intended work
   needs a durable handoff, interruption checkpoint or later resume.
10. Adapt the Change Request, emergency and CODEOWNERS templates. Add the Work
   Item and verification-plan templates only when they provide durable value.
   Establish one fast focused suite, one relevant
   boundary check and, when applicable, one critical smoke path rather than
   pursuing blanket coverage.
   Prepare the baseline and apply the
   [repository-settings checklist](../../templates/repository-settings-checklist.md)
   to map the policy to the selected provider. Do not publish or integrate the
   baseline yet.
11. Check source/runtime lockstep through the selected supported route. The
    canonical immutable-OCI invocation is:

   ```bash
   KNOWLEDGE_KIT_IMAGE='registry.example.org/gnostoa@sha256:<digest>'

   docker run --rm \
     --mount type=bind,source="$PWD",target=/workspace,readonly \
     --workdir /workspace \
     "$KNOWLEDGE_KIT_IMAGE" \
     surface-digest \
     --root .knowledge-kit

   # Record the exact output above as toolkit.public_surface_digest, then:
   docker run --rm \
     --env KNOWLEDGE_KIT_IMAGE \
     --mount type=bind,source="$PWD",target=/workspace,readonly \
     --workdir /workspace \
     "$KNOWLEDGE_KIT_IMAGE" \
     check-runtime \
     --lock .knowledge/kit.lock.yaml
   ```

12. Validate the inherited change and CI policies:

   ```bash
   docker run --rm \
     --env KNOWLEDGE_KIT_IMAGE \
     --mount type=bind,source="$PWD",target=/workspace,readonly \
     --workdir /workspace \
     "$KNOWLEDGE_KIT_IMAGE" \
     check-change-policy \
     --policy .knowledge/change-control.yaml
   ```

   ```bash
   docker run --rm \
     --env KNOWLEDGE_KIT_IMAGE \
     --mount type=bind,source="$PWD",target=/workspace,readonly \
     --workdir /workspace \
     "$KNOWLEDGE_KIT_IMAGE" \
     check-ci-policy \
     --policy .knowledge/continuous-integration.yaml \
     --verification .knowledge/verification.yaml
   ```

13. Validate project knowledge:

   ```bash
   docker run --rm \
     --env KNOWLEDGE_KIT_IMAGE \
     --mount type=bind,source="$PWD",target=/workspace,readonly \
     --workdir /workspace \
     "$KNOWLEDGE_KIT_IMAGE" \
     validate \
     --profile .knowledge/profile.yaml \
     --bundle knowledge/
   ```

   A bounded context pack projects selected metadata, descriptions and
   relations; it does not necessarily reproduce complete concept bodies.
   Material constraints needed during handoff therefore need accurate,
   non-misleading descriptions. Paths rendered into the saved pack are
   relative to the selected bundle and lead back to the canonical concepts.

14. Install and exercise the appropriate provider adapter through the
    [continuous-integration workflow](configure-continuous-integration.md).
    Make candidate checks required. Adapt
    [`templates/CODEOWNERS.project`](../../templates/CODEOWNERS.project) and
    [`templates/knowledge-change-checklist.md`](../../templates/knowledge-change-checklist.md)
    to make ownership and the change loop visible in review.
15. Stage the bounded candidate and follow the existing-project workflow's
    [mechanical completion-evidence boundary](adopt-existing-project.md#mechanical-completion-evidence).
    The project-owned `ci/verify` adapter must provide its bound runtime
    observation for adoption-check without changing ordinary suite behavior.
16. After steps 11-15 pass and the required provider protections and checks are
    verified, publish the validated baseline and integrate it through its
    protected Change Request at the exact tested head.

Use the project router template at
[`templates/AGENTS.project.md`](../../templates/AGENTS.project.md) so agents
load this guidance by task rather than loading the entire toolkit.

When the exact toolkit source is built locally, record the source commit and
built runtime identity, execute the same checks and classify the result as
source-built rather than published-OCI execution. When an OCI runtime is
unavailable, use the supported native fallback:

```bash
python3 -m venv .venv-knowledge
. .venv-knowledge/bin/activate
python -m pip install --only-binary=:all: --require-hashes \
  -r ./.knowledge-kit/requirements/runtime.lock
python -m pip install --no-deps -e ./.knowledge-kit
knowledge surface-digest --root ./.knowledge-kit
# Verify the exact output matches toolkit.public_surface_digest, then:
knowledge check-runtime --lock .knowledge/kit.lock.yaml
knowledge check-change-policy --policy .knowledge/change-control.yaml
knowledge check-ci-policy --policy .knowledge/continuous-integration.yaml --verification .knowledge/verification.yaml
knowledge validate --profile .knowledge/profile.yaml --bundle knowledge/
```

In this native fallback, a successful `check-runtime` declaration/source binding
does not establish observed-image binding. Unless the route supplies a real
observed identity, the command reports the image dimension as `UNKNOWN`; do not
rewrite that result as observed-image `PASS`.

## Verification

- The project profile resolves without weakening its parent.
- The bundle validates with zero errors.
- The root index reaches every initial concept.
- No generated concept is stable without human verification.
- CI uses the same pinned toolkit revision as local validation.
- The lock, recomputed toolkit public-surface digest, executing image revision
  and project profile agree.
- The inherited change-control policy validates without weakened controls.
- The inherited CI policy and verification capabilities validate without
  weakened controls or missing suites.
- Branch, Change Request, merge-candidate and integration events were exercised
  once through centralized CI.
- The default branch is protected and the baseline Change Request path is
  exercised once.
- The baseline is published only after lock, bundle, policy, provider-adapter
  and protection checks pass at its exact head.
- The first supported behavior has expected and final verification evidence;
  pre-change evidence is present when useful or required by a specialization.
- A task context pack can be produced from the Project concept.
- The staged baseline has a retained adoption-check evidence bundle, while
  semantic acceptance and durable adoption remain accountable-owner decisions.

## Recovery

If bootstrap validation fails, keep raw material outside the bundle and reduce
the first slice. Do not relax parent policies or mark incomplete content stable.
If the pinned toolkit version is incompatible, restore the previous pin and
perform the upgrade as a dedicated reviewed change.
