"""The workflow step reader's located YAML: what it gives, pinned against the BaseLoader subclass it is
characterized by (#389, owner 6606320054 for #477's TYP-028). The expected shapes below were written by that
implementation on 81c41aa0, the parent of the change, so they are its outputs, not a model of them: per document,
the structure, every scalar's value, type and its first and step, alias identity, and the exception class of a
refusal. Every tracked workflow is read with the same structure and values as yaml's BaseLoader gives."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

import yaml

from tools import quality_evidence

ROOT = Path(__file__).resolve().parent.parent


def located(text: str) -> object:
    """The step reader's located document, through the module's one loading seam."""
    return vars(quality_evidence)["_located_load"](text)


def shape(value: object, seen: dict[int, int]) -> object:
    """A loaded value as plain data: a repeated object as an alias to its first index, so identity counts."""
    if id(value) in seen:
        return ["alias", seen[id(value)]]
    seen[id(value)] = len(seen)
    if isinstance(value, dict):
        return ["map", [[shape(k, seen), shape(v, seen)] for k, v in value.items()]]
    if isinstance(value, list):
        return ["seq", [shape(v, seen) for v in value]]
    return [
        type(value).__name__,
        str(value),
        getattr(value, "first", None),
        getattr(value, "step", None),
    ]


def outcome(text: str) -> object:
    try:
        return ["ok", shape(located(text), {})]
    except (
        yaml.YAMLError,
        ValueError,
        RecursionError,
    ) as exc:  # as the step reader catches them
        return ["refused", type(exc).__name__]


def base_loaded(text: str) -> object:
    """What `yaml.load(text, Loader=yaml.BaseLoader)` returns, by the loader call that builds it: every scalar a
    string, no object of any other type. Written out, it is not the call form Bandit's B506 matches (#477 round 5)."""
    return yaml.BaseLoader(text).get_single_data()


def plain(value: object) -> object:
    """The same document without its locations, as BaseLoader builds it."""
    if isinstance(value, dict):
        return {str(k): plain(v) for k, v in value.items()}
    if isinstance(value, list):
        return [plain(v) for v in value]
    return str(value)


EDGE = {
    "empty": "",
    "comment only": "# x\n",
    "scalar doc": "abc\n",
    "literal": "a: |\n  one\n  two\n",
    "folded": "a: >\n  one\n  two\n",
    "alias": "a: &x {b: 1}\nc: *x\n",
    "recursive": "&a [ *a ]\n",
    "duplicate keys": "a: 1\na: 2\n",
    "complex key": "? [1, 2]\n: v\n",
    "unhashable map key": "? {a: 1}\n: v\n",
    "two documents": "a: 1\n---\nb: 2\n",
    "merge key": "base: &b {x: 1}\nd:\n  <<: *b\n  y: 2\n",
    "tag": "a: !!int 3\nb: !custom x\n",
    "bad indent": "a:\n b: 1\n  c: 2\n",
    "quoted": "a: 'x'\nb: \"y\\n\"\n",
    "null forms": "a: ~\nb: null\nc:\n",
    "deep": "[" * 60 + "]" * 60 + "\n",
    "recursive map": "&a {x: *a}\n",
    "shared twice": "a: &s [1]\nb: *s\nc: *s\n",
    "deeper": "[" * 2000 + "]" * 2000 + "\n",
}

# The replaced implementation's outputs, one case per line, as it wrote them on 81c41aa0.
EXPECTED: dict[str, object] = json.loads(
    r"""{
"empty": ["ok",["NoneType","None",null,null]],
"comment only": ["ok",["NoneType","None",null,null]],
"scalar doc": ["ok",["_Located","abc",1,0]],
"literal": ["ok",["map",[[["_Located","a",1,0],["_Located","one\ntwo\n",2,1]]]]],
"folded": ["ok",["map",[[["_Located","a",1,0],["_Located","one two\n",1,0]]]]],
"alias": ["ok",["map",[[["_Located","a",1,0],["map",[[["_Located","b",1,0],["_Located","1",1,0]]]]],[["_Located","c",2,0],["alias",2]]]]],
"recursive": ["refused","ConstructorError"],
"duplicate keys": ["ok",["map",[[["_Located","a",1,0],["_Located","2",2,0]]]]],
"complex key": ["refused","ConstructorError"],
"unhashable map key": ["refused","ConstructorError"],
"two documents": ["refused","ComposerError"],
"merge key": ["ok",["map",[[["_Located","base",1,0],["map",[[["_Located","x",1,0],["_Located","1",1,0]]]]],[["_Located","d",2,0],["map",[[["_Located","<<",3,0],["alias",2]],[["_Located","y",4,0],["_Located","2",4,0]]]]]]]],
"tag": ["ok",["map",[[["_Located","a",1,0],["_Located","3",1,0]],[["_Located","b",2,0],["_Located","x",2,0]]]]],
"bad indent": ["refused","ScannerError"],
"quoted": ["ok",["map",[[["_Located","a",1,0],["_Located","x",1,0]],[["_Located","b",2,0],["_Located","y\n",2,0]]]]],
"null forms": ["ok",["map",[[["_Located","a",1,0],["_Located","~",1,0]],[["_Located","b",2,0],["_Located","null",2,0]],[["_Located","c",3,0],["_Located","",3,0]]]]],
"deep": ["ok",["seq",[["seq",[["seq",[["seq",[["seq",[["seq",[["seq",[["seq",[["seq",[["seq",[["seq",[["seq",[["seq",[["seq",[["seq",[["seq",[["seq",[["seq",[["seq",[["seq",[["seq",[["seq",[["seq",[["seq",[["seq",[["seq",[["seq",[["seq",[["seq",[["seq",[["seq",[["seq",[["seq",[["seq",[["seq",[["seq",[["seq",[["seq",[["seq",[["seq",[["seq",[["seq",[["seq",[["seq",[["seq",[["seq",[["seq",[["seq",[["seq",[["seq",[["seq",[["seq",[["seq",[["seq",[["seq",[["seq",[["seq",[["seq",[["seq",[["seq",[]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]]],
"recursive map": ["refused","ConstructorError"],
"shared twice": ["ok",["map",[[["_Located","a",1,0],["seq",[["_Located","1",1,0]]]],[["_Located","b",2,0],["alias",2]],[["_Located","c",3,0],["alias",2]]]]],
"deeper": ["refused","RecursionError"]
}"""
)

WORKFLOW = "name: sample\ndefaults:\n  run:\n    shell: bash\nenv: &common\n  MODE: check\njobs:\n  build:\n    runs-on: ubuntu-latest\n    env: *common\n    steps:\n      - name: plain\n        run: echo one\n      - name: literal\n        run: |\n          set -eu\n          echo two\n          echo three\n      - name: folded\n        run: >\n          echo four\n          five\n      - name: quoted\n        shell: sh\n        run: 'printf \"%s\\n\" six'\n      - uses: actions/checkout@v4\n"

EXPECTED_WORKFLOW: object = json.loads(
    '["ok",["map",[[["_Located","name",1,0],["_Located","sample",1,0]],[["_Located","defaults",2,0],["map",[[["_Located","run",3,0],["map",[[["_Located","shell",4,0],["_Located","bash",4,0]]]]]]]],[["_Located","env",5,0],["map",[[["_Located","MODE",6,0],["_Located","check",6,0]]]]],[["_Located","jobs",7,0],["map",[[["_Located","build",8,0],["map",[[["_Located","runs-on",9,0],["_Located","ubuntu-latest",9,0]],[["_Located","env",10,0],["alias",10]],[["_Located","steps",11,0],["seq",[["map",[[["_Located","name",12,0],["_Located","plain",12,0]],[["_Located","run",13,0],["_Located","echo one",13,0]]]],["map",[[["_Located","name",14,0],["_Located","literal",14,0]],[["_Located","run",15,0],["_Located","set -eu\\necho two\\necho three\\n",16,1]]]],["map",[[["_Located","name",19,0],["_Located","folded",19,0]],[["_Located","run",20,0],["_Located","echo four five\\n",20,0]]]],["map",[[["_Located","name",23,0],["_Located","quoted",23,0]],[["_Located","shell",24,0],["_Located","sh",24,0]],[["_Located","run",25,0],["_Located","printf \\"%s\\\\n\\" six",25,0]]]],["map",[[["_Located","uses",26,0],["_Located","actions/checkout@v4",26,0]]]]]]]]]]]]]]]]'
)


class LocatedLoadTests(unittest.TestCase):
    def test_each_edge_case_reads_as_characterized(self) -> None:
        self.assertEqual(set(EXPECTED), set(EDGE))
        for name, text in EDGE.items():
            with self.subTest(name):
                self.assertEqual(EXPECTED[name], outcome(text))

    def test_a_workflow_keeps_each_script_s_first_line_and_step(self) -> None:
        self.assertEqual(EXPECTED_WORKFLOW, outcome(WORKFLOW))

    def test_every_tracked_workflow_reads_as_base_loader_reads_it(self) -> None:
        workflows = sorted((ROOT / ".github" / "workflows").glob("*.yml"))
        self.assertTrue(workflows)
        for path in workflows:
            with self.subTest(path.name):
                text = path.read_text(encoding="utf-8")
                self.assertEqual(plain(base_loaded(text)), plain(located(text)))
