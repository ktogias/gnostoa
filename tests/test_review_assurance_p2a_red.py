from __future__ import annotations

import copy
import inspect
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

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


def _protected_repository(
    root: Path,
    *,
    kind: str = "protected-current-advisory-authority",
    include_bundle: bool = True,
) -> tuple[Path, str]:
    repository = root / kind
    repository.mkdir()
    _git(repository, "init", "-q", "-b", "main")
    _git(repository, "config", "user.email", "gnostoa-tests@example.test")
    _git(repository, "config", "user.name", "Gnostoa Tests")
    if include_bundle:
        (repository / "tasks").mkdir()
        (repository / BUNDLE_PATH).write_text(
            json.dumps(
                {
                    "schema_version": "1.0",
                    "kind": kind,
                },
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
    else:
        (repository / "README.md").write_text("protected\n", encoding="utf-8")
    _git(repository, "add", ".")
    _git(repository, "commit", "-q", "-m", "protected main")
    return repository, _git(repository, "rev-parse", "HEAD")


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
    def test_fixed_readback_can_supply_dormant_authority_document(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repository, revision = _protected_repository(Path(directory))
            acquired = review_protected._acquire_from_repository(
                str(repository), BUNDLE_PATH
            )

        self.assertEqual(revision, acquired.protected_main_revision)
        self.assertEqual(
            "protected-current-advisory-authority", acquired.document["kind"]
        )

    def test_git_configuration_injection_cannot_redirect_fixed_readback(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            protected, protected_revision = _protected_repository(root)
            attacker, _ = _protected_repository(root, kind="attacker-authority")
            process_environment = {
                "GIT_CONFIG_COUNT": "1",
                "GIT_CONFIG_KEY_0": f"url.file://{attacker}/.insteadOf",
                "GIT_CONFIG_VALUE_0": f"file://{protected}/",
                "GIT_DIR": str(attacker / ".git"),
                "GIT_WORK_TREE": str(attacker),
            }
            with patch.dict(os.environ, process_environment, clear=False):
                acquired = review_protected._acquire_from_repository(
                    f"file://{protected}/", BUNDLE_PATH
                )

        self.assertEqual(protected_revision, acquired.protected_main_revision)
        self.assertEqual(
            "protected-current-advisory-authority", acquired.document["kind"]
        )

    def test_missing_protected_authority_document_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repository, _ = _protected_repository(Path(directory), include_bundle=False)
            with self.assertRaises(ProtectedAcquisitionUnavailable):
                review_protected._acquire_from_repository(str(repository), BUNDLE_PATH)

    def test_non_finite_protected_authority_document_fails_closed(self) -> None:
        for encoded_value in ("NaN", "Infinity", "-Infinity", "1e999"):
            with self.subTest(encoded_value=encoded_value):
                with tempfile.TemporaryDirectory() as directory:
                    repository, _ = _protected_repository(Path(directory))
                    (repository / BUNDLE_PATH).write_text(
                        '{"schema_version":"1.0","value":' + encoded_value + "}\n",
                        encoding="utf-8",
                    )
                    _git(repository, "add", BUNDLE_PATH)
                    _git(repository, "commit", "-q", "-m", "non-finite authority")
                    with self.assertRaisesRegex(
                        ProtectedAcquisitionUnavailable,
                        "non-finite JSON number",
                    ):
                        review_protected._acquire_from_repository(
                            str(repository), BUNDLE_PATH
                        )

    def test_oversized_authority_is_rejected_before_show_buffers_blob(self) -> None:
        oversized = review_protected._MAX_PROTECTED_DOCUMENT_BYTES + 1

        def fake_git_output(
            arguments: list[str], *, cwd: Path, description: str
        ) -> bytes:
            del cwd, description
            if arguments[0] == "fetch":
                return b""
            if arguments[0] == "rev-parse":
                return ("a" * 40 + "\n").encode("ascii")
            if arguments[:2] == ["cat-file", "-s"]:
                return f"{oversized}\n".encode("ascii")
            if arguments[0] == "show":
                self.fail("oversized protected blob must be rejected before git show")
            self.fail(f"unexpected Git command in bounded-size test: {arguments!r}")

        with patch.object(
            review_protected,
            "_git_output",
            side_effect=fake_git_output,
        ):
            with self.assertRaisesRegex(
                ProtectedAcquisitionUnavailable,
                "exceeds the bounded size",
            ):
                review_protected._acquire_from_repository(
                    "https://example.invalid/ignored.git",
                    BUNDLE_PATH,
                )

    def test_production_loader_has_no_caller_selectable_trust_inputs(self) -> None:
        signature = inspect.signature(
            review_protected.acquire_gnostoa_current_advisory_bundle
        )
        self.assertEqual([], list(signature.parameters))
        source = inspect.getsource(
            review_protected.acquire_gnostoa_current_advisory_bundle
        )
        self.assertIn("_GNOSTOA_SELF_REPOSITORY", source)
        self.assertIn("_GNOSTOA_SELF_BUNDLE_PATH", source)
        self.assertNotIn("KNOWLEDGE_KIT_", source)

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
