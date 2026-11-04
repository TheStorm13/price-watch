"""Serialize Ozon membership writers before taking run/card row locks."""
from sqlalchemy import select, text

from .models import CardVariantRecord, MarketplaceCardRecord

# Shared by add, collection and import. Must precede all run/card row locks.
OZON_MEMBERSHIP_LOCK = text('SELECT pg_advisory_xact_lock(578612393)')
MAX_OZON_VARIANTS = 500


async def ozon_owner(session, external_id):
    return await session.scalar(select(CardVariantRecord.card_id)
        .join(MarketplaceCardRecord, MarketplaceCardRecord.id == CardVariantRecord.card_id)
        .where(MarketplaceCardRecord.marketplace == 'ozon', CardVariantRecord.external_id == external_id))


def ownership_conflict(external_id, owner, card_id):
    return f'Ozon SKU {external_id}: конфликт карточек {card_id} и {owner}; вариант уже принадлежит карточке {owner}'
