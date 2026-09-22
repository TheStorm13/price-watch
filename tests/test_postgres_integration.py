import os
import unittest
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4
from sqlalchemy import delete, func, select

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


if __name__ == "__main__":
    unittest.main()
