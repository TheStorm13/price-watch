"""Store no current price for unavailable products.

Revision ID: 0007_unavailable_without_price
Revises: 0006_full_collection_schedule
"""

from alembic import op


revision = "0007_unavailable_without_price"
down_revision = "0006_full_collection_schedule"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("UPDATE price_history SET price = NULL WHERE availability = 'out_of_stock'")
    op.create_check_constraint(
        "price_history_unavailable_price_check", "price_history",
        "availability <> 'out_of_stock' or price is null",
    )


def downgrade() -> None:
    op.drop_constraint("price_history_unavailable_price_check", "price_history", type_="check")
