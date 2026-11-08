"""Dispatch invariants and experiment orchestration, without Chrome/network/DB."""
import asyncio
import json
import time
import unittest
from contextlib import asynccontextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from experiments.parallel_ozon import (
    MODES, Probe, measured_client, run, run_batch,
)
from tests.test_ozon_json_transport import FakePage, product_text, response
from marketplace_connector.connectors.ozon.json_transport import OzonJsonTransport


class DispatchExperimentTests(unittest.IsolatedAsyncioTestCase):
    async def test_unpaced_still_serializes_and_cancels_waiter(self):
        entered, release = asyncio.Event(), asyncio.Event()
        async def fetch(arg):
            entered.set()
            await release.wait()
            return response()
        page = FakePage(fetch)
        transport = OzonJsonTransport(MagicMock(new_page=AsyncMock(return_value=page)), AsyncMock(),
                                      concurrency=1, starts_per_second=None)
        self.addAsyncCleanup(transport.close)
        first = asyncio.create_task(transport.fetch('1'))
        await entered.wait()
        cancelled = asyncio.create_task(transport.fetch('2'))
        third = asyncio.create_task(transport.fetch('3'))
        await asyncio.sleep(0)
        self.assertEqual(len(page.calls), 1)
        cancelled.cancel()
        await asyncio.gather(cancelled, return_exceptions=True)
        release.set()
        self.assertEqual(await asyncio.gather(first, third), [product_text()] * 2)
        self.assertEqual(len(page.calls), 2)

    async def test_unpaced_retains_cooldown_and_recovery(self):
        page = FakePage(AsyncMock(side_effect=[response(429), response(403), response()]))
        prepare = AsyncMock()
        transport = OzonJsonTransport(MagicMock(new_page=AsyncMock(return_value=page)), prepare,
                                      concurrency=1, starts_per_second=None)
        self.addAsyncCleanup(transport.close)
        # Short controlled cooldown avoids waiting the default server pause.
        with patch('marketplace_connector.connectors.ozon.json_transport.retry_after_seconds', return_value=.04):
            started = time.perf_counter()
            self.assertEqual(await transport.fetch('1'), product_text())
        self.assertGreaterEqual(time.perf_counter() - started, .035)
        self.assertEqual(prepare.await_count, 2)
        self.assertEqual(len(page.calls), 3)

    def fake_session(self, fetch):
        context = MagicMock(new_page=AsyncMock(side_effect=lambda: FakePage(fetch)))
        @asynccontextmanager
        async def collection_session():
            yield context
        return SimpleNamespace(collection_session=collection_session, headless=False,
                               virtual_display=False, challenge_lock=asyncio.Lock())

    async def test_modes_measure_real_dispatch_and_pacing(self):
        args = SimpleNamespace(profile_dir=Path('/unused'))
        async def fetch(arg):
            await asyncio.sleep(.005)
            return response()
        durations = {}
        for mode in MODES:
            probe = Probe()
            session = self.fake_session(fetch)
            with patch('experiments.parallel_ozon.ExperimentClient._prepare_storefront', new=AsyncMock()):
                async with measured_client(args, probe, mode, session) as connector:
                    batch = await run_batch(connector, [str(i) for i in range(7)], probe, mode)
            self.assertEqual(batch['successes'], 7)
            self.assertEqual(batch['composer_dispatches'], 7)
            self.assertEqual(batch['logical_retries'], 0)
            self.assertEqual(batch['transport_retries'], 0)
            self.assertEqual(batch['peak_composer_dispatches'], 5 if mode in ('A', 'D') else 1)
            self.assertTrue(all(r['fields']['availability'] for r in batch['results']))
            durations[mode] = batch['seconds']
        self.assertGreater(durations['B'], 1.1)
        self.assertGreater(durations['A'], .35)
        self.assertLess(durations['D'], durations['A'] / 2)
        self.assertLess(durations['C'], durations['B'] / 2)

    async def test_challenge_stops_waiters_and_preserves_metrics(self):
        args = SimpleNamespace(profile_dir=Path('/unused'))
        probe = Probe()
        session = self.fake_session(AsyncMock(return_value=response(text='<html>challenge</html>',
                                                                  status=200)))
        with patch('experiments.parallel_ozon.ExperimentClient._prepare_storefront', new=AsyncMock()):
            async with measured_client(args, probe, 'C', session) as connector:
                batch = await run_batch(connector, [str(i) for i in range(30)], probe, 'C')
        self.assertEqual(probe.stop_reason, 'challenge')
        self.assertEqual(batch['composer_dispatches'], 1)
        self.assertEqual(batch['successes'], 0)
        self.assertGreater(batch['cancelled_targets'], 0)

    async def test_second_access_refusal_stops_after_one_recovery(self):
        args = SimpleNamespace(profile_dir=Path('/unused'))
        probe = Probe()
        session = self.fake_session(AsyncMock(return_value=response(403)))
        with patch('experiments.parallel_ozon.ExperimentClient._prepare_storefront', new=AsyncMock()):
            async with measured_client(args, probe, 'C', session) as connector:
                batch = await run_batch(connector, [str(i) for i in range(30)], probe, 'C')
        self.assertEqual(probe.stop_reason, 'repeated_access_refusal')
        self.assertEqual(batch['composer_dispatches'], 2)
        self.assertEqual(batch['recoveries'], 1)

    async def test_six_batches_keep_fixed_dataset_and_safe_report(self):
        session = self.fake_session(AsyncMock(return_value=response()))
        articles = [str(i) for i in range(30)]
        with TemporaryDirectory() as directory:
            args = SimpleNamespace(profile_dir=Path(directory), headless=True, pause=0, order=tuple('ABCCBA'),
                                   output=Path(directory) / 'result.json', articles=articles, size=30)
            async def batch(connector, received, probe, mode):
                self.assertEqual(received, articles)
                return {'mode': mode, 'successes': 30}
            with patch('experiments.parallel_ozon.ChromeSession', return_value=session), \
                 patch('experiments.parallel_ozon.run_batch', side_effect=batch):
                report = await run(args)
            self.assertEqual(report['status'], 'complete')
            self.assertEqual(report['browser_mode'], 'headless')
            self.assertEqual([b['mode'] for b in report['batches']], list('ABCCBA'))
            saved = json.loads(args.output.read_text())
            self.assertEqual(saved['articles'], articles)
            self.assertNotIn('widgetStates', args.output.read_text())
            args.order = tuple('CDDC')
            with patch('experiments.parallel_ozon.ChromeSession', return_value=session), \
                 patch('experiments.parallel_ozon.run_batch', side_effect=batch):
                report = await run(args)
            self.assertEqual(report['status'], 'complete')
            self.assertEqual(report['order'], tuple('CDDC'))
            self.assertEqual([b['mode'] for b in report['batches']], list('CDDC'))

    async def test_insufficient_discovery_does_not_run_comparison(self):
        session = self.fake_session(AsyncMock(return_value=response()))
        with TemporaryDirectory() as directory:
            args = SimpleNamespace(profile_dir=Path(directory), headless=True, pause=0, order=tuple('ABCCBA'),
                                   output=Path(directory) / 'result.json', articles=[], size=40)
            with patch('experiments.parallel_ozon.ChromeSession', return_value=session), \
                 patch('experiments.parallel_ozon.discover', new=AsyncMock(return_value=['1'])), \
                 patch('experiments.parallel_ozon.run_batch', new=AsyncMock()) as batch:
                report = await run(args)
            self.assertEqual(report['stop_reason'], 'insufficient_dataset')
            batch.assert_not_awaited()


if __name__ == '__main__':
    unittest.main()
