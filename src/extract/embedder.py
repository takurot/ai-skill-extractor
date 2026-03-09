from src.analyze.llm_client import LLMClient
from src.models.db import SkillCandidate


class EmbeddingGenerationError(Exception):
    """Raised when one or more candidate embeddings cannot be generated."""

    def __init__(self, failures: list[tuple[str, str]]):
        self.failures = failures
        failed_ids = ", ".join(candidate_id for candidate_id, _ in failures)
        super().__init__(
            f"failed to generate embeddings for {len(failures)} candidate(s): {failed_ids}"
        )


class SkillEmbedder:
    """Generates and stores embeddings for SkillCandidates."""

    def __init__(self, llm_client: LLMClient):
        self.llm = llm_client

    def generate_embedding(self, text: str) -> list[float]:
        """Generate an embedding for the given text."""
        return self.llm.generate_embedding(text)

    def process_candidates(self, candidates: list[SkillCandidate]) -> None:
        """Process a list of SkillCandidates, computing and assigning embeddings."""
        failures: list[tuple[str, str]] = []
        for candidate in candidates:
            try:
                text_to_embed = f"{candidate.canonical_name}\n{candidate.description_draft}"
                embedding = self.generate_embedding(text_to_embed)
                candidate.embedding = embedding
            except Exception as exc:
                failures.append((candidate.id, str(exc)))

        if failures:
            raise EmbeddingGenerationError(failures)
