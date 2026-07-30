# syntax=docker/dockerfile:1@sha256:87999aa3d42bdc6bea60565083ee17e86d1f3339802f543c0d03998580f9cb89

ARG PYTHON_BASE_IMAGE=python:3.12-slim@sha256:57cd7c3a7a273101a6485ba99423ee568157882804b1124b4dd04266317710de
FROM ${PYTHON_BASE_IMAGE} AS base

ARG GIT_PACKAGE_VERSION=1:2.47.3-0+deb13u1

RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install --yes --no-install-recommends \
      "git=${GIT_PACKAGE_VERSION}" \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd --gid 10001 kit \
    && useradd --uid 10001 --gid 10001 --create-home --shell /bin/sh kit

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

WORKDIR ${KNOWLEDGE_KIT_ROOT}
COPY --chown=kit:kit . .
RUN python -m pip install --no-cache-dir -r requirements/runtime.lock \
    && python -m pip install --no-cache-dir --no-deps -e .

FROM base AS runtime
USER kit
WORKDIR /workspace
ENTRYPOINT ["knowledge"]
CMD ["--help"]

FROM base AS development
USER root
RUN python -m pip install --no-cache-dir -r requirements/development.lock
USER kit
WORKDIR /workspace
CMD ["sleep", "infinity"]
