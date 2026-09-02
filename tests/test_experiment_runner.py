import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / "tools" / "experiment_runner.py"


class ExperimentRunnerContractTests(unittest.TestCase):
    def require_runner(self) -> None:
        if not RUNNER.is_file():
            self.skipTest(
                "RED contract retained: tools/experiment_runner.py is not implemented yet"
            )

    def invoke(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(RUNNER), *args],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )

    def parse_json_stdout(self, result: subprocess.CompletedProcess[str]) -> dict:
        try:
            value = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            self.fail(f"runner stdout must be one JSON object: {exc}: {result.stdout!r}")
        self.assertIsInstance(value, dict)
        return value

    def write_profile(self, root: Path, *, read_roots: list[str]) -> Path:
        project = root / "project"
        evidence = project / ".local-evidence"
        tmp = root / "tmp"
        excluded = root / "excluded"
        for path in (project, evidence, tmp, excluded):
            path.mkdir(parents=True, exist_ok=True)
        profile = {
            "schema": "gnostoa-experiment-runner-profile/v1",
            "read_only_roots": read_roots,
            "project_root": str(project.resolve()),
            "evidence_root": str(evidence.resolve()),
            "temporary_roots": [str(tmp.resolve())],
            "excluded_roots": [str(excluded.resolve())],
            "environment_allowlist": ["PATH", "LANG", "LC_ALL"],
            "network": {
                "mode": "restricted",
                "allow": ["opencode.ai:443"],
            },
        }
        path = root / "profile.yaml"
        path.write_text(yaml.safe_dump(profile, sort_keys=True), encoding="utf-8")
        return path

    def test_red_runner_entry_point_is_missing(self) -> None:
        self.assertTrue(
            RUNNER.is_file(),
            "RED: #164 has no reusable experiment-runner entry point yet",
        )

    def test_profile_rejects_broad_host_root_admission(self) -> None:
        self.require_runner()
        with tempfile.TemporaryDirectory(prefix="gnostoa-runner-red-") as raw:
            profile = self.write_profile(Path(raw), read_roots=["/"])
            result = self.invoke("validate-profile", "--profile", str(profile))
            self.assertEqual(2, result.returncode, result.stderr)
            payload = self.parse_json_stdout(result)
            self.assertEqual("gnostoa-experiment-runner-validation/v1", payload["schema"])
            self.assertEqual("INVALID", payload["status"])
            self.assertIn("broad-read-root-forbidden", payload["reasons"])

    def test_profile_rejects_symlink_or_resolved_root_escape(self) -> None:
        self.require_runner()
        with tempfile.TemporaryDirectory(prefix="gnostoa-runner-red-") as raw:
            root = Path(raw)
            admitted = root / "admitted"
            outside = root / "outside"
            admitted.mkdir()
            outside.mkdir()
            escape = admitted / "escape"
            escape.symlink_to(outside, target_is_directory=True)
            profile = self.write_profile(root, read_roots=[str(escape)])
            result = self.invoke("validate-profile", "--profile", str(profile))
            self.assertEqual(2, result.returncode, result.stderr)
            payload = self.parse_json_stdout(result)
            self.assertEqual("INVALID", payload["status"])
            self.assertIn("resolved-root-outside-admitted-surface", payload["reasons"])

    def test_capability_probe_is_available_or_explicitly_blocked(self) -> None:
        self.require_runner()
        result = self.invoke("probe", "--backend", "auto")
        self.assertEqual(0, result.returncode, result.stderr)
        payload = self.parse_json_stdout(result)
        self.assertEqual("gnostoa-experiment-runner-probe/v1", payload["schema"])
        self.assertIn(payload["status"], {"AVAILABLE", "BLOCKED"})
        if payload["status"] == "AVAILABLE":
            self.assertIn(payload["backend"], {"oci", "bwrap"})
            self.assertFalse(payload.get("reasons"))
        else:
            self.assertIsNone(payload.get("backend"))
            self.assertTrue(payload.get("reasons"))

    def test_smoke_never_converts_missing_capability_into_pass(self) -> None:
        self.require_runner()
        result = self.invoke("smoke", "--backend", "auto", "--network", "restricted")
        self.assertEqual(0, result.returncode, result.stderr)
        payload = self.parse_json_stdout(result)
        self.assertEqual("gnostoa-experiment-runner-smoke/v1", payload["schema"])
        self.assertIn(payload["status"], {"PASS", "BLOCKED", "FAIL"})
        if payload["status"] == "BLOCKED":
            self.assertTrue(payload["reasons"])
            self.assertFalse(payload.get("all_required_checks_passed", False))
            return
        if payload["status"] == "FAIL":
            self.assertTrue(payload["failed_checks"])
            self.assertFalse(payload.get("all_required_checks_passed", False))
            return

        required = {
            "read_admitted_input",
            "deny_write_to_read_only_input",
            "write_project_root",
            "write_evidence_root",
            "deny_outside_write",
            "deny_excluded_read",
            "deny_symlink_escape",
            "clean_environment",
            "no_container_control_socket",
            "admit_declared_egress",
            "refuse_undeclared_egress",
            "producer_bound_evidence",
        }
        self.assertEqual(required, set(payload["checks"]))
        self.assertTrue(all(payload["checks"].values()))
        self.assertTrue(payload["all_required_checks_passed"])
        self.assertIn(payload["backend"], {"oci", "bwrap"})

    def test_derived_identity_binds_producer_configuration_and_inputs(self) -> None:
        self.require_runner()
        with tempfile.TemporaryDirectory(prefix="gnostoa-runner-red-") as raw:
            root = Path(raw)
            artifact = root / "artifact.txt"
            artifact.write_text("bounded evidence\n", encoding="utf-8")
            config_digest = "a" * 64
            input_digest = "b" * 64
            result = self.invoke(
                "attest",
                "--artifact",
                str(artifact),
                "--producer-id",
                "fixture-producer",
                "--producer-version",
                "1.0",
                "--config-sha256",
                config_digest,
                "--input",
                f"fixture-input={input_digest}",
            )
            self.assertEqual(0, result.returncode, result.stderr)
            payload = self.parse_json_stdout(result)
            self.assertEqual("gnostoa-derived-artifact-identity/v1", payload["schema"])
            self.assertEqual(hashlib.sha256(artifact.read_bytes()).hexdigest(), payload["sha256"])
            self.assertEqual(len(artifact.read_bytes()), payload["bytes"])
            self.assertEqual(
                {
                    "id": "fixture-producer",
                    "version": "1.0",
                    "config_sha256": config_digest,
                },
                payload["producer"],
            )
            self.assertEqual(
                [{"id": "fixture-input", "sha256": input_digest}],
                payload["inputs"],
            )

    def test_smoke_separates_semantic_and_mechanical_counts(self) -> None:
        self.require_runner()
        result = self.invoke("smoke", "--backend", "auto", "--network", "restricted")
        self.assertEqual(0, result.returncode, result.stderr)
        payload = self.parse_json_stdout(result)
        self.assertEqual(
            {"semantic_owner_interventions", "mechanical_boundary_controls"},
            set(payload["counters"]),
        )
        self.assertEqual(0, payload["counters"]["semantic_owner_interventions"])
        self.assertGreaterEqual(payload["counters"]["mechanical_boundary_controls"], 0)


if __name__ == "__main__":
    unittest.main()
