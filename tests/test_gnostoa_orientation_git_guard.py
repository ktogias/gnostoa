from __future__ import annotations

import hashlib
import importlib.util
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "gnostoa_self_orientation_git_guard", ROOT / "tasks/gnostoa_orientation.py"
)
assert SPEC is not None and SPEC.loader is not None
orientation = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(orientation)

NOW = "2026-09-11T13:00:00Z"


def _fact(identity: str, text: str) -> dict[str, object]:
    return {"id": identity, "text": text, "source_ids": ["local"]}


def _snapshot(root: Path) -> dict[str, object]:
    local = root / "source.md"
    local.write_text("source\n", encoding="utf-8")
    digest = "sha256:" + hashlib.sha256(local.read_bytes()).hexdigest()
    return {
        "contract": "gnostoa-self-orientation/0.1",
        "subject": {"source_commit": "a" * 40, "source_tree": "b" * 40},
        "projection": {
            "id": "D14-O1",
            "observed_at": "2026-09-11T12:00:00Z",
            "freshness_seconds": 7200,
            "review_characters": 5000,
        },
        "sources": [
            {
                "id": "local",
                "kind": "local-file",
                "locator": "source.md",
                "identity": digest,
                "observed_at": "2026-09-11T12:00:00Z",
                "required": True,
                "status": "complete",
            }
        ],
        "facts": {
            "purpose": _fact("purpose", "Resume bounded work."),
            "implemented": [_fact("implemented", "A tested projector.")],
            "proposed": [_fact("proposed", "A generic projection capability.")],
            "current": [_fact("current", "D14-O1 is selected.")],
            "next_action": _fact("next", "Review the exact candidate."),
            "proposed_successor": {
                **_fact("successor", "Evaluate a later slice."),
                "admission_state": "proposed",
            },
            "blockers": [],
            "constraints": [_fact("constraint", "No provider write-back.")],
            "return_to_adoption": _fact("return", "Use actual launch gates."),
        },
    }


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


class OrientationGitGuardTests(unittest.TestCase):
    def test_bound_repository_subject_is_evidence_and_each_mismatch_is_stale(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            snapshot = _snapshot(root)
            matching = {"source_commit": "a" * 40, "source_tree": "b" * 40}
            current = orientation.build_manifest(
                snapshot, root, NOW, observed_repository_subject=matching
            )
            self.assertEqual("CURRENT", current["evaluation"]["status"])
            self.assertEqual(matching, current["evaluation"]["repository_subject"])

            for name in ("source_commit", "source_tree"):
                with self.subTest(name=name):
                    observed = dict(matching)
                    observed[name] = "c" * 40
                    stale = orientation.build_manifest(
                        snapshot,
                        root,
                        NOW,
                        observed_repository_subject=observed,
                    )
                    self.assertEqual("STALE", stale["evaluation"]["status"])
                    self.assertIn(
                        f"repository-subject-mismatch:{name}",
                        stale["evaluation"]["diagnostics"],
                    )

    def test_malformed_bound_repository_subject_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            snapshot = _snapshot(root)
            with self.assertRaisesRegex(
                orientation.OrientationError,
                "observed_repository_subject.source_commit",
            ):
                orientation.build_manifest(
                    snapshot,
                    root,
                    NOW,
                    observed_repository_subject={
                        "source_commit": "invalid",
                        "source_tree": "b" * 40,
                    },
                )

    def test_observer_rejects_repository_subdirectory_as_explicit_root(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "tracked.txt").write_text("tracked\n", encoding="utf-8")
            _git(root, "init", "-q")
            _git(root, "config", "user.email", "gnostoa-tests@example.test")
            _git(root, "config", "user.name", "Gnostoa Tests")
            _git(root, "add", "tracked.txt")
            _git(root, "commit", "-q", "-m", "fixture")
            child = root / "child"
            child.mkdir()
            with self.assertRaisesRegex(
                orientation.OrientationError,
                "repository root does not match Git top level",
            ):
                orientation.observe_repository_subject(child)

    def test_git_timeout_fails_closed(self) -> None:
        with patch.object(
            orientation.subprocess,
            "run",
            side_effect=subprocess.TimeoutExpired(cmd=["git"], timeout=5),
        ):
            with self.assertRaisesRegex(
                orientation.OrientationError,
                "cannot observe repository Git subject",
            ):
                orientation.observe_repository_subject(Path("."))

    def test_git_invocation_is_argument_vector_without_shell(self) -> None:
        completed = subprocess.CompletedProcess(
            args=["git"], returncode=0, stdout="a" * 40 + "\n", stderr=""
        )
        with patch.object(orientation.subprocess, "run", return_value=completed) as run:
            value = orientation._git_output(Path("/tmp/a path;not-shell"), "rev-parse", "HEAD")
        self.assertEqual("a" * 40, value)
        command = run.call_args.args[0]
        kwargs = run.call_args.kwargs
        self.assertIsInstance(command, list)
        self.assertEqual("git", command[0])
        self.assertEqual("/tmp/a path;not-shell", command[2])
        self.assertFalse(kwargs.get("shell", False))
        self.assertEqual(orientation.GIT_TIMEOUT_SECONDS, kwargs["timeout"])


if __name__ == "__main__":
    unittest.main()
