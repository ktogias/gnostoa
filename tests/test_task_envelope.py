from __future__ import annotations

import hashlib
import json
import os
import tempfile
import unicodedata
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path

import yaml

from tools.cli import main as cli_main

ROOT = Path(__file__).resolve().parents[1]
BASE = "git:cda51dad6a719da43d8465a3f0f270021c357d96"
CANDIDATE = "git:1111111111111111111111111111111111111111"
DEPENDENCY = "sha256:2222222222222222222222222222222222222222222222222222222222222222"


def _envelope() -> dict[str, object]:
    return {
        "schema_version": "0.1",
        "task": {
            "id": "GNOSTOA/B2/P1",
            "objective": "Validate one bounded task envelope and current projection.",
            "owner": "team:gnostoa-maintainers",
            "change_class": "normative",
        },
        "scope": {
            "included": ["task envelope validation", "current projection"],
            "excluded": ["workflow engine", "provider authority"],
        },
        "state": {
            "status": "active",
            "completed": ["Bound Issue #24 and Decision 0016."],
            "next_action": "Review the focused implementation diff.",
            "blocker": None,
        },
        "identities": {
            "base": {"kind": "git-commit", "value": BASE},
            "dependencies": [
                {
                    "id": "issue-24",
                    "kind": "record-digest",
                    "value": DEPENDENCY,
                }
            ],
        },
        "references": {
            "decisions": [
                {
                    "id": "decision-0016",
                    "resource": (
                        "knowledge/decisions/"
                        "0016-evolve-human-agent-workflow-through-bounded-"
                        "self-hosted-slices.md"
                    ),
                }
            ],
            "evidence": [
                {
                    "id": "issue-24",
                    "resource": "https://github.com/ktogias/gnostoa/issues/24",
                }
            ],
        },
        "handoff": {
            "actor": "accountable maintainer",
            "read": ["this projection", "the focused diff"],
            "verify": ["one semantic choice", "container evidence"],
        },
        "recording": {
            "actor": "agent:test-fixture",
            "at": "2026-08-16T00:00:00Z",
        },
        "review": {
            "projection_characters": 5000,
            "owner_minutes": 20,
            "on_exceed": "block",
        },
        "checkpoint": {"sequence": 1, "previous": None},
    }


class TaskEnvelopeTests(unittest.TestCase):
    def _write(
        self, root: Path, value: dict[str, object], name: str = "task.yaml"
    ) -> Path:
        path = root / name
        path.write_text(
            yaml.safe_dump(value, sort_keys=False, allow_unicode=True),
            encoding="utf-8",
        )
        return path

    def _run(self, arguments: list[str]) -> tuple[int, str, str]:
        stdout = StringIO()
        stderr = StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            result = cli_main(arguments)
        return result, stdout.getvalue(), stderr.getvalue()

    def _current_arguments(self, path: Path) -> list[str]:
        return [
            "--envelope",
            str(path),
            "--repository-root",
            str(ROOT),
            "--candidate",
            CANDIDATE,
            "--observed-base",
            BASE,
            "--observed-dependency",
            f"issue-24={DEPENDENCY}",
        ]

    def test_valid_envelope_projects_one_deterministic_current_view(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = self._write(root, _envelope(), "first.yaml")
            reordered = json.loads(json.dumps(_envelope(), sort_keys=True))
            second = self._write(root, reordered, "second.yaml")

            first_result, first_output, first_error = self._run(
                ["task-project", *self._current_arguments(first)]
            )
            second_result, second_output, second_error = self._run(
                ["task-project", *self._current_arguments(second)]
            )

        self.assertEqual((0, ""), (first_result, first_error))
        self.assertEqual((0, ""), (second_result, second_error))
        self.assertEqual(first_output, second_output)
        self.assertIn("# Current task projection", first_output)
        self.assertIn("`GNOSTOA/B2/P1`", first_output)
        self.assertIn("Review the focused implementation diff.", first_output)
        self.assertEqual(1, first_output.count("## Next action"))
        self.assertRegex(first_output, r"sha256:[0-9a-f]{64}")
        self.assertIn(CANDIDATE, first_output)
        self.assertIn("decision-0016", first_output)
        self.assertIn("- evidence `issue-24`:", first_output)
        self.assertIn("accountable maintainer", first_output)
        self.assertIn("not refresh or mediate provider HEAD", first_output)
        self.assertIn(
            "grants no acceptance, integration or external effect", first_output
        )
        self.assertNotIn(directory, first_output)

    def test_invalid_state_combinations_are_rejected(self) -> None:
        cases = (
            ("blocked", None, "Resolve the blocker."),
            ("active", "Unexpected blocker", "Continue."),
            ("complete", None, "Still active."),
            ("unknown", None, "Continue."),
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for index, (status, blocker, next_action) in enumerate(cases):
                with self.subTest(status=status, blocker=blocker):
                    envelope = _envelope()
                    envelope["state"] = {
                        "status": status,
                        "completed": [],
                        "next_action": next_action,
                        "blocker": blocker,
                    }
                    path = self._write(root, envelope, f"invalid-{index}.yaml")
                    result, output, error = self._run(
                        [
                            "task-validate",
                            "--envelope",
                            str(path),
                            "--repository-root",
                            str(ROOT),
                        ]
                    )
                    self.assertEqual(1, result)
                    self.assertEqual("", error)
                    self.assertIn("ERROR:", output)

    def test_references_remain_links_not_duplicated_bodies(self) -> None:
        envelope = _envelope()
        references = envelope["references"]
        assert isinstance(references, dict)
        evidence = references["evidence"]
        assert isinstance(evidence, list)
        evidence[0]["body"] = "A copied transcript or evidence body."

        with tempfile.TemporaryDirectory() as directory:
            path = self._write(Path(directory), envelope)
            result, output, error = self._run(
                [
                    "task-validate",
                    "--envelope",
                    str(path),
                    "--repository-root",
                    str(ROOT),
                ]
            )

        self.assertEqual(1, result)
        self.assertEqual("", error)
        self.assertIn("Additional properties are not allowed", output)
        self.assertIn("body", output)

    def test_stale_identities_fail_closed_with_precise_diagnostics(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = self._write(Path(directory), _envelope())
            base_arguments = self._current_arguments(path)

            result, _, error = self._run(["task-project", *base_arguments])
            self.assertEqual((0, ""), (result, error))

            stale_base = [
                "wrong-base" if value == BASE else value for value in base_arguments
            ]
            result, output, _ = self._run(["task-project", *stale_base])
            self.assertEqual(1, result)
            self.assertIn("base identity mismatch", output)

            missing_dependency = base_arguments[:-2]
            result, output, _ = self._run(["task-project", *missing_dependency])
            self.assertEqual(1, result)
            self.assertIn("missing observed dependency: issue-24", output)

            changed_dependency = [
                "issue-24=changed" if value.startswith("issue-24=") else value
                for value in base_arguments
            ]
            result, output, _ = self._run(["task-project", *changed_dependency])
            self.assertEqual(1, result)
            self.assertIn("dependency identity mismatch: issue-24", output)

    def test_checkpoint_resume_is_idempotent_and_detects_conflict(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = self._write(Path(directory), _envelope())
            arguments = self._current_arguments(path)
            result, first, error = self._run(["task-project", *arguments])
            self.assertEqual((0, ""), (result, error))
            digest_line = next(
                line for line in first.splitlines() if line.startswith("- Checkpoint:")
            )
            digest = digest_line.split("`", 2)[1]

            result, resumed, error = self._run(
                [
                    "task-project",
                    *arguments,
                    "--expected-checkpoint",
                    digest,
                ]
            )
            self.assertEqual((0, ""), (result, error))
            self.assertEqual(first, resumed)

            changed = _envelope()
            changed_state = changed["state"]
            assert isinstance(changed_state, dict)
            changed_state["completed"] = ["A later deterministic checkpoint."]
            self._write(Path(directory), changed)
            result, output, _ = self._run(
                [
                    "task-project",
                    *arguments,
                    "--expected-checkpoint",
                    digest,
                ]
            )
            self.assertEqual(1, result)
            self.assertIn("checkpoint conflict", output)

            successor = _envelope()
            successor["checkpoint"] = {"sequence": 2, "previous": digest}
            self._write(Path(directory), successor)
            result, _, error = self._run(
                [
                    "task-project",
                    *arguments,
                    "--expected-previous-checkpoint",
                    digest,
                ]
            )
            self.assertEqual((0, ""), (result, error))

            result, output, _ = self._run(
                [
                    "task-project",
                    *arguments,
                    "--expected-previous-checkpoint",
                    "sha256:" + "f" * 64,
                ]
            )
            self.assertEqual(1, result)
            self.assertIn("previous checkpoint mismatch", output)

    def test_checkpoint_sequence_requires_the_matching_predecessor_shape(self) -> None:
        invalid = (
            {"sequence": 1, "previous": "sha256:" + "a" * 64},
            {"sequence": 2, "previous": None},
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for index, checkpoint in enumerate(invalid):
                with self.subTest(checkpoint=checkpoint):
                    envelope = _envelope()
                    envelope["checkpoint"] = checkpoint
                    path = self._write(root, envelope, f"checkpoint-{index}.yaml")
                    result, output, error = self._run(
                        [
                            "task-validate",
                            "--envelope",
                            str(path),
                            "--repository-root",
                            str(ROOT),
                        ]
                    )
                    self.assertEqual((1, ""), (result, error))
                    self.assertIn("checkpoint.previous", output)

    def test_candidate_is_immutable_and_projection_cannot_overwrite_envelope(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = self._write(Path(directory), _envelope())
            arguments = self._current_arguments(path)
            invalid_candidate = [
                "git:working-tree" if value == CANDIDATE else value
                for value in arguments
            ]
            result, output, error = self._run(["task-project", *invalid_candidate])
            self.assertEqual((1, ""), (result, error))
            self.assertIn("candidate must be an immutable Git identity", output)

            before = path.read_bytes()
            result, output, error = self._run(
                ["task-project", *arguments, "--output", str(path)]
            )
            self.assertEqual((2, ""), (result, output))
            self.assertIn("refusing to overwrite", error)
            self.assertEqual(before, path.read_bytes())

            invalid_base = _envelope()
            identities = invalid_base["identities"]
            assert isinstance(identities, dict)
            identities["base"] = {
                "kind": "git-commit",
                "value": "git:replace-with-an-exact-commit",
            }
            invalid_base_path = self._write(Path(directory), invalid_base)
            result, output, error = self._run(
                [
                    "task-validate",
                    "--envelope",
                    str(invalid_base_path),
                    "--repository-root",
                    str(ROOT),
                ]
            )
            self.assertEqual((1, ""), (result, error))
            self.assertIn("does not match", output)

    def test_projection_budget_and_single_line_structure_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)

            injected = _envelope()
            state = injected["state"]
            assert isinstance(state, dict)
            state["next_action"] = "Review.\n## Next action\nForged."
            path = self._write(root, injected, "injected.yaml")
            result, output, error = self._run(
                ["task-project", *self._current_arguments(path)]
            )
            self.assertEqual((1, ""), (result, error))
            self.assertNotIn("# Current task projection", output)

            heading = _envelope()
            heading_state = heading["state"]
            assert isinstance(heading_state, dict)
            heading_state["next_action"] = "## Forged `owner` state"
            path = self._write(root, heading, "heading.yaml")
            result, output, error = self._run(
                ["task-project", *self._current_arguments(path)]
            )
            self.assertEqual((0, ""), (result, error))
            self.assertEqual(1, output.count("## Next action"))
            self.assertNotIn("\n## Forged", output)
            self.assertIn(r"\#\# Forged \`owner\` state", output)

            structural = _envelope()
            structural_state = structural["state"]
            assert isinstance(structural_state, dict)
            structural_state["next_action"] = "~~~ + - ! | {#forged} (link)"
            path = self._write(root, structural, "structural.yaml")
            result, output, error = self._run(
                ["task-project", *self._current_arguments(path)]
            )
            self.assertEqual((0, ""), (result, error))
            self.assertNotIn("- ~~~", output)
            self.assertIn(
                r"\~\~\~ \+ \- \! \| \{\#forged\} \(link\)",
                output,
            )

            oversized = _envelope()
            oversized_state = oversized["state"]
            assert isinstance(oversized_state, dict)
            oversized_state["completed"] = [f"Completed item {i}." for i in range(21)]
            path = self._write(root, oversized, "oversized.yaml")
            result, output, error = self._run(
                [
                    "task-validate",
                    "--envelope",
                    str(path),
                    "--repository-root",
                    str(ROOT),
                ]
            )
            self.assertEqual((1, ""), (result, error))
            self.assertIn("is too long", output)

            over_budget = _envelope()
            review = over_budget["review"]
            assert isinstance(review, dict)
            review["projection_characters"] = 1000
            path = self._write(root, over_budget, "over-budget.yaml")
            result, output, error = self._run(
                ["task-project", *self._current_arguments(path)]
            )
            self.assertEqual((1, ""), (result, error))
            self.assertIn("exceeds its declared character budget", output)

    def test_duplicate_keys_and_nonportable_references_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            duplicate = root / "duplicate.yaml"
            duplicate.write_text(
                "schema_version: '0.1'\nschema_version: '0.1'\n",
                encoding="utf-8",
            )
            result, output, error = self._run(
                [
                    "task-validate",
                    "--envelope",
                    str(duplicate),
                    "--repository-root",
                    str(ROOT),
                ]
            )
            self.assertEqual((2, ""), (result, output))
            self.assertIn("Duplicate YAML key", error)

            for index, resource in enumerate(
                (
                    "/home/user/private.md",
                    "file:///home/user/private.md",
                    "C:\\Users\\private.md",
                )
            ):
                with self.subTest(resource=resource):
                    envelope = _envelope()
                    references = envelope["references"]
                    assert isinstance(references, dict)
                    references["evidence"] = [
                        {"id": "nonportable", "resource": resource}
                    ]
                    path = self._write(root, envelope, f"reference-{index}.yaml")
                    result, output, error = self._run(
                        [
                            "task-validate",
                            "--envelope",
                            str(path),
                            "--repository-root",
                            str(ROOT),
                        ]
                    )
                    self.assertEqual((1, ""), (result, error))
                    self.assertRegex(output, r"not a portable|unsupported external")

            envelope = _envelope()
            references = envelope["references"]
            assert isinstance(references, dict)
            decisions = references["decisions"]
            assert isinstance(decisions, list)
            decisions[0]["resource"] += "#decision"
            path = self._write(root, envelope, "fragment.yaml")
            result, output, error = self._run(
                [
                    "task-validate",
                    "--envelope",
                    str(path),
                    "--repository-root",
                    str(ROOT),
                ]
            )
            self.assertEqual((0, ""), (result, error))
            self.assertIn("task envelope is valid", output)

    def test_cli_contract_and_exit_codes(self) -> None:
        result, output, error = self._run(["--help"])
        self.assertEqual((0, ""), (result, error))
        self.assertIn("task-validate", output)
        self.assertIn("task-project", output)

        with tempfile.TemporaryDirectory() as directory:
            malformed = Path(directory) / "malformed.yaml"
            malformed.write_text("task: [\n", encoding="utf-8")
            result, output, error = self._run(
                [
                    "task-validate",
                    "--envelope",
                    str(malformed),
                    "--repository-root",
                    str(ROOT),
                ]
            )
        self.assertEqual(2, result)
        self.assertEqual("", output)
        self.assertIn("ERROR:", error)
        self.assertNotIn("Traceback", error)

    def test_declared_repository_root_resolves_references_independently_of_cwd(
        self,
    ) -> None:
        """`self-check` runs from any working directory, including the packaged
        runtime image, so required evidence must never depend on the caller's
        current directory."""

        envelope = _envelope()
        with tempfile.TemporaryDirectory() as directory:
            unrelated = Path(directory)
            path = self._write(unrelated, envelope, "cwd-independent.yaml")
            previous = Path.cwd()
            os.chdir(unrelated)
            try:
                declared = self._run(
                    [
                        "task-validate",
                        "--envelope",
                        str(path),
                        "--repository-root",
                        str(ROOT),
                    ]
                )
                inherited = self._run(["task-validate", "--envelope", str(path)])
            finally:
                os.chdir(previous)

        result, output, error = declared
        self.assertEqual((0, ""), (result, error))
        self.assertIn("task envelope is valid", output)

        result, output, error = inherited
        self.assertEqual((1, ""), (result, error))
        self.assertIn("reference does not exist", output)

    def test_recorded_issue_digest_reproduces_without_any_transformation(self) -> None:
        """`github-issue-body-utf8-sha256-v1` covers the exact API body bytes.

        The fixture stores the provider response as JSON so that every line
        break inside the body is an escape sequence. A checkout that rewrites
        the file's line endings therefore cannot change the parsed body, and
        the digest recorded for Issue #24 stays reproducible offline.
        """

        envelope = yaml.safe_load(
            (ROOT / "tasks" / "issue-24-b2-p1.yaml").read_text(encoding="utf-8")
        )
        declared = next(
            item
            for item in envelope["identities"]["dependencies"]
            if item["id"] == "issue-24"
        )
        self.assertEqual("github-issue-body-utf8-sha256-v1", declared["kind"])

        fixture = (ROOT / "tests" / "fixtures" / "github-issue-24.json").read_bytes()
        text = json.loads(fixture)["body"]
        self.assertEqual(
            "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest(),
            declared["value"],
        )

        # The stored bytes must survive checkout line-ending normalization.
        self.assertNotIn(b"\r", fixture)
        normalized = json.loads(fixture.replace(b"\n", b"\r\n"))["body"]
        self.assertEqual(text, normalized)

        for label, variant in (
            ("stripped trailing newline", text.rstrip("\n")),
            ("added trailing newline", text + "\n"),
            ("windows line endings", text.replace("\n", "\r\n")),
        ):
            with self.subTest(variant=label):
                self.assertNotEqual(
                    declared["value"],
                    "sha256:" + hashlib.sha256(variant.encode("utf-8")).hexdigest(),
                )

        # The recorded body is ASCII, so pin the no-normalization clause on
        # input where composition actually changes the bytes.
        composed = "café\n"
        self.assertNotEqual(
            hashlib.sha256(composed.encode("utf-8")).hexdigest(),
            hashlib.sha256(
                unicodedata.normalize("NFD", composed).encode("utf-8")
            ).hexdigest(),
        )

    def test_b2_dogfood_envelope_validates_against_recorded_observations(self) -> None:
        path = ROOT / "tasks" / "issue-24-b2-p1.yaml"
        envelope = yaml.safe_load(path.read_text(encoding="utf-8"))
        dependencies = envelope["identities"]["dependencies"]
        decision = next(item for item in dependencies if item["id"] == "decision-0016")
        decision_path = (
            ROOT
            / "knowledge"
            / "decisions"
            / "0016-evolve-human-agent-workflow-through-bounded-self-hosted-slices.md"
        )
        self.assertEqual(
            "sha256:" + hashlib.sha256(decision_path.read_bytes()).hexdigest(),
            decision["value"],
        )
        result, output, error = self._run(
            [
                "task-project",
                "--envelope",
                str(path),
                "--repository-root",
                str(ROOT),
                "--candidate",
                CANDIDATE,
                "--observed-base",
                "git:cda51dad6a719da43d8465a3f0f270021c357d96",
                "--observed-dependency",
                (
                    "decision-0016=sha256:"
                    "2ee58de9f91f2bdd23c56da2389bd7130072a142ba43080c8bbca710dbd1896c"  # pragma: allowlist secret
                ),
                "--observed-dependency",
                (
                    "issue-24=sha256:"
                    "adb02bc2aa254e97ea9fd931da0ae467b640a031fdb9143b255a74f199b5c5c6"  # pragma: allowlist secret
                ),
            ]
        )
        self.assertEqual((0, ""), (result, error))
        self.assertIn("`GNOSTOA/B2/P1`", output)
        self.assertIn("Review the compact current projection", output)


if __name__ == "__main__":
    unittest.main()
