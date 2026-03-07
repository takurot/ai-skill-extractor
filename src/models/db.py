from datetime import datetime, timezone
from typing import Any, List, Optional

from sqlalchemy import JSON, Boolean, DateTime, Float, Integer, String
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
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
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
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )


class RawIssueComment(Base):
    __tablename__ = "raw_issue_comments"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    repo: Mapped[str] = mapped_column(String, index=True)
    pr_number: Mapped[int] = mapped_column(Integer)
    comment_id: Mapped[str] = mapped_column(String)
    body: Mapped[str] = mapped_column(String)
    raw_data: Mapped[dict[str, Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )


class RawReview(Base):
    __tablename__ = "raw_reviews"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    repo: Mapped[str] = mapped_column(String, index=True)
    pr_number: Mapped[int] = mapped_column(Integer)
    review_id: Mapped[str] = mapped_column(String)
    state: Mapped[str] = mapped_column(String)
    body: Mapped[str] = mapped_column(String)
    raw_data: Mapped[dict[str, Any]] = mapped_column(JSON)
    submitted_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )


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
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )

    # Semantic Analysis fields
    category: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    actionable: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    evidence_based: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    generalizability: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    quality_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    fix_correlation: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    # accepted | unchanged | superseded | unknown
    merged_outcome: Mapped[Optional[str]] = mapped_column(String, nullable=True)


class SkillCandidate(Base):
    __tablename__ = "skill_candidates"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    source_review_item_ids: Mapped[List[str]] = mapped_column(JSON, default=list)
    canonical_name: Mapped[str] = mapped_column(String)
    category: Mapped[str] = mapped_column(String)
    description_draft: Mapped[str] = mapped_column(String)
    engineering_principle: Mapped[str] = mapped_column(String)
    review_prompt_draft: Mapped[str] = mapped_column(String)
    detection_hint_draft: Mapped[str] = mapped_column(String)
    applicability_scope: Mapped[str] = mapped_column(String)
    languages: Mapped[List[str]] = mapped_column(JSON, default=list)
    frameworks: Mapped[List[str]] = mapped_column(JSON, default=list)
    confidence: Mapped[float] = mapped_column(Float)
    evidence_count: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String, default="proposed")
