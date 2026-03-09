from pathlib import Path

import yaml
from sqlalchemy.orm import Session
from typer.testing import CliRunner

from src.cli.main import app
from src.models.config import Config, GenerationConfig, StorageConfig
from src.models.db import Base, ReviewItem, SkillCandidate
from src.storage.database import get_engine, get_session_factory

runner = CliRunner()


def test_generate_command_creates_expected_artifacts(tmp_path: Path) -> None:
    db_path = tmp_path / "rke.db"
    artifact_dir = tmp_path / "output"
    config_path = tmp_path / "config.yaml"
    engine = get_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    session_factory = get_session_factory(engine)

    with session_factory() as session:
        _seed_generation_data(session)

    config = Config(
        storage=StorageConfig(db_url=f"sqlite:///{db_path}", artifact_dir=str(artifact_dir)),
        generation=GenerationConfig(
            skills_output="skills/SKILLS.yaml",
            docs_output_dir="docs",
            language_split=True,
            framework_split=True,
        ),
    )
    config_path.write_text(yaml.safe_dump(config.model_dump(), sort_keys=False), encoding="utf-8")

    result = runner.invoke(app, ["generate", "--config-file", str(config_path)])

    assert result.exit_code == 0
    skills_path = artifact_dir / "skills" / "SKILLS.yaml"
    coverage_path = artifact_dir / "docs" / "source_coverage_report.md"
    assert skills_path.exists()
    assert coverage_path.exists()
    payload = yaml.safe_load(skills_path.read_text(encoding="utf-8"))
    assert payload["source_summary"]["accepted_skill_count"] == 1
    assert payload["skills"][0]["id"] == "edge_case_testing"
    assert "- repo_specific_scope: 1" in coverage_path.read_text(encoding="utf-8")


def _seed_generation_data(session: Session) -> None:
    session.add(
        ReviewItem(
            id="ri_1",
            repo="org/repo-a",
            pr_number=1,
            source_type="review_comment",
            source_id="source_1",
            category="testing",
            comment_text="Add edge-case tests",
        )
    )
    session.add(
        ReviewItem(
            id="ri_2",
            repo="org/repo-b",
            pr_number=2,
            source_type="review_comment",
            source_id="source_2",
            category="testing",
            comment_text="Test invalid input",
        )
    )
    session.add(
        SkillCandidate(
            id="sc_accepted",
            source_review_item_ids=["ri_1", "ri_2"],
            canonical_name="Edge Case Testing",
            category="testing",
            description_draft="Test boundary and invalid inputs.",
            engineering_principle="Boundary conditions reveal correctness bugs.",
            review_prompt_draft="Check changed behavior for edge-case coverage.",
            detection_hint_draft="Look for public entry points without edge-case tests.",
            applicability_scope="general",
            languages=["python"],
            frameworks=[],
            confidence=0.91,
            evidence_count=2,
            status="accepted",
        )
    )
    session.add(
        SkillCandidate(
            id="sc_rejected",
            source_review_item_ids=["ri_1"],
            canonical_name="Repo Local Rule",
            category="readability",
            description_draft="Use the team's local abbreviation table.",
            engineering_principle="Consistency",
            review_prompt_draft="Check local abbreviations.",
            detection_hint_draft="Repo-specific naming pattern.",
            applicability_scope="repo_specific",
            languages=["python"],
            frameworks=[],
            confidence=0.4,
            evidence_count=1,
            status="rejected",
            rejection_reason="repo_specific_scope",
        )
    )
    session.commit()
