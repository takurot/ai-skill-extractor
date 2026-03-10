from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from src.models.db import ReviewItem, SkillCandidate


class ArtifactGenerator:
    """Generates YAML and Markdown artifacts from accepted skill candidates."""

    def __init__(
        self,
        output_root: str | None = None,
        *,
        language_split: bool = True,
        framework_split: bool = True,
    ) -> None:
        self.output_root = Path(output_root) if output_root else Path(".")
        self.language_split = language_split
        self.framework_split = framework_split

    def generate(
        self,
        accepted_candidates: list[SkillCandidate],
        review_items: list[ReviewItem],
        *,
        skills_output_path: str,
        docs_output_dir: str,
        all_candidates: list[SkillCandidate] | None = None,
        rejection_reasons: dict[str, int] | None = None,
    ) -> list[str]:
        """Write all configured artifacts and return their paths."""
        generated_at = _isoformat_now()
        review_item_by_id = {item.id: item for item in review_items if item.id}
        sorted_candidates = sorted(
            accepted_candidates,
            key=lambda candidate: (candidate.category or "", candidate.canonical_name or ""),
        )

        skills_document = {
            "version": "1.0",
            "generated_at": generated_at,
            "source_summary": self._build_source_summary(sorted_candidates, review_items),
            "skills": [
                self._build_skill_payload(candidate, review_item_by_id, generated_at)
                for candidate in sorted_candidates
            ],
        }

        skills_path = self.output_root / Path(skills_output_path)
        docs_path = self.output_root / Path(docs_output_dir)
        written_paths = [
            self._write_yaml(skills_path, skills_document),
            self._write_markdown(
                docs_path / "review_dimensions.md",
                self._render_review_dimensions(sorted_candidates),
            ),
            self._write_markdown(
                docs_path / "anti_patterns.md",
                self._render_anti_patterns(sorted_candidates),
            ),
            self._write_markdown(
                docs_path / "source_coverage_report.md",
                self._render_source_coverage_report(
                    sorted_candidates,
                    review_items,
                    generated_at,
                    all_candidates or accepted_candidates,
                    rejection_reasons or {},
                ),
            ),
        ]

        if self.language_split:
            written_paths.extend(self._write_language_splits(skills_path, skills_document))
        if self.framework_split:
            written_paths.extend(self._write_framework_splits(skills_path, skills_document))

        return written_paths

    def _build_source_summary(
        self,
        accepted_candidates: list[SkillCandidate],
        review_items: list[ReviewItem],
    ) -> dict[str, Any]:
        repos = sorted({item.repo for item in review_items if item.repo})
        pr_count = len(
            {
                (item.repo, item.pr_number)
                for item in review_items
                if item.repo and item.pr_number is not None
            }
        )
        return {
            "repos": repos,
            "pr_count": pr_count,
            "review_item_count": len(review_items),
            "accepted_skill_count": len(accepted_candidates),
        }

    def _build_skill_payload(
        self,
        candidate: SkillCandidate,
        review_item_by_id: dict[str, ReviewItem],
        generated_at: str,
    ) -> dict[str, Any]:
        related_items = [
            review_item_by_id[item_id]
            for item_id in (candidate.source_review_item_ids or [])
            if item_id in review_item_by_id
        ]
        repos = sorted({item.repo for item in related_items if item.repo})
        applies_when = (
            [candidate.detection_hint_draft]
            if candidate.detection_hint_draft
            else ["The change introduces behavior that should be reviewed."]
        )
        return {
            "id": _slugify(candidate.canonical_name or candidate.id or "skill"),
            "name": candidate.canonical_name,
            "category": candidate.category,
            "scope": candidate.applicability_scope,
            "languages": sorted(set(candidate.languages or [])),
            "frameworks": sorted(set(candidate.frameworks or [])),
            "description": candidate.description_draft,
            "rationale": candidate.engineering_principle,
            "detection_hint": candidate.detection_hint_draft,
            "review_prompt": candidate.review_prompt_draft,
            "severity": _severity_for_candidate(candidate),
            "confidence": round(float(candidate.confidence or 0.0), 4),
            "applicability": {
                "applies_when": applies_when,
                "does_not_apply_when": [
                    "The change is purely cosmetic.",
                    "The rule is not relevant to the modified code path.",
                ],
            },
            "examples": {
                "bad": [f"Missing review coverage for {candidate.canonical_name.lower()}."],
                "good": [f"Review explicitly validates {candidate.canonical_name.lower()}."],
            },
            "evidence": {
                "source_count": candidate.evidence_count
                or len(candidate.source_review_item_ids or []),
                "repos": repos,
                "representative_review_item_ids": (candidate.source_review_item_ids or [])[:3],
            },
            "metadata": {
                "generated_by": "rke-2.0",
                "generated_at": generated_at,
                "version": "1.0",
            },
        }

    def _render_review_dimensions(self, accepted_candidates: list[SkillCandidate]) -> str:
        lines = ["# Review Dimensions", ""]
        grouped: dict[str, list[SkillCandidate]] = {}
        for candidate in accepted_candidates:
            grouped.setdefault(candidate.category or "uncategorized", []).append(candidate)

        for category in sorted(grouped):
            skills = sorted(grouped[category], key=lambda candidate: candidate.canonical_name or "")
            lines.extend(
                [
                    f"## {category}",
                    "",
                    "Representative skills:",
                    *[
                        f"- {candidate.canonical_name}: {candidate.description_draft}"
                        for candidate in skills
                    ],
                    "",
                    "Review questions:",
                    *[
                        f"- {candidate.review_prompt_draft}"
                        for candidate in skills
                        if candidate.review_prompt_draft
                    ],
                    "",
                    "Frequent failure patterns:",
                    *[
                        f"- {candidate.detection_hint_draft}"
                        for candidate in skills
                        if candidate.detection_hint_draft
                    ],
                    "",
                ]
            )

        return "\n".join(lines).rstrip() + "\n"

    def _render_anti_patterns(self, accepted_candidates: list[SkillCandidate]) -> str:
        lines = ["# Anti Patterns", ""]
        for candidate in sorted(
            accepted_candidates,
            key=lambda item: (item.category or "", item.canonical_name or ""),
        ):
            lines.extend(
                [
                    f"## {candidate.canonical_name}",
                    "",
                    f"- Category: {candidate.category}",
                    f"- Failure pattern: {candidate.description_draft}",
                    f"- Detection hint: {candidate.detection_hint_draft}",
                    f"- Review focus: {candidate.review_prompt_draft}",
                    "",
                ]
            )
        return "\n".join(lines).rstrip() + "\n"

    def _render_source_coverage_report(
        self,
        accepted_candidates: list[SkillCandidate],
        review_items: list[ReviewItem],
        generated_at: str,
        all_candidates: list[SkillCandidate],
        rejection_reasons: dict[str, int],
    ) -> str:
        category_counts = Counter(
            candidate.category or "uncategorized" for candidate in accepted_candidates
        )
        repos = sorted({item.repo for item in review_items if item.repo})
        pr_count = len(
            {
                (item.repo, item.pr_number)
                for item in review_items
                if item.repo and item.pr_number is not None
            }
        )

        lines = [
            "# Source Coverage Report",
            "",
            f"Generated at: {generated_at}",
            "",
            "## Summary",
            "",
            f"- Repositories: {', '.join(repos) if repos else 'None'}",
            f"- PR count: {pr_count}",
            f"- Review item count: {len(review_items)}",
            f"- Accepted skill count: {len(accepted_candidates)}",
            f"- Total candidate count: {len(all_candidates)}",
            "",
            "## Category Distribution",
            "",
        ]
        lines.extend(
            f"- {category}: {count}" for category, count in sorted(category_counts.items())
        )
        if rejection_reasons:
            lines.extend(["", "## Rejection Reasons", ""])
            lines.extend(
                f"- {reason}: {count}" for reason, count in sorted(rejection_reasons.items())
            )
        return "\n".join(lines).rstrip() + "\n"

    def _write_language_splits(
        self, skills_output_path: Path, skills_document: dict[str, Any]
    ) -> list[str]:
        written_paths: list[str] = []
        languages = sorted(
            {
                language
                for skill in skills_document["skills"]
                for language in skill["languages"]
                if language
            }
        )
        for language in languages:
            filtered_document = {
                **skills_document,
                "skills": [
                    skill for skill in skills_document["skills"] if language in skill["languages"]
                ],
            }
            written_paths.append(
                self._write_yaml(skills_output_path.parent / f"{language}.yaml", filtered_document)
            )
        return written_paths

    def _write_framework_splits(
        self, skills_output_path: Path, skills_document: dict[str, Any]
    ) -> list[str]:
        written_paths: list[str] = []
        frameworks = sorted(
            {
                framework
                for skill in skills_document["skills"]
                for framework in skill["frameworks"]
                if framework
            }
        )
        framework_dir = skills_output_path.parent / "framework"
        for framework in frameworks:
            filtered_document = {
                **skills_document,
                "skills": [
                    skill for skill in skills_document["skills"] if framework in skill["frameworks"]
                ],
            }
            written_paths.append(
                self._write_yaml(framework_dir / f"{framework}.yaml", filtered_document)
            )
        return written_paths

    def _write_yaml(self, path: Path, payload: dict[str, Any]) -> str:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            yaml.safe_dump(payload, sort_keys=False, allow_unicode=False),
            encoding="utf-8",
        )
        return str(path)

    def _write_markdown(self, path: Path, content: str) -> str:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return str(path)


def _slugify(value: str) -> str:
    normalized = "".join(ch.lower() if ch.isalnum() else " " for ch in value)
    return "_".join(part for part in normalized.split())


def _severity_for_candidate(candidate: SkillCandidate) -> str:
    high_impact_categories = {"security", "concurrency", "memory"}
    confidence = float(candidate.confidence or 0.0)
    if (candidate.category or "") in high_impact_categories and confidence >= 0.85:
        return "high"
    if confidence >= 0.75 or (candidate.evidence_count or 0) >= 3:
        return "medium"
    return "low"


def _isoformat_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
