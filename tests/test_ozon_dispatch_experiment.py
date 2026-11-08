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
    Probe, ChromeResources, chrome_processes, measured_client, run, run_batch,
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
                                      max_in_flight_requests=1)
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
                                      max_in_flight_requests=1)
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

    async def test_fixed_n_reaches_requested_concurrency_above_five(self):
        args = SimpleNamespace(profile_dir=Path('/unused'))
        for n in (5, 8, 12):
            entered, release = asyncio.Event(), asyncio.Event()
            active = 0
            async def fetch(arg):
                nonlocal active
                active += 1
                if active == n:
                    entered.set()
                await release.wait()
                return response()
            probe = Probe()
            with patch('experiments.parallel_ozon.ExperimentClient._prepare_storefront', new=AsyncMock()):
                async with measured_client(args, probe, str(n), self.fake_session(fetch)) as connector:
                    task = asyncio.create_task(run_batch(connector, [str(i) for i in range(30)], probe, str(n)))
                    try:
                        await asyncio.wait_for(entered.wait(), timeout=1)
                        self.assertEqual(probe.peak, n)
                    finally:
                        release.set()
                        batch = await task
            self.assertEqual(batch['successes'], 30)
            self.assertEqual(batch['peak_composer_dispatches'], n)
            self.assertEqual(batch['max_in_flight_requests'], n)

    async def test_chrome_resource_sampling_excludes_other_process_groups(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            for pid, group in ((101, 101), (102, 101), (103, 999)):
                process = root / str(pid)
                process.mkdir()
                fields = ['0'] * 22
                fields[0], fields[2] = 'S', str(group)
                fields[11], fields[12], fields[19], fields[21] = '100', '50', str(pid), '10'
                (process / 'stat').write_text(str(pid) + ' (chrome test) ' + ' '.join(fields))
            values = chrome_processes(101, root)
            self.assertEqual({pid for pid, _ in values}, {101, 102})
            resources = ChromeResources(101)
            with patch('experiments.parallel_ozon.chrome_processes', return_value=values):
                await resources.sample()
            after = {key: (cpu + .25, rss * 2) for key, (cpu, rss) in values.items()}
            with patch('experiments.parallel_ozon.chrome_processes', return_value=after):
                await resources.sample()
            report = resources.report()
            self.assertEqual(report['sampled_cpu_seconds'], .5)
            self.assertEqual(report['sampled_peak_rss_bytes'], sum(rss for _, rss in after.values()))
            self.assertFalse(ChromeResources(None).report()['available'])

    async def test_challenge_stops_waiters_and_preserves_metrics(self):
        args = SimpleNamespace(profile_dir=Path('/unused'))
        probe = Probe()
        session = self.fake_session(AsyncMock(return_value=response(text='<html>challenge</html>',
                                                                  status=200)))
        with patch('experiments.parallel_ozon.ExperimentClient._prepare_storefront', new=AsyncMock()):
            async with measured_client(args, probe, '1', session) as connector:
                batch = await run_batch(connector, [str(i) for i in range(30)], probe, '1')
        self.assertEqual(probe.stop_reason, 'challenge')
        self.assertEqual(batch['composer_dispatches'], 1)
        self.assertEqual(batch['successes'], 0)
        self.assertGreater(batch['cancelled_targets'], 0)

    async def test_first_access_refusal_stops_without_recovery(self):
        args = SimpleNamespace(profile_dir=Path('/unused'))
        probe = Probe()
        session = self.fake_session(AsyncMock(return_value=response(403)))
        with patch('experiments.parallel_ozon.ExperimentClient._prepare_storefront', new=AsyncMock()):
            async with measured_client(args, probe, '1', session) as connector:
                batch = await run_batch(connector, [str(i) for i in range(30)], probe, '1')
        self.assertEqual(probe.stop_reason, 'access_refusal')
        self.assertEqual(batch['composer_dispatches'], 1)
        self.assertEqual(batch['recoveries'], 0)

    async def test_six_batches_keep_fixed_dataset_and_safe_report(self):
        session = self.fake_session(AsyncMock(return_value=response()))
        articles = [str(i) for i in range(30)]
        with TemporaryDirectory() as directory:
            args = SimpleNamespace(profile_dir=Path(directory), headless=True, pause=0, order=('1', '5', '100', '100', '5', '1'),
                                   output=Path(directory) / 'result.json', articles=articles, size=30)
            async def batch(connector, received, probe, mode):
                self.assertEqual(received, articles)
                return {'mode': mode, 'successes': 30}
            with patch('experiments.parallel_ozon.ChromeSession', return_value=session), \
                 patch('experiments.parallel_ozon.run_batch', side_effect=batch):
                report = await run(args)
            self.assertEqual(report['status'], 'complete')
            self.assertEqual(report['browser_mode'], 'headless')
            self.assertEqual([b['mode'] for b in report['batches']], ['1', '5', '100', '100', '5', '1'])
            saved = json.loads(args.output.read_text())
            self.assertEqual(saved['articles'], articles)
            self.assertNotIn('widgetStates', args.output.read_text())
            args.order = ('1', '5', '5', '1')
            with patch('experiments.parallel_ozon.ChromeSession', return_value=session), \
                 patch('experiments.parallel_ozon.run_batch', side_effect=batch):
                report = await run(args)
            self.assertEqual(report['status'], 'complete')
            self.assertEqual(report['order'], ('1', '5', '5', '1'))
            self.assertEqual([b['mode'] for b in report['batches']], ['1', '5', '5', '1'])
            args.order = ('5', '8', '12', '12', '8', '5') * 2
            with patch('experiments.parallel_ozon.ChromeSession', return_value=session), \
                 patch('experiments.parallel_ozon.run_batch', side_effect=batch):
                report = await run(args)
            self.assertEqual([b['mode'] for b in report['batches']], list(args.order))
            self.assertTrue(all(not b['chrome_resources']['available'] for b in report['batches']))

    async def test_insufficient_discovery_does_not_run_comparison(self):
        session = self.fake_session(AsyncMock(return_value=response()))
        with TemporaryDirectory() as directory:
            args = SimpleNamespace(profile_dir=Path(directory), headless=True, pause=0, order=('1', '5', '100', '100', '5', '1'),
                                   output=Path(directory) / 'result.json', articles=[], size=40)
            with patch('experiments.parallel_ozon.ChromeSession', return_value=session), \
                 patch('experiments.parallel_ozon.discover', new=AsyncMock(return_value=['1'])), \
                 patch('experiments.parallel_ozon.run_batch', new=AsyncMock()) as batch:
                report = await run(args)
            self.assertEqual(report['stop_reason'], 'insufficient_dataset')
            batch.assert_not_awaited()


if __name__ == '__main__':
    unittest.main()
