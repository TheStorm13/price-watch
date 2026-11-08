"""DB-free Ozon dispatch comparison; see the testing guide."""
from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import time
from collections import Counter
from contextlib import asynccontextmanager
from contextvars import ContextVar
from pathlib import Path
from unittest.mock import patch

from marketplace_connector.application.retry import fetch_with_retry
from marketplace_connector.browser.session import ChromeSession
from marketplace_connector.connectors.ozon.async_client import AsyncOzonClient
from marketplace_connector.connectors.ozon.connector import OzonConnector
from marketplace_connector.connectors.ozon.json_transport import OzonJsonTransport
from marketplace_connector.domain.errors import ChallengeRequired

MODES = {'A': (5, 5), 'B': (1, 5), 'C': (1, None), 'D': (5, None)}
MODES.update({str(n): (n, None) for n in (5, 8, 12)})
ORDER = ('A', 'B', 'C', 'C', 'B', 'A')
SEEDS = ('1604900984', '1634943359', '1607687714', '1641499399', '1607686851',
         '2056350478', '4465694803', '4545459627')
FETCH = ContextVar('experiment_fetch')


class ExperimentStopped(Exception):
    """A stop condition, without private response details."""


class Probe:
    def __init__(self):
        self.stop_reason = None
        self.stopped = asyncio.Event()
        self.access_refusals = 0
        self.reset()

    def reset(self):
        self.requests = []
        self.started = time.perf_counter()
        self.recoveries = self.active = self.peak = 0

    def check(self):
        if self.stop_reason:
            raise ExperimentStopped(self.stop_reason)

    def stop(self, reason):
        self.stop_reason = reason
        self.stopped.set()


class MeasuredTransport(OzonJsonTransport):
    def __init__(self, *args, probe, **kwargs):
        super().__init__(*args, **kwargs)
        self.probe, self.waits = probe, {}

    async def fetch(self, article, *, modal_link=None):
        token = FETCH.set({'article': article, 'kind': 'modal' if modal_link else 'product', 'attempt': 0})
        try:
            return await super().fetch(article, modal_link=modal_link)
        finally:
            FETCH.reset(token)

    async def _reserve(self):
        self.probe.check()
        started = time.perf_counter()
        generation = await super()._reserve()
        self.waits[asyncio.current_task()] = time.perf_counter() - started
        if self.probe.stop_reason:
            async with self._condition:
                self._active -= 1
                self._condition.notify_all()
            self.probe.check()
        return generation

    async def _evaluate(self, url):
        fetch = FETCH.get()
        fetch['attempt'] += 1
        record = {**fetch, 'gate_seconds': self.waits.pop(asyncio.current_task(), 0),
                  'start_seconds': time.perf_counter() - self.probe.started}
        self.probe.requests.append(record)
        self.probe.active += 1
        self.probe.peak = max(self.probe.peak, self.probe.active)
        started = time.perf_counter()
        try:
            result = await super()._evaluate(url)
            record.update(status=result.get('status'), error=result.get('error'))
            if self._needs_recovery(result):
                self.probe.access_refusals += 1
                challenge = result.get('status') in (200, 429)
                if challenge or self.probe.access_refusals >= 2:
                    self.probe.stop('challenge' if challenge else 'repeated_access_refusal')
                    self.probe.check()
            return result
        except asyncio.CancelledError:
            record['cancelled'] = True
            raise
        finally:
            record['network_seconds'] = time.perf_counter() - started
            self.probe.active -= 1

    async def _recover(self):
        self.probe.recoveries += 1
        return await super()._recover()


class StopChallenge:
    def __init__(self, probe):
        self.probe = probe

    async def handle_async(self, marketplace, message):
        self.probe.stop('challenge')
        raise ExperimentStopped('challenge')


class ExperimentClient(AsyncOzonClient):
    async def _handle_antibot_async(self, page, article, *, force=False):
        # A detected challenge stops even in headless mode; do not ask for input.
        await self.challenge_handler.handle_async('ozon', 'challenge')


@asynccontextmanager
async def measured_client(args, probe, mode, session):
    concurrency, rate = MODES[mode]
    client = ExperimentClient(args.profile_dir, session=session, concurrency=concurrency,
                            starts_per_second=rate, challenge_handler=StopChallenge(probe))
    def factory(*factory_args, **kwargs):
        return MeasuredTransport(*factory_args, probe=probe, **kwargs)
    with patch('marketplace_connector.connectors.ozon.async_client.OzonJsonTransport', factory):
        async with client.collection_session():
            yield OzonConnector(client)


def completeness(card):
    return {'price': card.price is not None, 'image': bool(card.image_url),
            'seller': card.seller is not None, 'rating': card.rating is not None,
            'attributes': len(card.attributes), 'variants': len(card.variants),
            'availability': card.availability.value,
            'variant_discovery_error': bool(card.extensions.get('variant_discovery_error'))}


async def fetch_one(connector, article, limit, probe):
    queued = time.perf_counter()
    attempts, slot_wait = 0, 0
    async def fetch():
        nonlocal attempts, slot_wait
        probe.check()
        waiting = time.perf_counter()
        async with limit:
            slot_wait += time.perf_counter() - waiting
            probe.check()
            attempts += 1
            return await connector.get_product(article)
    result = {'article': article, 'ok': False}
    try:
        card = await fetch_with_retry(fetch)
        result.update(ok=True, fields=completeness(card))
    except Exception as exc:
        result['error_type'] = type(exc).__name__
        if isinstance(exc, ChallengeRequired):
            probe.stop('challenge')
    result.update(seconds=time.perf_counter() - queued, slot_wait_seconds=slot_wait,
                  logical_attempts=attempts)
    return result


async def run_batch(connector, articles, probe, mode):
    probe.reset()
    started = time.perf_counter()
    workers = max(5, MODES[mode][0])
    limit = asyncio.Semaphore(workers)
    tasks = [asyncio.create_task(fetch_one(connector, article, limit, probe)) for article in articles]
    stop = asyncio.create_task(probe.stopped.wait())
    try:
        pending = set(tasks)
        while pending and not probe.stop_reason:
            done, _ = await asyncio.wait(pending | {stop}, return_when=asyncio.FIRST_COMPLETED)
            pending -= done
    finally:
        for task in [*tasks, stop]:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, stop, return_exceptions=True)
    results = [t.result() for t in tasks if not t.cancelled() and t.exception() is None]
    elapsed = time.perf_counter() - started
    successes = sum(r['ok'] for r in results)
    return {'mode': mode, 'card_workers': workers, 'concurrency': MODES[mode][0], 'starts_per_second': MODES[mode][1],
            'seconds': elapsed, 'successes': successes, 'successful_sku_per_minute': successes * 60 / elapsed,
            'cancelled_targets': len(articles) - len(results), 'results': results,
            'composer_dispatches': len(probe.requests), 'peak_composer_dispatches': probe.peak,
            'status_counts': dict(Counter(str(r.get('status')) for r in probe.requests)),
            'logical_retries': sum(max(0, r['logical_attempts'] - 1) for r in results),
            'transport_retries': sum(r['attempt'] > 1 for r in probe.requests),
            'recoveries': probe.recoveries, 'requests': list(probe.requests), 'stop_reason': probe.stop_reason}


async def discover(connector, size, probe):
    queue, visited, articles = list(SEEDS), set(), []
    while queue and len(articles) < size:
        article = queue.pop(0)
        if article in visited:
            continue
        visited.add(article)
        probe.check()
        try:
            card = await connector.get_product(article)
        except ExperimentStopped:
            raise
        except Exception as exc:
            if isinstance(exc, ChallengeRequired):
                probe.stop('challenge')
            probe.check()
            continue
        articles.append(article)
        queue.extend(v.ref.external_id for v in card.variants if v.ref.external_id not in visited)
    return articles


def save_report(report, output):
    # No raw responses, headers, profile paths or exception messages.
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + '.tmp')
    temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    temporary.replace(output)


def chrome_processes(group, proc_root=Path('/proc')):
    """Linux process-group CPU/RSS snapshot; shared pages can be counted twice."""
    if group is None or not proc_root.is_dir():
        return None
    samples = {}
    for entry in proc_root.iterdir():
        if not entry.name.isdecimal():
            continue
        try:
            fields = (entry / 'stat').read_text().rsplit(')', 1)[1].split()
            if int(fields[2]) == group:
                identity = (int(entry.name), int(fields[19]))
                samples[identity] = ((int(fields[11]) + int(fields[12])) / os.sysconf('SC_CLK_TCK'),
                                     int(fields[21]) * os.sysconf('SC_PAGE_SIZE'))
        except (OSError, ValueError, IndexError):
            continue  # A process can exit while /proc is being sampled.
    return samples


class ChromeResources:
    def __init__(self, group):
        self.group, self.previous = group, None
        self.cpu_seconds, self.peak_rss, self.samples = 0.0, 0, 0
        self.finished = asyncio.Event()

    async def sample(self):
        values = await asyncio.to_thread(chrome_processes, self.group)
        if not values:
            return
        if self.previous is not None:
            self.cpu_seconds += sum(max(0, cpu - self.previous.get(key, (0, 0))[0])
                                    for key, (cpu, _) in values.items())
        self.previous = values
        self.peak_rss = max(self.peak_rss, sum(rss for _, rss in values.values()))
        self.samples += 1

    async def monitor(self):
        while not self.finished.is_set():
            try:
                await asyncio.wait_for(self.finished.wait(), timeout=.1)
            except TimeoutError:
                await self.sample()

    def report(self):
        return {'available': bool(self.samples), 'samples': self.samples,
                'sampled_cpu_seconds': self.cpu_seconds if self.samples else None,
                'sampled_peak_rss_bytes': self.peak_rss if self.samples else None,
                'scope': 'Linux Chrome process group; 100ms samples; CPU may miss exited processes; RSS sums shared pages'}


async def run(args):
    probe = Probe()
    report = {'schema': 1, 'status': 'running', 'order': args.order, 'pause_seconds': args.pause,
              'browser_mode': 'headless' if args.headless else 'visible',
              'articles': list(args.articles), 'batches': [],
              'measurement_scope': 'composer fetch only; excludes navigation/background requests',
              'limitations': 'Small sample; discovery/cache/network/session state can bias results. No cache busting.'}
    try:
        session = ChromeSession(args.profile_dir, headless=args.headless)
        async with session.collection_session():
            if not report['articles']:
                async with measured_client(args, probe, 'B', session) as connector:
                    report['articles'] = await discover(connector, args.size, probe)
                report['discovery'] = {'composer_dispatches': len(probe.requests), 'recoveries': probe.recoveries}
            if not 30 <= len(report['articles']) <= 50:
                raise ExperimentStopped('insufficient_dataset')
            save_report(report, args.output)
            for index, mode in enumerate(args.order):
                probe.check()
                if index:
                    await asyncio.sleep(args.pause)
                async with measured_client(args, probe, mode, session) as connector:
                    process = getattr(session, '_async_process', None)
                    resources = ChromeResources(process.pid if process is not None else None)
                    await resources.sample()
                    monitor = asyncio.create_task(resources.monitor())
                    try:
                        batch = await run_batch(connector, report['articles'], probe, mode)
                    finally:
                        resources.finished.set()
                        await monitor
                        await resources.sample()
                    batch['chrome_resources'] = resources.report()
                report['batches'].append(batch)
                save_report(report, args.output)
                print(json.dumps({k: v for k, v in batch.items() if k not in ('results', 'requests')}), flush=True)
                probe.check()
            report['status'] = 'complete' if all(b['successes'] == len(report['articles']) for b in report['batches']) else 'completed_with_errors'
    except asyncio.CancelledError:
        report.update(status='interrupted', stop_reason='cancelled')
        report['partial_requests'] = list(probe.requests)
        raise
    except Exception as exc:
        report.update(status='stopped', stop_reason=probe.stop_reason or (
            str(exc) if isinstance(exc, ExperimentStopped) else type(exc).__name__))
        report['partial_requests'] = list(probe.requests)
    finally:
        save_report(report, args.output)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('articles', nargs='*', help='30–50 unique Ozon SKU IDs; otherwise discover from seeds')
    parser.add_argument('--articles-file', type=Path, help='JSON array of fixed SKU IDs')
    default_profile = Path(os.environ.get('XDG_DATA_HOME') or Path.home() / '.local/share') / 'price-watch/chrome-profile'
    parser.add_argument('--profile-dir', type=Path, default=default_profile,
                        help='Existing Price Watch Chrome profile (default: XDG_DATA_HOME/price-watch/chrome-profile)')
    parser.add_argument('--headless', action='store_true')
    parser.add_argument('--size', type=int, default=40)
    parser.add_argument('--pause', type=float, default=30)
    parser.add_argument('--order', nargs='+', choices=tuple(MODES), default=ORDER,
                        help='Batch order: A/B paced, C/D unpaced, 5/8/12 unpaced fixed N; default A B C C B A')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if not 30 <= args.size <= 50 or not math.isfinite(args.pause) or args.pause < 0:
        parser.error('size must be 30–50; pause must be finite and nonnegative')
    if args.articles_file:
        if args.articles:
            parser.error('Use articles or --articles-file')
        args.articles = json.loads(args.articles_file.read_text())
        if not isinstance(args.articles, list):
            parser.error('--articles-file must contain a JSON array')
    args.articles = list(dict.fromkeys(AsyncOzonClient.normalize_product_id(a) for a in args.articles))
    if args.articles and not 30 <= len(args.articles) <= 50:
        parser.error('Provide 30–50 unique SKU IDs')
    args.profile_dir = args.profile_dir.expanduser().resolve()
    if not args.profile_dir.is_dir():
        parser.error('Use an existing Price Watch Chrome profile; do not create a fresh experimental profile')
    report = asyncio.run(run(args))
    print(json.dumps({'status': report['status'], 'stop_reason': report.get('stop_reason'), 'output': str(args.output)}))
    return 0 if report['status'] == 'complete' else 1


if __name__ == '__main__':
    raise SystemExit(main())
