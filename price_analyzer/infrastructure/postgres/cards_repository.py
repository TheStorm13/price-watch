"""Card records and current-state queries."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import aliased

from ...domain.models import CardOverview, MarketplaceCard
from .models import CollectionRunRecord, MarketplaceCardRecord, PriceHistoryRecord
from .repository_common import CardAlreadyExists, CardInActiveRun, _card


class CardRepository:
    async def add_card(
        self,
        marketplace: str,
        external_id: str,
        title: Optional[str] = None,
        url: Optional[str] = None,
    ) -> MarketplaceCard:
        marketplace = marketplace.strip().lower()
        external_id = external_id.strip()
        if not marketplace or not external_id:
            raise ValueError("marketplace и external_id обязательны")
        record = MarketplaceCardRecord(
            marketplace=marketplace,
            external_id=external_id,
            title=title,
            url=url,
        )
        try:
            async with self._database.session() as session, session.begin():
                session.add(record)
                await session.flush()
        except IntegrityError as exc:
            raise CardAlreadyExists("Такая карточка уже добавлена") from exc
        return _card(record)

    async def update_card(
        self,
        card_id: int,
        *,
        title: Optional[str] = None,
        url: Optional[str] = None,
        is_active: Optional[bool] = None,
        update_title: bool = False,
        update_url: bool = False,
    ) -> Optional[MarketplaceCard]:
        async with self._database.session() as session, session.begin():
            record = (await session.get(MarketplaceCardRecord, card_id))
            if record is None:
                return None
            if update_title:
                record.title = title
            if update_url:
                record.url = url
            if is_active is not None:
                record.is_active = is_active
            record.updated_at = datetime.now(timezone.utc)
        return _card(record)

    async def delete_card(self, card_id: int) -> bool:
        async with self._database.session() as session, session.begin():
            record = (await session.get(MarketplaceCardRecord, card_id, with_for_update=True))
            if record is None:
                return False
            active = (await session.scalar(
                select(CollectionRunRecord.id).where(
                    CollectionRunRecord.status.in_(("queued", "running", "waiting_for_user")),
                    CollectionRunRecord.target_card_ids.any(card_id),
                ).limit(1)
            ))
            if active is not None:
                raise CardInActiveRun("Карточка участвует в незавершённом запуске")
            await session.delete(record)
        return True

    def _overview_statement(self):
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

    async def list_cards(self, include_inactive: bool = False) -> List[CardOverview]:
        statement = self._overview_statement()
        if not include_inactive:
            statement = statement.where(MarketplaceCardRecord.is_active.is_(True))
        statement = statement.order_by(MarketplaceCardRecord.is_active.desc(), MarketplaceCardRecord.id)
        async with self._database.session() as session:
            rows = (await session.execute(statement)).all()
        return [
            CardOverview(
                card=_card(card),
                current_price=latest.price if latest else None,
                current_availability=latest.availability if latest else None,
                last_observed_at=latest.observed_at if latest else None,
            )
            for card, latest in rows
        ]

    async def get_card(self, card_id: int) -> Optional[CardOverview]:
        async with self._database.session() as session:
            row = (await session.execute(
                self._overview_statement().where(MarketplaceCardRecord.id == card_id)
            )).first()
        if row is None:
            return None
        card, latest = row
        return CardOverview(
            card=_card(card),
            current_price=latest.price if latest else None,
            current_availability=latest.availability if latest else None,
            last_observed_at=latest.observed_at if latest else None,
        )

    async def list_collection_cards(self, card_id: Optional[int] = None) -> List[MarketplaceCard]:
        statement = select(MarketplaceCardRecord)
        if card_id is not None:
            statement = statement.where(MarketplaceCardRecord.id == card_id)
        statement = statement.order_by(MarketplaceCardRecord.marketplace, MarketplaceCardRecord.id)
        async with self._database.session() as session:
            records = (await session.scalars(statement)).all()
        return [_card(record) for record in records]
