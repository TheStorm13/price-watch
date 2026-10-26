"""Product groups are display aggregates; collection still targets individual cards."""

from .database import AsyncDatabase

from sqlalchemy import select, update

from .models import MarketplaceCardRecord, ProductGroupRecord


class GroupRepository:
    def __init__(self, database: AsyncDatabase):
        self._database = database

    async def create_group(self, name: str, card_ids: list[int], tags: list[str] | None = None) -> int:
        async with self._database.session() as session, session.begin():
            await self._validate_cards(session, card_ids)
            group = ProductGroupRecord(name=name, tags=tags or [])
            session.add(group)
            await session.flush()
            if card_ids:
                await session.execute(update(MarketplaceCardRecord)
                                      .where(MarketplaceCardRecord.id.in_(card_ids))
                                      .values(group_id=group.id))
            return group.id

    async def update_group(self, group_id: int, name: str, card_ids: list[int], tags: list[str] | None = None) -> bool:
        async with self._database.session() as session, session.begin():
            group = await session.get(ProductGroupRecord, group_id, with_for_update=True)
            if group is None:
                return False
            await self._validate_cards(session, card_ids)
            group.name = name
            group.tags = tags or []
            await session.execute(update(MarketplaceCardRecord)
                                  .where(MarketplaceCardRecord.group_id == group_id)
                                  .values(group_id=None))
            if card_ids:
                await session.execute(update(MarketplaceCardRecord)
                                      .where(MarketplaceCardRecord.id.in_(card_ids))
                                      .values(group_id=group_id))
            return True

    async def delete_group(self, group_id: int) -> bool:
        async with self._database.session() as session, session.begin():
            group = await session.get(ProductGroupRecord, group_id, with_for_update=True)
            if group is None:
                return False
            await session.delete(group)
            return True

    @staticmethod
    async def _validate_cards(session, card_ids: list[int]) -> None:
        if len(card_ids) != len(set(card_ids)):
            raise ValueError("Карточка указана несколько раз")
        if not card_ids:
            return
        existing = (await session.scalars(select(MarketplaceCardRecord.id)
                                          .where(MarketplaceCardRecord.id.in_(card_ids)))).all()
        if len(existing) != len(card_ids):
            raise ValueError("Одна или несколько карточек не найдены")
