"""Read-only deal projections."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import List

from sqlalchemy import select, text

from ...domain.models import CardOverview, Deal
from .models import MarketplaceCardRecord
from .repository_common import _card


_DEALS_SQL = text("""
    WITH latest AS (
        SELECT DISTINCT ON (card_id) card_id, id, price, availability, observed_at, collection_run_id
        FROM price_history ORDER BY card_id, observed_at DESC, id DESC
    ), daily AS (
        SELECT h.card_id, date_trunc('day', h.observed_at) AS day,
               avg(h.price) AS daily_average
        FROM price_history h JOIN latest l ON l.card_id = h.card_id
        WHERE h.id <> l.id AND h.availability = 'in_stock' AND h.price IS NOT NULL
        GROUP BY h.card_id, date_trunc('day', h.observed_at)
    )
    SELECT c.id, l.price, l.availability, l.observed_at, l.collection_run_id,
           avg(d.daily_average) AS average_price, count(d.day) AS baseline_days
    FROM marketplace_cards c
    JOIN latest l ON l.card_id = c.id
    JOIN daily d ON d.card_id = c.id
    WHERE c.is_active = true AND c.created_at <= :oldest_created
      AND l.availability = 'in_stock' AND l.price IS NOT NULL
    GROUP BY c.id, l.price, l.availability, l.observed_at, l.collection_run_id
    HAVING count(d.day) >= 2 AND l.price < avg(d.daily_average)
    ORDER BY (avg(d.daily_average) - l.price) DESC, c.id
""")


class DealRepository:
    async def list_deals(self, now: datetime | None = None) -> List[Deal]:
        now = now or datetime.now(timezone.utc)
        async with self._database.session() as session:
            rows = (await session.execute(_DEALS_SQL, {"oldest_created": now - timedelta(days=7)})).all()
            cards = {record.id: _card(record) for record in (await session.scalars(
                select(MarketplaceCardRecord).where(MarketplaceCardRecord.id.in_([row.id for row in rows]))
            )).all()} if rows else {}
        return [Deal(CardOverview(cards[row.id], row.price, row.availability, row.observed_at),
                     row.average_price, row.average_price - row.price, row.baseline_days,
                     row.collection_run_id)
                for row in rows]
