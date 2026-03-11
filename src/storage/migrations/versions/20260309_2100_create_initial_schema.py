"""
Create the initial database schema.

Revision ID: 20260309_2100
Revises:
Create Date: 2026-03-09 21:00:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "20260309_2100"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    if "raw_pull_requests" not in _table_names():
        op.create_table(
            "raw_pull_requests",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("repo", sa.String(), nullable=False),
            sa.Column("pr_number", sa.Integer(), nullable=False),
            sa.Column("state", sa.String(), nullable=False),
            sa.Column("merged_at", sa.DateTime(), nullable=True),
            sa.Column("changed_files_count", sa.Integer(), nullable=False),
            sa.Column("raw_data", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
    _create_index_if_missing("ix_raw_pull_requests_repo", "raw_pull_requests", ["repo"])

    if "raw_review_comments" not in _table_names():
        op.create_table(
            "raw_review_comments",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("repo", sa.String(), nullable=False),
            sa.Column("pr_number", sa.Integer(), nullable=False),
            sa.Column("comment_id", sa.String(), nullable=False),
            sa.Column("path", sa.String(), nullable=False),
            sa.Column("diff_hunk", sa.String(), nullable=False),
            sa.Column("body", sa.String(), nullable=False),
            sa.Column("raw_data", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
    _create_index_if_missing("ix_raw_review_comments_repo", "raw_review_comments", ["repo"])

    if "raw_issue_comments" not in _table_names():
        op.create_table(
            "raw_issue_comments",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("repo", sa.String(), nullable=False),
            sa.Column("pr_number", sa.Integer(), nullable=False),
            sa.Column("comment_id", sa.String(), nullable=False),
            sa.Column("body", sa.String(), nullable=False),
            sa.Column("raw_data", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
    _create_index_if_missing("ix_raw_issue_comments_repo", "raw_issue_comments", ["repo"])

    if "raw_reviews" not in _table_names():
        op.create_table(
            "raw_reviews",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("repo", sa.String(), nullable=False),
            sa.Column("pr_number", sa.Integer(), nullable=False),
            sa.Column("review_id", sa.String(), nullable=False),
            sa.Column("state", sa.String(), nullable=False),
            sa.Column("body", sa.String(), nullable=False),
            sa.Column("raw_data", sa.JSON(), nullable=False),
            sa.Column("submitted_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
    _create_index_if_missing("ix_raw_reviews_repo", "raw_reviews", ["repo"])

    if "review_items" not in _table_names():
        op.create_table(
            "review_items",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("repo", sa.String(), nullable=False),
            sa.Column("pr_number", sa.Integer(), nullable=False),
            sa.Column("source_type", sa.String(), nullable=False),
            sa.Column("source_id", sa.String(), nullable=False),
            sa.Column("file_path", sa.String(), nullable=True),
            sa.Column("language", sa.String(), nullable=True),
            sa.Column("framework_tags", sa.JSON(), nullable=False),
            sa.Column("code_context_before", sa.String(), nullable=True),
            sa.Column("code_context_after", sa.String(), nullable=True),
            sa.Column("diff_hunk", sa.String(), nullable=True),
            sa.Column("comment_text", sa.String(), nullable=False),
            sa.Column("comment_thread_context", sa.String(), nullable=True),
            sa.Column("review_state", sa.String(), nullable=True),
            sa.Column("author_redacted", sa.String(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("category", sa.String(), nullable=True),
            sa.Column("actionable", sa.Boolean(), nullable=True),
            sa.Column("evidence_based", sa.Boolean(), nullable=True),
            sa.Column("generalizability", sa.String(), nullable=True),
            sa.Column("quality_score", sa.Float(), nullable=True),
            sa.Column("fix_correlation", sa.Boolean(), nullable=True),
            sa.Column("merged_outcome", sa.String(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )
    _create_index_if_missing("ix_review_items_repo", "review_items", ["repo"])

    if "skill_candidates" not in _table_names():
        op.create_table(
            "skill_candidates",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("source_review_item_ids", sa.JSON(), nullable=False),
            sa.Column("canonical_name", sa.String(), nullable=False),
            sa.Column("category", sa.String(), nullable=False),
            sa.Column("description_draft", sa.String(), nullable=False),
            sa.Column("engineering_principle", sa.String(), nullable=False),
            sa.Column("review_prompt_draft", sa.String(), nullable=False),
            sa.Column("detection_hint_draft", sa.String(), nullable=False),
            sa.Column("applicability_scope", sa.String(), nullable=False),
            sa.Column("languages", sa.JSON(), nullable=False),
            sa.Column("frameworks", sa.JSON(), nullable=False),
            sa.Column("confidence", sa.Float(), nullable=False),
            sa.Column("evidence_count", sa.Integer(), nullable=False),
            sa.Column("status", sa.String(), nullable=False),
            sa.Column("embedding", sa.JSON(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )


def downgrade() -> None:
    for table_name in [
        "skill_candidates",
        "review_items",
        "raw_reviews",
        "raw_issue_comments",
        "raw_review_comments",
        "raw_pull_requests",
    ]:
        if table_name in _table_names():
            op.drop_table(table_name)


def _table_names() -> set[str]:
    return set(inspect(op.get_bind()).get_table_names())


def _create_index_if_missing(index_name: str, table_name: str, columns: list[str]) -> None:
    if table_name not in _table_names():
        return

    inspector = inspect(op.get_bind())
    existing_indexes = {index["name"] for index in inspector.get_indexes(table_name)}
    if index_name not in existing_indexes:
        op.create_index(index_name, table_name, columns)
