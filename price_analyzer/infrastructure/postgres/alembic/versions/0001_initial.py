"""Initial price analyzer schema.

Revision ID: 0001_initial
Revises: None
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "marketplace_cards",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column("marketplace", sa.Text(), nullable=False),
        sa.Column("external_id", sa.Text(), nullable=False),
        sa.Column("title", sa.Text()),
        sa.Column("url", sa.Text()),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("btrim(marketplace) <> ''", name="marketplace_cards_marketplace_not_blank"),
        sa.CheckConstraint("btrim(external_id) <> ''", name="marketplace_cards_external_id_not_blank"),
        sa.UniqueConstraint("marketplace", "external_id", name="marketplace_cards_marketplace_external_unique"),
    )
    op.create_table(
        "collection_runs",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column("status", sa.Text(), server_default="running", nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("total_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("success_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("failure_count", sa.Integer(), server_default="0", nullable=False),
        sa.CheckConstraint(
            "status in ('running', 'completed', 'completed_with_errors', 'failed')",
            name="collection_runs_status_check",
        ),
        sa.CheckConstraint(
            "total_count >= 0 and success_count >= 0 and failure_count >= 0 "
            "and success_count + failure_count <= total_count",
            name="collection_runs_counts_check",
        ),
    )
    op.create_table(
        "price_history",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column("card_id", sa.BigInteger(), sa.ForeignKey("marketplace_cards.id", ondelete="CASCADE"), nullable=False),
        sa.Column("collection_run_id", sa.BigInteger(), sa.ForeignKey("collection_runs.id", ondelete="SET NULL")),
        sa.Column("price", sa.Numeric(14, 2)),
        sa.Column("availability", sa.Text(), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.CheckConstraint("price is null or price >= 0", name="price_history_price_check"),
        sa.CheckConstraint("availability in ('in_stock', 'out_of_stock', 'unknown')", name="price_history_availability_check"),
    )
    op.create_index(
        "marketplace_cards_active_idx",
        "marketplace_cards",
        ["marketplace", "id"],
        postgresql_where=sa.text("is_active = true"),
    )
    op.create_index(
        "collection_runs_running_idx",
        "collection_runs",
        ["started_at"],
        postgresql_where=sa.text("status = 'running'"),
    )
    op.create_index(
        "price_history_card_observed_idx",
        "price_history",
        ["card_id", sa.text("observed_at desc")],
        postgresql_include=["price", "availability"],
    )
    op.create_index(
        "price_history_collection_run_idx",
        "price_history",
        ["collection_run_id"],
        postgresql_where=sa.text("collection_run_id is not null"),
    )


def downgrade() -> None:
    op.drop_table("price_history")
    op.drop_table("collection_runs")
    op.drop_table("marketplace_cards")
