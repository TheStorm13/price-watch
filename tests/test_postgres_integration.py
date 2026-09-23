import os
import asyncio
import unittest
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4
from sqlalchemy import delete, func, select
from datetime import timedelta
from httpx import ASGITransport, AsyncClient

from marketplace_connector import Availability, ProductRef, ProductSnapshot
from price_analyzer.infrastructure.postgres import (
    Database,
    MigrationRunner,
    PostgresPriceAnalyzerRepository,
)
from price_analyzer.infrastructure.postgres.models import (
    CollectionRunRecord,
    MarketplaceCardRecord,
    PriceHistoryRecord,
)
from price_analyzer.infrastructure.postgres.repository import CardInActiveRun
from price_analyzer.api import create_app


TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")


@unittest.skipUnless(TEST_DATABASE_URL, "TEST_DATABASE_URL не задан")
class PostgresRepositoryIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.database = Database(TEST_DATABASE_URL).open()
        MigrationRunner(cls.database).apply()

    @classmethod
    def tearDownClass(cls):
        cls.database.close()

    def test_card_collection_and_history_roundtrip(self):
        repository = PostgresPriceAnalyzerRepository(self.database)
        external_id = f"test-{uuid4()}"
        card = repository.add_card("integration-test", external_id)
        run_id = repository.start_run(1)
        try:
            snapshot = ProductSnapshot(
                ref=ProductRef("integration-test", external_id),
                title="Интеграционный товар",
                url="https://example.test/product",
                availability=Availability.IN_STOCK,
                price=123.45,
                collected_at=datetime.now(timezone.utc),
            )

            repository.save_observation(card, run_id, snapshot)
            repository.finish_run(run_id, "completed", 1, 0)

            history = repository.get_history(card.id, 1)
            statistics = repository.get_statistics(card.id, 1)
            self.assertEqual(len(history), 1)
            self.assertEqual(str(history[0].price), "123.45")
            self.assertEqual(statistics.average_price, Decimal("123.45"))
            self.assertTrue(repository.delete_card(card.id))
            self.assertIsNone(repository.get_card(card.id))
            with self.database.session() as session:
                history_count = session.scalar(
                    select(func.count()).select_from(PriceHistoryRecord).where(
                        PriceHistoryRecord.card_id == card.id
                    )
                )
            self.assertEqual(history_count, 0)
            self.assertFalse(repository.delete_card(card.id))
        finally:
            with self.database.session() as session, session.begin():
                session.execute(delete(MarketplaceCardRecord).where(MarketplaceCardRecord.id == card.id))
                session.execute(delete(CollectionRunRecord).where(CollectionRunRecord.id == run_id))

    def test_observations_keep_only_plateau_edges(self):
        repository = PostgresPriceAnalyzerRepository(self.database)
        external_id = f"test-{uuid4()}"
        card = repository.add_card("integration-test", external_id)
        run_id = repository.start_run(12)
        start = datetime.now(timezone.utc) - timedelta(hours=1)

        def save(minute, price, availability=Availability.IN_STOCK):
            repository.save_observation(card, run_id, ProductSnapshot(
                ref=ProductRef("integration-test", external_id), title="Товар",
                url="https://example.test/product", availability=availability,
                price=price, collected_at=start + timedelta(minutes=minute),
            ))

        try:
            for minute in range(4):
                save(minute, 100)
            for minute in range(4, 7):
                save(minute, 90)
            for minute in range(7, 10):
                save(minute, 90, Availability.OUT_OF_STOCK)
            save(10, 100)
            self.assertEqual(
                [(point.observed_at, point.price, point.availability)
                 for point in reversed(repository.get_history(card.id, 1))],
                [(start + timedelta(minutes=minute), Decimal(f"{price}.00"), availability)
                 for minute, price, availability in (
                     (0, 100, "in_stock"), (3, 100, "in_stock"),
                     (4, 90, "in_stock"), (6, 90, "in_stock"),
                     (7, 90, "out_of_stock"), (9, 90, "out_of_stock"),
                     (10, 100, "in_stock"),
                 )],
            )
            # A late observation triggers compaction of this card only.
            save(2, 100)
            self.assertEqual(repository.count_history(card.id, 1), 7)
            # Existing history from an older writer is also repaired on update.
            with self.database.session() as session, session.begin():
                for minute in (11, 12, 13):
                    session.add(PriceHistoryRecord(
                        card_id=card.id, collection_run_id=run_id,
                        price=Decimal("100.00"), availability="in_stock",
                        observed_at=start + timedelta(minutes=minute), snapshot={},
                    ))
            save(14, 100)
            self.assertEqual(repository.count_history(card.id, 1), 8)
            self.assertEqual(repository.get_card(card.id).last_observed_at,
                             start + timedelta(minutes=14))
        finally:
            repository.delete_card(card.id)
            with self.database.session() as session, session.begin():
                session.execute(delete(CollectionRunRecord).where(CollectionRunRecord.id == run_id))

    def test_queued_target_is_frozen_and_blocks_deletion(self):
        repository = PostgresPriceAnalyzerRepository(self.database)
        card = repository.add_card("integration-test", f"test-{uuid4()}")
        run = repository.create_queued_run(card.id)
        try:
            repository.update_card(card.id, is_active=False)
            self.assertEqual(run.target_card_ids, (card.id,))
            self.assertEqual([item.id for item in repository.cards_for_run(run)], [card.id])
            with self.assertRaises(CardInActiveRun):
                repository.delete_card(card.id)
            repository.finish_run(run.id, "failed", 0, 0)
            self.assertTrue(repository.delete_card(card.id))
        finally:
            with self.database.session() as session, session.begin():
                session.execute(delete(MarketplaceCardRecord).where(MarketplaceCardRecord.id == card.id))
                session.execute(delete(CollectionRunRecord).where(CollectionRunRecord.id == run.id))

    def test_chart_preserves_plateau_edges_and_null_breaks(self):
        repository = PostgresPriceAnalyzerRepository(self.database)
        card = repository.add_card("integration-test", f"test-{uuid4()}")
        start = datetime.now(timezone.utc) - timedelta(hours=1)
        prices = [Decimal("100.00"), Decimal("100.00"), Decimal("100.00"),
                  Decimal("90.00"), Decimal("90.00"), None, Decimal("90.00"),
                  Decimal("90.00"), Decimal("90.00")]
        try:
            with self.database.session() as session, session.begin():
                for index, price in enumerate(prices):
                    session.add(PriceHistoryRecord(
                        card_id=card.id, collection_run_id=None, price=price,
                        availability="out_of_stock" if index == 7 else "unknown" if price is None else "in_stock",
                        observed_at=start + timedelta(minutes=index), snapshot={},
                    ))
            points = repository.get_chart_points(card.id, 7)
            self.assertEqual([point.price for point in points],
                             [Decimal("100.00"), Decimal("100.00"), Decimal("90.00"),
                              Decimal("90.00"), None, Decimal("90.00"), None, Decimal("90.00")])
            self.assertEqual(repository.count_history(card.id, 7), len(prices))
        finally:
            repository.delete_card(card.id)

    def test_error_is_persisted_with_progress(self):
        repository = PostgresPriceAnalyzerRepository(self.database)
        card = repository.add_card("integration-test", f"test-{uuid4()}")
        run = repository.create_queued_run(card.id)
        try:
            error = {"cardId": card.id, "marketplace": "integration-test",
                     "externalId": card.external_id, "at": datetime.now(timezone.utc).isoformat(),
                     "type": "RuntimeError", "message": "failed", "traceback": "full traceback"}
            repository.record_run_error(run.id, error, 0, 1)
            loaded = repository.get_run(run.id)
            self.assertEqual(loaded.failure_count, 1)
            self.assertEqual(loaded.errors[0]["traceback"], "full traceback")
        finally:
            repository.finish_run(run.id, "failed", 0, 1)
            repository.delete_card(card.id)
            with self.database.session() as session, session.begin():
                session.execute(delete(CollectionRunRecord).where(CollectionRunRecord.id == run.id))

    def test_stale_worker_run_is_failed_with_diagnostic(self):
        repository = PostgresPriceAnalyzerRepository(self.database)
        card = repository.add_card("integration-test", f"test-{uuid4()}")
        run = repository.create_queued_run(card.id)
        try:
            old = datetime.now(timezone.utc) - timedelta(minutes=2)
            with self.database.session() as session, session.begin():
                record = session.get(CollectionRunRecord, run.id)
                record.status = "waiting_for_user"
                record.worker_id = "dead-worker"
                record.heartbeat_at = old
            repository.fail_stale_runs(datetime.now(timezone.utc) - timedelta(seconds=30))
            loaded = repository.get_run(run.id)
            self.assertEqual(loaded.status, "failed")
            self.assertEqual(loaded.errors[0]["type"], "WorkerStopped")
            self.assertIsNotNone(loaded.finished_at)
        finally:
            repository.delete_card(card.id)
            with self.database.session() as session, session.begin():
                session.execute(delete(CollectionRunRecord).where(CollectionRunRecord.id == run.id))

    def test_real_api_chart_uses_full_history_and_run_exposes_errors(self):
        repository = PostgresPriceAnalyzerRepository(self.database)
        card = repository.add_card("ozon", f"{uuid4().int % 10**15:015d}")
        start = datetime.now(timezone.utc) - timedelta(hours=2)
        run = repository.create_queued_run(card.id)
        try:
            with self.database.session() as session, session.begin():
                for index in range(60):
                    session.add(PriceHistoryRecord(
                        card_id=card.id, collection_run_id=None,
                        price=Decimal("100.00") if index < 30 else Decimal("90.00"),
                        availability="in_stock", observed_at=start + timedelta(minutes=index),
                        snapshot={},
                    ))
            repository.record_run_error(run.id, {
                "cardId": card.id, "marketplace": "ozon", "externalId": card.external_id,
                "at": datetime.now(timezone.utc).isoformat(), "type": "RuntimeError",
                "message": "network failed", "traceback": "full traceback",
            }, 0, 1)
            repository.finish_run(run.id, "completed_with_errors", 0, 1)
            app = create_app(repository=repository)
            app.state.repository = repository

            async def check_api():
                async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
                    history = await client.get(f"/api/cards/{card.id}/history?days=7")
                    chart = await client.get(f"/api/cards/{card.id}/chart?days=7")
                    detail = await client.get(f"/api/runs/{run.id}")
                    runs = await client.get("/api/runs")
                self.assertEqual(history.json()["totalCount"], 60)
                self.assertEqual(len(history.json()["history"]), 50)
                self.assertEqual([point["price"] for point in chart.json()["points"]],
                                 [100.0, 100.0, 90.0, 90.0])
                self.assertEqual(detail.json()["errors"][0]["traceback"], "full traceback")
                self.assertIsNone(runs.json()[0]["errors"])

            asyncio.run(check_api())
        finally:
            repository.delete_card(card.id)
            with self.database.session() as session, session.begin():
                session.execute(delete(CollectionRunRecord).where(CollectionRunRecord.id == run.id))


if __name__ == "__main__":
    unittest.main()
