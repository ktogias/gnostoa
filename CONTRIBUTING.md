# Contributing to Gnostoa

This file is a router. Canonical rules remain in the validated policy, guidance
and self-knowledge surfaces.

1. Read [`policy/change-control.yaml`](policy/change-control.yaml) and classify
   the change through the
   [change workflow](guidance/workflows/propose-review-merge-change.md).
2. Use the [maintainer runbook](knowledge/runbooks/maintain-the-kit.md) for
   toolkit-specific verification.
3. Create the required Work Item and Decision, then work on a short-lived
   branch and open a Change Request using
   [`templates/change-request.md`](templates/change-request.md).
4. Follow the
   [verification-first workflow](guidance/workflows/develop-verification-first.md)
   before implementation.
5. Run `knowledge self-check`.
6. For CI or hook changes, follow
   [configure continuous integration](guidance/workflows/configure-continuous-integration.md)
   and run `./ci/verify policy`.
7. Do not self-approve or bypass required human/CODEOWNER review.

The repository currently has no published baseline or remote. The one-time
bootstrap exception is recorded in
[`Decision 0006`](knowledge/decisions/0006-provider-neutral-change-governance.md).
Protection is mandatory immediately after the first reviewed baseline is
published.

## Copyright and contribution license

Contributors retain copyright in their contributions. An intentionally
submitted contribution is provided under Apache-2.0 as described by Section 5
of [`LICENSE`](LICENSE), unless it is explicitly marked otherwise or a separate
agreement applies. The project does not currently require copyright assignment
or a Contributor License Agreement.

Submit only work you have authority to license. Resolve employer,
institutional, research-grant and third-party ownership before contribution.
See [`LICENSING.md`](LICENSING.md) for the repository-wide licensing boundary.
