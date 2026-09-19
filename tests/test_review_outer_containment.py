from __future__ import annotations

import contextlib
import copy
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import ModuleType
from unittest import mock

import yaml
from test_review_assurance_p2b_b2_activation_red import (
    _consumer_authority,
    _current_advisory_input,
)

from tools import review_check, review_outer
from tools.review_model import canonical_json
from tools.review_protected import ProtectedMainDocument

ROOT = Path(__file__).resolve().parents[1]
SECURITY_JOBS = ("security-fast", "extended-route", "extended")
UNAVAILABLE_DETAIL = (
    "protected outer-consumer transport is not admitted as host-persistence-free; "
    "current_advisory is unavailable"
)


def _load_ci_smoke(filename: str) -> ModuleType:
    # CI scripts are shipped as files, not installed as the ci package.
    path = ROOT / "ci" / filename
    spec = importlib.util.spec_from_file_location(
        "gnostoa_containment_test_" + path.stem, path
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load containment smoke module from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


historical_smoke = _load_ci_smoke("review_outer_smoke.py")


def _historical_p2b_authority() -> dict[str, object]:
    authority = copy.deepcopy(_consumer_authority())
    historical = copy.deepcopy(historical_smoke.EXPECTED_CONSUMER)
    authority["expected_consumer"] = historical
    authority["acquired_consumer"] = copy.deepcopy(historical)
    return authority


def _unavailable_bytes() -> bytes:
    return (
        canonical_json(
            {
                "error": {
                    "code": "TOOL_ERROR",
                    "message": "protected prior-effective outer consumer is unavailable",
                    "details": {"error": UNAVAILABLE_DETAIL},
                }
            }
        )
        + "\n"
    ).encode("utf-8")


def _security_checkouts() -> dict[str, dict[str, object]]:
    workflow = yaml.safe_load(
        (ROOT / ".github/workflows/verification.yml").read_text(encoding="utf-8")
    )
    result = {}
    for name in SECURITY_JOBS:
        steps = [
            step
            for step in workflow["jobs"][name]["steps"]
            if str(step.get("uses", "")).startswith("actions/checkout@")
        ]
        if len(steps) != 1:
            raise AssertionError(f"{name} must have exactly one checkout")
        result[name] = steps[0]["with"]
    return result


class ContainmentImportIsolationTests(unittest.TestCase):
    def test_contracts_run_without_source_root_on_import_path(self) -> None:
        # The installed runtime exposes tools, not ci as an importable package.
        # Load tools from its exact path to simulate that boundary without
        # requiring an editable installation in native/source-only checks.
        script = """
import importlib.util
import sys
import unittest
from pathlib import Path
root = Path(sys.argv[1]).resolve()
assert str(root) not in sys.path
spec = importlib.util.spec_from_file_location(
    "tools", root / "tools" / "__init__.py",
    submodule_search_locations=[str(root / "tools")],
)
assert spec is not None and spec.loader is not None
module = importlib.util.module_from_spec(spec)
sys.modules["tools"] = module
spec.loader.exec_module(module)
sys.path.insert(0, str(root / "tests"))
import test_review_outer_containment as contracts
suite = unittest.TestSuite(
    unittest.defaultTestLoader.loadTestsFromTestCase(case)
    for case in (contracts.ReviewOuterContainmentTests, contracts.ContainmentSmokeTests)
)
raise SystemExit(not unittest.TextTestRunner().run(suite).wasSuccessful())
"""
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run(
                [sys.executable, "-I", "-c", script, str(ROOT)],
                cwd=directory,
                capture_output=True,
                text=True,
                timeout=60,
                check=False,
            )
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)


class ReviewOuterContainmentTests(unittest.TestCase):
    def test_production_catalog_admits_only_the_protected_restored_runtime(
        self,
    ) -> None:
        authority = json.loads(
            (ROOT / "tasks" / "issue-11-r2a-current-advisory-consumer.json").read_text(
                encoding="utf-8"
            )
        )
        acquired = authority["acquired_consumer"]
        self.assertEqual(
            frozenset({canonical_json(acquired)}),
            review_outer._HOST_PERSISTENCE_FREE_CONSUMER_IDENTITIES,
        )

    def test_guardrail_records_exact_restored_transport_without_merge_authority(
        self,
    ) -> None:
        guardrails = yaml.safe_load(
            (ROOT / "policy/guardrails.yaml").read_text(encoding="utf-8")
        )["guardrails"]
        guardrail = next(
            entry for entry in guardrails if entry["id"] == "semantic-review-assurance"
        )
        self.assertIn("without merge authority", guardrail["title"])
        self.assertIn(
            "current_advisory transport admits only the exact restored runtime",
            guardrail["title"],
        )
        self.assertIn(
            "knowledge/decisions/0082-eliminate-host-persistence-for-protected-review-payloads-and-route-security-gates.md",
            guardrail["implementation"],
        )

    def test_catalog_keys_bind_every_consumer_field(self) -> None:
        consumer = review_outer._validate_consumer_authority(_consumer_authority())
        self.assertEqual(9, len(consumer))
        # Hypothetical admission probes the comparator, not runtime safety.
        with mock.patch.object(
            review_outer,
            "_HOST_PERSISTENCE_FREE_CONSUMER_IDENTITIES",
            frozenset({canonical_json(consumer)}),
        ):
            review_outer._require_transport_compatible_consumer(consumer)
            for field, value in consumer.items():
                changed = copy.deepcopy(consumer)
                changed[field] = (
                    [*value, "2.0"] if isinstance(value, list) else value + "-changed"
                )
                with self.subTest(field=field):
                    with self.assertRaisesRegex(
                        review_outer.PriorEffectiveOuterUnavailable,
                        "transport is not admitted",
                    ):
                        review_outer._require_transport_compatible_consumer(changed)

    def test_hypothetical_catalog_entry_does_not_bypass_image_proof(self) -> None:
        protected = ProtectedMainDocument("c" * 40, _consumer_authority())
        with (
            mock.patch.object(
                review_outer,
                "_HOST_PERSISTENCE_FREE_CONSUMER_IDENTITIES",
                frozenset({canonical_json(protected.document["acquired_consumer"])}),
            ),
            mock.patch.object(
                review_outer,
                "acquire_gnostoa_current_advisory_consumer",
                return_value=protected,
            ),
            mock.patch.object(
                review_outer,
                "_verify_outer_image",
                side_effect=review_outer.ProtectedJudgeUnavailable(
                    "synthetic image proof failed"
                ),
            ) as verify_image,
            mock.patch.object(review_outer, "_checked_output") as command,
            mock.patch.object(review_outer, "_run_docker") as docker,
        ):
            code, raw = review_outer.run_prior_effective_current_advisory(
                _current_advisory_input()
            )
        self.assertEqual(2, code)
        self.assertIn(
            "synthetic image proof failed", json.loads(raw)["error"]["details"]["error"]
        )
        verify_image.assert_called_once()
        command.assert_not_called()
        docker.assert_not_called()

    def test_historical_stale_and_unknown_consumers_are_contained(self) -> None:
        historical_p2b = _historical_p2b_authority()
        unknown = copy.deepcopy(historical_p2b)
        for key in ("expected_consumer", "acquired_consumer"):
            unknown[key]["runtime_image"] = "ghcr.io/ktogias/gnostoa@sha256:" + "1" * 64
        authorities = {
            "historical-p2b": historical_p2b,
            "historical-b16": historical_smoke._stale_b16_authority(),
            "unknown": unknown,
        }
        for label, authority in authorities.items():
            with self.subTest(identity=label):
                protected = ProtectedMainDocument("c" * 40, authority)
                with (
                    mock.patch.object(
                        review_outer,
                        "acquire_gnostoa_current_advisory_consumer",
                        return_value=protected,
                    ) as acquire,
                    mock.patch.object(
                        review_outer.tempfile,
                        "TemporaryDirectory",
                        side_effect=AssertionError("outer temporary resource created"),
                    ) as temporary,
                    mock.patch.object(
                        review_outer,
                        "_verify_outer_image",
                        side_effect=AssertionError(
                            "Docker image acquisition attempted"
                        ),
                    ) as verify_image,
                    mock.patch.object(
                        review_outer,
                        "_run_docker",
                        side_effect=AssertionError("Docker execution attempted"),
                    ) as docker,
                ):
                    result = review_outer.run_prior_effective_current_advisory(
                        _current_advisory_input()
                    )
                self.assertEqual((2, _unavailable_bytes()), result)
                acquire.assert_called_once_with()
                temporary.assert_not_called()
                verify_image.assert_not_called()
                docker.assert_not_called()

    def test_public_cli_does_not_accept_caller_transport_or_image_selectors(
        self,
    ) -> None:
        document = _current_advisory_input()
        marker = "private caller review content must remain absent"
        document["transport_compatible"] = True
        document["acquired_consumer"] = _consumer_authority()["acquired_consumer"]
        document["caller_review"] = marker
        protected = ProtectedMainDocument("c" * 40, _historical_p2b_authority())
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "synthetic-input.json"
            path.write_text(canonical_json(document), encoding="utf-8")
            stdout = io.StringIO()
            with (
                mock.patch.object(
                    review_outer,
                    "acquire_gnostoa_current_advisory_consumer",
                    return_value=protected,
                ),
                mock.patch.dict(
                    os.environ,
                    {"GNOSTOA_R2A_CANDIDATE_IMAGE": "candidate:untrusted"},
                ),
                mock.patch.object(
                    review_outer.tempfile,
                    "TemporaryDirectory",
                    side_effect=AssertionError("outer temporary resource created"),
                ),
                contextlib.redirect_stdout(stdout),
            ):
                code = review_check.main(["--input", str(path)])
        self.assertEqual(2, code)
        self.assertEqual(_unavailable_bytes().decode("utf-8"), stdout.getvalue())
        self.assertNotIn(marker, stdout.getvalue())

    def test_authority_validation_is_not_replaced_by_containment(self) -> None:
        malformed = _consumer_authority()
        malformed["acquired_consumer"]["source_revision"] = "invalid"
        protected = ProtectedMainDocument("c" * 40, malformed)
        with mock.patch.object(
            review_outer,
            "acquire_gnostoa_current_advisory_consumer",
            return_value=protected,
        ):
            code, raw = review_outer.run_prior_effective_current_advisory({})
        self.assertEqual(2, code)
        self.assertNotEqual(_unavailable_bytes(), raw)
        self.assertIn("closed schema", json.loads(raw)["error"]["details"]["error"])


class ContainmentSmokeTests(unittest.TestCase):
    def test_smoke_input_is_valid_not_a_malformed_failure_fixture(self) -> None:
        smoke = _load_ci_smoke("review_outer_containment_smoke.py")
        self.assertEqual(
            [],
            review_check._schema_errors(
                smoke._synthetic_input(), "review-check-input.schema.json"
            ),
        )

    def test_smoke_exercises_real_public_refusal_and_reports_not_run(self) -> None:
        smoke = _load_ci_smoke("review_outer_containment_smoke.py")
        protected = ProtectedMainDocument("c" * 40, _historical_p2b_authority())
        output = io.StringIO()
        with (
            mock.patch.object(
                smoke.historical_smoke,
                "_acquire_under_candidate_poison",
                return_value=(protected, protected.document["acquired_consumer"]),
            ) as acquire,
            mock.patch.dict(
                os.environ, {"GNOSTOA_R2A_CANDIDATE_IMAGE": "candidate:test"}
            ),
            contextlib.redirect_stdout(output),
        ):
            self.assertEqual(0, smoke.main(["--expected-protected-main", "c" * 40]))
        acquire.assert_called_once_with(
            expected_protected_main="c" * 40, candidate_image="candidate:test"
        )
        receipt = json.loads(output.getvalue())
        self.assertEqual("PASS", receipt["containment_result"])
        self.assertEqual("UNAVAILABLE", receipt["current_advisory"])
        self.assertEqual("NOT_RUN", receipt["live_evaluation"])
        self.assertEqual("NOT_RUN", receipt["outer_docker_effects"])
        self.assertEqual(2, receipt["public_exit_code"])
        self.assertEqual("c" * 40, receipt["protected_main_revision"])
        self.assertNotIn("semantic_outcome", receipt)
        self.assertEqual(
            protected.document["acquired_consumer"], receipt["acquired_consumer"]
        )

    def test_smoke_rejects_semantic_success_and_unrelated_failure(self) -> None:
        smoke = _load_ci_smoke("review_outer_containment_smoke.py")
        for code, raw in (
            (0, b"{}\n"),
            (3, b'{"semantic_outcome":"INCOMPLETE"}\n'),
            (2, b'{"error":{"code":"TOOL_ERROR","details":{}}}\n'),
            (2, _unavailable_bytes() + b" "),
        ):
            with self.subTest(code=code, raw=raw):
                with self.assertRaisesRegex(
                    RuntimeError, "exact transport containment"
                ):
                    smoke._assert_contained_result(code, raw)
        smoke._assert_contained_result(2, _unavailable_bytes())

    def test_smoke_fails_if_real_route_attempts_outer_execution(self) -> None:
        smoke = _load_ci_smoke("review_outer_containment_smoke.py")
        protected = ProtectedMainDocument("c" * 40, _historical_p2b_authority())
        with mock.patch.object(review_outer, "_require_transport_compatible_consumer"):
            with self.assertRaisesRegex(AssertionError, "outer temporary resource"):
                smoke._exercise_containment(protected, _current_advisory_input())


class MergeSubjectSecurityTests(unittest.TestCase):
    def test_security_jobs_keep_the_provider_event_checkout(self) -> None:
        for name, checkout in _security_checkouts().items():
            with self.subTest(job=name):
                self.assertNotIn("ref", checkout)
                self.assertIs(checkout["persist-credentials"], False)

    def test_merge_only_content_reaches_every_security_subject(self) -> None:
        # A synthetic divergence, not a claim about the live PR's current tree.
        # The checkout action's default is the triggering event ref; an explicit
        # pull_request.head.sha instead selects the unmerged topic revision.
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)

            def git(*arguments: str) -> str:
                return subprocess.check_output(
                    ["git", "-C", str(root), *arguments],
                    stderr=subprocess.DEVNULL,
                    text=True,
                ).strip()

            git("init", "-b", "base")
            git("config", "user.name", "Synthetic verification")
            git("config", "user.email", "verification@example.invalid")
            (root / "readme.txt").write_text("base\n", encoding="utf-8")
            git("add", ".")
            git("commit", "-m", "base")
            git("checkout", "-b", "candidate")
            (root / "candidate.txt").write_text("topic\n", encoding="utf-8")
            git("add", ".")
            git("commit", "-m", "candidate")
            head = git("rev-parse", "HEAD")
            git("checkout", "base")
            (root / "tools").mkdir()
            (root / "tools/provider_merge_only.py").write_text(
                "merge_only = True\n", encoding="utf-8"
            )
            git("add", ".")
            git("commit", "-m", "integration-only content")
            git("merge", "--no-ff", "candidate", "-m", "provider merge candidate")
            event_sha = git("rev-parse", "HEAD")
            self.assertNotEqual(head, event_sha)
            for name, checkout in _security_checkouts().items():
                with self.subTest(job=name):
                    ref = checkout.get("ref")
                    if ref is None:
                        selected = event_sha
                    elif (
                        ref == "${{ github.event.pull_request.head.sha || github.sha }}"
                    ):
                        selected = head
                    else:
                        self.fail(f"unsupported checkout selector: {ref}")
                    result = subprocess.run(
                        [
                            "git",
                            "-C",
                            str(root),
                            "cat-file",
                            "-e",
                            f"{selected}:tools/provider_merge_only.py",
                        ],
                        capture_output=True,
                        check=False,
                    )
                    self.assertEqual(0, result.returncode, name)


if __name__ == "__main__":
    unittest.main()
