"""Which SonarCloud analysis a check run's details URL names (MA0 1b.3c, #424).

SonarCloud posts one GitHub check run per analysis, and a commit carries the runs
of every pull request analysed on it (#394, #395 and #396 share one), so a run is
attributed by the analysis its `details_url` names, never by its commit alone.
This one pure helper does that for the authenticated readback's adapter and the
merge-evidence gate alike (the PAO's Q-a on #424, 6123049205): no second parser.
"""

from __future__ import annotations

import re
import urllib.parse

# SonarCloud's GitHub check run.
CHECK_APP_ID = 12526
CHECK_NAME = "SonarCloud Code Analysis"
_DASHBOARD = ("https", "sonarcloud.io", "/dashboard")
_SCOPES = (["id", "pullRequest"], ["branch", "id"])
# A percent sign that does not begin a two-digit hexadecimal escape.
_BARE_PERCENT = re.compile(r"%(?![0-9A-Fa-f]{2})")


def project_key(repository: str) -> str:
    """SonarCloud's key for an imported GitHub repository, `owner/name`."""

    owner, name = repository.split("/", 1)
    return f"{owner}_{name}"


def details_scope(details: object, *, project: str, pull: str) -> str:
    """ "ours" when ``details`` names this project's pull request; "foreign" when
    it names another pull request, a branch, or another project; "malformed"
    when it names no single analysis of a project, or a blank identity, so the run
    might be anyone's."""

    if not isinstance(details, str):
        return "malformed"
    try:
        parsed = urllib.parse.urlsplit(details)
    except ValueError:
        # An unparsable host, such as an unclosed IPv6 bracket (CodeAnt on #424).
        return "malformed"
    # An identity that cannot be decoded as written is unread, so it names no
    # analysis: a percent sign beginning no escape, or an escape that is not UTF-8
    # (CodeAnt on #424). A well-formed escape is decoded, then matched exactly.
    if _BARE_PERCENT.search(parsed.query):
        return "malformed"
    try:
        query = urllib.parse.parse_qs(
            parsed.query, keep_blank_values=True, errors="strict"
        )
    except UnicodeDecodeError:
        return "malformed"
    if (parsed.scheme, parsed.netloc, parsed.path) != _DASHBOARD or sorted(
        query
    ) not in _SCOPES:
        return "malformed"
    if any(len(values) != 1 for values in query.values()):
        return "malformed"
    # An empty or whitespace-only identity names no analysis, so the run might be
    # anyone's (the PAO on #424, 6123979691). Matching stays exact: nothing is
    # trimmed.
    if any(not values[0].strip() for values in query.values()):
        return "malformed"
    if query == {"id": [project], "pullRequest": [pull]}:
        return "ours"
    return "foreign"
