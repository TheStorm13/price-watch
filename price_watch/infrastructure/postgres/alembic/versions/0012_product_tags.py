"""Persist tags on cards and product groups.

Revision ID: 0012_product_tags
Revises: 0011_product_groups
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY

revision = "0012_product_tags"
down_revision = "0011_product_groups"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("marketplace_cards", sa.Column("tags", ARRAY(sa.Text()), nullable=False, server_default=sa.text("'{}'::text[]")))
    op.add_column("product_groups", sa.Column("tags", ARRAY(sa.Text()), nullable=False, server_default=sa.text("'{}'::text[]")))
    op.create_check_constraint("marketplace_cards_tags_limit", "marketplace_cards", "cardinality(tags) <= 2")


def downgrade() -> None:
    op.drop_constraint("marketplace_cards_tags_limit", "marketplace_cards", type_="check")
    op.drop_column("product_groups", "tags")
    op.drop_column("marketplace_cards", "tags")
