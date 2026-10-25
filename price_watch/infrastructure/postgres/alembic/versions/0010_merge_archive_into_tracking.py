"""Use paused tracking as the only archive state.

Revision ID: 0010_merge_archive_into_tracking
Revises: 0009_card_image
"""

from alembic import op
import sqlalchemy as sa


revision = "0010_merge_archive_into_tracking"
down_revision = "0009_card_image"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        UPDATE marketplace_cards
        SET is_active = false, updated_at = now()
        WHERE is_archived = true AND is_active = true
    """)
    op.drop_column("marketplace_cards", "is_archived")


def downgrade() -> None:
    op.add_column("marketplace_cards", sa.Column(
        "is_archived", sa.Boolean(), server_default=sa.text("false"), nullable=False,
    ))
