"""Add persistent product groups.

Revision ID: 0011_product_groups
Revises: 0010_merge_archive_into_tracking
"""

from alembic import op
import sqlalchemy as sa

revision = "0011_product_groups"
down_revision = "0010_merge_archive_into_tracking"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "product_groups",
        sa.Column("id", sa.BigInteger(), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("btrim(name) <> ''", name="product_groups_name_not_blank"),
    )
    op.add_column("marketplace_cards", sa.Column("group_id", sa.BigInteger(), sa.ForeignKey("product_groups.id", ondelete="SET NULL"), nullable=True))
    op.create_index("ix_marketplace_cards_group_id", "marketplace_cards", ["group_id"])


def downgrade() -> None:
    op.drop_index("ix_marketplace_cards_group_id", table_name="marketplace_cards")
    op.drop_column("marketplace_cards", "group_id")
    op.drop_table("product_groups")
