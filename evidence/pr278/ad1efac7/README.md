# PR #278 full historical review and evidence archive

Read REPORT.el.md for the complete report, all dispositions and primary-source references. dispositions.json is a navigation index, not a replacement for the rationale.

This evidence-only branch is not a product change, is not a merge candidate, and must not be merged into main. Use the final commit-pinned URL, not the mutable branch name, as the archival locator.

## Boundaries

Reviewed source: `ad1efac7b5d62f2252131483066579728012690c`.
Provider event/merge subject: `fb3b19d1b1a01c58d11bc8c88da4e71e5595a1ec`.
Later PR state is separately captured under provider-readback/; it is NOT the original review-time snapshot and does not rebind the report to newer code.

## Contents of complete-review-archive.zip

- REPORT.el.md: full Greek report as published in PR comment 5735783198.
- pr278-review-evidence-original.zip: byte-for-byte original 149497-byte review package.
- provider-original.zip: exact original provider archive, artifact 10559267997 / run 35373573729.
- original/: all 18 original review-package members (14 provider reports including quality-summary.json, original README, characterization script, results and artifact audit).
- sources/: exact-source files, commit and complete Git tree metadata; source-index.json contains Git blob identities and SHA-256 hashes. Source extracts remain repository-owned code; the source LICENSE is retained.
- provider-readback/: paginated public comments/reviews and source/workflow/handoff records, collected at archival time. review-source-index.json records attribution, times and commit IDs without manufacturing absent portal findings or thread-resolution state.
- source-extract-validation.json: static AST binding checks, not tests or code execution.
- archival-validation.json: new archival checks and explicit gaps; original test results are unchanged.
- manifest.json, SHA256SUMS and verify_archive.py: per-file integrity metadata and offline verification.
- archiver-source.py: one-shot acquisition/verification script; contains no candidate execution or product repair.

## Verify without running tests

Download the complete ZIP and its outer ARCHIVE.sha256 from the same pinned commit. Verify the outer SHA-256 before extraction, then extract into a new directory and run:

```sh
python3 verify_archive.py
sha256sum -c SHA256SUMS
```

The manifest excludes itself and SHA256SUMS to avoid circular hashing; SHA256SUMS includes manifest.json. The complete ZIP is not a member of itself. Integrity is not signature, original provenance authentication, review approval or merge authorization.

## Reproduce the original isolated characterization separately

Read original/characterization.py first. On Linux/Python 3.11+, copy it into a fresh directory, then execute the copy. It starts/kills test children and overwrites the neighboring characterization-results.json. Retain the new interpreter version, stdout/stderr and result separately; do not overwrite archived evidence. The retained original run used Python 3.13.5. This script uses source extracts and stubs; it is not ci/verify, a full checkout test, Docker execution or a real hostile-filesystem experiment.

The original complete terminal transcript and original-time raw reviewer snapshot were not supplied. Qodo's omitted individual portal findings are not reconstructed. Any source-binding discrepancy in archival-validation.json must be investigated before evidence reuse.

## Restoration obligation

The only operational checklist is https://github.com/ktogias/gnostoa/issues/275#issuecomment-5734815516 (R1–R7), linked from #14 and #15. Containment is not restoration. No box is completed by archiving this report.

## Effects

The archiver reads fixed public source/review artifacts and writes this evidence branch only. It executes no candidate code or tests and retires the temporary bootstrap workflow by replacing the branch tree with evidence-only files. It changes neither main nor the #278 source branch, protected authority, required checks, package/release publication, reviewer-thread status, nor merge state.
