import unittest
from unittest.mock import MagicMock

from src.extract.extractor import SkillExtractionResult, SkillExtractor
from src.models.db import ReviewItem


class TestSkillExtractor(unittest.TestCase):
    def test_extract_from_item_success(self) -> None:
        mock_llm = MagicMock()
        mock_result = SkillExtractionResult(
            is_valid_skill=True,
            canonical_name="Test Empty List",
            description_draft="Always test empty lists.",
            engineering_principle="Boundary Testing",
            review_prompt_draft="Check if empty list is handled.",
            detection_hint_draft="Look for list arguments.",
            applicability_scope="general",
            languages=["python"],
            frameworks=[],
            confidence=0.9,
        )
        mock_llm.generate_structured_output.return_value = mock_result

        extractor = SkillExtractor(mock_llm)
        item = ReviewItem(
            id="1",
            comment_text="add a test for the empty list case",
            actionable=True,
            evidence_based=True,
            category="testing",
        )

        candidate = extractor.extract_from_item(item)

        self.assertIsNotNone(candidate)
        if candidate:
            self.assertEqual(candidate.canonical_name, "Test Empty List")
            self.assertEqual(candidate.confidence, 0.9)
            self.assertEqual(candidate.evidence_count, 1)

    def test_extract_from_item_invalid(self) -> None:
        mock_llm = MagicMock()
        # Item is not actionable, should return early
        extractor = SkillExtractor(mock_llm)
        item = ReviewItem(
            id="1",
            comment_text="looks good to me",
            actionable=False,
            evidence_based=False,
        )

        candidate = extractor.extract_from_item(item)
        self.assertIsNone(candidate)
        mock_llm.generate_structured_output.assert_not_called()


if __name__ == "__main__":
    unittest.main()
