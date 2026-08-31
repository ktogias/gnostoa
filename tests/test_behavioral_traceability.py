import hashlib
import re
import subprocess
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
            {"packet_version", "review_request", "requirement", "cases"},
            set(manifest),
        )
        self.assertEqual(
            "behavioral-traceability-blind-replay/v1",
            manifest["packet_version"],
        )

        entries = [manifest["review_request"], manifest["requirement"]]
        self.assertEqual({"path", "sha256"}, set(manifest["review_request"]))
        self.assertEqual({"path", "sha256"}, set(manifest["requirement"]))
        self.assertEqual("review-request.md", manifest["review_request"]["path"])
        self.assertEqual(
            "../../../../knowledge/requirements/bounded-behavioral-traceability.md",
            manifest["requirement"]["path"],
        )
        cases = manifest["cases"]
        self.assertEqual(3, len(cases))
        self.assertEqual(3, len({case["id"] for case in cases}))
        self.assertEqual(
            ["case-b683", "case-2d91", "case-7ac4"],
            [case["id"] for case in cases],
        )
        declared_packet_paths = {"manifest.yaml", "review-request.md"}
        for case in cases:
            self.assertRegex(case["id"], r"^case-[0-9a-f]{4}$")
            self.assertEqual({"id", "task", "candidate", "verification"}, set(case))
            for key, filename in (
                ("task", "task.md"),
                ("candidate", "candidate.patch"),
                ("verification", "verification.txt"),
            ):
                self.assertEqual({"path", "sha256"}, set(case[key]))
                expected_path = f"{case['id']}/{filename}"
                self.assertEqual(expected_path, case[key]["path"])
                declared_packet_paths.add(expected_path)
            entries.extend([case["task"], case["candidate"], case["verification"]])

        for entry in entries:
            path = (BLIND_REPLAY / entry["path"]).resolve()
            path.relative_to(ROOT.resolve())
            self.assertTrue(path.is_file(), path)
            self.assertRegex(entry["sha256"], r"^[a-f0-9]{64}$")
            self.assertEqual(entry["sha256"], sha256(path), path)

        actual_packet_paths = {
            path.relative_to(BLIND_REPLAY).as_posix()
            for path in BLIND_REPLAY.rglob("*")
            if path.is_file()
        }
        self.assertEqual(declared_packet_paths, actual_packet_paths)
        self.assertEqual(
            REQUIREMENT.resolve(),
            (BLIND_REPLAY / manifest["requirement"]["path"]).resolve(),
        )

        for case in cases:
            candidate_digest = case["candidate"]["sha256"]
            verification_path = (BLIND_REPLAY / case["verification"]["path"]).resolve()
            verification = verification_path.read_text(encoding="utf-8")
            self.assertIn(f"candidate_sha256: sha256:{candidate_digest}", verification)

    def test_blind_replay_candidate_patches_parse_and_cover_commands(self) -> None:
        manifest = load_mapping(BLIND_REPLAY / "manifest.yaml")
        for case in manifest["cases"]:
            candidate_path = (BLIND_REPLAY / case["candidate"]["path"]).resolve()
            parsed = subprocess.run(
                ["git", "apply", "--numstat", str(candidate_path)],
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(0, parsed.returncode, parsed.stderr)
            for line in candidate_path.read_text(encoding="utf-8").splitlines():
                self.assertFalse(line.endswith((" ", "\t")), candidate_path)

        negative_verification = (
            BLIND_REPLAY / "case-2d91" / "verification.txt"
        ).read_text(encoding="utf-8")
        self.assertIn("test_different_destination", negative_verification)
        self.assertIn("3 passed", negative_verification)

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
            r"\b(?:supports|contradicts|unknown|blocked|accept|not applicable)\b"
        )
        for case in manifest["cases"]:
            for key in ("task", "candidate", "verification"):
                path = (BLIND_REPLAY / case[key]["path"]).resolve()
                text = path.read_text(encoding="utf-8")
                lowered = text.lower()
                for forbidden in forbidden_fields:
                    self.assertNotIn(forbidden, lowered, path)
                self.assertIsNone(forbidden_verdicts.search(lowered), path)

        metadata = "\n".join(
            (BLIND_REPLAY / name).read_text(encoding="utf-8").lower()
            for name in ("manifest.yaml", "review-request.md")
        )
        for forbidden in (
            "answer_key",
            "scoring_key",
            "expected_results",
            "expected_disposition",
            "control_role",
            "negative_control",
            "positive_control",
        ):
            self.assertNotIn(forbidden, metadata)

        requirement = REQUIREMENT.read_text(encoding="utf-8").lower()
        for leaked_composition in (
            "sanitized negative replay",
            "aligned non-trivial control",
            "trivial not-applicable control",
        ):
            self.assertNotIn(leaked_composition, requirement)

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
        self.assertEqual("hybrid", guardrail["enforcement"])
        self.assertEqual(
            "knowledge/requirements/bounded-behavioral-traceability.md#required-workflow",
            guardrail["guidance"],
        )
        expected_implementation = {
            "AGENTS.md",
            "knowledge/index.md",
            "knowledge/decisions/0056-run-a-bounded-behavioral-traceability-review-experiment.md",
            "knowledge/requirements/bounded-behavioral-traceability.md",
            "knowledge/runbooks/deliver-bounded-self-hosted-slice.md",
        }
        expected_implementation.update(
            f"tests/fixtures/behavioral-traceability/blind-replay-v1/{path.relative_to(BLIND_REPLAY).as_posix()}"
            for path in BLIND_REPLAY.rglob("*")
            if path.is_file()
        )
        self.assertEqual(expected_implementation, set(guardrail["implementation"]))
        expected_tests = {
            "tests/test_behavioral_traceability.py::BehavioralTraceabilityTests.test_blind_replay_binds_inspectable_raw_artifacts",
            "tests/test_behavioral_traceability.py::BehavioralTraceabilityTests.test_blind_replay_candidate_patches_parse_and_cover_commands",
            "tests/test_behavioral_traceability.py::BehavioralTraceabilityTests.test_blind_replay_does_not_expose_control_answers",
            "tests/test_behavioral_traceability.py::BehavioralTraceabilityTests.test_requirement_defines_bounded_blocking_and_oracle_limits",
            "tests/test_behavioral_traceability.py::BehavioralTraceabilityTests.test_router_and_runbook_make_the_two_checkpoints_discoverable",
            "tests/test_behavioral_traceability.py::BehavioralTraceabilityTests.test_guardrail_binds_the_self_only_contract",
        }
        self.assertEqual(expected_tests, set(guardrail["tests"]))


if __name__ == "__main__":
    unittest.main()
