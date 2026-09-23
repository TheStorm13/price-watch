"""Freeze queued targets and retain collection errors.

Revision ID: 0003_run_targets_errors
Revises: 0002_web_runs
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0003_run_targets_errors"
down_revision = "0002_web_runs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("collection_runs", sa.Column("target_card_ids", postgresql.ARRAY(sa.BigInteger())))
    op.add_column(
        "collection_runs",
        sa.Column("errors", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
    )
    op.execute("""
        UPDATE collection_runs AS runs
        SET target_card_ids = ARRAY(
            SELECT cards.id FROM marketplace_cards AS cards
            WHERE cards.is_active = true
              AND (runs.requested_card_id IS NULL OR cards.id = runs.requested_card_id)
            ORDER BY cards.marketplace, cards.id
        )
        WHERE runs.status = 'queued'
    """)
    op.execute("UPDATE collection_runs SET total_count = cardinality(target_card_ids) WHERE status = 'queued'")
    op.execute("""
        UPDATE collection_runs SET heartbeat_at = now()
        WHERE status IN ('running', 'waiting_for_user')
          AND worker_id IS NOT NULL AND heartbeat_at IS NULL
    """)


def downgrade() -> None:
    op.drop_column("collection_runs", "errors")
    op.drop_column("collection_runs", "target_card_ids")
