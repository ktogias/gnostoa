# Contributing to Gnostoa

This file is a router. Canonical rules remain in the validated policy, guidance
and self-knowledge surfaces.

1. Read [`policy/change-control.yaml`](policy/change-control.yaml) and classify
   the change through the
   [change workflow](guidance/workflows/propose-review-merge-change.md).
2. Use the [maintainer runbook](knowledge/runbooks/maintain-the-kit.md) for
   toolkit-specific verification.
3. Work on a bounded branch and open a Change Request using
   [`templates/change-request.md`](templates/change-request.md).
   Gnostoa requires a linked Work Item and Decision for every non-mechanical
   change; an emergency may complete them in its mandatory follow-up.
4. Follow the
   [proportionate verification workflow](guidance/workflows/develop-verification-first.md)
   and establish the Gnostoa self-policy's required evidence before
   implementation, except for the explicit emergency follow-up path.
5. Run `knowledge self-check`.
6. For CI or hook changes, follow
   [configure continuous integration](guidance/workflows/configure-continuous-integration.md)
   and run `./ci/verify policy`. Run `./ci/verify extended` for changes that
   affect the maintained Python quality, documentation or release-evidence
   surfaces.
7. Inspect the final diff before merge. Community contributions receive
   maintainer review; satisfy additional approval gates only when the effective
   specialization requires them.

## Historical bootstrap boundary

The large append-only ledger on Issue #12 and PR #2 records Gnostoa's one-time
B1 self-dogfood bootstrap. It is useful failure and recovery evidence, but it is
**not the expected contribution workflow**. Contributors are not expected to
produce content-addressed prose packets or repeated recording approvals.
Present one compact current Change Request, use provider-native review, ask one
human decision for each genuine semantic choice and keep verification
proportionate to the effective policy and actual risk. Detailed deterministic
evidence should be generated or linked, not copied into a new comment at every
step. The bounded [B2 experiment](https://github.com/ktogias/gnostoa/issues/24)
will test this streamlined route explicitly.

The one-time pre-publication provider exception is recorded in
[`Decision 0013`](knowledge/decisions/0013-defer-provider-enforcement-while-private.md).
Protection is mandatory when the first baseline is published.

## Copyright and contribution license

Contributors retain copyright in their contributions. An intentionally
submitted contribution is provided under Apache-2.0 as described by Section 5
of [`LICENSE`](LICENSE), unless it is explicitly marked otherwise or a separate
agreement applies. The project does not currently require copyright assignment
or a Contributor License Agreement.

Submit only work you have authority to license. Resolve employer,
institutional, research-grant and third-party ownership before contribution.
See [`LICENSING.md`](LICENSING.md) for the repository-wide licensing boundary.
