"""Which SonarCloud analysis a check run's details URL names (MA0 1b.3c, #424).

SonarCloud posts one GitHub check run per analysis, and a commit carries the runs
of every pull request analysed on it (#394, #395 and #396 share one), so a run is
attributed by the analysis its `details_url` names, never by its commit alone.
This one pure helper does that for the authenticated readback's adapter and the
merge-evidence gate alike (the PAO's Q-a on #424, 6123049205): no second parser.
"""

from __future__ import annotations

import urllib.parse

# SonarCloud's GitHub check run.
CHECK_APP_ID = 12526
CHECK_NAME = "SonarCloud Code Analysis"
_DASHBOARD = ("https", "sonarcloud.io", "/dashboard")
_SCOPES = (["id", "pullRequest"], ["branch", "id"])


def project_key(repository: str) -> str:
    """SonarCloud's key for an imported GitHub repository, `owner/name`."""

    owner, name = repository.split("/", 1)
    return f"{owner}_{name}"


def details_scope(details: object, *, project: str, pull: str) -> str:
    """ "ours" when ``details`` names this project's pull request; "foreign" when
    it names another pull request, a branch, or another project; "malformed"
    when it names no single analysis of a project, so the run might be anyone's."""

    if not isinstance(details, str):
        return "malformed"
    try:
        parsed = urllib.parse.urlsplit(details)
    except ValueError:
        # An unparsable host, such as an unclosed IPv6 bracket (CodeAnt on #424).
        return "malformed"
    query = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)
    if (parsed.scheme, parsed.netloc, parsed.path) != _DASHBOARD or sorted(
        query
    ) not in _SCOPES:
        return "malformed"
    if any(len(values) != 1 for values in query.values()):
        return "malformed"
    if query == {"id": [project], "pullRequest": [pull]}:
        return "ours"
    return "foreign"
