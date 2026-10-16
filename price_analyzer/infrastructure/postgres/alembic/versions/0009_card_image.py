"""Store the primary product image on each card.

Revision ID: 0009_card_image
Revises: 0008_card_archive
"""

from alembic import op
import sqlalchemy as sa


revision = "0009_card_image"
down_revision = "0008_card_archive"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("marketplace_cards", sa.Column("image_url", sa.Text(), nullable=True))
    op.execute("""
        UPDATE marketplace_cards AS card
        SET image_url = latest.snapshot->>'image_url'
        FROM (
            SELECT DISTINCT ON (card_id) card_id, snapshot
            FROM price_history
            WHERE snapshot ? 'image_url' AND snapshot->>'image_url' IS NOT NULL
            ORDER BY card_id, observed_at DESC, id DESC
        ) AS latest
        WHERE card.id = latest.card_id
    """)


def downgrade() -> None:
    op.drop_column("marketplace_cards", "image_url")
