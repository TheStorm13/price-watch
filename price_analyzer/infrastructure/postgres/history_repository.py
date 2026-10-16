"""Observations, charts, and price statistics."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import List

from sqlalchemy import func, literal_column, select

from marketplace_connector.domain.models import ProductSnapshot
from marketplace_connector.serialization.product_json import snapshot_to_dict

from ...domain.models import MarketplaceCard, PriceHistoryPoint, PriceStatistics
from .models import MarketplaceCardRecord, PriceHistoryRecord


class HistoryRepository:
    async def save_observation(self, card: MarketplaceCard, run_id: int, snapshot: ProductSnapshot) -> None:
        price = (
            Decimal(str(snapshot.price)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            if snapshot.price is not None else None
        )
        availability = snapshot.availability.value
        async with self._database.session() as session, session.begin():
            # All writers for one card serialize here; browser I/O happens before this transaction.
            card_record = (await session.get(MarketplaceCardRecord, card.id, with_for_update=True))
            if card_record is None:
                raise LookupError(f"Карточка не найдена: {card.id}")
            latest = (await session.execute(
                select(PriceHistoryRecord.price, PriceHistoryRecord.availability)
                .where(PriceHistoryRecord.card_id == card.id)
                .order_by(PriceHistoryRecord.observed_at.desc(), PriceHistoryRecord.id.desc())
                .limit(1)
            )).first()
            card_record.title = snapshot.title
            card_record.url = snapshot.url or None
            card_record.updated_at = datetime.now(timezone.utc)
            if latest is not None and (latest.price, latest.availability) == (price, availability):
                return
            session.add(
                PriceHistoryRecord(
                    card_id=card.id,
                    collection_run_id=run_id,
                    price=price,
                    availability=availability,
                    observed_at=snapshot.collected_at,
                    snapshot=snapshot_to_dict(snapshot),
                )
            )

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
