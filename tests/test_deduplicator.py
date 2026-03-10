from unittest.mock import MagicMock

from src.curate.deduplicator import CanonicalSkillResult, SkillDeduplicator
from src.models.db import ReviewItem, SkillCandidate


def make_candidate(
    candidate_id: str,
    *,
    embedding: list[float],
    confidence: float,
    source_review_item_ids: list[str],
    applicability_scope: str = "general",
) -> SkillCandidate:
    return SkillCandidate(
        id=candidate_id,
        canonical_name=f"Skill {candidate_id}",
        category="testing",
        description_draft=f"Description for {candidate_id}",
        engineering_principle="Boundary testing",
        review_prompt_draft="Check edge cases.",
        detection_hint_draft="Look for missing edge-case tests.",
        applicability_scope=applicability_scope,
        languages=["python"],
        frameworks=[],
        confidence=confidence,
        evidence_count=len(source_review_item_ids),
        source_review_item_ids=source_review_item_ids,
        embedding=embedding,
        status="proposed",
    )


def make_review_item(review_item_id: str, repo: str, *, fix_correlation: bool = True) -> ReviewItem:
    return ReviewItem(id=review_item_id, repo=repo, fix_correlation=fix_correlation)


def test_process_candidates_merges_cluster_and_accepts_general_skill() -> None:
    mock_llm = MagicMock()
    mock_llm.generate_structured_output.return_value = CanonicalSkillResult(
        canonical_name="Edge Case Testing",
        description_draft="Test boundary, empty, and invalid inputs.",
        engineering_principle="Boundary testing",
        review_prompt_draft="Check changed behavior for untested edge cases.",
        detection_hint_draft="Look for branching logic without edge-case tests.",
        applicability_scope="general",
        languages=["python", "typescript"],
        frameworks=[],
        confidence=0.91,
    )

    deduplicator = SkillDeduplicator(
        mock_llm,
        dedup_threshold=0.95,
        min_skill_confidence=0.72,
        min_cross_repo_support=2,
    )
    candidates = [
        make_candidate(
            "sc_1",
            embedding=[1.0, 0.0],
            confidence=0.84,
            source_review_item_ids=["rvw_1"],
        ),
        make_candidate(
            "sc_2",
            embedding=[0.99, 0.01],
            confidence=0.89,
            source_review_item_ids=["rvw_2"],
        ),
        make_candidate(
            "sc_3",
            embedding=[0.98, 0.02],
            confidence=0.87,
            source_review_item_ids=["rvw_3"],
        ),
        make_candidate(
            "sc_4",
            embedding=[0.0, 1.0],
            confidence=0.9,
            source_review_item_ids=["rvw_4"],
        ),
    ]
    review_items = {
        "rvw_1": make_review_item("rvw_1", "owner/repo-a"),
        "rvw_2": make_review_item("rvw_2", "owner/repo-b"),
        "rvw_3": make_review_item("rvw_3", "owner/repo-a"),
        "rvw_4": make_review_item("rvw_4", "owner/repo-c", fix_correlation=False),
    }

    report = deduplicator.process_candidates(candidates, review_items)

    assert [candidate.id for candidate in report.accepted_candidates] == ["sc_2"]
    accepted = report.accepted_candidates[0]
    assert accepted.canonical_name == "Edge Case Testing"
    assert accepted.status == "accepted"
    assert accepted.source_review_item_ids == ["rvw_1", "rvw_2", "rvw_3"]
    assert accepted.evidence_count == 3
    assert accepted.languages == ["python", "typescript"]
    assert accepted.confidence >= 0.72

    duplicate_candidates = [
        candidate for candidate in candidates if candidate.id in {"sc_1", "sc_3"}
    ]
    assert all(candidate.status == "rejected" for candidate in duplicate_candidates)
    assert all(candidate.merged_into_id == "sc_2" for candidate in duplicate_candidates)
    assert candidates[3].status == "rejected"
    assert candidates[3].rejection_reason == "insufficient_evidence"

    assert report.clusters[0].status == "accepted"
    assert report.clusters[0].cross_repo_count == 2
    assert report.rejection_reasons["insufficient_evidence"] == 1


def test_process_candidates_rejects_general_skill_with_insufficient_evidence() -> None:
    mock_llm = MagicMock()
    mock_llm.generate_structured_output.return_value = CanonicalSkillResult(
        canonical_name="Rename Variables Clearly",
        description_draft="Prefer descriptive names over abbreviations.",
        engineering_principle="Readability",
        review_prompt_draft="Check whether new names communicate intent.",
        detection_hint_draft="Look for abbreviations in public APIs.",
        applicability_scope="general",
        languages=["python"],
        frameworks=[],
        confidence=0.95,
    )

    deduplicator = SkillDeduplicator(
        mock_llm,
        dedup_threshold=0.95,
        min_skill_confidence=0.72,
        min_cross_repo_support=2,
    )
    candidates = [
        make_candidate(
            "sc_1",
            embedding=[1.0, 0.0],
            confidence=0.9,
            source_review_item_ids=["rvw_1"],
        ),
        make_candidate(
            "sc_2",
            embedding=[0.99, 0.01],
            confidence=0.92,
            source_review_item_ids=["rvw_2"],
        ),
    ]
    review_items = {
        "rvw_1": make_review_item("rvw_1", "owner/repo-a"),
        "rvw_2": make_review_item("rvw_2", "owner/repo-b"),
    }

    report = deduplicator.process_candidates(candidates, review_items)

    assert report.accepted_candidates == []
    assert report.rejection_reasons["insufficient_evidence"] == 1
    assert candidates[1].status == "rejected"
    assert candidates[1].rejection_reason == "insufficient_evidence"
    assert candidates[0].merged_into_id == "sc_2"
