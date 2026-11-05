"""B1 (#389; owner 6633186827 §3; PAO 6634192406; lineage 6634384923; route (A), 6644368315): the git these sites
start is resolved on the repository's one trusted lookup, AGENTS.md's PATH, never the caller's. tools/trusted_path.py
owns it. The orientation task follows with its child environment, tools/repository_scope.py with
tests/test_quality_evidence.py's SLF001 repair, and tools/candidate_prepare.py, a preparation authority, by its own
separately admitted change (AGENTS.md; route (B), the owner's 6652443128)."""

from __future__ import annotations

import ast
import importlib
import os
import shutil
import sys
import tempfile
import unittest
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any
from unittest.mock import patch

from tools import exact_tree, quality_evidence

ROOT = Path(__file__).resolve().parents[1]

# The repository's trusted executable lookup, as AGENTS.md states it.
TRUSTED = "/usr/local/bin:/usr/bin:/bin:/opt/homebrew/bin"

# The authorities that run as one file: ci/prepare-candidate extracts and runs
# candidate_prepare with `python -I`, and the orientation task is self-only.
SINGLE_FILE = ("tools/candidate_prepare.py", "tasks/gnostoa_orientation.py")


def _leaf() -> ModuleType:
    # Imported when used, so each site's test runs on its own where the leaf is absent.
    return importlib.import_module("tools.trusted_path")


def _original(module: object, name: str) -> Any:
    """`module`'s own `name`, as unittest.mock hands an original to new_callable under spec=True, so no private
    attribute is named (the fixtures' own pattern, #389 6480056885)."""
    found: list[object] = []

    def kept(*, spec: object) -> object:
        found.append(spec)
        return spec

    with patch.object(module, name, spec=True, new_callable=kept):
        pass
    return found[0]


@contextmanager
def _shadow(name: str = "git") -> Iterator[Path]:
    """A directory first on the caller's PATH holding an executable `name`, which no trusted start may run."""
    with tempfile.TemporaryDirectory() as directory:
        fake = Path(directory) / name
        fake.write_text("#!/bin/sh\nexit 97\n", encoding="utf-8")
        fake.chmod(0o755)
        path = f"{directory}{os.pathsep}{os.environ.get('PATH', '')}"
        with patch.dict(os.environ, {"PATH": path}):
            yield fake


class TrustedPathTests(unittest.TestCase):
    def test_it_resolves_on_the_trusted_lookup_only(self) -> None:
        with _shadow() as fake:
            found = _leaf().trusted_executable("git")
        self.assertEqual(shutil.which("git", path=TRUSTED), found)
        self.assertTrue(os.path.isabs(found))
        self.assertNotEqual(str(fake), found)

    def test_an_executable_off_the_trusted_lookup_is_refused(self) -> None:
        # Planted first on the caller's PATH, so a lookup there would find it.
        leaf = _leaf()
        with _shadow("gnostoa-not-an-executable") as fake:
            self.assertEqual(str(fake), shutil.which(fake.name))
            with self.assertRaises(FileNotFoundError):
                leaf.trusted_executable(fake.name)

    def test_a_path_qualified_name_is_refused_unsearched(self) -> None:
        # A name with a directory part is never checked as a path (cubic, Sourcery).
        leaf = _leaf()
        with _shadow() as fake:
            for name in (str(fake), f"./{fake.name}", f"sub/{fake.name}", ""):
                with self.subTest(name=name), self.assertRaises(FileNotFoundError):
                    leaf.trusted_executable(name)

    def test_the_lookup_is_the_one_agents_md_states(self) -> None:
        leaf = _leaf()
        self.assertEqual(TRUSTED, leaf.TRUSTED_PATH)
        agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn(f"PATH={leaf.TRUSTED_PATH}", agents)

    def test_the_leaf_imports_only_the_standard_library(self) -> None:
        # So that a module importing it keeps its own import-time requirements
        # (quality_evidence imports without exact_tree's open flags, #451).
        tree = ast.parse((ROOT / "tools/trusted_path.py").read_text(encoding="utf-8"))
        roots = {
            alias.name.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        } | {
            (node.module or "").split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
        }
        self.assertTrue(roots)
        self.assertLessEqual(roots, set(sys.stdlib_module_names) | {"__future__"})

    def test_exact_tree_resolves_through_the_leaf(self) -> None:
        refused = FileNotFoundError("not on the trusted lookup")
        git_executable = _original(exact_tree, "_git_executable")
        with (
            patch.object(exact_tree, "trusted_executable", side_effect=refused),
            self.assertRaises(exact_tree.ExactTreeError) as raised,
        ):
            git_executable()
        self.assertEqual("git-failed", raised.exception.code)
        self.assertEqual(
            _leaf().TRUSTED_PATH, _original(exact_tree, "_GIT_ENV")["PATH"]
        )


class SitesStartTheTrustedGitTests(unittest.TestCase):
    """Each site, driven until its first child, with the caller's PATH shadowing git: the child's first argv entry is the
    trusted git, absolute (RED on main 7cb731af, where each passes the bare name). The capsule sites, whose fixed env
    PATH already confines their lookup, align in B4 (Router 6633811124)."""

    def _first_argvs(
        self,
        call: Callable[[], object],
        *refused: type[BaseException],
        answered: int = 0,
    ) -> list[str]:
        """The first argv entry of each child `call` starts: the first `answered` succeed
        with a revision on stdout, and the next is stopped."""
        seen: list[str] = []

        def capture(argv: list[str], *_args: object, **_kwargs: object) -> object:
            seen.append(argv[0])
            if len(seen) <= answered:
                # The fields `_git_state` reads, without the subprocess module itself.
                return SimpleNamespace(
                    args=argv, returncode=0, stdout="a" * 40 + "\n", stderr=""
                )
            raise OSError("stop at this child")

        with _shadow(), patch("subprocess.run", side_effect=capture):
            try:
                call()
            except refused:
                pass
        self.assertEqual(answered + 1, len(seen), seen)
        return seen

    def _first_argv(
        self, call: Callable[[], object], *refused: type[BaseException]
    ) -> str:
        return self._first_argvs(call, *refused)[0]

    def _assert_trusted(self, first: str) -> None:
        self.assertEqual(shutil.which("git", path=TRUSTED), first)

    def test_the_quality_evidence_git_state(self) -> None:
        git_state = _original(quality_evidence, "_git_state")
        with tempfile.TemporaryDirectory() as root:
            self._assert_trusted(self._first_argv(lambda: git_state(Path(root))))

    def test_the_quality_evidence_git_state_s_status_read(self) -> None:
        # Its second start, reached once the revision read has answered.
        git_state = _original(quality_evidence, "_git_state")
        with tempfile.TemporaryDirectory() as root:
            second = self._first_argvs(lambda: git_state(Path(root)), answered=1)[1]
        self._assert_trusted(second)


class PinnedCopiesTests(unittest.TestCase):
    """The single-file authorities run without the tools/ package, so a lookup they later state must be a pinned
    copy, never an import of the leaf; this pins that they import no tools/ module (Revix on #483)."""

    def test_the_single_file_authorities_import_no_tools_module(self) -> None:
        for relative in SINGLE_FILE:
            tree = ast.parse((ROOT / relative).read_text(encoding="utf-8"))
            named = [
                alias.name
                for node in ast.walk(tree)
                if isinstance(node, ast.Import)
                for alias in node.names
            ] + [
                node.module or ""
                for node in ast.walk(tree)
                if isinstance(node, ast.ImportFrom)
            ]
            with self.subTest(relative):
                self.assertFalse([n for n in named if n.split(".")[0] == "tools"])


if __name__ == "__main__":
    unittest.main()
