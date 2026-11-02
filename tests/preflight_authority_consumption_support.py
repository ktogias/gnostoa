"""What other test modules share from tests/test_preflight_authority_consumption.py, outside the discovered test modules (#389 N1b; Decision 0128)."""

from __future__ import annotations

import json
from pathlib import Path

from tests.experiment_capsule_support import CapsuleFixture, git
from tools.capsule import authority as authority_module
from tools.capsule import compiler, qualification
from tools.capsule.identity import digest_of
from tools.capsule.spec import load_spec

IMAGE = "sha256:" + "a" * 64


class ConsumptionFixture(CapsuleFixture):
    def setUp(self) -> None:
        super().setUp()
        self.repo = self.make_repo(
            "subject", {"src/pkg/__init__.py": "def render():\n    return 'old'\n"}
        )
        self.base = git(self.repo, "rev-parse", "HEAD")
        self.reference = self.commit(
            self.repo,
            {"src/pkg/__init__.py": "def render():\n    return 'new'\n"},
            "reference",
        )
        (self.root / "oracle.py").write_text(
            "import pkg\n\n\ndef test_discriminates():\n"
            "    assert pkg.render() == 'new'\n"
        )
        payload = self.base_spec(
            self.repo,
            self.base,
            self.reference,
            runtime={"image": IMAGE},
        )
        payload["tasks"][0]["reference"]["commit"] = self.reference
        payload["tasks"][0]["reference"]["tree"] = git(
            self.repo, "rev-parse", self.reference + "^{tree}"
        )
        self.payload = payload

    def _spec(self, receipt: Path | None = None):
        payload = json.loads(json.dumps(self.payload))
        if receipt is not None:
            payload["tasks"][0]["prior_qualification"] = {"receipt": str(receipt)}
        return load_spec(self.write_spec(payload))

    def prepare(
        self,
        *,
        authority=None,
        receipt: Path | None = None,
        qualification_backend: str = qualification.LOCAL_PYTHON,
    ):
        return compiler.prepare(
            self._spec(receipt),
            self.workspace,
            offline=True,
            preflight_authority=authority,
            qualification_backend=qualification_backend,
        )

    @staticmethod
    def authority(candidate: str) -> authority_module.PreflightAuthority:
        return authority_module.PreflightAuthority(
            id="auth-197",
            experiment_id="E1",
            scope=(authority_module.BASE_REFERENCE_QUALIFICATION,),
            preflight_candidate_sha256=candidate,
        )

    def prior_receipt(self, observed) -> Path:
        task = observed.task("T1")
        spec = self._spec()
        bound = {
            "base_tree": task.base_tree,
            "reference_tree": task.reference_tree,
            "oracle_sha256": task.oracle_sha256,
            "runtime_image": task.runtime_image,
            "harness_identity": task.harness.identity if task.harness else "",
            "expectations_digest": digest_of(spec.tasks[0].expectations.as_json()),
            "preparation_identity": task.prepared_runtime_identity or "none",
        }
        receipt = qualification.QualificationReceipt(
            task="T1",
            backend=qualification.LOCAL_PYTHON,
            base=qualification.SubjectOutcome(
                subject="base",
                collected=True,
                passed=(),
                failed=("test_discriminates",),
                error_types={"test_discriminates": "AssertionError"},
                classification=qualification.MATCH,
                detail="synthetic retained qualification",
            ),
            reference=qualification.SubjectOutcome(
                subject="reference",
                collected=True,
                passed=("test_discriminates",),
                failed=(),
                error_types={},
                classification=qualification.MATCH,
                detail="synthetic retained qualification",
            ),
            bound=bound,
        )
        path = self.root / "prior.json"
        path.write_text(json.dumps(receipt.as_json(), indent=2, sort_keys=True) + "\n")
        return path
