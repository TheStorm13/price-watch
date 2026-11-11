"""Time-weighted metrics against a separate disposable PostgreSQL database."""
import json
import os
import unittest
from datetime import datetime, timedelta, timezone
from contextlib import redirect_stdout
from io import StringIO
from decimal import Decimal
from unittest.mock import patch
from uuid import uuid4

from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete

from tests.variant_tracking_support import manual_queue
from price_watch.api import create_app
from price_watch.bootstrap import create_postgres_stores
from price_watch.domain.price_window import price_window
from price_watch.infrastructure.postgres import AsyncDatabase, Database, MigrationRunner
from price_watch.infrastructure.postgres.models import PriceHistoryRecord, CardVariantRecord

TEST_DATABASE_URL = os.environ.get('TEST_DATABASE_URL')
NOW = datetime(2028, 2, 29, 12, tzinfo=timezone.utc)


@unittest.skipUnless(TEST_DATABASE_URL, 'TEST_DATABASE_URL не задан')
class TimePriceMetricsTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        with Database(TEST_DATABASE_URL) as database:
            MigrationRunner(database).apply()

    async def asyncSetUp(self):
        manual_queue(self)
        self.database = await AsyncDatabase(TEST_DATABASE_URL).open()
        self.repository = create_postgres_stores(self.database)
        self.card = await self.repository.cards.add_card('integration-test', str(uuid4()))
        for module in ['queries', 'history_repository']:
            self.enterContext(patch(f'price_watch.infrastructure.postgres.{module}.price_window', return_value=price_window(NOW)))

    async def asyncTearDown(self):
        await self.repository.cards.delete_card(self.card.id)
        await self.database.close()

    async def points(self, rows):
        async with self.database.session() as session, session.begin():
            for at, price, availability in rows:
                session.add(PriceHistoryRecord(card_id=self.card.id, variant_id=self.card.variant_id,
                    price=Decimal(price) if price is not None else None, availability=availability,
                    observed_at=at, snapshot={}))
                await session.flush()  # deterministic ID ordering for simultaneous states

    async def assert_metrics(self, average, minimum, maximum):
        statistics = await self.repository.history.get_statistics(self.card.id)
        card = next(c for c in (await self.repository.catalog.get_catalog())['cards'] if c['id'] == self.card.id)
        self.assertEqual(statistics.average_price, Decimal(average) if average is not None else None)
        self.assertEqual(statistics.minimum_price, Decimal(minimum) if minimum is not None else None)
        self.assertEqual(statistics.maximum_price, Decimal(maximum) if maximum is not None else None)
        self.assertEqual(card['average_price'], statistics.average_price)
        self.assertEqual(card['minimum_price'], statistics.minimum_price)
        self.assertEqual(statistics.window_start, datetime(2026, 2, 28, 12, tzinfo=timezone.utc))
        self.assertEqual(statistics.window_end, NOW)
        return statistics

    async def test_duration_weight_and_http_statistics_are_independent_of_history_period(self):
        await self.points([(NOW - timedelta(days=30), '1000', 'in_stock'),
                           (NOW - timedelta(days=1), '3000', 'in_stock')])
        await self.assert_metrics('1066.666666666667', '1000', '3000')
        app = create_app(services=self.repository.api)
        # Request periods are relative to the same NOW as metric calculation.
        with patch.object(self.repository.history, '_cutoff', side_effect=lambda days: NOW - timedelta(days=days)):
            async with AsyncClient(transport=ASGITransport(app=app), base_url='http://test') as client:
                responses = [(await client.get(f'/api/cards/{self.card.id}/history?days={days}')).json() for days in [7, 30, 90]]
        self.assertEqual([r['totalCount'] for r in responses], [1, 2, 2])
        self.assertEqual(responses[0]['statistics'], responses[1]['statistics'])
        self.assertEqual(responses[1]['statistics'], responses[2]['statistics'])
        self.assertNotIn('days', responses[0]['statistics'])
        self.assertIn('windowStart', responses[0]['statistics'])

    async def test_cli_history_reports_two_year_bounds_while_filtering_rows(self):
        from price_watch.cli import _execute, build_parser
        await self.points([(NOW - timedelta(days=30), '1000', 'in_stock'),
                           (NOW - timedelta(days=1), '3000', 'in_stock')])
        args = build_parser().parse_args(['history', '--card-id', str(self.card.id), '--days', '7'])
        output = StringIO()
        with patch('price_watch.cli.create_postgres_stores', return_value=self.repository), patch.object(
                self.repository.history, '_cutoff', side_effect=lambda days: NOW - timedelta(days=days)), redirect_stdout(output):
            self.assertEqual(await _execute(args, self.database), 0)
        result = json.loads(output.getvalue())
        self.assertEqual(len(result['history']), 1)
        self.assertEqual(result['statistics']['average_price'], '1066.666666666667')
        self.assertEqual(result['statistics']['window_start'], '2026-02-28T12:00:00+00:00')
        self.assertNotIn('days', result['statistics'])

    async def test_large_money_and_repeating_decimal_keep_twelve_places(self):
        await self.points([(NOW - timedelta(microseconds=3), '999999999999.98', 'in_stock'),
                           (NOW - timedelta(microseconds=1), '999999999999.99', 'in_stock')])
        await self.assert_metrics('999999999999.983333333333', '999999999999.98', '999999999999.99')

    async def test_two_year_anchor_excludes_replaced_extrema_and_future_prices(self):
        start, _ = price_window(NOW)
        await self.points([(start - timedelta(days=100), '1', 'in_stock'),
                           (start - timedelta(days=1), '100', 'in_stock'),
                           (NOW + timedelta(days=1), '5000', 'in_stock')])
        statistics = await self.assert_metrics('100', '100', '100')
        self.assertEqual(statistics.observations_count, 0)
        self.assertEqual(statistics.observed_days, 0)

    async def test_invalid_states_interrupt_weight_and_latest_has_zero_duration(self):
        await self.points([(NOW - timedelta(days=6), '100', 'in_stock'),
                           (NOW - timedelta(days=5), None, 'out_of_stock'),
                           (NOW - timedelta(days=4), '999', 'unknown'),
                           (NOW - timedelta(days=3), None, 'in_stock'),
                           (NOW - timedelta(days=1), '200', 'in_stock'), (NOW, '0', 'in_stock')])
        statistics = await self.assert_metrics('150', '0', '200')
        self.assertEqual(statistics.observations_count, 3)
        self.assertEqual(statistics.observed_days, 3)

    async def test_empty_single_price_and_state_at_window_boundary(self):
        await self.assert_metrics(None, None, None)
        await self.points([(NOW, '100', 'in_stock')])
        await self.assert_metrics(None, '100', '100')
        async with self.database.session() as session, session.begin():
            await session.execute(delete(PriceHistoryRecord).where(PriceHistoryRecord.card_id == self.card.id))
        start, _ = price_window(NOW)
        await self.points([(start - timedelta(microseconds=1), '1', 'in_stock'), (start, '100', 'in_stock')])
        await self.assert_metrics('100', '100', '100')

    async def test_same_timestamp_id_microseconds_decimal_precision_and_variant_isolation(self):
        await self.points([(NOW - timedelta(microseconds=1000), '999', 'in_stock'),
                           (NOW - timedelta(microseconds=1000), '100.00', 'in_stock'),
                           (NOW - timedelta(microseconds=500), '100.01', 'in_stock')])
        async with self.database.session() as session, session.begin():
            variant = CardVariantRecord(card_id=self.card.id, marketplace='integration-test', external_id='other')
            session.add(variant)
            await session.flush()
            session.add(PriceHistoryRecord(card_id=self.card.id, variant_id=variant.id, price=Decimal('1'),
                availability='in_stock', observed_at=NOW - timedelta(days=1), snapshot={}))
        await self.assert_metrics('100.005', '100', '999')
        other = await self.repository.history.get_statistics(self.card.id, variant_id=variant.id)
        self.assertEqual(other.average_price, Decimal('1'))


class PriceWindowTests(unittest.TestCase):
    def test_calendar_years_and_timezone(self):
        self.assertEqual(price_window(NOW)[0], datetime(2026, 2, 28, 12, tzinfo=timezone.utc))
        self.assertEqual(price_window(datetime(2026, 11, 11, 15, tzinfo=timezone(timedelta(hours=3))))[0],
                         datetime(2024, 11, 11, 12, tzinfo=timezone.utc))
