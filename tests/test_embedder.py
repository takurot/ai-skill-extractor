import unittest
from unittest.mock import MagicMock

from src.extract.embedder import EmbeddingGenerationError, SkillEmbedder
from src.models.db import SkillCandidate


class TestSkillEmbedder(unittest.TestCase):
    def test_process_candidates(self) -> None:
        mock_llm = MagicMock()
        mock_llm.generate_embedding.return_value = [0.1, 0.2, 0.3]

        embedder = SkillEmbedder(mock_llm)
        candidate = SkillCandidate(
            id="sc_1",
            canonical_name="Test Skill",
            description_draft="This is a test skill.",
        )

        embedder.process_candidates([candidate])

        self.assertEqual(candidate.embedding, [0.1, 0.2, 0.3])
        mock_llm.generate_embedding.assert_called_once_with("Test Skill\nThis is a test skill.")

    def test_process_candidates_error(self) -> None:
        mock_llm = MagicMock()
        mock_llm.generate_embedding.side_effect = Exception("API Error")

        embedder = SkillEmbedder(mock_llm)
        candidate = SkillCandidate(
            id="sc_1",
            canonical_name="Test Skill",
            description_draft="This is a test skill.",
        )

        with self.assertRaises(EmbeddingGenerationError) as error:
            embedder.process_candidates([candidate])

        self.assertIsNone(candidate.embedding)
        self.assertEqual(error.exception.failures, [("sc_1", "API Error")])


if __name__ == "__main__":
    unittest.main()
