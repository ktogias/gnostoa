"""Isolated characterization of verbatim source extracts from PR #278.

NOT a checkout test run, ci/verify run, Docker test, or real hostile-filesystem
experiment. Imported dependencies outside the selected extracts are deliberately
stubbed. Source head: ad1efac7b5d62f2252131483066579728012690c.
"""
from __future__ import annotations
import errno, io, json, os, pathlib, subprocess, sys, tempfile, time, traceback
import types, unittest
from contextlib import contextmanager, redirect_stderr
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import patch

class SecurityScanError(RuntimeError):
    pass
class ProtectedJudgeUnavailable(RuntimeError):
    pass
class QualityEvidenceError(RuntimeError):
    pass
class LockFormatError(RuntimeError):
    pass

# Verbatim function bodies from tools/security_scan.py, blob ea1256ce819a331a39094c1e909d2ff8a97ff3ec.
def _os_error_symbol(exc: OSError) -> str:
    """Return a closed-set symbolic errno without exception-controlled text."""
    return (
        errno.errorcode.get(exc.errno, "UNKNOWN")
        if type(exc.errno) is int
        else "UNKNOWN"
    )

def _safe_os_error(prefix: str, exc: OSError) -> str:
    return f"{prefix} (OS error: {_os_error_symbol(exc)})"

def _close_snapshot_descriptor(descriptor: int | None, role: str) -> str | None:
    """Close one snapshot descriptor without publishing exception-controlled text."""
    if descriptor is None:
        return None
    try:
        os.close(descriptor)
    except OSError as exc:
        return _safe_os_error(
            f"tracked-tree snapshot {role} descriptor could not be closed", exc
        )
    return None

def _check_snapshot_deadline(deadline: float) -> None:
    """Check cooperative time; a blocked filesystem syscall is not interrupted."""
    if time.monotonic() >= deadline:
        raise SecurityScanError("tracked-tree snapshot timed out")

def _write_all(descriptor: int, content: bytes, *, deadline: float) -> None:
    offset = 0
    while offset < len(content):
        _check_snapshot_deadline(deadline)
        written = os.write(descriptor, content[offset:])
        _check_snapshot_deadline(deadline)
        if written <= 0:
            raise OSError("snapshot write made no progress")
        offset += written

# Dependency used by the following verbatim extract; no candidate copy occurs
# in the empty-list finalization experiments.
_SNAPSHOT_TIMEOUT_SECONDS = 60
_MAX_SNAPSHOT_TOTAL_BYTES = 67_108_864

def _copy_candidate_to_snapshot(*args, **kwargs):
    raise AssertionError("Copy helper is outside this characterization")

def _with_secondary(primary: str, secondary: str | None) -> str:
    return primary if secondary is None else f"{primary}; {secondary}"

@contextmanager
def _immutable_candidate_snapshot(
    root: Path,
    paths: list[Path],
) -> Iterator[Path]:
    nofollow = getattr(os, "O_NOFOLLOW", None)
    directory = getattr(os, "O_DIRECTORY", None)
    if nofollow is None or directory is None:
        raise SecurityScanError(
            "tracked-tree snapshot requires O_NOFOLLOW and O_DIRECTORY"
        )
    try:
        root_descriptor = os.open(root, os.O_RDONLY | directory | nofollow)
    except OSError as exc:
        raise SecurityScanError("cannot open the tracked-tree root safely") from exc
    primary_error: SecurityScanError | None = None
    primary_cause: Exception | None = None
    workspace: tempfile.TemporaryDirectory[str] | None = None
    finalization_issues: list[str] = []
    try:
        workspace = tempfile.TemporaryDirectory(prefix="gnostoa-secret-scan-")
        snapshot = Path(workspace.name)
        deadline = time.monotonic() + _SNAPSHOT_TIMEOUT_SECONDS
        total_bytes = 0
        for relative in paths:
            _check_snapshot_deadline(deadline)
            copied_bytes = _copy_candidate_to_snapshot(
                root_descriptor,
                snapshot,
                relative,
                deadline=deadline,
                remaining_total_bytes=_MAX_SNAPSHOT_TOTAL_BYTES - total_bytes,
            )
            total_bytes += copied_bytes
            _check_snapshot_deadline(deadline)
        _check_snapshot_deadline(deadline)
        yield snapshot
    except SecurityScanError as exc:
        primary_error = exc
    except OSError as exc:
        primary_error = SecurityScanError(
            _safe_os_error("tracked-tree snapshot workspace failed", exc)
        )
        primary_cause = exc
    finally:
        try:
            if workspace is not None:
                try:
                    workspace.cleanup()
                except OSError as exc:
                    finalization_issues.append(
                        _safe_os_error(
                            "tracked-tree snapshot workspace could not be removed", exc
                        )
                    )
                except RecursionError:
                    finalization_issues.append(
                        "tracked-tree snapshot workspace could not be removed "
                        "(recursion limit)"
                    )
        finally:
            close_issue = _close_snapshot_descriptor(root_descriptor, "root")
            if close_issue is not None:
                finalization_issues.append(close_issue)
    secondary = "; ".join(finalization_issues) or None
    if primary_error is not None:
        if secondary is not None:
            raise SecurityScanError(
                _with_secondary(str(primary_error), secondary)
            ) from primary_error
        if primary_cause is not None:
            raise primary_error from primary_cause
        raise primary_error
    if secondary is not None:
        raise SecurityScanError(
            _with_secondary("tracked-tree snapshot finalization failed", secondary)
        )

# Verbatim function body from tools/review_current.py,
# blob b593f2d6312e70f9ce2c127b254509666361cf6c.
_PROCESS_REAP_TIMEOUT_SECONDS = 5

def _kill_and_reap(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is None:
        try:
            process.kill()
        except OSError:
            pass
    try:
        process.wait(timeout=_PROCESS_REAP_TIMEOUT_SECONDS)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ProtectedJudgeUnavailable(
            "protected Docker client reap could not be confirmed within the bound"
        ) from exc

# Verbatim function body from tools/quality_evidence.py,
# blob e7a39775c358cf11c391bb0c3dacd3ce93b45d0b. Parser/collector are test stubs.
def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        summary = collect_quality_evidence(
            args.repository_root,
            args.output_dir,
            coverage_floor=args.coverage_floor,
        )
    except (LockFormatError, QualityEvidenceError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(f"quality evidence: {summary}")
    return 0

def build_parser():
    return types.SimpleNamespace(parse_args=lambda _: types.SimpleNamespace(
        repository_root=Path('.'), output_dir=Path('.'), coverage_floor=65))
def collect_quality_evidence(*args, **kwargs):
    raise AssertionError("Collector is outside this characterization")

OBS = {}
class Characterization(unittest.TestCase):
    def test_expired_deadline_prevents_write(self):
        with patch.object(os, 'write') as writer:
            with self.assertRaises(SecurityScanError):
                _write_all(-1, b'x', deadline=time.monotonic()-1)
            writer.assert_not_called()

    def test_short_writes_are_completed(self):
        seen=[]
        def short(fd, content):
            seen.append(len(content)); return min(2, len(content))
        with patch.object(os,'write',short):
            _write_all(-1,b'abcde',deadline=time.monotonic()+1)
        self.assertEqual(seen,[5,3,1])

    def test_zero_write_is_controlled_failure(self):
        with patch.object(os,'write',return_value=0):
            with self.assertRaisesRegex(OSError,'no progress'):
                _write_all(-1,b'x',deadline=time.monotonic()+1)

    def test_late_write_is_rejected_after_return_not_interrupted(self):
        def late(fd, content):
            time.sleep(.080); return len(content)
        started=time.monotonic()
        with patch.object(os,'write',late):
            with self.assertRaises(SecurityScanError):
                _write_all(-1,b'x',deadline=started+.020)
        elapsed=time.monotonic()-started
        self.assertGreaterEqual(elapsed,.080)
        OBS['late_write']={'deadline_seconds':.020,'elapsed_seconds':elapsed,
                           'result':'REJECTED_AFTER_RETURN'}

    def test_never_returning_injected_write_requires_external_kill(self):
        # Fake stalled operation, not a real filesystem exploit.
        code=r'''import importlib.util,sys,threading,time
s=importlib.util.spec_from_file_location('extract',sys.argv[1]);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
def stalled(fd,data):
    print('ENTERED',flush=True);threading.Event().wait();return len(data)
m.os.write=stalled
m._write_all(-1,b'x',deadline=time.monotonic()+.02)
'''
        p=subprocess.Popen([sys.executable,'-c',code,str(Path(__file__).resolve())],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        try:
            self.assertEqual(p.stdout.readline(),b'ENTERED\n')
            with self.assertRaises(subprocess.TimeoutExpired): p.wait(timeout=.100)
            p.kill();p.wait(timeout=2)
            OBS['stalled_write']={'fake_operation':True,'cooperative_seconds':.020,
                                  'still_running_after_seconds':.100,'external_kill_reaped':True}
        finally:
            if p.poll() is None:p.kill();p.wait(timeout=2)
            p.stdout.close();p.stderr.close()

    def _cleanup_fault(self, fault, body_fault=None):
        closed=[]; real_close=os.close
        def close(fd): closed.append(fd);real_close(fd)
        root=Path(tempfile.mkdtemp(prefix='pr278-characterization-'))
        ws=types.SimpleNamespace(name=str(root),cleanup=lambda: (_ for _ in ()).throw(fault))
        caught=None
        try:
            with patch.object(tempfile,'TemporaryDirectory',return_value=ws),patch.object(os,'close',close):
                try:
                    with _immutable_candidate_snapshot(root,[]):
                        if body_fault is not None: raise body_fault
                except Exception as exc: caught=exc
            self.assertEqual(len(closed),1)
            with self.assertRaises(OSError):os.fstat(closed[0])
        finally:root.rmdir()
        return caught

    def test_cleanup_recursion_keeps_primary_and_closes_root(self):
        exc=self._cleanup_fault(RecursionError('SENTINEL_PRIVATE_TEXT'),SecurityScanError('primary failure'))
        self.assertIsInstance(exc,SecurityScanError)
        self.assertTrue(str(exc).startswith('primary failure;'))
        self.assertIn('recursion limit',str(exc));self.assertNotIn('SENTINEL',str(exc))

    def test_cleanup_oserror_is_sanitized_and_root_closed(self):
        exc=self._cleanup_fault(OSError(errno.EIO,'SENTINEL_PRIVATE_TEXT'))
        self.assertIsInstance(exc,SecurityScanError)
        self.assertIn('EIO',str(exc));self.assertNotIn('SENTINEL',str(exc))

    def test_cleanup_unexpected_runtimeerror_escapes_but_root_closes(self):
        exc=self._cleanup_fault(RuntimeError('SENTINEL_PRIVATE_TEXT'),SecurityScanError('primary failure'))
        self.assertIs(type(exc),RuntimeError)
        self.assertEqual(str(exc),'SENTINEL_PRIVATE_TEXT')
        OBS['unexpected_cleanup_exception']={'fault_injected':True,'root_closed':True,
                                            'escapes_known_error_protocol':True,
                                            'real_content_driven_exploit_proven':False}

    def test_main_known_error_returns_one_without_traceback(self):
        with patch(__name__+'.collect_quality_evidence',side_effect=QualityEvidenceError('safe category')):
            output=io.StringIO()
            with redirect_stderr(output):self.assertEqual(main([]),1)
        self.assertEqual(output.getvalue(),'ERROR: safe category\n')

    def test_main_unexpected_runtimeerror_is_not_serialized_by_generic_handler(self):
        with patch(__name__+'.collect_quality_evidence',side_effect=RuntimeError('SENTINEL_PRIVATE_TEXT')):
            with self.assertRaisesRegex(RuntimeError,'SENTINEL_PRIVATE_TEXT'):main([])

    def test_hostile_errno_int_subclass_is_not_hashed(self):
        class HostileInt(int):
            def __hash__(self):raise RuntimeError('SENTINEL_PRIVATE_TEXT')
        exc=OSError('ignored');exc.errno=HostileInt(5)
        self.assertEqual(_os_error_symbol(exc),'UNKNOWN')

    def test_kill_first_reaps_real_pipe_blocked_child_without_drain(self):
        # The child ignores SIGTERM and blocks filling stdout. Its parent does
        # not drain stdout before invoking the actual extracted kill/reap body.
        code="import os,signal;signal.signal(signal.SIGTERM,signal.SIG_IGN);os.write(2,b'R');os.write(1,b'x'*1048576)"
        p=subprocess.Popen([sys.executable,'-c',code],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        try:
            self.assertEqual(p.stderr.read(1),b'R');time.sleep(.030)
            self.assertIsNone(p.poll())
            started=time.monotonic();_kill_and_reap(p);elapsed=time.monotonic()-started
            self.assertEqual(p.returncode,-9)
            OBS['kill_before_drain']={'real_subprocess':True,'elapsed_seconds':elapsed,
                                     'returncode':p.returncode,'stdout_not_drained':True}
        finally:
            if p.poll() is None:p.kill();p.wait(timeout=2)
            p.stdout.close();p.stderr.close()

if __name__=='__main__':
    stream=io.StringIO()
    result=unittest.TextTestRunner(stream=stream,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Characterization))
    print(stream.getvalue())
    report={'head':'ad1efac7b5d62f2252131483066579728012690c',
            'method':'isolated source-extract characterization; dependencies outside extracts stubbed',
            'python':sys.version,'tests_run':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),
            'observations':OBS,'not_performed':['full checkout tests','ci/verify','Docker execution','real hostile filesystem test']}
    Path(__file__).with_name('characterization-results.json').write_text(json.dumps(report,indent=2)+'\n')
    raise SystemExit(0 if result.wasSuccessful() else 1)
