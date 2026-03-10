from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from math import sqrt
from pathlib import Path
from statistics import fmean
from typing import Iterable, Mapping, Sequence

from pydantic import BaseModel, Field

from src.analyze.llm_client import LLMClient
from src.analyze.prompts import PromptManager
from src.models.db import ReviewItem, SkillCandidate


class CanonicalSkillResult(BaseModel):
    canonical_name: str = Field(description="Merged canonical skill name.")
    description_draft: str = Field(description="Merged description for the canonical skill.")
    engineering_principle: str = Field(description="Underlying engineering principle.")
    review_prompt_draft: str = Field(description="Review prompt for the canonical skill.")
    detection_hint_draft: str = Field(description="Detection hints for the canonical skill.")
    applicability_scope: str = Field(description="Applicability scope for the canonical skill.")
    languages: list[str] = Field(description="Applicable languages for the canonical skill.")
    frameworks: list[str] = Field(description="Applicable frameworks for the canonical skill.")
    confidence: float = Field(description="Confidence score from 0.0 to 1.0.")


@dataclass(frozen=True)
class CandidateCluster:
    canonical_candidate_id: str
    candidate_ids: list[str]
    cross_repo_count: int
    score: float
    status: str
    rejection_reason: str | None


@dataclass(frozen=True)
class CandidateCurationReport:
    accepted_candidates: list[SkillCandidate]
    rejected_candidates: list[SkillCandidate]
    clusters: list[CandidateCluster]
    rejection_reasons: dict[str, int]


class SkillDeduplicator:
    """Clusters similar skill candidates and promotes canonical accepted skills."""

    def __init__(
        self,
        llm_client: LLMClient,
        dedup_threshold: float = 0.88,
        min_skill_confidence: float = 0.72,
        min_cross_repo_support: int = 2,
    ):
        self.llm = llm_client
        self.similarity_threshold = dedup_threshold
        self.min_skill_confidence = min_skill_confidence
        self.min_cross_repo_support = min_cross_repo_support

    def cluster_candidates(
        self, candidates: Sequence[SkillCandidate]
    ) -> list[list[SkillCandidate]]:
        """Cluster candidates using cosine similarity within the same category."""
        ordered_candidates = sorted(candidates, key=lambda candidate: candidate.id)
        adjacency: dict[str, set[str]] = {candidate.id: set() for candidate in ordered_candidates}
        candidate_by_id = {candidate.id: candidate for candidate in ordered_candidates}

        for index, candidate in enumerate(ordered_candidates):
            for other in ordered_candidates[index + 1 :]:
                if candidate.category != other.category:
                    continue
                similarity = self.cosine_similarity(candidate.embedding, other.embedding)
                if similarity < self.similarity_threshold:
                    continue
                adjacency[candidate.id].add(other.id)
                adjacency[other.id].add(candidate.id)

        clusters: list[list[SkillCandidate]] = []
        visited: set[str] = set()
        for candidate in ordered_candidates:
            if candidate.id in visited:
                continue

            stack = [candidate.id]
            cluster_ids: list[str] = []
            while stack:
                current_id = stack.pop()
                if current_id in visited:
                    continue
                visited.add(current_id)
                cluster_ids.append(current_id)
                stack.extend(sorted(adjacency[current_id] - visited))

            clusters.append([candidate_by_id[cluster_id] for cluster_id in sorted(cluster_ids)])

        return clusters

    def process_candidates(
        self,
        candidates: Sequence[SkillCandidate],
        review_items: Sequence[ReviewItem] | Mapping[str, ReviewItem],
    ) -> CandidateCurationReport:
        """Curate proposed candidates in place and return accepted/rejected groups."""
        review_item_by_id = self._normalize_review_items(review_items)
        proposed_candidates = [
            candidate for candidate in candidates if candidate.status == "proposed"
        ]

        accepted: list[SkillCandidate] = []
        rejected: list[SkillCandidate] = []
        clusters: list[CandidateCluster] = []
        rejection_reasons: Counter[str] = Counter()

        for cluster in self.cluster_candidates(proposed_candidates):
            representative = self._choose_representative(cluster)
            merged = self._merge_cluster(cluster)
            self._apply_merged_fields(representative, merged, cluster)

            score = self._calculate_score(
                cluster=cluster,
                merged=merged,
                review_item_by_id=review_item_by_id,
            )
            representative.confidence = score
            cross_repo_count = len(self._collect_repos(cluster, review_item_by_id))

            rejection_reason = self._determine_rejection_reason(
                representative=representative,
                review_item_by_id=review_item_by_id,
            )

            if rejection_reason is None:
                representative.status = "accepted"
                representative.merged_into_id = None
                representative.rejection_reason = None
                accepted.append(representative)
                status = "accepted"
            else:
                representative.status = "rejected"
                representative.merged_into_id = None
                representative.rejection_reason = rejection_reason
                rejected.append(representative)
                rejection_reasons[rejection_reason] += 1
                status = "rejected"

            for candidate in cluster:
                if candidate.id == representative.id:
                    continue
                candidate.status = "rejected"
                candidate.merged_into_id = representative.id
                candidate.rejection_reason = "duplicate_cluster"
                rejected.append(candidate)

            clusters.append(
                CandidateCluster(
                    canonical_candidate_id=representative.id,
                    candidate_ids=[candidate.id for candidate in cluster],
                    cross_repo_count=cross_repo_count,
                    score=score,
                    status=status,
                    rejection_reason=rejection_reason,
                )
            )

        return CandidateCurationReport(
            accepted_candidates=accepted,
            rejected_candidates=rejected,
            clusters=clusters,
            rejection_reasons=dict(rejection_reasons),
        )

    def _merge_cluster(self, cluster: Sequence[SkillCandidate]) -> CanonicalSkillResult:
        if len(cluster) == 1:
            candidate = cluster[0]
            return CanonicalSkillResult(
                canonical_name=candidate.canonical_name,
                description_draft=candidate.description_draft,
                engineering_principle=candidate.engineering_principle,
                review_prompt_draft=candidate.review_prompt_draft,
                detection_hint_draft=candidate.detection_hint_draft,
                applicability_scope=candidate.applicability_scope,
                languages=sorted(set(candidate.languages)),
                frameworks=sorted(set(candidate.frameworks)),
                confidence=float(candidate.confidence),
            )

        prompt = PromptManager.get_prompt(
            "deduplicate_skills",
            candidates=self._format_candidates_for_prompt(cluster),
        )
        system_prompt = (
            "You are an expert technical lead consolidating overlapping code review skills into "
            "a single canonical rule."
        )
        return self.llm.generate_structured_output(
            prompt=prompt,
            response_format=CanonicalSkillResult,
            system_prompt=system_prompt,
        )

    def _format_candidates_for_prompt(self, cluster: Sequence[SkillCandidate]) -> str:
        lines = []
        for candidate in sorted(cluster, key=lambda item: item.id):
            lines.append(
                "\n".join(
                    [
                        f"- id: {candidate.id}",
                        f"  name: {candidate.canonical_name}",
                        f"  category: {candidate.category}",
                        f"  description: {candidate.description_draft}",
                        f"  principle: {candidate.engineering_principle}",
                        f"  prompt: {candidate.review_prompt_draft}",
                        f"  hints: {candidate.detection_hint_draft}",
                        f"  scope: {candidate.applicability_scope}",
                    ]
                )
            )
        return "\n".join(lines)

    def _choose_representative(self, cluster: Sequence[SkillCandidate]) -> SkillCandidate:
        return max(cluster, key=lambda candidate: (candidate.confidence, candidate.id))

    def _apply_merged_fields(
        self,
        representative: SkillCandidate,
        merged: CanonicalSkillResult,
        cluster: Sequence[SkillCandidate],
    ) -> None:
        representative.source_review_item_ids = sorted(
            {item_id for candidate in cluster for item_id in candidate.source_review_item_ids}
        )
        representative.canonical_name = merged.canonical_name
        representative.description_draft = merged.description_draft
        representative.engineering_principle = merged.engineering_principle
        representative.review_prompt_draft = merged.review_prompt_draft
        representative.detection_hint_draft = merged.detection_hint_draft
        representative.applicability_scope = merged.applicability_scope
        representative.languages = sorted(
            set(merged.languages)
            | {language for candidate in cluster for language in candidate.languages}
        )
        representative.frameworks = sorted(
            set(merged.frameworks)
            | {framework for candidate in cluster for framework in candidate.frameworks}
        )
        representative.evidence_count = len(representative.source_review_item_ids)
        representative.embedding = representative.embedding or next(
            (candidate.embedding for candidate in cluster if candidate.embedding is not None),
            None,
        )

    def _calculate_score(
        self,
        cluster: Sequence[SkillCandidate],
        merged: CanonicalSkillResult,
        review_item_by_id: dict[str, ReviewItem],
    ) -> float:
        evidence_count = len(
            {item_id for candidate in cluster for item_id in candidate.source_review_item_ids}
        )
        repo_count = len(self._collect_repos(cluster, review_item_by_id))
        fix_signals = [
            self._fix_score(review_item_by_id.get(item_id))
            for candidate in cluster
            for item_id in candidate.source_review_item_ids
        ]
        base_confidence = fmean(candidate.confidence for candidate in cluster)
        evidence_score = min(1.0, evidence_count / 3)
        cross_repo_score = min(1.0, repo_count / max(self.min_cross_repo_support, 1))
        fix_score = fmean(fix_signals) if fix_signals else 0.5
        scope_score = {
            "general": 1.0,
            "language_specific": 0.9,
            "framework_specific": 0.85,
            "repo_specific": 0.4,
        }.get(merged.applicability_scope, 0.75)
        weighted_score = (
            0.35 * float(merged.confidence)
            + 0.2 * base_confidence
            + 0.15 * evidence_score
            + 0.15 * cross_repo_score
            + 0.1 * fix_score
            + 0.05 * scope_score
        )
        return round(min(weighted_score, 0.99), 4)

    def _determine_rejection_reason(
        self,
        representative: SkillCandidate,
        review_item_by_id: dict[str, ReviewItem],
    ) -> str | None:
        if representative.applicability_scope == "repo_specific":
            return "repo_specific_scope"
        if representative.evidence_count < self._minimum_evidence_required(representative):
            return "insufficient_evidence"
        if representative.confidence < self.min_skill_confidence:
            return "low_confidence"

        repo_count = len(self._collect_repos([representative], review_item_by_id))
        if (
            representative.applicability_scope == "general"
            and repo_count < self.min_cross_repo_support
        ):
            return "insufficient_cross_repo_support"
        return None

    def _minimum_evidence_required(self, representative: SkillCandidate) -> int:
        if representative.applicability_scope == "general":
            return 3
        if representative.applicability_scope == "repo_specific":
            return 1
        return 1

    def _normalize_review_items(
        self, review_items: Sequence[ReviewItem] | Mapping[str, ReviewItem]
    ) -> dict[str, ReviewItem]:
        if isinstance(review_items, Mapping):
            return dict(review_items)
        return {item.id: item for item in review_items}

    def _collect_repos(
        self, candidates: Iterable[SkillCandidate], review_item_by_id: dict[str, ReviewItem]
    ) -> set[str]:
        repos: set[str] = set()
        for candidate in candidates:
            for item_id in candidate.source_review_item_ids:
                review_item = review_item_by_id.get(item_id)
                if review_item is not None and review_item.repo:
                    repos.add(review_item.repo)
        return repos

    def _fix_score(self, review_item: ReviewItem | None) -> float:
        if review_item is None or review_item.fix_correlation is None:
            return 0.5
        return 1.0 if review_item.fix_correlation else 0.0

    def cosine_similarity(
        self, left: Sequence[float] | None, right: Sequence[float] | None
    ) -> float:
        """Calculate cosine similarity between two embeddings."""
        if left is None or right is None or len(left) != len(right) or not left:
            return 0.0

        numerator = sum(float(a) * float(b) for a, b in zip(left, right, strict=True))
        left_norm = sqrt(sum(float(value) * float(value) for value in left))
        right_norm = sqrt(sum(float(value) * float(value) for value in right))
        if left_norm == 0 or right_norm == 0:
            return 0.0
        return numerator / (left_norm * right_norm)


def write_deduplication_artifacts(output_dir: str, report: CandidateCurationReport) -> None:
    """Write cluster and rejection summaries to the analysis artifact directory."""
    analysis_dir = Path(output_dir) / "analysis"
    analysis_dir.mkdir(parents=True, exist_ok=True)

    cluster_payload = [
        {
            "canonical_candidate_id": cluster.canonical_candidate_id,
            "candidate_ids": cluster.candidate_ids,
            "cross_repo_count": cluster.cross_repo_count,
            "score": cluster.score,
            "status": cluster.status,
            "rejection_reason": cluster.rejection_reason,
        }
        for cluster in report.clusters
    ]
    rejected_payload = [
        {
            "id": candidate.id,
            "canonical_name": candidate.canonical_name,
            "merged_into_id": candidate.merged_into_id,
            "rejection_reason": candidate.rejection_reason,
            "status": candidate.status,
        }
        for candidate in report.rejected_candidates
        if candidate.rejection_reason != "duplicate_cluster"
    ]

    (analysis_dir / "skill_clusters.json").write_text(
        json.dumps(cluster_payload, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    (analysis_dir / "rejected_candidates.json").write_text(
        json.dumps(rejected_payload, indent=2, sort_keys=True),
        encoding="utf-8",
    )


DeduplicationResult = CandidateCurationReport
