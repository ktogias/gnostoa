"""The merge gate's record states the policy in force, and agents are routed to it
(Decision 0110, #398)."""

from __future__ import annotations

import json
import re
import shutil
import subprocess  # nosec B404 -- test-only: runs the runbook's own shell functions
import tempfile
import unittest
from pathlib import Path
from typing import cast

ROOT = Path(__file__).resolve().parents[1]
RUNBOOK = ROOT / "knowledge" / "runbooks" / "operate-the-merge-gate.md"
DECISION = (
    ROOT
    / "knowledge"
    / "decisions"
    / "0110-bind-every-merge-to-the-owner-s-approval-of-the-exact-head.md"
)


# A calling shell as hostile to the token as a shell can be by accident: functions
# for what the bodies run, `gh`'s own variables, and a read-only `GH_CONFIG_DIR`
# (Codex, cubic and Claude on #400).
_CALLER = (
    'gh() { touch "$SHADOWED"; }\n'
    'test() { touch "$SHADOWED"; return 0; }\n'
    'cat() { touch "$SHADOWED"; echo t0ken; }\n'
    'mktemp() { touch "$SHADOWED"; echo "$KEPT"; }\n'
    'command() { touch "$SHADOWED"; }\n'
    "export GH_HOST=ghe.example.com GH_REPO=elsewhere/repo GH_DEBUG=api\n"
    'readonly GH_CONFIG_DIR="$KEPT"\n'
)


def _shells() -> list[str]:
    """Each POSIX shell present, by path."""
    return [path for name in ("sh", "bash", "dash") if (path := shutil.which(name))]


# AGENTS.md's fixed system path, so no entry of a caller's PATH is searched (Codex on
# #400).
FIXED_PATH = "/usr/local/bin:/usr/bin:/bin:/opt/homebrew/bin"


def _isolated(mint: str, tail: str) -> str:
    """The guarded body the runbook writes, whitespace normalised. It runs in a fresh
    `/bin/sh`, started by absolute path through `env -i`, so no function, alias or
    variable of the calling shell reaches it, only `PATH`, `HOME` and `TMPDIR`
    (cubic and Codex on #400). It traps every signal AGENTS.md's helper traps, and
    removes only the directory `mktemp` made (cubic and Claude on #400)."""
    return (
        f"/usr/bin/env -i PATH={FIXED_PATH} "
        'HOME="$HOME" TMPDIR="${TMPDIR:-/tmp}" '
        '/bin/sh -c \' cleanup() { unset GH_TOKEN; rm -rf -- "$created"; } '
        'trap "exit 130" INT trap "exit 143" TERM trap "exit 129" HUP '
        "created=$(mktemp -d) || exit trap cleanup EXIT "
        "GH_CONFIG_DIR=$created && export GH_CONFIG_DIR "
        f'&& GH_TOKEN={mint} && test -n "$GH_TOKEN" && export GH_TOKEN && gh {tail}'
    )


class MergeGateRecordTests(unittest.TestCase):
    def _r_main(self) -> dict[str, list[dict[str, object]]]:
        text = RUNBOOK.read_text(encoding="utf-8")
        block = re.search(r"```json\n(\{.*?\})\n```", text, re.S)
        if block is None:
            self.fail("the runbook records R-main as JSON")
        return cast(dict[str, list[dict[str, object]]], json.loads(block.group(1)))

    def _rules(self) -> dict[str, dict[str, object]]:
        # Each rule type once, so a duplicate cannot overwrite the one checked
        # (CodeAnt on #400).
        types = [str(rule["type"]) for rule in self._r_main()["rules"]]
        self.assertEqual(sorted(set(types)), sorted(types))
        return {
            str(rule["type"]): cast(dict[str, object], rule.get("parameters", {}))
            for rule in self._r_main()["rules"]
        }

    def test_r_main_requires_the_code_owner_s_approval_of_the_exact_head(self) -> None:
        pull_request = self._rules()["pull_request"]
        self.assertEqual(1, pull_request["required_approving_review_count"])
        for flag in (
            "require_code_owner_review",
            "dismiss_stale_reviews_on_push",
            "require_last_push_approval",
            "required_review_thread_resolution",
            # A safeguard the recorded policy holds too (CodeAnt on #400).
            "require_extra_approval_for_unattributed_changes",
        ):
            with self.subTest(flag=flag):
                self.assertIs(True, pull_request[flag])
        self.assertEqual(["squash"], pull_request["allowed_merge_methods"])

    def test_r_main_requires_the_four_checks_from_github_actions(self) -> None:
        rules = self._rules()
        checks = rules["required_status_checks"]
        self.assertIs(True, checks["strict_required_status_checks_policy"])
        self.assertEqual(
            {
                ("policy", 15368),
                ("fast", 15368),
                ("regression", 15368),
                ("smoke", 15368),
            },
            {
                (check["context"], check["integration_id"])
                for check in cast(
                    list[dict[str, object]], checks["required_status_checks"]
                )
            },
        )
        for rule in ("deletion", "non_fast_forward", "required_linear_history"):
            with self.subTest(rule=rule):
                self.assertIn(rule, rules)

    def test_only_break_glass_bypasses_r_main(self) -> None:
        """R-main's bypass list is pinned: break glass alone, in pull-request mode
        (Sourcery on #400)."""
        self.assertEqual(
            [
                {
                    "actor_id": 5230732,
                    "actor_type": "Integration",
                    "bypass_mode": "pull_request",
                }
            ],
            self._r_main()["bypass_actors"],
        )

    def test_only_the_code_owner_approves(self) -> None:
        """Every active CODEOWNERS entry names the owner alone, so no path-specific
        rule lets another reviewer's approval count (cubic, Sourcery, CodeAnt and
        Codex on #400)."""
        owners = (ROOT / ".github" / "CODEOWNERS").read_text(encoding="utf-8")
        entries = [
            line.split()
            for line in owners.splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        ]
        self.assertIn(["*", "@ktogias"], entries)
        for entry in entries:
            with self.subTest(pattern=entry[0]):
                self.assertEqual(["@ktogias"], entry[1:])

    def test_agents_are_routed_to_the_runbook(self) -> None:
        agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("knowledge/runbooks/operate-the-merge-gate.md", agents)
        prose = " ".join(agents.split())
        self.assertIn("never with `--admin`", prose)
        # The one exception is named where the rule is (CodeAnt on #400).
        self.assertIn("except through break glass", prose)
        # The summary does not read as GitHub binding the head (Claude on #400).
        self.assertIn(
            "until Phase 1b, the App checks that the approval's `commit_id` is that head",
            prose,
        )

    def test_no_command_carries_a_token_or_a_bare_helper(self) -> None:
        """A token reaches `gh` only through `$(...)`, never as a literal in a
        command or its history; each helper and the token file are named by their
        full path (cubic, Sourcery and CodeAnt on #400)."""
        text = RUNBOOK.read_text(encoding="utf-8")
        # Each token comes from a known minting command, run by its absolute path
        # (cubic and CodeAnt on #400).
        minted = {
            "$(~/.config/gnostoa-agent/bin/agent-token.sh)",
            "$(cat ~/.config/gnostoa-agent/machine-user-token)",
            "$(~/break-glass/break-glass-token.sh)",
        }
        assigned = re.findall(r"GH_TOKEN=(\$\([^)]*\)|\S*)", text)
        self.assertTrue(assigned)
        for value in assigned:
            with self.subTest(assignment=value):
                self.assertIn(value.rstrip("`"), minted)
        for literal in (
            r"--token\b",
            r"[Aa]uthorization:",
            r"x-access-token:",
            r"\bgh[opsur]_[A-Za-z0-9]{8,}",
            r"github_pat_",
        ):
            with self.subTest(literal=literal):
                self.assertIsNone(re.search(literal, text))
        for name in (
            "bin/agent-token.sh",
            "bin/agent-git.sh",
            "bin/agent-jwt.sh",
            "machine-user-token",
        ):
            base = name.rsplit("/", 1)[-1]
            for match in re.finditer(rf"(\S*?){re.escape(base)}", text):
                with self.subTest(name=base, at=match.start()):
                    self.assertTrue(
                        match.group(0).endswith(f"~/.config/gnostoa-agent/{name}"),
                        match.group(0),
                    )

    def test_gh_runs_only_after_a_checked_mint(self) -> None:
        """`GH_TOKEN=$(...) gh` still runs `gh` when the mint fails, which then falls
        back to a stored login (Codex on #400). So `gh` runs only through two
        functions whose bodies are subshells: the configuration directory first,
        then the mint, checked, then `gh` alone holds the token, which never exists
        in the calling shell (Codex and CodeAnt on #400)."""
        text = RUNBOOK.read_text(encoding="utf-8")
        blocks = [
            " ".join(block.replace("\\\n", " ").split())
            for block in re.findall(r"```sh\n(.*?)```", text, re.S)
        ]
        self.assertIn(
            "as_app() { "
            + _isolated(
                "$(~/.config/gnostoa-agent/bin/agent-token.sh)", '"$@" \' as_app "$@" }'
            )
            + " as_machine_user() { "
            + _isolated(
                "$(cat ~/.config/gnostoa-agent/machine-user-token)",
                '"$@" \' as_machine_user "$@" }',
            ),
            blocks,
        )
        for path in (RUNBOOK, ROOT / "AGENTS.md"):
            with self.subTest(path=path.name):
                self.assertIsNone(
                    re.search(
                        r"GH_TOKEN=\$\([^)]*\)\s*(?:\\\s*)?gh\b",
                        path.read_text(encoding="utf-8"),
                    )
                )
        # Every `gh` a command block runs is one of the two bodies or break glass.
        for block in blocks:
            for call in re.findall(r"(?<![\w-])gh (\S+)", block):
                with self.subTest(block=block[:60], call=call):
                    self.assertIn(call, {'"$@"', "api"})
                    if call == "api":
                        self.assertIn("break-glass-token.sh", block)

    def test_the_guarded_functions_run_as_written(self) -> None:
        """The two functions, executed verbatim, in each shell present, from a calling
        shell that defines `gh`, `test`, `cat`, `mktemp` and `command` functions,
        exports `GH_HOST`, `GH_REPO` and `GH_DEBUG`, and holds a read-only
        `GH_CONFIG_DIR` (Codex, cubic and Claude on #400). With stand-ins for the
        mint and `gh` under a test `HOME`: a failed or empty mint stops before `gh`; a
        working one runs the real `gh` with the token and none of the caller's
        variables; no caller function runs; the token never reaches the caller; the
        caller's configuration survives, populated or empty; and nothing is left in
        `TMPDIR`."""
        text = RUNBOOK.read_text(encoding="utf-8")
        self.assertIn(
            "Define them again after any change to this section", " ".join(text.split())
        )
        [block] = [
            b for b in re.findall(r"```sh\n(.*?)```", text, re.S) if "as_app() {" in b
        ]
        shells = [
            path for name in ("sh", "bash", "dash") if (path := shutil.which(name))
        ]
        self.assertTrue(shells)
        cases = (
            ("as_app", "exit 4", 4),
            ("as_app", "exit 0", 1),
            ("as_app", "echo t0ken", 0),
            ("as_machine_user", "", 1),
            ("as_machine_user", "t0ken", 0),
        )
        for interpreter in shells:
            for function, source, expected in cases:
                for populated in (True, False):
                    with (
                        self.subTest(
                            interpreter=interpreter,
                            function=function,
                            source=source,
                            populated=populated,
                        ),
                        tempfile.TemporaryDirectory() as directory,
                    ):
                        root = Path(directory)
                        helpers = root / ".config" / "gnostoa-agent" / "bin"
                        helpers.mkdir(parents=True)
                        for name in ("bin", "tmp", "caller config"):
                            (root / name).mkdir()
                        kept = root / "caller config"
                        if populated:
                            (kept / "hosts.yml").write_text("kept\n", encoding="utf-8")
                        mint = helpers / "agent-token.sh"
                        mint.write_text(f"#!/bin/sh\n{source}\n", encoding="utf-8")
                        mint.chmod(0o755)
                        (helpers.parent / "machine-user-token").write_text(
                            source, encoding="utf-8"
                        )
                        gh = root / "bin" / "gh"
                        # It writes into its configuration directory, as a real `gh` may,
                        # and the clean-up still leaves nothing (Claude on #400).
                        gh.write_text(
                            '#!/bin/sh\ntouch "$GH_CONFIG_DIR/state.yml"\n'
                            "printf '%s %s|%s|%s\\n' \"${GH_TOKEN:+token}\" "
                            '"${GH_HOST-}" "${GH_REPO-}" "${GH_DEBUG-}" > "$HOME/seen"\n',
                            encoding="utf-8",
                        )
                        gh.chmod(0o755)
                        test_path = f"{root / 'bin'}:/usr/bin:/bin"
                        script = (
                            _CALLER
                            + block.replace(FIXED_PATH, test_path)
                            + f"\n{function} api x\nstatus=$?\n"
                            + 'printf "%s %s\\n" "$status" "${GH_TOKEN-unset}"\n'
                        )
                        done = subprocess.run(  # nosec B603  # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-audit.dangerous-subprocess-use-audit
                            [interpreter, "-c", script],
                            capture_output=True,
                            text=True,
                            check=False,
                            timeout=30,
                            env={
                                "PATH": f"{root / 'bin'}:/usr/bin:/bin",
                                "HOME": str(root),
                                "TMPDIR": str(root / "tmp"),
                                "KEPT": str(kept),
                                "SHADOWED": str(root / "shadowed"),
                            },
                        )
                        self.assertEqual(
                            f"{expected} unset",
                            done.stdout.strip().splitlines()[-1],
                            done.stderr,
                        )
                        seen = root / "seen"
                        self.assertEqual(expected == 0, seen.exists())
                        if seen.exists():
                            self.assertEqual(
                                "token ||", seen.read_text(encoding="utf-8").strip()
                            )
                        self.assertFalse((root / "shadowed").exists())
                        self.assertTrue(kept.is_dir())
                        self.assertEqual(populated, (kept / "hosts.yml").is_file())
                        self.assertEqual([], list((root / "tmp").iterdir()))

    def test_break_glass_runs_as_written(self) -> None:
        """Break glass's block, executed as written with its placeholders filled, from
        the same calling shell: a failed or empty mint stops before `gh`; a working
        one merges the exact head with the token; nothing is left in `TMPDIR` (Claude
        on #400)."""
        text = RUNBOOK.read_text(encoding="utf-8")
        shells = _shells()
        self.assertTrue(shells)
        [glass] = [
            b
            for b in re.findall(r"```sh\n(.*?)```", text, re.S)
            if "break-glass-token.sh" in b
        ]
        for interpreter in shells:
            for source, expected in (("exit 4", 4), ("exit 0", 1), ("echo t0ken", 0)):
                with (
                    self.subTest(interpreter=interpreter, glass=source),
                    tempfile.TemporaryDirectory() as directory,
                ):
                    root = Path(directory)
                    (root / "break-glass").mkdir()
                    for name in ("bin", "tmp"):
                        (root / name).mkdir()
                    mint = root / "break-glass" / "break-glass-token.sh"
                    mint.write_text(f"#!/bin/sh\n{source}\n", encoding="utf-8")
                    mint.chmod(0o755)
                    gh = root / "bin" / "gh"
                    gh.write_text(
                        '#!/bin/sh\ntouch "$GH_CONFIG_DIR/state.yml"\n'
                        'printf "%s %s\\n" "${GH_TOKEN:+token}" "$*" > "$HOME/seen"\n',
                        encoding="utf-8",
                    )
                    gh.chmod(0o755)
                    filled = (
                        glass.replace("<N>", "7")
                        .replace("<head>", "0123abc")
                        .replace(FIXED_PATH, f"{root / 'bin'}:/usr/bin:/bin")
                    )
                    done = subprocess.run(  # nosec B603  # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-audit.dangerous-subprocess-use-audit
                        [
                            interpreter,
                            "-c",
                            # The caller's token stays unset after the block (cubic on
                            # #400).
                            _CALLER
                            + filled
                            + '\nprintf "%s %s\\n" "$?" "${GH_TOKEN-unset}"\n',
                        ],
                        capture_output=True,
                        text=True,
                        check=False,
                        timeout=30,
                        env={
                            "PATH": "/usr/bin:/bin",
                            "HOME": str(root),
                            "TMPDIR": str(root / "tmp"),
                            "KEPT": str(root / "tmp"),
                            "SHADOWED": str(root / "shadowed"),
                        },
                    )
                    self.assertEqual(
                        f"{expected} unset",
                        done.stdout.strip().splitlines()[-1],
                        done.stderr,
                    )
                    seen = root / "seen"
                    self.assertEqual(expected == 0, seen.exists())
                    if seen.exists():
                        self.assertEqual(
                            "token api -X PUT repos/ktogias/gnostoa/pulls/7/merge "
                            "-f merge_method=squash -f sha=0123abc",
                            seen.read_text(encoding="utf-8").strip(),
                        )
                    self.assertFalse((root / "shadowed").exists())
                    self.assertEqual([], list((root / "tmp").iterdir()))

    def test_the_host_rules_name_tracing_and_the_trusted_path(self) -> None:
        """Bash prints a command's expansion under xtrace, token included, so no
        token command runs with it on or in a recorded session (Claude on #400).
        The host's PATH resolves every program that holds a token, so it is part of
        the trust boundary, as recorded (cubic on #400)."""
        runbook = " ".join(RUNBOOK.read_text(encoding="utf-8").split())
        # Every program the procedure runs is named: `jq` (CodeAnt on #400), and `cat`
        # and `rm`, which the guarded bodies run (cubic and Claude on #400).
        needs = re.search(
            r"The procedure needs (.+?) on the fixed system path", runbook
        )
        if needs is None:
            self.fail("the runbook names the programs the procedure needs")
        named = set(re.findall(r"`([\w.]+)`", needs.group(1)))
        for program in (
            "gh",
            "git",
            "jq",
            "curl",
            "openssl",
            "python3",
            "cat",
            "rm",
            "mktemp",
        ):
            with self.subTest(program=program):
                self.assertIn(program, named)
        for phrase in (
            "never with xtrace (`set -x`) on, nor in a recorded session",
            "The host's `PATH` is trusted",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, runbook)

    def test_each_program_trusted_on_the_path_is_shown_holding_the_token(
        self,
    ) -> None:
        """Every program the trusted-PATH rule names appears where the runbook
        shows it holding a token, so the boundary can be audited (Claude on
        #400)."""
        text = RUNBOOK.read_text(encoding="utf-8")
        rule = re.search(
            r"It resolves every program that holds a token or the App's key: ([^.]+)\.",
            " ".join(text.split()),
        )
        if rule is None:
            self.fail("the runbook names the programs its trusted PATH resolves")
        programs = re.findall(r"`([\w.]+)`", rule.group(1))
        # Each program on a host entry, a table row or a rule, that handles a token
        # or the App's key: a mention elsewhere, such as `gh pr create`, or beside
        # nothing secret, does not count (cubic and CodeAnt on #400).
        host = text[text.index("### The agent host") : text.index("## Procedure")]
        entries = [
            entry
            for entry in re.split(r"\n(?=- |\| )", host)
            if "is trusted" not in entry
        ]
        for program in programs:
            named = re.compile(
                rf"`{re.escape(program)}`|\$\((?:command )?{re.escape(program)} "
                rf"|\) {re.escape(program)} "
            )
            with self.subTest(program=program):
                self.assertTrue(
                    any(
                        named.search(entry) and re.search(r"token|key|JWT", entry, re.I)
                        for entry in entries
                    ),
                    program,
                )

    def test_the_merge_binds_the_sha_the_owner_approved(self) -> None:
        """The App merges the `commit_id` of the owner's approving review, not the
        PR's current head, so a push that keeps the diff cannot slip in a commit
        the owner never saw (Codex on #400)."""
        raw = RUNBOOK.read_text(encoding="utf-8")
        runbook = " ".join(raw.split())
        merge = runbook[
            runbook.index("8. **The merge.**") : runbook.index(
                "9. **After the merge.**"
            )
        ]
        merge_text = raw[
            raw.index("8. **The merge.**") : raw.index("9. **After the merge.**")
        ]
        self.assertIn("`commit_id` of the owner's latest `APPROVED` review", merge)
        # The command itself, not only its prose (CodeAnt on #400): every page is
        # read before the latest owner review is chosen, since `--jq` with
        # `--paginate` runs once per page (cubic, Codex, CodeAnt and Claude on
        # #400).
        self.assertIn("pulls/<N>/reviews --paginate --slurp", merge)
        self.assertIn(
            """jq -r '[.[][] | select(.user.login == "ktogias")] | last | """
            """select(.state == "APPROVED") | .commit_id'""",
            merge,
        )
        # The squash message is pinned to the subject and body the pre-merge check
        # read, since either can be edited without moving the head (Codex on #400).
        # The merge passes no message: the squash commit's message is the commits',
        # which `<approved>` binds, and its title the PR's, which the comparison
        # below binds, so the PR's title, untrusted text, is never on a command line
        # (Codex and Claude on #400).
        [line] = [
            line.strip()
            for block in re.findall(
                r"```sh\n(.*?)```", RUNBOOK.read_text(encoding="utf-8"), re.S
            )
            for line in block.splitlines()
            if line.strip().startswith("as_app pr merge")
        ]
        self.assertEqual(
            "as_app pr merge <N> --squash --match-head-commit <approved>", line
        )
        self.assertNotIn("<subject>", merge)
        self.assertIn(
            "`<approved>` binds the commits, and the comparison binds the title", merge
        )
        for setting in (
            "`squash_merge_commit_title: COMMIT_OR_PR_TITLE`",
            "`squash_merge_commit_message: COMMIT_MESSAGES`",
        ):
            with self.subTest(setting=setting):
                self.assertIn(setting, runbook[: runbook.index("## Procedure")])
        # The comparison is a step, not a hope (CodeAnt on #400).
        self.assertIn(
            "Stop unless `<approved>`, the PR's head and the seal are one SHA", merge
        )
        # The head, the title and the body are read together just before the merge:
        # GitHub closes an issue a closing keyword in the description names,
        # whatever the squash message says (Codex on #400).
        self.assertIn("as_app pr view <N> --json headRefOid --jq .headRefOid", merge)
        # Each comparison runs only on a read that succeeded, since an empty file is
        # not an empty title (cubic on #400); both, and the head's read, come before
        # the merge in the order shown (cubic and Codex on #400).
        commands = [
            line.strip()
            for block in re.findall(r"```sh\n(.*?)```", merge_text, re.S)
            for line in block.splitlines()
        ]
        # The seal is read too, not remembered from an earlier step (Claude on #400).
        reads = [
            "as_app api repos/ktogias/gnostoa/issues/<N>/comments --paginate --slurp \\",
            "as_app pr view <N> --json headRefOid --jq .headRefOid",
            "as_app pr view <N> --json title --jq .title > <current-subject> "
            "&& cmp -s <current-subject> <checked-subject>",
            "as_app pr view <N> --json body --jq .body > <current-body> "
            "&& cmp -s <current-body> <checked-body>",
        ]
        for read in reads:
            with self.subTest(read=read):
                self.assertIn(read, commands)
                self.assertLess(commands.index(read), commands.index(line))
        self.assertIn("and both comparisons succeed", merge)
        self.assertIn("Only then does the App merge", merge)
        self.assertIn(
            """select(.user.login == "gnostoa-agent[bot]") | .body """
            """| select(startswith("Exact review candidate: "))""",
            merge,
        )
        self.assertLess(merge.index("Only then does the App merge"), merge.index(line))
        self.assertIn("whatever the squash message says", merge)
        # A squash merge makes a new commit, so after it the PR's recorded head is
        # compared with `<approved>`, and the new commit's tree with that head's
        # (Codex on #400).
        after = runbook[
            runbook.index("9. **After the merge.**") : runbook.index("### Break glass")
        ]
        self.assertNotIn("the merge commit and the head match", after)
        for phrase in (
            "--json headRefOid,mergeCommit --jq .headRefOid",
            "--json headRefOid,mergeCommit --jq .mergeCommit.oid",
            "If the trees differ, stop",
            "the PR's recorded head equals `<approved>`",
            "commits/<merge>",
            "commits/<approved>",
            "--jq .commit.tree.sha",
            "the two trees are one",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, after)
        text = RUNBOOK.read_text(encoding="utf-8")
        for command in re.findall(r"```sh\n(.*?)```", text, re.S):
            joined = " ".join(command.replace("\\\n", " ").split())
            with self.subTest(command=joined[:60]):
                self.assertFalse("--paginate" in joined and "--jq" in joined)

    def test_an_untrusted_title_is_compared_as_data(self) -> None:
        """The pre-merge check writes the title and body it read to files, and step 8
        compares the current ones with them, through pipes and files only: a title's
        shell syntax never runs, an unchanged title passes and an edited one stops
        the merge (Claude and Codex on #400)."""
        text = RUNBOOK.read_text(encoding="utf-8")
        flat = " ".join(text.split())
        rounds = flat[: flat.index("6. **The convergence report.**")]
        lines = [
            line.strip()
            for block in re.findall(r"```sh\n(.*?)```", text, re.S)
            for line in block.splitlines()
            if line.strip().startswith("as_app pr view <N> --json title")
        ]
        write = "as_app pr view <N> --json title --jq .title > <checked-subject>"
        compare = (
            "as_app pr view <N> --json title --jq .title > <current-subject> "
            "&& cmp -s <current-subject> <checked-subject>"
        )
        self.assertEqual([write, compare], lines)
        self.assertIn(write, rounds)
        self.assertIn(
            "as_app pr view <N> --json body --jq .body > <checked-body>", rounds
        )
        title = "Docs`touch PWNED` $(touch PWNED); touch PWNED 'q\" \\$HOME"
        # A failed read, after a failed write, is not a match (cubic on #400).
        for interpreter in _shells():
            for current, expected in (
                (title, 0),
                (title + " Closes #1", 1),
                ("FAIL", 1),
            ):
                with (
                    self.subTest(interpreter=interpreter, current=current),
                    tempfile.TemporaryDirectory() as directory,
                ):
                    root = Path(directory)
                    stub = (
                        "as_app() { "
                        '[ "$TITLE" = FAIL ] && return 1; printf "%s\\n" "$TITLE"; }\n'
                    )
                    run = [
                        line.replace("<N>", "7")
                        .replace("<checked-subject>", str(root / "subject"))
                        .replace("<current-subject>", str(root / "current"))
                        for line in (write, compare)
                    ]
                    checked = "FAIL" if current == "FAIL" else title
                    script = (
                        stub + "TITLE=$CHECKED\n" + run[0] + "\n"
                        "TITLE=$CURRENT\n" + run[1] + "\n"
                    )
                    done = subprocess.run(  # nosec B603  # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-audit.dangerous-subprocess-use-audit
                        [interpreter, "-c", script],
                        capture_output=True,
                        text=True,
                        check=False,
                        timeout=30,
                        cwd=root,
                        env={
                            "PATH": "/usr/bin:/bin",
                            "HOME": str(root),
                            "CHECKED": checked,
                            "CURRENT": current,
                        },
                    )
                    self.assertEqual(expected, done.returncode, done.stderr)
                    self.assertFalse((root / "PWNED").exists())
                    self.assertEqual(
                        "" if checked == "FAIL" else title + "\n",
                        (root / "subject").read_text(encoding="utf-8"),
                    )

    def test_break_glass_reads_the_classic_protection_back_first(self) -> None:
        """Break glass leaves the classic protection as the only layer requiring
        the checks, so the owner reads it back before the merge (Codex on #400)."""
        runbook = " ".join(RUNBOOK.read_text(encoding="utf-8").split())
        procedure = runbook[runbook.index("**How.**") : runbook.index("**After.**")]
        read_back = procedure.find(
            "GET /repos/ktogias/gnostoa/branches/main/protection"
        )
        merge = procedure.find("Merge the exact head")
        # The read-back is a step before the merge, not merely beside it (cubic on
        # #400).
        self.assertNotEqual(-1, read_back)
        self.assertNotEqual(-1, merge)
        self.assertLess(read_back, merge)
        # The owner reads the title, the description and the commits' messages just
        # before the merge, and stops on a closing keyword in any: the squash commit
        # is built from the commits' messages and the title (Codex on #400).
        # The PR is read again last, just before the merge, so the title and the
        # description are the latest read and the commits lie between two reads of
        # one head (Claude on #400).
        phrases = (
            "GET /repos/ktogias/gnostoa/pulls/<N>/commits",
            "and last, just before the merge, reads `GET /repos/ktogias/gnostoa/pulls/<N>` again",
            "stops unless that read's `head.sha` is still `<head>`",
            "stops if the commits' messages, or that read's `title` or `body`, carry a closing keyword",
            "the commits' messages and its title from the PR's title or its one",
        )
        for phrase in phrases:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, procedure)
                self.assertLess(procedure.index(phrase), procedure.index("```sh"))
        self.assertLess(procedure.index(phrases[0]), procedure.index(phrases[1]))
        # A failed mint stops the merge: `gh` would otherwise fall back to the
        # owner's stored login and merge as the owner (Codex on #400).
        self.assertIn("instead of letting `gh` fall back to a stored login", procedure)
        # The command itself, its guards chained in order (cubic on #400).
        # In a subshell, so the token never exists in the interactive shell, an
        # interruption cannot leave it there, and the block's status is the
        # merge's (Codex and CodeAnt on #400).
        # The guarded body, as the two functions have it (CodeAnt, Claude and Codex on
        # #400).
        command = _isolated(
            "$(~/break-glass/break-glass-token.sh)",
            "api -X PUT repos/ktogias/gnostoa/pulls/<N>/merge -f merge_method=squash"
            " -f sha=<head> ' break-glass",
        )
        blocks = [
            " ".join(block.replace("\\\n", " ").split())
            for block in re.findall(
                r"```sh\n(.*?)```", RUNBOOK.read_text(encoding="utf-8"), re.S
            )
        ]
        self.assertIn(command, blocks)
        self.assertIn("never exists in the interactive shell", procedure)
        # The minting script is never copied from the agent host, which may be the
        # compromised one (CodeAnt on #400).
        self.assertIn("never copied from the agent host", procedure)
        self.assertIn("kept offline with the key", runbook)
        # Its trusted source is GitHub's own documentation, step by step (cubic on
        # #400).
        for step in (
            "generating-a-json-web-token-jwt-for-a-github-app",
            "generating-an-installation-access-token-for-a-github-app",
            "GET /repos/ktogias/gnostoa/installation",
            "POST /app/installations/<installation>/access_tokens",
            '"repositories": ["gnostoa"]',
            "`iss` the App ID 5230732",
            # The JWT's algorithm and lifetime, which make it acceptable and short
            # (cubic on #400).
            "RS256",
            "`iat` 60 seconds in the past",
            "`exp` at most ten minutes on",
        ):
            with self.subTest(step=step):
                self.assertIn(step, procedure)
        # Break glass bypasses R-main's approvals only; the classic protection still
        # requires the checks and resolved conversations (Codex on #400).
        bypass = runbook[
            runbook.index("**What it bypasses") : runbook.index(
                "If a required check itself is broken"
            )
        ]
        self.assertNotIn("thread resolution and R-main's checks", bypass)
        self.assertIn("the four checks and resolved conversations", bypass)
        # Where `<head>` comes from (Claude on #400).
        self.assertIn("`<head>` is the head the owner has just reviewed", procedure)
        # The last resort removes one broken check, which the read-back before the
        # merge then expects, rather than restoring it (CodeAnt on #400).
        self.assertIn("Remove only the broken check from it", runbook)
        self.assertIn(
            "except in the last resort, where it must differ from Preconditions by "
            "exactly the check the owner removed",
            procedure,
        )
        # Restoring has a stated target (Claude on #400), and happens whether the
        # merge succeeded or not (CodeAnt on #400).
        self.assertIn("restore it to require the four checks", procedure)
        self.assertIn("whether the merge succeeded or not", runbook)
        # The last resort's restore has the same target (Claude on #400).
        last_resort = runbook[
            runbook.index("The last resort is then the owner") : runbook.index(
                "**How.**"
            )
        ]
        # Everything read back before the change, not only the checks (CodeAnt on
        # #400).
        self.assertIn("Read back the whole protection before changing it", last_resort)
        # The removed check protects every merge, so nothing else merges until it
        # is back, and the window is audited (Claude on #400).
        self.assertIn("hold every other merge until step 4", last_resort)
        # R-main still requires the check of every normal merge, so only another
        # break-glass merge is exposed (Claude on #400).
        self.assertIn("only another break-glass merge could skip it", last_resort)
        self.assertIn("any other merge in that window", last_resort)
        # Restored to the recorded settings, since a read-back is not a body to
        # replay, then compared with the first read-back (Claude on #400).
        # Restored to the incident's own read-back, re-entered since a read-back is
        # not a body to send back; repeated until they match; drift recorded
        # (Claude on #400).
        self.assertIn("re-enter the settings step 1 read back", last_resort)
        self.assertIn("a read-back is not a body to send back", last_resort)
        self.assertIn("until the new read-back equals step 1's", last_resort)
        self.assertIn("record the drift and update Preconditions", last_resort)
        # The routine re-verification reads it back too (Claude on #400).
        verify = runbook[
            runbook.index("### Re-verify the gate") : runbook.index("## Recovery")
        ]
        self.assertIn("branches/main/protection", verify)
        # A read, not a merge attempt: a weakened gate would let the attempt merge
        # (Codex on #400).
        flat_verify = " ".join(verify.split())
        self.assertNotIn("Try to merge an unapproved PR", flat_verify)
        # No merge operation at all, whatever the prose (cubic on #400).
        self.assertIsNone(re.search(r"pr merge|/merge\b|merge_method", flat_verify))
        for phrase in (
            "mergeStateStatus",
            "viewerCanMergeAsAdmin",
            "No merge is attempted",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, flat_verify)

    def test_break_glass_is_named_as_the_exception_and_closed_after(self) -> None:
        """The guarantee names break glass as its one exception (cubic and CodeAnt on
        #400). Its follow-up has a Work Item and a Decision (Greptile on #400); an
        exposed key's installation is suspended first (Codex on #400); a protection
        changed temporarily is restored and read back (CodeAnt on #400)."""
        runbook = " ".join(RUNBOOK.read_text(encoding="utf-8").split())
        decision = " ".join(DECISION.read_text(encoding="utf-8").split())
        for text in (runbook, decision):
            self.assertIn("except through break glass", text)
        for phrase in (
            "the emergency follow-up Work Item and Decision",
            "Suspend the installation of `gnostoa-break-glass`",
            "Suspend the installation of `gnostoa-agent`",
            "Restore the protection",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, runbook)

    def test_the_classic_protection_is_recorded_as_the_owner_read_it(self) -> None:
        """The classic protection's settings, as the owner read them back on
        2026-10-08 (rule 81822439); the App gets 403 there, so they were pending."""
        runbook = " ".join(RUNBOOK.read_text(encoding="utf-8").split())
        record = runbook[
            runbook.index("**Classic branch protection on `main`**") : runbook.index(
                "**Repository merge settings:**"
            )
        ]
        self.assertNotIn("in review of this runbook", record)
        for setting in (
            "rule 81822439",
            "a pull request, with no approvals required",
            "`policy`, `fast`, `regression` and `smoke` from GitHub Actions, on an up-to-date branch",
            "conversations resolved",
            "no bypass, administrators included",
            "no force pushes and no deletions",
        ):
            with self.subTest(setting=setting):
                self.assertIn(setting, record)
        codex = runbook[
            runbook.index("### Codex and the review bots") : runbook.index(
                "### The agent host"
            )
        ]
        self.assertNotIn("in review of this runbook", codex)

    def test_the_pre_merge_check_is_named_with_what_it_checks(self) -> None:
        """The convergence step names the pre-merge check, where it lives, and what
        it checks, so a fresh environment can perform it (Codex on #400)."""
        runbook = " ".join(RUNBOOK.read_text(encoding="utf-8").split())
        for phrase in (
            "`premerge-check.sh`",
            "not yet versioned",
            "the seal names the exact head",
            "every required check",
            "every other check run and status",
            "every review thread",
            "no closing keyword",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, runbook)

    def test_recovery_waits_out_stolen_tokens_and_identities_are_exact(self) -> None:
        """A suspended installation stops its tokens only while suspended, so it
        stays suspended until any token minted before it has expired (Codex on
        #400). The machine user's limit is its collaborator list, not its token
        (Claude on #400). Decision 0110 lists every R-main safeguard (Claude on
        #400)."""
        runbook = " ".join(RUNBOOK.read_text(encoding="utf-8").split())
        recovery = runbook[runbook.index("## Recovery") :]
        self.assertEqual(2, recovery.count("at least an hour after suspending it"))
        # A stolen key or host may already have merged, so `main` is audited back to
        # its last trusted identity before anything is restored (Codex on #400).
        self.assertEqual(
            2,
            recovery.count(
                "audit every merge into `main` since the earliest suspected exposure"
            ),
        )
        # For each merge, the approval, the recorded head and the integrated tree, since
        # a push that keeps the diff keeps the approval (Codex on #400).
        self.assertEqual(
            2,
            " ".join(recovery.split()).count(
                "its `commit_id` the PR's recorded head, and the integrated tree that "
                "head's, as the normal merge's steps 8 and 9 require"
            ),
        )
        # No "last good merge" anchor, which a compromise can postdate (Codex on
        # #400): the audit starts at the earliest suspected exposure, else at the
        # credential's creation, which GitHub records; each merge needs the owner's
        # latest review on it to approve its exact head, since an older approval can
        # stand beside a later request for changes (cubic on #400).
        flat = " ".join(recovery.split())
        for phrase in (
            "since the earliest suspected exposure",
            # Across rotations, since a routine rotation on a compromised host does
            # not end the exposure (Codex on #400).
            "since the earliest credential the compromised host or key could have held, across rotations",
            "the owner's latest review on that PR must be `APPROVED`",
        ):
            with self.subTest(phrase=phrase):
                self.assertEqual(2, flat.count(phrase))
        self.assertNotIn("last trusted identity", flat)
        # A compromised App can change an approved PR's title or description without
        # moving its head, so each audit also checks every merge's effects: the squash
        # commit, the title and description reconstructed from their history, and the
        # issues the merge closed; what cannot be reconstructed is UNKNOWN, never clean
        # (Codex on #400; the owner's bounded correction, 4221436778).
        for phrase in (
            "audit each merge's effects, which none of those comparisons covers",
            "read the squash commit's subject and message, `GET /repos/ktogias/gnostoa/commits/<merge>`, for a closing keyword",
            "GraphQL `userContentEdits` for the description and `RenamedTitleEvent` for the title",
            "list every issue closed since then whose closer, GraphQL `ClosedEvent.closer`, is a pull request or a commit",
            "is recorded as an incident and restored through the follow-up, with the owner's disposition",
            "the merge's audit is `UNKNOWN`, for the owner to dispose, never clean on its SHA and tree alone",
        ):
            with self.subTest(phrase=phrase):
                self.assertEqual(2, flat.count(phrase))
        # Each rotation is kept in the owner's offline record, so an audit can reach
        # back past it (Codex on #400).
        self.assertEqual(
            2, flat.count("as the owner's offline record of rotations shows")
        )
        self.assertEqual(
            2, flat.count("in the owner's offline record of rotations first")
        )
        # The credential's creation date is read before it is revoked, which erases
        # it (Claude on #400).
        self.assertEqual(
            2,
            flat.count(
                "record the compromised credential's creation date before revoking it"
            ),
        )
        # A break-glass merge carries no approval, so it passes against the owner's
        # offline record of it, which no agent identity can edit (Claude on #400).
        self.assertIn("the owner's offline record of each break glass", flat)
        self.assertIn("a collaborator on this repository alone", runbook)
        self.assertIn("account-wide", runbook)
        decision = " ".join(DECISION.read_text(encoding="utf-8").split())
        self.assertIn("unattributed changes", decision)

    def test_the_gate_is_a_registered_guardrail_and_its_target_is_main(self) -> None:
        """The gate's surfaces are owned by a kit-only guardrail, so their removal
        or drift is visible to the policy check (Codex on #400); R-main targets the
        default branch, as the API records it (CodeAnt on #400)."""
        import yaml

        manifest = yaml.safe_load(
            (ROOT / "policy" / "guardrails.yaml").read_text(encoding="utf-8")
        )
        [entry] = [
            g
            for g in manifest["guardrails"]
            if g["id"] == "owner-approved-exact-head-merge"
        ]
        self.assertEqual(["kit"], entry["applies_to"])
        for surface in (
            "AGENTS.md",
            "knowledge/runbooks/operate-the-merge-gate.md",
            f"knowledge/decisions/{DECISION.name}",
            ".github/CODEOWNERS",
        ):
            with self.subTest(surface=surface):
                self.assertIn(surface, entry["implementation"])
        # Every test of this module, so none is added without being registered, and
        # an unrelated test cannot stand in for one (cubic, CodeAnt and Claude on
        # #400).
        own = sorted(
            f"tests/test_merge_gate_record.py::MergeGateRecordTests.{name}"
            for name in dir(MergeGateRecordTests)
            if name.startswith("test_")
        )
        self.assertEqual(own, sorted(entry["tests"]))
        self.assertEqual(len(own), len(entry["tests"]))
        self.assertEqual(
            {"ref_name": {"include": ["~DEFAULT_BRANCH"], "exclude": []}},
            self._r_main()["conditions"],
        )

    def test_phase_1a_states_what_it_does_not_enforce(self) -> None:
        """No provider gate yet compares the approval's `commit_id` with the merged
        head; the procedure does, and Phase 1b's required check will (Codex on
        #400)."""
        for path in (DECISION, RUNBOOK):
            text = " ".join(path.read_text(encoding="utf-8").split())
            with self.subTest(path=path.name):
                self.assertIn(
                    "the approval's `commit_id` against the merged head", text
                )

    def test_the_zero_approval_decisions_are_marked_revised(self) -> None:
        """Decisions 0013 and 0014 set zero required approvals; each now says that
        Decision 0110 revised it, and 0110 names both, so no route reads the old
        rule alone (CodeAnt on #400). The policy file's inherited zero is #401."""
        decisions = ROOT / "knowledge" / "decisions"
        for name, rule in (
            (
                "0013-defer-provider-enforcement-while-private.md",
                "Use zero required approvals",
            ),
            (
                "0014-strengthen-gnostoa-self-governance.md",
                "required formal approvals remain zero",
            ),
        ):
            text = " ".join((decisions / name).read_text(encoding="utf-8").split())
            with self.subTest(decision=name):
                self.assertIn("*Revised by Decision 0110:*", text)
                # Break glass bypasses R-main, so no merge rule says "every merge"
                # (CodeAnt on #400).
                self.assertNotIn("for every merge,", text)
                self.assertLess(
                    text.index(rule), text.index("*Revised by Decision 0110:*")
                )
        revises = " ".join(DECISION.read_text(encoding="utf-8").split())
        revises = revises[revises.index("## What this supersedes or revises") :]
        for phrase in (
            "Decision 0013's zero required approvals",
            "Decision 0014's",
            "#401",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, revises)

    def test_no_record_claims_the_platform_binds_the_exact_head(self) -> None:
        """GitHub requires the owner's approval, but keeps it across a push that
        leaves the diff unchanged, so binding it to the exact head is the merge
        procedure's until Phase 1b; no record says otherwise (cubic on #400)."""
        decisions = ROOT / "knowledge" / "decisions"
        records = {
            path.name: " ".join(path.read_text(encoding="utf-8").split())
            for path in (
                RUNBOOK,
                DECISION,
                decisions / "0013-defer-provider-enforcement-while-private.md",
                decisions / "0014-strengthen-gnostoa-self-governance.md",
            )
        }
        for name, text in records.items():
            for claim in (
                "GitHub enforces it; no agent's discipline is relied on",
                "requires the code owner's approval of the exact head",
                "A later push dismisses the approval",
                "without the owner's approval of the head",
                # A push that keeps the diff may keep the approval (Codex on #400).
                "Every push, and every move of `main`, requires a new approval",
            ):
                with self.subTest(record=name, claim=claim):
                    self.assertNotIn(claim, text)
        self.assertIn(
            "binding it to the exact head is the merge procedure's step until Phase 1b",
            records[RUNBOOK.name],
        )
        # A whole sentence (cubic on #400).
        self.assertIn(
            "Binding the approval to the exact head is the merge procedure's step "
            "until Phase 1b",
            records[DECISION.name],
        )

    def test_0110_specialises_the_neutral_contract_and_defers_phase_1b(self) -> None:
        """The owner's bounded corrections (#400, 6061478624; #398, 6061470364):
        Decision 0110 names its governing neutral contract and says it does not alter
        it; the Phase-1a shell procedures are labelled temporary, with their
        successors; and Phase 1b's reuse contract is recorded, deferred."""
        import yaml

        text = DECISION.read_text(encoding="utf-8")
        front = yaml.safe_load(text.split("---", 2)[1])
        relations = {
            (r["kind"], r["target"]) for r in front["x-project-knowledge"]["relations"]
        }
        for relation in (
            ("governed-by", "/decisions/0006-provider-neutral-change-governance.md"),
            ("implements", "/requirements/reviewed-change-control.md"),
            ("references", "/decisions/0014-strengthen-gnostoa-self-governance.md"),
        ):
            with self.subTest(relation=relation):
                self.assertIn(relation, relations)
        decision = " ".join(text.split())
        self.assertIn(
            "This Decision is a Gnostoa-self/GitHub specialization and does not alter "
            "the provider-neutral public change-governance contract.",
            decision,
        )
        for phrase in (
            "Phase 1b is deferred",
            "`tools/github_rest.py`",
            "Decision 0086",
            "`ci/review_github_current_state.py`",
            "`tools/review_reconcile.py`",
            "#389",
            "#369",
            "the provider-neutral merge-admission verdict",
            "fails closed",
            "#398 (6061470364, 6061573600)",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, decision)
        runbook = " ".join(RUNBOOK.read_text(encoding="utf-8").split())
        for phrase in (
            "Phase-1a operational procedures",
            "not a permanent API, trusted-execution, observation or gate engine",
            "#369, which is not yet integrated",
            "Phase 1b's canonical adapter",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, runbook)

    def test_every_decision_cited_exists(self) -> None:
        """A Decision is cited by number only when it is in the repository; #384's
        unmerged proposal is cited by its PR (Claude on #400)."""
        decisions = {
            path.name[:4] for path in (ROOT / "knowledge" / "decisions").iterdir()
        }
        for path in (RUNBOOK, DECISION):
            for number in re.findall(
                r"Decision (\d{4})", path.read_text(encoding="utf-8")
            ):
                with self.subTest(source=path.name, decision=number):
                    self.assertIn(number, decisions)

    def test_the_decision_and_runbook_link_each_other_and_are_indexed(self) -> None:
        self.assertIn(DECISION.name, RUNBOOK.read_text(encoding="utf-8"))
        self.assertIn(RUNBOOK.name, DECISION.read_text(encoding="utf-8"))
        index = (ROOT / "knowledge" / "index.md").read_text(encoding="utf-8")
        self.assertIn(f"decisions/{DECISION.name}", index)
        self.assertIn(f"runbooks/{RUNBOOK.name}", index)


if __name__ == "__main__":
    unittest.main()
