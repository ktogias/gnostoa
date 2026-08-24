# Minimal evaluation and orientation

This page is a navigation projection of the supported public commands and
contracts. Use it to validate a public example and generate a bounded context
pack without adopting Gnostoa into a repository or changing canonical
Markdown. Full repository, CI and provider integration is a separate
[adoption route](core/adoption.md).

## Published v0.1.2 OCI route

Requirements: Git and a Docker-compatible container runtime. The image pull is
anonymous; after the pull, validation and context generation run offline.

```bash
git clone --branch v0.1.2 --depth 1 https://github.com/ktogias/gnostoa.git
cd gnostoa
test "$(git rev-parse HEAD)" = "56f6c5ede9ff1d6585404d102aba8413994a2697" # pragma: allowlist secret -- public source revision

GNOSTOA_IMAGE="ghcr.io/ktogias/gnostoa@sha256:0cd31a2a649c4ffede8972680c6779c981decf5ce8605f749fa7d58751472f80" # pragma: allowlist secret -- public registry identity
docker pull "$GNOSTOA_IMAGE"

docker run --rm --network none \
  --mount type=bind,source="$PWD",target=/workspace,readonly \
  --workdir /workspace \
  "$GNOSTOA_IMAGE" \
  validate --profile core/profile.yaml --bundle examples/generic
```

The successful validation result is:

```text
OK: bundle conforms to project-knowledge-core 0.1.0 (OKF 0.2)
```

Generate a bounded orientation pack from the same pinned source and image:

```bash
docker run --rm --network none \
  --mount type=bind,source="$PWD",target=/workspace,readonly \
  --workdir /workspace \
  "$GNOSTOA_IMAGE" \
  context-pack \
  --profile core/profile.yaml \
  --bundle examples/generic \
  --seed example.system.processing \
  --depth 2 \
  --max-tokens 800
```

Inspect the output for three concepts: the processing system, its governing
Decision and the project root. The pack is derived orientation only; the linked
files in `examples/generic/` remain authoritative. This example loads the public
core profile and the example bundle, not Gnostoa's self-knowledge bundle.

## Historical source-tag documentation

The documentation stored inside immutable tag `v0.1.2` records the source-only
state at the moment that tag was created. The tag cannot be rewritten after the
later OCI publication. Current `main`, the
[`v0.1.2` GitHub Release](https://github.com/ktogias/gnostoa/releases/tag/v0.1.2)
and the [publication result](../knowledge/assessments/v0-1-2-source-and-oci-publication-result.md)
record the later public image. Use the immutable digest above, not the `0.1.2`
registry tag alone, as the OCI consumer identity.

No Python wheel or package registry artifact is published. For native evaluation
of the pinned source, use the source checkout and locked runtime requirements:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --only-binary=:all: --require-hashes \
  -r requirements/runtime.lock
python -m pip install --no-deps -e .
export KNOWLEDGE_KIT_ROOT="$PWD"
knowledge validate --profile core/profile.yaml --bundle examples/generic
```

## Evaluation versus adoption

This minimal route demonstrates that the pinned public command surface can
validate and orient over one bundle. It does not establish net productivity,
human usability, production readiness or fit for a particular project.

Full adoption additionally places a pinned toolkit source under project
authority, defines a project profile and canonical Project concept, adapts the
agent route, and adds the selected repository/CI/provider controls. Follow the
[existing adoption guide](core/adoption.md) when that maintenance commitment is
justified.

## Continue

- Start from the existing [project profile example](https://github.com/ktogias/gnostoa/blob/main/examples/profiles/example-project/profile.yaml)
  and [Project concept example](https://github.com/ktogias/gnostoa/blob/main/examples/generic/project.md).
- Read [Current status](status.md) before relying on a capability.
- Read [Compatibility and upgrade status](compatibility.md) before changing a
  toolkit version.
- Use the [reusable guidance router](../guidance/index.md) for the chosen task.
- Inspect the [public inheritance contract](../knowledge/contracts/public-inheritance-surface.md)
  before extending a profile.
