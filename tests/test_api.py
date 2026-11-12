from marketplace_connector.domain.models import ProductRef
import unittest
from datetime import datetime, timezone

from httpx import ASGITransport, AsyncClient

from price_watch.api import create_app
from price_watch.api.schemas import CardResponse
from price_watch.domain.purchase import PurchaseSettings
from price_watch.domain.models import TrackedCardOverview, CollectionRun, TrackedCard
from price_watch.domain.errors import CardAlreadyExists, NoCards
from price_watch.application.services import ApiServices
from price_watch.application.catalog_service import CatalogService
from price_watch.application.catalog_models import CatalogInputs, CatalogCardInput, CardMetrics, GroupMetadata
from dataclasses import replace
from decimal import Decimal


NOW = datetime(2026, 9, 21, 12, 0, tzinfo=timezone.utc)


def make_card(card_id=1, external_id="1604900984"):
    return TrackedCard(
        id=card_id,
        ref=ProductRef("ozon", external_id),
        title="Тестовый товар",
        url="https://www.ozon.ru/product/1604900984",
        deals_enabled=True,
        created_at=NOW,
        updated_at=NOW,
    )


class FakeRepository:
    def __init__(self):
        self.card = make_card()
        self.duplicate = False
        self.no_cards = False
        self.groups = {}
        self.purchase = PurchaseSettings(instance_id="test-db")

    async def get_settings(self):
        return self.purchase

    async def update_settings(self, changes):
        self.purchase = replace(self.purchase, **changes)
        return self.purchase

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

    async def read_catalog(self):
        local = replace(self.card, group_id=next((key for key, group in self.groups.items()
                                                if self.card.id in group['card_ids']), None))
        return CatalogInputs(
            (CatalogCardInput(TrackedCardOverview(local, Decimal('999'), 'in_stock', NOW),
                              CardMetrics(Decimal('800'), Decimal('1100'), 1), None),),
            tuple(GroupMetadata(key, group['name'], tuple(group['tags']))
                  for key, group in self.groups.items()),
        )

    async def export_cards(self):
        return {"version": 3, "cards": [{
            "marketplace": "ozon", "external_id": "1604900984",
            "title": "Тестовый товар", "url": None, "tags": ["кухня"], "deals_enabled": True,
            "created_at": NOW, "primary_external_id": "1604900984", "variants": [{"external_id":"1604900984", "url":None, "history": [{
                "price": "999.00", "availability": "in_stock", "observed_at": NOW,
            }]}],
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
        article = external_id.split(':')[0] if marketplace in ('aliexpress', 'wildberries') else external_id
        self.card = TrackedCard(**{**card.__dict__, "ref": ProductRef(marketplace, article), "tags": tuple(tags or [])})
        return self.card

    async def get_card(self, card_id):
        return TrackedCardOverview(self.card, None, None, None) if self.card and self.card.id == card_id else None

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

    async def get_run(self, run_id, include_errors=True):
        if run_id != 7:
            return None
        run = await self.create_queued_run(1)
        return CollectionRun(**{**run.__dict__, "errors": ({
            "cardId": 1, "marketplace": "ozon", "externalId": "1604900984",
            "at": NOW.isoformat(), "type": "RuntimeError",
            "message": "failed", "traceback": "full traceback",
        },)})


class ApiTests(unittest.IsolatedAsyncioTestCase):
    async def test_startup_closes_database_when_service_configuration_fails(self):
        from unittest.mock import AsyncMock, patch
        database = AsyncMock()
        with (patch('price_watch.api.app.Database'), patch('price_watch.api.app.MigrationRunner'),
              patch('price_watch.api.app.AsyncDatabase') as factory,
              patch('price_watch.api.app.create_postgres_stores', side_effect=ValueError('invalid configuration'))):
            factory.return_value.open = AsyncMock(return_value=database)
            app = create_app(database_url='synthetic')
            with self.assertRaisesRegex(ValueError, 'invalid configuration'):
                async with app.router.lifespan_context(app):
                    self.fail('Startup should fail')
        database.close.assert_awaited_once_with()

    async def asyncSetUp(self):
        self.repository = FakeRepository()
        app = create_app(services=ApiServices(self.repository, self.repository, self.repository, self.repository, self.repository, self.repository, CatalogService(self.repository), self.repository))
        self.client = AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        )

    async def asyncTearDown(self):
        await self.client.aclose()

    async def test_thumbnail_auth_source_changes_and_missing_images(self):
        from unittest.mock import AsyncMock
        from price_watch.infrastructure.thumbnails import ThumbnailError
        thumbnails = AsyncMock()
        thumbnails.get.return_value = b'png-content'
        services = ApiServices(self.repository, self.repository, self.repository, self.repository,
                               self.repository, self.repository, CatalogService(self.repository), self.repository)
        app = create_app(services=services, api_token='secret', thumbnails=thumbnails)
        async with AsyncClient(transport=ASGITransport(app=app), base_url='http://test') as client:
            self.assertEqual((await client.get('/api/cards/1/thumbnail?profile=list&scale=1')).status_code, 401)
            headers = {'X-Price-Watch-Token': 'secret'}
            for query in ('', '?profile=no&scale=1', '?profile=list&scale=0', '?profile=list&scale=9', '?profile=list&scale=no'):
                self.assertEqual((await client.get('/api/cards/1/thumbnail' + query, headers=headers)).status_code, 422)

            self.assertEqual((await client.get('/api/cards/1/thumbnail?profile=list&scale=1', headers=headers)).status_code, 404)
            self.assertEqual((await client.get('/api/cards/999/thumbnail?profile=list&scale=1', headers=headers)).status_code, 404)
            thumbnails.get.assert_not_called()
            for source in ['https://cdn.test/first', 'https://cdn.test/new-primary']:
                self.repository.card = replace(self.repository.card, image_url=source)
                response = await client.get('/api/cards/1/thumbnail?profile=list&scale=1', headers=headers)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.headers['content-type'], 'image/png')
                self.assertEqual(response.headers['cache-control'], 'no-store')
                self.assertEqual(response.content, b'png-content')
                thumbnails.get.assert_awaited_with(source, (51, 68))
                self.assertEqual(self.repository.card.image_url, source)
            for profile, scale, expected in [('tile', 1, (276, 368)), ('detail', 8, (3072, 4096))]:
                response = await client.get(f'/api/cards/1/thumbnail?profile={profile}&scale={scale}', headers=headers)
                self.assertEqual(response.status_code, 200)
                thumbnails.get.assert_awaited_with(source, expected)
            thumbnails.get.side_effect = ThumbnailError('unavailable')
            response = await client.get('/api/cards/1/thumbnail?profile=list&scale=1', headers=headers)
            self.assertEqual(response.status_code, 502)
            self.assertEqual(response.json()['error']['code'], 'thumbnail_unavailable')

    async def test_replaced_list_routes_are_removed(self):
        schema = self.client._transport.app.openapi()
        self.assertNotIn('get', schema['paths']['/api/cards'])
        self.assertNotIn('get', schema['paths']['/api/groups'])
        self.assertNotIn('/api/cards/deals', schema['paths'])
        for path in ['/api/cards', '/api/groups', '/api/cards/deals']:
            self.assertNotEqual((await self.client.get(path)).status_code, 200)

    async def test_cards_use_camel_case_contract(self):
        response = await self.client.get("/api/catalog")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["cards"][0]["externalId"], "1604900984")
        self.assertEqual(response.json()["cards"][0]["currentPrice"], "999.00")
        self.assertEqual(response.json()["cards"][0]["minimumPrice"], "800.00")
        self.assertEqual(response.json()["cards"][0]["averagePrice"], "1100")
        self.assertNotIn("external_id", response.json()["cards"][0])

    async def test_group_contract_and_lifecycle(self):
        created = await self.client.post("/api/groups", json={"name": "Бутылка", "cardIds": [1], "tags": ["кухня"]})
        self.assertEqual(created.status_code, 201)
        self.assertEqual(created.json()["representativeCardId"], 1)
        self.assertEqual(created.json()["representativeCard"]["averagePrice"], "1100")
        self.assertEqual(created.json()["representativeCard"]["currentPrice"], created.json()["currentPrice"])
        self.assertTrue(created.json()["isDeal"])
        self.assertEqual(created.json()["savings"], "101")
        self.assertEqual(created.json()["minimumPrice"], "800.00")
        self.assertEqual(created.json()["cardIds"], [1])
        self.assertEqual(created.json()["tags"], ["кухня"])
        self.assertEqual(len((await self.client.get("/api/catalog")).json()["groups"]), 1)
        updated = await self.client.put("/api/groups/1", json={"name": "Термос", "cardIds": [], "tags": ["подарок"]})
        self.assertEqual(updated.json()["name"], "Термос")
        self.assertEqual(updated.json()["tags"], ["подарок"])
        self.assertIsNone(updated.json()["currentPrice"])
        self.assertIsNone(updated.json()["representativeCardId"])
        self.assertIsNone(updated.json()["representativeCard"])
        self.assertFalse(updated.json()["isDeal"])
        self.assertEqual(updated.json()["baselineDays"], 0)
        self.assertEqual((await self.client.delete("/api/groups/1")).status_code, 204)
        self.assertEqual((await self.client.get("/api/catalog")).json()["groups"], [])

    async def test_desktop_api_requires_its_session_token(self):
        app = create_app(services=ApiServices(self.repository, self.repository, self.repository, self.repository, self.repository, self.repository, CatalogService(self.repository), self.repository), api_token="session-secret")
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
            self.assertEqual((await client.get("/api/health")).status_code, 401)
            self.assertEqual(
                (await client.get("/api/catalog", headers={"X-Price-Watch-Token": "wrong"})).status_code,
                401,
            )
            response = await client.get("/api/catalog", headers={"X-Price-Watch-Token": "session-secret"})
            self.assertEqual(response.status_code, 200)
            preflight = await client.options("/api/cards", headers={
                "Origin": "http://tauri.localhost",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "x-price-watch-token",
            })
            self.assertEqual(preflight.status_code, 200)
            web_preflight = await client.options("/api/cards", headers={
                "Origin": "http://127.0.0.1:5173",
                "Access-Control-Request-Method": "GET",
            })
            self.assertEqual(web_preflight.status_code, 400)

    async def test_export_and_import_use_card_history_contract(self):
        exported = await self.client.get("/api/cards/export")
        self.assertEqual(exported.status_code, 200)
        document = exported.json()
        card = document["cards"][0]
        self.assertEqual(set(card), {"marketplace", "externalId", "title", "url", "imageUrl", "tags",
                                     "dealsEnabled", "createdAt", "primaryExternalId", "variants"})
        self.assertEqual(card["tags"], ["кухня"])
        self.assertEqual(document["groups"], [{
            "name": "Бутылки", "tags": ["подарок"],
            "cards": [{"marketplace": "ozon", "externalId": "1604900984"}],
        }])
        card["dealsEnabled"] = False
        del card["imageUrl"]
        preview = await self.client.post("/api/cards/import/preview", json=document)
        self.assertEqual(preview.status_code, 200)
        self.assertEqual(preview.json()["cardsMerged"], 1)
        self.assertFalse(self.repository.last_imported_cards[0]["deals_enabled"])
        self.assertEqual(self.repository.last_imported_cards[0]["tags"], ["кухня"])
        self.assertEqual(self.repository.last_imported_groups, [{
            "name": "Бутылки", "tags": ["подарок"],
            "cards": [{"marketplace": "ozon", "external_id": "1604900984"}],
        }])
        imported = await self.client.post("/api/cards/import", json=document)
        self.assertEqual(imported.status_code, 200)
        self.assertEqual(imported.json()["observationsAdded"], 1)
        self.assertEqual(imported.json()["groupsAdded"], 1)

    async def test_import_rejects_old_deal_fields_and_version(self):
        self.assertEqual((await self.client.patch("/api/cards/1", json={"isActive": False})).status_code, 422)
        document = (await self.client.get("/api/cards/export")).json()
        document["version"] = 1
        self.assertEqual((await self.client.post("/api/cards/import/preview", json=document)).status_code, 422)
        document["version"] = 3
        document["cards"][0]["isActive"] = document["cards"][0].pop("dealsEnabled")
        self.assertEqual((await self.client.post("/api/cards/import/preview", json=document)).status_code, 422)
        document["cards"][0]["dealsEnabled"] = True
        document["cards"][0]["isArchived"] = True
        self.assertEqual((await self.client.post("/api/cards/import/preview", json=document)).status_code, 422)

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

    async def test_yandex_market_cards_validate_exact_sku_url(self):
        for marketplace in ("yandex-market",):
            with self.subTest(marketplace=marketplace):
                response = await self.client.post("/api/cards", json={
                    "marketplace": marketplace, "externalId": "123456",
                    "title": "Товар", "url": "https://market.yandex.ru/card/tovar/123456",
                })
                self.assertEqual(response.status_code, 201)
                self.assertEqual(response.json()["marketplace"], marketplace)
                self.assertEqual(self.repository.last_added_marketplace, marketplace)

    async def test_aliexpress_accepts_product_id_and_exact_sku(self):
        product = await self.client.post("/api/cards", json={"marketplace":"aliexpress", "externalId":"123456"})
        self.assertEqual(product.status_code, 201)
        response = await self.client.post("/api/cards", json={"marketplace":"aliexpress", "externalId":"123456:98765432101234567"})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["externalId"], "123456")

    async def test_import_rejects_invalid_history_before_writing(self):
        document = (await self.client.get("/api/cards/export")).json()
        document["cards"][0]["variants"][0]["history"][0]["price"] = "-10"
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
