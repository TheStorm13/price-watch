import json
import asyncio
import unittest
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from marketplace_connector.application.product_service import ConnectorRegistry, ProductService
from marketplace_connector.domain.errors import UnknownMarketplace
from marketplace_connector.domain.models import (
    Attribute,
    Availability,
    ProductRef,
    ProductSnapshot,
)
from marketplace_connector.serialization.product_json import snapshot_to_json


class FakeConnector:
    marketplace = "demo"

    @asynccontextmanager
    async def collection_session(self):
        yield

    async def get_product(self, external_id):
        return ProductSnapshot(
            ref=ProductRef(self.marketplace, external_id),
            title="Тестовый товар",
            url="https://example.test/product/1",
            availability=Availability.IN_STOCK,
            price=199.9,
            attributes=(Attribute("Цвет", ("зелёный",)),),
            collected_at=datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc),
        )


class ConnectorContractTests(unittest.TestCase):
    def test_service_returns_marketplace_independent_snapshot(self):
        service = ProductService(ConnectorRegistry([FakeConnector()]))

        snapshot = asyncio.run(service.get_product("DEMO", "product-1"))

        self.assertEqual(snapshot.ref, ProductRef("demo", "product-1"))
        self.assertEqual(snapshot.price, 199.9)

    def test_serializes_stable_json_contract(self):
        snapshot = asyncio.run(FakeConnector().get_product("product-1"))

        payload = json.loads(snapshot_to_json(snapshot))

        self.assertEqual(payload["schema_version"], "1.0")
        self.assertEqual(
            payload["ref"],
            {"marketplace": "demo", "external_id": "product-1"},
        )
        self.assertEqual(payload["availability"], "in_stock")
        self.assertEqual(payload["price"], 199.9)
        self.assertNotIn("prices", payload)
        self.assertEqual(payload["attributes"][0]["values"], ["зелёный"])
        self.assertEqual(payload["collected_at"], "2026-01-02T03:04:05+00:00")

    def test_rejects_duplicate_connector(self):
        registry = ConnectorRegistry([FakeConnector()])

        with self.assertRaises(ValueError):
            registry.register(FakeConnector())

    def test_rejects_synchronous_connector(self):
        class SyncConnector(FakeConnector):
            def get_product(self, external_id):
                return None

        with self.assertRaisesRegex(TypeError, "async get_product"):
            ConnectorRegistry([SyncConnector()])

    def test_reports_unknown_marketplace(self):
        with self.assertRaises(UnknownMarketplace):
            ConnectorRegistry().get("unknown")

    def test_rejects_negative_price(self):
        with self.assertRaises(ValueError):
            ProductSnapshot(
                ref=ProductRef("demo", "1"),
                title="Товар",
                url="https://example.test/1",
                availability=Availability.IN_STOCK,
                price=-1,
            )

    def test_unavailable_product_has_no_current_price(self):
        snapshot = ProductSnapshot(
            ref=ProductRef("demo", "1"), title="Товар",
            url="https://example.test/1", availability=Availability.OUT_OF_STOCK,
            price=199.9,
        )

        self.assertIsNone(snapshot.price)
        self.assertIsNone(json.loads(snapshot_to_json(snapshot))["price"])


if __name__ == "__main__":
    unittest.main()
