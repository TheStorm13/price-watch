import asyncio
from datetime import datetime, timezone
import json
import os
import unittest
from uuid import uuid4
from unittest.mock import patch
from sqlalchemy import delete, event, text
from price_watch.domain.diagnostics import bounded_error, MAX_ERROR_BYTES
from price_watch.infrastructure.postgres import Database, AsyncDatabase, MigrationRunner
from price_watch.infrastructure.postgres.models import CollectionRunRecord, MarketplaceCardRecord
from price_watch.bootstrap import create_postgres_stores


class DiagnosticSizeTests(unittest.TestCase):
    def test_unicode_control_characters_and_long_fields_are_bounded(self):
        payload, limited = bounded_error({'cardId': 1, 'message':'\x00🔥'*10000, 'traceback':'я'*10000,
                                        'externalId':'1'*10000, 'type':'Bad', 'at':'now'})
        self.assertTrue(limited)
        self.assertLessEqual(len(json.dumps(payload,ensure_ascii=False).encode()),MAX_ERROR_BYTES)
        self.assertEqual(payload['cardId'],1)
        self.assertNotIn('\x00', payload['message'])


@unittest.skipUnless(os.environ.get('TEST_DATABASE_URL'), 'TEST_DATABASE_URL не задан')
class BoundedDiagnosticsTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        with patch('logging.config.fileConfig'), Database(os.environ['TEST_DATABASE_URL']) as db:
            MigrationRunner(db).apply()

    async def asyncSetUp(self):
        self.db = await AsyncDatabase(os.environ['TEST_DATABASE_URL']).open()
        self.stores = create_postgres_stores(self.db)
        self.cards = [await self.stores.cards.add_card('ozon',str(uuid4().int)) for _ in range(25)]
        self.ids=[]

    async def asyncTearDown(self):
        async with self.db.session() as s,s.begin():
            await s.execute(delete(CollectionRunRecord).where(CollectionRunRecord.id.in_(self.ids)))
            await s.execute(delete(MarketplaceCardRecord).where(MarketplaceCardRecord.id.in_([c.id for c in self.cards])))
        await self.db.close()

    async def owned(self):
        run=await self.stores.runs.start_direct_run()
        self.ids.append(run.id)
        return run

    def error(self,card):
        return {'cardId':card.id,'message':'bad','traceback':'trace','externalId':card.ref.external_id,
                'marketplace':'ozon','at':datetime.now(timezone.utc).isoformat(),'type':'Synthetic'}

    async def test_sample_cap_exact_results_and_general_error(self):
        run=await self.owned()
        for card in self.cards:
            await self.stores.runs.record_card_error(run.lease,card,self.error(card))
        await self.stores.runs.record_card_error(run.lease,self.cards[0],self.error(self.cards[0]))
        current=await self.stores.runs.get_run(run.id)
        self.assertEqual(current.failure_count,25)
        self.assertEqual(len(current.errors),20)
        self.assertEqual(current.diagnostics_status,'limited')
        await self.stores.runs.fail_run(run.lease,{'cardId':None,'message':'browser failed','traceback':'trace'})
        current=await self.stores.runs.get_run(run.id)
        self.assertEqual(len(current.errors),20)
        self.assertEqual(current.errors[-1]['message'],'browser failed')
        retry=await self.stores.runs.create_retry_run(run.id)
        self.ids.append(retry.id)
        self.assertEqual(retry.total_count,25)
        old=await self.stores.runs.get_run(run.id)
        self.assertEqual(old.errors,())
        self.assertEqual(old.diagnostics_status,'expired')

    async def test_zero_bytes_and_oversized_unicode_do_not_lose_target_result(self):
        run = await self.owned()
        error = self.error(self.cards[0])
        error.update(message='\x00🔥' * 10000, traceback='я' * 10000)
        await self.stores.runs.record_card_error(run.lease, self.cards[0], error)
        current = await self.stores.runs.get_run(run.id)
        self.assertEqual(current.failure_count, 1)
        self.assertEqual(current.diagnostics_status, 'limited')
        self.assertEqual(len(current.errors), 1)
        self.assertNotIn('\x00', current.errors[0]['message'])

    async def test_only_latest_creation_can_store_errors_even_if_previous_active(self):
        first=await self.owned()
        await self.stores.runs.record_card_error(first.lease,self.cards[0],self.error(self.cards[0]))
        next_run=await self.stores.runs.create_queued_run(self.cards[1].id)
        self.ids.append(next_run.id)
        await self.stores.runs.record_card_error(first.lease,self.cards[1],self.error(self.cards[1]))
        await self.stores.runs.fail_run(first.lease,{'message':'late general','cardId':None})
        old=await self.stores.runs.get_run(first.id)
        self.assertEqual(old.failure_count,2)
        self.assertEqual(old.errors,())
        self.assertEqual(old.diagnostics_status,'expired')

    async def test_concurrent_creation_and_old_writer_never_restore_expired_errors(self):
        first=await self.owned()
        new_run,_=await asyncio.gather(self.stores.runs.create_queued_run(self.cards[2].id),
            self.stores.runs.record_card_error(first.lease,self.cards[0],self.error(self.cards[0])))
        self.ids.append(new_run.id)
        current=await self.stores.runs.get_run(first.id)
        self.assertEqual(current.failure_count,1)
        self.assertEqual(current.errors,())

    async def test_creation_rollback_preserves_previous_diagnostics(self):
        first=await self.owned()
        await self.stores.runs.record_card_error(first.lease,self.cards[0],self.error(self.cards[0]))
        with self.assertRaises(RuntimeError):
            async with self.db.session() as s,s.begin():
                await s.execute(text('SELECT pg_advisory_xact_lock(578612391)'))
                await self.stores.runs._create_run(s,[self.cards[1]])
                raise RuntimeError('rollback')
        current=await self.stores.runs.get_run(first.id)
        self.assertEqual(len(current.errors),1)
        self.assertEqual(current.diagnostics_status,'complete')

    async def test_compact_reads_and_heartbeat_do_not_select_error_payload(self):
        run=await self.owned()
        statements=[]
        def capture(conn,cursor,statement,*args): statements.append(statement)
        event.listen(self.db.engine.sync_engine,'before_cursor_execute',capture)
        try:
            await self.stores.runs.get_run(run.id,include_errors=False)
            await self.stores.runs.list_runs()
            await self.stores.runs.touch_run(run.lease)
        finally:
            event.remove(self.db.engine.sync_engine,'before_cursor_execute',capture)
        for statement in statements:
            if statement.lstrip().upper().startswith('SELECT'):
                self.assertNotIn('collection_runs.errors',statement)
