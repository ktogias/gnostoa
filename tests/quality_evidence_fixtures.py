"""The diagnostic inventory tests' private fixtures (#389 F3 S2 B, Router 6326577610):
the fixture repository, the faked producers and their helpers, shared by the
inventory's test modules. It holds no test, so discovery runs none of it twice."""

from __future__ import annotations

import contextlib
import importlib
import json
import os
import subprocess  # nosec B404 -- test-only: drives git on temporary fixture repositories
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

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


class _DiagnosticFixture(unittest.TestCase):
    """A small tracked repository, and the helpers the inventory tests share."""

    def setUp(self) -> None:
        self.module = importlib.import_module("tools.quality_evidence")
        self.collect = self.module.collect_diagnostic_inventory
        # Each test runs without the caller's Git overrides, which the inventory
        # refuses: preparation's own environment sets GIT_CONFIG_* for its children
        # (Router 6223042901 on #436, R1). The refusal tests set theirs explicitly.
        owner = importlib.import_module("tools.candidate_prepare")
        self.enterContext(patch.dict(os.environ))
        for name in set(os.environ) - set(owner._git_env_without_caller_overrides()):
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
    def _then(real, failure):
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
        self.ruff_text: str | None = None
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
            report.write_text(f"{command[3]} 1.0.0\n", encoding="utf-8")
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
            text = (
                self.ruff_text
                if self.ruff_text is not None
                else json.dumps(self.ruff_records)
            )
            # Ruff names the files it read absolutely, under the staged source the
            # producers ran in, never the checkout (#389 F3 S2 B).
            report.write_text(self._staged_text(text, cwd), encoding="utf-8")
            return self.ruff_exit, None, False
        if command == self._observation_command():
            # The producers' environment observation (#389 F3 S2-C): one fixed
            # installed set, unless a test answers the observation itself.
            report.write_text(self._observation(), encoding="utf-8")
            return 0, None, False
        raise AssertionError(f"unexpected producer: {command}")

    def _observation_command(self) -> list[str]:
        """The observation launch as the collector must compose it, built here rather
        than taken from the collector, so that a launcher answers it and refuses any
        other (CodeAnt on #452)."""
        return [
            sys.executable,
            "-I",
            str(self.module._OBSERVER),
            json.dumps(self.module.ENVIRONMENT_OBSERVATION_CAPS, sort_keys=True),
            self.module.ENVIRONMENT_OBSERVATION_FORMAT,
        ]

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

    def _opened_sources(self):
        """A patch recording which tracked sources are opened, and their list."""
        opened: list[str] = []
        real_open, real_metric = os.open, self.module._run_complexity
        roots = [os.path.realpath(self.root)]

        def opening(name, flags, *args, **kwargs):
            path = os.path.realpath(name)
            for root in roots[1:]:
                if path.startswith(root + os.sep) and path.endswith(".py"):
                    opened.append(os.path.relpath(path, root))
            return real_open(name, flags, *args, **kwargs)

        def metric(root, *args, **kwargs):
            roots.append(os.path.realpath(root))
            try:
                return real_metric(root, *args, **kwargs)
            finally:
                roots.pop()

        @contextlib.contextmanager
        def spying():
            with (
                patch.object(self.module.os, "open", side_effect=opening),
                patch.object(self.module, "_run_complexity", side_effect=metric),
            ):
                yield

        return spying(), opened

    def _with_a_real_main_mypy(self, script: str):
        """A patch of _bounded_run under which the main mypy group runs `script` in a
        real child, through the real runner; every other producer is the fake."""
        real = self.module._bounded_run

        def run(command, **options):
            cwd = Path(options["cwd"]).resolve()
            main = cwd == self._source_root(cwd)
            if main and "mypy" in command and "--version" not in command:
                return real([sys.executable, "-I", "-c", script], **options)
            return self._fake_run(command, **options)

        return patch("tools.quality_evidence._bounded_run", side_effect=run)

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
        state = Mock(side_effect=self.module._git_state)
        comparison = Mock(side_effect=self.module._diagnostic_git)
        with (
            patch(
                "tools.quality_evidence._bounded_run",
                side_effect=self._fake_run if inside else quiet,
            ),
            patch.object(self.module, "_git_state", state),
            patch.object(self.module, "_diagnostic_git", comparison),
        ):
            path = self.collect(root, output, **options)
        return self._read(path), state, comparison

    def _refused_spied(self, root: Path, **options):
        state = Mock(side_effect=self.module._git_state)
        comparison = Mock(side_effect=self.module._diagnostic_git)
        with (
            patch("tools.quality_evidence._bounded_run", side_effect=self._fake_run),
            patch.object(self.module, "_git_state", state),
            patch.object(self.module, "_diagnostic_git", comparison),
            self.assertRaises(QualityEvidenceError) as raised,
        ):
            self.collect(root, self.output, **options)
        return str(raised.exception), state, comparison

    def _ruff_alone(self, records, max_findings: int):
        """`_run_ruff` alone, over the fake producer's `records`, under `max_findings`."""
        self.ruff_records = records
        run = Path(tempfile.mkdtemp(prefix="ruff-run-", dir=self.directory.name))
        limits = self.module.DiagnosticLimits(max_findings=max_findings)
        with patch("tools.quality_evidence._bounded_run", side_effect=self._fake_run):
            result = self.module._run_ruff(
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
        serialization, or the creation of its output handle (the Router's T1)."""
        clock = [1000.0]
        real_dumps, real_new_file = json.dumps, self.module._new_file

        def dumps(value, *args, **kwargs):
            if (
                stage == "serialization"
                and isinstance(value, dict)
                and value.get("schema") == self.module.DIAGNOSTIC_SCHEMA
            ):
                clock[0] = 10_000.0
            return real_dumps(value, *args, **kwargs)

        def new_file(path):
            if stage == "output" and path.name == self.module.DIAGNOSTIC_INVENTORY:
                clock[0] = 10_000.0
            return real_new_file(path)

        return (
            patch.object(self.module.time, "monotonic", side_effect=lambda: clock[0]),
            patch.object(self.module.json, "dumps", side_effect=dumps),
            patch.object(self.module, "_new_file", side_effect=new_file),
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
        the diagnostic path, nor may come back onto it."""
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
                self.module, "_diagnostic_git", wraps=self.module._diagnostic_git
            ) as git_reads,
            patch.object(
                self.module, "candidate_paths", wraps=self.module.candidate_paths
            ) as v1_scope,
            patch.object(
                self.module, "_git_state", wraps=self.module._git_state
            ) as v1_subject,
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
        read, no comparison published, every finding kept with in_diff null."""
        real, real_annotate = self.module._diagnostic_git, self.module._annotate_diff
        chosen = reader or real
        comparing: list[bool] = []

        def annotating(*args, **kwargs):
            comparing.append(True)
            try:
                return real_annotate(*args, **kwargs)
            finally:
                comparing.pop()

        def comparison_only(root, deadline, *arguments, **options):
            # The reader under test answers the comparison's reads alone, while the
            # comparison runs; the freeze's reads of the subject's own commit and tree
            # stay real, whatever they name (#389 F3 S2 B; Amazon Q on #451).
            read = chosen if comparing else real
            return read(root, deadline, *arguments, **options)

        with (
            patch.object(
                self.module, "_diagnostic_git", side_effect=comparison_only
            ) as git,
            patch.object(self.module, "_annotate_diff", side_effect=annotating),
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
