# Gnostoa

Gnostoa is a small Git-native toolkit for project knowledge that must remain
usable by both people and software agents. It validates structured Markdown and
YAML, enforces non-weakening project profiles and policy boundaries, and builds
bounded orientation packs without requiring a hosted knowledge service.

> **Status: pre-release source candidate.** The validator, examples, policy
> checks, context-pack builder and documentation projection run from this
> repository. No package, image or site has been released yet, and independent
> adoption has not been demonstrated.

## Why Gnostoa

Project knowledge is often split across prose, configuration, issue history and
tool-specific indexes. That makes authority unclear, permits documentation
drift and forces every new person or agent to rediscover the repository.

Gnostoa keeps the canonical layer deliberately boring:

- Markdown plus YAML frontmatter using OKF v0.2;
- stable concept IDs, owners, lifecycle state and typed relations;
- profiles that specialize by adding constraints rather than weakening them;
- deterministic validation and bounded, replaceable context views; and
- provider-neutral change and CI contracts.

## Try Gnostoa from this checkout

The shortest supported evaluation path uses Python 3.11 or newer:

```bash
git clone https://github.com/ktogias/gnostoa.git
cd gnostoa

python3 -m venv .venv
. .venv/bin/activate
python -m pip install --only-binary=:all: --require-hashes \
  -r requirements/runtime.lock
python -m pip install --no-deps -e .

knowledge validate \
  --profile core/profile.yaml \
  --bundle examples/generic
```

Expected result:

```text
OK: bundle conforms to project-knowledge-core 0.1.0 (OKF 0.2)
```

Then build a bounded orientation view from the same validated bundle:

```bash
knowledge context-pack \
  --profile core/profile.yaml \
  --bundle examples/generic \
  --seed example.system.processing \
  --depth 2 \
  --max-tokens 800
```

The output contains the selected system, its governing Decision and the project
root, while the Markdown files remain canonical. See the
[five-minute quick start](docs/quick-start.md) for the container route,
interpretation and limits of this result.

The editable install is intentional for evaluating the current source
candidate. A wheel or source-distribution install supplies execution only: set
`KNOWLEDGE_KIT_ROOT` to the separate pinned public-source checkout that supplies
schemas and profiles. Unbound or wrongly bound native execution fails with an
actionable error instead of treating installed package files as canonical
source. No artifact has been released yet; consumers must still pin the
artifact, source revision and public-surface digest together.

## What works today

| Capability | Current evidence |
|---|---|
| Validate OKF bundles and profile inheritance | Executable CLI, schemas, anonymous fixtures and unit tests |
| Enforce generic and Gnostoa policy boundaries | Change-control, CI-policy and guardrail checks |
| Build bounded orientation packs | Deterministic graph traversal with explicit depth and token limits |
| Project human documentation | MkDocs build from canonical public and self-knowledge surfaces |
| Run through one command surface | Native CLI plus a pinned, non-root OCI build route |
| Apply the model to Gnostoa itself | Recorded self-dogfood assessment and publication-baseline review |

The raw Issue #12 and PR #2 ledger is retained as one-time B1 self-dogfood
evidence; it is **not the expected contribution workflow**. Normal changes use
the compact route in [CONTRIBUTING.md](CONTRIBUTING.md), ordinary Pull Request
review and proportionate evidence. [B2](https://github.com/ktogias/gnostoa/issues/24)
will measure whether the useful B1 controls can be preserved with materially
less owner effort and evidence amplification. B1 has already demonstrated the
need for guided review, durable task context, bounded plans, explicit handoffs
and safe resume; the [bootstrap Decision](knowledge/decisions/0016-evolve-human-agent-workflow-through-bounded-self-hosted-slices.md)
selects incremental post-publication implementation because the full workflow
platform is not a publication prerequisite.

Gnostoa is not yet a hosted service, a workflow engine, a general-purpose graph
database or a production-ready release. It does not claim reduced engineering
cost, easy external adoption or independent assurance. Those claims require the
planned streamlined self-hosting and external transfer experiments.

## Choose one route

- **Evaluate:** follow the [quick start](docs/quick-start.md) and
  [current-status page](docs/status.md).
- **Plan:** inspect the explicit [Now / Next / Research roadmap](docs/roadmap.md).
- **Understand:** read the [architecture](docs/core/architecture.md),
  [public inheritance contract](knowledge/contracts/public-inheritance-surface.md)
  and [toolchain](docs/core/toolchain.md), then check the current
  [compatibility and upgrade boundary](docs/compatibility.md).
- **Adopt:** start with the [adoption guide](docs/core/adoption.md), then use the
  route for a [new project](guidance/workflows/bootstrap-new-project.md) or an
  [existing project](guidance/workflows/adopt-existing-project.md).
- **Operate changes:** use the [reusable guidance router](guidance/index.md) and
  [continuous-integration workflow](guidance/workflows/configure-continuous-integration.md).
- **Inspect the evidence:** read the
  [self-dogfood assessment](knowledge/assessments/gnostoa-self-dogfood-bootstrap-assessment.md),
  [provider audit snapshot](knowledge/assessments/first-publication-provider-audit.md)
  and [first-publication runbook](knowledge/runbooks/prepare-first-publication.md).

## Repository surfaces

| Surface | Purpose | Consumer behavior |
|---|---|---|
| `core/`, `schemas/`, `tools/`, `ci/`, `templates/` | Generic enforceable contract and tooling | Pin and inherit |
| `guidance/` | Project-independent workflows and reference material | Load the route for the current task |
| `examples/` | Anonymous conformance and learning fixtures | Inspect or copy deliberately |
| `knowledge/`, `policy/` | Gnostoa architecture, evidence and stricter self-policy | Do not inherit into consuming projects |
| `docs/` | Curated human navigation projection | Read as a view, not a second authority |

An adopting project extends `core/profile.yaml` and owns its own knowledge
bundle. Gnostoa's product name, maintainer history and self-policy do not become
consumer domain vocabulary.

## Container route

Build and test the current checkout without publishing an image:

```bash
docker build \
  --target runtime \
  --build-arg VCS_REF=source-checkout \
  --tag gnostoa:source-checkout \
  .

docker run --rm gnostoa:source-checkout self-check
```

Released consumers will use an OCI image pinned by digest. Until an image is
actually released, examples that contain registry coordinates are contracts or
templates—not installable artifact claims.

## Develop and verify

The [Development Container](.devcontainer/devcontainer.json) is the recommended
maintainer environment. From a shell, build the exact checkout and run a named
suite through the same `development` target before selecting the native
fallback:

```bash
candidate_ref="${GNOSTOA_CANDIDATE_REF:-working-tree}"
docker build \
  --target development \
  --build-arg VCS_REF="${candidate_ref}" \
  --tag gnostoa:development-checkout \
  .

docker run --rm \
  --mount type=bind,source="$PWD",target=/workspace,readonly \
  --workdir /workspace \
  --env KNOWLEDGE_KIT_ROOT=/workspace \
  --env KNOWLEDGE_KIT_REVISION="${candidate_ref}" \
  --env PYTHONPATH=/workspace \
  gnostoa:development-checkout \
  ./ci/verify extended
```

Replace `extended` with the required named suite. Use the native fallback only
when the container route is unavailable or when explicitly checking native
parity, and record that reason. The fallback uses the development lock:

```bash
python -m pip install --only-binary=:all: --require-hashes \
  -r requirements/development.lock

./ci/verify policy
./ci/verify fast
./ci/verify regression
./ci/verify smoke
./ci/verify extended
```

The scheduled/manual `extended` suite checks Ruff formatting and a bounded,
explicit lint rule set across `tools/`, `ci/` and `tests/`; runs strict mypy
across `tools/` and `ci/`; and emits those reports with branch-aware coverage,
exact-lock Python dependency audits, package-declared license inventories,
strictly validated CycloneDX 1.6 SBOMs and a heuristic scan of the current
Git-tracked tree into
`${GNOSTOA_QUALITY_OUTPUT:-/tmp/gnostoa-quality-evidence}`. Static analysis and
the coverage floor are regression signals, not acceptance. The dependency
lookup is time/provider-bound, and the tree scan does not replace the separate
full history and provider-surface disclosure audit. The inventories and SBOMs
cover only the exact installed Python distributions named by the runtime and
development locks. Legacy license metadata remains flagged for human review;
the locks now enforce wheel-only SHA-256 verification and the evidence binds
the wheel selected for the current environment. OS/base-image components,
publisher assurance, release provenance and legal compatibility remain
separate release gates. See [Dependency evidence](docs/dependency-evidence.md)
for report contents and limits.

See [CONTRIBUTING.md](CONTRIBUTING.md) and the
[maintainer runbook](knowledge/runbooks/maintain-the-kit.md) before changing a
public contract. Gnostoa uses its own mechanisms during development, but its
internal review overhead is not exported to adopting projects.

## Support and security

Use [Support](SUPPORT.md) for reproducible defects and bounded usage questions.
Report vulnerabilities through the private route described in
[Security](SECURITY.md); do not place unpatched exploit details or sensitive
project data in a public Issue. Gnostoa is pre-release and currently provides
neither a support SLA nor a security-response guarantee.

## License and identity

Gnostoa is licensed under the
[Apache License, Version 2.0](LICENSE). Using the tooling does not change the
license of an adopting project's independent material. See
[Licensing](LICENSING.md) for scope, copied templates, contributions and the
separate treatment of trademarks.

`Gnostoa` is the working project identity. Decision 0009's bounded
[owner-confirmed name-risk screening](knowledge/assessments/gnostoa-source-name-screening.md)
records a source-only conditional-go for Greece, the EU and Nice classes 9 and
42. It is not trade-mark clearance and does not authorize package, image, site
or commercial publication. Independent or professional clearance remains
required before stable artifact branding, trade-mark filing or commercial
reliance.
