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
from collections.abc import Iterator, Mapping
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
# How the runner reads an uploaded inventory: its digest and its scan in chunks of
# this size, its strict parse in one read of the collector's report bound and one
# byte more. The read-size test pins both, so a probe placed across the chunk's
# boundary cannot drift from it.
SCAN_CHUNK = 1_048_576
BOUNDED_READ = 64 * 1024 * 1024 + 1


@contextlib.contextmanager
def _token(value: str | None) -> Iterator[None]:
    """The environment's GitHub tokens for one collection: `value` as GITHUB_TOKEN,
    or none at all."""
    with patch.dict(os.environ):
        for name in ("GITHUB_TOKEN", "GH_TOKEN"):
            os.environ.pop(name, None)
        if value is not None:
            os.environ["GITHUB_TOKEN"] = value
        yield


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
        # Any answer GitHub gives, so a test can add the bundle's reads to it.
        self.answers: dict[str, Any] = {
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
        # What the upload step's pattern matches is the inventory alone.
        self.assertEqual(
            [left[0].resolve()],
            sorted(self.output.resolve().glob(runner.INVENTORY_UPLOAD)),
        )
        self.assertEqual(
            left[0].resolve(), (self.output / document["inventory"]["file"]).resolve()
        )

    def _collect_into(self, runner: Any, head: str, output: Path) -> Path:
        """`inventory_collect` of `head` into `output`, as the job runs it."""
        return runner.inventory_collect(
            self.root,
            output,
            repository=REPOSITORY,
            pull_number=PULL,
            requested_head=head,
            base_tip=OTHER,
            base=self.base,
            observed_at=OBSERVED,
        )

    def test_a_token_split_across_scan_chunks_is_found(self) -> None:
        # cubic on #460: the uploads are scanned in bounded chunks, never whole, so a
        # token across a chunk boundary must still be found. The uploaded inventory
        # carries the probe in a string of its own, across the scan's first chunk
        # boundary, and no readback carries it: only the uploads' scan can find it.
        # The inventory is named and digested before it is parsed, so the scan reads
        # it whatever its parse gives.
        runner = _runner()
        head = self._changed_head()
        probe = "inventoryprobe" + "7" * 12
        real = self.module.collect_diagnostic_inventory
        written: list[Path] = []

        def straddling(*args, **kwargs):
            inventory = real(*args, **kwargs)
            text = inventory.read_text(encoding="utf-8")
            opening = '{"padding": "'
            before = SCAN_CHUNK - len(opening) - len(probe) // 2
            inventory.write_text(
                opening + "x" * before + probe + "y" * 100_000 + '", ' + text[1:],
                encoding="utf-8",
            )
            written.append(inventory)
            return inventory

        with (
            _token(probe),
            patch("tools.quality_evidence._bounded_run", side_effect=self._fake_run),
            patch("tools.quality_evidence.collect_diagnostic_inventory", straddling),
            self.assertRaisesRegex(
                runner.RunnerError, "an uploaded file contains credential bytes"
            ),
        ):
            self._collect_into(runner, head, self.output)
        self.assertFalse((self.output / "gnostoa-inventory-readback.json").exists())
        # The probe straddles the first chunk's end, in an inventory over one chunk.
        raw = written[0].read_bytes()
        start = raw.index(probe.encode("utf-8"))
        self.assertLess(start, SCAN_CHUNK)
        self.assertGreater(start + len(probe), SCAN_CHUNK)

    def test_a_file_holds_no_needle_when_there_is_none(self) -> None:
        # Q on #460: the chunk reader stands on its own, with no needle to find. With
        # no token in the environment, the uploaded inventory is scanned for none,
        # and the collection completes without error.
        runner = _runner()
        head = self._changed_head()
        with (
            _token(None),
            patch("tools.quality_evidence._bounded_run", side_effect=self._fake_run),
        ):
            path = self._collect_into(runner, head, self.output)
        document = json.loads(path.read_text(encoding="utf-8"))
        self.assertIsNotNone(document["inventory"])
        self.assertEqual(
            [(self.output / document["inventory"]["file"]).resolve()],
            sorted(self.output.resolve().glob(runner.INVENTORY_UPLOAD)),
        )

    def test_a_link_in_the_uploaded_directory_is_refused(self) -> None:
        # Claude on #460: the pinned upload-artifact follows links
        # (followSymbolicLinks: true in its search), so a link would publish a target
        # the scan never read. An uploaded inventory reached through a link, as the
        # file or as its run directory, is refused, with or without a token, and no
        # document is written.
        runner = _runner()
        head = self._changed_head()
        real = self.module.collect_diagnostic_inventory

        def linking(kind, outside):
            """A collector whose inventory, or its run directory, is moved to
            `outside` and reached through a link in its place."""

            def collect(*args, **kwargs):
                written = real(*args, **kwargs)
                link = written if kind == "file" else written.parent
                outside.mkdir()
                moved = outside / link.name
                link.rename(moved)
                link.symlink_to(moved)
                return written

            return collect

        for kind in ("file", "directory"):
            for token in (None, "inventoryprobe"):
                case = f"{kind}-{'token' if token else 'none'}"
                # The fixture's producers run under its output directory, one per
                # case.
                self.output = output = Path(self.directory.name) / f"output-{case}"
                outside = Path(self.directory.name) / f"outside-{case}"
                with self.subTest(link=kind, token=token):
                    with (
                        _token(token),
                        patch(
                            "tools.quality_evidence._bounded_run",
                            side_effect=self._fake_run,
                        ),
                        patch(
                            "tools.quality_evidence.collect_diagnostic_inventory",
                            linking(kind, outside),
                        ),
                        self.assertRaisesRegex(runner.RunnerError, "through a link"),
                    ):
                        self._collect_into(runner, head, output)
                    self.assertFalse(
                        (output / "gnostoa-inventory-readback.json").exists()
                    )
        # A link the step's pattern does not match is neither uploaded nor refused,
        # though its target holds a file of the inventory's name.
        outside = Path(self.directory.name) / "outside-unmatched"
        outside.mkdir()
        (outside / "diagnostic-inventory.json").write_text("{}", encoding="utf-8")
        links: list[Path] = []

        def unmatched(*args, **kwargs):
            written = real(*args, **kwargs)
            link = written.parent / "raw-link"
            link.symlink_to(outside)
            links.append(link)
            return written

        self.output = output = Path(self.directory.name) / "output-unmatched"
        with (
            _token(None),
            patch("tools.quality_evidence._bounded_run", side_effect=self._fake_run),
            patch("tools.quality_evidence.collect_diagnostic_inventory", unmatched),
        ):
            path = self._collect_into(runner, head, output)
        document = json.loads(path.read_text(encoding="utf-8"))
        self.assertTrue(links[0].is_symlink())
        self.assertEqual(
            [(output / document["inventory"]["file"]).resolve()],
            sorted(output.resolve().glob(runner.INVENTORY_UPLOAD)),
        )

    def test_a_scan_without_the_token_reads_no_file_whole(self) -> None:
        # Revix on #460: every read of the scan asks for one chunk, never the whole
        # file. Once the collector has written it, the uploaded inventory is read in
        # a fixed order: its digest's chunks, the strict parse's one bounded read,
        # then the scan's chunks. A small inventory takes one chunk, then the end.
        runner = _runner()
        head = self._changed_head()
        real = self.module.collect_diagnostic_inventory
        written: list[Path] = []

        def collected(*args, **kwargs):
            inventory = real(*args, **kwargs)
            written.append(inventory.resolve())
            return inventory

        sizes: list[object] = []
        real_open = Path.open

        def recording(path, *args, **kwargs):
            handle = real_open(path, *args, **kwargs)
            if not written or path.resolve() != written[0]:
                return handle
            read = handle.read

            def sized(*size):
                sizes.append(size)
                return read(*size)

            handle.read = sized
            return handle

        with (
            _token("inventoryprobe"),
            patch("tools.quality_evidence._bounded_run", side_effect=self._fake_run),
            patch("tools.quality_evidence.collect_diagnostic_inventory", collected),
            patch.object(Path, "open", recording),
        ):
            self._collect_into(runner, head, self.output)
        self.assertEqual(
            [
                (SCAN_CHUNK,),
                (SCAN_CHUNK,),
                (BOUNDED_READ,),
                (SCAN_CHUNK,),
                (SCAN_CHUNK,),
            ],
            sizes,
        )

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


class InventoryBundleTests(_InventoryReadbackFixture):
    """#389 A0-MP1 slice 3 (r4, 6399931352): the readback job adds the same run's
    inventory document to the bundle, bound to the inventory job's trusted outputs:
    its result, and the document's SHA-256 that main's runner computed. Any refusal
    gives both project readbacks UNAVAILABLE, with its reason; never a prior one."""

    def _document(self) -> tuple[Path, str, str, str]:
        runner = _runner()
        head = self._changed_head()
        with patch("tools.quality_evidence._bounded_run", side_effect=self._fake_run):
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
        tree = self._git("rev-parse", f"{head}^{{tree}}")
        return path, hashlib.sha256(path.read_bytes()).hexdigest(), head, tree

    @staticmethod
    def _bound(
        path: Path, sha256: str, head: str, tree: str, result: str = "success"
    ) -> list[dict[str, Any]]:
        """The bundle's readbacks of `path`, as this attempt's job outputs give it
        (a name of its own, not the fixture's `_readbacks`: Codacy on #461)."""
        readbacks: list[dict[str, Any]] = _runner().inventory_bundle_readbacks(
            path,
            expected_sha256=sha256,
            result=result,
            attempt="1",
            run_attempt="1",
            repository=REPOSITORY,
            pull_number=PULL,
            requested_head=head,
            tree=lambda: tree,
            observed_at=OBSERVED,
        )
        return readbacks

    def test_a_document_bound_to_its_job_gives_its_two_readbacks(self) -> None:
        """RED: main's readback adds no inventory readback to the bundle."""
        path, sha256, head, tree = self._document()
        document = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(document["readbacks"], self._bound(path, sha256, head, tree))

    def test_each_refusal_gives_both_project_readbacks_unavailable(self) -> None:
        """RED (PAO 6399779328 findings 3 and 4): a document whose bytes are not the
        job's, a job that did not succeed, a missing document, another subject and
        another tree each refuse."""
        path, sha256, head, tree = self._document()
        for name, args, reason in (
            ("digest", (path, "0" * 64, head, tree), "DIGEST_MISMATCH"),
            (
                "failed job",
                (path, sha256, head, tree, "failure"),
                "INVENTORY_JOB_FAILURE",
            ),
            (
                "skipped job",
                (path, sha256, head, tree, "skipped"),
                "INVENTORY_JOB_SKIPPED",
            ),
            (
                "cancelled job",
                (path, sha256, head, tree, "cancelled"),
                "INVENTORY_JOB_CANCELLED",
            ),
            (
                "missing document",
                (self.output / "absent.json", sha256, head, tree),
                "INVENTORY_DOCUMENT_MISSING",
            ),
            ("another subject", (path, sha256, OTHER, tree), "WRONG_SUBJECT"),
            ("another tree", (path, sha256, head, "c" * 40), "WRONG_TREE"),
        ):
            with self.subTest(name):
                readbacks = self._bound(*args)
                self.assertEqual(
                    [
                        ("DIFF", "READBACK_UNAVAILABLE"),
                        ("FULL", "READBACK_UNAVAILABLE"),
                    ],
                    [(r["scope"], r["completeness"]) for r in readbacks],
                )
                self.assertEqual({reason}, {r["coverage"]["reason"] for r in readbacks})

    def test_a_foreign_profile_refuses(self) -> None:
        """RED: the readbacks' profile must be the protected profile's digest, computed
        again from main's checkout; the document's own claim proves nothing."""
        path, _, head, tree = self._document()
        document = json.loads(path.read_text(encoding="utf-8"))
        for readback in document["readbacks"]:
            readback["native"]["profile"] = "sha256:" + "f" * 64
        forged = self.output / "forged.json"
        forged.write_text(json.dumps(document), encoding="utf-8")
        readbacks = self._bound(
            forged, hashlib.sha256(forged.read_bytes()).hexdigest(), head, tree
        )
        self.assertEqual(
            {"FOREIGN_PROFILE"}, {r["coverage"]["reason"] for r in readbacks}
        )

    def test_the_bundle_binds_the_document_to_the_tree_github_reads(self) -> None:
        """Cubic on #461: end to end, `collect_bundle` hands the binding the tree
        GitHub reads for the head. The document's readbacks are kept when that tree
        is theirs, and refused when it is another. The reader is this module's own:
        a test module imported from another is unresolved for the project's
        inventory, a finding of its own."""
        runner = _runner()
        path, sha256, head, tree = self._document()
        document = json.loads(path.read_text(encoding="utf-8"))
        root = f"{API}/repos/{REPOSITORY}"
        for read, expected in ((tree, document["readbacks"]), ("c" * 40, None)):
            with self.subTest(tree=read):
                github = _PullRequestReader(head, OTHER, self.base)
                github.answers.update(
                    {
                        f"{root}/commits/{head}/statuses?per_page=100": [],
                        f"{root}/commits/{head}/check-runs?per_page=100": {
                            "check_runs": []
                        },
                        f"{root}/pulls/{PULL}/comments?per_page=50": [],
                        f"{root}/commits/{head}": {"commit": {"tree": {"sha": read}}},
                    }
                )
                bundle = runner.collect_bundle(
                    github,
                    repository=REPOSITORY,
                    pull_number=PULL,
                    requested_head=head,
                    deepsource=None,
                    codacy=None,
                    sonarcloud=None,
                    observed_at=OBSERVED,
                    inventory=runner.InventoryInput(path, sha256, "success", "1", "1"),
                )
                tail = bundle["readbacks"][-2:]
                if expected is None:
                    self.assertEqual(
                        {"WRONG_TREE"}, {r["coverage"]["reason"] for r in tail}
                    )
                else:
                    self.assertEqual(expected, tail)

    def test_a_document_of_another_attempt_refuses(self) -> None:
        """RED (Cubic on #461): re-running only the failed jobs reuses an earlier
        attempt's successful inventory, its outputs and its artifact. Its document
        is not this attempt's, so it refuses; the same attempt's is kept (PAO
        6401278396: the producer-1 / consumer-2 refusal beside the positive)."""
        path, sha256, head, tree = self._document()
        document = json.loads(path.read_text(encoding="utf-8"))
        kept = _runner().inventory_bundle_readbacks(
            path,
            expected_sha256=sha256,
            result="success",
            attempt="2",
            run_attempt="2",
            repository=REPOSITORY,
            pull_number=PULL,
            requested_head=head,
            tree=lambda: tree,
            observed_at=OBSERVED,
        )
        self.assertEqual(document["readbacks"], kept)
        for attempt, run_attempt in (
            ("1", "2"),
            ("", "1"),
            (None, "1"),
            ("1", None),
            # Equal, but naming no attempt: an output that never resolved.
            (None, None),
            ("", ""),
        ):
            with self.subTest(attempt=attempt, run_attempt=run_attempt):
                readbacks = _runner().inventory_bundle_readbacks(
                    path,
                    expected_sha256=sha256,
                    result="success",
                    attempt=attempt,
                    run_attempt=run_attempt,
                    repository=REPOSITORY,
                    pull_number=PULL,
                    requested_head=head,
                    tree=lambda: tree,
                    observed_at=OBSERVED,
                )
                self.assertEqual(
                    {"INVENTORY_ATTEMPT_STALE"},
                    {r["coverage"]["reason"] for r in readbacks},
                )

    def test_a_document_for_another_subject_or_shape_refuses(self) -> None:
        """#425 kill table, slice 3 round 1 (C04, C08): a document whose bytes are the
        job's, but whose pull request or repository is another's at the same head, or
        whose readbacks are not exactly the inventory's DIFF then FULL, refuses. Only
        the inventory's two readbacks may reach the bundle: a document never adds a
        readback of another provider."""
        path, _, head, tree = self._document()

        def pull(document: dict[str, Any]) -> None:
            document["pull_number"] = PULL + 1

        def repository(document: dict[str, Any]) -> None:
            document["repository"] = "other/repository"

        def reversed_scopes(document: dict[str, Any]) -> None:
            document["readbacks"].reverse()

        def diff_twice(document: dict[str, Any]) -> None:
            document["readbacks"][1] = document["readbacks"][0]

        def another_provider(document: dict[str, Any]) -> None:
            document["readbacks"][0]["provider"] = "codacy"

        def a_readback_of_another_head(document: dict[str, Any]) -> None:
            # The document names this subject, one of its readbacks another head
            # (#425 kill table, slice 3 round 4, C14).
            readback = document["readbacks"][1]
            readback["requested_head"] = OTHER
            if readback.get("observed_head"):
                readback["observed_head"] = OTHER

        for forge, reason in (
            (pull, "WRONG_SUBJECT"),
            (repository, "WRONG_SUBJECT"),
            (reversed_scopes, "MALFORMED_READBACKS"),
            (diff_twice, "MALFORMED_READBACKS"),
            (another_provider, "MALFORMED_READBACKS"),
            (a_readback_of_another_head, "WRONG_SUBJECT"),
        ):
            with self.subTest(forge.__name__):
                document = json.loads(path.read_text(encoding="utf-8"))
                forge(document)
                forged = self.output / f"{forge.__name__}.json"
                forged.write_text(json.dumps(document), encoding="utf-8")
                readbacks = self._bound(
                    forged,
                    hashlib.sha256(forged.read_bytes()).hexdigest(),
                    head,
                    tree,
                )
                self.assertEqual(
                    [
                        ("gnostoa-inventory", "DIFF", "READBACK_UNAVAILABLE"),
                        ("gnostoa-inventory", "FULL", "READBACK_UNAVAILABLE"),
                    ],
                    [(r["provider"], r["scope"], r["completeness"]) for r in readbacks],
                )
                self.assertEqual({reason}, {r["coverage"]["reason"] for r in readbacks})


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

        upload = _named(_workflow()["jobs"]["inventory"], "Upload the inventory")
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

    def test_a_failed_inventory_denies_rather_than_vanishes(self) -> None:
        """RED (#389 A0-MP1 slice 3; PAO 6399779328 finding 4): the inventory is no
        longer a shadow. Its failure is not hidden, and the readback still runs after
        it, so a failed, cancelled or skipped inventory becomes the project items'
        UNAVAILABLE, never a vanished item. A cancelled run runs nothing more
        (Revix on #461)."""
        jobs = _workflow()["jobs"]
        self.assertNotIn("continue-on-error", jobs["inventory"])
        self.assertEqual("inventory", jobs["readback"]["needs"])
        condition = " ".join(jobs["readback"]["if"].split())
        self.assertTrue(condition.startswith("!cancelled() && "))
        self.assertNotIn("always()", condition)

    def test_the_job_admits_exactly_the_readback_s_events(self) -> None:
        """RED (slice 3): the inventory runs wherever the readback does, the admission
        call included, under the same trusted-main condition."""
        jobs = _workflow()["jobs"]
        readback = " ".join(jobs["readback"]["if"].split())
        self.assertEqual(
            readback.removeprefix("!cancelled() && "),
            " ".join(jobs["inventory"]["if"].split()),
        )
        self.assertIn("inputs.admission == true", readback)

    def test_the_upload_s_identity_reaches_the_readback(self) -> None:
        """RED (r4, 6399931352): the readback learns which archive to read, and the
        document's SHA-256, only from the inventory job's own outputs; each attempt's
        artifact has its own name, so a re-run neither collides nor reads another."""
        job = _workflow()["jobs"]["inventory"]
        self.assertEqual(
            {
                "attempt": "${{ github.run_attempt }}",
                "artifact-id": "${{ steps.upload.outputs.artifact-id }}",
                "artifact-digest": "${{ steps.upload.outputs.artifact-digest }}",
                "document-sha256": "${{ steps.inventory.outputs.document-sha256 }}",
            },
            job["outputs"],
        )
        upload = _named(job, "Upload the inventory")
        self.assertEqual("upload", upload["id"])
        self.assertEqual(
            "${{ steps.subject.outputs.artifact }}-inventory-${{ github.run_attempt }}",
            upload["with"]["name"],
        )
        self.assertIn("document-sha256=", _named(job, "Inventory the head")["run"])

    def test_the_readback_reads_exactly_that_artifact(self) -> None:
        """RED (r4): the readback downloads the artifact its needed job uploaded, by
        id, with the pinned downloader, and hands the runner the job's result and the
        document's expected SHA-256; the runner refuses any mismatch."""
        job = _workflow()["jobs"]["readback"]
        [download] = [
            s
            for s in job["steps"]
            if s.get("uses", "").startswith("actions/download-artifact@")
        ]
        self.assertEqual(
            "actions/download-artifact@634f93cb2916e3fdff6788551b99b062d0335ce0",
            download["uses"],
        )
        self.assertEqual(
            "${{ needs.inventory.outputs.artifact-id }}",
            download["with"]["artifact-ids"],
        )
        self.assertNotIn("name", download["with"])
        step = _named(job, "Read exact-head analyzer evidence")
        self.assertEqual(
            "${{ needs.inventory.result }}", step["env"]["INVENTORY_RESULT"]
        )
        self.assertEqual(
            "${{ needs.inventory.outputs.document-sha256 }}",
            step["env"]["INVENTORY_SHA256"],
        )
        for argument in (
            "--inventory-document",
            "--inventory-sha256",
            "--inventory-result",
        ):
            self.assertIn(argument, step["run"])

    def test_the_inventory_s_attempt_reaches_the_readback(self) -> None:
        """RED (Cubic on #461): the inventory job names the attempt it ran in, and
        the readback hands the runner that and its own attempt, which must agree."""
        jobs = _workflow()["jobs"]
        self.assertEqual(
            "${{ github.run_attempt }}", jobs["inventory"]["outputs"]["attempt"]
        )
        step = _named(jobs["readback"], "Read exact-head analyzer evidence")
        self.assertEqual(
            "${{ needs.inventory.outputs.attempt }}", step["env"]["INVENTORY_ATTEMPT"]
        )
        self.assertEqual("${{ github.run_attempt }}", step["env"]["RUN_ATTEMPT"])
        for argument in (
            '--inventory-attempt "${INVENTORY_ATTEMPT}"',
            '--run-attempt "${RUN_ATTEMPT}"',
        ):
            self.assertIn(argument, step["run"])

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
        upload = _named(job, "Upload the inventory")
        self.assertEqual(
            "actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02",
            upload["uses"],
        )
        self.assertEqual(
            "${{ steps.subject.outputs.artifact }}-inventory-${{ github.run_attempt }}",
            upload["with"]["name"],
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
