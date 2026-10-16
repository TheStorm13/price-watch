"""Atomic export and import of cards and price history."""

from __future__ import annotations

from sqlalchemy import select, text, tuple_

from ...domain.history_merge import HistoryEvent, merge_history
from .models import CollectionRunRecord, MarketplaceCardRecord, PriceHistoryRecord, ProductGroupRecord
from .repository_common import ImportDuringRun, _RUN_CREATION_LOCK


class TransferRepository:
    async def export_cards(self) -> dict:
        """Export every card and saved price change from one consistent DB snapshot."""
        async with self._database.session() as session, session.begin():
            await session.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY"))
            cards = (await session.scalars(select(MarketplaceCardRecord).order_by(
                MarketplaceCardRecord.marketplace, MarketplaceCardRecord.external_id,
            ))).all()
            histories = (await session.scalars(select(PriceHistoryRecord).order_by(
                PriceHistoryRecord.card_id, PriceHistoryRecord.observed_at, PriceHistoryRecord.id,
            ))).all()
            groups = (await session.scalars(select(ProductGroupRecord).order_by(ProductGroupRecord.id))).all()
            result = [{
                "marketplace": card.marketplace,
                "external_id": card.external_id,
                "title": card.title,
                "url": card.url,
                "image_url": card.image_url,
                "tags": card.tags,
                "is_active": card.is_active,
                "created_at": card.created_at,
                "history": [],
            } for card in cards]
            by_id = {card.id: item for card, item in zip(cards, result)}
            for point in histories:
                by_id[point.card_id]["history"].append({
                    "price": point.price,
                    "availability": point.availability,
                    "observed_at": point.observed_at,
                })
            group_data = [{
                "name": group.name,
                "tags": group.tags,
                "cards": [{"marketplace": card.marketplace, "external_id": card.external_id}
                          for card in cards if card.group_id == group.id],
            } for group in groups]
        return {"version": 1, "cards": result, "groups": group_data}

    async def import_cards(self, cards: list[dict], *, groups: list[dict] | None = None, preview: bool = False) -> dict:
        """Merge cards and histories atomically; preview computes the same result."""
        summary = {
            "cards_added": 0, "cards_merged": 0, "observations_added": 0,
            "observations_removed": 0, "observations_skipped": 0, "groups_added": 0,
        }
        keys = [(card["marketplace"].lower(), card["external_id"]) for card in cards]
        async with self._database.session() as session, session.begin():
            await session.execute(_RUN_CREATION_LOCK)
            active_run = (await session.scalar(select(CollectionRunRecord.id).where(
                CollectionRunRecord.status.in_(("queued", "running", "waiting_for_user")),
            ).limit(1)))
            if active_run is not None:
                raise ImportDuringRun("Дождитесь завершения текущего сбора перед импортом")
            existing = (await session.scalars(select(MarketplaceCardRecord).where(
                tuple_(MarketplaceCardRecord.marketplace, MarketplaceCardRecord.external_id).in_(keys)
            ).with_for_update())).all() if keys else []
            by_key = {(card.marketplace, card.external_id): card for card in existing}
            existing_groups = (await session.scalars(select(ProductGroupRecord).order_by(ProductGroupRecord.id))).all()
            groups_by_name = {group.name: group for group in existing_groups}
            summary["groups_added"] = len({group["name"] for group in (groups or [])} - set(groups_by_name))
            histories: dict[int, list[PriceHistoryRecord]] = {card.id: [] for card in existing}
            if histories:
                rows = (await session.scalars(select(PriceHistoryRecord).where(
                    PriceHistoryRecord.card_id.in_(histories)
                ).order_by(PriceHistoryRecord.card_id, PriceHistoryRecord.observed_at,
                           PriceHistoryRecord.id))).all()
                for row in rows:
                    histories[row.card_id].append(row)

            for item in cards:
                key = (item["marketplace"].lower(), item["external_id"])
                card = by_key.get(key)
                local = histories.get(card.id, []) if card else []
                imported = item["history"]
                events = [HistoryEvent(row.observed_at, row.price, row.availability,
                                       "local", row.id) for row in local]
                events.extend(HistoryEvent(point["observed_at"], point["price"],
                                           point["availability"], "import", index)
                              for index, point in enumerate(imported))
                merged = merge_history(events)
                kept_local = {event.source_id for event in merged if event.source == "local"}
                added = [event for event in merged if event.source == "import"]
                removed = [row for row in local if row.id not in kept_local]
                summary["cards_merged" if card else "cards_added"] += 1
                summary["observations_added"] += len(added)
                summary["observations_removed"] += len(removed)
                summary["observations_skipped"] += len(imported) - len(added)
                if preview:
                    continue
                if card is None:
                    latest_imported_at = max((point["observed_at"] for point in imported),
                                             default=item["created_at"])
                    card = MarketplaceCardRecord(
                        marketplace=key[0], external_id=key[1], title=item["title"],
                        url=item["url"], is_active=item["is_active"] and not item.get("is_archived", False),
                        image_url=item.get("image_url"),
                        tags=item.get("tags", []),
                        created_at=item["created_at"],
                        updated_at=max(item["created_at"], latest_imported_at),
                    )
                    session.add(card)
                    await session.flush()
                    by_key[key] = card
                else:
                    card.created_at = min(card.created_at, item["created_at"])
                    if not card.image_url:
                        card.image_url = item.get("image_url")
                    card.tags = list(dict.fromkeys([*card.tags, *item.get("tags", [])]))[:2]
                    if imported:
                        card.updated_at = max(card.updated_at,
                                              max(point["observed_at"] for point in imported))
                for row in removed:
                    await session.delete(row)
                for event in added:
                    session.add(PriceHistoryRecord(
                        card_id=card.id, collection_run_id=None, price=event.price,
                        availability=event.availability, observed_at=event.observed_at,
                        snapshot={},
                    ))
            if not preview:
                for imported_group in groups or []:
                    group = groups_by_name.get(imported_group["name"])
                    if group is None:
                        group = ProductGroupRecord(name=imported_group["name"], tags=imported_group.get("tags", []))
                        session.add(group)
                        await session.flush()
                        groups_by_name[group.name] = group
                    else:
                        group.tags = list(dict.fromkeys([*group.tags, *imported_group.get("tags", [])]))
                    for member in imported_group["cards"]:
                        card = by_key[(member["marketplace"].lower(), member["external_id"])]
                        if card.group_id is None:
                            card.group_id = group.id
        return summary
