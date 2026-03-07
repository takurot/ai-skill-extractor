from typing import List

from src.analyze.llm_client import LLMClient
from src.models.db import SkillCandidate


class SkillEmbedder:
    """Generates and stores embeddings for SkillCandidates."""

    def __init__(self, llm_client: LLMClient):
        self.llm = llm_client

    def generate_embedding(self, text: str) -> List[float]:
        """Generate an embedding for the given text."""
        return self.llm.generate_embedding(text)

    def process_candidates(self, candidates: List[SkillCandidate]) -> None:
        """Process a list of SkillCandidates, computing and assigning embeddings."""
        for candidate in candidates:
            try:
                # We embed a combination of canonical_name and description
                text_to_embed = f"{candidate.canonical_name}\n{candidate.description_draft}"
                embedding = self.generate_embedding(text_to_embed)
                candidate.embedding = embedding
            except Exception as e:
                print(f"Failed to generate embedding for candidate {candidate.id}: {e}")
