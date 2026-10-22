"""One read-only snapshot, shared inputs and consistent catalog projections."""
from dataclasses import asdict
from sqlalchemy import select
from .models import ProductGroupRecord, MarketplaceCardRecord
from .repository_common import _card


class CatalogRepository:
    async def get_catalog(self):
        async with self._database.session() as session, session.begin():
            await session.connection(execution_options={
                'isolation_level': 'REPEATABLE READ', 'postgresql_readonly': True})
            groups = (await session.scalars(select(ProductGroupRecord).order_by(ProductGroupRecord.id))).all()
            rows = (await session.execute(self._overview_statement().order_by(
                # Keep existing card ordering; UI applies its selected sort.
                MarketplaceCardRecord.deals_enabled.desc(), MarketplaceCardRecord.id))).all()
            metrics = {m.id: m for m in await self._list_card_price_metric_rows(session)}
        cards, deals, grouped = [], [], {}
        for record, latest in rows:
            metric = metrics[record.id]
            card = {**asdict(_card(record)), 'current_price': latest.price if latest else None,
                'current_availability': latest.availability if latest else None,
                'last_observed_at': latest.observed_at if latest else None,
                'minimum_price': metric.minimum_price, 'average_price': metric.average_price}
            cards.append(card)
            grouped.setdefault(record.group_id, []).append(card)
            if (record.deals_enabled and latest is not None and latest.availability == 'in_stock'
                and latest.price is not None and metric.baseline_days >= 1
                and metric.average_price is not None and latest.price < metric.average_price):
                deals.append({'card': card, 'average_price': metric.average_price,
                    'savings': metric.average_price-latest.price, 'baseline_days': metric.baseline_days,
                    'last_collection_run_id': latest.collection_run_id})
        deals.sort(key=lambda d: (-d['savings'], d['card']['id']))
        by_id = {d['card']['id']: d for d in deals}
        projected_groups = []
        for group in groups:
            members = grouped.get(group.id, [])
            representative = min(members, key=lambda c: (c['current_price'] is None,
                c['current_price'] if c['current_price'] is not None else 0, c['id']), default=None)
            metric = metrics[representative['id']] if representative else None
            deal = by_id.get(representative['id']) if representative else None
            projected_groups.append({'id': group.id, 'name': group.name, 'tags': group.tags,
                'card_ids': sorted(c['id'] for c in members),
                'representative_card_id': representative['id'] if representative else None,
                'representative_card': representative,
                'current_price': representative['current_price'] if representative else None,
                'minimum_price': metric.minimum_price if metric else None,
                'savings': deal['savings'] if deal else None,
                'baseline_days': metric.baseline_days if metric else 0,
                'is_deal': deal is not None, 'has_member_deals': any(c['id'] in by_id for c in members)})
        return {'cards': cards, 'groups': projected_groups, 'deals': deals}
