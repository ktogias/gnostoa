---
type: Decision
title: Refresh a vulnerable development dependency pin on protected main
description: Fix a disclosed advisory in the hash-pinned development lock on main, as its own change, without bundling unrelated version drift or touching the runtime lock.
status: draft
generated:
  by: anthropic/claude-opus-5
  at: "2026-09-30T16:05:00Z"
sources:
  - id: work-item
    resource: https://github.com/ktogias/gnostoa/issues/335
    title: urllib3 2.7.0 advisories fail the development dependency audit on every branch
  - id: advisory-cve-97687
    resource: https://nvd.nist.gov/vuln/detail/CVE-2026-97687
    title: CVE-2026-97687 (urllib3)
  - id: advisory-cve-97688
    resource: https://nvd.nist.gov/vuln/detail/CVE-2026-97688
    title: CVE-2026-97688 (urllib3)
  - id: advisory-cve-97689
    resource: https://nvd.nist.gov/vuln/detail/CVE-2026-97689
    title: CVE-2026-97689 (urllib3)
  - id: candidate-preparation
    resource: ./0090-require-pre-candidate-preparation-receipts-for-non-hook-authoring.md
    title: Require pre-candidate preparation receipts for non-hook authoring
x-project-knowledge:
  id: kit.decision.0095.refresh-vulnerable-development-dependency-pins
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governed-by
      target: /decisions/0090-require-pre-candidate-preparation-receipts-for-non-hook-authoring.md
---

# Refresh a vulnerable development dependency pin on protected main

## Context

`requirements/development.lock` pinned `urllib3==2.7.0`. Three advisories were
disclosed against it -- CVE-2026-97687, CVE-2026-97688 and CVE-2026-97689 -- and
`ci/verify extended` fails at its `development_audit` quality gate as a result. The
`regression` suite gates on the extended result, so two checks went red from one cause.

The pin was byte-identical on `main` and on every open Pull Request, so no branch could
reach a green `extended`, including branches whose own content was complete and
reviewed. This is the condition the audit gate exists to create: it stops work until the
advisory is answered. It is not a defect in any candidate.

`urllib3` is not in `requirements/runtime.lock`, so the published runtime image never
carried the advisory. The exposure was the development and CI toolchain only.

## Prior-art and reuse disposition

No custom work was written. The repository already owns the mechanism that found this
(`pip_audit` behind the `development_audit` quality gate) and the mechanism that fixes
it (a hash-pinned lock). The only question was which version to pin and on what
evidence, so this Decision records the evidence rather than a new capability.

The upstream fix is the vendor's own release. No alternative was weighed, because
pinning anything other than a release that clears all three advisories would not close
the finding, and vendoring or patching a transport library to avoid a version bump is
disproportionate to a development-only dependency.

## Decision

1. **The lock records `urllib3==2.8.0` with the wheel's exact SHA-256.** The lock is
   `--only-binary :all:` and `--require-hashes`, so a version bump is a hash change and
   the hash is the thing that must be right.

2. **The hash is verified against the artefact, not against an API response.** The
   wheel was downloaded and its SHA-256 computed locally
   (`0cf3cae568d36aa9576b28dfb35f11328f1cb974ca7647d9475ebb86c75ac6e3`, 135717 bytes),
   and its embedded metadata read back to confirm `urllib3 2.8.0` and
   `Requires-Python: >=3.10` against the repository's supported 3.11 and 3.12.

   The first attempt at this verification used a download that did not fail on an HTTP
   error, and produced the SHA-256 of an empty file. A digest that matches nothing is
   indistinguishable from a digest that matches the wrong thing unless the size and the
   package metadata are checked too, so all three are recorded here.

3. **The advisory evidence is recorded before and after.** `pip_audit` reported three
   vulnerabilities in one package before the change and none after, against the same
   lock file and the same command.

4. **The resolution is proved, not assumed.** `pip install --dry-run` against the whole
   lock resolves with hashes enforced, and reports `urllib3 2.8.0` as the only package
   that needed to change -- so nothing else in the lock was disturbed.

5. **Nothing else moves.** `requirements/runtime.lock` is untouched, and no other pin in
   the development lock is refreshed in this change. A lock regeneration that wants to
   move other versions is a separate decision with separate evidence; bundling it here
   would mean a security fix that cannot be reviewed for what it actually changes.

6. **It lands on `main`, not on a feature branch.** Every branch inherits the fix from
   there. Fixing it inside an open Pull Request would leave `main` and the other
   branches red, and would create a lock conflict when the branches later merge.

## Consequences

`ci/verify extended` can pass again, and with it `regression`, so open Pull Requests can
be assessed on their own content.

This Decision does not establish a dependency-update cadence, a policy for which
advisories justify a bump, or any automation. It records one advisory answered on the
evidence above. A standing practice, if wanted, is separate work.
