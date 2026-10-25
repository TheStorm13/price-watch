"""Cross-boundary price and product contracts, independent of Ozon and user data."""
import asyncio
from contextlib import asynccontextmanager
from dataclasses import fields
from datetime import datetime, timezone
from decimal import Decimal
import json
from pathlib import Path
import unittest

from marketplace_connector import Availability, ConnectorRegistry, MarketplaceCard, ProductRef, ProductService
from marketplace_connector.connectors.ozon.connector import OzonConnector
from marketplace_connector.connectors.ozon.models import OzonResponse, OzonProductData
from marketplace_connector.connectors.ozon.parser import OzonProductParser
from marketplace_connector.connectors.ozon.mapper import OzonMapper
from marketplace_connector.domain.money import normalize_price
from marketplace_connector.domain.errors import MarketplaceSchemaChanged
from marketplace_connector.serialization import card_to_dict, card_to_json
from price_watch.api.schemas import CardResponse, StatisticsResponse, TransferHistoryPoint
from price_watch.domain.models import TrackedCard


class DecimalContractTests(unittest.TestCase):
    def test_price_normalization_and_range(self):
        self.assertEqual(normalize_price(Decimal('199.995')), Decimal('200.00'))
        self.assertEqual(normalize_price(Decimal('0.005')), Decimal('0.01'))
        self.assertEqual(normalize_price(Decimal('999999999999.99')), Decimal('999999999999.99'))
        self.assertEqual(normalize_price(Decimal('-0')), Decimal('0.00'))
        for value in (True, 1.1, '1.10', Decimal('NaN'), Decimal('Infinity'), Decimal('-0.001'), Decimal('999999999999.995')):
            with self.subTest(value=value), self.assertRaises(ValueError):
                normalize_price(value)

    def test_specific_model_and_nested_literals_never_round_through_float(self):
        raw = '''{"widgetStates":{"webProductHeading-1":"{\\"title\\":\\"Item\\"}",
            "webPrice-1":"{\\"isAvailable\\":true,\\"cardPrice\\":199.995}"},
            "pageInfo":{"analyticsInfo":{"sku":"123"}}}'''
        data = OzonProductParser.parse(raw, expected_external_id='123')
        self.assertIsInstance(data, OzonProductData)
        card = OzonMapper.to_card(data)
        self.assertEqual(card.price, Decimal('200.00'))
        self.assertIsInstance(card.price, Decimal)
        self.assertNotIn('id', {field.name for field in fields(card)})
        self.assertNotIn('tags', {field.name for field in fields(card)})
        with self.assertRaises(MarketplaceSchemaChanged):
            OzonMapper.to_card(OzonProductParser.parse(raw, expected_external_id='456'))

    def test_schema_and_full_or_partial_serialization_agree(self):
        schema = json.loads(Path('marketplace_connector/serialization/product.schema.json').read_text())
        for availability, price in [(Availability.IN_STOCK, Decimal('199.9')), (Availability.UNKNOWN, None),
                                     (Availability.OUT_OF_STOCK, Decimal('123'))]:
            card = MarketplaceCard(ProductRef('fixture', '1'), 'Item', '', availability, price=price)
            payload = json.loads(card_to_json(card))
            self.assertEqual(payload['schema_version'], '2.0')
            self.assertEqual(payload['price'], '199.90' if availability == Availability.IN_STOCK else None)
            self.assertEqual(set(payload), set(schema['properties']))
            self.assertTrue(set(schema['required']) <= set(payload))
            self.assertEqual(payload, card_to_dict(card))

    def test_decimal_schema_and_import_accept_exact_strings_only(self):
        point = TransferHistoryPoint(price='199.90', availability='in_stock', observed_at=datetime.now(timezone.utc))
        self.assertEqual(point.price, Decimal('199.90'))
        self.assertEqual(point.model_dump(mode='json')['price'], '199.90')
        self.assertEqual(CardResponse.model_json_schema(mode='serialization')['properties']['currentPrice']['anyOf'][0]['type'], 'string')
        input_schema = TransferHistoryPoint.model_json_schema(mode='validation')['properties']['price']
        self.assertEqual([item['type'] for item in input_schema['anyOf']], ['string', 'null'])
        for price in (199.9, 199, True):
            with self.subTest(price=price), self.assertRaises(ValueError):
                TransferHistoryPoint(price=price, availability='in_stock', observed_at=datetime.now(timezone.utc))

    def test_raw_cli_keeps_exact_text_and_output(self):
        import argparse
        import io
        from tempfile import TemporaryDirectory
        from unittest.mock import patch, AsyncMock
        from marketplace_connector.connectors.ozon.cli import _run
        text = '{ "widgetStates": {}, "value": 199.995 }'
        with TemporaryDirectory() as directory:
            target = Path(directory)/'raw.json'
            args = argparse.Namespace(profile_dir=Path(directory), chrome_binary=None,
                chrome_platform='x11', raw=True, output=target, article='123')
            with patch('marketplace_connector.connectors.ozon.cli.AsyncOzonClient') as client, patch('sys.stdout', new_callable=io.StringIO) as out:
                client.return_value.fetch_raw_text_async = AsyncMock(return_value=text)
                self.assertEqual(asyncio.run(_run(args)), 0)
                self.assertEqual(out.getvalue(), text+'\n')
            self.assertEqual(target.read_text(), text+'\n')

    def test_same_product_type_for_two_distinct_adapters(self):
        class OtherConnector:
            marketplace = 'other'
            @asynccontextmanager
            async def collection_session(self): yield
            async def get_product(self, external_id):
                # A different marketplace representation is converted locally.
                response = {'code': external_id, 'label': 'Other', 'amount': '12.34'}
                return MarketplaceCard(ProductRef(self.marketplace, response['code']), response['label'], '',
                                     Availability.IN_STOCK, price=Decimal(response['amount']))
        class Client:
            async def fetch_product_async(self, external_id):
                return OzonResponse(external_id, '{"widgetStates":{"webProductHeading-1":{"title":"Ozon"},"webPrice-1":{"cardPrice":"12.34","isAvailable":true}},"pageInfo":{"analyticsInfo":{"sku":"1"}}}', datetime.now(timezone.utc))
            @asynccontextmanager
            async def collection_session(self): yield
        async def check():
            service = ProductService(ConnectorRegistry([OzonConnector(Client()), OtherConnector()]))
            products = [await service.get_product(marketplace, '1') for marketplace in ('ozon', 'other')]
            self.assertEqual([type(product) for product in products], [MarketplaceCard, MarketplaceCard])
            self.assertEqual([product.price for product in products], [Decimal('12.34')]*2)
        asyncio.run(check())
