import unittest
from datetime import datetime, timezone

from marketplace_connector import (
    Availability,
    ConnectorRegistry,
    ProductRef,
    ProductSnapshot,
)
from price_analyzer.application.collection_service import CollectionService
from price_analyzer.domain.models import MarketplaceCard


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
        self.current.append((run_id, item.id))

    def update_run_progress(self, run_id, success_count, failure_count):
        self.progress.append((run_id, success_count, failure_count))


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

        result = service.execute_run(run_id=77)

        self.assertEqual(result.run_id, 77)
        self.assertEqual(repository.current, [(77, 1)])
        self.assertEqual(repository.progress, [(77, 1, 0)])
        self.assertEqual(repository.finished, [(77, "completed", 1, 0)])


if __name__ == "__main__":
    unittest.main()
