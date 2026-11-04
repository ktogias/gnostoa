"""The repository's trusted executable lookup (AGENTS.md): the one search path a tool
starts a named executable from, never the caller's PATH (#389 B1).

It imports only the standard library, so that a module importing it keeps its own
import-time requirements. The self-only tasks/gnostoa_orientation.py and the protected
ci/merge_admission_guard.py state the same lookup themselves."""

from __future__ import annotations

import errno
import os
import shutil

TRUSTED_PATH = "/usr/local/bin:/usr/bin:/bin:/opt/homebrew/bin"


def trusted_executable(name: str) -> str:
    """The absolute path of `name` on TRUSTED_PATH. It is refused as FileNotFoundError
    when it is not there, so that each caller's own OSError handling names it."""
    found = shutil.which(name, path=TRUSTED_PATH)
    if found is None or not os.path.isabs(found):
        raise FileNotFoundError(errno.ENOENT, "not on the trusted lookup", name)
    return found
