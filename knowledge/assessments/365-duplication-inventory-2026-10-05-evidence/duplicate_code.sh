#!/bin/sh
# Detector D of the 2026-10-05 duplication inventory (#365): pylint's
# duplicate-code check, run from the root of an extracted `git archive 4618e1b`.
# It prints the report recorded, gzip-compressed, in duplicate-code.txt.gz.
# pylint 3.3.9 was used.
set -eu
python -m pylint --version | head -1
python -m pylint --disable=all --enable=duplicate-code --min-similarity-lines=10 \
  --ignore-imports=y --ignore-docstrings=y --ignore-comments=y \
  tools ci tasks .github || true
