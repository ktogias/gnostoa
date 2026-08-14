#!/usr/bin/env python3
"""Repository entry point for bounded release-quality evidence."""

from pathlib import Path
import sys


REPOSITORY_ROOT = Path(__file__).resolve().parent.parent
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from tools.quality_evidence import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
