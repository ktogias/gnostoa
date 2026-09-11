from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "gnostoa_self_orientation", ROOT / "tasks/gnostoa_orientation.py"
)
assert SPEC is not None and SPEC.loader is not None
orientation = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(orientation)

NOW = "2026-09-11T13:00:00Z"


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _initialize_git(root: Path) -> tuple[str, str]:
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "gnostoa-tests@example.test")
    _git(root, "config", "user.name", "Gnostoa Tests")
    _git(root, "add", "source.md")
    _git(root, "commit", "-q", "-m", "fixture")
    return _git(root, "rev-parse", "HEAD"), _git(root, "rev-parse", "HEAD^{tree}")


def _fact(identity: str, text: str, source: str = "provider") -> dict[str, object]:
    return {"id": identity, "text": text, "source_ids": [source]}


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
            },
            {
                "id": "provider",
                "kind": "recorded-observation",
                "locator": "https://example.test/issues/14",
                "identity": "provider:14:admitted",
                "observed_at": "2026-09-11T12:00:00Z",
                "required": True,
                "status": "complete",
            },
        ],
        "facts": {
            "purpose": _fact("purpose", "Resume bounded work."),
            "implemented": [_fact("implemented", "A tested task projector.")],
            "proposed": [_fact("proposed", "A generic projection service.")],
            "current": [_fact("current", "Issue #14 / D14-O1 is selected.")],
            "next_action": _fact("next", "Review the exact candidate."),
            "proposed_successor": {
                **_fact("successor", "Evaluate component reuse."),
                "admission_state": "proposed",
            },
            "blockers": [_fact("blocker", "Full Phase D has not run.")],
            "constraints": [_fact("constraint", "No provider write-back.")],
            "return_to_adoption": _fact(
                "return", "Use the selected task's actual launch gates."
            ),
        },
    }


class OrientationTests(unittest.TestCase):
    def test_public_identity_annotation_does_not_relax_git_id_validation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            value = _snapshot(Path(directory))
            value["subject"]["_public_identity_note"] = "Public Git identities"
            orientation.validate_snapshot(value)
            value["subject"]["source_commit"] = "invalid"
            with self.assertRaises(orientation.OrientationError):
                orientation.validate_snapshot(value)

    def test_machine_and_markdown_carry_every_fact_and_source(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = orientation.build_manifest(_snapshot(root), root, NOW)
            markdown = orientation.render_markdown(manifest)
        for group in orientation.FACT_GROUPS:
            values = manifest["facts"][group]
            facts = values if isinstance(values, list) else [values]
            for fact in facts:
                self.assertIn(fact["id"], markdown)
                self.assertIn(orientation._markdown(fact["text"]), markdown)
                for source_id in fact["source_ids"]:
                    self.assertIn(source_id, markdown)
        self.assertIn(manifest["manifest_digest"], markdown)

    def test_reordered_input_is_byte_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            snapshot = _snapshot(root)
            reordered = json.loads(json.dumps(snapshot, sort_keys=True))
            first = orientation.build_manifest(snapshot, root, NOW)
            second = orientation.build_manifest(reordered, root, NOW)
        self.assertEqual(
            orientation.canonical_json(first), orientation.canonical_json(second)
        )
        self.assertEqual(
            orientation.render_markdown(first), orientation.render_markdown(second)
        )

    def test_two_current_items_remain_visible_and_conflicting(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            snapshot = _snapshot(root)
            snapshot["facts"]["current"].append(_fact("other", "Issue #237"))
            manifest = orientation.build_manifest(snapshot, root, NOW)
            markdown = orientation.render_markdown(manifest)
        self.assertEqual("CONFLICTING", manifest["evaluation"]["status"])
        self.assertIn(orientation._markdown("Issue #14"), markdown)
        self.assertIn(orientation._markdown("Issue #237"), markdown)

    def test_zero_current_is_valid_only_with_complete_fresh_sources(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            snapshot = _snapshot(root)
            snapshot["facts"]["current"] = []
            current = orientation.build_manifest(snapshot, root, NOW)
            snapshot["sources"][1]["status"] = "partial"
            partial = orientation.build_manifest(snapshot, root, NOW)
        self.assertEqual("CURRENT", current["evaluation"]["status"])
        self.assertEqual("INCOMPLETE", partial["evaluation"]["status"])
        self.assertIn(
            "No selected current item in complete, fresh declared coverage",
            orientation.render_markdown(current),
        )
        partial_markdown = orientation.render_markdown(partial)
        self.assertIn("prevents a complete no-selection claim", partial_markdown)
        self.assertNotIn(
            "No selected current item in complete, fresh declared coverage",
            partial_markdown,
        )

    def test_missing_partial_and_conflicting_sources_fail_closed(self) -> None:
        for source_status, expected in (
            ("missing", "INCOMPLETE"),
            ("partial", "INCOMPLETE"),
            ("conflicting", "CONFLICTING"),
        ):
            with (
                self.subTest(source_status=source_status),
                tempfile.TemporaryDirectory() as directory,
            ):
                root = Path(directory)
                snapshot = _snapshot(root)
                snapshot["sources"][1]["status"] = source_status
                manifest = orientation.build_manifest(snapshot, root, NOW)
                self.assertEqual(expected, manifest["evaluation"]["status"])

    def test_stale_future_and_invalid_times_do_not_establish_current(self) -> None:
        cases = (
            ("2026-09-10T12:00:00Z", NOW, "STALE"),
            ("2026-09-12T12:00:00Z", NOW, "INCOMPLETE"),
            ("invalid", NOW, "INCOMPLETE"),
        )
        for observed, evaluated, expected in cases:
            with (
                self.subTest(observed=observed),
                tempfile.TemporaryDirectory() as directory,
            ):
                root = Path(directory)
                snapshot = _snapshot(root)
                snapshot["sources"][1]["observed_at"] = observed
                manifest = orientation.build_manifest(snapshot, root, evaluated)
                self.assertEqual(expected, manifest["evaluation"]["status"])

    def test_local_digest_and_supplied_observation_are_compared(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            snapshot = _snapshot(root)
            snapshot["sources"][0]["identity"] = "sha256:" + "0" * 64
            local = orientation.build_manifest(snapshot, root, NOW)
            snapshot = _snapshot(root)
            supplied = orientation.build_manifest(
                snapshot, root, NOW, {"provider": "provider:changed"}
            )
        self.assertEqual("STALE", local["evaluation"]["status"])
        self.assertEqual("STALE", supplied["evaluation"]["status"])
        self.assertTrue(local["evaluation"]["diagnostics"])

    def test_declared_provider_identity_is_labelled_unverified(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = orientation.build_manifest(_snapshot(root), root, NOW)
        provider = next(
            item for item in manifest["sources"] if item["id"] == "provider"
        )
        self.assertEqual("recorded-not-authenticated", provider["identity_assurance"])

    def test_unreadable_or_oversized_local_source_never_claims_recomputation(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            snapshot = _snapshot(root)
            (root / "source.md").unlink()
            missing = orientation.build_manifest(snapshot, root, NOW)
            missing_source = missing["sources"][0]
            self.assertEqual("not-available", missing_source["identity_assurance"])
            self.assertNotIn("observed_identity", missing_source)
            (root / "source.md").write_bytes(b"x" * (orientation.MAX_SOURCE_BYTES + 1))
            oversized = orientation.build_manifest(snapshot, root, NOW)
            oversized_source = oversized["sources"][0]
        self.assertEqual("INCOMPLETE", missing["evaluation"]["status"])
        self.assertEqual("INCOMPLETE", oversized["evaluation"]["status"])
        self.assertEqual("not-available", oversized_source["identity_assurance"])

    def test_local_source_path_traversal_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            with self.assertRaisesRegex(
                orientation.OrientationError, "local source escapes repository root"
            ):
                orientation._within_root(root, "../outside.txt")

    def test_local_source_symlink_escape_is_rejected(self) -> None:
        with (
            tempfile.TemporaryDirectory() as directory,
            tempfile.TemporaryDirectory() as outside_directory,
        ):
            root = Path(directory).resolve()
            outside = Path(outside_directory).resolve() / "outside.txt"
            outside.write_text("outside\n", encoding="utf-8")
            (root / "escape-link").symlink_to(outside)
            with self.assertRaisesRegex(
                orientation.OrientationError, "local source escapes repository root"
            ):
                orientation._within_root(root, "escape-link")

    def test_required_groups_and_fact_source_references_are_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            snapshot = _snapshot(root)
            del snapshot["facts"]["blockers"]
            with self.assertRaisesRegex(orientation.OrientationError, "facts keys"):
                orientation.build_manifest(snapshot, root, NOW)
            snapshot = _snapshot(root)
            snapshot["facts"]["purpose"]["source_ids"] = ["absent"]
            with self.assertRaisesRegex(orientation.OrientationError, "unknown source"):
                orientation.build_manifest(snapshot, root, NOW)

    def test_malformed_types_and_duplicate_fact_ids_return_contract_errors(
        self,
    ) -> None:
        mutations = (
            lambda value: value["facts"]["purpose"].update({"source_ids": [{}]}),
            lambda value: value["sources"][0].update({"kind": []}),
            lambda value: value["sources"][0].update({"status": []}),
            lambda value: value["facts"]["implemented"][0].update({"id": "purpose"}),
        )
        for mutate in mutations:
            with (
                self.subTest(mutate=mutate),
                tempfile.TemporaryDirectory() as directory,
            ):
                root = Path(directory)
                snapshot = _snapshot(root)
                mutate(snapshot)
                with self.assertRaises(orientation.OrientationError):
                    orientation.build_manifest(snapshot, root, NOW)

    def test_freshness_window_is_foregrounded(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = orientation.build_manifest(_snapshot(root), root, NOW)
        markdown = orientation.render_markdown(manifest)
        self.assertIn("Freshness: `7200` seconds", markdown)

    def test_budget_counts_unicode_code_points_and_blocks_without_truncation(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            snapshot = _snapshot(root)
            manifest = orientation.build_manifest(snapshot, root, NOW)
            baseline = len(orientation._render_full_markdown(manifest))
            padding = 5000 - baseline
            self.assertGreater(padding, 0)
            snapshot["facts"]["blockers"][0]["text"] += "é" * padding
            exact = orientation.build_manifest(snapshot, root, NOW)
            self.assertEqual(5000, len(orientation.render_markdown(exact)))
            snapshot["facts"]["blockers"][0]["text"] += "é"
            over = orientation.build_manifest(snapshot, root, NOW)
            diagnostic = orientation.render_markdown(over)
        self.assertEqual("OVER_BUDGET", over["evaluation"]["status"])
        self.assertNotIn("Full Phase D", diagnostic)
        self.assertIn("5001", diagnostic)
        self.assertIn("5000", diagnostic)
        self.assertIn("Full Phase D", over["facts"]["blockers"][0]["text"])

    def test_cli_status_and_exit_codes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "snapshot.json"
            snapshot = _snapshot(root)
            commit, tree = _initialize_git(root)
            snapshot["subject"]["source_commit"] = commit
            snapshot["subject"]["source_tree"] = tree
            path.write_text(json.dumps(snapshot), encoding="utf-8")
            stdout, stderr = StringIO(), StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                result = orientation.main(
                    [
                        "--snapshot",
                        str(path),
                        "--repository-root",
                        str(root),
                        "--evaluated-at",
                        NOW,
                        "--format",
                        "json",
                    ]
                )
            self.assertEqual((0, ""), (result, stderr.getvalue()))
            self.assertEqual(
                "CURRENT", json.loads(stdout.getvalue())["evaluation"]["status"]
            )
            snapshot = _snapshot(root)
            snapshot["subject"]["source_commit"] = commit
            snapshot["subject"]["source_tree"] = tree
            snapshot["sources"][1]["status"] = "partial"
            path.write_text(json.dumps(snapshot), encoding="utf-8")
            with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
                self.assertEqual(
                    1,
                    orientation.main(
                        [
                            "--snapshot",
                            str(path),
                            "--repository-root",
                            str(root),
                            "--evaluated-at",
                            NOW,
                            "--format",
                            "markdown",
                        ]
                    ),
                )

    def test_live_cli_rejects_retained_projection_after_git_subject_drift(self) -> None:
        live_root = ROOT
        snapshot_path = live_root / "tasks/issue-14-orientation.json"
        if not snapshot_path.is_file():
            if (ROOT / ".gnostoa-source-files").is_file():
                self.skipTest(
                    "retained self-orientation snapshot is unavailable in packaged runtime"
                )
            self.fail(f"retained self-orientation snapshot missing: {snapshot_path}")
        snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
        observed = orientation.observe_repository_subject(live_root)
        mismatched = {
            name
            for name in ("source_commit", "source_tree")
            if snapshot["subject"][name] != observed[name]
        }
        self.assertTrue(
            mismatched, "retained snapshot must differ from the live checkout"
        )

        stdout, stderr = StringIO(), StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            result = orientation.main(
                [
                    "--snapshot",
                    str(snapshot_path),
                    "--repository-root",
                    str(live_root),
                    "--evaluated-at",
                    NOW,
                    "--format",
                    "json",
                ]
            )
        self.assertEqual("", stderr.getvalue())
        self.assertEqual(1, result)
        manifest = json.loads(stdout.getvalue())
        self.assertEqual("STALE", manifest["evaluation"]["status"])
        diagnostics = set(manifest["evaluation"]["diagnostics"])
        for name in ("source_commit", "source_tree"):
            diagnostic = f"repository-subject-mismatch:{name}"
            if name in mismatched:
                self.assertIn(diagnostic, diagnostics)
            else:
                self.assertNotIn(diagnostic, diagnostics)

    def test_live_cli_fails_closed_without_repository_subject(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            snapshot = _snapshot(root)
            path = root / "snapshot.json"
            path.write_text(json.dumps(snapshot), encoding="utf-8")
            with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
                result = orientation.main(
                    [
                        "--snapshot",
                        str(path),
                        "--repository-root",
                        str(root),
                        "--evaluated-at",
                        NOW,
                        "--format",
                        "json",
                    ]
                )
        self.assertNotEqual(0, result)

    def test_real_projection_is_routed_and_public_surface_excludes_changed_code(
        self,
    ) -> None:
        for path in (ROOT / "AGENTS.md", ROOT / "README.md", ROOT / "docs/roadmap.md"):
            self.assertIn(
                "tasks/issue-14-orientation.md", path.read_text(encoding="utf-8")
            )
        from tools.check_runtime_lock import PUBLIC_SURFACE_PATHS

        self.assertNotIn("tasks", PUBLIC_SURFACE_PATHS)
        self.assertTrue((ROOT / "tasks/issue-14-orientation.json").is_file())
        self.assertTrue((ROOT / "tasks/issue-14-orientation.md").is_file())
        agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("For a status or “what now?” request, stop there", agents)

    def test_open_adoption_questions_are_not_universal_or_current_task_blockers(
        self,
    ) -> None:
        snapshot = json.loads(
            (ROOT / "tasks/issue-14-orientation.json").read_text(encoding="utf-8")
        )
        manifest = orientation.build_manifest(snapshot, ROOT, "2026-09-11T10:55:00Z")
        markdown = orientation.render_markdown(manifest)
        self.assertIn("Open questions and task-specific blockers", markdown)
        self.assertIn("Neither is a prerequisite for D14\\-O1", markdown)
        self.assertIn("selected future task determines", markdown)


if __name__ == "__main__":
    unittest.main()
