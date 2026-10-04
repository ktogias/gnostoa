"""The one path-confinement check the agent review pipeline shares (Decision 0100).

Every path a pipeline step reads or writes comes from its composition, which is
trusted -- but a value that reaches a file read or write is worth checking where it is
used, not where it was set, and the check costs nothing.

It lives in one module because the check has been wrong twice: an earlier version
accepted a leading dash, and another accepted an empty argument, which resolves to the
working directory and would then satisfy every remaining check. Both had to be fixed in
three places. A second copy is a second chance to fix one and miss another.

Provider- and CI-neutral: the root a path must stay inside is named by its caller, as
an environment variable, so the core never assumes one runner's layout.
"""

from __future__ import annotations

import os
import pathlib


def within(raw: str, root_variable: str, *, must_exist: bool) -> pathlib.Path:
    """Resolve ``raw`` and refuse anything outside the area it belongs to.

    When the environment names the root, the resolved path must sit inside it;
    otherwise it must at least be absolute with an existing parent, which is what a
    local test run gives. Passing an empty ``root_variable`` asks for the second
    treatment deliberately -- a summary path is not pinned to a root, because refusing
    the report over an assumption about the runner's layout would lose the review.
    """
    if not raw or not raw.strip():
        # An empty argument resolves to the working directory, which is a real path and
        # would sail through every check below. A degenerate input is a reason to stop.
        raise ValueError("refusing an empty path")
    path = pathlib.Path(raw).resolve()
    if must_exist and not path.exists():
        raise ValueError(f"refusing a path that does not exist: {raw!r}")
    if not path.parent.exists():
        raise ValueError(f"refusing a path whose parent does not exist: {raw!r}")
    if path.is_dir() and not must_exist:
        # A file is expected here; a directory would fail later with a confusing error
        # or, worse, silently name something writable.
        raise ValueError(f"refusing a directory where a file is expected: {raw!r}")
    root = os.environ.get(root_variable)
    if root:
        resolved_root = pathlib.Path(root).resolve()
        if not path.is_relative_to(resolved_root):
            raise ValueError(f"refusing {raw!r}: outside {root_variable}")
    return path
