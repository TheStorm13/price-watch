"""Track which runs reset the automatic full-collection schedule.

Revision ID: 0006_full_collection_schedule
Revises: 0005_retry_runs
"""

from alembic import op
import sqlalchemy as sa


revision = "0006_full_collection_schedule"
down_revision = "0005_retry_runs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("collection_runs", sa.Column(
        "is_full_collection", sa.Boolean(), nullable=False, server_default=sa.true(),
    ))
    op.execute("""
        UPDATE collection_runs SET is_full_collection = false
        WHERE requested_card_id IS NOT NULL OR retry_of_run_id IS NOT NULL
    """)


def downgrade() -> None:
    op.drop_column("collection_runs", "is_full_collection")
