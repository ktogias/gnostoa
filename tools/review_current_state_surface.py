"""The typed surface the merge-admission guard reads from L1 in process (#389 F1).

The guard (`ci/merge_admission_guard.py`) and L1 (`ci/review_github_current_state.py`)
are flat CI scripts, and the two type checkers name L1 differently: the project's gate
as a top-level module, the protected collector by its path from the root. With their
current invocations, the direct imports tried on #389 each failed in one of them: the
run-time name is `import-not-found` in the collector, and the package path makes the
gate see one file under two module names. The guard therefore imports L1 by its
run-time name, and these protocols are the static contract both checkers share: the
guard's calls are checked against them, and L1 checks its own definitions against
them, so a changed name or signature on either side is a type error in both.
"""

from __future__ import annotations

from typing import Any, Protocol


class Reader(Protocol):
    """What L1's reads take, as L1's own `JsonReader` declares it."""

    def get(self, url: str) -> tuple[Any, dict[str, str]]: ...

    def graphql(self, query: str, variables: dict[str, Any]) -> Any: ...


class ClientFactory(Protocol):
    """L1's client, built from the token alone."""

    def __call__(self, token: str) -> Reader: ...


class SnapshotCollector(Protocol):
    """L1's `collect_snapshot`."""

    def __call__(
        self,
        client: Reader,
        *,
        repository: str,
        pull_number: int,
        observed_at: str | None,
        merge_evidence: bool = False,
    ) -> dict[str, Any]: ...


class OpenPullsReader(Protocol):
    """L1's `open_pulls`."""

    def __call__(self, client: Reader, repository: str) -> list[dict[str, Any]]: ...


class Surface(Protocol):
    """L1's module, as the guard reads it."""

    GitHubRestClient: ClientFactory
    collect_snapshot: SnapshotCollector
    open_pulls: OpenPullsReader
