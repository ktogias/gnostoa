from __future__ import annotations

from . import _execution_engine
from .evidence import ATTEST_SCHEMA, parse_input_identity_mapping, sha256_file

# Keep the already verified execution engine byte-stable while routing the
# evidence primitives through the shared trust-domain implementation.
_execution_engine.ATTEST_SCHEMA = ATTEST_SCHEMA
_execution_engine.sha256_file = sha256_file
_execution_engine.parse_input_identity = parse_input_identity_mapping

PROFILE_SCHEMA = _execution_engine.PROFILE_SCHEMA
VALIDATION_SCHEMA = _execution_engine.VALIDATION_SCHEMA
PROBE_SCHEMA = _execution_engine.PROBE_SCHEMA
SMOKE_SCHEMA = _execution_engine.SMOKE_SCHEMA
SIZE_SCHEMA = _execution_engine.SIZE_SCHEMA
RUN_SCHEMA = _execution_engine.RUN_SCHEMA
RunnerError = _execution_engine.RunnerError
ProbeResult = _execution_engine.ProbeResult
main = _execution_engine.main
