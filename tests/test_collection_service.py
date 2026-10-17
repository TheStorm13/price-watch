import asyncio
import unittest
from dataclasses import replace
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from marketplace_connector import (
    Availability,
    ConnectorRegistry,
    ProductRef,
    ProductSnapshot,
)
from marketplace_connector.domain.errors import ProductNotFound
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
        deals_enabled=True,
        created_at=NOW,
        updated_at=NOW,
    )


class FakeConnector:
    def __init__(self, marketplace, fail=False):
        self.marketplace = marketplace
        self.fail = fail

    @asynccontextmanager
    async def collection_session(self):
        yield

    async def get_product(self, external_id):
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

    async def list_collection_cards(self, card_id=None):
        return [item for item in self.cards if card_id is None or item.id == card_id]

    async def start_run(self, total_count):
        self.total_count = total_count
        return 42

    async def save_observation(self, item, run_id, snapshot):
        self.saved.append((item, run_id, snapshot))

    async def finish_run(self, run_id, status, success_count, failure_count):
        self.finished.append((run_id, status, success_count, failure_count))

    async def set_run_current(self, run_id, item):
        if self.fail_on_current:
            raise RuntimeError("progress failed")
        self.current.append((run_id, item.id))

    async def update_run_progress(self, run_id, success_count, failure_count):
        self.progress.append((run_id, success_count, failure_count))

    async def record_run_error(self, run_id, error, success_count, failure_count):
        self.errors.append((run_id, error, success_count, failure_count))

    async def cards_for_run(self, run):
        return [item for item in self.cards if item.id in (run.target_card_ids or ())]


class CollectionServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_excluded_card_still_collects_in_full_and_single_runs(self):
        excluded = replace(card(2, "ozon", "200"), deals_enabled=False)
        repository = FakeRepository([card(1, "ozon", "100"), excluded])
        service = CollectionService(repository, ConnectorRegistry([FakeConnector("ozon")]))

        summary = await service.collect()
        self.assertEqual(summary.success_count, 2)
        self.assertEqual({item.id for item, _, _ in repository.saved}, {1, 2})

        repository.saved.clear()
        summary = await service.collect(excluded.id)
        self.assertEqual(summary.success_count, 1)
        self.assertEqual([item.id for item, _, _ in repository.saved], [2])

    async def test_async_collection_limits_to_five_tabs_and_keeps_card_errors(self):
        class AsyncConnector(FakeConnector):
            def __init__(self):
                super().__init__("ozon")
                self.active = 0
                self.peak = 0
                self.opens = 0
                self.closes = 0

            @asynccontextmanager
            async def collection_session(self):
                self.opens += 1
                try:
                    yield
                finally:
                    self.closes += 1

            async def get_product(self, external_id):
                self.active += 1
                self.peak = max(self.peak, self.active)
                try:
                    await asyncio.sleep(0.01)
                    if external_id == "3":
                        raise RuntimeError("async card failed")
                    return await super().get_product(external_id)
                finally:
                    self.active -= 1

        repository = FakeRepository([card(i, "ozon", str(i)) for i in range(1, 10)])
        connector = AsyncConnector()
        with self.assertLogs("price_analyzer.application.collection_service", level="ERROR"):
            result = await CollectionService(repository, ConnectorRegistry([connector])).collect()

        self.assertEqual(connector.peak, 5)
        self.assertEqual((connector.opens, connector.closes), (1, 1))
        self.assertEqual((result.success_count, result.failure_count), (8, 1))
        self.assertEqual(len(repository.saved), 8)
        self.assertEqual(repository.errors[0][1]["externalId"], "3")

    async def test_uses_one_connector_session_across_cards_and_closes_after_error(self):
        class SessionConnector(FakeConnector):
            def __init__(self):
                super().__init__("ozon")
                self.opens = 0
                self.closes = 0

            @asynccontextmanager
            async def collection_session(self):
                self.opens += 1
                try:
                    yield
                finally:
                    self.closes += 1

            async def get_product(self, external_id):
                if external_id in {"100", "300"}:
                    raise RuntimeError("first card failed")
                return await super().get_product(external_id)

        repository = FakeRepository([card(1, "ozon", "100"), card(2, "ozon", "200")])
        connector = SessionConnector()
        with self.assertLogs("price_analyzer.application.collection_service", level="ERROR"):
            result = await CollectionService(repository, ConnectorRegistry([connector])).collect()

        self.assertEqual((connector.opens, connector.closes), (1, 1))
        self.assertEqual((result.success_count, result.failure_count), (1, 1))
        self.assertEqual(repository.saved[0][0].external_id, "200")

    async def test_closes_connector_session_after_unexpected_run_failure(self):
        class SessionConnector(FakeConnector):
            def __init__(self):
                super().__init__("ozon")
                self.closed = False

            @asynccontextmanager
            async def collection_session(self):
                try:
                    yield
                finally:
                    self.closed = True

        class FailingRepository(FakeRepository):
            async def set_run_current(self, run_id, item):
                if item.id == 2:
                    raise RuntimeError("progress failed")
                await super().set_run_current(run_id, item)

        repository = FailingRepository([card(1, "ozon", "100"), card(2, "ozon", "200")])
        connector = SessionConnector()
        run = CollectionRun(77, "running", 2, 0, 0, None, None, None, None, None, None, NOW, None, (1, 2))

        with self.assertRaisesRegex(RuntimeError, "progress failed"):
            await CollectionService(repository, ConnectorRegistry([connector])).execute_run(run)

        self.assertTrue(connector.closed)
        self.assertEqual(repository.finished, [(77, "failed", 1, 0)])

    async def test_collects_cards_and_continues_after_connector_error(self):
        repository = FakeRepository(
            [card(1, "ozon", "100"), card(2, "wildberries", "200")]
        )
        registry = ConnectorRegistry(
            [FakeConnector("ozon"), FakeConnector("wildberries", fail=True)]
        )

        with self.assertLogs(
            "price_analyzer.application.collection_service", level="ERROR"
        ):
            result = await CollectionService(repository, registry).collect()

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

    async def test_collects_only_requested_card(self):
        repository = FakeRepository(
            [card(1, "ozon", "100"), card(2, "ozon", "200")]
        )
        service = CollectionService(
            repository, ConnectorRegistry([FakeConnector("ozon")])
        )

        result = await service.collect(card_id=2)

        self.assertEqual(result.status, "completed")
        self.assertEqual(repository.total_count, 1)
        self.assertEqual(repository.saved[0][0].id, 2)

    async def test_missing_product_is_successful_out_of_stock_observation(self):
        class MissingProductConnector(FakeConnector):
            async def get_product(self, external_id):
                if external_id == "100":
                    raise ProductNotFound("Ozon перенаправил товар на поиск")
                return await super().get_product(external_id)

        missing = replace(
            card(1, "ozon", "100"), title="Старое название",
            url="https://ozon.ru/t/example",
        )
        repository = FakeRepository([missing, card(2, "ozon", "200"),
                                     card(3, "ozon", "300")])
        service = CollectionService(
            repository, ConnectorRegistry([MissingProductConnector("ozon")])
        )

        result = await service.collect()

        self.assertEqual((result.status, result.success_count, result.failure_count),
                         ("completed", 3, 0))
        self.assertEqual(repository.errors, [])
        snapshot = next(snapshot for item, _, snapshot in repository.saved if item.id == 1)
        self.assertEqual(snapshot.ref, ProductRef("ozon", "100"))
        self.assertEqual(snapshot.availability, Availability.OUT_OF_STOCK)
        self.assertIsNone(snapshot.price)
        self.assertEqual((snapshot.title, snapshot.url),
                         ("Старое название", "https://ozon.ru/t/example"))
        untitled = next(snapshot for item, _, snapshot in repository.saved if item.id == 3)
        self.assertEqual(untitled.title, "Товар 300")
        self.assertEqual(repository.finished, [(42, "completed", 3, 0)])

    async def test_rejects_unknown_card_without_creating_run(self):
        repository = FakeRepository([])
        service = CollectionService(
            repository, ConnectorRegistry([FakeConnector("ozon")])
        )

        with self.assertRaises(LookupError):
            await service.collect(card_id=999)

        self.assertFalse(hasattr(repository, "total_count"))

    async def test_executes_precreated_worker_run_and_reports_progress(self):
        repository = FakeRepository([card(1, "ozon", "100")])
        service = CollectionService(
            repository, ConnectorRegistry([FakeConnector("ozon")])
        )

        run = CollectionRun(77, "running", 1, 0, 0, None, None, None, None, None, None, NOW, None, (1,))
        result = await service.execute_run(run)

        self.assertEqual(result.run_id, 77)
        self.assertEqual(repository.current, [(77, 1)])
        self.assertEqual(repository.progress, [(77, 1, 0)])
        self.assertEqual(repository.finished, [(77, "completed", 1, 0)])

    async def test_unexpected_run_failure_keeps_traceback(self):
        repository = FakeRepository([card(1, "ozon", "100")])
        repository.fail_on_current = True
        service = CollectionService(repository, ConnectorRegistry([FakeConnector("ozon")]))
        run = CollectionRun(77, "running", 1, 0, 0, None, None, None, None, None, None, NOW, None, (1,))

        with self.assertRaisesRegex(RuntimeError, "progress failed"):
            await service.execute_run(run)

        self.assertEqual(repository.finished, [(77, "failed", 0, 0)])
        self.assertIn("RuntimeError: progress failed", repository.errors[0][1]["traceback"])


if __name__ == "__main__":
    unittest.main()
