"""The one owner of trusted execution (Decision 0102, #368).

These tests hold its rules. The rules for executables were proven by review on #364
and move here unchanged.
"""

from __future__ import annotations

import functools
import inspect
import os
import pathlib
import re
import shlex
import shutil
import stat
import subprocess  # nosec B404
import tarfile
import tempfile
import unittest
from typing import Any
from unittest import mock

from tools import trusted_execution

# A caller's routing and trust roots: a proxy, and the certificates that would
# authenticate an intercepting one (Codex on #369).
_CALLER_ROUTING = {
    name: f"/caller/{name.lower()}"
    for name in (
        "http_proxy",
        "HTTP_PROXY",
        "https_proxy",
        "HTTPS_PROXY",
        "all_proxy",
        "ALL_PROXY",
        "no_proxy",
        "NO_PROXY",
        "SSL_CERT_FILE",
        "SSL_CERT_DIR",
        "CURL_CA_BUNDLE",
        "OPENSSL_CONF",
        "GIT_SSL_CAINFO",
        "GIT_SSL_CAPATH",
        "GIT_SSL_NO_VERIFY",
        "GIT_PROXY_COMMAND",
    )
}

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _git(repository: pathlib.Path, *arguments: str) -> str:
    """Run git for a fixture, as the caller would, not through the owner."""
    completed = subprocess.run(  # nosec B603 B607
        ["git", "-C", str(repository), *arguments],
        check=True,
        capture_output=True,
        text=True,
        env={
            "PATH": "/usr/bin:/bin",
            "HOME": str(repository),
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_AUTHOR_NAME": "a",
            "GIT_AUTHOR_EMAIL": "a@example.invalid",
            "GIT_COMMITTER_NAME": "a",
            "GIT_COMMITTER_EMAIL": "a@example.invalid",
        },
    )
    return completed.stdout.strip()


def _tool(directory: pathlib.Path, name: str = "tool") -> pathlib.Path:
    directory.mkdir(parents=True, exist_ok=True)
    tool = directory / name
    tool.write_text("#!/bin/sh\n", encoding="utf-8")
    tool.chmod(0o755)
    return tool


class TrustedExecutableTests(unittest.TestCase):
    """An authority or judge path's tool comes from the fixed system directories."""

    def test_the_directories_are_the_preparation_wrapper_s(self) -> None:
        """`ci/prepare-candidate` is shell and cannot import this module, so the two
        lists are held equal here instead of drifting apart."""
        wrapper = (ROOT / "ci" / "prepare-candidate").read_text(encoding="utf-8")
        declared = re.search(r"^PATH=(\S+)$", wrapper, re.MULTILINE)
        if declared is None:
            self.fail("the preparation wrapper declares no trusted PATH")
        self.assertEqual(declared.group(1), trusted_execution.TRUSTED_EXECUTABLE_PATH)

    def test_the_caller_s_path_is_never_searched(self) -> None:
        with tempfile.TemporaryDirectory() as scratch:
            tool = _tool(pathlib.Path(scratch) / "bin", "gh")
            with mock.patch.object(shutil, "which", return_value=str(tool)) as which:
                self.assertEqual(
                    str(tool.resolve()), trusted_execution.trusted_executable("gh")
                )
        which.assert_called_once_with(
            "gh", path=trusted_execution.TRUSTED_EXECUTABLE_PATH
        )

    def test_a_found_executable_others_can_replace_is_refused(self) -> None:
        """What the search finds is held to `trusted_path`: a directory others can
        write chooses which binary runs (CodeAnt on #364)."""
        for file_mode, dir_mode in ((0o775, 0o755), (0o755, 0o775), (0o755, 0o777)):
            with tempfile.TemporaryDirectory() as scratch:
                directory = pathlib.Path(scratch) / "bin"
                tool = _tool(directory, "gh")
                tool.chmod(file_mode)
                directory.chmod(dir_mode)
                with (
                    self.subTest(file=oct(file_mode), directory=oct(dir_mode)),
                    mock.patch.object(shutil, "which", return_value=str(tool)),
                ):
                    self.assertIsNone(trusted_execution.trusted_executable("gh"))
                directory.chmod(0o755)

    def test_a_missing_executable_is_none(self) -> None:
        with mock.patch.object(shutil, "which", return_value=None):
            self.assertIsNone(trusted_execution.trusted_executable("gh"))


class TrustedExecutableNameTests(unittest.TestCase):
    def test_a_name_with_a_directory_is_refused(self) -> None:
        """`shutil.which` ignores its search path for a name with a slash, so a
        caller-owned program anywhere would pass (CodeAnt on #369)."""
        with tempfile.TemporaryDirectory() as scratch:
            tool = _tool(pathlib.Path(scratch) / "bin")
            for name in (str(tool), f"./{tool.name}", f"bin/{tool.name}"):
                with self.subTest(name=name):
                    self.assertIsNone(trusted_execution.trusted_executable(name))


class OperatorExecutableTests(unittest.TestCase):
    """A tool the operator chooses is found on the caller's `PATH`, by name only."""

    def test_the_caller_s_path_is_searched(self) -> None:
        with tempfile.TemporaryDirectory() as scratch:
            tool = _tool(pathlib.Path(scratch), "sandbox")
            with mock.patch.dict(os.environ, {"PATH": scratch}):
                self.assertEqual(
                    str(tool), trusted_execution.operator_executable("sandbox")
                )
            with mock.patch.dict(os.environ, {"PATH": "/nonexistent"}):
                self.assertIsNone(trusted_execution.operator_executable("sandbox"))


class TrustedDirectoryTests(unittest.TestCase):
    def test_only_a_directory_no_one_else_may_change_is_trusted(self) -> None:
        """`trusted_path`'s walk, ending at a directory (CodeAnt on #369)."""
        with tempfile.TemporaryDirectory() as scratch:
            base = pathlib.Path(scratch)
            (base / "file").write_text("x", encoding="utf-8")
            (base / "open").mkdir()
            (base / "open").chmod(0o777)
            self.assertEqual(
                os.path.realpath(scratch), trusted_execution.trusted_directory(scratch)
            )
            for found in (str(base / "file"), str(base / "open"), "relative/dir"):
                with self.subTest(found=found):
                    self.assertIsNone(trusted_execution.trusted_directory(found))


class TrustedPathTests(unittest.TestCase):
    """A path is walked one component at a time, judging every link before following
    it (Codex, CodeAnt and gitar on #364)."""

    def test_a_path_only_root_or_the_caller_can_change_is_trusted(self) -> None:
        with tempfile.TemporaryDirectory() as scratch:
            tool = _tool(pathlib.Path(scratch) / "bin")
            self.assertEqual(
                str(tool.resolve()), trusted_execution.trusted_path(str(tool))
            )

    def test_a_file_or_directory_others_can_change_is_refused(self) -> None:
        for file_mode, dir_mode in (
            (0o775, 0o755),
            (0o757, 0o755),
            (0o755, 0o775),
            (0o755, 0o777),
        ):
            with tempfile.TemporaryDirectory() as scratch:
                directory = pathlib.Path(scratch) / "bin"
                tool = _tool(directory)
                tool.chmod(file_mode)
                directory.chmod(dir_mode)
                with self.subTest(file=oct(file_mode), directory=oct(dir_mode)):
                    self.assertIsNone(trusted_execution.trusted_path(str(tool)))
                directory.chmod(0o755)

    def test_a_link_is_judged_by_its_own_directory_and_its_target(self) -> None:
        with tempfile.TemporaryDirectory() as scratch:
            base = pathlib.Path(scratch)
            target = _tool(base / "real")
            (base / "links").mkdir()
            link = base / "links" / "tool"
            link.symlink_to(target)
            self.assertEqual(
                str(target.resolve()), trusted_execution.trusted_path(str(link))
            )
            for changed in (base / "links", base / "real"):
                with self.subTest(writable=changed.name):
                    changed.chmod(0o775)
                    self.assertIsNone(trusted_execution.trusted_path(str(link)))
                    changed.chmod(0o755)

    def test_a_trailing_slash_names_no_file(self) -> None:
        """POSIX reads `x/` as a directory; the walk dropped the empty component and
        accepted a file (CodeAnt on #369)."""
        with tempfile.TemporaryDirectory() as scratch:
            base = pathlib.Path(scratch)
            tool = _tool(base / "bin")
            self.assertIsNone(trusted_execution.trusted_path(f"{tool}/"))
            (base / "links").mkdir()
            link = base / "links" / "tool"
            link.symlink_to(f"{tool}/")
            self.assertIsNone(trusted_execution.trusted_path(str(link)))

    def test_a_file_on_the_way_is_no_path(self) -> None:
        """Only the last component may be a file; a path through one names nothing."""
        with tempfile.TemporaryDirectory() as scratch:
            tool = _tool(pathlib.Path(scratch) / "bin")
            self.assertIsNone(trusted_execution.trusted_path(f"{tool}/more"))

    def test_a_relative_link_s_parent_component_is_followed_up(self) -> None:
        """A relative target's `..` climbs from the link's own directory."""
        with tempfile.TemporaryDirectory() as scratch:
            base = pathlib.Path(scratch)
            target = _tool(base / "real")
            (base / "links" / "deep").mkdir(parents=True)
            link = base / "links" / "deep" / "tool"
            link.symlink_to("../../real/tool")
            self.assertEqual(
                str(target.resolve()), trusted_execution.trusted_path(str(link))
            )

    def test_every_link_in_a_chain_is_judged_by_its_own_directory(self) -> None:
        with tempfile.TemporaryDirectory() as scratch:
            base = pathlib.Path(scratch)
            target = _tool(base / "real")
            (base / "shared").mkdir()
            (base / "safe").mkdir()
            (base / "shared" / "tool").symlink_to(target)
            (base / "safe" / "tool").symlink_to(base / "shared" / "tool")
            first = str(base / "safe" / "tool")
            self.assertEqual(
                str(target.resolve()), trusted_execution.trusted_path(first)
            )
            (base / "shared").chmod(0o775)
            self.assertIsNone(trusted_execution.trusted_path(first))
            (base / "shared").chmod(0o755)

    def test_a_link_loop_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as scratch:
            base = pathlib.Path(scratch)
            (base / "a").symlink_to(base / "b")
            (base / "b").symlink_to(base / "a")
            self.assertIsNone(trusted_execution.trusted_path(str(base / "a")))

    def test_every_directory_above_is_judged_and_a_sticky_one_holds(self) -> None:
        with tempfile.TemporaryDirectory() as scratch:
            above = pathlib.Path(scratch) / "above"
            tool = _tool(above / "bin")
            above.chmod(0o775)
            self.assertIsNone(trusted_execution.trusted_path(str(tool)))
            above.chmod(0o1777)
            self.assertEqual(
                str(tool.resolve()), trusted_execution.trusted_path(str(tool))
            )
            above.chmod(0o755)

    def test_a_directory_link_is_judged_where_it_leads(self) -> None:
        with tempfile.TemporaryDirectory() as scratch:
            base = pathlib.Path(scratch)
            tool = _tool(base / "shared" / "real")
            (base / "safe").mkdir()
            (base / "safe" / "link").symlink_to(base / "shared" / "real")
            through = str(base / "safe" / "link" / "tool")
            self.assertEqual(
                str(tool.resolve()), trusted_execution.trusted_path(through)
            )
            (base / "shared").chmod(0o775)
            self.assertIsNone(trusted_execution.trusted_path(through))
            (base / "shared").chmod(0o755)

    def test_a_directory_link_is_judged_by_its_own_owner(self) -> None:
        """In a sticky directory a link's owner can repoint it; another user's link
        stands as a caller other than the link's owner."""
        temporary = tempfile.gettempdir()
        held = os.stat(temporary)
        if held.st_uid != 0 or not held.st_mode & stat.S_ISVTX:
            self.skipTest("the temporary directory is not root's and sticky")
        if os.getuid() == 0:
            # A link root makes is root's whoever the caller stands as (Codex on #369).
            self.skipTest("root cannot stand as another user here")
        shell = shutil.which("sh", path="/usr/bin:/bin")
        if shell is None:
            self.skipTest("no sh in the system directories")
        link = pathlib.Path(temporary) / f"gnostoa-link-{os.getpid()}-{id(self)}"
        link.symlink_to(os.path.dirname(os.path.realpath(shell)))
        self.addCleanup(link.unlink)
        through = str(link / "sh")
        self.assertIsNotNone(trusted_execution.trusted_path(through))
        with mock.patch("os.getuid", return_value=4242):
            self.assertIsNone(trusted_execution.trusted_path(through))

    def test_a_relative_or_missing_path_is_not_trusted(self) -> None:
        self.assertIsNone(trusted_execution.trusted_path("gh"))
        self.assertIsNone(trusted_execution.trusted_path("/nonexistent/gnostoa/gh"))


class GitEnvironmentTests(unittest.TestCase):
    """Git runs on an allowlist: nothing of the caller's is inherited by default."""

    def test_nothing_of_the_caller_s_is_inherited(self) -> None:
        """A scrub list misses the next variable, as `GIT_EXEC_PATH` showed on #364."""
        caller = {
            "GIT_EXEC_PATH": "/planted",
            "GIT_TRACE": "/planted/trace",
            "GIT_DIR": "/elsewhere",
            "HOME": "/home/caller",
            "XDG_CONFIG_HOME": "/home/caller/.config",
            "LD_PRELOAD": "/planted.so",
            "https_proxy": "http://proxy.invalid:3128",
        }
        with mock.patch.dict(os.environ, caller):
            environment = trusted_execution.git_environment()
        for name in caller:
            with self.subTest(variable=name):
                self.assertNotIn(name, environment)
        self.assertEqual(trusted_execution.TRUSTED_EXECUTABLE_PATH, environment["PATH"])
        for name, value in (
            ("GIT_CONFIG_GLOBAL", os.devnull),
            ("GIT_CONFIG_SYSTEM", os.devnull),
            ("GIT_CONFIG_NOSYSTEM", "1"),
            ("GIT_ATTR_NOSYSTEM", "1"),
            ("GIT_NO_REPLACE_OBJECTS", "1"),
            ("GIT_TERMINAL_PROMPT", "0"),
            ("GIT_NO_LAZY_FETCH", "1"),
            ("LC_ALL", "C"),
        ):
            with self.subTest(pinned=name):
                self.assertEqual(value, environment[name])

    def test_no_option_passes_the_caller_s_routing_or_trust_roots(self) -> None:
        """A caller's proxy, with the certificates that authenticate it, could
        counterfeit a fetch that every later check would find consistent (Codex on
        #369). So no option of the owner's passes them, a flag included."""
        flags: list[tuple[str, dict[str, Any]]] = [
            (name, {name: True})
            for name, parameter in inspect.signature(
                trusted_execution.git_environment
            ).parameters.items()
            if parameter.default is False
        ]
        with mock.patch.dict(os.environ, _CALLER_ROUTING):
            environments = {
                "transports": trusted_execution.git_environment(transports=("https",)),
                **{
                    name: trusted_execution.git_environment(**options)
                    for name, options in flags
                },
            }
        for option, environment in environments.items():
            with self.subTest(option=option):
                self.assertFalse(set(_CALLER_ROUTING) & set(environment), environment)

    def test_the_routing_a_call_names_is_added(self) -> None:
        environment = trusted_execution.git_environment(
            git_dir="/m/git",
            object_directory="/r/objects",
            work_tree="/w",
            index_file="/i",
        )
        self.assertEqual("/m/git", environment["GIT_DIR"])
        self.assertEqual("/r/objects", environment["GIT_OBJECT_DIRECTORY"])
        self.assertEqual("/w", environment["GIT_WORK_TREE"])
        self.assertEqual("/i", environment["GIT_INDEX_FILE"])

    def test_hooks_and_fsmonitor_are_off_whatever_the_repository_says(self) -> None:
        """Command-scope configuration outranks the repository's own."""
        with tempfile.TemporaryDirectory() as scratch:
            repository = pathlib.Path(scratch)
            _git(repository, "init", "--quiet")
            _git(repository, "config", "core.hooksPath", "/planted/hooks")
            _git(repository, "config", "core.fsmonitor", "/planted/monitor")
            git = trusted_execution.trusted_executable("git")
            self.assertIsNotNone(git)
            for key, expected in (
                ("core.hooksPath", os.devnull),
                ("core.fsmonitor", "false"),
            ):
                with self.subTest(key=key):
                    read = subprocess.run(  # nosec B603  # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-audit.dangerous-subprocess-use-audit
                        [str(git), "config", "--get", key],
                        cwd=repository,
                        capture_output=True,
                        text=True,
                        check=True,
                        env=trusted_execution.git_environment(),
                    )
                    self.assertEqual(expected, read.stdout.strip())

    def test_a_transport_list_refuses_every_other_transport(self) -> None:
        environment = trusted_execution.git_environment(transports=("https",))
        pairs = {
            environment[f"GIT_CONFIG_KEY_{n}"]: environment[f"GIT_CONFIG_VALUE_{n}"]
            for n in range(int(environment["GIT_CONFIG_COUNT"]))
        }
        self.assertEqual("never", pairs["protocol.allow"])
        self.assertEqual("always", pairs["protocol.https.allow"])
        self.assertNotIn(
            "protocol.allow", self._pairs(trusted_execution.git_environment())
        )

    @staticmethod
    def _pairs(environment: dict[str, str]) -> dict[str, str]:
        return {
            environment[f"GIT_CONFIG_KEY_{n}"]: environment[f"GIT_CONFIG_VALUE_{n}"]
            for n in range(int(environment["GIT_CONFIG_COUNT"]))
        }


class WithoutGitVariablesTests(unittest.TestCase):
    def test_every_git_variable_goes_whatever_its_name(self) -> None:
        cleaned = trusted_execution.without_git_variables(
            {
                "GIT_DIR": "x",
                "GIT_EXEC_PATH": "y",
                "GIT_SOMETHING_NEW": "z",
                "HOME": "/h",
            }
        )
        self.assertEqual({"HOME": "/h"}, cleaned)


class DisposableGitMetadataTests(unittest.TestCase):
    def test_a_bare_repository_bound_to_the_objects_and_gone_after(self) -> None:
        with tempfile.TemporaryDirectory() as scratch:
            repository = pathlib.Path(scratch) / "r"
            repository.mkdir()
            _git(repository, "init", "--quiet")
            objects = repository / ".git" / "objects"
            with trusted_execution.disposable_git_metadata(objects) as git_dir:
                self.assertTrue((git_dir / "HEAD").is_file())
                alternates = (git_dir / "objects" / "info" / "alternates").read_text(
                    encoding="utf-8"
                )
                self.assertEqual(str(objects.resolve()), alternates.strip())
                self.assertEqual(
                    [],
                    sorted((git_dir / "hooks").glob("*"))
                    if (git_dir / "hooks").exists()
                    else [],
                )
            self.assertFalse(git_dir.exists())


def _repository_with_a_local_filter(
    base: pathlib.Path,
) -> tuple[pathlib.Path, str, pathlib.Path]:
    """A repository whose own configuration names a filter that leaves a marker."""
    repository = base / "subject"
    repository.mkdir()
    _git(repository, "init", "--quiet")
    (repository / "kept.txt").write_text("kept\n", encoding="utf-8")
    (repository / "ignored.txt").write_text("ignored\n", encoding="utf-8")
    (repository / ".gitattributes").write_text(
        "ignored.txt export-ignore\n", encoding="utf-8"
    )
    _git(repository, "add", ".")
    _git(repository, "commit", "--quiet", "-m", "subject")
    tree = _git(repository, "rev-parse", "HEAD^{tree}")
    marker = base / "filter-ran"
    hit = base / "hit"
    hit.write_text(
        f"#!/bin/sh\nprintf x > {shlex.quote(str(marker))}\ncat\n", encoding="utf-8"
    )
    hit.chmod(0o755)
    (repository / ".git" / "info").mkdir(exist_ok=True)
    (repository / ".git" / "info" / "attributes").write_text(
        "* filter=evil\n", encoding="utf-8"
    )
    _git(repository, "config", "filter.evil.smudge", str(hit))
    return repository, tree, marker


def _signed_commit(repository: pathlib.Path, tree: str) -> str:
    """A commit that carries a signature, so a read that verifies it runs gpg."""
    body = repository.parent / "signed-commit"
    body.write_text(
        f"tree {tree}\n"
        "author a <a@example.invalid> 0 +0000\n"
        "committer a <a@example.invalid> 0 +0000\n"
        "gpgsig -----BEGIN PGP SIGNATURE-----\n"
        " \n"
        " iQEzBAABCAAdFiEE\n"
        " -----END PGP SIGNATURE-----\n"
        "\n"
        "signed\n",
        encoding="utf-8",
    )
    return _git(repository, "hash-object", "-t", "commit", "-w", str(body))


def _has_object(repository: pathlib.Path, name: str) -> bool:
    try:
        _git(repository, "cat-file", "-e", name)
    except subprocess.CalledProcessError:
        return False
    return True


class DisposableGitMetadataFailureTests(unittest.TestCase):
    def test_a_file_system_failure_while_setting_up_is_the_owner_s_error(self) -> None:
        """A failed temporary directory or alternates write escaped as a raw
        `OSError` past `capsule`'s blockers (CodeAnt on #369)."""
        with tempfile.TemporaryDirectory() as scratch:
            repository, _, _ = _repository_with_a_local_filter(pathlib.Path(scratch))
            objects = trusted_execution.repository_objects(repository)
            for target in ("tempfile.TemporaryDirectory", "pathlib.Path.write_text"):
                with (
                    self.subTest(failing=target),
                    mock.patch(target, side_effect=OSError(28, "No space left")),
                    self.assertRaises(trusted_execution.TrustedExecutionError),
                    trusted_execution.disposable_git_metadata(objects),
                ):
                    pass

    def test_an_object_store_path_with_a_newline_is_refused(self) -> None:
        """The alternates file is line-delimited, so a path holding a newline became
        two directories that do not exist, and the metadata bound to neither (Codex on
        #369)."""
        with tempfile.TemporaryDirectory() as scratch:
            base = pathlib.Path(scratch) / "line\nbreak"
            base.mkdir()
            repository, _, _ = _repository_with_a_local_filter(base)
            objects = trusted_execution.repository_objects(repository)
            self.assertIn("\n", str(objects))
            with (
                self.assertRaises(trusted_execution.TrustedExecutionError),
                trusted_execution.disposable_git_metadata(objects),
            ):
                pass


class ExtractTreeTests(unittest.TestCase):
    def test_the_repository_s_own_filters_never_run(self) -> None:
        """`git archive` applies the repository's attributes and the filter drivers its
        configuration names; materializing a tree must not (as on #364, round 13)."""
        with tempfile.TemporaryDirectory() as scratch:
            base = pathlib.Path(scratch)
            repository, tree, marker = _repository_with_a_local_filter(base)
            destination = base / "out"
            trusted_execution.extract_tree(repository, tree, destination)
            self.assertFalse(marker.exists(), "the repository's filter ran")
            self.assertEqual(
                "kept\n", (destination / "kept.txt").read_text(encoding="utf-8")
            )
            # The exact tree: its own `export-ignore` no longer drops a file, which
            # made a valid subject's tree differ (CodeAnt on #369).
            self.assertTrue((destination / "ignored.txt").exists())

    def test_an_object_store_whose_path_is_not_utf8_is_bound(self) -> None:
        """A store under a directory named by the byte 0xff was written to the
        alternates file as UTF-8, so `UnicodeEncodeError` escaped the owner (Codex on
        #369). Git reads that file as bytes, and the name is the file system's."""
        with tempfile.TemporaryDirectory() as scratch:
            base = pathlib.Path(scratch) / os.fsdecode(b"store-\xff")
            repository = base / "subject"
            repository.mkdir(parents=True)
            _git(repository, "init", "--quiet")
            (repository / "kept.txt").write_text("kept\n", encoding="utf-8")
            _git(repository, "add", "kept.txt")
            tree = _git(repository, "write-tree")
            destination = pathlib.Path(scratch) / "out"
            trusted_execution.extract_tree(repository, tree, destination)
            self.assertEqual(
                "kept\n", (destination / "kept.txt").read_text(encoding="utf-8")
            )

    def test_a_parent_someone_else_may_change_is_no_staging_place(self) -> None:
        """The staging directory sits in the destination's parent. Whoever else may
        write there could swap it for a link while the tree is extracted (CodeAnt on
        #369). A sticky parent lets no one but its owner rename an entry."""
        with tempfile.TemporaryDirectory() as scratch:
            base = pathlib.Path(scratch)
            repository = base / "subject"
            repository.mkdir()
            _git(repository, "init", "--quiet")
            (repository / "kept.txt").write_text("kept\n", encoding="utf-8")
            _git(repository, "add", "kept.txt")
            tree = _git(repository, "write-tree")
            for mode, refused in ((0o777, True), (0o1777, False), (0o755, False)):
                parent = base / f"parent-{mode:o}"
                parent.mkdir()
                parent.chmod(mode)
                with self.subTest(mode=f"{mode:o}"):
                    if refused:
                        with self.assertRaises(trusted_execution.TrustedExecutionError):
                            trusted_execution.extract_tree(
                                repository, tree, parent / "out"
                            )
                        self.assertEqual([], list(parent.iterdir()))
                    else:
                        trusted_execution.extract_tree(repository, tree, parent / "out")
                        self.assertTrue((parent / "out" / "kept.txt").exists())

    def test_the_tree_s_own_attributes_change_no_byte(self) -> None:
        """`eol=crlf` rewrote line endings, `ident` expanded `$Id$` and
        `working-tree-encoding` re-encoded a file, so the materialized tree was not
        the tree (CodeAnt on #369). `export-subst` applies only to a commit's archive,
        never a tree's, which this also pins."""
        files = {
            "crlf": b"one\ntwo\n",
            "ident": b"$Id$\n",
            "encoded": b"abc\n",
            "subst": b"$Format:%H$\n",
        }
        with tempfile.TemporaryDirectory() as scratch:
            base = pathlib.Path(scratch)
            repository = base / "subject"
            repository.mkdir()
            _git(repository, "init", "--quiet")
            for name, data in files.items():
                (repository / name).write_bytes(data)
            # Stored before the attributes exist, so each blob holds these bytes.
            _git(repository, "add", ".")
            (repository / ".gitattributes").write_text(
                "crlf text eol=crlf\nident ident\n"
                "encoded working-tree-encoding=UTF-16LE\nsubst export-subst\n",
                encoding="utf-8",
            )
            _git(repository, "add", ".gitattributes")
            tree = _git(repository, "write-tree").strip()
            destination = base / "out"
            trusted_execution.extract_tree(repository, tree, destination)
            for name, data in files.items():
                with self.subTest(name=name):
                    self.assertEqual(data, (destination / name).read_bytes())

    def test_only_an_object_name_is_extracted(self) -> None:
        with tempfile.TemporaryDirectory() as scratch:
            base = pathlib.Path(scratch)
            repository, _, _ = _repository_with_a_local_filter(base)
            with self.assertRaises(ValueError):
                trusted_execution.extract_tree(repository, "HEAD", base / "out")


def _repository_with_an_escaping_link(base: pathlib.Path) -> tuple[pathlib.Path, str]:
    """A tree whose first member is ordinary and whose last escapes the destination."""
    repository = base / "escaping"
    repository.mkdir()
    _git(repository, "init", "--quiet")
    (repository / "a.txt").write_text("a\n", encoding="utf-8")
    (repository / "zz").symlink_to("../../outside")
    _git(repository, "add", ".")
    _git(repository, "commit", "--quiet", "-m", "escaping")
    return repository, _git(repository, "rev-parse", "HEAD^{tree}")


class RepositoryReadTests(unittest.TestCase):
    """A read of a repository that may be untrusted is plumbing, or it is refused."""

    def test_plumbing_runs_and_nothing_else_does(self) -> None:
        with tempfile.TemporaryDirectory() as scratch:
            base = pathlib.Path(scratch)
            repository, tree, marker = _repository_with_a_local_filter(base)
            self.assertEqual(
                tree,
                trusted_execution.repository_read(
                    repository, "rev-parse", "HEAD^{tree}"
                ),
            )
            for refused in (
                ("status",),
                ("diff", "HEAD"),
                ("show", "HEAD"),
                ("archive", tree),
                (),
            ):
                with self.subTest(arguments=refused), self.assertRaises(ValueError):
                    trusted_execution.repository_read(repository, *refused)
            with self.assertRaises(ValueError):
                trusted_execution.repository_read(repository, "describe", "--dirty")
            self.assertFalse(marker.exists())

    def test_only_the_option_shapes_callers_use_are_read(self) -> None:
        """A plumbing command takes options that run the repository's own programs:
        `cat-file --filters` its smudge filter, `--textconv` its diff driver. Git also
        accepts an abbreviated option, so `--filt` and `--dirt` are those options too
        (CodeAnt and Codex on #369). Only the shapes callers use are allowed."""
        with tempfile.TemporaryDirectory() as scratch:
            base = pathlib.Path(scratch)
            repository, tree, marker = _repository_with_a_local_filter(base)
            blob = _git(repository, "rev-parse", "HEAD:kept.txt")
            for refused in (
                ("cat-file", "--filters", "--path=kept.txt", blob),
                ("cat-file", "--filt", "--path=kept.txt", blob),
                ("cat-file", "--textconv", "HEAD:kept.txt"),
                ("describe", "--dirt"),
                ("ls-tree", "-r", "--format=%(objectname)", tree),
                ("for-each-ref",),
                ("show-ref",),
            ):
                with self.subTest(arguments=refused), self.assertRaises(ValueError):
                    trusted_execution.repository_read(repository, *refused)
            self.assertFalse(marker.exists(), "the repository's filter ran")

    def test_a_signature_check_never_runs_the_repository_s_gpg_program(self) -> None:
        """`rev-list --format=%G?` verifies a commit's signature with the repository's
        own `gpg.program`."""
        with tempfile.TemporaryDirectory() as scratch:
            base = pathlib.Path(scratch)
            repository, tree, _ = _repository_with_a_local_filter(base)
            marker = base / "gpg-ran"
            gpg = base / "gpg"
            gpg.write_text(
                f"#!/bin/sh\nprintf x > {shlex.quote(str(marker))}\nexit 1\n",
                encoding="utf-8",
            )
            gpg.chmod(0o755)
            _git(repository, "config", "gpg.program", str(gpg))
            signed = _signed_commit(repository, tree)
            refused = False
            try:
                trusted_execution.repository_read(
                    repository, "rev-list", "--format=%G?", "-1", signed
                )
            except ValueError:
                refused = True
            self.assertFalse(marker.exists(), "the repository's gpg program ran")
            self.assertTrue(refused)

    def test_a_relative_repository_path_is_read_from_where_it_is(self) -> None:
        """The owner entered the repository and then named it again with `-C`, so a
        relative path was resolved twice (CodeAnt on #369)."""
        with tempfile.TemporaryDirectory() as scratch:
            base = pathlib.Path(scratch)
            repository, tree, _ = _repository_with_a_local_filter(base)
            previous = os.getcwd()
            os.chdir(base)
            try:
                read = trusted_execution.repository_read(
                    pathlib.Path(repository.name), "rev-parse", "HEAD^{tree}"
                )
            finally:
                os.chdir(previous)
            self.assertEqual(tree, read)

    def test_a_failed_read_is_the_owner_s_error(self) -> None:
        """Each caller maps the owner's error to its own, so Git's must not escape past
        it (CodeAnt on #369)."""
        with tempfile.TemporaryDirectory() as scratch:
            repository, _, _ = _repository_with_a_local_filter(pathlib.Path(scratch))
            with self.assertRaises(trusted_execution.TrustedExecutionError):
                trusted_execution.repository_read(
                    repository, "rev-parse", "missing^{tree}"
                )

    def test_a_read_trusts_only_the_repository_it_names(self) -> None:
        """Git refuses a repository another user owns, as provider CI's container user
        finds the runner's checkout (CodeRabbit on #369). These reads run no program
        the repository configures, so the owner names that one repository, and only
        it, as safe."""
        with tempfile.TemporaryDirectory() as scratch:
            repository, _, _ = _repository_with_a_local_filter(pathlib.Path(scratch))
            seen: list[dict[str, str]] = []
            real = subprocess.run

            def recording(*args, **kwargs):  # type: ignore[no-untyped-def]
                seen.append(dict(kwargs["env"]))
                # The owner always says whether a failure raises; pass it on as said.
                return real(*args, check=kwargs.pop("check"), **kwargs)

            with mock.patch.object(subprocess, "run", recording):
                trusted_execution.repository_read(repository, "rev-parse", "HEAD")
            self.assertTrue(seen)
            for environment in seen:
                configured = [
                    (
                        environment[f"GIT_CONFIG_KEY_{index}"],
                        environment[f"GIT_CONFIG_VALUE_{index}"],
                    )
                    for index in range(int(environment["GIT_CONFIG_COUNT"]))
                ]
                self.assertIn(
                    ("safe.directory", os.path.abspath(repository)), configured
                )
                self.assertNotIn(("safe.directory", "*"), configured)
                # And it fetches nothing, by any transport (Codex on #369).
                self.assertIn(("protocol.allow", "never"), configured)


class RepositoryReadOutputTests(unittest.TestCase):
    def test_a_listing_keeps_the_whitespace_its_names_carry(self) -> None:
        """Only the final newline is Git's; a leading or trailing space belongs to a
        path (CodeAnt on #369)."""
        with tempfile.TemporaryDirectory() as scratch:
            repository = pathlib.Path(scratch) / "subject"
            repository.mkdir()
            _git(repository, "init", "--quiet")
            for name in (" lead.txt", "trail.txt "):
                (repository / name).write_text("x\n", encoding="utf-8")
            _git(repository, "add", "--", " lead.txt", "trail.txt ")
            _git(repository, "commit", "--quiet", "-m", "spaces")
            tree = _git(repository, "rev-parse", "HEAD^{tree}")
            listed = trusted_execution.repository_read(
                repository, "ls-tree", "-r", "--name-only", tree
            )
            self.assertEqual([" lead.txt", "trail.txt "], listed.splitlines())


class RepositoryReadFetchTests(unittest.TestCase):
    def test_a_partial_clone_s_missing_object_is_not_fetched(self) -> None:
        """A missing object in a partial clone is fetched lazily, through the
        repository's own `remote.origin.uploadpack` program (Codex on #369)."""
        with tempfile.TemporaryDirectory() as scratch:
            base = pathlib.Path(scratch)
            server = base / "server"
            server.mkdir()
            _git(server, "init", "--quiet")
            (server / "dir").mkdir()
            (server / "dir" / "f.txt").write_text("f\n", encoding="utf-8")
            _git(server, "add", ".")
            _git(server, "commit", "--quiet", "-m", "s")
            _git(server, "config", "uploadpack.allowFilter", "true")
            client = base / "client"
            _git(
                base,
                "clone",
                "--quiet",
                "--no-checkout",
                "--filter=tree:0",
                f"file://{server}",
                str(client),
            )
            marker = base / "upload-pack-ran"
            program = base / "upload-pack"
            program.write_text(
                f"#!/bin/sh\nprintf x > {shlex.quote(str(marker))}\nexit 1\n",
                encoding="utf-8",
            )
            program.chmod(0o755)
            _git(client, "config", "remote.origin.uploadpack", str(program))
            tree = _git(server, "rev-parse", "HEAD^{tree}")
            try:
                trusted_execution.repository_read(client, "ls-tree", "-r", tree)
            except trusted_execution.TrustedExecutionError:
                pass
            self.assertFalse(
                marker.exists(), "the repository's upload-pack program ran"
            )


class RepositoryReadTimeoutTests(unittest.TestCase):
    def test_a_read_is_bounded_in_time(self) -> None:
        """A pathological repository must not block a caller for ever (CodeAnt on
        #369)."""
        with tempfile.TemporaryDirectory() as scratch:
            repository, _, _ = _repository_with_a_local_filter(pathlib.Path(scratch))
            seen: list[object] = []
            real = subprocess.run

            def recording(*args, **kwargs):  # type: ignore[no-untyped-def]
                seen.append(kwargs.get("timeout"))
                return real(*args, check=kwargs.pop("check"), **kwargs)

            with mock.patch.object(subprocess, "run", recording):
                trusted_execution.repository_read(repository, "rev-parse", "HEAD")
            self.assertTrue(seen)
            for timeout in seen:
                self.assertIsInstance(timeout, (int, float))


class RepositoryFilesTests(unittest.TestCase):
    """The files a repository tracks, as the file system names them."""

    def test_tracked_files_are_listed_and_untracked_ones_are_not(self) -> None:
        with tempfile.TemporaryDirectory() as scratch:
            repository, _, _ = _repository_with_a_local_filter(pathlib.Path(scratch))
            (repository / "untracked.txt").write_text("u\n", encoding="utf-8")
            name = os.fsdecode(b"caf\xe9.txt")
            (repository / name).write_text("x\n", encoding="utf-8")
            _git(repository, "add", "--", name)
            listed = trusted_execution.repository_files(repository)
            self.assertEqual(
                sorted([".gitattributes", "ignored.txt", "kept.txt", name]),
                sorted(listed or []),
            )
            self.assertTrue((repository / name).exists())

    def test_a_directory_in_no_repository_is_none(self) -> None:
        with tempfile.TemporaryDirectory() as scratch:
            self.assertIsNone(trusted_execution.repository_files(pathlib.Path(scratch)))

    def test_a_repository_git_cannot_list_is_an_error_not_none(self) -> None:
        with tempfile.TemporaryDirectory() as scratch:
            repository, _, _ = _repository_with_a_local_filter(pathlib.Path(scratch))
            (repository / ".git" / "index").write_bytes(b"not an index")
            with self.assertRaises(trusted_execution.TrustedExecutionError):
                trusted_execution.repository_files(repository)


class ExtractTreeFailureTests(unittest.TestCase):
    def test_a_refused_member_leaves_nothing_behind(self) -> None:
        """A tree extracted in part would pass for a whole one: a caller that finds the
        directory non-empty skips extraction (CodeAnt on #369)."""
        with tempfile.TemporaryDirectory() as scratch:
            base = pathlib.Path(scratch)
            repository, tree = _repository_with_an_escaping_link(base)
            destination = base / "out"
            with self.assertRaises(trusted_execution.TrustedExecutionError):
                trusted_execution.extract_tree(repository, tree, destination)
            self.assertFalse(destination.exists() and any(destination.iterdir()))
            # Nor is the staging directory left beside it.
            self.assertEqual([], [p.name for p in base.glob(".out.*")])

    def test_a_destination_already_holding_files_is_refused(self) -> None:
        """A caller materializes only into a missing or empty directory; anything
        else would merge two trees into one that looks whole."""
        with tempfile.TemporaryDirectory() as scratch:
            base = pathlib.Path(scratch)
            repository, tree, _ = _repository_with_a_local_filter(base)
            destination = base / "out"
            destination.mkdir()
            (destination / "stale.txt").write_text("stale\n", encoding="utf-8")
            with self.assertRaises(trusted_execution.TrustedExecutionError) as raised:
                trusted_execution.extract_tree(repository, tree, destination)
            # Refused before any extraction, with the reason the caller's blocker
            # records, not as a race lost at the move.
            self.assertEqual(f"{destination} is not empty", str(raised.exception))
            self.assertEqual(
                ["stale.txt"], sorted(p.name for p in destination.iterdir())
            )

    def test_a_ref_name_as_long_as_an_object_name_is_refused(self) -> None:
        """Forty characters that are not hex digits are a ref, which Git would resolve
        to whatever it names now."""
        with tempfile.TemporaryDirectory() as scratch:
            base = pathlib.Path(scratch)
            repository, _, _ = _repository_with_a_local_filter(base)
            ref = "z" * 40
            _git(repository, "branch", ref)
            with self.assertRaises(ValueError):
                trusted_execution.extract_tree(repository, ref, base / "out")
            self.assertFalse((base / "out").exists())

    def test_a_tree_that_is_not_a_string_is_a_value_error(self) -> None:
        """A lock's non-string tree raised `TypeError` past `capsule`'s blockers, which
        map `ValueError` (CodeAnt on #369)."""
        with tempfile.TemporaryDirectory() as scratch:
            base = pathlib.Path(scratch)
            repository, _, _ = _repository_with_a_local_filter(base)
            for tree in (None, 123, b"0" * 40):
                with self.subTest(tree=tree), self.assertRaises(ValueError):
                    trusted_execution.extract_tree(repository, tree, base / "out")  # type: ignore[arg-type]

    def test_a_dangling_destination_link_is_refused(self) -> None:
        """A dangling link looked missing, so the tree replaced it instead of being
        refused (CodeAnt on #369)."""
        with tempfile.TemporaryDirectory() as scratch:
            base = pathlib.Path(scratch)
            repository, tree, _ = _repository_with_a_local_filter(base)
            destination = base / "out"
            destination.symlink_to(base / "nowhere")
            with self.assertRaises(trusted_execution.TrustedExecutionError) as raised:
                trusted_execution.extract_tree(repository, tree, destination)
            self.assertTrue(destination.is_symlink())
            # Named as a link, not left to the final rename (CodeAnt on #369).
            self.assertIn("is a link", str(raised.exception))

    def test_a_commit_is_not_a_tree(self) -> None:
        """`git archive` extracts a commit's tree when given the commit, so a commit
        id the right length passed for the tree (CodeAnt on #369)."""
        with tempfile.TemporaryDirectory() as scratch:
            base = pathlib.Path(scratch)
            repository, _, _ = _repository_with_a_local_filter(base)
            commit = _git(repository, "rev-parse", "HEAD")
            with self.assertRaises(ValueError):
                trusted_execution.extract_tree(repository, commit, base / "out")
            self.assertFalse((base / "out").exists())

    def test_a_sha256_tree_is_named_in_full(self) -> None:
        """Forty hex digits are an abbreviation in a SHA-256 repository, and Git
        would archive whatever object they match (CodeAnt on #369)."""
        with tempfile.TemporaryDirectory() as scratch:
            base = pathlib.Path(scratch)
            repository = base / "sha256"
            repository.mkdir()
            _git(repository, "init", "--quiet", "--object-format=sha256")
            (repository / "f.txt").write_text("f\n", encoding="utf-8")
            _git(repository, "add", ".")
            _git(repository, "commit", "--quiet", "-m", "s")
            tree = _git(repository, "rev-parse", "HEAD^{tree}")
            with self.assertRaises(
                (ValueError, trusted_execution.TrustedExecutionError)
            ):
                trusted_execution.extract_tree(repository, tree[:40], base / "out")
            self.assertFalse((base / "out").exists())

    def test_a_sha256_repository_s_tree_is_extracted(self) -> None:
        """The disposable metadata takes the repository's object format (CodeAnt on
        #369)."""
        with tempfile.TemporaryDirectory() as scratch:
            base = pathlib.Path(scratch)
            repository = base / "sha256"
            repository.mkdir()
            _git(repository, "init", "--quiet", "--object-format=sha256")
            (repository / "f.txt").write_text("f\n", encoding="utf-8")
            _git(repository, "add", ".")
            _git(repository, "commit", "--quiet", "-m", "s")
            tree = _git(repository, "rev-parse", "HEAD^{tree}")
            self.assertEqual(64, len(tree))
            trusted_execution.extract_tree(repository, tree, base / "out")
            self.assertEqual(
                "f\n", (base / "out" / "f.txt").read_text(encoding="utf-8")
            )


class ExtractTreeGitFailureTests(unittest.TestCase):
    def test_a_tree_git_cannot_archive_is_the_owner_s_error(self) -> None:
        """`git archive` failing is reported as the owner's error, so the caller records
        a blocker (CodeAnt on #369)."""
        with tempfile.TemporaryDirectory() as scratch:
            base = pathlib.Path(scratch)
            repository, _, _ = _repository_with_a_local_filter(base)
            destination = base / "out"
            with self.assertRaises(trusted_execution.TrustedExecutionError):
                trusted_execution.extract_tree(repository, "0" * 40, destination)
            self.assertFalse(destination.exists())
            self.assertEqual([], [p.name for p in base.glob(".out.*")])

    def test_a_writer_racing_into_the_destination_is_the_owner_s_error(self) -> None:
        """Another writer can fill the destination between the emptiness check and the
        move; that is the owner's error too, and nothing of the tree is left
        (CodeRabbit on #369)."""
        with tempfile.TemporaryDirectory() as scratch:
            base = pathlib.Path(scratch)
            repository, tree, _ = _repository_with_a_local_filter(base)
            destination = base / "out"
            destination.mkdir()
            extract = tarfile.TarFile.extractall

            def racing(archive, *args, **kwargs):  # type: ignore[no-untyped-def]
                extract(archive, *args, **kwargs)
                (destination / "late.txt").write_text("late\n", encoding="utf-8")

            with (
                mock.patch.object(tarfile.TarFile, "extractall", racing),
                self.assertRaises(trusted_execution.TrustedExecutionError),
            ):
                trusted_execution.extract_tree(repository, tree, destination)
            self.assertEqual(
                ["late.txt"], sorted(p.name for p in destination.iterdir())
            )
            self.assertEqual([], [p.name for p in base.glob(".out.*")])


class ExtractTreeBoundsTests(unittest.TestCase):
    def test_the_archive_is_bounded_in_time(self) -> None:
        """A huge tree must not block a caller for ever (CodeAnt on #369)."""
        with tempfile.TemporaryDirectory() as scratch:
            base = pathlib.Path(scratch)
            repository, tree, _ = _repository_with_a_local_filter(base)
            seen: list[tuple[str, object]] = []
            real = subprocess.run

            def recording(*args, **kwargs):  # type: ignore[no-untyped-def]
                command = args[0][1] if len(args[0]) > 1 else ""
                seen.append((command, kwargs.get("timeout")))
                return real(*args, check=kwargs.pop("check"), **kwargs)

            with mock.patch.object(subprocess, "run", recording):
                trusted_execution.extract_tree(repository, tree, base / "out")
            archives = [timeout for command, timeout in seen if command == "archive"]
            self.assertTrue(archives)
            for timeout in archives:
                self.assertIsInstance(timeout, (int, float))

    def test_an_unreadable_destination_is_the_owner_s_error(self) -> None:
        """(CodeAnt on #369.)"""
        if os.geteuid() == 0:
            self.skipTest("root reads a directory whatever its mode")
        with tempfile.TemporaryDirectory() as scratch:
            base = pathlib.Path(scratch)
            repository, tree, _ = _repository_with_a_local_filter(base)
            destination = base / "out"
            destination.mkdir()
            destination.chmod(0)
            try:
                with self.assertRaises(trusted_execution.TrustedExecutionError):
                    trusted_execution.extract_tree(repository, tree, destination)
            finally:
                destination.chmod(0o755)


class ExtractTreeFileSystemTests(unittest.TestCase):
    def test_a_destination_that_is_a_file_is_the_owner_s_error(self) -> None:
        """(CodeAnt on #369.)"""
        with tempfile.TemporaryDirectory() as scratch:
            base = pathlib.Path(scratch)
            repository, tree, _ = _repository_with_a_local_filter(base)
            destination = base / "out"
            destination.write_text("a file\n", encoding="utf-8")
            with self.assertRaises(trusted_execution.TrustedExecutionError) as raised:
                trusted_execution.extract_tree(repository, tree, destination)
            self.assertEqual(f"{destination} is not a directory", str(raised.exception))
            self.assertEqual("a file\n", destination.read_text(encoding="utf-8"))

    def test_a_file_system_error_while_extracting_is_the_owner_s_error(self) -> None:
        """A full disk or a vanished scratch directory is a blocker, not a raw
        `OSError` (CodeAnt on #369)."""
        with tempfile.TemporaryDirectory() as scratch:
            base = pathlib.Path(scratch)
            repository, tree, _ = _repository_with_a_local_filter(base)
            with (
                mock.patch.object(
                    tarfile, "open", side_effect=OSError(28, "No space left")
                ),
                self.assertRaises(trusted_execution.TrustedExecutionError),
            ):
                trusted_execution.extract_tree(repository, tree, base / "out")
            self.assertEqual([], [p.name for p in base.glob(".out.*")])


class CallerTests(unittest.TestCase):
    """The callers that materialized trees themselves now go through the owner."""

    def test_capsule_materialization_runs_no_filter_of_the_subject_s(self) -> None:
        from tools.capsule import compiler, execute

        for name, materialize in (
            ("execute", execute._materialize),  # skipcq: PYL-W0212
            ("compiler", compiler._materialize),  # skipcq: PYL-W0212
        ):  # skipcq: PYL-W0212
            with tempfile.TemporaryDirectory() as scratch:
                base = pathlib.Path(scratch)
                repository, tree, marker = _repository_with_a_local_filter(base)
                with self.subTest(module=name):
                    materialize(repository, tree, base / "out")
                    self.assertFalse(
                        marker.exists(), f"capsule.{name} ran the subject's filter"
                    )
                    self.assertEqual(
                        "kept\n",
                        (base / "out" / "kept.txt").read_text(encoding="utf-8"),
                    )


class CallerFailureTests(unittest.TestCase):
    def test_capsule_reports_a_refused_member_as_its_own_error(self) -> None:
        """`execute_lock` turns an `ExecuteError` into a blocker; a raw tar error would
        abort it instead (CodeAnt on #369)."""
        from tools.capsule import compiler, execute

        for name, materialize, error in (
            (
                "execute",
                execute._materialize,  # skipcq: PYL-W0212
                execute.ExecuteError,
            ),
            (
                "compiler",
                compiler._materialize,  # skipcq: PYL-W0212
                compiler.CompileError,
            ),
        ):
            with tempfile.TemporaryDirectory() as scratch, self.subTest(module=name):
                base = pathlib.Path(scratch)
                repository, tree = _repository_with_an_escaping_link(base)
                with self.assertRaises(error):
                    materialize(repository, tree, base / "out")

    def test_capsule_tree_verification_runs_no_filter_of_the_subject_s(self) -> None:
        """`git add` in the subject repository would run its local clean filter
        (CodeAnt on #369): the tree is reconstructed under disposable metadata."""
        from tools.capsule import compiler

        with tempfile.TemporaryDirectory() as scratch:
            base = pathlib.Path(scratch)
            repository, tree, marker = _repository_with_a_local_filter(base)
            _git(repository, "config", "filter.evil.clean", str(base / "hit"))
            worktree = base / "materialized"
            worktree.mkdir()
            (worktree / "kept.txt").write_text("kept\n", encoding="utf-8")
            (worktree / ".gitattributes").write_text(
                "ignored.txt export-ignore\n", encoding="utf-8"
            )
            (worktree / "ignored.txt").write_text("ignored\n", encoding="utf-8")
            observed = compiler._observed_tree(  # skipcq: PYL-W0212
                repository, worktree
            )  # skipcq: PYL-W0212
            self.assertFalse(marker.exists(), "the subject's clean filter ran")
            self.assertEqual(tree, observed)


class TransportTests(unittest.TestCase):
    def test_a_repository_cannot_allow_a_refused_transport(self) -> None:
        """`protocol.allow=never` is only the default: a repository's own
        `protocol.file.allow=always` re-allowed `file`, and a fetch the caller had
        refused went through (Codex on #369)."""
        with tempfile.TemporaryDirectory() as scratch:
            base = pathlib.Path(scratch)
            source, destination = base / "source", base / "destination"
            for repository in (source, destination):
                repository.mkdir()
                _git(repository, "init", "--quiet")
            (source / "a").write_text("a\n", encoding="utf-8")
            _git(source, "add", "a")
            _git(
                source,
                "-c",
                "user.name=t",
                "-c",
                "user.email=t@e",
                "commit",
                "-qm",
                "a",
            )
            _git(destination, "config", "protocol.file.allow", "always")
            fetch = ["fetch", "--quiet", str(source), "HEAD"]
            refusing = trusted_execution.git_environment(transports=())
            with self.assertRaises(trusted_execution.GitFailure):
                trusted_execution.run_git(fetch, cwd=destination, environment=refusing)
            trusted_execution.run_git(
                fetch,
                cwd=destination,
                environment=trusted_execution.git_environment(transports=("file",)),
            )


class BrokenRepositoryTests(unittest.TestCase):
    def test_a_broken_git_pointer_is_no_absent_repository(self) -> None:
        """Git calls a broken `.git` file "not a git repository" too, and the check
        then walked the tree as if there were none (CodeAnt on #369)."""
        with tempfile.TemporaryDirectory() as scratch:
            base = pathlib.Path(scratch)
            (base / ".git").write_text(
                "gitdir: /nonexistent/gitdir\n", encoding="utf-8"
            )
            with self.assertRaises(trusted_execution.TrustedExecutionError):
                trusted_execution.repository_files(base)

    def test_a_broken_ancestor_git_pointer_is_no_absent_repository(self) -> None:
        """Git looks up through the parents, so a broken `.git` above the directory
        names a repository too (CodeAnt on #369)."""
        with tempfile.TemporaryDirectory() as scratch:
            base = pathlib.Path(scratch)
            (base / ".git").write_text(
                "gitdir: /nonexistent/gitdir\n", encoding="utf-8"
            )
            (base / "sub").mkdir()
            with self.assertRaises(trusted_execution.TrustedExecutionError):
                trusted_execution.repository_files(base / "sub")

    def test_an_object_store_that_does_not_resolve_is_refused(self) -> None:
        """Bound loosely, a missing store, or on Python 3.14 a loop, which resolves
        without error there, gave metadata that named nothing (Codex on #369)."""
        with (
            tempfile.TemporaryDirectory() as scratch,
            self.assertRaises(trusted_execution.TrustedExecutionError),
            trusted_execution.disposable_git_metadata(pathlib.Path(scratch) / "none"),
        ):
            pass

    def test_an_object_store_behind_a_link_loop_is_the_owner_s_error(self) -> None:
        """`resolve` raises `RuntimeError` on a loop in Python 3.11 and 3.12, which
        callers do not map (CodeAnt on #369)."""
        with tempfile.TemporaryDirectory() as scratch:
            base = pathlib.Path(scratch)
            (base / "a").symlink_to(base / "b")
            (base / "b").symlink_to(base / "a")
            with (
                self.assertRaises(trusted_execution.TrustedExecutionError),
                trusted_execution.disposable_git_metadata(base / "a"),
            ):
                pass

    def test_a_directory_with_no_git_entry_is_no_repository(self) -> None:
        with tempfile.TemporaryDirectory() as scratch:
            self.assertIsNone(trusted_execution.repository_files(pathlib.Path(scratch)))


class RunGitTests(unittest.TestCase):
    def test_a_caller_that_names_no_timeout_still_gets_one(self) -> None:
        """`run_git` waited forever by default, so the capsule compiler's `git add`
        could stall preparation (CodeAnt on #369)."""
        with (
            tempfile.TemporaryDirectory() as scratch,
            mock.patch.object(subprocess, "run") as run,
        ):
            environment = trusted_execution.git_environment()
            trusted_execution.run_git(
                ["status"], cwd=pathlib.Path(scratch), environment=environment
            )
        timeout = run.call_args.kwargs["timeout"]
        self.assertIsNotNone(timeout)
        self.assertGreater(timeout, 0)

    def test_a_git_that_outlives_its_timeout_is_the_owner_s_error(self) -> None:
        """A timeout is the owner's error, and no Git failure: Git said nothing."""
        with (
            tempfile.TemporaryDirectory() as scratch,
            mock.patch.object(
                subprocess,
                "run",
                side_effect=subprocess.TimeoutExpired("git", 1),
            ),
        ):
            environment = trusted_execution.git_environment()
            with self.assertRaises(trusted_execution.TrustedExecutionError) as raised:
                trusted_execution.run_git(
                    ["status"],
                    cwd=pathlib.Path(scratch),
                    environment=environment,
                    timeout=1,
                )
            self.assertNotIsInstance(raised.exception, trusted_execution.GitFailure)


def _record_then_time_out(
    seen: list[dict[str, str]], *_arguments: object, **options: object
) -> None:
    """Record a Git call's environment, then fail the call as a timeout would."""
    seen.append(dict(options["env"]))  # type: ignore[call-overload]
    raise subprocess.TimeoutExpired("git", 1)


def _record_each_command(
    seen: dict[str, str | None], argv: list[str], **options: object
) -> subprocess.CompletedProcess[bytes]:
    """Record the transports each Git command allows; `init` succeeds, and the fetch
    then fails as a timeout would."""
    command = next((a for a in argv[1:] if a in {"init", "fetch"}), "")
    environment = options["env"]
    if not isinstance(environment, dict):
        raise TypeError("a Git call names its whole environment")
    seen[command] = environment.get("GIT_ALLOW_PROTOCOL")
    if command == "fetch":
        raise subprocess.TimeoutExpired("git", 1)
    # A result, not a run: `init` succeeds as the real call would.
    return subprocess.CompletedProcess(  # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-audit.dangerous-subprocess-use-audit
        argv, 0, b"", b""
    )


class ProtectedRouteCharacterizationTests(unittest.TestCase):
    def test_git_s_own_reason_reaches_the_unavailable_route(self) -> None:
        """The route reports what Git said, not only its own description."""
        from tools import review_protected

        with tempfile.TemporaryDirectory() as scratch:
            source = pathlib.Path(scratch) / "source"
            source.mkdir()
            _git(source, "init", "--quiet", "--initial-branch=other")
            _git(source, "commit", "--quiet", "--allow-empty", "-m", "not main")
            with self.assertRaises(
                review_protected.ProtectedAcquisitionUnavailable
            ) as raised:
                review_protected._acquire_from_repository(  # skipcq: PYL-W0212
                    str(source), "tasks/protected.json"
                )
            self.assertIn("remote ref", str(raised.exception))

    def test_a_git_that_outlives_its_timeout_makes_the_route_unavailable(self) -> None:
        """The same before and after `review_protected` moved onto the owner's
        runner (Codex on #369): it caught the timeout itself, and now the owner
        does."""
        from tools import review_protected

        with (
            mock.patch.object(
                subprocess,
                "run",
                side_effect=subprocess.TimeoutExpired("git", 1),
            ),
            self.assertRaises(review_protected.ProtectedAcquisitionUnavailable),
        ):
            review_protected._acquire_from_repository(  # skipcq: PYL-W0212
                "https://example.invalid/protected.git", "tasks/protected.json"
            )

    def test_the_protected_fetch_takes_no_routing_or_trust_root_of_the_caller_s(
        self,
    ) -> None:
        """Before it moved onto the owner the route inherited none of them; on the
        owner it passed the caller's proxy and certificates (Codex on #369)."""
        from tools import review_protected

        seen: list[dict[str, str]] = []
        record = functools.partial(_record_then_time_out, seen)
        with (
            mock.patch.dict(os.environ, _CALLER_ROUTING),
            mock.patch.object(subprocess, "run", side_effect=record),
            self.assertRaises(review_protected.ProtectedAcquisitionUnavailable),
        ):
            review_protected._acquire_from_repository(  # skipcq: PYL-W0212
                "https://example.invalid/protected.git", "tasks/protected.json"
            )
        self.assertTrue(seen)
        for environment in seen:
            self.assertFalse(set(_CALLER_ROUTING) & set(environment), environment)

    def test_the_protected_fetch_allows_only_its_own_transport(self) -> None:
        """With no transport allowlist, Git could follow the protected fetch's redirect
        over another protocol (CodeAnt on #369). The fixed HTTPS route allows HTTPS
        alone; a local repository, as the tests use, allows the file transport alone."""
        from tools import review_protected

        for repository, transport in (
            ("https://github.com/ktogias/gnostoa.git", "https"),
            ("/srv/protected", "file"),
        ):
            seen: dict[str, str | None] = {}
            record = functools.partial(_record_each_command, seen)
            with (
                self.subTest(repository=repository),
                mock.patch.object(subprocess, "run", side_effect=record),
                self.assertRaises(review_protected.ProtectedAcquisitionUnavailable),
            ):
                review_protected._acquire_from_repository(  # skipcq: PYL-W0212
                    repository, "tasks/protected.json"
                )
            # The fetch allows its own transport alone; a local call allows none.
            self.assertEqual(transport, seen.get("fetch"))
            self.assertEqual("", seen.get("init"))


class CallerGitFailureTests(unittest.TestCase):
    def test_capsule_reports_a_failed_git_call_as_its_own_error(self) -> None:
        """A raw `CalledProcessError` escaped `capsule`'s own error before and after
        the migration (CodeAnt on #369)."""
        from tools.capsule import compiler, execute, preparation

        with tempfile.TemporaryDirectory() as scratch:
            base = pathlib.Path(scratch)
            repository, _, _ = _repository_with_a_local_filter(base)
            commit = _git(repository, "rev-parse", "HEAD")
            missing = "0" * 40
            for name, call, error in (
                (
                    "compiler._git",
                    lambda: compiler._git(  # skipcq: PYL-W0212
                        repository, "rev-parse", "missing^{tree}"
                    ),
                    compiler.CompileError,
                ),
                (
                    "compiler._git refusing a spec's argument",
                    lambda: compiler._git(  # skipcq: PYL-W0212
                        repository, "rev-parse", "--not-a-read"
                    ),
                    compiler.CompileError,
                ),
                (
                    "compiler._frozen_tree_paths",
                    lambda: compiler._frozen_tree_paths(  # skipcq: PYL-W0212
                        repository, missing
                    ),
                    compiler.CompileError,
                ),
                (
                    "compiler._materialize",
                    lambda: compiler._materialize(  # skipcq: PYL-W0212
                        repository, missing, base / "c"
                    ),
                    compiler.CompileError,
                ),
                (
                    "execute._materialize",
                    lambda: execute._materialize(  # skipcq: PYL-W0212
                        repository, missing, base / "e"
                    ),
                    execute.ExecuteError,
                ),
                (
                    "preparation.derive_scm_version refusing an input",
                    lambda: preparation.derive_scm_version(repository, "--dirty"),
                    preparation.PreparationError,
                ),
                (
                    "preparation.derive_scm_version",
                    lambda: preparation.derive_scm_version(repository, commit),
                    preparation.PreparationError,
                ),
            ):
                with self.subTest(call=name), self.assertRaises(error):
                    call()

    def test_capsule_reports_a_malformed_tree_name_as_its_own_error(self) -> None:
        """A spec's or lock's tree name is data: a malformed one is a blocker, not an
        uncaught `ValueError` (CodeAnt on #369)."""
        from tools.capsule import compiler, execute

        with tempfile.TemporaryDirectory() as scratch:
            base = pathlib.Path(scratch)
            repository, _, _ = _repository_with_a_local_filter(base)
            for name, materialize, error in (
                (
                    "compiler",
                    compiler._materialize,  # skipcq: PYL-W0212
                    compiler.CompileError,
                ),  # skipcq: PYL-W0212
                (
                    "execute",
                    execute._materialize,  # skipcq: PYL-W0212
                    execute.ExecuteError,
                ),  # skipcq: PYL-W0212
            ):
                with self.subTest(module=name), self.assertRaises(error):
                    materialize(repository, "HEAD", base / name)

    def test_capsule_tree_verification_reports_git_failing_as_its_own_error(
        self,
    ) -> None:
        """`_observed_tree` ran Git itself, so its failure escaped as a raw
        `CalledProcessError` (Codex on #369)."""
        from tools.capsule import compiler

        if os.geteuid() == 0:
            self.skipTest("root reads a file whatever its mode")
        with tempfile.TemporaryDirectory() as scratch:
            base = pathlib.Path(scratch)
            repository, _, _ = _repository_with_a_local_filter(base)
            worktree = base / "work"
            worktree.mkdir()
            sealed = worktree / "sealed.txt"
            sealed.write_text("unreadable\n", encoding="utf-8")
            sealed.chmod(0)
            try:
                with self.assertRaises(compiler.CompileError):
                    compiler._observed_tree(repository, worktree)  # skipcq: PYL-W0212
            finally:
                sealed.chmod(0o644)

    def test_capsule_reads_a_frozen_tree_s_paths_as_the_file_system_names_them(
        self,
    ) -> None:
        """Without `-z`, Git quotes a name with a newline or a non-ASCII byte, so the
        frozen path set held the quoted form (CodeAnt on #369)."""
        from tools.capsule import compiler

        with tempfile.TemporaryDirectory() as scratch:
            repository = pathlib.Path(scratch) / "subject"
            repository.mkdir()
            _git(repository, "init", "--quiet")
            names = ["plain.txt", "caf\u00e9.txt", "line\nbreak.txt"]
            for name in names:
                (repository / name).write_text("x\n", encoding="utf-8")
            _git(repository, "add", "--", *names)
            _git(repository, "commit", "--quiet", "-m", "names")
            tree = _git(repository, "rev-parse", "HEAD^{tree}")
            self.assertEqual(
                frozenset(names),
                compiler._frozen_tree_paths(repository, tree),  # skipcq: PYL-W0212
            )

    def test_capsule_reports_its_own_scratch_failing_as_its_own_error(self) -> None:
        """The compiler's own scratch directory for the index could fail with a raw
        `OSError` (CodeAnt on #369)."""
        from tools.capsule import compiler

        real = tempfile.TemporaryDirectory
        calls: list[int] = []

        def second_fails(*args, **kwargs):  # type: ignore[no-untyped-def]
            calls.append(1)
            if len(calls) == 2:
                raise OSError(28, "No space left")
            return real(*args, **kwargs)

        with tempfile.TemporaryDirectory() as scratch:
            base = pathlib.Path(scratch)
            repository, _, _ = _repository_with_a_local_filter(base)
            worktree = base / "work"
            worktree.mkdir()
            with (
                mock.patch.object(tempfile, "TemporaryDirectory", second_fails),
                self.assertRaises(compiler.CompileError),
            ):
                compiler._observed_tree(repository, worktree)  # skipcq: PYL-W0212

    def test_capsule_tree_verification_writes_nothing_into_the_subject(self) -> None:
        """A reconstructed tree's objects go into the disposable metadata, not into the
        subject repository's store (CodeAnt on #369)."""
        from tools.capsule import compiler

        with tempfile.TemporaryDirectory() as scratch:
            base = pathlib.Path(scratch)
            repository, _, _ = _repository_with_a_local_filter(base)
            worktree = base / "work"
            worktree.mkdir()
            fresh = worktree / "fresh.txt"
            fresh.write_text("written only here\n", encoding="utf-8")
            blob = _git(repository, "hash-object", "--no-filters", str(fresh))
            compiler._observed_tree(repository, worktree)  # skipcq: PYL-W0212
            self.assertFalse(
                _has_object(repository, blob),
                "the reconstructed tree's blob was written into the subject",
            )


if __name__ == "__main__":
    unittest.main()
