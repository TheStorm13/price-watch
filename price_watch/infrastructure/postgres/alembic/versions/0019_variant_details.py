"""Variant-owned display data; cards project their primary variant."""
from alembic import op
import sqlalchemy as sa

revision = '0019_variant_details'
down_revision = '0018_product_variants'
branch_labels = None
depends_on = None


def upgrade():
    c = op.get_bind()
    c.execute(sa.text('SELECT pg_advisory_xact_lock(578612391)'))
    if c.scalar(sa.text("SELECT EXISTS(SELECT 1 FROM collection_runs WHERE status IN ('queued','running','waiting_for_user'))")):
        raise RuntimeError('Завершите активный сбор перед переносом данных вариантов')
    op.add_column('card_variants', sa.Column('product_title', sa.Text()))
    op.add_column('card_variants', sa.Column('image_url', sa.Text()))
    # The old card fields describe its primary only, never an arbitrary sibling.
    c.execute(sa.text('''
        UPDATE card_variants v SET product_title=c.title, image_url=c.image_url,
            url=coalesce(v.url,c.url)
        FROM marketplace_cards c WHERE c.primary_variant_id=v.id
    '''))
    # Recover only snapshots belonging to this exact identity. History stays intact.
    c.execute(sa.text('''
        WITH own_snapshot AS (
            SELECT h.variant_id,
                (array_agg(h.snapshot->>'title' ORDER BY h.observed_at DESC,h.id DESC)
                    FILTER (WHERE jsonb_typeof(h.snapshot->'title')='string'
                        AND btrim(h.snapshot->>'title')<>''))[1] AS title,
                (array_agg(h.snapshot->>'image_url' ORDER BY h.observed_at DESC,h.id DESC)
                    FILTER (WHERE jsonb_typeof(h.snapshot->'image_url')='string'
                        AND btrim(h.snapshot->>'image_url')<>''))[1] AS image_url
            FROM price_history h JOIN card_variants v ON v.id=h.variant_id
            JOIN marketplace_cards c ON c.id=v.card_id
            WHERE h.snapshot->'ref'->>'external_id'=v.external_id
              AND h.snapshot->'ref'->>'marketplace'=c.marketplace
            GROUP BY h.variant_id
        )
        UPDATE card_variants v SET
            product_title=coalesce(v.product_title,s.title),
            image_url=coalesce(v.image_url,s.image_url)
        FROM own_snapshot s WHERE v.id=s.variant_id
    '''))
    for field in ('title', 'url', 'image_url'):
        op.drop_column('marketplace_cards', field)


def downgrade():
    raise RuntimeError('Forward-only: display data belongs to each variant')
