"""Shared PostgreSQL statement builders; no application policy lives here."""
from sqlalchemy import select, text
from sqlalchemy.orm import aliased
from .models import MarketplaceCardRecord, PriceHistoryRecord


def overview_statement():
    latest_id = (
        select(PriceHistoryRecord.id)
        .where(PriceHistoryRecord.card_id == MarketplaceCardRecord.id)
        .order_by(PriceHistoryRecord.observed_at.desc(), PriceHistoryRecord.id.desc())
        .limit(1)
        .correlate(MarketplaceCardRecord)
        .scalar_subquery()
    )
    latest = aliased(PriceHistoryRecord)
    return select(MarketplaceCardRecord, latest).outerjoin(latest, latest.id == latest_id)


async def card_price_metric_rows(session):
    statement = text("""
        WITH latest AS (
            SELECT DISTINCT ON (card_id) card_id, id
            FROM price_history ORDER BY card_id, observed_at DESC, id DESC
        ), daily AS (
            SELECT h.card_id, date_trunc('day', h.observed_at) AS day,
                   avg(h.price) AS daily_average
            FROM price_history h JOIN latest l ON l.card_id = h.card_id
            WHERE h.id <> l.id AND h.availability = 'in_stock' AND h.price IS NOT NULL
            GROUP BY h.card_id, date_trunc('day', h.observed_at)
        ), averages AS (
            SELECT card_id, avg(daily_average) AS average_price, count(*) AS baseline_days
            FROM daily GROUP BY card_id
        ), minimums AS (
            SELECT card_id, min(price) AS minimum_price
            FROM price_history
            WHERE availability = 'in_stock' AND price IS NOT NULL
            GROUP BY card_id
        )
        SELECT c.id, m.minimum_price, a.average_price, coalesce(a.baseline_days, 0) AS baseline_days
        FROM marketplace_cards c
        LEFT JOIN minimums m ON m.card_id = c.id
        LEFT JOIN averages a ON a.card_id = c.id
    """)
    return (await session.execute(statement)).all()
