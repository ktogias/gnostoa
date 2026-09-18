# PR #278 evidence archival bootstrap

Evidence-only support branch for owner-requested archival of the complete ad1efac7 review and all retained artifacts. Never merge this branch into main or the PR source branch. The one-shot workflow reads the fixed provider artifact and public source/review records, verifies all original hashes, writes a commit-pinned archive to this evidence branch only, and removes the bootstrap workflow from the resulting tree. It does not execute candidate code or tests and has no package/release, issue, or pull-request write permissions.

Full report: https://github.com/ktogias/gnostoa/pull/278#issuecomment-5735783198
