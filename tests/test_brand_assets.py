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
}


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
        # The prose as read, whatever its line breaks and emphasis.
        prose = " ".join(notice.replace("*", "").split())
        self.assertIn("not licensed under the Apache License", prose)
        self.assertIn("refer to the Gnostoa project", prose)
        self.assertIn("generated with an AI image tool", prose)
        declared = dict(
            re.findall(r"^\| `([\w.-]+)` \| `([0-9a-f]{16})…` \|", notice, re.M)
        )
        self.assertEqual(sorted(LOGOS), sorted(declared))
        for name, digest in LOGOS.items():
            with self.subTest(logo=name):
                self.assertTrue(digest.startswith(declared[name]))

    def test_licensing_points_to_the_notice(self) -> None:
        licensing = (ROOT / "LICENSING.md").read_text(encoding="utf-8")
        self.assertIn("docs/assets/brand/NOTICE", licensing)

    def test_the_readme_shows_the_logo(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        images = re.findall(r'<img src="([^"]+)"', readme.split("\n## ", 1)[0])
        self.assertIn("docs/assets/brand/gnostoa-logo.png", images)
        for image in images:
            with self.subTest(image=image):
                self.assertTrue((ROOT / image).is_file())


if __name__ == "__main__":
    unittest.main()
