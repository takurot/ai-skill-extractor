from __future__ import annotations

import os
from collections.abc import Sequence
from pathlib import Path

from sqlalchemy import text

from src.models.config import Config
from src.storage.database import get_engine
from src.storage.migration_manager import get_current_revision, get_head_revision


class PreflightCheckError(Exception):
    """Raised when a command's runtime prerequisites are not satisfied."""


def run_preflight(config: Config, *, required_env_vars: Sequence[str] = ()) -> None:
    """Validate runtime prerequisites for commands that need initialized storage."""
    _ensure_required_env_vars(required_env_vars)
    _ensure_output_directory(config.storage.artifact_dir)
    _ensure_database_connection(config.storage.db_url)
    _ensure_current_migration(config.storage.db_url)


def _ensure_required_env_vars(required_env_vars: Sequence[str]) -> None:
    missing_env_vars = [name for name in required_env_vars if not os.environ.get(name)]
    if missing_env_vars:
        missing = ", ".join(sorted(missing_env_vars))
        raise PreflightCheckError(f"Missing required environment variables: {missing}")


def _ensure_output_directory(artifact_dir: str) -> None:
    Path(artifact_dir).mkdir(parents=True, exist_ok=True)


def _ensure_database_connection(db_url: str) -> None:
    engine = get_engine(db_url)
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    finally:
        engine.dispose()


def _ensure_current_migration(db_url: str) -> None:
    current_revision = get_current_revision(db_url)
    head_revision = get_head_revision()

    if current_revision is None:
        raise PreflightCheckError("Database is not initialized. Run `rke init-db` first.")
    if current_revision != head_revision:
        raise PreflightCheckError(
            "Database migrations are out of date "
            f"(current: {current_revision}, head: {head_revision}). Run `rke migrate`."
        )
