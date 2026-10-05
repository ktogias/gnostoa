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
from types import SimpleNamespace
from typing import Any
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
                self.worktree, subject
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

    def test_every_push_url_must_be_bound(self) -> None:
        """Git pushes to every configured push URL, and `get-url --push` alone names
        only the first: a bound HTTPS URL followed by an SSH one is not bound (Codex on
        #364)."""
        self._bind_gh()
        self._git(
            "remote", "set-url", "--push", "origin", f"https://github.com/{SUBJECT}.git"
        )
        self._git(
            "remote",
            "set-url",
            "--add",
            "--push",
            "origin",
            f"git@github.com:{SUBJECT}.git",
        )
        self.assertEqual("UNBOUND", self._binding()[0])

    def test_two_bound_push_urls_are_bound(self) -> None:
        self._bind_gh()
        self._git(
            "remote", "set-url", "--push", "origin", f"https://github.com/{SUBJECT}.git"
        )
        self._git(
            "remote",
            "set-url",
            "--add",
            "--push",
            "origin",
            f"https://github.com/{SUBJECT}",
        )
        self.assertEqual("BOUND", self._binding()[0])

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

    def test_a_later_git_read_that_fails_is_unknown(self) -> None:
        """Every git read after the push URL fails closed: a header read that errors is
        not "no header", and a stalled read is not a traceback (gitar on #364). Each
        read fails alone, so a later read cannot mask the one under test."""
        self._bind_gh()
        real = credential_check._git  # skipcq: PYL-W0212
        target = f"https://github.com/{SUBJECT}.git"
        routing = credential_check._PUSH_ROUTING  # skipcq: PYL-W0212
        reads = {
            "the push routing": lambda a: routing in a,
            "the header": lambda a: "http.extraheader" in a,
            "the helper listing": lambda a: r"^credential\..*helper$" in a,
            "a context's normalization": lambda a: "--file" in a and a[-1] != target,
            "a context's match": lambda a: "--file" in a and a[-1] == target,
        }

        def failing(read: Any, failure: int | BaseException) -> object:
            def git(
                worktree: pathlib.Path, *arguments: str, stdin: str | None = None
            ) -> object:
                if read(arguments):
                    if isinstance(failure, BaseException):
                        raise failure
                    return SimpleNamespace(returncode=failure, stdout="", stderr="")
                return real(worktree, *arguments, stdin=stdin)

            return git

        failures = (128, subprocess.TimeoutExpired(["git"], 30), OSError("gone"))
        for name, read in reads.items():
            for failure in failures:
                with (
                    self.subTest(read=name, failure=repr(failure)),
                    mock.patch.object(
                        credential_check, "_git", side_effect=failing(read, failure)
                    ),
                ):
                    self.assertEqual("UNKNOWN", self._binding()[0])

    def test_a_scheme_less_helper_context_is_not_judged(self) -> None:
        """Git matches `github.com` to a push as a partial URL, by rules this check does
        not model: it applies, so it must not read as not applying."""
        self._bind_gh()
        self._git("config", "--add", "credential.github.com.helper", "store")
        self.assertEqual("UNKNOWN", self._binding()[0])

    def test_a_context_that_needs_quoting_is_judged(self) -> None:
        """The probe holds the context exactly, quoted as git's syntax requires, so a
        context with a quote is judged rather than misread."""
        self._bind_gh()
        self._git(
            "config", "--add", 'credential.https://github.com/other"x.helper', "store"
        )
        self.assertEqual("BOUND", self._binding()[0])

    def test_a_push_url_on_another_port_is_unbound(self) -> None:
        """A port-scoped header or helper would escape the lookup, and the push would
        not reach GitHub's own service (CodeAnt on #364)."""
        self._bind_gh()
        self._git(
            "remote",
            "set-url",
            "--push",
            "origin",
            f"https://github.com:8443/{SUBJECT}.git",
        )
        self.assertEqual("UNBOUND", self._binding()[0])

    def test_no_caller_input_reaches_a_git_argument(self) -> None:
        """The checkout is git's working directory, never an argument, and the remote
        is `origin`, never a caller's value: nothing a caller passes can become a git
        option (SonarCloud S8705 on #364)."""
        ran: list[tuple[list[str], object]] = []

        def run(argv: list[str], **options: object) -> object:
            ran.append((argv, options.get("cwd")))
            return SimpleNamespace(returncode=1, stdout="", stderr="")

        with mock.patch.object(subprocess, "run", side_effect=run):
            self._binding()
        self.assertTrue(ran)
        for argv, cwd in ran:
            with self.subTest(argv=argv):
                self.assertEqual(self.worktree, cwd)
                self.assertNotIn(str(self.worktree), argv)
                self.assertNotIn("-C", argv)
        # The remotes are git's own answer, never a caller's value.
        self.assertEqual(["remote"], ran[0][0][1:])

    def test_a_push_default_to_another_remote_is_unbound(self) -> None:
        """A bare `git push` follows `branch.<name>.pushRemote`, then
        `remote.pushDefault`, then `branch.<name>.remote`, not `origin` (Codex on
        #364): every destination Git could choose must be bound."""
        self._bind_gh()
        self._git("remote", "add", "fork", f"git@github.com:{SUBJECT}.git")
        self._git("config", "remote.pushDefault", "fork")
        self.assertEqual("UNBOUND", self._binding()[0])

    def test_a_branch_push_remote_elsewhere_is_unbound(self) -> None:
        self._bind_gh()
        self._git("remote", "add", "fork", f"git@github.com:{SUBJECT}.git")
        self._git("config", "branch.main.pushRemote", "fork")
        self.assertEqual("UNBOUND", self._binding()[0])

    def test_a_push_default_that_is_a_url_is_judged_as_one(self) -> None:
        self._bind_gh()
        self._git("config", "remote.pushDefault", f"git@github.com:{SUBJECT}.git")
        self.assertEqual("UNBOUND", self._binding()[0])

    def test_every_remote_must_be_bound(self) -> None:
        self._bind_gh()
        self._git("remote", "add", "upstream", f"git@github.com:{SUBJECT}.git")
        self.assertEqual("UNBOUND", self._binding()[0])

    def test_a_second_bound_remote_and_a_local_upstream_are_bound(self) -> None:
        self._bind_gh()
        self._git("remote", "add", "mirror", f"https://github.com/{SUBJECT}")
        self._git("config", "branch.main.remote", ".")
        self.assertEqual("BOUND", self._binding()[0])

    def test_a_header_or_helper_scoped_to_the_git_url_is_found(self) -> None:
        """Git looks configuration up by the URL it pushes to, `.git` and all: a header
        or helper scoped to that exact URL must not be missed (CodeAnt on #364)."""
        exact = f"https://github.com/{SUBJECT}.git"
        for key, value in (
            (f"http.{exact}.extraheader", "AUTHORIZATION: basic x"),
            (f"credential.{exact}.helper", "store"),
        ):
            with self.subTest(key=key):
                self._bind_gh()
                self._git("config", key, value)
                try:
                    self.assertEqual("UNBOUND", self._binding()[0])
                finally:
                    self._git("config", "--unset-all", key)
                    self._git(
                        "config", "--unset-all", "credential.https://github.com.helper"
                    )

    def test_an_option_shaped_remote_name_never_reaches_git(self) -> None:
        """A remote name comes from configuration, which can say anything: one git could
        read as an option is refused before it reaches a git command line."""
        self._bind_gh()
        self._git("config", "remote.-evil.url", f"https://github.com/{SUBJECT}.git")
        real = credential_check._git  # skipcq: PYL-W0212
        seen: list[tuple[str, ...]] = []

        def spy(
            worktree: pathlib.Path, *arguments: str, stdin: str | None = None
        ) -> object:
            seen.append(arguments)
            return real(worktree, *arguments, stdin=stdin)

        with mock.patch.object(credential_check, "_git", side_effect=spy):
            state, evidence = self._binding()
        self.assertEqual("UNKNOWN", state)
        self.assertIn("option", evidence)
        self.assertFalse(any("-evil" in arguments for arguments in seen))

    def test_a_routed_url_a_rewrite_could_change_is_not_judged(self) -> None:
        """A remote's URLs come back from git already rewritten, but a URL that push
        routing names directly is the raw value: with any `insteadOf` or
        `pushInsteadOf` configured, git could push it somewhere else (gitar on #364)."""
        self._bind_gh()
        # Origin's own URL differs in case, so only the routed URL matches the rewrite
        # (git's prefixes are case-sensitive; GitHub's names are not).
        self._git(
            "remote", "set-url", "origin", "https://github.com/KTOGIAS/gnostoa.git"
        )
        routed = f"https://github.com/{SUBJECT}"
        self._git("config", "remote.pushDefault", routed)
        self.assertEqual("BOUND", self._binding()[0])
        self._git("config", f"url.git@github.com:{SUBJECT}.pushInsteadOf", routed)
        self.assertNotEqual("BOUND", self._binding()[0])

    def test_a_context_git_normalizes_is_found(self) -> None:
        """Git normalizes a credential context before matching it: a host in another
        case, a default port, a percent-encoded path all apply to the push, so a helper
        or an empty reset under one must not be missed (Codex and CodeAnt on #364)."""
        # Git matches a path at a segment boundary: the owner segment applies to
        # `<owner>/<name>.git`.
        owner = SUBJECT.partition("/")[0]
        encoded = f"{owner[:-1]}%{ord(owner[-1]):02X}"
        for context, values in (
            ("https://GITHUB.COM", ("store",)),
            ("https://github.com:443", ("store",)),
            (f"https://github.com/{encoded}", ("store",)),
            # Codex's case: the reset drops the trusted gh, another helper follows.
            ("https://GITHUB.COM", ("", "store")),
        ):
            key = f"credential.{context}.helper"
            with self.subTest(context=context, values=values):
                self._bind_gh()
                for value in values:
                    self._git("config", "--add", key, value)
                try:
                    self.assertEqual("UNBOUND", self._binding()[0])
                finally:
                    self._git("config", "--unset-all", key)
                    self._git(
                        "config", "--unset-all", "credential.https://github.com.helper"
                    )

    def test_a_context_git_cannot_normalize_is_not_judged(self) -> None:
        """Git matches a context it cannot normalize as a partial URL, by rules this
        check does not model: such a context is not judged, so it fails closed."""
        self._bind_gh()
        self._git(
            "config", "--add", "credential.https://github.com/%zz.helper", "store"
        )
        self.assertEqual("UNKNOWN", self._binding()[0])

    def test_an_inherited_exec_path_is_unbound(self) -> None:
        """`GIT_EXEC_PATH` chooses which `git-remote-https` a push runs, so a session
        that sets it may push through a transport other than the one checked (Codex on
        #364)."""
        self._bind_gh()
        self.environment["GIT_EXEC_PATH"] = str(
            pathlib.Path(self.scratch.name) / "exec"
        )
        state, evidence = self._binding()
        self.assertEqual("UNBOUND", state)
        self.assertIn("GIT_EXEC_PATH", evidence)

    def test_a_helper_reached_through_a_replaceable_link_is_unbound(self) -> None:
        """Git runs the helper's own path, not its target: a link to the trusted gh in
        a directory others can write can be repointed after the check (Codex on #364).
        The helper's path is held to the rule `trusted_executable` applies."""
        links = pathlib.Path(self.scratch.name) / "links"
        links.mkdir()
        link = links / "gh"
        link.symlink_to(self.gh)
        links.chmod(0o775)
        self._git("config", "--add", "credential.https://github.com.helper", "")
        self._git(
            "config",
            "--add",
            "credential.https://github.com.helper",
            f"!{link} auth git-credential",
        )
        self.assertEqual("UNBOUND", self._binding()[0])
        links.chmod(0o755)
        self.assertEqual("BOUND", self._binding()[0])

    def test_a_missing_remote_is_unknown(self) -> None:
        self._git("remote", "remove", "origin")
        self.assertEqual("UNKNOWN", self._binding()[0])


if __name__ == "__main__":
    unittest.main()
