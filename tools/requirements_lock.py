"""Parse and refresh Gnostoa's exact wheel-only Python requirement locks."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, TypedDict
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

HASH_PATTERN = re.compile(r"[0-9a-f]{64}")
NAME_PATTERN = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
REQUIRED_GLOBAL_OPTIONS = frozenset({"--only-binary :all:", "--require-hashes"})


class LockFormatError(RuntimeError):
    """The requirements lock is outside the supported fail-closed format."""


class LockedRequirement(TypedDict):
    """One exact distribution and its admitted wheel identities."""

    name: str
    normalized_name: str
    version: str
    artifact_hashes: list[str]


def normalized_distribution_name(name: str) -> str:
    """Return the normalized Python distribution identity used by the locks."""

    return re.sub(r"[-_.]+", "-", name).lower()


def _logical_lines(path: Path) -> list[tuple[int, str]]:
    try:
        physical_lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise LockFormatError(
            f"cannot read requirements lock {path.name}: {exc}"
        ) from exc

    logical_lines: list[tuple[int, str]] = []
    fragments: list[str] = []
    start_line = 0
    for line_number, physical_line in enumerate(physical_lines, start=1):
        candidate = physical_line.strip()
        if not candidate or candidate.startswith("#"):
            if fragments:
                raise LockFormatError(
                    f"{path.name}:{line_number} interrupts a continued requirement"
                )
            continue
        if not fragments:
            start_line = line_number
        continued = candidate.endswith("\\")
        fragment = candidate[:-1].strip() if continued else candidate
        if not fragment:
            raise LockFormatError(
                f"{path.name}:{line_number} has an empty continuation"
            )
        fragments.append(fragment)
        if not continued:
            logical_lines.append((start_line, " ".join(fragments)))
            fragments = []
    if fragments:
        raise LockFormatError(
            f"{path.name}:{start_line} has an unterminated continuation"
        )
    return logical_lines


def _parse_requirements(
    path: Path,
    *,
    require_artifact_hashes: bool,
) -> list[LockedRequirement]:
    requirements: list[LockedRequirement] = []
    options: set[str] = set()
    seen: set[str] = set()

    for line_number, logical_line in _logical_lines(path):
        if logical_line.startswith("--"):
            if logical_line not in REQUIRED_GLOBAL_OPTIONS:
                raise LockFormatError(
                    f"{path.name}:{line_number} has unsupported global option "
                    f"{logical_line!r}"
                )
            if logical_line in options:
                raise LockFormatError(
                    f"{path.name}:{line_number} duplicates {logical_line}"
                )
            options.add(logical_line)
            continue

        tokens = logical_line.split()
        pin = tokens[0]
        if pin.count("==") != 1:
            raise LockFormatError(
                f"{path.name}:{line_number} must use exact name==version syntax"
            )
        name, version = pin.split("==", maxsplit=1)
        if not name or not version:
            raise LockFormatError(
                f"{path.name}:{line_number} must use exact name==version syntax"
            )
        normalized_name = normalized_distribution_name(name)
        if NAME_PATTERN.fullmatch(normalized_name) is None:
            raise LockFormatError(
                f"{path.name}:{line_number} has an invalid distribution name"
            )
        if normalized_name in seen:
            raise LockFormatError(
                f"{path.name}:{line_number} duplicates {normalized_name}"
            )
        seen.add(normalized_name)

        hashes: list[str] = []
        for token in tokens[1:]:
            prefix = "--hash=sha256:"
            if not token.startswith(prefix):
                raise LockFormatError(
                    f"{path.name}:{line_number} permits only SHA-256 artifact hashes"
                )
            digest = token.removeprefix(prefix)
            if HASH_PATTERN.fullmatch(digest) is None:
                raise LockFormatError(
                    f"{path.name}:{line_number} has a malformed SHA-256 artifact hash"
                )
            hashes.append(digest)
        if hashes != sorted(set(hashes)):
            raise LockFormatError(
                f"{path.name}:{line_number} artifact hashes must be unique and sorted"
            )
        requirements.append(
            {
                "name": name,
                "normalized_name": normalized_name,
                "version": version,
                "artifact_hashes": hashes,
            }
        )

    if not requirements:
        raise LockFormatError(f"requirements lock {path.name} has no requirements")
    if require_artifact_hashes:
        missing_options = sorted(REQUIRED_GLOBAL_OPTIONS - options)
        if missing_options:
            raise LockFormatError(
                f"{path.name} must declare " + " and ".join(missing_options)
            )
        missing_hashes = [
            requirement["normalized_name"]
            for requirement in requirements
            if not requirement["artifact_hashes"]
        ]
        if missing_hashes:
            raise LockFormatError(
                f"{path.name} has requirements without SHA-256 hashes: "
                + ", ".join(missing_hashes)
            )
    return requirements


def locked_requirements(path: Path) -> list[LockedRequirement]:
    """Parse the repository's exact, wheel-only, fully hashed lock format."""

    return _parse_requirements(path, require_artifact_hashes=True)


def version_pins(path: Path) -> list[tuple[str, str]]:
    """Read exact pins from either the pre-hash bootstrap or current lock format."""

    return [
        (requirement["name"], requirement["version"])
        for requirement in _parse_requirements(path, require_artifact_hashes=False)
    ]


def _header_lines(path: Path) -> list[str]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise LockFormatError(
            f"cannot read requirements lock {path.name}: {exc}"
        ) from exc
    header: list[str] = []
    for line in lines:
        if line.startswith("#"):
            header.append(line)
            continue
        if not line.strip() and header:
            continue
        break
    return header


def render_hashed_requirements(
    requirements: Sequence[tuple[str, str]],
    artifact_hashes: Mapping[str, Sequence[str]],
    *,
    header: Sequence[str] = (),
) -> str:
    """Render deterministic pip hash-checking input from reviewed exact pins."""

    lines = [*header, "--only-binary :all:", "--require-hashes", ""]
    seen: set[str] = set()
    for name, version in requirements:
        normalized_name = normalized_distribution_name(name)
        if normalized_name in seen:
            raise LockFormatError(f"requirements duplicate {normalized_name}")
        seen.add(normalized_name)
        hashes = sorted(set(artifact_hashes.get(normalized_name, ())))
        if not hashes:
            raise LockFormatError(
                f"no non-yanked wheel hashes found for {name}=={version}"
            )
        if any(HASH_PATTERN.fullmatch(digest) is None for digest in hashes):
            raise LockFormatError(f"malformed SHA-256 wheel hash for {name}=={version}")
        lines.append(f"{name}=={version} \\")
        for index, digest in enumerate(hashes):
            continuation = " \\" if index < len(hashes) - 1 else ""
            lines.append(f"    --hash=sha256:{digest}{continuation}")
    return "\n".join(lines) + "\n"


def wheel_hashes_from_pypi_release(
    document: Mapping[str, Any],
    package_name: str,
    version: str,
) -> list[str]:
    """Select reviewed wheel identities without admitting sdists or yanked files."""

    urls = document.get("urls")
    if not isinstance(urls, list):
        raise LockFormatError(
            f"PyPI response for {package_name}=={version} has no URLs"
        )
    hashes: set[str] = set()
    for item in urls:
        if not isinstance(item, dict):
            raise LockFormatError(
                f"PyPI response for {package_name}=={version} has a malformed file"
            )
        if item.get("packagetype") != "bdist_wheel" or item.get("yanked") not in (
            False,
            None,
            "",
        ):
            continue
        filename = item.get("filename")
        digests = item.get("digests")
        digest = digests.get("sha256") if isinstance(digests, dict) else None
        if (
            not isinstance(filename, str)
            or not filename.endswith(".whl")
            or not isinstance(digest, str)
            or HASH_PATTERN.fullmatch(digest) is None
        ):
            raise LockFormatError(
                f"PyPI wheel for {package_name}=={version} lacks a valid SHA-256"
            )
        hashes.add(digest)
    if not hashes:
        raise LockFormatError(
            f"PyPI has no non-yanked wheels for {package_name}=={version}"
        )
    return sorted(hashes)


def _pypi_release(
    index_base: str,
    name: str,
    version: str,
) -> Mapping[str, Any]:
    url = f"{index_base.rstrip('/')}/{quote(name, safe='')}/{quote(version, safe='')}/json"
    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "gnostoa-requirements-lock/0.1",
        },
    )
    try:
        with urlopen(request, timeout=30) as response:
            document = json.load(response)
    except (HTTPError, URLError, OSError, json.JSONDecodeError) as exc:
        raise LockFormatError(
            f"cannot read release metadata for {name}=={version}: {exc}"
        ) from exc
    if not isinstance(document, dict):
        raise LockFormatError(
            f"release metadata for {name}=={version} is not an object"
        )
    return document


def refresh_lock(path: Path, *, index_base: str) -> str:
    """Fetch current PyPI wheel digests and render a reviewable lock candidate."""

    requirements = version_pins(path)
    hashes: dict[str, list[str]] = {}
    for name, version in requirements:
        normalized_name = normalized_distribution_name(name)
        hashes[normalized_name] = wheel_hashes_from_pypi_release(
            _pypi_release(index_base, name, version),
            name,
            version,
        )
    return render_hashed_requirements(
        requirements,
        hashes,
        header=_header_lines(path),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Refresh one exact requirements lock with non-yanked PyPI wheel hashes",
    )
    parser.add_argument("--lock", type=Path, required=True)
    parser.add_argument("--index-base", default="https://pypi.org/pypi")
    parser.add_argument(
        "--write",
        action="store_true",
        help="replace the lock after complete successful reconstruction",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if not str(args.index_base).startswith("https://"):
        print("ERROR: index base must use HTTPS", file=sys.stderr)
        return 2
    try:
        rendered = refresh_lock(args.lock, index_base=args.index_base)
        locked_requirements_path = args.lock.resolve()
        if args.write:
            locked_requirements_path.write_text(rendered, encoding="utf-8")
            print(f"wrote {locked_requirements_path}")
        else:
            sys.stdout.write(rendered)
    except (LockFormatError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
