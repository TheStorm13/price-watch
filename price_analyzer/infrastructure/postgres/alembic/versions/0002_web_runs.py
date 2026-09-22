"""Add durable web collection queue state.

Revision ID: 0002_web_runs
Revises: 0001_initial
"""

from alembic import op
import sqlalchemy as sa


revision = "0002_web_runs"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index("collection_runs_running_idx", table_name="collection_runs")
    op.drop_constraint("collection_runs_status_check", "collection_runs", type_="check")
    op.alter_column("collection_runs", "status", type_=sa.String(32), server_default="queued")
    op.create_check_constraint(
        "collection_runs_status_check",
        "collection_runs",
        "status in ('queued', 'running', 'waiting_for_user', 'completed', 'completed_with_errors', 'failed')",
    )
    op.add_column("collection_runs", sa.Column("requested_card_id", sa.BigInteger()))
    op.add_column("collection_runs", sa.Column("current_card_id", sa.BigInteger()))
    op.add_column("collection_runs", sa.Column("current_marketplace", sa.Text()))
    op.add_column("collection_runs", sa.Column("current_external_id", sa.Text()))
    op.add_column("collection_runs", sa.Column("challenge_type", sa.String(64)))
    op.add_column("collection_runs", sa.Column("challenge_message", sa.Text()))
    op.add_column("collection_runs", sa.Column("worker_id", sa.String(128)))
    op.add_column("collection_runs", sa.Column("heartbeat_at", sa.DateTime(timezone=True)))
    op.create_foreign_key(
        "collection_runs_requested_card_id_fkey",
        "collection_runs",
        "marketplace_cards",
        ["requested_card_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "collection_runs_current_card_id_fkey",
        "collection_runs",
        "marketplace_cards",
        ["current_card_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "collection_runs_queue_idx",
        "collection_runs",
        ["started_at"],
        postgresql_where=sa.text("status = 'queued'"),
    )
    op.create_index("collection_runs_requested_card_idx", "collection_runs", ["requested_card_id"])
    op.create_index("collection_runs_current_card_idx", "collection_runs", ["current_card_id"])


def downgrade() -> None:
    op.drop_index("collection_runs_current_card_idx", table_name="collection_runs")
    op.drop_index("collection_runs_requested_card_idx", table_name="collection_runs")
    op.drop_index("collection_runs_queue_idx", table_name="collection_runs")
    op.drop_constraint("collection_runs_current_card_id_fkey", "collection_runs", type_="foreignkey")
    op.drop_constraint("collection_runs_requested_card_id_fkey", "collection_runs", type_="foreignkey")
    for column in (
        "heartbeat_at", "worker_id", "challenge_message", "challenge_type",
        "current_external_id", "current_marketplace", "current_card_id", "requested_card_id",
    ):
        op.drop_column("collection_runs", column)
    op.drop_constraint("collection_runs_status_check", "collection_runs", type_="check")
    op.alter_column("collection_runs", "status", type_=sa.Text(), server_default="running")
    op.create_check_constraint(
        "collection_runs_status_check",
        "collection_runs",
        "status in ('running', 'completed', 'completed_with_errors', 'failed')",
    )
    op.create_index(
        "collection_runs_running_idx",
        "collection_runs",
        ["started_at"],
        postgresql_where=sa.text("status = 'running'"),
    )
