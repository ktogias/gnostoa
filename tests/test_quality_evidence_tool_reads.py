"""The pinned-tool families' own reads of the candidate's files (#389 H-PYSEC-2; Decision 0122): never through a link,
never waiting on a named pipe. Kept apart from tests/test_quality_evidence_tool_families.py, which is at M13's per-file
patch cap."""

from __future__ import annotations

import os
import threading
from pathlib import Path

from tests.test_quality_evidence_profile import _original
from tests.test_quality_evidence_tool_families import _ToolFamilyFixture


class CandidateReadTests(_ToolFamilyFixture):
    def test_a_shebang_is_never_read_through_a_link_or_from_a_pipe(self) -> None:
        # Revix on #470: staging materialises a tracked link, and the shebang read, before any withholding, followed
        # it: to a file outside the tree, or to a named pipe it then waited on.
        first_line = _original(self.module, "_first_line")
        outside = Path(self.directory.name)
        fifo, script = outside / "pipe", outside / "script"
        os.mkfifo(fifo)
        script.write_bytes(b"#!/bin/sh\n")
        (self.root / "to-script").symlink_to(script)
        (self.root / "to-pipe").symlink_to(fifo)
        (self.root / "plain").write_bytes(b"#!/bin/bash\n")
        self.assertEqual(b"#!/bin/bash\n", first_line(self.root, "plain"))
        with self.subTest("a link to a file outside the tree"):
            self.assertEqual(b"", first_line(self.root, "to-script"))
        with self.subTest("a link to a named pipe"):
            reader = threading.Thread(
                target=first_line, args=(self.root, "to-pipe"), daemon=True
            )
            reader.start()
            reader.join(2)
            blocked = reader.is_alive()
            if blocked:
                os.close(os.open(fifo, os.O_WRONLY | os.O_NONBLOCK))
            self.assertFalse(blocked, "the shebang read waited on a named pipe")
