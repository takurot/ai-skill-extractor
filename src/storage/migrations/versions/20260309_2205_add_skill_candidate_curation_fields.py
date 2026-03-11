"""
Add curation tracking columns to skill_candidates.

Revision ID: 20260309_2205
Revises:
Create Date: 2026-03-09 22:05:00
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "20260309_2205"
down_revision = "20260309_2100"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if "skill_candidates" not in inspector.get_table_names():
        return

    existing_columns = {column["name"] for column in inspector.get_columns("skill_candidates")}
    if "merged_into_id" not in existing_columns:
        op.add_column("skill_candidates", sa.Column("merged_into_id", sa.String(), nullable=True))
    if "rejection_reason" not in existing_columns:
        op.add_column("skill_candidates", sa.Column("rejection_reason", sa.String(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if "skill_candidates" not in inspector.get_table_names():
        return

    existing_columns = {column["name"] for column in inspector.get_columns("skill_candidates")}
    if "rejection_reason" in existing_columns:
        op.drop_column("skill_candidates", "rejection_reason")
    if "merged_into_id" in existing_columns:
        op.drop_column("skill_candidates", "merged_into_id")
