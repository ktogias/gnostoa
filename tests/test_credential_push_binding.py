"""The push credential is the checked token, or the check says so (Decision 0101, #364).

A push authenticates through Git's own credential: a credential helper, a header Git
is told to send, or an SSH key. `knowledge credential-check` checks the token the
agents' API tooling uses, so it also shows that Git's push to the subject uses that
same token: an HTTPS push URL with no credential in it, Git's effective helpers for
it exactly the trusted `gh`, and no extra header. Every case runs real `git` against a
real configuration (Codex on #364; owner decision 2026-10-05).
"""

from __future__ import annotations

import os
import pathlib
import subprocess  # nosec B404
import tempfile
import unittest
from unittest import mock

from tools import credential_check

SUBJECT = "ktogias/gnostoa"


class PushBindingTests(unittest.TestCase):
    """`_push_binding` reads the worktree's Git configuration, never a credential."""

    def setUp(self) -> None:
        self.scratch = tempfile.TemporaryDirectory()
        self.addCleanup(self.scratch.cleanup)
        base = pathlib.Path(self.scratch.name)
        self.home = base / "home"
        self.home.mkdir()
        self.worktree = base / "worktree"
        self.worktree.mkdir()
        tools = base / "tools"
        tools.mkdir()
        self.gh = tools / "gh"
        self.gh.write_text("#!/bin/sh\\n", encoding="utf-8")
        self.gh.chmod(0o755)
        tools.chmod(0o755)
        self.environment = {
            "PATH": "/usr/local/bin:/usr/bin:/bin",
            "HOME": str(self.home),
            "GIT_CONFIG_NOSYSTEM": "1",
        }
        self._git("init", "--quiet")
        self._git("remote", "add", "origin", f"https://github.com/{SUBJECT}.git")

    def _git(self, *arguments: str) -> None:
        subprocess.run(  # nosec B603 B607
            ["git", "-C", str(self.worktree), *arguments],
            check=True,
            capture_output=True,
            env=self.environment,
        )

    def _bind_gh(self) -> None:
        self._git("config", "--add", "credential.https://github.com.helper", "")
        self._git(
            "config",
            "--add",
            "credential.https://github.com.helper",
            f"!{self.gh} auth git-credential",
        )

    def _binding(self, subject: str = SUBJECT) -> tuple[str, str]:
        def trusted(name: str) -> str | None:
            return {"gh": str(self.gh.resolve())}.get(name) or __import__(
                "shutil"
            ).which(name, path="/usr/bin:/bin")

        with (
            mock.patch.dict(os.environ, self.environment, clear=True),
            mock.patch.object(
                credential_check, "trusted_executable", side_effect=trusted
            ),
        ):
            return credential_check._push_binding(  # skipcq: PYL-W0212
                self.worktree, subject, "origin"
            )

    def test_gh_managed_https_is_bound(self) -> None:
        self._bind_gh()
        state, evidence = self._binding()
        self.assertEqual("BOUND", state, evidence)

    def test_another_helper_before_gh_is_unbound(self) -> None:
        """Git asks every helper in turn: a store or keychain helper that is not reset
        can answer with another credential first."""
        self._git("config", "--global", "credential.helper", "store")
        self._git(
            "config",
            "--add",
            "credential.https://github.com.helper",
            f"!{self.gh} auth git-credential",
        )
        self.assertEqual("UNBOUND", self._binding()[0])

    def test_a_helper_reset_after_gh_is_unbound(self) -> None:
        self._bind_gh()
        self._git("config", "--add", "credential.helper", "")
        self.assertEqual("UNBOUND", self._binding()[0])

    def test_an_untrusted_gh_is_unbound(self) -> None:
        self._git("config", "--add", "credential.https://github.com.helper", "")
        self._git(
            "config",
            "--add",
            "credential.https://github.com.helper",
            "!gh auth git-credential",
        )
        self.assertEqual("UNBOUND", self._binding()[0])

    def test_an_ssh_push_url_is_unbound(self) -> None:
        self._bind_gh()
        self._git(
            "remote", "set-url", "--push", "origin", f"git@github.com:{SUBJECT}.git"
        )
        self.assertEqual("UNBOUND", self._binding()[0])

    def test_a_push_rewritten_to_ssh_is_unbound(self) -> None:
        self._bind_gh()
        self._git("config", "url.git@github.com:.pushInsteadOf", "https://github.com/")
        self.assertEqual("UNBOUND", self._binding()[0])

    def test_a_credential_in_the_url_is_unbound(self) -> None:
        self._bind_gh()
        # Built from parts: a credential-shaped literal would itself trip the secret scan.
        hidden = "p" * 12
        userinfo = ":".join(("someone", hidden))
        self._git(
            "remote",
            "set-url",
            "--push",
            "origin",
            f"https://{userinfo}@github.com/{SUBJECT}.git",
        )
        state, evidence = self._binding()
        self.assertEqual("UNBOUND", state)
        self.assertNotIn(hidden, evidence)

    def test_an_extra_header_is_unbound(self) -> None:
        self._bind_gh()
        self._git(
            "config", "http.https://github.com/.extraheader", "AUTHORIZATION: basic x"
        )
        state, evidence = self._binding()
        self.assertEqual("UNBOUND", state)
        self.assertNotIn("basic x", evidence)

    def test_a_push_to_another_repository_is_unbound(self) -> None:
        self._bind_gh()
        self.assertEqual("UNBOUND", self._binding("ktogias/other")[0])

    def test_a_push_to_another_host_is_unbound(self) -> None:
        self._bind_gh()
        self._git(
            "remote", "set-url", "--push", "origin", f"https://gitlab.com/{SUBJECT}.git"
        )
        self.assertEqual("UNBOUND", self._binding()[0])

    def test_a_helper_naming_another_gh_is_unbound(self) -> None:
        other = pathlib.Path(self.scratch.name) / "other-gh"
        other.write_text("#!/bin/sh\n", encoding="utf-8")
        other.chmod(0o755)
        self._git("config", "--add", "credential.https://github.com.helper", "")
        self._git(
            "config",
            "--add",
            "credential.https://github.com.helper",
            f"!{other} auth git-credential",
        )
        self.assertEqual("UNBOUND", self._binding()[0])

    def test_a_wildcard_helper_context_is_not_judged(self) -> None:
        self._bind_gh()
        self._git("config", "--add", "credential.https://*.github.com.helper", "store")
        self.assertEqual("UNKNOWN", self._binding()[0])

    def test_a_missing_remote_is_unknown(self) -> None:
        self._git("remote", "remove", "origin")
        self.assertEqual("UNKNOWN", self._binding()[0])


if __name__ == "__main__":
    unittest.main()
