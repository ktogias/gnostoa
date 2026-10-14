"""#389 F3 calibration fixture (never merged): the d90c612 function DeepSource rated PY-R1000, cyclomatic complexity 17, verbatim."""

from __future__ import annotations

import unittest
from typing import Any

ADMISSION = "admission.yml"
APP_MINT_ACTION = "app-mint"
READBACK_CALL = "readback-call"
ANALYZER_FORWARDING: dict[str, str] = {}


def _load(path: str) -> dict[str, Any]:
    return {"jobs": {}}


def _steps(job: dict[str, Any]) -> list[dict[str, Any]]:
    return []


def _secret_references(value: object) -> set[str]:
    return set()


class Calibration(unittest.TestCase):
    def test_only_the_publishing_jobs_hold_the_dedicated_app(self) -> None:
        jobs = _load(ADMISSION)["jobs"]
        holders = {
            name: job
            for name, job in jobs.items()
            if job.get("environment") == "gnostoa-ma0"
        }
        self.assertEqual({"invalidate", "admit"}, set(holders))
        gates = {
            # cubic on #426: without the App's id no token is minted (the shadow).
            "invalidate": "${{ vars.GNOSTOA_MA0_APP_ID != '' }}",
            "admit": "${{ !cancelled() && vars.GNOSTOA_MA0_APP_ID != '' }}",
        }
        for name, job in holders.items():
            with self.subTest(job=name):
                minting = [s for s in _steps(job) if s.get("uses") == APP_MINT_ACTION]
                self.assertEqual(1, len(minting))
                inputs = minting[0].get("with", {})
                permissions = {
                    k: v for k, v in inputs.items() if k.startswith("permission-")
                }
                self.assertEqual({"permission-checks": "write"}, permissions)
                self.assertEqual(gates[name], minting[0].get("if"))
        for other_name, other in jobs.items():
            if other_name in holders:
                continue
            with self.subTest(job=other_name):
                text = str(other)
                self.assertNotIn(APP_MINT_ACTION, text)
                # CodeAnt on #426: nor the App's key, id or token by any other route.
                # The readback's call forwards exactly the analyzer tokens (#407
                # 6154772083); no other secret reaches a job that is not a holder.
                rest = other
                if other.get("uses") == READBACK_CALL:
                    self.assertEqual(ANALYZER_FORWARDING, other.get("secrets"))
                    rest = {k: v for k, v in other.items() if k != "secrets"}
                self.assertNotIn("secrets.", str(rest))
                self.assertNotIn("GNOSTOA_MA0", text)
                self.assertNotIn("steps.token", text)
        relays = {
            "invalidate": "Invalidate a standing success on the exact head",
            "admit": "Publish the verdict on the exact head",
        }
        for name, job in holders.items():
            for step in _steps(job):
                with self.subTest(job=name, step=step.get("name")):
                    if "secrets." in str(step):
                        self.assertEqual(APP_MINT_ACTION, step.get("uses"))
                    if "steps.token" in str(step):
                        self.assertEqual(relays[name], step.get("name"))
