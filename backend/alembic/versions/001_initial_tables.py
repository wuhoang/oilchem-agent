"""Initial schema — all base tables.

Revision ID: 001
Revises:
Create Date: 2026-08-08 00:00:00.000000

Creates:
  - users
  - sessions
  - messages
  - tool_audits
  - knowledge
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create all initial tables."""

    # ---- users ----
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("username", sa.String(length=64), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=32), server_default="user", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
        sa.UniqueConstraint("username"),
    )
    op.create_index("ix_users_username", "users", ["username"])

    # ---- sessions ----
    op.create_table(
        "sessions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("session_id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), server_default="", nullable=False),
        sa.Column("summary", sa.Text(), server_default="", nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_id"),
    )
    op.create_index("ix_sessions_session_id", "sessions", ["session_id"])
    op.create_index("ix_sessions_user_id", "sessions", ["user_id"])

    # ---- messages ----
    op.create_table(
        "messages",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("tool_name", sa.String(length=128), nullable=True),
        sa.Column("tool_args", sa.Text(), nullable=True),
        sa.Column("tool_result", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_messages_session_id", "messages", ["session_id"])
    op.create_index(
        "ix_messages_session_created", "messages", ["session_id", "created_at"]
    )

    # ---- tool_audits ----
    op.create_table(
        "tool_audits",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tool_name", sa.String(length=128), nullable=False),
        sa.Column("session_id", sa.String(length=64), nullable=True),
        sa.Column("args", sa.Text(), server_default="", nullable=False),
        sa.Column("success", sa.Boolean(), nullable=False),
        sa.Column("result", sa.Text(), server_default="", nullable=False),
        sa.Column("duration_ms", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_tool_audits_tool_name", "tool_audits", ["tool_name"])
    op.create_index("ix_tool_audits_session_id", "tool_audits", ["session_id"])

    # ---- knowledge ----
    op.create_table(
        "knowledge",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("source", sa.String(length=255), server_default="unknown", nullable=False),
        sa.Column("tags", sa.String(length=255), server_default="", nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    """Drop all tables (reverse order)."""
    op.drop_table("knowledge")
    op.drop_table("tool_audits")
    op.drop_table("messages")
    op.drop_table("sessions")
    op.drop_table("users")
