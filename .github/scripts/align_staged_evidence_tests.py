from pathlib import Path


PATH = Path("tests/test_tools.py")
text = PATH.read_text()


def replace_once(old: str, new: str) -> None:
    global text
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"expected one test block match, found {count}")
    text = text.replace(old, new)


replace_once(
    '''        # The invariant is that the workflow need stays durably planned while
        # completed B2 evidence remains distinct from the selected B3 target,
        # four recorded adoption attempts and the new exact-subject rerun.
        self.assertIn("B2/P1 and B2/P2 are both complete", roadmap)
        self.assertIn("B2/P1 completed", status)
        for projection in (roadmap, status):
            normalized_projection = " ".join(projection.split())
            self.assertIn(
                "https://github.com/ktogias/gnostoa/issues/24",
                normalized_projection,
            )
            self.assertIn("Operational work toward B3 has begun", normalized_projection)
            self.assertIn("exact-subject rerun has not begun", normalized_projection)
            self.assertIn("Nextcloud Mail", normalized_projection)
            self.assertNotIn("Active B2/P1", normalized_projection)
''',
    '''        # The invariant is that the workflow need stays durably planned while
        # completed B2 evidence remains distinct from the historical pre-B3 attempts
        # and the currently selected owner-led evidence stream.
        self.assertIn("B2/P1 and B2/P2 are both complete", roadmap)
        self.assertIn("B2/P1 completed", status)
        for projection in (roadmap, status):
            normalized_projection = " ".join(projection.split())
            self.assertIn(
                "https://github.com/ktogias/gnostoa/issues/24",
                normalized_projection,
            )
            self.assertIn("Decision 0052", normalized_projection)
            self.assertIn("`OWNER-LED`", normalized_projection)
            self.assertIn("`INDEPENDENT`", normalized_projection)
            self.assertIn("later separate work", normalized_projection)
            self.assertIn("Nextcloud Mail", normalized_projection)
            self.assertNotIn("exact-subject rerun has not begun", normalized_projection)
            self.assertNotIn("Active B2/P1", normalized_projection)
''',
)

replace_once(
    '''        projections = {
            "README": (ROOT / "README.md").read_text(encoding="utf-8"),
            "roadmap": (ROOT / "docs" / "roadmap.md").read_text(encoding="utf-8"),
            "status": (ROOT / "docs" / "status.md").read_text(encoding="utf-8"),
            "B3 design": (
                ROOT
                / "knowledge"
                / "assessments"
                / "b3-independent-adoption-experiment-design.md"
            ).read_text(encoding="utf-8"),
            "release result": (
                ROOT
                / "knowledge"
                / "assessments"
                / "v0-2-0-release-candidate-and-source-boundary-result.md"
            ).read_text(encoding="utf-8"),
            "Decision 0051": (
                ROOT
                / "knowledge"
                / "decisions"
                / "0051-select-the-v0-2-0-source-and-oci-publication-series.md"
            ).read_text(encoding="utf-8"),
        }

        for name, projection in projections.items():
            with self.subTest(projection=name):
                normalized = " ".join(projection.split())
                self.assertIn("Operational work toward B3 has begun", normalized)
                self.assertIn("four autonomous adoption attempts", normalized.lower())
                self.assertIn("#117", normalized)
                self.assertIn("#122", normalized)
                self.assertIn("#125", normalized)
                self.assertIn("owner acceptance `REJECT`", normalized)
                self.assertIn("measured utility `UNKNOWN`", normalized)
                self.assertIn("durable adoption `NO`", normalized)
                self.assertIn("controlled pre-B3", normalized)
                self.assertIn("exact-subject rerun has not begun", normalized)
                self.assertNotIn("B3 measurement has not begun", normalized)
                self.assertNotIn("Operational B3 work", normalized)
                self.assertNotIn("initial-adoption gate", normalized)

        frozen_design = (
            ROOT
            / "knowledge"
            / "assessments"
            / "b3-independent-adoption-experiment-design.md"
        ).read_text(encoding="utf-8")
        self.assertIn("## Later chronology note", frozen_design)
        self.assertIn("not a current status projection", frozen_design)
        self.assertIn("B3 has not begun", frozen_design)
''',
    '''        current_projections = {
            "README": (ROOT / "README.md").read_text(encoding="utf-8"),
            "roadmap": (ROOT / "docs" / "roadmap.md").read_text(encoding="utf-8"),
            "status": (ROOT / "docs" / "status.md").read_text(encoding="utf-8"),
            "B3 design": (
                ROOT
                / "knowledge"
                / "assessments"
                / "b3-independent-adoption-experiment-design.md"
            ).read_text(encoding="utf-8"),
        }
        detailed_current_projections = {
            name: current_projections[name] for name in ("README", "B3 design")
        }
        historical_projections = {
            "release result": (
                ROOT
                / "knowledge"
                / "assessments"
                / "v0-2-0-release-candidate-and-source-boundary-result.md"
            ).read_text(encoding="utf-8"),
            "Decision 0051": (
                ROOT
                / "knowledge"
                / "decisions"
                / "0051-select-the-v0-2-0-source-and-oci-publication-series.md"
            ).read_text(encoding="utf-8"),
        }

        for name, projection in current_projections.items():
            with self.subTest(current_projection=name):
                normalized = " ".join(projection.split())
                self.assertIn("four autonomous", normalized.lower())
                self.assertIn("`REJECT`", normalized)
                self.assertIn("`UNKNOWN`", normalized)
                self.assertIn("`NO`", normalized)
                self.assertIn("controlled pre-B3", normalized)
                self.assertIn("Decision 0052", normalized)
                self.assertIn("`OWNER-LED`", normalized)
                self.assertIn("`INDEPENDENT`", normalized)
                self.assertNotIn("exact-subject rerun has not begun", normalized)
                self.assertNotIn("exact B3 contract freeze", normalized)
                self.assertNotIn("initial-adoption gate", normalized)

        for name, projection in detailed_current_projections.items():
            with self.subTest(detailed_current_projection=name):
                normalized = " ".join(projection.split())
                self.assertIn("#117", normalized)
                self.assertIn("#122", normalized)
                self.assertIn("#125", normalized)

        for name, projection in historical_projections.items():
            with self.subTest(historical_projection=name):
                normalized = " ".join(projection.split())
                self.assertIn("Operational work toward B3 has begun", normalized)
                self.assertIn("four autonomous adoption attempts", normalized.lower())
                self.assertIn("#117", normalized)
                self.assertIn("#122", normalized)
                self.assertIn("#125", normalized)
                self.assertIn("owner acceptance `REJECT`", normalized)
                self.assertIn("measured utility `UNKNOWN`", normalized)
                self.assertIn("durable adoption `NO`", normalized)
                self.assertIn("controlled pre-B3", normalized)
                self.assertIn("exact-subject rerun has not begun", normalized)
                self.assertNotIn("B3 measurement has not begun", normalized)
                self.assertNotIn("Operational B3 work", normalized)
                self.assertNotIn("initial-adoption gate", normalized)

        frozen_design = current_projections["B3 design"]
        self.assertIn("## Later chronology and staged-evidence note", frozen_design)
        self.assertIn("not a current status projection", frozen_design)
        self.assertIn("B3 has not begun", frozen_design)
        self.assertIn("Decision 0052", frozen_design)
        self.assertIn("`OWNER-LED`", frozen_design)
''',
)

replace_once(
    '''        for projection in (status, roadmap):
            normalized_projection = " ".join(projection.split())
            self.assertIn("Operational work toward B3 has begun", normalized_projection)
            self.assertIn("exact-subject rerun has not begun", normalized_projection)
            self.assertIn("Nextcloud Mail", normalized_projection)
            self.assertIn("0051-select-the-v0-2-0", normalized_projection)
            self.assertNotIn("candidate selection remains", normalized_projection)
            self.assertNotIn(
                "candidate selection — one eligible", normalized_projection
            )
''',
    '''        for projection in (status, roadmap):
            normalized_projection = " ".join(projection.split())
            self.assertIn("Decision 0052", normalized_projection)
            self.assertIn("`OWNER-LED`", normalized_projection)
            self.assertIn("`INDEPENDENT`", normalized_projection)
            self.assertIn("later separate work", normalized_projection)
            self.assertIn("Nextcloud Mail", normalized_projection)
            self.assertIn("0052-use-staged-evidence-maturity", normalized_projection)
            self.assertIn("owner-led-adoption-trial-baseline", normalized_projection)
            self.assertNotIn("exact-subject rerun has not begun", normalized_projection)
            self.assertNotIn("exact B3 contract freeze", normalized_projection)
            self.assertNotIn("candidate selection remains", normalized_projection)
            self.assertNotIn(
                "candidate selection — one eligible", normalized_projection
            )
''',
)

PATH.write_text(text)
