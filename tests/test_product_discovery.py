"""Product-only discovery uses the real connectors and isolated PostgreSQL schemas."""
import json
import os
import unittest
from contextlib import asynccontextmanager
from dataclasses import replace
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

from sqlalchemy import text

from marketplace_connector.connectors.aliexpress.client import AsyncAliExpressClient
from marketplace_connector.connectors.aliexpress.connector import AliExpressConnector
from marketplace_connector.connectors.wildberries.client import AsyncWildberriesClient
from marketplace_connector.connectors.wildberries.connector import WildberriesConnector
from marketplace_connector.domain.errors import MarketplaceSchemaChanged
from price_watch.domain.models import LeaseLost
from tests import test_product_variants as variants_tests


@unittest.skipUnless(os.environ.get('TEST_DATABASE_URL'), 'requires disposable TEST_DATABASE_URL')
class ProductDiscoveryTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = variants_tests.ProductVariantTests.asyncSetUp
    asyncTearDown = variants_tests.ProductVariantTests.asyncTearDown
    executor = variants_tests.ProductVariantTests.executor
    def connector(self, marketplace, *, fail_discovery=False, fail_sku=None):
        fixture = 'wildberries/runtime-product.json' if marketplace == 'wildberries' else 'aliexpress/product-data.json'
        payload = json.loads((Path(__file__).parent / 'fixtures' / fixture).read_text())
        article = payload['product']['id'] if marketplace == 'wildberries' else payload['data']['id']
        if marketplace == 'wildberries':
            from copy import deepcopy
            row = deepcopy(payload['product']['sizes'][0])
            row['optionId'] = str(int(row['optionId']) + 1)
            row['price']['priceToShow'] = '205600'
            payload['product']['sizes'].append(row)
        variants = payload['product']['sizes'] if marketplace == 'wildberries' else payload['data']['skuInfo']['priceList']
        ids = [f"{article}:{row['optionId' if marketplace == 'wildberries' else 'skuId']}" for row in variants]
        client_type = AsyncWildberriesClient if marketplace == 'wildberries' else AsyncAliExpressClient
        client = client_type('/tmp/unused-synthetic-discovery-profile')

        async def fetch(ref):
            if ref == article and fail_discovery:
                raise MarketplaceSchemaChanged('Synthetic discovery failure')
            if ref == fail_sku:
                raise MarketplaceSchemaChanged('Synthetic SKU failure')
            if marketplace == 'aliexpress':
                # Return the requested exact SKU, or no selected SKU for discovery.
                data = json.loads(json.dumps(payload))
                data['data']['activeSkuId'] = ref.split(':')[1] if ':' in ref else None
                return json.dumps(data)
            return payload

        transport = MagicMock(fetch=AsyncMock(side_effect=fetch))
        @asynccontextmanager
        async def request_session():
            yield transport
        @asynccontextmanager
        async def collection_session():
            yield
        client._request_session = request_session
        client.collection_session = collection_session
        connector_type = WildberriesConnector if marketplace == 'wildberries' else AliExpressConnector
        return connector_type(client), transport, article, ids

    async def create_product(self, marketplace, article):
        result = await self.client.post('/api/cards', json={'marketplace': marketplace, 'externalId': article})
        self.assertEqual(result.status_code, 201, result.text)
        return result.json()

    async def test_product_only_collects_all_skus_then_targets_only_exact_variants(self):
        for marketplace in ('wildberries', 'aliexpress'):
            with self.subTest(marketplace=marketplace):
                connector, transport, article, ids = self.connector(marketplace)
                card = await self.create_product(marketplace, article)
                discovery_id = card['primaryVariantId']
                result = await self.executor(connector).collect(card['id'])
                self.assertEqual((result.total_count, result.success_count, result.failure_count), (len(ids)+1, len(ids)+1, 0))
                self.assertEqual([c.args[0] for c in transport.fetch.await_args_list], [article, *ids])
                variants = (await self.client.get(f'/api/cards/{card["id"]}/variants')).json()
                self.assertEqual([v['externalId'] for v in variants], ids)
                self.assertTrue(all(v['currentPrice'] is not None for v in variants))
                updated = (await self.client.get(f'/api/cards/{card["id"]}')).json()
                self.assertEqual(updated['primaryVariantId'], variants[0]['id'])
                self.assertNotEqual(updated['primaryVariantId'], discovery_id)
                self.assertEqual((await self.client.post('/api/cards', json={'marketplace':marketplace,'externalId':article})).status_code,409)
                chart = (await self.client.get(f'/api/cards/{card["id"]}/chart')).json()
                self.assertEqual({p['variantId'] for p in chart['points']}, {v['id'] for v in variants})
                transport.fetch.reset_mock()
                queued = await self.stores.runs.create_queued_run(card['id'])
                owned = await self.stores.runs.claim_next_run()
                self.assertEqual(queued.id, owned.id)
                second = await self.executor(connector).execute(owned)
                self.assertEqual((second.total_count, second.failure_count),(1,0))
                self.assertEqual([c.args[0] for c in transport.fetch.await_args_list], ids[:1])
                self.assertEqual((await self.client.get(f'/api/cards/{card["id"]}/chart')).json(),chart)
                exported = (await self.client.get('/api/cards/export')).json()
                imported = await self.client.post('/api/cards/import',json=exported)
                self.assertEqual(imported.status_code,200,imported.text)
                self.assertEqual(imported.json()['observationsAdded'],0)

    async def test_failed_discovery_retry_expands_but_sku_retry_stays_exact(self):
        for marketplace in ('wildberries', 'aliexpress'):
            with self.subTest(marketplace=marketplace):
                bad, _, article, ids = self.connector(marketplace, fail_discovery=True)
                card = await self.create_product(marketplace, article)
                failed = await self.executor(bad).collect(card['id'])
                self.assertEqual((failed.success_count,failed.failure_count),(0,1))
                await self.stores.runs.create_retry_run(failed.run_id)
                owned = await self.stores.runs.claim_next_run()
                partial, transport, _, _ = self.connector(marketplace, fail_sku=ids[-1])
                result = await self.executor(partial).execute(owned)
                self.assertEqual((result.total_count,result.success_count,result.failure_count),(len(ids)+1,len(ids),1))
                await self.stores.runs.create_retry_run(result.run_id)
                owned = await self.stores.runs.claim_next_run()
                targets = await self.stores.runs.cards_for_run(owned.id)
                self.assertEqual([c.ref.external_id for c in targets], [ids[-1]])
                good, transport, _, _ = self.connector(marketplace)
                result = await self.executor(good).execute(owned)
                self.assertEqual((result.total_count,result.success_count,result.failure_count),(1,1,0))
                self.assertEqual([c.args[0] for c in transport.fetch.await_args_list],[ids[-1]])

    async def test_unresolved_history_stays_separate_and_old_target_id_is_unchanged(self):
        connector, transport, article, ids = self.connector('wildberries')
        card = await self.create_product('wildberries',article)
        variant_id = card['primaryVariantId']
        async with self.db.session() as session, session.begin():
            await session.execute(text("INSERT INTO price_history(card_id,variant_id,price,availability,observed_at,snapshot) VALUES (:card,:variant,500,'in_stock',now(),'{\"keep\": true}')"),{'card':card['id'],'variant':variant_id})
        with self.sync.engine.connect() as c:
            before=c.execute(text('SELECT * FROM price_history WHERE variant_id=:id'),{'id':variant_id}).all()
        async with self.db.session() as session, session.begin():
            run = await self.stores.runs._create_run(session,
                await self.stores.runs._select_targets(session, card['id'], discover_all=True),
                card_id=card['id'], owner='initial-fixture', discover_all=True)
        target = (await self.stores.runs.cards_for_run(run.id))[0]
        snapshot = await connector.get_product(article)
        with self.assertRaises(LeaseLost):
            await self.stores.runs.save_result(replace(run.lease,owner_token='wrong'),target,snapshot)
        await self.stores.runs.save_result(run.lease,target,snapshot)
        # Duplicate result does not add targets/counters twice.
        await self.stores.runs.save_result(run.lease,target,snapshot)
        result = await self.executor(connector).execute(replace(run,total_count=len(ids)+1))
        self.assertEqual((result.total_count,result.success_count),(len(ids)+1,len(ids)+1))
        with self.sync.engine.connect() as c:
            self.assertEqual(c.execute(text('SELECT * FROM price_history WHERE variant_id=:id'),{'id':variant_id}).all(),before)
            self.assertEqual(c.scalar(text('SELECT external_id FROM card_variants WHERE id=:id'),{'id':variant_id}),article)
        variants=(await self.client.get(f'/api/cards/{card["id"]}/variants')).json()
        self.assertEqual(len(variants),len(ids)+1)
        self.assertEqual(variants[0]['currentPrice'],'500.00')
        # Scheduler uses only exact SKU targets once discovery succeeded.
        from datetime import timedelta
        due=await self.stores.runs.create_due_run(now=self.stores.runs._clock()+timedelta(days=10))
        self.assertEqual({c.ref.external_id for c in await self.stores.runs.cards_for_run(due.id)},set(ids[:1]))
