"""Reduced live modal structures; synthetic transport failures and exact prices."""
import asyncio
import copy
import io
import json
import os
import unittest
from contextlib import asynccontextmanager, redirect_stdout
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from unittest.mock import AsyncMock, MagicMock, patch

from marketplace_connector.connectors.ozon.aspects import complete_aspects
from marketplace_connector.connectors.ozon.async_client import AsyncOzonClient
from marketplace_connector.connectors.ozon.connector import OzonConnector
from marketplace_connector.connectors.ozon.json_transport import OzonJsonTransport
from tests.test_ozon_json_transport import FakePage, response

SKU = '410630078'
FIXTURE = json.loads((Path(__file__).parent / 'fixtures/ozon/aspects-modal.json').read_text())


def product():
    return json.dumps({'pageInfo': {'analyticsInfo': {'sku': SKU}}, 'widgetStates': {
        'webProductHeading-1': {'title': 'Exact product'},
        'webPrice-1': {'cardPrice': '123.45', 'isAvailable': True},
        'webAspects-1': FIXTURE['source']}})


def modal(value=None):
    return json.dumps({'widgetStates': {'webAspectsModal-1': value or FIXTURE['modal']}})


class OzonAspectTests(unittest.IsolatedAsyncioTestCase):
    async def test_observed_ten_variants_keep_exact_selected_metadata_and_raw(self):
        raw = product()
        client = AsyncOzonClient('/tmp/unused-profile')
        transport = MagicMock(fetch=AsyncMock(side_effect=[raw, modal(), raw]))
        @asynccontextmanager
        async def session():
            yield transport
        with patch.object(client, '_request_session', session):
            card = await OzonConnector(client).get_product(SKU)
            self.assertEqual(str(card.price), '123.45')
            self.assertEqual(card.title, 'Exact product')
            self.assertEqual(len(card.variants), 10)
            self.assertEqual(card.extensions, {})
            raw_result = await client.fetch_raw_text_async(SKU)
        self.assertEqual(raw_result, raw)
        self.assertEqual(transport.fetch.await_count, 3)
        self.assertIn('modal_link', transport.fetch.await_args_list[1].kwargs)
        self.assertEqual(FIXTURE['source']['aspects'][0]['variants'][0],
                         next(v for v in (await complete_aspects(FIXTURE['source'], SKU, AsyncMock(return_value=modal())))[0]['aspects'][0]['variants']
                              if v['sku'] == FIXTURE['source']['aspects'][0]['variants'][0]['sku']))

    async def test_tracking_only_does_not_fetch_or_report_incomplete(self):
        source = copy.deepcopy(FIXTURE['source'])
        source['aspects'][0]['aspectModalInfo'] = {'trackingInfo': {}}
        fetch = AsyncMock()
        result, error = await complete_aspects(source, SKU, fetch)
        self.assertIsNone(error)
        self.assertNotIn('aspectModalInfo', result['aspects'][0])
        fetch.assert_not_awaited()

    async def test_wrong_origin_identity_short_list_and_unknown_continuation_stay_visible(self):
        for failure in ('external', 'wrong_sku', 'missing_link', 'count', 'missing_widget', 'incomplete', 'unknown'):
            source, expanded = copy.deepcopy(FIXTURE['source']), copy.deepcopy(FIXTURE['modal'])
            info = source['aspects'][0]['aspectModalInfo']
            body = modal(expanded)
            if failure == 'external': info['link'] = 'https://evil.test/modal/aspectsNew?product_id='+SKU
            if failure == 'wrong_sku': info['link'] = info['link'].replace(SKU, '123')
            if failure == 'missing_link': info.pop('link')
            if failure == 'count': info['realNumberOfVariants'] = '501'
            if failure == 'missing_widget': body = '{}'
            if failure == 'incomplete':
                expanded['aspects'][0]['variants'].pop()
                body = modal(expanded)
            if failure == 'unknown':
                expanded['nextPage'] = '/more'
                body = modal(expanded)
            with self.subTest(failure=failure):
                result, error = await complete_aspects(source, SKU, AsyncMock(return_value=body))
                self.assertIsNotNone(error)
                self.assertEqual(result['aspects'][0]['variants'], source['aspects'][0]['variants'])

    async def test_modal_failure_preserves_inline_and_next_call_can_succeed(self):
        fetch = AsyncMock(side_effect=[RuntimeError('network'), modal()])
        first, error = await complete_aspects(FIXTURE['source'], SKU, fetch)
        self.assertIn('network', error)
        self.assertEqual(len(first['aspects'][0]['variants']), 6)
        second, error = await complete_aspects(FIXTURE['source'], SKU, fetch)
        self.assertIsNone(error)
        self.assertEqual(len(second['aspects'][0]['variants']), 10)

    async def test_duplicate_links_fetch_once_and_cancellation_propagates(self):
        source = copy.deepcopy(FIXTURE['source'])
        source['aspects'].append(copy.deepcopy(source['aspects'][0]))
        fetch = AsyncMock(return_value=modal())
        _, error = await complete_aspects(source, SKU, fetch)
        self.assertIsNone(error)
        fetch.assert_awaited_once()
        with self.assertRaises(asyncio.CancelledError):
            await complete_aspects(FIXTURE['source'], SKU, AsyncMock(side_effect=asyncio.CancelledError))

    async def test_modal_uses_transport_retry_and_correct_composer_link(self):
        calls = []
        async def fetch(arg):
            path = parse_qs(urlsplit(arg['url']).query)['url'][0]
            calls.append(path)
            return response(status=503) if len(calls) == 1 else response(text=modal())
        page = FakePage(fetch)
        transport = OzonJsonTransport(MagicMock(new_page=AsyncMock(return_value=page)), AsyncMock())
        self.addAsyncCleanup(transport.close)
        link = FIXTURE['source']['aspects'][0]['aspectModalInfo']['link']
        result = await transport.fetch(SKU, modal_link=link)
        self.assertEqual(result, modal())
        self.assertEqual(calls, [link, link])

    async def test_numeric_and_raw_have_no_database_and_different_modal_work(self):
        from marketplace_connector.connectors.ozon import cli
        for raw in (False, True):
            client = AsyncOzonClient('/tmp/unused-profile')
            transport = MagicMock(fetch=AsyncMock(side_effect=[product(), modal()]))
            @asynccontextmanager
            async def session():
                yield transport
            output = io.StringIO()
            args = cli.build_parser().parse_args([SKU, *(['--raw'] if raw else [])])
            with (patch.dict(os.environ, {}, clear=True), patch.object(cli, 'AsyncOzonClient', return_value=client),
                  patch.object(client, '_request_session', session), patch.object(client, 'collection_session', session), redirect_stdout(output)):
                self.assertEqual(await cli._run(args), 0)
            result = json.loads(output.getvalue())
            self.assertEqual(transport.fetch.await_count, 1 if raw else 2)
            self.assertEqual(len(result['widgetStates']['webAspects-1']['aspects'][0]['variants']) if raw else len(result['variants']), 6 if raw else 10)
