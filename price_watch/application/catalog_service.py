"""Build catalog projections from one materialized snapshot and shared rules."""
from ..domain.catalog_rules import deal_savings, representative_id
from ..ports.catalog import CatalogReader
from .catalog_models import CatalogCard, CatalogDeal, CatalogGroup, CatalogSnapshot


class CatalogService:
    def __init__(self, reader: CatalogReader):
        self._reader = reader

    async def get_catalog(self) -> CatalogSnapshot:
        inputs = await self._reader.read_catalog()
        cards: list[CatalogCard] = []
        deals: list[CatalogDeal] = []
        grouped: dict[int | None, list[CatalogCard]] = {}
        metrics = {}
        for entry in inputs.cards:
            overview, metric = entry.overview, entry.metrics
            local = overview.card
            metrics[local.id] = metric
            card: CatalogCard = {
                'primary_variant_id': local.primary_variant_id, 'last_collected_at': local.last_collected_at,
                'id': local.id, 'marketplace': local.ref.marketplace, 'external_id': local.ref.external_id,
                'title': local.title, 'url': local.url, 'image_url': local.image_url,
                'deals_enabled': local.deals_enabled, 'group_id': local.group_id, 'tags': local.tags,
                'created_at': local.created_at, 'updated_at': local.updated_at,
                'current_price': overview.current_price, 'current_availability': overview.current_availability,
                'last_observed_at': overview.last_observed_at,
                'minimum_price': metric.minimum_price, 'average_price': metric.average_price,
            }
            cards.append(card)
            grouped.setdefault(local.group_id, []).append(card)
            savings = deal_savings(enabled=local.deals_enabled, price=overview.current_price,
                                   availability=overview.current_availability,
                                   average=metric.average_price, baseline_days=metric.baseline_days)
            if savings is not None:
                assert metric.average_price is not None
                deals.append({'card': card, 'average_price': metric.average_price, 'savings': savings,
                              'baseline_days': metric.baseline_days,
                              'last_collection_run_id': entry.last_collection_run_id})
        deals.sort(key=lambda deal: (-deal['savings'], deal['card']['id']))
        by_id = {deal['card']['id']: deal for deal in deals}
        projected_groups: list[CatalogGroup] = []
        for group in inputs.groups:
            members = grouped.get(group.id, [])
            chosen = representative_id((card['id'], card['current_price']) for card in members)
            representative = next((card for card in members if card['id'] == chosen), None)
            metric = metrics[chosen] if chosen is not None else None
            deal = by_id.get(chosen) if chosen is not None else None
            projected_groups.append({
                'id': group.id, 'name': group.name, 'tags': list(group.tags),
                'card_ids': sorted(card['id'] for card in members),
                'representative_card_id': chosen, 'representative_card': representative,
                'current_price': representative['current_price'] if representative else None,
                'minimum_price': metric.minimum_price if metric else None,
                'savings': deal['savings'] if deal else None,
                'baseline_days': metric.baseline_days if metric else 0,
                'is_deal': deal is not None,
                'has_member_deals': any(card['id'] in by_id for card in members),
            })
        return {'cards': cards, 'groups': projected_groups, 'deals': deals}
