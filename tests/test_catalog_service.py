"""Catalog projection can be exercised from materialized inputs without a database."""
from dataclasses import replace
from datetime import datetime, timezone
from decimal import Decimal
import unittest

from marketplace_connector.domain.models import ProductRef
from price_watch.domain.models import TrackedCard, TrackedCardOverview
from price_watch.application.catalog_models import CatalogInputs, CatalogCardInput, CardMetrics, GroupMetadata
from price_watch.application.catalog_service import CatalogService

NOW = datetime(2026, 10, 26, tzinfo=timezone.utc)


def entry(card_id, price, *, availability='in_stock', average='100', minimum='40', enabled=True):
    local = TrackedCard(card_id, ProductRef('ozon', str(card_id)), 'Item', '', enabled, NOW, NOW, group_id=1)
    return CatalogCardInput(TrackedCardOverview(local, Decimal(price) if price is not None else None,
                                              availability, NOW),
                            CardMetrics(Decimal(minimum), Decimal(average), 1), 7)


class Reader:
    def __init__(self, inputs):
        self.inputs = inputs
        self.reads = 0

    async def read_catalog(self):
        self.reads += 1
        return self.inputs


class CatalogServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_representative_and_member_deal_have_separate_roles(self):
        reader = Reader(CatalogInputs((entry(1, '80', average='70', minimum='60'), entry(2, '90')),
                                     (GroupMetadata(1, 'Group', ('own',)), GroupMetadata(2, 'Empty', ()))))
        catalog = await CatalogService(reader).get_catalog()
        group, empty = catalog['groups']
        self.assertEqual(reader.reads, 1)
        self.assertEqual([deal['card']['id'] for deal in catalog['deals']], [2])
        self.assertEqual(group['representative_card_id'], 1)
        self.assertEqual(group['minimum_price'], Decimal('60'))
        self.assertIs(group['representative_card'], catalog['cards'][0])
        self.assertFalse(group['is_deal'])
        self.assertTrue(group['has_member_deals'])
        self.assertIsNone(group['savings'])
        self.assertEqual(group['tags'], ['own'])
        self.assertIsNone(empty['representative_card'])
        self.assertEqual(empty['baseline_days'], 0)
        self.assertFalse(empty['has_member_deals'])

    async def test_availability_does_not_replace_the_cheapest_representative(self):
        inputs = CatalogInputs((entry(2, '0', availability='unknown'), entry(1, '.01')),
                               (GroupMetadata(1, 'Group', ()),))
        group = (await CatalogService(Reader(inputs)).get_catalog())['groups'][0]
        self.assertEqual(group['representative_card_id'], 2)
        self.assertEqual(group['current_price'], Decimal(0))
        self.assertFalse(group['is_deal'])
        self.assertTrue(group['has_member_deals'])

    async def test_deal_order_exact_savings_and_collection_identity(self):
        inputs = CatalogInputs((entry(2, '1', average='1.001'), entry(1, '1', average='1.001')),
                               (GroupMetadata(1, 'Group', ()),))
        catalog = await CatalogService(Reader(inputs)).get_catalog()
        self.assertEqual([deal['card']['id'] for deal in catalog['deals']], [1, 2])
        self.assertEqual(catalog['deals'][0]['savings'], Decimal('.001'))
        self.assertEqual(catalog['deals'][0]['last_collection_run_id'], 7)
        self.assertEqual(catalog['groups'][0]['representative_card_id'], 1)
        self.assertEqual(catalog['groups'][0]['savings'], Decimal('.001'))

    async def test_disabled_representative_and_missing_prices(self):
        inputs = CatalogInputs((entry(2, None), entry(1, None)), (GroupMetadata(1, 'Group', ()),))
        result = await CatalogService(Reader(inputs)).get_catalog()
        self.assertEqual(result['groups'][0]['representative_card_id'], 1)
        self.assertEqual(result['deals'], [])
        disabled = entry(1, '20', enabled=False)
        result = await CatalogService(Reader(replace(inputs, cards=(disabled, entry(2, '30'))))).get_catalog()
        self.assertFalse(result['groups'][0]['is_deal'])
        self.assertTrue(result['groups'][0]['has_member_deals'])
