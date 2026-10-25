"""Link retry runs to their source run.

Revision ID: 0005_retry_runs
Revises: 0004_compact_price_plateaus
"""

from alembic import op
import sqlalchemy as sa


revision = "0005_retry_runs"
down_revision = "0004_compact_price_plateaus"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("collection_runs", sa.Column("retry_of_run_id", sa.BigInteger(), nullable=True))
    op.create_foreign_key("collection_runs_retry_of_run_fk", "collection_runs", "collection_runs",
                          ["retry_of_run_id"], ["id"], ondelete="SET NULL")
    op.create_index("collection_runs_retry_of_unique", "collection_runs", ["retry_of_run_id"],
                    unique=True, postgresql_where=sa.text("retry_of_run_id is not null"))


def downgrade() -> None:
    op.drop_index("collection_runs_retry_of_unique", table_name="collection_runs")
    op.drop_constraint("collection_runs_retry_of_run_fk", "collection_runs", type_="foreignkey")
    op.drop_column("collection_runs", "retry_of_run_id")
