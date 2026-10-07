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
   `time` and `exec`, and after `coproc`. A name after `coproc` is the coprocess's
   before a group; before a simple command, Bash takes it for the command word, as
   measured with `coproc JOB echo hi` (round 47). A redirection, its target and a descriptor's number before
   it are removed wherever they stand, and a process substitution, `<(...)`,
   opens a command of its own (round 40). A backquoted command substitution is
   found before the text is split, since `shlex` keeps no quoting: a backtick
   opens one unless it is in single quotes or after a backslash, in double quotes
   too, and the first backtick no backslash precedes closes it, as Bash's manual
   states. Its command is read on its own, to the bounded depth, and it leaves a
   word in the text around it, so `x=`date` git status` runs Git and
   `` `date` git `` does not (rounds 45 and 46). A line ends at a newline outside
   quotes; a quoted newline is part of its word, and a backslash before a newline
   continues the line (round 47).
3. **What precedes the command word is peeled:**
   - assignments, `NAME=value`;
   - Make's recipe prefixes, `@`, `-` and `+`;
   - wrappers, by name or path: `env`, `command`, `sudo`, `timeout`, `nice`,
     `nohup`, `xargs`, `stdbuf`, `ionice`, `setsid`, `chrt`, `flock` and `time`.
     Their options are peeled too, together with the word an option takes. The
     first positional word of `flock`, `timeout` and `chrt` is their operand,
     however it is spelt: a lock file, a duration such as `.5s`, or a priority
     (round 43). Any other path is the command a wrapper runs, as in
     `sudo /usr/bin/make`. An option whose value is a command is read as one: `env -S`
     and `flock -c` (round 41).
4. **A shell with `-c`** (`sh`, `bash`, `dash`, `ksh`, `zsh` or `ash`) runs its
   command string, which is read the same way, to a bounded depth. Its options are
   peeled first, including those that take a value: `-o`, `+o`, `-O`, `+O`,
   `--rcfile` and `--init-file`. `eval` runs its arguments, joined, as a command
   (round 46).
5. **Git** is a command word whose name, after its path, is `git`.

**Sources of shell text:**
- a shell script, by its suffix or a shell shebang. The shebang is split as a shell
  splits it, and `env`'s options in it are skipped (round 42);
- `RUN` in a `Dockerfile`, with the lines its escape character continues: a
  backslash, or the backtick its `escape` parser directive names. A directive
  counts only before any other line (round 42). Any whitespace separates `RUN` from
  its text, and `RUN`'s own options, as `--mount=type=cache`, are skipped (round
  43). A here-document's body is shell text when a shell reads it: `RUN <<EOF`
  alone, unless its shebang names no shell, or after a shell that reads its
  standard input. Another program's body, as `python3 <<EOF`'s, is data. One
  here-document per instruction is read (round 44), on its first line or a
  continuation line, and judged by the command it follows, after any control
  operator (round 45), or on an earlier continuation line; after a group, as in
  `{ cat; } <<EOF`, by the group's first command (round 46). A redirection before
  the document, as `2>&1`, and the document's own descriptor, as in `0<<EOF`, are
  the shell's (round 47). The exec form's JSON
  list is read as the argument list it runs, which may hand a shell its command;
  text that is no JSON list of strings is the shell form, as Docker reads it
  (round 46). An exec form the escape character splits across lines is joined
  first; an element that spells an operator, as `";"`, is an argument, and
  separates nothing; a list too deep for `json` is the shell form (round 47);
- a workflow's `run` value, or a composite action's in its `action.yml` (round 42),
  found by composing the file as YAML with PyYAML, already a dependency, rather
  than by a pattern for the key. Any spelling of the key, a flow mapping, any block
  indicator and an alias's anchor are read as YAML reads them (round 41). A block's
  lines are read each on its own; another value is read as YAML decodes it, on the
  line it starts on. A file YAML cannot read is read whole, so it cannot pass as
  clean;
- a Make recipe line, opened by a tab or by the character `.RECIPEPREFIX` names,
  from its assignment on (round 44);
- a fenced shell block in an `AGENTS.md`, fenced by three or more backticks or
  tildes, and closed only by a bare fence of at least as many of the same
  character (round 42);
- the commands Python hands to a shell: a string literal given to a shell helper,
  the first word of an argument list given with `shell=True` (round 44), and an
  argument list that names a shell, which is read as its words already are.

Each physical line is read on its own, so a command is reported on the line
that holds it, as the line patterns report it. A line ends where the line
patterns' lines end, at CR or LF only (round 41). A continuation line starts a
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
  expands to, as `$GIT status`, is not followed, and neither are aliases. Text `shlex` cannot split, such as an unterminated quote, is read as
  far as it splits. A quoted control character, as `'('`, is read as the
  operator it spells, since `shlex` removes the quotes before the reader sees the
  word. A wrapper's option value that names a command, as the user in
  `sudo -u git echo ok`, is read as that command. The reader does not know which
  options take a value, and `sudo -E git status` is spelt the same way, so it
  reports rather than misses (round 43). For the same reason, an option that
  takes no value before a wrapper's operand, as `-f` in `chrt -f 99 grep git`,
  makes the reader take the operand for that option's value and the next word for
  the operand, and it reports `git` (round 44). Under the owner's scope bound of
  2026-10-05, the check guards accidental copies, not obfuscation.
- **Linear by construction.** A token walk with bounded recursion replaces
  nested regular expressions, so no backtracking is introduced.

## Alternatives

- **`bashlex`:** a full bash parser, but GPL-3.0+, which is incompatible with this
  Apache-2.0 toolkit's distribution.
- **`shlex` with the backtick as punctuation:** measured in round 46, it reads a
  backtick in double quotes as a character, so it misses ``echo "`git log`"``, and
  it splits `x=a`date`b` into three words.
- **`tree-sitter-bash`:** MIT, but it needs a new dependency, and `pyproject.toml`
  is frozen preparation authority in a candidate.
- **More regular-expression forms:** the owner chose against continuing.

## Verification

Tests fail first on the head before the change, `0dc0a0a`, for the forms the
patterns missed: each source, each position, each peeled word and the shell
recursion. Mutants cover each table and each branch of the reader.
