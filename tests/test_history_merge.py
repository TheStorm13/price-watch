import unittest
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from price_analyzer.domain.history_merge import (
    ConflictingObservation,
    HistoryEvent,
    merge_history,
)


START = datetime(2026, 1, 1, tzinfo=timezone.utc)


def point(minute, price, source="local", source_id=0, availability="in_stock"):
    return HistoryEvent(
        START + timedelta(minutes=minute),
        None if price is None else Decimal(price),
        availability, source, source_id,
    )


class HistoryMergeTests(unittest.TestCase):
    def test_interleaved_histories_compact_equal_neighbours(self):
        merged = merge_history([
            point(0, "100", source_id=1),
            point(2, "90", source_id=2),
            point(4, "100", source_id=3),
            point(1, "100", "import", 0),
            point(3, "90", "import", 1),
            point(5, "100", "import", 2),
            point(6, "80", "import", 3),
        ])
        self.assertEqual([(item.source, item.source_id) for item in merged],
                         [("local", 1), ("local", 2), ("local", 3), ("import", 3)])

    def test_null_availability_breaks_price_series(self):
        merged = merge_history([
            point(0, "100"), point(1, None, availability="out_of_stock"),
            point(2, "100"),
        ])
        self.assertEqual([item.price for item in merged],
                         [Decimal("100"), None, Decimal("100")])

    def test_availability_transitions_are_retained_even_at_the_same_price(self):
        merged = merge_history([
            point(0, "100"), point(1, "100", availability="unknown"),
            point(2, "100", availability="out_of_stock"),
            point(3, "100", availability="out_of_stock"), point(4, "100"),
        ])
        self.assertEqual([(item.price, item.availability) for item in merged], [
            (Decimal("100"), "in_stock"), (Decimal("100"), "unknown"),
            (None, "out_of_stock"), (Decimal("100"), "in_stock"),
        ])

    def test_same_timestamp_preserves_local_or_reports_conflict(self):
        same = merge_history([point(0, "100", source_id=1),
                              point(0, "100.00", "import", 0)])
        self.assertEqual(len(same), 1)
        self.assertEqual(same[0].source, "local")
        with self.assertRaises(ConflictingObservation):
            merge_history([point(0, "100", source_id=1),
                           point(0, "90", "import", 0)])
        with self.assertRaises(ConflictingObservation):
            merge_history([point(0, "100", source_id=1),
                           point(0, "100", "import", 0, availability="unknown")])


if __name__ == "__main__":
    unittest.main()
