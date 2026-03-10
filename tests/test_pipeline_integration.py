from pathlib import Path
from unittest.mock import MagicMock

import yaml

from src.curate.deduplicator import CanonicalSkillResult, SkillDeduplicator
from src.generate.generator import ArtifactGenerator
from src.models.db import ReviewItem, SkillCandidate


def make_candidate(
    candidate_id: str,
    *,
    embedding: list[float],
    confidence: float,
    source_review_item_ids: list[str],
) -> SkillCandidate:
    return SkillCandidate(
        id=candidate_id,
        canonical_name=f"Skill {candidate_id}",
        category="testing",
        description_draft=f"Description for {candidate_id}",
        engineering_principle="Boundary testing",
        review_prompt_draft="Check changed behavior for edge cases.",
        detection_hint_draft="Look for missing boundary tests.",
        applicability_scope="general",
        languages=["python"],
        frameworks=[],
        confidence=confidence,
        evidence_count=len(source_review_item_ids),
        source_review_item_ids=source_review_item_ids,
        embedding=embedding,
        status="proposed",
    )


def test_dedup_to_generate_pipeline_creates_expected_artifacts(tmp_path: Path) -> None:
    mock_llm = MagicMock()
    mock_llm.generate_structured_output.return_value = CanonicalSkillResult(
        canonical_name="Edge Case Testing",
        description_draft="Test boundary, empty, and invalid inputs.",
        engineering_principle="Boundary testing",
        review_prompt_draft="Check whether changed behavior covers edge cases.",
        detection_hint_draft="Look for branching logic without edge-case tests.",
        applicability_scope="general",
        languages=["python"],
        frameworks=[],
        confidence=0.92,
    )
    deduplicator = SkillDeduplicator(mock_llm, dedup_threshold=0.95)
    candidates = [
        make_candidate(
            "sc_1",
            embedding=[1.0, 0.0],
            confidence=0.86,
            source_review_item_ids=["ri_1"],
        ),
        make_candidate(
            "sc_2",
            embedding=[0.99, 0.01],
            confidence=0.89,
            source_review_item_ids=["ri_2"],
        ),
        make_candidate(
            "sc_3",
            embedding=[0.98, 0.02],
            confidence=0.88,
            source_review_item_ids=["ri_3"],
        ),
    ]
    review_items = {
        "ri_1": ReviewItem(id="ri_1", repo="owner/repo-a", pr_number=1, fix_correlation=True),
        "ri_2": ReviewItem(id="ri_2", repo="owner/repo-b", pr_number=2, fix_correlation=True),
        "ri_3": ReviewItem(id="ri_3", repo="owner/repo-a", pr_number=3, fix_correlation=True),
    }

    report = deduplicator.process_candidates(candidates, review_items)

    generator = ArtifactGenerator()
    generator.generate(
        report.accepted_candidates,
        list(review_items.values()),
        skills_output_path=str(tmp_path / "skills" / "SKILLS.yaml"),
        docs_output_dir=str(tmp_path / "docs"),
        all_candidates=candidates,
        rejection_reasons=report.rejection_reasons,
    )

    payload = yaml.safe_load((tmp_path / "skills" / "SKILLS.yaml").read_text(encoding="utf-8"))
    coverage_report = (tmp_path / "docs" / "source_coverage_report.md").read_text(encoding="utf-8")

    assert payload["source_summary"]["accepted_skill_count"] == 1
    assert payload["skills"][0]["name"] == "Edge Case Testing"
    assert "Total candidate count: 3" in coverage_report
