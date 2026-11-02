"""Group projections run only on an explicitly supplied disposable test database."""
import os
import unittest
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

from httpx import ASGITransport, AsyncClient

from marketplace_connector import Availability, ProductRef, MarketplaceCard
from price_watch.api import create_app
from price_watch.bootstrap import create_postgres_stores
from price_watch.infrastructure.postgres import AsyncDatabase, Database, MigrationRunner
from price_watch.infrastructure.postgres.models import MarketplaceCardRecord, PriceHistoryRecord

TEST_DATABASE_URL = os.environ.get('TEST_DATABASE_URL')


@unittest.skipUnless(TEST_DATABASE_URL, 'TEST_DATABASE_URL не задан')
class GroupMetricsIntegrationTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        database = Database(TEST_DATABASE_URL).open()
        try:
            MigrationRunner(database).apply()
        finally:
            database.close()

    @asynccontextmanager
    async def fixture(self):
        database = await AsyncDatabase(TEST_DATABASE_URL).open()
        repository = create_postgres_stores(database)
        cards = [await repository.cards.add_card(marketplace, f'{uuid4().int % 1000000000 + 1}:2' if marketplace == 'wildberries' else f'test-{uuid4()}', title=f'Card {index}', tags=[f'tag{index}'])
                 for index, marketplace in enumerate(('ozon', 'wildberries'))]
        group_id = await repository.groups.create_group('Group', [card.id for card in cards], ['own'])
        try:
            yield database, repository, cards, group_id
        finally:
            await repository.groups.delete_group(group_id)
            for card in cards:
                await repository.cards.delete_card(card.id)
            await database.close()

    async def point(self, database, card, price, at, availability='in_stock'):
        async with database.session() as session, session.begin():
            session.add(PriceHistoryRecord(card_id=card.id, variant_id=card.variant_id, price=Decimal(price) if price is not None else None,
                availability=availability, observed_at=at, collection_run_id=None, snapshot={}))

    async def group(self, repository, group_id):
        return next(group for group in (await repository.catalog.get_catalog())["groups"] if group['id'] == group_id)

    async def test_representative_owns_all_metrics_and_member_deal_is_separate(self):
        async with self.fixture() as (database, repository, cards, group_id):
            a, b = cards
            now = datetime.now(timezone.utc)
            for card, price, days in [(a, '80', 2), (a, '90', 0), (b, '60', 3), (b, '240', 2), (b, '120', 0)]:
                await self.point(database, card, price, now - timedelta(days=days))
            group = await self.group(repository, group_id)
            self.assertEqual(group['representative_card_id'], a.id)
            self.assertEqual(group['minimum_price'], Decimal('80'))  # not B's 60
            self.assertEqual(group['representative_card']['average_price'], Decimal('80'))
            self.assertEqual(group['baseline_days'], 1)
            self.assertFalse(group['is_deal'])
            self.assertIsNone(group['savings'])
            self.assertTrue(group['has_member_deals'])
            self.assertEqual({deal["card"]["id"] for deal in (await repository.catalog.get_catalog())["deals"]} & {a.id, b.id}, {b.id})
            metrics = {c["id"]: (c["minimum_price"],c["average_price"]) for c in (await repository.catalog.get_catalog())["cards"]}
            self.assertEqual(metrics[a.id], (Decimal('80'), Decimal('80')))

            await self.point(database, b, '50', now + timedelta(seconds=1))
            group = await self.group(repository, group_id)
            self.assertEqual(group['representative_card_id'], b.id)
            self.assertEqual(group['current_price'], Decimal('50'))
            self.assertEqual(group['minimum_price'], Decimal('50'))
            self.assertEqual(group['representative_card']['marketplace'], 'wildberries')
            self.assertEqual(tuple(group['representative_card']['tags']), ('tag1',))
            self.assertTrue(group['is_deal'])
            self.assertEqual(group['savings'], group['representative_card']['average_price'] - Decimal('50'))
            await repository.cards.update_card(b.id, deals_enabled=False)
            group = await self.group(repository, group_id)
            self.assertEqual(group['representative_card_id'], b.id)
            self.assertFalse(group['representative_card']['deals_enabled'])
            self.assertFalse(group['is_deal'])
            self.assertIsNone(group['savings'])

            await repository.groups.update_group(group_id, 'Group', [a.id])
            self.assertEqual((await self.group(repository, group_id))['representative_card_id'], a.id)
            await repository.groups.update_group(group_id, 'Group', [a.id, b.id])
            await repository.cards.delete_card(b.id)
            self.assertEqual((await self.group(repository, group_id))['representative_card_id'], a.id)

    async def test_ties_unknown_availability_null_and_empty(self):
        async with self.fixture() as (database, repository, cards, group_id):
            a, b = cards
            now = datetime.now(timezone.utc)
            group = await self.group(repository, group_id)
            self.assertEqual(group['representative_card_id'], a.id)
            self.assertIsNone(group['current_price'])
            self.assertIsNone(group['representative_card']['last_observed_at'])
            await self.point(database, a, '90', now)
            await self.point(database, b, '90', now)
            self.assertEqual((await self.group(repository, group_id))['representative_card_id'], a.id)
            # Same timestamp: a larger history ID is the new latest point.
            await self.point(database, b, '0', now, 'unknown')
            group = await self.group(repository, group_id)
            self.assertEqual(group['representative_card_id'], b.id)
            self.assertEqual(group['current_price'], Decimal('0'))
            self.assertEqual(group['representative_card']['current_availability'], 'unknown')
            self.assertFalse(group['is_deal'])
            await self.point(database, b, None, now + timedelta(seconds=1), 'out_of_stock')
            self.assertEqual((await self.group(repository, group_id))['representative_card_id'], a.id)
            await repository.groups.update_group(group_id, 'Empty', [])
            group = await self.group(repository, group_id)
            for key in ('representative_card', 'representative_card_id', 'current_price', 'minimum_price', 'savings'):
                self.assertIsNone(group[key])
            self.assertEqual(group['baseline_days'], 0)
            self.assertFalse(group['has_member_deals'])
            self.assertFalse(group['is_deal'])

    async def test_group_api_matches_card_projection_and_imported_membership(self):
        async with self.fixture() as (database, repository, cards, group_id):
            a, b = cards
            now = datetime.now(timezone.utc)
            await self.point(database, a, '100', now - timedelta(days=1))
            await self.point(database, a, '80', now)
            app = create_app(services=repository.api)

            async with AsyncClient(transport=ASGITransport(app=app), base_url='http://testserver') as client:
                groups = (await client.get('/api/catalog')).json()['groups']
                group = next(item for item in groups if item['id'] == group_id)
                card = next(item for item in (await client.get('/api/catalog')).json()['cards'] if item['id'] == a.id)
                self.assertEqual(group['representativeCard'], card)
                self.assertEqual(group['representativeCardId'], a.id)
                self.assertEqual(group['savings'], '20')
            document = await repository.transfer.export_cards()
            imported_cards = [item for item in document['cards'] if item['external_id'] in {a.ref.external_id.split(':')[0], b.ref.external_id.split(':')[0]}]
            imported_group = next(item for item in document['groups'] if item['name'] == 'Group')
            await repository.groups.update_group(group_id, 'Group', [])
            await repository.transfer.import_cards(imported_cards, groups=[imported_group])
            self.assertEqual((await self.group(repository, group_id))['representative_card_id'], a.id)

    async def test_dates_follow_only_representative_and_deduplicated_collection(self):
        async with self.fixture() as (database, repository, cards, group_id):
            a, b = cards
            past = datetime.now(timezone.utc) - timedelta(days=2)
            await self.point(database, a, '90', past)
            await self.point(database, b, '120', past)
            async with database.session() as session, session.begin():
                for card in cards:
                    (await session.get(MarketplaceCardRecord, card.id)).updated_at = past
            before = await self.group(repository, group_id)
            await repository.cards.update_card(b.id, title='B', update_title=True)
            after_other = await self.group(repository, group_id)
            self.assertEqual(after_other['representative_card'], before['representative_card'])
            owned = await repository.runs.start_direct_run(a.id)
            await repository.runs.save_result(owned.lease, a, MarketplaceCard(ref=ProductRef(a.ref.marketplace, a.ref.external_id),
                title='A', url=None, price=90, availability=Availability.IN_STOCK))
            await repository.runs.finish_run(owned.lease)
            after = await self.group(repository, group_id)
            self.assertGreater(after['representative_card']['updated_at'], past)
            self.assertEqual(after['representative_card']['last_observed_at'], past)
            self.assertEqual(after['baseline_days'], before['baseline_days'])
            self.assertEqual(await repository.history.count_history(a.id, 30), 1)
