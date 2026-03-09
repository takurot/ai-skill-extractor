from datetime import datetime, timezone

import yaml

from src.generate.generator import ArtifactGenerator
from src.models.db import ReviewItem, SkillCandidate


def make_candidate(
    candidate_id: str,
    *,
    name: str,
    category: str,
    confidence: float,
    source_review_item_ids: list[str],
    languages: list[str],
    frameworks: list[str],
    status: str = "accepted",
) -> SkillCandidate:
    return SkillCandidate(
        id=candidate_id,
        source_review_item_ids=source_review_item_ids,
        canonical_name=name,
        category=category,
        description_draft=f"{name} description.",
        engineering_principle=f"{name} rationale.",
        review_prompt_draft=f"Review prompt for {name}.",
        detection_hint_draft=f"Detection hint for {name}.",
        applicability_scope="general",
        languages=languages,
        frameworks=frameworks,
        confidence=confidence,
        evidence_count=len(source_review_item_ids),
        status=status,
    )


def test_generate_writes_yaml_markdown_and_split_outputs(tmp_path) -> None:
    generator = ArtifactGenerator(
        tmp_path,
        language_split=True,
        framework_split=True,
    )
    accepted_candidates = [
        make_candidate(
            "sc_1",
            name="Edge Case Testing",
            category="testing",
            confidence=0.91,
            source_review_item_ids=["rvw_1", "rvw_2"],
            languages=["python", "typescript"],
            frameworks=["fastapi"],
        ),
        make_candidate(
            "sc_2",
            name="Readable Public APIs",
            category="readability",
            confidence=0.82,
            source_review_item_ids=["rvw_3"],
            languages=["python"],
            frameworks=[],
        ),
    ]
    rejected_candidate = make_candidate(
        "sc_3",
        name="Repo Local Style Rule",
        category="readability",
        confidence=0.6,
        source_review_item_ids=["rvw_4"],
        languages=["python"],
        frameworks=[],
        status="rejected",
    )
    rejected_candidate.rejection_reason = "repo_specific_scope"

    review_items = {
        "rvw_1": ReviewItem(id="rvw_1", repo="org/repo-a", pr_number=1),
        "rvw_2": ReviewItem(id="rvw_2", repo="org/repo-b", pr_number=2),
        "rvw_3": ReviewItem(id="rvw_3", repo="org/repo-a", pr_number=3),
        "rvw_4": ReviewItem(id="rvw_4", repo="org/repo-c", pr_number=4),
    }

    generated_files = generator.generate(
        accepted_candidates,
        review_items,
        skills_output_path="skills/SKILLS.yaml",
        docs_output_dir="docs",
        all_candidates=[*accepted_candidates, rejected_candidate],
        rejection_reasons={"repo_specific_scope": 1},
        generated_at=datetime(2026, 3, 9, tzinfo=timezone.utc),
    )

    assert generated_files == [
        str(tmp_path / "skills" / "SKILLS.yaml"),
        str(tmp_path / "docs" / "review_dimensions.md"),
        str(tmp_path / "docs" / "anti_patterns.md"),
        str(tmp_path / "docs" / "source_coverage_report.md"),
    ]

    payload = yaml.safe_load((tmp_path / "skills" / "SKILLS.yaml").read_text(encoding="utf-8"))
    assert payload["version"] == "1.0"
    assert payload["source_summary"]["accepted_skill_count"] == 2
    assert payload["source_summary"]["pr_count"] == 4
    assert [skill["id"] for skill in payload["skills"]] == [
        "edge_case_testing",
        "readable_public_apis",
    ]
    assert payload["skills"][0]["evidence"]["repos"] == ["org/repo-a", "org/repo-b"]
    assert payload["skills"][0]["examples"]["bad"]
    assert payload["skills"][0]["examples"]["good"]

    review_dimensions = (tmp_path / "docs" / "review_dimensions.md").read_text(encoding="utf-8")
    anti_patterns = (tmp_path / "docs" / "anti_patterns.md").read_text(encoding="utf-8")
    coverage = (tmp_path / "docs" / "source_coverage_report.md").read_text(encoding="utf-8")
    assert "## readability" in review_dimensions
    assert "## Edge Case Testing" in anti_patterns
    assert "- repo_specific_scope: 1" in coverage
    assert "- testing: 1" in coverage

    assert (tmp_path / "skills" / "python.yaml").exists()
    assert (tmp_path / "skills" / "typescript.yaml").exists()
    assert (tmp_path / "skills" / "framework" / "fastapi.yaml").exists()
