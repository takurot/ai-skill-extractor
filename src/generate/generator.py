from __future__ import annotations

import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping, Sequence

import yaml

from src.models.db import ReviewItem, SkillCandidate


class ArtifactGenerator:
    """Generate deterministic YAML and Markdown artifacts from accepted skills."""

    def __init__(
        self,
        output_root: str | Path,
        *,
        skills_output: str = "skills/SKILLS.yaml",
        docs_output_dir: str = "docs",
        language_split: bool = True,
        framework_split: bool = True,
        generated_by: str = "rke-2.0",
        version: str = "1.0",
    ) -> None:
        self.output_root = Path(output_root)
        self.skills_output = Path(skills_output)
        self.docs_output_dir = Path(docs_output_dir)
        self.language_split = language_split
        self.framework_split = framework_split
        self.generated_by = generated_by
        self.version = version

    def generate(
        self,
        accepted_candidates: Sequence[SkillCandidate],
        review_items: Sequence[ReviewItem] | Mapping[str, ReviewItem],
        *,
        skills_output_path: str,
        docs_output_dir: str,
        all_candidates: Sequence[SkillCandidate] | None = None,
        rejection_reasons: Mapping[str, int] | None = None,
        generated_at: datetime | None = None,
    ) -> list[str]:
        """Write YAML and Markdown artifacts and return their paths."""
        review_item_by_id = self._normalize_review_items(review_items)
        timestamp = generated_at or datetime.now(timezone.utc)
        accepted = sorted(
            accepted_candidates,
            key=lambda candidate: candidate.canonical_name.lower(),
        )
        candidates_for_metrics = (
            list(all_candidates) if all_candidates is not None else list(accepted)
        )
        rejection_summary = dict(rejection_reasons or {})

        skills_path = self.output_root / skills_output_path
        docs_dir = self.output_root / docs_output_dir
        skills_path.parent.mkdir(parents=True, exist_ok=True)
        docs_dir.mkdir(parents=True, exist_ok=True)

        payload = self._build_skills_payload(accepted, review_item_by_id, timestamp)
        skills_path.write_text(
            yaml.safe_dump(payload, allow_unicode=False, sort_keys=False),
            encoding="utf-8",
        )

        if self.language_split:
            self._write_language_split_files(
                accepted,
                review_item_by_id,
                timestamp,
                skills_path.parent,
            )
        if self.framework_split:
            self._write_framework_split_files(
                accepted,
                review_item_by_id,
                timestamp,
                skills_path.parent,
            )

        review_dimensions_path = docs_dir / "review_dimensions.md"
        anti_patterns_path = docs_dir / "anti_patterns.md"
        coverage_report_path = docs_dir / "source_coverage_report.md"

        review_dimensions_path.write_text(
            self._render_review_dimensions(accepted),
            encoding="utf-8",
        )
        anti_patterns_path.write_text(
            self._render_anti_patterns(accepted),
            encoding="utf-8",
        )
        coverage_report_path.write_text(
            self._render_coverage_report(
                accepted,
                review_item_by_id,
                candidates_for_metrics,
                rejection_summary,
            ),
            encoding="utf-8",
        )

        return [
            str(skills_path),
            str(review_dimensions_path),
            str(anti_patterns_path),
            str(coverage_report_path),
        ]

    def _build_skills_payload(
        self,
        candidates: Sequence[SkillCandidate],
        review_item_by_id: Mapping[str, ReviewItem],
        generated_at: datetime,
    ) -> dict[str, object]:
        review_items = list(review_item_by_id.values())
        repos = sorted({item.repo for item in review_items if item.repo})
        pr_count = len({(item.repo, item.pr_number) for item in review_items if item.repo})

        return {
            "version": self.version,
            "generated_at": generated_at.isoformat().replace("+00:00", "Z"),
            "source_summary": {
                "repos": repos,
                "pr_count": pr_count,
                "review_item_count": len(review_items),
                "accepted_skill_count": len(candidates),
            },
            "skills": [
                self._build_skill_entry(candidate, review_item_by_id, generated_at)
                for candidate in candidates
            ],
        }

    def _build_skill_entry(
        self,
        candidate: SkillCandidate,
        review_item_by_id: Mapping[str, ReviewItem],
        generated_at: datetime,
    ) -> dict[str, object]:
        representative_review_item_ids = sorted(candidate.source_review_item_ids)[:3]
        evidence_repos = sorted(
            {
                review_item.repo
                for review_item_id in candidate.source_review_item_ids
                if (review_item := review_item_by_id.get(review_item_id)) is not None
                and review_item.repo
            }
        )
        slug = self._slugify(candidate.canonical_name)

        return {
            "id": slug,
            "name": candidate.canonical_name,
            "category": candidate.category,
            "scope": candidate.applicability_scope,
            "languages": sorted(set(candidate.languages)),
            "frameworks": sorted(set(candidate.frameworks)),
            "description": candidate.description_draft,
            "rationale": candidate.engineering_principle,
            "detection_hint": candidate.detection_hint_draft,
            "review_prompt": candidate.review_prompt_draft,
            "severity": self._severity_for(candidate),
            "confidence": round(float(candidate.confidence), 2),
            "applicability": {
                "applies_when": self._applies_when(candidate),
                "does_not_apply_when": self._does_not_apply_when(candidate),
            },
            "examples": {
                "bad": [self._bad_example(candidate)],
                "good": [self._good_example(candidate)],
            },
            "evidence": {
                "source_count": int(candidate.evidence_count),
                "repos": evidence_repos,
                "representative_review_item_ids": representative_review_item_ids,
            },
            "metadata": {
                "generated_by": self.generated_by,
                "generated_at": generated_at.isoformat().replace("+00:00", "Z"),
                "version": self.version,
            },
        }

    def _write_language_split_files(
        self,
        candidates: Sequence[SkillCandidate],
        review_item_by_id: Mapping[str, ReviewItem],
        generated_at: datetime,
        skills_dir: Path,
    ) -> None:
        grouped: defaultdict[str, list[SkillCandidate]] = defaultdict(list)
        for candidate in candidates:
            if candidate.languages:
                for language in sorted(set(candidate.languages)):
                    grouped[language].append(candidate)
            else:
                grouped["general"].append(candidate)

        for language, language_candidates in grouped.items():
            payload = self._build_skills_payload(
                language_candidates,
                review_item_by_id,
                generated_at,
            )
            (skills_dir / f"{language}.yaml").write_text(
                yaml.safe_dump(payload, allow_unicode=False, sort_keys=False),
                encoding="utf-8",
            )

    def _write_framework_split_files(
        self,
        candidates: Sequence[SkillCandidate],
        review_item_by_id: Mapping[str, ReviewItem],
        generated_at: datetime,
        skills_dir: Path,
    ) -> None:
        framework_dir = skills_dir / "framework"
        grouped: defaultdict[str, list[SkillCandidate]] = defaultdict(list)
        for candidate in candidates:
            for framework in sorted(set(candidate.frameworks)):
                grouped[framework].append(candidate)

        if not grouped:
            return

        framework_dir.mkdir(parents=True, exist_ok=True)
        for framework, framework_candidates in grouped.items():
            payload = self._build_skills_payload(
                framework_candidates,
                review_item_by_id,
                generated_at,
            )
            (framework_dir / f"{framework}.yaml").write_text(
                yaml.safe_dump(payload, allow_unicode=False, sort_keys=False),
                encoding="utf-8",
            )

    def _render_review_dimensions(self, candidates: Sequence[SkillCandidate]) -> str:
        grouped: defaultdict[str, list[SkillCandidate]] = defaultdict(list)
        for candidate in candidates:
            grouped[candidate.category].append(candidate)

        lines = ["# Review Dimensions", ""]
        for category in sorted(grouped):
            lines.append(f"## {category}")
            lines.append("")
            for candidate in sorted(
                grouped[category],
                key=lambda item: item.canonical_name.lower(),
            ):
                lines.append(f"- Representative skill: {candidate.canonical_name}")
                lines.append(f"- Frequent failure pattern: {candidate.description_draft}")
                lines.append(f"- Review question: {candidate.review_prompt_draft}")
                lines.append("")
        return "\n".join(lines).rstrip() + "\n"

    def _render_anti_patterns(self, candidates: Sequence[SkillCandidate]) -> str:
        lines = ["# Anti Patterns", ""]
        for candidate in sorted(candidates, key=lambda item: item.canonical_name.lower()):
            lines.append(f"## {candidate.canonical_name}")
            lines.append("")
            lines.append(f"- Category: {candidate.category}")
            lines.append(f"- Bad example: {self._bad_example(candidate)}")
            lines.append(f"- AI review focus: {candidate.review_prompt_draft}")
            lines.append("")
        return "\n".join(lines).rstrip() + "\n"

    def _render_coverage_report(
        self,
        accepted_candidates: Sequence[SkillCandidate],
        review_item_by_id: Mapping[str, ReviewItem],
        all_candidates: Sequence[SkillCandidate],
        rejection_reasons: Mapping[str, int],
    ) -> str:
        repos = sorted({item.repo for item in review_item_by_id.values() if item.repo})
        category_counts = Counter(candidate.category for candidate in accepted_candidates)
        total_candidates = len(all_candidates)
        accepted_count = len(accepted_candidates)
        acceptance_rate = accepted_count / total_candidates if total_candidates else 0.0

        lines = ["# Source Coverage Report", ""]
        lines.append(f"- Target repos: {', '.join(repos) if repos else 'n/a'}")
        pr_count = len(
            {
                (item.repo, item.pr_number)
                for item in review_item_by_id.values()
                if item.repo
            }
        )
        lines.append(
            "- Collected PR count: "
            f"{pr_count}"
        )
        lines.append(f"- Collected review item count: {len(review_item_by_id)}")
        lines.append(f"- Accepted skill count: {accepted_count}")
        lines.append(f"- Acceptance rate: {acceptance_rate:.2%}")
        lines.append("")
        lines.append("## Top Rejection Reasons")
        lines.append("")
        if rejection_reasons:
            for reason, count in sorted(rejection_reasons.items()):
                lines.append(f"- {reason}: {count}")
        else:
            lines.append("- none: 0")
        lines.append("")
        lines.append("## Category Distribution")
        lines.append("")
        if category_counts:
            for category, count in sorted(category_counts.items()):
                lines.append(f"- {category}: {count}")
        else:
            lines.append("- none: 0")
        lines.append("")
        return "\n".join(lines)

    def _normalize_review_items(
        self, review_items: Sequence[ReviewItem] | Mapping[str, ReviewItem]
    ) -> dict[str, ReviewItem]:
        if isinstance(review_items, Mapping):
            return dict(review_items)
        return {item.id: item for item in review_items}

    def _severity_for(self, candidate: SkillCandidate) -> str:
        if (
            candidate.category in {"security", "concurrency", "memory"}
            and candidate.confidence >= 0.85
        ):
            return "high"
        if candidate.confidence >= 0.75:
            return "medium"
        return "low"

    def _applies_when(self, candidate: SkillCandidate) -> list[str]:
        primary_hint = candidate.detection_hint_draft.strip().rstrip(".")
        scope_hint = {
            "general": "the change introduces or modifies behavior that users rely on",
            "language_specific": "language-specific constructs or idioms are introduced",
            "framework_specific": "framework-managed lifecycle or APIs are changed",
            "repo_specific": "the repository has an explicit local convention for this pattern",
        }[candidate.applicability_scope]
        return [scope_hint, primary_hint] if primary_hint else [scope_hint]

    def _does_not_apply_when(self, candidate: SkillCandidate) -> list[str]:
        lines = ["the change is purely cosmetic"]
        if candidate.applicability_scope != "general":
            lines.append("the rule would overfit repository-local conventions")
        return lines

    def _bad_example(self, candidate: SkillCandidate) -> str:
        if candidate.category == "testing":
            return "A new public function ships without edge-case or invalid-input tests."
        if candidate.category == "readability":
            return "A public API introduces abbreviations that hide domain meaning."
        return f"The change ignores the rule behind {candidate.canonical_name}."

    def _good_example(self, candidate: SkillCandidate) -> str:
        if candidate.category == "testing":
            return "The patch adds tests for empty, boundary, and malformed inputs."
        if candidate.category == "readability":
            return "The code uses descriptive names that communicate intent without extra comments."
        return f"The code applies {candidate.canonical_name} consistently across the change."

    def _slugify(self, value: str) -> str:
        normalized = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
        return normalized or "skill"
