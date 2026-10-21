"""Product groups are display aggregates; collection still targets individual cards."""

from dataclasses import asdict

from sqlalchemy import select, update

from .models import MarketplaceCardRecord, ProductGroupRecord


class GroupRepository:
    async def list_groups(self) -> list[dict]:
        # All parts of the projection must describe the same saved state.
        async with self._database.session() as session, session.begin():
            await session.connection(execution_options={"isolation_level": "REPEATABLE READ"})
            groups = (await session.scalars(select(ProductGroupRecord).order_by(ProductGroupRecord.id))).all()
            cards = await self.list_cards(session=session)
            metrics = {row.id: row for row in await self._list_card_price_metric_rows(session)}
            deals = {deal.card.card.id: deal for deal in await self.list_deals(session=session)}
        by_group = {}
        for item in cards:
            by_group.setdefault(item.card.group_id, []).append(item)
        result = []
        for group in groups:
            members = by_group.get(group.id, [])
            representative = min(members, key=lambda item: (
                item.current_price is None,
                item.current_price if item.current_price is not None else 0,
                item.card.id,
            ), default=None)
            card_id = representative.card.id if representative else None
            metric = metrics.get(card_id)
            deal = deals.get(card_id)
            card_view = None
            if representative:
                card_view = {
                    **asdict(representative.card),
                    "current_price": representative.current_price,
                    "current_availability": representative.current_availability,
                    "last_observed_at": representative.last_observed_at,
                    "minimum_price": metric.minimum_price,
                    "average_price": metric.average_price,
                }
            result.append({
                "id": group.id,
                "name": group.name,
                "tags": group.tags,
                "card_ids": sorted(item.card.id for item in members),
                "representative_card_id": card_id,
                "representative_card": card_view,
                "current_price": representative.current_price if representative else None,
                "minimum_price": metric.minimum_price if metric else None,
                "savings": deal.savings if deal else None,
                "baseline_days": metric.baseline_days if metric else 0,
                "is_deal": deal is not None,
                "has_member_deals": any(item.card.id in deals for item in members),
            })
        return result

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
