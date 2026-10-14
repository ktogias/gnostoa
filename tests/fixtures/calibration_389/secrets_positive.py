"""#389 F3 calibration fixture (never merged): the two d90c612 literal shapes DeepSource
reported as SCT-A000 and Codacy as Bandit_B106. They name secrets; they hold none."""

from __future__ import annotations


def forwarding(**secrets: str) -> dict[str, str]:
    return dict(secrets)


A_WRONG_SELECTOR = forwarding(DEEPSOURCE_API_TOKEN="${{ secrets.CODACY_API_TOKEN }}")
AN_EXTRA_SECRET = forwarding(ANOTHER_TOKEN="${{ secrets.ANOTHER_TOKEN }}")
