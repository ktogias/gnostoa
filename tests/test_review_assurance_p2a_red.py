from __future__ import annotations

import copy
import inspect
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from tools import review_check, review_evaluate, review_protected
from tools.review_protected import ProtectedAcquisitionUnavailable

ROOT = Path(__file__).resolve().parents[1]
BUNDLE_PATH = "tasks/issue-11-r2a-current-advisory.json"


def _git(root: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *arguments],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _protected_repository(root: Path, *, include_bundle: bool = True) -> tuple[Path, str]:
    repository = root / "origin"
    repository.mkdir()
    _git(repository, "init", "-q", "-b", "main")
    _git(repository, "config", "user.email", "gnostoa-tests@example.test")
    _git(repository, "config", "user.name", "Gnostoa Tests")

    (repository / "tools").mkdir()
    (repository / "tools" / "marker.py").write_text("VALUE = 1\n", encoding="utf-8")
    if include_bundle:
        (repository / "tasks").mkdir()
        (repository / BUNDLE_PATH).write_text(
            json.dumps(
                {
                    "schema_version": "1.0",
                    "kind": "protected-current-advisory-authority",
                },
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
    _git(repository, "add", ".")
    _git(repository, "commit", "-q", "-m", "protected main")
    return repository, _git(repository, "rev-parse", "HEAD")


def _runtime_root(root: Path, *, marker: str = "VALUE = 1\n") -> Path:
    runtime = root / "runtime"
    (runtime / "tools").mkdir(parents=True)
    (runtime / "tools" / "marker.py").write_text(marker, encoding="utf-8")
    return runtime


def _current_advisory_fixture() -> tuple[dict[str, object], dict[str, object]]:
    fixture = json.loads(
        (ROOT / "tests" / "fixtures" / "review_check" / "cases.json").read_text(
            encoding="utf-8"
        )
    )
    base = fixture["base"]
    input_document = copy.deepcopy(base["input"])
    policy_document = copy.deepcopy(base["policy"])
    input_document["evaluation_context"].update(
        {
            "mode": "current_advisory",
            "fixture_only": False,
            "judge_relation": "prior_integrated",
        }
    )
    return input_document, policy_document


class ReviewAssuranceP2aTests(unittest.TestCase):
    def test_exact_protected_main_can_supply_dormant_authority_document(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repository, revision = _protected_repository(root)
            runtime = _runtime_root(root)
            acquired = review_protected._acquire_from_repository(
                str(repository),
                BUNDLE_PATH,
                revision,
                runtime,
            )

        self.assertEqual(revision, acquired.protected_main_revision)
        self.assertEqual(revision, acquired.runtime_revision)
        self.assertEqual(
            "protected-current-advisory-authority", acquired.document["kind"]
        )
        self.assertTrue(acquired.public_surface_digest.startswith("sha256:"))

    def test_candidate_revision_cannot_claim_protected_main(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repository, _ = _protected_repository(root)
            runtime = _runtime_root(root)
            with self.assertRaisesRegex(
                ProtectedAcquisitionUnavailable,
                "not the exact protected-main revision",
            ):
                review_protected._acquire_from_repository(
                    str(repository),
                    BUNDLE_PATH,
                    "0" * 40,
                    runtime,
                )

    def test_runtime_surface_mismatch_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repository, revision = _protected_repository(root)
            runtime = _runtime_root(root, marker="VALUE = 2\n")
            with self.assertRaisesRegex(
                ProtectedAcquisitionUnavailable,
                "public surface does not match protected main",
            ):
                review_protected._acquire_from_repository(
                    str(repository),
                    BUNDLE_PATH,
                    revision,
                    runtime,
                )

    def test_missing_protected_authority_document_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repository, revision = _protected_repository(root, include_bundle=False)
            runtime = _runtime_root(root)
            with self.assertRaises(ProtectedAcquisitionUnavailable):
                review_protected._acquire_from_repository(
                    str(repository),
                    BUNDLE_PATH,
                    revision,
                    runtime,
                )

    def test_production_loader_has_no_caller_selectable_trust_inputs(self) -> None:
        signature = inspect.signature(
            review_protected.acquire_gnostoa_current_advisory_bundle
        )
        self.assertEqual([], list(signature.parameters))

    def test_p2a_exposes_no_candidate_callable_semantic_activation_route(self) -> None:
        input_document, policy_document = _current_advisory_fixture()
        code, payload = review_check.evaluate_documents(
            input_document,
            policy_document,
        )

        self.assertEqual(3, code)
        self.assertEqual("INCOMPLETE", payload["outcome"])
        self.assertEqual(
            "BOOTSTRAP_PROTECTED_AUTHORITY_UNAVAILABLE",
            payload["reason"],
        )
        self.assertFalse(
            hasattr(review_check, "_evaluate_protected_current_advisory_documents")
        )
        self.assertFalse(
            hasattr(review_evaluate, "_evaluate_protected_current_advisory")
        )


if __name__ == "__main__":
    unittest.main()
