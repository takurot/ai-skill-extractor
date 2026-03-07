from string import Template


class PromptManager:
    """Manages prompt templates for LLM tasks."""

    TEMPLATES = {
        "analyze_review_comment": Template(
            "Analyze the following code review comment and determine its category, "
            "quality, and whether it's actionable.\n\n"
            "File: $file_path\n"
            "Language: $language\n\n"
            "Before:\n$code_before\n\n"
            "After:\n$code_after\n\n"
            "Comment:\n$comment_text\n\n"
            "Return the analysis in the requested JSON format."
        ),
        "extract_skill_candidate": Template(
            "Extract a generic software engineering skill from this review context.\n\n"
            "Category: $category\n"
            "Comment: $comment_text\n\n"
            "Create a generalized skill candidate, including rationale and detection hints."
        ),
        "deduplicate_skills": Template(
            "Merge these similar skill candidates into a single canonical skill.\n\n"
            "Candidates:\n$candidates\n\n"
            "Return a unified Canonical Skill."
        ),
    }

    @classmethod
    def get_prompt(cls, template_name: str, **kwargs: str) -> str:
        """Render a prompt template with the provided kwargs."""
        if template_name not in cls.TEMPLATES:
            raise KeyError(f"Template '{template_name}' not found.")

        template = cls.TEMPLATES[template_name]
        return template.safe_substitute(**kwargs)
