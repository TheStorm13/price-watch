"""Database enforcement and explicit repair on disposable PostgreSQL only."""
import asyncio
import os
import unittest
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from marketplace_connector.connectors.ozon.connector import OzonConnector
from price_watch.infrastructure.postgres.ozon_repair import merge_ozon_cards
from tests import test_ozon_variants as support
from tests import test_product_variants as migration_support

FixtureClient, SEED = support.FixtureClient, support.SEED


@unittest.skipUnless(os.environ.get('TEST_DATABASE_URL'), 'requires disposable TEST_DATABASE_URL')
class OzonOwnershipTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = support.OzonVariantIntegrationTests.asyncSetUp
    asyncTearDown = support.OzonVariantIntegrationTests.asyncTearDown
    executor = support.OzonVariantIntegrationTests.executor
    add_ozon = support.OzonVariantIntegrationTests.add_ozon

    async def test_direct_sql_cannot_duplicate_sku_or_forge_marketplace(self):
        first = await self.add_ozon('100')
        second = await self.add_ozon('200')
        for marketplace in ('ozon', 'wildberries'):
            with self.subTest(marketplace=marketplace), self.assertRaises(IntegrityError):
                with self.sync.engine.begin() as c:
                    c.execute(text('INSERT INTO card_variants(card_id,marketplace,external_id) VALUES (:card,:marketplace,:sku)'),
                              dict(card=second['id'], marketplace=marketplace, sku='100'))
        with self.sync.engine.begin() as c:
            c.execute(text("INSERT INTO marketplace_cards(marketplace,external_id) VALUES ('wildberries','100')"))
            c.execute(text("INSERT INTO card_variants(card_id,marketplace,external_id) SELECT id,'wildberries','100' FROM marketplace_cards WHERE marketplace='wildberries' AND external_id='100'"))
        duplicate = await self.client.post('/api/cards', json={'marketplace':'ozon','externalId':'100'})
        self.assertEqual(duplicate.status_code, 409)

    async def test_competing_direct_writes_have_exactly_one_owner(self):
        first, second = await self.add_ozon('100'), await self.add_ozon('200')
        async def insert(card):
            try:
                async with self.db.session() as s, s.begin():
                    await s.execute(text("INSERT INTO card_variants(card_id,marketplace,external_id) VALUES (:card,'ozon','300')"), dict(card=card))
                    await asyncio.sleep(.01)
                return True
            except IntegrityError:
                return False
        results = await asyncio.gather(insert(first['id']), insert(second['id']))
        self.assertEqual(sorted(results), [False, True])

    async def test_repair_preserves_variant_and_history_ids_and_tracks_former_primary(self):
        first, second = await self.add_ozon(SEED), await self.add_ozon('2936649562')
        fixture = FixtureClient()
        for sku in fixture.family:
            fixture.family[sku]['neighbors'] = [sku]
        await self.executor(OzonConnector(fixture)).collect(first['id'])
        await self.executor(OzonConnector(fixture)).collect(second['id'])
        with self.sync.engine.begin() as c:
            before = c.execute(text('SELECT id,variant_id,price,observed_at,snapshot FROM price_history ORDER BY id')).all()
            targets = c.execute(text('SELECT * FROM collection_run_targets ORDER BY run_id,variant_id')).all()
            summary = merge_ozon_cards(c, [(second['id'], first['id'])])
            self.assertEqual(summary['cards_removed'], 1)
            self.assertEqual(c.execute(text('SELECT id,variant_id,price,observed_at,snapshot FROM price_history ORDER BY id')).all(), before)
            self.assertEqual(c.execute(text('SELECT * FROM collection_run_targets ORDER BY run_id,variant_id')).all(), targets)
            self.assertEqual(c.scalar(text('SELECT card_id FROM card_variants WHERE id=:id'), dict(id=second['primaryVariantId'])), first['id'])
            self.assertTrue(c.scalar(text('SELECT tracking_enabled FROM card_variants WHERE id=:id'), dict(id=second['primaryVariantId'])))
            self.assertEqual(c.scalar(text('SELECT count(*) FROM price_history WHERE card_id=:id'), dict(id=first['id'])), 2)
        duplicate = await self.client.post('/api/cards', json={'marketplace':'ozon','externalId':'2936649562'})
        self.assertEqual(duplicate.status_code, 409)

    async def test_repair_rejects_active_run_and_conflicting_settings_atomically(self):
        first, second = await self.add_ozon('100'), await self.add_ozon('200')
        with self.sync.engine.begin() as c:
            c.execute(text('UPDATE marketplace_cards SET deals_enabled=false WHERE id=:id'), dict(id=second['id']))
        with self.assertRaisesRegex(ValueError, 'Настройки'):
            with self.sync.engine.begin() as c:
                merge_ozon_cards(c, [(second['id'], first['id'])])

        with self.sync.engine.begin() as c:
            self.assertEqual(c.scalar(text('SELECT count(*) FROM marketplace_cards')), 2)
            c.execute(text('UPDATE marketplace_cards SET deals_enabled=true'))
        await self.stores.runs.create_queued_run(first['id'])
        with self.assertRaisesRegex(ValueError, 'запусков'):
            with self.sync.engine.begin() as c:
                merge_ozon_cards(c, [(second['id'], first['id'])])

    async def test_queued_and_direct_collect_expand_modal_without_intermediate_failure(self):
        from marketplace_connector.application.product_service import ConnectorRegistry
        from marketplace_connector.connectors.ozon.async_client import AsyncOzonClient
        from price_watch.application.run_executor import RunExecutor
        from tests.test_ozon_aspects import SKU, product, modal
        card = await self.add_ozon(SKU)
        client = AsyncOzonClient('/tmp/unused-profile')
        transport = MagicMock(fetch=AsyncMock(side_effect=[product(), modal(), product(), modal()]))
        @asynccontextmanager
        async def session():
            yield transport
        async def factory(run):
            return ConnectorRegistry([OzonConnector(client)])
        executor = RunExecutor(self.stores.runs, factory)
        with patch.object(client, '_request_session', session), patch.object(client, 'collection_session', session):
            await self.stores.runs.create_queued_run(card['id'])
            owned = await self.stores.runs.claim_next_run()
            queued = await executor.execute(owned)
            direct = await executor.collect(card['id'])
        self.assertEqual((queued.success_count, queued.failure_count), (1, 0))
        self.assertEqual((direct.success_count, direct.failure_count), (1, 0))
        with self.sync.engine.connect() as c:
            self.assertEqual(c.scalar(text('SELECT count(*) FROM card_variants')), 10)
            self.assertEqual(c.scalar(text('SELECT count(*) FROM price_history')), 1)


@unittest.skipUnless(os.environ.get('TEST_DATABASE_URL'), 'requires disposable TEST_DATABASE_URL')
class OzonOwnershipMigrationTests(unittest.TestCase):
    setUp = migration_support.ProductVariantMigrationTests.setUp
    tearDown = migration_support.ProductVariantMigrationTests.tearDown

    def test_duplicate_legacy_sku_stops_migration_without_deleting_data(self):
        from alembic import command
        with patch('logging.config.fileConfig'):
            command.upgrade(self.config, '0020_variant_tracking')
        with self.db.engine.begin() as c:
            c.execute(text("INSERT INTO marketplace_cards(id,marketplace,external_id) OVERRIDING SYSTEM VALUE VALUES (1,'ozon','100'),(2,'ozon','200')"))
            c.execute(text("INSERT INTO card_variants(card_id,external_id) VALUES (1,'100'),(2,'100')"))
        with self.assertRaisesRegex(RuntimeError, 'Повторное владение'), patch('logging.config.fileConfig'):
            command.upgrade(self.config, 'head')
        with self.db.engine.connect() as c:
            self.assertEqual(c.scalar(text('SELECT count(*) FROM card_variants')), 2)
            self.assertEqual(c.scalar(text('SELECT version_num FROM alembic_version')), '0020_variant_tracking')
            self.assertEqual(c.scalar(text("SELECT count(*) FROM information_schema.columns WHERE table_schema=:schema AND table_name='card_variants' AND column_name='marketplace'"), dict(schema=self.schema)), 0)
