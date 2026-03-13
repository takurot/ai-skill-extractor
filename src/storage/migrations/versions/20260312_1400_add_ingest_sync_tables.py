"""
Add ingest sync state and request cache tables.

Revision ID: 20260312_1400
Revises: 20260309_2205
Create Date: 2026-03-12 14:00:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "20260312_1400"
down_revision = "20260309_2205"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    table_names = set(inspector.get_table_names())

    if "repo_sync_states" not in table_names:
        op.create_table(
            "repo_sync_states",
            sa.Column("repo", sa.String(), nullable=False),
            sa.Column("last_synced_at", sa.DateTime(), nullable=True),
            sa.Column("latest_pr_updated_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("repo"),
        )

    if "request_cache_entries" not in table_names:
        op.create_table(
            "request_cache_entries",
            sa.Column("key", sa.String(), nullable=False),
            sa.Column("etag", sa.String(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("key"),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    table_names = set(inspector.get_table_names())

    if "request_cache_entries" in table_names:
        op.drop_table("request_cache_entries")
    if "repo_sync_states" in table_names:
        op.drop_table("repo_sync_states")
