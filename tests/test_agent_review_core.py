"""The agent review pipeline's core is provider- and agent-neutral (Decision 0100).

Falsifiers for the lineage table on #353: the core names no provider, agent or CI
system and imports nothing but the standard library and itself; a test-only second
agent and a test-only second provider drive the unchanged core with the same
guarantees; and the GitHub-and-Claude composition keeps every guarantee it had.
"""

from __future__ import annotations

import ast
import json
import pathlib
import re
import sys
import tempfile
import unittest
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
# The neutral core. Adapters (`*_github.py`, `*_claude_code.py`) are deliberately not
# in this list: translating native vocabulary is their job.
CORE = (
    "agent_review_report",
    "agent_review_delivery",
)
# Provider, agent and CI vocabulary that has no place in a neutral core. A word guard,
# not a portability oracle: the second-adapter tests below are the semantic check.
COUPLING = re.compile(
    r"github|gitlab|bitbucket|claude|anthropic|codex|openai|\bgemini\b|"
    r"RUNNER_TEMP|GITHUB_|actions/runs|\[bot\]|workflow_run|author_association",
    re.IGNORECASE,
)


def _core_source(name: str) -> str:
    """Return a core module's source."""
    return (TOOLS / f"{name}.py").read_text(encoding="utf-8")


def _imports(source: str) -> set[str]:
    """Return the top-level module names a source imports."""
    names: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names.add(node.module.split(".")[0])
    return names


class NeutralCoreStructureTests(unittest.TestCase):
    """The core carries no provider, agent or CI vocabulary and no foreign imports."""

    def test_the_core_imports_only_the_standard_library_and_itself(self) -> None:
        """A core that imports an adapter, or a third-party client, is not a core."""
        allowed = set(sys.stdlib_module_names) | {"tools"}
        for name in CORE:
            with self.subTest(module=name):
                imported = _imports(_core_source(name))
                self.assertEqual(set(), imported - allowed)
                tools_imports = {
                    node.module
                    for node in ast.walk(ast.parse(_core_source(name)))
                    if isinstance(node, ast.ImportFrom)
                    and node.module
                    and node.module.startswith("tools.")
                }
                for module in tools_imports:
                    self.assertIn(module.removeprefix("tools."), CORE)

    def test_the_core_names_no_provider_agent_or_ci_system(self) -> None:
        """Provider, agent and CI vocabulary belongs to adapters."""
        for name in CORE:
            with self.subTest(module=name):
                self.assertEqual([], COUPLING.findall(_core_source(name)))


def _codex_like_report(stream: str) -> Any:
    """A test-only second agent adapter: a JSONL event stream, not an envelope.

    Materially different from the Claude Code execution file: one JSON object per
    line, the answer in `item.completed` events of type `agent_message`, and
    completion signalled by a `turn.completed` event rather than a result subtype.
    """
    from tools import agent_review_report as report

    texts: list[str] = []
    finished = False
    for line in stream.splitlines():
        event = json.loads(line)
        if event.get("type") == "item.completed":
            item = event.get("item") or {}
            if item.get("type") == "agent_message":
                texts.append(str(item.get("text", "")))
        elif event.get("type") == "turn.completed":
            finished = True
        elif event.get("type") == "turn.failed":
            finished = False
    if not texts:
        return report.AgentReport("unavailable", "", False)
    return report.AgentReport(
        "complete" if finished else "incomplete", texts[-1], False
    )


class _ForgeLikeSink:
    """A test-only second provider's comment sink, with its own failure modes.

    Notes are keyed by opaque string ids, authored by a service account named in the
    provider's own vocabulary, and a create may land and still time out.
    """

    def __init__(self, fates: list[str]) -> None:
        self.fates = fates
        self.notes: list[dict[str, str]] = []

    def create(self, body: str) -> str:
        """Create a note, failing as ``fates`` scripts."""
        from tools import agent_review_delivery as delivery

        fate = self.fates.pop(0)
        if fate == "unreached":
            raise delivery.DeliveryUncertain("connection refused before sending")
        note = {
            "id": f"note-{len(self.notes)}",
            "author": "service:review",
            "body": body,
        }
        self.notes.append(note)
        if fate == "lost":
            raise delivery.DeliveryUncertain("the answer never arrived")
        return note["id"]

    def find(self, marker: str) -> str | None:
        """Return the id of this sink's own note carrying ``marker``, if any."""
        for note in self.notes:
            if note["author"] == "service:review" and note["body"].startswith(marker):
                return note["id"]
        return None


class SecondAdapterTests(unittest.TestCase):
    """The unchanged core serves an agent and a provider it was never written for."""

    def test_a_second_agent_drives_the_unchanged_publisher_and_poster(self) -> None:
        """Another agent's output reaches a comment through the same handoff and the
        same rendering, with every guarantee intact."""
        from tools import agent_review_delivery as delivery
        from tools import agent_review_report as report

        stream = "\n".join(
            json.dumps(event)
            for event in (
                {"type": "item.completed", "item": {"type": "reasoning", "text": "x"}},
                {
                    "type": "item.completed",
                    "item": {
                        "type": "agent_message",
                        "text": "Finding: see a.py:3. cc @someone\n```\nfence\n```",
                    },
                },
                {"type": "turn.completed"},
            )
        )
        produced = _codex_like_report(stream)
        with tempfile.TemporaryDirectory() as scratch:
            handoff = pathlib.Path(scratch) / "handoff"
            report.write_handoff(produced, handoff)
            received = report.read_handoff(handoff)
        self.assertEqual(produced, received)
        body = delivery.render_comment(
            received,
            reviewer="Codex",
            provenance="Run: https://ci.example/runs/7 · Reviewed revision: `abc`",
            secret_patterns=(),
        )
        self.assertIn("### Codex review", body)
        self.assertIn("Finding: see a.py:3.", body)
        self.assertNotIn("@someone", body)
        self.assertIn("\uff20someone", body)
        self.assertTrue(body.count("````") >= 2)

    def test_a_second_provider_sink_gets_exactly_one_comment(self) -> None:
        """Post-once is the core's: a sink in another provider's vocabulary, losing a
        create's answer, still ends with one note, and the marker is the core's."""
        from tools import agent_review_delivery as delivery

        marker = delivery.delivery_marker("forge-run-42.1")
        self.assertRegex(marker, r"\A<!-- gnostoa:agent-review:forge-run-42\.1 -->\Z")
        for fates in (["lost"], ["unreached", "ok"]):
            with self.subTest(fates=fates):
                sink = _ForgeLikeSink(list(fates))
                posted = delivery.post_once(
                    sink, f"{marker}\nbody", marker, pause=lambda _seconds: None
                )
                self.assertEqual(1, len(sink.notes))
                self.assertEqual(sink.notes[0]["id"], posted)


class GitHubClaudeCompositionTests(unittest.TestCase):
    """The GitHub-and-Claude composition keeps the guarantees the core leaves to it."""

    def test_the_composition_redacts_both_adapters_credential_shapes(self) -> None:
        """Credential shapes are contributed by the adapters that know them; composed,
        the GitHub poster redacts GitHub tokens, Anthropic keys and generic shapes."""
        from tools import agent_review_claude_code as claude
        from tools import agent_review_delivery as delivery
        from tools import agent_review_github as github
        from tools import agent_review_report as report

        text = " ".join(
            (
                "ghp_" + "A" * 36,
                "github_pat_" + "B" * 30,
                "sk-ant-" + "C" * 30,
                "AKIA" + "D" * 16,
            )
        )
        body = delivery.render_comment(
            report.AgentReport("complete", text, False),
            reviewer=claude.REVIEWER_NAME,
            provenance="Run: x",
            secret_patterns=github.SECRET_PATTERNS + claude.SECRET_PATTERNS,
        )
        for leaked in ("A" * 12, "B" * 12, "C" * 12, "D" * 12):
            with self.subTest(leaked=leaked):
                self.assertNotIn(leaked, body)
        self.assertIn("4 value(s) shaped like a credential", body)

    def test_the_claude_adapter_reads_the_execution_envelope(self) -> None:
        """The Claude Code envelope is translated into the core's report record."""
        from tools import agent_review_claude_code as claude

        with tempfile.TemporaryDirectory() as scratch:
            execution = pathlib.Path(scratch) / "execution.json"
            execution.write_text(
                json.dumps(
                    [
                        {
                            "type": "result",
                            "subtype": "success",
                            "is_error": False,
                            "result": "Looks fine.",
                        }
                    ]
                ),
                encoding="utf-8",
            )
            produced = claude.read_report(execution)
        self.assertEqual(("complete", "Looks fine.", False), tuple(produced)[:3])

    def test_an_empty_execution_is_an_unavailable_report_not_a_crash(self) -> None:
        """An execution file holding no turns at all has no report: `run_succeeded`
        returns before it would read the last turn (CodeAnt on #353)."""
        from tools import agent_review_claude_code as claude

        self.assertFalse(claude.run_succeeded([]))
        self.assertEqual(("", False), claude.final_report([]))
        with tempfile.TemporaryDirectory() as scratch:
            execution = pathlib.Path(scratch) / "execution.json"
            execution.write_text("[]", encoding="utf-8")
            produced = claude.read_report(execution)
        self.assertEqual("unavailable", produced.status)
        self.assertEqual("The reviewer produced no final text.", produced.reason)


if __name__ == "__main__":
    unittest.main()
