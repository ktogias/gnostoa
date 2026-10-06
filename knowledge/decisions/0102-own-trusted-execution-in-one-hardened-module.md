---
type: Decision
title: Own trusted execution in one hardened module, and refuse new copies
description: Gather every implementation of trusted executable resolution, isolated Git environments, disposable Git metadata, tree materialization and authority execution into one hardened owner that every caller imports. Then refuse new copies through a responsibility registry, a deterministic reuse check and routing hooks.
status: draft
generated:
  by: anthropic/claude-opus-5-5
  at: "2026-10-05T12:30:00Z"
sources:
  - id: incident
    resource: https://github.com/ktogias/gnostoa/issues/368
    title: One owner for trusted authority execution (incident, root-cause analysis and plan)
  - id: lineage
    resource: https://github.com/ktogias/gnostoa/issues/368#issuecomment-5993238884
    title: Prior-art inventory and architecture-inheritance lineage table, bound to c54b18d
  - id: admission
    resource: https://github.com/ktogias/gnostoa/issues/15#issuecomment-5993243322
    title: Owner admission of #368 and of the preparation authority's evolution (2026-10-05)
  - id: reuse-class
    resource: https://github.com/ktogias/gnostoa/issues/365
    title: Detect and prevent re-implementation of responsibilities that already have an owner
  - id: shared-client
    resource: ./0100-separate-the-agent-review-pipeline-into-a-neutral-core-and-adapters.md
    title: The precedent, five hardened GitHub clients merged into one
  - id: preparation
    resource: ./0090-require-pre-candidate-preparation-receipts-for-non-hook-authoring.md
    title: The preparation authority and its bootstrap exception
  - id: credential-check
    resource: https://github.com/ktogias/gnostoa/pull/364
    title: The credential check, where the hardening was proven by review (paused)
  - id: pep-706
    resource: https://peps.python.org/pep-0706/
    title: PEP 706, the tarfile data filter (consumed)
  - id: openssh-safe-path
    resource: https://github.com/openssh/openssh-portable/blob/master/misc.c
    title: OpenSSH safe_path (BSD); the every-component ownership pattern, consulted as a pattern only
x-project-knowledge:
  id: kit.decision.0102.own-trusted-execution-in-one-hardened-module
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governed-by
      target: /decisions/0090-require-pre-candidate-preparation-receipts-for-non-hook-authoring.md
    - kind: governed-by
      target: /decisions/0100-separate-the-agent-review-pipeline-into-a-neutral-core-and-adapters.md
---

# Own trusted execution in one hardened module, and refuse new copies

## Context

"Run code from the authority commit, not from the editable checkout" is the
precondition of every authority Gnostoa grants an agent: the preparation receipt,
the protected judge and the credential gate. It rests on four smaller
responsibilities:
- resolving an executable that cannot be stood in for;
- running Git free of the caller's routing and configuration;
- reading a commit's content without the repository's local attributes and filters;
- running the authority's entrypoint.

On protected `main` at `c54b18d` these responsibilities have nine implementations
and no owner (#368 records the incident and its root-cause analysis):
- six Python builders of a Git environment;
- two identical tree materializers;
- three executable-lookup policies;
- two shell scrub lists.

PR #364 added two more by copying the preparation helper. Eight review rounds then
proved the hardening that this kind of code needs, but only for #364's copy. Among
the remaining implementations:
- the subject repository's local filters run during `capsule`'s `git archive`;
- an inherited `GIT_EXEC_PATH` reaches every scrub-list builder;
- `review_protected` never checks that main is protected.

This is the fourth occurrence of the class. The earlier ones are the
provider-abstraction retrospective (2026-09-19), the review-pipeline recurrence RCA
(2026-10-02) and #365 (2026-10-04). Each time, prevention was prose an agent had to
read. On 2026-10-05 the owner admitted the abstraction first, the preparation
authority's evolution onto it, and hooks "everywhere" so that later agents find the
owner before they write.

## Prior-art and reuse disposition

The inventory and the lineage table are in the source `lineage`. They are summarized
here.

| need | candidate | disposition |
|---|---|---|
| executable trust | #364's `knowledge_common.trusted_path` (component walk), proven by review | **factored** into this owner, unchanged in rule |
| a path walked one component at a time, every component owned by root or the caller | OpenSSH `safe_path` (`StrictModes`) | the pattern, consulted, not copied; ours also walks links without following them implicitly |
| safe tar extraction | `tarfile`'s `data` filter (PEP 706), already used by `capsule` | **consumed** |
| an isolated Git environment | six builders: scrub lists and allowlists | **factored** as one allowlist; scrub lists **superseded**, since a list misses the next variable, as `GIT_EXEC_PATH` showed |
| disposable metadata over an object store | `candidate_prepare._isolated_git_metadata` | **factored** |
| a Python API ban | ruff `banned-api` (TID251, MIT) | not used. Ruff's configuration is a preparation authority surface, and ruff cannot see shell or AGENTS.md; the registry check covers all three |
| layer contracts | import-linter (BSD-2-Clause) | not used: it constrains import direction and cannot detect a re-implementation (#365) |
| single-owner fitness tests | `SharedClientOwnershipTests`, `test_one_confinement_implementation_serves_every_script`, `COUPLING` | **extended**: the registry generalizes their perimeter-by-perimeter pattern into one declared, checked list |

## Decision

1. **One owner, `tools/trusted_execution.py`, registry id `trusted-execution`.** It
   holds:
   - `trusted_path(path)` and `trusted_executable(name)`. The path is walked one
     component at a time and no link is followed before it is judged. Every
     component must be root's or the caller's. Every directory must be writable by
     no one else unless it is sticky, and the file at the end by no one else.
     `trusted_executable` searches the fixed `TRUSTED_EXECUTABLE_PATH` only.
   - `operator_executable(name)`, a lookup on the caller's `PATH` by explicit policy.
     It is for tools the operator chooses, such as a sandbox backend, and never for
     an authority or judge path.
   - `git_environment(...)`, an allowlist: nothing of the caller's is inherited, not
     even a proxy or certificate setting; `PATH` is the trusted one. A caller's
     proxy, with the certificates that authenticate it, could counterfeit a
     protected fetch that every later check would find consistent (round 25).
     - No `HOME`, so no global configuration or attributes file is read.
     - Configuration comes from no file, there are no replacement objects and no
       prompt, and `LC_ALL=C`.
     - Pinned through command-scope configuration: `core.hooksPath=/dev/null` and
       `core.fsmonitor=false`, and an allowed-transport list when the call asks for
       one. That list is also `GIT_ALLOW_PROTOCOL`, which outranks configuration: a
       repository's own `protocol.<name>.allow` re-allowed a transport the generic
       `protocol.allow=never` refused (Codex on #369).
     - Only the repository-routing values the call names are added.
   - `without_git_variables(environment)`: every `GIT_*` variable removed, for a
     child that is not Git and must not route Git elsewhere.
   - `disposable_git_metadata(objects, object_format=...)`: a bare repository from
     an empty template, bound to an object store, in that store's object format. Its
     own `info/attributes`, which outranks every `.gitattributes`, unsets each
     attribute that changes a file's bytes when it is written.
   - `extract_tree(repository, tree, destination)`: the tree archived under
     disposable metadata and extracted with the `data` filter. The repository's own
     configuration, its checkout-local attributes (`info/attributes`) and its filter
     drivers do not apply, and nor do the tree's own `.gitattributes`: the files are
     the tree's bytes. Its `export-ignore` dropped a file, and `eol`, `ident` and
     `working-tree-encoding` rewrote one, so the compiler saw another tree and blocked
     a valid subject (CodeAnt on #369). `export-subst` applies to a commit's archive
     only. A destination that is a link is refused by name.
     - The tree is the full object name in the repository's format; 40 hex digits
       are an abbreviation in a SHA-256 repository.
     - It names a tree. Given a commit, `git archive` archives the commit's tree, so
       any other object type is refused (CodeAnt on #369).
     - It extracts into a staging directory beside the destination, which must be
       missing or an empty directory, and moves it into place by one `rename`, which
       replaces an empty directory and refuses anything else.
     - A refused member, a Git failure and any file-system failure raise the owner's
       error.
   - `repository_read(repository, ...)` and `repository_files(directory)`: a read of
     a repository that may be untrusted. The environment cannot neutralize a
     repository's own configuration, which can name programs: filters, diff drivers,
     textconv and `gpg.program`. A plumbing command's options can reach them, such as
     `cat-file --filters`, `rev-list --format=%G?` and `describe --dirty`, and Git
     accepts an abbreviated option. So the owner allows a table of exact command and
     option shapes (`rev-parse`, `ls-tree -r --name-only`,
     `describe --tags --long --match`, `ls-files -z`) and refuses every other command
     and option. A call inside a repository you do not trust is either one of these
     reads or runs under disposable metadata.
     - Because an allowed read runs no configured program, it names its one
       repository as `safe.directory`. Git then reads a checkout another user owns,
       as provider CI's container user finds the runner's.
     - `repository_files` returns None only outside any repository. A repository
       Git cannot list raises, because walking it instead would read its untracked
       files as tracked.
   - `run_git(arguments, cwd=..., environment=..., timeout=...)`: the one place Git
     runs, with an environment from `git_environment`. A Git failure raises
     `GitFailure`, which carries Git's stderr. A Git that cannot start, or that
     outlives its timeout, raises `TrustedExecutionError`. Each caller maps them to
     its own error.
2. **Every caller imports it.**
   - PR A, through the ordinary preparation route: `capsule` (`execute`,
     `preparation`, `compiler`), `review_protected` (its environment and its
     executable), `review_current`, `experiment/backend` and the `b15` runtime smoke.
   - PR B (authority evolution, rule 5): the preparation authority, meaning
     `tools/candidate_prepare.py`, `ci/prepare-candidate` and its AGENTS.md helper.
     It goes onto this owner and onto one shell library, `ci/lib/trusted.sh`,
     launched by one AGENTS.md bootstrap primitive, `run_authority`. The
     primitive's minimal copy of the resolution block is kept identical to the
     library's by a test.
   - PR C: #364 rebuilt as a caller.
   - PR D: the workflows' base-code selection, assessed against the owner.
3. **A responsibility registry**, `policy/owned-responsibilities.yaml` with
   `schemas/owned-responsibilities.schema.json`. Each entry names:
   - the responsibility and its owner;
   - how to extend the owner;
   - the source signatures that would mark a re-implementation. Every entry has at
     least one. For running Git they match the acquisition of the executable
     (`git_executable()`, `trusted_executable("git")`, a fixed Git path), which every
     way of running it needs, whatever the call's layout or the name the executable
     is kept under; a literal `"git"` argument; and a Git subcommand in shell command
     position;
   - where a signature may legitimately appear;
   - the debt still pending migration: for each file, the exact lines it owes, tied
     to the Work Item that removes them.
4. **A deterministic reuse check.** `knowledge reuse-check` (`tools/reuse_check.py`)
   scans production for each signature. Production is every tracked file but tests,
   knowledge, guidance and Markdown other than `AGENTS.md`. Outside a repository,
   such as in the installed image, the tree is walked instead, skipping hidden
   directories the product does not track, such as a generated `.evidence/`. The
   check fails on a match outside the owner, the allowed places and the declared
   debt. A repository Git cannot list, or a file it cannot read, is an error, never
   a clean result. A debt entry names the exact lines it owes, compared stripped. A
   matching line it does not name is a new copy, reported with its line number, and
   a line it names that has gone must be removed from it, so debt can only shrink.
   A count of lines stayed equal when one owed line went and a new copy came (Codex
   on #369). A signature is a line pattern or, for a Python file, a named structural
   detector. Python's standard `ast` is used, not Semgrep or a pylint plugin, which
   would add a runtime dependency to a check that runs offline in the installed image.
   The first detector, `relative-to-under-value-error`, marks a `relative_to` call
   in a `try` that catches `ValueError`: the common way to confine a path, which no
   line pattern can tell from a relative path computed for display (Codex on #369;
   the owner chose it on 2026-10-06). The 15 existing sites are debt under #376. A
   Python file that does not parse makes the check fail. So does a line over 1 MiB,
   and a `.git` entry Git cannot read, in the root or above it: neither passes as a
   clean tree. Production includes an `AGENTS.md` in any directory. An object store
   is resolved strictly before it is bound. Lines are counted as Python counts
   them. Each line pattern reads a line one way only, so a search is about linear;
   three were quadratic and one exponential until round 16, and a test now searches
   the hostile shapes found. Lines are read a block at a time, so a long file
   whose lines end in `\r` alone is read line by line too. A Git command line in a
   string that a call hands to a shell is a signature; a message that names one is
   not. So is Git run with no subcommand (`--version`, `--help`, `-v`, `-h`), and a
   command line after a run of shell keywords such as `if !`, which surfaced three
   more existing copies, now debt. The command may be an absolute path, unquoted.
   Rounds 15 to 19 each found one more form, so round 20 lists the rest at once:
   - a workflow's `run:` and a Dockerfile's `RUN`;
   - a backtick substitution, `find -exec` and `sh -c '...'`;
   - wrappers such as `timeout`, `sudo` and `xargs`;
   - `shlex.split` and `pexpect.spawn` strings;
   - an argv list headed by a name like `git_bin`;
   - GitPython.

   In an explicit command context, any subcommand counts, external ones such as
   `git lfs` included. At a bare line start, where `git and ...` is also prose,
   only Git's own subcommands and well-known extensions count.
   A loader, a validator or `which` can also be reached where no line names it: by a
   name on a line of its own in a multi-line import, or by a call through an alias
   of its module. Three structural signatures read those from the syntax tree, and
   leave an import's own line, and a call through the module's own name, to the line
   patterns, so no line is marked twice.
   An argument list headed by a name for git, such as `git_bin`, written as a tuple
   or split across lines, is read from the syntax tree too. Outside a repository,
   a directory the walk cannot read is an error. Git on the caller's own checkout
   gets the caller's environment without `GIT_*`, `LD_*` or `DYLD_*`, through the
   owner's `caller_git_environment()`.
   Round 23 closes four more families:
   - **Git named by any argument:** first or later, positional or keyword, as in
     `trusted_executable(name="git")`.
   - **Submodules:** a function imported from one, or called through its dotted name.
   - **What a definition runs at once:** decorators and defaults are the `try`'s own;
     a generator's body runs later, so only its first iterable is.
   - **A routing variable assigned in a shell:** `export GIT_DIR=`, a command's
     prefix, `env`, a workflow's `env:` key, or a Dockerfile's `ENV`.

   Outside a repository, the walk does not enter a directory it would skip anyway.
   Round 24 widens two more:
   - an HTTP client imported by name (`from http import client`, `from urllib
     import request`) or a third-party one (`requests`, `httpx`, `urllib3`,
     `aiohttp`), on its own line or in a multi-line import;
   - a call reached through any alias, its full module path resolved first, as in
     `js.validators.validate(...)` or `from jsonschema import validators as v`.
   Round 25 widens path confinement to its other ordinary forms: a common path or
   prefix compared with a root, a root among a path's parents, and a prefix ending
   in the separator. `tools/candidate_prepare.py`, frozen preparation authority, is
   recorded as debt under #376.
   Round 26 widens Git's forms again:
   - a name bound to Git in a shell, unquoted, perhaps as an absolute path or
     through `export`, `readonly`, `local` or `declare`, as `git_cmd=git`, and a
     shell `alias`;
   - the shell's own lookups, `$(which git)` and `$(type -P git)`;
   - Git's other bare options, such as `--exec-path`, which run it with no
     subcommand.
   Round 27 refuses a registry whose responsibility id is used twice: it would
   name no single owner.
   Round 28 sees a wrapper named by its absolute path, as `/usr/bin/env git`, and
   one whose option takes a word or a path, as `sudo -u builder git`. The owner
   writes the bound store's name as the file system's bytes, so a name that is not
   UTF-8 is bound instead of raising.
   A line of exactly the reader's bound, before a `\r\n` split across blocks, is
   read, and a common prefix compared with a constant is no confinement.
   A class body runs where it stands, so its calls are the `try`'s own; only
   function and lambda bodies wait. The structural signature reads the `try`'s own lines and follows no call:
   `relative_to` in a function is not seen there, even in one the `try` defines and
   calls, under the owner's scope bound of accidental copies (2026-10-05). Identical
   lines are interchangeable call sites. Removing one and adding
   the same text elsewhere in that file keeps the debt the same size, and the number
   can still only shrink. The owner set this bound on 2026-10-06, over binding each
   line to its function or its neighbour, which would make every refactor of an
   indebted file a registry edit (Codex on #369). The file is read a line at a time. It runs as a unittest, and
   so in the `fast`, `regression` and `extended` profiles of `ci/verify`, in the
   repository's pre-commit and pre-push hooks, and in provider CI.
   **What the check is for.** It guards against an agent *accidentally*
   re-implementing an owned responsibility, as #364 did and #365 records. It does
   not detect deliberate obfuscation, such as `getattr`, a name built at run time or
   an alias of an alias. No source signature can, and review and the routing hooks
   below cover that. The owner set this bound on 2026-10-05, after six review rounds
   on #369. A finding that the *check* can be bypassed only by deliberate
   obfuscation is declined, citing this bound. A disguised copy found in a change is
   still a copy, and review refuses it (CodeAnt on #369). A shape an agent would write
   by accident is fixed in the check. Every finding on the owner itself is fixed, since those are
   security boundaries. An AST-aware Python signature is captured on #365, to be
   admitted only if a real accidental miss is observed.
5. **The hooks that route an agent to the owner before it writes:**
   - AGENTS.md routes every helper-writing task through the registry.
   - The runbook's prior-art checkpoint queries it, and re-runs whenever an owner
     decision or a review round adds a responsibility.
   - A guardrail covers the registry and the check.
   - Each owner's docstring names its registry id and says to extend it, not copy it.
6. **The authority-evolution path for the preparation authority (PR B).** Its parent
   cannot prepare a change to its own authority, as Decision 0090 states for its own
   introduction. The owner admitted the evolution on 2026-10-05 (source
   `admission`), so PR B is a stated bootstrap exception:
   - it carries no trusted preparation receipt;
   - its candidate is verified by every container suite and by provider CI;
   - the exception is stated in the PR;
   - the owner approves it at merge.

   Its descendants are prepared by the evolved authority.

## Delivery status

- **PR A:** the owner, the migrations through the ordinary route, the registry, the
  check and the hooks. Not yet merged.
- **PR B, PR C and PR D:** not started.

## Verification

- **Before any change:** the callers' existing suites characterize their behavior.
  New REDs show the defects this removes:
  - a subject repository's local filter runs during `capsule` materialization;
  - an inherited `GIT_EXEC_PATH` or `GIT_TRACE` reaches the old builders;
  - a planted copy passes unnoticed.
- **After the change:** the same suites pass. The reuse check fails on a planted
  copy and on a stale debt entry, and mutants of each rule are killed.

## Consequences

- One place is hardened, and every caller gets the hardening.
- Policy is explicit: strict trust for authority and judge paths, the operator's
  `PATH` only by name.
- A new copy fails a unittest in the pre-commit hook and in CI, rather than waiting
  for an owner to notice.
- The preparation authority evolves once, through a stated exception, rather than
  through a parallel copy.
