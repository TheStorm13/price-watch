"""Card records and current-state queries."""

from __future__ import annotations

from marketplace_connector.application.card_identity import validate_card_identity

from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from ...domain.models import TrackedCardOverview, TrackedCard
from .models import CollectionRunRecord, CollectionRunTargetRecord, MarketplaceCardRecord, ProductGroupRecord, CardVariantRecord
from ...domain.errors import CardAlreadyExists, CardInActiveRun
from .repository_common import _tracked_card, _RUN_CREATION_LOCK
from .queries import overview_statement
from .database import AsyncDatabase
from .runs_repository import RunRepository, _DIAGNOSTIC_CREATION_LOCK
from .variant_membership import YANDEX_MEMBERSHIP_LOCK, yandex_owner, OZON_MEMBERSHIP_LOCK, ozon_owner


class CardRepository:
    def __init__(self, database: AsyncDatabase, runs: RunRepository):
        self._database = database
        self._runs = runs

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
        external_id, url = validate_card_identity(marketplace, external_id, url)
        article = external_id.split(':')[0] if marketplace in ('aliexpress', 'wildberries') else external_id
        try:
            async with self._database.session() as session, session.begin():
                await session.execute(_RUN_CREATION_LOCK)
                if marketplace == 'ozon':
                    await session.execute(OZON_MEMBERSHIP_LOCK)
                    owner = await ozon_owner(session, external_id)
                    if owner is not None:
                        raise CardAlreadyExists(f'Ozon SKU {external_id} уже добавлен в карточку {owner}')
                if marketplace == 'yandex-market':
                    await session.execute(YANDEX_MEMBERSHIP_LOCK)
                    owner = await yandex_owner(session, external_id)
                    if owner is not None:
                        raise CardAlreadyExists(f'Маркет SKU {external_id} уже добавлен в карточку {owner}')
                await session.execute(_DIAGNOSTIC_CREATION_LOCK)
                record = await session.scalar(select(MarketplaceCardRecord).where(
                    MarketplaceCardRecord.marketplace == marketplace, MarketplaceCardRecord.external_id == article).with_for_update())
                if record is None:
                    record = MarketplaceCardRecord(marketplace=marketplace, external_id=article, tags=tags or [])
                    session.add(record)
                    await session.flush()
                if external_id == article and record.primary_variant_id is not None:
                    raise CardAlreadyExists("Такой товар уже добавлен")
                if await session.scalar(select(CardVariantRecord.id).where(
                    CardVariantRecord.card_id == record.id, CardVariantRecord.external_id == external_id)):
                    raise CardAlreadyExists("Такой вариант уже добавлен")
                variant = CardVariantRecord(card_id=record.id, marketplace=marketplace, external_id=external_id, url=url, product_title=title)
                session.add(variant)
                await session.flush()
                if record.primary_variant_id is None:
                    record.primary_variant_id = variant.id
                await session.flush()
                await session.refresh(record)
                if marketplace in ('ozon', 'wildberries', 'aliexpress', 'yandex-market'):
                    await self._runs.enqueue_initial(session, record.id)
        except IntegrityError as exc:
            raise CardAlreadyExists("Такая карточка или вариант уже добавлены") from exc
        return _tracked_card(record, variant)

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
        primary_variant_id: int | None = None,
    ) -> Optional[TrackedCard]:
        async with self._database.session() as session, session.begin():
            record = (await session.get(MarketplaceCardRecord, card_id, with_for_update=True))
            if record is None:
                return None
            selected_id = primary_variant_id if primary_variant_id is not None else record.primary_variant_id
            variant = await session.get(CardVariantRecord, selected_id) if selected_id else None
            if primary_variant_id is not None:
                if variant is None or variant.card_id != card_id:
                    raise ValueError("Вариант не принадлежит этому товару")
                if record.marketplace in ('wildberries', 'aliexpress') and ':' not in variant.external_id:
                    exact = await session.scalar(select(CardVariantRecord.id).where(
                        CardVariantRecord.card_id == card_id, CardVariantRecord.external_id.contains(':')).limit(1))
                    if exact is not None:
                        raise ValueError('Выберите точный вариант товара; прежняя общая история доступна отдельно')
                record.primary_variant_id = primary_variant_id
            if update_url and record.marketplace in ("ozon", "aliexpress", "wildberries", "yandex-market") and url:
                validate_card_identity(record.marketplace, variant.external_id, url)
            if update_title:
                variant.product_title = title
            if update_url:
                if variant is not None:
                    variant.url = url
            if deals_enabled is not None:
                record.deals_enabled = deals_enabled
            if update_group:
                if group_id is not None and await session.get(ProductGroupRecord, group_id) is None:
                    raise ValueError("Группа не найдена")
                record.group_id = group_id
            if tags is not None:
                record.tags = tags
            record.updated_at = datetime.now(timezone.utc)
        return _tracked_card(record, variant)

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
                card=_tracked_card(card, variant, last_collected_at=variant.updated_at if variant else None),
                current_price=latest.price if latest else None,
                current_availability=latest.availability if latest else None,
                last_observed_at=latest.observed_at if latest else None,
            )
            for card, latest, variant in rows
        ]

    async def get_card(self, card_id: int) -> Optional[TrackedCardOverview]:
        async with self._database.session() as session:
            row = (await session.execute(
                overview_statement().where(MarketplaceCardRecord.id == card_id)
            )).first()
        if row is None:
            return None
        card, latest, variant = row
        return TrackedCardOverview(
            card=_tracked_card(card, variant, last_collected_at=variant.updated_at if variant else None),
            current_price=latest.price if latest else None,
            current_availability=latest.availability if latest else None,
            last_observed_at=latest.observed_at if latest else None,
        )

    async def list_collection_cards(self, card_id: Optional[int] = None) -> List[TrackedCard]:
        statement = select(MarketplaceCardRecord, CardVariantRecord).join(CardVariantRecord,
            CardVariantRecord.card_id == MarketplaceCardRecord.id)
        if card_id is not None:
            statement = statement.where(MarketplaceCardRecord.id == card_id)
        async with self._database.session() as session:
            rows = (await session.execute(statement.order_by(MarketplaceCardRecord.id, CardVariantRecord.id))).all()
            return [_tracked_card(record, variant, for_collection=True) for record, variant in rows
                    if variant.id == record.primary_variant_id or variant.tracking_enabled]

    async def get_variant_image(self, card_id: int, variant_id: int) -> tuple[str | None] | None:
        async with self._database.session() as session:
            row = (await session.execute(select(CardVariantRecord.image_url).where(
                CardVariantRecord.card_id == card_id, CardVariantRecord.id == variant_id,
            ))).first()
        return (row[0],) if row is not None else None

    async def get_variants(self, card_id: int) -> list[dict]:
        from .models import PriceHistoryRecord
        from sqlalchemy.orm import aliased
        latest_id = select(PriceHistoryRecord.id).where(PriceHistoryRecord.variant_id == CardVariantRecord.id).order_by(
            PriceHistoryRecord.observed_at.desc(), PriceHistoryRecord.id.desc()).limit(1).correlate(CardVariantRecord).scalar_subquery()
        latest = aliased(PriceHistoryRecord)
        async with self._database.session() as session:
            rows = (await session.execute(select(CardVariantRecord, latest.price, latest.availability, latest.observed_at).outerjoin(latest, latest.id == latest_id)
                .where(CardVariantRecord.card_id == card_id).order_by(CardVariantRecord.id))).all()
            product = await session.get(MarketplaceCardRecord, card_id)
            if product is None:
                return []
            exact = any(':' in v.external_id for v, *_ in rows)
            return [dict(id=v.id, card_id=v.card_id, external_id=v.external_id, title=v.title,
                         url=v.url, image_url=v.image_url, product_title=v.product_title, options=v.options, current_price=price,
                         tracking_enabled=v.tracking_enabled,
                         is_tracked=v.id == product.primary_variant_id or (v.tracking_enabled and (not exact or ':' in v.external_id)),
                         current_availability=availability,
                         last_observed_at=observed_at, updated_at=v.updated_at)
                    for v, price, availability, observed_at in rows if not exact or ':' in v.external_id or observed_at is not None]

    async def set_variant_tracking(self, card_id: int, enabled: bool, variant_id: int | None = None) -> bool:
        async with self._database.session() as session, session.begin():
            product = await session.get(MarketplaceCardRecord, card_id, with_for_update=True)
            if product is None:
                return False
            query = update(CardVariantRecord).where(CardVariantRecord.card_id == card_id)
            if variant_id is not None:
                variant = await session.get(CardVariantRecord, variant_id)
                if variant is None or variant.card_id != card_id:
                    raise ValueError('Вариант не принадлежит этому товару')
                if product.marketplace in ('wildberries', 'aliexpress') and ':' not in variant.external_id:
                    raise ValueError('Общая история не является точным вариантом товара')
                if variant_id == product.primary_variant_id:
                    raise ValueError('Главный вариант всегда отслеживается')
                query = query.where(CardVariantRecord.id == variant_id)
            else:
                query = query.where(CardVariantRecord.id != product.primary_variant_id)
            if product.marketplace in ('wildberries', 'aliexpress'):
                query = query.where(CardVariantRecord.external_id.contains(':'))
            await session.execute(query.values(tracking_enabled=enabled))
            product.updated_at = datetime.now(timezone.utc)
            return True
