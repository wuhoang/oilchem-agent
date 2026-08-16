"""Add experiment review fields.

Revision ID: 005
Revises: 004
Create Date: 2026-08-15 00:00:00.000000

Changes:
  - experiments: add reviewed_by (String, nullable)
  - experiments: add reviewed_by_id (String, nullable)
  - experiments: add reviewed_at (DateTime, nullable)
  - experiments: add review_comment (Text, nullable)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("experiments", sa.Column("reviewed_by", sa.String(64), nullable=True))
    op.add_column("experiments", sa.Column("reviewed_by_id", sa.String(32), nullable=True))
    op.add_column("experiments", sa.Column("reviewed_at", sa.DateTime(), nullable=True))
    op.add_column("experiments", sa.Column("review_comment", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("experiments", "review_comment")
    op.drop_column("experiments", "reviewed_at")
    op.drop_column("experiments", "reviewed_by_id")
    op.drop_column("experiments", "reviewed_by")
