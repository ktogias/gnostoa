"""The diagnostic inventory tests' private fixtures (#389 F3 S2 B, Router 6326577610):
the fixture repository, the faked producers and their helpers, shared by the
inventory's test modules. It holds no test, so discovery runs none of it twice."""

from __future__ import annotations

import contextlib
import functools
import importlib
import json
import os
import re
import subprocess  # nosec B404 -- test-only: drives git on temporary fixture repositories
import sys
import tempfile
import threading
import time
import unittest
from collections.abc import Callable
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

from tools.quality_evidence import (
    QualityEvidenceError,
)

_DIAGNOSTIC_SAMPLE = (
    '"""Diagnostic fixture: production side."""\n'
    "\n"
    "_hidden = 1\n"
    "\n"
    "\n"
    "def takes_int(value: int) -> int:\n"
    "    return value\n"
    "\n"
    "\n"
    "def branchy(a: int) -> int:\n"
    "    total = 0\n"
    + "".join(f"    if a > {n}:\n        total += 1\n" for n in range(16))
    + "    return total\n"
    "\n"
    "\n"
    "def sixteen(a: int) -> int:\n"
    "    total = 0\n"
    + "".join(f"    if a > {n}:\n        total += 1\n" for n in range(15))
    + "    return total\n"
    "\n"
    "\n"
    "def fifteen(a: int) -> int:\n"
    "    total = 0\n"
    + "".join(f"    if a > {n}:\n        total += 1\n" for n in range(14))
    + "    return total\n"
    "\n"
    "\n"
    "def outer(a: int) -> int:\n"
    "    def inner(b: int) -> int:\n"
    "        total = 0\n"
    + "".join(f"        if b > {n}:\n            total += 1\n" for n in range(8))
    + "        return total\n"
    "\n"
    "    total = inner(a)\n"
    + "".join(f"    if a > {n}:\n        total += 1\n" for n in range(8))
    + "    return total\n"
)
_DIAGNOSTIC_REASON = "the fixture's justified white-box access"
_DIAGNOSTIC_TESTS = (
    '"""Diagnostic fixture: test side."""\n'
    "\n"
    "from tools import sample\n"
    "from tools.sample import takes_int\n"
    "\n"
    "\n"
    "def typed_call() -> int:\n"
    '    return takes_int("text")\n'
    "\n"
    "\n"
    "def white_box() -> object:\n"
    "    return sample._hidden\n"
    "\n"
    "\n"
    "def justified() -> object:\n"
    f"    # skipcq: PYL-W0212 -- {_DIAGNOSTIC_REASON}\n"
    "    return sample._hidden\n"
)


def _fixture_git_env() -> dict[str, str]:
    """The environment of the fixtures' own Git: the caller's, never its global or
    system configuration, so a developer's ~/.gitconfig or /etc/gitconfig cannot run a
    hook, sign or alias in a fixture repository (Revix on #450; #389 6327632965)."""
    return {
        **os.environ,
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_SYSTEM": os.devnull,
    }


def _diagnostic_line(text: str, needle: str, after: str | None = None) -> int:
    start = 0
    lines = text.splitlines()
    if after is not None:
        start = next(i for i, line in enumerate(lines) if after in line)
    return next(i for i, line in enumerate(lines) if i >= start and needle in line) + 1


# The Router's I3 on #436 (6210989878): without a bounded check of the index, no
# inventory is COMPLETE, however clean its subject looks. Its U1 (6225341677) adds the
# import graph, which is not proven confined to the recorded tracked inputs.
_SOURCE_BINDING_GAP = (
    "source binding UNVERIFIED: the producers' installed environment and import graph "
    "is not proven confined to the staged tracked inputs; only the frozen tree's bytes "
    "are bound, observed before and after the producers, not throughout them"
)
# The launched producers' pins, read from the producer tree's lock bytes here, never
# through the collector's own parser (#389 P2, Decision 0120). A name matches in any
# case, as the parser normalizes it (CodeAnt on #463).
PINS = {
    name.lower(): version
    for name, version in re.findall(
        r"^(mypy|ruff)==([^\s\\]+)",
        (
            Path(__file__).resolve().parent.parent / "requirements" / "development.lock"
        ).read_text(encoding="utf-8"),
        re.MULTILINE | re.IGNORECASE,
    )
}
if not {"mypy", "ruff"} <= PINS.keys():
    # Named, rather than a KeyError below at import (Amazon Q on #463).
    raise RuntimeError("requirements/development.lock does not pin both mypy and ruff")
# A default fixture run's binding gaps: the residual, its producers' 1.0.0, which no
# pin matches (P2), and the supplied profile of the private path (P3). Decision 0120.
_UNBOUND_FIXTURE_GAP = "; ".join(
    [
        _SOURCE_BINDING_GAP,
        "source binding P2 unmet: "
        f"mypy's version '1.0.0' is not its pin {PINS['mypy']!r}, "
        f"ruff's version '1.0.0' is not its pin {PINS['ruff']!r}",
        "source binding P3 unmet: the profile was supplied, not the producer tree's",
    ]
)


def _calling_through(*, spec: Callable[..., object]) -> Mock:
    """A new_callable for patch.object(..., spec=True), which hands it the original
    it replaces as `spec`: a spy that calls that original, and answers as it does."""
    return Mock(side_effect=spec)


def _wrapping(*, spec: Callable[..., object]) -> MagicMock:
    """A new_callable for patch.object(..., spec=True): the original, `spec`, wrapped
    as patch.object(..., wraps=original) wraps it."""
    return MagicMock(wraps=spec)


def _v1_subject_spy() -> Mock:
    """A spy for `_git_state`, v1's subject read, which the diagnostic path never
    calls: every assertion on it is a negative (D1), so it passes no call through,
    and fails one loudly."""
    return Mock(side_effect=AssertionError("v1's _git_state was called"))


class _RaisingRead:
    """A stream whose read raises `error`. The real stream's descriptor, its checks
    and its closing are kept."""

    def __init__(self, stream, error: type[BaseException]) -> None:
        self.stream = stream
        self.error = error

    def __enter__(self) -> _RaisingRead:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.stream.close()

    def fileno(self) -> int:
        return self.stream.fileno()

    def read(self, size: int = -1) -> bytes:
        raise self.error(f"injected at the stream read of {size} bytes")


# Every family on every file, as the inventory ran before its profile: the producers'
# own tests keep their whole selection, and the protected profile has its own tests
# (#389 A0-MP1).
_EVERY_FAMILY = {
    "schema": "gnostoa-diagnostic-profile/v1",
    "id": "fixture.every-family",
    "scopes": {"all": {"exclude": []}},
    "families": [
        {"id": "typing", "producer": "mypy", "diff": "all", "full": "all"},
        {
            "id": "every-rule",
            "producer": "ruff",
            "select": ["SLF001", "PLR6301", "SIM117", "S106"],
            "diff": "all",
            "full": "all",
        },
        {
            "id": "complexity",
            "producer": "complexity",
            "reported_above": 15,
            "diff": "all",
            "full": "all",
        },
    ],
}


class _DiagnosticFixture(unittest.TestCase):
    """A small tracked repository, and the helpers the inventory tests share."""

    def setUp(self) -> None:
        self.module = importlib.import_module("tools.quality_evidence")
        # The private collector, as unittest.mock hands an original to new_callable
        # under spec=True; patched with itself for an empty block, so nothing is
        # replaced. The fixture's profile is bound to it, as before: its record's
        # origin is "argument", never the producer tree's.
        originals: list[Callable[..., Path]] = []

        def kept(*, spec: Callable[..., Path]) -> Callable[..., Path]:
            originals.append(spec)
            return spec

        with patch.object(
            self.module, "_collect_diagnostic_inventory", spec=True, new_callable=kept
        ):
            pass
        self.collect = functools.partial(originals[0], profile=_EVERY_FAMILY)
        # Each test runs without the caller's Git overrides, which the inventory
        # refuses: preparation's own environment sets GIT_CONFIG_* for its children
        # (Router 6223042901 on #436, R1). Every GIT_ name goes, a superset of the
        # owner's rule in candidate_prepare, each of whose names starts with GIT_.
        # The refusal tests set theirs explicitly.
        self.enterContext(patch.dict(os.environ))
        for name in [name for name in os.environ if name.startswith("GIT_")]:
            del os.environ[name]
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name) / "repository"
        self.output = Path(self.directory.name) / "evidence"
        self.files = {
            "tools/__init__.py": "",
            "tools/sample.py": _DIAGNOSTIC_SAMPLE,
            "tests/test_sample.py": _DIAGNOSTIC_TESTS,
            "tests/fixtures/one/baseline.py": "VALUE = 1\n",
        }
        for path, text in self.files.items():
            (self.root / path).parent.mkdir(parents=True, exist_ok=True)
            (self.root / path).write_text(text, encoding="utf-8")
        self._git("init", "-q")
        self._git("add", "-A")
        self._git("commit", "-q", "-m", "base")
        self.base = self._git("rev-parse", "HEAD")
        self.lines = {
            "typing": _diagnostic_line(_DIAGNOSTIC_TESTS, 'takes_int("text")'),
            "private": _diagnostic_line(_DIAGNOSTIC_TESTS, "return sample._hidden"),
            "marked": _diagnostic_line(
                _DIAGNOSTIC_TESTS, "return sample._hidden", after=_DIAGNOSTIC_REASON
            ),
            "branchy": _diagnostic_line(_DIAGNOSTIC_SAMPLE, "def branchy"),
            "sixteen": _diagnostic_line(_DIAGNOSTIC_SAMPLE, "def sixteen"),
            "fifteen": _diagnostic_line(_DIAGNOSTIC_SAMPLE, "def fifteen"),
            "outer": _diagnostic_line(_DIAGNOSTIC_SAMPLE, "def outer"),
        }

    def _git(self, *args: str) -> str:
        return subprocess.run(  # nosec B603 B607 -- test-only: a literal git argv on a temporary fixture repository
            [
                "git",
                "-c",
                "user.name=diagnostic",
                "-c",
                "user.email=diagnostic@example.invalid",
                "-c",
                "commit.gpgsign=false",
                *args,
            ],
            cwd=self.root,
            env=_fixture_git_env(),
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()

    @staticmethod
    def _then(
        real: Callable[..., object], failure: BaseException
    ) -> Callable[..., object]:
        """A side effect that answers through `real` once, then raises `failure`."""
        calls: list[int] = []

        def answer(*args, **kwargs):
            calls.append(1)
            if len(calls) > 1:
                raise failure
            return real(*args, **kwargs)

        return answer

    def _head(self) -> str:
        """The fixture's current commit, the one a collection would freeze."""
        return self._git("rev-parse", "HEAD")

    @staticmethod
    def _find(inventory: dict, tool: str, rule, path: str, line: int) -> list[dict]:
        return [
            f
            for f in inventory["findings"]
            if f["tool"]["id"] == tool
            and f.get("rule") == rule
            and f["path"] == path
            and (f.get("range") or {}).get("start_line") == line
        ]

    @staticmethod
    def _read(path: Path) -> dict:
        return json.loads(Path(path).read_text(encoding="utf-8"))


_EXTRA_COMPLEX = (
    "\n\ndef extra(a: int) -> int:\n    total = 0\n"
    + "".join(f"    if a > {n}:\n        total += 1\n" for n in range(16))
    + "    return total\n"
)


class _DiagnosticInventoryFixture(_DiagnosticFixture):
    """The inventory tests' shared fixture, with no test of its own: the producers
    faked at `_bounded_run` with their real report formats, their records, and the
    collection and spies through them."""

    def setUp(self) -> None:
        super().setUp()
        self.mypy_records: dict[str, list[dict]] = {
            "tests/test_sample.py": [
                self._mypy(
                    "tests/test_sample.py",
                    self.lines["typing"],
                    11,
                    "arg-type",
                    'Argument 1 to "takes_int" has incompatible type "str"; expected "int"',
                ),
                self._mypy(
                    "tests/test_sample.py",
                    self.lines["typing"],
                    11,
                    "union-attr",
                    'Item "None" of "str | None" has no attribute "x"',
                ),
            ],
        }
        self.ruff_records = [
            self._ruff(
                "tests/test_sample.py",
                self.lines["private"],
                12,
                "SLF001",
                "Private member accessed: `_hidden`",
            ),
            self._ruff(
                "tests/test_sample.py",
                self.lines["marked"],
                12,
                "SLF001",
                "Private member accessed: `_hidden`",
            ),
            self._ruff(
                "tests/test_sample.py",
                self.lines["typing"],
                5,
                "PLR6301",
                "Method could be a function",
            ),
        ]
        self.mypy_exit: dict[str, int] = {}
        self.mypy_text: str | None = None
        self.ruff_exit = 1
        self.ruff_as_ruff = False
        self.ruff_text: str | None = None
        # Each producer's `--version` answer, 1.0.0 unless a test sets one; None
        # answers as an unreadable version (#389 P2).
        self.versions: dict[str, str | None] = {}
        self.commands: list[tuple[list[str], Path, dict[str, str]]] = []

    @staticmethod
    def _mypy(
        path: str,
        line: int,
        column: int,
        code: str | None,
        message: str,
        severity: str = "error",
    ) -> dict:
        return {
            "file": path,
            "line": line,
            "column": column,
            "end_line": line,
            "end_column": column + 4,
            "message": message,
            "hint": None,
            "code": code,
            "severity": severity,
        }

    def _ruff(self, path: str, line: int, column: int, code: str, message: str) -> dict:
        return {
            "cell": None,
            "code": code,
            "end_location": {"column": column + 14, "row": line},
            "filename": str(self.root.resolve() / path),
            "fix": None,
            "location": {"column": column, "row": line},
            "message": message,
            "url": None,
        }

    def _source_root(self, cwd) -> Path:
        """The root the producers ran in: the run's staged copy of the frozen tree,
        `<output>/<run>/source`, never the checkout (#389 F3 S2 B); or the fixture's
        root, for a producer a test runs on it directly."""
        output, cwd = self.output.resolve(), Path(cwd).resolve()
        if not cwd.is_relative_to(output):
            return self.root.resolve()
        relative = cwd.relative_to(output)
        if len(relative.parts) < 2:
            raise AssertionError(f"a producer ran outside a staged source: {cwd}")
        return output / relative.parts[0] / relative.parts[1]

    def _group(self, cwd) -> str:
        """A producer's working directory, relative to the root it analyzed."""
        return Path(cwd).resolve().relative_to(self._source_root(cwd)).as_posix()

    def _staged_text(self, text: str, cwd) -> str:
        """`text` as a producer run in `cwd` writes it: its absolute names under the
        staged source it read, never the checkout (#389 F3 S2 B)."""
        return text.replace(str(self.root.resolve()), str(self._source_root(cwd)))

    def _fake_run(self, command, *, cwd, environment, report, deadline, limits):
        self.commands.append((list(command), Path(cwd), dict(environment)))
        if "--version" in command:
            version = self.versions.get(command[3], "1.0.0")
            if version is None:
                return 1, "exited 1", False
            report.write_text(f"{command[3]} {version}\n", encoding="utf-8")
            return 0, None, False
        if "mypy" in command:
            prefix = Path(cwd).resolve().relative_to(self._source_root(cwd)).as_posix()
            prefix = "" if prefix == "." else prefix + "/"
            if self.mypy_text is not None and not prefix:
                report.write_text(self.mypy_text, encoding="utf-8")
                return self.mypy_exit.get(".", 1), None, False
            files = command[command.index("--") + 1 :]
            lines = [
                json.dumps({**r, "file": r["file"][len(prefix) :]})
                for f in files
                for r in self.mypy_records.get(prefix + f, [])
            ]
            report.write_text("".join(line + "\n" for line in lines), encoding="utf-8")
            status = self.mypy_exit.get(prefix or ".", 1 if lines else 0)
            return status, None if status in (0, 1) else f"exited {status}", False
        if "ruff" in command:
            records = self._ruff_answer(command)
            text = self.ruff_text if self.ruff_text is not None else json.dumps(records)
            # Ruff names the files it read absolutely, under the staged source the
            # producers ran in, never the checkout (#389 F3 S2 B).
            report.write_text(self._staged_text(text, cwd), encoding="utf-8")
            if self.ruff_exit is None:
                # Ruff's own status: 1 only when it reports a diagnostic (_ruff_gap).
                return (1 if records else 0), None, False
            return self.ruff_exit, None, False
        if command == self._observation_command():
            # The producers' environment observation (#389 F3 S2-C): one fixed
            # installed set, unless a test answers the observation itself.
            report.write_text(self._observation(), encoding="utf-8")
            return 0, None, False
        raise AssertionError(f"unexpected producer: {command}")

    def _ruff_answer(self, command: list[str]) -> list:
        """The records the fake Ruff reports for `command`: every record a test holds,
        for the report-parsing and budget tests, unless `ruff_as_ruff` makes it answer
        as Ruff does, with only its selected rules on the files it was given (#389
        A0-MP1). A record that names no rule or no file of the fixture stays either
        way."""
        if not self.ruff_as_ruff:
            return list(self.ruff_records)
        selected = set(command[command.index("--select") + 1].split(","))
        given = set(command[command.index("--") + 1 :])
        root = self.root.resolve()

        def reported(record) -> bool:
            if not isinstance(record, dict):
                return True
            code, name = record.get("code"), record.get("filename")
            if not isinstance(code, str) or not isinstance(name, str):
                return True
            if not Path(name).is_relative_to(root):
                return True
            return code in selected and Path(name).relative_to(root).as_posix() in given

        return [record for record in self.ruff_records if reported(record)]

    def _observation_command(self) -> list[str]:
        """The observation launch the collector must compose, pinned here rather than
        read from it: the observer beside the collector's module, the measured caps and
        the v2 format. A launcher answers exactly this and refuses any other, so that a
        moved observer, cap or format fails its tests (CodeAnt and cubic on #452)."""
        caps = {
            "roots": 32,
            "entries_per_root": 4096,
            "entries": 16384,
            "distributions": 1024,
            "file_bytes": 64 * 1024 * 1024,
            "file_bytes_total": 256 * 1024 * 1024,
            "string_bytes": 4096,
            "output_bytes": 1024 * 1024,
            "tree_directories": 8192,
            "tree_entries": 131072,
            "tree_depth": 32,
            "record_rows": 131072,
            "unlisted": 1024,
        }
        module_file = self.module.__file__
        assert module_file is not None
        observer = Path(module_file).resolve().parent
        return [
            sys.executable,
            "-I",
            str(observer / "python_environment_observation.py"),
            json.dumps(caps, sort_keys=True),
            "gnostoa-producer-environment-observation/v2",
        ]

    def _restored_environment(self):
        """A launcher whose environment is A, becomes B while mypy runs, and is A
        again after Ruff, before the last observation: the case equal endpoints
        cannot see (PAO 6347682576; cubic on #452)."""
        # Unannotated, as in the fixture's other untyped helpers: an annotation in
        # an untyped body is a mypy note the inventory acquires.
        installed = {"now": ()}

        def run(command, *, cwd, environment, report, deadline, limits):
            if command == self._observation_command():
                report.write_text(self._observation(installed["now"]), encoding="utf-8")
                return 0, None, False
            if "--version" not in command and "mypy" in command:
                installed["now"] = ("probe-dep-1.0",)
            elif "--version" not in command and "ruff" in command:
                installed["now"] = ()
            return self._fake_run(
                command,
                cwd=cwd,
                environment=environment,
                report=report,
                deadline=deadline,
                limits=limits,
            )

        return run

    def _observation(
        self,
        installed: tuple[str, ...] = ("fixture-1.0",),
        incomplete: str | None = None,
    ) -> str:
        """An environment observation in the collector's own format, whose one root
        holds a `*.dist-info` for each of `installed`."""
        root = "/fixture/site-packages"
        names = sorted(f"{name}.dist-info" for name in installed)
        return json.dumps(
            {
                "format": self.module.ENVIRONMENT_OBSERVATION_FORMAT,
                "incomplete": incomplete,
                "interpreter": {"executable": "/fixture/python", "version": "3.12"},
                "roots": [root],
                "entries": {root: names},
                "archives": [],
                "distributions": [[root, name, "0" * 64] for name in names],
                "unlisted": [],
            },
            sort_keys=True,
        )

    def _inventory(self, **options) -> dict:
        with patch("tools.quality_evidence._bounded_run", side_effect=self._fake_run):
            path = self.collect(self.root, self.output, **options)
        self.run_directory = Path(path).parent
        return self._read(path)

    def _tracked_fifo(self):
        """Replace tools/sample.py with a FIFO. Opening one waits for a writer, so a
        thread becomes that writer after two seconds unless the returned `done` is
        called first: a regression is slow and fails instead of hanging (CodeAnt on
        #436)."""
        fifo = self.root / "tools" / "sample.py"
        fifo.unlink()
        os.mkfifo(fifo)
        stop = threading.Event()

        def release() -> None:
            if stop.wait(2.0):
                return
            end = time.monotonic() + 3.0
            while time.monotonic() < end and not stop.is_set():
                try:
                    os.close(os.open(fifo, os.O_WRONLY | os.O_NONBLOCK))
                    return
                except OSError:
                    time.sleep(0.05)

        writer = threading.Thread(target=release, daemon=True)
        writer.start()

        def done() -> None:
            stop.set()
            writer.join(5)

        return done

    def _read_raises(self, error: type[BaseException], path: str):
        """Patches making the metric's existing stream read raise `error` for `path`
        alone, and the streams they replaced: the boundary is exercised by injection,
        never by exhausting memory (the Router's L2, 6228117951 on #436)."""
        target = os.path.realpath(self.root / path)
        # The same file in a run's staged source, `<output>/<run>/source/<path>`, the
        # producers' root (#389 F3 S2 B); opened for reading alone.
        staged = os.sep + os.path.join("source", path)
        output = os.path.realpath(self.output) + os.sep
        failing: set[int] = set()
        streams: list[_RaisingRead] = []
        real_open, real_fdopen = os.open, os.fdopen

        def matches(name, flags) -> bool:
            if flags & (os.O_WRONLY | os.O_RDWR):
                return False
            real = os.path.realpath(name)
            return real == target or (real.startswith(output) and real.endswith(staged))

        def opening(name, flags, *args, **kwargs):
            descriptor = real_open(name, flags, *args, **kwargs)
            if matches(name, flags):
                failing.add(descriptor)
            else:
                failing.discard(descriptor)
            return descriptor

        def wrapping(descriptor, *args, **kwargs):
            stream = real_fdopen(descriptor, *args, **kwargs)
            if descriptor not in failing:
                return stream
            failing.discard(descriptor)
            streams.append(_RaisingRead(stream, error))
            return streams[-1]

        return (
            patch.object(self.module.os, "open", side_effect=opening),
            patch.object(self.module.os, "fdopen", side_effect=wrapping),
            streams,
        )

    def _opened_sources(
        self,
    ) -> tuple[contextlib.AbstractContextManager[None], list[str]]:
        """A patch recording which tracked sources the metric opens, and their list.
        The metric is the original the patch hands its new_callable (spec=True)."""
        opened: list[str] = []
        real_open = os.open
        roots = [os.path.realpath(self.root)]

        def opening(name, flags, *args, **kwargs):
            path = os.path.realpath(name)
            for root in roots[1:]:
                if path.startswith(root + os.sep) and path.endswith(".py"):
                    opened.append(os.path.relpath(path, root))
            return real_open(name, flags, *args, **kwargs)

        def measuring(*, spec):
            def metric(root, *args, **kwargs):
                roots.append(os.path.realpath(root))
                try:
                    return spec(root, *args, **kwargs)
                finally:
                    roots.pop()

            return MagicMock(side_effect=metric)

        @contextlib.contextmanager
        def spying():
            with (
                patch.object(self.module.os, "open", side_effect=opening),
                patch.object(
                    self.module, "_run_complexity", spec=True, new_callable=measuring
                ),
            ):
                yield

        return spying(), opened

    def _with_a_real_main_mypy(self, script: str):
        """A patch of _bounded_run under which the main mypy group runs `script` in a
        real child, through the real runner; every other producer is the fake. The
        real runner is the original the patch hands its new_callable (spec=True)."""

        def delegate(*, spec):
            def run(command, **options):
                cwd = Path(options["cwd"]).resolve()
                main = cwd == self._source_root(cwd)
                if main and "mypy" in command and "--version" not in command:
                    return spec([sys.executable, "-I", "-c", script], **options)
                return self._fake_run(command, **options)

            return MagicMock(side_effect=run)

        return patch.object(
            self.module, "_bounded_run", spec=True, new_callable=delegate
        )

    def _two_batches(self) -> tuple[str, str]:
        """A child script writing one mypy record, then, a moment later, another."""
        first, second = (
            json.dumps(r) + "\n" for r in self.mypy_records["tests/test_sample.py"]
        )
        script = (
            "import sys, time\n"
            f"sys.stdout.write({first!r}); sys.stdout.flush(); time.sleep(0.5)\n"
            f"sys.stdout.write({second!r}); sys.stdout.flush()\n"
        )
        return script, first

    def _package(self, where: Path) -> Path:
        """A packaged root: the scope owner's manifest, and no `.git` of its own."""
        (where / "tools").mkdir(parents=True)
        (where / "tools" / "sample.py").write_text("def f(x):\n    return x\n")
        (where / ".gnostoa-source-files").write_bytes(b"tools/sample.py\0")
        return where

    def _collect_spied(self, root: Path, output: Path, **options):
        def quiet(command, *, cwd, environment, report, deadline, limits):
            # A root outside the fixture's repository: the version answer, no findings.
            if "--version" in command:
                report.write_text(f"{command[3]} 1.0.0\n", encoding="utf-8")
            else:
                report.write_text("[]" if "ruff" in command else "", encoding="utf-8")
            return 0, None, False

        inside = root.resolve().is_relative_to(self.root.resolve())
        state = _v1_subject_spy()
        with (
            patch(
                "tools.quality_evidence._bounded_run",
                side_effect=self._fake_run if inside else quiet,
            ),
            patch.object(self.module, "_git_state", state),
            patch.object(
                self.module,
                "_diagnostic_git",
                spec=True,
                new_callable=_calling_through,
            ) as comparison,
        ):
            path = self.collect(root, output, **options)
        return self._read(path), state, comparison

    def _refused_spied(self, root: Path, **options):
        state = _v1_subject_spy()
        with (
            patch("tools.quality_evidence._bounded_run", side_effect=self._fake_run),
            patch.object(self.module, "_git_state", state),
            patch.object(
                self.module,
                "_diagnostic_git",
                spec=True,
                new_callable=_calling_through,
            ) as comparison,
            self.assertRaises(QualityEvidenceError) as raised,
        ):
            self.collect(root, self.output, **options)
        return str(raised.exception), state, comparison

    def _ruff_alone(self, records, max_findings: int):
        """`_run_ruff` alone, over the fake producer's `records`, under `max_findings`."""
        self.ruff_records = records
        run = Path(tempfile.mkdtemp(prefix="ruff-run-", dir=self.directory.name))
        limits = self.module.DiagnosticLimits(max_findings=max_findings)
        with (
            patch("tools.quality_evidence._bounded_run", side_effect=self._fake_run),
            patch.object(
                self.module, "_run_ruff", spec=True, new_callable=_calling_through
            ) as ruff,
        ):
            # The original, through the spy the patch built around it.
            result = ruff(
                self.root,
                run,
                ["tests/test_sample.py", "tools/sample.py"],
                limits,
                time.monotonic() + 30,
                "1.0.0",
            )
        return result, run

    def _late_by(self, stage: str):
        """A clock that passes the deadline during `stage`: the inventory document's
        serialization, or the creation of its output handle (the Router's T1), seen
        at the exclusive open of the inventory's name that creates it."""
        clock = [1000.0]
        real_dumps, real_open = json.dumps, os.open

        def dumps(value, *args, **kwargs):
            if (
                stage == "serialization"
                and isinstance(value, dict)
                and value.get("schema") == self.module.DIAGNOSTIC_SCHEMA
            ):
                clock[0] = 10_000.0
            return real_dumps(value, *args, **kwargs)

        def opening(name, flags, *args, **kwargs):
            if (
                stage == "output"
                and flags & os.O_CREAT
                and os.path.basename(name) == self.module.DIAGNOSTIC_INVENTORY
            ):
                clock[0] = 10_000.0
            return real_open(name, flags, *args, **kwargs)

        return (
            patch.object(self.module.time, "monotonic", side_effect=lambda: clock[0]),
            patch.object(self.module.json, "dumps", side_effect=dumps),
            patch.object(self.module.os, "open", side_effect=opening),
        )

    @staticmethod
    def _timeouts_overflow() -> bool:
        """Whether this platform's subprocess refuses a 1e20 timeout as OverflowError
        when it captures output, as the Git reads do, and as CPython 3.12 and 3.14 on
        Linux do (measured): only communicate's selector converts the timeout."""
        try:
            subprocess.run(  # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-audit.dangerous-subprocess-use-audit  # nosec B603 -- test-only: this interpreter, an empty literal script
                [sys.executable, "-c", ""],
                capture_output=True,
                timeout=1e20,
                check=False,
            )
        except OverflowError:
            return True
        return False

    def _written(self) -> str:
        return (self.run_directory / self.module.DIAGNOSTIC_INVENTORY).read_text(
            encoding="utf-8"
        )

    def _report_read_raises(self, pattern: str, error: OSError):
        """A patch making the read of the one report whose name matches `pattern`
        raise `error`."""
        original = Path.read_text

        def reading(path, *args, **kwargs):
            if path.match(pattern):
                raise error
            return original(path, *args, **kwargs)

        return patch.object(Path, "read_text", autospec=True, side_effect=reading)

    def _reasons(self, inventory: dict) -> dict[str, str]:
        return {
            u["path"]: u["reason"] for u in inventory["scope"]["full"]["unanalyzed"]
        }

    @contextlib.contextmanager
    def _watched_work(self):
        """Spies, by name, on each piece of work a diagnostic collection does, where
        v2 does it: the producers, the scope owner's metadata check (`subject`), the
        exact-tree owner's enumeration (`scope`) and staging (`stage`), which run their
        own Git, and every `_diagnostic_git` read (`git_reads`): the freeze's object
        resolution as well as the comparison's (Amazon Q and Claude on #451).
        `candidate_paths` and `_git_state` are watched as D1's negatives: neither is on
        the diagnostic path, nor may come back onto it; `_git_state`'s spy answers no
        call (`_v1_subject_spy`)."""
        owner = importlib.import_module("tools.exact_tree")
        with (
            patch.object(
                self.module, "_bounded_run", side_effect=self._fake_run
            ) as producer,
            patch.object(
                self.module, "has_git_metadata", wraps=self.module.has_git_metadata
            ) as subject,
            patch.object(owner, "tree_paths", wraps=owner.tree_paths) as scope,
            patch.object(owner, "materialize", wraps=owner.materialize) as stage,
            patch.object(
                self.module, "_diagnostic_git", spec=True, new_callable=_wrapping
            ) as git_reads,
            patch.object(
                self.module, "candidate_paths", wraps=self.module.candidate_paths
            ) as v1_scope,
            patch.object(self.module, "_git_state", _v1_subject_spy()) as v1_subject,
        ):
            yield {
                "producer": producer,
                "subject": subject,
                "scope": scope,
                "stage": stage,
                "git_reads": git_reads,
                "v1_scope": v1_scope,
                "v1_subject": v1_subject,
            }

    def _refused(self, environment: dict[str, str]) -> QualityEvidenceError:
        """Collect under `environment`, and return the refusal. No work watched by
        `_watched_work` may start, no output may be written, and the caller's
        environment must be left as it was."""
        with patch.dict(os.environ, environment), self._watched_work() as watched:
            before = dict(os.environ)
            # Any other exception fails the test by itself (SonarCloud S8714 on #436).
            with self.assertRaises(QualityEvidenceError) as raised:
                self.collect(self.root, self.output, base=self.base)
            refusal = raised.exception
            self.assertEqual(
                before, dict(os.environ), "the caller's environment changed"
            )
        for work in watched.values():
            work.assert_not_called()
        self.assertFalse(self.output.exists(), "a refused call wrote output")
        self.assertIn("no inventory was written", str(refusal))
        return refusal

    def _changed_once(self) -> None:
        sample = self.root / "tools" / "sample.py"
        sample.write_text(
            sample.read_text(encoding="utf-8") + "# changed\n", encoding="utf-8"
        )
        self._git("add", "-A")
        self._git("commit", "-q", "-m", "one change")

    def _uncompared(self, base: str, reader=None) -> dict:
        """Collect against `base` and require the comparison's named gap: no diff
        read, no comparison published, every finding kept with in_diff null. Each
        real function is the original its patch hands its new_callable (spec=True)."""
        comparing: list[bool] = []

        def annotation(*, spec):
            def annotating(*args, **kwargs):
                comparing.append(True)
                try:
                    return spec(*args, **kwargs)
                finally:
                    comparing.pop()

            return MagicMock(side_effect=annotating)

        def comparison(*, spec):
            chosen = reader or spec

            def comparison_only(root, deadline, *arguments, **options):
                # The reader under test answers the comparison's reads alone, while
                # the comparison runs; the freeze's reads of the subject's own commit
                # and tree stay real, whatever they name (#389 F3 S2 B; Amazon Q on
                # #451).
                read = chosen if comparing else spec
                return read(root, deadline, *arguments, **options)

            return MagicMock(side_effect=comparison_only)

        with (
            patch.object(
                self.module, "_diagnostic_git", spec=True, new_callable=comparison
            ) as git,
            patch.object(
                self.module, "_annotate_diff", spec=True, new_callable=annotation
            ),
        ):
            inventory = self._inventory(base=base)
        self.assertNotIn("diff", [call.args[2] for call in git.call_args_list])
        self.assertIsNone(inventory["scope"]["diff"])
        self.assertTrue(inventory["findings"])
        self.assertEqual(
            {None}, {f["native"]["in_diff"] for f in inventory["findings"]}
        )
        self.assertIn("cannot compare with base", inventory["coverage"]["reason"])
        return inventory
