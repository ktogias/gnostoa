#!/usr/bin/env python3
"""Run the bounded tracked-tree secret gate without exposing candidate values."""

from __future__ import annotations

import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parent.parent
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from tools.security_scan import SecurityScanError, scan_tracked_tree  # noqa: E402


def main() -> int:
    try:
        result = scan_tracked_tree(REPOSITORY_ROOT)
    except SecurityScanError as exc:
        print(f"ERROR: security-fast failed: {exc}", file=sys.stderr)
        return 1
    for finding in result.unresolved_findings:
        print(
            "ERROR: unresolved secret candidate: "
            f"{finding['path']}:{finding['line']} ({finding['type']})",
            file=sys.stderr,
        )
    if result.unresolved_findings:
        return 1
    print(
        "security-fast: PASS "
        f"(reviewed_false_positives={result.reviewed_false_positives}, "
        "unresolved=0)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
