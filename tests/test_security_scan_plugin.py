"""The protected secrets plugin's forms (#389 H-PYSEC-2; Decision 0122): what it reports in Dockerfiles, Makefiles,
YAML and encrypted keys, what it never reports, and that it reads a hostile line in linear time.

Values are built here, so no tracked file holds one. The plugin imports detect-secrets, which only the exact
development verification environment carries."""

from __future__ import annotations

import importlib.util
import tempfile
import time
import unittest
from pathlib import Path

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

    def test_the_plugin_scan_never_follows_a_link(self) -> None:
        # Amazon Q on #470: the public scan reads no file through a link; a linked path is one it could not read.
        from tools import security_scan

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "target.yml").write_text(f"api_key: {_VALUE}\n", encoding="utf-8")
            (root / "link.yml").symlink_to(root / "target.yml")
            records, unread = security_scan.scan_with_protected_plugins(
                root, ["link.yml"]
            )
        self.assertEqual([], records)
        self.assertEqual(["link.yml"], unread)

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
