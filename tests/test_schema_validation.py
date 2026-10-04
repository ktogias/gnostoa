"""The one JSON Schema validation the toolkit's commands share (#365, Decision 0101).

Nine commands each validated with their own helper (eight module functions such as
`_schema`/`_schema_errors`, one inline); the credential check was about to write a tenth
by hand (#365, I6). This module owns the responsibility; the
copies converge on it under #365 P4.
"""

from __future__ import annotations

import json
import os
import pathlib
import shutil
import tempfile
import unittest
from unittest import mock

from tools import schema_validation
from tools.knowledge_common import KnowledgeFormatError, load_yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCHEMA = "agent-credentials.schema.json"


class SchemaErrorsTests(unittest.TestCase):
    """A document is checked against an installed toolkit schema."""

    def test_the_repository_declaration_matches_its_schema(self) -> None:
        document = load_yaml(ROOT / "policy" / "agent-credentials.yaml")
        self.assertEqual([], schema_validation.schema_errors(document, SCHEMA))

    def test_each_violation_is_reported_with_its_location_in_order(self) -> None:
        document = load_yaml(ROOT / "policy" / "agent-credentials.yaml")
        document["capabilities"]["contents"]["max"] = "owner"
        document["max_lifetime_days"] = 0
        document["accepted_unmeasurable"]["pages"] = "no level"
        document["extra"] = True
        errors = schema_validation.schema_errors(document, SCHEMA)
        locations = [error.split(":", 1)[0] for error in errors]
        self.assertIn("capabilities.contents.max", locations)
        self.assertIn("max_lifetime_days", locations)
        self.assertIn("<root>", locations)
        self.assertTrue(any("pages" in error for error in errors), errors)
        self.assertEqual(sorted(locations), locations)

    def test_a_schema_that_is_not_installed_or_not_a_schema_is_refused(self) -> None:
        with self.assertRaises(KnowledgeFormatError):
            schema_validation.schema_errors({}, "no-such.schema.json")
        for name in ("../pyproject.toml", "sub/x.schema.json", ""):
            with self.subTest(name=name), self.assertRaises(KnowledgeFormatError):
                schema_validation.schema_errors({}, name)
        with tempfile.TemporaryDirectory() as scratch:
            kit = pathlib.Path(scratch) / "kit"
            shutil.copytree(ROOT, kit, ignore=shutil.ignore_patterns(".git", "tests"))
            (kit / "schemas" / "broken.schema.json").write_text(
                json.dumps({"type": 7}), encoding="utf-8"
            )
            with (
                mock.patch.dict(os.environ, {"KNOWLEDGE_KIT_ROOT": str(kit)}),
                self.assertRaises(KnowledgeFormatError),
            ):
                schema_validation.schema_errors({}, "broken.schema.json")


if __name__ == "__main__":
    unittest.main()
