"""The DeepSource full read's normalization diagnostic (#309, slice A1).

A normalization failure stays an `ERROR` readback with reason
`NORMALIZATION_ERROR`; its `native` provenance names the failed rule in fixed,
allowlisted text, so the cause is observable without provider content
reaching the readback (owner admission, #309 6103078908).
"""

from __future__ import annotations

import ast
import pathlib
import unittest
from typing import Any
from unittest.mock import patch

from deepsource_fakes import (
    HEAD,
    OBSERVED,
    RUN_UID,
    GraphQLFake,
    check_page,
    issue,
    run_page,
)

from tools import analyzer_deepsource
from tools.analyzer_readback import AnalyzerReadbackError

ROOT = pathlib.Path(__file__).resolve().parents[1]


# Shaped like a GitHub token, to prove such a value cannot reach the diagnostic.
LEAK_PROBE = "ghp_" + "A" * 36


def _read(*issues: dict[str, Any]) -> dict[str, Any]:
    client = GraphQLFake(
        {("run", None): run_page(), ("check-python", None): check_page(list(issues))}
    )
    return analyzer_deepsource.read_full_run(
        client,
        repository="ktogias/gnostoa",
        pull_number=312,
        requested_head=HEAD,
        run_uid=RUN_UID,
        observed_at=OBSERVED,
    )


class FullReadDiagnosticTests(unittest.TestCase):
    def assertUnread(self, document: dict[str, Any]) -> None:
        """The failure's readback is unchanged apart from its diagnostic."""

        self.assertEqual("READBACK_UNAVAILABLE", document["completeness"])
        self.assertEqual("ERROR", document["coverage"]["status"])
        self.assertEqual("NORMALIZATION_ERROR", document["coverage"]["reason"])
        self.assertEqual([], document["findings"])

    def test_a_failed_rule_is_named_in_fixed_text(self) -> None:
        negative = {**issue("issue-1", 10), "beginColumn": -1}
        reversed_range = {**issue("issue-2", 10), "endLine": 9}
        for name, item, rule in (
            (
                "a negative column",
                negative,
                "finding range start_column must be a positive integer",
            ),
            ("a reversed range", reversed_range, "finding range ends before it starts"),
        ):
            with self.subTest(name):
                document = _read(item)
                self.assertUnread(document)
                self.assertEqual({"normalization_error": rule}, document.get("native"))

    def test_provider_content_never_reaches_the_diagnostic(self) -> None:
        """A conflicting identity is provider-controlled; only its fixed text is
        kept (advisory 6102923764)."""

        first = {**issue(LEAK_PROBE, 10)}
        conflicting = {**issue(LEAK_PROBE, 10), "path": f"tools/{LEAK_PROBE}.py"}
        document = _read(first, conflicting)
        self.assertUnread(document)
        self.assertEqual(
            {
                "normalization_error": "a provider-native finding identity is conflicting"
            },
            document.get("native"),
        )
        self.assertNotIn(LEAK_PROBE, repr(document))

    def test_an_unlisted_message_gives_the_fallback(self) -> None:
        for message in (
            f"something new about {LEAK_PROBE}",
            "finding range start_column must be a positive integer, and more",
            "Finding id must be a non-empty string",
            f"prefix: provider-native finding identity {LEAK_PROBE} is conflicting",
            f"provider-native finding identity {LEAK_PROBE} is conflicting, and more",
            "x" * 300 + " must be a positive integer",
        ):
            with (
                self.subTest(message=message[:40]),
                patch.object(
                    analyzer_deepsource,
                    "_read_full_run",
                    side_effect=AnalyzerReadbackError(message),
                ),
            ):
                document = _read()
                self.assertUnread(document)
                self.assertEqual(
                    {"normalization_error": "unclassified normalization failure"},
                    document.get("native"),
                )
                self.assertNotIn(LEAK_PROBE, repr(document))

    def test_every_listed_message_is_one_the_validator_raises(self) -> None:
        """The allowlist can't drift from the validator: each fixed message, and
        each labelled template's text, is one that `analyzer_readback` raises."""

        tree = ast.parse((ROOT / "tools" / "analyzer_readback.py").read_text())
        fixed, labelled = set(), set()
        for node in ast.walk(tree):
            if not (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "AnalyzerReadbackError"
                and node.args
            ):
                continue
            message = node.args[0]
            if isinstance(message, ast.Constant):
                fixed.add(message.value)
            elif (
                isinstance(message, ast.JoinedStr)
                and len(message.values) == 2
                and isinstance(message.values[0], ast.FormattedValue)
                and isinstance(message.values[0].value, ast.Name)
                and message.values[0].value.id == "label"
                and isinstance(message.values[1], ast.Constant)
            ):
                labelled.add(message.values[1].value)
        self.assertLessEqual(set(analyzer_deepsource.NORMALIZATION_RULES), fixed)
        self.assertLessEqual(
            set(analyzer_deepsource.NORMALIZATION_LABELLED_RULES), labelled
        )


if __name__ == "__main__":
    unittest.main()
