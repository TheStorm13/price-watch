"""Deterministic transport races; all response bodies are synthetic."""
import asyncio
import json
import unittest
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from tempfile import TemporaryDirectory
from unittest.mock import AsyncMock, MagicMock, patch

from marketplace_connector.connectors.ozon.async_client import AsyncOzonClient
from marketplace_connector.connectors.ozon.json_transport import (
    ABORT_SCRIPT, API_PATH, FETCH_SCRIPT, HOME_URL, OzonJsonTransport, retry_after_seconds,
)
from marketplace_connector.domain.errors import MarketplaceSchemaChanged, MarketplaceUnavailable, RateLimited


def response(status=200, text=None, **kwargs):
    return dict(status=status, text=text if text is not None else product_text(),
                contentType='application/json; charset=utf-8', url=HOME_URL.rstrip('/') + API_PATH,
                retryAfter=None, redirected=False, **kwargs)


def product_text():
    return ' {"widgetStates":{"webProductHeading-1":"{\\"title\\":\\"test\\"}"}}\n'


class FakePage:
    def __init__(self, fetch):
        self.fetch = fetch
        self.calls = []
        self.aborted = []
        self.pending = {}
        self.close = AsyncMock()

    async def evaluate(self, script, arg):
        if script == ABORT_SCRIPT:
            self.aborted.append(arg)
            task = self.pending.get(arg)
            if task is not None:
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
            return
        assert script == FETCH_SCRIPT
        self.calls.append(arg)
        task = asyncio.create_task(self.fetch(arg))
        self.pending[arg['id']] = task
        try:
            return await task
        finally:
            self.pending.pop(arg['id'], None)


class JsonTransportTests(unittest.IsolatedAsyncioTestCase):
    async def make_transport(self, fetch=None, prepare=None, **kwargs):
        page = FakePage(fetch or AsyncMock(return_value=response()))
        context = MagicMock(new_page=AsyncMock(return_value=page))
        prepare = prepare or AsyncMock()
        transport = OzonJsonTransport(context, prepare, **kwargs)
        self.addAsyncCleanup(transport.close)
        return transport, page, context, prepare

    async def test_five_overlap_and_sixth_waits_shared_bootstrap_exact_raw(self):
        release = asyncio.Event()
        five = asyncio.Event()
        started = 0
        async def fetch(arg):
            nonlocal started
            started += 1
            if started == 5:
                five.set()
            await release.wait()
            return response()
        transport, page, context, prepare = await self.make_transport(fetch)
        tasks = [asyncio.create_task(transport.fetch(str(i))) for i in range(6)]
        await asyncio.wait_for(five.wait(), 1)
        self.assertEqual(len(page.calls), 5)
        self.assertFalse(any(task.done() for task in tasks))
        release.set()
        self.assertEqual(await asyncio.gather(*tasks), [product_text()] * 6)
        context.new_page.assert_awaited_once()
        prepare.assert_awaited_once_with(page)
        self.assertEqual(page.calls[0]['url'], HOME_URL.rstrip('/') + API_PATH + '?url=%2Fproduct%2F0%2F')
        self.assertEqual(page.calls[0]['timeoutMs'], 30000)
        self.assertNotEqual(page.calls[0]['id'], page.calls[1]['id'])
        page.close.assert_not_awaited()

    async def test_cancel_only_one_fetch_neighbor_survives(self):
        release = asyncio.Event()
        entered = asyncio.Event()
        async def fetch(arg):
            if len(page.calls) == 2:
                entered.set()
            await release.wait()
            return response()
        transport, page, _, _ = await self.make_transport(fetch)
        one = asyncio.create_task(transport.fetch('1'))
        two = asyncio.create_task(transport.fetch('2'))
        await asyncio.wait_for(entered.wait(), 1)
        one.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await one
        self.assertEqual(page.aborted, [page.calls[0]['id']])
        self.assertFalse(two.done())
        page.close.assert_not_awaited()
        release.set()
        self.assertEqual(await two, product_text())
        self.assertEqual(transport._active, 0)

    async def test_recovery_is_single_flight_and_drains_successful_neighbors(self):
        failed = asyncio.Event()
        neighbor = asyncio.Event()
        count = 0
        refresh_active_counts = []
        async def prepare(page):
            refresh_active_counts.append(transport._active)
        async def fetch(arg):
            nonlocal count
            count += 1
            if count < 3:
                await failed.wait()
                return response(403, '{}')
            if count == 3:
                await neighbor.wait()
            return response()
        transport, page, _, _ = await self.make_transport(fetch, prepare, starts_per_second=1000)
        tasks = [asyncio.create_task(transport.fetch(str(i))) for i in range(3)]
        while len(page.calls) < 3:
            await asyncio.sleep(0)
        failed.set()
        while transport._recovery is None:
            await asyncio.sleep(0)
        waiter = asyncio.create_task(transport.fetch('4'))
        await asyncio.sleep(.02)
        self.assertEqual(refresh_active_counts, [0])
        self.assertEqual(len(page.calls), 3)
        neighbor.set()
        self.assertEqual(await asyncio.gather(*tasks, waiter), [product_text()] * 4)
        self.assertEqual(refresh_active_counts, [0, 0])
        self.assertEqual(transport._generation, 1)

    async def test_persistent_access_html_redirect_each_refresh_only_once(self):
        cases = [response(403, '{}'), response(401, '{}'),
                 response(200, '{"incidentId":"synthetic","blockURL":"/blocked"}')]
        html = response(text='<html>challenge</html>'); html['contentType'] = 'text/html'
        redirect = response(); redirect.update(url='https://www.ozon.ru/login/', redirected=True)
        cases += [html, redirect]
        for value in cases:
            with self.subTest(value=value):
                transport, page, _, prepare = await self.make_transport(AsyncMock(return_value=value))
                with self.assertRaises(MarketplaceUnavailable):
                    await transport.fetch('1')
                self.assertEqual(len(page.calls), 2)
                self.assertEqual(prepare.await_count, 2)
                with self.assertRaises(MarketplaceUnavailable):
                    await transport.fetch('2')
                self.assertEqual(len(page.calls), 2)

    async def test_recovery_failure_is_shared_without_retry_storm(self):
        prepare = AsyncMock(side_effect=[None, MarketplaceUnavailable('access')])
        transport, page, _, _ = await self.make_transport(AsyncMock(return_value=response(403)), prepare)
        results = await asyncio.gather(*(transport.fetch(str(i)) for i in range(5)), return_exceptions=True)
        self.assertTrue(all(isinstance(r, MarketplaceUnavailable) for r in results))
        self.assertEqual(prepare.await_count, 2)
        with self.assertRaises(MarketplaceUnavailable):
            await transport.fetch('6')
        self.assertLessEqual(len(page.calls), 5)

    async def test_schema_and_status_errors_never_become_empty_success_or_not_found(self):
        cases = [(response(404, '<html>404</html>'), MarketplaceUnavailable),
                 (response(400), MarketplaceUnavailable)]
        for body in ('not JSON', '[]', '{"widgetStates":[]}', '{"widgetStates":{}}',
                     '{"widgetStates":{},"invalid":NaN}',
                     '{"widgetStates":{"webPrice-1":"not JSON"}}',
                     '{"widgetStates":{"webPrice-1":[]}}'):
            cases.append((response(text=body), MarketplaceSchemaChanged))
        wrong_type = response(); wrong_type['contentType'] = 'text/plain'
        cases.append((wrong_type, MarketplaceSchemaChanged))
        for value, error in cases:
            with self.subTest(value=value):
                transport, page, _, prepare = await self.make_transport(AsyncMock(return_value=value))
                with self.assertRaises(error):
                    await transport.fetch('1')
                self.assertEqual(len(page.calls), 1)
                self.assertEqual(prepare.await_count, 1)

    async def test_confirmed_removed_product_stays_valid_raw(self):
        text = json.dumps({'widgetStates': {}, 'pageInfo': {'pageType': 'search', 'url': '/search/?product_id=1'}})
        transport, _, _, _ = await self.make_transport(AsyncMock(return_value=response(text=text)))
        self.assertEqual(await transport.fetch('1'), text)

    async def test_transient_errors_have_three_attempts_and_release_slots(self):
        for value in (response(503), {'error': 'timeout'}, {'error': 'network'}):
            with self.subTest(value=value):
                transport, page, _, _ = await self.make_transport(AsyncMock(return_value=value), max_retry_wait=.001)
                with self.assertRaises(MarketplaceUnavailable):
                    await transport.fetch('1')
                self.assertEqual(len(page.calls), 3)
                self.assertEqual(transport._active, 0)

    async def test_transient_errors_can_recover_without_refresh(self):
        fetch = AsyncMock(side_effect=[{'error': 'network'}, response(502), response()])
        transport, page, _, prepare = await self.make_transport(fetch, max_retry_wait=.001)
        self.assertEqual(await transport.fetch('1'), product_text())
        self.assertEqual(len(page.calls), 3)
        prepare.assert_awaited_once()

    async def test_cancelling_backoff_does_not_send_another_request(self):
        transport, page, _, _ = await self.make_transport(AsyncMock(return_value=response(503)))
        task = asyncio.create_task(transport.fetch('1'))
        while not page.calls or transport._active:
            await asyncio.sleep(0)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.assertEqual(len(page.calls), 1)
        self.assertEqual(transport._active, 0)

    async def test_cancel_recovery_waiter_keeps_shared_refresh_alive(self):
        entered = asyncio.Event()
        release = asyncio.Event()
        prepares = 0
        async def prepare(page):
            nonlocal prepares
            prepares += 1
            if prepares == 2:
                entered.set()
                await release.wait()
        transport, page, _, _ = await self.make_transport(
            AsyncMock(side_effect=[response(403), response()]), prepare)
        one = asyncio.create_task(transport.fetch('1'))
        await asyncio.wait_for(entered.wait(), 1)
        two = asyncio.create_task(transport.fetch('2'))
        one.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await one
        self.assertFalse(transport._recovery.cancelled())
        release.set()
        self.assertEqual(await two, product_text())
        self.assertEqual(prepares, 2)

    async def test_token_bucket_is_independent_of_inflight_slots_and_covers_retries(self):
        transport, page, _, _ = await self.make_transport(starts_per_second=10, concurrency=5)
        await asyncio.gather(*(transport.fetch(str(i)) for i in range(5)))
        started = asyncio.get_running_loop().time()
        await transport.fetch('6')
        self.assertGreaterEqual(asyncio.get_running_loop().time() - started, .07)
        self.assertEqual(len(page.calls), 6)
        transport.rate = 20
        transport._tokens = 0
        page.fetch = AsyncMock(side_effect=[response(429), response()])
        # Numeric zero permits retry immediately, but the token bucket still applies.
        first = response(429); first['retryAfter'] = '0'
        page.fetch = AsyncMock(side_effect=[first, response()])
        started = asyncio.get_running_loop().time()
        await transport.fetch('7')
        self.assertGreaterEqual(asyncio.get_running_loop().time() - started, .08)

    async def test_parallel_429_extend_cooldown_and_waiting_dispatch_rechecks(self):
        short = response(429); short['retryAfter'] = '1'
        long = response(429); long['retryAfter'] = '2'
        release = asyncio.Event()
        first_two = 0
        timestamps = []
        async def fetch(arg):
            nonlocal first_two
            timestamps.append(asyncio.get_running_loop().time())
            first_two += 1
            if first_two == 1:
                await release.wait()
                await asyncio.sleep(.02)
                return long
            if first_two == 2:
                release.set()
                return short
            return response()
        transport, page, _, _ = await self.make_transport(fetch, starts_per_second=10000, concurrency=2)
        self.assertEqual(await asyncio.gather(transport.fetch('1'), transport.fetch('2'), transport.fetch('3')), [product_text()] * 3)
        self.assertGreaterEqual(min(timestamps[2:]) - max(timestamps[:2]), 1.95)

    async def test_long_retry_after_blocks_new_products_without_early_sends(self):
        limited = response(429); limited['retryAfter'] = '600'
        transport, page, _, _ = await self.make_transport(AsyncMock(return_value=limited), max_retry_wait=.01)
        for sku in ('1', '2'):
            with self.assertRaises(RateLimited) as caught:
                await transport.fetch(sku)
            self.assertGreater(caught.exception.retry_after, 590)
        self.assertEqual(len(page.calls), 1)

    async def test_429_exhausted_attempts_preserve_retry_after(self):
        limited = response(429); limited['retryAfter'] = '0'
        transport, page, _, _ = await self.make_transport(AsyncMock(return_value=limited))
        with self.assertRaises(RateLimited) as caught:
            await transport.fetch('1')
        self.assertEqual(len(page.calls), 3)
        self.assertEqual(caught.exception.retry_after, 0)

    async def test_close_cancels_owned_requests_then_closes_shared_page(self):
        entered = asyncio.Event()
        async def fetch(arg):
            entered.set()
            await asyncio.Event().wait()
        transport, page, _, _ = await self.make_transport(fetch)
        tasks = [asyncio.create_task(transport.fetch(str(i))) for i in range(5)]
        await entered.wait()
        await transport.close()
        self.assertTrue(all(task.cancelled() for task in tasks))
        self.assertEqual(transport._active, 0)
        page.close.assert_awaited_once()

    async def test_cancelled_bootstrap_waiter_does_not_cancel_bootstrap_for_neighbor(self):
        entered = asyncio.Event()
        release = asyncio.Event()
        async def prepare(page):
            entered.set()
            await release.wait()
        transport, _, context, _ = await self.make_transport(prepare=prepare)
        one = asyncio.create_task(transport.fetch('1'))
        await entered.wait()
        two = asyncio.create_task(transport.fetch('2'))
        one.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await one
        release.set()
        self.assertEqual(await two, product_text())
        context.new_page.assert_awaited_once()

    async def test_python_guard_aborts_a_nonresponsive_evaluation(self):
        async def fetch(arg):
            await asyncio.Event().wait()
        transport, page, _, _ = await self.make_transport(fetch, request_timeout=.001, max_attempts=1)
        with self.assertRaisesRegex(MarketplaceUnavailable, 'Таймаут'):
            await asyncio.wait_for(transport.fetch('1'), 4)
        self.assertEqual(page.aborted, [page.calls[0]['id']])
        self.assertFalse(page.pending)
        self.assertEqual(transport._active, 0)

    def test_retry_after_formats(self):
        now = datetime(2026, 10, 26, tzinfo=timezone.utc)
        self.assertEqual(retry_after_seconds('12'), 12)
        self.assertEqual(retry_after_seconds(format_datetime(now + timedelta(seconds=7)), now=now), 7)
        self.assertEqual(retry_after_seconds(format_datetime(now - timedelta(seconds=7)), now=now), 0)
        for value in ('NaN', '1.5', '-1', 'invalid', None):
            self.assertEqual(retry_after_seconds(value), 1)
        self.assertEqual(retry_after_seconds('9' * 500), float('inf'))

    def test_invalid_settings_rejected(self):
        for kwargs in ({'concurrency': 0}, {'concurrency': True}, {'max_attempts': 1.5},
                       {'request_timeout': float('nan')}, {'starts_per_second': 0}, {'max_retry_wait': -1}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                OzonJsonTransport(None, None, **kwargs)


class ClientSessionTests(unittest.IsolatedAsyncioTestCase):
    async def test_concurrent_standalone_and_repeated_sessions_share_one_home_page(self):
        with TemporaryDirectory() as directory:
            client = AsyncOzonClient(directory)
            pages = []
            launches = []
            entered = asyncio.Event()
            release = asyncio.Event()
            async def fetch(arg):
                if len(pages[-1].calls) == 5:
                    entered.set()
                await release.wait()
                return response()
            async def new_page():
                page = FakePage(fetch)
                page.goto = AsyncMock(return_value=MagicMock(status=200))
                page.url = HOME_URL
                pages.append(page)
                return page
            context = MagicMock(new_page=AsyncMock(side_effect=new_page))
            @asynccontextmanager
            async def playwright():
                yield MagicMock()
            async def launch(pw):
                launches.append(pw)
                client._async_context = context
            with (patch('marketplace_connector.connectors.ozon.async_client.async_playwright', playwright),
                  patch.object(client, '_launch_async_context', side_effect=launch),
                  patch.object(client, '_is_antibot_page_async', AsyncMock(return_value=False))):
                tasks = [asyncio.create_task(client.fetch_raw_text_async(str(i), validate=False)) for i in range(5)]
                await asyncio.wait_for(entered.wait(), 1)
                self.assertEqual(len(launches), 1)
                self.assertEqual(len(pages), 1)
                pages[0].goto.assert_awaited_once_with(HOME_URL, wait_until='domcontentloaded', timeout=90000)
                release.set()
                self.assertEqual(await asyncio.gather(*tasks), [product_text()] * 5)
                pages[0].close.assert_awaited_once()
                self.assertIsNone(client._transport)
                async with client.collection_session():
                    await client.fetch_product_async('10')
                    await client.fetch_product_async('11')
                    self.assertEqual(len(pages), 2)
                    pages[1].close.assert_not_awaited()
                self.assertEqual(len(launches), 2)
                pages[1].close.assert_awaited_once()
                self.assertFalse(client._session_open)
