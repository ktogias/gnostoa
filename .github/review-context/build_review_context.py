"""Build the bounded review context from one provider comparison payload.

Writes ``diff.stat``, ``no-patch.txt`` and ``assembled.diff``. Deriving them from a
single payload keeps the comparison to one request, keeps the workflow step free of an
external ``jq``, and puts the field semantics somewhere the suite can exercise directly
rather than by scraping YAML.

There is no network access here and no subprocess: the step fetches the comparison and
this turns it into files. Two properties are load-bearing, and each exists because
getting it wrong would hand the reviewer something *false* rather than something
missing:

* a **renamed** entry keeps its old path in every artefact, because bytes and hunks
  presented under a new name with no record of where they came from are unusable for
  precisely the swap and overwrite cases a rename raises;
* a **missing per-file patch** is a neutral fact, not a file type. It happens for a
  binary or oversized blob, and equally for a metadata-only change -- a mode bit, an
  empty file, a pure rename -- which is perfectly reviewable. Saying "binary" would make
  the reviewer report a real change as not examined.

Invoked from ``.github/workflows/claude.yml``, which for the mention triggers runs from
the repository's default branch, so this file is not candidate-supplied.
"""

from __future__ import annotations

import json
import pathlib
import sys
from typing import Any

from review_context_paths import within

_FILE_CAP = 300


_C_ESCAPES = {
    0x07: "\\a",
    0x08: "\\b",
    0x09: "\\t",
    0x0A: "\\n",
    0x0B: "\\v",
    0x0C: "\\f",
    0x0D: "\\r",
    0x22: '\\"',
    0x5C: "\\\\",
}


def quote_path(name: str) -> str:
    """Return ``name`` the way ``git -c core.quotePath=false`` would print it.

    Git permits a newline in a pathname and the comparison carries it through as JSON,
    but every artefact this script writes is read line by line. A name interpolated
    verbatim could therefore add a `+++ b/other.py` header, a diff line or an extra
    summary record, and a reviewer with no git and no candidate tree has nothing to
    check that against. Quoting is used rather than refusal because such a name is a
    legal path: dropping the file would hide a real change.

    Control characters, a double quote and a backslash are C-quoted; UTF-8 is left
    alone, exactly as Git does with `core.quotePath=false`. A legitimate international
    filename is not a line-injection risk, and quoting it would only make the artefacts
    harder to read.
    """
    if not any(ord(ch) < 0x20 or ord(ch) == 0x7F or ch in '"\\' for ch in name):
        return name
    out = ['"']
    for ch in name:
        code = ord(ch)
        if code in _C_ESCAPES:
            out.append(_C_ESCAPES[code])
        elif code < 0x20 or code == 0x7F:
            out.append(f"\\{code:03o}")
        else:
            out.append(ch)
    out.append('"')
    return "".join(out)


def base_path_of(entry: dict[str, Any]) -> str:
    """Return the path the base revision holds this entry under."""
    if entry.get("status") == "renamed":
        previous = entry.get("previous_filename")
        if not previous:
            raise ValueError("a renamed entry carries no previous_filename")
        return str(previous)
    return str(entry["filename"])


def write_summaries(context: pathlib.Path, comparison: dict[str, Any]) -> None:
    """Write diff.stat and no-patch.txt from the comparison payload."""
    files = comparison.get("files") or []
    # A rename's old path is part of what changed. Emitting only the new name leaves
    # the reviewer unable to say where the file came from, which matters most in the
    # swap and overwrite cases where another file already occupied the new path.
    lines = [
        f"{entry['status']} +{entry['additions']} -{entry['deletions']} "
        + (
            f"{quote_path(str(entry['previous_filename']))} -> "
            f"{quote_path(str(entry['filename']))}"
            if entry.get("status") == "renamed" and entry.get("previous_filename")
            else quote_path(str(entry["filename"]))
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
    without_patch = [entry for entry in files if entry.get("patch") is None]
    (context / "no-patch.txt").write_text(
        "".join(
            [
                "Changed files for which the comparison carried no hunks. This means\n",
                "either a binary or oversized blob, whose bytes are not in the diff, or\n",
                "a metadata-only change such as a mode bit, an empty file or a pure\n",
                "rename. The status below distinguishes them; the unified diff may\n",
                "still describe the change.\n",
                "\n",
            ]
            + [
                f"{entry['status']} {str(entry['sha'])[:9]} "
                + (
                    f"{quote_path(str(entry['previous_filename']))} -> "
                    f"{quote_path(str(entry['filename']))}\n"
                    if entry.get("status") == "renamed"
                    and entry.get("previous_filename")
                    else f"{quote_path(str(entry['filename']))}\n"
                )
                for entry in without_patch
            ]
        ),
        encoding="utf-8",
    )


def write_assembled(context: pathlib.Path, comparison: dict[str, Any]) -> None:
    """Write the per-file hunks, so a refused unified diff still carries the change."""
    (context / "assembled.diff").write_text(
        "".join(
            f"--- a/{quote_path(base_path_of(entry))}\n"
            f"+++ b/{quote_path(str(entry['filename']))}\n"
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


def build(context: pathlib.Path) -> None:
    """Derive every file-level artefact from the retained comparison payload."""
    comparison = json.loads((context / "comparison.json").read_text(encoding="utf-8"))
    write_summaries(context, comparison)
    write_assembled(context, comparison)


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(f"usage: {argv[0]} <context-dir>", file=sys.stderr)
        return 2
    build(within(argv[1], "GITHUB_WORKSPACE", must_exist=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
