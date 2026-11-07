"""Enforce one Ozon SKU owner, including direct SQL writers."""
from alembic import op
import sqlalchemy as sa

revision = '0021_ozon_sku_ownership'
down_revision = '0020_variant_tracking'
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    duplicates = connection.execute(sa.text("""
        SELECT v.external_id, array_agg(v.card_id ORDER BY v.card_id)
        FROM card_variants v JOIN marketplace_cards c ON c.id=v.card_id
        WHERE c.marketplace='ozon' GROUP BY v.external_id HAVING count(*)>1
    """)).all()
    if duplicates:
        raise RuntimeError(f'Повторное владение SKU Ozon; устраните конфликт до миграции: {duplicates}')
    op.add_column('card_variants', sa.Column('marketplace', sa.Text(), nullable=True))
    connection.execute(sa.text('UPDATE card_variants v SET marketplace=c.marketplace FROM marketplace_cards c WHERE c.id=v.card_id'))
    op.alter_column('card_variants', 'marketplace', nullable=False)
    op.create_unique_constraint('marketplace_cards_id_marketplace_unique', 'marketplace_cards', ['id', 'marketplace'])
    op.create_foreign_key('variant_marketplace_owner_fk', 'card_variants', 'marketplace_cards',
                          ['card_id', 'marketplace'], ['id', 'marketplace'], ondelete='CASCADE')
    op.create_index('ozon_sku_unique', 'card_variants', ['external_id'], unique=True,
                    postgresql_where=sa.text("marketplace='ozon'"))
    connection.execute(sa.text('ALTER TABLE price_history ALTER CONSTRAINT history_variant_fk DEFERRABLE INITIALLY IMMEDIATE'))


def downgrade():
    raise RuntimeError('Forward-only: SKU ownership must remain enforced')
