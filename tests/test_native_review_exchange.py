"""Native result consumption oracle for #235; no live worker or launch claim.

These synthetic captures exercise collect and a separate persisted view process.
They do not establish real native schema generation, startup or agent handoff.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any


class NativeReviewExchangeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        default = Path(__file__).parent / "fixtures" / "review_exchange"
        cls.fixture = Path(os.environ.get("GNOSTOA_EXCHANGE_FIXTURE_ROOT", default))
        cls.inputs = json.loads(
            (default / "native_oracle" / "inputs.json").read_bytes()
        )

    def setUp(self) -> None:
        retained = os.environ.get("GNOSTOA_NATIVE_EXCHANGE_EVIDENCE")
        if retained:
            Path(retained).mkdir(parents=True, exist_ok=True)
            self.root = Path(
                tempfile.mkdtemp(prefix=self._testMethodName, dir=retained)
            )
        else:
            temporary = tempfile.TemporaryDirectory(prefix="native-exchange-")
            self.addCleanup(temporary.cleanup)
            self.root = Path(temporary.name)
        self.workspace = self.root / "workspace"
        self.call_count = 0
        self.subject = {"commit": "1" * 40}
        self.native: dict[str, bytes] = {}
        self.assignments = {}
        for job in ("A", "B"):
            path = self.root / (job + ".json")
            self.write(path, {"job_id": job, "subject": self.subject, "role": job})
            self.assignments[job] = path
        roster = self.root / "roster.json"
        self.write(
            roster,
            {
                "eligible_job_ids": ["A", "B"],
                "subject": self.subject,
                "assignments": {"A": "A.json", "B": "B.json"},
            },
        )
        self.cli("init", "--roster", str(roster))

    @staticmethod
    def write(path: Path, value: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, ensure_ascii=False) + "\n", encoding="utf-8")

    def cli(self, *args: str) -> dict[str, Any]:
        command = [
            sys.executable,
            str(self.fixture / "exchange.py"),
            "--workspace",
            str(self.workspace),
            *args,
        ]
        completed = subprocess.run(
            command, capture_output=True, timeout=15, check=False
        )
        prefix = self.root / f"call-{self.call_count:02d}"
        prefix.with_suffix(".stdout").write_bytes(completed.stdout)
        prefix.with_suffix(".stderr").write_bytes(completed.stderr)
        self.write(
            prefix.with_suffix(".json"),
            {"argv": command, "returncode": completed.returncode},
        )
        self.call_count += 1
        if completed.returncode:
            raise RuntimeError(
                f"CLI infrastructure failure: {args!r}: {completed.stderr!r}"
            )
        return json.loads(completed.stdout)

    def captured(
        self, job_id: str, name: str, adapter: str = "claude-structured"
    ) -> None:
        """Materialize a completed synthetic capture, not a successful native run."""
        job = self.workspace / "jobs" / job_id
        assignment = self.assignments[job_id].read_bytes()
        identity = hashlib.sha256(assignment).hexdigest()
        stdout = self.inputs["streams"][name].encode("utf-8")
        stderr = b"synthetic native diagnostic retained\r\n"
        self.native[job_id] = stdout
        self.write(job / "spec.json", {"normalizer": adapter})
        self.write(
            job / "intent.json",
            {"assignment_sha256": identity, "subject": self.subject},
        )
        self.write(
            job / "receipt.json",
            {
                "assignment_sha256": identity,
                "subject": self.subject,
                "stdout_sha256": hashlib.sha256(stdout).hexdigest(),
                "stderr_sha256": hashlib.sha256(stderr).hexdigest(),
                "returncode": 0,
            },
        )
        (job / "stdout.bin").write_bytes(stdout)
        (job / "stderr.bin").write_bytes(stderr)

    def assert_native_retained(self, job: str) -> None:
        self.assertEqual(
            (self.workspace / "jobs" / job / "stdout.bin").read_bytes(),
            self.native[job],
        )
        self.assertEqual(
            (self.workspace / "jobs" / job / "stderr.bin").read_bytes(),
            b"synthetic native diagnostic retained\r\n",
        )

    def assert_rejected(self, job: str) -> None:
        view = self.cli("view")
        self.assertIn(job, view["pending_ids"])
        self.assertIn(job, view["normalization_error_ids"])
        self.assertNotIn(job, view["current_ids"])
        self.assertFalse((self.workspace / "jobs" / job / "review.json").exists())
        self.assert_native_retained(job)

    def fresh_workspace(self, name: str) -> None:
        """Give each negative input new state without deleting prior observations."""
        self.workspace = self.root / name
        self.native = {}
        self.cli("init", "--roster", str(self.root / "roster.json"))

    def test_N02_structured_review_wins_over_conflicting_prose(self) -> None:
        self.captured("A", "structured-success")
        self.cli("collect")
        view = self.cli("view")
        self.assertEqual(view["current_ids"], ["A"])
        self.assertEqual(view["pending_ids"], ["B"])
        self.assertEqual(view["never_dispatched_ids"], ["B"])
        self.assertEqual(
            view["original_review_records"], {"A": self.inputs["structured_review"]}
        )
        self.assertFalse(view["human_approval"])
        self.assert_native_retained("A")

    def test_N02_prose_and_nonobject_fields_cannot_supply_structured_review(
        self,
    ) -> None:
        for name in (
            "prose-json-only",
            "prose-fenced-only",
            "structured-null",
            "structured-string",
            "structured-array",
        ):
            with self.subTest(stream=name):
                self.fresh_workspace(name)
                self.captured("A", name)
                self.cli("collect")
                self.assert_rejected("A")

    def test_N02_unsuccessful_missing_or_ambiguous_terminal_is_pending(self) -> None:
        for name in (
            "missing-result",
            "missing-subtype",
            "error-subtype",
            "error-true",
            "missing-error-flag",
            "duplicate-result",
            "nonobject-event",
        ):
            with self.subTest(stream=name):
                self.fresh_workspace(name)
                self.captured("A", name)
                self.cli("collect")
                self.assert_rejected("A")

    def test_N02_native_schema_claim_does_not_replace_domain_validation(self) -> None:
        for name in (
            "missing-findings",
            "bad-recommendation",
            "duplicate-finding",
            "nonboolean-material",
            "missing-finding-text",
        ):
            with self.subTest(stream=name):
                self.fresh_workspace(name)
                self.captured("A", name)
                self.cli("collect")
                self.assert_rejected("A")

    def test_N03_bad_capture_does_not_abort_other_native_collection(self) -> None:
        self.captured("A", "error-subtype")
        self.captured("B", "codex-success", "codex-jsonl")
        self.cli("collect")
        view = self.cli("view")
        self.assertEqual(view["current_ids"], ["B"])
        self.assertEqual(view["pending_ids"], ["A"])
        self.assertEqual(view["normalization_error_ids"], ["A"])
        self.assertEqual(
            view["original_review_records"], {"B": self.inputs["codex_review"]}
        )
        for job in ("A", "B"):
            self.assert_native_retained(job)

    def test_N02_codex_final_text_still_requires_completion_and_complete_json(
        self,
    ) -> None:
        for name in ("codex-missing-completion", "codex-fenced"):
            with self.subTest(stream=name):
                self.fresh_workspace(name)
                self.captured("A", name, "codex-jsonl")
                self.cli("collect")
                self.assert_rejected("A")

    def test_N05_original_dissent_survives_disposition_collection_and_drift(
        self,
    ) -> None:
        self.captured("A", "structured-success")
        self.cli("collect")
        view = self.cli("view")
        self.assertEqual(view["current_ids"], ["A"])
        original = (self.workspace / "jobs" / "A" / "review.json").read_bytes()
        self.cli(
            "disposition",
            "--job",
            "A",
            "--finding",
            "N-DISSENT",
            "--value",
            "DEFERRED",
            "--reason",
            "Retained for human judgement; no agreement inferred.",
        )
        self.cli("collect")
        self.cli("revise", "--commit", "2" * 40)
        view = self.cli("view")
        self.assertEqual(view["current_ids"], [])
        self.assertEqual(view["stale_ids"], ["A"])
        self.assertEqual(view["pending_ids"], ["B"])
        self.assertEqual(view["never_dispatched_ids"], ["B"])
        self.assertEqual(
            view["original_review_records"]["A"], self.inputs["structured_review"]
        )
        self.assertEqual(
            view["executor_dispositions"]["A:N-DISSENT"]["disposition"], "DEFERRED"
        )
        self.assertFalse(view["independent_review_claim"])
        self.assertFalse(view["human_approval"])
        self.assertEqual(
            (self.workspace / "jobs" / "A" / "review.json").read_bytes(), original
        )
        self.assert_native_retained("A")


if __name__ == "__main__":
    unittest.main()
