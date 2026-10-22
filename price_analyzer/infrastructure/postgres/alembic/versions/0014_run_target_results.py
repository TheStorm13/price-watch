"""Move frozen targets to durable results; preserve uncertainty in old runs."""
from alembic import op
import sqlalchemy as sa

revision = '0014_run_target_results'
down_revision = '0013_deals_enabled'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('collection_runs', sa.Column('targets_complete', sa.Boolean(), nullable=False, server_default=sa.true()))
    op.create_table('collection_run_targets',
        sa.Column('run_id', sa.BigInteger(), sa.ForeignKey('collection_runs.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('card_id', sa.BigInteger(), primary_key=True),
        sa.Column('position', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(16), nullable=False, server_default='pending'),
        sa.CheckConstraint("status in ('pending','succeeded','failed','unknown')", name='run_target_status_check'),
        sa.UniqueConstraint('run_id', 'position', name='run_target_position_unique'))
    op.create_index('run_targets_card_idx', 'collection_run_targets', ['card_id', 'run_id'])
    op.execute("""
        WITH known AS (
            SELECT r.id run_id, x.card_id, x.ord position
            FROM collection_runs r CROSS JOIN LATERAL unnest(r.target_card_ids) WITH ORDINALITY x(card_id,ord)
            UNION ALL SELECT id, requested_card_id, 2147483647 FROM collection_runs WHERE requested_card_id IS NOT NULL
            UNION ALL SELECT r.id,
                CASE WHEN e->>'cardId' ~ '^[0-9]{1,19}$' THEN
                    CASE WHEN (e->>'cardId')::numeric <= 9223372036854775807
                         THEN (e->>'cardId')::bigint END END, 2147483647
            FROM collection_runs r CROSS JOIN LATERAL jsonb_array_elements(r.errors) e
            WHERE jsonb_typeof(e->'cardId') = 'number'
            UNION ALL SELECT collection_run_id, card_id, 2147483647 FROM price_history WHERE collection_run_id IS NOT NULL
        ), unique_targets AS (
            SELECT run_id,card_id,min(position) position FROM known WHERE card_id IS NOT NULL GROUP BY run_id,card_id
        )
        INSERT INTO collection_run_targets(run_id,card_id,position,status)
        SELECT t.run_id,t.card_id,row_number() OVER (PARTITION BY t.run_id ORDER BY t.position,t.card_id)-1,
          CASE WHEN r.status='queued' THEN 'pending'
               WHEN EXISTS (SELECT 1 FROM jsonb_array_elements(r.errors) e WHERE e->>'cardId'=t.card_id::text) THEN 'failed'
               ELSE 'unknown' END
        FROM unique_targets t JOIN collection_runs r ON r.id=t.run_id
    """)
    op.execute("""UPDATE collection_runs r SET targets_complete =
        ((r.target_card_ids IS NOT NULL AND cardinality(r.target_card_ids)=r.total_count)
          OR (r.requested_card_id IS NOT NULL AND r.total_count=1))
        AND (SELECT count(*) FROM collection_run_targets t WHERE t.run_id=r.id)=r.total_count""")
    op.drop_column('collection_runs', 'target_card_ids')


def downgrade():
    raise RuntimeError('Forward-only migration: restore no obsolete execution model; use a corrective upgrade')
