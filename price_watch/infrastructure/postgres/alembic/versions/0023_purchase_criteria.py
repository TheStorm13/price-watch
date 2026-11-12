"""Personal purchase settings and variant targets, preserving price history."""
from uuid import uuid4
from alembic import op
import sqlalchemy as sa

revision = '0023_purchase_criteria'
down_revision = '0022_yandex_sku_ownership'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('card_variants', sa.Column('target_price', sa.Numeric(14, 2), nullable=True))
    op.create_check_constraint('variant_target_positive', 'card_variants', 'target_price > 0')
    settings = op.create_table('purchase_settings',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('instance_id', sa.Text, nullable=False),
        sa.Column('small_range_tolerance', sa.Numeric(14, 2)),
        sa.Column('historical_savings_share', sa.Numeric(5, 2)),
        sa.Column('target_notifications_enabled', sa.Boolean, nullable=False, server_default=sa.false()),
        sa.CheckConstraint('id = 1', name='purchase_settings_singleton'),
        sa.CheckConstraint('small_range_tolerance >= 0', name='purchase_tolerance_nonnegative'),
        sa.CheckConstraint('historical_savings_share > 0 AND historical_savings_share <= 100', name='purchase_share_range'))
    op.bulk_insert(settings, [dict(id=1, instance_id=str(uuid4()), target_notifications_enabled=False)])


def downgrade():
    raise RuntimeError('Forward-only: preserve user purchase conditions')
