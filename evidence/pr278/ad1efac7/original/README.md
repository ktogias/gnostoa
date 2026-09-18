# PR #278 — source-extract review evidence

## Scope and identity

Repository: ktogias/gnostoa, PR #278.
Reviewed source head: `ad1efac7b5d62f2252131483066579728012690c`.
Protected base: `7c14f9111cb560ea26dd68440812f64b37069706`.
Provider event/merge subject: `fb3b19d1b1a01c58d11bc8c88da4e71e5595a1ec`.

This package contains an independent inspection of the downloaded quality artifact
and isolated characterization tests for selected source function bodies. It is
NOT a complete independent checkout test run, Docker run, or ci/verify run.
No repository mutation, publication, merge, or thread resolution was performed.

## Files

- `artifact-audit.json`: downloaded provider artifact identity, summary, limits,
  and independently computed hashes/sizes of the 13 referenced report files.
- `provider-reports/`: original extracted provider-produced report files.
- `characterization.py`: 12 local tests of selected source extracts, with explicit
  stubs for dependencies outside those extracts.
- `characterization-results.json`: actual local execution version and results.

Run the isolated tests on Linux using Python 3.11 or newer:

```sh
python characterization.py
```

The recorded run used Python 3.13.5, not Python 3.11. The script records its actual
interpreter version on every execution. It overwrites characterization-results.json.
It launches and terminates test children, including a real pipe-blocked process.
Fault-injected filesystem operations are not real FUSE/NFS/kernel-hang experiments.

## Recorded observations

All 12 local characterization tests passed. A simulated 80 ms write with a 20 ms
cooperative deadline was rejected only after the write returned. An injected
nonreturning operation remained alive beyond the deadline until an external
supervisor killed it. A real child blocked writing to an undrained stdout pipe
was killed and reaped by the extracted kill-before-wait implementation.

Expected cleanup OSError and RecursionError were sanitized and the root descriptor
was closed. An injected unexpected RuntimeError escaped the known-error protocol;
the root descriptor still closed. This is a defensive exception-boundary gap,
NOT a demonstrated content-controlled payload disclosure vulnerability.

## Informed dispositions

1. Cooperative snapshot deadline: valid, accepted staged limitation; not a hard
   wall-clock bound and not a reason for an unscoped process-worker refactor.
2. CodeAnt abort ordering: the ordering exists, but the asserted pipe deadlock
   is not established because kill precedes bounded wait. Nonblocking lifecycle
   refinement, not demonstrated correctness failure.
3. New CodeRabbit scanner-error report: the described generic report-serialization
   handler is absent. Expected scanner failures are sanitized; unexpected injected
   exceptions reveal a narrower nonblocking robustness gap. A centralized safe
   boundary and sentinel tests would be reasonable hardening, not proof of a
   Major content-driven exploit.
4. Passing an earlier tracked_paths list blindly is not an acceptable one-line
   repair: explicit paths select noncanonical baseline behavior. Preserve canonical
   strictness independently if scope-sharing is redesigned.
5. Cleanup RecursionError/root-descriptor defect: repaired by depth rejection,
   explicit classification, and unconditional root finalization. Successful error
   handling does not prove a failed cleanup physically deleted the workspace.
6. Prior assertion/stub/style/type failures: provider reports no longer exhibit
   those failures. Raw repository-scope errors now have an explicit sanitized
   consumer handler.
7. Current-advisory unavailability: intentionally contained, not restored; the
   restoration obligation remains separate from this PR's containment proof.
8. Omitted Qodo findings: the public summary reports 15 omitted lower-priority
   findings without a complete per-item inventory. No invented individual
   disposition or inference of 15 active bugs is justified.

## Deadline architecture boundary

A supervised worker would need to cover acquisition/preflight as well as copying;
the present timer does not cover root resolution, initial Git enumeration and
validation, workspace creation, or final cleanup. Git enumeration itself has no
explicit timeout/output bound. Candidate file counts and metadata work should
not be confused with the copied-byte limit.

Killing a child does not execute its Python finally blocks. A future design must
specify snapshot ownership, bounded IPC, partial-result rejection, child/process-
group disposition, and cleanup recovery. The parent must not defeat its own timeout
by waiting indefinitely or synchronously cleaning up a stalled filesystem. A bounded
parent decision is not an unconditional guarantee of kernel-level reaping and
physical cleanup on a broken filesystem.

## Primary source references

- https://github.com/ktogias/gnostoa/pull/278
- https://github.com/ktogias/gnostoa/blob/ad1efac7b5d62f2252131483066579728012690c/tools/security_scan.py
- https://github.com/ktogias/gnostoa/blob/ad1efac7b5d62f2252131483066579728012690c/tools/review_current.py
- https://github.com/ktogias/gnostoa/blob/ad1efac7b5d62f2252131483066579728012690c/tools/quality_evidence.py
- https://github.com/ktogias/gnostoa/blob/ad1efac7b5d62f2252131483066579728012690c/tools/repository_scope.py
- https://github.com/ktogias/gnostoa/actions/runs/35373573729
- https://man7.org/linux/man-pages/man2/open.2.html
- https://docs.python.org/3.11/library/subprocess.html
- https://docs.python.org/3.11/library/multiprocessing.html
- https://docs.kernel.org/filesystems/fuse/fuse.html
- https://docs.kernel.org/driver-api/basics.html
