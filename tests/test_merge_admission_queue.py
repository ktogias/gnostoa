"""RED: the bounded merge-admission queue correction (#407; the owner's direction on
#407, 6664424932, after the #478 queue saturation).

The relay put every admission run into one repository-wide concurrency group with
`queue: max` (`.github/workflows/merge-admission.yml`). Every eligible event waited
its turn and, when it came, evaluated the pull request's current state again, and
each evaluation began by replacing a standing success with a pending run. On #478's
head `30423e3d`, 20 full evaluations published a check between 15:33Z and 17:15Z;
15 of them repeated the state the check before them already bound, and the check
stood pending for 77% of the span between the first ALLOW and the merge.

The tests bind the correction at the two places the defect lives:

1. **Scheduling**, the `concurrency` GitHub enforces for the workflow and its jobs.
   The model is GitHub's documented rule as Decision 0086 records it: a group runs
   one execution at a time; with `queue: max` up to 100 more wait in order; without
   it, a new pending execution replaces the pending one, which is cancelled before
   it starts. A run takes its turn even when every job it holds will be skipped.
2. **Subject selection**, L1's `--mode subjects` (`ci/review_github_current_state.py`),
   which names what the relay evaluates. A routine request selects nothing when
   equivalence is proved: the pinned App's latest record on the head is a completed
   authoritative success (its external id the plan's digest, not a pending,
   superseded, overtaken or incomplete one) written from the protected revision
   this run executes, recording the digest of the evidence rebuilt now without the
   analyzer bundle, the digest the guarded merge itself compares
   (`ci/merge_admission_guard.py`), and the pull request is alone at its head. So no
   pending check is created and nothing is acquired. A guarded dispatch, a manual
   dispatch and the sweep never coalesce. The selection reads the pinned App's id
   from `GNOSTOA_MA0_APP_ID`, the run's event and protected revision from the runner
   (`GITHUB_EVENT_NAME`, `GITHUB_SHA`), and every provider state through L1's own
   client.

A test named in `GUARDS` passes on main by construction, since main coalesces
nothing and serializes everything: it binds a safety property the correction must
keep, and is not a RED. `MODEL_CHECKS` check the model itself.
"""

from __future__ import annotations

import contextlib
import copy
import functools
import io
import json
import math
import os
import re
import tempfile
import unittest
from collections.abc import Callable, Mapping
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Any
from unittest import mock

import yaml

from tests.merge_evidence_github_support import CHECK_RUNS, _replies
from tests.review_reconcile_l1_support import adapter_fixture, paged_fake_fixture
from tools import github_rest, merge_evidence_github
from tools.merge_admission_checks import correlation_text, digest

ROOT = Path(__file__).resolve().parents[1]
ADMISSION = ROOT / ".github" / "workflows" / "merge-admission.yml"
REPOSITORY = "ktogias/gnostoa"
API = f"https://api.github.com/repos/{REPOSITORY}"
HEAD = "a" * 40
MOVED = "d" * 40
REVISION = "9" * 40
MOVED_REVISION = "8" * 40
MA0_APP = 4242
OTHER_APP = 15368
TRIGGER = ".github/workflows/merge-admission-trigger.yml"
VERIFICATION = ".github/workflows/verification.yml"
LISTING = f"{API}/pulls?state=open&per_page=100"
PUBLISHING_JOBS = ("invalidate", "admit")
# The safety properties main already holds; every other test here is a RED.
GUARDS = frozenset(
    {
        "test_publication_on_one_head_is_serialized_for_every_pairing",
        "test_a_record_that_is_not_an_authoritative_success_never_coalesces",
        "test_a_moved_head_a_moved_main_or_changed_evidence_never_coalesces",
        "test_a_shared_head_never_coalesces",
        "test_a_guarded_manual_or_scheduled_request_never_coalesces",
        "test_a_selection_that_names_no_event_never_coalesces",
        "test_an_unreadable_record_never_coalesces",
    }
)
# The model's own rules, independent of the workflow: they pass on any revision.
MODEL_CHECKS = frozenset(
    {
        "test_expressions_follow_github_s_documented_rules",
        "test_without_queue_max_a_new_request_replaces_the_pending_one",
        "test_with_queue_max_every_request_waits_its_turn",
    }
)


# --- GitHub Actions expressions, the subset a concurrency group can use ---------

_TOKEN = re.compile(
    r"\s*(?:(?P<number>\d+(?:\.\d+)?)|(?P<string>'(?:[^']|'')*')"
    r"|(?P<op>==|!=|<=|>=|&&|\|\||[()\[\].,!<>])"
    r"|(?P<name>[A-Za-z_][A-Za-z0-9_-]*))"
)


def _tokens(text: str) -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    position = 0
    while text[position:].strip():
        match = _TOKEN.match(text, position)
        if match is None or match.lastgroup is None:
            raise AssertionError(f"unsupported expression text at {text[position:]!r}")
        found.append((match.lastgroup, match.group(match.lastgroup)))
        position = match.end()
    return found


def _truthy(value: object) -> bool:
    return value not in (None, False, 0, "") and not (
        isinstance(value, float) and math.isnan(value)
    )


def _number(value: object) -> float:
    if value is None:
        return 0.0
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip() or 0)
        except ValueError:
            return float("nan")
    return float("nan")


def _equal(left: object, right: object) -> bool:
    """GitHub's loose equality: strings ignore case, other types compare as numbers."""
    if isinstance(left, str) and isinstance(right, str):
        return left.casefold() == right.casefold()
    if type(left) is type(right) and isinstance(left, (dict, list)):
        return left is right
    return _number(left) == _number(right)


def _text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    if isinstance(value, (dict, list)):
        return "Object" if isinstance(value, dict) else "Array"
    return str(value)


def _format(template: str, *arguments: object) -> str:
    def replace(match: re.Match[str]) -> str:
        token = match.group(0)
        if token in ("{{", "}}"):
            return token[0]
        return _text(arguments[int(token[1:-1])])

    return re.sub(r"\{\{|\}\}|\{\d+\}", replace, template)


def _contains(search: object, item: object) -> bool:
    if isinstance(search, list):
        return any(_equal(element, item) for element in search)
    return _text(item).casefold() in _text(search).casefold()


_FUNCTIONS: dict[str, Callable[..., object]] = {
    "format": lambda template, *rest: _format(_text(template), *rest),
    "contains": _contains,
    "startswith": lambda text, prefix: (
        _text(text).casefold().startswith(_text(prefix).casefold())
    ),
    "endswith": lambda text, suffix: (
        _text(text).casefold().endswith(_text(suffix).casefold())
    ),
    "tojson": lambda value: json.dumps(value, indent=2),
    "fromjson": lambda text: json.loads(_text(text)),
    "join": lambda values, separator=",": _text(separator).join(
        _text(value) for value in (values if isinstance(values, list) else [values])
    ),
}


def _member(value: object, key: object) -> object:
    if isinstance(value, dict):
        if key in value:
            return value[key]
        folded = {str(name).casefold(): item for name, item in value.items()}
        return folded.get(_text(key).casefold())
    if isinstance(value, list) and isinstance(key, (int, float)):
        index = int(key)
        return value[index] if 0 <= index < len(value) else None
    return None


class _Expression:
    """One expression, evaluated against a context, by GitHub's documented rules:
    `||` and `&&` return an operand, a missing property is null, and `==` is loose."""

    def __init__(self, text: str, context: Mapping[str, Any]) -> None:
        self.tokens = _tokens(text)
        self.index = 0
        self.context = context

    def value(self) -> object:
        result = self._or()
        if self.index != len(self.tokens):
            raise AssertionError(
                f"unparsed expression tokens {self.tokens[self.index :]}"
            )
        return result

    def _peek(self) -> str | None:
        return self.tokens[self.index][1] if self.index < len(self.tokens) else None

    def _take(self, expected: str | None = None) -> tuple[str, str]:
        if self.index >= len(self.tokens):
            raise AssertionError("the expression ends early")
        token = self.tokens[self.index]
        if expected is not None and token[1] != expected:
            raise AssertionError(f"expected {expected!r}, found {token[1]!r}")
        self.index += 1
        return token

    def _or(self) -> object:
        left = self._and()
        while self._peek() == "||":
            self._take()
            right = self._and()
            left = left if _truthy(left) else right
        return left

    def _and(self) -> object:
        left = self._comparison()
        while self._peek() == "&&":
            self._take()
            right = self._comparison()
            left = right if _truthy(left) else left
        return left

    def _comparison(self) -> object:
        left = self._unary()
        operator = self._peek()
        if operator not in ("==", "!=", "<", "<=", ">", ">="):
            return left
        self._take()
        right = self._unary()
        if operator in ("==", "!="):
            return _equal(left, right) is (operator == "==")
        ordered = {
            "<": _number(left) < _number(right),
            "<=": _number(left) <= _number(right),
            ">": _number(left) > _number(right),
            ">=": _number(left) >= _number(right),
        }
        return ordered[operator]

    def _unary(self) -> object:
        if self._peek() == "!":
            self._take()
            return not _truthy(self._unary())
        return self._postfix(self._primary())

    def _primary(self) -> object:
        kind, text = self._take()
        if kind == "number":
            return float(text)
        if kind == "string":
            return text[1:-1].replace("''", "'")
        if text == "(":
            inner = self._or()
            self._take(")")
            return inner
        if kind != "name":
            raise AssertionError(f"unexpected token {text!r}")
        if self._peek() == "(":
            return self._call(text)
        literals: dict[str, object] = {"true": True, "false": False, "null": None}
        if text in literals:
            return literals[text]
        return _member(dict(self.context), text)

    def _call(self, name: str) -> object:
        function = _FUNCTIONS.get(name.casefold())
        if function is None:
            raise AssertionError(f"unsupported function {name}()")
        self._take("(")
        arguments: list[object] = []
        while self._peek() != ")":
            arguments.append(self._or())
            if self._peek() == ",":
                self._take()
        self._take(")")
        return function(*arguments)

    def _postfix(self, value: object) -> object:
        while self._peek() in (".", "["):
            if self._take()[1] == ".":
                value = _member(value, self._take()[1])
            else:
                key = self._or()
                self._take("]")
                value = _member(value, key)
        return value


def _evaluate(value: object, context: Mapping[str, Any]) -> object:
    """A workflow value: a literal, one whole `${{ }}` expression, or a string with
    expressions interpolated as text."""
    if not isinstance(value, str):
        return value
    whole = re.fullmatch(r"\s*\$\{\{(.*?)\}\}\s*", value, flags=re.DOTALL)
    if whole:
        return _Expression(whole.group(1), context).value()
    return re.sub(
        r"\$\{\{(.*?)\}\}",
        lambda match: _text(_Expression(match.group(1), context).value()),
        value,
        flags=re.DOTALL,
    )


# --- The admission workflow's declared concurrency -------------------------------


def _workflow() -> dict[str, Any]:
    document = yaml.safe_load(ADMISSION.read_text(encoding="utf-8"))
    if not isinstance(document, dict):
        raise AssertionError("merge-admission.yml is not a workflow")
    return document


def _declaration(node: object) -> dict[str, Any] | None:
    if node is None:
        return None
    if isinstance(node, str):
        return {"group": node}
    if not isinstance(node, dict) or "group" not in node:
        raise AssertionError(f"unreadable concurrency {node!r}")
    return node


def _group(declaration: Mapping[str, Any], context: Mapping[str, Any]) -> str:
    group = _text(_evaluate(declaration["group"], context))
    if not group:
        raise AssertionError("a concurrency group evaluated to an empty name")
    return group


def _cancels(declaration: Mapping[str, Any], context: Mapping[str, Any]) -> bool:
    return _truthy(_evaluate(declaration.get("cancel-in-progress", False), context))


def _queues(declaration: Mapping[str, Any]) -> bool:
    """True for `queue: max`, which keeps every pending execution in order."""
    return declaration.get("queue") == "max"


class _Scheduler:
    """GitHub's concurrency rule for one declaration, over named runs."""

    def __init__(
        self,
        declaration: Mapping[str, Any] | None,
        on_start: Callable[[str], None] | None = None,
    ) -> None:
        self.declaration = declaration
        self.on_start = on_start
        self.running: dict[str, str] = {}
        self.pending: dict[str, list[str]] = {}
        self.started: list[str] = []
        self.cancelled: list[str] = []
        self.group_of: dict[str, str] = {}

    def arrive(self, name: str, context: Mapping[str, Any]) -> None:
        if self.declaration is None:
            self._start(name, f"none:{name}")
            return
        group = _group(self.declaration, context)
        self.group_of[name] = group
        if _cancels(self.declaration, context) and group in self.running:
            self.cancelled.append(self.running.pop(group))
        if group not in self.running:
            self._start(name, group)
            return
        waiting = self.pending.setdefault(group, [])
        if not _queues(self.declaration):
            self.cancelled.extend(waiting)
            waiting.clear()
        if len(waiting) >= 100:
            raise AssertionError("the model's queue is past GitHub's 100 pending")
        waiting.append(name)

    def finish(self, name: str) -> None:
        group = next(
            (g for g, running in self.running.items() if running == name), None
        )
        if group is None:
            raise AssertionError(f"the model has no running {name}")
        del self.running[group]
        waiting = self.pending.get(group, [])
        if waiting:
            self._start(waiting.pop(0), group)

    def ahead_of(self, name: str) -> list[str]:
        """The runs that must end before `name` starts."""
        group = self.group_of.get(name)
        if group is None or name in self.started:
            return []
        waiting = self.pending.get(group, [])
        return [self.running[group], *waiting[: waiting.index(name)]]

    def waiting(self) -> list[str]:
        return [name for names in self.pending.values() for name in names]

    def _start(self, name: str, group: str) -> None:
        self.running[group] = name
        self.started.append(name)
        if self.on_start is not None:
            self.on_start(name)


# --- Event contexts, as GitHub delivers them to merge-admission.yml --------------


def _context(
    event_name: str,
    event: dict[str, Any],
    run_id: int,
    inputs: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "github": {
            "event_name": event_name,
            "event": event,
            "ref": "refs/heads/main",
            "sha": REVISION,
            "repository": REPOSITORY,
            "workflow": "Merge admission",
            "run_id": run_id,
            "run_number": run_id,
            "run_attempt": 1,
        },
        "inputs": inputs or {},
        "vars": {"GNOSTOA_MA0_APP_ID": str(MA0_APP)},
    }


def _woken(
    run_id: int,
    *,
    kind: str = "pull_request_review",
    pull: int | None = 300,
    head: str = HEAD,
    path: str = TRIGGER,
    conclusion: str = "success",
) -> dict[str, Any]:
    """An admission run woken by a completed trigger or verification run."""
    pulls = [] if pull is None else [{"number": pull, "head": {"sha": head}}]
    return _context(
        "workflow_run",
        {
            "action": "completed",
            "workflow_run": {
                "id": 7000 + run_id,
                "run_attempt": 1,
                "path": path,
                "event": kind,
                "conclusion": conclusion,
                "head_sha": head,
                "head_branch": "main" if pull is None else f"agent/{pull}",
                "pull_requests": pulls,
            },
        },
        run_id,
    )


def _relayed_comment(run_id: int, *, conclusion: str = "skipped") -> dict[str, Any]:
    """A PR conversation comment's trigger run: from main, naming no pull request."""
    return _woken(
        run_id, kind="issue_comment", pull=None, head=REVISION, conclusion=conclusion
    )


def _dispatched(run_id: int, pull: int = 300) -> dict[str, Any]:
    return _context(
        "repository_dispatch",
        {
            "action": "gnostoa-merge-admission",
            "client_payload": {"pull_number": pull, "nonce": f"{run_id:032x}"},
        },
        run_id,
    )


def _scheduled(run_id: int) -> dict[str, Any]:
    return _context("schedule", {"schedule": "41 * * * *"}, run_id)


def _manual(run_id: int, pull: int = 300) -> dict[str, Any]:
    return _context(
        "workflow_dispatch",
        {"inputs": {"pull_number": pull}},
        run_id,
        inputs={"pull_number": pull},
    )


def _matrix(context: Mapping[str, Any], pull: int, head: str) -> dict[str, Any]:
    return {**context, "matrix": {"subject": {"pull_number": pull, "head": head}}}


# --- The provider L1 reads, with the pinned App's latest record ------------------


_LATEST = "/check-runs?check_name=merge-admission&filter=latest&per_page=100"


class _Provider:
    """L1's provider: the replies it was given, the open population, and the pinned
    App's latest `merge-admission` record per head. It refuses any other read."""

    def __init__(self, replies: dict[str, tuple[Any, dict[str, str]]]) -> None:
        self.replies = replies
        self.records: dict[str, list[dict[str, Any]]] = {}
        self.unreadable = False
        self.short = False
        self.fake = paged_fake_fixture(self._served())

    def _served(self) -> dict[str, tuple[Any, dict[str, str]]]:
        served = dict(self.replies)
        if LISTING not in served:
            pull = copy.deepcopy(self.replies[f"{API}/pulls/300"][0])
            served[LISTING] = ([pull], {})
        return served

    def refresh(self, replies: dict[str, tuple[Any, dict[str, str]]]) -> None:
        self.replies = replies
        self.fake.replies = self._served()

    @staticmethod
    def url(path: str) -> str:
        return f"https://api.github.com/{path.lstrip('/')}"

    def get(self, url: str) -> tuple[Any, dict[str, str]]:
        prefix = f"{API}/commits/"
        if url.startswith(prefix) and url.endswith(_LATEST):
            if self.unreadable:
                raise github_rest.GitHubReadError("GitHub API HTTP 502", status=502)
            runs = self.records.get(url[len(prefix) : -len(_LATEST)], [])
            # A latest view short of its count holds only part of what it counts.
            total = len(runs) + (1 if self.short else 0)
            return {"total_count": total, "check_runs": copy.deepcopy(runs)}, {}
        result: tuple[Any, dict[str, str]] = self.fake.get(url)
        return result

    def graphql(self, query: str, variables: dict[str, Any]) -> Any:
        return self.fake.graphql(query, variables)


def _state_digest(replies: dict[str, tuple[Any, dict[str, str]]]) -> str:
    """The digest of the evidence rebuilt without the analyzer bundle, exactly as the
    relay records it and the guarded merge compares it."""
    snapshot = adapter_fixture().collect_snapshot(
        paged_fake_fixture(copy.deepcopy(replies)),
        repository=REPOSITORY,
        pull_number=300,
        observed_at=None,
        merge_evidence=True,
    )
    return digest(merge_evidence_github.evidence_for(snapshot, project_root=ROOT))


def _record(
    state_digest: str | None,
    *,
    external_id: str = "e" * 64,
    status: str = "completed",
    conclusion: str | None = "success",
    revision: str = REVISION,
    app: int = MA0_APP,
    head: str = HEAD,
    run_id: int = 9001,
) -> dict[str, Any]:
    """A `merge-admission` run as the relay writes it (`ci/merge_admission_relay.py`)."""
    return {
        "id": run_id,
        "name": "merge-admission",
        "head_sha": head,
        "status": status,
        "conclusion": conclusion,
        "external_id": external_id,
        "app": {"id": app, "slug": "gnostoa-ma0"},
        "output": {
            "title": "merge-admission: ALLOW",
            "summary": "Pull request 300.",
            "text": correlation_text(
                {
                    "workflow_run_id": 41000 + run_id,
                    "run_attempt": 1,
                    "protected_revision": revision,
                    "nonce": None,
                    "unbundled_evidence_sha256": state_digest,
                }
            ),
        },
    }


def _changed(**edits: Any) -> dict[str, tuple[Any, dict[str, str]]]:
    """PR 300's replies with a failed required check, or its owner's approval
    withdrawn: a material change the digest sees."""
    replies = _replies()
    if edits.get("failed_check"):
        checks = copy.deepcopy(replies[CHECK_RUNS])
        checks[0]["check_runs"][0]["conclusion"] = "failure"
        replies[CHECK_RUNS] = checks
    if edits.get("unapproved"):
        reviews = replies[f"{API}/pulls/300/reviews?per_page=100"][0]
        reviews[0]["state"] = "COMMENTED"
    return replies


def _moved_head() -> dict[str, tuple[Any, dict[str, str]]]:
    """PR 300 pushed to another head: every read of the old head now names the new."""
    text = json.dumps(_replies()).replace(HEAD, MOVED)
    loaded: dict[str, list[Any]] = json.loads(text)
    return {key: (value[0], value[1]) for key, value in loaded.items()}


_ROUTINE = (
    "--event",
    "--workflow-run-pulls-json",
    json.dumps([{"number": 300, "head": {"sha": HEAD}}]),
    "--workflow-run-head-sha",
    HEAD,
)


def _select(
    provider: _Provider,
    *arguments: str,
    event_name: str = "workflow_run",
    revision: str = REVISION,
    app_id: str = str(MA0_APP),
) -> tuple[int, list[dict[str, Any]] | None]:
    """L1's `--mode subjects`, as the relay's `subjects` job runs it."""
    module = adapter_fixture()
    environment = {
        "GH_TOKEN": "x" * 40,
        "GITHUB_EVENT_NAME": event_name,
        "GITHUB_SHA": revision,
        "GNOSTOA_MA0_APP_ID": app_id,
    }
    with tempfile.TemporaryDirectory() as raw:
        output = Path(raw) / "subjects.json"
        argv = [
            "--mode",
            "subjects",
            "--repository",
            REPOSITORY,
            *(arguments or _ROUTINE),
            "--output",
            str(output),
        ]
        with (
            mock.patch.object(module, "GitHubRestClient", return_value=provider),
            mock.patch.dict(os.environ, environment),
            contextlib.chdir(ROOT),
            redirect_stdout(io.StringIO()),
            redirect_stderr(io.StringIO()),
        ):
            try:
                code = int(module.main(argv))
            except SystemExit as exc:
                code = exc.code if isinstance(exc.code, int) else 1
        if not output.exists():
            return code, None
        written: list[dict[str, Any]] = json.loads(output.read_text(encoding="utf-8"))
        return code, written


class SchedulingTests(unittest.TestCase):
    """The workflow's declared concurrency, under GitHub's rule."""

    def setUp(self) -> None:
        self.workflow = _workflow()
        self.declaration = _declaration(self.workflow.get("concurrency"))

    def _scheduler(self) -> _Scheduler:
        return _Scheduler(self.declaration)

    def test_unrelated_pull_requests_do_not_wait_for_each_other(self) -> None:
        """Unrelated PRs progress independently: #301's request starts while #300's
        evaluation runs, and their heads publish under different locks."""
        scheduler = self._scheduler()
        scheduler.arrive("pr300", _woken(1, pull=300, head=HEAD))
        scheduler.arrive("pr301", _woken(2, pull=301, head=MOVED))
        self.assertEqual(
            [],
            scheduler.ahead_of("pr301"),
            "#301's request waits behind #300's evaluation",
        )
        for job in PUBLISHING_JOBS:
            declared = _declaration(self.workflow["jobs"][job].get("concurrency"))
            with self.subTest(job=job):
                if declared is not None:
                    self.assertNotEqual(
                        _group(declared, _matrix(_woken(1), 300, HEAD)),
                        _group(declared, _matrix(_woken(2, pull=301), 301, MOVED)),
                    )

    def test_a_request_that_selects_nothing_never_waits(self) -> None:
        """The #478 baseline: 115 comment relays the trigger skipped each waited for
        every evaluation queued before it, up to 84 minutes, only to be skipped. A
        run whose every job is skipped must neither wait nor displace a request."""
        scheduler = self._scheduler()
        scheduler.arrive("pr300", _woken(1))
        scheduler.arrive("pr300-next", _woken(2, kind="pull_request_review_comment"))
        scheduler.arrive("comment", _relayed_comment(3))
        self.assertEqual([], scheduler.ahead_of("comment"))
        self.assertNotIn("pr300-next", scheduler.cancelled)

    def test_a_guarded_request_never_waits_behind_or_yields_to_routine_work(
        self,
    ) -> None:
        """G1's dispatch is the merge's own admission: it must not wait for routine
        evaluations, whose queue outlasted the guard's 80-minute deadline in the
        #478 baseline (waits up to 84 minutes), and no later routine request may
        replace it."""
        scheduler = self._scheduler()
        scheduler.arrive("pr300", _woken(1))
        for number in range(301, 306):
            scheduler.arrive(f"pr{number}", _woken(number, pull=number, head=MOVED))
        scheduler.arrive("pr300-next", _woken(2, kind="pull_request_review_comment"))
        scheduler.arrive("guard", _dispatched(10))
        for index in range(3):
            scheduler.arrive(f"pr300-later{index}", _woken(20 + index))
        self.assertNotIn("guard", scheduler.cancelled)
        self.assertEqual(
            [], scheduler.ahead_of("guard"), "the guarded request waits behind them"
        )

    def test_publication_on_one_head_is_serialized_for_every_pairing(self) -> None:
        """Guard: whatever woke two runs, their publications on one head never run at
        once, none is dropped, and nothing in flight is cancelled."""
        pairings = {
            "routine and routine": (_woken(1), _woken(2, kind="pull_request")),
            "routine and guard": (_woken(1), _dispatched(2)),
            "routine and sweep": (_woken(1), _scheduled(2)),
            "routine and manual": (_woken(1), _manual(2)),
            "comment relay and routine": (
                _relayed_comment(1, conclusion="success"),
                _woken(2),
            ),
            "two pull requests at one head": (_woken(1), _woken(2, pull=301)),
            "a fork's event and routine": (_woken(1, pull=None), _woken(2)),
        }
        for label, (first, second) in pairings.items():
            with self.subTest(pairing=label):
                self.assertTrue(self._serialized(first, second), label)

    def test_only_a_routine_request_the_selection_admits_shares_a_group(self) -> None:
        """A run whose `subjects` job is skipped, whatever its trigger's path, event
        or conclusion, shares no group, so it can neither wait for nor replace a
        request that evaluates; a routine request `subjects` admits shares its pull
        request's group, except a relayed comment, whose pull request only its
        artifact names. No run's group is a head's publication lock."""
        condition = str(self.workflow["jobs"]["subjects"]["if"])
        declaration = self.declaration
        if declaration is None:
            raise AssertionError("merge-admission.yml declares no concurrency")
        lock = _declaration(self.workflow["jobs"]["admit"].get("concurrency"))
        cases: dict[str, Callable[[int], dict[str, Any]]] = {}
        for kind in (
            "pull_request",
            "pull_request_review",
            "pull_request_review_comment",
            "issue_comment",
        ):
            for conclusion in ("success", "failure", "skipped", "cancelled"):
                cases[f"trigger {kind} {conclusion}"] = functools.partial(
                    _woken, kind=kind, conclusion=conclusion
                )
        for conclusion in ("success", "failure"):
            cases[f"verification pull_request {conclusion}"] = functools.partial(
                _woken, kind="pull_request", path=VERIFICATION, conclusion=conclusion
            )
        cases["verification push"] = functools.partial(
            _woken, kind="push", pull=None, head=REVISION, path=VERIFICATION
        )
        cases["another workflow"] = functools.partial(
            _woken, kind="pull_request", path=".github/workflows/other.yml"
        )
        for label, woken in cases.items():
            first, second = woken(1), woken(2)
            admitted = _truthy(_Expression(condition, first).value())
            trigger = first["github"]["event"]["workflow_run"]
            relayed = trigger["event"] == "issue_comment"
            with self.subTest(case=label):
                self.assertEqual(
                    admitted and not relayed,
                    _group(declaration, first) == _group(declaration, second),
                )
                if lock is not None:
                    self.assertNotEqual(
                        _group(lock, _matrix(first, 300, HEAD)),
                        _group(declaration, first),
                    )

    def test_a_newer_routine_request_replaces_the_one_waiting(self) -> None:
        """One routine request runs and one waits: a newer one replaces the one
        waiting, so a burst never queues more than one follow-up, and nothing that
        runs is cancelled."""
        scheduler = self._scheduler()
        for name, run in (("first", 1), ("second", 2), ("third", 3)):
            scheduler.arrive(name, _woken(run, kind="pull_request_review"))
        self.assertEqual(
            (["first"], ["second"], ["third"]),
            (scheduler.started, scheduler.cancelled, scheduler.waiting()),
        )

    def test_the_sweep_a_dispatch_or_a_manual_request_never_joins_routine_work(
        self,
    ) -> None:
        """The sweep has one group of its own, and a guarded dispatch or a manual
        request a group of its own run: none waits behind a pull request's routine
        requests, or replaces one, or another of its kind."""
        declaration = self.declaration
        if declaration is None:
            raise AssertionError("merge-admission.yml declares no concurrency")
        routine = _group(declaration, _woken(1))
        sweeps = {_group(declaration, _scheduled(run)) for run in (2, 3)}
        self.assertEqual(1, len(sweeps))
        self.assertNotIn(routine, sweeps)
        for label, request in (("dispatch", _dispatched), ("manual", _manual)):
            with self.subTest(request=label):
                first, second = (
                    _group(declaration, request(4)),
                    _group(declaration, request(5)),
                )
                self.assertNotEqual(first, second)
                self.assertNotIn(first, {routine, *sweeps})

    def _serialized(self, first: dict[str, Any], second: dict[str, Any]) -> bool:
        declared = self.declaration
        for context in (first, second):
            if declared is not None and _cancels(declared, context):
                return False
        if declared is not None and _group(declared, first) == _group(declared, second):
            return True
        for job in PUBLISHING_JOBS:
            locked = _declaration(self.workflow["jobs"][job].get("concurrency"))
            if locked is None or not _queues(locked):
                return False
            one, two = _matrix(first, 300, HEAD), _matrix(second, 301, HEAD)
            if _cancels(locked, one) or _group(locked, one) != _group(locked, two):
                return False
        return True


class ModelTests(unittest.TestCase):
    """The model's rules, checked apart from any workflow."""

    def test_expressions_follow_github_s_documented_rules(self) -> None:
        context = _woken(5, pull=None, head=MOVED)
        self.assertEqual(
            f"head-{MOVED}",
            _evaluate(
                "head-${{ github.event.workflow_run.pull_requests[0].number"
                " || github.event.workflow_run.head_sha }}",
                context,
            ),
        )
        self.assertEqual(
            "pr-301",
            _evaluate(
                "${{ format('pr-{0}', github.event.workflow_run.pull_requests[0].number"
                " || github.event.workflow_run.head_sha) }}",
                _woken(6, pull=301),
            ),
        )
        self.assertIs(
            True, _evaluate("${{ github.event_name == 'WORKFLOW_RUN' }}", context)
        )
        self.assertIsNone(_evaluate("${{ github.event.nothing.here }}", context))
        self.assertIs(
            True,
            _evaluate(
                "${{ contains(fromJSON('[\"a\",\"b\"]'), 'B')"
                " && !(github.run_id != 5) }}",
                context,
            ),
        )
        self.assertEqual("x-", _evaluate("x-${{ github.event.missing }}", context))

    def test_without_queue_max_a_new_request_replaces_the_pending_one(self) -> None:
        scheduler = _Scheduler({"group": "g", "cancel-in-progress": False})
        for name in ("one", "two", "three"):
            scheduler.arrive(name, _woken(1))
        self.assertEqual(
            (["two"], ["three"]), (scheduler.cancelled, scheduler.waiting())
        )
        scheduler.finish("one")
        self.assertEqual(["one", "three"], scheduler.started)

    def test_with_queue_max_every_request_waits_its_turn(self) -> None:
        scheduler = _Scheduler(
            {"group": "g", "cancel-in-progress": False, "queue": "max"}
        )
        for name in ("one", "two", "three"):
            scheduler.arrive(name, _woken(1))
        self.assertEqual(["one", "two"], scheduler.ahead_of("three"))
        scheduler.finish("one")
        scheduler.finish("two")
        self.assertEqual(
            ([], ["one", "two", "three"]), (scheduler.cancelled, scheduler.started)
        )


class SelectionTests(unittest.TestCase):
    """L1's subject selection, before any pending check is created."""

    current: str

    @classmethod
    def setUpClass(cls) -> None:
        cls.current = _state_digest(_replies())

    @staticmethod
    def _provider(*records: dict[str, Any], head: str = HEAD) -> _Provider:
        provider = _Provider(_replies())
        provider.records[head] = list(records)
        return provider

    def test_an_equivalent_routine_request_selects_nothing(self) -> None:
        """The pinned App's latest record already binds this exact material state:
        the evaluation would repeat it, so it is skipped before any pending check."""
        code, written = _select(self._provider(_record(self.current)))
        self.assertEqual(0, code)
        self.assertEqual(
            [],
            written,
            "an equivalent routine request is selected for a full evaluation",
        )

    def test_a_record_that_is_not_an_authoritative_success_never_coalesces(
        self,
    ) -> None:
        """Guard: only a completed authoritative success of the pinned App proves
        equivalence; a pending, superseded, overtaken or incomplete record, another
        App's run, a record without the digest, or none, never does."""
        records: dict[str, list[dict[str, Any]]] = {
            "pending": [
                _record(
                    self.current,
                    external_id="pending:41:1",
                    status="in_progress",
                    conclusion=None,
                )
            ],
            "superseded": [
                _record(
                    self.current, external_id="superseded:41:1", conclusion="failure"
                )
            ],
            "overtaken": [
                _record(
                    self.current, external_id="overtaken:41:1", conclusion="failure"
                )
            ],
            "incomplete": [
                _record(
                    self.current, external_id="incomplete:41:1", conclusion="failure"
                )
            ],
            "another App's": [_record(self.current, app=OTHER_APP)],
            "no digest": [_record(None)],
            # A success under an id no verdict carries, which the relay never writes.
            "a success under no verdict's id": [
                _record(self.current, external_id="overtaken:41:1")
            ],
            # A verdict's own id, for a DENY: only a success coalesces.
            "a verdict's DENY": [_record(self.current, conclusion="failure")],
            "none": [],
        }
        for label, runs in records.items():
            with self.subTest(record=label):
                code, written = _select(self._provider(*runs))
                self.assertEqual(0, code)
                self.assertEqual([{"pull_number": 300, "head": HEAD}], written)

    def test_a_moved_head_a_moved_main_or_changed_evidence_never_coalesces(
        self,
    ) -> None:
        """Guard: the commit alone never proves equivalence, nor an equal head under
        another protected revision or other evidence."""
        moved = _Provider(_moved_head())
        moved.records[HEAD] = [_record(self.current)]
        code, written = _select(
            moved,
            "--event",
            "--workflow-run-pulls-json",
            json.dumps([{"number": 300, "head": {"sha": MOVED}}]),
            "--workflow-run-head-sha",
            MOVED,
        )
        self.assertEqual((0, [{"pull_number": 300, "head": MOVED}]), (code, written))
        self.assertEqual(
            (0, [{"pull_number": 300, "head": HEAD}]),
            _select(self._provider(_record(self.current)), revision=MOVED_REVISION),
        )
        for edit in ("failed_check", "unapproved"):
            with self.subTest(edit=edit):
                provider = self._provider(_record(self.current))
                provider.refresh(_changed(**{edit: True}))
                self.assertEqual(
                    (0, [{"pull_number": 300, "head": HEAD}]), _select(provider)
                )

    def test_a_shared_head_never_coalesces(self) -> None:
        """Guard: a success at a head two pull requests share would satisfy both (H1),
        so a shared head is always evaluated."""
        provider = self._provider(_record(self.current))
        replies = _replies()
        pull = replies[f"{API}/pulls/300"][0]
        peer = {
            **copy.deepcopy(pull),
            "number": 301,
            "html_url": "https://github.com/ktogias/gnostoa/pull/301",
        }
        replies[LISTING] = ([copy.deepcopy(pull), peer], {})
        provider.refresh(replies)
        self.assertEqual((0, [{"pull_number": 300, "head": HEAD}]), _select(provider))

    def test_a_guarded_manual_or_scheduled_request_never_coalesces(self) -> None:
        """Guard: the guarded merge's dispatch needs its own record (G1), a manual
        request is the owner's, and the sweep re-reads what no event names."""
        cases = {
            "repository_dispatch": (
                "--workflow-run-pulls-json",
                "null",
                "--pull-number",
                "300",
                "--event",
            ),
            "workflow_dispatch": (
                "--workflow-run-pulls-json",
                "null",
                "--pull-number",
                "300",
            ),
            "schedule": ("--workflow-run-pulls-json", "null"),
        }
        for event_name, arguments in cases.items():
            with self.subTest(event=event_name):
                self.assertEqual(
                    (0, [{"pull_number": 300, "head": HEAD}]),
                    _select(
                        self._provider(_record(self.current)),
                        *arguments,
                        event_name=event_name,
                    ),
                )

    def test_a_selection_that_names_no_event_never_coalesces(self) -> None:
        """Only an event run's selection is routine: one without `--event`, the
        sweep's, never coalesces, whatever event the runner names."""
        self.assertEqual(
            (0, [{"pull_number": 300, "head": HEAD}]),
            _select(
                self._provider(_record(self.current)),
                "--workflow-run-pulls-json",
                "null",
            ),
        )

    def test_an_app_id_in_another_script_s_digits_never_coalesces(self) -> None:
        """Guard: the pinned App's id is a positive ASCII decimal (SonarCloud on #484).
        The same number in another script's digits, which int() would still read,
        names no App, so the request is evaluated."""
        first, *rest = str(MA0_APP)
        # Its first digit is ASCII, so only the decimal pattern's ASCII rule refuses it.
        other_digits = first + "".join(chr(0x0660 + int(digit)) for digit in rest)
        self.assertEqual(
            (0, [{"pull_number": 300, "head": HEAD}]),
            _select(self._provider(_record(self.current)), app_id=other_digits),
        )

    def test_an_unreadable_record_never_coalesces(self) -> None:
        """Guard: a record that cannot be read, or reads back short of its count,
        proves nothing, and the request is evaluated."""
        for flag in ("unreadable", "short"):
            with self.subTest(read=flag):
                provider = self._provider(_record(self.current))
                setattr(provider, flag, True)
                self.assertEqual(
                    (0, [{"pull_number": 300, "head": HEAD}]), _select(provider)
                )


class BurstReproductionTests(unittest.TestCase):
    """The #478 burst replayed: the declared scheduling decides which requests run,
    and each run's selection decides whether it evaluates in full. A run that
    evaluates publishes, as it ends, the record of what it evaluated, superseded
    when the state moved during the evaluation (its verdict's conclusion plays no
    part in what these tests count)."""

    def setUp(self) -> None:
        self.provider = _Provider(_replies())
        self.provider.records[HEAD] = []
        self.evaluated: dict[str, str] = {}
        self.order: list[str] = []
        self.scheduler = _Scheduler(
            _declaration(_workflow().get("concurrency")), on_start=self._started
        )

    def _started(self, name: str) -> None:
        code, written = _select(self.provider)
        if code != 0:
            raise AssertionError(f"selection failed for {name}: exit {code}")
        if written:
            self.evaluated[name] = _state_digest(self.provider.replies)
            self.order.append(name)

    def _ended(self, name: str, *, then: Callable[[], None] | None = None) -> None:
        if name in self.evaluated:
            now = _state_digest(self.provider.replies)
            moved = now != self.evaluated[name]
            self.provider.records[HEAD] = [
                _record(
                    self.evaluated[name],
                    external_id=f"superseded:{len(self.order)}:1"
                    if moved
                    else "e" * 64,
                    conclusion="failure" if moved else "success",
                    run_id=9000 + len(self.order),
                )
            ]
        self.scheduler.finish(name)
        if then is not None:
            then()

    def _drain(self) -> None:
        while self.scheduler.running:
            self._ended(next(iter(self.scheduler.running.values())))

    def test_a_burst_of_equivalent_events_is_evaluated_once(self) -> None:
        """Six equivalent events for #300 while its evaluation runs (reviews, review
        comments, a pull-request event and the verification's completion): one
        evaluation of the latest state, and nothing repeated."""
        self.scheduler.arrive("first", _woken(1))
        kinds = (
            "pull_request_review",
            "pull_request_review_comment",
            "pull_request_review_comment",
            "pull_request",
            "pull_request_review",
        )
        for index, kind in enumerate(kinds, start=2):
            self.scheduler.arrive(f"event{index}", _woken(index, kind=kind))
        self.scheduler.arrive(
            "verification", _woken(9, kind="pull_request", path=VERIFICATION)
        )
        self._drain()
        self.assertEqual(
            ["first"],
            self.order,
            f"{len(self.order)} full evaluations of one unchanged state",
        )

    def test_a_change_during_an_evaluation_is_evaluated_once_more(self) -> None:
        """The owner's approval, then a failed check, arrive during the evaluation of
        an unapproved state: exactly one follow-up, and it evaluates the newest
        state."""
        self.provider.refresh(_changed(unapproved=True))
        self.scheduler.arrive("first", _woken(1))
        self.provider.refresh(_replies())
        self.scheduler.arrive("approval", _woken(2, kind="pull_request_review"))
        self.provider.refresh(_changed(failed_check=True))
        self.scheduler.arrive(
            "failed-check",
            _woken(3, kind="pull_request", path=VERIFICATION, conclusion="failure"),
        )
        self._drain()
        newest = _state_digest(_changed(failed_check=True))
        self.assertEqual(2, len(self.order), f"full evaluations: {self.order}")
        self.assertEqual(newest, self.evaluated[self.order[-1]])


if __name__ == "__main__":
    unittest.main()
