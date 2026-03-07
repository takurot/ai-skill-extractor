from typing import List

from pydantic import BaseModel, Field

from src.analyze.llm_client import LLMClient
from src.analyze.prompts import PromptManager
from src.models.db import ReviewItem


class SemanticAnalysisResult(BaseModel):
    category: str = Field(
        description="The category of the review (e.g., architecture, testing, readability)."
    )
    actionable: bool = Field(description="Whether the comment clearly states a required change.")
    evidence_based: bool = Field(
        description="Whether the comment is grounded in code context or established patterns."
    )
    generalizability: str = Field(
        description="How generalizable this feedback is "
        "(general, language_specific, framework_specific, repo_specific)."
    )
    quality_score: float = Field(
        description="A score from 0.0 to 1.0 evaluating the quality of the review comment."
    )


class SemanticAnalyzer:
    """Analyzes ReviewItems using LLMs to enrich them with semantic labels."""

    def __init__(self, llm_client: LLMClient):
        self.llm = llm_client

    def analyze_item(self, item: ReviewItem) -> SemanticAnalysisResult:
        """Analyze a single ReviewItem and return structured analysis."""
        prompt = PromptManager.get_prompt(
            "analyze_review_comment",
            file_path=item.file_path or "unknown",
            language=item.language or "unknown",
            code_before=item.code_context_before or "",
            code_after=item.code_context_after or "",
            comment_text=item.comment_text,
        )

        system_prompt = (
            "You are an expert software engineer reviewing code review comments. "
            "Analyze the given comment and classify it strictly according to the requested schema."
        )

        return self.llm.generate_structured_output(
            prompt=prompt,
            response_format=SemanticAnalysisResult,
            system_prompt=system_prompt,
        )

    def calculate_fix_correlation(self, item: ReviewItem) -> bool:
        """
        Calculate if the feedback in the comment was reflected in subsequent commits.

        Currently a stub returning True by default.
        """
        # TODO: Implement commit history parsing to verify if code changed after comment
        return True

    def process_items(self, items: List[ReviewItem]) -> None:
        """Process a list of ReviewItems in place, updating their semantic fields."""
        for item in items:
            try:
                result = self.analyze_item(item)
                item.category = result.category
                item.actionable = result.actionable
                item.evidence_based = result.evidence_based
                item.generalizability = result.generalizability
                item.quality_score = result.quality_score
                item.fix_correlation = self.calculate_fix_correlation(item)
            except Exception as e:
                # Log or handle the error, but continue processing
                print(f"Failed to analyze item {item.id}: {e}")
