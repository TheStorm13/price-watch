import asyncio
import os
import unittest
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4
from sqlalchemy import delete, func, select
from datetime import timedelta
from httpx import ASGITransport, AsyncClient

from marketplace_connector import Availability, ConnectorRegistry, ProductRef, MarketplaceCard
from price_watch.bootstrap import create_postgres_stores
from price_watch.infrastructure.postgres import (
    AsyncDatabase,
    Database,
    MigrationRunner,
)
from price_watch.infrastructure.postgres.models import (
    CollectionRunRecord,
    MarketplaceCardRecord,
    PriceHistoryRecord,
)
from price_watch.domain.errors import CardInActiveRun
from price_watch.api import create_app
from price_watch.worker import CollectionWorker


TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")


@unittest.skipUnless(TEST_DATABASE_URL, "TEST_DATABASE_URL не задан")
class PostgresRepositoryIntegrationTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        cls.database = Database(TEST_DATABASE_URL).open()
        MigrationRunner(cls.database).apply()

    async def asyncSetUp(self):
        self.async_database = await AsyncDatabase(TEST_DATABASE_URL).open()
        self.fixture_runs = []

    async def asyncTearDown(self):
        async with self.async_database.session() as session, session.begin():
            await session.execute(delete(CollectionRunRecord).where(CollectionRunRecord.id.in_(self.fixture_runs)))
        await self.async_database.close()

    async def fixture_run(self):
        async with self.async_database.session() as session, session.begin():
            record = CollectionRunRecord(status="completed", total_count=0, is_full_collection=False)
            session.add(record)
            await session.flush()
            self.fixture_runs.append(record.id)
            return record.id

    async def observe(self, repository, card, snapshot):
        run = await repository.runs.start_direct_run(card.id)
        self.fixture_runs.append(run.id)
        await repository.runs.save_result(run.lease, card, snapshot)
        await repository.runs.finish_run(run.lease)
        return run.id

    async def abandon_queued(self, repository, run):
        owned = await repository.runs.claim_next_run()
        self.assertEqual(owned.id, run.id)
        await repository.runs.fail_run(owned.lease, {"cardId": None, "message": "test complete"})


    async def test_api_lifespan_opens_async_database(self):
        app = create_app(database_url=TEST_DATABASE_URL)
        async with app.router.lifespan_context(app):
            async with AsyncClient(transport=ASGITransport(app=app),
                                   base_url="http://testserver") as client:
                response = await client.get("/api/catalog")
        self.assertEqual(response.status_code, 200)

    async def test_group_uses_cheapest_card_with_its_own_historical_minimum(self):
        repository = create_postgres_stores(self.async_database)
        first = await repository.cards.add_card("integration-test", f"test-{uuid4()}")
        second = await repository.cards.add_card("integration-test", f"test-{uuid4()}")
        group_id = await repository.groups.create_group("Группа бутылок", [first.id, second.id])
        observed = datetime.now(timezone.utc)
        try:
            async with self.async_database.session() as session, session.begin():
                session.add_all([
                    PriceHistoryRecord(card_id=first.id, collection_run_id=None, price=Decimal("60.00"), availability="in_stock", observed_at=observed - timedelta(days=2), snapshot={}),
                    PriceHistoryRecord(card_id=first.id, collection_run_id=None, price=Decimal("90.00"), availability="in_stock", observed_at=observed, snapshot={}),
                    PriceHistoryRecord(card_id=second.id, collection_run_id=None, price=Decimal("75.00"), availability="in_stock", observed_at=observed - timedelta(days=1), snapshot={}),
                    PriceHistoryRecord(card_id=second.id, collection_run_id=None, price=None, availability="out_of_stock", observed_at=observed, snapshot={}),
                ])
            group = next(group for group in (await repository.catalog.get_catalog())["groups"] if group["id"] == group_id)
            self.assertEqual(group["current_price"], Decimal("90.00"))
            self.assertEqual(group["minimum_price"], Decimal("60.00"))
            self.assertEqual(set(group["card_ids"]), {first.id, second.id})
            self.assertEqual({card.id for card in await repository.cards.list_collection_cards()} & {first.id, second.id}, {first.id, second.id})
            await repository.groups.delete_group(group_id)
            self.assertIsNone((await repository.cards.get_card(first.id)).card.group_id)
        finally:
            await repository.cards.delete_card(first.id)
            await repository.cards.delete_card(second.id)

    async def test_marketplaces_without_connectors_are_not_queued(self):
        repository = create_postgres_stores(self.async_database)
        ozon = await repository.cards.add_card("ozon", f"test-{uuid4()}")
        wildberries = await repository.cards.add_card("wildberries", f"{uuid4().int % 1000000000 + 1}:2")
        aliexpress = await repository.cards.add_card("aliexpress", f"{uuid4().int}:2")
        yandex_market = await repository.cards.add_card("yandex-market", f"test-{uuid4()}")
        try:
            app = create_app(services=repository.api)

            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
                response = await client.post("/api/runs", json={"cardId": yandex_market.id})
                self.assertEqual(response.status_code, 409)
                self.assertEqual(response.json()["error"]["code"], "connector_not_available")
            for card in (yandex_market,):
                with self.assertRaisesRegex(ValueError, "коннектор ещё не подключён"):
                    await repository.runs.create_queued_run(card.id)
            full_run = await repository.runs.create_queued_run()
            self.assertIn(ozon.id, [c.id for c in await repository.runs.cards_for_run(full_run.id)])
            self.assertIn(wildberries.id, [c.id for c in await repository.runs.cards_for_run(full_run.id)])
            self.assertIn(aliexpress.id, [c.id for c in await repository.runs.cards_for_run(full_run.id)])
            self.assertNotIn(yandex_market.id, [c.id for c in await repository.runs.cards_for_run(full_run.id)])
            await self.abandon_queued(repository, full_run)
            self.assertIn(wildberries.id, [card.id for card in await repository.cards.list_collection_cards()])
            self.assertIn(aliexpress.id, [card.id for card in await repository.cards.list_collection_cards()])
            self.assertNotIn(yandex_market.id, [card.id for card in await repository.cards.list_collection_cards()])
        finally:
            await repository.cards.delete_card(ozon.id)
            await repository.cards.delete_card(wildberries.id)
            await repository.cards.delete_card(aliexpress.id)
            await repository.cards.delete_card(yandex_market.id)

    async def test_worker_collects_with_async_connector_and_database(self):
        repository = create_postgres_stores(self.async_database)
        external_id = f"test-{uuid4()}"
        card = await repository.cards.add_card("integration-test", external_id)
        run = await repository.runs.create_queued_run(card.id)

        class Connector:
            marketplace = "integration-test"

            @asynccontextmanager
            async def collection_session(self):
                yield

            async def get_product(self, article):
                return MarketplaceCard(
                    ref=ProductRef(self.marketplace, article), title="Товар",
                    url="https://example.test/product", availability=Availability.IN_STOCK,
                    price=100,
                )

        async def connectors(_run):
            return ConnectorRegistry([Connector()])

        try:
            worker = CollectionWorker(repository.runs, connectors, execution=repository.runs)
            self.assertTrue(await worker.run_once())
            self.assertEqual((await repository.runs.get_run(run.id)).status, "completed")
            self.assertEqual((await repository.cards.get_card(card.id)).current_price,
                             Decimal("100.00"))
        finally:
            await repository.cards.delete_card(card.id)
            with self.database.session() as session, session.begin():
                session.execute(delete(CollectionRunRecord).where(CollectionRunRecord.id == run.id))

    @classmethod
    def tearDownClass(cls):
        cls.database.close()

    async def test_export_import_merges_complete_history_idempotently(self):
        repository = create_postgres_stores(self.async_database)
        external_id = f"test-{uuid4()}"
        new_external_id = f"test-{uuid4()}"
        card = await repository.cards.add_card("integration-test", external_id, "Местное название")
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
            exported = await repository.transfer.export_cards()
            item = next(item for item in exported["cards"] if item["external_id"] == external_id)
            self.assertEqual(exported["version"], 2)
            self.assertEqual(len(item["history"]), 4)
            self.assertEqual(set(item["history"][0]), {"price", "availability", "observed_at"})
            self.assertEqual(set(item), {"marketplace", "external_id", "title", "url", "image_url",
                                         "tags", "deals_enabled", "created_at", "history"})
            item["title"] = "Название из файла"
            item["image_url"] = "https://img.test/import.jpg"
            item["created_at"] = start - timedelta(days=20)
            item["history"].extend({
                "price": Decimal(price), "availability": "in_stock",
                "observed_at": start + timedelta(minutes=minute),
            } for minute, price in ((1, "100.00"), (3, "90.00"),
                                    (5, "100.00"), (6, "80.00")))
            new_item = {**item, "external_id": new_external_id, "title": "Новая карточка",
                        "deals_enabled": False, "history": [{
                            "price": Decimal("200.00"), "availability": "in_stock",
                            "observed_at": start,
                        }]}
            payload = [item, new_item]
            preview = await repository.transfer.import_cards(payload, preview=True)
            self.assertEqual(preview["cards_added"], 1)
            self.assertEqual(preview["cards_merged"], 1)
            self.assertEqual(preview["observations_added"], 2)
            self.assertEqual(await repository.history.count_history(card.id, 1), 3)
            self.assertEqual(await repository.transfer.import_cards(payload), preview)
            self.assertEqual((await repository.cards.get_card(card.id)).card.title, "Местное название")
            self.assertEqual((await repository.cards.get_card(card.id)).card.image_url,
                             "https://img.test/import.jpg")
            self.assertEqual((await repository.cards.get_card(card.id)).card.created_at,
                             start - timedelta(days=20))
            self.assertEqual([point.price for point in reversed(await repository.history.get_history(card.id, 1))],
                             [Decimal("100.00"), Decimal("90.00"),
                              Decimal("100.00"), Decimal("80.00")])
            self.assertEqual(await repository.history.count_history(card.id, 365), 5)
            self.assertEqual((await repository.transfer.import_cards(payload))["observations_added"], 0)
            imported = next(overview.card for overview in await repository.cards.list_cards()
                            if overview.card.ref.external_id == new_external_id)
            self.assertFalse(imported.deals_enabled)
            self.assertEqual(await repository.history.count_history(imported.id, 1), 1)
        finally:
            for overview in await repository.cards.list_cards():
                if overview.card.ref.external_id in {external_id, new_external_id}:
                    await repository.cards.delete_card(overview.card.id)

    async def test_export_import_restores_groups_membership_and_tags(self):
        repository = create_postgres_stores(self.async_database)
        first_external_id = f"test-{uuid4()}"
        second_external_id = f"test-{uuid4()}"
        group_name = f"Бутылки {uuid4()}"
        first = await repository.cards.add_card("integration-test", first_external_id, tags=["кухня", "подарок"])
        second = await repository.cards.add_card("integration-test", second_external_id, tags=["спорт"])
        group_id = None
        restored_group_id = None
        restored_card_ids = []
        try:
            group_id = await repository.groups.create_group(group_name, [first.id, second.id], tags=["бутылки"])
            exported = await repository.transfer.export_cards()
            members = {first_external_id, second_external_id}
            cards = [item for item in exported["cards"] if item["external_id"] in members]
            groups = [item for item in exported["groups"] if item["name"] == group_name]
            self.assertEqual({item["external_id"]: item["tags"] for item in cards}, {
                first_external_id: ["кухня", "подарок"], second_external_id: ["спорт"],
            })
            self.assertEqual(groups[0]["tags"], ["бутылки"])
            self.assertEqual({item["external_id"] for item in groups[0]["cards"]}, members)

            await repository.cards.delete_card(first.id)
            await repository.cards.delete_card(second.id)
            await repository.groups.delete_group(group_id)
            group_id = None

            preview = await repository.transfer.import_cards(cards, groups=groups, preview=True)
            self.assertEqual(preview["cards_added"], 2)
            self.assertEqual(preview["groups_added"], 1)
            self.assertEqual(await repository.transfer.import_cards(cards, groups=groups), preview)

            restored = [overview.card for overview in await repository.cards.list_cards()
                        if overview.card.ref.external_id in members]
            restored_card_ids = [card.id for card in restored]
            restored_group = next(group for group in (await repository.catalog.get_catalog())["groups"] if group["name"] == group_name)
            restored_group_id = restored_group["id"]
            self.assertEqual(restored_group["tags"], ["бутылки"])
            self.assertEqual(set(restored_group["card_ids"]), set(restored_card_ids))
            self.assertEqual({card.ref.external_id: list(card.tags) for card in restored}, {
                first_external_id: ["кухня", "подарок"], second_external_id: ["спорт"],
            })
            second_export = next(item for item in cards if item["external_id"] == second_external_id)
            second_export["tags"] = ["спорт", "набор"]
            groups[0]["tags"] = ["бутылки", "подарок"]
            self.assertEqual((await repository.transfer.import_cards(cards, groups=groups))["groups_added"], 0)
            restored_second = (await repository.cards.get_card(next(card.id for card in restored
                                                                if card.ref.external_id == second_external_id))).card
            self.assertEqual(list(restored_second.tags), ["спорт", "набор"])
            restored_group = next(group for group in (await repository.catalog.get_catalog())["groups"] if group["name"] == group_name)
            self.assertEqual(restored_group["tags"], ["бутылки", "подарок"])
            self.assertEqual(len([group for group in (await repository.catalog.get_catalog())["groups"]
                                  if group["name"] == group_name]), 1)
        finally:
            for card_id in {first.id, second.id, *restored_card_ids}:
                await repository.cards.delete_card(card_id)
            for current_group_id in {group_id, restored_group_id} - {None}:
                await repository.groups.delete_group(current_group_id)

    async def test_card_collection_and_history_roundtrip(self):
        repository = create_postgres_stores(self.async_database)
        external_id = f"test-{uuid4()}"
        card = await repository.cards.add_card("integration-test", external_id)
        run_id = await self.fixture_run()
        try:
            snapshot = MarketplaceCard(
                ref=ProductRef("integration-test", external_id),
                title="Интеграционный товар",
                url="https://example.test/product",
                availability=Availability.IN_STOCK,
                price=Decimal("123.45"),
                image_url="https://img.test/first.jpg",
                collected_at=datetime.now(timezone.utc),
            )

            await self.observe(repository, card, snapshot)
            self.assertEqual((await repository.cards.get_card(card.id)).card.image_url,
                             "https://img.test/first.jpg")
            await self.observe(repository, card, MarketplaceCard(
                ref=snapshot.ref, title=snapshot.title, url=snapshot.url,
                availability=snapshot.availability, price=snapshot.price,
                image_url="https://img.test/updated.jpg",
            ))
            self.assertEqual((await repository.cards.get_card(card.id)).card.image_url,
                             "https://img.test/updated.jpg")
            exported = await repository.transfer.export_cards()
            self.assertEqual(next(item for item in exported["cards"]
                                  if item["external_id"] == external_id)["image_url"],
                             "https://img.test/updated.jpg")

            history = await repository.history.get_history(card.id, 1)
            statistics = await repository.history.get_statistics(card.id, 1)
            self.assertEqual(len(history), 1)
            self.assertEqual(str(history[0].price), "123.45")
            self.assertEqual(statistics.average_price, Decimal("123.45"))
            self.assertTrue(await repository.cards.delete_card(card.id))
            self.assertIsNone(await repository.cards.get_card(card.id))
            with self.database.session() as session:
                history_count = session.scalar(
                    select(func.count()).select_from(PriceHistoryRecord).where(
                        PriceHistoryRecord.card_id == card.id
                    )
                )
            self.assertEqual(history_count, 0)
            self.assertFalse(await repository.cards.delete_card(card.id))
        finally:
            with self.database.session() as session, session.begin():
                session.execute(delete(MarketplaceCardRecord).where(MarketplaceCardRecord.id == card.id))
                session.execute(delete(CollectionRunRecord).where(CollectionRunRecord.id == run_id))

    async def test_collection_keeps_nonempty_title_and_refreshes_known_url(self):
        repository = create_postgres_stores(self.async_database)
        manual = await repository.cards.add_card("integration-test", f"test-{uuid4()}", title="Моё название")
        automatic = await repository.cards.add_card("integration-test", f"test-{uuid4()}")
        run_id = await self.fixture_run()
        try:
            async def save(card, title, url):
                await self.observe(repository, card, MarketplaceCard(
                    ref=ProductRef(card.ref.marketplace, card.ref.external_id),
                    title=title, url=url, availability=Availability.IN_STOCK, price=100,
                ))

            await save(manual, "Название площадки", "https://example.test/first")
            await save(automatic, "Первое название", "https://example.test/first")
            await save(manual, "Новое название площадки", "https://example.test/second")
            await save(automatic, "Второе название", "")
            manual_card = (await repository.cards.get_card(manual.id)).card
            automatic_card = (await repository.cards.get_card(automatic.id)).card
            self.assertEqual((manual_card.title, manual_card.url),
                             ("Моё название", "https://example.test/second"))
            self.assertEqual((automatic_card.title, automatic_card.url),
                             ("Первое название", "https://example.test/first"))
            await repository.cards.update_card(automatic.id, title="", update_title=True)
            await save(automatic, "Название после очистки", "")
            self.assertEqual((await repository.cards.get_card(automatic.id)).card.title,
                             "Название после очистки")
        finally:
            await repository.cards.delete_card(manual.id)
            await repository.cards.delete_card(automatic.id)
            with self.database.session() as session, session.begin():
                session.execute(delete(CollectionRunRecord).where(CollectionRunRecord.id == run_id))

    async def test_import_keeps_availability_transitions_at_the_same_price(self):
        repository = create_postgres_stores(self.async_database)
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
            summary = await repository.transfer.import_cards([{
                "marketplace": "integration-test", "external_id": external_id,
                "title": "Товар", "url": None, "deals_enabled": True,
                "created_at": start, "history": history,
            }])
            self.assertEqual(summary["observations_added"], 3)
            card = next(overview.card for overview in await repository.cards.list_cards()
                        if overview.card.ref.external_id == external_id)
            card_id = card.id
            self.assertEqual(
                [(point.price, point.availability)
                 for point in reversed(await repository.history.get_history(card_id, 1))],
                [(Decimal("100.00"), "in_stock"), (None, "out_of_stock"),
                 (Decimal("100.00"), "in_stock")],
            )
        finally:
            if card_id is not None:
                await repository.cards.delete_card(card_id)

    async def test_observations_keep_availability_transitions_and_skip_equal_state(self):
        repository = create_postgres_stores(self.async_database)
        external_id = f"test-{uuid4()}"
        card = await repository.cards.add_card("integration-test", external_id)
        run_id = await self.fixture_run()
        start = datetime.now(timezone.utc) - timedelta(hours=1)

        async def save(minute, price, availability=Availability.IN_STOCK):
            await self.observe(repository, card, MarketplaceCard(
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
            unavailable = await repository.cards.get_card(card.id)
            self.assertEqual(unavailable.current_availability, "out_of_stock")
            self.assertIsNone(unavailable.current_price)
            await save(10, 90)
            self.assertEqual(
                [(point.observed_at, point.price, point.availability)
                 for point in reversed(await repository.history.get_history(card.id, 1))],
                [(start + timedelta(minutes=0), Decimal("100.00"), "in_stock"),
                 (start + timedelta(minutes=4), Decimal("90.00"), "in_stock"),
                 (start + timedelta(minutes=7), None, "out_of_stock"),
                 (start + timedelta(minutes=10), Decimal("90.00"), "in_stock")],
            )
            self.assertEqual((await repository.cards.get_card(card.id)).current_price, Decimal("90.00"))
            # A late observation equal to the latest state is skipped.
            await save(2, 90)
            self.assertEqual(await repository.history.count_history(card.id, 1), 4)
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
            self.assertEqual(await repository.history.count_history(card.id, 1), 7)
            self.assertEqual((await repository.cards.get_card(card.id)).last_observed_at,
                             start + timedelta(minutes=13))
            self.assertGreater((await repository.cards.get_card(card.id)).card.updated_at,
                               start + timedelta(minutes=13))
        finally:
            await repository.cards.delete_card(card.id)
            with self.database.session() as session, session.begin():
                session.execute(delete(CollectionRunRecord).where(CollectionRunRecord.id == run_id))

    async def test_queued_target_is_frozen_and_blocks_deletion(self):
        repository = create_postgres_stores(self.async_database)
        card = await repository.cards.add_card("integration-test", f"test-{uuid4()}")
        run = await repository.runs.create_queued_run(card.id)
        self.fixture_runs.append(run.id)
        await repository.cards.update_card(card.id, deals_enabled=False)
        self.assertEqual([c.id for c in await repository.runs.cards_for_run(run.id)], [card.id])
        with self.assertRaises(CardInActiveRun):
            await repository.cards.delete_card(card.id)
        await self.abandon_queued(repository, run)
        self.assertTrue(await repository.cards.delete_card(card.id))

    async def test_chart_returns_saved_points_and_unavailable_gap(self):
        repository = create_postgres_stores(self.async_database)
        card = await repository.cards.add_card("integration-test", f"test-{uuid4()}")
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
            points = await repository.history.get_chart_points(card.id, 7)
            self.assertEqual([point.price for point in points],
                             [Decimal("100.00"), Decimal("100.00"), Decimal("100.00"),
                              Decimal("90.00"), Decimal("90.00"), None, Decimal("90.00"),
                              None, Decimal("90.00")])
            self.assertEqual(await repository.history.count_history(card.id, 7), len(prices))
        finally:
            await repository.cards.delete_card(card.id)

    async def test_error_is_persisted_with_progress(self):
        repository = create_postgres_stores(self.async_database)
        card = await repository.cards.add_card("integration-test", f"test-{uuid4()}")
        run = await repository.runs.start_direct_run(card.id)
        self.fixture_runs.append(run.id)
        error = {"cardId": card.id, "marketplace": card.ref.marketplace, "externalId": card.ref.external_id,
                 "message": "failed", "traceback": "full traceback"}
        await repository.runs.record_card_error(run.lease, card, error)
        loaded = await repository.runs.get_run(run.id)
        self.assertEqual(loaded.failure_count, 1)
        self.assertEqual(loaded.errors[0]["traceback"], "full traceback")
        await repository.runs.finish_run(run.lease)
        await repository.cards.delete_card(card.id)

    async def test_stale_worker_run_is_failed_with_diagnostic(self):
        repository = create_postgres_stores(self.async_database)
        card = await repository.cards.add_card("integration-test", f"test-{uuid4()}")
        run = await repository.runs.start_direct_run(card.id)
        self.fixture_runs.append(run.id)
        await repository.runs.save_result(run.lease, card, MarketplaceCard(ref=ProductRef(card.ref.marketplace,card.ref.external_id),
            title="Item",url="",price=Decimal("123.45"),availability=Availability.IN_STOCK))
        async with self.async_database.session() as session, session.begin():
            record = await session.get(CollectionRunRecord, run.id)
            record.heartbeat_at = datetime.now(timezone.utc)-timedelta(minutes=2)
        await repository.runs.fail_stale_runs(datetime.now(timezone.utc)-timedelta(seconds=30))
        loaded = await repository.runs.get_run(run.id)
        self.assertEqual(loaded.status,"failed")
        self.assertEqual(loaded.errors[0]["type"],"WorkerStopped")
        self.assertEqual((await repository.history.get_history(card.id,1))[0].price,Decimal("123.45"))
        await repository.cards.delete_card(card.id)

    async def test_real_api_chart_uses_full_history_and_run_exposes_errors(self):
        repository = create_postgres_stores(self.async_database)
        card = await repository.cards.add_card("ozon", f"{uuid4().int % 10**15:015d}")
        start = datetime.now(timezone.utc) - timedelta(hours=2)
        run = await repository.runs.start_direct_run(card.id)
        try:
            with self.database.session() as session, session.begin():
                for index in range(60):
                    session.add(PriceHistoryRecord(
                        card_id=card.id, collection_run_id=None,
                        price=Decimal("100.00") if index < 30 else Decimal("90.00"),
                        availability="in_stock", observed_at=start + timedelta(minutes=index),
                        snapshot={},
                    ))
            await repository.runs.record_card_error(run.lease, card, {
                "cardId": card.id, "marketplace": "ozon", "externalId": card.ref.external_id,
                "at": datetime.now(timezone.utc).isoformat(), "type": "RuntimeError",
                "message": "network failed", "traceback": "full traceback",
            })
            await repository.runs.finish_run(run.lease)
            app = create_app(services=repository.api)


            async def check_api():
                async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
                    history = await client.get(f"/api/cards/{card.id}/history?days=7")
                    chart = await client.get(f"/api/cards/{card.id}/chart?days=7")
                    detail = await client.get(f"/api/runs/{run.id}")
                    runs = await client.get("/api/runs")
                self.assertEqual(history.json()["totalCount"], 60)
                self.assertEqual(len(history.json()["history"]), 50)
                self.assertEqual([point["price"] for point in chart.json()["points"]],
                                 ["100.00"] * 30 + ["90.00"] * 30)
                self.assertEqual(detail.json()["errors"][0]["traceback"], "full traceback")
                self.assertIsNone(runs.json()[0]["errors"])

            await check_api()
        finally:
            await repository.cards.delete_card(card.id)
            with self.database.session() as session, session.begin():
                session.execute(delete(CollectionRunRecord).where(CollectionRunRecord.id == run.id))

    async def test_only_full_runs_reset_automatic_collection_clock(self):
        repository = create_postgres_stores(self.async_database)
        cards = [await repository.cards.add_card("integration-test",f"test-{uuid4()}") for _ in range(2)]
        future = datetime(2100,1,1,tzinfo=timezone.utc)
        try:
            full = await repository.runs.create_due_run(future)
            self.fixture_runs.append(full.id)
            self.assertEqual({c.id for c in await repository.runs.cards_for_run(full.id)}, {c.id for c in cards})
            self.assertIsNone(await repository.runs.create_due_run(future+timedelta(hours=7)))
            await self.abandon_queued(repository,full)
            self.assertIsNone(await repository.runs.create_due_run(future+timedelta(hours=6,seconds=-1)))
            single = await repository.runs.start_direct_run(cards[0].id)
            self.fixture_runs.append(single.id)
            async with self.async_database.session() as session, session.begin():
                (await session.get(CollectionRunRecord,single.id)).started_at = future+timedelta(hours=5)
            await repository.runs.fail_run(single.lease,{"cardId":None,"message":"failed"})
            due = await repository.runs.create_due_run(future+timedelta(hours=6))
            self.assertIsNotNone(due)
            self.fixture_runs.append(due.id)
            await self.abandon_queued(repository,due)
            self.assertIsNone(await repository.runs.create_due_run(future+timedelta(hours=12,seconds=-1)))
            overdue = await repository.runs.create_due_run(future+timedelta(days=2))
            self.fixture_runs.append(overdue.id)
            self.assertIsNone(await repository.runs.create_due_run(future+timedelta(days=2)))
            await self.abandon_queued(repository,overdue)
            manual = await repository.runs.start_direct_run()
            self.fixture_runs.append(manual.id)
            async with self.async_database.session() as session, session.begin():
                (await session.get(CollectionRunRecord,manual.id)).started_at = future+timedelta(days=2,hours=1)
            await repository.runs.fail_run(manual.lease,{"cardId":None,"message":"failed"})
            self.assertIsNone(await repository.runs.create_due_run(future+timedelta(days=2,hours=7,seconds=-1)))
            final = await repository.runs.create_due_run(future+timedelta(days=2,hours=7))
            self.fixture_runs.append(final.id)
            await self.abandon_queued(repository,final)
        finally:
            for card in cards: await repository.cards.delete_card(card.id)

    async def test_retry_targets_only_failed_cards_and_links_source(self):
        repository = create_postgres_stores(self.async_database)
        cards = [await repository.cards.add_card("integration-test", f"test-{uuid4()}") for _ in range(2)]
        run = await repository.runs.start_direct_run()
        self.fixture_runs.append(run.id)
        await repository.runs.save_result(run.lease, cards[0], MarketplaceCard(ref=ProductRef(cards[0].ref.marketplace,cards[0].ref.external_id),
            title="Item",url="",price=100,availability=Availability.IN_STOCK))
        await repository.runs.record_card_error(run.lease,cards[1],{"cardId":cards[1].id,"message":"failed"})
        await repository.runs.finish_run(run.lease)
        retry = await repository.runs.create_retry_run(run.id)
        self.fixture_runs.append(retry.id)
        self.assertEqual([c.id for c in await repository.runs.cards_for_run(retry.id)],[cards[1].id])
        self.assertEqual(retry.retry_of_run_id,run.id)
        await self.abandon_queued(repository,retry)
        for card in cards: await repository.cards.delete_card(card.id)

    async def test_deal_excludes_current_price_from_daily_average(self):
        repository = create_postgres_stores(self.async_database)
        card = await repository.cards.add_card("integration-test", f"test-{uuid4()}")
        run_id = await self.fixture_run()
        now = datetime.now(timezone.utc)
        try:
            with self.database.session() as session, session.begin():
                session.get(MarketplaceCardRecord, card.id).created_at = now - timedelta(days=10)
                for index, price in enumerate((100, 120, 80)):
                    session.add(PriceHistoryRecord(card_id=card.id, collection_run_id=run_id,
                        price=Decimal(price), availability="in_stock",
                        observed_at=now - timedelta(days=3 - index), snapshot={}))
            deal = next(item for item in (await repository.catalog.get_catalog())["deals"] if item["card"]["id"] == card.id)
            self.assertEqual(deal["average_price"], Decimal("110"))
            self.assertEqual(deal["savings"], Decimal("30"))
            self.assertEqual(deal["baseline_days"], 2)
            self.assertEqual(deal["last_collection_run_id"], run_id)
            metrics = {c["id"]: (c["minimum_price"], c["average_price"]) for c in (await repository.catalog.get_catalog())["cards"]}
            self.assertEqual(metrics[card.id], (Decimal("80"), Decimal("110")))
            app = create_app(services=repository.api)


            async def check_deal_api():
                async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
                    response = await client.get("/api/catalog")
                    cards_response = await client.get("/api/catalog")
                self.assertEqual(response.status_code, 200)
                item = next(item for item in response.json()["deals"] if item["card"]["id"] == card.id)
                self.assertEqual(item["averagePrice"], "110")
                self.assertEqual(item["lastCollectionRunId"], run_id)
                card_response = next(entry for entry in cards_response.json()["cards"] if entry["id"] == card.id)
                self.assertEqual(card_response["minimumPrice"], "80.00")
                self.assertEqual(card_response["averagePrice"], "110")

            await check_deal_api()
            with self.database.session() as session, session.begin():
                session.add(PriceHistoryRecord(card_id=card.id, collection_run_id=run_id,
                    price=Decimal("150"), availability="in_stock", observed_at=now, snapshot={}))
            self.assertFalse(any(item["card"]["id"] == card.id for item in (await repository.catalog.get_catalog())["deals"]))
        finally:
            await repository.cards.delete_card(card.id)
            with self.database.session() as session, session.begin():
                session.execute(delete(CollectionRunRecord).where(CollectionRunRecord.id == run_id))

    async def test_deal_accepts_one_previous_day(self):
        repository = create_postgres_stores(self.async_database)
        card = await repository.cards.add_card("integration-test", f"test-{uuid4()}")
        now = datetime.now(timezone.utc)
        try:
            with self.database.session() as session, session.begin():
                session.get(MarketplaceCardRecord, card.id).created_at = now - timedelta(days=10)
                for days_ago, price in ((2, "100"), (1, "80")):
                    session.add(PriceHistoryRecord(
                        card_id=card.id, collection_run_id=None,
                        price=Decimal(price), availability="in_stock",
                        observed_at=now - timedelta(days=days_ago), snapshot={},
                    ))
            deal = next(item for item in (await repository.catalog.get_catalog())["deals"] if item["card"]["id"] == card.id)
            self.assertEqual(deal["average_price"], Decimal("100"))
            self.assertEqual(deal["savings"], Decimal("20"))
            self.assertEqual(deal["baseline_days"], 1)
        finally:
            await repository.cards.delete_card(card.id)

    async def test_recent_card_qualifies_without_waiting_seven_days(self):
        repository = create_postgres_stores(self.async_database)
        card = await repository.cards.add_card("integration-test", f"test-{uuid4()}")
        now = datetime.now(timezone.utc)
        try:
            async with self.async_database.session() as session, session.begin():
                session.add(PriceHistoryRecord(
                    card_id=card.id, collection_run_id=None,
                    price=Decimal("100"), availability="in_stock",
                    observed_at=now - timedelta(minutes=2), snapshot={},
                ))
            self.assertFalse(any(item["card"]["id"] == card.id for item in (await repository.catalog.get_catalog())["deals"]))

            async with self.async_database.session() as session, session.begin():
                session.add(PriceHistoryRecord(
                    card_id=card.id, collection_run_id=None,
                    price=Decimal("80"), availability="in_stock",
                    observed_at=now - timedelta(minutes=1), snapshot={},
                ))
            deal = next(item for item in (await repository.catalog.get_catalog())["deals"] if item["card"]["id"] == card.id)
            self.assertEqual(deal["average_price"], Decimal("100"))
            self.assertEqual(deal["savings"], Decimal("20"))
            self.assertEqual(deal["baseline_days"], 1)
        finally:
            await repository.cards.delete_card(card.id)

    async def test_excluded_card_is_collected_but_not_offered_as_deal(self):
        repository = create_postgres_stores(self.async_database)
        card = await repository.cards.add_card("integration-test", f"test-{uuid4()}")
        now = datetime.now(timezone.utc)
        try:
            with self.database.session() as session, session.begin():
                session.get(MarketplaceCardRecord, card.id).created_at = now - timedelta(days=10)
                for age, price in ((3, "100"), (2, "120"), (1, "80")):
                    session.add(PriceHistoryRecord(
                        card_id=card.id, collection_run_id=None, price=Decimal(price),
                        availability="in_stock", observed_at=now - timedelta(days=age), snapshot={},
                    ))
            self.assertTrue(any(item["card"]["id"] == card.id for item in (await repository.catalog.get_catalog())["deals"]))

            app = create_app(services=repository.api)

            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
                response = await client.patch(f"/api/cards/{card.id}", json={"dealsEnabled": False})
                self.assertEqual(response.status_code, 200)
                self.assertFalse(response.json()["dealsEnabled"])
                self.assertNotIn("isActive", response.json())
                self.assertNotIn("isArchived", response.json())
            self.assertIn(card.id, [item.id for item in await repository.cards.list_collection_cards()])
            run = await repository.runs.create_queued_run(card.id)
            self.assertEqual(tuple(c.id for c in await repository.runs.cards_for_run(run.id)), (card.id,))
            await self.abandon_queued(repository, run)
            full_run = await repository.runs.create_queued_run()
            self.assertIn(card.id, [c.id for c in await repository.runs.cards_for_run(full_run.id)])
            await self.abandon_queued(repository, full_run)
            self.assertFalse(any(item["card"]["id"] == card.id for item in (await repository.catalog.get_catalog())["deals"]))

            await repository.cards.update_card(card.id, deals_enabled=True)
            self.assertTrue(any(item["card"]["id"] == card.id for item in (await repository.catalog.get_catalog())["deals"]))
        finally:
            await repository.cards.delete_card(card.id)


if __name__ == "__main__":
    unittest.main()
