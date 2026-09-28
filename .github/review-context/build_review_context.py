"""Build the bounded review context from one provider comparison payload.

Writes ``diff.stat``, ``unreviewable.txt`` and ``base/``. Deriving all three from a
single payload keeps the comparison to one request and keeps the workflow step free of
an external ``jq``, and it puts the field semantics somewhere the suite can exercise
directly rather than by scraping YAML.

``base/`` matters most. The bounded reviewer of Decision 0094 reads the repository's
default branch for its entry route and general context, and that tree is deliberately
**not** the Pull Request's base: the branch may have advanced, or the Pull Request may
target another branch. Unchanged code read from it can therefore come from a revision
the candidate never saw, which produces interaction findings that are not real. So the
exact base revision of every changed file is written here, as provider-supplied bytes.

Bytes, not a checkout: no mode, symlink or directory entry from either side reaches the
runner, which is what keeps rule 21 intact. Provider-supplied names are refused rather
than sanitised when absolute, empty, traversing, or carrying a backslash or NUL,
because a name that should not occur is a reason to stop instead of to guess.

There is no subprocess here. The request is an ordinary HTTPS GET whose URL is matched
against a pattern pinning scheme, host and shape, so no argument can be mistaken for a
flag and no other origin is representable.

Invoked from ``.github/workflows/claude.yml``, which for the mention triggers runs from
the repository's default branch, so this file is not candidate-supplied.
"""

from __future__ import annotations

import base64
import json
import os
import pathlib
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

_API = "https://api.github.com"
_FILE_CAP = 300
_TIMEOUT_SECONDS = 30

# Validated on the raw string. PurePosixPath normalises "a//b" and "." away, so
# inspecting its parts would accept names that should never have been produced.
_REFUSED_COMPONENTS = frozenset({"", ".", ".."})
_SHA = re.compile(r"\A[0-9a-f]{40}\Z")
# Each side must begin with an alphanumeric. A leading dash is precisely the shape an
# earlier version of this check accepted, and the reason it is spelled out here.
_REPOSITORY = re.compile(r"\A[A-Za-z0-9][A-Za-z0-9._-]*/[A-Za-z0-9][A-Za-z0-9._-]*\Z")
# Pins scheme, host and shape together, so the request cannot be pointed at another
# origin whatever reaches this function.
_URL = re.compile(
    r"\Ahttps://api\.github\.com/repos/[A-Za-z0-9][A-Za-z0-9._-]*"
    r"/[A-Za-z0-9][A-Za-z0-9._-]*"
    r"/contents/[A-Za-z0-9._~!$&'()*+,;=:@%/-]+\?ref=[0-9a-f]{40}\Z"
)


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


def base_endpoint(repository: str, path: str, base_sha: str) -> str:
    """Build the contents URL for ``path`` at ``base_sha``.

    Constructed from values this script was given rather than taken from the
    comparison's own ``contents_url``, which is provider-supplied data.
    """
    if not _REPOSITORY.match(repository):
        raise ValueError(f"refusing a malformed repository: {repository!r}")
    if not _SHA.match(base_sha):
        raise ValueError(f"refusing a non-exact base revision: {base_sha!r}")
    encoded = urllib.parse.quote(str(safe_relative_path(path)), safe="/")
    return f"{_API}/repos/{repository}/contents/{encoded}?ref={base_sha}"


def _authorization() -> dict[str, str]:
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    return {"Authorization": f"Bearer {token}"} if token else {}


def _provider_json(url: str) -> dict[str, Any] | None:
    """Return the provider's JSON for ``url``, or None when it has none."""
    # Checked here, at the point of use, and before anything else. The value that
    # reaches the request is what matters, and trusting it because an earlier function
    # was careful is how the first version of this validation came to accept a leading
    # dash; validating before any environment lookup also keeps "is this input
    # acceptable" independent of "is the environment configured".
    if not _URL.match(url):
        raise ValueError(f"refusing an unexpected provider URL: {url!r}")
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            **_authorization(),
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=_TIMEOUT_SECONDS) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        if error.code == 404:
            # A file the candidate added has no base revision. That is expected, and
            # the diff already carries its content.
            return None
        raise


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
        name = str(entry["filename"])
        payload = _provider_json(base_endpoint(repository, name, base_sha))
        if payload is None or "content" not in payload:
            skipped += 1
            continue
        content = base64.b64decode(str(payload["content"]))
        if len(content) > remaining:
            skipped += 1
            continue
        destination = target / safe_relative_path(name)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)
        remaining -= len(content)
        written += 1
    (target / "README").write_text(
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
