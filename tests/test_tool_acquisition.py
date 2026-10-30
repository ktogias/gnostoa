"""Tool acquisition for the diagnostic profile's pinned tools (#389 H-PYSEC-2, Decision 0122's remainder).

Both mandatory consumers -- the protected inventory job and the development image -- run the one acquisition entry, and
with every tool family inactive it selects nothing and makes no request. On the active path an asset must equal its pin
before any member is read, an archive yields exactly one regular member of the pinned name under a decompression bound,
the executable must equal its pin before it is installed read-only, and nothing already at the target is followed or
replaced (PAO 6530109793). Every refusal installs nothing for that tool."""

from __future__ import annotations

import hashlib
import io
import os
import stat
import tarfile
import tempfile
import unittest
import urllib.request
from pathlib import Path
from typing import Any
from unittest import mock

import yaml

from tools import quality_evidence, security_scan, tool_acquisition

ROOT = Path(__file__).resolve().parents[1]


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _tar(members: list[tuple[str, bytes | None, str]], mode: str = "w:xz") -> bytes:
    """An archive of the given members: (name, bytes, kind) with kind file, symlink or dir."""
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode=mode) as archive:  # type: ignore[call-overload]
        for name, data, kind in members:
            info = tarfile.TarInfo(name)
            if kind == "file":
                assert data is not None
                info.size = len(data)
                archive.addfile(info, io.BytesIO(data))
            elif kind == "symlink":
                info.type = tarfile.SYMTYPE
                info.linkname = "elsewhere"
                archive.addfile(info)
            else:
                info.type = tarfile.DIRTYPE
                archive.addfile(info)
    return buffer.getvalue()


def _profile(
    active: tuple[str, ...], tools: dict[str, Any] | None = None
) -> dict[str, Any]:
    families = [
        {"id": "typing", "producer": "mypy", "diff": "all", "full": "all"},
        {
            "id": "shell-lint",
            "producer": "shellcheck",
            "diff": "all",
            "full": "all",
            "active": "shell-lint" in active,
        },
        {
            "id": "workflow-lint",
            "producer": "actionlint",
            "diff": "all",
            "full": "all",
            "active": "workflow-lint" in active,
        },
        {
            "id": "dockerfile-lint",
            "producer": "hadolint",
            "diff": "all",
            "full": "all",
            "active": "dockerfile-lint" in active,
        },
    ]
    return {"families": families, "tools": tools or {}}


def _pins(
    name: str, asset: bytes, executable: bytes, member: str | None
) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "url": f"https://github.com/o/{name}/releases/download/v1/{name}.tar.xz",
        "sha256": _sha(asset),
    }
    if member is not None:
        entry["member"] = member
    return {
        name: {
            "version": "1",
            "sha256": {"x86_64": _sha(executable)},
            "asset": {"x86_64": entry},
        }
    }


class SelectionTests(unittest.TestCase):
    def test_mains_profile_acquires_nothing_and_makes_no_request(self) -> None:
        profile = quality_evidence.load_diagnostic_profile(
            ROOT / "policy" / "diagnostic-profile.yaml"
        )
        self.assertEqual([], quality_evidence.tool_names(profile))
        fetcher = mock.Mock(side_effect=AssertionError("no request may be made"))
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(
                [], tool_acquisition.acquire(profile, Path(directory), fetcher=fetcher)
            )
            self.assertEqual([], os.listdir(directory))
        fetcher.assert_not_called()

    def test_selection_follows_the_active_families_producers(self) -> None:
        self.assertEqual(
            ["shellcheck"], quality_evidence.tool_names(_profile(("shell-lint",)))
        )
        self.assertEqual(
            ["actionlint", "shellcheck"],
            quality_evidence.tool_names(_profile(("workflow-lint",))),
        )
        self.assertEqual(
            ["hadolint"], quality_evidence.tool_names(_profile(("dockerfile-lint",)))
        )
        self.assertEqual([], quality_evidence.tool_names(_profile(())))

    def test_an_unsupported_machine_is_refused_before_any_fetch(self) -> None:
        tools = _pins("shellcheck", b"a", b"e", "d/shellcheck")
        fetcher = mock.Mock(side_effect=AssertionError("no request may be made"))
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(
                tool_acquisition.AcquisitionError, "no pin for machine riscv64"
            ):
                tool_acquisition.acquire(
                    _profile(("shell-lint",), tools),
                    Path(directory),
                    machine="riscv64",
                    fetcher=fetcher,
                )
            self.assertEqual([], os.listdir(directory))
        fetcher.assert_not_called()


class ArchiveTests(unittest.TestCase):
    def _acquire(
        self,
        asset: bytes,
        executable: bytes,
        member: str | None,
        served: bytes | None = None,
    ) -> tuple[Path, Exception | None]:
        directory = Path(self.enterContext(tempfile.TemporaryDirectory()))
        tools = _pins("shellcheck", asset, executable, member)
        try:
            tool_acquisition.acquire(
                _profile(("shell-lint",), tools),
                directory,
                machine="x86_64",
                fetcher=lambda url: served if served is not None else asset,
            )
        except tool_acquisition.AcquisitionError as exc:
            return directory, exc
        return directory, None

    def test_an_asset_of_other_bytes_installs_nothing(self) -> None:
        executable = b"#!/bin/sh\necho shellcheck\n"
        asset = _tar([("d/shellcheck", executable, "file")])
        directory, error = self._acquire(
            asset, executable, "d/shellcheck", served=asset + b"x"
        )
        self.assertRegex(str(error), "the asset's bytes are not its pin")
        self.assertEqual([], os.listdir(directory))

    def test_the_member_must_be_one_regular_file_of_the_pinned_name(self) -> None:
        executable = b"#!/bin/sh\necho shellcheck\n"
        cases: dict[str, list[tuple[str, bytes | None, str]]] = {
            "missing": [("d/other", executable, "file")],
            "duplicated": [
                ("d/shellcheck", executable, "file"),
                ("d/shellcheck", executable, "file"),
            ],
            "a link": [("d/shellcheck", None, "symlink")],
            "a directory": [("d/shellcheck", None, "dir")],
        }
        for name, members in cases.items():
            with self.subTest(name):
                directory, error = self._acquire(
                    _tar(members), executable, "d/shellcheck"
                )
                self.assertRegex(str(error), "member d/shellcheck")
                self.assertEqual([], os.listdir(directory))

    def test_a_pinned_member_name_outside_the_archive_root_is_refused(self) -> None:
        executable = b"x"
        for member in (
            "../shellcheck",
            "/shellcheck",
            "d/../shellcheck",
            "d//shellcheck",
        ):
            with self.subTest(member):
                directory, error = self._acquire(
                    _tar([(member, executable, "file")]), executable, member
                )
                self.assertRegex(str(error), "member name")
                self.assertEqual([], os.listdir(directory))

    def test_decompression_is_bounded_and_a_truncated_archive_is_refused(self) -> None:
        big = _tar([("d/shellcheck", b"\0" * 4096, "file")])
        with self.assertRaisesRegex(
            tool_acquisition.AcquisitionError, "decompresses past 1024 bytes"
        ):
            tool_acquisition.member_bytes(big, "d/shellcheck", 1024)
        for mode in ("w:xz", "w:gz"):
            with (
                self.subTest(mode),
                self.assertRaisesRegex(tool_acquisition.AcquisitionError, "truncated"),
            ):
                tool_acquisition.member_bytes(
                    _tar([("d/shellcheck", b"x" * 4096, "file")], mode)[:-16],
                    "d/shellcheck",
                    1 << 20,
                )
        with self.assertRaisesRegex(
            tool_acquisition.AcquisitionError, "not an xz or gzip archive"
        ):
            tool_acquisition.member_bytes(b"PK\x03\x04", "d/shellcheck", 1 << 20)

    def test_an_executable_of_other_bytes_installs_nothing(self) -> None:
        executable = b"#!/bin/sh\necho shellcheck\n"
        asset = _tar([("d/shellcheck", executable + b"#", "file")])
        directory, error = self._acquire(asset, executable, "d/shellcheck")
        self.assertRegex(str(error), "the executable's bytes are not its pin")
        self.assertEqual([], os.listdir(directory))

    def test_a_verified_executable_is_installed_read_only(self) -> None:
        executable = b"#!/bin/sh\necho shellcheck\n"
        for mode in ("w:xz", "w:gz"):
            with self.subTest(mode):
                directory, error = self._acquire(
                    _tar([("d/shellcheck", executable, "file")], mode),
                    executable,
                    "d/shellcheck",
                )
                self.assertIsNone(error)
                installed = directory / "shellcheck"
                self.assertEqual(0o555, stat.S_IMODE(installed.lstat().st_mode))
                self.assertEqual(
                    executable,
                    security_scan.verified_pinned_bytes(
                        directory,
                        "shellcheck",
                        _sha(executable),
                        1 << 20,
                        label="tool shellcheck",
                    ),
                )

    def test_an_asset_that_is_the_executable_is_installed_as_is(self) -> None:
        executable = b"#!/bin/sh\necho hadolint\n"
        directory = Path(self.enterContext(tempfile.TemporaryDirectory()))
        tools = _pins("hadolint", executable, executable, None)
        installed = tool_acquisition.acquire(
            _profile(("dockerfile-lint",), tools),
            directory,
            machine="x86_64",
            fetcher=lambda url: executable,
        )
        self.assertEqual(["hadolint"], installed)
        self.assertEqual(executable, (directory / "hadolint").read_bytes())

    def test_nothing_already_at_the_target_is_followed_or_replaced(self) -> None:
        executable = b"#!/bin/sh\necho shellcheck\n"
        asset = _tar([("d/shellcheck", executable, "file")])
        directory = Path(self.enterContext(tempfile.TemporaryDirectory()))
        outside = directory / "outside"
        outside.write_bytes(b"keep")
        (directory / "root").mkdir()
        for kind in ("link", "file"):
            with self.subTest(kind):
                target = directory / "root" / "shellcheck"
                if kind == "link":
                    target.symlink_to(outside)
                else:
                    target.write_bytes(b"old")
                with self.assertRaisesRegex(
                    tool_acquisition.AcquisitionError, "already exists"
                ):
                    tool_acquisition.acquire(
                        _profile(
                            ("shell-lint",),
                            _pins("shellcheck", asset, executable, "d/shellcheck"),
                        ),
                        directory / "root",
                        machine="x86_64",
                        fetcher=lambda url: asset,
                    )
                self.assertEqual(b"keep", outside.read_bytes())
                if kind == "file":
                    self.assertEqual(b"old", target.read_bytes())
                target.unlink()


class InstallBoundaryTests(unittest.TestCase):
    """The Router's 6530414059: provisioning the initially absent root is its own boundary, not the collector's run copy."""

    def test_the_root_must_be_a_directory_and_never_a_link(self) -> None:
        executable = b"#!/bin/sh\necho shellcheck\n"
        asset = _tar([("d/shellcheck", executable, "file")])
        tools = _pins("shellcheck", asset, executable, "d/shellcheck")
        directory = Path(self.enterContext(tempfile.TemporaryDirectory()))
        real = directory / "real"
        real.mkdir()
        (directory / "link").symlink_to(real)
        (directory / "file").write_bytes(b"")
        for root in ("missing", "link", "file"):
            with (
                self.subTest(root),
                self.assertRaisesRegex(
                    tool_acquisition.AcquisitionError,
                    "is not a directory to install into",
                ),
            ):
                tool_acquisition.acquire(
                    _profile(("shell-lint",), tools),
                    directory / root,
                    machine="x86_64",
                    fetcher=lambda url: asset,
                )
        self.assertEqual([], os.listdir(real))


class _Response:
    def __init__(self, body: bytes) -> None:
        self._body = io.BytesIO(body)
        self.headers: dict[str, str] = {}

    def read1(self, size: int) -> bytes:
        return self._body.read(min(size, 1024))

    def __enter__(self) -> _Response:
        return self

    def __exit__(self, *exc: object) -> None:
        return None


class FetchTests(unittest.TestCase):
    def test_redirects_go_only_once_to_the_release_asset_host(self) -> None:
        handler = tool_acquisition.PinnedRedirect()
        first = urllib.request.Request("https://github.com/o/r/releases/download/v1/a")
        asset = "https://release-assets.githubusercontent.com/x/y?sig=1"
        redirected = handler.redirect_request(first, None, 302, "Found", {}, asset)
        assert redirected is not None
        self.assertEqual(asset, redirected.full_url)
        for target in (
            "https://example.com/a",
            "http://release-assets.githubusercontent.com/a",
            "https://user@release-assets.githubusercontent.com/a",
            "https://release-assets.githubusercontent.com:8443/a",
        ):
            with (
                self.subTest(target),
                self.assertRaisesRegex(tool_acquisition.AcquisitionError, "redirect"),
            ):
                handler.redirect_request(first, None, 302, "Found", {}, target)
        second = urllib.request.Request(asset)
        with self.assertRaisesRegex(
            tool_acquisition.AcquisitionError, "a second redirect"
        ):
            handler.redirect_request(second, None, 302, "Found", {}, asset)

    def test_no_credential_crosses_to_the_asset_host(self) -> None:
        """The Router's 6530414059: no App, owner or readback credential reaches the release-asset host. Acquisition
        sends none, and a redirect carries none even when the first request had one."""
        handler = tool_acquisition.PinnedRedirect()
        first = urllib.request.Request(
            "https://github.com/o/r/releases/download/v1/a",
            headers={
                "Authorization": "token t",
                "Cookie": "c=1",
                "Proxy-Authorization": "p",
            },
        )
        redirected = handler.redirect_request(
            first,
            None,
            302,
            "Found",
            {},
            "https://release-assets.githubusercontent.com/x",
        )
        assert redirected is not None
        sent = {key.lower() for key, _ in redirected.header_items()}
        self.assertTrue(
            {"authorization", "cookie", "proxy-authorization"}.isdisjoint(sent), sent
        )
        opener = mock.Mock()
        opener.open.return_value = _Response(b"x")
        tool_acquisition.fetch(
            "https://github.com/o/r/releases/download/v1/a", opener=opener
        )
        request = opener.open.call_args.args[0]
        self.assertEqual(
            [],
            [
                key
                for key, _ in request.header_items()
                if key.lower() in ("authorization", "cookie")
            ],
        )

    def test_only_a_github_release_url_is_fetched(self) -> None:
        opener = mock.Mock()
        for url in (
            "https://example.com/a",
            "http://github.com/a",
            "https://github.com:8443/a",
            "https://u@github.com/a",
        ):
            with (
                self.subTest(url),
                self.assertRaisesRegex(
                    tool_acquisition.AcquisitionError, "not a GitHub release URL"
                ),
            ):
                tool_acquisition.fetch(url, opener=opener)
        opener.open.assert_not_called()

    def test_the_transfer_is_bounded(self) -> None:
        opener = mock.Mock()
        opener.open.return_value = _Response(b"x" * 5000)
        with self.assertRaisesRegex(
            tool_acquisition.AcquisitionError, "exceeded 4096 bytes"
        ):
            tool_acquisition.fetch(
                "https://github.com/o/r/releases/download/v1/a",
                opener=opener,
                max_bytes=4096,
            )
        opener.open.return_value = _Response(b"x" * 4096)
        self.assertEqual(
            b"x" * 4096,
            tool_acquisition.fetch(
                "https://github.com/o/r/releases/download/v1/a",
                opener=opener,
                max_bytes=4096,
            ),
        )


class ConsumerTests(unittest.TestCase):
    def test_the_protected_inventory_job_acquires_before_it_collects(self) -> None:
        workflow = yaml.safe_load(
            (ROOT / ".github" / "workflows" / "analyzer-readback.yml").read_text(
                encoding="utf-8"
            )
        )
        steps = workflow["jobs"]["inventory"]["steps"]
        names = [step.get("name") for step in steps]
        acquire = names.index("Acquire the active families' pinned tools")
        self.assertLess(names.index("Install main's development tools"), acquire)
        self.assertLess(acquire, names.index("Inventory the head"))
        step = steps[acquire]
        self.assertIn(
            "python -m tools.tool_acquisition --root /opt/gnostoa-tools", step["run"]
        )
        # A refused acquisition leaves its families INCOMPLETE in the inventory; it never stops the inventory itself.
        self.assertIs(True, step.get("continue-on-error"))
        self.assertNotIn("curl", step["run"])
        self.assertNotIn("wget", step["run"])

    def test_the_development_image_acquires_with_the_same_entry(self) -> None:
        dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
        development = dockerfile[
            dockerfile.index("FROM development-build AS development") :
        ]
        entry = development.index(
            "python -m tools.tool_acquisition --root /opt/gnostoa-tools"
        )
        self.assertLess(development.index("requirements/development.lock"), entry)
        self.assertLess(entry, development.index("USER kit"))
        self.assertNotIn("ADD ", development)


if __name__ == "__main__":
    unittest.main()
