"""The Gnostoa logos are kept as supplied, under the terms and provenance their notice
states (Decision 0111, #397)."""

from __future__ import annotations

import hashlib
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BRAND = ROOT / "docs" / "assets" / "brand"
NOTICE = BRAND / "NOTICE"
# Each logo's SHA-256, as the owner supplied it on 2026-10-08.
LOGOS = {
    "gnostoa-logo.png": "89cf604436eafc89b5f05631111ebc87990b3755da545ad62e2eeaacb3b411a8",  # pragma: allowlist secret -- public asset digest
    "gnostoa-mark.webp": "dee5e5ad3a700c066fb1de2a09a3886ee19340b8035b7c44c9b92cd50140dd3e",  # pragma: allowlist secret -- public asset digest
    "gnostoa-break-glass-logo.png": "514a8000b1a1f7c78e7de77974660268e786506cadc548c7fe6f919a0381883a",  # pragma: allowlist secret -- public asset digest
    "gnostoa-break-glass-mark.png": "fd9ef460533a47aa6f8c3cde0351d72be045a59690ad18274c7bf04a43ceb0c9",  # pragma: allowlist secret -- public asset digest
    # Derived on 2026-10-08, at the owner's choice: the logo on a white tile (#399).
    "gnostoa-logo-on-light.png": "30c13beb92a413721b20044274887a03e82c416c5e7a3c5095945715206c61c5",  # pragma: allowlist secret -- public asset digest
}


# What each file is, as the notice says.
WHAT = {
    "gnostoa-logo.png": "The mark and the wordmark, 1254x1254 PNG.",
    "gnostoa-mark.webp": "The mark alone, WebP; also the icon of the gnostoa-agent App.",
    "gnostoa-break-glass-logo.png": "The break-glass mark with the wordmark, 1254x1254 PNG.",
    "gnostoa-break-glass-mark.png": "The break-glass mark alone, 1254x1254 PNG; also the "
    "icon of the gnostoa-break-glass App.",
    "gnostoa-logo-on-light.png": "The logo on a white tile, 1254x1254 PNG, for dark "
    "backgrounds.",
}
# The notice, paragraph by paragraph, with its whitespace normalised.
NOTICE_TEXT = [
    "GNOSTOA LOGOS",
    "These files are the Gnostoa project's logos. They are not licensed under the "
    "Apache License, which covers the project's other material as LICENSING.md, at "
    "the repository root, describes. All rights in them are reserved by Konstantinos "
    "Togias.",
    "You may use them unmodified to refer to the Gnostoa project, for example in an "
    "article, a list of tools, or a link to this repository. Do not modify them, "
    "combine them with another mark, or use them in a way that suggests endorsement "
    "or affiliation. This notice is not a claim that Gnostoa is a registered "
    "trademark.",
    "FILES",
    *(f"{name} SHA-256 {digest} {WHAT[name]}" for name, digest in LOGOS.items()),
    "PROVENANCE",
    "The four logos the owner supplied on 2026-10-08 (#397), gnostoa-logo.png, "
    "gnostoa-mark.webp, gnostoa-break-glass-logo.png and "
    "gnostoa-break-glass-mark.png, were generated with an AI image tool under the "
    "owner's direction, then chosen and approved by the owner. They are kept byte "
    "for byte as supplied.",
    "gnostoa-logo-on-light.png is derived from gnostoa-logo.png: the same image, "
    "unchanged, on a white tile with rounded corners, for dark backgrounds. The owner "
    "chose it on 2026-10-08 (#399). The terms above apply to it as to the others.",
    "tests/test_brand_assets.py checks each file against the digest above. Decision "
    "0111 records their location, terms and provenance.",
]


class BrandAssetTests(unittest.TestCase):
    def test_each_logo_is_kept_byte_for_byte(self) -> None:
        self.assertEqual(
            sorted([*LOGOS, "NOTICE"]),
            sorted(path.name for path in BRAND.iterdir()),
        )
        for name, digest in LOGOS.items():
            with self.subTest(logo=name):
                content = (BRAND / name).read_bytes()
                self.assertEqual(digest, hashlib.sha256(content).hexdigest())

    def test_the_notice_states_the_terms_provenance_and_digests(self) -> None:
        notice = NOTICE.read_text(encoding="utf-8")
        # Plain text, as the root NOTICE is: no Markdown construct, whether
        # emphasis, code, a table, a heading, a quote, a link or HTML (cubic and
        # CodeAnt on #399).
        for construct in (
            r"\*",
            r"`",
            r"\|",
            r"^ {0,3}#",
            r"^ {0,3}>",
            r"\[[^\]\n]*\]\(",
            r"(?<!\w)_[^_\n]+_(?!\w)",
            r"__",
            r"<[A-Za-z/!]",
        ):
            with self.subTest(construct=construct):
                self.assertIsNone(re.search(construct, notice, re.M))
        # The prose as read, whatever its line breaks.
        prose = " ".join(notice.split())
        # Every term the owner set, so a broader use cannot pass (cubic on #399).
        for term in (
            "not licensed under the Apache License",
            "All rights in them are reserved by Konstantinos Togias.",
            "You may use them unmodified to refer to the Gnostoa project",
            "Do not modify them, combine them with another mark, or use them in a way "
            "that suggests endorsement or affiliation.",
            "This notice is not a claim that Gnostoa is a registered trademark.",
            "generated with an AI image tool under the owner's direction, then "
            "chosen and approved by the owner.",
            # Apache-2.0 covers what LICENSING.md says it covers, which leaves
            # third-party material under its own licenses (Codex on #399).
            "which covers the project's other material as LICENSING.md, at the "
            "repository root, describes.",
            "gnostoa-logo-on-light.png is derived from gnostoa-logo.png: the same "
            "image, unchanged, on a white tile with rounded corners, for dark "
            "backgrounds. The owner chose it on 2026-10-08 (#399).",
        ):
            with self.subTest(term=term):
                self.assertIn(term, prose)
        self.assertNotIn("the repository's other material", prose)
        # Each file's full digest, compared exactly (Sourcery and cubic on #399),
        # as a list, so a repeated entry cannot hide (CodeAnt on #399).
        declared = re.findall(r"^([\w.-]+)\n  SHA-256 ([0-9a-f]{64})$", notice, re.M)
        self.assertEqual(sorted(LOGOS.items()), sorted(declared))
        # Every declaration parses: a malformed one is not skipped (cubic and
        # CodeAnt on #399).
        self.assertEqual(len(declared), notice.count("SHA-256"))

    def test_the_notice_says_exactly_what_the_owner_approved(self) -> None:
        """The notice's whole text, paragraph by paragraph, so that no added
        grant, heading or claim can pass beside the terms (CodeAnt and cubic on
        #399). Changing its terms means changing this test, in review."""
        paragraphs = [
            " ".join(paragraph.split())
            for paragraph in NOTICE.read_text(encoding="utf-8").split("\n\n")
        ]
        self.assertEqual(NOTICE_TEXT, paragraphs)

    def test_licensing_points_to_the_notice(self) -> None:
        licensing = (ROOT / "LICENSING.md").read_text(encoding="utf-8")
        self.assertIn("docs/assets/brand/NOTICE", licensing)

    def test_the_readme_shows_the_logo_under_its_title(self) -> None:
        """The logo follows the `# Gnostoa` title and precedes the first section;
        its alt text names the project where the image cannot load (Sourcery on
        #399)."""
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertTrue(readme.startswith("# Gnostoa\n"))
        head = readme.split("\n## ", 1)[0]
        self.assertEqual(
            [("docs/assets/brand/gnostoa-logo.png", "Gnostoa")],
            re.findall(r'<img src="([^"]+)" alt="([^"]*)"', head),
        )
        # On a dark theme, the logo on its light tile, since the logo's background
        # is transparent and its navy lines vanish there (Codex on #399).
        self.assertEqual(
            ["docs/assets/brand/gnostoa-logo-on-light.png"],
            re.findall(
                r'<source media="\(prefers-color-scheme: dark\)" srcset="([^"]+)">',
                head,
            ),
        )
        for image in ("gnostoa-logo.png", "gnostoa-logo-on-light.png"):
            with self.subTest(image=image):
                self.assertTrue((BRAND / image).is_file())


if __name__ == "__main__":
    unittest.main()
