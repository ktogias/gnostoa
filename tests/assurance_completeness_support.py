"""What other test modules share from tests/test_assurance_completeness.py, outside the discovered test modules (#389 N1b; Decision 0128)."""

from __future__ import annotations

from typing import Any

GNOSTOA_1_0: dict[str, Any] = {
    "schema_version": "1.0",
    "id": "gnostoa.required-evidence",
    "version": "0.1.0",
    "requirements": [
        {
            "id": "verification-checks",
            "title": "The status checks R-main requires ran on the exact head",
            "applies_to": ["mechanical", "normal", "normative", "critical"],
            "coverage": ["policy", "fast", "regression", "smoke"],
        },
        {
            "id": "codeql",
            "title": "CodeQL analysed the exact head",
            "applies_to": ["mechanical", "normal", "normative", "critical"],
            "coverage": ["codeql"],
        },
        {
            "id": "analyzer-readback",
            "title": "The authenticated analyzer readback is bound to the exact head",
            "applies_to": ["mechanical", "normal", "normative", "critical"],
            "coverage": ["deepsource-diff", "deepsource-full", "codacy"],
        },
        {
            "id": "sonarcloud",
            "title": "SonarCloud's quality gate and its issue inventory",
            "applies_to": ["mechanical", "normal", "normative", "critical"],
            "coverage": ["quality-gate", "issue-inventory"],
        },
    ],
}
