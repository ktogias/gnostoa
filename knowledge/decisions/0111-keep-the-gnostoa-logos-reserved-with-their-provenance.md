---
type: Decision
title: Keep the Gnostoa logos reserved, with their provenance
description: The four Gnostoa logos live in docs/assets/brand/ byte for byte as the owner supplied them. They are not licensed under Apache-2.0; a notice beside them reserves them, permits unmodified reference to the project, records their AI-assisted provenance and their digests, and LICENSING.md points to it. The README shows the logo.
status: draft
generated:
  by: anthropic/claude-opus-5-5
  at: "2026-10-08T02:15:00Z"
sources:
  - id: work-item
    resource: https://github.com/ktogias/gnostoa/issues/397
    title: Add the Gnostoa logos, reserved as marks, with their provenance
  - id: licensing
    resource: ../../LICENSING.md
    title: Unless a file states otherwise, Apache-2.0; Section 6 grants no right to the name or logos
x-project-knowledge:
  id: kit.decision.0111.keep-the-gnostoa-logos-reserved-with-their-provenance
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
---

# Keep the Gnostoa logos reserved, with their provenance

## Context

On 2026-10-08 the owner supplied four Gnostoa logos:
- the mark with the wordmark;
- the mark alone;
- a break-glass variant of each, for the emergency merge App.

The owner asked to add them to the repository. Two of them are also the icons of the
`gnostoa-agent` and `gnostoa-break-glass` Apps (#15).

`LICENSING.md` makes the repository's material Apache-2.0 "unless a file states
otherwise". It notes that Section 6 grants no right to the name or logos.

## Decision

1. **Location.** The logos live in `docs/assets/brand/`, byte for byte as supplied:
   - `gnostoa-logo.png`;
   - `gnostoa-mark.webp`;
   - `gnostoa-break-glass-logo.png`;
   - `gnostoa-break-glass-mark.png`;
   - `gnostoa-logo-on-light.png`, derived (item 8).
2. **Terms (the owner's choice).** The logo files are not licensed under
   Apache-2.0, and all rights in them are reserved. Anyone may use them unmodified to
   refer to the Gnostoa project, without implying endorsement. A notice beside them,
   `docs/assets/brand/NOTICE`, says so, and `LICENSING.md` points to it. Neither
   claims that `Gnostoa` is a registered trademark.
3. **Provenance (the owner's statement).** The logos were generated with an AI image
   tool under the owner's direction, then chosen and approved by the owner. The
   notice records this, with each file's full SHA-256.
4. **Integrity.** `tests/test_brand_assets.py` checks:
   - each file against its full SHA-256;
   - that the directory holds nothing else;
   - that the notice states every term and the provenance, and records each full
     digest exactly;
   - that `LICENSING.md` points to the notice;
   - that the README's logo resolves, under the title and before the first section.
5. **Use.** The README shows `gnostoa-logo.png` under its `# Gnostoa` heading, which the brand-identity test requires to come first. On a dark theme it shows `gnostoa-logo-on-light.png` instead, through `<picture>`. Its alt text, `Gnostoa`, names the project wherever the image cannot load.
6. **The notice is plain text**, as the root `NOTICE` is, because every Markdown file under `docs/` is a navigation projection of canonical knowledge. It holds no Markdown markers.
7. **The distributions do not carry the logos.** The source distribution and the
   wheel declare `license = "Apache-2.0"`, with `LICENSE` and `NOTICE` as their
   license files. Shipping reserved files in them would make that declaration
   untrue. So the unpacked source distribution's README shows the alt text in place
   of the logo (Greptile on #399). PyPI renders no README, because the project
   declares no `readme` metadata.

8. **The dark-theme tile (the owner's choice, #399).** `gnostoa-logo.png` has a
   transparent background, so its navy lines vanish on a dark page (Codex on #399),
   and GitHub strips inline styles. `gnostoa-logo-on-light.png` is that image,
   unchanged, on a white tile with rounded corners. It was made with Pillow 12.3.0:
   a white 1254×1254 image whose alpha is a rounded rectangle of radius 156
   (`width // 8`), alpha-composited under the logo. None of the logo's opaque pixels
   changed. The notice records it as derived, and its terms are the others'.

## Consequences

- The logos are versioned with the project, and their terms are explicit wherever
  the repository is copied.
- They add about 1.5 MB to the tracked tree, and so to the runtime image's source
  payload.
- Replacing a logo is a change through this Decision: a new file, a new digest, and
  the owner's provenance statement.

## Alternatives not chosen

- **Apache-2.0 for the logo files:** the owner chose to reserve them.
- **Vector (SVG) sources:** none were supplied. Adding them later is a separate
  change.
- **A trademark registration or a full trademark-use policy:** out of scope (#397).
- **The logos in the source distribution:** this would need a license expression
  beyond `Apache-2.0` for the archive; see item 7.
