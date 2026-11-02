"""Characterization of the spec's control parser and the handoff's source walk before
their extraction (Decision 0127).

Each test reaches its function through the public API and pins behaviour that the
pre-change mutant table left unpinned (#389 6568479405):
- `parse_spec`'s refusals of malformed controls, and the values a control carries;
- `freeze_handoff`'s refusal of an unsupported entry, and each of its race guards. A race
  is injected through the module's own `os.stat` and `os.fstat`, one observation at a
  time, as the existing handoff tests patch `os.mkdir`.
"""

from __future__ import annotations

import copy
import os
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest import mock

from tools.capsule.spec import SpecError, parse_spec
from tools.experiment import handoff

_REAL_STAT = os.stat
_REAL_FSTAT = os.fstat
_REAL_OPEN = os.open
_INPUT = f"fixture={'a' * 64}"


def _spec(controls: object) -> dict[str, Any]:
    task = {
        "id": "T1",
        "adapter": "python-pytest",
        "source": {"repository": "repo", "base_commit": "b", "base_tree": "t"},
        "reference": {"kind": "accepted-merge-commit", "commit": "r", "tree": "t"},
        "runtime": {"image": "sha256:" + "a" * 64},
        "oracle": {"path": "oracle.py"},
        "semantics": {
            "requirement": "subject must not regress",
            "discriminator": {"cases": ["test_discriminates"]},
            "controls": controls,
        },
        "expectations": {
            "base": {"failed": 1, "passed": 0},
            "reference": {"failed": 0, "passed": 1},
        },
        "execution": {"command": ["python", "-V"], "environment_allowlist": []},
    }
    return {
        "schema": "gnostoa-experiment-spec/v1",
        "experiment": {
            "id": "E1",
            "question": "q",
            "claim_boundary": "bounded",
            "executor": {"id": "exec", "version": "1", "config_sha256": "1" * 64},
            "resources": {
                "timeout_seconds": 600,
                "archive_limit_bytes": 268435456,
                "network": {"mode": "none", "allow": []},
            },
        },
        "tasks": [task],
    }


class SpecControlParsingTests(unittest.TestCase):
    """What a declared control may be, and what it carries once parsed."""

    def _parse(self, controls: object) -> Any:
        return parse_spec(copy.deepcopy(_spec(controls)), source_path=Path("spec.json"))

    def test_each_malformed_control_is_refused_by_its_own_message(self) -> None:
        cases: dict[str, tuple[object, str]] = {
            "a control that is not a mapping": (
                ["test_control"],
                "each control must be a mapping",
            ),
            "a corroboration that is not a mapping": (
                [{"case": "test_control", "corroboration": "evidence.py"}],
                "control corroboration must be a mapping",
            ),
            "value substitutions that are not a mapping": (
                [
                    {
                        "case": "test_control",
                        "corroboration": {"path": "e.py", "value_substitutions": []},
                    }
                ],
                "value_substitutions must be a mapping",
            ),
            "a corroboration with neither a path nor a prior": (
                [{"case": "test_control", "corroboration": {"symbol": "f"}}],
                "corroboration needs either a base-tree path or a "
                "prior_qualification_sha256",
            ),
        }
        for label, (controls, message) in cases.items():
            with self.subTest(label), self.assertRaisesRegex(SpecError, message):
                self._parse(controls)

    def test_a_control_carries_its_declared_values(self) -> None:
        cited = self._parse(
            [{"case": "test_control", "corroboration": {"path": "evidence.py"}}]
        )
        corroboration = cited.tasks[0].semantics.controls[0].corroboration
        self.assertEqual("evidence.py", corroboration.path)
        self.assertIsNone(corroboration.symbol)
        self.assertIsNone(corroboration.prior_qualification_sha256)

        prior = "b" * 64
        reused = self._parse(
            [
                {
                    "case": "test_control",
                    "corroboration": {"prior_qualification_sha256": prior},
                }
            ]
        )
        carried = reused.tasks[0].semantics.controls[0].corroboration
        self.assertIsNone(carried.path)
        self.assertEqual(prior, carried.prior_qualification_sha256)


class _Changed:
    """A stat result that reads as the same entry, modified once."""

    def __init__(self, real: os.stat_result) -> None:
        self._real = real

    def __getattr__(self, name: str) -> object:
        if name == "st_mtime_ns":
            return self._real.st_mtime_ns + 1
        return getattr(self._real, name)


class _Race:
    """Wraps os.open, os.stat and os.fstat so that exactly one observation of one source
    entry reads as changed: the `index`-th `stat` of `name`, or the `index`-th `fstat` of
    the descriptor first opened for `name` (the source root's path for the root)."""

    def __init__(self, call: str, name: str, index: int) -> None:
        self.call, self.name, self.index = call, name, index
        self.seen = 0
        self.fds: dict[int, str] = {}

    def open(self, path: Any, *args: Any, **kwargs: Any) -> int:
        fd = _REAL_OPEN(path, *args, **kwargs)
        label = str(path)
        if label not in self.fds.values():
            self.fds[fd] = label
        return fd

    def _maybe_change(self, call: str, label: str, real: os.stat_result) -> Any:
        if call == self.call and label == self.name:
            self.seen += 1
            if self.seen - 1 == self.index:
                return _Changed(real)
        return real

    def stat(self, path: Any, *args: Any, **kwargs: Any) -> Any:
        return self._maybe_change("stat", str(path), _REAL_STAT(path, *args, **kwargs))

    def fstat(self, fd: int) -> Any:
        return self._maybe_change("fstat", self.fds.get(fd, ""), _REAL_FSTAT(fd))


class HandoffSourceWalkTests(unittest.TestCase):
    """The freeze refuses an unsupported entry, and an entry or directory that changes."""

    def setUp(self) -> None:
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.source = self.root / "source"
        (self.source / "sub").mkdir(parents=True)
        (self.source / "sub" / "file.txt").write_text("content\n")
        (self.source / "sub" / "link").symlink_to("file.txt")

    def _freeze(self, race: _Race | None = None) -> tuple[int, dict[str, object]]:
        bundle = self.root / f"bundle-{len(list(self.root.iterdir()))}"
        if race is None:
            return handoff.freeze_handoff(self.source, bundle, [_INPUT])
        with (
            mock.patch.object(handoff.os, "open", side_effect=race.open),
            mock.patch.object(handoff.os, "stat", side_effect=race.stat),
            mock.patch.object(handoff.os, "fstat", side_effect=race.fstat),
        ):
            return handoff.freeze_handoff(self.source, bundle, [_INPUT])

    def test_an_unchanged_source_freezes(self) -> None:
        code, payload = self._freeze()
        self.assertEqual((0, "FROZEN"), (code, payload["status"]))

    def test_an_unsupported_entry_is_refused(self) -> None:
        # The entry's mode is normalized before its type is dispatched, so a FIFO is
        # refused there, by type; the walk's own unsupported-entry refusal is
        # unreachable for a real entry.
        os.mkfifo(self.source / "sub" / "pipe")
        code, payload = self._freeze()
        self.assertEqual(2, code)
        self.assertEqual(
            ["HandoffError:unsupported-source-entry-type"], payload["reasons"]
        )

    def test_each_race_guard_refuses_its_own_change(self) -> None:
        root = str(self.source.resolve())
        cases: dict[str, tuple[_Race, str]] = {
            "a directory changed between stat and open": (
                _Race("stat", "sub", 0),
                "source-entry-changed:sub",
            ),
            "a directory changed during its walk": (
                _Race("fstat", "sub", 3),
                "source-directory-changed:sub",
            ),
            "a file changed between stat and open": (
                _Race("stat", "file.txt", 0),
                "source-entry-changed:sub/file.txt",
            ),
            "a file replaced after its copy": (
                _Race("stat", "file.txt", 1),
                "source-entry-changed:sub/file.txt",
            ),
            "a symlink replaced after its read": (
                _Race("stat", "link", 1),
                "source-entry-changed:sub/link",
            ),
            "the source root changed during its listing": (
                _Race("fstat", root, 1),
                "source-directory-changed:.",
            ),
        }
        for label, (race, reason) in cases.items():
            with self.subTest(label):
                code, payload = self._freeze(race)
                self.assertEqual(2, code)
                self.assertEqual([f"HandoffError:{reason}"], payload["reasons"])


if __name__ == "__main__":
    unittest.main()
