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

import base64
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


# Git's own rule is not sufficient here. `git -c core.quotePath=false` prints U+0085,
# U+2028 and U+2029 raw, because Git orients on bytes -- but these artefacts are read by
# a Unicode-aware reader, and Python's ``str.splitlines`` treats all three as line
# breaks. A name carrying one would recreate exactly the forged-record problem that
# escaping the C0 controls closed.
_UNICODE_BREAKS = frozenset("\u0085\u2028\u2029")


def _must_escape(ch: str) -> bool:
    """Return whether ``ch`` could end a line for some reader of these artefacts."""
    code = ord(ch)
    return code < 0x20 or code == 0x7F or ch in _UNICODE_BREAKS


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
    if not any(_must_escape(ch) or ch in '"\\' for ch in name):
        return name
    out = ['"']
    for ch in name:
        code = ord(ch)
        if code in _C_ESCAPES:
            out.append(_C_ESCAPES[code])
        elif code < 0x20 or code == 0x7F:
            out.append(f"\\{code:03o}")
        elif _must_escape(ch):
            # Octal of the UTF-8 bytes, which is how `git -c core.quotePath=true`
            # renders a non-ASCII byte -- so the escape stays in Git's own vocabulary
            # even though Git itself does not escape these.
            out.extend(f"\\{byte:03o}" for byte in ch.encode())
        else:
            out.append(ch)
    out.append('"')
    return "".join(out)


def base_path_of(entry: dict[str, Any]) -> str:
    """Return the path the base revision holds this entry under."""
    if entry.get("status") in ("renamed", "copied"):
        # A copy carries previous_filename exactly as a rename does, and the source is
        # the one thing a copy is about: without it the fallback claims the destination
        # existed on the base side and no summary says where the content came from.
        previous = entry.get("previous_filename")
        if not previous:
            raise ValueError(f"a {entry['status']} entry carries no previous_filename")
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
            if entry.get("status") in ("renamed", "copied")
            and entry.get("previous_filename")
            else quote_path(str(entry["filename"]))
        )
        for entry in files
    ]
    if len(files) >= _FILE_CAP:
        # The provider caps this list and does not paginate it, so a list that reached
        # the cap must not be allowed to read as the whole change.
        #
        # What is established is that the list *reached* the maximum -- not that
        # anything was dropped. A change with exactly `_FILE_CAP` files is complete and
        # indistinguishable from a truncated one, because the payload carries no total.
        # Saying "is incomplete" turned that into a certainty and the prompt makes the
        # reviewer repeat it, so an exactly-at-cap change was reported as truncated: a
        # false limitation in the review's own output. The condition observed is
        # stated, not the conclusion it merely permits.
        lines.append(
            f"[the changed-file list reached the provider's maximum of {_FILE_CAP} "
            "and is not paginated, so this summary may be incomplete; nothing here "
            "says whether a further file exists]"
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
                "rename. The status below does NOT distinguish them: a binary content\n",
                "change and a mode-only change both arrive as 'modified' with no hunks.\n",
                "A real unified diff does, by its mode lines and its binary notice. If\n",
                "patches-source is present the diff was assembled per file and carries\n",
                "neither, so report such an entry as not examined rather than guessing.\n",
                "\n",
            ]
            + [
                f"{entry['status']} {str(entry['sha'])[:9]} "
                + (
                    f"{quote_path(str(entry['previous_filename']))} -> "
                    f"{quote_path(str(entry['filename']))}\n"
                    if entry.get("status") in ("renamed", "copied")
                    and entry.get("previous_filename")
                    else f"{quote_path(str(entry['filename']))}\n"
                )
                for entry in without_patch
            ]
        ),
        encoding="utf-8",
    )


def old_side(entry: dict[str, Any]) -> str:
    """Return the diff header's left side, or /dev/null when there was no left side.

    Unified diff names the nonexistent side `/dev/null`. Writing `--- a/<name>` for an
    added file tells a reviewer with no tree and no base that the file existed before
    the change, and on the assembled fallback that header is the only description of it
    the reviewer gets.
    """
    if entry.get("status") == "added":
        return "/dev/null"
    return quote_path("a/" + base_path_of(entry))


def new_side(entry: dict[str, Any]) -> str:
    """Return the diff header's right side, or /dev/null for a removal."""
    if entry.get("status") == "removed":
        return "/dev/null"
    return quote_path("b/" + str(entry["filename"]))


def write_assembled(context: pathlib.Path, comparison: dict[str, Any]) -> None:
    """Write the per-file hunks, so a refused unified diff still carries the change."""
    (context / "assembled.diff").write_text(
        "".join(
            f"--- {old_side(entry)}\n+++ {new_side(entry)}\n"
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


def write_commits(context: pathlib.Path) -> None:
    """Render commits.log from the base64-carried subjects the step collected.

    A commit subject is candidate-controlled text and this artefact is read line by
    line, so it is escaped exactly as a pathname is. The step cannot do it: splitting a
    message on "\\n" leaves a Unicode line separator intact, and the subject could then
    add a standalone fake commit, or a fake provider-cap notice, to a file the reviewer
    trusts.
    """
    source = context / "commits.b64"
    if not source.exists():
        return
    records = []
    for line in source.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        sha, _, encoded = line.partition(" ")
        try:
            raw = base64.b64decode(encoded, validate=True) if encoded else b""
        except ValueError:
            # `binascii.Error` *is* a `ValueError`, so naming both said there were two
            # branches here when there is one. This file names base classes rather
            # than members on purpose -- enumerating them missed a member four times
            # -- and listing a base class beside one of its own members is the same
            # mistake wearing the fix's clothes: it reads as coverage the base already
            # gave.
            # One unreadable subject is that commit's gap, not the step's. Saying so
            # keeps the record count honest, which is what the cap notice counts.
            records.append(f"{sha} [subject unavailable]\n")
            continue
        records.append(f"{sha} {quote_path(raw.decode('utf-8', 'replace'))}\n")
    (context / "commits.log").write_text("".join(records), encoding="utf-8")
    source.unlink()


def build(context: pathlib.Path) -> None:
    """Derive every file-level artefact from the retained comparison payload."""
    comparison = json.loads((context / "comparison.json").read_text(encoding="utf-8"))
    write_commits(context)
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
