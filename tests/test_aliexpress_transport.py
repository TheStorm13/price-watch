"""AliExpress transport policy using synthetic responses and cancellable fetches."""
import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock
from pathlib import Path
from marketplace_connector.connectors.aliexpress.json_transport import AliExpressJsonTransport, API_PATH, HOME_URL
from marketplace_connector.domain.errors import MarketplaceSchemaChanged, MarketplaceUnavailable, RateLimited, InvalidProductId
from tests.test_ozon_json_transport import FakePage

REF = '1005009868651525:12000061135122688'
RAW = (Path(__file__).parent / 'fixtures/aliexpress/product-data.json').read_text()


def response(status=200, text=RAW, **kwargs):
    return dict(status=status, text=text, contentType='application/json', url=HOME_URL.rstrip('/')+API_PATH, **kwargs)


class AliExpressTransportTests(unittest.IsolatedAsyncioTestCase):
    async def transport(self, fetch=None, prepare=None, **kwargs):
        page = FakePage(fetch or AsyncMock(return_value=response()))
        transport = AliExpressJsonTransport(MagicMock(new_page=AsyncMock(return_value=page)), prepare or AsyncMock(), **kwargs)
        self.addAsyncCleanup(transport.close)
        return transport, page

    async def test_five_overlap_exact_identity_and_independent_cancel(self):
        entered, release = asyncio.Event(), asyncio.Event()
        async def fetch(arg):
            if len(page.calls) == 5: entered.set()
            await release.wait()
            return response()
        transport, page = await self.transport(fetch, concurrency=5)
        tasks = [asyncio.create_task(transport.fetch(REF)) for _ in range(5)]
        await asyncio.wait_for(entered.wait(), 1)
        tasks[0].cancel()
        with self.assertRaises(asyncio.CancelledError): await tasks[0]
        self.assertFalse(tasks[1].done())
        release.set()
        self.assertEqual(await asyncio.gather(*tasks[1:]), [RAW]*4)
        self.assertEqual(len(page.aborted), 1)
        self.assertEqual(page.calls[0]['url'], HOME_URL.rstrip('/')+API_PATH+'?productId=1005009868651525&sourceId=0&sku_id=12000061135122688')

    async def test_retry_after_cooldown_and_long_pause(self):
        times=[]
        async def fetch(arg):
            times.append(asyncio.get_running_loop().time())
            return response(429, retryAfter='1') if len(times)==1 else response()
        transport, _ = await self.transport(fetch)
        self.assertEqual(await transport.fetch(REF), RAW)
        self.assertGreaterEqual(times[1]-times[0], .95)
        transport, _ = await self.transport(AsyncMock(return_value=response(429, retryAfter='999')))
        with self.assertRaises(RateLimited): await transport.fetch(REF)

    async def test_challenge_recovery_once_including_429_html(self):
        prepare = AsyncMock()
        fetch = AsyncMock(side_effect=[response(429, '<html>_____tmd_____</html>'),response()])
        transport, _ = await self.transport(fetch, prepare)
        self.assertEqual(await transport.fetch(REF), RAW)
        self.assertEqual(prepare.await_count, 2)
        transport, _ = await self.transport(AsyncMock(return_value=response(200,'<html>captcha</html>')))
        with self.assertRaises(MarketplaceUnavailable): await transport.fetch(REF)

    async def test_schema_http_timeout_and_no_sku(self):
        for result, error in [(response(404),MarketplaceUnavailable), (response(text='{}'),MarketplaceSchemaChanged),
                              ({'error':'timeout'},MarketplaceUnavailable),
                              (dict(response(), contentType='text/plain'),MarketplaceSchemaChanged)]:
            transport, _ = await self.transport(AsyncMock(return_value=result), max_attempts=1)
            with self.subTest(result=result.get('status')), self.assertRaises(error): await transport.fetch(REF)

    async def test_product_only_fetch_omits_sku_and_returns_discovery(self):
        from urllib.parse import parse_qs, urlsplit
        fetch = AsyncMock(return_value=response())
        transport, _ = await self.transport(fetch)
        self.assertEqual(await transport.fetch(REF.split(':')[0]), RAW)
        params = parse_qs(urlsplit(fetch.call_args.args[0]['url']).query)
        self.assertEqual(params['productId'], [REF.split(':')[0]])
        self.assertNotIn('sku_id', params)

    async def test_recovery_waits_for_active_neighbor(self):
        blocked,release=asyncio.Event(),asyncio.Event()
        counts=[]
        active=0
        calls=0
        async def prepare(page):counts.append(active)
        async def fetch(arg):
            nonlocal active,calls
            calls+=1
            current=calls
            active+=1
            try:
                if current==1:
                    await blocked.wait()
                    return response(403)
                if current==2:
                    blocked.set()
                    await release.wait()
                return response()
            finally:active-=1
        transport,_=await self.transport(fetch,prepare,concurrency=2)
        tasks=[asyncio.create_task(transport.fetch(REF)) for _ in range(2)]
        await asyncio.wait_for(blocked.wait(),1)
        await asyncio.sleep(.02)
        self.assertEqual(counts,[0])
        release.set()
        self.assertEqual(await asyncio.gather(*tasks),[RAW,RAW])
        self.assertEqual(counts,[0,0])

    async def test_database_free_product_service(self):
        from marketplace_connector import ConnectorRegistry,ProductService
        from marketplace_connector.connectors.aliexpress.connector import AliExpressConnector
        from marketplace_connector.connectors.aliexpress.models import AliExpressResponse
        from datetime import datetime,timezone
        client=MagicMock(fetch_product_async=AsyncMock(return_value=AliExpressResponse(REF,RAW,datetime.now(timezone.utc))))
        service=ProductService(ConnectorRegistry([AliExpressConnector(client)]))
        self.assertEqual(str((await service.get_product('aliexpress',REF)).price),'77648.00')
