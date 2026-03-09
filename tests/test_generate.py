from pathlib import Path

import yaml

from src.generate.generator import ArtifactGenerator
from src.models.db import ReviewItem, SkillCandidate


def test_artifact_generator_writes_yaml_markdown_and_split_outputs(tmp_path: Path) -> None:
    generator = ArtifactGenerator()
    candidate = SkillCandidate(
        id="sc_1",
        canonical_name="Edge Case Testing",
        category="testing",
        description_draft="Test boundary, empty, and invalid inputs.",
        engineering_principle="Boundary testing",
        review_prompt_draft="Check whether changed behavior covers edge cases.",
        detection_hint_draft="Look for branching logic without edge-case tests.",
        applicability_scope="general",
        languages=["python"],
        frameworks=["fastapi"],
        confidence=0.91,
        evidence_count=3,
        source_review_item_ids=["ri_1", "ri_2", "ri_3"],
        status="accepted",
    )
    review_items = [
        ReviewItem(id="ri_1", repo="owner/repo-a", pr_number=1),
        ReviewItem(id="ri_2", repo="owner/repo-b", pr_number=2),
        ReviewItem(id="ri_3", repo="owner/repo-a", pr_number=3),
    ]

    written_files = generator.generate(
        [candidate],
        review_items,
        skills_output_path=str(tmp_path / "skills" / "SKILLS.yaml"),
        docs_output_dir=str(tmp_path / "docs"),
    )

    skills_path = tmp_path / "skills" / "SKILLS.yaml"
    assert str(skills_path) in written_files
    assert str(tmp_path / "skills" / "python.yaml") in written_files
    assert str(tmp_path / "skills" / "framework" / "fastapi.yaml") in written_files
    payload = yaml.safe_load(skills_path.read_text(encoding="utf-8"))
    assert payload["source_summary"]["accepted_skill_count"] == 1
    assert payload["source_summary"]["pr_count"] == 3
    assert payload["skills"][0]["id"] == "edge_case_testing"
    assert payload["skills"][0]["evidence"]["repos"] == ["owner/repo-a", "owner/repo-b"]

    assert (tmp_path / "skills" / "python.yaml").exists()
    assert (tmp_path / "skills" / "framework" / "fastapi.yaml").exists()

    review_dimensions = (tmp_path / "docs" / "review_dimensions.md").read_text(encoding="utf-8")
    anti_patterns = (tmp_path / "docs" / "anti_patterns.md").read_text(encoding="utf-8")
    coverage_report = (tmp_path / "docs" / "source_coverage_report.md").read_text(encoding="utf-8")

    assert "## testing" in review_dimensions
    assert "Edge Case Testing" in anti_patterns
    assert "Accepted skill count: 1" in coverage_report
