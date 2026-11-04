"""API, storage, transfer and mixed execution in an isolated disposable schema."""
from tests.variant_tracking_support import manual_queue
import os
import json
import unittest
from contextlib import asynccontextmanager
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.engine import make_url
from marketplace_connector import ConnectorRegistry
from marketplace_connector.connectors.wildberries.client import AsyncWildberriesClient
from marketplace_connector.connectors.wildberries.connector import WildberriesConnector
from marketplace_connector.connectors.wildberries.identity import WildberriesRef
from price_watch.api import create_app
from price_watch.bootstrap import create_postgres_stores
from price_watch.application.run_executor import RunExecutor
from price_watch.infrastructure.postgres import AsyncDatabase, Database, MigrationRunner
from tests.test_wildberries_mapper import FIXTURE, REF
RAW = json.loads(FIXTURE.read_text())


@unittest.skipUnless(os.environ.get('TEST_DATABASE_URL'),'requires disposable TEST_DATABASE_URL')
class WildberriesIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        manual_queue(self)
        self.schema='wb_contract_'+uuid4().hex
        self.base=Database(os.environ['TEST_DATABASE_URL'])
        with self.base.engine.begin() as c:c.execute(text(f'CREATE SCHEMA {self.schema}'))
        url=make_url(self.base.url).update_query_dict({'options':'-csearch_path='+self.schema})
        self.sync=Database(str(url))
        with patch('logging.config.fileConfig'):
            MigrationRunner(self.sync).apply()
        self.db=await AsyncDatabase(str(url)).open()
        self.stores=create_postgres_stores(self.db)
        self.client=AsyncClient(transport=ASGITransport(app=create_app(services=self.stores.api)),base_url='http://test')

    async def asyncTearDown(self):
        await self.client.aclose()
        await self.db.close()
        self.sync.close()
        with self.base.engine.begin() as c:c.execute(text(f'DROP SCHEMA {self.schema} CASCADE'))
        self.base.close()

    async def test_two_sizes_create_duplicate_url_update_and_transfer_roundtrip(self):
        ids=[]
        for ref in [REF,'179224846:296499717']:
            result=await self.client.post('/api/cards',json={'marketplace':'wildberries','externalId':ref})
            self.assertEqual(result.status_code,201,result.text)
            self.assertEqual(result.json()['externalId'],ref.split(':')[0])
            ids.append(result.json()['id'])
        duplicate=await self.client.post('/api/cards',json={'marketplace':'wildberries','externalId':REF})
        self.assertEqual(duplicate.status_code,409)
        mismatch=await self.client.patch(f'/api/cards/{ids[0]}',json={'url':WildberriesRef.parse('1:2').url})
        self.assertEqual(mismatch.status_code,422)
        before=(await self.client.get(f'/api/cards/{ids[0]}')).json()
        self.assertEqual(before['externalId'],REF.split(':')[0])
        document=(await self.client.get('/api/cards/export')).json()
        for card_id in set(ids):self.assertEqual((await self.client.delete(f'/api/cards/{card_id}')).status_code,204)
        imported=await self.client.post('/api/cards/import',json=document)
        self.assertEqual(imported.status_code,200,imported.text)
        exported=(await self.client.get('/api/cards/export')).json()
        self.assertEqual({v['externalId'] for c in exported['cards'] for v in c['variants']},{REF,'179224846:296499717'})
        document['cards'][0]['variants'][0]['externalId']='179224846'
        self.assertEqual((await self.client.post('/api/cards/import',json=document)).status_code,422)

    async def test_wrong_discovery_response_preserves_history_and_neighbor_success(self):
        with self.sync.engine.begin() as c:
            c.execute(text("INSERT INTO marketplace_cards(marketplace,external_id) VALUES ('wildberries','999999999')"))
            c.execute(text("INSERT INTO card_variants(card_id,external_id,product_title) VALUES (1,'999999999','Legacy')"))
            c.execute(text('UPDATE marketplace_cards SET primary_variant_id=1 WHERE id=1'))
            c.execute(text("INSERT INTO price_history(card_id,variant_id,price,availability,observed_at,snapshot) VALUES (1,1,500,'in_stock',now(),'{\"keep\": true}')"))
            before=c.execute(text('SELECT * FROM marketplace_cards WHERE id=1')).one()
            history=c.execute(text('SELECT * FROM price_history WHERE card_id=1')).all()
        exported = await self.client.get('/api/cards/export')
        self.assertEqual(exported.status_code, 200)
        self.assertEqual(exported.json()['cards'][0]['externalId'], '999999999')
        self.assertEqual(exported.json()['cards'][0]['variants'][0]['history'][0]['price'], '500.00')
        self.assertEqual((await self.client.post('/api/cards/import', json=exported.json())).status_code, 200)
        valid=await self.stores.cards.add_card('wildberries',REF)
        client=AsyncWildberriesClient('/tmp/unused-ali-profile')
        @asynccontextmanager
        async def no_browser():yield
        client.collection_session=no_browser
        # Keep production identity validation, intercept only its browser transport.
        transport=MagicMock(fetch=AsyncMock(return_value=RAW))
        @asynccontextmanager
        async def request_session():yield transport
        client._request_session=request_session
        async def factory(run):return ConnectorRegistry([WildberriesConnector(client)])
        run=await RunExecutor(self.stores.runs,factory).collect()
        self.assertEqual((run.success_count,run.failure_count),(1,1))
        self.assertEqual(transport.fetch.await_count,2)
        transport.fetch.assert_any_await(REF)
        transport.fetch.assert_any_await('999999999')
        with self.sync.engine.connect() as c:
            self.assertEqual(c.execute(text('SELECT * FROM marketplace_cards WHERE id=1')).one(),before)
            self.assertEqual(c.execute(text('SELECT * FROM price_history WHERE card_id=1')).all(),history)
            self.assertEqual(c.scalar(text('SELECT price FROM price_history WHERE card_id=:id'),{'id':valid.id}),1024)
        errors=(await self.client.get(f'/api/runs/{run.run_id}')).json()['errors']
        self.assertIn('ответ другого товара',errors[0]['message'])

    async def test_direct_cli_and_queued_worker_share_one_price_and_history(self):
        import asyncio
        import subprocess
        import sys
        from decimal import Decimal
        from price_watch.worker import CollectionWorker
        card = await self.stores.cards.add_card('wildberries', REF)
        script = '''
import runpy,sys,json
from pathlib import Path
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock,patch
from marketplace_connector import ConnectorRegistry
from marketplace_connector.connectors.wildberries.client import AsyncWildberriesClient
from marketplace_connector.connectors.wildberries.connector import WildberriesConnector
client=AsyncWildberriesClient('/tmp/unused-wb-cli')
@asynccontextmanager
async def session():yield
@asynccontextmanager
async def request():
    from unittest.mock import MagicMock
    yield MagicMock(fetch=AsyncMock(return_value=json.loads(Path('tests/fixtures/wildberries/runtime-product.json').read_text())))
client.collection_session=session
client._request_session=request
with patch('price_watch.cli._build_connectors',return_value=ConnectorRegistry([WildberriesConnector(client)])):
    sys.argv=['main.py','collect','--card-id',sys.argv[1]]
    runpy.run_path('main.py',run_name='__main__')
'''
        result = await asyncio.to_thread(subprocess.run, [sys.executable,'-c',script,str(card.id)],
            env={**os.environ,'DATABASE_URL':self.sync.url},capture_output=True,text=True,timeout=20)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(json.loads(result.stdout)['success_count'],1)
        self.assertEqual((await self.stores.cards.get_card(card.id)).current_price,Decimal('1024.00'))
        queued=await self.client.post('/api/runs',json={'cardId':card.id})
        self.assertEqual(queued.status_code,202,queued.text)
        client=AsyncWildberriesClient('/tmp/unused-wb-worker')
        @asynccontextmanager
        async def session():yield
        @asynccontextmanager
        async def request():yield MagicMock(fetch=AsyncMock(return_value=RAW))
        client.collection_session=session
        client._request_session=request
        async def factory(run):return ConnectorRegistry([WildberriesConnector(client)])
        self.assertTrue(await CollectionWorker(self.stores.runs,factory,execution=self.stores.runs).run_once())
        self.assertEqual(await self.stores.history.count_history(card.id,30),1)
        detail=(await self.client.get(f'/api/cards/{card.id}')).json()
        self.assertEqual(detail['currentPrice'],'1024.00')
        with self.sync.engine.connect() as connection:
            snapshot=connection.scalar(text('SELECT snapshot FROM price_history WHERE card_id=:id'),{'id':card.id})
        self.assertNotIn('1056',json.dumps(snapshot))
        self.assertNotIn('paymentDiscountAmount',json.dumps(snapshot))

    async def test_schedule_and_retry_keep_exact_wb_size(self):
        from marketplace_connector.domain.errors import MarketplaceUnavailable
        from price_watch.worker import CollectionWorker
        card = await self.stores.cards.add_card('wildberries', REF)
        scheduled = await self.stores.runs.create_due_run()
        self.assertIsNotNone(scheduled)
        self.assertEqual([target.ref.external_id for target in await self.stores.runs.cards_for_run(scheduled.id)], [REF])
        transport = MagicMock(fetch=AsyncMock(side_effect=MarketplaceUnavailable('Synthetic transient error')))
        client=AsyncWildberriesClient('/tmp/unused-wb-schedule')
        @asynccontextmanager
        async def session(): yield
        @asynccontextmanager
        async def request(): yield transport
        client.collection_session=session
        client._request_session=request
        async def factory(run): return ConnectorRegistry([WildberriesConnector(client)])
        worker=CollectionWorker(self.stores.runs,factory,execution=self.stores.runs)
        self.assertTrue(await worker.run_once())
        self.assertEqual(await self.stores.history.count_history(card.id,30),0)
        retry=await self.stores.runs.create_retry_run(scheduled.id)
        self.assertEqual([target.ref.external_id for target in await self.stores.runs.cards_for_run(retry.id)], [REF])
        transport.fetch.side_effect=None
        transport.fetch.return_value=RAW
        self.assertTrue(await worker.run_once())
        self.assertEqual((await self.stores.cards.get_card(card.id)).current_price,1024)
        self.assertEqual(await self.stores.history.count_history(card.id,30),1)
