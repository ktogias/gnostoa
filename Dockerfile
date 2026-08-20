# syntax=docker/dockerfile:1@sha256:87999aa3d42bdc6bea60565083ee17e86d1f3339802f543c0d03998580f9cb89

ARG PYTHON_BASE_IMAGE=python:3.12-slim@sha256:2c941e860699f878900b0edc2403613c234d4b32eda3cc9fa7036991a2a63c4a
FROM ${PYTHON_BASE_IMAGE} AS base

ARG GIT_PACKAGE_VERSION=1:2.47.3-0+deb13u1

# Debian security update for the util-linux source package already present in the
# pinned base image. Every version below is pinned explicitly because the binary
# packages use three different version forms for the same source build: plain,
# epoch-bearing (bsdutils) and "+really" (login). Only already-installed packages
# are upgraded; no package is added or removed and no unrelated package moves.
ARG UTIL_LINUX_VERSION=2.41.5-0+deb13u1
ARG UTIL_LINUX_BSDUTILS_VERSION=1:2.41.5-0+deb13u1
ARG UTIL_LINUX_LOGIN_VERSION=1:4.16.0-2+really2.41.5-0+deb13u1

RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install --yes --no-install-recommends \
      "git=${GIT_PACKAGE_VERSION}" \
    && DEBIAN_FRONTEND=noninteractive apt-get install --yes --only-upgrade \
      --no-install-recommends \
      "bsdutils=${UTIL_LINUX_BSDUTILS_VERSION}" \
      "libblkid1=${UTIL_LINUX_VERSION}" \
      "liblastlog2-2=${UTIL_LINUX_VERSION}" \
      "libmount1=${UTIL_LINUX_VERSION}" \
      "libsmartcols1=${UTIL_LINUX_VERSION}" \
      "libuuid1=${UTIL_LINUX_VERSION}" \
      "login=${UTIL_LINUX_LOGIN_VERSION}" \
      "mount=${UTIL_LINUX_VERSION}" \
      "util-linux=${UTIL_LINUX_VERSION}" \
    && rm -rf /var/lib/apt/lists/*

ARG KIT_VERSION=0.1.0
ARG VCS_REF=development
ARG BUILD_DATE=unknown

LABEL org.opencontainers.image.title="Gnostoa" \
      org.opencontainers.image.description="Technology-neutral OKF validation and context tooling" \
      org.opencontainers.image.authors="Konstantinos Togias" \
      org.opencontainers.image.licenses="Apache-2.0" \
      org.opencontainers.image.version="${KIT_VERSION}" \
      org.opencontainers.image.revision="${VCS_REF}" \
      org.opencontainers.image.created="${BUILD_DATE}"

ENV KNOWLEDGE_KIT_ROOT=/opt/gnostoa \
    KNOWLEDGE_KIT_REVISION=${VCS_REF} \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_ROOT_USER_ACTION=ignore

RUN groupadd --gid 10001 kit \
    && useradd --uid 10001 --gid 10001 --create-home --shell /bin/sh kit

WORKDIR ${KNOWLEDGE_KIT_ROOT}

# The published runtime takes its Gnostoa source from `ci/build-runtime`, which
# materialises exactly the Git-tracked candidate paths into a throwaway context.
# Copying the ordinary build context here instead would let host-local files
# become importable Gnostoa source and shadow the pip invocations below, so the
# filtered source must be in place before any source-sensitive Python runs.
FROM base AS runtime-build
ARG MANIFEST_SHA256
COPY --from=candidate --chown=kit:kit source/ .
RUN --mount=from=candidate,type=bind,source=meta/.gnostoa-source-files,target=/tmp/candidate-manifest \
    set -eux; \
    test -n "${MANIFEST_SHA256}"; \
    echo "${MANIFEST_SHA256}  /tmp/candidate-manifest" | sha256sum -c -; \
    find . -mindepth 1 \( -type f -o -type l \) -printf '%P\0' \
      | LC_ALL=C sort -z > /tmp/candidate-payload; \
    cmp -s /tmp/candidate-payload /tmp/candidate-manifest \
      || { echo "source payload does not match the candidate manifest" >&2; exit 6; }; \
    install --owner=kit --group=kit --mode=0444 \
      /tmp/candidate-manifest .gnostoa-source-files; \
    rm -f /tmp/candidate-payload
RUN install --directory --owner=kit --group=kit --mode=0555 .evidence \
    && python -m pip install \
      --no-cache-dir \
      --only-binary=:all: \
      --require-hashes \
      --report .evidence/runtime-install-report.json \
      -r requirements/runtime.lock \
    && chmod 0444 .evidence/runtime-install-report.json \
    && python -m pip install --no-cache-dir --no-deps -e .

# Development keeps the ordinary local context so uncommitted work is usable and
# the devcontainer needs no extra build context. It is deliberately outside the
# filtered-source guarantee above.
FROM base AS development-build
COPY --chown=kit:kit . .
RUN find . -mindepth 1 \( -type f -o -type l \) \
      -printf '%P\0' > /tmp/gnostoa-source-files.unsorted \
    && LC_ALL=C sort --zero-terminated /tmp/gnostoa-source-files.unsorted \
      > /tmp/.gnostoa-source-files \
    && install --owner=kit --group=kit --mode=0444 \
      /tmp/.gnostoa-source-files .gnostoa-source-files \
    && rm -f \
      /tmp/gnostoa-source-files.unsorted \
      /tmp/.gnostoa-source-files
RUN install --directory --owner=kit --group=kit --mode=0555 .evidence \
    && python -m pip install \
      --no-cache-dir \
      --only-binary=:all: \
      --require-hashes \
      --report .evidence/runtime-install-report.json \
      -r requirements/runtime.lock \
    && chmod 0444 .evidence/runtime-install-report.json \
    && python -m pip install --no-cache-dir --no-deps -e .

FROM runtime-build AS runtime
# The published runtime does not use pip: the base stage has already installed
# the runtime lock and the editable source, and no documented runtime command
# imports or invokes pip. Both shipped copies are removed, because uninstalling
# the distribution leaves the wheel bundled under ensurepip, which is a separate
# copy of the same component and can reinstall it.
USER root
RUN set -eux; \
    python -m pip uninstall --yes pip; \
    rm -rf "$(python -c 'import sysconfig; print(sysconfig.get_paths()["stdlib"])')/ensurepip"; \
    rm -f /usr/local/bin/pip /usr/local/bin/pip3 /usr/local/bin/pip3.12
USER kit
WORKDIR /workspace
ENTRYPOINT ["knowledge"]
CMD ["--help"]

FROM development-build AS development
USER root
RUN python -m pip install \
      --no-cache-dir \
      --only-binary=:all: \
      --require-hashes \
      --report .evidence/development-install-report.json \
      -r requirements/development.lock \
    && chmod 0444 .evidence/development-install-report.json
USER kit
WORKDIR /workspace
CMD ["sleep", "infinity"]
