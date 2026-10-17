"""Name the deal preference independently from collection tracking.

Revision ID: 0013_deals_enabled
Revises: 0012_product_tags
"""

from alembic import op
import sqlalchemy as sa


revision = "0013_deals_enabled"
down_revision = "0012_product_tags"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index("marketplace_cards_active_idx", table_name="marketplace_cards")
    op.alter_column("marketplace_cards", "is_active", new_column_name="deals_enabled",
                    existing_type=sa.Boolean(), existing_nullable=False,
                    existing_server_default=sa.text("true"))
    op.create_index("marketplace_cards_deals_enabled_idx", "marketplace_cards",
                    ["marketplace", "id"], postgresql_where=sa.text("deals_enabled = true"))


def downgrade() -> None:
    op.drop_index("marketplace_cards_deals_enabled_idx", table_name="marketplace_cards")
    op.alter_column("marketplace_cards", "deals_enabled", new_column_name="is_active",
                    existing_type=sa.Boolean(), existing_nullable=False,
                    existing_server_default=sa.text("true"))
    op.create_index("marketplace_cards_active_idx", "marketplace_cards",
                    ["marketplace", "id"], postgresql_where=sa.text("is_active = true"))
