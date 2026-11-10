"""Market transport retries, cancellation and coalesced family session."""
import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock

from marketplace_connector.connectors.yandex_market.transport import YandexMarketTransport
from marketplace_connector.connectors.yandex_market.discovery import FamilySession
from marketplace_connector.domain.errors import MarketplaceUnavailable, RateLimited
from tests.test_ozon_json_transport import FakePage
from tests.test_yandex_market import SEED, html


def response(status=200, **overrides):
    return dict(status=status, contentType='text/html', text=html(),
                url='https://market.yandex.ru/card/tovar/' + SEED, **overrides)


class YandexTransportTests(unittest.IsolatedAsyncioTestCase):
    async def transport(self, fetch, **options):
        page = FakePage(fetch)
        prepare = AsyncMock()
        transport = YandexMarketTransport(MagicMock(new_page=AsyncMock(return_value=page)), prepare, **options)
        self.addAsyncCleanup(transport.close)
        return transport, page, prepare

    async def test_hundred_admitted_101_waits_cancel_is_independent(self):
        release = asyncio.Event()
        entered = asyncio.Event()
        async def fetch(arg):
            if len(page.calls) == 100:entered.set()
            await release.wait()
            return response()
        transport, page, prepare = await self.transport(fetch)
        tasks = [asyncio.create_task(transport.fetch(SEED)) for _ in range(101)]
        await asyncio.wait_for(entered.wait(), 2)
        self.assertEqual(transport.pool.pending, 1)
        self.assertEqual(transport.pool.in_flight, 100)
        tasks[0].cancel()
        with self.assertRaises(asyncio.CancelledError):await tasks[0]
        release.set()
        self.assertEqual(len(await asyncio.gather(*tasks[1:])), 100)
        self.assertEqual(prepare.await_count, 1)
        self.assertEqual(len(page.aborted), 1)
        self.assertEqual(transport.pool.in_flight, 0)

    async def test_200_challenge_recovery_and_bounded_errors(self):
        challenge = dict(response(), url='https://market.yandex.ru/showcaptcha')
        transport, _, prepare = await self.transport(AsyncMock(side_effect=[challenge, response()]))
        self.assertEqual(await transport.fetch(SEED), html())
        self.assertEqual(prepare.await_count, 2)
        for result, error in [(challenge, MarketplaceUnavailable), (response(500), MarketplaceUnavailable),
                              (response(429, retryAfter='999'), RateLimited), ({'error':'timeout'}, MarketplaceUnavailable)]:
            fetch = AsyncMock(return_value=result)
            transport, _, _ = await self.transport(fetch)
            with self.subTest(result=result.get('status')), self.assertRaises(error):
                await transport.fetch(SEED)
            self.assertLessEqual(fetch.await_count, 3)

    async def test_session_coalesces_overlapping_skus_and_clears_on_close(self):
        transport = AsyncMock()
        transport.fetch.side_effect = lambda sku: html(sku)
        session = FamilySession(transport)
        self.addAsyncCleanup(session.close)
        first, second = await asyncio.gather(session.get(SEED), session.get('5355099813'))
        self.assertEqual(len(first.variants), 64)
        self.assertEqual(len(second.variants), 64)
        self.assertEqual(transport.fetch.await_count, 64)

    async def test_failed_root_can_retry_in_same_session(self):
        calls = 0
        async def fetch(sku):
            nonlocal calls
            calls += 1
            if calls == 1: raise MarketplaceUnavailable('temporary')
            from copy import deepcopy
            from tests.test_yandex_market import FAMILY
            data = deepcopy(FAMILY[SEED])
            data['edges'] = []
            return html(data=data)
        session = FamilySession(AsyncMock(fetch=fetch))
        self.addAsyncCleanup(session.close)
        with self.assertRaises(MarketplaceUnavailable):await session.get(SEED)
        self.assertEqual((await session.get(SEED)).ref.external_id, SEED)

    async def test_hidden_challenge_does_not_prompt_and_visible_uses_shared_handler(self):
        from marketplace_connector.connectors.yandex_market.client import AsyncYandexMarketClient
        from unittest.mock import patch
        for hidden in (True, False):
            handler = MagicMock(handle_async=AsyncMock())
            client = AsyncYandexMarketClient('/tmp/unused-yandex-profile', headless=hidden, challenge_handler=handler)
            page = MagicMock(reload=AsyncMock(return_value=MagicMock(status=200)))
            with patch.object(client, '_wait_for_antibot_async', AsyncMock(return_value=True)):
                if hidden:
                    with self.assertRaises(MarketplaceUnavailable):
                        await client._handle_antibot_async(page, 'test', force=True)
                else:
                    await client._handle_antibot_async(page, 'test', force=True)
            self.assertEqual(handler.handle_async.await_count, 0 if hidden else 1)
            self.assertFalse(client.session.challenge_lock.locked())
