import unittest
from datetime import datetime, timezone

from marketplace_connector import (
    Availability,
    ConnectorRegistry,
    ProductRef,
    ProductSnapshot,
)
from price_analyzer.application.collection_service import CollectionService
from price_analyzer.domain.models import CollectionRun, MarketplaceCard


NOW = datetime(2026, 9, 21, tzinfo=timezone.utc)


def card(card_id, marketplace, external_id):
    return MarketplaceCard(
        id=card_id,
        marketplace=marketplace,
        external_id=external_id,
        title=None,
        url=None,
        is_active=True,
        created_at=NOW,
        updated_at=NOW,
    )


class FakeConnector:
    def __init__(self, marketplace, fail=False):
        self.marketplace = marketplace
        self.fail = fail

    def get_product(self, external_id):
        if self.fail:
            raise RuntimeError("connector failed")
        return ProductSnapshot(
            ref=ProductRef(self.marketplace, external_id),
            title=f"Товар {external_id}",
            url=f"https://{self.marketplace}.test/{external_id}",
            availability=Availability.IN_STOCK,
            price=100,
            collected_at=NOW,
        )


class FakeRepository:
    def __init__(self, cards):
        self.cards = cards
        self.saved = []
        self.finished = []
        self.current = []
        self.progress = []
        self.errors = []
        self.fail_on_current = False

    def list_active_cards(self, card_id=None):
        return [item for item in self.cards if card_id is None or item.id == card_id]

    def start_run(self, total_count):
        self.total_count = total_count
        return 42

    def save_observation(self, item, run_id, snapshot):
        self.saved.append((item, run_id, snapshot))

    def finish_run(self, run_id, status, success_count, failure_count):
        self.finished.append((run_id, status, success_count, failure_count))

    def set_run_current(self, run_id, item):
        if self.fail_on_current:
            raise RuntimeError("progress failed")
        self.current.append((run_id, item.id))

    def update_run_progress(self, run_id, success_count, failure_count):
        self.progress.append((run_id, success_count, failure_count))

    def record_run_error(self, run_id, error, success_count, failure_count):
        self.errors.append((run_id, error, success_count, failure_count))

    def cards_for_run(self, run):
        return [item for item in self.cards if item.id in (run.target_card_ids or ())]


class CollectionServiceTests(unittest.TestCase):
    def test_collects_cards_and_continues_after_connector_error(self):
        repository = FakeRepository(
            [card(1, "ozon", "100"), card(2, "wildberries", "200")]
        )
        registry = ConnectorRegistry(
            [FakeConnector("ozon"), FakeConnector("wildberries", fail=True)]
        )

        with self.assertLogs(
            "price_analyzer.application.collection_service", level="ERROR"
        ):
            result = CollectionService(repository, registry).collect()

        self.assertEqual(result.run_id, 42)
        self.assertEqual(result.status, "completed_with_errors")
        self.assertEqual(result.success_count, 1)
        self.assertEqual(result.failure_count, 1)
        self.assertEqual(len(repository.saved), 1)
        self.assertEqual(repository.errors[0][1]["message"], "connector failed")
        self.assertIn("RuntimeError: connector failed", repository.errors[0][1]["traceback"])
        self.assertEqual(
            repository.finished,
            [(42, "completed_with_errors", 1, 1)],
        )

    def test_collects_only_requested_card(self):
        repository = FakeRepository(
            [card(1, "ozon", "100"), card(2, "ozon", "200")]
        )
        service = CollectionService(
            repository, ConnectorRegistry([FakeConnector("ozon")])
        )

        result = service.collect(card_id=2)

        self.assertEqual(result.status, "completed")
        self.assertEqual(repository.total_count, 1)
        self.assertEqual(repository.saved[0][0].id, 2)

    def test_rejects_unknown_card_without_creating_run(self):
        repository = FakeRepository([])
        service = CollectionService(
            repository, ConnectorRegistry([FakeConnector("ozon")])
        )

        with self.assertRaises(LookupError):
            service.collect(card_id=999)

        self.assertFalse(hasattr(repository, "total_count"))

    def test_executes_precreated_worker_run_and_reports_progress(self):
        repository = FakeRepository([card(1, "ozon", "100")])
        service = CollectionService(
            repository, ConnectorRegistry([FakeConnector("ozon")])
        )

        run = CollectionRun(77, "running", 1, 0, 0, None, None, None, None, None, None, NOW, None, (1,))
        result = service.execute_run(run)

        self.assertEqual(result.run_id, 77)
        self.assertEqual(repository.current, [(77, 1)])
        self.assertEqual(repository.progress, [(77, 1, 0)])
        self.assertEqual(repository.finished, [(77, "completed", 1, 0)])

    def test_unexpected_run_failure_keeps_traceback(self):
        repository = FakeRepository([card(1, "ozon", "100")])
        repository.fail_on_current = True
        service = CollectionService(repository, ConnectorRegistry([FakeConnector("ozon")]))
        run = CollectionRun(77, "running", 1, 0, 0, None, None, None, None, None, None, NOW, None, (1,))

        with self.assertRaisesRegex(RuntimeError, "progress failed"):
            service.execute_run(run)

        self.assertEqual(repository.finished, [(77, "failed", 0, 0)])
        self.assertIn("RuntimeError: progress failed", repository.errors[0][1]["traceback"])


if __name__ == "__main__":
    unittest.main()
