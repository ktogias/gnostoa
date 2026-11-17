"""The pinned shell parser pair is installed and compatible, the surfaces it reads are
the repository's, and the assessment's retained evidence is what it names
(Decision 0108). The shared interim helpers are in
`shell_parser_dependency_support`."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess  # nosec B404 -- test-only boundary; the argv below is literal
import tarfile
import tempfile
import tomllib
import unittest
from importlib import metadata
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from tests.shell_parser_dependency_support import (
    BOM,
    INSTRUCTION_FILES,
    ROOT,
    _declared,
    _dockerfile_runs,
    _facts,
    _probe,
    _shell_surfaces,
    _workflow_runs,
)
from tools.repository_scope import candidate_paths


class ShellParserDependencyTests(unittest.TestCase):
    def test_the_pinned_pair_is_installed(self) -> None:
        """`tree-sitter` 0.26.0 segfaulted with this grammar in the evaluation, so
        the pair is pinned together; the grammar's ABI is the runtime's.

        This smoke cannot reproduce that crash: it needs the reader's nested parses
        (the assessment's "The tree-sitter 0.26.0 crash"). Changing either version
        here therefore also needs the reader re-run over the corpus first."""
        self.assertEqual("0.25.2", metadata.version("tree-sitter"))
        self.assertEqual("0.25.1", metadata.version("tree-sitter-bash"))
        self.assertEqual(15, _probe([])["abi"])

    def test_the_pair_is_declared_exactly(self) -> None:
        """An install from the package metadata alone takes the same pair as the
        locks (Codex and CodeAnt on #394; Decision 0108, items 7 and 14)."""
        project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        declared = project["project"]["dependencies"]
        self.assertIn("tree-sitter==0.25.2", declared)
        self.assertIn("tree-sitter-bash==0.25.1", declared)
        self.assertEqual(
            [],
            [
                line
                for line in declared
                if line.startswith("tree-sitter") and "==" not in line
            ],
        )

    def test_the_grammar_reads_what_the_shell_reader_relies_on(self) -> None:
        cases = {
            # A substitution in an assignment, then the command after it.
            "x=`date` git status": ["date", "git"],
            # Single quotes keep a substitution inert; double quotes do not.
            "echo '$(git status)'": ["echo"],
            'echo "$(git status)"': ["echo", "git"],
            # A quoted newline is part of its word.
            "echo 'abc\ndef`git status`'": ["echo"],
            # A comment's apostrophe opens no quote.
            "echo hi # it's\ngit status": ["echo", "git"],
            # A function body and a process substitution hold commands.
            "f() { git log; }": ["git"],
            "cat < <(git status)": ["cat", "git"],
            # A quoted command word keeps its quotes in the tree, so the shell
            # reader unquotes it (Kody on #394; Decision 0108, item 11).
            '"git" status': ['"git"'],
            "'git' status": ["'git'"],
            'g"i"t status': ['g"i"t'],
            'echo "$("git" status)"': ['"git"', "echo"],
            'f() { "git" status; }; f': ['"git"', "f"],
            'cat < <("git" status)': ['"git"', "cat"],
        }
        facts = _facts(list(cases))
        for (text, names), found in zip(cases.items(), facts, strict=True):
            with self.subTest(text=text):
                self.assertEqual(sorted(names), found["names"])
                self.assertEqual(0, found["errors"])
        heredoc = _facts(['bash 2>&1 <<EOF\n"git" status\nEOF\n'])[0]
        self.assertEqual(['"git" status\n'], heredoc["heredocs"])
        # In source order (CodeAnt on #394).
        facts = _facts(["cat <<A\none\nA\ncat <<B\ntwo\nB\n"])
        self.assertEqual(["one\n", "two\n"], facts[0]["heredocs"])

    def test_every_shell_surface_parses_without_an_unexpected_error(self) -> None:
        """Every surface kind of the frozen corpus parses with no error. The
        instruction fences' placeholders are documentation, not shell, so each is
        masked at its own width first (Codex, Kody and CodeAnt on #394)."""
        surfaces = _shell_surfaces()
        self.assertGreater(len(surfaces), 50)
        self._assert_corpus_surface_identities(surfaces)
        for kind in (
            ".github/workflows/verification.yml#",
            ".gitlab-ci.yml#",
            "ci/gitlab-ci.yml#",
            "ci/github-actions.yml#",
            "Dockerfile#",
            "AGENTS.md#",
            "ci/verify",
            "knowledge/assessments/365-duplication-inventory-2026-10-05-evidence/"
            "duplicate_code.sh",
        ):
            with self.subTest(kind=kind):
                self.assertTrue(any(name.startswith(kind) for name in surfaces))
        facts = _facts(list(surfaces.values()))
        broken = {
            name for name, found in zip(surfaces, facts, strict=True) if found["errors"]
        }
        # With its placeholders masked, every surface, the instruction fences
        # included, parses with no error at all (Codex and CodeAnt on #394).
        self.assertEqual(set(), broken)
        self.assertTrue(
            any(
                Path(name.split("#")[0]).name in INSTRUCTION_FILES and "_exact-" in text
                for name, text in surfaces.items()
            )
        )

    def _assert_corpus_surface_identities(self, surfaces: dict[str, str]) -> None:
        """Keep the existing corpus and current-source identity assertions together."""
        declared = {path.as_posix() for path in candidate_paths(ROOT)}
        # Each file of the frozen corpus that is still tracked still yields a
        # surface, so an extraction that drops one fails here (CodeAnt on #396).
        evidence = json.loads(
            (
                ROOT / "knowledge/assessments/0108-shell-parser-evaluation.json"
            ).read_text(encoding="utf-8")
        )
        found = {name.split("#", 1)[0] for name in surfaces}
        for path in sorted(
            {script["path"] for script in evidence["scripts"]} & declared
        ):
            if (ROOT / path).is_file():
                with self.subTest(corpus_file=path):
                    self.assertIn(path, found)
        # A separate current-parent fixture supplements the historical evidence;
        # it never rewrites the frozen evaluation. Only byte-identical source
        # files inherit its expected surface identities (CodeAnt on #396).
        coverage = json.loads(
            (ROOT / "tests/fixtures/shell_parser_corpus_coverage.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(
            coverage["frozen_evidence_sha256"],
            hashlib.sha256(
                (
                    ROOT / "knowledge/assessments/0108-shell-parser-evaluation.json"
                ).read_bytes()
            ).hexdigest(),
        )
        self.assertEqual(
            {script["path"] for script in evidence["scripts"]},
            {record["path"] for record in coverage["files"]},
        )
        for record in coverage["files"]:
            source = ROOT / record["path"]
            if (
                record["path"] not in declared
                or not source.is_file()
                or hashlib.sha256(source.read_bytes()).hexdigest()
                != record["source_sha256"]
            ):
                continue
            expected = {
                script["id"]: script["masked_sha256"] for script in record["surfaces"]
            }
            actual = {
                name: hashlib.sha256(text.encode("utf-8")).hexdigest()
                for name, text in surfaces.items()
                if name.split("#", 1)[0] == record["path"]
            }
            self.assertEqual(
                expected, actual, f"{record['path']}: surface identities differ"
            )


class SurfaceExtractionTests(unittest.TestCase):
    """Each extraction rule, and each case it refuses rather than misreads."""

    def test_a_run_instruction_is_read_as_docker_hands_it_to_the_shell(self) -> None:
        text = (
            "FROM alpine\n"
            "RUN --mount=type=bind,source=a,target=/b \\\n"
            "    set -eux; \\\n"
            "    # a comment Docker drops\n"
            "    echo 'a b'\n"
            'RUN ["python", "-V"]\n'
            "run true\n"
        )
        self.assertEqual(["set -eux;     echo 'a b'", "true"], _dockerfile_runs(text))
        # Exec form is a JSON list of strings; a shell test is not (CodeAnt on #394).
        self.assertEqual(
            ["[ -f marker ] && git status"],
            _dockerfile_runs(
                'FROM alpine\nRUN ["python", "-V"]\nRUN [ -f marker ] && git status\n'
            ),
        )

    def test_an_exec_form_shell_run_hands_its_command_to_the_shell(self) -> None:
        """`RUN ["bash", "-c", "…"]` still asks bash to parse its command; another
        shell in exec form fails closed (cubic on #396)."""
        self.assertEqual(
            ["git status"],
            _dockerfile_runs(
                'RUN ["/bin/bash", "-o", "pipefail", "-c", "git status"]\n'
            ),
        )
        self.assertEqual([], _dockerfile_runs('RUN ["python", "-c", "print()"]\n'))
        with self.assertRaisesRegex(AssertionError, "an exec-form `zsh` RUN"):
            _dockerfile_runs('RUN ["zsh", "-c", "git status"]\n')

    def test_a_run_here_document_or_another_escape_fails_closed(self) -> None:
        with self.assertRaisesRegex(AssertionError, "here-document"):
            _dockerfile_runs("FROM alpine\nRUN <<EOF\ngit status\nEOF\n")
        with self.assertRaisesRegex(AssertionError, "escape directive"):
            _dockerfile_runs("# escape=`\nRUN true\n")
        # The default escape may be stated (CodeAnt on #396).
        self.assertEqual(
            ["true"], _dockerfile_runs("# escape=\\\nFROM alpine\nRUN true\n")
        )

    def test_a_dockerfile_shell_override_is_honoured_or_fails_closed(self) -> None:
        """A `SHELL` instruction to bash or sh keeps the `RUN` lines shell; to
        another program it fails closed (CodeAnt on #394)."""
        self.assertEqual(
            ["git status"],
            _dockerfile_runs(
                'SHELL ["/bin/bash", "-o", "pipefail", "-c"]\nRUN git status\n'
            ),
        )
        with self.assertRaisesRegex(AssertionError, "a `pwsh` SHELL"):
            _dockerfile_runs('SHELL ["pwsh", "-Command"]\nRUN Write-Output hi\n')

    def test_a_workflow_step_is_read_with_its_expressions_masked(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "w.yml"
            path.write_bytes(
                BOM + b"jobs:\n  j:\n    defaults:\n      run:\n        shell: bash\n"
                b"    steps:\n      - run: echo ${{ github.sha }}\n"
                b"      - run: git status\n        shell: sh\n"
            )
            self.assertEqual(
                sorted(["echo " + "_" * 17, "git status"]),
                sorted(_workflow_runs(path)),
            )

    def test_a_multi_line_expression_keeps_its_line_breaks(self) -> None:
        """Masking keeps each newline, so the shell's lines stay where they were
        (CodeAnt on #394)."""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "w.yml"
            path.write_text(
                "on: push\njobs:\n  j:\n    runs-on: ubuntu-latest\n    steps:\n"
                "      - run: |\n          echo ${{ fromJSON(\n            x) }}\n"
                "          git status\n",
                "utf-8",
            )
            runs = _workflow_runs(path)
            self.assertEqual(
                ["echo " + "_" * 13 + "\n" + "_" * 7 + "\ngit status\n"], runs
            )
            self.assertEqual(3, runs[0].count("\n"))

    def test_a_step_in_another_language_or_broken_yaml_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "w.yml"
            path.write_text(
                "on: push\njobs:\n  j:\n    runs-on: ubuntu-latest\n    steps:\n"
                "      - run: print(1)\n        shell: python\n",
                "utf-8",
            )
            with self.assertRaisesRegex(AssertionError, "`python` step"):
                _workflow_runs(path)
            path.write_text("steps: [\n", "utf-8")
            with self.assertRaisesRegex(AssertionError, "w.yml: not YAML"):
                _workflow_runs(path)

    def test_every_surface_kind_is_found_and_a_make_recipe_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".github" / "workflows").mkdir(parents=True)
            (root / ".github" / "workflows" / "w.yml").write_text(
                "on: push\njobs:\n  j:\n    runs-on: ubuntu-latest\n    steps:\n"
                "      - run: git status\n",
                "utf-8",
            )
            (root / "AGENTS.md").write_text(
                "x\n```bash\ngit log <ref>\n```\n```python\nprint()\n```\n", "utf-8"
            )
            # An instruction file is found by its name, at any depth (Codex on #394).
            (root / "sub").mkdir()
            (root / "sub" / "AGENTS.md").write_text(
                "```sh\ngit fetch <remote>\n```\n", "utf-8"
            )
            (root / "Dockerfile").write_text("FROM alpine\nRUN git fetch\n", "utf-8")
            (root / "deep" / "er").mkdir(parents=True)
            (root / "deep" / "er" / "tool").write_bytes(BOM + b"#!/bin/sh\ngit gc\n")
            (root / "deep" / "data.bin").write_bytes(b"\xff\xfe")
            # A hidden source directory is read; an untracked file is not (Codex on
            # #394).
            (root / ".husky").mkdir()
            (root / ".husky" / "pre-commit").write_text(
                "#!/bin/sh\ngit diff\n", "utf-8"
            )
            (root / "scratch").write_text("#!/bin/sh\nuntracked\n", "utf-8")
            self.assertEqual(
                {
                    ".github/workflows/w.yml#0": "git status",
                    "AGENTS.md#0": "git log _ref_\n",
                    "sub/AGENTS.md#0": "git fetch _remote_\n",
                    "Dockerfile#0": "git fetch",
                    "deep/er/tool": "#!/bin/sh\ngit gc\n",
                    ".husky/pre-commit": "#!/bin/sh\ngit diff\n",
                },
                _shell_surfaces(_declared(root, unlisted=("scratch",))),
            )
            (root / "deep" / "er" / "tool").write_bytes(b"#!/bin/sh\n\xff\n")
            declared = _declared(root, unlisted=("scratch",))
            with self.assertRaises(UnicodeDecodeError):
                _shell_surfaces(declared)
            (root / "deep" / "er" / "tool").unlink()
            (root / "Makefile").write_text("all:\n\tgit status\n", "utf-8")
            declared = _declared(root, unlisted=("scratch",))
            with self.assertRaisesRegex(AssertionError, "Makefile: a Make recipe"):
                _shell_surfaces(declared)

    def test_a_probe_answer_that_is_not_json_is_reported(self) -> None:
        answer = SimpleNamespace(returncode=0, stdout="warn", stderr="")
        with (
            patch("subprocess.run", return_value=answer),
            self.assertRaisesRegex(AssertionError, "answered no JSON.*'warn'"),
        ):
            _probe([])

    def test_a_probe_answer_of_another_shape_is_reported(self) -> None:
        """Amazon Q on #394: a missing key is named, not a bare KeyError."""
        for stdout in ('{"facts": []}', "[]", '{"abi": 15, "facts": [], "x": 1}'):
            answer = SimpleNamespace(returncode=0, stdout=stdout, stderr="")
            with (
                self.subTest(stdout=stdout),
                patch("subprocess.run", return_value=answer),
                self.assertRaisesRegex(AssertionError, "answered another shape"),
            ):
                _probe([])

    def test_probe_facts_must_be_a_list_of_mappings(self) -> None:
        invalid_facts: tuple[object, ...] = (None, {}, "facts", [None], ["fact"], [1])
        for facts in invalid_facts:
            answer = SimpleNamespace(
                returncode=0, stdout=json.dumps({"abi": 15, "facts": facts}), stderr=""
            )
            with (
                self.subTest(facts=facts),
                patch("subprocess.run", return_value=answer),
                self.assertRaisesRegex(AssertionError, "probe facts"),
            ):
                _facts(["# one\n"])
        for scripts, facts in (
            ([], []),
            (["# one\n"], [{"names": [], "errors": 0, "heredocs": []}]),
        ):
            answer = SimpleNamespace(
                returncode=0, stdout=json.dumps({"abi": 15, "facts": facts}), stderr=""
            )
            with (
                self.subTest(facts=facts),
                patch("subprocess.run", return_value=answer),
            ):
                self.assertEqual(facts, _facts(scripts))

    def test_probe_facts_match_the_input_script_count(self) -> None:
        """A valid-looking fact cannot stand in for a missing or extra script
        result (CodeAnt on #396)."""
        valid = {"names": [], "errors": 0, "heredocs": []}
        for scripts, facts in (
            (["# one\n", "# two\n"], [valid]),
            (["# one\n"], [valid, valid]),
            ([], [valid]),
            (["# one\n"], []),
        ):
            answer = SimpleNamespace(
                returncode=0,
                stdout=json.dumps({"abi": 15, "facts": facts}),
                stderr="",
            )
            with (
                self.subTest(scripts=len(scripts), facts=len(facts)),
                patch("subprocess.run", return_value=answer),
                self.assertRaisesRegex(AssertionError, "one fact per input script"),
            ):
                _facts(scripts)

    def test_probe_fact_fields_follow_the_producer_contract(self) -> None:
        """Malformed facts must fail before a falsy error value reaches the smoke
        (CodeAnt on #396). Empty names and here-documents are valid lists."""
        valid = {"names": [], "errors": 0, "heredocs": []}
        error_values: tuple[object, ...] = (None, "", [], False, True, 0.0, -1)
        invalid = [
            {},
            {"commands": []},
            {key: value for key, value in valid.items() if key != "names"},
            {**valid, "unexpected": []},
            *({**valid, "names": value} for value in (None, "git", [None], [1])),
            *({**valid, "errors": value} for value in error_values),
            *({**valid, "heredocs": value} for value in (None, "", [None], [1])),
        ]
        for fact in invalid:
            answer = SimpleNamespace(
                returncode=0,
                stdout=json.dumps({"abi": 15, "facts": [fact]}),
                stderr="",
            )
            with (
                self.subTest(fact=fact),
                patch("subprocess.run", return_value=answer),
                self.assertRaisesRegex(AssertionError, "probe fact"),
            ):
                _facts(["git status"])
        for fact in (
            valid,
            {"names": ["git", "git"], "errors": 2, "heredocs": ["", "text\n"]},
        ):
            answer = SimpleNamespace(
                returncode=0,
                stdout=json.dumps({"abi": 15, "facts": [fact]}),
                stderr="",
            )
            with (
                self.subTest(valid_fact=fact),
                patch("subprocess.run", return_value=answer),
            ):
                self.assertEqual([fact], _facts(["git status"]))
        self.assertEqual(
            [{"names": [], "errors": 0, "heredocs": []}], _facts(["# no command\n"])
        )

    def test_corpus_smoke_rejects_omitted_or_replaced_surfaces(self) -> None:
        """A sibling surface must not hide a missing one behind the same path
        (CodeAnt on #396). The actual unchanged-parent workflow has two."""
        surfaces = _shell_surfaces()
        target = ".github/workflows/analyzer-readback.yml#0"
        self.assertIn(target, surfaces)
        self.assertIn(".github/workflows/analyzer-readback.yml#1", surfaces)
        omitted = {name: text for name, text in surfaces.items() if name != target}
        replaced = {**surfaces, target: "git status\n"}
        method = "test_every_shell_surface_parses_without_an_unexpected_error"
        for changed in (omitted, replaced):
            smoke = getattr(ShellParserDependencyTests(method), method)
            with (
                self.subTest(surface_count=len(changed)),
                patch(__name__ + "._shell_surfaces", return_value=changed),
                self.assertRaisesRegex(AssertionError, "surface identities"),
            ):
                smoke()

        # Physical presence does not make a historical file canonical source.
        path = ".github/workflows/analyzer-readback.yml"
        declared = [
            entry for entry in candidate_paths(ROOT) if entry.as_posix() != path
        ]
        self.assertTrue((ROOT / path).is_file())
        smoke = getattr(ShellParserDependencyTests(method), method)
        with patch(__name__ + ".candidate_paths", return_value=declared):
            smoke()

    def test_corpus_guard_keeps_changed_source_applicability_explicit(self) -> None:
        """Older surface identities do not govern changed raw source bytes. The
        ordinary kind and parser checks still run; this is not a completeness
        claim for changed files."""
        surfaces = _shell_surfaces()
        target = ".github/workflows/analyzer-readback.yml#0"
        changed = {**surfaces, target: surfaces[target] + "\n# changed source\n"}
        source = ROOT / ".github/workflows/analyzer-readback.yml"
        read_bytes = Path.read_bytes

        def after_source_edit(path: Path) -> bytes:
            content = read_bytes(path)
            return content + b"\n# changed source\n" if path == source else content

        method = "test_every_shell_surface_parses_without_an_unexpected_error"
        with patch.object(Path, "read_bytes", after_source_edit):
            with patch(__name__ + "._shell_surfaces", return_value=changed):
                getattr(ShellParserDependencyTests(method), method)()
            malformed = {**changed, target: "if true; then\n"}
            smoke = getattr(ShellParserDependencyTests(method), method)
            with (
                patch(__name__ + "._shell_surfaces", return_value=malformed),
                self.assertRaises(AssertionError) as rejected,
            ):
                smoke()
            self.assertIn(target, str(rejected.exception))
            self.assertNotIn("surface identities", str(rejected.exception))

    def test_a_default_shell_in_another_language_fails_closed(self) -> None:
        """A step inherits the job's or the workflow's `defaults.run.shell`
        (Claude on #394)."""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "w.yml"
            for document in (
                "defaults:\n  run:\n    shell: pwsh\njobs:\n  j:\n    steps:\n"
                "      - run: Get-Content x\n",
                "jobs:\n  j:\n    defaults:\n      run:\n        shell: python\n"
                "    steps:\n      - run: print(1)\n",
            ):
                path.write_text(document, "utf-8")
                with (
                    self.subTest(document=document),
                    self.assertRaisesRegex(AssertionError, "a `(pwsh|python)` default"),
                ):
                    _workflow_runs(path)

    def test_a_dockerfile_variant_fails_closed(self) -> None:
        """Only `Dockerfile` itself is read; another container file fails closed
        rather than going unread (Claude on #394)."""
        for name in ("Dockerfile.ci", "build.Dockerfile", "Containerfile"):
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                (root / name).write_text("FROM a\nRUN true\n", "utf-8")
                declared = _declared(root)
                with (
                    self.subTest(name=name),
                    self.assertRaisesRegex(AssertionError, "a container file"),
                ):
                    _shell_surfaces(declared)


RETAINED_SCRIPTS = [
    "stress_probe.py",
    "audit_oracle.py",
    "audit_docs.py",
    "evaluate314.py",
    "corpus_scripts.py",
    "diff_parsers.py",
    "oracle.py",
    "docs.py",
    "worker.py",
    "parent.py",
    "spike.py",
    "gate.py",
    "crash_doc.py",
]


class RetainedEvidenceTests(unittest.TestCase):
    """The assessment's retained evidence is the evidence it names (Codex and
    CodeRabbit on #394)."""

    ASSESSMENT = ROOT / "knowledge/assessments/0108-shell-parser-evaluation.md"
    EVIDENCE = ROOT / "knowledge/assessments/0108-shell-parser-evaluation.json"

    ARCHIVE = (
        ROOT
        / "knowledge/assessments/0108-shell-parser-evaluation-evidence"
        / "spike-scripts.tar.gz"
    )

    def test_each_retained_script_is_a_native_file_of_its_declared_digest(
        self,
    ) -> None:
        """The scripts are retained as native `.py` files, byte for byte, in the
        evidence archive (Codex on #394; AGENTS.md: executable artifacts stay
        canonical in their native formats). The assessment declares each digest."""
        text = self.ASSESSMENT.read_text(encoding="utf-8")
        declared = dict(
            re.findall(r"^\| `([\w.]+\.py)` \| `([0-9a-f]{16})…` \|", text, re.M)
        )
        with tarfile.open(self.ARCHIVE, "r:gz") as archive:
            members = archive.getmembers()
            # The exact inventory, so a lost script fails too (CodeAnt on #394).
            self.assertEqual(
                sorted(RETAINED_SCRIPTS), [member.name for member in members]
            )
            self.assertEqual(sorted(RETAINED_SCRIPTS), sorted(declared))
            for member in members:
                with self.subTest(script=member.name):
                    self.assertTrue(member.isfile())
                    handle = archive.extractfile(member)
                    if handle is None:
                        self.fail(f"{member.name} has no content")
                    digest = hashlib.sha256(handle.read()).hexdigest()
                    self.assertTrue(digest.startswith(declared[member.name]))
        # The prose holds no copy that could drift from the archive.
        self.assertNotIn("````text", text)

    def test_the_assessment_prints_the_archive_s_digests(self) -> None:
        """The digest prefixes the assessment prints are those of the JSON
        evidence, for the archive and for each script, so neither can go stale
        (CodeAnt on #396)."""
        text = self.ASSESSMENT.read_text(encoding="utf-8")
        scripts = json.loads(self.EVIDENCE.read_text(encoding="utf-8"))["spike_scripts"]
        [archive] = re.findall(
            r"spike-scripts\.tar\.gz\)\n\(SHA-256 `([0-9a-f]{16})…`\)", text
        )
        self.assertTrue(scripts["sha256"].startswith(archive))
        printed = dict(
            re.findall(r"^\| `([\w.]+\.py)` \| `([0-9a-f]{16})…` \|", text, re.M)
        )
        full = {member["name"]: member["sha256"] for member in scripts["members"]}
        self.assertEqual(sorted(full), sorted(printed))
        for name, digest in printed.items():
            with self.subTest(script=name):
                self.assertTrue(full[name].startswith(digest))

    def test_the_evaluated_artifacts_keep_their_full_digests(self) -> None:
        """Decision 0108 item 12 asks for the hashes of the wheels and binaries, so
        the JSON evidence keeps each full SHA-256 and its source, and the prefixes
        the assessment prints are theirs (Codex on #396). The image's full identity
        was never recorded, and the assessment says so."""
        text = self.ASSESSMENT.read_text(encoding="utf-8")
        artifacts = json.loads(self.EVIDENCE.read_text(encoding="utf-8"))["artifacts"]
        self.assertEqual(
            [
                "tree_sitter-0.25.2-cp312-cp312-manylinux2014_x86_64.manylinux_2_17_x86_64.manylinux_2_28_x86_64.whl",
                "tree_sitter_bash-0.25.1-cp310-abi3-manylinux2014_x86_64.manylinux_2_17_x86_64.manylinux_2_28_x86_64.whl",
                "tree_sitter-0.26.0-cp312-cp312-manylinux2014_x86_64.manylinux_2_17_x86_64.manylinux_2_28_x86_64.whl",
                "shfmt_v3.10.0_linux_amd64",
                "shfmt_v3.14.1_linux_amd64",
            ],
            [artifact["name"] for artifact in artifacts],
        )
        printed = re.findall(r"`([0-9a-f]{16})`", text.split("## Corpus", 1)[0])
        self.assertEqual(len(artifacts), len(printed))
        for artifact, prefix in zip(artifacts, printed, strict=True):
            with self.subTest(artifact=artifact["name"]):
                self.assertRegex(artifact["sha256"], r"\A[0-9a-f]{64}\Z")
                self.assertTrue(artifact["sha256"].startswith(prefix))
                self.assertTrue(artifact["source"].startswith("https://"))
        self.assertIn("its full identity was not recorded", " ".join(text.split()))

    def test_the_archive_is_deterministic_and_matches_its_full_digests(self) -> None:
        """The archive and each member match their full SHA-256 in the JSON
        evidence, not a prefix (CodeAnt on #396), and the archive is as deterministic
        as the assessment says: sorted members, no times or owners, mode 0644
        (Claude on #396)."""
        evidence = json.loads(self.EVIDENCE.read_text(encoding="utf-8"))
        scripts = evidence["spike_scripts"]
        self.assertEqual(
            scripts["sha256"], hashlib.sha256(self.ARCHIVE.read_bytes()).hexdigest()
        )
        expected = {member["name"]: member["sha256"] for member in scripts["members"]}
        with tarfile.open(self.ARCHIVE, "r:gz") as archive:
            members = archive.getmembers()
            self.assertEqual(sorted(expected), [member.name for member in members])
            for member in members:
                with self.subTest(script=member.name):
                    self.assertEqual(
                        (0, 0, 0, "", "", 0o644),
                        (
                            member.mtime,
                            member.uid,
                            member.gid,
                            member.uname,
                            member.gname,
                            member.mode,
                        ),
                    )
                    handle = archive.extractfile(member)
                    if handle is None:
                        self.fail(f"{member.name} has no content")
                    self.assertEqual(
                        expected[member.name], hashlib.sha256(handle.read()).hexdigest()
                    )

    def test_the_scripts_materialise_read_only_with_their_digests(self) -> None:
        """Option A, the owner's choice on Codex's P1 (#396, 6064178587): the scripts
        are immutable evidence, not active code, and the assessment says what the
        archive does not give them. Its materialisation block, run as written,
        extracts each original script read-only into a disposable directory, with the
        digest the JSON evidence records, and runs none of them."""
        text = self.ASSESSMENT.read_text(encoding="utf-8")
        flat = " ".join(text.split())
        for phrase in (
            "immutable evidence, not Ruff-clean active code",
            "does not mean they received repository-root static analysis",
            "or ordinary Git line-diff review",
            "It is no general Ruff exclusion",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, flat)
        [block] = [
            block
            for block in re.findall(r"```sh\n(.*?)```", text, re.S)
            if "spike-scripts.tar.gz" in block
        ]
        self.assertNotIn("python", block)
        evidence = json.loads(self.EVIDENCE.read_text(encoding="utf-8"))
        expected = {
            member["name"]: member["sha256"]
            for member in evidence["spike_scripts"]["members"]
        }
        with tempfile.TemporaryDirectory() as directory:
            done = subprocess.run(  # nosec B603  # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-audit.dangerous-subprocess-use-audit  # -- test-only retained materialization recipe with isolated TMPDIR and member digest checks
                ["/bin/sh", "-c", block],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
                timeout=60,
                env={"PATH": "/usr/bin:/bin", "TMPDIR": directory},
            )
            self.assertEqual(0, done.returncode, done.stderr)
            printed = {
                name: digest
                for digest, name in (line.split() for line in done.stdout.splitlines())
            }
            self.assertEqual(expected, printed)
            [made] = list(Path(directory).iterdir())
            files = sorted(made.iterdir())
            self.assertEqual(sorted(expected), [path.name for path in files])
            for path in files:
                with self.subTest(script=path.name):
                    self.assertEqual(
                        expected[path.name],
                        hashlib.sha256(path.read_bytes()).hexdigest(),
                    )
                    # Read-only and not executable.
                    self.assertEqual(0, path.stat().st_mode & 0o333)

    def test_the_oracle_is_retained_with_its_digest(self) -> None:
        evidence = json.loads(self.EVIDENCE.read_text(encoding="utf-8"))
        oracle = evidence["oracle"]["entries"]
        self.assertEqual(76, len(oracle))
        # `oracle.py` wrote it with `json.dump(oracle, …, indent=0)`, so those bytes
        # are what its digest names.
        self.assertEqual(
            evidence["oracle"]["sha256"],
            hashlib.sha256(json.dumps(oracle, indent=0).encode("utf-8")).hexdigest(),
        )
        counts: dict[str, int] = {}
        for entry in oracle:
            counts[entry["path"]] = counts.get(entry["path"], 0) + 1
        self.assertEqual(evidence["oracle_git_commands_per_file"], counts)


if __name__ == "__main__":
    unittest.main()
