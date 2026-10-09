"""The Markdown parser joins the runtime (Decision 0113; #407, #413).

The pins are checked as Decision 0109 checked `unittest-parallel`'s: the runtime
lock carries the development lock's reviewed hashes. The property tests run every
case #413's review rounds found through the locked parser. Each is code, an HTML
block or a comment, never a list item, which is what the change-control reader
will rely on.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

from markdown_it import MarkdownIt

ROOT = Path(__file__).resolve().parents[1]
PINS = {
    "markdown-it-py": "4.2.0",
    "mdurl": "0.1.2",
}
FIELD = "- Work Item: #999"


def _entry(lock: str, name: str, version: str) -> str:
    """One lock entry: the pin line and its hash lines."""

    match = re.search(
        rf"^{re.escape(name)}=={re.escape(version)} \\\n((?:    --hash=sha256:[0-9a-f]{{64}}(?: \\)?\n)+)",
        lock,
        re.MULTILINE,
    )
    if match is None:
        raise AssertionError(f"{name}=={version} is not pinned")
    return match.group(0)


def _list_item_texts(markdown: str) -> list[str]:
    """The inline text of every list item the parser finds."""

    tokens = MarkdownIt("commonmark").parse(markdown)
    texts, depth = [], 0
    for token in tokens:
        if token.type == "list_item_open":
            depth += 1
        elif token.type == "list_item_close":
            depth -= 1
        elif depth and token.type == "inline":
            texts.append(token.content)
    return texts


class PinTests(unittest.TestCase):
    def test_the_runtime_lock_pins_the_parser_with_the_reviewed_hashes(self) -> None:
        runtime = (ROOT / "requirements" / "runtime.lock").read_text(encoding="utf-8")
        development = (ROOT / "requirements" / "development.lock").read_text(
            encoding="utf-8"
        )
        for name, version in PINS.items():
            with self.subTest(name=name):
                self.assertEqual(
                    _entry(development, name, version), _entry(runtime, name, version)
                )

    def test_the_project_declares_the_parser(self) -> None:
        pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        self.assertIn('"markdown-it-py>=4.2,<5",', pyproject)


class CommonMarkPropertyTests(unittest.TestCase):
    """Each case one of #413's rounds found: GitHub renders it as code, or hides
    it, so its lines must not reach the reader as list items."""

    def test_a_real_field_is_a_list_item(self) -> None:
        self.assertEqual(["Work Item: #999"], _list_item_texts(FIELD + "\n"))

    def test_code_html_and_comments_are_never_list_items(self) -> None:
        cases = {
            "fence": f"```\n{FIELD}\n```\n",
            "indented fence": f"  ```\n{FIELD}\n  ```\n",
            "long fence with a shorter inner marker": f"````\n```\n{FIELD}\n````\n",
            "mixed markers": f"~~~\n```\n{FIELD}\n~~~\n",
            "unclosed fence": f"```\n{FIELD}\n",
            "indented code block": f"    {FIELD}\n",
            "pre block": f"<pre>\n{FIELD}\n</pre>\n",
            "div block": f"<div>\n{FIELD}\n</div>\n",
            "comment": f"<!--\n{FIELD}\n-->\n",
            "unclosed comment": f"<!--\n{FIELD}\n",
            "fence straddling a comment": f"```\n<!--\n```\n{FIELD}\n-->\n",
        }
        for name, markdown in cases.items():
            with self.subTest(name):
                self.assertNotIn("Work Item: #999", _list_item_texts(markdown))

    def test_a_comment_delimiter_in_a_code_span_is_text(self) -> None:
        """cubic on #413: `<!--` inside backticks opens no comment."""
        markdown = f"Write `<!--` to open a comment.\n\n{FIELD}\n"
        self.assertEqual(["Work Item: #999"], _list_item_texts(markdown))


if __name__ == "__main__":
    unittest.main()
