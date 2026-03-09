import os
from collections.abc import Callable, Sequence
from typing import Optional, ParamSpec, Type, TypeVar, cast

from openai import OpenAI
from openai.types.chat import ChatCompletionMessageParam
from pydantic import BaseModel
from tenacity import Retrying, stop_after_attempt, wait_exponential

from src.runtime_env import load_project_env

P = ParamSpec("P")
R = TypeVar("R")
T = TypeVar("T", bound=BaseModel)

load_project_env()


class LLMError(Exception):
    """Custom exception for LLM-related errors."""

    pass


class LLMClient:
    """Wrapper for LLM API calls with retry and structured output capabilities."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gpt-4o-mini",
        embedding_model: str = "text-embedding-3-small",
    ):
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OpenAI API key must be provided or set in OPENAI_API_KEY")
        self.client = OpenAI(api_key=self.api_key)
        self.model = model
        self.embedding_model = embedding_model

    def _call_with_retry(self, func: Callable[P, R], *args: P.args, **kwargs: P.kwargs) -> R:
        for attempt in Retrying(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=2, max=10),
            reraise=True,
        ):
            with attempt:
                return func(*args, **kwargs)
        raise AssertionError("Retrying should return a result or re-raise the last exception.")

    def _build_messages(
        self, prompt: str, system_prompt: Optional[str] = None
    ) -> list[ChatCompletionMessageParam]:
        messages: list[ChatCompletionMessageParam] = []
        if system_prompt:
            messages.append(
                cast(ChatCompletionMessageParam, {"role": "system", "content": system_prompt})
            )
        messages.append(cast(ChatCompletionMessageParam, {"role": "user", "content": prompt}))
        return messages

    def generate_structured_output(
        self, prompt: str, response_format: Type[T], system_prompt: Optional[str] = None
    ) -> T:
        """Generate structured JSON output constrained by a Pydantic model."""
        return self._call_with_retry(
            self._generate_structured_output_once,
            prompt,
            response_format,
            system_prompt,
        )

    def _generate_structured_output_once(
        self, prompt: str, response_format: Type[T], system_prompt: Optional[str] = None
    ) -> T:
        messages = self._build_messages(prompt, system_prompt)

        response = self.client.beta.chat.completions.parse(
            model=self.model,
            messages=messages,
            response_format=response_format,
        )

        parsed = response.choices[0].message.parsed
        if not isinstance(parsed, response_format):
            raise LLMError("Failed to parse structured output from LLM.")

        return parsed

    def generate_embedding(self, text: str) -> list[float]:
        """Generate an embedding vector for the provided text."""
        return self._call_with_retry(self._generate_embedding_once, text)

    def _generate_embedding_once(self, text: str) -> list[float]:
        response = self.client.embeddings.create(
            input=text,
            model=self.embedding_model,
        )
        embedding = response.data[0].embedding
        if not isinstance(embedding, Sequence):
            raise LLMError("Received invalid embedding response from LLM.")
        return [float(value) for value in embedding]

    def generate_text(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """Generate raw text response."""
        return self._call_with_retry(self._generate_text_once, prompt, system_prompt)

    def _generate_text_once(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        messages = self._build_messages(prompt, system_prompt)

        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
        )

        content = response.choices[0].message.content
        if not isinstance(content, str):
            raise LLMError("Received empty response from LLM.")

        return content
