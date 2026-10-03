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
            request=note["text"],
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


def _forge_trigger(**changes: str) -> Any:
    """What the second provider recorded about the triggering run."""
    from tools import agent_review_admission as admission

    fields = {
        "event": "note",
        "origin": _FORGE_ORIGIN,
        "actor": "ana",
        "created_at": "2026-10-03T10:00:05Z",
        "revision": _REVISION,
    }
    fields.update(changes)
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
                _forge_trigger(revision="main"),
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
                    _forge_trigger(**trigger),
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
        # Not even a read-back: nothing it could find would make a second create safe.
        self.assertEqual([], sink.searched)

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

            def get(self, url: str) -> tuple[list[Any], dict[str, str]]:
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
