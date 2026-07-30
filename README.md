# Gnostoa

Gnostoa is a technology-neutral, Git-native foundation for knowledge that must
be usable by both people and software agents. It uses itself without forcing
consuming projects to inherit its internal documentation.

The name joins *gnosis* (knowledge) with *stoa* (a shared place for teaching,
discussion and exchange). Gnostoa is the product identity; its public contracts
remain generic so adopting projects do not inherit branded domain vocabulary.

## Three bounded surfaces

| Surface | Purpose | Consumer behavior |
|---|---|---|
| `core/`, `schemas/`, `tools/`, `ci/`, `templates/` | Enforceable generic contract | Pin and inherit |
| `guidance/` | Generic workflows, patterns and practices | Load one task route |
| `knowledge/`, `policy/` | Architecture, operation and self-policy of this toolkit | Toolkit maintainers only |

An adopting project creates a profile that extends `core/profile.yaml` and owns
its own OKF bundle. A project area or module specializes that profile only when
it needs stricter rules or additional vocabulary. It may consult `guidance/`,
but must not copy or load `knowledge/`.

Profiles contain rules and vocabulary. Knowledge remains in an OKF bundle owned
by the adopting project. This repository ships no domain profile. Everything
under `examples/` is deliberately anonymous and non-normative.

## Start here

- [Reusable guidance router](guidance/index.md)
- [Toolkit self-knowledge router](knowledge/index.md)
- [Public inheritance contract](knowledge/contracts/public-inheritance-surface.md)
- [Guardrail coverage manifest](policy/guardrails.yaml)
- [Architecture and layer contract](docs/core/architecture.md)
- [Tool selection](docs/core/toolchain.md)
- [Runtime and distribution](guidance/reference/runtime-and-distribution.md)
- [Governance](docs/core/governance.md)
- [Contributing](CONTRIBUTING.md)
- [Licensing](LICENSING.md)
- [Change classification and review](guidance/reference/change-classification-and-approval.md)
- [Protected lightweight change flow](guidance/patterns/protected-short-lived-change-flow.md)
- [Proportionate verification](guidance/patterns/verification-first-development.md)
- [Testing and verification strategy](guidance/reference/testing-and-verification-strategy.md)
- [Tiered centralized CI](guidance/patterns/tiered-ci-and-local-feedback.md)
- [Continuous-integration contract](guidance/reference/continuous-integration-contract.md)
- [Configure continuous integration](guidance/workflows/configure-continuous-integration.md)
- [Adoption guide](docs/core/adoption.md)
- [Implementation roadmap](docs/roadmap.md)
- [Profile authoring](docs/profiles.md)

## Container-first execution

Build the development revision locally:

```bash
docker build \
  --target runtime \
  --build-arg VCS_REF=development \
  --tag gnostoa:development \
  .
```

Run the complete self-check in the immutable image:

```bash
docker run --rm gnostoa:development self-check
```

Consuming projects use a released image pinned by digest, mount their repository
read-only and invoke the unified `knowledge` entry point:

```bash
KNOWLEDGE_KIT_IMAGE='registry.example.org/gnostoa@sha256:<digest>'

docker run --rm \
  --env KNOWLEDGE_KIT_IMAGE \
  --mount type=bind,source="$PWD",target=/workspace,readonly \
  --workdir /workspace \
  "$KNOWLEDGE_KIT_IMAGE" \
  validate \
  --profile .knowledge/profile.yaml \
  --bundle knowledge
```

The [Development Container](.devcontainer/devcontainer.json) is the recommended
environment for maintaining this repository.

## Native fallback

The implementation language is not a consuming-project requirement. When a
container runtime is unavailable or low-level debugging is required, install
the native tooling in an isolated environment:

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements/runtime.lock
python -m pip install --no-deps -e .

knowledge self-check

python -m tools.validate_bundle \
  --profile core/profile.yaml \
  --bundle examples/generic

python -m tools.validate_bundle \
  --profile examples/profiles/example-project/example-module/profile.yaml \
  --bundle examples/example-project-module

python -m tools.validate_bundle \
  --profile guidance/profile.yaml \
  --bundle guidance

python -m tools.validate_bundle \
  --profile knowledge/profile.yaml \
  --bundle knowledge

python -m tools.check_guardrails
python -m tools.check_ci_policy \
  --policy policy/continuous-integration.yaml \
  --verification policy/verification.yaml
```

Generate a deterministic, PEEK-inspired orientation pack:

```bash
python -m tools.build_context_pack \
  --profile examples/profiles/example-project/example-module/profile.yaml \
  --bundle examples/example-project-module \
  --seed example.module.sample \
  --depth 2 \
  --max-tokens 1600
```

MkDocs is an optional human-facing renderer:

```bash
python -m pip install -r requirements/development.lock
knowledge docs-build --site-dir site
```

The builder creates a temporary projection containing `docs/`, `guidance/`,
`knowledge/`, `policy/` and `templates/`, plus versioned public schema copies
under `schemas/v1/`. The generated site is derived; it does not create another
canonical copy in the repository.

## Design constraints

- Canonical knowledge is plain Markdown plus YAML frontmatter using OKF v0.2.
- Derived wikis, search indexes, graphs and context packs are replaceable.
- A specialization may add constraints and vocabulary but must not silently
  weaken its parent profile.
- Generated content starts as `draft`; stable knowledge requires human
  verification.
- Executable artifacts such as OpenAPI, JSON Schema and tests remain canonical
  in their native formats and are referenced rather than copied into prose.
- Normative guardrails have stable IDs, ownership and explicit enforcement
  coverage in `policy/guardrails.yaml`.
- Agent instructions are short routers; they do not embed the whole knowledge
  corpus into every task.
- Consumer and CI execution is OCI-container-first and pinned by digest.
- Default-branch integration uses bounded, risk-classified Change Requests.
- Change-control specializations may strengthen but not weaken their parent.
- Gnostoa's internal self-policy requires a Work Item, Decision and
  pre-implementation evidence for normal, normative and critical toolkit
  changes, with emergency follow-up; consumers do not inherit that
  specialization.
- Agents never satisfy a required human gate or bypass repository controls.
- Expected observable behavior and proportionate evidence precede integration;
  test-first evidence is recommended where it adds confidence and can be
  required by a specialization.
- Required tests are behavior-oriented, deterministic and blocking when flaky;
  coverage alone is not acceptance.
- Centralized CI is authoritative on the latest integration candidate; local
  Git hooks are bounded advisory adapters to shared commands.
- Projects declare verification capabilities and suites through inherited CI
  policy without placing provider syntax in the generic core.
- Delivery gates activate only for deployable artifacts and promote the exact
  verified artifact.
- The native implementation environment remains a supported fallback.
- Concrete implementation frameworks and test products belong in project or
  module specializations.

## License

Gnostoa is licensed under the
[Apache License, Version 2.0](LICENSE). Using its tooling does not, by itself,
change the license of an independent adopting project or its knowledge. See
[Licensing](LICENSING.md) for repository scope, copied-template obligations,
initial copyright ownership, contributions and the separate treatment of
trademarks.

## Bootstrap routes

- For a new project, follow
  [`guidance/workflows/bootstrap-new-project.md`](guidance/workflows/bootstrap-new-project.md).
- For an existing project, follow
  [`guidance/workflows/adopt-existing-project.md`](guidance/workflows/adopt-existing-project.md).
- Add a module or domain specialization only through
  [`guidance/workflows/create-specialization.md`](guidance/workflows/create-specialization.md).
- Copy and adapt
  [`templates/AGENTS.project.md`](templates/AGENTS.project.md) as the consuming
  project's bounded agent router.
- Adapt [`templates/CODEOWNERS.project`](templates/CODEOWNERS.project) and the
  [knowledge change checklist](templates/knowledge-change-checklist.md) to make
  semantic review controls explicit.
- Adapt the [change-control policy](templates/change-control.project.yaml),
  [CI policy](templates/continuous-integration.project.yaml),
  [verification manifest](templates/verification.project.yaml),
  [shared verification command](templates/verify.project),
  [Change Request](templates/change-request.md), optional
  [Work Item](templates/work-item.md),
  [Execution Plan](templates/execution-plan.project.yaml),
  [emergency record](templates/emergency-change-record.md) and
  [repository-settings checklist](templates/repository-settings-checklist.md).
- Record expected behavior and the evidence portfolio with the
  [verification plan](templates/verification-plan.md).
- For work that needs continuity, follow the
  [resume and handoff workflow](guidance/workflows/resume-and-handoff-change.md);
  do not make raw agent logs part of project knowledge.
- Adapt the GitHub or GitLab provider template under `ci/`; optionally copy
  `templates/githooks/` and configure `core.hooksPath` for local feedback.
