"""Product ownership, exact SKU collection and data-preserving migration."""
import copy
import os
import unittest
from contextlib import asynccontextmanager
from decimal import Decimal
from unittest.mock import patch
from uuid import uuid4

from alembic import command
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.engine import make_url
from marketplace_connector import ConnectorRegistry
from marketplace_connector.domain.models import Availability, MarketplaceCard, ProductRef, ProductVariant
from price_watch.api import create_app
from price_watch.application.run_executor import RunExecutor
from price_watch.bootstrap import create_postgres_stores
from price_watch.domain.models import LeaseLost
from price_watch.infrastructure.postgres import AsyncDatabase, Database, MigrationRunner


class VariantConnector:
    marketplace = 'wildberries'

    def __init__(self, fail=()):
        self.fail = set(fail)
        self.calls = []
        self.sizes = ['10', '20']
        self.opens = 0

    @asynccontextmanager
    async def collection_session(self):
        self.opens += 1
        yield

    async def get_product(self, ref):
        self.calls.append(ref)
        article, size = ref.split(':')
        if size in self.fail:
            raise RuntimeError('Synthetic SKU failure')
        return MarketplaceCard(ProductRef(self.marketplace, ref), 'Товар', self.url(article, size), Availability.IN_STOCK,
            Decimal(size), variants=tuple(ProductVariant(ProductRef(self.marketplace, f'{article}:{s}'), f'Размер {s}',
            self.url(article,s), Availability.IN_STOCK, options={'Размер':s}) for s in self.sizes))

    @staticmethod
    def url(article, size):
        return f'https://www.wildberries.ru/catalog/{article}/detail.aspx?size={size}'


@unittest.skipUnless(os.environ.get('TEST_DATABASE_URL'), 'requires disposable TEST_DATABASE_URL')
class ProductVariantTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.schema = 'product_variants_' + uuid4().hex
        self.base = Database(os.environ['TEST_DATABASE_URL'])
        with self.base.engine.begin() as c:
            c.execute(text(f'CREATE SCHEMA {self.schema}'))
        self.sync = Database(str(make_url(self.base.url).update_query_dict({'options':'-csearch_path='+self.schema})))
        with patch('logging.config.fileConfig'):
            MigrationRunner(self.sync).apply()
        self.db = await AsyncDatabase(self.sync.url).open()
        self.stores = create_postgres_stores(self.db)
        self.client = AsyncClient(transport=ASGITransport(app=create_app(services=self.stores.api)), base_url='http://test')

    async def asyncTearDown(self):
        await self.client.aclose()
        await self.db.close()
        self.sync.close()
        with self.base.engine.begin() as c:
            c.execute(text(f'DROP SCHEMA {self.schema} CASCADE'))
        self.base.close()

    def executor(self, connector):
        async def factory(run):
            return ConnectorRegistry([connector])
        return RunExecutor(self.stores.runs, factory)

    async def add(self, ref='123:10'):
        response = await self.client.post('/api/cards', json={'marketplace':'wildberries','externalId':ref,'tags':['тест']})
        self.assertEqual(response.status_code,201,response.text)
        self.assertEqual(response.json()['externalId'],ref.split(':')[0])
        return response.json()

    async def test_discovery_collects_each_sku_and_primary_switch_preserves_history(self):
        card = await self.add()
        connector = VariantConnector()
        result = await self.executor(connector).collect(card['id'])
        self.assertEqual((result.total_count,result.success_count,result.failure_count),(2,2,0))
        self.assertEqual(connector.calls,['123:10','123:20'])
        self.assertEqual(connector.opens,1)
        variants = (await self.client.get(f'/api/cards/{card["id"]}/variants')).json()
        self.assertEqual([v['currentPrice'] for v in variants],['10.00','20.00'])
        before = (await self.client.get(f'/api/cards/{card["id"]}/chart')).json()
        self.assertEqual({p['variantId'] for p in before['points']},{v['id'] for v in variants})
        switched = await self.client.patch(f'/api/cards/{card["id"]}',json={'primaryVariantId':variants[1]['id']})
        self.assertEqual(switched.status_code,200,switched.text)
        self.assertEqual(switched.json()['currentPrice'],'20.00')
        catalog = (await self.client.get('/api/catalog')).json()
        self.assertEqual(len(catalog['cards']),1)
        self.assertEqual(catalog['cards'][0]['currentPrice'],'20.00')
        self.assertEqual((await self.client.get(f'/api/cards/{card["id"]}/chart')).json(),before)
        await self.executor(connector).collect(card['id'])
        self.assertEqual((await self.client.get(f'/api/cards/{card["id"]}/chart')).json(),before)
        filtered = (await self.client.get(f'/api/cards/{card["id"]}/history?variantId={variants[0]["id"]}')).json()
        self.assertEqual([h['price'] for h in filtered['history']],['10.00'])
        self.assertEqual(filtered['statistics']['minimumPrice'],'10.00')

    async def test_partial_error_retry_only_failed_and_stale_lease_rejected(self):
        card = await self.add()
        connector = VariantConnector(fail=['20'])
        result = await self.executor(connector).collect(card['id'])
        self.assertEqual((result.success_count,result.failure_count),(1,1))
        retry = await self.stores.runs.create_retry_run(result.run_id)
        targets = await self.stores.runs.cards_for_run(retry.id)
        self.assertEqual([c.ref.external_id for c in targets],['123:20'])
        owned = await self.stores.runs.claim_next_run()
        connector.fail.clear()
        connector.calls.clear()
        await self.executor(connector).execute(owned)
        self.assertEqual(connector.calls,['123:20'])
        snapshot = await connector.get_product('123:20')
        with self.assertRaises(LeaseLost):
            await self.stores.runs.save_result(owned.lease,targets[0],snapshot)
        self.assertEqual(len((await self.client.get(f'/api/cards/{card["id"]}/chart')).json()['points']),2)

    async def test_invalid_identity_and_foreign_primary_rejected_atomically(self):
        first, other = await self.add(), await self.add('456:10')
        path=f'/api/cards/{first["id"]}'
        for payload in ({'marketplace':'aliexpress'},{'externalId':'456'},{'primaryVariantId':other['primaryVariantId'],'title':'Must not change'},
                        {'url':VariantConnector.url('456','10')}):
            self.assertEqual((await self.client.patch(path,json=payload)).status_code,422)
        self.assertIsNone((await self.client.get(path)).json()['title'])
        self.assertEqual((await self.client.get(f'{path}/history?variantId={other["primaryVariantId"]}')).status_code,422)
        cleared=await self.client.patch(path,json={'title':None,'url':None,'tags':[]})
        self.assertEqual(cleared.status_code,200,cleared.text)
        self.assertEqual((cleared.json()['title'],cleared.json()['url'],cleared.json()['tags']),(None,None,[]))

    async def test_adding_known_variant_reuses_product_and_duplicate_is_conflict(self):
        first=await self.add()
        second=await self.add('123:20')
        self.assertEqual(first['id'],second['id'])
        self.assertEqual((await self.client.post('/api/cards',json={'marketplace':'wildberries','externalId':'123:20'})).status_code,409)
        self.assertEqual(len((await self.client.get('/api/catalog')).json()['cards']),1)

    async def test_transfer_v3_roundtrip_and_independent_merge(self):
        card=await self.add()
        await self.executor(VariantConnector()).collect(card['id'])
        variants=(await self.client.get(f'/api/cards/{card["id"]}/variants')).json()
        await self.client.patch(f'/api/cards/{card["id"]}',json={'primaryVariantId':variants[1]['id']})
        exported=(await self.client.get('/api/cards/export')).json()
        self.assertEqual(exported['version'],3)
        self.assertEqual(exported['cards'][0]['primaryExternalId'],'123:20')
        self.assertEqual((await self.client.delete(f'/api/cards/{card["id"]}')).status_code,204)
        imported=await self.client.post('/api/cards/import',json=exported)
        self.assertEqual(imported.status_code,200,imported.text)
        self.assertEqual((await self.client.get('/api/cards/export')).json(),exported)
        duplicate=await self.client.post('/api/cards/import',json=exported)
        self.assertEqual(duplicate.json()['observationsAdded'],0)
        bad=copy.deepcopy(exported);bad['cards'][0]['variants'][0]['externalId']='999:10'
        self.assertEqual((await self.client.post('/api/cards/import',json=bad)).status_code,422)
        old=copy.deepcopy(exported);old['version']=2
        self.assertEqual((await self.client.post('/api/cards/import',json=old)).status_code,422)


@unittest.skipUnless(os.environ.get('TEST_DATABASE_URL'), 'requires disposable TEST_DATABASE_URL')
class ProductVariantMigrationTests(unittest.TestCase):
    def setUp(self):
        self.schema='variant_migration_'+uuid4().hex
        self.base=Database(os.environ['TEST_DATABASE_URL'])
        with self.base.engine.begin() as c:c.execute(text(f'CREATE SCHEMA {self.schema}'))
        self.db=Database(str(make_url(self.base.url).update_query_dict({'options':'-csearch_path='+self.schema})))
        self.config=MigrationRunner(self.db)._config()
        with patch('logging.config.fileConfig'):command.upgrade(self.config,'0017_bounded_diagnostics')

    def tearDown(self):
        self.db.close()
        with self.base.engine.begin() as c:c.execute(text(f'DROP SCHEMA {self.schema} CASCADE'))
        self.base.close()

    def seed(self, conflict=False):
        with self.db.engine.begin() as c:
            c.execute(text("INSERT INTO marketplace_cards(id,marketplace,external_id,title,url) OVERRIDING SYSTEM VALUE VALUES (11,'wildberries','123:10','Товар','https://www.wildberries.ru/catalog/123/detail.aspx?size=10'),(22,'wildberries','123:20',:title,'https://www.wildberries.ru/catalog/123/detail.aspx?size=20'),(33,'aliexpress','999','Неполный',NULL)"),{'title':'Разное' if conflict else 'Товар'})
            c.execute(text("INSERT INTO price_history(card_id,price,availability,observed_at,snapshot) VALUES (11,10,'in_stock',now(),'{\"keep\": 1}'),(22,20,'in_stock',now(),'{\"keep\": 2}'),(33,30,'in_stock',now(),'{\"keep\": 3}')"))
            c.execute(text("INSERT INTO collection_runs(id,status,total_count,success_count) OVERRIDING SYSTEM VALUE VALUES (1,'completed',2,2)"))
            c.execute(text("INSERT INTO collection_run_targets(run_id,card_id,position,status) VALUES (1,11,0,'succeeded'),(1,22,1,'succeeded')"))

    def test_migration_keeps_ids_history_snapshot_and_distinct_targets(self):
        self.seed()
        with patch('logging.config.fileConfig'):command.upgrade(self.config,'head')
        with self.db.engine.connect() as c:
            self.assertEqual(c.execute(text('SELECT id,external_id FROM marketplace_cards ORDER BY id')).all(),[(11,'123'),(33,'999')])
            self.assertEqual(c.execute(text('SELECT id,card_id,external_id FROM card_variants ORDER BY id')).all(),[(11,11,'123:10'),(22,11,'123:20'),(33,33,'999')])
            rows=c.execute(text('SELECT card_id,variant_id,price,snapshot FROM price_history ORDER BY variant_id')).all()
            self.assertEqual([(r.card_id,r.variant_id,r.price,r.snapshot) for r in rows],[(11,11,10,{'keep':1}),(11,22,20,{'keep':2}),(33,33,30,{'keep':3})])
            self.assertEqual(c.execute(text('SELECT card_id,variant_id FROM collection_run_targets ORDER BY position')).all(),[(11,11),(11,22)])

    def test_conflict_fails_before_schema_or_data_change(self):
        self.seed(conflict=True)
        with patch('logging.config.fileConfig'),self.assertRaisesRegex(RuntimeError,'Конфликт'):
            command.upgrade(self.config,'head')
        with self.db.engine.connect() as c:
            self.assertEqual(c.scalar(text('SELECT count(*) FROM marketplace_cards')),3)
            self.assertEqual(c.scalar(text('SELECT count(*) FROM price_history')),3)
            self.assertIsNone(c.scalar(text("SELECT to_regclass('card_variants')")))
