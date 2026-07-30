## Outcome

<!-- State the observable result, not the implementation activity. -->

## Change control

- Class: `mechanical | normal | normative | critical | emergency`
- Work Item:
- Decision:
- Accountable owner:

## Why and scope

<!-- Explain the problem, boundaries and explicit non-goals. Do not duplicate the linked Work Item. -->

## Impact

- Public contract or compatibility:
- Knowledge or documentation:
- Security, runtime or operations:
- CI policy, capabilities or suite mapping:
- Migration or rollback:

## Verification

### Verification strategy

- Expected behavior:
- Pre-change failure evidence:
- Automated test level:
- Human semantic evidence:
- Exact commands:
- Test-first exception: `none | mechanical | exploratory | emergency`
- Exception rationale and follow-up:

- [ ] Required checks pass.
- [ ] Required checks belong to the latest merge-candidate revision.
- [ ] CI policy and verification manifest validate.
- [ ] New or changed tests would fail when the intended behavior is broken.
- [ ] Tests assert observable behavior rather than implementation details.
- [ ] Required tests are deterministic and non-flaky.
- [ ] Contracts, tests and canonical knowledge are synchronized.
- [ ] Required Work Item and Decision are linked.
- [ ] Required independent human/CODEOWNER approvals are present.
- [ ] Review conversations are resolved or deferred through a linked Work Item.
