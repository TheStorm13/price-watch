import unittest
from datetime import datetime, timezone

from httpx import ASGITransport, AsyncClient

from price_analyzer.api import create_app
from price_analyzer.domain.models import CardOverview, CollectionRun, MarketplaceCard
from price_analyzer.infrastructure.postgres.repository import CardAlreadyExists


NOW = datetime(2026, 9, 21, 12, 0, tzinfo=timezone.utc)


def make_card(card_id=1, external_id="1604900984"):
    return MarketplaceCard(
        id=card_id,
        marketplace="ozon",
        external_id=external_id,
        title="Тестовый товар",
        url="https://www.ozon.ru/product/1604900984",
        is_active=True,
        created_at=NOW,
        updated_at=NOW,
    )


class FakeRepository:
    def __init__(self):
        self.card = make_card()
        self.duplicate = False

    def list_cards(self, include_inactive=False):
        return [CardOverview(self.card, 999, "in_stock", NOW)]

    def add_card(self, marketplace, external_id, title=None, url=None):
        if self.duplicate:
            raise CardAlreadyExists("Такая карточка уже добавлена")
        return make_card(2, external_id)

    def delete_card(self, card_id):
        if self.card is None or self.card.id != card_id:
            return False
        self.card = None
        return True

    def create_queued_run(self, card_id=None):
        return CollectionRun(
            id=7,
            status="queued",
            total_count=1,
            success_count=0,
            failure_count=0,
            requested_card_id=card_id,
            current_card_id=None,
            current_marketplace=None,
            current_external_id=None,
            challenge_type=None,
            challenge_message=None,
            started_at=NOW,
            finished_at=None,
        )


class ApiTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.repository = FakeRepository()
        app = create_app(repository=self.repository)
        app.state.repository = self.repository
        self.client = AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        )

    async def asyncTearDown(self):
        await self.client.aclose()

    async def test_cards_use_camel_case_contract(self):
        response = await self.client.get("/api/cards")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()[0]["externalId"], "1604900984")
        self.assertEqual(response.json()[0]["currentPrice"], 999.0)
        self.assertNotIn("external_id", response.json()[0])

    async def test_creates_queued_run(self):
        response = await self.client.post("/api/runs", json={"cardId": 1})

        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.json()["status"], "queued")
        self.assertEqual(response.json()["totalCount"], 1)

    async def test_duplicate_card_has_structured_field_error(self):
        self.repository.duplicate = True
        response = await self.client.post(
            "/api/cards",
            json={"marketplace": "ozon", "externalId": "1604900984"},
        )

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["error"]["code"], "card_already_exists")
        self.assertEqual(response.json()["error"]["field"], "externalId")

    async def test_deletes_card_and_returns_no_content(self):
        response = await self.client.delete("/api/cards/1")

        self.assertEqual(response.status_code, 204)
        self.assertEqual(response.content, b"")
        self.assertIsNone(self.repository.card)

    async def test_delete_missing_card_returns_404(self):
        response = await self.client.delete("/api/cards/999")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["error"]["code"], "card_not_found")


if __name__ == "__main__":
    unittest.main()
