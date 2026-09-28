"""Build the bounded review context from one provider comparison payload.

Writes ``diff.stat``, ``no-patch.txt``, ``base.manifest`` and ``base/``. Deriving
them from a single payload keeps the comparison to one request, keeps the workflow step
free of an external ``jq``, and puts the field semantics somewhere the suite can
exercise directly rather than by scraping YAML.

``base/`` matters most. The bounded reviewer of Decision 0094 reads the repository's
default branch for its entry route and general context, and that tree is deliberately
**not** this Pull Request's base: the branch may have advanced, or the Pull Request may
target another branch. Unchanged code read from it can therefore come from a revision
the candidate never saw, which produces interaction findings that are not real. So the
exact pre-change revision of every changed file is written here.

Four properties of that collection are load-bearing, and each exists because getting it
wrong would hand the reviewer something false rather than something missing:

* the revision fetched is the **merge base**, not the base branch tip, because a
  three-dot comparison is computed from the merge base and mixing the two would describe
  two different pre-change states;
* a **renamed** entry is fetched under ``previous_filename``, since that is where the
  base holds it, and fetching the new path could return an unrelated file that a swap or
  overwrite rename happens to have replaced;
* a response that is not an ordinary base64 ``file`` -- a symlink the API resolved to its
  target, or a large file returned with ``encoding: "none"`` -- is recorded as
  unavailable rather than written, because resolved or empty bytes presented as the
  exact base are worse than an acknowledged gap;
* every path not written is named in ``base.manifest`` with the reason, so the reviewer
  can see which file it cannot rely on instead of inferring it from a count.

Bytes are written, never a checkout: no mode, symlink or directory entry from either
side reaches the runner, which is what keeps rule 21 intact. Provider-supplied names are
refused rather than sanitised when absolute, empty, traversing, or carrying a backslash
or NUL, because a name that should not occur is a reason to stop instead of to guess.
The manifest lives outside ``base/`` so it cannot collide with a repository path.

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
# The contents API returns at most this many entries for a directory and does not
# paginate it. A changed file in a larger directory is simply missing from the listing,
# which must not be reported as "the base did not hold this".
_LISTING_CAP = 1000
_TIMEOUT_SECONDS = 30
_MANIFEST = "base.manifest"

# Validated on the raw string. PurePosixPath normalises "a//b" and "." away, so
# inspecting its parts would accept names that should never have been produced.
_REFUSED_COMPONENTS = frozenset({"", ".", ".."})
_SHA = re.compile(r"\A[0-9a-f]{40}\Z")
# Each side must begin with an alphanumeric. A leading dash is precisely the shape an
# earlier version of this check accepted, and the reason it is spelled out here.
_REPOSITORY = re.compile(r"\A[A-Za-z0-9][A-Za-z0-9._-]*/[A-Za-z0-9][A-Za-z0-9._-]*\Z")
# Pins scheme, host and shape together, so the request cannot be pointed at another
# origin whatever reaches the fetch.
_URL = re.compile(
    r"\Ahttps://api\.github\.com/repos/[A-Za-z0-9][A-Za-z0-9._-]*"
    r"/[A-Za-z0-9][A-Za-z0-9._-]*"
    r"/contents/[A-Za-z0-9._~!$&'()*+,;=:@%/-]*\?ref=[0-9a-f]{40}\Z"
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
    """Build the contents URL for ``path`` at ``base_sha``."""
    if not _REPOSITORY.match(repository):
        raise ValueError(f"refusing a malformed repository: {repository!r}")
    if not _SHA.match(base_sha):
        raise ValueError(f"refusing a non-exact base revision: {base_sha!r}")
    encoded = urllib.parse.quote(str(safe_relative_path(path)), safe="/")
    return f"{_API}/repos/{repository}/contents/{encoded}?ref={base_sha}"


def listing_endpoint(repository: str, directory: str, base_sha: str) -> str:
    """Build the contents URL for a directory listing at ``base_sha``."""
    if not _REPOSITORY.match(repository):
        raise ValueError(f"refusing a malformed repository: {repository!r}")
    if not _SHA.match(base_sha):
        raise ValueError(f"refusing a non-exact base revision: {base_sha!r}")
    encoded = (
        urllib.parse.quote(str(safe_relative_path(directory)), safe="/")
        if directory
        else ""
    )
    return f"{_API}/repos/{repository}/contents/{encoded}?ref={base_sha}"


def listing_entry(listing: Any, name: str) -> dict[str, Any] | None:
    """Return the ``listing`` record for ``name``, or None when it is not there."""
    if not isinstance(listing, list):
        return None
    for item in listing:
        if isinstance(item, dict) and str(item.get("name")) == name:
            return item
    return None


def entry_type(listing: Any, name: str) -> str | None:
    """Return the declared type of ``name`` within a directory ``listing``."""
    item = listing_entry(listing, name)
    return str(item.get("type")) if item else None


def base_path_of(entry: dict[str, Any]) -> str:
    """Return the path the base revision holds this entry under."""
    if entry.get("status") == "renamed":
        previous = entry.get("previous_filename")
        if not previous:
            raise ValueError("a renamed entry carries no previous_filename")
        return str(previous)
    return str(entry["filename"])


def _authorization() -> dict[str, str]:
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    return {"Authorization": f"Bearer {token}"} if token else {}


def _provider_json(url: str) -> Any:
    """Return the provider's JSON for ``url``, or None when it reports 404.

    Every other failure propagates. A rate limit, an authentication failure or a server
    error must not be indistinguishable from "the candidate added this file": that would
    let the review continue while the manifest attributed a missing file to the wrong
    cause.
    """
    # Checked here, at the point of use, and before any environment lookup. The value
    # that reaches the request is what matters, and trusting it because an earlier
    # function was careful is how the first version of this validation came to accept a
    # leading dash.
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
            return None
        raise


def decoded_file(payload: dict[str, Any]) -> bytes | None:
    """Return the payload's bytes, or None when the response is not usable.

    The response *shape* cannot identify a symlink: the contents API answers a symlink
    to a regular file with the target's content under an ordinary ``type: file``. The
    authoritative check is the parent directory's listing, which declares
    ``type: symlink``; this function only rejects what the response itself rules out.
    """
    if payload.get("type") != "file":
        return None
    if payload.get("encoding") != "base64":
        # Files above roughly 1 MB come back with `encoding: "none"` and empty content.
        return None
    content = payload.get("content")
    if not isinstance(content, str):
        return None
    return base64.b64decode(content)


def write_summaries(context: pathlib.Path, comparison: dict[str, Any]) -> None:
    """Write diff.stat and no-patch.txt from the comparison payload."""
    files = comparison.get("files") or []
    # A rename's old path is part of what changed. Emitting only the new name leaves
    # the reviewer unable to say where the file came from, which matters most in the
    # swap and overwrite cases where another file already occupied the new path.
    lines = [
        f"{entry['status']} +{entry['additions']} -{entry['deletions']} "
        + (
            f"{entry['previous_filename']} -> {entry['filename']}"
            if entry.get("status") == "renamed" and entry.get("previous_filename")
            else str(entry["filename"])
        )
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
    # A missing per-file patch is a neutral fact, not a file type. It happens for a
    # binary or oversized blob, and equally for a metadata-only change -- a mode bit, an
    # empty file, a rename with no textual edit -- which is perfectly reviewable. Saying
    # "binary or oversized" here made the reviewer report a real change as not examined.
    without_patch = [entry for entry in files if entry.get("patch") is None]
    (context / "no-patch.txt").write_text(
        "".join(
            [
                "Changed files for which the comparison carried no hunks. This means\n",
                "either a binary or oversized blob, whose bytes are in neither the diff\n",
                "nor the checkout, or a metadata-only change such as a mode bit, an\n",
                "empty file or a pure rename. The status below distinguishes them; the\n",
                "unified diff may still describe the change.\n",
                "\n",
            ]
            + [
                f"{entry['status']} {str(entry['sha'])[:9]} "
                + (
                    f"{entry['previous_filename']} -> {entry['filename']}\n"
                    if entry.get("status") == "renamed"
                    and entry.get("previous_filename")
                    else f"{entry['filename']}\n"
                )
                for entry in without_patch
            ]
        ),
        encoding="utf-8",
    )


def collect(
    context: pathlib.Path, repository: str, budget: int
) -> tuple[int, list[str]]:
    """Write pre-change revisions under ``base/``.

    Returns the number of files written and one manifest line per file that is not.
    """
    comparison = json.loads((context / "comparison.json").read_text(encoding="utf-8"))
    write_summaries(context, comparison)
    # A three-dot comparison is computed from the merge base, so the pre-change content
    # must come from there too. The base branch tip would be a different revision
    # whenever the target branch has advanced since the candidate diverged.
    merge_base = str((comparison.get("merge_base_commit") or {}).get("sha") or "")
    # Per-file patches, so a provider that refuses the whole diff still leaves the
    # changed content reachable. Without this, a refusal produced a context with paths
    # and pre-change bytes but nothing about what the candidate actually changed.
    (context / "assembled.diff").write_text(
        "".join(
            f"--- a/{base_path_of(entry)}\n+++ b/{entry['filename']}\n"
            + (
                f"{entry['patch']}\n"
                if entry.get("patch") is not None
                # A metadata-only change has no hunks, and dropping it here would have
                # removed a reviewable change from the fallback entirely.
                else f"[no hunks: {entry['status']}; see no-patch.txt]\n"
            )
            for entry in comparison.get("files") or []
        ),
        encoding="utf-8",
    )
    listings: dict[str, Any] = {}
    target = context / "base"
    target.mkdir(exist_ok=True)
    written = 0
    unavailable: list[str] = []
    classified: list[str] = []
    remaining = budget
    # Files with hunks are fetched first so that a large binary cannot consume the
    # budget ahead of a textual change. Entries without hunks are not skipped: a mode
    # change or a pure rename of a text file has pre-change bytes, and those bytes are
    # exactly what the reviewer is told to read from base/. Skipping them left the
    # reviewer with no content and no gap recorded for a change it was told to review.
    ordered = sorted(
        comparison.get("files") or [], key=lambda item: item.get("patch") is None
    )
    for entry in ordered:
        name = str(entry["filename"])
        if entry.get("status") == "added":
            unavailable.append(f"added-by-candidate {name}")
            continue
        source = base_path_of(entry)
        # The parent listing declares the entry's real type. Asking the contents API
        # alone cannot: it answers a symlink to a regular file with the target's bytes
        # under an ordinary `type: file`, so accepting that response would write
        # unrelated content and call it the exact pre-change state.
        directory = str(pathlib.PurePosixPath(source).parent)
        directory = "" if directory == "." else directory
        if directory not in listings:
            listings[directory] = _provider_json(
                listing_endpoint(repository, directory, merge_base)
            )
        listing = listings[directory]
        record = listing_entry(listing, pathlib.PurePosixPath(source).name)
        declared = str(record.get("type")) if record else None
        if declared is None:
            if isinstance(listing, list) and len(listing) >= _LISTING_CAP:
                # The name may be present in the part the provider did not return.
                # Saying "absent" here would be the false base-state claim this
                # collection exists to avoid.
                unavailable.append(f"listing-truncated {source}")
            else:
                unavailable.append(f"absent-at-merge-base {source}")
            continue
        if declared != "file":
            unavailable.append(f"not-a-plain-file {source}")
            continue
        payload = _provider_json(base_endpoint(repository, source, merge_base))
        if payload is None:
            unavailable.append(f"absent-at-merge-base {source}")
            continue
        content = decoded_file(payload)
        if content is None:
            unavailable.append(f"not-a-plain-file {source}")
            continue
        if len(content) > remaining:
            unavailable.append(f"over-budget {source}")
            continue
        destination = target / safe_relative_path(name)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)
        remaining -= len(content)
        written += 1
        if entry.get("patch") is None:
            # `status` cannot tell a mode-only change from a binary content change:
            # both arrive as "modified" with no hunks. The blob identity can. Claiming
            # the status distinguishes them would leave the reviewer able to call a
            # binary change examined without ever seeing what changed.
            base_blob = str(record.get("sha") or "") if record else ""
            head_blob = str(entry.get("sha") or "")
            classified.append(
                f"metadata-only {name}"
                if base_blob and base_blob == head_blob
                else f"content-changed-without-hunks {name}"
            )
    renames = [
        f"renamed {entry['previous_filename']} -> {entry['filename']}"
        for entry in comparison.get("files") or []
        if entry.get("status") == "renamed" and entry.get("previous_filename")
    ]
    lines = [
        "Exact pre-change bytes of each changed file, taken at the merge base",
        f"({merge_base or 'unknown'}). A renamed file is fetched under its previous",
        "path and written under its new one, so the mapping is listed here: the",
        "bytes under a new name came from the old one.",
        f"Written: {written}. Unavailable: {len(unavailable)}. Renamed: {len(renames)}.",
        "",
        "A change the comparison gave no hunks for is classified below by blob",
        "identity, because its status cannot distinguish the cases: identical blobs",
        "mean a metadata-only change, which is reviewable from base/ plus diff.stat,",
        "while differing blobs mean content changed that no artefact here can show.",
        "",
        *classified,
        *renames,
        *unavailable,
    ]
    (context / _MANIFEST).write_text(
        "".join(f"{line}\n" for line in lines), encoding="utf-8"
    )
    return written, unavailable


def main(argv: list[str]) -> int:
    if len(argv) != 4:
        print(
            f"usage: {argv[0]} <context-dir> <repository> <budget-bytes>",
            file=sys.stderr,
        )
        return 2
    collect(pathlib.Path(argv[1]), argv[2], int(argv[3]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
