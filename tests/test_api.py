import unittest
from datetime import datetime, timezone

from httpx import ASGITransport, AsyncClient

from price_analyzer.api import create_app
from price_analyzer.domain.models import CardOverview, CollectionRun, MarketplaceCard
from price_analyzer.infrastructure.postgres.repository import CardAlreadyExists, NoCards


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
        self.no_cards = False
        self.groups = {}

    async def list_groups(self):
        return [{"id": group_id, "name": group["name"], "card_ids": group["card_ids"],
                 "tags": group["tags"],
                 "current_price": 999 if group["card_ids"] else None,
                 "minimum_price": 800 if group["card_ids"] else None}
                for group_id, group in self.groups.items()]

    async def create_group(self, name, card_ids, tags=None):
        self.groups[1] = {"name": name, "card_ids": card_ids, "tags": tags or []}
        return 1

    async def update_group(self, group_id, name, card_ids, tags=None):
        if group_id not in self.groups:
            return False
        self.groups[group_id] = {"name": name, "card_ids": card_ids, "tags": tags or []}
        return True

    async def delete_group(self, group_id):
        return self.groups.pop(group_id, None) is not None

    async def list_cards(self, include_inactive=False):
        return [CardOverview(self.card, 999, "in_stock", NOW)]

    async def list_card_price_metrics(self):
        return {1: (800, 1100)}

    async def export_cards(self):
        return {"version": 1, "cards": [{
            "marketplace": "ozon", "external_id": "1604900984",
            "title": "Тестовый товар", "url": None, "tags": ["кухня"], "is_active": True,
            "created_at": NOW, "history": [{
                "price": "999.00", "availability": "in_stock", "observed_at": NOW,
            }],
        }], "groups": [{
            "name": "Бутылки", "tags": ["подарок"],
            "cards": [{"marketplace": "ozon", "external_id": "1604900984"}],
        }]}

    async def import_cards(self, cards, *, groups=None, preview=False):
        self.last_imported_cards = cards
        self.last_imported_groups = groups
        return {"cards_added": 0, "cards_merged": len(cards),
                "observations_added": 0 if preview else 1,
                "observations_removed": 0, "observations_skipped": 1,
                "groups_added": len(groups or [])}

    async def add_card(self, marketplace, external_id, title=None, url=None, tags=None):
        if self.duplicate:
            raise CardAlreadyExists("Такая карточка уже добавлена")
        self.last_added_marketplace = marketplace
        card = make_card(2, external_id)
        return MarketplaceCard(**{**card.__dict__, "marketplace": marketplace, "tags": tuple(tags or [])})

    async def delete_card(self, card_id):
        if self.card is None or self.card.id != card_id:
            return False
        self.card = None
        return True

    async def create_queued_run(self, card_id=None):
        if self.no_cards:
            raise NoCards("Нет карточек для сбора")
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

    async def get_run(self, run_id):
        if run_id != 7:
            return None
        run = await self.create_queued_run(1)
        return CollectionRun(**{**run.__dict__, "errors": ({
            "cardId": 1, "marketplace": "ozon", "externalId": "1604900984",
            "at": NOW.isoformat(), "type": "RuntimeError",
            "message": "failed", "traceback": "full traceback",
        },)})


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
        self.assertEqual(response.json()[0]["minimumPrice"], 800.0)
        self.assertEqual(response.json()[0]["averagePrice"], 1100.0)
        self.assertNotIn("external_id", response.json()[0])

    async def test_group_contract_and_lifecycle(self):
        created = await self.client.post("/api/groups", json={"name": "Бутылка", "cardIds": [1], "tags": ["кухня"]})
        self.assertEqual(created.status_code, 201)
        self.assertEqual(created.json()["minimumPrice"], 800)
        self.assertEqual(created.json()["cardIds"], [1])
        self.assertEqual(created.json()["tags"], ["кухня"])
        self.assertEqual(len((await self.client.get("/api/groups")).json()), 1)
        updated = await self.client.put("/api/groups/1", json={"name": "Термос", "cardIds": [], "tags": ["подарок"]})
        self.assertEqual(updated.json()["name"], "Термос")
        self.assertEqual(updated.json()["tags"], ["подарок"])
        self.assertIsNone(updated.json()["currentPrice"])
        self.assertEqual((await self.client.delete("/api/groups/1")).status_code, 204)
        self.assertEqual((await self.client.get("/api/groups")).json(), [])

    async def test_desktop_api_requires_its_session_token(self):
        app = create_app(repository=self.repository, api_token="session-secret")
        app.state.repository = self.repository
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
            self.assertEqual((await client.get("/api/health")).status_code, 401)
            self.assertEqual(
                (await client.get("/api/cards", headers={"X-Price-Watch-Token": "wrong"})).status_code,
                401,
            )
            response = await client.get("/api/cards", headers={"X-Price-Watch-Token": "session-secret"})
            self.assertEqual(response.status_code, 200)
            preflight = await client.options("/api/cards", headers={
                "Origin": "http://tauri.localhost",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "x-price-watch-token",
            })
            self.assertEqual(preflight.status_code, 200)

    async def test_export_and_import_use_card_history_contract(self):
        exported = await self.client.get("/api/cards/export")
        self.assertEqual(exported.status_code, 200)
        document = exported.json()
        card = document["cards"][0]
        self.assertEqual(set(card), {"marketplace", "externalId", "title", "url", "imageUrl", "tags",
                                     "isActive", "createdAt", "history"})
        self.assertEqual(card["tags"], ["кухня"])
        self.assertEqual(document["groups"], [{
            "name": "Бутылки", "tags": ["подарок"],
            "cards": [{"marketplace": "ozon", "externalId": "1604900984"}],
        }])
        card["isArchived"] = True  # Старый архив превращается в приостановку.
        del card["imageUrl"]
        preview = await self.client.post("/api/cards/import/preview", json=document)
        self.assertEqual(preview.status_code, 200)
        self.assertEqual(preview.json()["cardsMerged"], 1)
        self.assertFalse(self.repository.last_imported_cards[0]["is_active"])
        self.assertEqual(self.repository.last_imported_cards[0]["tags"], ["кухня"])
        self.assertEqual(self.repository.last_imported_groups, [{
            "name": "Бутылки", "tags": ["подарок"],
            "cards": [{"marketplace": "ozon", "external_id": "1604900984"}],
        }])
        imported = await self.client.post("/api/cards/import", json=document)
        self.assertEqual(imported.status_code, 200)
        self.assertEqual(imported.json()["observationsAdded"], 1)
        self.assertEqual(imported.json()["groupsAdded"], 1)

    async def test_card_tags_are_limited_to_two(self):
        valid = await self.client.post("/api/cards", json={
            "marketplace": "ozon", "externalId": "123", "tags": [" кухня ", "Подарок"],
        })
        self.assertEqual(valid.status_code, 201)
        self.assertEqual(valid.json()["tags"], ["кухня", "Подарок"])
        invalid = await self.client.post("/api/cards", json={
            "marketplace": "ozon", "externalId": "124", "tags": ["a", "b", "c"],
        })
        self.assertEqual(invalid.status_code, 422)
        duplicate = await self.client.post("/api/cards", json={
            "marketplace": "ozon", "externalId": "125", "tags": ["Кухня", "кухня"],
        })
        self.assertEqual(duplicate.status_code, 422)

    async def test_cards_can_be_added_for_marketplaces_without_connectors(self):
        for marketplace in ("wildberries", "aliexpress"):
            with self.subTest(marketplace=marketplace):
                response = await self.client.post("/api/cards", json={
                    "marketplace": marketplace, "externalId": "123456",
                    "title": "Товар", "url": "https://example.com/product/123456",
                })
                self.assertEqual(response.status_code, 201)
                self.assertEqual(response.json()["marketplace"], marketplace)
                self.assertEqual(self.repository.last_added_marketplace, marketplace)

    async def test_import_rejects_invalid_history_before_writing(self):
        document = (await self.client.get("/api/cards/export")).json()
        document["cards"][0]["history"][0]["price"] = "-10"
        response = await self.client.post("/api/cards/import", json=document)
        self.assertEqual(response.status_code, 422)

    async def test_creates_queued_run(self):
        response = await self.client.post("/api/runs", json={"cardId": 1})

        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.json()["status"], "queued")
        self.assertEqual(response.json()["totalCount"], 1)

    async def test_empty_collection_returns_conflict(self):
        self.repository.no_cards = True
        response = await self.client.post("/api/runs", json={})
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["error"]["code"], "no_cards")

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

    async def test_tauri_delete_preflight_is_allowed(self):
        response = await self.client.options(
            "/api/cards/1",
            headers={
                "Origin": "http://tauri.localhost",
                "Access-Control-Request-Method": "DELETE",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("DELETE", response.headers["access-control-allow-methods"])

    async def test_run_detail_can_omit_tracebacks_during_polling(self):
        full = await self.client.get("/api/runs/7")
        summary = await self.client.get("/api/runs/7?includeErrors=false")
        self.assertEqual(full.json()["errors"][0]["traceback"], "full traceback")
        self.assertIsNone(summary.json()["errors"])


if __name__ == "__main__":
    unittest.main()
