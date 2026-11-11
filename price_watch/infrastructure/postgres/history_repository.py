"""Observations, charts, and price statistics."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import List

from sqlalchemy import func, select, text

from ...domain.models import PriceHistoryPoint, PriceStatistics
from .models import PriceHistoryRecord, MarketplaceCardRecord
from .database import AsyncDatabase
from .queries import price_metrics_ctes, price_window


class HistoryRepository:
    def __init__(self, database: AsyncDatabase):
        self._database = database

    @staticmethod
    def _selected_variant(card_id, variant_id):
        return variant_id if variant_id is not None else select(MarketplaceCardRecord.primary_variant_id).where(MarketplaceCardRecord.id == card_id).scalar_subquery()

    @staticmethod
    def _cutoff(days: int) -> datetime:
        return datetime.now(timezone.utc) - timedelta(days=days)

    async def get_history(
        self, card_id: int, days: int, page: int = 1, page_size: int = 50, variant_id: int | None = None
    ) -> List[PriceHistoryPoint]:
        if days <= 0 or page <= 0 or not 1 <= page_size <= 200:
            raise ValueError("Некорректные параметры истории")
        statement = (
            select(PriceHistoryRecord.id, PriceHistoryRecord.card_id, PriceHistoryRecord.variant_id, PriceHistoryRecord.collection_run_id,
                   PriceHistoryRecord.price, PriceHistoryRecord.availability, PriceHistoryRecord.observed_at)
            .where(
                PriceHistoryRecord.card_id == card_id,
                PriceHistoryRecord.variant_id == self._selected_variant(card_id, variant_id),
                PriceHistoryRecord.observed_at >= self._cutoff(days),
            )
            .order_by(PriceHistoryRecord.observed_at.desc(), PriceHistoryRecord.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        async with self._database.session() as session:
            records = (await session.execute(statement)).all()
        return [
            PriceHistoryPoint(
                id=record.id,
                variant_id=record.variant_id,
                card_id=record.card_id,
                collection_run_id=record.collection_run_id,
                price=record.price,
                availability=record.availability,
                observed_at=record.observed_at,
            )
            for record in records
        ]

    async def get_chart_points(self, card_id: int, days: int) -> List[PriceHistoryPoint]:
        """Return every saved price change in chronological order."""
        statement = (
            select(PriceHistoryRecord.id, PriceHistoryRecord.card_id, PriceHistoryRecord.variant_id, PriceHistoryRecord.collection_run_id,
                   PriceHistoryRecord.price, PriceHistoryRecord.availability, PriceHistoryRecord.observed_at)
            .where(PriceHistoryRecord.card_id == card_id,
                   PriceHistoryRecord.observed_at >= self._cutoff(days))
            .order_by(PriceHistoryRecord.observed_at, PriceHistoryRecord.id)
        )
        async with self._database.session() as session:
            records = (await session.execute(statement)).all()
        return [PriceHistoryPoint(
            id=record.id, card_id=record.card_id, variant_id=record.variant_id,
            collection_run_id=record.collection_run_id,
            price=None if record.availability == "out_of_stock" else record.price,
            availability=record.availability, observed_at=record.observed_at,
        ) for record in records]

    async def count_history(self, card_id: int, days: int, variant_id: int | None = None) -> int:
        async with self._database.session() as session:
            return int((await session.scalar(
                select(func.count()).select_from(PriceHistoryRecord).where(
                    PriceHistoryRecord.card_id == card_id,
                    PriceHistoryRecord.variant_id == self._selected_variant(card_id, variant_id),
                    PriceHistoryRecord.observed_at >= self._cutoff(days),
                )
            )) or 0)

    async def get_statistics(self, card_id: int, variant_id: int | None = None) -> PriceStatistics:
        start, end = price_window()
        statement = text(price_metrics_ctes(
            'SELECT id AS variant_id FROM card_variants WHERE card_id = :card_id '
            'AND id = coalesce(:variant_id, (SELECT primary_variant_id FROM marketplace_cards WHERE id = :card_id))'
        ) + """
            SELECT m.average_price, m.minimum_price, m.maximum_price,
                   coalesce(m.observations_count, 0) AS observations_count,
                   coalesce(m.baseline_days, 0) AS baseline_days
            FROM (SELECT 1) seed LEFT JOIN metrics m ON true
        """)
        async with self._database.session() as session:
            row = (await session.execute(statement, {
                'card_id': card_id, 'variant_id': variant_id,
                'window_start': start, 'window_end': end,
            })).one()
        return PriceStatistics(
            card_id=card_id, window_start=start, window_end=end,
            average_price=row.average_price, minimum_price=row.minimum_price,
            maximum_price=row.maximum_price, observations_count=row.observations_count,
            observed_days=row.baseline_days,
        )
