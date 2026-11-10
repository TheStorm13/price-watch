"""Enforce one Yandex Market SKU owner without changing stored history."""
from alembic import op
import sqlalchemy as sa

revision = '0022_yandex_sku_ownership'
down_revision = '0021_ozon_sku_ownership'
branch_labels = None
depends_on = None


def upgrade():
    duplicates = op.get_bind().execute(sa.text("""
        SELECT external_id, array_agg(card_id ORDER BY card_id)
        FROM card_variants WHERE marketplace='yandex-market'
        GROUP BY external_id HAVING count(*)>1
    """)).all()
    if duplicates:
        raise RuntimeError(f'Повторное владение SKU Маркета; устраните конфликт до миграции: {duplicates}')
    op.create_index('yandex_sku_unique', 'card_variants', ['external_id'], unique=True,
                    postgresql_where=sa.text("marketplace='yandex-market'"))


def downgrade():
    raise RuntimeError('Forward-only: SKU ownership must remain enforced')
