import hashlib
import re
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "behavioral-traceability"
BLIND_REPLAY = FIXTURES / "blind-replay-v1"
REQUIREMENT = ROOT / "knowledge" / "requirements" / "bounded-behavioral-traceability.md"


def load_mapping(path: Path) -> dict[str, object]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise AssertionError(f"fixture must be a mapping: {path}")
    return value


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class BehavioralTraceabilityTests(unittest.TestCase):
    def requirement_text(self) -> str:
        self.assertTrue(
            REQUIREMENT.is_file(),
            "the admitted behavioral-traceability Requirement is not implemented",
        )
        return REQUIREMENT.read_text(encoding="utf-8")

    def test_blind_replay_binds_inspectable_raw_artifacts(self) -> None:
        manifest_path = BLIND_REPLAY / "manifest.yaml"
        manifest = load_mapping(manifest_path)
        self.assertEqual(
            "behavioral-traceability-blind-replay/v1",
            manifest["packet_version"],
        )

        entries = [manifest["review_request"], manifest["requirement"]]
        cases = manifest["cases"]
        self.assertEqual(3, len(cases))
        self.assertEqual(3, len({case["id"] for case in cases}))
        for case in cases:
            self.assertRegex(case["id"], r"^case-[0-9a-f]{4}$")
            self.assertEqual({"id", "task", "candidate", "verification"}, set(case))
            entries.extend([case["task"], case["candidate"], case["verification"]])

        for entry in entries:
            path = (BLIND_REPLAY / entry["path"]).resolve()
            path.relative_to(ROOT.resolve())
            self.assertTrue(path.is_file(), path)
            self.assertRegex(entry["sha256"], r"^[a-f0-9]{64}$")
            self.assertEqual(entry["sha256"], sha256(path), path)

        for case in cases:
            candidate_digest = case["candidate"]["sha256"]
            verification_path = (BLIND_REPLAY / case["verification"]["path"]).resolve()
            verification = verification_path.read_text(encoding="utf-8")
            self.assertIn(f"candidate_sha256: sha256:{candidate_digest}", verification)

    def test_blind_replay_does_not_expose_control_answers(self) -> None:
        manifest = load_mapping(BLIND_REPLAY / "manifest.yaml")
        forbidden_fields = (
            "applicability:",
            "contradiction:",
            "alignment:",
            "executor_disposition",
            "reviewer_disposition",
            "expected_trace_review",
            "expected_disposition",
            "control_role",
        )
        forbidden_verdicts = re.compile(
            r"\b(?:SUPPORTS|CONTRADICTS|UNKNOWN|BLOCKED|ACCEPT|NOT APPLICABLE)\b"
        )
        for case in manifest["cases"]:
            for key in ("task", "candidate", "verification"):
                path = (BLIND_REPLAY / case[key]["path"]).resolve()
                text = path.read_text(encoding="utf-8")
                lowered = text.lower()
                for forbidden in forbidden_fields:
                    self.assertNotIn(forbidden, lowered, path)
                self.assertIsNone(forbidden_verdicts.search(text), path)

        for obsolete in ("case-a.yaml", "case-b.yaml", "case-c.yaml"):
            self.assertFalse((FIXTURES / obsolete).exists(), obsolete)

    def test_requirement_defines_bounded_blocking_and_oracle_limits(self) -> None:
        requirement = self.requirement_text()
        normalized = " ".join(requirement.split())
        for marker in (
            "multiple material behaviors",
            "contradiction or ambiguity",
            "material correctness risk",
            "before the first semantic production mutation",
            "initial map",
            "NOT RUN",
            "PENDING",
            "re-bind",
            "active Work Item or change record",
            "blocks review-ready",
            "PASS",
            "FAIL",
            "BLOCKED",
            "NOT RUN",
            "SKIPPED",
            "does not establish semantic completeness",
        ):
            self.assertIn(marker, normalized)

    def test_router_and_runbook_make_the_two_checkpoints_discoverable(self) -> None:
        agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        runbook = (
            ROOT / "knowledge" / "runbooks" / "deliver-bounded-self-hosted-slice.md"
        ).read_text(encoding="utf-8")
        index = (ROOT / "knowledge" / "index.md").read_text(encoding="utf-8")

        self.assertIn("bounded-behavioral-traceability.md", agents)
        self.assertIn("Requirement's applicability criteria", agents)
        self.assertIn("before the first semantic production mutation", runbook)
        self.assertIn("active Work Item or change record", runbook)
        self.assertIn("independently reconcile the behavior map", runbook)
        self.assertIn("requirements/bounded-behavioral-traceability.md", index)

    def test_guardrail_binds_the_self_only_contract(self) -> None:
        policy = yaml.safe_load(
            (ROOT / "policy" / "guardrails.yaml").read_text(encoding="utf-8")
        )
        matching = [
            item
            for item in policy["guardrails"]
            if item["id"] == "bounded-behavioral-traceability"
        ]
        self.assertEqual(1, len(matching))
        guardrail = matching[0]
        self.assertEqual(["kit"], guardrail["applies_to"])
        for path in (
            "AGENTS.md",
            "tests/fixtures/behavioral-traceability/blind-replay-v1/manifest.yaml",
            "tests/fixtures/behavioral-traceability/blind-replay-v1/review-request.md",
            "knowledge/requirements/bounded-behavioral-traceability.md",
            "knowledge/runbooks/deliver-bounded-self-hosted-slice.md",
        ):
            self.assertIn(path, guardrail["implementation"])
        for test in (
            "tests/test_behavioral_traceability.py::BehavioralTraceabilityTests.test_blind_replay_binds_inspectable_raw_artifacts",
            "tests/test_behavioral_traceability.py::BehavioralTraceabilityTests.test_blind_replay_does_not_expose_control_answers",
        ):
            self.assertIn(test, guardrail["tests"])


if __name__ == "__main__":
    unittest.main()
