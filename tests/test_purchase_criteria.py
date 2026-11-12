"""User purchase rules and precision boundaries, without a database."""
import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from price_watch.domain.purchase import PurchaseSettings, assess_purchase, validate_money

NOW = datetime(2026, 11, 12, tzinfo=timezone.utc)


class PurchaseCriteriaTests(unittest.TestCase):
    def assess(self, **changes):
        args = dict(evaluated_at=NOW, history_started_at=NOW-timedelta(days=31),
                    price=Decimal('850'), availability='in_stock', minimum=Decimal('800'),
                    maximum=Decimal('1000'), average=Decimal('1000'), target=None,
                    settings=PurchaseSettings(Decimal('50'), Decimal('70')))
        args.update(changes)
        return assess_purchase(**args)

    def test_share_is_distance_to_minimum_and_includes_exact_threshold(self):
        for price, matched in [('860', True), ('860.000000000001', False), ('799', True)]:
            result = self.assess(price=Decimal(price))
            self.assertEqual(result['threshold'], Decimal('860'))
            self.assertEqual('historical_savings_share' in result['matches'], matched)

    def test_range_uses_whole_range_even_above_average(self):
        result = self.assess(price=Decimal('340'), minimum=Decimal('315'), maximum=Decimal('340'), average=Decimal('320'))
        self.assertEqual(result['matches'], ['small_range'])
        self.assertEqual(self.assess(price=Decimal('800'))['matches'], ['historical_savings_share'])

    def test_three_matches_are_or_and_ordered(self):
        result = self.assess(target=Decimal('900'), settings=PurchaseSettings(Decimal('200'), Decimal('70')))
        self.assertEqual(result['matches'], ['small_range', 'target_price', 'historical_savings_share'])
        self.assertTrue(result['is_match'])

    def test_strict_month_and_goal_without_history(self):
        for start in [None, NOW-timedelta(days=30), NOW-timedelta(days=30)+timedelta(microseconds=1)]:
            result = self.assess(history_started_at=start, target=Decimal('850'))
            self.assertFalse(result['history_eligible'])
            self.assertEqual(result['matches'], ['target_price'])
        self.assertTrue(self.assess(history_started_at=NOW-timedelta(days=30,microseconds=1))['history_eligible'])

    def test_constant_zero_tolerance_and_undefined_share(self):
        result = self.assess(price=Decimal('800'), minimum=Decimal('800'), maximum=Decimal('800'), average=Decimal('800'),
                             settings=PurchaseSettings(Decimal('0'), Decimal('100')))
        self.assertEqual(result['matches'], ['small_range'])
        self.assertIsNone(result['threshold'])

    def test_empty_unavailable_disabled_and_missing_statistics(self):
        for changes in [dict(availability='out_of_stock'), dict(availability='unknown'), dict(price=None),
                        dict(settings=PurchaseSettings()), dict(minimum=None, maximum=None, average=None)]:
            self.assertFalse(self.assess(**changes)['is_match'])

    def test_money_validation_does_not_round_or_accept_non_finite(self):
        for value in ['0', '-1', 'NaN', 'Infinity', '0.001', '1000000000000', 'text', '', '1e2', 100, 1.1]:
            with self.subTest(value=value), self.assertRaises(ValueError): validate_money(value)
        self.assertEqual(validate_money('0', allow_zero=True), Decimal(0))
        self.assertEqual(validate_money('999999999999.99'), Decimal('999999999999.99'))

    def test_large_decimal_prices_keep_subkopeck_threshold_precision(self):
        result = self.assess(price=Decimal('999999999999.98'), average=Decimal('999999999999.99'),
                             minimum=Decimal('999999999999.98'), maximum=Decimal('999999999999.99'),
                             settings=PurchaseSettings(Decimal('.01'), Decimal('70')))
        self.assertEqual(result['threshold'], Decimal('999999999999.983'))
        self.assertEqual(result['matches'], ['small_range', 'historical_savings_share'])
