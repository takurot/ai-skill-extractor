from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect
from typer.testing import CliRunner

from src.cli.main import app
from src.storage.migration_manager import get_head_revision

runner = CliRunner()


def _write_config(tmp_path: Path, *, db_path: Path, artifact_dir: Path) -> Path:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        f"""
storage:
  db_url: "sqlite:///{db_path}"
  artifact_dir: "{artifact_dir}"

models:
  embedding_model: text-embedding-3-large
  classification_model: gpt-4o
  summarization_model: gpt-4o-mini

pipeline:
  enable_human_review: true
  min_skill_confidence: 0.72
  min_cross_repo_support: 2
  require_evidence: true
  enable_fix_correlation: true
  dedup_threshold: 0.88
  redact_identity: true

generation:
  skills_output: skills/SKILLS.yaml
  docs_output_dir: docs
  language_split: true
  framework_split: true
""".strip()
        + "\n",
        encoding="utf-8",
    )
    return config_path


def test_init_db_creates_schema_and_applies_head_revision(tmp_path: Path) -> None:
    db_path = tmp_path / "rke.db"
    config_path = _write_config(
        tmp_path,
        db_path=db_path,
        artifact_dir=tmp_path / "artifacts",
    )

    result = runner.invoke(app, ["init-db", "--config-file", str(config_path)])

    assert result.exit_code == 0
    engine = create_engine(f"sqlite:///{db_path}")
    with engine.connect() as connection:
        table_names = set(inspect(connection).get_table_names())
        current_revision = connection.exec_driver_sql(
            "SELECT version_num FROM alembic_version"
        ).scalar_one()
    assert {"raw_pull_requests", "review_items", "skill_candidates"} <= table_names
    assert current_revision == get_head_revision()


def test_normalize_requires_migrated_database(tmp_path: Path) -> None:
    config_path = _write_config(
        tmp_path,
        db_path=tmp_path / "not_initialized.db",
        artifact_dir=tmp_path / "artifacts",
    )

    result = runner.invoke(app, ["normalize", "--config-file", str(config_path)])

    assert result.exit_code == 1
    assert "Database is not initialized" in result.stdout


def test_generate_preflight_creates_output_dir(tmp_path: Path) -> None:
    artifact_dir = tmp_path / "artifacts"
    config_path = _write_config(
        tmp_path,
        db_path=tmp_path / "ready.db",
        artifact_dir=artifact_dir,
    )
    init_result = runner.invoke(app, ["init-db", "--config-file", str(config_path)])
    assert init_result.exit_code == 0
    assert not artifact_dir.exists()

    result = runner.invoke(app, ["generate", "--config-file", str(config_path)])

    assert result.exit_code == 0
    assert artifact_dir.exists()
    assert (artifact_dir / "skills" / "SKILLS.yaml").exists()


def test_migrate_is_idempotent_after_initialization(tmp_path: Path) -> None:
    config_path = _write_config(
        tmp_path,
        db_path=tmp_path / "ready.db",
        artifact_dir=tmp_path / "artifacts",
    )
    init_result = runner.invoke(app, ["init-db", "--config-file", str(config_path)])
    assert init_result.exit_code == 0

    result = runner.invoke(app, ["migrate", "--config-file", str(config_path)])

    assert result.exit_code == 0
    assert get_head_revision() in result.stdout


def test_run_preflight_requires_pipeline_env_vars(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_path = _write_config(
        tmp_path,
        db_path=tmp_path / "ready.db",
        artifact_dir=tmp_path / "artifacts",
    )
    init_result = runner.invoke(app, ["init-db", "--config-file", str(config_path)])
    assert init_result.exit_code == 0
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    result = runner.invoke(app, ["run", "--config-file", str(config_path)])

    assert result.exit_code == 1
    assert "GITHUB_TOKEN" in result.stdout
    assert "OPENAI_API_KEY" in result.stdout
