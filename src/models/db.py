from datetime import datetime, timezone
from typing import Any, List, Optional

from sqlalchemy import JSON, Boolean, DateTime, Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class RawPullRequest(Base):
    __tablename__ = "raw_pull_requests"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    repo: Mapped[str] = mapped_column(String, index=True)
    pr_number: Mapped[int] = mapped_column(Integer)
    state: Mapped[str] = mapped_column(String)
    merged_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    changed_files_count: Mapped[int] = mapped_column(Integer)
    raw_data: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc)
    )


class RawReviewComment(Base):
    __tablename__ = "raw_review_comments"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    repo: Mapped[str] = mapped_column(String, index=True)
    pr_number: Mapped[int] = mapped_column(Integer)
    comment_id: Mapped[str] = mapped_column(String)
    path: Mapped[str] = mapped_column(String)
    diff_hunk: Mapped[str] = mapped_column(String)
    body: Mapped[str] = mapped_column(String)
    raw_data: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))


class ReviewItem(Base):
    __tablename__ = "review_items"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    repo: Mapped[str] = mapped_column(String, index=True)
    pr_number: Mapped[int] = mapped_column(Integer)
    # review_comment | review_summary | issue_comment
    source_type: Mapped[str] = mapped_column(String)
    source_id: Mapped[str] = mapped_column(String)
    file_path: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    language: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    framework_tags: Mapped[List[str]] = mapped_column(JSON, default=list)
    code_context_before: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    code_context_after: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    diff_hunk: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    comment_text: Mapped[str] = mapped_column(String)
    comment_thread_context: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    review_state: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    author_redacted: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    fix_correlation: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    # accepted | unchanged | superseded | unknown
    merged_outcome: Mapped[Optional[str]] = mapped_column(String, nullable=True)
