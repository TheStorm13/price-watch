"""Purchase API, variant ownership, transfer and metrics on disposable PostgreSQL."""
import os
import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from tests.variant_tracking_support import manual_queue
from price_watch.api import create_app
from price_watch.bootstrap import create_postgres_stores
from price_watch.infrastructure.postgres import AsyncDatabase, Database, MigrationRunner
from price_watch.infrastructure.postgres.models import CardVariantRecord, PriceHistoryRecord

URL = os.environ.get('TEST_DATABASE_URL')


@unittest.skipUnless(URL, 'TEST_DATABASE_URL не задан')
class PurchaseIntegrationTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        with Database(URL) as db: MigrationRunner(db).apply()

    async def asyncSetUp(self):
        manual_queue(self)
        self.db = await AsyncDatabase(URL).open()
        self.stores = create_postgres_stores(self.db)
        self.card = await self.stores.cards.add_card('integration-test', str(uuid4()))
        self.client = AsyncClient(transport=ASGITransport(app=create_app(services=self.stores.api)), base_url='http://test')
        await self.stores.purchase.update_settings(dict(small_range_tolerance=None, historical_savings_share=None, target_notifications_enabled=False))

    async def asyncTearDown(self):
        await self.client.aclose()
        await self.stores.cards.delete_card(self.card.id)
        await self.stores.purchase.update_settings(dict(small_range_tolerance=None, historical_savings_share=None, target_notifications_enabled=False))
        await self.db.close()

    async def api_card(self):
        data = (await self.client.get('/api/catalog')).json()
        return next(c for c in data['cards'] if c['id'] == self.card.id)

    async def points(self, rows, variant=None):
        async with self.db.session() as s, s.begin():
            for at, price, availability in rows:
                s.add(PriceHistoryRecord(card_id=self.card.id, variant_id=variant or self.card.variant_id,
                    price=Decimal(price) if price else None, availability=availability, observed_at=at, snapshot={}))

    async def test_settings_atomic_patch_null_validation_and_persistence(self):
        first = (await self.client.get('/api/purchase-settings')).json()
        self.assertIsNone(first['smallRangeTolerance'])
        result = await self.client.patch('/api/purchase-settings', json=dict(smallRangeTolerance='50.00', historicalSavingsShare='70'))
        self.assertEqual(result.status_code, 200, result.text)
        for payload in [dict(smallRangeTolerance='-1'), dict(smallRangeTolerance='0.001'), dict(smallRangeTolerance='NaN'),
                        dict(historicalSavingsShare='0'), dict(historicalSavingsShare='100.01'), dict(smallRangeTolerance='99', historicalSavingsShare='101'),
                        dict(smallRangeTolerance='text'), dict(historicalSavingsShare='text'), dict(historicalSavingsShare=70), dict(smallRangeTolerance=50), dict(targetNotificationsEnabled=None), dict(instanceId='other')]:
            response = await self.client.patch('/api/purchase-settings', json=payload)
            self.assertEqual(response.status_code, 422, response.text)
            self.assertIn('field', response.json()['error'])
        stores = create_postgres_stores(self.db)
        settings = await stores.purchase.get_settings()
        self.assertEqual(settings.small_range_tolerance, Decimal('50'))
        self.assertEqual(settings.historical_savings_share, Decimal('70'))
        self.assertEqual(settings.instance_id, first['instanceId'])
        await self.client.patch('/api/purchase-settings', json=dict(smallRangeTolerance=None))
        current = (await self.client.get('/api/purchase-settings')).json()
        self.assertIsNone(current['smallRangeTolerance'])
        self.assertEqual(Decimal(current['historicalSavingsShare']), Decimal(70))

    async def test_constant_history_compaction_anchor_and_deal_independence(self):
        now = datetime.now(timezone.utc)
        await self.points([(now-timedelta(days=31), '340', 'in_stock'), (now+timedelta(days=1), '1', 'in_stock')])
        await self.client.patch('/api/purchase-settings', json=dict(smallRangeTolerance='0', historicalSavingsShare='70'))
        await self.client.patch(f'/api/cards/{self.card.id}', json=dict(dealsEnabled=False))
        card = await self.api_card()
        self.assertEqual(card['purchaseAssessment']['matches'], ['small_range'])
        self.assertTrue(card['purchaseAssessment']['historyEligible'])
        self.assertEqual(Decimal(card['purchaseAssessment']['maximumPrice']), Decimal(340))
        data = (await self.client.get('/api/catalog')).json()
        self.assertNotIn(self.card.id, [d['card']['id'] for d in data['deals']])
        self.assertEqual(data['instanceId'], (await self.client.get('/api/purchase-settings')).json()['instanceId'])
        # An old clipped anchor is valid monthly evidence without new saved rows.
        async with self.db.session() as s, s.begin():
            row = await s.scalar(select(PriceHistoryRecord).where(PriceHistoryRecord.variant_id == self.card.variant_id).order_by(PriceHistoryRecord.observed_at))
            row.observed_at = now-timedelta(days=900)
        self.assertTrue((await self.api_card())['purchaseAssessment']['historyEligible'])

    async def test_target_primary_change_is_atomic_and_isolated_and_null(self):
        now = datetime.now(timezone.utc)
        await self.points([(now-timedelta(seconds=1), '850', 'in_stock')])
        url = f'/api/cards/{self.card.id}'
        self.assertEqual((await self.client.patch(url, json=dict(targetPrice='850'))).status_code, 200)
        self.assertEqual((await self.api_card())['purchaseAssessment']['matches'], ['target_price'])
        for value in ['0', '-1', '1.001', 'Infinity', 'text', '', '1e2', 850]:
            self.assertEqual((await self.client.patch(url, json=dict(targetPrice=value))).status_code, 422)
        async with self.db.session() as s, s.begin():
            variant = CardVariantRecord(card_id=self.card.id, marketplace='integration-test', external_id=str(uuid4()))
            s.add(variant); await s.flush(); other_id = variant.id
        result = await self.client.patch(url, json=dict(primaryVariantId=other_id, targetPrice='200'))
        self.assertEqual(Decimal(result.json()['targetPrice']), Decimal(200))
        self.assertFalse((await self.api_card())['purchaseAssessment']['isMatch'])
        await self.client.patch(url, json=dict(primaryVariantId=self.card.variant_id))
        self.assertEqual(Decimal((await self.client.get(url)).json()['targetPrice']), Decimal(850))
        rejected = await self.client.patch(url, json=dict(primaryVariantId=999999999, targetPrice='100'))
        self.assertEqual(rejected.status_code, 422)
        self.assertEqual(Decimal((await self.client.get(url)).json()['targetPrice']), Decimal(850))
        await self.client.patch(url, json=dict(targetPrice=None))
        self.assertIsNone((await self.client.get(url)).json()['targetPrice'])

    async def test_transfer_missing_null_and_decimal_roundtrip_preserves_history(self):
        # Use a real Ozon identity so the HTTP import validator also exercises the contract.
        other = await self.stores.cards.add_card('ozon', str(int(uuid4().int % 10**12)))
        try:
            await self.stores.cards.update_card(other.id, target_price=Decimal('123.45'), update_target=True)
            async with self.db.session() as s, s.begin():
                s.add(PriceHistoryRecord(card_id=other.id, variant_id=other.variant_id, price=Decimal('150'),
                    availability='in_stock', observed_at=datetime.now(timezone.utc)-timedelta(days=31), snapshot={}))
            data = (await self.client.get('/api/cards/export')).json()
            data['cards'] = [c for c in data['cards'] if c['externalId'] == other.ref.external_id]
            data['groups'] = []
            variant = data['cards'][0]['variants'][0]
            self.assertEqual(Decimal(variant['targetPrice']), Decimal('123.45'))
            for goal, expected in [('missing', Decimal('123.45')), (None, None), ('222.22', Decimal('222.22'))]:
                if goal == 'missing': variant.pop('targetPrice')
                else: variant['targetPrice'] = goal
                result = await self.client.post('/api/cards/import', json=data)
                self.assertEqual(result.status_code, 200, result.text)
                self.assertEqual(result.json()['observationsAdded'], 0)
                self.assertEqual(result.json()['observationsRemoved'], 0)
                self.assertEqual((await self.stores.cards.get_card(other.id)).card.target_price, expected)
            variant['targetPrice'] = '-5'
            self.assertEqual((await self.client.post('/api/cards/import', json=data)).status_code, 422)
        finally: await self.stores.cards.delete_card(other.id)

    async def test_unavailable_interval_and_same_instant_do_not_age_history(self):
        now = datetime.now(timezone.utc)
        await self.points([(now-timedelta(days=31), '10', 'in_stock'), (now-timedelta(days=31), None, 'out_of_stock'),
                           (now-timedelta(days=1), '10', 'in_stock')])
        await self.client.patch('/api/purchase-settings', json=dict(smallRangeTolerance='50'))
        result = (await self.api_card())['purchaseAssessment']
        self.assertFalse(result['historyEligible'])
        self.assertFalse(result['isMatch'])
