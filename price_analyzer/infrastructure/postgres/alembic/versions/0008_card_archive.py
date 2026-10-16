"""Keep archived cards in collection while excluding them from deals.

Revision ID: 0008_card_archive
Revises: 0007_unavailable_without_price
"""

from alembic import op
import sqlalchemy as sa


revision = "0008_card_archive"
down_revision = "0007_unavailable_without_price"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "marketplace_cards",
        sa.Column("is_archived", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("marketplace_cards", "is_archived")
