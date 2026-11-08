"""Shared execution lifecycle with deterministic connectors and persistence doubles."""
import asyncio
from contextlib import asynccontextmanager
from dataclasses import replace
from datetime import datetime, timezone
import unittest
from unittest.mock import AsyncMock, patch
from marketplace_connector import Availability, ConnectorRegistry, ProductRef, MarketplaceCard
from marketplace_connector.domain.errors import ProductNotFound, MarketplaceUnavailable, MarketplaceSchemaChanged, RateLimited
from price_watch.application.run_executor import RunExecutor
from price_watch.domain.models import CollectionRun, TrackedCard, LeaseLost


def card(i, deals_enabled=True):
    now = datetime.now(timezone.utc)
    return TrackedCard(i, ProductRef('ozon', str(i)), f'Card {i}', '', deals_enabled, now, now)


class FakeRepository:
    def __init__(self, cards):
        self.cards = cards
        self.saved = []
        self.errors = []
        self.current = []
        self.lost = False
        self.run = None
    async def start_direct_run(self, card_id=None):
        self.targets = [c for c in self.cards if card_id is None or c.id == card_id]
        if not self.targets:
            raise LookupError('Карточка не найдена')
        now = datetime.now(timezone.utc)
        self.run = CollectionRun(42, 'running', len(self.targets), 0, 0, card_id, None, None, None, None, None, now, None, owner_token='owner')
        return self.run
    async def cards_for_run(self, run_id, pending_only=False):
        done = {c.id for c, _ in self.saved} | {e['cardId'] for e in self.errors}
        return [c for c in self.targets if not pending_only or c.id not in done]
    async def touch_run(self, lease): return not self.lost
    async def set_run_current(self, lease, item):
        if self.lost: raise LeaseLost('lost')
        self.current.append(item.id)
    async def save_result(self, lease, item, snapshot):
        if snapshot.ref != ProductRef(item.ref.marketplace, item.ref.external_id): raise ValueError('Другая карточка')
        self.saved.append((item, snapshot))
        self.run = replace(self.run, success_count=self.run.success_count+1)
    async def record_card_error(self, lease, item, error):
        self.errors.append(error)
        self.run = replace(self.run, failure_count=self.run.failure_count+1)
    async def finish_run(self, lease):
        self.run = replace(self.run, status='completed_with_errors' if self.run.failure_count else 'completed')
        return self.run
    async def fail_run(self, lease, error):
        self.errors.append(error)
        self.run = replace(self.run, status='failed')


class Connector:
    marketplace = 'ozon'
    def __init__(self, failed=(), missing=(), mismatch=False):
        self.failed, self.missing, self.mismatch = failed, missing, mismatch
        self.opens = self.closes = self.active = self.peak = 0
    @asynccontextmanager
    async def collection_session(self):
        self.opens += 1
        try: yield
        finally: self.closes += 1
    async def get_product(self, external_id):
        self.active += 1
        self.peak = max(self.peak, self.active)
        try:
            await asyncio.sleep(.001)
            if external_id in self.failed: raise RuntimeError('fetch failed')
            if external_id in self.missing: raise ProductNotFound('missing')
            return MarketplaceCard(ref=ProductRef('ozon', 'other' if self.mismatch else external_id), title='Fetched',
                url='https://example.test/product', price=100, availability=Availability.IN_STOCK)
        finally: self.active -= 1


class CollectionServiceTests(unittest.IsolatedAsyncioTestCase):
    def executor(self, repository, connector, **kwargs):
        async def factory(run): return ConnectorRegistry([connector])
        return RunExecutor(repository, factory, **kwargs)

    async def test_retry_is_pending_until_success_and_successful_neighbors_are_not_repeated(self):
        repo, connector = FakeRepository([card(1), card(2)]), Connector()
        original = connector.get_product
        calls = []
        async def get_product(external_id):
            calls.append(external_id)
            if external_id == '1' and calls.count('1') == 1:
                raise MarketplaceSchemaChanged('first response')
            return await original(external_id)
        connector.get_product = get_product
        entered, release = asyncio.Event(), asyncio.Event()
        async def delay(seconds):
            self.assertEqual(seconds, 1)
            entered.set()
            await release.wait()
        with patch('marketplace_connector.application.retry.sleep', side_effect=delay):
            task = asyncio.create_task(self.executor(repo, connector).collect())
            try:
                await asyncio.wait_for(entered.wait(), 1)
                self.assertEqual(repo.errors, [])
                self.assertEqual(repo.run.failure_count, 0)
                self.assertEqual(repo.run.status, 'running')
                release.set()
                result = await task
            finally:
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
        self.assertEqual((result.success_count, result.failure_count), (2, 0))
        self.assertEqual(calls.count('1'), 2)
        self.assertEqual(calls.count('2'), 1)
        self.assertEqual(len(repo.saved), 2)

    async def test_persistence_failure_does_not_fetch_again(self):
        repo, connector = FakeRepository([card(1)]), Connector()
        connector.get_product = AsyncMock(wraps=connector.get_product)
        repo.save_result = AsyncMock(side_effect=RuntimeError('write failed'))
        result = await self.executor(repo, connector).collect()
        self.assertEqual(connector.get_product.await_count, 1)
        self.assertEqual(result.failure_count, 1)

    async def test_lease_loss_during_retry_delay_cancels_second_attempt(self):
        repo, connector = FakeRepository([card(1)]), Connector()
        connector.get_product = AsyncMock(side_effect=RuntimeError('temporary'))
        entered = asyncio.Event()
        async def delay(seconds):
            entered.set()
            await asyncio.Event().wait()
        with patch('marketplace_connector.application.retry.sleep', side_effect=delay):
            task = asyncio.create_task(self.executor(repo, connector, heartbeat_interval=.001).collect())
            await asyncio.wait_for(entered.wait(), 1)
            repo.lost = True
            with self.assertRaises(LeaseLost):
                await asyncio.wait_for(task, 1)
        self.assertEqual(connector.get_product.await_count, 1)
        self.assertEqual(connector.closes, 1)
        self.assertEqual(repo.errors, [])

    async def test_retry_delay_does_not_hold_a_fetch_slot(self):
        repo, connector = FakeRepository([card(i) for i in range(9)]), Connector()
        entered, last_started = asyncio.Event(), asyncio.Event()
        calls = []
        async def get_product(external_id):
            calls.append(external_id)
            if external_id != '8' and calls.count(external_id) == 1:
                raise RuntimeError('temporary')
            if external_id == '8':
                last_started.set()
            return MarketplaceCard(ref=ProductRef('ozon', external_id), title='Fetched',
                                 url='', availability=Availability.OUT_OF_STOCK)
        connector.get_product = get_product
        async def delay(seconds):
            entered.set()
            await last_started.wait()
        with patch('marketplace_connector.application.retry.sleep', side_effect=delay):
            result = await asyncio.wait_for(self.executor(repo, connector).collect(), 1)
        self.assertTrue(entered.is_set())
        self.assertEqual(result.success_count, 9)

    async def test_two_fetch_failures_record_one_error_with_both_attempts(self):
        repo, connector = FakeRepository([card(1)]), Connector()
        connector.get_product = AsyncMock(side_effect=[RuntimeError('first'), RuntimeError('last')])
        with patch('marketplace_connector.application.retry.sleep', new_callable=AsyncMock):
            result = await self.executor(repo, connector).collect()
        self.assertEqual((result.success_count, result.failure_count), (0, 1))
        self.assertEqual(len(repo.errors), 1)
        self.assertIn('first', repo.errors[0]['traceback'])
        self.assertIn('last', repo.errors[0]['traceback'])
        self.assertEqual(repo.saved, [])

    async def test_limits_ozon_to_eight_and_keeps_individual_errors(self):
        repo, connector = FakeRepository([card(i) for i in range(9)]), Connector(failed=['3'])
        with self.assertLogs('price_watch.application.collection_service', level='ERROR'):
            result = await self.executor(repo, connector).collect()
        self.assertEqual(connector.peak, 8)
        self.assertEqual((connector.opens, connector.closes), (1,1))
        self.assertEqual((result.success_count, result.failure_count), (8,1))
        self.assertIn('fetch failed', repo.errors[0]['traceback'])

    async def test_mixed_run_has_eight_ozon_slots_and_shared_five_other_slots(self):
        release = asyncio.Event()
        ready = {'ozon': asyncio.Event(), 'other': asyncio.Event()}
        active = {'ozon': 0, 'other': 0}
        peak = dict(active)
        class Waiting(Connector):
            def __init__(self, marketplace):
                super().__init__()
                self.marketplace = marketplace
            async def get_product(self, external_id):
                group = 'ozon' if self.marketplace == 'ozon' else 'other'
                active[group] += 1
                peak[group] = max(peak[group], active[group])
                if active[group] == (8 if group == 'ozon' else 5):
                    ready[group].set()
                try:
                    await release.wait()
                    return MarketplaceCard(ref=ProductRef(self.marketplace, external_id),
                                         title='Fetched', url='', availability=Availability.OUT_OF_STOCK)
                finally:
                    active[group] -= 1
        connectors = [Waiting(m) for m in ('ozon', 'wildberries', 'aliexpress')]
        cards = [replace(card(i), ref=ProductRef(connectors[i % 3].marketplace, str(i)))
                 for i in range(36)]
        repo = FakeRepository(cards)
        async def factory(run):
            return ConnectorRegistry(connectors)
        task = asyncio.create_task(RunExecutor(repo, factory).collect())
        try:
            await asyncio.wait_for(asyncio.gather(*(event.wait() for event in ready.values())), 1)
            self.assertEqual(active, {'ozon': 8, 'other': 5})
        finally:
            release.set()
            result = await task
        self.assertEqual(peak, {'ozon': 8, 'other': 5})
        self.assertEqual(result.success_count, 36)
        self.assertEqual([(c.opens, c.closes) for c in connectors], [(1, 1)] * 3)

    async def test_excluded_card_still_collects_and_single_collect_is_scoped(self):
        repo = FakeRepository([card(1),card(2,False)])
        result = await self.executor(repo, Connector()).collect()
        self.assertEqual(result.success_count, 2)
        repo.saved.clear()
        await self.executor(repo, Connector()).collect(2)
        self.assertEqual([c.id for c, _ in repo.saved], [2])

    async def test_missing_is_successful_unavailable(self):
        repo = FakeRepository([card(1)])
        result = await self.executor(repo, Connector(missing=['1'])).collect()
        self.assertEqual(result.success_count, 1)
        snapshot = repo.saved[0][1]
        self.assertEqual(snapshot.availability, Availability.OUT_OF_STOCK)
        self.assertEqual(snapshot.title, 'Card 1')
        self.assertIsNone(snapshot.price)

    async def test_transport_errors_do_not_write_successful_price_or_out_of_stock(self):
        for error in (MarketplaceUnavailable('HTTP 403'), MarketplaceSchemaChanged('JSON'), RateLimited('429')):
            with self.subTest(error=type(error).__name__):
                class Rejected(Connector):
                    async def get_product(self, external_id):
                        raise error
                repo, connector = FakeRepository([card(1)]), Rejected()
                with self.assertLogs('price_watch.application.collection_service', level='ERROR'):
                    result = await self.executor(repo, connector).collect()
                self.assertEqual((result.success_count, result.failure_count), (0, 1))
                self.assertFalse(repo.saved)
                self.assertEqual(connector.closes, 1)

    async def test_mismatch_is_recorded_and_session_closed(self):
        repo, connector = FakeRepository([card(1)]), Connector(mismatch=True)
        with self.assertLogs('price_watch.application.collection_service', level='ERROR'):
            result = await self.executor(repo, connector).collect()
        self.assertEqual(result.failure_count, 1)
        self.assertEqual(connector.closes, 1)
        self.assertFalse(repo.saved)

    async def test_factory_failure_marks_run_failed(self):
        repo = FakeRepository([card(1)])
        async def factory(run): raise RuntimeError('browser startup failed')
        with self.assertRaisesRegex(RuntimeError, 'browser startup'):
            await RunExecutor(repo, factory).collect()
        self.assertEqual(repo.run.status, 'failed')
        self.assertIsNone(repo.errors[0]['cardId'])

    async def test_session_failure_marks_run_failed(self):
        class Broken(Connector):
            @asynccontextmanager
            async def collection_session(self):
                raise RuntimeError('session failed')
                yield
        repo = FakeRepository([card(1)])
        with self.assertRaisesRegex(RuntimeError, 'session failed'):
            await self.executor(repo, Broken()).collect()
        self.assertEqual(repo.run.status, 'failed')

    async def test_heartbeat_loss_cancels_fetch_and_closes_without_stale_finish(self):
        entered = asyncio.Event()
        class Waiting(Connector):
            async def get_product(self, external_id):
                entered.set()
                await asyncio.Event().wait()
        repo, connector = FakeRepository([card(1)]), Waiting()
        task = asyncio.create_task(self.executor(repo, connector, heartbeat_interval=.001).collect())
        await asyncio.wait_for(entered.wait(), 1)
        repo.lost = True
        with self.assertRaises(LeaseLost): await asyncio.wait_for(task, 1)
        self.assertEqual(connector.closes, 1)
        self.assertFalse(repo.errors)
        self.assertEqual(repo.run.status, 'running')

    async def test_cancel_closes_session_and_records_failure(self):
        entered = asyncio.Event()
        class Waiting(Connector):
            async def get_product(self, external_id):
                entered.set()
                await asyncio.Event().wait()
        repo, connector = FakeRepository([card(1)]), Waiting()
        task = asyncio.create_task(self.executor(repo, connector).collect())
        await asyncio.wait_for(entered.wait(), 1)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError): await task
        self.assertEqual(connector.closes, 1)
        self.assertEqual(repo.run.status, 'failed')

    async def test_unknown_card_does_not_create_run(self):
        repo = FakeRepository([card(1)])
        with self.assertRaises(LookupError): await self.executor(repo, Connector()).collect(99)
        self.assertIsNone(repo.run)
