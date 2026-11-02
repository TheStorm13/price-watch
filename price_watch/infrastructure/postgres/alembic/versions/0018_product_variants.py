"""One product card, exact variants, and independent histories; forward only."""
from collections import defaultdict
import json

from alembic import op
import sqlalchemy as sa

revision = '0018_product_variants'
down_revision = '0017_bounded_diagnostics'
branch_labels = None
depends_on = None


def upgrade():
    c = op.get_bind()
    c.execute(sa.text('SELECT pg_advisory_xact_lock(578612391)'))
    if c.scalar(sa.text("SELECT EXISTS(SELECT 1 FROM collection_runs WHERE status IN ('queued','running','waiting_for_user'))")):
        raise RuntimeError('Завершите активный сбор перед переходом на варианты товара')
    rows = c.execute(sa.text('SELECT * FROM marketplace_cards ORDER BY id FOR UPDATE')).mappings().all()
    products = defaultdict(list)
    for row in rows:
        article = row['external_id'].split(':')[0] if row['marketplace'] in ('aliexpress', 'wildberries') else row['external_id']
        products[row['marketplace'], article].append(row)
    for key, members in products.items():
        for field in ('title', 'tags', 'group_id', 'deals_enabled'):
            values = {json.dumps(row[field], ensure_ascii=False, sort_keys=True) for row in members}
            if len(values) > 1:
                raise RuntimeError(f'Конфликт {key}, поле {field}, карточки {[r["id"] for r in members]}; данные не изменены')
    op.create_table('card_variants',
        sa.Column('id', sa.BigInteger(), primary_key=True),
        sa.Column('card_id', sa.BigInteger(), sa.ForeignKey('marketplace_cards.id', ondelete='CASCADE'), nullable=False),
        sa.Column('external_id', sa.Text(), nullable=False),
        sa.Column('title', sa.Text(), nullable=False, server_default=''),
        sa.Column('url', sa.Text()),
        sa.Column('options', sa.dialects.postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column('updated_at', sa.DateTime(timezone=True)),
        sa.UniqueConstraint('card_id', 'external_id', name='card_variants_identity_unique'),
        sa.UniqueConstraint('card_id', 'id', name='card_variants_owner_unique'),
        sa.CheckConstraint("btrim(external_id) <> ''", name='card_variants_identity_not_blank'))
    op.create_index('ix_card_variants_card_id', 'card_variants', ['card_id'])
    op.add_column('marketplace_cards', sa.Column('primary_variant_id', sa.BigInteger()))
    op.add_column('price_history', sa.Column('variant_id', sa.BigInteger()))
    op.add_column('collection_run_targets', sa.Column('variant_id', sa.BigInteger()))
    # Target identities remain readable even after deletion; as before, no target FK.
    op.drop_constraint('collection_run_targets_pkey', 'collection_run_targets', type_='primary')
    for (_, article), members in products.items():
        parent = members[0]['id']
        for row in members:
            c.execute(sa.text('INSERT INTO card_variants(id,card_id,external_id,url,updated_at) VALUES (:id,:parent,:ref,:url,:at)'),
                      dict(id=row['id'], parent=parent, ref=row['external_id'], url=row['url'], at=row['updated_at']))
            c.execute(sa.text('UPDATE price_history SET card_id=:parent, variant_id=:old WHERE card_id=:old'), dict(parent=parent, old=row['id']))
            c.execute(sa.text('UPDATE collection_run_targets SET card_id=:parent, variant_id=:old WHERE card_id=:old AND variant_id IS NULL'), dict(parent=parent, old=row['id']))
            for field in ('requested_card_id', 'current_card_id'):
                c.execute(sa.text(f'UPDATE collection_runs SET {field}=:parent WHERE {field}=:old'), dict(parent=parent, old=row['id']))
        for row in members[1:]:
            c.execute(sa.text('DELETE FROM marketplace_cards WHERE id=:id'), dict(id=row['id']))
        c.execute(sa.text('UPDATE marketplace_cards SET external_id=:article, primary_variant_id=:primary, created_at=:created, updated_at=:updated WHERE id=:id'),
                  dict(article=article, primary=parent, id=parent, created=min(r['created_at'] for r in members), updated=max(r['updated_at'] for r in members)))
    # Historical targets may refer to deleted cards: their original ID remains a variant key.
    c.execute(sa.text('UPDATE collection_run_targets SET variant_id=card_id WHERE variant_id IS NULL'))
    c.execute(sa.text("SELECT setval(pg_get_serial_sequence('card_variants','id'), greatest(coalesce((SELECT max(id) FROM card_variants),0),1), EXISTS(SELECT 1 FROM card_variants))"))
    op.alter_column('price_history', 'variant_id', nullable=False)
    op.alter_column('collection_run_targets', 'variant_id', nullable=False)
    op.create_primary_key('collection_run_targets_pkey', 'collection_run_targets', ['run_id', 'variant_id'])
    op.create_foreign_key('history_variant_fk', 'price_history', 'card_variants', ['card_id', 'variant_id'], ['card_id', 'id'], ondelete='CASCADE')
    op.create_foreign_key('card_primary_variant_owner_fk', 'marketplace_cards', 'card_variants', ['id', 'primary_variant_id'], ['card_id', 'id'], deferrable=True, initially='DEFERRED')
    op.create_index('history_variant_observed_idx', 'price_history', ['variant_id', sa.text('observed_at DESC')])


def downgrade():
    raise RuntimeError('Forward-only: independent SKU histories must remain distinct')
