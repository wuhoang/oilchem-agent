"""Add experiment-domain tables (M1).

Revision ID: 003
Revises: 002
Create Date: 2026-08-13 00:00:00.000000

Creates:
  - experimenters
  - protocols
  - protocol_steps
  - materials
  - experiment_steps
  - measurements

Alters:
  - experiments: add operator_id / protocol_id / sample_code
  - samples: add material_id
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 001 迁移未建 experiments/samples/devices（历史上由 create_all 补建）。
    # fresh 部署时 ALTER 会找不到表，先幂等补建这三张基础表。
    bind = op.get_bind()
    from sqlalchemy import inspect as sa_inspect

    inspector = sa_inspect(bind)
    existing = set(inspector.get_table_names())

    if "experiments" not in existing:
        op.create_table(
            "experiments",
            sa.Column("id", sa.String(32), primary_key=True),
            sa.Column("name", sa.String(255), nullable=False),
            sa.Column("operator", sa.String(64), nullable=False, server_default=""),
            sa.Column("status", sa.String(32), nullable=False, server_default="待开始"),
            sa.Column("created_at", sa.String(32), nullable=False, server_default=""),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
        )
    if "samples" not in existing:
        op.create_table(
            "samples",
            sa.Column("code", sa.String(32), primary_key=True),
            sa.Column("name", sa.String(255), nullable=False),
            sa.Column("batch", sa.String(64), nullable=False, server_default=""),
            sa.Column("location", sa.String(128), nullable=False, server_default=""),
            sa.Column("status", sa.String(32), nullable=False, server_default="在用"),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
        )
    if "devices" not in existing:
        op.create_table(
            "devices",
            sa.Column("id", sa.String(32), primary_key=True),
            sa.Column("name", sa.String(255), nullable=False),
            sa.Column("model", sa.String(128), nullable=False, server_default=""),
            sa.Column("status", sa.String(32), nullable=False, server_default="在线"),
            sa.Column("last_maintain", sa.String(32), nullable=False, server_default=""),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
        )

    # ---- experimenters ----
    op.create_table(
        "experimenters",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("role", sa.String(32), nullable=False, server_default="技术员"),
        sa.Column("department", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )

    # ---- protocols ----
    op.create_table(
        "protocols",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("version", sa.String(16), nullable=False, server_default="v1"),
        sa.Column("status", sa.String(32), nullable=False, server_default="草稿"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )

    # ---- protocol_steps ----
    op.create_table(
        "protocol_steps",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("protocol_id", sa.String(32), nullable=False),
        sa.Column("step_order", sa.Integer(), nullable=False),
        sa.Column("device_id", sa.String(32), nullable=False),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("params", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("timeout_s", sa.Integer(), nullable=False, server_default="60"),
        sa.Column("complete_criteria", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("description", sa.String(255), nullable=True),
    )
    op.create_index("ix_protocol_steps_protocol_id", "protocol_steps", ["protocol_id"])

    # ---- materials ----
    op.create_table(
        "materials",
        sa.Column("id", sa.String(32), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("spec", sa.String(255), nullable=True),
        sa.Column("manufacturer", sa.String(128), nullable=True),
        sa.Column("unit", sa.String(32), nullable=True),
    )

    # ---- experiment_steps ----
    op.create_table(
        "experiment_steps",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("experiment_id", sa.String(32), nullable=False),
        sa.Column("protocol_step_id", sa.Integer(), nullable=True),
        sa.Column("step_order", sa.Integer(), nullable=False),
        sa.Column("device_id", sa.String(32), nullable=False),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("params", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("timeout_s", sa.Integer(), nullable=False, server_default="60"),
        sa.Column("complete_criteria", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("error_message", sa.String(255), nullable=True),
    )
    op.create_index("ix_experiment_steps_experiment_id", "experiment_steps", ["experiment_id"])

    # ---- measurements ----
    op.create_table(
        "measurements",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("experiment_id", sa.String(32), nullable=False),
        sa.Column("experiment_step_id", sa.Integer(), nullable=True),
        sa.Column("metric_name", sa.String(64), nullable=False),
        sa.Column("metric_value", sa.Float(), nullable=False),
        sa.Column("unit", sa.String(32), nullable=True),
        sa.Column("timestamp", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_measurements_experiment_id", "measurements", ["experiment_id"])
    op.create_index("ix_measurements_experiment_step_id", "measurements", ["experiment_step_id"])
    op.create_index("ix_measurements_timestamp", "measurements", ["timestamp"])

    # ---- alter experiments ----
    op.add_column("experiments", sa.Column("operator_id", sa.String(32), nullable=True))
    op.add_column("experiments", sa.Column("protocol_id", sa.String(32), nullable=True))
    op.add_column("experiments", sa.Column("sample_code", sa.String(32), nullable=True))
    op.add_column("experiments", sa.Column("result", sa.Text(), nullable=True))
    op.create_index("ix_experiments_operator_id", "experiments", ["operator_id"])
    op.create_index("ix_experiments_protocol_id", "experiments", ["protocol_id"])
    op.create_index("ix_experiments_sample_code", "experiments", ["sample_code"])

    # ---- experiment_audits ----
    op.create_table(
        "experiment_audits",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("experiment_id", sa.String(32), nullable=False),
        sa.Column("event_type", sa.String(32), nullable=False),
        sa.Column("detail", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_experiment_audits_experiment_id", "experiment_audits", ["experiment_id"])
    op.create_index("ix_experiment_audits_created_at", "experiment_audits", ["created_at"])

    # ---- alter samples ----
    op.add_column("samples", sa.Column("material_id", sa.String(32), nullable=True))
    op.create_index("ix_samples_material_id", "samples", ["material_id"])


def downgrade() -> None:
    op.drop_index("ix_samples_material_id", table_name="samples")
    op.drop_column("samples", "material_id")

    op.drop_index("ix_experiment_audits_created_at", table_name="experiment_audits")
    op.drop_index("ix_experiment_audits_experiment_id", table_name="experiment_audits")
    op.drop_table("experiment_audits")

    op.drop_index("ix_experiments_sample_code", table_name="experiments")
    op.drop_index("ix_experiments_protocol_id", table_name="experiments")
    op.drop_index("ix_experiments_operator_id", table_name="experiments")
    op.drop_column("experiments", "result")
    op.drop_column("experiments", "sample_code")
    op.drop_column("experiments", "protocol_id")
    op.drop_column("experiments", "operator_id")

    op.drop_index("ix_measurements_timestamp", table_name="measurements")
    op.drop_index("ix_measurements_experiment_step_id", table_name="measurements")
    op.drop_index("ix_measurements_experiment_id", table_name="measurements")
    op.drop_table("measurements")

    op.drop_index("ix_experiment_steps_experiment_id", table_name="experiment_steps")
    op.drop_table("experiment_steps")

    op.drop_table("materials")
    op.drop_index("ix_protocol_steps_protocol_id", table_name="protocol_steps")
    op.drop_table("protocol_steps")
    op.drop_table("protocols")
    op.drop_table("experimenters")
