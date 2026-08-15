## Protected integration branch

- [ ] The default integration branch is protected.
- [ ] Direct push, force push and deletion are prohibited.
- [ ] A Change Request is required before integration.
- [ ] Required CI checks must pass.
- [ ] Unresolved review conversations block integration.
- [ ] Required approval count is zero when the repository has one maintainer and
      the project has not selected a stricter specialization.
- [ ] CODEOWNER approval is required where the policy declares it.
- [ ] Community contributions receive accountable maintainer review.
- [ ] Author or agent self-approval does not satisfy an independent approval
      required by a stricter specialization.
- [ ] New reviewable commits invalidate or refresh prior approval.
- [ ] The latest Change Request and merge candidate report stable required
      policy, fast and regression checks.
- [ ] Merge-queue or merged-result validation is enabled where supported.
- [ ] Required workflows cannot be skipped by path or commit-message filtering.

## Merge and recovery

- [ ] Short-lived branches are deleted after integration.
- [ ] Auto-merge is limited to policy classes that permit it.
- [ ] Emergency bypass is restricted to authorized humans and audited.
- [ ] Obsolete branch runs may be cancelled; trunk and release runs are not.
- [ ] A provider/version limitation that prevents enforcement is recorded as a
      Decision with compensating controls.

## Audit

- [ ] Settings are rechecked after provider, plan or organization-policy changes.
- [ ] The effective provider settings match `.knowledge/change-control.yaml`.
- [ ] Provider events match `.knowledge/continuous-integration.yaml`.
- [ ] Workflow/actions/components and runtime images are pinned immutably.
- [ ] The configured project verification image equals the manifest image.
- [ ] Verification permissions are read-only and untrusted changes receive no
      privileged secrets.
