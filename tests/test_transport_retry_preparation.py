"""Outer attempts can recover temporary bootstrap failures without retry storms."""
import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from marketplace_connector.connectors.ozon.json_transport import OzonJsonTransport
from marketplace_connector.connectors.aliexpress.json_transport import AliExpressJsonTransport
from marketplace_connector.domain.errors import MarketplaceUnavailable, MarketplaceSchemaChanged, RateLimited
from tests.test_ozon_json_transport import FakePage, response as ozon_response
from tests.test_aliexpress_transport import response as ali_response, REF
from marketplace_connector.application.retry import fetch_with_retry


class PreparationRetryTests(unittest.IsolatedAsyncioTestCase):
    async def test_aliexpress_failed_initial_navigation_does_not_force_manual_recovery(self):
        from marketplace_connector.connectors.aliexpress.client import AsyncAliExpressClient
        client = AsyncAliExpressClient('/tmp/unused-retry-profile')
        page = MagicMock(url='https://aliexpress.ru/')
        page.goto = AsyncMock(side_effect=[TimeoutError('temporary navigation'), MagicMock(status=200)])
        client._is_antibot_page_async = AsyncMock(return_value=False)
        client._handle_antibot_async = AsyncMock()
        with self.assertRaises(TimeoutError):
            await client._prepare_storefront(page)
        self.assertFalse(client._storefront_prepared)
        await client._prepare_storefront(page)
        self.assertTrue(client._storefront_prepared)
        client._handle_antibot_async.assert_not_awaited()

    async def test_outer_attempt_retains_three_inner_attempts(self):
        for failures in (3, 6):
            with self.subTest(failures=failures):
                replies = [{'error': 'network'} for _ in range(failures)] + [ali_response()]
                page = FakePage(AsyncMock(side_effect=replies))
                transport = AliExpressJsonTransport(MagicMock(new_page=AsyncMock(return_value=page)),
                    AsyncMock(), max_retry_wait=.001, starts_per_second=10000)
                try:
                    with patch('marketplace_connector.application.retry.sleep', new_callable=AsyncMock) as sleep:
                        if failures == 3:
                            self.assertEqual(await fetch_with_retry(lambda: transport.fetch(REF)), ali_response()['text'])
                        else:
                            with self.assertRaises(MarketplaceUnavailable):
                                await fetch_with_retry(lambda: transport.fetch(REF))
                    self.assertEqual(len(page.calls), 4 if failures == 3 else 6)
                    sleep.assert_awaited_once_with(1)
                finally:
                    await transport.close()

    async def test_concurrent_failed_bootstrap_is_replaced_once_on_next_attempt(self):
        for cls, reply, external_id in [(OzonJsonTransport, ozon_response(), '1'),
                                        (AliExpressJsonTransport, ali_response(), REF)]:
            with self.subTest(marketplace=cls.__name__):
                entered, release = asyncio.Event(), asyncio.Event()
                count = 0
                async def prepare(page):
                    nonlocal count
                    count += 1
                    if count == 1:
                        entered.set()
                        await release.wait()
                        raise MarketplaceUnavailable('temporary preparation')
                failed, ready = [FakePage(AsyncMock(return_value=reply)) for _ in range(2)]
                context = MagicMock(new_page=AsyncMock(side_effect=[failed, ready]))
                transport = cls(context, prepare, concurrency=5, starts_per_second=1000)
                try:
                    tasks = [asyncio.create_task(transport.fetch(external_id)) for _ in range(5)]
                    await asyncio.wait_for(entered.wait(), 1)
                    release.set()
                    results = await asyncio.gather(*tasks, return_exceptions=True)
                    self.assertTrue(all(isinstance(result, MarketplaceUnavailable) for result in results))
                    self.assertEqual(count, 1)
                    failed.close.assert_awaited_once()
                    self.assertEqual(failed.calls, [])
                    results = await asyncio.gather(*(transport.fetch(external_id) for _ in range(5)))
                    self.assertEqual(results, [reply['text']] * 5)
                    self.assertEqual(count, 2)
                    self.assertEqual(context.new_page.await_count, 2)
                    self.assertEqual(len(ready.calls), 5)
                finally:
                    await transport.close()

    async def test_schema_preparation_error_is_not_reset_as_temporary(self):
        for cls in (OzonJsonTransport, AliExpressJsonTransport):
            with self.subTest(marketplace=cls.__name__):
                page = FakePage(AsyncMock())
                prepare = AsyncMock(side_effect=MarketplaceSchemaChanged('broken preparation'))
                transport = cls(MagicMock(new_page=AsyncMock(return_value=page)), prepare)
                try:
                    for _ in range(2):
                        with self.assertRaises(MarketplaceSchemaChanged):
                            await transport.fetch('1')
                    self.assertEqual(prepare.await_count, 1)
                    page.close.assert_awaited_once()
                finally:
                    await transport.close()

    async def test_aliexpress_challenge_429_preserves_retry_after(self):
        page = FakePage(AsyncMock(return_value=ali_response(429, '<html>_____tmd_____</html>', retryAfter='60')))
        prepare = AsyncMock()
        transport = AliExpressJsonTransport(MagicMock(new_page=AsyncMock(return_value=page)), prepare)
        try:
            with self.assertRaises(RateLimited) as caught:
                await transport.fetch(REF)
            self.assertGreater(caught.exception.retry_after, 59)
            self.assertEqual(len(page.calls), 1)
            self.assertEqual(prepare.await_count, 2)
        finally:
            await transport.close()
