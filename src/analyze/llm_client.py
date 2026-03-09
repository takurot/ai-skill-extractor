import os
from typing import Optional, Type, TypeVar

from openai import OpenAI
from pydantic import BaseModel
from tenacity import retry, stop_after_attempt, wait_exponential

from src.runtime_env import load_project_env

T = TypeVar("T", bound=BaseModel)

load_project_env()


class LLMError(Exception):
    """Custom exception for LLM-related errors."""

    pass


class LLMClient:
    """Wrapper for LLM API calls with retry and structured output capabilities."""

    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4o-mini"):
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OpenAI API key must be provided or set in OPENAI_API_KEY")
        self.client = OpenAI(api_key=self.api_key)
        self.model = model

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def generate_structured_output(
        self, prompt: str, response_format: Type[T], system_prompt: Optional[str] = None
    ) -> T:
        """Generate structured JSON output constrained by a Pydantic model."""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        # Ignoring type on chat.completions.create because the OpenAI types can be tricky
        response = self.client.beta.chat.completions.parse(
            model=self.model,
            messages=messages,  # type: ignore
            response_format=response_format,
        )

        if not response.choices[0].message.parsed:
            raise LLMError("Failed to parse structured output from LLM.")

        return response.choices[0].message.parsed

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def generate_embedding(self, text: str) -> list[float]:
        """Generate an embedding vector for the provided text."""
        response = self.client.embeddings.create(
            input=text,
            model="text-embedding-3-small",  # Hardcoded for now, can be configured
        )
        return response.data[0].embedding

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def generate_text(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """Generate raw text response."""
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,  # type: ignore
        )

        content = response.choices[0].message.content
        if content is None:
            raise LLMError("Received empty response from LLM.")

        return content
