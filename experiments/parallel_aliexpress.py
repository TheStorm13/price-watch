"""One DB-free AliExpress batch: forty async SKU tasks, no rate cap, optional concurrency cap."""
from __future__ import annotations

import argparse
import asyncio
import json
import math
import platform
import subprocess
import time
from contextlib import asynccontextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path
from unittest.mock import patch

from marketplace_connector.browser.session import ChromeSession
from marketplace_connector.connectors.aliexpress.client import AsyncAliExpressClient
from marketplace_connector.connectors.aliexpress.connector import AliExpressConnector
from marketplace_connector.connectors.aliexpress.identity import AliExpressRef
from marketplace_connector.connectors.aliexpress.json_transport import AliExpressJsonTransport

SEED = '1005009868651525'
FETCH = ContextVar('aliexpress_experiment_fetch')
PROFILE = Path.home() / '.local/share/price-watch/chrome-profile'


class ExperimentStopped(Exception):
    """Safe stop reason; never include a response body or challenge URL."""


class Probe:
    def __init__(self):
        self.stopped = asyncio.Event()
        self.reason = None
        self.requests = []
        self.active = self.peak = self.recoveries = 0
        self.started = time.perf_counter()

    def stop(self, reason):
        if self.reason is None:
            self.reason = reason
        self.stopped.set()

    def check(self):
        if self.reason:
            raise ExperimentStopped(self.reason)


def access_signal(result):
    """Return only a safe class; access refusal does not prove a CAPTCHA."""
    status = result.get('status')
    if status in (401, 403, 429):
        return f'http_{status}'
    if AliExpressJsonTransport._needs_recovery(result):
        text = result.get('text', '')
        if '_____tmd_____' in text or '"rgv587_flag"' in text:
            return 'challenge_marker'
        if 'text/html' in result.get('contentType', '').lower() or text.lstrip().startswith('<'):
            return 'html_instead_of_json'
        return 'unexpected_response_location'
    return None


class MeasuredTransport(AliExpressJsonTransport):
    def __init__(self, *args, probe, **kwargs):
        super().__init__(*args, **kwargs)
        self.probe = probe
        self.waits = {}

    async def _reserve(self):
        self.probe.check()
        started = time.perf_counter()
        generation = await super()._reserve()
        if self.probe.reason:
            async with self._condition:
                self._active -= 1
                self._condition.notify_all()
            self.probe.check()
        self.waits[asyncio.current_task()] = time.perf_counter() - started
        return generation

    async def fetch(self, article):
        token = FETCH.set({'article': article, 'attempt': 0})
        try:
            return await super().fetch(article)
        finally:
            FETCH.reset(token)

    async def _evaluate(self, url):
        self.probe.check()
        fetch = FETCH.get()
        fetch['attempt'] += 1
        started = time.perf_counter()
        record = {**fetch, 'start_seconds': started - self.probe.started,
                  'gate_seconds': self.waits.pop(asyncio.current_task(), 0)}
        self.probe.requests.append(record)
        self.probe.active += 1
        self.probe.peak = max(self.probe.peak, self.probe.active)
        try:
            result = await super()._evaluate(url)
            signal = access_signal(result)
            record.update(status=result.get('status'), error=result.get('error'), access_signal=signal)
            if signal:
                # Raise before _attempt receives result: no automatic recovery or retry.
                self.probe.stop(signal)
                self.probe.check()
            if result.get('error') == 'network' and self.page.is_closed():
                self.probe.stop('page_closed')
                self.probe.check()
            return result
        except asyncio.CancelledError:
            record['cancelled'] = True
            raise
        except Exception as exc:
            record['exception_type'] = type(exc).__name__
            raise
        finally:
            record['network_seconds'] = time.perf_counter() - started
            self.probe.active -= 1

    async def _recover(self):
        self.probe.recoveries += 1
        self.probe.stop('unexpected_recovery')
        self.probe.check()


class ExperimentClient(AsyncAliExpressClient):
    def __init__(self, *args, probe, **kwargs):
        self.probe = probe
        super().__init__(*args, **kwargs)

    async def _is_antibot_page_async(self, page):
        detected = await super()._is_antibot_page_async(page)
        if detected:
            self.probe.stop('storefront_challenge')
            self.probe.check()
        return detected

    async def _handle_antibot_async(self, page, article, *, force=False):
        self.probe.stop('storefront_access_check')
        self.probe.check()


@asynccontextmanager
async def measured_client(profile, session, probe, *, concurrency=None):
    client = ExperimentClient(profile, session=session, probe=probe,
                              concurrency=concurrency, starts_per_second=None)
    def factory(*args, **kwargs):
        return MeasuredTransport(*args, probe=probe, **kwargs)
    with patch('marketplace_connector.connectors.aliexpress.client.AliExpressJsonTransport', factory):
        async with client.collection_session():
            # Explicit preparation excludes navigation from batch timings. Normal
            # fetch calls join exactly this bootstrap task rather than start a second page.
            transport = client._transport
            transport._bootstrap = asyncio.create_task(transport._start())
            transport._bootstrap.add_done_callback(transport._retrieve_exception)
            await asyncio.shield(transport._bootstrap)
            yield client, AliExpressConnector(client)


def percentiles(values):
    values = sorted(values)
    return {f'p{p}': values[max(0, math.ceil(len(values) * p / 100) - 1)] if values else None
            for p in (50, 95)}


async def run_batch(connector, articles, probe):
    probe.check()
    probe.started = time.perf_counter()
    results = [{'article': article, 'state': 'not_started'} for article in articles]

    async def fetch_one(row):
        started = time.perf_counter()
        try:
            probe.check()
            row['state'] = 'running'
            card = await connector.get_product(row['article'])
            row.update(state='success', price=str(card.price) if card.price is not None else None,
                       availability=card.availability.value, variants=len(card.variants))
        except asyncio.CancelledError:
            row['state'] = 'cancelled'
            raise
        except Exception as exc:
            row.update(state='failed', error_type=type(exc).__name__)
        finally:
            row['seconds'] = time.perf_counter() - started

    # Entire finite pool is scheduled immediately: no workers, semaphore, or pacing.
    tasks = [asyncio.create_task(fetch_one(row)) for row in results]
    group = asyncio.gather(*tasks)
    stop = asyncio.create_task(probe.stopped.wait())
    try:
        await asyncio.wait((group, stop), return_when=asyncio.FIRST_COMPLETED)
    finally:
        stop.cancel()
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, stop, return_exceptions=True)
        await asyncio.gather(group, return_exceptions=True)
    counts = {state: sum(row['state'] == state for row in results)
              for state in ('success', 'failed', 'cancelled', 'not_started')}
    requests = list(probe.requests)
    dispatched = {request['article'] for request in requests}
    return {'seconds': time.perf_counter() - probe.started, 'counts': counts,
            'http_attempts': len(requests), 'retries': sum(r['attempt'] > 1 for r in requests),
            'recoveries': probe.recoveries, 'peak_active_fetches': probe.peak,
            'not_dispatched': sum(row['article'] not in dispatched for row in results),
            'request_seconds': percentiles([r['network_seconds'] for r in requests if not r.get('cancelled')]),
            'card_seconds': percentiles([r['seconds'] for r in results if r['state'] == 'success']),
            'requests': requests, 'results': results, 'stop_reason': probe.reason}


async def discover(client, connector, probe, report, seed_product_ids=None):
    page = client._transport.page
    if seed_product_ids:
        seeds = list(dict.fromkeys(seed_product_ids))
    else:
        # Only public product IDs survive extraction; URLs/tokens are not stored.
        product_ids = await page.evaluate('''() => [...new Set([...document.querySelectorAll('a[href]')]
            .map(a => { try { const u = new URL(a.href); return u.hostname === 'aliexpress.ru'
                ? (u.pathname.match(/^\\/item\\/(\\d+)\\.html/) || [])[1] : null; }
                catch { return null; } }).filter(Boolean))]''')
        seeds = list(dict.fromkeys([SEED, *product_ids]))
    report['discovery']['seed_product_ids'] = seeds
    candidates = []
    for product_id in seeds:
        probe.check()
        try:
            card = await connector.get_product(product_id)
        except ExperimentStopped:
            raise
        except Exception as exc:
            report['discovery']['errors'].append({'product_id': product_id, 'error_type': type(exc).__name__})
            if page.is_closed():
                probe.stop('page_closed')
                probe.check()
            continue
        candidates.append(list(card.variants))
        report['discovery'].setdefault('sku_counts', {})[product_id] = len(card.variants)
        # Round-robin keeps supplied products represented when one has many SKUs.
        articles = []
        availability = {}
        for index in range(max(map(len, candidates), default=0)):
            for variants in candidates:
                if index < len(variants):
                    variant = variants[index]
                    ref = variant.ref.external_id
                    if ref not in articles:
                        articles.append(ref)
                        availability[ref] = variant.availability.value
                    if len(articles) == 40:
                        break
            if len(articles) == 40:
                break
        report['articles'] = articles
        report['discovery']['availability'] = availability
        if not seed_product_ids and len(articles) == 40:
            return articles
    if len(report['articles']) == 40:
        return report['articles']
    probe.stop('insufficient_dataset')
    probe.check()


def save(report, path):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    temporary.replace(path)


def validate_articles(articles):
    if not isinstance(articles, list) or len(articles) != 40 or len(set(articles)) != 40:
        raise ValueError('Exactly 40 unique productId:skuId strings are required')
    for article in articles:
        ref = AliExpressRef.parse(article)
        if ref.sku_id is None or ref.external_id != article:
            raise ValueError('Exact productId:skuId is required')
    return articles


def runtime_versions():
    return {'python': platform.python_version(), 'playwright': version('playwright'),
            'git_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
            'working_tree_dirty': bool(subprocess.check_output(['git', 'status', '--porcelain'], text=True).strip())}


async def run(args):
    concurrency = getattr(args, "concurrency", None)
    report = {'schema': 1, 'status': 'running', 'created_at': datetime.now(timezone.utc).isoformat(),
              'configuration': {'concurrency': concurrency, 'starts_per_second': None, 'size': 40,
                                'browser_mode': 'visible', 'batches': 1},
              'versions': await asyncio.to_thread(runtime_versions),
              'articles': list(args.articles), 'batch': None,
              'discovery': {'performed': not bool(args.articles), 'errors': [], 'availability': {}},
              'measurement_scope': 'productData fetch evaluations only; excludes discovery, navigation and browser background requests',
              'limitations': 'One finite batch, no control; browser scheduling may queue fetches; SKU count is not distinct product count; no general stability claim.'}
    probe = Probe()
    phase = 'browser_start'
    try:
        lock = args.profile_dir / 'SingletonLock'
        if lock.exists() or lock.is_symlink():
            probe.stop('profile_locked')
            probe.check()
        session = ChromeSession(args.profile_dir, headless=False)
        async with session.collection_session():
            report['versions']['chrome'] = session._async_browser.version
            if not report['articles']:
                phase = 'discovery'
                async with measured_client(args.profile_dir, session, probe) as (client, connector):
                    report['articles'] = await discover(client, connector, probe, report, getattr(args, 'seed_product_ids', None))
            report['discovery'].update(requests=list(probe.requests), recoveries=probe.recoveries,
                                       seconds=time.perf_counter() - probe.started)
            validate_articles(report['articles'])
            report['distinct_product_ids'] = len({ref.split(':')[0] for ref in report['articles']})
            # Persist the frozen set before any measured requests are scheduled.
            save(report, args.output)
            probe = Probe()
            phase = 'batch_preparation'
            preparation = time.perf_counter()
            async with measured_client(args.profile_dir, session, probe, concurrency=concurrency) as (_, connector):
                report['preparation_seconds'] = time.perf_counter() - preparation
                phase = 'batch'
                report['batch'] = await run_batch(connector, report['articles'], probe)
                report['status'] = ('stopped' if probe.reason else 'complete'
                                    if report['batch']['counts']['success'] == 40 else 'completed_with_errors')
                report['stop_reason'] = probe.reason
    except asyncio.CancelledError:
        report.update(status='interrupted', stop_reason='cancelled', phase=phase)
        raise
    except Exception as exc:
        report.update(status='stopped', stop_reason=probe.reason or type(exc).__name__, phase=phase,
                      error_type=type(exc).__name__)
    finally:
        if phase == 'discovery':
            report['discovery'].update(requests=list(probe.requests), recoveries=probe.recoveries,
                                       seconds=time.perf_counter() - probe.started)
        elif report['batch'] is None:
            report['partial_requests'] = list(probe.requests)
        save(report, args.output)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile-dir', type=Path, default=PROFILE, help='Existing stable Price Watch Chrome profile')
    parser.add_argument('--concurrency', type=int, help='Maximum active requests; omitted means no cap. No rate limit in either mode.')
    parser.add_argument('--seed-product-ids', nargs='+', help='Public product IDs for separate SKU discovery')
    parser.add_argument('--articles-file', type=Path, help='JSON array of exactly 40 fixed productId:skuId pairs')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.concurrency is not None and args.concurrency <= 0:
        parser.error('--concurrency must be positive')
    args.profile_dir = args.profile_dir.expanduser().resolve()
    if not args.profile_dir.is_dir():
        parser.error('Use the existing stable profile; do not create a new experimental profile')
    if args.articles_file and args.seed_product_ids:
        parser.error('Use --articles-file or --seed-product-ids, not both')
    if args.seed_product_ids:
        for product_id in args.seed_product_ids:
            if not product_id.isascii() or not product_id.isdigit():
                parser.error('--seed-product-ids requires numeric product IDs')
    args.articles = validate_articles(json.loads(args.articles_file.read_text())) if args.articles_file else []
    report = asyncio.run(run(args))
    print(json.dumps({'status': report['status'], 'stop_reason': report.get('stop_reason'),
                      'batch': {k: v for k, v in (report['batch'] or {}).items() if k not in ('requests', 'results')},
                      'output': str(args.output)}, ensure_ascii=False))
    return 0 if report['status'] == 'complete' else 1


if __name__ == '__main__':
    raise SystemExit(main())
