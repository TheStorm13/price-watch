import os
import unittest
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4
from sqlalchemy import delete, func, select
from datetime import timedelta
from httpx import ASGITransport, AsyncClient

from marketplace_connector import Availability, ConnectorRegistry, ProductRef, ProductSnapshot
from price_analyzer.infrastructure.postgres import (
    AsyncDatabase,
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
from price_analyzer.worker import CollectionWorker


TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")


@unittest.skipUnless(TEST_DATABASE_URL, "TEST_DATABASE_URL не задан")
class PostgresRepositoryIntegrationTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        cls.database = Database(TEST_DATABASE_URL).open()
        MigrationRunner(cls.database).apply()

    async def asyncSetUp(self):
        self.async_database = await AsyncDatabase(TEST_DATABASE_URL).open()

    async def asyncTearDown(self):
        await self.async_database.close()

    async def test_api_lifespan_opens_async_database(self):
        app = create_app(database_url=TEST_DATABASE_URL)
        async with app.router.lifespan_context(app):
            async with AsyncClient(transport=ASGITransport(app=app),
                                   base_url="http://testserver") as client:
                response = await client.get("/api/cards")
        self.assertEqual(response.status_code, 200)

    async def test_worker_collects_with_async_connector_and_database(self):
        repository = PostgresPriceAnalyzerRepository(self.async_database)
        external_id = f"test-{uuid4()}"
        card = await repository.add_card("integration-test", external_id)
        run = await repository.create_queued_run(card.id)

        class Connector:
            marketplace = "integration-test"

            @asynccontextmanager
            async def collection_session(self):
                yield

            async def get_product(self, article):
                return ProductSnapshot(
                    ref=ProductRef(self.marketplace, article), title="Товар",
                    url="https://example.test/product", availability=Availability.IN_STOCK,
                    price=100,
                )

        async def connectors(_run):
            return ConnectorRegistry([Connector()])

        try:
            worker = CollectionWorker(repository, connectors)
            self.assertTrue(await worker.run_once())
            self.assertEqual((await repository.get_run(run.id)).status, "completed")
            self.assertEqual((await repository.get_card(card.id)).current_price,
                             Decimal("100.00"))
        finally:
            await repository.delete_card(card.id)
            with self.database.session() as session, session.begin():
                session.execute(delete(CollectionRunRecord).where(CollectionRunRecord.id == run.id))

    @classmethod
    def tearDownClass(cls):
        cls.database.close()

    async def test_export_import_merges_complete_history_idempotently(self):
        repository = PostgresPriceAnalyzerRepository(self.async_database)
        external_id = f"test-{uuid4()}"
        new_external_id = f"test-{uuid4()}"
        card = await repository.add_card("integration-test", external_id, "Местное название")
        start = datetime.now(timezone.utc) - timedelta(hours=1)
        try:
            with self.database.session() as session, session.begin():
                session.add(PriceHistoryRecord(
                    card_id=card.id, collection_run_id=None, price=Decimal("120.00"),
                    availability="in_stock", observed_at=start - timedelta(days=200),
                    snapshot={},
                ))
                for minute, price in ((0, "100.00"), (2, "90.00"), (4, "100.00")):
                    session.add(PriceHistoryRecord(
                        card_id=card.id, collection_run_id=None, price=Decimal(price),
                        availability="in_stock", observed_at=start + timedelta(minutes=minute),
                        snapshot={"not": "exported"},
                    ))
            exported = await repository.export_cards()
            item = next(item for item in exported["cards"] if item["external_id"] == external_id)
            self.assertEqual(exported["version"], 1)
            self.assertEqual(len(item["history"]), 4)
            self.assertEqual(set(item["history"][0]), {"price", "availability", "observed_at"})
            self.assertEqual(set(item), {"marketplace", "external_id", "title", "url",
                                         "is_active", "created_at", "history"})
            item["title"] = "Название из файла"
            item["created_at"] = start - timedelta(days=20)
            item["history"].extend({
                "price": Decimal(price), "availability": "in_stock",
                "observed_at": start + timedelta(minutes=minute),
            } for minute, price in ((1, "100.00"), (3, "90.00"),
                                    (5, "100.00"), (6, "80.00")))
            new_item = {**item, "external_id": new_external_id, "title": "Новая карточка",
                        "is_active": False, "history": [{
                            "price": Decimal("200.00"), "availability": "in_stock",
                            "observed_at": start,
                        }]}
            payload = [item, new_item]
            preview = await repository.import_cards(payload, preview=True)
            self.assertEqual(preview["cards_added"], 1)
            self.assertEqual(preview["cards_merged"], 1)
            self.assertEqual(preview["observations_added"], 2)
            self.assertEqual(await repository.count_history(card.id, 1), 3)
            self.assertEqual(await repository.import_cards(payload), preview)
            self.assertEqual((await repository.get_card(card.id)).card.title, "Местное название")
            self.assertEqual((await repository.get_card(card.id)).card.created_at,
                             start - timedelta(days=20))
            self.assertEqual([point.price for point in reversed(await repository.get_history(card.id, 1))],
                             [Decimal("100.00"), Decimal("90.00"),
                              Decimal("100.00"), Decimal("80.00")])
            self.assertEqual(await repository.count_history(card.id, 365), 5)
            self.assertEqual((await repository.import_cards(payload))["observations_added"], 0)
            imported = next(overview.card for overview in await repository.list_cards(include_inactive=True)
                            if overview.card.external_id == new_external_id)
            self.assertFalse(imported.is_active)
            self.assertEqual(await repository.count_history(imported.id, 1), 1)
        finally:
            for overview in await repository.list_cards(include_inactive=True):
                if overview.card.external_id in {external_id, new_external_id}:
                    await repository.delete_card(overview.card.id)

    async def test_card_collection_and_history_roundtrip(self):
        repository = PostgresPriceAnalyzerRepository(self.async_database)
        external_id = f"test-{uuid4()}"
        card = await repository.add_card("integration-test", external_id)
        run_id = await repository.start_run(1)
        try:
            snapshot = ProductSnapshot(
                ref=ProductRef("integration-test", external_id),
                title="Интеграционный товар",
                url="https://example.test/product",
                availability=Availability.IN_STOCK,
                price=123.45,
                collected_at=datetime.now(timezone.utc),
            )

            await repository.save_observation(card, run_id, snapshot)
            await repository.finish_run(run_id, "completed", 1, 0)

            history = await repository.get_history(card.id, 1)
            statistics = await repository.get_statistics(card.id, 1)
            self.assertEqual(len(history), 1)
            self.assertEqual(str(history[0].price), "123.45")
            self.assertEqual(statistics.average_price, Decimal("123.45"))
            self.assertTrue(await repository.delete_card(card.id))
            self.assertIsNone(await repository.get_card(card.id))
            with self.database.session() as session:
                history_count = session.scalar(
                    select(func.count()).select_from(PriceHistoryRecord).where(
                        PriceHistoryRecord.card_id == card.id
                    )
                )
            self.assertEqual(history_count, 0)
            self.assertFalse(await repository.delete_card(card.id))
        finally:
            with self.database.session() as session, session.begin():
                session.execute(delete(MarketplaceCardRecord).where(MarketplaceCardRecord.id == card.id))
                session.execute(delete(CollectionRunRecord).where(CollectionRunRecord.id == run_id))

    async def test_import_keeps_availability_transitions_at_the_same_price(self):
        repository = PostgresPriceAnalyzerRepository(self.async_database)
        external_id = f"test-{uuid4()}"
        start = datetime.now(timezone.utc) - timedelta(hours=1)
        history = [
            {"price": Decimal("100.00"), "availability": "in_stock", "observed_at": start},
            {"price": Decimal("100.00"), "availability": "out_of_stock",
             "observed_at": start + timedelta(minutes=1)},
            {"price": Decimal("100.00"), "availability": "in_stock",
             "observed_at": start + timedelta(minutes=2)},
        ]
        card_id = None
        try:
            summary = await repository.import_cards([{
                "marketplace": "integration-test", "external_id": external_id,
                "title": "Товар", "url": None, "is_active": True,
                "created_at": start, "history": history,
            }])
            self.assertEqual(summary["observations_added"], 3)
            card = next(overview.card for overview in await repository.list_cards()
                        if overview.card.external_id == external_id)
            card_id = card.id
            self.assertEqual(
                [(point.price, point.availability)
                 for point in reversed(await repository.get_history(card_id, 1))],
                [(Decimal("100.00"), "in_stock"), (None, "out_of_stock"),
                 (Decimal("100.00"), "in_stock")],
            )
        finally:
            if card_id is not None:
                await repository.delete_card(card_id)

    async def test_observations_keep_availability_transitions_and_skip_equal_state(self):
        repository = PostgresPriceAnalyzerRepository(self.async_database)
        external_id = f"test-{uuid4()}"
        card = await repository.add_card("integration-test", external_id)
        run_id = await repository.start_run(12)
        start = datetime.now(timezone.utc) - timedelta(hours=1)

        async def save(minute, price, availability=Availability.IN_STOCK):
            await repository.save_observation(card, run_id, ProductSnapshot(
                ref=ProductRef("integration-test", external_id), title="Товар",
                url="https://example.test/product", availability=availability,
                price=price, collected_at=start + timedelta(minutes=minute),
            ))

        try:
            for minute in range(4):
                await save(minute, 100)
            for minute in range(4, 7):
                await save(minute, 90)
            for minute in range(7, 10):
                await save(minute, 90, Availability.OUT_OF_STOCK)
            unavailable = await repository.get_card(card.id)
            self.assertEqual(unavailable.current_availability, "out_of_stock")
            self.assertIsNone(unavailable.current_price)
            await save(10, 90)
            self.assertEqual(
                [(point.observed_at, point.price, point.availability)
                 for point in reversed(await repository.get_history(card.id, 1))],
                [(start + timedelta(minutes=0), Decimal("100.00"), "in_stock"),
                 (start + timedelta(minutes=4), Decimal("90.00"), "in_stock"),
                 (start + timedelta(minutes=7), None, "out_of_stock"),
                 (start + timedelta(minutes=10), Decimal("90.00"), "in_stock")],
            )
            self.assertEqual((await repository.get_card(card.id)).current_price, Decimal("90.00"))
            # A late observation equal to the latest state is skipped.
            await save(2, 90)
            self.assertEqual(await repository.count_history(card.id, 1), 4)
            # Existing duplicates are left to the one-time migration.
            with self.database.session() as session, session.begin():
                for minute in (11, 12, 13):
                    session.add(PriceHistoryRecord(
                        card_id=card.id, collection_run_id=run_id,
                        price=Decimal("100.00"), availability="in_stock",
                        observed_at=start + timedelta(minutes=minute), snapshot={},
                    ))
                session.get(MarketplaceCardRecord, card.id).updated_at = start
            await save(14, 100)
            self.assertEqual(await repository.count_history(card.id, 1), 7)
            self.assertEqual((await repository.get_card(card.id)).last_observed_at,
                             start + timedelta(minutes=13))
            self.assertGreater((await repository.get_card(card.id)).card.updated_at,
                               start + timedelta(minutes=13))
        finally:
            await repository.delete_card(card.id)
            with self.database.session() as session, session.begin():
                session.execute(delete(CollectionRunRecord).where(CollectionRunRecord.id == run_id))

    async def test_queued_target_is_frozen_and_blocks_deletion(self):
        repository = PostgresPriceAnalyzerRepository(self.async_database)
        card = await repository.add_card("integration-test", f"test-{uuid4()}")
        run = await repository.create_queued_run(card.id)
        try:
            await repository.update_card(card.id, is_active=False)
            self.assertEqual(run.target_card_ids, (card.id,))
            self.assertEqual([item.id for item in await repository.cards_for_run(run)], [card.id])
            with self.assertRaises(CardInActiveRun):
                await repository.delete_card(card.id)
            await repository.finish_run(run.id, "failed", 0, 0)
            self.assertTrue(await repository.delete_card(card.id))
        finally:
            with self.database.session() as session, session.begin():
                session.execute(delete(MarketplaceCardRecord).where(MarketplaceCardRecord.id == card.id))
                session.execute(delete(CollectionRunRecord).where(CollectionRunRecord.id == run.id))

    async def test_chart_returns_saved_points_and_unavailable_gap(self):
        repository = PostgresPriceAnalyzerRepository(self.async_database)
        card = await repository.add_card("integration-test", f"test-{uuid4()}")
        start = datetime.now(timezone.utc) - timedelta(hours=1)
        prices = [Decimal("100.00"), Decimal("100.00"), Decimal("100.00"),
                  Decimal("90.00"), Decimal("90.00"), None, Decimal("90.00"),
                  None, Decimal("90.00")]
        try:
            with self.database.session() as session, session.begin():
                for index, price in enumerate(prices):
                    session.add(PriceHistoryRecord(
                        card_id=card.id, collection_run_id=None, price=price,
                        availability="out_of_stock" if index == 7 else "unknown" if price is None else "in_stock",
                        observed_at=start + timedelta(minutes=index), snapshot={},
                    ))
            points = await repository.get_chart_points(card.id, 7)
            self.assertEqual([point.price for point in points],
                             [Decimal("100.00"), Decimal("100.00"), Decimal("100.00"),
                              Decimal("90.00"), Decimal("90.00"), None, Decimal("90.00"),
                              None, Decimal("90.00")])
            self.assertEqual(await repository.count_history(card.id, 7), len(prices))
        finally:
            await repository.delete_card(card.id)

    async def test_error_is_persisted_with_progress(self):
        repository = PostgresPriceAnalyzerRepository(self.async_database)
        card = await repository.add_card("integration-test", f"test-{uuid4()}")
        run = await repository.create_queued_run(card.id)
        try:
            error = {"cardId": card.id, "marketplace": "integration-test",
                     "externalId": card.external_id, "at": datetime.now(timezone.utc).isoformat(),
                     "type": "RuntimeError", "message": "failed", "traceback": "full traceback"}
            await repository.record_run_error(run.id, error, 0, 1)
            loaded = await repository.get_run(run.id)
            self.assertEqual(loaded.failure_count, 1)
            self.assertEqual(loaded.errors[0]["traceback"], "full traceback")
        finally:
            await repository.finish_run(run.id, "failed", 0, 1)
            await repository.delete_card(card.id)
            with self.database.session() as session, session.begin():
                session.execute(delete(CollectionRunRecord).where(CollectionRunRecord.id == run.id))

    async def test_stale_worker_run_is_failed_with_diagnostic(self):
        repository = PostgresPriceAnalyzerRepository(self.async_database)
        card = await repository.add_card("integration-test", f"test-{uuid4()}")
        run = await repository.create_queued_run(card.id)
        try:
            old = datetime.now(timezone.utc) - timedelta(minutes=2)
            with self.database.session() as session, session.begin():
                record = session.get(CollectionRunRecord, run.id)
                record.status = "waiting_for_user"
                record.worker_id = "dead-worker"
                record.heartbeat_at = old
            await repository.fail_stale_runs(datetime.now(timezone.utc) - timedelta(seconds=30))
            loaded = await repository.get_run(run.id)
            self.assertEqual(loaded.status, "failed")
            self.assertEqual(loaded.errors[0]["type"], "WorkerStopped")
            self.assertIsNotNone(loaded.finished_at)
        finally:
            await repository.delete_card(card.id)
            with self.database.session() as session, session.begin():
                session.execute(delete(CollectionRunRecord).where(CollectionRunRecord.id == run.id))

    async def test_real_api_chart_uses_full_history_and_run_exposes_errors(self):
        repository = PostgresPriceAnalyzerRepository(self.async_database)
        card = await repository.add_card("ozon", f"{uuid4().int % 10**15:015d}")
        start = datetime.now(timezone.utc) - timedelta(hours=2)
        run = await repository.create_queued_run(card.id)
        try:
            with self.database.session() as session, session.begin():
                for index in range(60):
                    session.add(PriceHistoryRecord(
                        card_id=card.id, collection_run_id=None,
                        price=Decimal("100.00") if index < 30 else Decimal("90.00"),
                        availability="in_stock", observed_at=start + timedelta(minutes=index),
                        snapshot={},
                    ))
            await repository.record_run_error(run.id, {
                "cardId": card.id, "marketplace": "ozon", "externalId": card.external_id,
                "at": datetime.now(timezone.utc).isoformat(), "type": "RuntimeError",
                "message": "network failed", "traceback": "full traceback",
            }, 0, 1)
            await repository.finish_run(run.id, "completed_with_errors", 0, 1)
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
                                 [100.0] * 30 + [90.0] * 30)
                self.assertEqual(detail.json()["errors"][0]["traceback"], "full traceback")
                self.assertIsNone(runs.json()[0]["errors"])

            await check_api()
        finally:
            await repository.delete_card(card.id)
            with self.database.session() as session, session.begin():
                session.execute(delete(CollectionRunRecord).where(CollectionRunRecord.id == run.id))

    async def test_only_full_runs_reset_automatic_collection_clock(self):
        repository = PostgresPriceAnalyzerRepository(self.async_database)
        cards = [await repository.add_card("integration-test", f"test-{uuid4()}") for _ in range(2)]
        future = datetime(2100, 1, 1, tzinfo=timezone.utc)
        scheduled = single = later = manual_full = final = None
        try:
            scheduled = await repository.create_due_run(future)
            self.assertIsNotNone(scheduled)
            self.assertIn(cards[0].id, scheduled.target_card_ids)
            self.assertIsNone(await repository.create_due_run(future + timedelta(hours=13)))
            await repository.finish_run(scheduled.id, "completed", 0, 0)
            self.assertIsNone(await repository.create_due_run(future + timedelta(hours=11)))

            single = await repository.create_queued_run(cards[0].id)
            with self.database.session() as session, session.begin():
                session.get(CollectionRunRecord, single.id).started_at = future + timedelta(hours=11)
            await repository.finish_run(single.id, "completed", 1, 0)
            await repository.delete_card(cards[0].id)
            self.assertIsNone((await repository.get_run(single.id)).requested_card_id)

            later = await repository.create_due_run(future + timedelta(hours=13))
            self.assertIsNotNone(later)
            self.assertEqual(later.started_at, future + timedelta(hours=13))
            self.assertEqual(later.target_card_ids, (cards[1].id,))
            await repository.finish_run(later.id, "completed", 1, 0)

            manual_full = await repository.create_queued_run()
            with self.database.session() as session, session.begin():
                session.get(CollectionRunRecord, manual_full.id).started_at = future + timedelta(hours=14)
            await repository.finish_run(manual_full.id, "completed", 1, 0)
            self.assertIsNone(await repository.create_due_run(future + timedelta(hours=25)))
            final = await repository.create_due_run(future + timedelta(hours=27))
            self.assertIsNotNone(final)
        finally:
            for run in (scheduled, single, later, manual_full, final):
                if run:
                    await repository.finish_run(run.id, "failed", 0, 0)
            for card in cards:
                await repository.delete_card(card.id)
            with self.database.session() as session, session.begin():
                for run in (scheduled, single, later, manual_full, final):
                    if run:
                        session.execute(delete(CollectionRunRecord).where(CollectionRunRecord.id == run.id))

    async def test_retry_targets_only_failed_cards_and_links_source(self):
        repository = PostgresPriceAnalyzerRepository(self.async_database)
        cards = [await repository.add_card("integration-test", f"test-{uuid4()}") for _ in range(2)]
        source = await repository.create_queued_run()
        retry = None
        try:
            await repository.record_run_error(source.id, {"cardId": cards[0].id, "marketplace": "integration-test",
                                                    "externalId": cards[0].external_id, "message": "failed"}, 1, 1)
            await repository.finish_run(source.id, "completed_with_errors", 1, 1)
            app = create_app(repository=repository)
            app.state.repository = repository

            async def create_via_api():
                async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
                    return await client.post(f"/api/runs/{source.id}/retry")

            response = await create_via_api()
            self.assertEqual(response.status_code, 202)
            self.assertEqual(response.json()["retryOfRunId"], source.id)
            retry = await repository.get_run(response.json()["id"])
            self.assertEqual(retry.target_card_ids, (cards[0].id,))
            self.assertEqual(retry.retry_of_run_id, source.id)
            with self.assertRaises(ValueError):
                await repository.create_retry_run(source.id)
        finally:
            if retry:
                await repository.finish_run(retry.id, "failed", 0, 0)
            for card in cards:
                await repository.delete_card(card.id)
            with self.database.session() as session, session.begin():
                for run in (retry, source):
                    if run:
                        session.execute(delete(CollectionRunRecord).where(CollectionRunRecord.id == run.id))

    async def test_deal_excludes_current_price_from_daily_average(self):
        repository = PostgresPriceAnalyzerRepository(self.async_database)
        card = await repository.add_card("integration-test", f"test-{uuid4()}")
        run_id = await repository.start_run(1)
        now = datetime.now(timezone.utc)
        try:
            with self.database.session() as session, session.begin():
                session.get(MarketplaceCardRecord, card.id).created_at = now - timedelta(days=10)
                for index, price in enumerate((100, 120, 80)):
                    session.add(PriceHistoryRecord(card_id=card.id, collection_run_id=run_id,
                        price=Decimal(price), availability="in_stock",
                        observed_at=now - timedelta(days=3 - index), snapshot={}))
            deal = next(item for item in await repository.list_deals(now) if item.card.card.id == card.id)
            self.assertEqual(deal.average_price, Decimal("110"))
            self.assertEqual(deal.savings, Decimal("30"))
            self.assertEqual(deal.baseline_days, 2)
            self.assertEqual(deal.last_collection_run_id, run_id)
            app = create_app(repository=repository)
            app.state.repository = repository

            async def check_deal_api():
                async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
                    response = await client.get("/api/cards/deals")
                self.assertEqual(response.status_code, 200)
                item = next(item for item in response.json() if item["card"]["id"] == card.id)
                self.assertEqual(item["averagePrice"], 110.0)
                self.assertEqual(item["lastCollectionRunId"], run_id)

            await check_deal_api()
            with self.database.session() as session, session.begin():
                session.add(PriceHistoryRecord(card_id=card.id, collection_run_id=run_id,
                    price=Decimal("150"), availability="in_stock", observed_at=now, snapshot={}))
            self.assertFalse(any(item.card.card.id == card.id for item in await repository.list_deals(now)))
        finally:
            await repository.delete_card(card.id)
            with self.database.session() as session, session.begin():
                session.execute(delete(CollectionRunRecord).where(CollectionRunRecord.id == run_id))


if __name__ == "__main__":
    unittest.main()
