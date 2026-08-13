"""Add device_telemetry_history table.

Revision ID: 002
Revises: 001
Create Date: 2026-08-10 00:00:00.000000

Creates:
  - device_telemetry_history
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the device_telemetry_history table."""
    op.create_table(
        "device_telemetry_history",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("device_id", sa.String(length=64), nullable=False),
        sa.Column("metric_name", sa.String(length=64), nullable=False),
        sa.Column("metric_value", sa.Float(), nullable=False),
        sa.Column("unit", sa.String(length=32), nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_device_telemetry_history_device_id",
        "device_telemetry_history",
        ["device_id"],
    )
    op.create_index(
        "ix_device_telemetry_history_timestamp",
        "device_telemetry_history",
        ["timestamp"],
    )


def downgrade() -> None:
    """Drop the device_telemetry_history table."""
    op.drop_index(
        "ix_device_telemetry_history_timestamp",
        table_name="device_telemetry_history",
    )
    op.drop_index(
        "ix_device_telemetry_history_device_id",
        table_name="device_telemetry_history",
    )
    op.drop_table("device_telemetry_history")
