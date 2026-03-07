from datetime import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.models.db import Base, RawPullRequest


# Use in-memory SQLite for testing upsert logic structure
# Note: PostgreSQL specific 'ON CONFLICT' won't work in SQLite,
# but we can verify the model and session usage.
@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    session = session_factory()
    yield session
    session.close()


def test_raw_pr_model(session):
    pr_data = {
        "id": "repo/1",
        "repo": "repo",
        "pr_number": 1,
        "state": "merged",
        "changed_files_count": 5,
        "raw_data": {"test": "data"},
        "created_at": datetime.utcnow(),
    }
    pr = RawPullRequest(**pr_data)
    session.add(pr)
    session.commit()

    saved_pr = session.query(RawPullRequest).filter_by(id="repo/1").first()
    assert saved_pr is not None
    assert saved_pr.state == "merged"
