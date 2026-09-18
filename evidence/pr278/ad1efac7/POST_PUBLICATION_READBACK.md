# Post-publication read-back — PR #278 historical review archive

Recorded 2026-09-18 by ChatGPT at the owner's request to preserve the full report and evidence. This is an append-only operational receipt, not a new code review, human approval, test result or merge authorization.

## Permanent published objects

- Evidence commit: `0f7fe446272219fb42f615d0db1a55107953bb8f`.
- Evidence tree: `b74d301e1c14264f7b729462459c4ecda531ac76`.
- Evidence-only branch: `evidence/pr278-deep-review-ad1efac7-20260918`.
- [Full report in PR](https://github.com/ktogias/gnostoa/pull/278#issuecomment-5735783198).
- [Commit-pinned full report](https://github.com/ktogias/gnostoa/blob/0f7fe446272219fb42f615d0db1a55107953bb8f/evidence/pr278/ad1efac7/REPORT.el.md).
- [Commit-pinned complete archive](https://github.com/ktogias/gnostoa/blob/0f7fe446272219fb42f615d0db1a55107953bb8f/evidence/pr278/ad1efac7/complete-review-archive.zip).

`complete-review-archive.zip`: **1498406 bytes**, SHA-256 `1071f96cf543630658c28a7e0fa111b2aaa1ece468e682d4443d123dacc4101b`, Git blob `370f7fbc2844b720fea74bd1d930081f1f86fcc2`.

The original 149497-byte review ZIP and 135205-byte provider ZIP were retained byte-for-byte, with their original SHA-256 values. The archival script verified all 18 original members, 13 internal provider manifest entries (14 reports including the summary) and 8/8 exact-source AST extracts. The archival validation is separate from the original 12-test Python 3.13.5 run. No candidate code or original tests were executed by the archiver.

## The helper did NOT finish green

[Archival workflow run 35392149686](https://github.com/ktogias/gnostoa/actions/runs/35392149686), job `105752707914`, completed with **failure**. Its final log shows the failure occurred at the immediate ref read-back, after creating the archive commit and requesting its ref update:

```text
2026-09-18T20:34:32.8933631Z Traceback (most recent call last):
2026-09-18T20:34:32.8934139Z   File "<stdin>", line 13, in <module>
2026-09-18T20:34:32.8934440Z   File "<frozen runpy>", line 286, in run_path
2026-09-18T20:34:32.8934773Z   File "<frozen runpy>", line 98, in _run_module_code
2026-09-18T20:34:32.8935170Z   File "<frozen runpy>", line 88, in _run_code
2026-09-18T20:34:32.8935552Z   File "/home/runner/work/_temp/archive_pr278.py", line 315, in <module>
2026-09-18T20:34:32.8935899Z     main()
2026-09-18T20:34:32.8936166Z   File "/home/runner/work/_temp/archive_pr278.py", line 307, in main
2026-09-18T20:34:32.8936542Z     raise RuntimeError('evidence ref read-back mismatch')
2026-09-18T20:34:32.8937388Z RuntimeError: evidence ref read-back mismatch
2026-09-18T20:34:32.9153371Z ##[error]Process completed with exit code 1.
```

This is the exact failure excerpt, not the full job transcript. The provider run retains the full log. The cause of the immediate mismatch has **not been established**. It must not be rewritten as a successful workflow, attributed to caching without evidence, or treated as a product-check failure.

## Subsequent independent connector read-backs

After the failure, separate authenticated GitHub connector reads established:

1. The evidence branch ref points to `0f7fe446272219fb42f615d0db1a55107953bb8f`.
2. That commit exists, points to tree `b74d301e1c14264f7b729462459c4ecda531ac76`, and has bootstrap commit `df46e02335efd90d4f195ed662ef6dceb6abcc29` as parent.
3. The full, untruncated tree includes the report, original archives, complete archive, manifests, original results, verifier and validation records with the expected blob identities and sizes.
4. The published `archival-validation.json` and `ARCHIVE.sha256` were fetched directly at that commit. They retain the verification results and archive hash above.
5. The final tree contains no `.github` workflow or bootstrap directory: the one-shot helper was retired from the evidence branch's published tree.
6. Protected `main` remained `7c14f9111cb560ea26dd68440812f64b37069706` on read-back.

These read-backs independently verify publication of the recorded Git objects, ref and validation files; they are not a second local download-and-byte-verification of the full binary archive. The connector's generic text fetch could not download that ZIP. Its Git object, size and published digest remain available, and the archive contains an offline verifier for readers.

## Scope and next-agent navigation

The report stays bound to reviewed head `ad1efac7b5d62f2252131483066579728012690c` and provider event/merge subject `fb3b19d1b1a01c58d11bc8c88da4e71e5595a1ec`. The later archived PR read-back observed `efc39c409e696e45b1529e76df101c0d2cbc3968`; this does not rebind the historical review to newer code.

The complete archive and its internal manifests remain unmodified. This receipt necessarily follows publication and is therefore outside the original archive. It is retained as a separate evidence-only follow-up, not retroactively inserted into the original evidence.

[Issue #275 R1–R7](https://github.com/ktogias/gnostoa/issues/275#issuecomment-5734815516) remains the sole operational restoration checklist. No checklist box is satisfied merely by archiving this report. No main or PR-source commit, merge, reviewer-thread resolution, release/OCI publication, authority promotion or required-check configuration change was performed by this archival task. The evidence branch must not be merged into main or the PR source branch.
