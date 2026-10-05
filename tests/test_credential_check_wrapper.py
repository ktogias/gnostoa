"""The credential check runs from an exact authority commit (Decision 0101, #364).

The check gates an agent's first provider write, so it must not take its declaration
or its judgement from the candidate it authorizes: a candidate could widen a maximum
or accept a grant and pass its own gate (Codex on #364; owner decision 2026-10-05).
`ci/credential-check`, retrieved from the protected-main commit, extracts that commit
and runs its checker against its declaration; the agent's checkout is read only for
how it pushes. These tests run the wrapper against a real repository whose working
tree disagrees with the commit, and whose PATH is poisoned.
"""

from __future__ import annotations

import json
import os
import pathlib
import shutil
import subprocess  # nosec B404
import tempfile
import textwrap
import unittest
from typing import ClassVar

ROOT = pathlib.Path(__file__).resolve().parents[1]
WRAPPER = ROOT / "ci" / "credential-check"
# Parses as the real checker does (argparse: the last occurrence of an option wins).
FAKE_CHECKER = """
import argparse, json, os, sys


def main(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy")
    parser.add_argument("--worktree")
    known, _ = parser.parse_known_args(argv)
    policy = known.policy
    print(json.dumps({
        "from": "authority",
        "cwd": os.getcwd(),
        "argv": argv,
        "policy": open(policy, encoding="utf-8").read() if policy else None,
        "kit": os.environ.get("KNOWLEDGE_KIT_ROOT"),
        "worktree": known.worktree,
    }))
    return 0
"""


def _git(root: pathlib.Path, *arguments: str) -> str:
    completed = subprocess.run(  # nosec B603 B607
        ["git", "-C", str(root), *arguments],
        check=True,
        capture_output=True,
        text=True,
        env={"PATH": "/usr/bin:/bin", "HOME": str(root), "GIT_CONFIG_NOSYSTEM": "1"},
    )
    return completed.stdout.strip()


class CredentialCheckWrapperTests(unittest.TestCase):
    """The wrapper's authority is the commit it names, never the working tree."""

    def setUp(self) -> None:
        self.scratch = tempfile.TemporaryDirectory()
        self.addCleanup(self.scratch.cleanup)
        self.root = pathlib.Path(self.scratch.name) / "repository"
        self.root.mkdir()
        _git(self.root, "init", "--quiet")
        _git(self.root, "config", "user.email", "authority@example.invalid")
        _git(self.root, "config", "user.name", "Authority")
        for directory in ("ci", "tools", "policy"):
            (self.root / directory).mkdir()
        shutil.copyfile(WRAPPER, self.root / "ci" / "credential-check")
        (self.root / "tools" / "__init__.py").write_text("", encoding="utf-8")
        (self.root / "tools" / "credential_check.py").write_text(
            FAKE_CHECKER, encoding="utf-8"
        )
        (self.root / "policy" / "agent-credentials.yaml").write_text(
            "authority-declaration\\n", encoding="utf-8"
        )
        _git(self.root, "add", ".")
        _git(self.root, "commit", "--quiet", "-m", "authority")
        self.authority = _git(self.root, "rev-parse", "HEAD")
        # The candidate disagrees with its authority, and its PATH is hostile.
        (self.root / "tools" / "credential_check.py").write_text(
            "raise SystemExit(97)\\n", encoding="utf-8"
        )
        (self.root / "policy" / "agent-credentials.yaml").write_text(
            "candidate-declaration\\n", encoding="utf-8"
        )
        self.poison = pathlib.Path(self.scratch.name) / "poison"
        self.poison.mkdir()
        self.marker = pathlib.Path(self.scratch.name) / "poisoned"
        for executable in ("git", "python", "python3", "mktemp", "tar"):
            fake = self.poison / executable
            fake.write_text(
                f"#!/bin/sh\\nprintf x > {self.marker}\\nexit 99\\n", encoding="utf-8"
            )
            fake.chmod(0o755)
        self.tmp = pathlib.Path(self.scratch.name) / "tmp"
        self.tmp.mkdir()

    def _run(
        self, *arguments: str, extra: dict[str, str] | None = None
    ) -> subprocess.CompletedProcess[str]:
        private = pathlib.Path(self.scratch.name) / "wrapper"
        shutil.copyfile(WRAPPER, private)
        private.chmod(0o700)
        environment = {
            "PATH": f"{self.poison}{os.pathsep}/usr/local/bin:/usr/bin:/bin",
            "HOME": str(self.root),
            "PYTHONPATH": str(self.root),
            "TMPDIR": str(self.tmp),
            "GIT_CONFIG_NOSYSTEM": "1",
            **(extra or {}),
        }
        return subprocess.run(  # nosec B603 B607
            ["sh", str(private), *arguments],
            cwd=self.root,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
            timeout=120,
        )

    def test_a_shell_function_never_stands_in_for_an_executable(self) -> None:
        """`command -v` names a shell function rather than a path, and a name runs the
        function: an exported `git` or `tar` function must not run in place of the
        trusted executable (CodeAnt on #364). Bash imports exported functions, and
        `sh` is bash on some hosts."""
        private = pathlib.Path(self.scratch.name) / "wrapper"
        shutil.copyfile(WRAPPER, private)
        private.chmod(0o700)
        for names in (("git",), ("tar",), ("python3", "python"), ("mktemp",)):
            name = names[0]
            with self.subTest(function=name):
                self.marker.unlink(missing_ok=True)
                environment = {
                    "PATH": "/usr/local/bin:/usr/bin:/bin",
                    "HOME": str(self.root),
                    "TMPDIR": str(self.tmp),
                    "GIT_CONFIG_NOSYSTEM": "1",
                }
                for shadowed in names:
                    environment[f"BASH_FUNC_{shadowed}%%"] = (
                        f"() {{ printf x > {self.marker}; return 99; }}"
                    )
                completed = subprocess.run(  # nosec B603 B607
                    ["bash", str(private), self.authority, "--repository", "o/r"],
                    cwd=self.root,
                    env=environment,
                    capture_output=True,
                    text=True,
                    check=False,
                    timeout=120,
                )
                self.assertFalse(self.marker.exists(), f"a {name} function ran")
                self.assertEqual(2, completed.returncode, completed.stderr)

    def _hit(self) -> pathlib.Path:
        """An executable that leaves the marker and passes its input through."""
        hit = pathlib.Path(self.scratch.name) / "hit"
        hit.write_text(f"#!/bin/sh\nprintf x > {self.marker}\ncat\n", encoding="utf-8")
        hit.chmod(0o755)
        return hit

    def test_tar_options_from_the_caller_never_reach_the_extraction(self) -> None:
        """GNU tar takes `TAR_OPTIONS` before its own arguments, and a checkpoint
        action can rewrite the extracted checker before Python imports it (Codex on
        #364): tar runs with an empty environment."""
        action = f"--checkpoint=1 --checkpoint-action=exec={self._hit()}"
        completed = self._run(
            self.authority, "--repository", "o/r", extra={"TAR_OPTIONS": action}
        )
        self.assertFalse(self.marker.exists(), "TAR_OPTIONS ran a command")
        self.assertEqual(0, completed.returncode, completed.stderr)
        self.assertEqual("authority", json.loads(completed.stdout)["from"])

    def test_no_inherited_git_environment_reaches_the_extraction(self) -> None:
        """Git and tar run with no inherited environment, not with a list of scrubbed
        variables: `GIT_EXEC_PATH` escaped such a list (Codex on #364). An inherited
        `GIT_TRACE` would make git write its trace."""
        trace = pathlib.Path(self.scratch.name) / "trace"
        completed = self._run(
            self.authority, "--repository", "o/r", extra={"GIT_TRACE": str(trace)}
        )
        self.assertEqual(0, completed.returncode, completed.stderr)
        self.assertFalse(trace.exists(), "an inherited GIT_TRACE reached git")

    def test_the_checkout_s_attributes_and_filters_never_touch_the_extraction(
        self,
    ) -> None:
        """`git archive` applies attributes and the filter drivers configuration names:
        the checkout's own `info/attributes` and configuration must not run a command
        or rewrite the authority's bytes, as they must not during the fetch."""
        git_dir = pathlib.Path(_git(self.root, "rev-parse", "--absolute-git-dir"))
        (git_dir / "info").mkdir(exist_ok=True)
        (git_dir / "info" / "attributes").write_text(
            "* filter=evil\n", encoding="utf-8"
        )
        _git(self.root, "config", "filter.evil.smudge", str(self._hit()))
        completed = self._run(self.authority, "--repository", "o/r")
        self.assertFalse(self.marker.exists(), "the checkout's filter ran")
        self.assertEqual(0, completed.returncode, completed.stderr)
        self.assertEqual("authority", json.loads(completed.stdout)["from"])

    def test_the_authority_s_checker_judges_by_the_authority_s_declaration(
        self,
    ) -> None:
        completed = self._run(self.authority, "--repository", "o/r")
        self.assertEqual(0, completed.returncode, completed.stderr)
        ran = json.loads(completed.stdout)
        self.assertEqual("authority", ran["from"])
        self.assertEqual("authority-declaration\\n", ran["policy"])
        # Run from the extracted commit, reading the checkout only for its pushes.
        self.assertNotEqual(
            str(self.root.resolve()), str(pathlib.Path(ran["cwd"]).resolve())
        )
        self.assertEqual(ran["cwd"], ran["kit"])
        worktree = ran["argv"][ran["argv"].index("--worktree") + 1]
        self.assertEqual(
            str(self.root.resolve()), str(pathlib.Path(worktree).resolve())
        )
        self.assertEqual("policy/agent-credentials.yaml", ran["argv"][-1])
        self.assertFalse(self.marker.exists(), "a poisoned executable ran")
        self.assertEqual(
            [], list(self.tmp.iterdir()), "the extracted tree was left behind"
        )

    def test_a_caller_cannot_point_the_declaration_elsewhere(self) -> None:
        completed = self._run(
            self.authority, "--repository", "o/r", "--policy", "/etc/passwd"
        )
        self.assertEqual(0, completed.returncode, completed.stderr)
        self.assertEqual(
            "authority-declaration\\n", json.loads(completed.stdout)["policy"]
        )

    def test_a_caller_cannot_point_the_push_binding_at_another_checkout(self) -> None:
        """The checkout the wrapper runs in is the one whose pushes are bound, whatever
        the caller passes (gitar on #364)."""
        completed = self._run(
            self.authority, "--repository", "o/r", "--worktree", "/elsewhere"
        )
        self.assertEqual(0, completed.returncode, completed.stderr)
        worktree = json.loads(completed.stdout)["worktree"]
        self.assertEqual(
            str(self.root.resolve()), str(pathlib.Path(worktree).resolve())
        )

    def test_an_authority_that_is_not_an_exact_commit_is_refused(self) -> None:
        for authority in ("", "main", "HEAD", "0" * 39, "g" * 40):
            with self.subTest(authority=authority):
                completed = self._run(authority, "--repository", "o/r")
                self.assertEqual(2, completed.returncode)
                self.assertIn("exact 40-character", completed.stderr)

    def test_an_authority_this_repository_does_not_hold_is_refused(self) -> None:
        completed = self._run("1" * 40, "--repository", "o/r")
        self.assertEqual(2, completed.returncode)
        self.assertIn("could not be extracted", completed.stderr)


def _resolution(text: str) -> str:
    """The trusted-executable resolution, from its first comment to the end of
    `trusted()`, dedented."""
    start = text.index("`command -v` names a shell function or alias")
    start = text.rindex("\n", 0, start) + 1
    head = text.index("trusted() {", start)
    indent = head - (text.rindex("\n", 0, head) + 1)
    end = text.index("\n" + " " * indent + "}\n", head) + indent + 3
    return textwrap.dedent(text[start:end])


class TrustedResolutionTests(unittest.TestCase):
    """The shells resolve executables as `knowledge_common.trusted_executable` does."""

    SOURCES: ClassVar[dict[str, pathlib.Path]] = {
        "wrapper": WRAPPER,
        "helper": ROOT / "AGENTS.md",
    }

    @staticmethod
    @staticmethod
    def _trusted(
        source: pathlib.Path, path: str, then: str = "", command: str = "trusted git"
    ) -> subprocess.CompletedProcess[str]:
        block = _resolution(source.read_text(encoding="utf-8"))
        return subprocess.run(  # nosec B603 B607  # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-audit.dangerous-subprocess-use-audit
            ["sh", "-c", f"{block}\n{then}{command}"],
            env={"PATH": path},
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )

    def test_the_helper_and_the_wrapper_resolve_executables_alike(self) -> None:
        """One resolution in two places, since the helper must run before the wrapper
        exists: the two texts may not drift apart (#365)."""
        blocks = {
            name: _resolution(path.read_text(encoding="utf-8"))
            for name, path in self.SOURCES.items()
        }
        self.assertEqual(blocks["wrapper"], blocks["helper"])

    def test_every_directory_above_is_judged_too(self) -> None:
        """Whoever can change a directory above can replace the one below it whole
        (CodeAnt on #364); a sticky directory lets no one but an entry's owner do so."""
        for name, source in self.SOURCES.items():
            with tempfile.TemporaryDirectory() as scratch:
                above = pathlib.Path(scratch) / "above"
                found = above / "bin"
                found.mkdir(parents=True)
                fake = found / "git"
                fake.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
                fake.chmod(0o755)
                path = f"{found}:/usr/bin:/bin"
                for case, mode, trusted in (
                    ("no one else can change it", 0o755, True),
                    ("a group-writable directory above", 0o775, False),
                    ("a sticky directory above", 0o1777, True),
                ):
                    above.chmod(mode)
                    with self.subTest(source=name, case=case):
                        completed = self._trusted(source, path)
                        if trusted:
                            self.assertEqual(str(fake), completed.stdout.strip())
                        else:
                            self.assertNotEqual(0, completed.returncode)
                            self.assertEqual("", completed.stdout)
                above.chmod(0o755)
                # Through a directory link, judged where it leads too.
                (pathlib.Path(scratch) / "safe").mkdir()
                link = pathlib.Path(scratch) / "safe" / "link"
                link.symlink_to(found)
                through = f"{link}:/usr/bin:/bin"
                above.chmod(0o775)
                with self.subTest(source=name, case="a directory link into it"):
                    completed = self._trusted(source, through)
                    self.assertNotEqual(0, completed.returncode)
                    self.assertEqual("", completed.stdout)
                above.chmod(0o755)

    def test_a_directory_link_is_judged_by_its_own_owner(self) -> None:
        """A link is followed only after it is judged: a safe directory link is
        trusted, another user's in a sticky directory is not (Codex on #364). Another
        user stands as a caller other than the link's owner."""
        temporary = tempfile.gettempdir()
        held = os.stat(temporary)
        if held.st_uid != 0 or not held.st_mode & 0o1000:
            self.skipTest("the temporary directory is not root's and sticky")
        shell = shutil.which("sh", path="/usr/bin:/bin")
        if shell is None:
            self.skipTest("no sh in the system directories")
        system = os.path.dirname(os.path.realpath(shell))
        link = pathlib.Path(temporary) / f"gnostoa-link-{os.getpid()}-{id(self)}"
        link.symlink_to(system)
        self.addCleanup(link.unlink)
        for name, source in self.SOURCES.items():
            with self.subTest(source=name, case="the caller's own link"):
                completed = self._trusted(
                    source, "/usr/bin:/bin", command=f'checked "{link}/sh"'
                )
                self.assertEqual(
                    f"{link}/sh", completed.stdout.strip(), completed.stderr
                )
            with self.subTest(source=name, case="another user's link"):
                completed = self._trusted(
                    source,
                    "/usr/bin:/bin",
                    then="caller=4242\n",
                    command=f'checked "{link}/sh"',
                )
                self.assertNotEqual(0, completed.returncode)
                self.assertEqual("", completed.stdout)

    def test_an_executable_others_can_replace_is_not_trusted(self) -> None:
        """Writable by no one but root or the caller, as the Python owner requires:
        `/opt/homebrew/bin` is commonly group-writable, and whoever can change the
        directory, the file or a symlink's target chooses what runs (CodeAnt on #364)."""
        for name, source in self.SOURCES.items():
            with tempfile.TemporaryDirectory() as scratch:
                found = pathlib.Path(scratch) / "bin"
                elsewhere = pathlib.Path(scratch) / "elsewhere"
                found.mkdir()
                elsewhere.mkdir()
                fake = found / "git"
                fake.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
                fake.chmod(0o755)
                path = f"{found}:/usr/bin:/bin"
                with self.subTest(source=name, case="writable only by the caller"):
                    completed = self._trusted(source, path)
                    self.assertEqual(0, completed.returncode, completed.stderr)
                    self.assertEqual(str(fake), completed.stdout.strip())
                for case, changed, mode in (
                    ("a group-writable directory", found, 0o775),
                    ("a world-writable file", fake, 0o757),
                ):
                    changed.chmod(mode)
                    with self.subTest(source=name, case=case):
                        completed = self._trusted(source, path)
                        self.assertNotEqual(0, completed.returncode)
                        self.assertEqual("", completed.stdout)
                    changed.chmod(0o755)
                # Another user's file: a caller other than the file's owner, named
                # directly, stands in for an owner no test can create.
                with self.subTest(source=name, case="a file another user owns"):
                    completed = self._trusted(source, path, then="caller=4242\n")
                    self.assertNotEqual(0, completed.returncode)
                    self.assertEqual("", completed.stdout)
                # A validator planted where the rule would refuse it must not vouch for
                # itself and then for everything else (gitar on #364).
                planted = found / "ls"
                planted.write_text(
                    "#!/bin/sh\necho '-rwxr-xr-x 1 0 0 0 Jan 1 00:00 x'\n",
                    encoding="utf-8",
                )
                planted.chmod(0o755)
                found.chmod(0o775)
                with self.subTest(source=name, case="a planted ls"):
                    completed = self._trusted(source, path)
                    self.assertNotEqual(0, completed.returncode)
                    self.assertEqual("", completed.stdout)
                found.chmod(0o755)
                planted.unlink()
                # A link in the middle of a chain is judged by its own directory too
                # (gitar on #364).
                shared = pathlib.Path(scratch) / "shared"
                shared.mkdir()
                real = elsewhere / "git"
                fake.rename(real)
                (shared / "git").symlink_to(real)
                fake.symlink_to(shared / "git")
                with self.subTest(source=name, case="a chain through a safe chain"):
                    completed = self._trusted(source, path)
                    self.assertEqual(0, completed.returncode, completed.stderr)
                shared.chmod(0o775)
                with self.subTest(
                    source=name, case="a chain through a shared directory"
                ):
                    completed = self._trusted(source, path)
                    self.assertNotEqual(0, completed.returncode)
                    self.assertEqual("", completed.stdout)
                shared.chmod(0o755)
                fake.unlink()
                fake.symlink_to(shared / "loop")
                (shared / "loop").symlink_to(fake)
                # A loop is never found by name, which needs an executable: judge the
                # path itself.
                with self.subTest(source=name, case="a link loop"):
                    completed = self._trusted(source, path, command=f'checked "{fake}"')
                    self.assertNotEqual(0, completed.returncode)
                    self.assertEqual("", completed.stdout)
                fake.unlink()
                (shared / "loop").unlink()
                real.rename(fake)
                target = elsewhere / "git"
                fake.rename(target)
                fake.symlink_to(target)
                elsewhere.chmod(0o775)
                with self.subTest(
                    source=name, case="a symlink into a group-writable directory"
                ):
                    completed = self._trusted(source, path)
                    self.assertNotEqual(0, completed.returncode)
                    self.assertEqual("", completed.stdout)


if __name__ == "__main__":
    unittest.main()
