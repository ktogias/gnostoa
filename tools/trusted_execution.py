"""The one owner of trusted execution: registry id `trusted-execution`.

Decision 0102 and #368. Do not write any of these again; extend this module, and its
tests in `tests/test_trusted_execution.py`, with the new need:

- **Executables.** `trusted_executable()` for an authority or judge path, from the
  fixed system directories, refusing any that someone else could replace;
  `trusted_path()` for a path a configuration names; `operator_executable()` for a
  tool the operator chooses, from the caller's `PATH`, by explicit policy.
- **Git environments.** `git_environment()` is an allowlist: nothing of the caller's
  is inherited. A scrub list misses the next variable, as `GIT_EXEC_PATH` showed on
  #364. `without_git_variables()` is for a child that is not Git, and
  `caller_git_environment()` for Git on the caller's own checkout.
- **Repository content.** `disposable_git_metadata()` binds throwaway metadata to an
  object store. `extract_tree()` materializes an exact tree, byte for byte: none of
  the repository's own configuration, attributes or filter drivers apply, and nor do
  the tree's own `.gitattributes` (CodeAnt on #369).

`policy/owned-responsibilities.yaml` registers this owner, and `knowledge reuse-check`
refuses a copy of any of it elsewhere.
"""

from __future__ import annotations

import os
import re
import shutil
import stat
import subprocess  # nosec B404
import tarfile
import tempfile
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import IO

# The directories an authority or judge path's tools come from. They are root-owned
# on every supported host, and never the caller's `PATH`, where a shadowed executable
# would run. The preparation wrapper's list is the same, and a test holds the two
# equal. Not `os.defpath`, which omits `/usr/local/bin`.
TRUSTED_EXECUTABLE_PATH = "/usr/local/bin:/usr/bin:/bin:/opt/homebrew/bin"

# As many links as a path may pass through before it is refused, as `SYMLOOP_MAX` bounds.
_MAX_LINKS = 40

# Command-scope configuration, which outranks the repository's own: no hook and no
# file-system monitor a repository names may run.
_PINNED_CONFIGURATION = (
    ("core.hooksPath", os.devnull),
    ("core.fsmonitor", "false"),
)

# The reads of a repository that may be untrusted, each with the only options it may
# take. A command's other options can run the repository's own programs:
# `cat-file --filters` its smudge filter, `--textconv` its diff driver,
# `rev-list --format=%G?` its `gpg.program`, `describe --dirty` an index refresh.
# Git also accepts an abbreviated option, so `--filt` is `--filters` (CodeAnt and
# Codex on #369). So the shapes are allowed, not the dangers refused: extend this
# table for a new read, after checking that none of its options can run a program.
_READS: dict[str, frozenset[str]] = {
    "rev-parse": frozenset(
        {"--show-object-format", "--path-format=absolute", "--git-common-dir"}
    ),
    "ls-tree": frozenset({"-r", "--name-only", "-z"}),
    "describe": frozenset({"--tags", "--long", "--match"}),
    "ls-files": frozenset({"-z"}),
}
# How much of what Git says on failure the owner's error carries.
_STDERR_LIMIT = 2000

# An exact object name, SHA-1 or SHA-256: the metadata a tree is extracted under has no
# refs to resolve a name against.
_OBJECT_NAME = re.compile(r"\A[0-9a-f]{40}(?:[0-9a-f]{24})?\Z")
# The length of a full object name in each object format.
_OBJECT_NAME_LENGTH = {"sha1": 40, "sha256": 64}
# A read of a repository is bounded in time, so a pathological one cannot block its
# caller for ever (CodeAnt on #369).
_READ_TIMEOUT_SECONDS = 120
# How long any Git the owner runs may take when its caller names no bound.
_GIT_TIMEOUT_SECONDS = 900
# Unsets every attribute that changes what a tree's files hold when they are written.
# `export-subst` needs none: it applies to a commit's archive, never a tree's.
_NEUTRAL_ATTRIBUTES = (
    "* -export-ignore -text -eol -crlf -ident -filter -working-tree-encoding\n"
)
# An archive of a whole tree is bounded too, more generously (CodeAnt on #369).
_ARCHIVE_TIMEOUT_SECONDS = 900


class TrustedExecutionError(RuntimeError):
    """What trusted execution needs is unavailable or untrusted, or Git failed."""


class GitFailure(TrustedExecutionError):
    """Git exited non-zero; ``stderr`` is what it said."""

    def __init__(self, command: str, stderr: bytes) -> None:
        self.stderr = stderr
        said = stderr.decode("utf-8", errors="replace").strip()[:_STDERR_LIMIT]
        super().__init__(f"git {command} failed: {said}")


def _theirs(held: os.stat_result) -> bool:
    """Return whether root or the caller owns what ``held`` describes."""
    return held.st_uid in {0, os.getuid()}


def _closed(held: os.stat_result, *, sticky: bool) -> bool:
    """Return whether no one else may write it; a sticky directory, as `/tmp` is, lets
    no one but an entry's owner replace the entry."""
    if not held.st_mode & (stat.S_IWGRP | stat.S_IWOTH):
        return True
    return sticky and bool(held.st_mode & stat.S_ISVTX)


def trusted_path(found: str) -> str | None:
    """Return the file the absolute path ``found`` really is, if no one can replace it.

    The path is walked one component at a time, and no link is followed before it is
    judged (Codex, CodeAnt and gitar on #364):
    - every component, a link included, must be root's or the caller's;
    - every directory on the way, as it really is, must be writable by no one else
      unless it is sticky;
    - the file at the end must be writable by no one else.

    Whoever can change any of them can replace what ``found`` names.
    """
    if not os.path.isabs(found):
        return None
    try:
        return _walk(found)
    except OSError:
        return None


def trusted_directory(found: str) -> str | None:
    """Return the directory the absolute path ``found`` really is, if no one else can
    replace it or any entry in it: `trusted_path`'s walk, ending at a directory, which
    must be closed unless it is sticky (CodeAnt on #369)."""
    if not os.path.isabs(found):
        return None
    try:
        return _walk(found, directory=True)
    except OSError:
        return None


def _parts(path: str) -> list[str]:
    """Return the components of ``path``, as a walk reads them.

    A trailing slash makes the last component a directory, as POSIX reads `x/`, so
    it is kept as a final `.`: a walk that reaches a file with `.` still to read
    names nothing (CodeAnt on #369).
    """
    parts = [part for part in path.split("/") if part]
    return [*parts, "."] if parts and path.endswith("/") else parts


def _follow(entry: str, current: str, pending: list[str]) -> tuple[str, list[str]]:
    """Return where the link ``entry`` leads: from the root if its target is absolute,
    from the directory it is in otherwise, its target's components read first."""
    target = os.readlink(entry)
    start = "/" if target.startswith("/") else current
    return start, _parts(target) + pending


def _dot(current: str, name: str) -> str:
    """The directory ``.`` or ``..`` names from ``current``."""
    return current if name == "." else os.path.dirname(current)


def _component(entry: str, pending: list[str]) -> str:
    """Judge one component of a walk: "link", "directory", "file" (the end of the
    path) or "refuse"."""
    held = os.lstat(entry)
    if not _theirs(held):
        return "refuse"
    if stat.S_ISLNK(held.st_mode):
        return "link"
    if not stat.S_ISDIR(held.st_mode):
        # The file at the end, writable by no one else; a file on the way is no path.
        return "file" if not pending and _closed(held, sticky=False) else "refuse"
    return "directory" if _closed(held, sticky=True) else "refuse"


def _walk(found: str, *, directory: bool = False) -> str | None:
    """Resolve ``found`` as `trusted_path` describes, or return None. With
    ``directory``, the walk ends at a directory instead of a file."""
    root = os.lstat("/")
    if not _theirs(root) or not _closed(root, sticky=True):
        return None
    current, pending, links = "/", _parts(found), 0
    while pending:
        name = pending.pop(0)
        if name in {".", ".."}:
            current = _dot(current, name)
            continue
        entry = os.path.join(current, name)
        kind = _component(entry, pending)
        if kind == "link":
            links += 1
            if links > _MAX_LINKS:
                return None
            current, pending = _follow(entry, current, pending)
        elif kind == "directory":
            current = entry
        elif kind == "file" and not directory:
            return entry
        else:
            return None
    return current if directory else None


def trusted_executable(name: str) -> str | None:
    """Return ``name`` resolved from the trusted system directories, or None.

    For an authority or judge path. What is found is not trusted yet: it must be a
    `trusted_path`. `/opt/homebrew/bin` belongs to a user, not to root (CodeAnt on
    #364).
    """
    # `shutil.which` ignores its search path for a name with a directory in it, so
    # a caller-owned program anywhere would pass (CodeAnt on #369).
    if os.sep in name or (os.altsep and os.altsep in name):
        return None
    found = shutil.which(name, path=TRUSTED_EXECUTABLE_PATH)
    if found is None:
        return None
    return trusted_path(os.path.abspath(found))


def operator_executable(name: str) -> str | None:
    """Return ``name`` as the caller's `PATH` resolves it, or None.

    Only for a tool the operator chooses, such as a sandbox backend: the operator's
    `PATH` is the intended source. Never use this on an authority or judge path.
    """
    return shutil.which(name)


def git_executable() -> str:
    """Return the trusted git, or raise `TrustedExecutionError`."""
    git = trusted_executable("git")
    if git is None:
        raise TrustedExecutionError(
            f"no trusted git in the system directories ({TRUSTED_EXECUTABLE_PATH})"
        )
    return git


def git_environment(
    *,
    transports: Sequence[str] | None = None,
    git_dir: str | os.PathLike[str] | None = None,
    work_tree: str | os.PathLike[str] | None = None,
    index_file: str | os.PathLike[str] | None = None,
    object_directory: str | os.PathLike[str] | None = None,
) -> dict[str, str]:
    """Return the whole environment for one git call: an allowlist.

    Nothing of the caller's is inherited: no `HOME` (so no global configuration or
    attributes file is read), no `GIT_*`, no `LD_*`, and no proxy or certificate
    setting. A caller's proxy, with the certificates that authenticate it, could
    counterfeit a fetch that every later check would find consistent (Codex on #369).
    Every other environment setting is fixed:
    - configuration comes from no file;
    - there are no replacement objects and no prompt;
    - `LC_ALL=C`;
    - hooks and file-system monitors are off by command-scope configuration, which
      outranks the repository's own.

    ``transports`` refuses every transport but those named. The routing arguments are
    the only repository selectors added.
    """
    environment = {
        "PATH": TRUSTED_EXECUTABLE_PATH,
        "LC_ALL": "C",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_SYSTEM": os.devnull,
        "GIT_ATTR_NOSYSTEM": "1",
        "GIT_NO_REPLACE_OBJECTS": "1",
        "GIT_TERMINAL_PROMPT": "0",
        # A partial clone's missing object is fetched lazily, through the
        # repository's own transport configuration (Codex on #369).
        "GIT_NO_LAZY_FETCH": "1",
    }
    configuration = list(_PINNED_CONFIGURATION)
    if transports is not None:
        configuration.append(("protocol.allow", "never"))
        configuration.extend(
            (f"protocol.{name}.allow", "always") for name in transports
        )
        # `protocol.allow` is only a default: a repository's own
        # `protocol.<name>.allow` re-allowed a refused transport (Codex on #369).
        # `GIT_ALLOW_PROTOCOL` outranks every configuration.
        environment["GIT_ALLOW_PROTOCOL"] = ":".join(transports)
    environment["GIT_CONFIG_COUNT"] = str(len(configuration))
    for index, (key, value) in enumerate(configuration):
        environment[f"GIT_CONFIG_KEY_{index}"] = key
        environment[f"GIT_CONFIG_VALUE_{index}"] = value
    routing: dict[str, str | os.PathLike[str] | None] = {
        "GIT_DIR": git_dir,
        "GIT_WORK_TREE": work_tree,
        "GIT_INDEX_FILE": index_file,
        "GIT_OBJECT_DIRECTORY": object_directory,
    }
    for name, selected in routing.items():
        if selected is not None:
            environment[name] = os.fspath(selected)
    return environment


def without_git_variables(environment: dict[str, str]) -> dict[str, str]:
    """Return ``environment`` without any `GIT_*` variable, whatever its name.

    For a child that is not git but must not route git elsewhere.
    """
    return {
        name: value
        for name, value in environment.items()
        if not name.startswith("GIT_")
    }


def caller_git_environment(environment: dict[str, str]) -> dict[str, str]:
    """Return ``environment`` for Git run on the caller's own checkout with the caller's
    configuration: without any `GIT_*` variable, which would route Git elsewhere, and
    without any `LD_*` or `DYLD_*` variable, which would load other code into it
    (CodeAnt on #369)."""
    return {
        name: value
        for name, value in without_git_variables(environment).items()
        if not name.startswith(("LD_", "DYLD_"))
    }


def run_git(
    arguments: Sequence[str],
    *,
    cwd: Path,
    environment: dict[str, str],
    stdout: int | IO[bytes] = subprocess.PIPE,
    timeout: float = _GIT_TIMEOUT_SECONDS,
) -> subprocess.CompletedProcess[bytes]:
    """Run the trusted git once, in ``cwd``, with ``environment`` (build it with
    `git_environment`). It is where Git runs (Codex on #369); a caller that still
    runs Git itself is declared debt in `policy/owned-responsibilities.yaml`.

    A failure raises `GitFailure`, carrying Git's stderr; a git that cannot be
    started, or that outlives ``timeout``, raises `TrustedExecutionError`. Each
    caller maps them to its own error (CodeAnt on #369). A caller that names no
    timeout gets `_GIT_TIMEOUT_SECONDS`: without one, a stalled `git add` waited
    forever (CodeAnt on #369).
    """
    command = next((a for a in arguments if not a.startswith("-")), "")
    try:
        return subprocess.run(  # nosec B603  # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-audit.dangerous-subprocess-use-audit
            [git_executable(), *arguments],
            cwd=cwd,
            env=environment,
            stdout=stdout,
            stderr=subprocess.PIPE,
            check=True,
            timeout=timeout,
        )
    except subprocess.CalledProcessError as exc:
        raise GitFailure(command, exc.stderr or b"") from exc
    except subprocess.TimeoutExpired as exc:
        raise TrustedExecutionError(
            f"git {command} timed out after {timeout} s"
        ) from exc
    except OSError as exc:
        raise TrustedExecutionError(f"git {command} could not run: {exc}") from exc


def _read(repository: Path, *arguments: str) -> bytes:
    """Run one read of ``repository``, in a shape `_READS` allows, and return its
    output.

    Git refuses a repository another user owns, as provider CI's container user finds
    the runner's checkout, and a refused listing was read as "no repository"
    (CodeRabbit on #369). An allowed read runs no program the repository configures,
    so this read, and only it, names that one repository as safe.
    """
    if not arguments or arguments[0] not in _READS:
        raise ValueError(f"not an allowed read: {arguments[:1]}")
    allowed = _READS[arguments[0]]
    for argument in arguments[1:]:
        if argument.startswith("-") and argument not in allowed:
            raise ValueError(f"{arguments[0]} may not take {argument!r} here")
    # No transport at all: a read fetches nothing, so a Git that ignores
    # `GIT_NO_LAZY_FETCH` still runs no upload-pack (Codex on #369).
    environment = git_environment(transports=())
    count = int(environment["GIT_CONFIG_COUNT"])
    environment["GIT_CONFIG_COUNT"] = str(count + 1)
    environment[f"GIT_CONFIG_KEY_{count}"] = "safe.directory"
    # Git normalizes both this value and the repository's path with its own real
    # path, so an absolute path names it without touching the file system here
    # (SonarCloud S6549 on #369).
    environment[f"GIT_CONFIG_VALUE_{count}"] = os.path.abspath(repository)
    # One way into the repository: entering it. Naming it again with `-C` resolved a
    # relative path twice (CodeAnt on #369).
    return run_git(
        list(arguments),
        cwd=repository,
        environment=environment,
        timeout=_READ_TIMEOUT_SECONDS,
    ).stdout


def repository_read(repository: Path, *arguments: str) -> str:
    """Return the output of one read of ``repository``, which may be untrusted.

    `git_environment()` cannot neutralize a repository's own configuration, and inside
    a repository that configuration can name programs: filters, diff drivers,
    textconv, `gpg.program`. So a call in a repository you do not trust is either a
    read of a shape `_READS` allows, which runs none of them, or runs under
    `disposable_git_metadata`, as `extract_tree` does (Codex on #369). Any other
    command or option is refused with `ValueError`; a failed read raises
    `TrustedExecutionError`.
    """
    # Only the final newline is Git's: a leading or trailing space can belong to a
    # listed path (CodeAnt on #369).
    output = _read(repository, *arguments).decode("utf-8", errors="surrogateescape")
    return output.removesuffix("\n")


def repository_files(directory: Path) -> list[str] | None:
    """Return every path the repository at ``directory`` tracks, as the file system
    names it, or None if ``directory`` is in no repository.

    `git ls-files -z` writes each path's bytes as they are, so a path that is not
    UTF-8 is decoded as the file system's own name for it (CodeRabbit and CodeAnt on
    #369). A repository Git cannot list raises `TrustedExecutionError`: a caller that
    walked it instead would read its untracked files as tracked.
    """
    try:
        listed = _read(directory, "ls-files", "-z")
    except GitFailure as exc:
        # Git says the same of a broken `.git` pointer, which names a repository the
        # caller must not walk as if there were none (CodeAnt on #369).
        if b"not a git repository" in exc.stderr and not _git_entry_above(directory):
            return None
        raise
    return [os.fsdecode(path) for path in listed.split(b"\0") if path]


def _git_entry_above(directory: Path) -> bool:
    """Whether ``directory`` or a parent has a `.git` entry: Git looks up through the
    parents, so a broken one above names a repository too (CodeAnt on #369)."""
    try:
        start = Path(directory).resolve()
    except (OSError, RuntimeError):
        return True
    return any(os.path.lexists(place / ".git") for place in (start, *start.parents))


def repository_format(repository: Path) -> str:
    """Return the object format of the repository at ``repository``: sha1 or sha256."""
    return repository_read(repository, "rev-parse", "--show-object-format")


def repository_objects(repository: Path) -> Path:
    """Return the object store of the repository at ``repository``."""
    common = repository_read(
        repository, "rev-parse", "--path-format=absolute", "--git-common-dir"
    )
    return Path(common) / "objects"


@contextmanager
def disposable_git_metadata(
    objects: str | os.PathLike[str], *, object_format: str = "sha1"
) -> Iterator[Path]:
    """Yield a bare repository from an empty template, bound to ``objects``.

    It takes the object format of the store it binds, as `repository_format` reads
    it, since a SHA-1 repository cannot name a SHA-256 object (CodeAnt on #369). No
    hook, configuration, attribute or ref of any existing repository comes with it,
    and its own attributes undo any that a tree sets on its content.
    It is gone when the block ends. A failure to set it up is the owner's error
    (CodeAnt on #369). One inside the caller's block is the caller's, and passes
    through as it is.

    The store is named in the metadata's line-delimited `alternates` file. A path
    holding a newline would name two directories there, neither of them the store,
    so it is refused (Codex on #369).
    """
    try:
        # Strictly: on Python 3.14 a loop resolves without error, and a store that
        # does not resolve cannot be bound (Codex on #369).
        store = str(Path(objects).resolve(strict=True))
    # A link loop raises RuntimeError in Python 3.11 and 3.12 (CodeAnt on #369).
    except (OSError, RuntimeError) as exc:
        raise TrustedExecutionError(
            f"cannot resolve the object store {objects}: {exc}"
        ) from exc
    if "\n" in store or "\r" in store:
        raise TrustedExecutionError(
            f"an object store whose path holds a line break cannot be bound: {store!r}"
        )
    try:
        holder = tempfile.TemporaryDirectory(prefix="gnostoa-git-")
    except OSError as exc:
        raise TrustedExecutionError(
            f"cannot make disposable Git metadata: {exc}"
        ) from exc
    with holder as directory:
        try:
            base = Path(directory)
            template = base / "template"
            template.mkdir(mode=0o700)
            git_dir = base / "git"
            run_git(
                [
                    "init",
                    "--quiet",
                    "--bare",
                    f"--object-format={object_format}",
                    f"--template={template}",
                    str(git_dir),
                ],
                cwd=base,
                environment=git_environment(),
            )
            alternates = git_dir / "objects" / "info" / "alternates"
            alternates.parent.mkdir(parents=True, exist_ok=True)
            # The store's name as the file system holds it: a byte that is not UTF-8
            # raised `UnicodeEncodeError`, which escaped the owner (Codex on #369).
            alternates.write_bytes(os.fsencode(store) + b"\n")
            # `info/attributes` outranks every `.gitattributes`, so a tree's own
            # attributes change no byte of it: `export-ignore` dropped a file, and
            # `eol`, `ident` and `working-tree-encoding` rewrote one (CodeAnt on #369).
            attributes = git_dir / "info" / "attributes"
            attributes.parent.mkdir(parents=True, exist_ok=True)
            attributes.write_text(_NEUTRAL_ATTRIBUTES, encoding="utf-8")
        except OSError as exc:
            raise TrustedExecutionError(
                f"cannot set up disposable Git metadata: {exc}"
            ) from exc
        yield git_dir


def extract_tree(repository: Path, tree: str, destination: Path) -> None:
    """Materialize the exact tree ``tree`` of ``repository`` into ``destination``.

    The archive is made under disposable metadata, so the repository's own attributes
    and filter drivers do not apply, and the metadata's own attributes undo any the
    tree's `.gitattributes` set: the files are the tree's bytes, and none is left out.
    It is extracted with `tarfile`'s `data` filter (PEP 706).

    - ``tree`` is the full object name in the repository's format. Forty hex digits are
      an abbreviation in a SHA-256 repository, which Git would resolve to whatever
      object they match (CodeAnt on #369).
    - ``tree`` names a tree. Given a commit, `git archive` archives the commit's tree,
      so a commit id would pass for a tree id (CodeAnt on #369). Any other object
      raises `ValueError`.
    - ``destination`` must be missing or an empty directory. The tree is extracted
      beside it and moved into place whole by one `rename`, which replaces an empty
      directory and refuses anything else. A tree extracted in part would pass for a
      whole one (CodeAnt and CodeRabbit on #369).
    - A member the filter refuses, a tree Git cannot archive, a destination that
      changes meanwhile and any file-system failure each raise
      `TrustedExecutionError`.
    """
    # A tree that is no string raised `TypeError` past callers that map `ValueError`
    # (CodeAnt on #369).
    if not isinstance(tree, str) or not _OBJECT_NAME.fullmatch(tree):
        raise ValueError(f"an exact object name is needed, not {tree!r}")
    if not hasattr(tarfile, "data_filter"):
        raise TrustedExecutionError("tarfile-data-filter-unavailable")
    try:
        # `exists` follows a link, and only the final rename refused one (CodeAnt on
        # #369).
        if destination.is_symlink():
            raise TrustedExecutionError(f"{destination} is a link")
        if destination.exists() and not destination.is_dir():
            raise TrustedExecutionError(f"{destination} is not a directory")
        if destination.exists() and any(destination.iterdir()):
            raise TrustedExecutionError(f"{destination} is not empty")
    except OSError as exc:
        # An unreadable destination, too (CodeAnt on #369).
        raise TrustedExecutionError(f"cannot inspect {destination}: {exc}") from exc
    object_format = repository_format(repository)
    if len(tree) != _OBJECT_NAME_LENGTH.get(object_format, 0):
        raise ValueError(f"{tree!r} is not a full {object_format} object name")
    objects = repository_objects(repository)
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        # The tree is staged beside its destination. Whoever else may write the
        # parent, or a directory on the way, could swap the staging directory for a
        # link while the tree is extracted (CodeAnt on #369).
        if trusted_directory(os.path.abspath(destination.parent)) is None:
            raise TrustedExecutionError(
                f"{destination.parent} may be changed by someone else, so no tree is"
                " staged in it"
            )
        staging = Path(
            tempfile.mkdtemp(prefix=f".{destination.name}.", dir=destination.parent)
        )
    except OSError as exc:
        raise TrustedExecutionError(f"cannot stage {destination}: {exc}") from exc
    try:
        _archive_into(objects, object_format, tree, staging)
        # One rename: it replaces an empty directory and refuses a filled one, so
        # another writer is the owner's error, never a raw OSError (CodeRabbit on
        # #369).
        try:
            staging.rename(destination)
        except OSError as exc:
            raise TrustedExecutionError(
                f"{destination} changed while the tree was extracted: {exc}"
            ) from exc
    finally:
        shutil.rmtree(staging, ignore_errors=True)


def _archive_into(objects: Path, object_format: str, tree: str, staging: Path) -> None:
    """Archive ``tree`` under disposable metadata and extract it into ``staging``."""
    try:
        with (
            disposable_git_metadata(objects, object_format=object_format) as git_dir,
            tempfile.TemporaryDirectory(prefix="gnostoa-tree-") as scratch,
        ):
            environment = git_environment(git_dir=git_dir, object_directory=objects)
            kind = run_git(
                ["cat-file", "-t", tree],
                cwd=git_dir,
                environment=environment,
                timeout=_READ_TIMEOUT_SECONDS,
            ).stdout.strip()
            if kind != b"tree":
                raise ValueError(
                    f"{tree} is a {kind.decode(errors='replace')}, not a tree"
                )
            archive = Path(scratch) / "tree.tar"
            with archive.open("wb") as handle:
                run_git(
                    ["archive", "--format=tar", tree],
                    cwd=git_dir,
                    environment=environment,
                    stdout=handle,
                    timeout=_ARCHIVE_TIMEOUT_SECONDS,
                )
            with tarfile.open(archive) as handle:
                handle.extractall(staging, filter="data")
    except tarfile.TarError as exc:
        raise TrustedExecutionError(f"a member of the tree was refused: {exc}") from exc
    except OSError as exc:
        # A full disk or a vanished scratch directory (CodeAnt on #369).
        raise TrustedExecutionError(f"cannot extract {tree}: {exc}") from exc
