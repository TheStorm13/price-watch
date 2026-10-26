"""API, storage, transfer and mixed execution in an isolated disposable schema."""
import os
import unittest
from contextlib import asynccontextmanager
from uuid import uuid4
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.engine import make_url
from marketplace_connector import ConnectorRegistry
from marketplace_connector.connectors.aliexpress.client import AsyncAliExpressClient
from marketplace_connector.connectors.aliexpress.connector import AliExpressConnector
from marketplace_connector.connectors.aliexpress.models import AliExpressResponse
from marketplace_connector.connectors.aliexpress.identity import AliExpressRef
from price_watch.api import create_app
from price_watch.bootstrap import create_postgres_stores
from price_watch.application.run_executor import RunExecutor
from price_watch.infrastructure.postgres import AsyncDatabase, Database, MigrationRunner
from tests.test_aliexpress_transport import RAW, REF
from datetime import datetime, timezone
import json


@unittest.skipUnless(os.environ.get('TEST_DATABASE_URL'),'requires disposable TEST_DATABASE_URL')
class AliExpressIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.schema='ali_contract_'+uuid4().hex
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

    async def test_two_skus_create_duplicate_url_update_and_transfer_roundtrip(self):
        ids=[]
        for ref in [REF,'1005009868651525:12000061135122692']:
            result=await self.client.post('/api/cards',json={'marketplace':'aliexpress','externalId':ref})
            self.assertEqual(result.status_code,201,result.text)
            self.assertEqual(result.json()['externalId'],ref)
            ids.append(result.json()['id'])
        duplicate=await self.client.post('/api/cards',json={'marketplace':'aliexpress','externalId':REF})
        self.assertEqual(duplicate.status_code,409)
        mismatch=await self.client.patch(f'/api/cards/{ids[0]}',json={'url':AliExpressRef.parse('1:2').url})
        self.assertEqual(mismatch.status_code,422)
        before=(await self.client.get(f'/api/cards/{ids[0]}')).json()
        self.assertEqual(before['externalId'],REF)
        document=(await self.client.get('/api/cards/export')).json()
        for card_id in ids:self.assertEqual((await self.client.delete(f'/api/cards/{card_id}')).status_code,204)
        imported=await self.client.post('/api/cards/import',json=document)
        self.assertEqual(imported.status_code,200,imported.text)
        exported=(await self.client.get('/api/cards/export')).json()
        self.assertEqual({c['externalId'] for c in exported['cards']},{REF,'1005009868651525:12000061135122692'})
        document['cards'][0]['externalId']='1005009868651525'
        self.assertEqual((await self.client.post('/api/cards/import',json=document)).status_code,422)

    async def test_legacy_card_error_preserves_all_fields_history_and_neighbor_success(self):
        with self.sync.engine.begin() as c:
            c.execute(text("INSERT INTO marketplace_cards(marketplace,external_id,title) VALUES ('aliexpress','1005009868651525','Legacy')"))
            c.execute(text("INSERT INTO price_history(card_id,price,availability,observed_at,snapshot) VALUES (1,500,'in_stock',now(),'{\"keep\": true}')"))
            before=c.execute(text('SELECT * FROM marketplace_cards WHERE id=1')).one()
            history=c.execute(text('SELECT * FROM price_history WHERE card_id=1')).all()
        exported = await self.client.get('/api/cards/export')
        self.assertEqual(exported.status_code, 200)
        self.assertEqual(exported.json()['cards'][0]['externalId'], '1005009868651525')
        self.assertEqual(exported.json()['cards'][0]['history'][0]['price'], '500.00')
        self.assertEqual((await self.client.post('/api/cards/import', json=exported.json())).status_code, 422)
        valid=await self.stores.cards.add_card('aliexpress',REF)
        client=AsyncAliExpressClient('/tmp/unused-ali-profile')
        @asynccontextmanager
        async def no_browser():yield
        client.collection_session=no_browser
        # Keep production identity validation, intercept only its browser transport.
        transport=MagicMock(fetch=AsyncMock(return_value=RAW))
        @asynccontextmanager
        async def request_session():yield transport
        client._request_session=request_session
        async def factory(run):return ConnectorRegistry([AliExpressConnector(client)])
        run=await RunExecutor(self.stores.runs,factory).collect()
        self.assertEqual((run.success_count,run.failure_count),(1,1))
        transport.fetch.assert_awaited_once_with(REF)
        with self.sync.engine.connect() as c:
            self.assertEqual(c.execute(text('SELECT * FROM marketplace_cards WHERE id=1')).one(),before)
            self.assertEqual(c.execute(text('SELECT * FROM price_history WHERE card_id=1')).all(),history)
            self.assertEqual(c.scalar(text('SELECT price FROM price_history WHERE card_id=:id'),{'id':valid.id}),77648)
        errors=(await self.client.get(f'/api/runs/{run.run_id}')).json()['errors']
        self.assertIn('Не указан SKU',errors[0]['message'])
