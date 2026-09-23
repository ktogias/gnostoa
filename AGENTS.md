# Gnostoa agent router

Start with `README.md`. Load only the route required by the task.

- Core profile, schemas, validators, templates or CI: read
  `knowledge/contracts/public-inheritance-surface.md` and
  `knowledge/runbooks/maintain-the-kit.md`.
- Reusable workflow or practice: route through `guidance/index.md`.
- CI policy, provider adapters or hooks: read
  `guidance/workflows/configure-continuous-integration.md`.
- Toolkit architecture or rationale: route through `knowledge/index.md`.
- Gnostoa self-hosted delivery, workflow, governance, evidence or control
  capability evolution: after this README, read the compact, source-bound
  [`tasks/issue-14-orientation.md`](tasks/issue-14-orientation.md) for the current
  item and next action. Treat a `STALE`, `INCOMPLETE`, `CONFLICTING` or
  `OVER_BUDGET` status as a stop before relying on its current-state claims.
  Do not trust an embedded `CURRENT` status after its declared freshness window
  has expired, or after a newer integrated/provider event has superseded its
  observed subject: treat the view as stale and perform fresh provider/read-back
  orientation before naming current or next work. When the selected work or its
  successor is provider-authoritative, perform fresh provider read-back even if
  the embedded `CURRENT` freshness window has not expired. At minimum, read the
  provider's open `roadmap:now` selection (zero is valid; more than one is
  conflicting) and the protected `main` head/latest integration identity, then
  reconcile those exact identities with the retained view's selected work,
  observed subject and observation time. If that read-back is unavailable,
  ambiguous or disagrees, do not name current or next work: treat the view as
  blocked/stale and stop. In a status or “what now?” answer, report the exact
  provider selection (or verified absence) and protected-main identity used for
  that reconciliation. For every such answer, state the selected objective and
  the latest integrated slice's unresolved invariant before choosing a successor.
  A generic roadmap ordering must not demote a capability-specific mandatory
  successor when the selected objective depends on that capability.
  For a status or “what now?” request, stop there after that reconciliation when
  the resulting view is current unless one of its source links is needed to answer
  a named question. Before proposing or implementing a change, continue with
  `knowledge/lifecycles/evidence-gated-capability-evolution.md`,
  `knowledge/runbooks/deliver-bounded-self-hosted-slice.md`, Decision 0016,
  the current roadmap and the active Work Item before proposing implementation.
- When the Requirement's applicability criteria hold for Gnostoa-self work,
  also read
  `knowledge/requirements/bounded-behavioral-traceability.md` before semantic
  production mutation and exact-candidate review.
- When agent reviews are supplied for Gnostoa-self work, whether the owner
  forwards them or we commission them, follow
  [supplied-agent review capture](knowledge/runbooks/deliver-bounded-self-hosted-slice.md#supplied-agent-reviews).
- Gnostoa version-bound source-and-OCI release series: after the ordinary
  self-hosted route, read
  `knowledge/runbooks/publish-version-bound-source-and-oci-release.md`.
- Anonymous examples: use only generic vocabulary and never treat examples as
  approved project facts.

Before creating or materially revising a Gnostoa-self Issue, Decision or PR, and
before new code or implementation, apply **Prior-art and reuse checkpoint** in
`knowledge/runbooks/deliver-bounded-self-hosted-slice.md`. Reuse applicable
research; record alternatives, intended-use license compatibility and the
remaining need before choosing custom work.

Before changing normative behavior, read
`guidance/guardrails/non-negotiable.md` and update
`policy/guardrails.yaml` when coverage changes. Generated content starts as
draft. Stable concepts require a `human:` verifier. Preserve provenance and
keep executable artifacts canonical in their native formats.

Classify every change through
`guidance/workflows/propose-review-merge-change.md` and
`policy/change-control.yaml`. Agents may author changes and evidence, but never
self-approve where independent approval is required, bypass controls or replace
required human semantic review.
For this repository, every normal, normative or critical change requires a
linked Work Item and Decision before implementation; an emergency supplies them
in its mandatory follow-up.

For any **unadmitted finding** produced by a retrospective, experiment,
evaluation, review, incident analysis or comparable learning surface, read
`knowledge/requirements/retrospective-findings-require-explicit-admission.md`
and stop before implementing the finding. Read provider state first and resume
the existing same-purpose Work Item when one already owns the outcome; otherwise
create a **focused tracked Work Item** with a desired outcome, bounded acceptance
criteria, scope boundary and explicit admission condition. Issue creation is
backlog capture, not implementation admission. Do not create a branch, Pull
Request or source mutation for that finding until a separate owner/admission step
selects it under the current classification, Decision, evidence and effect
boundary. A non-actionable lesson may remain knowledge-only until its admission
condition occurs.

Before implementation, follow
`guidance/workflows/develop-verification-first.md`; record expected behavior and
establish the applicable failing or characterization evidence before editing.
Mechanical changes and emergency follow-up use the timing declared by
`policy/change-control.yaml`.

Before creating or pushing a candidate that changes Python source or Python
verification surfaces, use the pre-candidate preparation boundary from the
recommended Development Container defined by `.devcontainer/devcontainer.json`.
That route provides a writable workspace mount and remaps the container user to
the checkout owner; do not reuse the read-only one-shot verification container
shown later in this file for preparation. A direct host invocation is a native
fallback only when the container route is unavailable; record that reason.

The preparation authority must come from the exact bound parent, never from the
editable candidate checkout. Retrieve the parent wrapper before executing it;
the retrieval itself is part of the trust boundary, so it must use trusted
system executable lookup, scrub caller Git routing/configuration, disable Git
replacement objects, and check `git show` success instead of piping directly
into a shell. Use this bootstrap at the start of each prepare/verify/release
shell session:

```bash
parent=<exact-40-character-parent-sha>
if [ "${#parent}" -ne 40 ]; then
  echo "ERROR: parent must be an exact 40-character commit SHA" >&2
  exit 2
fi
case "${parent}" in
  *[!0-9a-f]*)
    echo "ERROR: parent must be an exact 40-character commit SHA" >&2
    exit 2
    ;;
esac

PATH=/usr/local/bin:/usr/bin:/bin:/opt/homebrew/bin
export PATH
git_executable="$(command -v git || true)"
mktemp_executable="$(command -v mktemp || true)"
if [ -z "${git_executable}" ] || [ -z "${mktemp_executable}" ]; then
  echo "ERROR: trusted wrapper-retrieval executables are unavailable" >&2
  exit 2
fi

parent_wrapper="$("${mktemp_executable}" /tmp/gnostoa-parent-wrapper.XXXXXX)"
trap 'rm -f -- "$parent_wrapper"' EXIT HUP INT TERM
if ! (
  unset GIT_DIR GIT_WORK_TREE GIT_COMMON_DIR GIT_OBJECT_DIRECTORY
  unset GIT_ALTERNATE_OBJECT_DIRECTORIES GIT_INDEX_FILE GIT_CEILING_DIRECTORIES
  unset GIT_DISCOVERY_ACROSS_FILESYSTEM GIT_CONFIG GIT_CONFIG_PARAMETERS
  unset GIT_EXTERNAL_DIFF GIT_TEMPLATE_DIR GIT_REPLACE_REF_BASE
  export GIT_CONFIG_COUNT=0
  export GIT_CONFIG_GLOBAL=/dev/null
  export GIT_CONFIG_SYSTEM=/dev/null
  export GIT_CONFIG_NOSYSTEM=1
  export GIT_ATTR_NOSYSTEM=1
  export GIT_NO_REPLACE_OBJECTS=1
  "${git_executable}" -c core.hooksPath=/dev/null \
    show "${parent}:ci/prepare-candidate"
) > "${parent_wrapper}"; then
  echo "ERROR: unable to retrieve exact-parent preparation wrapper" >&2
  exit 2
fi

sh "${parent_wrapper}" prepare \
  --parent "${parent}" \
  --receipt <new-path-outside-the-worktree> \
  --focused-profile fast
```

The retrieved wrapper then restricts executable lookup again, scrubs inherited
Git/Python routing, disables Git replacement objects, and runs the extracted
parent `tools/candidate_prepare.py` with isolated Python (`-I`).

If the bound parent does not contain this authority, no trusted preparation
receipt can be issued through this route; authority evolution/bootstrap must be
handled by its separately admitted path rather than executing candidate bytes.
When the documented host fallback needs a virtualenv or other trusted
interpreter environment with Ruff installed, pass
`--trusted-python /absolute/path/to/python`. The wrapper validates both the
resolved target and resolved containing directory outside the repository
worktree, then invokes the supplied leaf through that validated directory so
virtualenv discovery is preserved while still launching with isolated mode
(`-I`); it never reopens caller `PATH` or user-site packages.

Preparation captures the proposed delta through disposable Git metadata with
trusted local configuration. Git object reads/writes are bound explicitly to
the source content-addressed object store so the verified prepared-tree identity
survives the disposable metadata. The source `.git/info/exclude` and the caller's effective `core.excludesFile`
patterns are snapshotted once into that metadata so ignored scratch/secrets
remain excluded without retaining caller Git configuration. Disposable Git
metadata is initialized with an explicitly empty trusted template, and inherited
`GIT_TEMPLATE_DIR` is ignored. Candidate staging, checkout and verification no
longer consume the mutable source `.git/config`, caller global/system config or
caller Git templates after admission, so concurrent or inherited Git configuration
cannot inject filters into preparation. The source worktree is captured twice from the
same exact parent; mismatched trees/path sets or any source-HEAD movement fail
closed. The path rejects candidate changes to `ci/prepare-candidate`,
`ci/style`, `ci/verify`, `tools/candidate_prepare.py`, or any
`pyproject.toml`/`ruff.toml`/`.ruff.toml` unless authority evolution is
separately admitted. It materializes the exact proposed tree into a disposable
workspace and runs `ci/style --fix` with unsafe Python path injection disabled.
The active interpreter's unresolved directory stays first on `PATH`, preserving
a virtualenv's Python/Ruff installation while preventing a candidate
`ruff.py`/`ruff` package from shadowing it.
It restores the normalized tree, then runs the allowlisted
`ci/verify` profile under a separate scrubbed Python environment: inherited
`PYTHONPATH`/`PYTHONHOME`/user-site state and arbitrary executable search
paths are excluded, while the isolated candidate workspace remains intentionally
importable for candidate tests. Focused verification has a 900-second deadline
and bounded retained stdout/stderr; cleanup terminates the full
preparation-owned process group on success, timeout, or collection failure.
Focused candidate code runs with separate disposable Git metadata/worktree; all
post-focused mutation/style evidence is rebuilt from trusted normalization
metadata, so candidate-controlled index/config/skip-worktree state cannot hide a
mutation. A preparation-owned `knowledge` shim precedes
the executable search path and executes `python -m tools.cli` from that workspace;
`KNOWLEDGE_KIT_ROOT` is rebound to the isolated workspace and its revision label
is reset to `development`, so installed-image or source-worktree toolkit routing
cannot satisfy a focused receipt. Final `ci/style --check` returns to the stricter
safe-path style environment. Source-worktree-only
ignored/untracked files and concurrent caller edits are not part of verification. Candidate symlinks are rejected
before style or focused verification because this bounded contract does not
admit external target chains. The CLI never accepts an executable or arbitrary
verification arguments; supported profiles are `policy`,
`security-fast`, `fast`, `regression`, `smoke`, and `extended`.

The preparation command prints a JSON receipt object containing
`receipt_sha256` and a receipt-unique namespaced `retention_ref`; retain the
digest identity outside the receipt bytes in the trusted preparation handoff.
Each receipt gets its own
`refs/gnostoa/prepared/<parent>/<tree>/<nonce>` GC root, so releasing one
receipt cannot unroot another receipt for the same tree. The ref keeps the
prepared tree reachable until publication or explicit receipt expiry. The digest is integrity
evidence, not producer authentication or bearer authority. To inspect/consume a
receipt, supply the separately retained identity:

After the trusted exact-parent wrapper retrieval above has populated
`parent_wrapper` for this `parent`:

```bash
sh "${parent_wrapper}" verify \
  --parent "${parent}" \
  --tree <exact-40-character-prepared-tree-sha> \
  --receipt <path-outside-the-worktree> \
  --receipt-sha256 <trusted-sha256-from-prepare>
```

A self-consistent receipt with a caller-chosen digest must never authorize a
provider write. After publication or explicit receipt expiry, release the exact
retained tree only through:

After performing the same trusted exact-parent wrapper retrieval for this
`parent`:

```bash
sh "${parent_wrapper}" release \
  --parent "${parent}" \
  --tree <exact-40-character-prepared-tree-sha> \
  --receipt <path-outside-the-worktree> \
  --receipt-sha256 <trusted-sha256-from-prepare>
```

This slice intentionally has no provider-write adapter; Git-data or API ref
effects remain governed by #15/#308 and must run trusted preparation or consume
separately authenticated preparation provenance before writing.
Ordinary hooks remain advisory early feedback; direct `ci/style --fix` alone
is not a preparation receipt for non-hook authoring.
Provider CI stays check-only
and remains the non-bypassable verifier.

After PR #272 is integrated, record any potentially eligible candidate before
fresh external review with an unedited top-level comment whose first line is
`Exact review candidate: <40-character commit SHA>`. When assessing whether the
repository-root Ruff gate adds value, use the pre-registered cohort, receipts,
attribution rules, metrics and outcome rule in
[Decision 0081](knowledge/decisions/0081-make-repository-root-ruff-scope-authoritative-before-candidate-sealing.md#post-integration-effectiveness-assessment)
and write the required per-PR evidence table and result to
`knowledge/assessments/0081-repository-root-ruff-effectiveness-result.md`. Green
CI establishes candidate correctness, not effectiveness by itself.

Before completion, run the applicable suites in the development container by
default:

```bash
candidate_ref="${GNOSTOA_CANDIDATE_REF:-working-tree}"
docker build --target development --build-arg VCS_REF="${candidate_ref}" \
  --tag gnostoa:development-checkout .
docker run --rm --mount type=bind,source="$PWD",target=/workspace,readonly \
  --workdir /workspace --env KNOWLEDGE_KIT_ROOT=/workspace \
  --env KNOWLEDGE_KIT_REVISION="${candidate_ref}" --env PYTHONPATH=/workspace \
  gnostoa:development-checkout ./ci/verify extended
```

Replace `extended` with each required named suite. Use the native commands
below only as an explicit restricted-environment or parity fallback, and state
why the container route was not used:

```bash
python -m unittest discover -s tests -v
python -m tools.validate_bundle --profile guidance/profile.yaml --bundle guidance
python -m tools.validate_bundle --profile knowledge/profile.yaml --bundle knowledge
python -m tools.check_guardrails
python -m tools.check_change_policy
python -m tools.check_ci_policy --policy policy/continuous-integration.yaml --verification policy/verification.yaml
```

For runtime, distribution or CI changes, also build the `runtime` container
target and run `knowledge self-check` inside it.
