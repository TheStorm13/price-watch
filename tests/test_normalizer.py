import json
import unittest

from decimal import Decimal
from marketplace_connector.connectors.ozon.parser import OzonProductParser
from marketplace_connector.connectors.ozon.mapper import OzonMapper
from marketplace_connector.domain.errors import MarketplaceSchemaChanged, ProductNotFound
from marketplace_connector.domain.models import Availability
from marketplace_connector.serialization.product_json import card_to_dict


def widget(value):
    return json.dumps(value, ensure_ascii=False)


def map_product(raw, **kwargs):
    return OzonMapper.to_card(OzonProductParser.parse(raw, **kwargs))


class NormalizerTests(unittest.TestCase):
    def setUp(self):
        self.payload = {
            "pageInfo": {"analyticsInfo": {"sku": 1604900984}},
            "seo": {
                "link": [{"rel": "canonical", "href": "https://ozon.test/product"}],
                "script": [{
                    "type": "application/ld+json",
                    "innerHTML": json.dumps({
                        "@type": "Product",
                        "description": "Полное описание",
                        "offers": {
                            "availability": "http://schema.org/InStock",
                            "priceCurrency": "RUB",
                        },
                    }),
                }],
            },
            "widgetStates": {
                "webProductHeading-1": widget({"title": "Название товара"}),
                "webPrice-1": widget({
                    "isAvailable": True,
                    "cardPrice": "577 ₽",
                    "price": "650 ₽",
                }),
                "webStickyProducts-1": widget({
                    "sku": "1604900984",
                    "seller": {
                        "name": "Leaves",
                        "link": "https://www.ozon.ru/seller/leaves-2099474/",
                    },
                }),
                "webCurrentSeller-1": widget({
                    "rating": {"title": {"text": "4.8"}},
                }),
                "webReviewProductScore-1": widget({
                    "totalScore": 4.8,
                    "reviewsCount": 25443,
                }),
                "webShortCharacteristics-1": widget({
                    "characteristics": [{
                        "title": {"textRs": [{"content": "Тип"}]},
                        "values": [{"text": "Чай листовой"}],
                    }],
                }),
                "webAspects-1": widget({
                    "groups": [{
                        "variants": [{
                            "sku": "1604900984",
                            "link": "/product/item-1604900984/",
                            "availability": "inStock",
                            "price": 577,
                            "data": {
                                "title": "Название товара",
                                "searchableText": "Габа",
                                "originalPrice": "1 611 ₽",
                                "coverImage": "https://img.test/1.jpg",
                            },
                        }],
                    }],
                }),
            },
        }

    def test_builds_requested_entity(self):
        card = map_product(self.payload)

        self.assertEqual(card.ref.external_id, "1604900984")
        self.assertEqual(card.title, "Название товара")
        self.assertEqual(card.availability, Availability.IN_STOCK)
        self.assertEqual(card.price, 577)
        self.assertEqual(card.rating.value, Decimal("4.8"))
        self.assertEqual(card.rating.reviews_count, 25443)
        self.assertEqual(card.seller.external_id, "2099474")
        self.assertEqual(card.seller.name, "Leaves")
        self.assertEqual(card.seller.rating.value, Decimal("4.8"))
        self.assertEqual({a.name: a.values[0] for a in card.attributes}, {"Тип": "Чай листовой"})
        self.assertEqual(card.description, "Полное описание")
        self.assertEqual(len(card.variants), 1)
        self.assertEqual(card.variants[0].ref.external_id, "1604900984")
        self.assertIs(card.variants[0].availability, Availability.IN_STOCK)
        self.assertTrue(card.variants[0].selected)

        serialized = card_to_dict(card)
        self.assertNotIn("card_price_text", serialized)
        self.assertNotIn("currency", serialized)
        self.assertNotIn("sku", serialized["variants"][0])
        self.assertEqual(serialized["variants"][0]["image_url"], "https://img.test/1.jpg")
        self.assertEqual(serialized["availability"], "in_stock")
        self.assertEqual(serialized["variants"][0]["availability"], "in_stock")

    def test_string_false_is_not_treated_as_available(self):
        price = json.loads(self.payload["widgetStates"]["webPrice-1"])
        price["isAvailable"] = "false"
        self.payload["widgetStates"]["webPrice-1"] = widget(price)

        card = map_product(self.payload)

        self.assertEqual(card.availability, Availability.OUT_OF_STOCK)

    def test_unavailable_snapshot_ignores_card_price(self):
        price = json.loads(self.payload["widgetStates"]["webPrice-1"])
        price["isAvailable"] = False
        self.payload["widgetStates"]["webPrice-1"] = widget(price)

        snapshot = map_product(self.payload)

        self.assertEqual(snapshot.availability, Availability.OUT_OF_STOCK)
        self.assertIsNone(snapshot.price)

    def test_accepts_prompt_before_json(self):
        raw = "Инструкция пользователю... " + json.dumps(self.payload)

        card = map_product(raw)

        self.assertEqual(card.ref.external_id, "1604900984")

    def test_builds_common_connector_contract(self):
        snapshot = map_product(self.payload)
        serialized = card_to_dict(snapshot)

        self.assertEqual(snapshot.ref.marketplace, "ozon")
        self.assertEqual(snapshot.ref.external_id, "1604900984")
        self.assertEqual(snapshot.availability, Availability.IN_STOCK)
        self.assertEqual(snapshot.price, 577)
        self.assertEqual(serialized["price"], "577.00")
        self.assertNotIn("prices", serialized)
        self.assertEqual(serialized["attributes"][0]["values"], ["Чай листовой"])
        self.assertEqual(snapshot.image_url, "https://img.test/1.jpg")
        self.assertEqual(serialized["image_url"], snapshot.image_url)

    def test_prefers_first_gallery_photo_to_structured_data_and_variant(self):
        product = json.loads(self.payload["seo"]["script"][0]["innerHTML"])
        product["image"] = ["https://img.test/structured.jpg"]
        self.payload["seo"]["script"][0]["innerHTML"] = json.dumps(product)
        self.payload["widgetStates"]["webGallery-1"] = widget({
            "images": [{"src": "https://img.test/first.jpg"},
                       {"src": "https://img.test/second.jpg"}],
        })

        self.assertEqual(map_product(self.payload).image_url,
                         "https://img.test/first.jpg")

    def test_uses_unknown_when_availability_is_absent(self):
        price = json.loads(self.payload["widgetStates"]["webPrice-1"])
        price.pop("isAvailable")
        self.payload["widgetStates"]["webPrice-1"] = widget(price)
        product = json.loads(self.payload["seo"]["script"][0]["innerHTML"])
        product["offers"].pop("availability")
        self.payload["seo"]["script"][0]["innerHTML"] = json.dumps(product)

        snapshot = map_product(self.payload)

        self.assertEqual(snapshot.availability, Availability.UNKNOWN)

    def test_does_not_fallback_to_regular_price(self):
        price = json.loads(self.payload["widgetStates"]["webPrice-1"])
        price.pop("cardPrice")
        price["price"] = "650 ₽"
        self.payload["widgetStates"]["webPrice-1"] = widget(price)

        snapshot = map_product(self.payload)

        self.assertIsNone(snapshot.price)

    def test_rejects_response_without_product_identity(self):
        self.payload["pageInfo"] = {}
        self.payload["seo"]["script"] = []
        self.payload["widgetStates"].pop("webProductHeading-1")
        self.payload["widgetStates"].pop("webStickyProducts-1")

        with self.assertRaises(MarketplaceSchemaChanged):
            map_product(self.payload)

    def test_search_redirect_for_requested_product_means_not_found(self):
        self.payload["pageInfo"] = {
            "pageType": "search",
            "url": "/search/?text=Чай&product_id=1604900984",
        }
        self.payload["widgetStates"] = {"searchResults-1": widget({"items": []})}
        self.payload["seo"]["script"] = []

        with self.assertRaises(ProductNotFound):
            map_product(self.payload, expected_external_id="1604900984")

    def test_ambiguous_search_response_remains_an_error(self):
        self.payload["pageInfo"] = {
            "pageType": "search", "url": "/search/?product_id=999"
        }
        self.payload["widgetStates"] = {"searchResults-1": widget({"items": []})}
        self.payload["seo"]["script"] = []

        for page_url, widgets in (
            ("/search/?product_id=999", self.payload["widgetStates"]),
            ("/search/?text=Чай", self.payload["widgetStates"]),
            ("/search/?product_id=1604900984", {"webPrice-1": "{}"}),
        ):
            with self.subTest(page_url=page_url, widgets=widgets):
                self.payload["pageInfo"]["url"] = page_url
                self.payload["widgetStates"] = widgets
                with self.assertRaises(MarketplaceSchemaChanged):
                    map_product(self.payload, expected_external_id="1604900984")


if __name__ == "__main__":
    unittest.main()
