from datetime import datetime, timezone
from typing import Generator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.models.db import Base, RawPullRequest
from src.storage.database import upsert


# Use in-memory SQLite for testing upsert logic structure
# Note: PostgreSQL specific 'ON CONFLICT' won't work in SQLite,
# but we can verify the model and session usage.
@pytest.fixture
def session() -> Generator[Session, None, None]:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()
    yield session
    session.close()


def test_raw_pr_model(session: Session) -> None:
    pr_data = {
        "id": "repo/1",
        "repo": "repo",
        "pr_number": 1,
        "state": "merged",
        "changed_files_count": 5,
        "raw_data": {"test": "data"},
        "created_at": datetime.now(timezone.utc),
    }
    pr = RawPullRequest(**pr_data)
    session.add(pr)
    session.commit()

    saved_pr = session.query(RawPullRequest).filter_by(id="repo/1").first()
    assert saved_pr is not None
    assert saved_pr.state == "merged"


def test_upsert_updates_existing_row_in_sqlite(session: Session) -> None:
    initial_data = {
        "id": "repo/1",
        "repo": "repo",
        "pr_number": 1,
        "state": "open",
        "merged_at": None,
        "changed_files_count": 3,
        "raw_data": {"version": 1},
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    upsert(session, RawPullRequest, initial_data)
    session.commit()

    updated_data = {
        **initial_data,
        "state": "closed",
        "changed_files_count": 5,
        "raw_data": {"version": 2},
    }
    upsert(session, RawPullRequest, updated_data)
    session.commit()

    saved_pr = session.query(RawPullRequest).filter_by(id="repo/1").one()
    assert saved_pr.state == "closed"
    assert saved_pr.changed_files_count == 5
    assert saved_pr.raw_data == {"version": 2}
    assert session.query(RawPullRequest).count() == 1
