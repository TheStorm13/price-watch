"""Behavioral checks for owned execution on an explicitly disposable database."""
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import os
import unittest
from uuid import uuid4
from unittest.mock import patch

from sqlalchemy import delete, func, select, update
from marketplace_connector import Availability, ConnectorRegistry, ProductRef, ProductSnapshot
from price_analyzer.infrastructure.postgres import AsyncDatabase, Database, MigrationRunner, PostgresPriceAnalyzerRepository
from price_analyzer.infrastructure.postgres.models import CollectionRunRecord, MarketplaceCardRecord, PriceHistoryRecord

URL = os.environ.get('TEST_DATABASE_URL')


@unittest.skipUnless(URL, 'TEST_DATABASE_URL не задан')
class RunReliabilityTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        with Database(URL) as db:
            MigrationRunner(db).apply()

    async def asyncSetUp(self):
        self.db = await AsyncDatabase(URL).open()
        self.repo = PostgresPriceAnalyzerRepository(self.db)
        self.cards = [await self.repo.add_card('ozon', str(uuid4().int), title=f'Card {i}') for i in range(3)]
        self.run_ids = []

    async def asyncTearDown(self):
        async with self.db.session() as s, s.begin():
            await s.execute(delete(CollectionRunRecord).where(CollectionRunRecord.id.in_(self.run_ids)))
            await s.execute(delete(MarketplaceCardRecord).where(MarketplaceCardRecord.id.in_([c.id for c in self.cards])))
        await self.db.close()

    async def owned(self, card=None):
        run = await self.repo.start_direct_run(card.id if card else None)
        self.run_ids.append(run.id)
        return run

    def snapshot(self, card, price=100):
        return ProductSnapshot(ref=ProductRef(card.marketplace, card.external_id), title='Collected',
                               url='https://example.test/product', price=price, availability=Availability.IN_STOCK)

    async def expire(self, run):
        async with self.db.session() as s, s.begin():
            await s.execute(update(CollectionRunRecord).where(CollectionRunRecord.id == run.id)
                            .values(heartbeat_at=datetime.now(timezone.utc)-timedelta(minutes=2)))
        await self.repo.fail_stale_runs(datetime.now(timezone.utc)-timedelta(seconds=30))

    async def test_waiting_challenge_keeps_lease_alive_and_resumes(self):
        from price_analyzer.application.run_executor import RunExecutor
        from price_analyzer.worker.challenge import DatabaseChallengeHandler
        run = await self.owned(self.cards[0])
        waiting, heartbeats = asyncio.Event(), asyncio.Event()
        set_waiting, touch = self.repo.set_run_waiting, self.repo.touch_run
        beats = 0

        async def wait(*args, **kwargs):
            await set_waiting(*args, **kwargs)
            waiting.set()

        async def beat(lease):
            nonlocal beats
            result = await touch(lease)
            if waiting.is_set():
                beats += 1
                if beats >= 2:
                    heartbeats.set()
            return result

        handler = DatabaseChallengeHandler(self.repo, run.lease, poll_interval=.01)
        snapshot = self.snapshot(self.cards[0])

        class Connector:
            marketplace = 'ozon'

            @asynccontextmanager
            async def collection_session(self):
                await handler.handle_async('ozon', 'Synthetic verification')
                yield

            async def get_product(self, external_id):
                return snapshot

        async def factory(_run):
            return ConnectorRegistry([Connector()])

        with patch.object(self.repo, 'set_run_waiting', wait), patch.object(self.repo, 'touch_run', beat):
            task = asyncio.create_task(RunExecutor(self.repo, factory, heartbeat_interval=.01).execute(run))
            try:
                await asyncio.wait_for(heartbeats.wait(), 5)
                current = await self.repo.get_run(run.id)
                self.assertEqual(current.status, 'waiting_for_user')
                self.assertIsNotNone(current.owner_token)
                await self.repo.continue_run(run.id)
                self.assertEqual((await asyncio.wait_for(task, 5)).status, 'completed')
            finally:
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)

    async def test_unchanged_success_and_idempotent_result_are_not_retried(self):
        a, b, c = self.cards
        first = await self.owned(a)
        await self.repo.save_result(first.lease, a, self.snapshot(a))
        await self.repo.finish_run(first.lease)
        run = await self.owned()
        await self.repo.save_result(run.lease, a, self.snapshot(a))
        await self.repo.save_result(run.lease, a, self.snapshot(a))
        await self.repo.record_card_error(run.lease, b, {'cardId': b.id, 'message': 'failed'})
        await self.expire(run)
        loaded = await self.repo.get_run(run.id)
        self.assertEqual((loaded.success_count, loaded.failure_count), (1, 1))
        self.assertEqual(loaded.retryable_count, 2)
        self.assertEqual(await self.repo.count_history(a.id, 30), 1)
        retry = await self.repo.create_retry_run(run.id)
        self.run_ids.append(retry.id)
        self.assertEqual({x.id for x in await self.repo.cards_for_run(retry.id)}, {b.id, c.id})
        self.assertEqual((await self.repo.get_run(run.id)).retryable_count, 0)
        with self.assertRaises(ValueError):
            await self.repo.create_retry_run(run.id)

    async def test_all_executor_writes_are_rejected_after_recovery(self):
        from price_analyzer.domain.models import LeaseLost, RunLease
        run = await self.owned(self.cards[0])
        lease = run.lease
        card = self.cards[0]
        wrong = RunLease(run.id, 'not-the-owner')
        operations = lambda token: [
            self.repo.save_result(token, card, self.snapshot(card)),
            self.repo.set_run_current(token, card),
            self.repo.set_run_waiting(token, 'browser_verification', 'check'),
            self.repo.record_card_error(token, card, {'cardId': card.id}),
            self.repo.fail_run(token, {'message': 'stale error'}),
            self.repo.finish_run(token),
        ]
        # Generate/await one coroutine at a time to avoid unawaited coroutine leaks.
        for token in [wrong, lease]:
            if token == lease:
                await self.expire(run)
            for operation in operations(token):
                with self.assertRaises(LeaseLost):
                    await operation
            self.assertFalse(await self.repo.touch_run(token))
        loaded = await self.repo.get_run(run.id)
        self.assertEqual(loaded.status, 'failed')
        self.assertEqual((loaded.success_count, loaded.failure_count), (0, 0))
        self.assertEqual(await self.repo.count_history(card.id, 30), 0)
        self.assertEqual((await self.repo.get_card(card.id)).card.title, card.title)
        with self.assertRaises(ValueError):
            await self.repo.continue_run(run.id)

    async def test_ownerless_cli_recovers_without_resetting_six_hour_clock(self):
        run = await self.owned()
        async with self.db.session() as s, s.begin():
            latest = await s.scalar(select(func.max(CollectionRunRecord.started_at)))
            observation = max(latest, datetime.now(timezone.utc))+timedelta(hours=14)
            await s.execute(update(CollectionRunRecord).where(CollectionRunRecord.id == run.id).values(
                worker_id=None, heartbeat_at=None, started_at=observation-timedelta(hours=7)))
        await self.repo.fail_stale_runs(observation-timedelta(seconds=30))
        due = await self.repo.create_due_run(observation)
        self.assertIsNotNone(due)
        self.run_ids.append(due.id)
        self.assertIsNone(await self.repo.create_due_run(observation))

    async def test_factory_failure_keeps_all_targets_retryable(self):
        from price_analyzer.application.run_executor import RunExecutor
        async def factory(run):
            self.run_ids.append(run.id)
            raise RuntimeError('browser startup failed')
        with self.assertRaisesRegex(RuntimeError, 'browser startup'):
            await RunExecutor(self.repo, factory).collect(self.cards[0].id)
        run = await self.repo.get_run(self.run_ids[-1])
        self.assertEqual(run.status, 'failed')
        self.assertEqual(run.retryable_count, 1)
        self.assertIsNone(run.errors[0]['cardId'])

    async def test_result_rollback_preserves_pending_target(self):
        run = await self.owned(self.cards[0])
        with patch('price_analyzer.infrastructure.postgres.history_repository.snapshot_to_dict', side_effect=RuntimeError('serialization failed')):
            with self.assertRaisesRegex(RuntimeError, 'serialization failed'):
                await self.repo.save_result(run.lease, self.cards[0], self.snapshot(self.cards[0]))
        loaded = await self.repo.get_run(run.id)
        self.assertEqual(loaded.success_count, 0)
        self.assertEqual(await self.repo.count_history(self.cards[0].id, 30), 0)
        self.assertEqual((await self.repo.get_card(self.cards[0].id)).card.title, self.cards[0].title)
        await self.repo.save_result(run.lease, self.cards[0], self.snapshot(self.cards[0]))
        await self.repo.finish_run(run.lease)
        self.assertEqual((await self.repo.get_run(run.id)).status, 'completed')

    async def test_concurrent_retry_creates_only_one_child(self):
        run = await self.owned(self.cards[0])
        await self.repo.fail_run(run.lease, {'cardId': None, 'message': 'startup'})
        results = await asyncio.gather(self.repo.create_retry_run(run.id), self.repo.create_retry_run(run.id),
                                       return_exceptions=True)
        children = [r for r in results if not isinstance(r, Exception)]
        self.assertEqual(len(children), 1)
        self.run_ids.extend(r.id for r in children)
        self.assertEqual(sum(isinstance(r, ValueError) for r in results), 1)

    async def test_reaper_cannot_revoke_during_atomic_result(self):
        run = await self.owned(self.cards[0])
        locked, commit = asyncio.Event(), asyncio.Event()
        original = self.repo._begin_result
        async def hold(session, lease, card_id, status, error=None):
            row = await original(session, lease, card_id, status, error)
            locked.set()
            await commit.wait()
            return row
        async with self.db.session() as s, s.begin():
            await s.execute(update(CollectionRunRecord).where(CollectionRunRecord.id == run.id)
                            .values(heartbeat_at=datetime.now(timezone.utc)-timedelta(minutes=2)))
        with patch.object(self.repo, '_begin_result', hold):
            saving = asyncio.create_task(self.repo.save_result(run.lease, self.cards[0], self.snapshot(self.cards[0])))
            try:
                await asyncio.wait_for(locked.wait(), 3)
                self.assertEqual(await self.repo.fail_stale_runs(datetime.now(timezone.utc)-timedelta(seconds=30)), 0)
                from price_analyzer.infrastructure.postgres.repository import CardInActiveRun, ImportDuringRun
                with self.assertRaises(CardInActiveRun):
                    await self.repo.delete_card(self.cards[0].id)
                with self.assertRaises(ImportDuringRun):
                    await self.repo.import_cards([])
            finally:
                commit.set()
                await saving
        self.assertEqual((await self.repo.get_run(run.id)).success_count, 1)
        await self.repo.finish_run(run.lease)

    async def test_unknown_and_incomplete_targets_use_the_same_retry_model(self):
        from price_analyzer.infrastructure.postgres.models import CollectionRunTargetRecord
        run = await self.owned(self.cards[0])
        async with self.db.session() as s, s.begin():
            (await s.get(CollectionRunRecord, run.id)).targets_complete = False
            (await s.get(CollectionRunTargetRecord, (run.id, self.cards[0].id))).status = 'unknown'
        from price_analyzer.application.run_executor import RunExecutor
        async def must_not_open_browser(run):
            self.fail('Incomplete run opened a browser')
        with self.assertRaisesRegex(ValueError, 'не полностью'):
            await RunExecutor(self.repo, must_not_open_browser).execute(await self.repo.get_run(run.id))
        failed = await self.repo.get_run(run.id)
        self.assertFalse(failed.targets_complete)
        self.assertEqual(failed.retryable_count, 1)
        retry = await self.repo.create_retry_run(run.id)
        self.run_ids.append(retry.id)
        self.assertTrue(retry.targets_complete)
        self.assertEqual([c.id for c in await self.repo.cards_for_run(retry.id)], [self.cards[0].id])

    async def test_waiting_continuation_cannot_revive_a_recovered_run(self):
        from price_analyzer.worker import DatabaseChallengeHandler
        run = await self.owned(self.cards[0])
        await self.repo.set_run_waiting(run.lease, 'browser_verification', 'check')
        self.assertEqual((await self.repo.continue_run(run.id)).status, 'running')
        await self.repo.set_run_waiting(run.lease, 'browser_verification', 'check')
        continuation = []
        original = self.repo._finish
        def race(record, status):
            # The reaper owns the row; the concurrent command must wait for commit.
            continuation.append(asyncio.create_task(self.repo.continue_run(run.id)))
            original(record, status)
        with patch.object(self.repo, '_finish', race):
            await self.expire(run)
        with self.assertRaises(ValueError):
            await continuation[0]
        from price_analyzer.domain.models import LeaseLost
        with self.assertRaises(LeaseLost):
            await self.repo.get_owned_status(run.lease)

    async def test_catalog_keeps_one_snapshot_during_collection_write(self):
        a, b, _ = self.cards
        first = await self.owned(a)
        await self.repo.save_result(first.lease, a, self.snapshot(a, 200))
        await self.repo.finish_run(first.lease)
        second = await self.owned(a)
        await self.repo.save_result(second.lease, a, self.snapshot(a, 100))
        await self.repo.finish_run(second.lease)
        other = await self.owned(b)
        await self.repo.save_result(other.lease, b, self.snapshot(b, 75))
        await self.repo.finish_run(other.lease)
        group_id = await self.repo.create_group('Snapshot', [a.id, b.id])
        writer = await self.owned(a)
        original = self.repo._list_card_price_metric_rows
        async def change_between_queries(session):
            await self.repo.save_result(writer.lease, a, self.snapshot(a, 50))
            return await original(session)
        try:
            with patch.object(self.repo, '_list_card_price_metric_rows', change_between_queries):
                before = await self.repo.get_catalog()
            item = next(c for c in before['cards'] if c['id'] == a.id)
            group = next(g for g in before['groups'] if g['id'] == group_id)
            self.assertEqual(item['current_price'], Decimal('100'))
            self.assertEqual(item['minimum_price'], Decimal('100'))
            self.assertEqual(group['representative_card_id'], b.id)
            after = await self.repo.get_catalog()
            self.assertEqual(next(c for c in after['cards'] if c['id'] == a.id)['current_price'], Decimal('50'))
            self.assertEqual(next(g for g in after['groups'] if g['id'] == group_id)['representative_card_id'], a.id)
            await self.repo.finish_run(writer.lease)
        finally:
            await self.repo.delete_group(group_id)

    async def test_killed_direct_cli_is_recovered_without_losing_saved_history(self):
        import json
        import sys
        import tempfile
        from pathlib import Path
        card = self.cards[0]
        first = await self.owned(card)
        await self.repo.save_result(first.lease, card, self.snapshot(card))
        await self.repo.finish_run(first.lease)
        script = '''
import asyncio,json,os,sys
from pathlib import Path
from price_analyzer.infrastructure.postgres import AsyncDatabase,PostgresPriceAnalyzerRepository
from price_analyzer.application.run_executor import RunExecutor
async def main():
    db=await AsyncDatabase(os.environ['TEST_DATABASE_URL']).open()
    repo=PostgresPriceAnalyzerRepository(db)
    async def factory(run):
        Path(sys.argv[2]).write_text(json.dumps({'id':run.id}))
        await asyncio.Event().wait()
    await RunExecutor(repo,factory,heartbeat_interval=.01).collect(int(sys.argv[1]))
asyncio.run(main())
'''
        with tempfile.TemporaryDirectory(prefix='rel-cli-') as root:
            marker = Path(root)/'ready.json'
            process = await asyncio.create_subprocess_exec(sys.executable, '-c', script, str(card.id), str(marker),
                stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE)
            try:
                async def ready():
                    while not marker.exists():
                        if process.returncode is not None:
                            self.fail((await process.stderr.read()).decode())
                        await asyncio.sleep(.01)
                await asyncio.wait_for(ready(), 5)
                run_id = json.loads(marker.read_text())['id']
                self.run_ids.append(run_id)
                process.kill()
                await process.wait()
                async with self.db.session() as s, s.begin():
                    await s.execute(update(CollectionRunRecord).where(CollectionRunRecord.id == run_id).values(
                        heartbeat_at=datetime.now(timezone.utc)-timedelta(minutes=2)))
                await self.repo.fail_stale_runs(datetime.now(timezone.utc)-timedelta(seconds=30))
                run = await self.repo.get_run(run_id)
                self.assertEqual((run.status, run.retryable_count), ('failed', 1))
                self.assertEqual(await self.repo.count_history(card.id, 30), 1)
            finally:
                if process.returncode is None:
                    process.kill()
                    await process.wait()
