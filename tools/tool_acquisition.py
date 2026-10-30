"""Acquire the diagnostic profile's pinned tool executables into the inventory's `TOOL_ROOT`, for the active tool
families only (#389 H-PYSEC-2, Decision 0122's remainder; owner 6508582845).

Both mandatory consumers run this one entry: the protected inventory job and the development image. With every tool
family inactive, it selects nothing and makes no request, so neither consumer depends on a release download while the
families are off. On the active path, for each tool the active families' producers run:
- the release asset is fetched from its pinned GitHub URL, following only GitHub's one redirect to its release-asset
  host, under a transfer bound and a deadline;
- the asset's bytes must equal its pin before any member is read;
- an archive yields exactly one regular, non-sparse member of the pinned name, under a decompression bound and a
  read bound;
- the executable's bytes must equal the profile's executable pin before they are installed, read-only, through an
  exclusive create that never follows or replaces anything already at the target, and are then read back through the
  pinned-bytes owner.

A refusal installs nothing for that tool and is named; the inventory then reports the family INCOMPLETE ("tool … is
unavailable"), never clean."""

from __future__ import annotations

import argparse
import hashlib
import http.client
import io
import lzma
import os
import platform
import sys
import tarfile
import urllib.parse
import urllib.request
import zlib
from collections.abc import Callable, Mapping
from pathlib import Path, PurePosixPath
from typing import Any

from tools import github_rest, quality_evidence, security_scan

SOURCE_HOST = "github.com"
# Where GitHub serves a release download after one redirect (measured for the pinned assets, #389 6530146486).
ASSET_HOST = "release-assets.githubusercontent.com"
# The largest pinned asset is Hadolint's aarch64 executable, 60,491,096 bytes.
MAX_ASSET_BYTES = 96 * 1024 * 1024
FETCH_SECONDS = 300.0
_XZ_MAGIC = b"\xfd7zXZ\x00"
_CREDENTIAL_HEADERS = ("Authorization", "Cookie", "Proxy-authorization")
_GZIP_MAGIC = b"\x1f\x8b"


class AcquisitionError(RuntimeError):
    """A tool that was not acquired, and why."""


class PinnedRedirect(urllib.request.HTTPRedirectHandler):
    """Follow a release download's one redirect, and only to GitHub's release-asset host over HTTPS."""

    max_redirections = 1

    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: Any,
        code: int,
        msg: str,
        headers: Any,
        newurl: str,
    ) -> urllib.request.Request | None:
        try:
            target = urllib.parse.urlparse(newurl)
            port = target.port
        except ValueError as exc:
            raise AcquisitionError("a redirect to a malformed URL") from exc
        if (target.scheme, target.hostname, port, target.username, target.password) != (
            "https",
            ASSET_HOST,
            None,
            None,
            None,
        ):
            raise AcquisitionError(
                f"a redirect outside https://{ASSET_HOST}: {target.scheme}://{target.hostname}"
            )
        if urllib.parse.urlparse(req.full_url).hostname != SOURCE_HOST:
            raise AcquisitionError("a second redirect")
        redirected = super().redirect_request(req, fp, code, msg, headers, newurl)
        # No credential crosses to the asset host: acquisition sends none, and none is carried if one were set.
        if redirected is not None:
            for header in _CREDENTIAL_HEADERS:
                redirected.remove_header(header)
        return redirected


def fetch(
    url: str,
    *,
    opener: Any = None,
    max_bytes: int = MAX_ASSET_BYTES,
    limit: float = FETCH_SECONDS,
) -> bytes:
    """A pinned release asset's bytes, read through the bounded exchange (transfer bound, deadline) of `github_rest`."""
    try:
        source = urllib.parse.urlparse(url)
        port = source.port
    except ValueError as exc:
        raise AcquisitionError(f"{url!r} is not a GitHub release URL") from exc
    if (source.scheme, source.hostname, port, source.username, source.password) != (
        "https",
        SOURCE_HOST,
        None,
        None,
        None,
    ):
        raise AcquisitionError(f"{url!r} is not a GitHub release URL")
    if opener is None:
        opener = urllib.request.build_opener(PinnedRedirect())
    policy = github_rest.Policy(max_response_bytes=max_bytes)
    try:
        raw, _ = github_rest.exchange(
            opener, urllib.request.Request(url), limit, policy
        )
    # Every transport failure below the client's own is a named refusal too (Cubic on #471).
    except (
        github_rest.GitHubError,
        OSError,
        http.client.HTTPException,
        ValueError,
    ) as exc:
        raise AcquisitionError(f"{url}: {exc}") from exc
    return raw


def _checked_member_name(name: str) -> str:
    parts = PurePosixPath(name).parts
    if (
        name.startswith("/")
        or "//" in name
        or not parts
        or any(part in (".", "..") for part in parts)
    ):
        raise AcquisitionError(
            f"member name {name!r} is not a plain path inside the archive"
        )
    return name


def member_bytes(raw: bytes, name: str, max_bytes: int) -> bytes:
    """The bytes of the one regular member `name` of an xz or gzip tar archive, decompressed under `max_bytes`."""
    _checked_member_name(name)
    decompressor: Any
    if raw.startswith(_XZ_MAGIC):
        decompressor = lzma.LZMADecompressor(format=lzma.FORMAT_XZ)
    elif raw.startswith(_GZIP_MAGIC):
        decompressor = zlib.decompressobj(wbits=31)
    else:
        raise AcquisitionError("the asset is not an xz or gzip archive")
    try:
        data = decompressor.decompress(raw, max_bytes + 1)
    except (lzma.LZMAError, zlib.error) as exc:
        raise AcquisitionError(f"the archive does not decompress: {exc}") from exc
    if len(data) > max_bytes:
        raise AcquisitionError(f"the archive decompresses past {max_bytes} bytes")
    if not decompressor.eof:
        raise AcquisitionError("the archive is truncated")
    try:
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:") as archive:
            members = [member for member in archive.getmembers() if member.name == name]
            # A sparse member is "regular" to tarfile, and reading it expands its holes past what was decompressed
            # (Cubic on #471): it is refused, and the read is bounded whatever the member claims.
            if len(members) != 1 or not members[0].isreg() or members[0].issparse():
                raise AcquisitionError(
                    f"member {name} is not exactly one regular, non-sparse file in the archive"
                )
            stream = archive.extractfile(members[0])
            if stream is None:
                raise AcquisitionError(f"member {name} cannot be read")
            member = stream.read(max_bytes + 1)
    except tarfile.TarError as exc:
        raise AcquisitionError(f"the archive is not a readable tar: {exc}") from exc
    if len(member) > max_bytes:
        raise AcquisitionError(f"member {name} is past {max_bytes} bytes")
    return member


def _install(root: Path, name: str, data: bytes, digest: str) -> None:
    """Install `data` as `root/name`, read-only: the root opened as a directory without following a link, the file
    created inside that handle exclusively and without following one, so nothing already there is followed or
    replaced; then read back through the pinned-bytes owner, and removed on any mismatch."""
    target = root / name
    try:
        root_fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    except OSError as exc:
        raise AcquisitionError(
            f"{root} is not a directory to install into: {exc}"
        ) from exc
    try:
        descriptor = os.open(
            name,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
            0o555,
            dir_fd=root_fd,
        )
    except FileExistsError as exc:
        raise AcquisitionError(f"{target} already exists") from exc
    except OSError as exc:
        raise AcquisitionError(f"{target} cannot be created: {exc}") from exc
    finally:
        os.close(root_fd)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
        security_scan.verified_pinned_bytes(
            root, name, digest, quality_evidence.MAX_TOOL_BYTES, label=f"tool {name}"
        )
    except (OSError, security_scan.SecurityScanError) as exc:
        target.unlink(missing_ok=True)
        raise AcquisitionError(f"{target} did not install as pinned: {exc}") from exc


def _plan(
    profile: Mapping[str, Any], names: list[str], machine: str
) -> list[tuple[str, str, Mapping[str, Any]]]:
    """Each tool's executable and asset pins for this machine. A pin missing for any tool refuses the whole
    acquisition before any fetch: it is the protected profile's defect, not one tool's runtime failure."""
    plan: list[tuple[str, str, Mapping[str, Any]]] = []
    for name in names:
        pin = profile["tools"].get(name, {})
        digest = pin.get("sha256", {}).get(machine)
        asset = pin.get("asset", {}).get(machine)
        if digest is None or asset is None:
            raise AcquisitionError(f"tool {name}: no pin for machine {machine}")
        plan.append((name, digest, asset))
    return plan


def _acquire_one(
    root: Path,
    name: str,
    digest: str,
    asset: Mapping[str, Any],
    fetcher: Callable[[str], bytes],
) -> None:
    raw = fetcher(asset["url"])
    if hashlib.sha256(raw).hexdigest() != asset["sha256"]:
        raise AcquisitionError("the asset's bytes are not its pin")
    executable = (
        member_bytes(raw, asset["member"], quality_evidence.MAX_TOOL_BYTES)
        if "member" in asset
        else raw
    )
    if hashlib.sha256(executable).hexdigest() != digest:
        raise AcquisitionError("the executable's bytes are not its pin")
    _install(root, name, executable, digest)


def acquire(
    profile: Mapping[str, Any],
    root: Path,
    *,
    machine: str | None = None,
    fetcher: Callable[[str], bytes] = fetch,
) -> list[str]:
    """Install the active families' pinned tools under `root` and return their names; nothing, and no request, while
    every tool family is inactive. Every pin is checked for this machine before any fetch; after that, one tool's
    refusal does not stop the others, and every refusal is named."""
    names = quality_evidence.tool_names(profile)
    if not names:
        return []
    installed: list[str] = []
    refused: list[str] = []
    for name, digest, asset in _plan(profile, names, machine or platform.machine()):
        try:
            _acquire_one(root, name, digest, asset, fetcher)
            installed.append(name)
        except AcquisitionError as exc:
            refused.append(f"tool {name}: {exc}")
    if refused:
        raise AcquisitionError(
            "; ".join(refused)
            + (f" (installed: {', '.join(installed)})" if installed else "")
        )
    return installed


def main(argv: list[str] | None = None) -> int:
    """Acquire into the collector's own `TOOL_ROOT` from the protected profile: no path is taken from the command
    line (SonarCloud S8707 on #471), and a profile that cannot be used is refused like any other acquisition."""
    argparse.ArgumentParser(
        description="Acquire the active tool families' pinned executables into the inventory's TOOL_ROOT."
    ).parse_args(argv)
    try:
        profile = quality_evidence.load_diagnostic_profile()
        installed = acquire(profile, Path(quality_evidence.TOOL_ROOT))
    except (AcquisitionError, quality_evidence.QualityEvidenceError) as exc:
        print(f"tool acquisition refused: {exc}", file=sys.stderr)
        return 1
    print(
        "tool acquisition: "
        + (
            ", ".join(installed)
            if installed
            else "nothing to acquire, no tool family is active"
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
