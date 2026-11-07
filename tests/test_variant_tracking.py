"""Initial discovery is independent from retained recurring preferences."""
import os
import json
import unittest
from dataclasses import replace
from unittest.mock import patch
from sqlalchemy import text
from marketplace_connector.connectors.ozon.connector import OzonConnector
from marketplace_connector.domain.models import ProductRef
from tests import test_product_variants as support
from tests.test_ozon_variants import FixtureClient, SEED, FAMILY


@unittest.skipUnless(os.environ.get('TEST_DATABASE_URL'), 'requires disposable TEST_DATABASE_URL')
class VariantTrackingTests(unittest.IsolatedAsyncioTestCase):
    automatic_initial_refresh = True
    asyncSetUp = support.ProductVariantTests.asyncSetUp
    asyncTearDown = support.ProductVariantTests.asyncTearDown
    executor = support.ProductVariantTests.executor

    async def add(self, marketplace='ozon', ref=SEED):
        response = await self.client.post('/api/cards', json={'marketplace': marketplace, 'externalId': ref})
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    async def variants(self, card):
        return (await self.client.get(f'/api/cards/{card["id"]}/variants')).json()

    async def toggle(self, card, enabled, variant_id=None):
        data = {'enabled': enabled}
        if variant_id is not None:
            data['variantId'] = variant_id
        return await self.client.patch(f'/api/cards/{card["id"]}/variant-tracking', json=data)

    async def test_ozon_initial_all_then_selective_frozen_targets_and_primary(self):
        card = await self.add()
        job = await self.stores.runs.claim_next_run()
        self.assertIsNotNone(job)
        fixture = FixtureClient()
        result = await self.executor(OzonConnector(fixture)).execute(job)
        self.assertEqual((result.total_count, result.success_count), (12, 12))
        variants = await self.variants(card)
        self.assertEqual(len(variants), len(FAMILY))
        self.assertTrue(all(not v['trackingEnabled'] for v in variants))
        self.assertEqual(sum(v['isTracked'] for v in variants), 1)
        before = (await self.client.get(f'/api/cards/{card["id"]}/chart')).json()
        self.assertEqual(len(before['points']), 12)
        fixture.calls.clear()
        await self.executor(OzonConnector(fixture)).collect(card['id'])
        self.assertEqual(fixture.calls, [SEED])
        extra = next(v for v in variants if v['id'] != card['primaryVariantId'])
        self.assertEqual((await self.toggle(card, True, extra['id'])).status_code, 200)
        queued = await self.stores.runs.create_queued_run(card['id'])
        self.assertEqual(len(await self.stores.runs.cards_for_run(queued.id)), 2)
        await self.toggle(card, False)
        self.assertEqual(len(await self.stores.runs.cards_for_run(queued.id)), 2)
        owned = await self.stores.runs.claim_next_run()
        await self.executor(OzonConnector(fixture)).execute(owned)
        self.assertEqual((await self.toggle(card, False, card['primaryVariantId'])).status_code, 422)
        self.assertEqual((await self.toggle(card, True, 987654321)).status_code, 422)
        await self.client.patch(f'/api/cards/{card["id"]}', json={'primaryVariantId': extra['id']})
        fixture.calls.clear()
        await self.executor(OzonConnector(fixture)).collect(card['id'])
        self.assertEqual(fixture.calls, [extra['externalId']])
        await self.toggle(card, True)
        fixture.calls.clear()
        await self.executor(OzonConnector(fixture)).collect(card['id'])
        self.assertEqual(set(fixture.calls), set(FAMILY))
        await self.toggle(card, False)
        self.assertEqual((await self.client.get(f'/api/cards/{card["id"]}/chart')).json(), before)
        # Explicit preference survives temporary primary status.
        old = card['primaryVariantId']
        await self.toggle(card, True, old)
        await self.client.patch(f'/api/cards/{card["id"]}', json={'primaryVariantId': old})
        await self.client.patch(f'/api/cards/{card["id"]}', json={'primaryVariantId': extra['id']})
        selected = await self.stores.cards.list_collection_cards(card['id'])
        self.assertEqual({c.variant_id for c in selected}, {old, extra['id']})

    async def test_unavailable_ozon_initial_discovery_then_queued_and_direct_refresh(self):
        import io
        from contextlib import redirect_stdout
        from marketplace_connector.application.product_service import ConnectorRegistry
        from price_watch import cli
        from price_watch.worker import CollectionWorker

        card = await self.add()
        fixture = FixtureClient(unavailable=[SEED])
        fixture.image_revision = 'unavailable'
        async def factory(run):
            return ConnectorRegistry([OzonConnector(fixture)])
        worker = CollectionWorker(self.stores.runs, factory, execution=self.stores.runs)
        self.assertTrue(await worker.run_once())  # Actual initial job created by API.
        self.assertEqual(set(fixture.calls), set(FAMILY))
        variants = await self.variants(card)
        self.assertEqual(len(variants), len(FAMILY))
        own = next(v for v in variants if v['externalId'] == SEED)
        self.assertEqual((own['currentPrice'], own['currentAvailability']), (None, 'out_of_stock'))
        self.assertEqual(own['options'], FAMILY[SEED]['options'])
        self.assertEqual(own['imageUrl'], f'https://img.test/{SEED}-unavailable.jpg')
        self.assertTrue(all(not v['trackingEnabled'] for v in variants))
        before = (await self.client.get(f'/api/cards/{card["id"]}/chart')).json()
        self.assertEqual(len(before['points']), len(FAMILY))

        fixture.calls.clear()
        queued = await self.client.post('/api/runs', json={'cardId': card['id']})
        self.assertEqual(queued.status_code, 202, queued.text)
        self.assertTrue(await worker.run_once())
        self.assertEqual(fixture.calls, [SEED])
        finished = await self.stores.runs.get_run(queued.json()['id'])
        self.assertEqual((finished.success_count, finished.failure_count), (1, 0))

        fixture.calls.clear()
        fixture.image_revision = 'refreshed'
        args = cli.build_parser().parse_args(['collect', '--card-id', str(card['id'])])
        output = io.StringIO()
        with patch.object(cli, '_build_connectors', return_value=ConnectorRegistry([OzonConnector(fixture)])), redirect_stdout(output):
            self.assertEqual(await cli._execute(args, self.db), 0)
        self.assertEqual(json.loads(output.getvalue())['success_count'], 1)
        self.assertEqual(fixture.calls, [SEED])
        self.assertEqual((await self.client.get(f'/api/cards/{card["id"]}/chart')).json(), before)
        own = next(v for v in await self.variants(card) if v['externalId'] == SEED)
        self.assertEqual(own['imageUrl'], f'https://img.test/{SEED}-refreshed.jpg')
        self.assertEqual((own['currentPrice'], own['currentAvailability']), (None, 'out_of_stock'))

    async def test_wb_and_ali_root_bootstrap_all_then_primary_only(self):
        for marketplace in ('wildberries', 'aliexpress'):
            with self.subTest(marketplace=marketplace):
                class Connector(support.VariantConnector):
                    async def get_product(inner, ref):
                        root = ':' not in ref
                        snapshot = await super().get_product(ref + ':10' if root else ref)
                        return replace(snapshot, ref=ProductRef(marketplace, ref), variants=tuple(
                            replace(v, ref=ProductRef(marketplace, v.ref.external_id)) for v in snapshot.variants))
                    @staticmethod
                    def url(article, size):
                        return (f'https://aliexpress.ru/item/{article}.html?sku_id={size}' if marketplace == 'aliexpress'
                                else support.VariantConnector.url(article, size))
                connector = Connector()
                connector.marketplace = marketplace
                card = await self.add(marketplace, '123')
                initial = await self.stores.runs.claim_next_run()
                result = await self.executor(connector).execute(initial)
                self.assertEqual(result.failure_count, 0)
                variants = await self.variants(card)
                self.assertEqual(len(variants), 2)
                self.assertTrue(all(v['currentPrice'] for v in variants))
                self.assertTrue(all(not v['trackingEnabled'] for v in variants))
                connector.calls.clear()
                await self.executor(connector).collect(card['id'])
                self.assertEqual(connector.calls, ['123:10'])
                connector.sizes.append('30')
                await self.executor(connector).collect(card['id'])
                new = next(v for v in await self.variants(card) if v['externalId'] == '123:30')
                root_id = card['primaryVariantId']
                self.assertEqual((await self.toggle(card, True, root_id)).status_code, 422)
                selected_root = await self.client.patch(f'/api/cards/{card["id"]}', json={'primaryVariantId': root_id})
                self.assertEqual(selected_root.status_code, 422)
                self.assertFalse(new['isTracked'])
                self.assertIsNone(new['currentPrice'])

    async def test_creation_rolls_back_when_initial_queue_fails(self):
        with patch('price_watch.infrastructure.postgres.runs_repository.RunRepository.enqueue_initial', side_effect=RuntimeError('queue unavailable')):
            with self.assertRaisesRegex(RuntimeError, 'queue unavailable'):
                await self.stores.cards.add_card('ozon', SEED)
        self.assertEqual(await self.stores.cards.list_cards(), [])
        async with self.db.session() as s:
            self.assertEqual(await s.scalar(text('SELECT count(*) FROM collection_runs')), 0)

    async def test_transfer_retains_preferences_and_existing_merge_keeps_local_choice(self):
        card = await self.add()
        await self.executor(OzonConnector(FixtureClient())).execute(await self.stores.runs.claim_next_run())
        await self.toggle(card, True)
        exported = (await self.client.get('/api/cards/export')).json()
        self.assertEqual(sum(v['trackingEnabled'] for v in exported['cards'][0]['variants']), 11)
        await self.toggle(card, False)
        self.assertEqual((await self.client.post('/api/cards/import', json=exported)).status_code, 200)
        self.assertFalse(any(v['trackingEnabled'] for v in await self.variants(card)))
        await self.client.delete(f'/api/cards/{card["id"]}')
        self.assertEqual((await self.client.post('/api/cards/import', json=exported)).status_code, 200)
        restored = (await self.client.get('/api/cards/export')).json()
        self.assertEqual(restored, exported)

    async def test_auto_created_job_is_consumed_by_worker_and_cli_add_enqueues(self):
        from marketplace_connector import ConnectorRegistry
        from price_watch.worker import CollectionWorker
        from price_watch import cli
        import io
        import json
        from contextlib import redirect_stdout
        card = await self.add()
        fixture = FixtureClient()
        async def factory(run):
            return ConnectorRegistry([OzonConnector(fixture)])
        worker = CollectionWorker(self.stores.runs, factory, execution=self.stores.runs)
        self.assertTrue(await worker.run_once())
        self.assertEqual(set(fixture.calls), set(FAMILY))
        self.assertTrue(all(not v['trackingEnabled'] for v in await self.variants(card)))
        output = io.StringIO()
        args = cli.build_parser().parse_args(['card', 'add', '--marketplace', 'ozon', '--external-id', '999000888'])
        with redirect_stdout(output):
            self.assertEqual(await cli._execute(args, self.db), 0)
        async with self.db.session() as s:
            count = await s.scalar(text("SELECT count(*) FROM collection_runs WHERE status='queued' AND discover_all"))
            self.assertEqual(count, 1)


@unittest.skipUnless(os.environ.get('TEST_DATABASE_URL'), 'requires disposable TEST_DATABASE_URL')
class VariantTrackingMigrationTests(unittest.TestCase):
    setUp = support.ProductVariantMigrationTests.setUp
    tearDown = support.ProductVariantMigrationTests.tearDown
    seed = support.ProductVariantMigrationTests.seed
    # Reuse setup/seed only, not all inherited migration tests.
    def test_tracking_migration_preserves_existing_data_and_queued_targets(self):
        from alembic import command
        self.seed()
        with patch('logging.config.fileConfig'):
            command.upgrade(self.config, '0019_variant_details')
        with self.db.engine.begin() as c:
            c.execute(text("UPDATE collection_runs SET status='queued' WHERE id=1"))
            tables = ['marketplace_cards', 'card_variants', 'price_history', 'collection_run_targets']
            before = {t: c.execute(text(f'SELECT * FROM {t} ORDER BY 1,2')).mappings().all() for t in tables}
        with patch('logging.config.fileConfig'):
            command.upgrade(self.config, 'head')
        with self.db.engine.connect() as c:
            self.assertEqual(c.execute(text('SELECT tracking_enabled FROM card_variants')).scalars().all(), [False]*3)
            self.assertFalse(c.scalar(text('SELECT discover_all FROM collection_runs WHERE id=1')))
            for t in tables:
                rows = c.execute(text(f'SELECT * FROM {t} ORDER BY 1,2')).mappings().all()
                if t == 'card_variants':
                    self.assertEqual({r['marketplace'] for r in rows}, {'wildberries', 'aliexpress'})
                added = {'tracking_enabled', 'marketplace'} if t == 'card_variants' else set()
                rows = [{k:v for k,v in r.items() if k not in added} for r in rows]
                self.assertEqual(rows, before[t])
