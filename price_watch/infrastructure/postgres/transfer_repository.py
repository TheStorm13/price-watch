"""Atomic product/variant transfer v3, merging each independent price history."""
from __future__ import annotations
from sqlalchemy import select, text, tuple_
from sqlalchemy.orm import defer
from marketplace_connector.application.card_identity import validate_variant_identity
from ...domain.history_merge import HistoryEvent, merge_history
from ...domain.errors import ImportDuringRun, VariantOwnershipConflict
from .database import AsyncDatabase
from .models import CollectionRunRecord, MarketplaceCardRecord, CardVariantRecord, PriceHistoryRecord, ProductGroupRecord
from .repository_common import _RUN_CREATION_LOCK
from .variant_membership import OZON_MEMBERSHIP_LOCK, ozon_owner, ownership_conflict


class TransferRepository:
    def __init__(self, database: AsyncDatabase):
        self._database = database

    async def export_cards(self) -> dict:
        async with self._database.session() as s, s.begin():
            await s.execute(text('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY'))
            products = (await s.scalars(select(MarketplaceCardRecord).order_by(MarketplaceCardRecord.id))).all()
            variants = (await s.scalars(select(CardVariantRecord).order_by(CardVariantRecord.id))).all()
            histories = (await s.scalars(select(PriceHistoryRecord).options(defer(PriceHistoryRecord.snapshot)).order_by(PriceHistoryRecord.observed_at, PriceHistoryRecord.id))).all()
            groups = (await s.scalars(select(ProductGroupRecord).order_by(ProductGroupRecord.id))).all()
            by_variant = {v.id: dict(external_id=v.external_id, title=v.title, url=v.url, image_url=v.image_url, product_title=v.product_title, options=v.options,
                                     tracking_enabled=v.tracking_enabled, updated_at=v.updated_at, history=[]) for v in variants}
            for h in histories:
                by_variant[h.variant_id]['history'].append(dict(price=h.price, availability=h.availability, observed_at=h.observed_at))
            members = {}
            for v in variants:
                members.setdefault(v.card_id, []).append(by_variant[v.id])
            cards = [dict(marketplace=c.marketplace, external_id=c.external_id, title=by_variant[c.primary_variant_id]['product_title'], url=by_variant[c.primary_variant_id]['url'],
                          image_url=by_variant[c.primary_variant_id]['image_url'], tags=c.tags, deals_enabled=c.deals_enabled, created_at=c.created_at,
                          primary_external_id=by_variant[c.primary_variant_id]['external_id'], variants=members[c.id]) for c in products]
            group_data = [dict(name=g.name, tags=g.tags, cards=[dict(marketplace=c.marketplace, external_id=c.external_id)
                for c in products if c.group_id == g.id]) for g in groups]
            return dict(version=3, cards=cards, groups=group_data)

    async def import_cards(self, cards: list[dict], *, groups: list[dict] | None = None, preview: bool = False) -> dict:
        summary = dict(cards_added=0, cards_merged=0, observations_added=0,
                       observations_removed=0, observations_skipped=0, groups_added=0)
        # Validate also at the storage boundary, including direct CLI callers.
        ozon_members = {}
        for item in cards:
            item['marketplace'] = item['marketplace'].strip().lower()
            refs = set()
            for v in item['variants']:
                ref, url = validate_variant_identity(item['marketplace'], item['external_id'], v['external_id'], v.get('url'))
                if ref in refs:
                    raise ValueError('Повторный или чужой вариант')
                if item['marketplace'] == 'ozon':
                    if ref in ozon_members:
                        raise ValueError(f'Ozon SKU {ref} указан в нескольких карточках')
                    ozon_members[ref] = item['external_id']
                v['external_id'], v['url'] = ref, url
                refs.add(ref)
            if item['primary_external_id'] not in refs:
                raise ValueError('Главный вариант отсутствует')
            if item['marketplace'] == 'ozon' and item['external_id'] not in refs:
                raise ValueError('Исходный SKU Ozon отсутствует в товаре')
        keys = [(c['marketplace'].lower(), c['external_id']) for c in cards]
        async with self._database.session() as s, s.begin():
            await s.execute(_RUN_CREATION_LOCK)
            if ozon_members:
                await s.execute(OZON_MEMBERSHIP_LOCK)
            if await s.scalar(select(CollectionRunRecord.id).where(CollectionRunRecord.status.in_(('queued','running','waiting_for_user'))).limit(1)):
                raise ImportDuringRun('Дождитесь завершения текущего сбора перед импортом')
            existing = (await s.scalars(select(MarketplaceCardRecord).where(tuple_(MarketplaceCardRecord.marketplace, MarketplaceCardRecord.external_id).in_(keys)).with_for_update())).all() if keys else []
            by_key = {(c.marketplace,c.external_id):c for c in existing}
            for ref, article in ozon_members.items():
                owner = await ozon_owner(s, ref)
                product = by_key.get(('ozon', article))
                if owner is not None and (product is None or product.id != owner):
                    raise VariantOwnershipConflict(ownership_conflict(ref, owner, product.id if product else f'импорт {article}'))
            variants = (await s.scalars(select(CardVariantRecord).where(CardVariantRecord.card_id.in_([c.id for c in existing])))).all() if existing else []
            by_ref = {(v.card_id,v.external_id):v for v in variants}
            histories = {}
            if variants:
                for h in (await s.scalars(select(PriceHistoryRecord).options(defer(PriceHistoryRecord.snapshot)).where(PriceHistoryRecord.variant_id.in_([v.id for v in variants])).order_by(PriceHistoryRecord.observed_at, PriceHistoryRecord.id))).all():
                    histories.setdefault(h.variant_id,[]).append(h)
            local_groups = {g.name:g for g in (await s.scalars(select(ProductGroupRecord))).all()}
            summary['groups_added'] = len({g['name'] for g in groups or []} - set(local_groups))
            for item in cards:
                key = (item['marketplace'].lower(),item['external_id'])
                product = by_key.get(key)
                summary['cards_merged' if product else 'cards_added'] += 1
                if not preview:
                    if product is None:
                        product = MarketplaceCardRecord(marketplace=key[0],external_id=key[1],tags=item.get('tags',[]),deals_enabled=item['deals_enabled'],created_at=item['created_at'],updated_at=item['created_at'])
                        s.add(product)
                        await s.flush()
                        by_key[key]=product
                    else:
                        product.created_at=min(product.created_at,item['created_at'])
                        product.tags=list(dict.fromkeys([*product.tags,*item.get('tags',[])]))[:2]
                for imported in item['variants']:
                    variant = by_ref.get((product.id,imported['external_id'])) if product else None
                    local = histories.get(variant.id,[]) if variant else []
                    events=[HistoryEvent(h.observed_at,h.price,h.availability,'local',h.id) for h in local]
                    events += [HistoryEvent(h['observed_at'],h['price'],h['availability'],'import',i) for i,h in enumerate(imported['history'])]
                    merged=merge_history(events)
                    kept={h.source_id for h in merged if h.source=='local'}
                    added=[h for h in merged if h.source=='import']
                    removed=[h for h in local if h.id not in kept]
                    summary['observations_added']+=len(added)
                    summary['observations_removed']+=len(removed)
                    summary['observations_skipped']+=len(imported['history'])-len(added)
                    if preview:
                        continue
                    if variant is None:
                        variant=CardVariantRecord(card_id=product.id,external_id=imported['external_id'],url=imported.get('url'),
                            tracking_enabled=imported.get('tracking_enabled',False),
                            title=imported.get('title',''),product_title=imported.get('product_title'),image_url=imported.get('image_url'),options=imported.get('options',{}),updated_at=imported.get('updated_at'))
                        s.add(variant)
                        await s.flush()
                    variant.image_url = variant.image_url or imported.get('image_url')
                    variant.product_title = variant.product_title or imported.get('product_title')
                    if imported['external_id']==item['primary_external_id']:
                        variant.product_title = variant.product_title or item.get('title')
                        variant.image_url = variant.image_url or item.get('image_url')
                        product.primary_variant_id=variant.id
                    for h in removed:
                        await s.delete(h)
                    for h in added:
                        s.add(PriceHistoryRecord(card_id=product.id,variant_id=variant.id,price=h.price,availability=h.availability,observed_at=h.observed_at,snapshot={}))
                    dates=[h.observed_at for h in added]
                    if dates:
                        product.updated_at=max(product.updated_at,*dates)
            if not preview:
                for item in groups or []:
                    group=local_groups.get(item['name'])
                    if group is None:
                        group=ProductGroupRecord(name=item['name'],tags=item.get('tags',[]))
                        s.add(group)
                        await s.flush()
                        local_groups[group.name]=group
                    group.tags=list(dict.fromkeys([*group.tags,*item.get('tags',[])]))
                    for ref in item['cards']:
                        product=by_key[ref['marketplace'].lower(),ref['external_id']]
                        if product.group_id is None:
                            product.group_id=group.id
        return summary
