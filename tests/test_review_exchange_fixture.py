"""Independent frozen-oracle tests; the transport controller is external."""

from __future__ import annotations

import hashlib
import json
import os
import stat
import subprocess
import sys
import tempfile
import time
import unittest
import zipfile
from pathlib import Path
from typing import Any


class ReviewExchangeFixtureTests(unittest.TestCase):
    """Exercise observable behavior, including real child-process evidence."""

    @classmethod
    def setUpClass(cls) -> None:
        here = Path(__file__).resolve().parent
        override = os.environ.get("GNOSTOA_EXCHANGE_FIXTURE_ROOT")
        roots = (
            [Path(override)]
            if override
            else [here / "fixtures" / "review_exchange", here]
        )
        cls.fixture = next(
            (root for root in roots if (root / "exchange.py").is_file()), roots[0]
        )
        cls.controller = cls.fixture / "exchange.py"
        cls.worker = cls.fixture / "scripted_worker.py"
        if not cls.worker.is_file():
            cls.worker = here / "scripted_worker.py"
        oracle_override = os.environ.get("GNOSTOA_EXCHANGE_ORACLE_ROOT")
        cls.oracle = (
            Path(oracle_override) if oracle_override else cls.fixture / "oracle"
        )
        archive = cls.oracle / "inputs.zip"
        if archive.is_file():
            expected_digest = "147239f44eccca59deb31cf8911eec302a076e4651f50272da1ea437a989e38d"  # pragma: allowlist secret -- public frozen input archive digest
            if hashlib.sha256(archive.read_bytes()).hexdigest() != expected_digest:
                raise RuntimeError("frozen input archive changed")
            expected_members = {
                "native-diagnostic.stderr",
                "roster-single.json",
                "assignment-B.json",
                "cases.json",
                "native-empty.stderr",
                "assignment-A-revised.json",
                "assignment-A.json",
                "roster-two.json",
                "freeze.json",
                "native-A.stdout",
                "native-dissent.stdout",
                "native-malformed.stdout",
                "expected.json",
                "native-B.stdout",
            }
            temporary = tempfile.TemporaryDirectory(prefix="review-exchange-inputs-")
            cls.addClassCleanup(temporary.cleanup)
            cls.oracle = Path(temporary.name)
            with zipfile.ZipFile(archive) as packed:
                members = packed.infolist()
                if (
                    len(members) != len(expected_members)
                    or {member.filename for member in members} != expected_members
                ):
                    raise RuntimeError("unexpected or duplicate frozen input member")
                for member in members:
                    if not stat.S_ISREG(member.external_attr >> 16):
                        raise RuntimeError("frozen input member is not a regular file")
                    (cls.oracle / member.filename).write_bytes(packed.read(member))
        if (
            not (cls.oracle / "expected.json").is_file()
            and (cls.fixture / "expected.json").is_file()
        ):
            cls.oracle = cls.fixture
        for path in [cls.controller, cls.worker, cls.oracle / "freeze.json"]:
            if not path.is_file():
                raise RuntimeError(f"test infrastructure missing: {path}")
        freeze = json.loads((cls.oracle / "freeze.json").read_text())
        for name, identity in freeze["files"].items():
            raw = (cls.oracle / name).read_bytes()
            if (
                len(raw) != identity["bytes"]
                or hashlib.sha256(raw).hexdigest() != identity["sha256"]
            ):
                raise RuntimeError(f"frozen oracle input changed: {name}")
        cls.expected = json.loads((cls.oracle / "expected.json").read_text())[
            "expected"
        ]

    def setUp(self) -> None:
        retained = os.environ.get("GNOSTOA_EXCHANGE_EVIDENCE")
        self.temporary: tempfile.TemporaryDirectory[str] | None = None
        if retained:
            evidence = Path(retained)
            evidence.mkdir(parents=True, exist_ok=True)
            self.run_root = Path(
                tempfile.mkdtemp(prefix=self._testMethodName + "-", dir=evidence)
            )
            with (evidence / "scenario-index.jsonl").open("a") as stream:
                stream.write(
                    json.dumps({"test": self.id(), "path": str(self.run_root)}) + "\n"
                )
        else:
            self.temporary = tempfile.TemporaryDirectory(
                prefix="review-exchange-oracle-"
            )
            self.run_root = Path(self.temporary.name)
        self.workspace = self.run_root / "workspace"
        self.driver = self.run_root / "driver"
        self.driver.mkdir()
        self.calls: list[dict[str, Any]] = []
        self.expected_native: dict[str, tuple[str, str]] = {}

    def tearDown(self) -> None:
        if self.temporary is not None:
            self.temporary.cleanup()

    def cli(
        self,
        *arguments: str,
        phase: str = "coordinator",
        json_result: bool = False,
        allowed_codes: tuple[int, ...] = (0,),
    ) -> Any:
        command = [
            sys.executable,
            str(self.controller),
            "--workspace",
            str(self.workspace),
            *arguments,
        ]
        started = time.time_ns()
        process = subprocess.Popen(
            command, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        try:
            stdout, stderr = process.communicate(timeout=15)
        except subprocess.TimeoutExpired as exc:
            process.kill()
            stdout, stderr = process.communicate()
            self._record_call(
                command, process.pid, phase, started, process.returncode, stdout, stderr
            )
            raise RuntimeError(
                "test infrastructure: controller command did not terminate"
            ) from exc
        self._record_call(
            command, process.pid, phase, started, process.returncode, stdout, stderr
        )
        if process.returncode not in allowed_codes:
            raise RuntimeError(
                f"controller execution error ({process.returncode}): {arguments!r}; "
                f"stderr={stderr.decode('utf-8', errors='replace')}"
            )
        if json_result:
            try:
                return json.loads(stdout)
            except (ValueError, UnicodeDecodeError) as exc:
                raise RuntimeError(
                    f"controller emitted non-JSON result: {arguments!r}"
                ) from exc
        return None

    def _record_call(
        self,
        command: list[str],
        pid: int,
        phase: str,
        started: int,
        returncode: int | None,
        stdout: bytes,
        stderr: bytes,
    ) -> None:
        number = len(self.calls)
        (self.driver / f"call-{number:02d}.stdout").write_bytes(stdout)
        (self.driver / f"call-{number:02d}.stderr").write_bytes(stderr)
        item = {
            "argv": command,
            "pid": pid,
            "phase": phase,
            "started_at_unix_ns": started,
            "ended_at_unix_ns": time.time_ns(),
            "returncode": returncode,
            "stdout_sha256": hashlib.sha256(stdout).hexdigest(),
            "stderr_sha256": hashlib.sha256(stderr).hexdigest(),
        }
        self.calls.append(item)
        with (self.driver / "process-calls.jsonl").open("a") as stream:
            stream.write(json.dumps(item, sort_keys=True) + "\n")

    def init(self, *, single: bool = False, phase: str = "coordinator") -> None:
        roster = self.oracle / ("roster-single.json" if single else "roster-two.json")
        self.cli("init", "--roster", str(roster), phase=phase)

    def dispatch(
        self,
        job: str,
        *,
        response: str | None = None,
        diagnostic: str = "native-empty.stderr",
        drop_receipt: bool = False,
        normalizer: str = "plain",
        release: Path | None = None,
        phase: str = "coordinator",
    ) -> None:
        response = response or f"native-{job}.stdout"
        self.expected_native[job] = (response, diagnostic)
        argv = [
            sys.executable,
            str(self.worker),
            "--response",
            str(self.oracle / response),
            "--diagnostic",
            str(self.oracle / diagnostic),
            "--marker",
            str(self.driver / f"{job}.launches.jsonl"),
            "--assignment-out",
            str(self.driver / f"{job}.assignment.bin"),
            "--intent-path",
            str(self.workspace / "jobs" / job / "intent.json"),
        ]
        if release is not None:
            argv.extend(["--release-file", str(release)])
        spec = self.driver / f"{job}.spec.json"
        spec.write_text(
            json.dumps(
                {
                    "argv": argv,
                    "normalizer": normalizer,
                    "drop_receipt": drop_receipt,
                    "timeout_seconds": 30,
                }
            )
            + "\n"
        )
        result = self.cli(
            "dispatch", "--job", job, "--spec", str(spec), phase=phase, json_result=True
        )
        self.assertEqual(result["job"], job)
        self.assertIsInstance(result["pid"], int)
        self.assertGreater(result["pid"], 0)

    def wait_for(self, path: Path) -> None:
        deadline = time.monotonic() + 10
        while not path.is_file():
            if time.monotonic() >= deadline:
                self.fail(f"required observable artifact was not produced: {path}")
            time.sleep(0.02)

    def receipt(self, job: str) -> None:
        self.wait_for(self.workspace / "jobs" / job / "receipt.json")
        self.assert_native(job)
        self.assert_assignment_and_launch(job)

    def assert_native(self, job: str) -> None:
        response, diagnostic = self.expected_native[job]
        for output, original in [("stdout.bin", response), ("stderr.bin", diagnostic)]:
            actual = self.workspace / "jobs" / job / output
            self.assertTrue(
                actual.is_file(), f"missing retained native stream: {actual}"
            )
            observed = actual.read_bytes()
            frozen = (self.oracle / original).read_bytes()
            self.assertEqual(len(observed), len(frozen), (job, output))
            self.assertEqual(
                hashlib.sha256(observed).hexdigest(), hashlib.sha256(frozen).hexdigest()
            )
            self.assertEqual(
                observed, frozen, "native byte fidelity, not parsed equality"
            )

    def assert_assignment_and_launch(self, job: str) -> None:
        self.wait_for(self.driver / f"{job}.launches.jsonl")
        captured = (self.driver / f"{job}.assignment.bin").read_bytes()
        frozen = (self.oracle / f"assignment-{job}.json").read_bytes()
        self.assertEqual(
            captured, frozen, "worker must receive exact frozen assignment bytes"
        )
        launches = [
            json.loads(line)
            for line in (self.driver / f"{job}.launches.jsonl").read_text().splitlines()
        ]
        self.assertEqual(len(launches), 1, "collect/resume must not redispatch")
        self.assertTrue(launches[0]["intent_present_before_native_worker_output"])
        self.assertEqual(
            launches[0]["assignment_sha256"], hashlib.sha256(frozen).hexdigest()
        )

    def observe(
        self, case: str, *, stage: str | None = None, phase: str = "coordinator"
    ) -> dict[str, Any]:
        actual = self.cli("view", phase=phase, json_result=True)
        expected = self.expected[case] if stage is None else self.expected[case][stage]
        # Check every frozen field. Additional implementation diagnostics are permitted.
        unordered = {
            "current_ids",
            "pending_ids",
            "stale_ids",
            "unknown_dispatch_ids",
            "never_dispatched_ids",
            "unresolved_material_finding_ids",
            "normalization_error_ids",
        }
        for key, value in expected.items():
            self.assertIn(key, actual, f"{case}: missing required observable {key}")
            if key in unordered:
                self.assertCountEqual(actual[key], value, f"{case}: {key}")
            else:
                self.assertEqual(actual[key], value, f"{case}: {key}")
        return actual

    def complete_pair(self) -> None:
        self.init()
        for job in ["A", "B"]:
            self.dispatch(job)
            self.receipt(job)
        self.cli("collect")

    def test_X01_valid_two_job_exchange(self) -> None:
        self.complete_pair()
        self.observe("X01")

    def test_X02_single_actor_is_not_independent(self) -> None:
        self.init(single=True)
        self.dispatch("A")
        self.receipt("A")
        self.cli("collect")
        self.observe("X02")

    def test_X03_separate_coordinator_process_resumes_durable_results(self) -> None:
        self.init(phase="P1")
        release = self.driver / "release-workers"
        for job in ["A", "B"]:
            self.dispatch(job, release=release, phase="P1")
            self.wait_for(self.driver / f"{job}.launches.jsonl")
        first = list(self.calls)
        self.assertTrue(all(call["returncode"] == 0 for call in first))
        # These fixture files release workers; no task/result is passed into P2.
        release.touch()
        for job in ["A", "B"]:
            self.receipt(job)
        self.cli("collect", phase="P2")
        self.observe("X03", phase="P2")
        second = [call for call in self.calls if call["phase"] == "P2"]
        self.assertTrue(second)
        self.assertTrue(
            {call["pid"] for call in first}.isdisjoint(call["pid"] for call in second)
        )
        self.assertLessEqual(
            max(call["ended_at_unix_ns"] for call in first),
            min(call["started_at_unix_ns"] for call in second),
        )
        self.assertTrue(all(call["argv"][-1] in {"collect", "view"} for call in second))
        for job in ["A", "B"]:
            self.assert_assignment_and_launch(job)

    def test_X04_never_registered_job_stays_in_denominator(self) -> None:
        self.init()
        self.dispatch("A")
        self.receipt("A")
        self.cli("collect")
        self.assertFalse((self.driver / "B.launches.jsonl").exists())
        self.assertFalse((self.workspace / "jobs" / "B" / "intent.json").exists())
        self.observe("X04")

    def test_X05_ambiguous_dispatch_is_not_retried(self) -> None:
        self.init()
        self.dispatch("A")
        self.receipt("A")
        self.dispatch("B", drop_receipt=True)
        self.wait_for(self.driver / "B.launches.jsonl")
        self.wait_for(self.workspace / "jobs" / "B" / "stdout.bin")
        for _ in range(2):
            self.cli("collect", phase="P2")
            self.observe("X05", phase="P2")
            self.assertFalse((self.workspace / "jobs" / "B" / "receipt.json").exists())
            self.assert_assignment_and_launch("B")

    def test_X06_assignment_and_candidate_drift_preserve_originals(self) -> None:
        self.complete_pair()
        originals = [
            self.workspace / "assignments" / f"{job}.json" for job in ["A", "B"]
        ]
        originals += [
            self.workspace / "jobs" / job / "review.json" for job in ["A", "B"]
        ]
        before = {str(path): path.read_bytes() for path in originals}
        self.cli(
            "revise",
            "--job",
            "A",
            "--assignment",
            str(self.oracle / "assignment-A-revised.json"),
        )
        self.observe("X06", stage="stage1")
        self.cli(
            "revise",
            "--commit",
            "ad88768fc83163850db46eda198bf18f8965cab3",  # pragma: allowlist secret -- public historical commit
        )
        self.observe("X06", stage="stage2")
        for path in originals:
            self.assertEqual(
                path.read_bytes(), before[str(path)], "historical original changed"
            )
        for job in ["A", "B"]:
            self.assert_native(job)
            self.assert_assignment_and_launch(job)

    def test_X07_duplicate_and_dissent_preserve_separate_disposition(self) -> None:
        self.init()
        self.dispatch("A")
        self.receipt("A")
        self.dispatch(
            "B", response="native-dissent.stdout", diagnostic="native-diagnostic.stderr"
        )
        self.receipt("B")
        self.cli("collect")
        original = (self.workspace / "jobs" / "B" / "review.json").read_bytes()
        self.cli("collect")
        self.cli(
            "disposition",
            "--job",
            "B",
            "--finding",
            "F-D1",
            "--value",
            "DEFERRED",
            "--reason",
            "Unresolved; retained for owner disposition.",
        )
        self.observe("X07")
        self.assertEqual(
            (self.workspace / "jobs" / "B" / "review.json").read_bytes(), original
        )
        self.assert_native("B")
        self.assert_assignment_and_launch("B")

    def test_X08_failed_normalization_preserves_native_bytes(self) -> None:
        self.init()
        self.dispatch("A")
        self.receipt("A")
        self.dispatch(
            "B",
            response="native-malformed.stdout",
            diagnostic="native-diagnostic.stderr",
        )
        self.receipt("B")
        # Both raw streams are checked before the command allowed to normalize.
        self.cli("collect", allowed_codes=(0, 1))
        self.observe("X08")
        self.assert_native("B")
        self.assertFalse((self.workspace / "jobs" / "B" / "review.json").exists())
        self.assert_assignment_and_launch("B")

    def test_R01_spawn_error_is_capture_diagnostic_not_native_stderr(self) -> None:
        self.init(single=True)
        spec = self.driver / "absent-command.json"
        spec.write_text(
            json.dumps(
                {
                    "argv": [str(self.driver / "does-not-exist")],
                    "normalizer": "plain",
                    "timeout_seconds": 3,
                }
            )
        )
        self.cli("dispatch", "--job", "A", "--spec", str(spec))
        job = self.workspace / "jobs" / "A"
        self.wait_for(job / "receipt.json")
        self.assertEqual((job / "stderr.bin").read_bytes(), b"")
        receipt = json.loads((job / "receipt.json").read_bytes())
        self.assertIs(receipt["process_started"], False)
        self.assertEqual(receipt["capture_error"], "FileNotFoundError")
        self.cli("collect")
        self.assertEqual(self.cli("view", json_result=True)["pending_ids"], ["A"])

    def test_R02_malformed_native_events_do_not_abort_other_collection(self) -> None:
        for adapter in ("codex-jsonl", "claude-jsonl"):
            with self.subTest(adapter=adapter):
                self.workspace = self.run_root / adapter
                self.driver = self.run_root / (adapter + "-driver")
                self.driver.mkdir()
                self.init()
                response = self.driver / "null.jsonl"
                response.write_bytes(b"null\n")
                self.dispatch("A", response=str(response), normalizer=adapter)
                self.receipt("A")
                self.dispatch("B")
                self.receipt("B")
                self.cli("collect", allowed_codes=(0, 1))
                self.assertTrue(
                    (self.workspace / "jobs/A/normalization-error.json").exists()
                )
                result = self.cli("view", json_result=True)
                self.assertEqual(result["pending_ids"], ["A"])
                self.assertEqual(result["current_ids"], ["B"])
                self.assert_native("A")

    def test_R03_timeout_stops_cooperative_descendants(self) -> None:
        self.init(single=True)
        marker = self.driver / "after-deadline"
        ready = self.driver / "descendant-started"
        child_code = (
            "import time; from pathlib import Path; "
            f"Path({str(ready)!r}).write_text('ready'); time.sleep(3); "
            f"Path({str(marker)!r}).write_text('continued')"
        )
        worker_code = (
            "import subprocess,sys,time; "
            f"subprocess.Popen([sys.executable,'-c',{child_code!r}]); time.sleep(10)"
        )
        spec = self.driver / "timeout.json"
        spec.write_text(
            json.dumps(
                {
                    "argv": [sys.executable, "-c", worker_code],
                    "normalizer": "plain",
                    "timeout_seconds": 2,
                }
            )
        )
        self.cli("dispatch", "--job", "A", "--spec", str(spec))
        self.wait_for(ready)
        self.wait_for(self.workspace / "jobs/A/receipt.json")
        receipt = json.loads((self.workspace / "jobs/A/receipt.json").read_bytes())
        self.assertIsNone(receipt["returncode"])
        self.assertEqual(receipt["capture_error"], "TimeoutExpired")
        time.sleep(2)
        self.assertFalse(marker.exists(), "descendant continued after timeout")
        self.cli("collect")
        self.assertEqual(self.cli("view", json_result=True)["pending_ids"], ["A"])

    def test_R04_packet_keeps_every_original_and_disposition(self) -> None:
        self.init()
        originals = {}
        for job in ("A", "B"):
            original = {
                "reviewer": "reported-" + job,
                "recommendation": "REQUEST_CHANGES",
                "limitations": "Synthetic response, no real reviewer identity.",
                "findings": [
                    {"id": "same-local-id", "material": True, "text": job + " concern"}
                ],
            }
            originals[job] = original
            response = self.driver / (job + "-original.json")
            response.write_text(json.dumps(original))
            self.dispatch(job, response=str(response))
            self.receipt(job)
        self.cli("collect")
        for job in ("A", "B"):
            self.cli(
                "disposition",
                "--job",
                job,
                "--finding",
                "same-local-id",
                "--value",
                "DEFERRED",
                "--reason",
                job + " remains open",
            )
        result = self.cli("view", json_result=True)
        self.assertIn("original_review_records", result)
        self.assertEqual(result["original_review_records"], originals)
        self.assertEqual(
            set(result["executor_dispositions"]), {"A:same-local-id", "B:same-local-id"}
        )
        for job in ("A", "B"):
            self.assertEqual(
                result["executor_dispositions"][job + ":same-local-id"]["reason"],
                job + " remains open",
            )
            for path in result["native_artifact_paths"][job]:
                self.assertTrue((self.workspace / path).is_file())
            self.assertIn(
                "jobs/" + job + "/stdout.bin", result["native_artifact_paths"][job]
            )


if __name__ == "__main__":
    unittest.main()
