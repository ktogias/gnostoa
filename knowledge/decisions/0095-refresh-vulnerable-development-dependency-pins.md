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

3. **The advisory evidence is recorded before and after, and bound to the exact lock.**
   A claim a reader cannot reproduce is the same defect this repository fixes in its
   review artefacts: it asserts a result without the condition that makes it checkable.
   So the command, the subject's content identity and the environment are recorded, not
   only the outcome.

   | | |
   |---|---|
   | command | `python -m pip_audit --no-deps --strict --progress-spinner off --requirement requirements/development.lock` |
   | environment | Python 3.12.14, `pip-audit` 2.10.1, in the repository's `development` image |
   | lock before | sha256 `e3c2f4f5b429fadf903ac9981ebcc8f5d303497dc06468413bcb6373624cba5b` (at `ff9915e`) |
   | lock after | sha256 `e4fbace14e5c7fb2734e240625df7a8433daccad25c499c85a46c13f1c664fba` |
   | report before | `Found 3 known vulnerabilities in 1 package` -- urllib3 2.7.0, CVE-2026-97687/97688/97689, each `Fix Versions: 2.8.0` |
   | report after | `No known vulnerabilities found` |

4. **The resolution is proved, not assumed** -- and the proof names its environment,
   because this observation has no meaning without one.

   ```
   python -m pip install --dry-run --quiet --report <path> \
     --requirement requirements/development.lock
   ```

   Run in an image built from the **previous** lock, the report's `install` list holds
   exactly one entry, `urllib3 2.8.0`: the resolver, with `--require-hashes` in force,
   finds every other pin already satisfied at its locked version. Run in an image built
   from **this** lock, the list is empty, because nothing is left to change.

   Both readings say the same thing -- urllib3 is the only pin that moves -- and
   neither is the whole claim on its own. An earlier draft of this Decision recorded
   only the first as though it were absolute, which would have failed for the next
   reader who ran it in the obvious place.

5. **The evidence is produced in an image built from the lock under test.** The suites
   were first run in a container built from the *previous* lock, and the repository's
   own gate refused it: `installed distribution version mismatch for urllib3: expected
   2.8.0, found 2.7.0`. A lock verified against an environment that does not use it is
   not verified. The green run is on an image rebuilt from this branch.

6. **Nothing else moves.** `requirements/runtime.lock` is untouched, and no other pin in
   the development lock is refreshed in this change. A lock regeneration that wants to
   move other versions is a separate decision with separate evidence; bundling it here
   would mean a security fix that cannot be reviewed for what it actually changes.

7. **It lands on `main`, not on a feature branch.** Every branch inherits the fix from
   there. Fixing it inside an open Pull Request would leave `main` and the other
   branches red, and would create a lock conflict when the branches later merge.

## Consequences

`ci/verify extended` can pass again, and with it `regression`, so open Pull Requests can
be assessed on their own content.

This Decision does not establish a dependency-update cadence, a policy for which
advisories justify a bump, or any automation. It records one advisory answered on the
evidence above. A standing practice, if wanted, is separate work.
