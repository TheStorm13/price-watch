"""Retain cards and history; canonicalize only unambiguous Wildberries size URLs."""
from alembic import op
import sqlalchemy as sa

from marketplace_connector.connectors.wildberries.identity import WildberriesRef
from marketplace_connector.domain.errors import InvalidProductId

revision = '0016_wildberries_size'
down_revision = '0015_aliexpress_sku'
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    # Serialize with run creation, then protect the rows through preflight/update.
    connection.execute(sa.text("SELECT pg_advisory_xact_lock(578612391)"))
    rows = connection.execute(sa.text("SELECT id, external_id, url FROM marketplace_cards WHERE marketplace='wildberries' FOR UPDATE")).all()
    if not rows:
        return
    if connection.scalar(sa.text("SELECT EXISTS (SELECT 1 FROM collection_runs WHERE status IN ('queued','running','waiting_for_user'))")):
        raise RuntimeError('Завершите активный сбор перед переходом Wildberries на размеры')
    planned = []
    identities = set()
    for card_id, external_id, url in rows:
        candidate = external_id
        if external_id.isascii() and external_id.isdigit() and url:
            try:
                ref = WildberriesRef.from_url(url)
            except (InvalidProductId, ValueError):
                pass
            else:
                if ref.nm_id == external_id:
                    candidate = ref.external_id
                    planned.append((card_id, candidate))
        if candidate in identities:
            raise RuntimeError(f'Конфликт Wildberries размер: {candidate}; данные не изменены')
        identities.add(candidate)
    for card_id, external_id in planned:
        connection.execute(sa.text('UPDATE marketplace_cards SET external_id=:external_id WHERE id=:id'),
                           dict(id=card_id, external_id=external_id))


def downgrade():
    raise RuntimeError('Forward-only migration: Size histories must remain distinct')
