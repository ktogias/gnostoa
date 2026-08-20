# Five-minute source quick start

This page is a derived navigation projection of the supported commands and
public contracts in the repository. It is not a released-artifact claim.

## Outcome

Validate an anonymous knowledge bundle and derive a bounded orientation pack
without changing the canonical Markdown files.

## Native route

Requirements: Git and Python 3.11 or newer.

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

The successful validation result is:

```text
OK: bundle conforms to project-knowledge-core 0.1.0 (OKF 0.2)
```

Build a bounded context view:

```bash
knowledge context-pack \
  --profile core/profile.yaml \
  --bundle examples/generic \
  --seed example.system.processing \
  --depth 2 \
  --max-tokens 800
```

Inspect the output for three concepts: the processing system, its governing
Decision and the project root. The context pack is derived orientation only;
the linked files under `examples/generic/` remain authoritative.

This is deliberately an editable source-checkout installation and remains the
shortest way to evaluate an unreleased revision.

## Artifact-installed native fallback

No artifact has been published yet. For a locally built or future released
wheel, keep execution separate from the immutable public-source checkout:

```bash
GNOSTOA_SOURCE=/absolute/path/to/pinned/gnostoa-source

python3 -m venv .venv
. .venv/bin/activate
python -m pip install --only-binary=:all: --require-hashes \
  -r "$GNOSTOA_SOURCE/requirements/runtime.lock"
python -m pip install --no-deps /absolute/path/to/gnostoa-0.1.0-py3-none-any.whl

export KNOWLEDGE_KIT_ROOT="$GNOSTOA_SOURCE"
knowledge validate \
  --profile "$KNOWLEDGE_KIT_ROOT/core/profile.yaml" \
  --bundle "$KNOWLEDGE_KIT_ROOT/examples/generic"
```

The wheel intentionally does not duplicate canonical schemas, profiles or
guidance. `KNOWLEDGE_KIT_ROOT` locates those assets; it does not prove their
identity. A consuming project must also hash-pin the executable artifact and
validate its `.knowledge/kit.lock.yaml` source revision and public-surface
digest before use. Missing or malformed bindings fail explicitly.

## Container route

Requirements: Git and a Docker-compatible container runtime.

`ci/build-runtime` supplies the image with exactly the Git-tracked candidate
files at their current working-tree contents, so a local scratch file cannot
become runtime source. It needs a Git checkout: a plain source archive has no
candidate to read.

```bash
git clone https://github.com/ktogias/gnostoa.git
cd gnostoa

ci/build-runtime --tag gnostoa:source-checkout

docker run --rm gnostoa:source-checkout self-check
```

To validate the checkout through the image's public command surface:

```bash
docker run --rm \
  --mount type=bind,source="$PWD",target=/workspace,readonly \
  --workdir /workspace \
  gnostoa:source-checkout \
  validate \
  --profile core/profile.yaml \
  --bundle examples/generic
```

## What this proves

- the checkout installs and exposes the declared `knowledge` command;
- clean wheel and source-distribution installs use an explicit source binding;
- the generic profile validates a technology-neutral fixture;
- the same canonical bundle can produce a bounded derived view; and
- the container can run the repository self-check as a non-root user.

It does not prove that a package or image has been published, that Gnostoa is
production-ready, or that another project can adopt it efficiently. Those are
separate release and transfer gates.

For release-candidate verification, the maintainer smoke builds both native
archives, checks their metadata and clean-install behavior, and can emit an
exact evidence manifest. See [Compatibility and upgrade status](compatibility.md)
for the command, pinning boundary and remaining non-promises.

## Continue

- Read [Current status](status.md) before relying on a capability.
- Read [Compatibility and upgrade status](compatibility.md) before pinning an
  artifact or changing a toolkit version.
- Follow the [adoption guide](core/adoption.md) to evaluate project integration.
- Use the [reusable guidance router](../guidance/index.md) for a specific task.
- Inspect the [public inheritance contract](../knowledge/contracts/public-inheritance-surface.md)
  before extending a profile.
