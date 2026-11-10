"""Read the members of a compressed tar archive within bounds (Decision 0134, item 4).

One reader for its two users. The pinned tool acquisition (Decision 0122) takes one named member of an xz or gzip
tar; merge evidence takes every member of an Owner-declared gzip tar (Decision 0134). Both are refused, with an
`ArchiveError` that names why, when:
- the archive is not one compressed stream of an accepted format, does not decompress, decompresses past its bound,
  is truncated, or has any data after the stream;
- a member read has a name that is not a plain relative path, or is not a regular, non-sparse file;
- read whole, the tar has anything but zero bytes after the end of its members.

Only the standard library is imported: merge evidence is a supported entrypoint, and its whole import closure is
bound into the candidate's source digest (SB2)."""

from __future__ import annotations

import io
import lzma
import tarfile
import zlib
from typing import Any

_XZ_MAGIC = b"\xfd7zXZ\x00"
_GZIP_MAGIC = b"\x1f\x8b"
# zlib's window bits for a gzip header and trailer.
_GZIP_WBITS = 31


class ArchiveError(ValueError):
    """An archive, or one of its members, that was refused, and why."""


def checked_member_name(name: str) -> str:
    """`name` when it is a plain relative path: no empty, `.` or `..` segment, so no leading `/` either."""

    if any(segment in ("", ".", "..") for segment in name.split("/")):
        raise ArchiveError(
            f"member name {name!r} is not a plain path inside the archive"
        )
    return name


def _decompressed(raw: bytes, decompressor: Any, max_bytes: int) -> bytes:
    """The one stream `raw` holds, decompressed under `max_bytes`, with nothing after it."""

    try:
        data: bytes = decompressor.decompress(raw, max_bytes + 1)
    except (lzma.LZMAError, zlib.error) as exc:
        raise ArchiveError(f"the archive does not decompress: {exc}") from exc
    if len(data) > max_bytes:
        raise ArchiveError(f"the archive decompresses past {max_bytes} bytes")
    if not decompressor.eof:
        raise ArchiveError("the archive is truncated")
    if decompressor.unused_data:
        raise ArchiveError("the archive has data after its compressed stream")
    return data


def _regular(info: tarfile.TarInfo) -> bool:
    # A sparse member is "regular" to tarfile, and reading it expands its holes past what was decompressed (Cubic on
    # #471): it is refused.
    return info.isreg() and not info.issparse()


def _read(archive: tarfile.TarFile, info: tarfile.TarInfo, max_bytes: int) -> bytes:
    """A regular member's bytes, read under `max_bytes` whatever the member claims."""

    stream = archive.extractfile(info)
    if stream is None:
        raise ArchiveError(f"member {info.name} cannot be read")
    data = stream.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise ArchiveError(f"member {info.name} is past {max_bytes} bytes")
    return data


def member_bytes(raw: bytes, name: str, max_bytes: int) -> bytes:
    """The bytes of the one regular member `name` of an xz or gzip tar archive, decompressed under `max_bytes`."""

    checked_member_name(name)
    decompressor: Any
    if raw.startswith(_XZ_MAGIC):
        decompressor = lzma.LZMADecompressor(format=lzma.FORMAT_XZ)
    elif raw.startswith(_GZIP_MAGIC):
        decompressor = zlib.decompressobj(wbits=_GZIP_WBITS)
    else:
        raise ArchiveError("the asset is not an xz or gzip archive")
    data = _decompressed(raw, decompressor, max_bytes)
    try:
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:") as archive:
            members = [member for member in archive.getmembers() if member.name == name]
            if len(members) != 1 or not _regular(members[0]):
                raise ArchiveError(
                    f"member {name} is not exactly one regular, non-sparse file in the archive"
                )
            return _read(archive, members[0], max_bytes)
    except tarfile.TarError as exc:
        raise ArchiveError(f"the archive is not a readable tar: {exc}") from exc


def gzip_tar_members(
    raw: bytes, *, max_bytes: int, max_members: int
) -> list[tuple[str, bytes]]:
    """Every member of a gzip tar archive, in its order, with its bytes. The archive is one gzip stream, decompressed
    under `max_bytes`, with nothing after it; it has at most `max_members` members, each a regular, non-sparse file
    with a plain relative name that no other member has, and only zero bytes after the last one's data. Any refusal
    reads none of them. Anything but gzip does not decompress."""

    data = _decompressed(raw, zlib.decompressobj(wbits=_GZIP_WBITS), max_bytes)
    members: dict[str, bytes] = {}
    end = 0
    try:
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:") as archive:
            # Read one header at a time, so the count is refused before the member past it is read.
            for info in archive:
                if len(members) == max_members:
                    raise ArchiveError(
                        f"the archive has more than {max_members} members"
                    )
                name = checked_member_name(info.name)
                if not _regular(info):
                    raise ArchiveError(
                        f"member {name} is not a regular, non-sparse file"
                    )
                if name in members:
                    raise ArchiveError(f"member {name} is in the archive twice")
                members[name] = _read(archive, info, max_bytes)
                end = info.offset_data + len(members[name])
    except tarfile.TarError as exc:
        raise ArchiveError(f"the archive is not a readable tar: {exc}") from exc
    # tarfile stops at the first zero block, or at a header cut short: what follows would never be read (Sourcery on
    # #489). Only the end-of-archive blocks and the record's padding, all zero, may follow the last member.
    if data[end:].strip(b"\0"):
        raise ArchiveError("the archive has data after the end of its members")
    return list(members.items())
