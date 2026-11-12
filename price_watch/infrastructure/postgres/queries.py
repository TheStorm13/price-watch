"""Shared PostgreSQL statement builders; no application policy lives here."""
from sqlalchemy import select, text
from sqlalchemy.orm import aliased, defer
from ...domain.price_window import price_window
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


def price_metrics_ctes(target_variants: str) -> str:
    """Internal SELECT of variant IDs; parameters carry all external values.

    Keep unavailable states until after LEAD: they terminate a priced interval.
    Fetch only the window and one preceding state per variant. The high-scale
    divisor prevents PostgreSQL from reducing division precision for large money.
    """
    return f"""
        WITH targets AS ({target_variants}), points AS (
            SELECT h.id, h.variant_id, h.price, h.availability, h.observed_at
            FROM price_history h JOIN targets t ON t.variant_id = h.variant_id
            WHERE h.observed_at >= :window_start AND h.observed_at <= :window_end
            UNION ALL
            SELECT h.id, h.variant_id, h.price, h.availability, h.observed_at
            FROM targets t CROSS JOIN LATERAL (
                SELECT id, variant_id, price, availability, observed_at
                FROM price_history WHERE variant_id = t.variant_id AND observed_at < :window_start
                ORDER BY observed_at DESC, id DESC LIMIT 1
            ) h
        ), intervals AS (
            SELECT *, lead(observed_at, 1, :window_end) OVER (
                PARTITION BY variant_id ORDER BY observed_at, id) AS next_at
            FROM points
        ), valid AS (
            SELECT *, extract(epoch FROM (next_at - greatest(observed_at, :window_start))) AS duration
            FROM intervals WHERE availability = 'in_stock' AND price IS NOT NULL
              AND (observed_at >= :window_start OR next_at > :window_start)
        ), metrics AS (
            SELECT variant_id, min(price) AS minimum_price, max(price) AS maximum_price,
                   round(sum(price * duration) / nullif(sum(duration), 0)::numeric(60, 40), 12) AS average_price,
                   min(greatest(observed_at, :window_start)) FILTER (WHERE duration > 0) AS history_started_at,
                   count(*) FILTER (WHERE observed_at >= :window_start) AS observations_count,
                   count(DISTINCT (observed_at AT TIME ZONE 'UTC')::date)
                       FILTER (WHERE observed_at >= :window_start) AS baseline_days
            FROM valid GROUP BY variant_id
        )
    """


async def card_price_metric_rows(session, as_of=None):
    start, end = price_window(as_of)
    statement = text(price_metrics_ctes(
        'SELECT DISTINCT primary_variant_id AS variant_id FROM marketplace_cards '
        'WHERE primary_variant_id IS NOT NULL'
    ) + """
        SELECT c.id, m.minimum_price, m.maximum_price, m.average_price, m.history_started_at, coalesce(m.baseline_days, 0) AS baseline_days
        FROM marketplace_cards c
        LEFT JOIN metrics m ON m.variant_id = c.primary_variant_id
    """)
    return (await session.execute(statement, {'window_start': start, 'window_end': end})).all()
