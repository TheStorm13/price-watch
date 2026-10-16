"""Product groups are display aggregates; collection still targets individual cards."""

from sqlalchemy import func, select, update

from .models import MarketplaceCardRecord, PriceHistoryRecord, ProductGroupRecord


class GroupRepository:
    async def list_groups(self) -> list[dict]:
        async with self._database.session() as session:
            groups = (await session.scalars(select(ProductGroupRecord).order_by(ProductGroupRecord.id))).all()
            minimums = dict((await session.execute(
                select(MarketplaceCardRecord.group_id, func.min(PriceHistoryRecord.price))
                .join(PriceHistoryRecord, PriceHistoryRecord.card_id == MarketplaceCardRecord.id)
                .where(MarketplaceCardRecord.group_id.is_not(None),
                       PriceHistoryRecord.availability == "in_stock",
                       PriceHistoryRecord.price.is_not(None))
                .group_by(MarketplaceCardRecord.group_id)
            )).all())
        cards = await self.list_cards(include_inactive=True)
        result = []
        for group in groups:
            members = [item for item in cards if item.card.group_id == group.id]
            current = [item.current_price for item in members
                       if item.current_availability == "in_stock" and item.current_price is not None]
            result.append({
                "id": group.id,
                "name": group.name,
                "card_ids": [item.card.id for item in members],
                "current_price": min(current) if current else None,
                "minimum_price": minimums.get(group.id),
            })
        return result

    async def create_group(self, name: str, card_ids: list[int]) -> int:
        async with self._database.session() as session, session.begin():
            await self._validate_cards(session, card_ids)
            group = ProductGroupRecord(name=name)
            session.add(group)
            await session.flush()
            if card_ids:
                await session.execute(update(MarketplaceCardRecord)
                                      .where(MarketplaceCardRecord.id.in_(card_ids))
                                      .values(group_id=group.id))
            return group.id

    async def update_group(self, group_id: int, name: str, card_ids: list[int]) -> bool:
        async with self._database.session() as session, session.begin():
            group = await session.get(ProductGroupRecord, group_id, with_for_update=True)
            if group is None:
                return False
            await self._validate_cards(session, card_ids)
            group.name = name
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
