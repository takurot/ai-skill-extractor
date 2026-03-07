import unittest
from unittest.mock import MagicMock

from src.analyze.analyzer import SemanticAnalysisResult, SemanticAnalyzer
from src.models.db import ReviewItem


class TestSemanticAnalyzer(unittest.TestCase):
    def test_analyze_item_success(self) -> None:
        mock_llm = MagicMock()
        mock_result = SemanticAnalysisResult(
            category="testing",
            actionable=True,
            evidence_based=True,
            generalizability="general",
            quality_score=0.9,
        )
        mock_llm.generate_structured_output.return_value = mock_result

        analyzer = SemanticAnalyzer(mock_llm)
        item = ReviewItem(
            id="1",
            file_path="test.py",
            language="python",
            comment_text="add a test for the empty list case",
        )

        result = analyzer.analyze_item(item)

        self.assertEqual(result.category, "testing")
        self.assertTrue(result.actionable)
        self.assertEqual(result.quality_score, 0.9)
        mock_llm.generate_structured_output.assert_called_once()

    def test_process_items(self) -> None:
        mock_llm = MagicMock()
        mock_result = SemanticAnalysisResult(
            category="readability",
            actionable=True,
            evidence_based=False,
            generalizability="repo_specific",
            quality_score=0.5,
        )
        mock_llm.generate_structured_output.return_value = mock_result

        analyzer = SemanticAnalyzer(mock_llm)
        items = [
            ReviewItem(id="1", comment_text="use camelCase"),
            ReviewItem(id="2", comment_text="rename this"),
        ]

        analyzer.process_items(items)

        self.assertEqual(items[0].category, "readability")
        self.assertEqual(items[1].generalizability, "repo_specific")
        self.assertEqual(mock_llm.generate_structured_output.call_count, 2)


if __name__ == "__main__":
    unittest.main()
