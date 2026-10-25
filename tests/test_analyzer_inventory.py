"""The diagnostic inventory as a shadow analyzer readback (#389 A0-MP1 slice 2).

A no-secret job of the protected readback workflow runs main's inventory over a
Pull Request head fetched as data, adapts it into two readbacks of the existing
contract, and uploads them for qualification. Nothing here changes the bundle, the
merge-evidence map or the declaration: those are slice 3's (#389 6392516998).
"""

from __future__ import annotations

import contextlib
import hashlib
import importlib
import importlib.util
import io
import json
import os
import tempfile
import unittest
from collections.abc import Mapping
from pathlib import Path
from typing import Any
from unittest.mock import patch

import yaml

from tests.quality_evidence_fixtures import _DiagnosticInventoryFixture
from tools.analyzer_readback import AnalyzerReadbackError, parse_readback
from tools.review_model import canonical_digest

ROOT = Path(__file__).resolve().parents[1]
RUNNER_PATH = ROOT / "ci" / "analyzer_readback.py"
WORKFLOW_PATH = ROOT / ".github" / "workflows" / "analyzer-readback.yml"
REPOSITORY = "ktogias/gnostoa"
PULL = 459
OBSERVED = "2026-10-25T03:00:00Z"
OTHER = "b" * 40
# What the job does before the collector starts (checkout, setup, the locked install,
# the base lookup, the fetch) and after it (the scan, the upload). This repository's
# readback job took 13 s end to end; its locked installs take 9 to 13 s with a pip
# cache, which this job lacks.
JOB_MARGIN_SECONDS = 300
API = "https://api.github.com"


def _adapter() -> Any:
    return importlib.import_module("tools.analyzer_inventory")


def _runner() -> Any:
    """The readback's own runner, whose `inventory` command the job runs (#389
    6392658842: the admitted owner, never a new entry point)."""
    spec = importlib.util.spec_from_file_location(
        "gnostoa_analyzer_readback_inventory", RUNNER_PATH
    )
    if spec is None or spec.loader is None:
        raise ModuleNotFoundError(f"no runner at {RUNNER_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _ids(findings: list[Mapping[str, Any]]) -> set[str]:
    return {finding["id"] for finding in findings}


class _InventoryReadbackFixture(_DiagnosticInventoryFixture):
    """A real inventory of the fixture repository, its head changed in one test file
    whose unchanged lines carry findings."""

    def _changed_head(self) -> str:
        path = self.root / "tests" / "test_sample.py"
        path.write_text(
            path.read_text(encoding="utf-8").replace(
                '"""Diagnostic fixture: test side."""',
                '"""Diagnostic fixture: test side, changed."""',
                1,
            ),
            encoding="utf-8",
        )
        self._git("commit", "-q", "-am", "head")
        return self._head()

    def _readbacks(self, record: Mapping[str, Any], head: str) -> list[dict]:
        return _adapter().readbacks(
            record,
            repository=REPOSITORY,
            pull_number=PULL,
            requested_head=head,
            observed_at=OBSERVED,
        )

    @staticmethod
    def _complete(record: dict) -> dict:
        """The record as if its composite were COMPLETE: no real collection can be
        while its source binding is UNVERIFIED, so this is the adapter's own case."""
        count = len(record["findings"])
        return {
            **record,
            "coverage": {
                "status": "COMPLETE",
                "pages": 1,
                "count": count,
                "total": count,
            },
        }


class InventoryReadbackTests(_InventoryReadbackFixture):
    """The adapter: every obtained finding in exactly one readback, and no readback
    claiming more than the inventory's composite (the PAO's R1, R2 and R4 on #389
    6387305292)."""

    def test_every_obtained_finding_is_in_exactly_one_readback(self) -> None:
        head = self._changed_head()
        record = self._inventory(base=self.base, expected_revision=head)
        diff, full = self._readbacks(record, head)
        self.assertEqual(("DIFF", "FULL"), (diff["scope"], full["scope"]))
        changed = set(record["scope"]["diff"]["changed_paths"])
        self.assertEqual(
            {f["id"] for f in record["findings"] if f["path"] in changed},
            _ids(diff["findings"]),
        )
        self.assertEqual(
            _ids(record["findings"]), _ids(diff["findings"]) | _ids(full["findings"])
        )
        self.assertFalse(_ids(diff["findings"]) & _ids(full["findings"]))
        # Fix-on-touch: a finding on an unchanged line of a changed file is the DIFF
        # readback's, never dropped for its line (the PAO's R1).
        untouched = self._find(
            record, "ruff", "SLF001", "tests/test_sample.py", self.lines["private"]
        )
        self.assertEqual([False], [f["native"]["in_diff"] for f in untouched])
        self.assertIn(untouched[0]["id"], _ids(diff["findings"]))

    def test_a_readback_never_claims_more_than_the_composite(self) -> None:
        head = self._changed_head()
        record = self._inventory(base=self.base, expected_revision=head)
        self.assertEqual("INCOMPLETE", record["coverage"]["status"])
        for readback in self._readbacks(record, head):
            with self.subTest(scope=readback["scope"]):
                self.assertEqual("AMBIGUOUS", readback["completeness"])
                self.assertEqual("INCOMPLETE", readback["coverage"]["status"])
                self.assertEqual(
                    record["coverage"]["reason"], readback["coverage"]["reason"]
                )
                # Its negatives stay listed while it is incomplete (M17).
                self.assertEqual(
                    len(readback["findings"]), readback["coverage"]["count"]
                )
                self.assertEqual(readback, parse_readback(readback))

    def test_a_complete_composite_gives_complete_readbacks_of_their_own_kind(
        self,
    ) -> None:
        head = self._changed_head()
        record = self._complete(self._inventory(base=self.base, expected_revision=head))
        diff, full = self._readbacks(record, head)
        self.assertEqual(
            [("DIFF_LOCAL", "COMPLETE"), ("FULL_RUN", "COMPLETE")],
            [(r["completeness"], r["coverage"]["status"]) for r in (diff, full)],
        )
        for readback in (diff, full):
            self.assertEqual(head, readback["observed_head"])
            self.assertEqual(readback, parse_readback(readback))

    def test_without_a_comparison_every_finding_is_the_full_readback_s(self) -> None:
        head = self._changed_head()
        record = self._complete(self._inventory(expected_revision=head))
        self.assertIsNone(record["scope"]["diff"])
        diff, full = self._readbacks(record, head)
        self.assertEqual("AMBIGUOUS", diff["completeness"])
        self.assertEqual("INCOMPLETE", diff["coverage"]["status"])
        self.assertIn("comparison", diff["coverage"]["reason"])
        self.assertEqual([], diff["findings"])
        self.assertEqual("COMPLETE", full["coverage"]["status"])
        self.assertEqual(_ids(record["findings"]), _ids(full["findings"]))

    def test_another_commit_never_reads_as_the_requested_head(self) -> None:
        head = self._changed_head()
        record = self._complete(self._inventory(base=self.base, expected_revision=head))
        for readback in self._readbacks(record, OTHER):
            with self.subTest(scope=readback["scope"]):
                self.assertEqual("INCOMPLETE", readback["coverage"]["status"])
                self.assertEqual(OTHER, readback["requested_head"])
                self.assertEqual(head, readback["observed_head"])
                # The run seen is another subject's (Q on #460), as the provider
                # adapters say of a head they did not observe.
                self.assertEqual("UNKNOWN", readback["run_state"])

    def test_the_requested_head_s_run_is_complete_whatever_its_coverage(self) -> None:
        # The run finished and wrote its record; whether it covered everything is
        # the coverage's to say, not the run's (Q on #460).
        head = self._changed_head()
        record = self._inventory(base=self.base, expected_revision=head)
        for readback in self._readbacks(record, head):
            with self.subTest(scope=readback["scope"]):
                self.assertEqual("INCOMPLETE", readback["coverage"]["status"])
                self.assertEqual("COMPLETE", readback["run_state"])

    def test_the_readbacks_name_the_inventory_they_came_from(self) -> None:
        head = self._changed_head()
        record = self._inventory(base=self.base, expected_revision=head)
        for readback in self._readbacks(record, head):
            with self.subTest(scope=readback["scope"]):
                self.assertEqual("gnostoa-inventory", readback["provider"])
                self.assertEqual("gnostoa-diagnostic-inventory/v3", readback["adapter"])
                self.assertEqual(canonical_digest(record), readback["analysis_id"])
                self.assertEqual(
                    record["configuration"]["profile"]["digest"],
                    readback["native"]["profile"],
                )
                self.assertEqual("UNVERIFIED", readback["native"]["source_binding"])

    def test_a_record_of_another_schema_is_refused(self) -> None:
        head = self._changed_head()
        record = self._inventory(base=self.base, expected_revision=head)
        with self.assertRaises(AnalyzerReadbackError):
            self._readbacks(
                {**record, "schema": "gnostoa-diagnostic-inventory/v2"}, head
            )

    def test_an_inventory_that_was_not_written_reads_unavailable(self) -> None:
        readbacks = _adapter().unavailable(
            repository=REPOSITORY,
            pull_number=PULL,
            requested_head=OTHER,
            observed_at=OBSERVED,
            reason="QualityEvidenceError",
        )
        self.assertEqual(["DIFF", "FULL"], [r["scope"] for r in readbacks])
        for readback in readbacks:
            with self.subTest(scope=readback["scope"]):
                self.assertEqual("READBACK_UNAVAILABLE", readback["completeness"])
                self.assertEqual("ERROR", readback["coverage"]["status"])
                self.assertEqual([], readback["findings"])
                self.assertEqual(readback, parse_readback(readback))


class _PullRequestReader:
    """GitHub for the runner: one Pull Request and its comparison with its base."""

    def __init__(self, head: str, base: str, merge_base: str | None) -> None:
        self.calls: list[str] = []
        comparison = (
            {} if merge_base is None else {"merge_base_commit": {"sha": merge_base}}
        )
        self.answers = {
            f"{API}/repos/{REPOSITORY}/pulls/{PULL}": {
                "head": {"sha": head},
                "base": {"sha": base, "ref": "main"},
            },
            f"{API}/repos/{REPOSITORY}/compare/{base}...{head}?per_page=1": comparison,
        }

    def get(self, url: str) -> tuple[Any, Mapping[str, str]]:
        self.calls.append(url)
        return self.answers[url], {}


class InventoryRunnerTests(_InventoryReadbackFixture):
    """The runner the no-secret job executes from main's checkout."""

    def test_the_base_is_the_merge_base_and_its_branch_tip_is_kept(self) -> None:
        # A diverged base: its branch moved past the merge base.
        runner = _runner()
        reader = _PullRequestReader(head=self.base, base=OTHER, merge_base="c" * 40)
        self.assertEqual(
            (OTHER, "c" * 40),
            runner.inventory_base(
                reader,
                repository=REPOSITORY,
                pull_number=PULL,
                requested_head=self.base,
            ),
        )

    def test_a_comparison_that_names_no_merge_base_is_refused(self) -> None:
        runner = _runner()
        reader = _PullRequestReader(head=self.base, base=OTHER, merge_base=None)
        with self.assertRaises(runner.RunnerError):
            runner.inventory_base(
                reader,
                repository=REPOSITORY,
                pull_number=PULL,
                requested_head=self.base,
            )

    def test_a_head_the_pull_request_no_longer_has_is_refused(self) -> None:
        runner = _runner()
        reader = _PullRequestReader(head=OTHER, base="d" * 40, merge_base="c" * 40)
        with self.assertRaises(runner.RunnerError):
            runner.inventory_base(
                reader,
                repository=REPOSITORY,
                pull_number=PULL,
                requested_head=self.base,
            )
        self.assertEqual(1, len(reader.calls))

    def test_collect_writes_the_inventory_and_its_two_readbacks(self) -> None:
        runner = _runner()
        head = self._changed_head()
        # The fixture's fake producers run only under its own output directory.
        out = self.output
        with patch("tools.quality_evidence._bounded_run", side_effect=self._fake_run):
            path = runner.inventory_collect(
                self.root,
                out,
                repository=REPOSITORY,
                pull_number=PULL,
                requested_head=head,
                base_tip=OTHER,
                base=self.base,
                observed_at=OBSERVED,
            )
        document = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual("gnostoa-inventory-readback/v1", document["schema"])
        self.assertEqual(
            (REPOSITORY, PULL, head, OTHER, self.base),
            (
                document["repository"],
                document["pull_number"],
                document["requested_head"],
                document["base_tip"],
                document["base"],
            ),
        )
        inventory = out / document["inventory"]["file"]
        self.assertEqual(
            hashlib.sha256(inventory.read_bytes()).hexdigest(),
            document["inventory"]["sha256"],
        )
        record = json.loads(inventory.read_text(encoding="utf-8"))
        self.assertEqual(head, record["source"]["revision"])
        self.assertEqual(["DIFF", "FULL"], [r["scope"] for r in document["readbacks"]])
        for readback in document["readbacks"]:
            self.assertEqual(readback, parse_readback(readback))
            self.assertEqual(canonical_digest(record), readback["analysis_id"])

    def test_collect_never_overwrites_a_document(self) -> None:
        runner = _runner()
        head = self._changed_head()
        # The fixture's fake producers run only under its own output directory.
        out = self.output
        options = {
            "repository": REPOSITORY,
            "pull_number": PULL,
            "requested_head": head,
            "base_tip": OTHER,
            "base": self.base,
            "observed_at": OBSERVED,
        }
        with patch("tools.quality_evidence._bounded_run", side_effect=self._fake_run):
            runner.inventory_collect(self.root, out, **options)
            with self.assertRaises(runner.RunnerError):
                runner.inventory_collect(self.root, out, **options)

    def _in_temporary(self, output: Path):
        """The patches that make `collect`'s temporary directory `output`'s parent,
        as the workflow's TMPDIR does, so it writes under `output`."""
        output.parent.mkdir(parents=True, exist_ok=True)
        return (
            patch.dict(os.environ, {"TMPDIR": str(output.parent)}),
            patch.object(tempfile, "tempdir", None),
        )

    def test_an_inventory_refusal_is_recorded_and_fails_the_run(self) -> None:
        runner = _runner()
        head = self._changed_head()
        out = Path(self.directory.name) / "runner-temp" / "gnostoa-inventory"
        environment, tempdir = self._in_temporary(out)
        refusal = self.module.QualityEvidenceError("budget: a fixture refusal")
        argv = [
            "inventory",
            "collect",
            "--repository",
            REPOSITORY,
            "--pull-number",
            str(PULL),
            "--head",
            head,
            "--base-tip",
            OTHER,
            "--base",
            self.base,
        ]
        cwd = os.getcwd()
        os.chdir(self.root)
        self.addCleanup(os.chdir, cwd)
        with (
            environment,
            tempdir,
            patch(
                "tools.quality_evidence.collect_diagnostic_inventory",
                side_effect=refusal,
            ),
            contextlib.redirect_stderr(io.StringIO()),
        ):
            status = runner.main(argv)
        self.assertEqual(1, status)
        document = json.loads(
            (out / "gnostoa-inventory-readback.json").read_text(encoding="utf-8")
        )
        self.assertIsNone(document["inventory"])
        for readback in document["readbacks"]:
            self.assertEqual("READBACK_UNAVAILABLE", readback["completeness"])
            self.assertEqual("QualityEvidenceError", readback["coverage"]["reason"])

    def _main_collect(self, head: str, temporary: str = "runner-temp") -> int:
        argv = [
            "inventory",
            "collect",
            "--repository",
            REPOSITORY,
            "--pull-number",
            str(PULL),
            "--head",
            head,
            "--base-tip",
            OTHER,
            "--base",
            self.base,
        ]
        cwd = os.getcwd()
        os.chdir(self.root)
        self.addCleanup(os.chdir, cwd)
        # The fixture's fake producers run only under its own output directory, so
        # that is where the runner's temporary directory puts it.
        self.output = Path(self.directory.name) / temporary / "gnostoa-inventory"
        environment, tempdir = self._in_temporary(self.output)
        with (
            environment,
            tempdir,
            patch("tools.quality_evidence._bounded_run", side_effect=self._fake_run),
            contextlib.redirect_stderr(io.StringIO()),
        ):
            return _runner().main(argv)

    def test_a_written_inventory_whose_readbacks_fail_is_recorded_and_fails(
        self,
    ) -> None:
        # Q on #460: an inventory that was written but cannot be read back, by the
        # adapter or as JSON, is recorded by its type and fails the run, as a
        # refused one does.
        head = self._changed_head()
        for case, failure in enumerate(
            (
                AnalyzerReadbackError("a fixture refusal"),
                json.JSONDecodeError("a fixture decode", "", 0),
            )
        ):
            with self.subTest(failure=type(failure).__name__):
                # Each case collects into a temporary directory of its own, so none
                # starts with the files of the one before (Revix on #460).
                temporary = f"runner-temp-{case}"
                self.assertFalse((Path(self.directory.name) / temporary).exists())
                with patch("tools.analyzer_inventory.readbacks", side_effect=failure):
                    status = self._main_collect(head, temporary)
                self.assertEqual(1, status)
                document = json.loads(
                    (self.output / "gnostoa-inventory-readback.json").read_text(
                        encoding="utf-8"
                    )
                )
                self.assertIsNotNone(document["inventory"])
                for readback in document["readbacks"]:
                    self.assertEqual("READBACK_UNAVAILABLE", readback["completeness"])
                    self.assertEqual(
                        type(failure).__name__, readback["coverage"]["reason"]
                    )

    def test_a_token_only_the_inventory_file_holds_is_never_uploaded(self) -> None:
        # Revix on #460: the inventory is uploaded beside the document, so its own
        # bytes are checked too. The probe names a tracked file with no finding, so
        # only the inventory's scope and argv carry it, never a readback.
        runner = _runner()
        probe = "inventoryprobe" + "7" * 12
        (self.root / "tools" / f"{probe}.py").write_text(
            "VALUE = 1\n", encoding="utf-8"
        )
        self._git("add", "-A")
        self._git("commit", "-q", "-m", "head")
        head = self._head()
        with (
            patch.dict(os.environ, {"GITHUB_TOKEN": probe}),
            patch("tools.quality_evidence._bounded_run", side_effect=self._fake_run),
            self.assertRaises(runner.RunnerError),
        ):
            runner.inventory_collect(
                self.root,
                self.output,
                repository=REPOSITORY,
                pull_number=PULL,
                requested_head=head,
                base_tip=OTHER,
                base=self.base,
                observed_at=OBSERVED,
            )
        self.assertFalse((self.output / "gnostoa-inventory-readback.json").exists())

    def test_only_the_named_inventory_is_uploaded(self) -> None:
        # CodeAnt on #460: the run directory can hold more than the inventory, the
        # producers' raw reports and a staged source the collector could not remove,
        # and none of it is published (Decision 0118: the inventory and the document).
        runner = _runner()
        head = self._changed_head()
        real = self.module.collect_diagnostic_inventory
        left: list[Path] = []

        def leaving(*args, **kwargs):
            written = real(*args, **kwargs)
            source = written.parent / "source" / "tools"
            source.mkdir(parents=True)
            (source / "left.py").write_text("VALUE = 1\n", encoding="utf-8")
            (written.parent / "diagnostic-echo.txt").write_text("{}", encoding="utf-8")
            left.append(written)
            return written

        with (
            patch("tools.quality_evidence._bounded_run", side_effect=self._fake_run),
            patch("tools.quality_evidence.collect_diagnostic_inventory", leaving),
        ):
            path = runner.inventory_collect(
                self.root,
                self.output,
                repository=REPOSITORY,
                pull_number=PULL,
                requested_head=head,
                base_tip=OTHER,
                base=self.base,
                observed_at=OBSERVED,
            )
        document = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual([left[0].resolve()], runner._uploaded_files(self.output))
        self.assertEqual(
            left[0].resolve(), (self.output / document["inventory"]["file"]).resolve()
        )

    def test_a_token_split_across_scan_chunks_is_found(self) -> None:
        # cubic on #460: the uploads are scanned in bounded chunks, never whole, so a
        # token across a chunk boundary must still be found.
        runner = _runner()
        probe = "inventoryprobe" + "7" * 12
        folder = self.output / "diagnostic-run"
        folder.mkdir(parents=True)
        (folder / "diagnostic-inventory.json").write_text(
            "x" * 5 + probe + "y" * 9, encoding="utf-8"
        )
        with self.assertRaises(runner.RunnerError):
            runner._assert_uploads_secret_free(self.output, [probe], chunk=8)

    def test_a_file_holds_no_needle_when_there_is_none(self) -> None:
        # Q on #460: the chunk reader stands on its own, with no needle to find.
        runner = _runner()
        (self.output / "run").mkdir(parents=True)
        report = self.output / "run" / "report.json"
        report.write_text("z" * 40, encoding="utf-8")
        self.assertIs(False, runner._holds_any(report, [], 8))

    def test_a_link_in_the_uploaded_directory_is_refused(self) -> None:
        # Claude on #460: the pinned upload-artifact follows links
        # (followSymbolicLinks: true in its search), so a link would publish a target
        # the scan never read. An uploaded inventory reached through a link, as the
        # file or as its run directory, is refused, with or without a token.
        runner = _runner()
        outside = Path(self.directory.name) / "outside"
        outside.mkdir()
        (outside / "diagnostic-inventory.json").write_text("{}", encoding="utf-8")
        (self.output / "diagnostic-file").mkdir(parents=True)
        for link, target in (
            (
                self.output / "diagnostic-file" / "diagnostic-inventory.json",
                outside / "diagnostic-inventory.json",
            ),
            (self.output / "diagnostic-dir", outside),
        ):
            link.symlink_to(target)
            for secrets in ([], ["inventoryprobe"]):
                with (
                    self.subTest(link=link.name, secrets=secrets),
                    self.assertRaises(runner.RunnerError),
                ):
                    runner._assert_uploads_secret_free(self.output, secrets)
            link.unlink()
        # A link the step's pattern does not match is never uploaded.
        (self.output / "diagnostic-file" / "raw-link").symlink_to(outside)
        self.assertEqual([], runner._uploaded_files(self.output))

    def test_a_scan_without_the_token_reads_no_file_whole(self) -> None:
        # Revix on #460: every read asks for one chunk, never the whole file.
        runner = _runner()
        (self.output / "diagnostic-run").mkdir(parents=True)
        (self.output / "diagnostic-run" / "diagnostic-inventory.json").write_text(
            "z" * 40, encoding="utf-8"
        )
        sizes: list[object] = []
        real_open = Path.open

        def recording(path, *args, **kwargs):
            handle = real_open(path, *args, **kwargs)
            read = handle.read

            def sized(*size):
                sizes.append(size)
                return read(*size)

            handle.read = sized
            return handle

        with patch.object(Path, "open", recording):
            runner._assert_uploads_secret_free(self.output, ["inventoryprobe"], chunk=8)
        self.assertTrue(sizes)
        self.assertEqual({(8,)}, set(sizes))

    def test_an_upload_the_document_does_not_name_is_refused(self) -> None:
        # What the step's pattern matches must be exactly the inventory the document
        # names: neither a second match nor none, as for a run directory the scan
        # cannot list, whose inventory it would not see (Revix and CodeAnt on #460).
        runner = _runner()
        head = self._changed_head()
        real = self.module.collect_diagnostic_inventory

        def doubling(*args, **kwargs):
            written = real(*args, **kwargs)
            other = written.parent.parent / "diagnostic-other"
            other.mkdir()
            (other / written.name).write_text("{}", encoding="utf-8")
            return written

        # The pattern matches nothing once the collector has returned, as for a run
        # directory the scan cannot list, so only the runner's own read meets it. It
        # is the public `Path.glob` that is replaced, whatever the version's
        # internals (Python 3.11's glob never reaches a patched os.scandir).
        runs: list[str] = []

        def collected(*args, **kwargs):
            written = real(*args, **kwargs)
            runs.append(written.parent.name)
            return written

        real_glob = Path.glob

        def unseeing(path, pattern, *args, **kwargs):
            if runs:
                return iter(())
            return real_glob(path, pattern, *args, **kwargs)

        for case, extra in (
            (
                "second",
                patch("tools.quality_evidence.collect_diagnostic_inventory", doubling),
            ),
            (
                "unseen",
                patch("tools.quality_evidence.collect_diagnostic_inventory", collected),
            ),
        ):
            # The fixture's producers run under its output directory, one per case.
            self.output = output = Path(self.directory.name) / f"output-{case}"
            with (
                self.subTest(case=case),
                patch(
                    "tools.quality_evidence._bounded_run", side_effect=self._fake_run
                ),
                extra,
                patch.object(Path, "glob", unseeing),
                self.assertRaisesRegex(runner.RunnerError, "does not name"),
            ):
                runner.inventory_collect(
                    self.root,
                    output,
                    repository=REPOSITORY,
                    pull_number=PULL,
                    requested_head=head,
                    base_tip=OTHER,
                    base=self.base,
                    observed_at=OBSERVED,
                )
            self.assertFalse((output / "gnostoa-inventory-readback.json").exists())

    def test_an_error_is_reported_by_its_type_never_its_text(self) -> None:
        # Revix on #460 (sanitized-error-diagnostics): an OSError's or ValueError's
        # text can name local paths, so only its type reaches the log.
        runner = _runner()
        head = self._changed_head()
        stderr = io.StringIO()
        # The last case: the document is written, and its read-back fails (Claude on
        # #460), so the exit decision itself must report by type.
        cases = (
            ("OSError", {"side_effect": OSError("/a/local/path")}),
            ("ValueError", {"side_effect": ValueError("/a/local/path")}),
            ("FileNotFoundError", {"return_value": Path("/a/local/path/doc.json")}),
        )
        for name, effect in cases:
            with self.subTest(failure=name):
                stderr.seek(0)
                stderr.truncate()
                with (
                    patch.object(runner, "inventory_collect", **effect),
                    contextlib.redirect_stderr(stderr),
                ):
                    status = runner.main(
                        [
                            "inventory",
                            "collect",
                            "--repository",
                            REPOSITORY,
                            "--pull-number",
                            str(PULL),
                            "--head",
                            head,
                            "--base-tip",
                            OTHER,
                            "--base",
                            self.base,
                        ]
                    )
                self.assertEqual(2, status)
                self.assertNotIn("/a/local/path", stderr.getvalue())
                self.assertIn(name, stderr.getvalue())

    def _collect_rewritten(self, rewrite) -> dict:
        """The document of a collection whose written inventory `rewrite` replaced."""
        runner = _runner()
        head = self._changed_head()
        real = self.module.collect_diagnostic_inventory

        def rewriting(*args, **kwargs):
            written = real(*args, **kwargs)
            written.write_text(
                rewrite(written.read_text(encoding="utf-8")), encoding="utf-8"
            )
            return written

        with (
            patch("tools.quality_evidence._bounded_run", side_effect=self._fake_run),
            patch("tools.quality_evidence.collect_diagnostic_inventory", rewriting),
        ):
            path = runner.inventory_collect(
                self.root,
                self.output,
                repository=REPOSITORY,
                pull_number=PULL,
                requested_head=head,
                base_tip=OTHER,
                base=self.base,
                observed_at=OBSERVED,
            )
        return json.loads(path.read_text(encoding="utf-8"))

    def test_an_inventory_that_says_two_things_is_refused(self) -> None:
        # Revix on #460 (strict-bounded-json-parsing): json.loads keeps the last of a
        # repeated field, so a record could say two things and be read as one.
        document = self._collect_rewritten(
            lambda text: '{"schema": "gnostoa-diagnostic-inventory/v2", ' + text[1:]
        )
        for readback in document["readbacks"]:
            self.assertEqual("READBACK_UNAVAILABLE", readback["completeness"])
            self.assertEqual("ValueError", readback["coverage"]["reason"])

    def test_an_inventory_nested_past_the_bound_is_refused(self) -> None:
        document = self._collect_rewritten(
            lambda text: '{"deep": ' + "[" * 100 + "]" * 100 + ", " + text[1:]
        )
        for readback in document["readbacks"]:
            self.assertEqual("READBACK_UNAVAILABLE", readback["completeness"])
            self.assertEqual("ValueError", readback["coverage"]["reason"])

    def test_an_inventory_over_its_byte_bound_is_refused(self) -> None:
        runner = _runner()
        with patch.object(runner, "_INVENTORY_MAX_BYTES", 64):
            head = self._changed_head()
            with patch(
                "tools.quality_evidence._bounded_run", side_effect=self._fake_run
            ):
                path = runner.inventory_collect(
                    self.root,
                    self.output,
                    repository=REPOSITORY,
                    pull_number=PULL,
                    requested_head=head,
                    base_tip=OTHER,
                    base=self.base,
                    observed_at=OBSERVED,
                )
        document = json.loads(path.read_text(encoding="utf-8"))
        for readback in document["readbacks"]:
            self.assertEqual("READBACK_UNAVAILABLE", readback["completeness"])
            self.assertEqual("ValueError", readback["coverage"]["reason"])
        # The oversized inventory is uploaded with its document, so the document
        # still names it and its digest (CodeAnt on #460).
        inventory = self.output / document["inventory"]["file"]
        self.assertEqual(
            hashlib.sha256(inventory.read_bytes()).hexdigest(),
            document["inventory"]["sha256"],
        )

    def test_collect_takes_no_output_path(self) -> None:
        # SonarCloud pythonsecurity:S8707 on #460: no caller-supplied path chooses
        # where the job writes; it is the process's temporary directory, which the
        # workflow sets to the runner's own (TMPDIR).
        runner = _runner()
        head = self._changed_head()
        temporary = Path(self.directory.name) / "runner-temp"
        temporary.mkdir()
        written = Path(self.directory.name) / "document.json"
        written.write_text('{"readbacks": []}', encoding="utf-8")
        argv = [
            "inventory",
            "collect",
            "--repository",
            REPOSITORY,
            "--pull-number",
            str(PULL),
            "--head",
            head,
            "--base-tip",
            OTHER,
            "--base",
            self.base,
        ]
        with (
            patch.dict(os.environ, {"TMPDIR": str(temporary)}),
            patch.object(tempfile, "tempdir", None),
            patch.object(runner, "inventory_collect", return_value=written) as collect,
        ):
            self.assertEqual(0, runner.main(argv))
        self.assertEqual(temporary / "gnostoa-inventory", collect.call_args.args[1])
        with (
            contextlib.redirect_stderr(io.StringIO()),
            self.assertRaises(SystemExit),
        ):
            runner.main([*argv, "--output-dir", str(temporary)])

    def test_the_exit_decision_reads_its_document_strictly(self) -> None:
        # Revix on #460: the read-back that decides the exit uses the inventory's own
        # bounded, strict loader, so a document that says two things is an error.
        runner = _runner()
        head = self._changed_head()
        document = Path(self.directory.name) / "doubled.json"
        document.write_text(
            '{"readbacks": [], "readbacks": [{"completeness": "READBACK_UNAVAILABLE"}]}',
            encoding="utf-8",
        )
        argv = [
            "inventory",
            "collect",
            "--repository",
            REPOSITORY,
            "--pull-number",
            str(PULL),
            "--head",
            head,
            "--base-tip",
            OTHER,
            "--base",
            self.base,
        ]
        stderr = io.StringIO()
        with (
            patch.object(runner, "inventory_collect", return_value=document),
            contextlib.redirect_stderr(stderr),
        ):
            self.assertEqual(2, runner.main(argv))
        self.assertIn("ValueError", stderr.getvalue())

    def test_the_document_carries_no_credential(self) -> None:
        runner = _runner()
        head = self._changed_head()
        # The fixture's fake producers run only under its own output directory.
        out = self.output
        probe = "inventory-probe-" + "7" * 12
        with (
            patch.dict(os.environ, {"GITHUB_TOKEN": probe}),
            patch("tools.quality_evidence._bounded_run", side_effect=self._fake_run),
        ):
            path = runner.inventory_collect(
                self.root,
                out,
                repository=REPOSITORY,
                pull_number=PULL,
                requested_head=head,
                base_tip=OTHER,
                base=self.base,
                observed_at=OBSERVED,
            )
        self.assertNotIn(probe, path.read_text(encoding="utf-8"))

    def test_a_document_holding_the_job_s_token_is_never_written(self) -> None:
        # The control's own case: a finding message that carries the token's bytes.
        runner = _runner()
        head = self._changed_head()
        # The fixture's fake producers run only under its own output directory.
        out = self.output
        probe = "inventory-probe-" + "7" * 12
        self.ruff_records[0]["message"] = f"Private member accessed: {probe}"
        with (
            patch.dict(os.environ, {"GITHUB_TOKEN": probe}),
            patch("tools.quality_evidence._bounded_run", side_effect=self._fake_run),
            self.assertRaises(runner.RunnerError),
        ):
            runner.inventory_collect(
                self.root,
                out,
                repository=REPOSITORY,
                pull_number=PULL,
                requested_head=head,
                base_tip=OTHER,
                base=self.base,
                observed_at=OBSERVED,
            )
        self.assertFalse((out / "gnostoa-inventory-readback.json").exists())

    def test_a_depth_one_fetch_of_head_and_base_is_enough(self) -> None:
        # The job's own data path: main's checkout holds neither commit until it
        # fetches both, each alone, by its id.
        runner = _runner()
        head = self._changed_head()
        self._git("config", "uploadpack.allowAnySHA1InWant", "true")
        shallow = Path(self.directory.name) / "shallow"
        shallow.mkdir()
        # Git's own -C: the fixture's identity and environment, another repository.
        self._git("-C", str(shallow), "init", "-q")
        self._git(
            "-C",
            str(shallow),
            "fetch",
            "-q",
            "--no-tags",
            "--depth=1",
            self.root.as_uri(),
            head,
            self.base,
        )
        # The fixture's fake producers run only under its own output directory.
        out = self.output
        with patch("tools.quality_evidence._bounded_run", side_effect=self._fake_run):
            path = runner.inventory_collect(
                shallow,
                out,
                repository=REPOSITORY,
                pull_number=PULL,
                requested_head=head,
                base_tip=OTHER,
                base=self.base,
                observed_at=OBSERVED,
            )
        document = json.loads(path.read_text(encoding="utf-8"))
        record = json.loads(
            (out / document["inventory"]["file"]).read_text(encoding="utf-8")
        )
        self.assertEqual(head, record["source"]["revision"])
        self.assertEqual(
            ["tests/test_sample.py"], record["scope"]["diff"]["changed_paths"]
        )


def _workflow() -> dict:
    return yaml.safe_load(WORKFLOW_PATH.read_text(encoding="utf-8"))


def _named(job: Mapping[str, Any], name: str) -> dict:
    (step,) = [s for s in job["steps"] if s.get("name") == name]
    return step


class InventoryJobTests(unittest.TestCase):
    """The shadow producer job (Decision 0118): main's code and main's hash-locked
    tools over the head as data, with no secret, and no effect on the gate."""

    def test_the_workflow_has_the_readback_and_the_shadow_inventory_job(self) -> None:
        self.assertEqual({"readback", "inventory"}, set(_workflow()["jobs"]))

    def test_the_job_outlasts_the_collector_s_own_budget(self) -> None:
        # CodeAnt on #460: a job limit no longer than the collector's own budget kills
        # a slow scan before its bounded refusal is written, so no document records it.
        from tools.quality_evidence import DEFAULT_DIAGNOSTIC_LIMITS

        job = _workflow()["jobs"]["inventory"]
        self.assertGreaterEqual(
            int(job["timeout-minutes"]) * 60,
            DEFAULT_DIAGNOSTIC_LIMITS.timeout_seconds + JOB_MARGIN_SECONDS,
        )

    def test_the_upload_names_the_document_and_the_inventory_alone(self) -> None:
        # CodeAnt on #460: the step names the two files Decision 0118 publishes, the
        # inventory by the runner's own pattern, never the whole directory.
        from tools.quality_evidence import DIAGNOSTIC_INVENTORY

        upload = _named(_workflow()["jobs"]["inventory"], "Upload the shadow inventory")
        base = "${{ runner.temp }}/gnostoa-inventory"
        self.assertEqual(
            [
                f"{base}/gnostoa-inventory-readback.json",
                f"{base}/diagnostic-*/{DIAGNOSTIC_INVENTORY}",
            ],
            [line.strip() for line in upload["with"]["path"].splitlines()],
        )
        # The runner matches what the step publishes by the same names.
        runner = _runner()
        self.assertEqual("gnostoa-inventory", runner.INVENTORY_DIRECTORY)
        self.assertEqual("gnostoa-inventory-readback.json", runner.INVENTORY_DOCUMENT)
        self.assertEqual(
            f"diagnostic-*/{DIAGNOSTIC_INVENTORY}", runner.INVENTORY_UPLOAD
        )

    def test_the_job_holds_no_readback_slot(self) -> None:
        # CodeAnt on #460: a workflow-level group is held until every job of the run
        # ends, so each readback run would keep the analyzers' one slot for the
        # whole inventory, and other heads' readbacks and the admission call would
        # queue behind it. The slot is the readback job's alone.
        workflow = _workflow()
        self.assertNotIn("concurrency", workflow)
        self.assertEqual(
            "gnostoa-analyzer-readback",
            workflow["jobs"]["readback"]["concurrency"]["group"],
        )
        self.assertNotIn("concurrency", workflow["jobs"]["inventory"])

    def test_the_job_holds_no_secret_and_reads_only(self) -> None:
        job = _workflow()["jobs"]["inventory"]
        self.assertNotIn("environment", job)
        self.assertNotIn("secrets.", yaml.safe_dump(job))
        self.assertEqual(
            {"contents": "read", "pull-requests": "read"}, job["permissions"]
        )

    def test_the_job_runs_on_a_pinned_image(self) -> None:
        # Qualification evidence stays on one runner image, as the repository's
        # other qualification jobs do (Revix on #460).
        self.assertEqual("ubuntu-24.04", _workflow()["jobs"]["inventory"]["runs-on"])

    def test_the_job_can_never_change_the_run_s_conclusion(self) -> None:
        # A shadow: its failure is its own, never the readback's (slice 2).
        self.assertIs(True, _workflow()["jobs"]["inventory"]["continue-on-error"])

    def test_the_job_admits_the_readback_s_events_except_the_admission_call(
        self,
    ) -> None:
        # The admission point waits for its called workflow; the shadow has no
        # consumer there until slice 3 adds one.
        self.assertEqual(
            "github.ref == 'refs/heads/main'"
            " && inputs.admission != true"
            " && (github.event_name == 'workflow_dispatch'"
            " || github.event_name == 'repository_dispatch'"
            " || (github.event_name == 'workflow_run'"
            " && (github.event.workflow_run.conclusion == 'success'"
            " || github.event.workflow_run.conclusion == 'failure'"
            " || github.event.workflow_run.conclusion == 'timed_out')"
            " && github.event.workflow_run.event == 'pull_request'"
            " && github.event.workflow_run.path"
            " == '.github/workflows/verification.yml'))",
            " ".join(_workflow()["jobs"]["inventory"]["if"].split()),
        )

    def test_the_job_binds_main_and_the_subject_as_the_readback_does(self) -> None:
        jobs = _workflow()["jobs"]
        steps = jobs["inventory"]["steps"]
        self.assertEqual(jobs["readback"]["steps"][0], steps[0])
        for name in (
            "Bind trusted main execution source",
            "Resolve the readback subject",
        ):
            with self.subTest(step=name):
                self.assertEqual(
                    _named(jobs["readback"], name), _named(jobs["inventory"], name)
                )

    def test_the_tools_are_main_s_hash_locked_ones(self) -> None:
        install = _named(
            _workflow()["jobs"]["inventory"], "Install main's development tools"
        )
        run = " ".join(install["run"].split())
        for part in (
            "--only-binary=:all:",
            "--require-hashes",
            "-r requirements/development.lock",
        ):
            self.assertIn(part, run)

    def test_the_head_is_fetched_as_data_and_never_checked_out(self) -> None:
        job = _workflow()["jobs"]["inventory"]
        fetch = _named(job, "Fetch the head's objects as data")
        self.assertIn("git fetch --no-tags", " ".join(fetch["run"].split()))
        for step in job["steps"]:
            text = str(step.get("run", ""))
            with self.subTest(step=step.get("name", step.get("uses"))):
                for verb in ("checkout", "switch", "worktree", "reset", "restore"):
                    self.assertNotIn(f"git {verb}", text)
                if str(step.get("uses", "")).startswith("actions/checkout@"):
                    self.assertNotIn("ref", step.get("with", {}))
                    self.assertIs(False, step["with"]["persist-credentials"])

    def test_the_inventory_runs_main_s_runner_and_uploads_its_document(self) -> None:
        job = _workflow()["jobs"]["inventory"]
        collect = _named(job, "Inventory the head")
        self.assertIn(
            "python ci/analyzer_readback.py inventory collect", collect["run"]
        )
        # A document is uploaded only when the runner says it wrote it whole: exit 0,
        # or 1 for a recorded refusal; an error (2) may leave it partial (CodeAnt on
        # #460).
        self.assertIn(
            'if [ "${status}" -le 1 ] && [ -f "${output}/gnostoa-inventory-readback.json" ]',
            collect["run"],
        )
        upload = _named(job, "Upload the shadow inventory")
        self.assertEqual(
            "actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02",
            upload["uses"],
        )
        self.assertEqual(
            "${{ steps.subject.outputs.artifact }}-inventory", upload["with"]["name"]
        )

    def test_the_collect_step_holds_no_credential(self) -> None:
        # The boundary itself: the step that runs the inventory has no token to
        # leak (Revix on #460); the document check is defence in depth.
        collect = _named(_workflow()["jobs"]["inventory"], "Inventory the head")
        self.assertEqual(
            {"PULL_NUMBER", "REQUESTED_HEAD", "BASE_TIP", "BASE", "TMPDIR"},
            set(collect["env"]),
        )
        # Nor through an allowed name's value (cubic on #460).
        for reference in ("secrets", "github.token"):
            self.assertNotIn(reference, yaml.safe_dump(collect))

    def test_each_pinned_action_names_its_release(self) -> None:
        # The repository's pinning rule (Revix on #460): a full SHA, and its
        # release beside it, on every action the job uses.
        text = WORKFLOW_PATH.read_text(encoding="utf-8")
        job = text[text.index("\n  inventory:\n") :]
        uses = [line.strip() for line in job.splitlines() if "uses: " in line]
        self.assertEqual(3, len(uses))
        for line in uses:
            with self.subTest(line=line):
                self.assertRegex(line, r"@[0-9a-f]{40} # v\d+\.\d+\.\d+$")

    def test_an_event_s_fields_reach_only_the_resolver(self) -> None:
        for step in _workflow()["jobs"]["inventory"]["steps"]:
            if step.get("name") == "Resolve the readback subject":
                continue
            text = yaml.safe_dump(step)
            for field in ("inputs.", "client_payload", "workflow_run."):
                with self.subTest(step=step.get("name", step.get("uses")), field=field):
                    self.assertNotIn(field, text)
