"""Initial all-SKU prices, selective tracking, ownership and frozen retries."""
import os
import unittest
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from marketplace_connector.connectors.yandex_market.connector import YandexMarketConnector
from marketplace_connector.connectors.yandex_market.discovery import FamilySession
from tests.test_yandex_market import SEED, html
from tests import test_product_variants as support


class FixtureClient:
    def __init__(self):
        self.calls = []
        self.fail = set()

    @asynccontextmanager
    async def collection_session(self):
        self.session = FamilySession(AsyncMock(fetch=self.fetch))
        try:yield
        finally:await self.session.close()

    async def fetch(self, sku):
        self.calls.append(sku)
        return html(sku)

    async def fetch_product_async(self, sku):
        if sku in self.fail:raise RuntimeError('Synthetic exact SKU failure')
        return await self.session.get(sku)


@unittest.skipUnless(os.environ.get('TEST_DATABASE_URL'), 'requires disposable TEST_DATABASE_URL')
class YandexIntegrationTests(unittest.IsolatedAsyncioTestCase):
    automatic_initial_refresh = True
    asyncSetUp = support.ProductVariantTests.asyncSetUp
    asyncTearDown = support.ProductVariantTests.asyncTearDown
    executor = support.ProductVariantTests.executor

    async def test_added_external_article_keeps_identity_and_collects_price(self):
        from copy import deepcopy
        from tests.test_yandex_market import FAMILY, external_article_html
        article = '6019174271'
        response = await self.client.post('/api/cards', json={'marketplace':'yandex-market','externalId':article})
        self.assertEqual(response.status_code, 201, response.text)
        card = response.json()
        fixture = FixtureClient()
        async def fetch(sku):
            if sku == article: return external_article_html()
            other = deepcopy(FAMILY[SEED])
            next(iter(other['collections']['compose'].values()))['oskuId'] = sku
            other['edges'] = []
            return html(data=other)
        fixture.fetch = fetch
        executor = self.executor(YandexMarketConnector(fixture))
        result = await executor.execute(await self.stores.runs.claim_next_run())
        self.assertEqual((result.total_count,result.success_count,result.failure_count),(1,1,0))
        updated = (await self.client.get(f'/api/cards/{card["id"]}')).json()
        self.assertEqual(updated['externalId'], article)
        self.assertEqual(updated['primaryVariantId'], card['primaryVariantId'])
        variants = (await self.client.get(f'/api/cards/{card["id"]}/variants')).json()
        self.assertEqual([v['externalId'] for v in variants], [article])
        self.assertEqual(variants[0]['currentPrice'], '3058.20')
        await executor.collect(card['id'])
        with self.sync.engine.connect() as c:
            self.assertEqual(c.scalar(text('SELECT count(*) FROM price_history')),1)

    async def test_initial_64_prices_selective_collection_dedup_and_ownership(self):
        response = await self.client.post('/api/cards', json={'marketplace':'yandex-market', 'externalId':SEED})
        self.assertEqual(response.status_code, 201, response.text)
        card = response.json()
        fixture = FixtureClient()
        executor = self.executor(YandexMarketConnector(fixture))
        owned = await self.stores.runs.claim_next_run()
        result = await executor.execute(owned)
        self.assertEqual((result.total_count, result.success_count, result.failure_count), (64,64,0))
        self.assertEqual(len(fixture.calls),64)
        variants = (await self.client.get(f'/api/cards/{card["id"]}/variants')).json()
        self.assertEqual(len(variants),64)
        self.assertTrue(all(v['currentPrice'] is not None for v in variants))
        self.assertEqual(sum(v['isTracked'] for v in variants),1)
        other = next(v for v in variants if v['externalId'] != SEED)
        with self.sync.engine.begin() as c:
            self.assertEqual(c.scalar(text('SELECT count(*) FROM price_history')),64)
            c.execute(text('UPDATE card_variants SET tracking_enabled=true WHERE id=:id'), {'id':other['id']})
        result = await executor.collect(card['id'])
        self.assertEqual((result.total_count,result.success_count),(2,2))
        with self.sync.engine.connect() as c:
            self.assertEqual(c.scalar(text('SELECT count(*) FROM price_history')),64)
        duplicate = await self.client.post('/api/cards', json={'marketplace':'yandex-market','externalId':other['externalId']})
        self.assertEqual(duplicate.status_code,409)
        fixture.fail = {other['externalId']}
        failed = await executor.collect(card['id'])
        self.assertEqual((failed.success_count,failed.failure_count),(1,1))
        fixture.fail.clear()
        retry = await self.stores.runs.create_retry_run(failed.run_id)
        result = await executor.execute(await self.stores.runs.claim_next_run())
        self.assertEqual((result.total_count,result.success_count),(1,1))
        self.assertEqual((await self.client.get(f'/api/cards/{card["id"]}')).json()['primaryVariantId'], card['primaryVariantId'])
        # Direct SQL cannot assign a known SKU to a second local card.
        with self.assertRaises(IntegrityError):
            with self.sync.engine.begin() as c:
                new = c.scalar(text("INSERT INTO marketplace_cards(marketplace,external_id) VALUES ('yandex-market','999') RETURNING id"))
                c.execute(text("INSERT INTO card_variants(card_id,marketplace,external_id) VALUES (:id,'yandex-market',:sku)"),dict(id=new,sku=SEED))
        document = (await self.client.get('/api/cards/export')).json()
        document['cards'][0]['externalId'] = '999'
        from copy import deepcopy
        new_variant = deepcopy(document['cards'][0]['variants'][0])
        new_variant.update(externalId='999', url='https://market.yandex.ru/card/tovar/999', history=[])
        document['cards'][0]['variants'].append(new_variant)
        # Existing foreign members cannot be silently merged by importing another root.
        self.assertEqual((await self.client.post('/api/cards/import',json=document)).status_code, 409)

    async def test_existing_card_expands_and_partial_discovery_preserves_history(self):
        from copy import deepcopy
        from tests.test_yandex_market import FAMILY
        from marketplace_connector.domain.errors import MarketplaceUnavailable
        response = await self.client.post('/api/cards', json={'marketplace':'yandex-market','externalId':SEED})
        card = response.json()
        fixture = FixtureClient()
        async def solo(sku):
            data = deepcopy(FAMILY[sku])
            data['edges'] = []
            return html(sku, data=data)
        fixture.fetch = solo
        executor = self.executor(YandexMarketConnector(fixture))
        await executor.execute(await self.stores.runs.claim_next_run())
        with self.sync.engine.connect() as c:
            old_id = c.scalar(text('SELECT id FROM price_history'))
        fixture.fetch = FixtureClient.fetch.__get__(fixture)
        result = await executor.collect(card['id'])
        self.assertEqual((result.total_count,result.success_count),(64,64))
        with self.sync.engine.connect() as c:
            self.assertEqual(c.scalar(text('SELECT min(id) FROM price_history')),old_id)
        async def incomplete(sku):
            if sku != SEED:raise MarketplaceUnavailable('synthetic neighbor failure')
            return html(sku)
        fixture.fetch = incomplete
        result = await executor.collect(card['id'])
        self.assertEqual(result.failure_count,1)
        with self.sync.engine.connect() as c:
            self.assertEqual(c.scalar(text('SELECT count(*) FROM price_history')),64)
            self.assertEqual(c.scalar(text('SELECT count(*) FROM card_variants')),64)
        self.assertEqual((await self.client.get(f'/api/cards/{card["id"]}')).json()['primaryVariantId'],card['primaryVariantId'])


@unittest.skipUnless(os.environ.get('TEST_DATABASE_URL'), 'requires disposable TEST_DATABASE_URL')
class YandexMigrationTests(unittest.TestCase):
    setUp = support.ProductVariantMigrationTests.setUp
    tearDown = support.ProductVariantMigrationTests.tearDown

    def test_conflict_stops_migration_preserving_rows(self):
        from alembic import command
        from unittest.mock import patch
        with patch('logging.config.fileConfig'):command.upgrade(self.config, '0021_ozon_sku_ownership')
        with self.db.engine.begin() as c:
            c.execute(text("INSERT INTO marketplace_cards(id,marketplace,external_id) OVERRIDING SYSTEM VALUE VALUES (1,'yandex-market','100'),(2,'yandex-market','200')"))
            c.execute(text("INSERT INTO card_variants(card_id,marketplace,external_id) VALUES (1,'yandex-market','100'),(2,'yandex-market','100')"))
        with self.assertRaisesRegex(RuntimeError,'Повторное владение'), patch('logging.config.fileConfig'):
            command.upgrade(self.config,'head')
        with self.db.engine.connect() as c:self.assertEqual(c.scalar(text('SELECT count(*) FROM card_variants')),2)
