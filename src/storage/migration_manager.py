from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config as AlembicConfig
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy.engine import make_url

from src.storage.database import get_engine

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ALEMBIC_INI_PATH = PROJECT_ROOT / "alembic.ini"


def apply_migrations(db_url: str, revision: str = "head") -> str:
    """Apply Alembic migrations up to the requested revision."""
    _ensure_database_path(db_url)
    command.upgrade(_build_alembic_config(db_url), revision)
    return get_head_revision()


def get_current_revision(db_url: str) -> str | None:
    """Return the database's currently applied Alembic revision."""
    _ensure_database_path(db_url)
    engine = get_engine(db_url)
    try:
        with engine.connect() as connection:
            context = MigrationContext.configure(connection)
            return context.get_current_revision()
    finally:
        engine.dispose()


def get_head_revision() -> str:
    """Return the current Alembic head revision for the repository."""
    head_revision = ScriptDirectory.from_config(_build_alembic_config()).get_current_head()
    if head_revision is None:
        raise RuntimeError("Alembic has no configured head revision.")
    return head_revision


def _build_alembic_config(db_url: str | None = None) -> AlembicConfig:
    config = AlembicConfig(str(ALEMBIC_INI_PATH))
    if db_url is not None:
        config.set_main_option("sqlalchemy.url", db_url)
    return config


def _ensure_database_path(db_url: str) -> None:
    url = make_url(db_url)
    if not url.drivername.startswith("sqlite"):
        return

    database = url.database
    if not database or database == ":memory:":
        return

    Path(database).expanduser().parent.mkdir(parents=True, exist_ok=True)
