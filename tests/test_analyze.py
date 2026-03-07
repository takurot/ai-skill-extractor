import os
import unittest
from unittest.mock import MagicMock, patch

from pydantic import BaseModel

from src.analyze.llm_client import LLMClient
from src.analyze.prompts import PromptManager


class DummyModel(BaseModel):
    category: str
    actionable: bool


class TestLLMClient(unittest.TestCase):
    @patch.dict(os.environ, {"OPENAI_API_KEY": "fake_key"})
    @patch("src.analyze.llm_client.OpenAI")
    def test_generate_text(self, mock_openai: MagicMock) -> None:
        mock_client_instance = mock_openai.return_value
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "response text"
        mock_client_instance.chat.completions.create.return_value = mock_response

        client = LLMClient()
        result = client.generate_text("test prompt", "system prompt")

        self.assertEqual(result, "response text")
        mock_client_instance.chat.completions.create.assert_called_once()

    @patch.dict(os.environ, {"OPENAI_API_KEY": "fake_key"})
    @patch("src.analyze.llm_client.OpenAI")
    def test_generate_structured_output(self, mock_openai: MagicMock) -> None:
        mock_client_instance = mock_openai.return_value
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.parsed = DummyModel(category="testing", actionable=True)
        mock_client_instance.beta.chat.completions.parse.return_value = mock_response

        client = LLMClient()
        result = client.generate_structured_output("test prompt", DummyModel)

        self.assertIsInstance(result, DummyModel)
        self.assertEqual(result.category, "testing")
        self.assertTrue(result.actionable)
        mock_client_instance.beta.chat.completions.parse.assert_called_once()


class TestPromptManager(unittest.TestCase):
    def test_get_prompt_success(self) -> None:
        prompt = PromptManager.get_prompt(
            "extract_skill_candidate", category="testing", comment_text="add more edge cases"
        )
        self.assertIn("Category: testing", prompt)
        self.assertIn("Comment: add more edge cases", prompt)

    def test_get_prompt_missing_key(self) -> None:
        with self.assertRaises(KeyError):
            PromptManager.get_prompt("non_existent_template")


if __name__ == "__main__":
    unittest.main()
