import hashlib
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "behavioral-traceability"
BLIND_REPLAY = FIXTURES / "blind-replay-v1"
REQUIREMENT = ROOT / "knowledge" / "requirements" / "bounded-behavioral-traceability.md"
ASSESSMENT = (
    ROOT
    / "knowledge"
    / "assessments"
    / "bounded-behavioral-traceability-blind-replay-result.md"
)


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
            {"packet_version", "review_request", "requirement", "bases", "cases"},
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
        bases = manifest["bases"]
        self.assertEqual(2, len(bases))
        self.assertEqual(2, len({base["id"] for base in bases}))
        base_by_id = {base["id"]: base for base in bases}
        declared_packet_paths = {"manifest.yaml", "review-request.md"}
        for base in bases:
            self.assertEqual({"id", "tree", "files"}, set(base))
            self.assertRegex(base["id"], r"^base-[0-9a-f]{4}$")
            self.assertRegex(base["tree"], r"^[a-f0-9]{40}$")
            self.assertGreaterEqual(len(base["files"]), 2)
            for entry in base["files"]:
                self.assertEqual({"path", "sha256"}, set(entry))
                self.assertTrue(entry["path"].startswith(f"bases/{base['id']}/"))
                declared_packet_paths.add(entry["path"])
                entries.append(entry)

        cases = manifest["cases"]
        self.assertEqual(3, len(cases))
        self.assertEqual(3, len({case["id"] for case in cases}))
        self.assertEqual(
            ["case-b683", "case-2d91", "case-7ac4"],
            [case["id"] for case in cases],
        )
        self.assertNotEqual(cases[0]["base"], cases[1]["base"])
        self.assertEqual(cases[1]["base"], cases[2]["base"])
        for case in cases:
            self.assertRegex(case["id"], r"^case-[0-9a-f]{4}$")
            self.assertEqual(
                {"id", "base", "task", "candidate", "verification"}, set(case)
            )
            self.assertIn(case["base"], base_by_id)
            for key, filename in (
                ("task", "task.md"),
                ("candidate", "candidate.patch"),
                ("verification", "verification.yaml"),
            ):
                expected_keys = (
                    {"path", "sha256", "tree"}
                    if key == "candidate"
                    else {"path", "sha256"}
                )
                self.assertEqual(expected_keys, set(case[key]))
                expected_path = f"{case['id']}/{filename}"
                self.assertEqual(expected_path, case[key]["path"])
                declared_packet_paths.add(expected_path)
            self.assertRegex(case["candidate"]["tree"], r"^[a-f0-9]{40}$")
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
            base_tree = base_by_id[case["base"]]["tree"]
            verification_path = (BLIND_REPLAY / case["verification"]["path"]).resolve()
            verification = load_mapping(verification_path)
            self.assertEqual(
                {
                    "base_tree",
                    "candidate_sha256",
                    "candidate_tree",
                    "argv",
                    "exit_code",
                    "tests_run",
                    "result",
                },
                set(verification),
            )
            self.assertEqual(base_tree, verification["base_tree"])
            self.assertEqual(
                f"sha256:{candidate_digest}", verification["candidate_sha256"]
            )
            self.assertEqual(case["candidate"]["tree"], verification["candidate_tree"])

    def test_blind_replay_candidates_apply_and_verification_is_reproducible(
        self,
    ) -> None:
        manifest = load_mapping(BLIND_REPLAY / "manifest.yaml")
        base_by_id = {base["id"]: base for base in manifest["bases"]}
        allowed_argv = {
            "case-b683": ["python", "-m", "unittest", "-q", "tests.test_help_text"],
            "case-2d91": ["python", "-m", "unittest", "-q", "tests.test_relocate"],
            "case-7ac4": ["python", "-m", "unittest", "-q", "tests.test_relocate"],
        }
        for case in manifest["cases"]:
            candidate_path = (BLIND_REPLAY / case["candidate"]["path"]).resolve()
            for line in candidate_path.read_text(encoding="utf-8").splitlines():
                if line == " ":
                    continue
                self.assertFalse(line.endswith((" ", "\t")), candidate_path)
            verification = load_mapping(
                (BLIND_REPLAY / case["verification"]["path"]).resolve()
            )
            self.assertEqual(allowed_argv[case["id"]], verification["argv"])

            base = base_by_id[case["base"]]
            with tempfile.TemporaryDirectory(prefix=f"gnostoa-{case['id']}-") as raw:
                work = Path(raw)
                for entry in base["files"]:
                    source = (BLIND_REPLAY / entry["path"]).resolve()
                    target = work / Path(entry["path"]).relative_to(
                        f"bases/{base['id']}"
                    )
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(source, target)

                init = subprocess.run(
                    ["git", "init", "--quiet", "--object-format=sha1", str(work)],
                    cwd=ROOT,
                    check=False,
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(0, init.returncode, init.stderr)
                subprocess.run(
                    ["git", "-C", str(work), "add", "--all"],
                    check=True,
                    capture_output=True,
                    text=True,
                )
                base_tree = subprocess.run(
                    ["git", "-C", str(work), "write-tree"],
                    check=True,
                    capture_output=True,
                    text=True,
                ).stdout.strip()
                self.assertEqual(base["tree"], base_tree)

                check = subprocess.run(
                    [
                        "git",
                        "-C",
                        str(work),
                        "apply",
                        "--check",
                        "--index",
                        "--unidiff-zero",
                        str(candidate_path),
                    ],
                    check=False,
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(0, check.returncode, check.stderr)
                subprocess.run(
                    [
                        "git",
                        "-C",
                        str(work),
                        "apply",
                        "--index",
                        "--unidiff-zero",
                        str(candidate_path),
                    ],
                    check=True,
                    capture_output=True,
                    text=True,
                )
                candidate_tree = subprocess.run(
                    ["git", "-C", str(work), "write-tree"],
                    check=True,
                    capture_output=True,
                    text=True,
                ).stdout.strip()
                self.assertEqual(case["candidate"]["tree"], candidate_tree)

                regenerated = subprocess.run(
                    [
                        "git",
                        "-C",
                        str(work),
                        "diff",
                        "--cached",
                        "--unified=0",
                        "--full-index",
                        "--binary",
                        "--no-ext-diff",
                        "--no-color",
                        base["tree"],
                    ],
                    check=True,
                    capture_output=True,
                ).stdout
                self.assertEqual(candidate_path.read_bytes(), regenerated)

                environment = dict(os.environ)
                environment["PYTHONDONTWRITEBYTECODE"] = "1"
                environment["PYTHONPATH"] = str(work)
                executed = subprocess.run(
                    [sys.executable, *verification["argv"][1:]],
                    cwd=work,
                    env=environment,
                    check=False,
                    capture_output=True,
                    text=True,
                )
                combined = executed.stdout + executed.stderr
                self.assertEqual(
                    verification["exit_code"], executed.returncode, combined
                )
                match = re.search(r"Ran (\d+) tests? in ", combined)
                self.assertIsNotNone(match, combined)
                self.assertEqual(verification["tests_run"], int(match.group(1)))
                self.assertRegex(combined, r"(?m)^OK$")
                self.assertEqual("OK", verification["result"])

    def test_blind_replay_secret_allowlists_are_line_scoped_and_schema_bounded(
        self,
    ) -> None:
        pragma = "# pragma: allowlist secret -- "
        manifest_lines = (
            (BLIND_REPLAY / "manifest.yaml").read_text(encoding="utf-8").splitlines()
        )
        manifest_allowlists = [line for line in manifest_lines if pragma in line]
        content_digest = re.compile(
            r"^\s+sha256: [a-f0-9]{64}  # pragma: allowlist secret -- "
            r"content-addressed replay evidence$"
        )
        tree_identity = re.compile(
            r"^\s+tree: [a-f0-9]{40}  # pragma: allowlist secret -- "
            r"content-addressed replay identity$"
        )
        self.assertEqual(
            15,
            sum(content_digest.fullmatch(line) is not None for line in manifest_lines),
        )
        self.assertEqual(
            5,
            sum(tree_identity.fullmatch(line) is not None for line in manifest_lines),
        )
        self.assertEqual(20, len(manifest_allowlists))

        verification_identity = re.compile(
            r"^(?:base_tree|candidate_tree): [a-f0-9]{40}  "
            r"# pragma: allowlist secret -- content-addressed replay identity$"
        )
        verification_allowlists: list[str] = []
        for path in sorted(BLIND_REPLAY.glob("case-*/verification.yaml")):
            lines = path.read_text(encoding="utf-8").splitlines()
            allowlists = [line for line in lines if pragma in line]
            self.assertEqual(2, len(allowlists), path)
            self.assertTrue(
                all(verification_identity.fullmatch(line) for line in allowlists),
                path,
            )
            verification_allowlists.extend(allowlists)
        self.assertEqual(6, len(verification_allowlists))

        packet_allowlists = [
            (path, line)
            for path in BLIND_REPLAY.rglob("*")
            if path.is_file()
            for line in path.read_text(encoding="utf-8").splitlines()
            if pragma in line
        ]
        self.assertEqual(26, len(packet_allowlists))

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
        reviewer_visible = [
            entry for base in manifest["bases"] for entry in base["files"]
        ]
        reviewer_visible.extend(
            case[key]
            for case in manifest["cases"]
            for key in ("task", "candidate", "verification")
        )
        for entry in reviewer_visible:
            path = (BLIND_REPLAY / entry["path"]).resolve()
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

    def test_result_record_binds_valid_replay_and_limits_claims(self) -> None:
        result = ASSESSMENT.read_text(encoding="utf-8")
        normalized = " ".join(result.split())
        for marker in (
            "752e798c88107a1f402baccc8adde5e6504d26f3",  # pragma: allowlist secret -- public replay source identity
            "20f907dc44aecbbcedba7eb9ce21448a947e8440",  # pragma: allowlist secret -- public replay tree identity
            "7b0b4f0bb9aabe4bede3d1148287959b23badd0c23814d3e23a8ce91d89444dd",  # pragma: allowlist secret -- public replay manifest digest
            "be438bdf3dd4b67b39bfe8a405caa2475b2f0c51c7a0c30d17a6c93057638432",  # pragma: allowlist secret -- public replay response digest
            "1/1",
            "0/2",
            "13m50s",
            "Three earlier raw replay results",
            "Executor-checkpoint effectiveness, real-task productivity and causal Gnostoa utility remain `UNKNOWN`",
            "Public or adopting-project promotion | `NOT AUTHORIZED`",
            "Pull Request #178 owner acceptance and merge | `PENDING`",
        ):
            self.assertIn(marker, normalized)

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
            "knowledge/assessments/bounded-behavioral-traceability-blind-replay-result.md",
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
            "tests/test_behavioral_traceability.py::BehavioralTraceabilityTests.test_blind_replay_candidates_apply_and_verification_is_reproducible",
            "tests/test_behavioral_traceability.py::BehavioralTraceabilityTests.test_blind_replay_secret_allowlists_are_line_scoped_and_schema_bounded",
            "tests/test_behavioral_traceability.py::BehavioralTraceabilityTests.test_blind_replay_does_not_expose_control_answers",
            "tests/test_behavioral_traceability.py::BehavioralTraceabilityTests.test_result_record_binds_valid_replay_and_limits_claims",
            "tests/test_behavioral_traceability.py::BehavioralTraceabilityTests.test_requirement_defines_bounded_blocking_and_oracle_limits",
            "tests/test_behavioral_traceability.py::BehavioralTraceabilityTests.test_router_and_runbook_make_the_two_checkpoints_discoverable",
            "tests/test_behavioral_traceability.py::BehavioralTraceabilityTests.test_guardrail_binds_the_self_only_contract",
        }
        self.assertEqual(expected_tests, set(guardrail["tests"]))


if __name__ == "__main__":
    unittest.main()
