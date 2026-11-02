"""Shared PostgreSQL statement builders; no application policy lives here."""
from sqlalchemy import select, text
from sqlalchemy.orm import aliased, defer
from .models import MarketplaceCardRecord, PriceHistoryRecord, CardVariantRecord


def overview_statement():
    latest_id = (
        select(PriceHistoryRecord.id)
        .where(PriceHistoryRecord.variant_id == MarketplaceCardRecord.primary_variant_id)
        .order_by(PriceHistoryRecord.observed_at.desc(), PriceHistoryRecord.id.desc())
        .limit(1)
        .correlate(MarketplaceCardRecord)
        .scalar_subquery()
    )
    latest = aliased(PriceHistoryRecord)
    collected_at = select(CardVariantRecord.updated_at).where(CardVariantRecord.id == MarketplaceCardRecord.primary_variant_id).correlate(MarketplaceCardRecord).scalar_subquery()
    return select(MarketplaceCardRecord, latest, collected_at.label('last_collected_at')).outerjoin(latest, latest.id == latest_id).options(defer(latest.snapshot))


async def card_price_metric_rows(session):
    statement = text("""
        WITH latest AS (
            SELECT DISTINCT ON (variant_id) variant_id, id
            FROM price_history WHERE variant_id IN (SELECT primary_variant_id FROM marketplace_cards) ORDER BY variant_id, observed_at DESC, id DESC
        ), daily AS (
            SELECT h.variant_id, date_trunc('day', h.observed_at) AS day,
                   avg(h.price) AS daily_average
            FROM price_history h JOIN latest l ON l.variant_id = h.variant_id
            WHERE h.id <> l.id AND h.availability = 'in_stock' AND h.price IS NOT NULL
            GROUP BY h.variant_id, date_trunc('day', h.observed_at)
        ), averages AS (
            SELECT variant_id, avg(daily_average) AS average_price, count(*) AS baseline_days
            FROM daily GROUP BY variant_id
        ), minimums AS (
            SELECT variant_id, min(price) AS minimum_price
            FROM price_history
            WHERE availability = 'in_stock' AND price IS NOT NULL
              AND variant_id IN (SELECT primary_variant_id FROM marketplace_cards)
            GROUP BY variant_id
        )
        SELECT c.id, m.minimum_price, a.average_price, coalesce(a.baseline_days, 0) AS baseline_days
        FROM marketplace_cards c
        LEFT JOIN minimums m ON m.variant_id = c.primary_variant_id
        LEFT JOIN averages a ON a.variant_id = c.primary_variant_id
    """)
    return (await session.execute(statement)).all()
