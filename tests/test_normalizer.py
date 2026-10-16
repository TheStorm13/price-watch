import json
import unittest

from ozon_article_json.normalizer import ProductCardNormalizer
from marketplace_connector.connectors.ozon.mapper import OzonMapper
from marketplace_connector.domain.errors import MarketplaceSchemaChanged
from marketplace_connector.domain.models import Availability
from marketplace_connector.serialization.product_json import snapshot_to_dict


def widget(value):
    return json.dumps(value, ensure_ascii=False)


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
        card = ProductCardNormalizer.from_raw(self.payload)

        self.assertEqual(card.article, "1604900984")
        self.assertEqual(card.name, "Название товара")
        self.assertTrue(card.available)
        self.assertEqual(card.card_price, 577)
        self.assertEqual(card.rating, 4.8)
        self.assertEqual(card.reviews_count, 25443)
        self.assertEqual(card.seller.id, "2099474")
        self.assertEqual(card.seller.name, "Leaves")
        self.assertEqual(card.seller.rating, 4.8)
        self.assertEqual(card.characteristics, {"Тип": "Чай листовой"})
        self.assertEqual(card.description, "Полное описание")
        self.assertEqual(len(card.variants), 1)
        self.assertEqual(card.variants[0].article, "1604900984")
        self.assertIs(card.variants[0].available, True)
        self.assertTrue(card.variants[0].selected)

        serialized = card.to_dict()
        self.assertNotIn("card_price_text", serialized)
        self.assertNotIn("currency", serialized)
        self.assertNotIn("sku", serialized["variants"][0])
        self.assertNotIn("image_url", serialized["variants"][0])
        self.assertIsInstance(serialized["available"], bool)
        self.assertIsInstance(serialized["variants"][0]["available"], bool)

    def test_string_false_is_not_treated_as_available(self):
        price = json.loads(self.payload["widgetStates"]["webPrice-1"])
        price["isAvailable"] = "false"
        self.payload["widgetStates"]["webPrice-1"] = widget(price)

        card = ProductCardNormalizer.from_raw(self.payload)

        self.assertIs(card.available, False)

    def test_unavailable_snapshot_ignores_card_price(self):
        price = json.loads(self.payload["widgetStates"]["webPrice-1"])
        price["isAvailable"] = False
        self.payload["widgetStates"]["webPrice-1"] = widget(price)

        snapshot = OzonMapper.to_snapshot(self.payload)

        self.assertEqual(snapshot.availability, Availability.OUT_OF_STOCK)
        self.assertIsNone(snapshot.price)

    def test_accepts_prompt_before_json(self):
        raw = "Инструкция пользователю... " + json.dumps(self.payload)

        card = ProductCardNormalizer.from_raw(raw)

        self.assertEqual(card.article, "1604900984")

    def test_builds_common_connector_contract(self):
        snapshot = OzonMapper.to_snapshot(self.payload)
        serialized = snapshot_to_dict(snapshot)

        self.assertEqual(snapshot.ref.marketplace, "ozon")
        self.assertEqual(snapshot.ref.external_id, "1604900984")
        self.assertEqual(snapshot.availability, Availability.IN_STOCK)
        self.assertEqual(snapshot.price, 577)
        self.assertEqual(serialized["price"], 577)
        self.assertNotIn("prices", serialized)
        self.assertEqual(serialized["attributes"][0]["values"], ["Чай листовой"])

    def test_uses_unknown_when_availability_is_absent(self):
        price = json.loads(self.payload["widgetStates"]["webPrice-1"])
        price.pop("isAvailable")
        self.payload["widgetStates"]["webPrice-1"] = widget(price)
        product = json.loads(self.payload["seo"]["script"][0]["innerHTML"])
        product["offers"].pop("availability")
        self.payload["seo"]["script"][0]["innerHTML"] = json.dumps(product)

        snapshot = OzonMapper.to_snapshot(self.payload)

        self.assertEqual(snapshot.availability, Availability.UNKNOWN)

    def test_does_not_fallback_to_regular_price(self):
        price = json.loads(self.payload["widgetStates"]["webPrice-1"])
        price.pop("cardPrice")
        price["price"] = "650 ₽"
        self.payload["widgetStates"]["webPrice-1"] = widget(price)

        snapshot = OzonMapper.to_snapshot(self.payload)

        self.assertIsNone(snapshot.price)

    def test_rejects_response_without_product_identity(self):
        self.payload["pageInfo"] = {}
        self.payload["seo"]["script"] = []
        self.payload["widgetStates"].pop("webProductHeading-1")
        self.payload["widgetStates"].pop("webStickyProducts-1")

        with self.assertRaises(MarketplaceSchemaChanged):
            OzonMapper.to_snapshot(self.payload)


if __name__ == "__main__":
    unittest.main()
