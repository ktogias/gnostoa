#!/usr/bin/env python3
"""Repository entry point for the clean native artifact smoke."""

from pathlib import Path
import sys


REPOSITORY_ROOT = Path(__file__).resolve().parent.parent
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from tools.release_smoke import main  # noqa: E402


if __name__ == "__main__":
    raise SystemExit(main())
