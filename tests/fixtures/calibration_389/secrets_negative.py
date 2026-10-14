"""#389 F3 calibration fixture (never merged): the same selectors built from names, as
the 2bcb622 fix built them; DeepSource and Codacy reported nothing there."""

from __future__ import annotations


def forwarding(**secrets: str) -> dict[str, str]:
    return dict(secrets)


def _selector(name: str) -> str:
    return f"${{{{ secrets.{name} }}}}"


A_WRONG_SELECTOR = forwarding(DEEPSOURCE_API_TOKEN=_selector("CODACY_API_TOKEN"))
AN_EXTRA_SECRET = forwarding(ANOTHER_TOKEN=_selector("ANOTHER_TOKEN"))
