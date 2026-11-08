"""Unbounded Ali dispatch and first-access-refusal cancellation, without live data."""
import asyncio
import json
import unittest
from contextlib import asynccontextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from experiments.parallel_aliexpress import (
    ExperimentClient, ExperimentStopped, MeasuredTransport, Probe, access_signal,
    discover, measured_client, run, run_batch, validate_articles,
)
from marketplace_connector.connectors.aliexpress.client import AsyncAliExpressClient
from marketplace_connector.connectors.aliexpress.json_transport import AliExpressJsonTransport
from tests.test_aliexpress_transport import RAW, REF, response
from tests.test_ozon_json_transport import FakePage

ARTICLES = [f'1005009868651525:{12000061135122688 + i}' for i in range(40)]


def card():
    return SimpleNamespace(price=12, availability=SimpleNamespace(value='in_stock'), variants=())


class RequestPoolTransportTests(unittest.IsolatedAsyncioTestCase):
    async def make_transport(self, fetch, **options):
        page = FakePage(fetch)
        page.is_closed = lambda: False
        transport = AliExpressJsonTransport(MagicMock(new_page=AsyncMock(return_value=page)), AsyncMock(), **options)
        self.addAsyncCleanup(transport.close)
        return transport, page

    async def test_all_forty_enter_without_waiting_for_first_result(self):
        entered, release = asyncio.Event(), asyncio.Event()
        async def fetch(arg):
            if len(page.calls) == 40:
                entered.set()
            await release.wait()
            return response()
        transport, page = await self.make_transport(fetch, max_in_flight_requests=100)
        tasks = [asyncio.create_task(transport.fetch(REF)) for _ in range(40)]
        try:
            await asyncio.wait_for(entered.wait(), 2)
            self.assertEqual(transport._active, 40)
            self.assertTrue(all(not task.done() for task in tasks))
        finally:
            release.set()
            results = await asyncio.gather(*tasks, return_exceptions=True)
        self.assertEqual(results, [RAW] * 40)
        self.assertEqual(transport._active, 0)

    async def test_finite_concurrency_still_works_without_pacing(self):
        release, entered = asyncio.Event(), asyncio.Event()
        async def fetch(arg):
            if len(page.calls) == 4:
                entered.set()
            await release.wait()
            return response()
        transport, page = await self.make_transport(fetch, max_in_flight_requests=4)
        tasks = [asyncio.create_task(transport.fetch(REF)) for _ in range(5)]
        try:
            await asyncio.wait_for(entered.wait(), 1)
            self.assertEqual(len(page.calls), 4)
            self.assertEqual(transport._active, 4)
        finally:
            release.set()
            await asyncio.gather(*tasks)
        self.assertEqual(len(page.calls), 5)

    async def test_unbounded_still_honors_retry_after_and_recovery(self):
        times = []
        async def fetch(arg):
            times.append(asyncio.get_running_loop().time())
            return response(429, retryAfter='1') if len(times) == 1 else response()
        transport, _ = await self.make_transport(fetch, max_in_flight_requests=100)
        self.assertEqual(await transport.fetch(REF), RAW)
        self.assertGreaterEqual(times[1] - times[0], .95)
        transport, _ = await self.make_transport(AsyncMock(side_effect=[response(403), response()]),
                                                max_in_flight_requests=100)
        self.assertEqual(await transport.fetch(REF), RAW)
        self.assertEqual(transport.prepare_page.await_count, 2)

    def test_validation_and_application_defaults(self):
        transport = AliExpressJsonTransport(None, None)
        self.assertEqual(transport.pool.max_in_flight_requests, 100)
        client = AsyncAliExpressClient('/tmp/unused-ali-default')
        self.assertEqual(client._transport_options['max_in_flight_requests'], 100)
        for options in ({'max_in_flight_requests': None}, {'max_in_flight_requests': False},
                        {'max_in_flight_requests': 0}, {'max_in_flight_requests': 1.5},
                        {'max_attempts': None}, {'request_timeout': None}):
            with self.subTest(options=options), self.assertRaises(ValueError):
                AliExpressJsonTransport(None, None, **options)


class ExperimentTests(unittest.IsolatedAsyncioTestCase):
    async def test_whole_batch_runs_concurrently(self):
        entered = asyncio.Event()
        active = 0
        async def fetch(article):
            nonlocal active
            active += 1
            if active == 40:
                entered.set()
            await entered.wait()
            return card()
        connector = SimpleNamespace(get_product=fetch)
        batch = await asyncio.wait_for(run_batch(connector, ARTICLES, Probe()), 2)
        self.assertEqual(batch['counts'], dict(success=40, failed=0, cancelled=0, not_started=0))

    async def test_first_403_stops_before_recovery_and_cancels_neighbors(self):
        probe = Probe()
        ready = asyncio.Event()
        calls = 0
        async def fetch(arg):
            nonlocal calls
            calls += 1
            index = calls
            if index == 40:
                ready.set()
            if index == 1:
                await ready.wait()
                return response(403, '<html>private-challenge-token</html>')
            await asyncio.Event().wait()
        page = FakePage(fetch)
        page.is_closed = lambda: False
        transport = MeasuredTransport(MagicMock(new_page=AsyncMock(return_value=page)), AsyncMock(),
                                      max_in_flight_requests=100, probe=probe)
        self.addAsyncCleanup(transport.close)
        async def get_product(article):
            await transport.fetch(article)
            return card()
        batch = await asyncio.wait_for(run_batch(SimpleNamespace(get_product=get_product), ARTICLES, probe), 2)
        self.assertEqual(batch['stop_reason'], 'http_403')
        self.assertEqual(batch['peak_active_fetches'], 40)
        self.assertEqual(batch['http_attempts'], 40)
        self.assertEqual(batch['counts'], dict(success=0, failed=1, cancelled=39, not_started=0))
        self.assertEqual(batch['retries'], 0)
        self.assertEqual(batch['recoveries'], 0)
        self.assertEqual(transport.prepare_page.await_count, 1)
        self.assertEqual(transport._active, 0)
        self.assertFalse(page.pending)
        self.assertNotIn('private-challenge-token', json.dumps(batch))
        self.assertEqual(batch['not_dispatched'], 0)

    async def test_401_429_html_and_markers_stop_without_retry(self):
        for result in (response(401), response(429), response(200, '<html>captcha</html>'),
                       response(200, '{"rgv587_flag":true}')):
            probe = Probe()
            page = FakePage(AsyncMock(return_value=result))
            transport = MeasuredTransport(MagicMock(new_page=AsyncMock(return_value=page)), AsyncMock(),
                                          max_in_flight_requests=100, probe=probe)
            with self.subTest(status=result["status"]):
                try:
                    with self.assertRaises(ExperimentStopped):
                        await transport.fetch(REF)
                    self.assertEqual(len(page.calls), 1)
                    self.assertEqual(probe.recoveries, 0)
                    self.assertIsNone(transport._recovery)
                finally:
                    await transport.close()

    async def test_parent_cancellation_drains_pending_fetches(self):
        started = asyncio.Event()
        active = 0
        async def fetch(article):
            nonlocal active
            active += 1
            try:
                if active == 40:
                    started.set()
                await asyncio.Event().wait()
            finally:
                active -= 1
        task = asyncio.create_task(run_batch(SimpleNamespace(get_product=fetch), ARTICLES, Probe()))
        await asyncio.wait_for(started.wait(), 1)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.assertEqual(active, 0)

    async def test_shared_preparation_stops_immediately_on_storefront_challenge(self):
        probe = Probe()
        client = ExperimentClient('/tmp/unused-ali-experiment', probe=probe,
                                  max_in_flight_requests=100)
        page = MagicMock(title=AsyncMock(return_value='captcha'))
        page.url = 'https://aliexpress.ru/'
        page.locator.return_value.inner_text = AsyncMock(return_value='captcha')
        with self.assertRaises(ExperimentStopped):
            await client._is_antibot_page_async(page)
        self.assertEqual(probe.reason, 'storefront_challenge')

    async def test_run_saves_partial_discovery_and_never_runs_batch(self):
        @asynccontextmanager
        async def session_scope():
            yield
        session = SimpleNamespace(collection_session=session_scope, _async_browser=SimpleNamespace(version='synthetic'))
        @asynccontextmanager
        async def client_scope(profile, session, probe, **options):
            probe.stop('storefront_challenge')
            probe.check()
            yield
        with TemporaryDirectory() as directory:
            args = SimpleNamespace(profile_dir=Path(directory), articles=[], output=Path(directory)/'report.json')
            with patch('experiments.parallel_aliexpress.ChromeSession', return_value=session), \
                 patch('experiments.parallel_aliexpress.measured_client', client_scope), \
                 patch('experiments.parallel_aliexpress.run_batch', new_callable=AsyncMock) as batch:
                report = await run(args)
            batch.assert_not_awaited()
            saved = json.loads(args.output.read_text())
            self.assertEqual(saved['status'], 'stopped')
            self.assertEqual(saved['stop_reason'], 'storefront_challenge')
            self.assertEqual(saved['discovery']['requests'], [])
            self.assertIsNone(saved['batch'])

    async def test_explicit_preparation_reused_by_all_client_calls(self):
        page = FakePage(AsyncMock(return_value=response()))
        session = SimpleNamespace(headless=False, virtual_display=False, challenge_lock=asyncio.Lock())
        @asynccontextmanager
        async def scope():
            yield MagicMock(new_page=AsyncMock(return_value=page))
        session.collection_session = scope
        with patch.object(ExperimentClient, '_prepare_storefront', new_callable=AsyncMock) as prepare:
            async with measured_client('/tmp/unused-ali-test', session, Probe()) as (client, connector):
                await asyncio.gather(*(connector.get_product(REF) for _ in range(40)))
                self.assertEqual(prepare.await_count, 1)
                self.assertEqual(client._transport.pool.max_in_flight_requests, 100)
                self.assertEqual(len(page.calls), 40)
        page.close.assert_awaited_once()

    async def test_n8_client_has_eight_active_fetches_and_no_rate_limit(self):
        entered, release = asyncio.Event(), asyncio.Event()
        async def fetch(arg):
            if len(page.calls) == 8:
                entered.set()
            await release.wait()
            return response()
        page = FakePage(fetch)
        session = SimpleNamespace(headless=False, virtual_display=False, challenge_lock=asyncio.Lock())
        @asynccontextmanager
        async def scope():
            yield MagicMock(new_page=AsyncMock(return_value=page))
        session.collection_session = scope
        probe = Probe()
        with patch.object(ExperimentClient, '_prepare_storefront', new_callable=AsyncMock):
            async with measured_client('/tmp/unused-ali-n8', session, probe, max_in_flight_requests=8) as (client, connector):
                tasks = [asyncio.create_task(connector.get_product(REF)) for _ in range(40)]
                try:
                    await asyncio.wait_for(entered.wait(), 1)
                    self.assertEqual(len(page.calls), 8)
                    self.assertEqual(client._transport.pool.max_in_flight_requests, 8)
                finally:
                    release.set()
                    await asyncio.gather(*tasks)
                self.assertEqual(probe.peak, 8)
                self.assertEqual(len(page.calls), 40)
        page.close.assert_awaited_once()

    async def test_run_has_exactly_one_unbounded_batch_and_persists_frozen_set(self):
        @asynccontextmanager
        async def session_scope():
            yield
        session = SimpleNamespace(collection_session=session_scope, _async_browser=SimpleNamespace(version='synthetic'))
        @asynccontextmanager
        async def client_scope(profile, session, probe, **options):
            yield None, SimpleNamespace(get_product=AsyncMock(return_value=card()))
        with TemporaryDirectory() as directory:
            args = SimpleNamespace(profile_dir=Path(directory), articles=ARTICLES, output=Path(directory)/'report.json')
            from experiments.parallel_aliexpress import save
            snapshots = []
            def capture(report, path):
                snapshots.append(json.loads(json.dumps(report)))
                save(report, path)
            with patch('experiments.parallel_aliexpress.ChromeSession', return_value=session), \
                 patch('experiments.parallel_aliexpress.measured_client', client_scope), \
                 patch('experiments.parallel_aliexpress.save', side_effect=capture):
                report = await run(args)
            self.assertEqual(report['status'], 'complete')
            self.assertEqual(report['batch']['counts']['success'], 40)
            self.assertEqual(report['configuration']['batches'], 1)
            self.assertEqual(report['configuration']['max_in_flight_requests'], 100)
            self.assertEqual(snapshots[0]['articles'], ARTICLES)
            self.assertIsNone(snapshots[0]['batch'])
            self.assertEqual(json.loads(args.output.read_text())['status'], 'complete')

    async def test_profile_lock_is_preserved_without_launching_chrome(self):
        with TemporaryDirectory() as directory:
            profile = Path(directory)
            lock = profile / 'SingletonLock'
            lock.symlink_to('not-a-real-host-123456789')
            args = SimpleNamespace(profile_dir=profile, articles=ARTICLES, output=profile/'report.json')
            with patch('experiments.parallel_aliexpress.ChromeSession') as session:
                report = await run(args)
            session.assert_not_called()
            self.assertEqual(report['stop_reason'], 'profile_locked')
            self.assertTrue(lock.is_symlink())

    async def test_supplied_seeds_discover_forty_distinct_skus_across_products(self):
        seeds = ['1005007620335204', '1005008127103020', '1005003918845337', '1005013177457618']
        def product(product_id):
            return SimpleNamespace(variants=[SimpleNamespace(
                ref=SimpleNamespace(external_id=f'{product_id}:{10000+i}'),
                availability=SimpleNamespace(value='in_stock')) for i in range(12)])
        connector = SimpleNamespace(get_product=AsyncMock(side_effect=product))
        page = MagicMock(evaluate=AsyncMock())
        client = SimpleNamespace(_transport=SimpleNamespace(page=page))
        report = {'articles': [], 'discovery': {'errors': [], 'availability': {}}}
        articles = await discover(client, connector, Probe(), report, seeds)
        self.assertEqual(len(articles), 40)
        self.assertEqual(len(set(articles)), 40)
        self.assertEqual([call.args[0] for call in connector.get_product.await_args_list], seeds)
        self.assertEqual({seed: sum(ref.startswith(seed+':') for ref in articles) for seed in seeds},
                         {seed: 10 for seed in seeds})
        self.assertEqual(report['articles'], articles)
        page.evaluate.assert_not_awaited()

    def test_frozen_dataset_requires_unique_exact_skus(self):
        self.assertEqual(validate_articles(ARTICLES), ARTICLES)
        for articles in ([REF] * 40, ARTICLES[:39], ['123'] + ARTICLES[1:]):
            with self.assertRaises(ValueError):
                validate_articles(articles)
