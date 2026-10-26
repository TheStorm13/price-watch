"""Card records and current-state queries."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from ...domain.models import TrackedCardOverview, TrackedCard
from ...domain.marketplaces import PENDING_CONNECTOR_MARKETPLACES
from .models import CollectionRunRecord, CollectionRunTargetRecord, MarketplaceCardRecord, ProductGroupRecord
from ...domain.errors import CardAlreadyExists, CardInActiveRun
from .repository_common import _tracked_card
from .queries import overview_statement
from .database import AsyncDatabase


class CardRepository:
    def __init__(self, database: AsyncDatabase):
        self._database = database

    async def add_card(
        self,
        marketplace: str,
        external_id: str,
        title: Optional[str] = None,
        url: Optional[str] = None,
        tags: list[str] | None = None,
    ) -> TrackedCard:
        marketplace = marketplace.strip().lower()
        external_id = external_id.strip()
        if not marketplace or not external_id:
            raise ValueError("marketplace и external_id обязательны")
        record = MarketplaceCardRecord(
            marketplace=marketplace,
            external_id=external_id,
            title=title,
            url=url,
            tags=tags or [],
        )
        try:
            async with self._database.session() as session, session.begin():
                session.add(record)
                await session.flush()
        except IntegrityError as exc:
            raise CardAlreadyExists("Такая карточка уже добавлена") from exc
        return _tracked_card(record)

    async def update_card(
        self,
        card_id: int,
        *,
        title: Optional[str] = None,
        url: Optional[str] = None,
        deals_enabled: Optional[bool] = None,
        update_title: bool = False,
        update_url: bool = False,
        group_id: Optional[int] = None,
        update_group: bool = False,
        tags: list[str] | None = None,
    ) -> Optional[TrackedCard]:
        async with self._database.session() as session, session.begin():
            record = (await session.get(MarketplaceCardRecord, card_id))
            if record is None:
                return None
            if update_title:
                record.title = title
            if update_url:
                record.url = url
            if deals_enabled is not None:
                record.deals_enabled = deals_enabled
            if update_group:
                if group_id is not None and await session.get(ProductGroupRecord, group_id) is None:
                    raise ValueError("Группа не найдена")
                record.group_id = group_id
            if tags is not None:
                record.tags = tags
            record.updated_at = datetime.now(timezone.utc)
        return _tracked_card(record)

    async def delete_card(self, card_id: int) -> bool:
        async with self._database.session() as session, session.begin():
            record = (await session.get(MarketplaceCardRecord, card_id, with_for_update=True))
            if record is None:
                return False
            active = (await session.scalar(
                select(CollectionRunRecord.id).join(CollectionRunTargetRecord, CollectionRunTargetRecord.run_id == CollectionRunRecord.id).where(
                    CollectionRunRecord.status.in_(("queued", "running", "waiting_for_user")),
                    CollectionRunTargetRecord.card_id == card_id,
                ).limit(1)
            ))
            if active is not None:
                raise CardInActiveRun("Карточка участвует в незавершённом запуске")
            await session.delete(record)
        return True

    async def list_cards(self, *, session=None) -> List[TrackedCardOverview]:
        if session is None:
            async with self._database.session() as session:
                return await self.list_cards(session=session)
        statement = overview_statement()
        statement = statement.order_by(MarketplaceCardRecord.deals_enabled.desc(), MarketplaceCardRecord.id)
        rows = (await session.execute(statement)).all()
        return [
            TrackedCardOverview(
                card=_tracked_card(card),
                current_price=latest.price if latest else None,
                current_availability=latest.availability if latest else None,
                last_observed_at=latest.observed_at if latest else None,
            )
            for card, latest in rows
        ]

    async def get_card(self, card_id: int) -> Optional[TrackedCardOverview]:
        async with self._database.session() as session:
            row = (await session.execute(
                overview_statement().where(MarketplaceCardRecord.id == card_id)
            )).first()
        if row is None:
            return None
        card, latest = row
        return TrackedCardOverview(
            card=_tracked_card(card),
            current_price=latest.price if latest else None,
            current_availability=latest.availability if latest else None,
            last_observed_at=latest.observed_at if latest else None,
        )

    async def list_collection_cards(self, card_id: Optional[int] = None) -> List[TrackedCard]:
        statement = select(MarketplaceCardRecord)
        if card_id is not None:
            statement = statement.where(MarketplaceCardRecord.id == card_id)
        statement = statement.where(MarketplaceCardRecord.marketplace.notin_(PENDING_CONNECTOR_MARKETPLACES))
        statement = statement.order_by(MarketplaceCardRecord.marketplace, MarketplaceCardRecord.id)
        async with self._database.session() as session:
            records = (await session.scalars(statement)).all()
        return [_tracked_card(record) for record in records]
