"""The protected secrets plugin's forms (#389 H-PYSEC-2; Decision 0122): what it reports in Dockerfiles, Makefiles,
YAML and encrypted keys, what it never reports, and that it reads a hostile line in linear time.

Values are built here, so no tracked file holds one. The plugin imports detect-secrets, which only the exact
development verification environment carries."""

from __future__ import annotations

import hashlib
import importlib.util
import os
import tempfile
import threading
import time
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch

_AVAILABLE = importlib.util.find_spec("detect_secrets") is not None
_VALUE = "q7".join(["Zr", "Lm", "Vx", "Wp"])
# A base64 body line, and its header, from parts.
_BODY = "QUJD" * 16
_HEADER = "-----BEGIN " + "ENCRYPTED PRIVATE KEY-----"


@unittest.skipUnless(
    _AVAILABLE,
    "detect-secrets is available only in the exact development verification environment",
)
class SecretValuesTests(unittest.TestCase):
    def setUp(self) -> None:
        from tools import security_scan_plugin

        self.values = security_scan_plugin.secret_values

    def _check(self, cases: list[tuple[str, str, list[str]]]) -> None:
        for filename, line, expected in cases:
            with self.subTest(filename=filename, line=line):
                self.assertEqual(expected, list(self.values(filename, line, None)))

    def test_a_dockerfile_assignment_is_reported_and_a_reference_is_not(self) -> None:
        self._check(
            [
                ("Dockerfile", f"ENV DB_PASSWORD={_VALUE}", [_VALUE]),
                ("Dockerfile", f'ENV DB_PASSWORD="{_VALUE}"', [_VALUE]),
                ("Dockerfile.app", f"ARG API_TOKEN={_VALUE} OTHER=x", [_VALUE]),
                ("app.dockerfile", f"env SERVICE_SECRET='{_VALUE}'", [_VALUE]),
                ("Dockerfile", f"ENV DB_PASSWORD {_VALUE}", [_VALUE]),
                ("Dockerfile", f'ENV DB_PASSWORD "{_VALUE}"', [_VALUE]),
                ("Dockerfile", f"ENV DB_PASSWORD {_VALUE} more", []),
                ("Dockerfile", "ENV DB_PASSWORD=${DB_PASSWORD}", []),
                ("Dockerfile", f"ENV DB_HOST={_VALUE}", []),
                ("Dockerfile", f"RUN echo DB_PASSWORD={_VALUE}", []),
            ]
        )

    def test_a_legacy_env_value_keeps_its_equals_signs(self) -> None:
        # Codex on #470: the form follows the first token; `ENV NAME value=` is the legacy form whatever its value.
        self._check(
            [
                ("Dockerfile", f"ENV DB_PASSWORD {_VALUE}=", [f"{_VALUE}="]),
                ("Dockerfile", f"ENV DB_PASSWORD {_VALUE}==", [f"{_VALUE}=="]),
                ("Dockerfile", f"ENV DB_PASSWORD=x API_TOKEN={_VALUE}", [_VALUE]),
            ]
        )

    def test_a_legacy_env_value_is_read_for_its_pairs_too(self) -> None:
        # cubic on #470: a secret-named pair inside a legacy value is still read, as before the legacy form was read.
        self._check(
            [
                (
                    "Dockerfile",
                    f'ENV JAVA_OPTS "-Dspring.datasource.password={_VALUE}"',
                    [_VALUE],
                ),
                ("Dockerfile", f"ENV JAVA_OPTS -Dx=1 -Ddb.password={_VALUE}", [_VALUE]),
                ("Dockerfile", f"ENV DB_PASSWORD {_VALUE}=", [f"{_VALUE}="]),
                ("Dockerfile", "ENV JAVA_OPTS -Dpassword=${DB_PASSWORD}", []),
                # Both forms are read: the line's one candidate then has two values (deduplicated by its hit).
                (
                    "Dockerfile",
                    f'ENV DB_PASSWORD "api_key={_VALUE}"',
                    [f"api_key={_VALUE}", _VALUE],
                ),
            ]
        )

    def test_a_makefile_assignment_is_reported_and_a_reference_is_not(self) -> None:
        self._check(
            [
                ("Makefile", f"DB_PASSWORD := {_VALUE}", [_VALUE]),
                ("GNUmakefile", f"DB_PASSWORD::={_VALUE}", [_VALUE]),
                ("rules.mk", f"export API_KEY ?= {_VALUE}", [_VALUE]),
                ("makefile", f"override AUTH_TOKEN += '{_VALUE}'", [_VALUE]),
                ("Makefile", f"DB_PASSWORD != {_VALUE}  ", [_VALUE]),
                ("Makefile", "DB_PASSWORD = $(shell cat secret.txt)", []),
                ("Makefile", f"DB_USER = {_VALUE}", []),
            ]
        )

    def test_a_yaml_mapping_is_reported_and_a_reference_or_placeholder_is_not(
        self,
    ) -> None:
        self._check(
            [
                ("config.yml", f"api_key: {_VALUE}", [_VALUE]),
                ("config.yaml", f'  client_secret: "{_VALUE}"', [_VALUE]),
                ("config.yml", f"- auth-token: '{_VALUE}'", [_VALUE]),
                ("config.yml", f"password: {_VALUE}  # rotated", [_VALUE]),
                ("config.yml", "password: ${{ secrets.DB }}", []),
                ("config.yml", "password: changeme", []),
                ("config.yml", "password: <your password>", []),
                ("config.yml", "password: 123456789", []),
                ("config.yml", "password: short", []),
                ("config.yml", "password: /run/secrets/db_password", []),
                ("config.yml", f"username: {_VALUE}", []),
                ("notes.txt", f"password: {_VALUE}", []),
            ]
        )

    def test_a_literal_dollar_is_part_of_a_value_and_only_a_reference_is_not(
        self,
    ) -> None:
        # cubic on #470: a `$` anywhere dropped the value; only a reference form is benign.
        self._check(
            [
                ("config.yml", f"password: pa$${_VALUE}", [f"pa$${_VALUE}"]),
                ("Dockerfile", f"ENV DB_PASSWORD={_VALUE}$", [f"{_VALUE}$"]),
                ("config.yml", "password: $DB_PASSWORD", []),
                ("config.yml", "password: prefix-${DB_PASSWORD}", []),
                ("Makefile", "DB_PASSWORD = $(DB_SECRET_VALUE)", []),
                ("config.yml", "password: %DB_PASSWORD%", []),
            ]
        )

    def test_a_hash_without_whitespace_before_it_is_part_of_a_yaml_value(self) -> None:
        # cubic on #470: YAML starts a comment only at a `#` after whitespace.
        self._check([("config.yml", f"password: ab#{_VALUE}", [f"ab#{_VALUE}"])])

    def test_a_value_starting_with_a_slash_is_a_path_only_when_it_is_one(self) -> None:
        # cubic on #470: a base64 value may start with `/`.
        token = "/" + _VALUE + "+/" + _VALUE + "=="
        self._check(
            [
                ("config.yml", f"password: {token}", [token]),
                ("config.yml", "password: /run/secrets/db_password", []),
                ("config.yml", "password: ./secrets/db_password", []),
                ("config.yml", "password: ~/secrets/db_password", []),
            ]
        )

    def test_an_encrypted_private_key_body_is_reported(self) -> None:
        self.assertEqual([_BODY], list(self.values("key.txt", _HEADER, _BODY)))
        self.assertEqual([], list(self.values("key.txt", _HEADER, "short")))
        self.assertEqual([], list(self.values("key.txt", _HEADER, None)))

    def _refused(self, build) -> None:
        """The plugin scan over the one path `build` makes under a new root refuses it, in time, as the scanner's
        own snapshot refuses it."""
        from tools import security_scan

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            relative = build(root)
            outcome: list[object] = []

            def scan() -> None:
                try:
                    outcome.append(
                        security_scan.scan_with_protected_plugins(root, [relative])
                    )
                except Exception as exc:  # the test names whatever the scan raises
                    outcome.append(exc)

            worker = threading.Thread(target=scan, daemon=True)
            worker.start()
            worker.join(10)
            blocked = worker.is_alive()
            if blocked:
                # Release a read that waits for a writer, so the worker ends.
                os.close(os.open(root / relative, os.O_WRONLY | os.O_NONBLOCK))
                worker.join(10)
        self.assertFalse(blocked, f"the scan of {relative} waited for a writer")
        self.assertEqual(1, len(outcome))
        self.assertIsInstance(outcome[0], security_scan.SecurityScanError)

    def test_the_plugin_scan_never_follows_a_link(self) -> None:
        # Amazon Q and cubic on #470: no link is followed, at the file or at any parent; the scan refuses it.
        def link(root: Path) -> str:
            (root / "target.yml").write_text(f"api_key: {_VALUE}\n", encoding="utf-8")
            (root / "link.yml").symlink_to(root / "target.yml")
            return "link.yml"

        def parent(root: Path) -> str:
            (root / "real").mkdir()
            (root / "real" / "file.yml").write_text(
                f"api_key: {_VALUE}\n", encoding="utf-8"
            )
            (root / "parent").symlink_to(root / "real")
            return "parent/file.yml"

        for build in (link, parent):
            with self.subTest(build=build.__name__):
                self._refused(build)

    @unittest.skipUnless(
        hasattr(os, "mkfifo") and hasattr(os, "O_NONBLOCK"),
        "the named-pipe regression requires POSIX non-blocking opens",
    )
    def test_the_plugin_scan_reads_only_regular_files_and_never_waits(self) -> None:
        # Amazon Q and cubic on #470: a named pipe or a directory is no file the plugins read; neither blocks nor
        # escapes as an exception of its own.
        def pipe(root: Path) -> str:
            os.mkfifo(root / "pipe.yml")
            return "pipe.yml"

        def directory(root: Path) -> str:
            (root / "dir.yml").mkdir()
            return "dir.yml"

        for build in (pipe, directory):
            with self.subTest(build=build.__name__):
                self._refused(build)

    def test_one_line_records_one_hit_of_a_type(self) -> None:
        # Amazon Q and cubic on #470: a legacy value and a secret-named pair it holds are one candidate of the line.
        from tools import security_scan

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "Dockerfile").write_text(
                f'ENV DB_PASSWORD "api_key={_VALUE}"\n', encoding="utf-8"
            )
            records, unread = security_scan.scan_with_protected_plugins(
                root, ["Dockerfile"]
            )
        self.assertEqual([], unread)
        self.assertEqual([1], [record["line"] for record in records])

    def test_a_hostile_line_is_read_in_linear_time(self) -> None:
        # Sonar S8786 and Revix on #470: no pattern may backtrack on a long run. Each line is 200,000 characters, a
        # size at which a quadratic reader takes minutes.
        size = 200_000
        hostile = [
            ("config.yml", "password: x" + " " * size + "y"),
            ("config.yml", "password: " + "a" * size + " #"),
            ("Makefile", "DB_PASSWORD = x" + " " * size + "y"),
            ("Dockerfile", "ENV DB_PASSWORD " + "a" * size + " b"),
            ("Dockerfile", "ENV DB_PASSWORD" + " " * size + "x="),
            ("Dockerfile", "ENV " + "A=" * (size // 2)),
        ]
        for filename, line in hostile:
            with self.subTest(filename=filename, start=line[:20]):
                started = time.monotonic()
                list(self.values(filename, line, None))
                self.assertLess(time.monotonic() - started, 2.0)


class PinnedFileTests(unittest.TestCase):
    """The pinned-file reader and the plugin loader of tools/security_scan.py fail closed, as SecurityScanError, on
    every path (Amazon Q, cubic and Claude on #470). They need no detect-secrets: each failure comes before the
    plugin is imported."""

    def setUp(self) -> None:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name) / "tree"
        self.tool_root = Path(directory.name) / "tools"
        self.root.mkdir()
        self.tool_root.mkdir()

    @unittest.skipUnless(
        hasattr(os, "mkfifo") and hasattr(os, "O_NONBLOCK"),
        "the named-pipe regression requires POSIX non-blocking opens",
    )
    def test_a_pinned_path_that_is_no_regular_file_never_waits(self) -> None:
        # Amazon Q and cubic on #470: a pinned path that is a named pipe or a directory is refused, and its open
        # never waits for a writer.
        from tools import security_scan

        os.mkfifo(self.tool_root / "pipe")
        (self.tool_root / "dir").mkdir()
        for name in ("pipe", "dir"):
            with self.subTest(name=name):
                blocked, raised = self._pinned_read(security_scan, name)
                self.assertFalse(blocked, f"the read of {name} waited for a writer")
                self.assertEqual([f"tool {name} is not a bounded regular file"], raised)

    def _pinned_read(self, security_scan: Any, name: str) -> tuple[bool, list[str]]:
        """Whether reading the pinned path `name` waited for a writer, and what it raised."""
        outcome: list[str] = []

        def read() -> None:
            try:
                security_scan.verified_pinned_bytes(
                    self.tool_root, name, "0" * 64, 100, label=f"tool {name}"
                )
            except Exception as exc:  # the test names whatever the read raises
                outcome.append(str(exc))

        worker = threading.Thread(target=read, daemon=True)
        worker.start()
        worker.join(10)
        blocked = worker.is_alive()
        if blocked:
            # Release a read that waits for a writer, so the worker ends.
            os.close(os.open(self.tool_root / name, os.O_WRONLY | os.O_NONBLOCK))
            worker.join(10)
        return blocked, outcome

    def test_a_pinned_read_fails_closed_without_its_open_flags(self) -> None:
        # Claude on #470: without O_NOFOLLOW or O_NONBLOCK the read refuses, as the snapshot does, never degrades.
        from tools import security_scan

        (self.tool_root / "file").write_bytes(b"x")
        for flag in ("O_NOFOLLOW", "O_NONBLOCK"):
            with self.subTest(flag=flag), patch.object(security_scan.os, flag, None):
                with self.assertRaises(security_scan.SecurityScanError) as raised:
                    security_scan.verified_pinned_bytes(
                        self.tool_root, "file", "0" * 64, 100, label="tool file"
                    )
                self.assertEqual("tool file is unavailable", str(raised.exception))

    def test_a_pinned_read_that_fails_after_its_open_is_a_scan_error(self) -> None:
        # Claude on #470: a failure after the open is SecurityScanError too, and the descriptor is closed.
        from tools import security_scan

        if not os.path.isdir("/proc/self/fd"):
            self.skipTest("needs /proc/self/fd to count descriptors")
        (self.tool_root / "file").write_bytes(b"x")
        before = len(os.listdir("/proc/self/fd"))
        with patch.object(security_scan.os, "fstat", side_effect=OSError(5, "EIO")):
            with self.assertRaises(security_scan.SecurityScanError) as raised:
                security_scan.verified_pinned_bytes(
                    self.tool_root, "file", "0" * 64, 100, label="tool file"
                )
        self.assertEqual("tool file is unavailable", str(raised.exception))
        self.assertEqual(before, len(os.listdir("/proc/self/fd")))

    def test_a_pinned_read_whose_close_fails_is_a_scan_error(self) -> None:
        # Claude on #470: even the descriptor's close failing is the read's own refusal, never a raw OSError.
        from tools import security_scan

        (self.tool_root / "file").write_bytes(b"x")
        real_close = os.close

        def failing_close(descriptor):
            real_close(descriptor)
            raise OSError(4, "EINTR")

        with patch.object(security_scan.os, "close", side_effect=failing_close):
            with self.assertRaises(security_scan.SecurityScanError) as raised:
                security_scan.verified_pinned_bytes(
                    self.tool_root,
                    "file",
                    hashlib.sha256(b"x").hexdigest(),
                    100,
                    label="tool file",
                )
        self.assertEqual("tool file is unavailable", str(raised.exception))

    def test_a_plugin_whose_module_cannot_be_made_is_a_scan_error(self) -> None:
        # Claude on #470: making the module from its spec is inside the plugin's refusal too.
        from tools import security_scan

        (self.root / "notes.txt").write_text("x\n", encoding="utf-8")
        with patch("importlib.util.module_from_spec", side_effect=ImportError("x")):
            with self.assertRaises(security_scan.SecurityScanError) as raised:
                security_scan.scan_with_protected_plugins(self.root, ["notes.txt"])
        self.assertIn("cannot be loaded", str(raised.exception))

    def test_a_plugin_whose_staging_copy_cannot_be_written_is_a_scan_error(
        self,
    ) -> None:
        # Claude on #470: the staging write is inside the plugin's refusal, so the scan fails with SecurityScanError.
        from tools import security_scan

        (self.root / "notes.txt").write_text("x\n", encoding="utf-8")
        real_open = os.open

        def no_staging(path, flags, *args, **kwargs):
            if flags & os.O_CREAT and "gnostoa-secret-plugins-" in str(path):
                raise OSError(28, "ENOSPC")
            return real_open(path, flags, *args, **kwargs)

        with patch.object(security_scan.os, "open", side_effect=no_staging):
            with self.assertRaises(security_scan.SecurityScanError) as raised:
                security_scan.scan_with_protected_plugins(self.root, ["notes.txt"])
        self.assertIn("cannot be loaded", str(raised.exception))
