"""Rules use only prepared values, fixed time and exact monetary arithmetic."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import unittest

from price_watch.domain.catalog_rules import deal_savings, representative_id
from price_watch.domain.collection_policy import CollectionPolicy


class CatalogRulesTests(unittest.TestCase):
    def test_deal_conditions_and_unrounded_decimal(self):
        values = dict(enabled=True, price=Decimal('1.00'), availability='in_stock',
                      average=Decimal('1.001'))
        self.assertEqual(deal_savings(**values), Decimal('.001'))
        for patch in [dict(enabled=False), dict(price=None), dict(availability='unknown'),
                      dict(availability='out_of_stock'), dict(average=None),
                      dict(average=Decimal('1')), dict(price=Decimal('2'))]:
            with self.subTest(patch=patch):
                self.assertIsNone(deal_savings(**(values | patch)))
        self.assertEqual(deal_savings(**(values | dict(price=Decimal(0)))), Decimal('1.001'))

    def test_representative_empty_missing_ties_and_zero(self):
        self.assertIsNone(representative_id([]))
        self.assertEqual(representative_id([(3, None), (2, None)]), 2)
        self.assertEqual(representative_id([(3, Decimal('1')), (2, Decimal('1'))]), 2)
        self.assertEqual(representative_id([(1, None), (3, Decimal(0)), (2, Decimal('0.01'))]), 3)


class CollectionPolicyTests(unittest.TestCase):
    now = datetime(2026, 10, 26, tzinfo=timezone.utc)

    def test_full_collection_boundary_and_active_run(self):
        policy = CollectionPolicy()
        self.assertTrue(policy.full_collection_due(now=self.now, last_started_at=None, has_active=False))
        for delta, due in [(timedelta(hours=6)-timedelta(microseconds=1), False),
                           (timedelta(hours=6), True), (timedelta(days=2), True)]:
            self.assertEqual(policy.full_collection_due(now=self.now, last_started_at=self.now-delta,
                                                       has_active=False), due)
            self.assertFalse(policy.full_collection_due(now=self.now, last_started_at=self.now-delta,
                                                        has_active=True))

    def test_stale_boundary_fallback_and_minimum(self):
        for seconds, expected in [(30, 30), (1, 15), (90, 90)]:
            policy = CollectionPolicy(stale_after=timedelta(seconds=seconds))
            cutoff = self.now-timedelta(seconds=expected)
            self.assertEqual(policy.stale_cutoff(self.now), cutoff)
            self.assertFalse(policy.is_stale(now=self.now, heartbeat_at=cutoff, started_at=cutoff))
            self.assertTrue(policy.is_stale(now=self.now, heartbeat_at=None,
                                           started_at=cutoff-timedelta(microseconds=1)))
            self.assertFalse(policy.is_stale(now=self.now, heartbeat_at=self.now,
                                            started_at=cutoff-timedelta(days=1)))
