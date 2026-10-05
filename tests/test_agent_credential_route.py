"""The agent credential check is routed from source (Decision 0101, #362).

The check verifies that the agents' token holds exactly its declared least privilege:
the precondition of the owner's authority channel for MA0. A check an agent is not
routed to is skipped the first time it is not remembered -- the 2026-10-04 incident
on #15 (5977488379) was exactly that. These tests pin the routing: the router names it
before provider writes, the delivery runbook carries its rule, a guardrail binds the
route, the tools, the declaration and the tests, and the Decision is indexed.
"""

from __future__ import annotations

import pathlib
import re
import subprocess  # nosec B404
import tempfile
import unittest

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]
AGENTS = ROOT / "AGENTS.md"
RUNBOOK = ROOT / "knowledge" / "runbooks" / "deliver-bounded-self-hosted-slice.md"
GUARDRAILS = ROOT / "policy" / "guardrails.yaml"
INDEX = ROOT / "knowledge" / "index.md"
DECISION = (
    "decisions/0101-verify-agent-provider-credentials-against-a-least-privilege-"
    "declaration.md"
)
HEADING = "### Agent credential check"
COMMAND = "knowledge credential-check"


def _flat(text: str) -> str:
    return " ".join(text.split())


def _section() -> str:
    text = RUNBOOK.read_text(encoding="utf-8")
    start = text.find(HEADING)
    if start < 0:
        raise AssertionError(f"the runbook has no {HEADING!r} subsection")
    following = re.search(r"^#{2,3} ", text[start + len(HEADING) :], re.MULTILINE)
    end = len(text) if following is None else start + len(HEADING) + following.start()
    return text[start:end]


class AgentCredentialRouteTests(unittest.TestCase):
    """The check is reachable from the router, the runbook and the guardrail policy."""

    def test_router_routes_the_check_before_provider_writes(self) -> None:
        router = _flat(AGENTS.read_text(encoding="utf-8"))
        self.assertIn(COMMAND, router)
        self.assertIn("before the first provider write", router.lower())
        self.assertIn("EXACT", router)
        self.assertIn("policy/agent-credentials.yaml", router)
        self.assertIn(
            "deliver-bounded-self-hosted-slice.md#agent-credential-check", router
        )

    def test_runbook_states_the_rule_for_every_verdict(self) -> None:
        section = _flat(_section())
        for verdict in (
            "EXACT",
            "EXCESS",
            "DEFICIENT",
            "UNVERIFIED",
            "CREDENTIAL_KIND_MISMATCH",
            "LIFETIME_EXCEEDED",
        ):
            with self.subTest(verdict=verdict):
                self.assertIn(verdict, section)
        self.assertIn("no provider write", section)
        # It says what the check is not, so it is never mistaken for the boundary.
        self.assertIn("not the credential boundary", section)
        self.assertIn("browser", section)

    def test_procedure_step_one_runs_the_check(self) -> None:
        text = RUNBOOK.read_text(encoding="utf-8")
        step = re.search(r"^1\. \*\*Orient.*?(?=^2\. )", text, re.MULTILINE | re.DOTALL)
        if step is None:
            self.fail("the runbook's Procedure has no step 1")
        self.assertIn("agent credential check", _flat(step.group(0)).lower())

    def test_guardrail_binds_the_route_tools_declaration_and_tests(self) -> None:
        guardrails = yaml.safe_load(GUARDRAILS.read_text(encoding="utf-8"))[
            "guardrails"
        ]
        guardrail = next(
            (g for g in guardrails if g["id"] == "agent-credential-least-privilege"),
            None,
        )
        if guardrail is None:
            self.fail("no guardrail binds the credential check")
        for path in (
            "AGENTS.md",
            "knowledge/runbooks/deliver-bounded-self-hosted-slice.md",
            f"knowledge/{DECISION}",
            "policy/agent-credentials.yaml",
            "schemas/agent-credentials.schema.json",
            "tools/credential_posture.py",
            "tools/credential_posture_github.py",
            "tools/credential_check.py",
            "tools/cli.py",
            "ci/credential-check",
            # The owners it consumes (#365): a change to one reaches this control.
            "tools/github_rest.py",
            "tools/agent_review_paths.py",
            "tools/schema_validation.py",
            "tools/knowledge_common.py",
        ):
            with self.subTest(implementation=path):
                self.assertIn(path, guardrail["implementation"])
        tests = " ".join(guardrail["tests"])
        for test in (
            "tests/test_credential_posture.py",
            "tests/test_agent_credential_route.py",
            "tests/test_github_rest.py",
            "tests/test_agent_review_paths.py",
            "tests/test_schema_validation.py",
            "tests/test_knowledge_common.py",
            "tests/test_credential_push_binding.py",
            "tests/test_credential_check_wrapper.py",
        ):
            with self.subTest(test=test):
                self.assertIn(test, tests)

    def test_the_decision_and_the_runbook_name_the_same_moment(self) -> None:
        """The Decision said "at the start of a session", the route "before the first
        provider write": two operational requirements (CodeAnt on #364). They now say
        the same."""
        decision = _flat((ROOT / "knowledge" / DECISION).read_text(encoding="utf-8"))
        self.assertIn("before the first provider write of a session", decision.lower())
        self.assertNotIn("at the start of a session", decision.lower())
        self.assertIn(
            "before the first provider write of a session", _flat(_section()).lower()
        )

    def test_the_router_runs_the_gate_from_protected_main(self) -> None:
        """The gate's authority is protected main as the provider reports it: the
        wrapper is retrieved from that exact commit with routing scrubbed and its
        success checked, never piped into a shell (owner decision 2026-10-05)."""
        router = AGENTS.read_text(encoding="utf-8")
        self.assertIn("run_main_credential_check() (", router)
        self.assertIn("branches/main", router)
        # The provider read is pinned to the host the fetch uses: `GH_HOST` must not
        # let another server name the authority (CodeAnt on #364).
        self.assertIn("api --hostname github.com", router)
        # The authority is protected main: the same read that names its commit must
        # show the branch protected, or no wrapper is fetched (CodeAnt on #364).
        self.assertIn("(.protected)", router)
        self.assertIn('[ "${protected}" != true ]', router)
        self.assertIn('show "${main}:ci/credential-check"', router)
        self.assertNotIn(':ci/credential-check" | sh', router)
        helper = router.split("run_main_credential_check() (", 1)[1].split("\n)\n", 1)[
            0
        ]
        # Every git the retrieval runs inherits no environment (Codex on #364): an
        # inherited `GIT_EXEC_PATH` alone would choose the transport the fetch runs.
        self.assertIn('"${env_executable}" -i PATH=', helper)
        for pinned in ("GIT_CONFIG_GLOBAL=/dev/null", "GIT_TERMINAL_PROMPT=0"):
            self.assertIn(pinned, helper)
        retrieval = helper.split("  status=0\n  (", 1)[1].split('> "${wrapper}"', 1)[0]
        logical = retrieval.replace("\\\n", " ").splitlines()
        git_calls = [line for line in logical if '"${git_executable}"' in line]
        self.assertTrue(git_calls)
        for line in git_calls:
            self.assertIn("isolated ", line)
        # The fetch reads none of the checkout's configuration, whose `insteadOf` could
        # redirect it and whose credential helper could run first (CodeAnt on #364):
        # disposable metadata from an empty template, bound to the checkout's object
        # store, from an explicit HTTPS URL with every other transport refused.
        (fetch,) = [line for line in git_calls if "fetch --quiet" in line]
        for isolated in (
            'GIT_DIR="${metadata}/git"',
            'GIT_OBJECT_DIRECTORY="${objects}"',
            '"https://github.com/${repository}.git"',
            "-c protocol.allow=never",
            "-c protocol.https.allow=always",
        ):
            self.assertIn(isolated, fetch)
        self.assertIn('--template="${metadata}/template"', retrieval)
        self.assertNotIn("fetch --quiet origin", helper)
        self.assertIn("run_main_credential_check ktogias/gnostoa", router)

    def test_a_shell_function_never_stands_in_for_an_executable(self) -> None:
        """The helper runs in the agent's own shell, whose functions it inherits:
        `command -v` names a function rather than a path, so a `gh` function could forge
        protected main and a `git` or `mktemp` one could run in place of the trusted
        executable (CodeAnt on #364). Only an absolute path is run. A forged `gh`
        carries the flow past the provider read offline, so each function is reached."""
        router = AGENTS.read_text(encoding="utf-8")
        start = router.index("run_main_credential_check() (")
        helper = router[start : router.index("\n)\n", start) + 3]
        with tempfile.TemporaryDirectory() as scratch:
            marker = pathlib.Path(scratch) / "ran"
            subprocess.run(  # nosec B603 B607
                ["git", "init", "--quiet", scratch], check=True, timeout=30
            )
            for name in ("gh", "git", "mktemp", "sh"):
                with self.subTest(function=name):
                    marker.unlink(missing_ok=True)
                    touch = f'printf x > "{marker}"; ' if name == "gh" else ""
                    functions = f"gh() {{ {touch}echo {'a' * 40}; }}\n"
                    if name != "gh":
                        functions += (
                            f'{name}() {{ printf x > "{marker}"; return 0; }}\n'
                        )
                    completed = subprocess.run(  # nosec B603 B607  # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-audit.dangerous-subprocess-use-audit
                        [
                            "bash",
                            "-c",
                            f"{functions}{helper}\nrun_main_credential_check ktogias/gnostoa",
                        ],
                        cwd=scratch,
                        env={"PATH": "/usr/local/bin:/usr/bin:/bin", "HOME": scratch},
                        capture_output=True,
                        text=True,
                        check=False,
                        timeout=120,
                    )
                    self.assertFalse(marker.exists(), f"a {name} function ran")
                    self.assertEqual(2, completed.returncode, completed.stderr)
                    self.assertRegex(
                        completed.stderr, rf"not a trusted executable path:.*\b{name}\b"
                    )

    def test_the_runbook_states_the_bootstrap_and_the_push_binding(self) -> None:
        section = _flat(_section())
        self.assertIn("protected main", section)
        self.assertIn("bootstrap", section.lower())
        self.assertIn("gh auth setup-git", section)
        self.assertIn("transport:push", section)

    def test_decision_is_indexed(self) -> None:
        self.assertIn(DECISION, INDEX.read_text(encoding="utf-8"))
        self.assertTrue((ROOT / "knowledge" / DECISION).is_file())


if __name__ == "__main__":
    unittest.main()
