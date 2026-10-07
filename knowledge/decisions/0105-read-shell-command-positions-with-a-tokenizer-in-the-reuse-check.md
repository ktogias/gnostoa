---
type: Decision
title: Read shell command positions with a tokenizer in the reuse check
description: The reuse check reads where a shell runs a command by tokenizing shell text with the standard library's shlex and walking its command positions, instead of adding a regular-expression form for each new way of writing a Git command. The git-execution line pattern is frozen as a line-level net.
status: draft
generated:
  by: anthropic/claude-opus-5-5
  at: "2026-10-07T03:20:00Z"
sources:
  - id: pr
    resource: https://github.com/ktogias/gnostoa/pull/369
    title: PR A of #368, the trusted-execution owner, the registry and the reuse check
  - id: owner-choice
    resource: https://github.com/ktogias/gnostoa/pull/369#issuecomment-6032323532
    title: The owner's choice of a tokenizer on 2026-10-07, with the prior-art checkpoint and lineage
  - id: owner-decision
    resource: ./0102-own-trusted-execution-in-one-hardened-module.md
    title: The trusted-execution owner, its registry and the reuse check
  - id: reuse
    resource: https://github.com/ktogias/gnostoa/issues/365
    title: Detect and prevent re-implementation of responsibilities that already have an owner
x-project-knowledge:
  id: kit.decision.0105.read-shell-command-positions-with-a-tokenizer-in-the-reuse-check
  owners:
    - team:gnostoa-maintainers
  scope:
    - gnostoa
  relations:
    - kind: governed-by
      target: /decisions/0102-own-trusted-execution-in-one-hardened-module.md
---

# Read shell command positions with a tokenizer in the reuse check

## Context

Decision 0102's `git-execution` signature is a line pattern. Since #369's round 17
the reviewers found one more way to write a Git command in about 18 of 22 rounds:
- a wrapper named by its path, or with an option that takes a word;
- a leading assignment;
- `env`'s own options;
- `while` and `until`;
- a brace group or a subshell;
- Make's recipe prefixes;
- a `case` arm;
- a shell reached through an argument list, or through a wrapper in one.

Each round added one more regular-expression form, and cost about an hour. On
2026-10-07 the owner chose to stop adding forms and read shell text with a
tokenizer instead («Tokenizer τώρα»).

## Decision

The reuse check gains one **shell command reader**:

1. **Tokens.** Shell text is split by the standard library's `shlex`, with
   `punctuation_chars`, so `;`, `&&`, `||`, `|`, `&`, `(`, `)` and `;;` are tokens
   of their own. `#` begins a comment. Quotes are removed, as the shell removes
   them.
2. **Command positions.** A command starts at the start of the text, after a
   control operator or a group's `(`, `{` or `)`, and after a reserved word that
   introduces one: `if`, `then`, `elif`, `else`, `do`, `while`, `until`, `!`,
   `time` and `exec`.
3. **What precedes the command word is peeled:**
   - assignments, `NAME=value`;
   - Make's recipe prefixes, `@`, `-` and `+`;
   - wrappers, by name or path: `env`, `command`, `sudo`, `timeout`, `nice`,
     `nohup`, `xargs`, `stdbuf`, `ionice`, `setsid`, `chrt`, `flock` and `time`.
     Their options are peeled too, together with the word an option takes and the
     leading number or path some take.
4. **A shell with `-c`** (`sh`, `bash`, `dash`, `ksh`, `zsh` or `ash`) runs its
   command string, which is read the same way, to a bounded depth. Its options are
   peeled first, including those that take a value: `-o`, `+o`, `-O`, `+O`,
   `--rcfile` and `--init-file`.
5. **Git** is a command word whose name, after its path, is `git`.

**Sources of shell text:**
- a shell script, by its suffix or a shell shebang;
- `RUN` in a `Dockerfile`;
- a workflow step's `run:`, on its line or as a block;
- a Make recipe line;
- a fenced shell block in an `AGENTS.md`;
- the commands Python hands to a shell: a string literal given to a shell helper,
  and an argument list, which is read as its words already are.

Each physical line is read on its own, so a command is reported on the line
that holds it, as the line patterns report it. A continuation line starts a
command position of its own. A Dockerfile's `RUN` keeps its continuation lines.

**The signature** is the existing `git-shell-command`. Its structure,
`shell-command-indirect`, already held the commands Python hands to a shell; it
now holds each shell-ish file's shell text too. A command marks its line when the
reader finds Git in it, or when the entry's own line patterns match it, and only
where no line pattern already marked the line itself, so no line is reported
twice. The reader lives in `tools/shell_reader.py`, which the reuse check calls.
Argument-list reading moves there too, so nothing describes it twice.

**The line pattern is frozen.** `git-execution`'s shell alternatives stay as a
line-level net, but no new shell form is added to them. A new form is the
reader's. Their removal, once the reader has covered them in production, is
residual work under #365.

## Consequences

- **Covered by construction.** The forms the reviewers found, and any
  combination of them, are read as positions and peeled words, not as patterns.
  That includes a `then` after a `;`, a quoted or escaped command word, and a
  wrapper before a shell in an argument list.
- **The reader's limits are stated.** A command word that only a variable
  expands to, as `$GIT status`, is not followed, and neither are `eval` and
  aliases. Text `shlex` cannot split, such as an unterminated quote, is read as
  far as it splits. Under the owner's scope bound of 2026-10-05, the check guards
  accidental copies, not obfuscation.
- **Linear by construction.** A token walk with bounded recursion replaces
  nested regular expressions, so no backtracking is introduced.

## Alternatives

- **`bashlex`:** a full bash parser, but GPL-3.0+, which is incompatible with this
  Apache-2.0 toolkit's distribution.
- **`tree-sitter-bash`:** MIT, but it needs a new dependency, and `pyproject.toml`
  is frozen preparation authority in a candidate.
- **More regular-expression forms:** the owner chose against continuing.

## Verification

Tests fail first on the head before the change, `0dc0a0a`, for the forms the
patterns missed: each source, each position, each peeled word and the shell
recursion. Mutants cover each table and each branch of the reader.
