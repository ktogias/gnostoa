"""Build the bounded review context from one provider comparison payload.

Writes ``diff.stat``, ``unreviewable.txt`` and ``base/``. Doing all three from one
payload keeps the comparison to a single request and keeps the workflow step free of
an external ``jq``.

The ``base/`` part matters most. Materialise the exact pre-change content of every
changed file.

The bounded reviewer of Decision 0094 reads the repository's default branch for its
entry route and general context, and that tree is deliberately **not** the Pull
Request's base: the branch may have advanced, or the Pull Request may target another
branch. Surrounding unchanged code read from it can therefore come from a revision the
candidate never saw, which produces interaction findings that are not real.

This script writes the exact base revision of each changed file under
``base/`` in the review context, so the reviewer has an authoritative
pre-change state without a candidate working tree ever existing.

Content is written as regular files from provider-supplied bytes, so no mode, symlink
or directory entry from either side reaches the runner. Paths are validated before
use: anything absolute, empty, or containing a parent-directory component is refused
rather than sanitised, because a path that should not occur is a reason to stop.

It is invoked from ``.github/workflows/claude.yml``, which for the mention triggers
runs from the repository's default branch, so it is not candidate-supplied.
"""

from __future__ import annotations

import base64
import json
import pathlib
import re
import shutil
import subprocess  # nosec B404 -- single audited boundary in _provider_json
import sys
import urllib.parse
from typing import Any

_GH = shutil.which("gh")


# Validated on the raw string. PurePosixPath normalises "a//b" and "." away, so
# inspecting its parts would accept names that should never have been produced.
_REFUSED_COMPONENTS = frozenset({"", ".", ".."})


def safe_relative_path(name: str) -> pathlib.PurePosixPath:
    """Return ``name`` as a relative path, refusing anything that could escape."""
    if not name or name.startswith("/") or name.endswith("/"):
        raise ValueError(f"refusing a non-relative path: {name!r}")
    if "\\" in name or "\x00" in name:
        raise ValueError(f"refusing a path with a backslash or NUL: {name!r}")
    components = name.split("/")
    if any(component in _REFUSED_COMPONENTS for component in components):
        raise ValueError(f"refusing a degenerate or traversing path: {name!r}")
    return pathlib.PurePosixPath(*components)


# Checked again at the point of use, not only where the endpoint is built. The
# argument reaching a subprocess is the thing that matters, so it is validated at that
# boundary rather than trusted because an earlier function was careful.
_ENDPOINT = re.compile(
    r"\Arepos/[A-Za-z0-9][A-Za-z0-9._-]*/[A-Za-z0-9][A-Za-z0-9._-]*"
    r"/contents/[A-Za-z0-9._~!$&'()*+,;=:@%/-]+\?ref=[0-9a-f]{40}\Z"
)


def _provider_json(endpoint: str) -> dict[str, Any] | None:
    """Return the provider's JSON for ``endpoint``, or None when it has none."""
    # Validated before anything else: whether the input is acceptable does not depend
    # on whether the tool that would consume it happens to be installed.
    if not _ENDPOINT.match(endpoint):
        raise ValueError(f"refusing an unexpected endpoint: {endpoint!r}")
    if _GH is None:  # pragma: no cover - the workflow always provides gh
        raise RuntimeError("gh is required to reach the provider")
    completed = subprocess.run(  # nosec B603
        # The argv is a fixed executable, a fixed verb and an endpoint matched against
        # _ENDPOINT immediately above, so no argument can be read as a flag.
        [
            _GH,
            "api",
            endpoint,
        ],  # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-audit.dangerous-subprocess-use-audit, python.lang.security.audit.dangerous-subprocess-use-tainted-env-args.dangerous-subprocess-use-tainted-env-args
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        # A file added by the candidate has no base revision. That is expected, and
        # the diff already carries its content.
        return None
    return json.loads(completed.stdout)


_SHA = re.compile(r"\A[0-9a-f]{40}\Z")
# Each side must begin with an alphanumeric: a leading dash is precisely the shape
# that would be read as a flag rather than as an endpoint.
_REPOSITORY = re.compile(r"\A[A-Za-z0-9][A-Za-z0-9._-]*/[A-Za-z0-9][A-Za-z0-9._-]*\Z")


def base_endpoint(repository: str, path: str, base_sha: str) -> str:
    """Build the contents endpoint for ``path`` at ``base_sha``.

    The endpoint is constructed from values this script was given rather than taken
    from the comparison's own ``contents_url``: that field is provider-supplied data
    reaching a subprocess argument, and an endpoint that begins with a dash would be
    read as a flag. Every component is validated, and the path is percent-encoded.
    """
    if not _REPOSITORY.match(repository):
        raise ValueError(f"refusing a malformed repository: {repository!r}")
    if not _SHA.match(base_sha):
        raise ValueError(f"refusing a non-exact base revision: {base_sha!r}")
    encoded = urllib.parse.quote(str(safe_relative_path(path)), safe="/")
    return f"repos/{repository}/contents/{encoded}?ref={base_sha}"


_FILE_CAP = 300


def write_summaries(context: pathlib.Path, comparison: dict[str, Any]) -> None:
    """Write diff.stat and unreviewable.txt from the comparison payload."""
    files = comparison.get("files") or []
    lines = [
        f"{entry['status']} +{entry['additions']} -{entry['deletions']} "
        f"{entry['filename']}"
        for entry in files
    ]
    if len(files) >= _FILE_CAP:
        # The provider caps this list and does not paginate it, so a capped summary
        # must not be allowed to read as the whole change.
        lines.append(
            f"[provider caps the changed-file list at {_FILE_CAP}; "
            "this summary is incomplete]"
        )
    (context / "diff.stat").write_text(
        "".join(f"{line}\n" for line in lines), encoding="utf-8"
    )
    # A file with no patch is binary or oversized: its bytes are in neither the diff
    # nor the checkout, so the reviewer must report it as not examined.
    (context / "unreviewable.txt").write_text(
        "".join(
            f"{entry['status']} {str(entry['sha'])[:9]} {entry['filename']}\n"
            for entry in files
            if entry.get("patch") is None
        ),
        encoding="utf-8",
    )


def collect(
    context: pathlib.Path, repository: str, base_sha: str, budget: int
) -> tuple[int, int]:
    """Write base revisions under ``base/``; return files written and files skipped."""
    comparison = json.loads((context / "comparison.json").read_text(encoding="utf-8"))
    write_summaries(context, comparison)
    target = context / "base"
    target.mkdir(exist_ok=True)
    written = 0
    skipped = 0
    remaining = budget
    for entry in comparison.get("files") or []:
        if entry.get("patch") is None:
            continue
        relative = safe_relative_path(str(entry["filename"]))
        payload = _provider_json(
            base_endpoint(repository, str(entry["filename"]), base_sha)
        )
        if payload is None or "content" not in payload:
            skipped += 1
            continue
        content = base64.b64decode(str(payload["content"]))
        if len(content) > remaining:
            skipped += 1
            continue
        destination = target / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)
        remaining -= len(content)
        written += 1
    notice = target / "README"
    notice.write_text(
        "Exact base revision of each changed file, as provider-supplied bytes.\n"
        f"Written: {written}. Not available or over the budget: {skipped}.\n"
        "A file absent here was added by the candidate, or exceeded the budget; the\n"
        "diff carries its content in either case.\n",
        encoding="utf-8",
    )
    return written, skipped


def main(argv: list[str]) -> int:
    if len(argv) != 5:
        print(
            f"usage: {argv[0]} <context-dir> <repository> <base-sha> <budget-bytes>",
            file=sys.stderr,
        )
        return 2
    collect(pathlib.Path(argv[1]), argv[2], argv[3], int(argv[4]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
