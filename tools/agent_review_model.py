"""The agent review pipeline's subject vocabulary (Decisions 0086 and 0100).

A review subject names what is reviewed in terms every provider can supply: which
provider and adapter answered, an opaque repository, the item the request was made
on, the change request when there is one, and the exact head and base commits. Kinds
and ids are opaque strings that the adapter chooses, so a provider whose ids are not
numbers, or whose change requests have another name, needs no change here.

NamedTuples rather than dataclasses: the repository's test harness imports the
pipeline's entrypoints by path without registering them in `sys.modules`, and a
dataclass with postponed annotations resolves its module through `sys.modules`.
"""

from __future__ import annotations

from typing import NamedTuple

# A wrapped line's continuation begins with this byte, for every reader-facing
# artefact. It never begins a line of unified diff output, so a continuation cannot
# read as a deletion, an addition or a header; one marker for every artefact means a
# reader learns one convention.
CONTINUATION = b">"


class Provider(NamedTuple):
    """Which provider answered, and which adapter translated its answer."""

    id: str
    adapter: str


class Ref(NamedTuple):
    """An item or change request, as the provider names it."""

    kind: str
    id: str


class ReviewSubject(NamedTuple):
    """What one review is of. Every field is the provider's answer, never a relay's."""

    provider: Provider
    repository: str
    item: Ref
    # None when the request concerns the item itself rather than a change.
    change_request: Ref | None
    head_commit: str
    base_commit: str
