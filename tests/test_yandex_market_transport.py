"""Market transport retries, cancellation and coalesced family session."""
import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock

from marketplace_connector.connectors.yandex_market.transport import YandexMarketTransport, FETCH_SCRIPT
from marketplace_connector.connectors.yandex_market.discovery import FamilySession
from marketplace_connector.domain.errors import AuthenticationRequired, MarketplaceUnavailable, RateLimited
from tests.test_ozon_json_transport import FakePage
from tests.test_yandex_market import SEED, html, external_family_html


def response(status=200, **overrides):
    return dict(status=status, contentType='text/html', text=html(),
                url='https://market.yandex.ru/card/tovar/' + SEED, **overrides)


class YandexTransportTests(unittest.IsolatedAsyncioTestCase):
    async def transport(self, fetch, **options):
        page = FakePage(fetch, fetch_script=FETCH_SCRIPT)
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

    async def test_empty_200_retries_only_that_request_and_is_not_auth_failure(self):
        for text in ('', '<!DOCTYPE html>', '<!DOCTYPE html><html><script>' + 'x' * 200000 + '</script>'):
            stub = dict(response(), text=text)
            fetch = AsyncMock(side_effect=[stub, response()])
            transport, _, prepare = await self.transport(fetch)
            with self.subTest(response_length=len(text)):
                self.assertEqual(await transport.fetch(SEED), html())
                self.assertEqual(fetch.await_count, 2)
                self.assertEqual(prepare.await_count, 1)
        fetch = AsyncMock(return_value=stub)
        transport, _, _ = await self.transport(fetch)
        with self.assertRaisesRegex(MarketplaceUnavailable, 'незавершённый'):
            await transport.fetch(SEED)
        self.assertEqual(fetch.await_count, 3)

    async def test_session_coalesces_overlapping_skus_and_clears_on_close(self):
        transport = AsyncMock()
        transport.fetch.side_effect = lambda sku: html(sku)
        session = FamilySession(transport)
        self.addAsyncCleanup(session.close)
        first, second = await asyncio.gather(session.get(SEED), session.get('5355099813'))
        self.assertEqual(len(first.variants), 64)
        self.assertEqual(len(second.variants), 64)
        self.assertEqual(transport.fetch.await_count, 64)

    async def test_structured_variants_fetch_concurrently_and_coalesce_across_parents(self):
        entered, release = asyncio.Event(), asyncio.Event()
        calls = []
        async def fetch(sku):
            calls.append(sku)
            if len(calls) == 10: entered.set()
            if sku != '6019174271': await release.wait()
            return external_family_html(sku)
        session = FamilySession(AsyncMock(fetch=fetch))
        self.addAsyncCleanup(session.close)
        root = asyncio.create_task(session.get('6019174271'))
        try:
            await asyncio.wait_for(entered.wait(), 2)
            other = asyncio.create_task(session.get('241701528573190144'))
        finally:
            release.set()
        first, second = await asyncio.gather(root, other)
        self.assertEqual(len(first.variants), 10)
        self.assertEqual(len(second.variants), 10)
        self.assertEqual(second.ref.external_id, '241701528573190144')
        self.assertEqual(len(calls), len(set(calls)))
        self.assertEqual(len(session.families), 1)

    async def test_parallel_close_cancels_all_pending_variant_requests(self):
        entered = asyncio.Event()
        active = cancelled = 0
        async def fetch(sku):
            nonlocal active, cancelled
            if sku == '6019174271': return external_family_html(sku)
            active += 1
            if active == 9: entered.set()
            try: await asyncio.Future()
            except asyncio.CancelledError:
                cancelled += 1
                raise
        session = FamilySession(AsyncMock(fetch=fetch))
        task = asyncio.create_task(session.get('6019174271'))
        try:
            await asyncio.wait_for(entered.wait(), 2)
        finally:
            await session.close()
        with self.assertRaises(asyncio.CancelledError): await task
        self.assertEqual(cancelled, 9)
        self.assertEqual(session.snapshots, {})

    async def test_parallel_guest_response_cannot_publish_anonymous_price(self):
        async def fetch(sku):
            body = external_family_html(sku)
            return body.replace('"isAuth": true', '"isAuth": false') if sku != '6019174271' else body
        session = FamilySession(AsyncMock(fetch=fetch))
        self.addAsyncCleanup(session.close)
        with self.assertRaises(AuthenticationRequired): await session.get('6019174271')
        self.assertEqual(session.snapshots, {})

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
