# Bounded review exchange experiment

This is self-only experimental test code for Work Item #233 and Decision 0063.
It is not a supported Gnostoa CLI, authenticated storage, orchestration service
or protected acceptance gate. A command can run an explicitly supplied worker
argv; the fixture does not sandbox that worker. Only the experiment operator
may supply a qualified command. Candidate/GitHub read-only and account/spend
constraints require separately qualified actual invocation boundaries.

`exchange.py --workspace DIR` supplies `init`, `dispatch`, `collect`, `view`,
`revise` and `disposition`. Each invocation is a separate coordinator process.
An independently supplied roster contains the eligible job IDs and paths to
exact assignment bytes. `init --roster FILE` freezes that input in DIR.
`dispatch --job ID --spec FILE` persists its intent before launching a detached
capture process. The spec contains an explicit `argv`, `normalizer` and bounded
`timeout_seconds`; it may name the qualified worker's `cwd`.

The capture process passes the assignment bytes on stdin and retains native
stdout/stderr before writing a receipt. `collect` normalizes completed captures;
`view` enumerates the frozen roster, including jobs absent from the dispatch
registry. The next coordinator needs only DIR and these commands. Neither
collection nor viewing retries a worker. A missing receipt leaves uncertainty
visible, even if some raw bytes exist. `drop_receipt` is a controlled fault
injection option, not a production recovery strategy.

Original replies and executor dispositions are separate files. Disposition
labels are recorded claims: they do not mechanically resolve a material finding.
Even a current, completely transported set of reviews is not human acceptance.
The output does not claim independent review or real provider portability.

## Replay

From the repository root, preferably inside its development container:

```sh
GNOSTOA_EXCHANGE_IMPLEMENTATION=baseline python -m unittest discover -s tests -p test_review_exchange_fixture.py -v
python -m unittest discover -s tests -p test_review_exchange_fixture.py -v
python tests/fixtures/review_exchange/replay_mutant.py
```

The first and third commands intentionally fail the X04 oracle with one
assertion failure. The middle command must pass eight original controlled cases
and four review regression methods (twelve test methods total).
Infrastructure errors are not the intended RED. Set `GNOSTOA_EXCHANGE_EVIDENCE`
to a writable directory to retain each scenario's files and actual process
observations. The test uses temporary directories otherwise.

The independent oracle includes a CRLF response so parsed JSON equality cannot
substitute for byte fidelity. Its original `NOT_RUN` capture and freeze remain
historical inputs; the assessment owns subsequent observed results. Real tool
response normalizers are optional experimental adapters, not proof that a live
route ran. The full native response always remains inspectable.
