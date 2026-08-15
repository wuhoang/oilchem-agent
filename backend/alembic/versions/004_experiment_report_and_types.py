"""Add experiment report_path + fix created_at type.

Revision ID: 004
Revises: 003
Create Date: 2026-08-14 00:00:00.000000

Changes:
  - experiments: add report_path (String, nullable)
  - experiments: created_at String -> DateTime（存量字符串值置空，演示数据可接受）
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("experiments", sa.Column("report_path", sa.String(255), nullable=True))

    # created_at String -> DateTime（batch 模式重建表，SQLite 安全）
    with op.batch_alter_table("experiments") as batch_op:
        batch_op.alter_column(
            "created_at",
            existing_type=sa.String(32),
            type_=sa.DateTime(),
            nullable=True,
            existing_nullable=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("experiments") as batch_op:
        batch_op.alter_column(
            "created_at",
            existing_type=sa.DateTime(),
            type_=sa.String(32),
            nullable=False,
            existing_nullable=True,
        )
    op.drop_column("experiments", "report_path")
