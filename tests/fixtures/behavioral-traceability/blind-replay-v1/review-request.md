# Blind behavioral-traceability replay

Review only the Requirement, manifest and case files named in the manifest. Do
not inspect the issue, pull request, Decision, tests outside the packet,
assessment, repository history or prior conversation. Treat every case ID and
its ordering as opaque.

First recompute every SHA-256 in the manifest. If any value differs, return only
`INTEGRITY ERROR` with the mismatched paths.

Then assess each case independently from its raw task, candidate patch and
verification result. Do not infer correctness from a passing command, test name
or implementation shape. For each case return:

- `case_id`;
- `applicability`: `REQUIRED` or `NOT APPLICABLE`, with a bounded reason;
- every material behavior derived from the task, each with its source selector;
- candidate coverage for each behavior;
- evidence relation for each behavior: `SUPPORTS`, `CONTRADICTS` or `UNKNOWN`;
- any contradiction, ambiguity, unsupported narrowing or missing evidence;
- `disposition`: `ACCEPT`, `BLOCKED` or `NOT APPLICABLE`; and
- the shortest concrete basis for that disposition.

Finish with limitations of this replay. Do not assign an executor disposition,
invent absent facts or use an expected-answer key.
