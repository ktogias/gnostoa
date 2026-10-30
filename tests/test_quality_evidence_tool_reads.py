"""Contracts of the pinned-tool and secrets families (#389 H-PYSEC-2; Decision 0122) that
tests/test_quality_evidence_tool_families.py, at M13's per-file patch cap, has no room for: their own reads of the
candidate's files never go through a link or wait on a named pipe, and no acquired finding is dropped."""

from __future__ import annotations

import importlib.util
import os
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from tests.test_quality_evidence_profile import _original
from tests.test_quality_evidence_tool_families import _ToolFamilyFixture


class CandidateReadTests(_ToolFamilyFixture):
    def test_a_shebang_is_never_read_through_a_link_or_from_a_pipe(self) -> None:
        # Revix on #470: staging materialises a tracked link, and the shebang read, before any withholding, followed
        # it: to a file outside the tree, or to a named pipe it then waited on.
        first_line = _original(self.module, "_first_line")
        outside = Path(self.directory.name)
        fifo, script = outside / "pipe", outside / "script"
        os.mkfifo(fifo)
        script.write_bytes(b"#!/bin/sh\n")
        (self.root / "to-script").symlink_to(script)
        (self.root / "to-pipe").symlink_to(fifo)
        (self.root / "plain").write_bytes(b"#!/bin/bash\n")
        self.assertEqual(b"#!/bin/bash\n", first_line(self.root, "plain"))
        with self.subTest("a link to a file outside the tree"):
            self.assertEqual(b"", first_line(self.root, "to-script"))
        with self.subTest("a link to a named pipe"):
            reader = threading.Thread(
                target=first_line, args=(self.root, "to-pipe"), daemon=True
            )
            reader.start()
            reader.join(2)
            blocked = reader.is_alive()
            if blocked:
                os.close(os.open(fifo, os.O_WRONLY | os.O_NONBLOCK))
            self.assertFalse(blocked, "the shebang read waited on a named pipe")


@unittest.skipUnless(
    importlib.util.find_spec("detect_secrets") is not None,
    "detect-secrets is available only in the exact development verification environment",
)
class SecretsNegativeTests(_ToolFamilyFixture):
    def test_a_plugin_failure_keeps_the_scanners_own_findings(self) -> None:
        # PAO's F1 (#325 6520982658): a protected plugin failing after the scan discarded the scanner's acquired
        # findings with it. A keyword assignment in Python, which only the scanner's own detectors read; its keyword is
        # built from parts, so no tracked line holds a secret-like literal.
        from tools import security_scan

        (self.root / "config.py").write_text(
            "pass" + "word = '" + "Zq7" * 6 + "'\n", encoding="utf-8"
        )
        self._git("add", "-A")
        self._git("commit", "-q", "-m", "keyword")

        def found(inventory: dict) -> list[int]:
            return [
                f["range"]["start_line"]
                for f in self._findings(inventory, "secrets")
                if f["path"] == "config.py"
            ]

        self.assertEqual([1], found(self._collect(base=self.base)))
        failure = security_scan.SecurityScanError(
            "protected secret plugin x cannot be loaded"
        )
        with patch.object(
            security_scan, "scan_with_protected_plugins", side_effect=failure
        ):
            inventory = self._collect(base=self.base)
        self.assertEqual([1], found(inventory))
        row = self._rows(inventory)["secrets"]
        self.assertEqual("INCOMPLETE", row["analysis"])
        self.assertIn("protected secret plugin x cannot be loaded", row["reason"])
