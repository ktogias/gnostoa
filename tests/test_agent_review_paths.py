"""The one path-confinement check, for a root its caller names (#365, Decision 0101).

`within` confines a path to a root named by an environment variable, as the review
pipeline's runners supply. A command whose root is a directory it already holds -- the
credential check's working tree -- had no form to call, so it wrote its own check
(#365, I4). `within_root` is that form, sharing every degenerate-input refusal with
`within` rather than repeating it.
"""

from __future__ import annotations

import os
import pathlib
import tempfile
import unittest
from unittest import mock

from tools import agent_review_paths


class WithinRootTests(unittest.TestCase):
    """A path is confined to a named directory, with `within`'s refusals."""

    def test_a_path_inside_the_root_is_returned_resolved(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            inside = pathlib.Path(root) / "policy.yaml"
            inside.write_text("x: 1\n", encoding="utf-8")
            self.assertEqual(
                inside.resolve(),
                agent_review_paths.within_root(
                    str(inside), pathlib.Path(root), must_exist=True
                ),
            )

    def test_a_relative_path_resolves_from_the_working_directory(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            (pathlib.Path(root) / "p.yaml").write_text("x: 1\n", encoding="utf-8")
            previous = pathlib.Path.cwd()
            os.chdir(root)
            try:
                found = agent_review_paths.within_root(
                    "p.yaml", pathlib.Path(root), must_exist=True
                )
            finally:
                os.chdir(previous)
        self.assertEqual("p.yaml", found.name)

    def test_anything_outside_the_root_is_refused(self) -> None:
        with (
            tempfile.TemporaryDirectory() as root,
            tempfile.TemporaryDirectory() as other,
        ):
            outside = pathlib.Path(other) / "p.yaml"
            outside.write_text("x: 1\n", encoding="utf-8")
            for refused in (
                str(outside),
                "/etc/hostname",
                str(pathlib.Path(root).parent),
            ):
                with self.subTest(refused=refused), self.assertRaises(ValueError):
                    agent_review_paths.within_root(
                        refused, pathlib.Path(root), must_exist=True
                    )

    def test_the_refusals_are_within_s_own(self) -> None:
        """Empty, missing and directory-for-a-file are refused exactly as `within`
        refuses them: one implementation of each check."""
        with tempfile.TemporaryDirectory() as root:
            base = pathlib.Path(root)
            cases = (
                ("", False),
                ("   ", False),
                (str(base / "absent"), True),
                (root, False),
            )
            for raw, must_exist in cases:
                with (
                    mock.patch.dict(os.environ, {"GNOSTOA_TEST_ROOT": root}),
                    self.assertRaises(ValueError) as shared,
                ):
                    agent_review_paths.within(
                        raw, "GNOSTOA_TEST_ROOT", must_exist=must_exist
                    )
                with self.subTest(raw=raw), self.assertRaises(ValueError) as named:
                    agent_review_paths.within_root(raw, base, must_exist=must_exist)
                self.assertEqual(
                    str(shared.exception).split(":")[0],
                    str(named.exception).split(":")[0],
                )


if __name__ == "__main__":
    unittest.main()
