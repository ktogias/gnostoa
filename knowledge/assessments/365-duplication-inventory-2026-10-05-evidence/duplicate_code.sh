#!/bin/sh
# Detector D of the 2026-10-05 duplication inventory (#365): pylint's
# duplicate-code check, run from the root of an extracted `git archive 4618e1b`.
# It prints the report recorded, gzip-compressed, in duplicate-code.txt.gz.
# pylint 3.3.9 was used.
#
# Only duplicate-code is enabled, so pylint exits 0 with no finding and 8 with
# findings. Any other status means the detector did not run, and must not pass for a
# clean result (Codex on #375).
set -eu
python -m pylint --version | head -1
status=0
python -m pylint --disable=all --enable=duplicate-code --min-similarity-lines=10 \
  --ignore-imports=y --ignore-docstrings=y --ignore-comments=y \
  tools ci tasks .github || status=$?
case "$status" in
  0 | 8) exit 0 ;;
  *) echo "duplicate-code: pylint exited $status; the detector did not run" >&2; exit "$status" ;;
esac
