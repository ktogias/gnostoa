"""The agent review pipeline's core is provider- and agent-neutral (Decision 0100).

Falsifiers for the lineage table on #353: the core names no provider, agent or CI
system and imports nothing but the standard library and itself; a test-only second
agent and a test-only second provider drive the unchanged core with the same
guarantees; and the GitHub-and-Claude composition keeps every guarantee it had.
"""

from __future__ import annotations

import ast
import json
import os
import pathlib
import re
import shutil
import sys
import tempfile
import unittest
from typing import Any
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
# The neutral core. Adapters (`*_github.py`, `*_claude_code.py`) are deliberately not
# in this list: translating native vocabulary is their job.
CORE = (
    "agent_review_model",
    "agent_review_paths",
    "agent_review_admission",
    "agent_review_context",
    "agent_review_base",
    "agent_review_diff",
    "agent_review_report",
    "agent_review_delivery",
)
# Provider, agent and CI vocabulary that has no place in a neutral core. A word guard,
# not a portability oracle: the second-adapter tests below are the semantic check.
COUPLING = re.compile(
    r"github|gitlab|bitbucket|claude|anthropic|codex|openai|\bgemini\b|"
    r"RUNNER_TEMP|GITHUB_|actions/runs|\[bot\]|workflow_run|author_association",
    re.IGNORECASE,
)


def _core_source(name: str) -> str:
    """Return a core module's source."""
    return (TOOLS / f"{name}.py").read_text(encoding="utf-8")


def _imports(source: str) -> set[str]:
    """Return the top-level module names a source imports."""
    names: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names.add(node.module.split(".")[0])
    return names


class NeutralCoreStructureTests(unittest.TestCase):
    """The core carries no provider, agent or CI vocabulary and no foreign imports."""

    def test_the_core_imports_only_the_standard_library_and_itself(self) -> None:
        """A core that imports an adapter, or a third-party client, is not a core."""
        allowed = set(sys.stdlib_module_names) | {"tools"}
        for name in CORE:
            with self.subTest(module=name):
                imported = _imports(_core_source(name))
                self.assertEqual(set(), imported - allowed)
                tools_imports = {
                    node.module
                    for node in ast.walk(ast.parse(_core_source(name)))
                    if isinstance(node, ast.ImportFrom)
                    and node.module
                    and node.module.startswith("tools.")
                }
                for module in tools_imports:
                    self.assertIn(module.removeprefix("tools."), CORE)

    def test_the_core_names_no_provider_agent_or_ci_system(self) -> None:
        """Provider, agent and CI vocabulary belongs to adapters."""
        for name in CORE:
            with self.subTest(module=name):
                self.assertEqual([], COUPLING.findall(_core_source(name)))


def _codex_like_report(stream: str) -> Any:
    """A test-only second agent adapter: a JSONL event stream, not an envelope.

    Materially different from the Claude Code execution file: one JSON object per
    line, the answer in `item.completed` events of type `agent_message`, and
    completion signalled by a `turn.completed` event rather than a result subtype.
    """
    from tools import agent_review_report as report

    texts: list[str] = []
    finished = False
    for line in stream.splitlines():
        event = json.loads(line)
        if event.get("type") == "item.completed":
            item = event.get("item") or {}
            if item.get("type") == "agent_message":
                texts.append(str(item.get("text", "")))
        elif event.get("type") == "turn.completed":
            finished = True
        elif event.get("type") == "turn.failed":
            finished = False
    if not texts:
        return report.AgentReport("unavailable", "", False)
    return report.AgentReport(
        "complete" if finished else "incomplete", texts[-1], False
    )


class _ForgeLikeSink:
    """A test-only second provider's comment sink, with its own failure modes.

    Notes are keyed by opaque string ids, authored by a service account named in the
    provider's own vocabulary, and a create may land and still time out.
    """

    def __init__(self, fates: list[str]) -> None:
        self.fates = fates
        self.notes: list[dict[str, str]] = []

    def create(self, body: str) -> str:
        """Create a note, failing as ``fates`` scripts."""
        from tools import agent_review_delivery as delivery

        fate = self.fates.pop(0)
        if fate == "unreached":
            raise delivery.DeliveryUncertain("connection refused before sending")
        note = {
            "id": f"note-{len(self.notes)}",
            "author": "service:review",
            "body": body,
        }
        self.notes.append(note)
        if fate == "lost":
            raise delivery.DeliveryUncertain("the answer never arrived")
        return note["id"]

    def find(self, marker: str) -> str | None:
        """Return the id of this sink's own note carrying ``marker``, if any."""
        for note in self.notes:
            if note["author"] == "service:review" and note["body"].startswith(marker):
                return note["id"]
        return None


class SecondAdapterTests(unittest.TestCase):
    """The unchanged core serves an agent and a provider it was never written for."""

    def test_a_second_agent_drives_the_unchanged_publisher_and_poster(self) -> None:
        """Another agent's output reaches a comment through the same handoff and the
        same rendering, with every guarantee intact."""
        from tools import agent_review_delivery as delivery
        from tools import agent_review_report as report

        stream = "\n".join(
            json.dumps(event)
            for event in (
                {"type": "item.completed", "item": {"type": "reasoning", "text": "x"}},
                {
                    "type": "item.completed",
                    "item": {
                        "type": "agent_message",
                        "text": "Finding: see a.py:3. cc @someone\n```\nfence\n```",
                    },
                },
                {"type": "turn.completed"},
            )
        )
        produced = _codex_like_report(stream)
        with tempfile.TemporaryDirectory() as scratch:
            handoff = pathlib.Path(scratch) / "handoff"
            report.write_handoff(produced, handoff)
            received = report.read_handoff(handoff)
        self.assertEqual(produced, received)
        body = delivery.render_comment(
            received,
            reviewer="Codex",
            provenance="Run: https://ci.example/runs/7 · Reviewed revision: `abc`",
            secret_patterns=(),
        )
        self.assertIn("### Codex review", body)
        self.assertIn("Finding: see a.py:3.", body)
        self.assertNotIn("@someone", body)
        self.assertIn("\uff20someone", body)
        self.assertTrue(body.count("````") >= 2)

    def test_a_second_provider_sink_gets_exactly_one_comment(self) -> None:
        """Post-once is the core's: a sink in another provider's vocabulary, losing a
        create's answer, still ends with one note, and the marker is the core's."""
        from tools import agent_review_delivery as delivery

        marker = delivery.delivery_marker("forge-run-42.1")
        self.assertRegex(marker, r"\A<!-- gnostoa:agent-review:forge-run-42\.1 -->\Z")
        for fates in (["lost"], ["unreached", "ok"]):
            with self.subTest(fates=fates):
                sink = _ForgeLikeSink(list(fates))
                posted = delivery.post_once(
                    sink, f"{marker}\nbody", marker, pause=lambda _seconds: None
                )
                self.assertEqual(1, len(sink.notes))
                self.assertEqual(sink.notes[0]["id"], posted)


# A placeholder for the job's token, built at runtime so no scanner reads a literal
# credential here (Codacy, Bandit B105).
_NOT_A_CREDENTIAL = "-".join(("not", "a", "credential"))
_FORGE_ORIGIN = ".forge/pipelines/mention.yml"
_FORGE_REPOSITORY = "group/sub/project"
_HEAD = "a" * 40
_BASE = "b" * 40
_REVISION = "c" * 40


class _ForgeLikeRequests:
    """A test-only second provider's request source, in materially different shapes.

    Notes with string ids rather than numbers; change requests called merge requests,
    with "!"-prefixed ids; a role vocabulary rather than associations; the author
    nested as `author.username`; a nested repository path. It translates them into
    the core's vocabulary and decides nothing itself.
    """

    def __init__(self, notes: dict[str, Any], merges: dict[str, Any]) -> None:
        from tools import agent_review_model as model

        self.provider = model.Provider("forge", "test-forge")
        self.notes = notes
        self.merges = merges

    def read_request(self, event: str, pointer: dict[str, Any]) -> Any:
        """Re-read the note the pointer names."""
        from tools import agent_review_admission as admission
        from tools import agent_review_model as model

        if event != "note":
            raise admission.Refused(f"event {event!r} is not an admitted trigger")
        note = self.notes[pointer["note"]]
        target = note["noteable"]
        change = (
            model.Ref("merge_request", target["iid"])
            if target["type"] == "MergeRequest"
            else None
        )
        return admission.Request(
            author=note["author"]["username"],
            association=note["author"]["role"],
            mention_text=note["text"],
            item=model.Ref("work_item", target["iid"]),
            change_request=change,
            occurred_at=note["at"],
            request_text=note["text"],
            title=target["title"],
            body=target["description"],
            item_association=target["author_role"],
        )

    def revisions(self, change_request: Any) -> Any:
        """Read a merge request's live revisions."""
        from tools import agent_review_admission as admission

        merge = self.merges[change_request.id]
        return admission.Revisions(
            head_repository=merge["source_project"],
            head_commit=merge["sha"],
            base_commit=merge["target_sha"],
        )


def _forge_case(
    *,
    text: str = "@reviewer please look",
    role: str = "maintainer",
    item_role: str = "maintainer",
    on_merge: bool = True,
    source_project: str = _FORGE_REPOSITORY,
    at: str = "2026-10-03T10:00:00Z",
    digest_of: str | None = None,
    head: str = _HEAD,
) -> tuple[Any, dict[str, Any]]:
    """Return a forge-like source and the pointer a relay would hand over."""
    from tools import agent_review_admission as admission

    note = {
        "author": {"username": "ana", "role": role},
        "text": text,
        "at": at,
        "noteable": {
            "type": "MergeRequest" if on_merge else "WorkItem",
            "iid": "!12",
            "title": "Tighten the parser",
            "description": "Details of the change.",
            "author_role": item_role,
        },
    }
    merge = {"source_project": source_project, "sha": head, "target_sha": _BASE}
    source = _ForgeLikeRequests({"n-7f3a": note}, {"!12": merge})
    pointer = {
        "event_name": "note",
        "note": "n-7f3a",
        "request_sha256": admission.request_sha256(
            text if digest_of is None else digest_of
        ),
    }
    return source, pointer


def _forge_rules() -> Any:
    """The second provider's configuration: its own token, roles, origin and event."""
    from tools import agent_review_admission as admission

    return admission.Rules(
        mention_tokens=("@reviewer",),
        trusted=("owner", "maintainer"),
        origin=_FORGE_ORIGIN,
        events=("note",),
    )


def _forge_trigger(changes: dict[str, str] | None = None) -> Any:
    """What the second provider recorded about the triggering run, with ``changes``."""
    from tools import agent_review_admission as admission

    fields = {
        "event": "note",
        "origin": _FORGE_ORIGIN,
        "actor": "ana",
        "created_at": "2026-10-03T10:00:05Z",
        "revision": _REVISION,
    }
    fields.update(changes or {})
    return admission.Trigger(**fields)


class SecondProviderAdmissionTests(unittest.TestCase):
    """The unchanged admission core decides a second provider's request.

    Every rule is exercised through the forge-like source above, whose shapes differ
    from the first provider's in every field the rules read. The same request is
    admitted or refused for the same reason as on the first provider.
    """

    def test_a_trusted_unedited_timely_mention_is_admitted(self) -> None:
        """Admitted, with the provider's own subject vocabulary passed through."""
        from tools import agent_review_admission as admission
        from tools import agent_review_model as model

        source, pointer = _forge_case()
        admitted = admission.admit(
            source, _FORGE_REPOSITORY, pointer, _forge_trigger(), _forge_rules()
        )
        self.assertEqual(
            model.ReviewSubject(
                provider=model.Provider("forge", "test-forge"),
                repository=_FORGE_REPOSITORY,
                item=model.Ref("work_item", "!12"),
                change_request=model.Ref("merge_request", "!12"),
                head_commit=_HEAD,
                base_commit=_BASE,
            ),
            admitted.subject,
        )
        self.assertEqual(
            {
                "request": "@reviewer please look",
                "title": "Tighten the parser",
                "item": "Details of the change.",
            },
            admitted.forwarded,
        )

    def test_an_item_without_a_change_request_is_reviewed_at_the_protected_revision(
        self,
    ) -> None:
        """Both revisions are the run's own, equal, as on the first provider."""
        from tools import agent_review_admission as admission

        source, pointer = _forge_case(on_merge=False)
        admitted = admission.admit(
            source, _FORGE_REPOSITORY, pointer, _forge_trigger(), _forge_rules()
        )
        self.assertIsNone(admitted.subject.change_request)
        self.assertEqual(
            (_REVISION, _REVISION),
            (admitted.subject.head_commit, admitted.subject.base_commit),
        )
        with self.assertRaisesRegex(admission.Refused, "protected revision"):
            admission.admit(
                source,
                _FORGE_REPOSITORY,
                pointer,
                _forge_trigger({"revision": "main"}),
                _forge_rules(),
            )

    def test_every_refusal_holds_for_the_second_provider(self) -> None:
        """Each rule refuses the second provider's request for the same reason."""
        from tools import agent_review_admission as admission

        cases = {
            "an untrusted role": (_forge_case(role="guest"), {}, "not admitted"),
            "no mention": (_forge_case(text="please look"), {}, "carry the mention"),
            "an edited request": (
                _forge_case(digest_of="@reviewer earlier text"),
                {},
                "edited after",
            ),
            "a fork-controlled head": (
                _forge_case(source_project="someone/fork"),
                {},
                "fork-controlled head",
            ),
            "a head that is not an exact commit": (
                _forge_case(head="main"),
                {},
                "not an exact SHA",
            ),
            "a stale occurrence": (
                _forge_case(at="2026-10-02T10:00:00Z"),
                {},
                "not the occurrence",
            ),
            "another origin": (
                _forge_case(),
                {"origin": ".forge/pipelines/other.yml"},
                "not the trigger",
            ),
            "another event": (_forge_case(), {"event": "push"}, "not an admitted"),
            "another requester": (_forge_case(), {"actor": "bo"}, "triggered by 'bo'"),
        }
        for name, ((source, pointer), trigger, reason) in cases.items():
            with (
                self.subTest(case=name),
                self.assertRaisesRegex(admission.Refused, reason),
            ):
                admission.admit(
                    source,
                    _FORGE_REPOSITORY,
                    pointer,
                    _forge_trigger(trigger),
                    _forge_rules(),
                )

    def test_an_untrusted_item_authors_text_is_withheld(self) -> None:
        """The requester is trusted; the item's author is not, so its text is not
        forwarded, and the withholding is stated rather than silent."""
        from tools import agent_review_admission as admission

        source, pointer = _forge_case(item_role="guest")
        admitted = admission.admit(
            source, _FORGE_REPOSITORY, pointer, _forge_trigger(), _forge_rules()
        )
        self.assertEqual("@reviewer please look", admitted.forwarded["request"])
        for field in ("title", "item"):
            with self.subTest(field=field):
                self.assertIn("withheld", admitted.forwarded[field])
                self.assertNotIn("parser", admitted.forwarded[field])
                self.assertNotIn("Details", admitted.forwarded[field])


class _ForgeLikeChanges:
    """A test-only second provider's change source, in its own native shapes.

    Its comparison counts commits as `commit_count`, its commits carry `id` and
    `title`, and its diff refusal is its own error: it translates each into the core's
    vocabulary and decides nothing itself.
    """

    def __init__(
        self,
        native: dict[str, Any],
        commits: list[dict[str, str]],
        diff: bytes | None,
    ) -> None:
        self.native = native
        self.native_commits = commits
        self.diff = diff

    def comparison(self) -> bytes:
        """Translate the native comparison into the document the collector reads."""
        return json.dumps(
            {"total_commits": self.native["commit_count"], "files": []}
        ).encode("utf-8")

    def commits(self) -> list[Any]:
        """Translate native commits: an `id` and a `title`."""
        from tools import agent_review_context as context

        return [
            context.Commit(item["id"][:9], item["title"])
            for item in self.native_commits
        ]

    def unified_diff(self) -> bytes:
        """Return the diff, or the core's refusal for the forge's own."""
        from tools import agent_review_context as context

        if self.diff is None:
            raise context.DiffRefused("the forge declined to render the diff")
        return self.diff


def _forge_collector(state: int, *, logged: int = 1, listed: bool = False) -> Any:
    """A collector that writes what the real one writes, then exits ``state``."""

    def collect(target: pathlib.Path) -> int:
        if state == 1:
            return 1
        (target / "commits.log").write_text(
            "".join(f"abcdef12{n} subject\n" for n in range(logged)), encoding="utf-8"
        )
        (target / "diff.stat").write_text(
            " one.py | 2 +-\n" if listed else "", encoding="utf-8"
        )
        (target / "no-patch.txt").write_text("", encoding="utf-8")
        (target / "assembled.diff").write_text(
            "--- a/one.py\n+++ b/one.py\n" if listed else "", encoding="utf-8"
        )
        (target / "base").mkdir(exist_ok=True)
        (target / "base.manifest").write_text(
            "Written: 0. Unavailable: 0.\n", encoding="utf-8"
        )
        return state

    return collect


class SecondProviderContextTests(unittest.TestCase):
    """The unchanged context core assembles a second provider's change."""

    @staticmethod
    def _assemble(
        source: Any, collect: Any, chunked: list[pathlib.Path]
    ) -> tuple[pathlib.Path, str]:
        """Assemble into a fresh context; return it and how far collection got."""
        from tools import agent_review_context as context

        scratch = pathlib.Path(tempfile.mkdtemp())
        request = scratch / "request-in"
        request.mkdir()
        (request / "request").write_text("please review\n", encoding="utf-8")
        target = scratch / "context"
        context.prepare(target, request)
        state = context.assemble(
            target,
            source,
            collect=collect,
            chunk=chunked.append,
            vocabulary=context.Vocabulary(change_request="merge request"),
        )
        return target, state

    def test_an_empty_change_is_named_in_the_providers_own_words(self) -> None:
        """No refusal, a comparison that was read, an empty list: "No changes"."""
        source = _ForgeLikeChanges(
            {"commit_count": 1}, [{"id": "f" * 40, "title": "t"}], b""
        )
        chunked: list[pathlib.Path] = []
        target, state = self._assemble(source, _forge_collector(0), chunked)
        self.addCleanup(shutil.rmtree, target.parent, True)
        self.assertEqual("collected", state)
        self.assertEqual(
            "No changes between base and head for this merge request.\n",
            (target / "diff.patch").read_text(encoding="utf-8"),
        )
        self.assertEqual([], chunked)
        self.assertEqual(
            "please review\n", (target / "request" / "request").read_text()
        )
        for spent in ("diff.full", "comparison.json"):
            with self.subTest(spent=spent):
                self.assertFalse((target / spent).exists())

    def test_the_forges_refusal_reaches_the_per_file_fallback(self) -> None:
        """Only the provider's refusal is lossy, and the fallback says what it lacks."""
        source = _ForgeLikeChanges(
            {"commit_count": 1}, [{"id": "f" * 40, "title": "t"}], None
        )
        chunked: list[pathlib.Path] = []
        target, _ = self._assemble(source, _forge_collector(0, listed=True), chunked)
        self.addCleanup(shutil.rmtree, target.parent, True)
        notice = (target / "patches-source").read_text(encoding="utf-8")
        self.assertIn("refused the unified diff", notice)
        self.assertIn("file modes", notice)
        self.assertEqual([target], chunked)

    def test_a_failed_collection_keeps_the_diff_and_says_so(self) -> None:
        """The collector's failure is a degraded context, never an absent one."""
        source = _ForgeLikeChanges(
            {"commit_count": 3}, [{"id": "f" * 40, "title": "t"}], b"+x\n"
        )
        chunked: list[pathlib.Path] = []
        target, state = self._assemble(source, _forge_collector(1), chunked)
        self.addCleanup(shutil.rmtree, target.parent, True)
        self.assertEqual("failed", state)
        self.assertIn(
            "provider-error base-context",
            (target / "base.manifest").read_text(encoding="utf-8"),
        )
        log = (target / "commits.log").read_text(encoding="utf-8")
        self.assertIn("commit log unavailable", log)
        self.assertNotIn("provider listed", log)
        self.assertEqual([target], chunked)

    def test_a_capped_commit_list_says_so(self) -> None:
        """The second provider's count, in its own field, still bounds the log."""
        source = _ForgeLikeChanges(
            {"commit_count": 5}, [{"id": "f" * 40, "title": "t"}] * 2, b"+x\n"
        )
        target, _ = self._assemble(
            source, _forge_collector(0, logged=2, listed=True), []
        )
        self.addCleanup(shutil.rmtree, target.parent, True)
        self.assertIn(
            "[provider listed 2 of 5 commits]",
            (target / "commits.log").read_text(encoding="utf-8"),
        )

    def test_a_comparison_without_a_count_says_the_log_may_be_short(self) -> None:
        """A missing count was read as zero, so a log of unknown completeness passed as
        complete (CodeAnt on #353). It is stated instead."""
        source = _ForgeLikeChanges(
            {"commit_count": None}, [{"id": "f" * 40, "title": "t"}], b"+x\n"
        )
        target, _ = self._assemble(source, _forge_collector(0, listed=True), [])
        self.addCleanup(shutil.rmtree, target.parent, True)
        log = (target / "commits.log").read_text(encoding="utf-8")
        self.assertIn("gave no commit count", log)
        self.assertNotIn("provider listed", log)

    def test_a_comparison_that_is_not_one_ends_the_assembly(self) -> None:
        """Refusal is the default for what the core cannot establish."""
        from tools import agent_review_context as context

        for body in (b"{not json", b"[]", b'{"total_commits": "5"}'):
            with self.subTest(body=body), self.assertRaises(context.Unavailable):
                context.total_commits(body)


class ThinContextEntrypointTests(unittest.TestCase):
    """The context entrypoint composes; the workflow step runs it and nothing else."""

    def test_the_step_runs_the_entrypoint_alone(self) -> None:
        """The inline shell held the context's rules; they are the core's now."""
        import yaml

        workflow = yaml.safe_load(
            (ROOT / ".github" / "workflows" / "claude.yml").read_text(encoding="utf-8")
        )
        runs = [
            str(step["run"]).strip()
            for step in workflow["jobs"]["claude"]["steps"]
            if step.get("name") == "Collect review context"
        ]
        self.assertEqual(["python3 .github/review-context/collect_context.py"], runs)
        entrypoint = ROOT / ".github" / "review-context" / "collect_context.py"
        source = entrypoint.read_text(encoding="utf-8")
        self.assertIn("agent_review_context", source)
        self.assertNotIn("shell=True", source)


class _ForgeLikeBase:
    """A test-only second provider's base source, in its own native shapes.

    Its tree is a mapping of paths to bytes, with kinds of its own: `link` for a
    symbolic link, `tree` for a directory. Its listings cap at a size of its own, and
    a path it does not hold is answered with its own absence. It translates each into
    the core's vocabulary and decides nothing itself.
    """

    def __init__(
        self,
        tree: dict[str, bytes],
        *,
        kinds: dict[str, str] | None = None,
        tampered: dict[str, bytes] | None = None,
        listing_cap: int = 50,
        sizeless: frozenset[str] = frozenset(),
        malformed: frozenset[str] = frozenset(),
    ) -> None:
        self.tree = tree
        self.kinds = kinds or {}
        self.tampered = tampered or {}
        self.listing_cap = listing_cap
        self.sizeless = sizeless
        self.malformed = malformed
        self.requests: list[str] = []

    def listing(self, directory: str, needed: set[str], _deadline: float) -> Any:
        """Return the base revision's records for ``needed`` names in ``directory``."""
        from tools import agent_review_base as base

        self.requests.append(f"list {directory}")
        if directory in self.malformed:
            return base.Listing(records=(), total=0, malformed=True)
        native = {"link": "symlink", "tree": "dir", "blob": "file"}
        here = {
            path.rsplit("/", 1)[-1]: data
            for path, data in self.tree.items()
            if (path.rsplit("/", 1)[0] if "/" in path else "") == directory
        }
        records = tuple(
            base.BaseRecord(
                name=name,
                kind=native[self.kinds.get(name, "blob")],
                size=None if name in self.sizeless else len(data),
                blob=base.blob_id(data),
            )
            for name, data in here.items()
            if name in needed
        )
        return base.Listing(records=records, total=len(here), malformed=False)

    def contents(self, path: str, _deadline: float) -> Any:
        """Return the base revision's bytes for ``path``, as the forge serves them."""
        from tools import agent_review_base as base

        self.requests.append(f"read {path}")
        if path not in self.tree:
            return base.Contents(data=None, reason="", found=False)
        return base.Contents(
            data=self.tampered.get(path, self.tree[path]), reason="", found=True
        )


def _forge_changes(
    *entries: tuple[str, str, str | None], hunkless: frozenset[str] = frozenset()
) -> Any:
    """A comparison in the core's vocabulary, as a forge adapter would translate it."""
    from tools import agent_review_base as base

    files = [
        base.ChangedFile(
            path=path,
            status=status,
            previous_path=previous,
            patch=None if path in hunkless else "@@ -1 +1 @@\n-a\n+b",
            additions=1,
            deletions=1,
            blob="f" * 40,
        )
        for path, status, previous in entries
    ]
    return base.Comparison(
        files=files,
        delivered=len(files),
        merge_base="c" * 40,
        notices=[],
        refused=[],
        listed=True,
    )


def _collect_base(
    case: unittest.TestCase, source: Any, comparison: Any, **bounds: Any
) -> tuple[pathlib.Path, str, int]:
    """Collect into a fresh context; return it, its manifest and the count written."""
    from tools import agent_review_base as base

    context = pathlib.Path(tempfile.mkdtemp())
    case.addCleanup(shutil.rmtree, context, True)
    written, _, _ = base.collect(
        context,
        comparison,
        source,
        budget=bounds.get("budget", 1 << 20),
        file_cap=bounds.get("file_cap", 300),
        deadline_seconds=bounds.get("deadline_seconds", 60),
        # The reader's own line budget, which its adapter declares.
        line_cap=bounds.get("line_cap", 1900),
    )
    manifest = (context / "base.manifest").read_text(encoding="utf-8")
    return context, manifest, written


class SecondProviderBaseTests(unittest.TestCase):
    """The unchanged collection core gathers a second provider's base revision."""

    def _collect(
        self, source: Any, comparison: Any, **bounds: Any
    ) -> tuple[pathlib.Path, str, int]:
        """Collect into a fresh context; return it, its manifest and the count."""
        return _collect_base(self, source, comparison, **bounds)

    def test_the_exact_base_bytes_are_written_and_a_rename_read_from_its_source(
        self,
    ) -> None:
        """Written under its new name, read from where the base holds it."""
        source = _ForgeLikeBase({"src/a.py": b"before\n", "old.py": b"moved\n"})
        context, manifest, written = self._collect(
            source,
            _forge_changes(
                ("src/a.py", "modified", None),
                ("new.py", "renamed", "old.py"),
                ("added.py", "added", None),
            ),
        )
        self.assertEqual(2, written)
        self.assertEqual(b"before\n", (context / "base" / "src" / "a.py").read_bytes())
        self.assertEqual(b"moved\n", (context / "base" / "new.py").read_bytes())
        self.assertIn("read old.py", source.requests)
        self.assertIn("renamed old.py -> new.py", manifest)
        self.assertIn("added-by-candidate added.py", manifest)

    def test_every_gap_is_named_for_the_second_provider(self) -> None:
        """Each refusal names the path and the reason, in the core's own labels."""
        tree = {
            "bad.py": b"real\n",
            "link": b"target\n",
            "big.bin": b"x" * 64,
        }
        source = _ForgeLikeBase(
            tree, kinds={"link": "link"}, tampered={"bad.py": b"forged\n"}
        )
        _, manifest, written = self._collect(
            source,
            _forge_changes(
                ("bad.py", "modified", None),
                ("link", "modified", None),
                ("big.bin", "modified", None),
                ("gone.py", "modified", None),
            ),
            budget=32,
        )
        self.assertEqual(0, written)
        for line in (
            "blob-mismatch bad.py",
            "not-a-plain-file link",
            "over-budget big.bin",
            "provider-error gone.py",
        ):
            with self.subTest(line=line):
                self.assertIn(line, manifest)

    def test_a_listing_at_its_cap_and_a_spent_deadline_are_stated(self) -> None:
        """The second provider's own cap, and the collection's own deadline."""
        crowded = {f"f{n}.py": b"x" for n in range(3)}
        _, manifest, _ = self._collect(
            _ForgeLikeBase(crowded, listing_cap=3),
            _forge_changes(("missing.py", "modified", None)),
        )
        self.assertIn("listing-at-cap missing.py", manifest)
        _, manifest, written = self._collect(
            _ForgeLikeBase({"a.py": b"x"}),
            _forge_changes(("a.py", "modified", None)),
            deadline_seconds=0,
        )
        self.assertEqual(0, written)
        self.assertIn("deadline-reached a.py", manifest)


class BaseCollectionRuleTests(unittest.TestCase):
    """Rules the stage-4b mutation pass found no test pinning, each now pinned."""

    def _collect(
        self, source: Any, comparison: Any, **bounds: Any
    ) -> tuple[pathlib.Path, str, int]:
        """Collect into a fresh context; return it, its manifest and the count."""
        return _collect_base(self, source, comparison, **bounds)

    def test_bytes_over_the_budget_are_refused_without_a_declared_size(self) -> None:
        """The declared size is checked first; a listing without one is backstopped
        by the bytes themselves."""
        source = _ForgeLikeBase({"big.bin": b"x" * 64}, sizeless=frozenset({"big.bin"}))
        _, manifest, written = self._collect(
            source, _forge_changes(("big.bin", "modified", None)), budget=32
        )
        self.assertEqual(0, written)
        self.assertIn("over-budget big.bin", manifest)
        self.assertIn("read big.bin", source.requests)

    def test_a_malformed_listing_is_the_providers_error_not_an_absence(self) -> None:
        """The collection never got to look, so the gap is named as that."""
        _, manifest, _ = self._collect(
            _ForgeLikeBase({"src/a.py": b"x"}, malformed=frozenset({"src"})),
            _forge_changes(("src/a.py", "modified", None)),
        )
        self.assertIn(
            "provider-error src/a.py: directory listing was not an array", manifest
        )

    def test_a_change_with_hunks_is_collected_before_one_without(self) -> None:
        """A large binary listed first cannot spend the budget a textual change needs."""
        source = _ForgeLikeBase({"big.bin": b"x" * 64, "small.py": b"y" * 8})
        context, manifest, written = self._collect(
            source,
            _forge_changes(
                ("big.bin", "modified", None),
                ("small.py", "modified", None),
                hunkless=frozenset({"big.bin"}),
            ),
            budget=64,
        )
        self.assertEqual(1, written)
        self.assertTrue((context / "base" / "small.py").is_file())
        self.assertIn("over-budget big.bin", manifest)

    def test_bytes_are_staged_outside_the_directory_they_go_to(self) -> None:
        """No name in base/ can be told apart from a staging file, so none is staged
        there: an interrupted write leaves nothing among the files."""
        from tools import agent_review_base as base

        staged: list[pathlib.Path] = []

        def writer(path: pathlib.Path, content: bytes) -> None:
            staged.append(path)
            path.write_bytes(content)

        with tempfile.TemporaryDirectory() as scratch:
            target = pathlib.Path(scratch) / "base"
            target.mkdir()
            staging = pathlib.Path(scratch) / ".base-staging"
            base.write_exact(target / "x", b"bytes", writer, staging=staging)
            self.assertEqual([staging], [path.parent for path in staged])
            self.assertEqual(b"bytes", (target / "x").read_bytes())


class ThinCollectorEntrypointTests(unittest.TestCase):
    """The base collector's entrypoint composes; the rules are the core's."""

    def test_the_entrypoint_defines_no_collection_rule(self) -> None:
        """A rule defined in the entrypoint is a rule a second provider cannot use."""
        entrypoint = ROOT / ".github" / "review-context" / "build_review_context.py"
        tree = ast.parse(entrypoint.read_text(encoding="utf-8"))
        defined = {
            node.name
            for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.ClassDef))
        }
        rules = {
            "_visit",
            "_base_record",
            "_fetch_and_write",
            "_content_gap",
            "_manifest_lines",
            "hunkless_label",
            "write_summaries",
            "write_assembled",
            "quote_path",
            "write_exact",
            "usable_files",
            "decoded_file",
            "reduce_listing",
        }
        self.assertEqual(set(), defined & rules)


class SecondReaderDiffTests(unittest.TestCase):
    """The unchanged diff core serves a reader with another line budget."""

    def test_a_second_readers_budget_bounds_every_line(self) -> None:
        """The cap is the reader's, supplied by its adapter: another agent's, here 80
        bytes, wraps and is disclosed at 80, and no byte is lost."""
        from tools import agent_review_diff as diff
        from tools import agent_review_model as model

        record = b"+" + b"x" * 200
        with tempfile.TemporaryDirectory() as scratch:
            context = pathlib.Path(scratch)
            (context / "diff.full").write_bytes(
                b"diff --git a/a b/a\n" + record + b"\n"
            )
            parts = diff.split_diff(context, 4096, line_cap=80)
            self.assertEqual(1, parts)
            written = (context / "patches" / "part-0001").read_bytes()
            self.assertTrue(all(len(line) <= 80 for line in written.split(b"\n")))
            self.assertEqual(
                record,
                b"".join(
                    line.removeprefix(model.CONTINUATION) if n else line
                    for n, line in enumerate(written.split(b"\n")[1:-1])
                ),
            )
            readme = (context / "patches" / "README").read_text(encoding="utf-8")
            self.assertIn("exceeded 80 bytes", readme)


class DiffDisclosureTests(unittest.TestCase):
    """Rules the stage-4c mutation pass found no test pinning, each now pinned."""

    def test_doubled_backslashes_are_disclosed_without_any_separator(self) -> None:
        """Invalid UTF-8 alone takes the escaping path, which doubles every backslash:
        that rewrite is explained even when no separator was escaped."""
        from tools import agent_review_diff as diff

        with tempfile.TemporaryDirectory() as scratch:
            context = pathlib.Path(scratch)
            (context / "diff.full").write_bytes(b"+a\\b \xff\n")
            diff.split_diff(context, 4096, line_cap=1900)
            readme = (context / "patches" / "README").read_text(encoding="utf-8")
        self.assertIn("1 backslash(es) were doubled", readme)
        self.assertIn("not valid UTF-8", readme)

    def test_a_diff_needing_more_parts_than_the_naming_allows_is_refused(self) -> None:
        """Part names hold four digits; a diff needing more is refused rather than
        written under names that would no longer sort in order."""
        from tools import agent_review_diff as diff

        with tempfile.TemporaryDirectory() as scratch:
            context = pathlib.Path(scratch)
            (context / "diff.full").write_bytes(b"x\n" * 10_000)
            with self.assertRaisesRegex(
                ValueError, "more parts than the naming allows"
            ):
                diff.split_diff(context, 2, line_cap=1900)


class ThinChunkerEntrypointTests(unittest.TestCase):
    """The chunker's entrypoint binds the core to the reader's budget; no more."""

    def test_the_entrypoint_defines_no_chunking_rule(self) -> None:
        """A rule defined in the entrypoint is one a second agent cannot use."""
        entrypoint = ROOT / ".github" / "review-context" / "chunk_diff.py"
        tree = ast.parse(entrypoint.read_text(encoding="utf-8"))
        defined = {node.name for node in tree.body if isinstance(node, ast.FunctionDef)}
        rules = {
            "escape_embedded_breaks",
            "next_cut",
            "_readme_notes",
            "_write_parts",
            "_overview_notices",
            "_escape_invalid_utf8",
        }
        self.assertEqual(set(), defined & rules)


class AdmissionFileTests(unittest.TestCase):
    """The payload is read, and the artefacts written, never through a link."""

    def test_the_payload_reader_never_follows_a_link(self) -> None:
        """The entrypoint refuses a link before reading; the reader refuses one too,
        so a link swapped in after that check is not followed either."""
        from tools import agent_review_admission as admission

        with tempfile.TemporaryDirectory() as scratch:
            outside = pathlib.Path(scratch) / "outside.json"
            outside.write_text('{"event_name": "note"}', encoding="utf-8")
            link = pathlib.Path(scratch) / "payload.json"
            link.symlink_to(outside)
            with self.assertRaisesRegex(admission.Refused, "not a regular file"):
                admission.read_payload(str(link))

    def test_an_artefact_is_never_written_through_a_link(self) -> None:
        """The directory is created here, so nothing should be in it; if something is
        -- a link planted between creation and writing -- it is refused, and the file
        it names is untouched."""
        from tools import agent_review_admission as admission

        with tempfile.TemporaryDirectory() as scratch:
            target = pathlib.Path(scratch) / "request"
            target.mkdir()
            victim = pathlib.Path(scratch) / "victim"
            victim.write_text("kept", encoding="utf-8")
            (target / "request").symlink_to(victim)
            with (
                mock.patch.object(pathlib.Path, "mkdir"),
                self.assertRaises(OSError),
            ):
                admission.write_request(target, {"request": "x"}, line_cap=100)
            self.assertEqual("kept", victim.read_text(encoding="utf-8"))


class GitHubRequestSourceTests(unittest.TestCase):
    """The GitHub request source takes ids from the relay and facts from GitHub."""

    @staticmethod
    def _source(answers: dict[str, Any], repository: str = "o/r") -> Any:
        """A source whose provider answers only ``answers`` and refuses the rest."""
        from tools import agent_review_admission as admission
        from tools import agent_review_github as github

        def read(path: str) -> Any:
            if path not in answers:
                raise admission.Refused(f"HTTP 404 reading {path!r}")
            return answers[path]

        return github.IssueRequests(repository, read)

    def test_the_item_is_the_comments_own_not_the_relays(self) -> None:
        """A relay naming another issue beside the comment changes nothing."""
        from tools import agent_review_model as model

        source = self._source(
            {
                "repos/o/r/issues/comments/7": {
                    "issue_url": "https://api.github.com/repos/o/r/issues/5",
                    "user": {"login": "ana"},
                    "body": "please review",
                },
                "repos/o/r/issues/5": {"title": "t", "body": "b"},
                "repos/o/r/issues/9": {"title": "other", "body": "other"},
            }
        )
        request = source.read_request(
            "issue_comment", {"comment_id": 7, "issue_number": 9}
        )
        self.assertEqual(model.Ref("issue", "5"), request.item)
        self.assertEqual("t", request.title)

    def test_a_repository_not_in_owner_name_form_is_refused(self) -> None:
        """The name reaches every URL, so a path in its place is refused first."""
        from tools import agent_review_admission as admission

        # Not "../r": the pattern admits dot segments, and the value is GitHub's own
        # `github.repository`, which cannot be one. Decision 0100 records the limit.
        for repository in ("o", "o/r/../x", "o/r?x=1", "o/r/issues", "o r/x"):
            with (
                self.subTest(repository=repository),
                self.assertRaisesRegex(admission.Refused, "owner/name form"),
            ):
                self._source({}, repository)


class ThinAdmissionEntrypointTests(unittest.TestCase):
    """The admission entrypoint composes; it holds no rule of its own."""

    def test_the_entrypoint_imports_the_core_and_decides_nothing(self) -> None:
        """The rules' own dependencies -- digests, constant-time comparison, instants
        -- belong to the core, so an entrypoint that imports them has a rule in it."""
        entrypoint = ROOT / ".github" / "review-context" / "admit_mention.py"
        imported = _imports(entrypoint.read_text(encoding="utf-8"))
        self.assertIn("tools", imported)
        self.assertEqual(set(), imported & {"hashlib", "hmac", "datetime"})
        source = entrypoint.read_text(encoding="utf-8")
        self.assertIn("agent_review_admission", source)


class HandoffRecordTests(unittest.TestCase):
    """The handoff's status record is all or nothing."""

    def test_a_status_record_cut_off_after_its_first_line_is_not_a_record(self) -> None:
        """A cut report's record is two lines, and its first line alone is a valid
        record of an uncut one: a write interrupted between them was read back as a
        complete, uncut report, and the comment lost its tail and its notice (Codex on
        #353). The record is published only whole."""
        from tools import agent_review_report as report

        cut = report.AgentReport("complete", "x" * (report.HANDOFF_BYTES + 10), False)
        names: dict[int, str] = {}
        real_open, real_fdopen = os.open, os.fdopen

        def recording_open(
            path: Any, flags: int, mode: int = 0o777, **options: Any
        ) -> int:
            """Open as os.open does, remembering which descriptor names which file."""
            descriptor = real_open(path, flags, mode, **options)
            names[descriptor] = os.path.basename(str(path))
            return descriptor

        def interrupting(descriptor: int, *args: Any, **options: Any) -> Any:
            """Wrap as os.fdopen does, cutting the status record after its first line."""
            stream = real_fdopen(descriptor, *args, **options)
            if not names.get(descriptor, "").lstrip(".").startswith("status"):
                return stream
            original = stream.write

            def write(text: str) -> int:
                """Write the first line, as an interruption could leave it, then stop."""
                original(text.split("\n")[0] + "\n")
                stream.flush()
                raise OSError("cancelled mid-record")

            stream.write = write
            return stream

        with tempfile.TemporaryDirectory() as scratch:
            directory = pathlib.Path(scratch) / "handoff"
            with (
                mock.patch.object(os, "open", recording_open),
                mock.patch.object(os, "fdopen", interrupting),
                self.assertRaises(OSError),
            ):
                report.write_handoff(cut, directory)
            received = report.read_handoff(directory)
        self.assertEqual("unavailable", received.status)

    def test_an_unreadable_handoff_is_an_unavailable_report(self) -> None:
        """A handoff file that exists but cannot be read is not a crash: the poster
        must still post that the report is unavailable (CodeAnt on #353)."""
        from tools import agent_review_report as report

        with tempfile.TemporaryDirectory() as scratch:
            directory = pathlib.Path(scratch) / "handoff"
            report.write_handoff(report.AgentReport("complete", "x", False), directory)
            (directory / "report.txt").chmod(0)
            try:
                received = report.read_handoff(directory)
            finally:
                (directory / "report.txt").chmod(0o600)
        self.assertEqual("unavailable", received.status)


class InFlightDeliveryTests(unittest.TestCase):
    """A create that may still be running is never followed by another (Codex)."""

    def test_an_attempt_still_in_flight_is_not_followed_by_another(self) -> None:
        """When an attempt outlives its bound it is abandoned, not stopped: it can
        still create the comment after a read-back found nothing, and a second create
        would then make two. Delivery stops instead, visibly."""
        from tools import agent_review_delivery as delivery

        class Abandoning:
            """A sink whose first create is abandoned in flight and lands later."""

            def __init__(self) -> None:
                self.created: list[str] = []
                self.searched: list[str] = []

            def create(self, body: str) -> str:
                self.created.append(body)
                raise delivery.DeliveryUncertain("still running", in_flight=True)

            def find(self, marker: str) -> str | None:
                self.searched.append(marker)
                return None

        sink = Abandoning()
        marker = delivery.delivery_marker("run-1.1")
        with self.assertRaises(delivery.DeliveryUnconfirmed):
            delivery.post_once(sink, f"{marker}\nbody", marker, pause=lambda _s: None)
        self.assertEqual([f"{marker}\nbody"], sink.created)
        # Only the read-back before the first create: after an attempt in flight,
        # nothing a read-back could find would make a second create safe.
        self.assertEqual([marker], sink.searched)

    def test_a_resumed_delivery_finds_its_comment_before_creating(self) -> None:
        """A rerun of the delivery is a new process with the same marker. Reading back
        only after a failure in the same process, it created again over the comment
        the first attempt had made (Codex on #353). It reads back first."""
        from tools import agent_review_delivery as delivery

        class Delivered:
            """A sink that already holds this delivery's comment."""

            def __init__(self) -> None:
                self.created: list[str] = []

            def create(self, body: str) -> str:
                self.created.append(body)
                return "https://example.invalid/second"

            @staticmethod
            def find(marker: str) -> str | None:
                return f"https://example.invalid/first#{marker}"

        sink = Delivered()
        marker = delivery.delivery_marker("run-1.1")
        posted = delivery.post_once(
            sink, f"{marker}\nbody", marker, pause=lambda _s: None
        )
        self.assertEqual(f"https://example.invalid/first#{marker}", posted)
        self.assertEqual([], sink.created)

    def test_the_github_sink_reports_an_abandoned_create_as_in_flight(self) -> None:
        """The adapter carries the client's in-flight fact into the core's vocabulary."""
        from tools import agent_review_delivery as delivery
        from tools import agent_review_github as github
        from tools import github_rest

        class Client:
            """A client whose create outlived its bound and was abandoned."""

            api_root = github_rest.API_ROOT

            def __init__(self) -> None:
                self.posted: list[tuple[str, object]] = []

            def post(self, url: str, payload: object) -> object:
                self.posted.append((url, payload))
                raise github_rest.GitHubWriteError("timed out", in_flight=True)

        url = f"{github_rest.API_ROOT}/repos/o/r/issues/1/comments"
        client = Client()
        sink = github.IssueCommentSink(url, client=client)  # type: ignore[arg-type]
        with self.assertRaises(delivery.DeliveryUncertain) as caught:
            sink.create("body")
        self.assertTrue(caught.exception.in_flight)
        self.assertEqual([(url, {"body": "body"})], client.posted)


class ReadBackWindowTests(unittest.TestCase):
    """The read-back covers the whole delivery, not the minutes before a job."""

    def test_the_sink_reads_back_from_the_instant_it_is_given(self) -> None:
        """A rerun of only the posting job keeps the run's start; reading back from
        five minutes before the rerun missed a comment the first attempt created."""
        from tools import agent_review_delivery as delivery
        from tools import agent_review_github as github
        from tools import github_rest

        class Client:
            """A client that records each read and answers an empty listing."""

            api_root = github_rest.API_ROOT

            def __init__(self) -> None:
                self.read: list[str] = []

            def read_page(self, url: str) -> tuple[list[Any], dict[str, str]]:
                self.read.append(url)
                return [], {}

        url = f"{github_rest.API_ROOT}/repos/o/r/issues/1/comments"
        client = Client()
        sink = github.IssueCommentSink(
            url,
            client=client,  # type: ignore[arg-type]
            since="2026-10-03T09:00:00Z",
        )
        self.assertIsNone(sink.find("marker"))
        self.assertEqual(
            [f"{url}?since=2026-10-03T09:00:00Z&per_page=100"], client.read
        )
        for bad in ("2026-10-03T09:00:00Z&per_page=1", "yesterday", ""):
            with (
                self.subTest(since=bad),
                self.assertRaises(delivery.DeliveryRefused),
            ):
                github.IssueCommentSink(url, client=client, since=bad)  # type: ignore[arg-type]


class LocatedCreateTests(unittest.TestCase):
    """A create counts as delivered only with the comment's location."""

    def test_a_create_answered_without_a_location_is_uncertain(self) -> None:
        """A success whose answer was not an object, or named no location, was reported
        as delivered with an empty location (CodeAnt on #353). It is uncertain, so
        delivery reads back for the comment it may have made."""
        from tools import agent_review_delivery as delivery
        from tools import agent_review_github as github
        from tools import github_rest

        url = f"{github_rest.API_ROOT}/repos/o/r/issues/1/comments"
        answers: tuple[object, ...] = ([], {}, {"html_url": ""}, {"html_url": 5})
        for answer in answers:
            with self.subTest(answer=answer):

                class Client:
                    """A client whose create succeeded with ``answer``."""

                    api_root = github_rest.API_ROOT

                    def __init__(self, answer: object) -> None:
                        self.answer = answer
                        self.posted: list[str] = []

                    def post(self, target: str, _payload: object) -> object:
                        self.posted.append(target)
                        return self.answer

                client = Client(answer)
                sink = github.IssueCommentSink(url, client=client)  # type: ignore[arg-type]
                with self.assertRaises(delivery.DeliveryUncertain):
                    sink.create("body")
                self.assertEqual([url], client.posted)


class LocatedReadBackTests(unittest.TestCase):
    """A read-back counts a comment as delivered only with its location."""

    def test_a_matching_comment_without_a_location_is_uncertain(self) -> None:
        """A comment of this delivery's that the provider listed without a location was
        reported delivered with an empty one (CodeAnt on #353). It is uncertain."""
        from tools import agent_review_delivery as delivery
        from tools import agent_review_github as github
        from tools import github_rest

        url = f"{github_rest.API_ROOT}/repos/o/r/issues/1/comments"
        marker = "<!-- marker -->"
        for location in (None, "", 5):

            class Client:
                """A client listing one comment of this delivery's."""

                api_root = github_rest.API_ROOT

                def __init__(self, location: object) -> None:
                    self.location = location

                def read_page(self, _url: str) -> tuple[list[Any], dict[str, str]]:
                    comment: dict[str, Any] = {
                        "user": {"login": github.COMMENT_AUTHOR},
                        "body": f"{marker}\nthe review",
                    }
                    if self.location is not None:
                        comment["html_url"] = self.location
                    return [comment], {}

            with self.subTest(location=location):
                sink = github.IssueCommentSink(
                    url,
                    client=Client(location),  # type: ignore[arg-type]
                    since="2026-10-03T09:00:00Z",
                )
                with self.assertRaises(delivery.DeliveryUncertain):
                    sink.find(marker)


class RetriedReadBackTests(unittest.TestCase):
    """A read-back is a read: a transient failure is retried, not a reason to stop."""

    def test_a_transient_failure_reading_back_is_retried(self) -> None:
        """One 502 during the read-back ended delivery as unconfirmed, and lost the
        review, though reading again could not duplicate anything (CodeAnt on #353).
        The sink's own client retries the read, and still never retries a create."""
        import email.message
        import io
        import urllib.error
        import urllib.request

        from tools import agent_review_github as github
        from tools import github_rest

        url = f"{github_rest.API_ROOT}/repos/o/r/issues/1/comments"
        marker = "<!-- marker -->"
        comment = {
            "user": {"login": github.COMMENT_AUTHOR},
            "body": f"{marker}\nthe review",
            "html_url": "https://github.com/o/r/issues/1#c1",
        }

        class Answer(io.BytesIO):
            """A provider answer as an opener returns one."""

            def __init__(self, body: bytes) -> None:
                super().__init__(body)
                self.headers: dict[str, str] = {}

        calls: list[str] = []

        def answer(request: urllib.request.Request, **_kwargs: Any) -> Any:
            calls.append(request.full_url)
            if len(calls) == 1:
                raise urllib.error.HTTPError(
                    request.full_url,
                    502,
                    "Bad Gateway",
                    email.message.Message(),
                    io.BytesIO(),
                )
            return Answer(json.dumps([comment]).encode("utf-8"))

        opener = mock.MagicMock()
        opener.open.side_effect = answer
        with (
            mock.patch.object(urllib.request, "build_opener", return_value=opener),
            mock.patch.dict(os.environ, {"GH_TOKEN": _NOT_A_CREDENTIAL}),
            mock.patch("time.sleep", lambda _seconds: None),
        ):
            sink = github.IssueCommentSink(url, since="2026-10-03T09:00:00Z")
            self.assertEqual(comment["html_url"], sink.find(marker))
        self.assertEqual(2, len(calls))


class GitHubClaudeCompositionTests(unittest.TestCase):
    """The GitHub-and-Claude composition keeps the guarantees the core leaves to it."""

    def test_the_composition_redacts_both_adapters_credential_shapes(self) -> None:
        """Credential shapes are contributed by the adapters that know them; composed,
        the GitHub poster redacts GitHub tokens, Anthropic keys and generic shapes."""
        from tools import agent_review_claude_code as claude
        from tools import agent_review_delivery as delivery
        from tools import agent_review_github as github
        from tools import agent_review_report as report

        text = " ".join(
            (
                "ghp_" + "A" * 36,
                "github_pat_" + "B" * 30,
                "sk-ant-" + "C" * 30,
                "AKIA" + "D" * 16,
            )
        )
        body = delivery.render_comment(
            report.AgentReport("complete", text, False),
            reviewer=claude.REVIEWER_NAME,
            provenance="Run: x",
            secret_patterns=github.SECRET_PATTERNS + claude.SECRET_PATTERNS,
        )
        for leaked in ("A" * 12, "B" * 12, "C" * 12, "D" * 12):
            with self.subTest(leaked=leaked):
                self.assertNotIn(leaked, body)
        self.assertIn("4 value(s) shaped like a credential", body)

    def test_the_claude_adapter_reads_the_execution_envelope(self) -> None:
        """The Claude Code envelope is translated into the core's report record."""
        from tools import agent_review_claude_code as claude

        with tempfile.TemporaryDirectory() as scratch:
            execution = pathlib.Path(scratch) / "execution.json"
            execution.write_text(
                json.dumps(
                    [
                        {
                            "type": "result",
                            "subtype": "success",
                            "is_error": False,
                            "result": "Looks fine.",
                        }
                    ]
                ),
                encoding="utf-8",
            )
            produced = claude.read_report(execution)
        self.assertEqual(("complete", "Looks fine.", False), tuple(produced)[:3])

    def test_an_empty_execution_is_an_unavailable_report_not_a_crash(self) -> None:
        """An execution file holding no turns at all has no report: `run_succeeded`
        returns before it would read the last turn (CodeAnt on #353)."""
        from tools import agent_review_claude_code as claude

        self.assertFalse(claude.run_succeeded([]))
        self.assertEqual(("", False), claude.final_report([]))
        with tempfile.TemporaryDirectory() as scratch:
            execution = pathlib.Path(scratch) / "execution.json"
            execution.write_text("[]", encoding="utf-8")
            produced = claude.read_report(execution)
        self.assertEqual("unavailable", produced.status)
        self.assertEqual("The reviewer produced no final text.", produced.reason)


if __name__ == "__main__":
    unittest.main()
