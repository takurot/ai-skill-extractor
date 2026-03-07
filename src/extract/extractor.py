import uuid
from typing import List, Optional

from pydantic import BaseModel, Field

from src.analyze.llm_client import LLMClient
from src.analyze.prompts import PromptManager
from src.models.db import ReviewItem, SkillCandidate


class SkillExtractionResult(BaseModel):
    is_valid_skill: bool = Field(
        description="Whether this review comment represents an actionable, generalizable skill."
    )
    canonical_name: str = Field(description="A short, descriptive name for the skill.")
    description_draft: str = Field(description="A clear description of the rule or pattern.")
    engineering_principle: str = Field(
        description="The underlying engineering principle behind this skill."
    )
    review_prompt_draft: str = Field(
        description="Instructions on how to look for this issue in a code review."
    )
    detection_hint_draft: str = Field(
        description="Clues or hints on where this issue might appear."
    )
    applicability_scope: str = Field(
        description="Scope of applicability: "
        "general, language_specific, framework_specific, repo_specific."
    )
    languages: List[str] = Field(description="List of applicable programming languages.")
    frameworks: List[str] = Field(description="List of applicable frameworks, if any.")
    confidence: float = Field(description="Confidence score (0.0 to 1.0) of this extraction.")


class SkillExtractor:
    """Extracts generalized SkillCandidates from analyzed ReviewItems."""

    def __init__(self, llm_client: LLMClient, min_confidence: float = 0.72):
        self.llm = llm_client
        self.min_confidence = min_confidence

    def extract_from_item(self, item: ReviewItem) -> Optional[SkillCandidate]:
        """Extract a SkillCandidate from a single ReviewItem if it meets the criteria."""
        if not item.actionable or not item.evidence_based:
            return None

        prompt = PromptManager.get_prompt(
            "extract_skill_candidate",
            category=item.category or "general",
            comment_text=item.comment_text,
        )

        system_prompt = (
            "You are an expert technical lead. Extract a general software engineering "
            "review skill from the provided code review comment."
        )

        result = self.llm.generate_structured_output(
            prompt=prompt,
            response_format=SkillExtractionResult,
            system_prompt=system_prompt,
        )

        if not result.is_valid_skill or result.confidence < self.min_confidence:
            return None

        # Build initial SkillCandidate
        return SkillCandidate(
            id=f"sc_{uuid.uuid4().hex[:8]}",
            source_review_item_ids=[item.id],
            canonical_name=result.canonical_name,
            category=item.category or "general",
            description_draft=result.description_draft,
            engineering_principle=result.engineering_principle,
            review_prompt_draft=result.review_prompt_draft,
            detection_hint_draft=result.detection_hint_draft,
            applicability_scope=result.applicability_scope,
            languages=result.languages,
            frameworks=result.frameworks,
            confidence=result.confidence,
            evidence_count=1,
            status="proposed",
        )

    def process_items(self, items: List[ReviewItem]) -> List[SkillCandidate]:
        """Process multiple ReviewItems and return valid SkillCandidates."""
        candidates = []
        for item in items:
            try:
                candidate = self.extract_from_item(item)
                if candidate:
                    candidates.append(candidate)
            except Exception as e:
                print(f"Failed to extract from item {item.id}: {e}")
        return candidates
