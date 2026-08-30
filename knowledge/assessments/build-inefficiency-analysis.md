---
type: Source
title: Build image inefficiency analysis and best practices
description: Evidence-based analysis of Docker build image inefficiency with best practice recommendations following the evidence-gated capability evolution lifecycle.
status: draft
generated:
  by: agent:opencode
  at: "2026-08-26T00:00:00Z"
sources:
  - id: issue-132-build-inefficiency
    resource: https://github.com/ktogias/gnostoa/issues/132
    title: Investigate repeated candidate-image build inefficiency
  - id: issue-7-workspace-ownership
    resource: https://github.com/ktogias/gnostoa/issues/7
    title: Workspace ownership and hermetic safeguards
  - id: issue-130-adoption-completion
    resource: https://github.com/ktogias/gnostoa/issues/130
    title: Adoption-completion gate
x-project-knowledge:
  id: kit.assessment.build-inefficiency-analysis
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governed-by
      target: /lifecycles/evidence-gated-capability-evolution.md
    - kind: derived-from
      target: /assessments/b2-p1-streamlined-self-hosting-measurements.md
    - kind: references
      target: /failure-modes/publication-baseline-review-drift.md
---

# Build image inefficiency analysis and best practices

## Executive Summary

This document analyzes the build image inefficiency identified in [Issue #132](https://github.com/ktogias/gnostoa/issues/132) and recommends evidence-based best practices for optimization. The analysis follows the project's evidence-gated capability evolution lifecycle, progressing through all seven epistemic questions before recording the research record.

Assessment candidate complete; awaiting owner review/integration/reconciliation.

## Current State

**Measured Impact**: 5 builds accumulated 269 seconds of build time, with the largest single waste at 42 seconds (runtime-build stage). The relevant locked dependency inputs were unchanged across the measured candidate builds while dependency-install/build work was repeated.

**Root Cause**: Docker layer cache invalidation due to:
1. Source code changes invalidating downstream layers
2. No cache mounts for download directories
3. No cross-job image reuse
4. Governance files included in full-context (development) builds

## Epistemic Order (Research)

### 1. What the system can know

Five builds completed; cumulative 269s; largest single waste 42s (runtime-build); largest candidate-context waste 83s; runtime produced by 4 of 5 runs (smoke job runtime ignored).

### 2. Which mechanisms are already present and deterministic

Docker layer cache works, but `runtime-build` triggers on every candidate context; no optional cache mounts bound; smoke job tags with merge SHA while building with PR-head context; no cross-job shared image reuse.

### 3. Which observations are authoritatively acquired

Build logs were captured during the measurement session (5 entries); pipeline triggers recorded (5 runs); timing data measured across 3 runs; `manifest.json` verified as deterministic. **Limitation**: The referenced workflow-run IDs are from the measurement session and may not be resolvable from the current provider surface if those runs have expired or been cleaned up. The timing measurements are durable; the full logs are not guaranteed to be.

### 4. At which system boundary a mechanism is reliably executed

Dependency-first layering applies at Dockerfile boundary; optional cache mounts apply at runner boundary; shared-image reuse requires GitHub Actions cache boundary; smoke-image naming is bounded by GitHub event boundary.

### 5. Whether new evidence primitives are needed

Not yet; class B transitioning to class C. No new evidence primitive appears necessary for the current research decision; some raw historical logs are no longer durably bound.

### 6. Which smaller mechanics should be verified first

Dependency-first layering for `development` stage; optional `--mount=type=cache` for pip download directory; smoke-job image-name correction; then optional per-work-item shared image via GHA cache.

### 7. Where oracle limits remain

The owner must judge whether the inefficiency is worth fixing, cache poisoning risk is low enough, shared image is safe enough, smoke naming should be corrected, and speed-vs-determinism balance is acceptable.

## Measurements

| Run | Workflow | Job | Candidate context | Build duration (s) | pip install duration (s) | Runtime produced? |
|-----|----------|-----|-------------------|---------------------|--------------------------|-------------------|
| 14276646574 | verification.yml (push to main) | fast | full | 61 | 1.126 | yes |
| 14276222604 | verification.yml (push to main) | regression | full | 51 | 0.685 | yes |
| 14275965916 | verification.yml (push to main) | extended | full | 42 | 0.522 | yes |
| 14275830343 | publish-oci.yml (workflow_dispatch) | build-runtime-image | filtered (45→36 files) | 97 | 15.133 | yes |
| 14275414862 | verification.yml (merge_group) | smoke | full | 18 | 0.383 | no (ignored) |

**Key finding**: `runtime-build` stage rebuilds from scratch on every candidate context change. The largest single waste is 42s (run 14275965916). The relevant locked dependency inputs were unchanged across the measured candidate builds while dependency-install/build work was repeated. Candidate context filtering removes only 9 files (governance docs), providing negligible speed benefit for this codebase.

## Deterministic-Sufficiency Judgment

Build defense is bounded to smoke tests. The stage sequence is deterministic. Exact OCI digest rebuild repeatability is not established (see v0.1.2 publication result). Optional reuse of deterministic runtime images across jobs or across commits in the same Pull Request is bounded by the evidence-gated lifecycle and would not weaken build defense, provided reuse is scoped to jobs with the same exact source/build subject.

## Best Practice Recommendations

### 1. Dependency-First Layering (Priority: Critical)

**Practice**: Copy dependency manifests before application code in Dockerfiles.

**Rationale**: Docker uses layer caching. When a layer changes, all subsequent layers rebuild. By copying `requirements.txt` or `pyproject.toml` before source code, we ensure dependency installation is cached until dependencies actually change.

**Current State**: Our Dockerfile copies source code before dependencies, causing full rebuilds on any code change.

**Recommendation**:
```dockerfile
# GOOD: Dependencies first
COPY requirements/ ./requirements/
COPY pyproject.toml .
RUN pip install --no-cache-dir -r requirements.txt

# Then copy source code
COPY src/ ./src/
```

**Evidence**: Industry standard practice; Docker documentation explicitly recommends this pattern.

### 2. BuildKit Cache Mounts (Priority: High — requires separate experiment)

**Practice**: Use `--mount=type=cache` for download directories.

**Rationale**: Even with dependency-first layering, `pip install` still downloads packages from PyPI. Cache mounts persist download caches across builds, eliminating network latency for unchanged dependencies.

**Current State**: No cache mounts used; `pip install` re-downloads packages on every build.

**Experiment Required**: The current recipe `--mount=type=cache,target=/root/.cache/pip` with `pip install --no-cache-dir` conflicts: `--no-cache-dir` disables the cache that the mount is trying to persist. This must be tested as a separate experiment with either:
- Change pip invocation to `pip install` (without `--no-cache-dir`) under controlled evidence, or
- Do not claim the cache-mount benefit until the conflict is resolved.

**Evidence**: Docker documentation; AWS build optimization guide. Actual benefit to be measured in controlled experiment.

### 3. Multi-Stage Build Optimization (Priority: Medium)

**Practice**: Separate build-time and runtime dependencies.

**Rationale**: Build tools (compilers, test frameworks) are unnecessary in production images. Smaller images mean faster pulls, less storage, and reduced attack surface.

**Current State**: Already implemented. The `runtime-build` stage uses the runtime lock; the `development` stage uses the development lock. This separation is already satisfied with no remediation selected.

**Recommendation**: Maintain this pattern.

### 4. Image Reuse Across Jobs (Priority: Medium — requires careful scoping)

**Practice**: Share verified runtime images between verification jobs with the same exact source/build subject.

**Rationale**: The same runtime image is rebuilt identically across verification.yml jobs (excluding smoke, which checks out the PR head). Building once and reusing could save build time per subsequent job.

**Current State**: Each verification job builds its own image independently.

**Recommendation**: Build runtime image once, store in GitHub Actions cache or local registry, reuse in dependent jobs. **Must be keyed and scoped only across jobs with the same exact source/build subject** (e.g., fast, regression, extended on the same merge candidate). Smoke job uses a different subject and must not share images.

**Caveat**: Requires careful consideration of cache invalidation, build determinism, and cache-poisoning controls.

### 5. Governance Separation (Priority: Low)

**Practice**: Exclude governance files from production contexts.

**Rationale**: Governance docs (decisions, roadmaps, knowledge base) are irrelevant to runtime. Including them wastes storage and complicates builds.

**Current State**: `ci/build-runtime` already filters these files.

**Recommendation**: Maintain current practice; no action needed.

## Implementation Roadmap

### Phase 1: Low-Risk, High-Impact (Immediate)

1. **Fix smoke job naming** - Correct image tag naming inconsistency (correctness issue)
2. **Dependency-first layering for `development` stage** - Move dependency installation before source code copy in `development` stage only (not `runtime-build`, which participates in candidate-manifest/source-binding semantics)
3. **Cache mount experiment** - Test BuildKit cache mount with appropriate pip invocation (resolve `--no-cache-dir` conflict)

**Expected Impact**: To be measured in controlled experiments.

### Phase 2: Medium-Risk, Medium-Impact (Future)

1. **Implement image reuse** - Share runtime images across verification jobs (scoped to same source/build subject only)
2. **Optimize CI pipeline** - Parallelize independent jobs

**Expected Impact**: To be measured after Phase 1.

### Phase 3: High-Risk, High-Impact (Long-term)

1. **Implement build matrix** - Test multiple configurations simultaneously
2. **Add build caching to registry** - Store layers in container registry

**Expected Impact**: Further optimization, but requires significant infrastructure changes.

## Security Considerations

### Cache Poisoning Risk

**Risk Level**: Medium

**Mitigation**:
- Use cache mounts only for download directories (not build outputs)
- Implement cache key versioning
- Regularly rotate cache keys
- Monitor cache usage

### Image Reuse Security

**Risk Level**: Low

**Mitigation**:
- Verify image integrity before reuse
- Use immutable tags for shared images
- Implement access controls for image storage

## Monitoring and Measurement

### Key Metrics

1. **Build duration** - Total time per job
2. **Cache hit rate** - Percentage of cached layers used
3. **Download time** - Time spent downloading packages
4. **Image size** - Final production image size

### Measurement Tools

- Docker build timing (`--progress=plain`)
- GitHub Actions job timing
- Layer analysis (`docker history`)
- Cache statistics (`docker system df`)

## References

1. Docker Documentation - Multi-stage builds
2. Docker Documentation - BuildKit cache mounts
3. AWS - Optimize Docker builds for CI/CD
4. GitHub Actions - Caching dependencies
5. Container Best Practices - Security hardening

## Recommended Implementation Order

Following the owner's suggested order:

1. **Smoke job image-name correction** (correctness issue): rename tag from `${{ github.sha }}` (merge SHA) to PR-head SHA to match actual content source. This is an identity/observability ambiguity, not merely an optimization.
2. **Isolated `development` dependency-layering experiment**: move `COPY requirements/ .` and `COPY pyproject.toml .` before source code copy in `development` stage only. Do not generalize to `runtime-build` without a separate binding analysis.
3. **Separate pip cache-mount experiment**: test BuildKit cache mount with cold/warm and changed/unchanged-lock measurements. Resolve the `--no-cache-dir` conflict before claiming benefit.
4. **Exact-subject cross-job image reuse** (only if still justified): implement with cache-poisoning and identity controls, scoped only to jobs with the same exact source/build subject.

## Non-Goals

- Chasing CI concurrency or job-level parallelism.
- Changing the package set for speed.
- Changing what gets built or verified.
- Accelerating network or registry operations.
- Replacing the runtime image reuse mechanism with a different approach.
- Introducing new infrastructure beyond Docker and GitHub Actions.

## Backward-Compatible Evolution

| Step | Safe rollback? | Risk level |
|------|---------------|------------|
| Dependency-first layering | yes | low |
| Cache mount | yes | low |
| Smoke naming fix | yes | low |
| Shared image | yes | medium |
| Export cache | yes | medium |

## Status

Assessment candidate complete; awaiting owner review/integration/reconciliation. Recorded in [Issue #132](https://github.com/ktogias/gnostoa/issues/132). No code changes were made — the working tree remains clean.

The next step would be change implementation (smoke naming fix, dependency-layering experiment, cache-mount experiment), which requires a Work Item and Decision before proceeding per the evidence-gated lifecycle.
