"""Keep only the first and last observation of each price plateau.

Revision ID: 0004_compact_price_plateaus
Revises: 0003_run_targets_errors
"""

from alembic import op


revision = "0004_compact_price_plateaus"
down_revision = "0003_run_targets_errors"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # One ordered pass over all history. Price and availability form a plateau;
    # id resolves equal observation timestamps deterministically.
    op.execute("""
        WITH transitions AS (
            SELECT id, card_id, observed_at,
                CASE WHEN price IS DISTINCT FROM lag(price) OVER timeline
                       OR availability IS DISTINCT FROM lag(availability) OVER timeline
                     THEN 1 ELSE 0 END AS starts_plateau
            FROM price_history
            WINDOW timeline AS (PARTITION BY card_id ORDER BY observed_at, id)
        ), plateaus AS (
            SELECT id, card_id, observed_at,
                sum(starts_plateau) OVER (
                    PARTITION BY card_id ORDER BY observed_at, id
                    ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
                ) AS plateau_id
            FROM transitions
        ), numbered AS (
            SELECT id,
                row_number() OVER (
                    PARTITION BY card_id, plateau_id ORDER BY observed_at, id
                ) AS from_start,
                row_number() OVER (
                    PARTITION BY card_id, plateau_id ORDER BY observed_at DESC, id DESC
                ) AS from_end
            FROM plateaus
        )
        DELETE FROM price_history AS history USING numbered
        WHERE history.id = numbered.id
          AND numbered.from_start > 1 AND numbered.from_end > 1
    """)


def downgrade() -> None:
    # Deleted observations cannot be reconstructed. Schema is unchanged.
    pass
