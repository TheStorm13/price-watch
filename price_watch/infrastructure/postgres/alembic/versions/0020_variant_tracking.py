"""Default-off variant preferences and initial discovery purpose; no data deletion."""
from alembic import op
import sqlalchemy as sa

revision = '0020_variant_tracking'
down_revision = '0019_variant_details'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('card_variants', sa.Column('tracking_enabled', sa.Boolean(), nullable=False, server_default=sa.false()))
    # Preserve queued/active targets exactly; new ordinary runs no longer expand.
    op.add_column('collection_runs', sa.Column('discover_all', sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade():
    raise RuntimeError('Forward-only: tracking preferences must be retained')
