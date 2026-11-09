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
    return (select(MarketplaceCardRecord, latest, CardVariantRecord)
            .outerjoin(CardVariantRecord, CardVariantRecord.id == MarketplaceCardRecord.primary_variant_id)
            .outerjoin(latest, latest.id == latest_id).options(defer(latest.snapshot)))


async def card_price_metric_rows(session):
    statement = text("""
        WITH metrics AS (
            SELECT variant_id, min(price) AS minimum_price,
                   (min(price) + max(price)) / 2 AS average_price,
                   count(DISTINCT date_trunc('day', observed_at)) AS baseline_days
            FROM price_history
            WHERE availability = 'in_stock' AND price IS NOT NULL
              AND variant_id IN (SELECT primary_variant_id FROM marketplace_cards)
            GROUP BY variant_id
        )
        SELECT c.id, m.minimum_price, m.average_price, coalesce(m.baseline_days, 0) AS baseline_days
        FROM marketplace_cards c
        LEFT JOIN metrics m ON m.variant_id = c.primary_variant_id
    """)
    return (await session.execute(statement)).all()
