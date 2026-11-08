"""Adapter parsing stays strict and runs once across the complete connector path."""
import json
import unittest
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from marketplace_connector.connectors.ozon.async_client import AsyncOzonClient
from marketplace_connector.connectors.ozon.connector import OzonConnector
from marketplace_connector.connectors.ozon.json_transport import OzonJsonTransport
from marketplace_connector.connectors.ozon.mapper import OzonMapper
from marketplace_connector.connectors.ozon.parser import OzonProductParser
from marketplace_connector.connectors.aliexpress.client import AsyncAliExpressClient
from marketplace_connector.connectors.aliexpress.connector import AliExpressConnector
from marketplace_connector.connectors.aliexpress.json_transport import AliExpressJsonTransport
from marketplace_connector.connectors.aliexpress.mapper import AliExpressMapper
from marketplace_connector.connectors.aliexpress.parser import AliExpressProductParser
from marketplace_connector.domain.errors import ProductNotFound, MarketplaceSchemaChanged, UnsafeBrowserTeardown
from tests.test_ozon_json_transport import FakePage, response
from tests.test_aliexpress_transport import FakePage as AliPage, response as ali_response, RAW, REF


class ConnectorPipelineTests(unittest.IsolatedAsyncioTestCase):
    async def test_each_adapter_decodes_parses_and_maps_once(self):
        raw = ' {"widgetStates":{"webProductHeading-1":"{\\"title\\":\\"Exact\\"}","webPrice-1":{"cardPrice":199.995,"isAvailable":true}}} '
        cases = [
            (AsyncOzonClient, OzonConnector, OzonJsonTransport, OzonProductParser, OzonMapper, FakePage, response(text=raw), '1', raw, 2, '200.00'),
            (AsyncAliExpressClient, AliExpressConnector, AliExpressJsonTransport, AliExpressProductParser, AliExpressMapper, AliPage, ali_response(), REF, RAW, 1, '77648.00'),
        ]
        for client_type, connector_type, transport_type, parser, mapper, page_type, result, ref, text, decodes, price in cases:
            for raw_mode in (False, True):
                with self.subTest(client=client_type.__name__, raw=raw_mode):
                    page = page_type(AsyncMock(return_value=result))
                    transport = transport_type(MagicMock(new_page=AsyncMock(return_value=page)), AsyncMock())
                    self.addAsyncCleanup(transport.close)
                    client = client_type('/tmp/unused-profile')
                    @asynccontextmanager
                    async def session(): yield transport
                    with (patch.object(client, '_request_session', session),
                          patch.object(parser, 'parse', wraps=parser.parse) as parse,
                          patch.object(mapper, 'to_card', wraps=mapper.to_card) as map_card,
                          patch('json.loads', wraps=json.loads) as decode):
                        if raw_mode:
                            self.assertEqual(await client.fetch_raw_text_async(ref), text)
                        else:
                            card = await connector_type(client).get_product(ref)
                            self.assertEqual(str(card.price), price)
                            self.assertEqual(card.ref.external_id, ref)
                        self.assertEqual(parse.call_count, 1)
                        self.assertEqual(map_card.call_count, 1)
                        self.assertEqual(decode.call_count, decodes)

    async def test_raw_absence_remains_document_product_mode_raises(self):
        raw = ' {"widgetStates":{},"pageInfo":{"pageType":"search","url":"/search/?product_id=1"}} '
        transport = MagicMock(fetch=AsyncMock(return_value=raw))
        client = AsyncOzonClient('/tmp/unused-profile')
        @asynccontextmanager
        async def session(): yield transport
        with patch.object(client, '_request_session', session):
            self.assertEqual(await client.fetch_raw_text_async('1'), raw)
            with self.assertRaises(ProductNotFound):
                await OzonConnector(client).get_product('1')

    async def test_raw_validation_rejects_trailing_data_and_nested_nonfinite_widgets(self):
        client = AsyncOzonClient('/tmp/unused-profile')
        for raw in ['prefix {"widgetStates":{}}', '{"widgetStates":{}} trailing',
                    '{"widgetStates":{"webProductHeading-1":{"title":"x"},"webPrice-1":"{\\"cardPrice\\":NaN}"}}',
                    '{"widgetStates":{"webProductHeading-1":{"title":"x"},"webGallery-1":null}}']:
            transport = MagicMock(fetch=AsyncMock(return_value=raw))
            @asynccontextmanager
            async def session(): yield transport
            with patch.object(client, '_request_session', session), self.assertRaises(MarketplaceSchemaChanged):
                await client.fetch_raw_text_async('1')

    async def test_discovery_does_not_move_price_collection_time(self):
        from tests.test_ozon_aspects import SKU, product, modal
        received = datetime(2026, 1, 2, tzinfo=timezone.utc)
        client = AsyncOzonClient('/tmp/unused-profile')
        transport = MagicMock(fetch=AsyncMock(side_effect=[product(), modal()]))
        @asynccontextmanager
        async def session(): yield transport
        with (patch.object(client, '_request_session', session),
              patch('marketplace_connector.connectors.ozon.async_client.datetime') as clock):
            clock.now.return_value = received
            card = await OzonConnector(client).get_product(SKU)
            self.assertEqual(card.collected_at, received)
            clock.now.assert_called_once_with(timezone.utc)
            self.assertEqual(len(card.variants), 10)

    async def test_real_ozon_discovery_failure_stops_run_before_next_stage(self):
        from dataclasses import replace
        from tests.test_collection_service import FakeRepository, Connector, card
        from tests.test_ozon_aspects import SKU, product
        from marketplace_connector.application.product_service import ConnectorRegistry
        from marketplace_connector.domain.models import ProductRef
        from price_watch.application.run_executor import RunExecutor
        transport = MagicMock(fetch=AsyncMock(side_effect=[product(), UnsafeBrowserTeardown('unknown I/O')]))
        client = AsyncOzonClient('/tmp/unused-profile')
        @asynccontextmanager
        async def session(): yield transport
        ali = Connector()
        ali.marketplace = 'aliexpress'
        repo = FakeRepository([replace(card(1), ref=ProductRef('ozon', SKU)),
                               replace(card(2), ref=ProductRef('aliexpress', '2'))])
        async def factory(run): return ConnectorRegistry([OzonConnector(client), ali])
        with patch.object(client, '_request_session', session), patch.object(client, 'collection_session', session):
            with self.assertRaises(UnsafeBrowserTeardown):
                await RunExecutor(repo, factory).collect()
        self.assertEqual(ali.opens, 0)
        self.assertEqual(repo.run.status, 'failed')
        self.assertEqual(transport.fetch.await_count, 2)

    async def test_transport_retry_budget_cannot_be_bypassed_by_application_retry(self):
        from marketplace_connector.application.retry import fetch_with_retry
        from marketplace_connector.domain.errors import RateLimited
        cases = [(OzonJsonTransport, FakePage, response(status=429, text='{}')),
                 (AliExpressJsonTransport, AliPage, ali_response(status=429))]
        for kind, page_type, value in cases:
            value['retryAfter'] = '1'
            page = page_type(AsyncMock(return_value=value))
            transport = kind(MagicMock(new_page=AsyncMock(return_value=page)), AsyncMock(), max_retry_wait=.01)
            self.addAsyncCleanup(transport.close)
            with patch('marketplace_connector.application.retry.sleep', new_callable=AsyncMock) as sleep:
                with self.assertRaises(RateLimited) as caught:
                    await fetch_with_retry(lambda: transport.fetch(REF if kind is AliExpressJsonTransport else '1'))
            self.assertFalse(caught.exception.retry_allowed)
            sleep.assert_not_awaited()
            self.assertEqual(len(page.calls), 1)

    async def test_malformed_aspect_rows_have_schema_error_in_both_modes(self):
        client = AsyncOzonClient('/tmp/unused-profile')
        raw = '{"widgetStates":{"webProductHeading-1":{"title":"x"},"webAspects-1":{"aspects":[1]}}}'
        transport = MagicMock(fetch=AsyncMock(return_value=raw))
        @asynccontextmanager
        async def session(): yield transport
        with patch.object(client, '_request_session', session):
            for fetch in (client.fetch_raw_text_async, client.fetch_product_async):
                with self.assertRaises(MarketplaceSchemaChanged): await fetch('1')
