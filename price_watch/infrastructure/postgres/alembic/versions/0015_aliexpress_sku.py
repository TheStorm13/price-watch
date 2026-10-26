"""Retain cards and history; canonicalize only unambiguous AliExpress SKU URLs."""
from alembic import op
import sqlalchemy as sa

from marketplace_connector.connectors.aliexpress.identity import AliExpressRef
from marketplace_connector.domain.errors import InvalidProductId

revision = '0015_aliexpress_sku'
down_revision = '0014_run_target_results'
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    # Serialize with run creation, then protect the rows through preflight/update.
    connection.execute(sa.text("SELECT pg_advisory_xact_lock(578612391)"))
    rows = connection.execute(sa.text("SELECT id, external_id, url FROM marketplace_cards WHERE marketplace='aliexpress' FOR UPDATE")).all()
    if not rows:
        return
    if connection.scalar(sa.text("SELECT EXISTS (SELECT 1 FROM collection_runs WHERE status IN ('queued','running','waiting_for_user'))")):
        raise RuntimeError('Завершите активный сбор перед переходом AliExpress на SKU')
    planned = []
    identities = set()
    for card_id, external_id, url in rows:
        candidate = external_id
        if external_id.isascii() and external_id.isdigit() and url:
            try:
                ref = AliExpressRef.from_url(url)
            except (InvalidProductId, ValueError):
                pass
            else:
                if ref.product_id == external_id:
                    candidate = ref.external_id
                    planned.append((card_id, candidate))
        if candidate in identities:
            raise RuntimeError(f'Конфликт AliExpress SKU: {candidate}; данные не изменены')
        identities.add(candidate)
    for card_id, external_id in planned:
        connection.execute(sa.text('UPDATE marketplace_cards SET external_id=:external_id WHERE id=:id'),
                           dict(id=card_id, external_id=external_id))


def downgrade():
    raise RuntimeError('Forward-only migration: SKU histories must remain distinct')
