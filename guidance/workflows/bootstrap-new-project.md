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

## Preconditions

- The toolkit has a released tag or immutable commit.
- A matching runtime image is available by immutable OCI digest.
- The project repository and accountable owner are known.
- The team has selected embedded or dedicated knowledge-repository placement.
- Local development or CI provides an OCI-compatible container runtime.

## Procedure

1. Pin the toolkit as `.knowledge-kit/` using a submodule, vendored release or
   reproducible local dependency. Pin the matching runtime image by digest in
   `.knowledge/kit.lock.yaml`, adapting
   [`templates/knowledge-kit.lock.yaml`](../../templates/knowledge-kit.lock.yaml).
   Do not follow a mutable default branch or image tag.
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
10. Adapt the Change Request, emergency and CODEOWNERS templates. Add the Work
   Item and verification-plan templates only when they provide durable value.
   Establish one fast focused suite, one relevant
   boundary check and, when applicable, one critical smoke path rather than
   pursuing blanket coverage.
   Publish the baseline and apply the
   [repository-settings checklist](../../templates/repository-settings-checklist.md)
   to map the policy to the selected provider.
11. Check source/runtime lockstep and validate through the pinned image:

   ```bash
   KNOWLEDGE_KIT_IMAGE='registry.example.org/gnostoa@sha256:<digest>'

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

14. Install and exercise the appropriate provider adapter through the
    [continuous-integration workflow](configure-continuous-integration.md).
    Make candidate checks required. Adapt
    [`templates/CODEOWNERS.project`](../../templates/CODEOWNERS.project) and
    [`templates/knowledge-change-checklist.md`](../../templates/knowledge-change-checklist.md)
    to make ownership and the change loop visible in review.

Use the project router template at
[`templates/AGENTS.project.md`](../../templates/AGENTS.project.md) so agents
load this guidance by task rather than loading the entire toolkit.

When an OCI runtime is unavailable, use the supported native fallback:

```bash
python3 -m venv .venv-knowledge
. .venv-knowledge/bin/activate
python -m pip install -r ./.knowledge-kit/requirements/runtime.lock
python -m pip install --no-deps -e ./.knowledge-kit
knowledge check-runtime --lock .knowledge/kit.lock.yaml
knowledge check-change-policy --policy .knowledge/change-control.yaml
knowledge check-ci-policy --policy .knowledge/continuous-integration.yaml --verification .knowledge/verification.yaml
knowledge validate --profile .knowledge/profile.yaml --bundle knowledge/
```

## Verification

- The project profile resolves without weakening its parent.
- The bundle validates with zero errors.
- The root index reaches every initial concept.
- No generated concept is stable without human verification.
- CI uses the same pinned toolkit revision as local validation.
- The lock, executing image revision and project profile agree.
- The inherited change-control policy validates without weakened controls.
- The inherited CI policy and verification capabilities validate without
  weakened controls or missing suites.
- Branch, Change Request, merge-candidate and integration events were exercised
  once through centralized CI.
- The default branch is protected and the baseline Change Request path is
  exercised once.
- The first supported behavior has expected and final verification evidence;
  pre-change evidence is present when useful or required by a specialization.
- A task context pack can be produced from the Project concept.

## Recovery

If bootstrap validation fails, keep raw material outside the bundle and reduce
the first slice. Do not relax parent policies or mark incomplete content stable.
If the pinned toolkit version is incompatible, restore the previous pin and
perform the upgrade as a dedicated reviewed change.
