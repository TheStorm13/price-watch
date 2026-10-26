"""Observations, charts, and price statistics."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import List

from sqlalchemy import func, literal_column, select

from ...domain.models import PriceHistoryPoint, PriceStatistics
from .models import PriceHistoryRecord
from .database import AsyncDatabase


class HistoryRepository:
    def __init__(self, database: AsyncDatabase):
        self._database = database

    @staticmethod
    def _cutoff(days: int) -> datetime:
        return datetime.now(timezone.utc) - timedelta(days=days)

    async def get_history(
        self, card_id: int, days: int, page: int = 1, page_size: int = 50
    ) -> List[PriceHistoryPoint]:
        if days <= 0 or page <= 0 or not 1 <= page_size <= 200:
            raise ValueError("Некорректные параметры истории")
        statement = (
            select(PriceHistoryRecord)
            .where(
                PriceHistoryRecord.card_id == card_id,
                PriceHistoryRecord.observed_at >= self._cutoff(days),
            )
            .order_by(PriceHistoryRecord.observed_at.desc(), PriceHistoryRecord.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        async with self._database.session() as session:
            records = (await session.scalars(statement)).all()
        return [
            PriceHistoryPoint(
                id=record.id,
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
            select(PriceHistoryRecord)
            .where(PriceHistoryRecord.card_id == card_id,
                   PriceHistoryRecord.observed_at >= self._cutoff(days))
            .order_by(PriceHistoryRecord.observed_at, PriceHistoryRecord.id)
        )
        async with self._database.session() as session:
            records = (await session.scalars(statement)).all()
        return [PriceHistoryPoint(
            id=record.id, card_id=record.card_id,
            collection_run_id=record.collection_run_id,
            price=None if record.availability == "out_of_stock" else record.price,
            availability=record.availability, observed_at=record.observed_at,
        ) for record in records]

    async def count_history(self, card_id: int, days: int) -> int:
        async with self._database.session() as session:
            return int((await session.scalar(
                select(func.count()).select_from(PriceHistoryRecord).where(
                    PriceHistoryRecord.card_id == card_id,
                    PriceHistoryRecord.observed_at >= self._cutoff(days),
                )
            )) or 0)

    async def get_statistics(self, card_id: int, days: int) -> PriceStatistics:
        if days <= 0:
            raise ValueError("days должен быть положительным")
        observed_day = func.date_trunc(
            literal_column("'day'"), PriceHistoryRecord.observed_at
        )
        daily = (
            select(
                observed_day.label("observed_day"),
                func.avg(PriceHistoryRecord.price).label("daily_average"),
                func.min(PriceHistoryRecord.price).label("daily_minimum"),
                func.max(PriceHistoryRecord.price).label("daily_maximum"),
                func.count().label("observations_count"),
            )
            .where(
                PriceHistoryRecord.card_id == card_id,
                PriceHistoryRecord.observed_at >= self._cutoff(days),
                PriceHistoryRecord.availability == "in_stock",
                PriceHistoryRecord.price.is_not(None),
            )
            .group_by(observed_day)
            .subquery()
        )
        async with self._database.session() as session:
            row = (await session.execute(select(
                func.avg(daily.c.daily_average),
                func.min(daily.c.daily_minimum),
                func.max(daily.c.daily_maximum),
                func.coalesce(func.sum(daily.c.observations_count), 0),
                func.count(),
            ))).one()
        return PriceStatistics(
            card_id=card_id,
            days=days,
            average_price=row[0],
            minimum_price=row[1],
            maximum_price=row[2],
            observations_count=int(row[3]),
            observed_days=int(row[4]),
        )
