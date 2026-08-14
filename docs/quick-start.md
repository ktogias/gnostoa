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
python -m pip install -r requirements/runtime.lock
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

This is deliberately an editable source-checkout installation. The current
wheel installation has no verified binding to the separate pinned public
source that supplies schemas and profiles, so it is not a supported quick-start
path. Release preparation must define and retest that binding rather than hide
the limitation or silently create a second canonical copy.

## Container route

Requirements: Git and a Docker-compatible container runtime.

```bash
git clone https://github.com/ktogias/gnostoa.git
cd gnostoa

docker build \
  --target runtime \
  --build-arg VCS_REF=source-checkout \
  --tag gnostoa:source-checkout \
  .

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
- the generic profile validates a technology-neutral fixture;
- the same canonical bundle can produce a bounded derived view; and
- the container can run the repository self-check as a non-root user.

It does not prove that a package or image has been published, that Gnostoa is
production-ready, or that another project can adopt it efficiently. Those are
separate release and transfer gates.

## Continue

- Read [Current status](status.md) before relying on a capability.
- Follow the [adoption guide](core/adoption.md) to evaluate project integration.
- Use the [reusable guidance router](../guidance/index.md) for a specific task.
- Inspect the [public inheritance contract](../knowledge/contracts/public-inheritance-surface.md)
  before extending a profile.
