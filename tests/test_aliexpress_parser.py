import json
import unittest
from copy import deepcopy
from decimal import Decimal
from pathlib import Path
from marketplace_connector.connectors.aliexpress.parser import AliExpressProductParser
from marketplace_connector.connectors.aliexpress.mapper import AliExpressMapper
from marketplace_connector.domain.errors import MarketplaceSchemaChanged
from marketplace_connector.serialization.product_json import card_to_dict

REF = '1005009868651525:12000061135122688'
FIXTURE = Path(__file__).parent / 'fixtures/aliexpress/product-data.json'


class AliExpressParserTests(unittest.TestCase):
    def setUp(self):
        self.payload = json.loads(FIXTURE.read_text())
        self.row = self.payload['data']['skuInfo']['priceList'][0]

    def card(self):
        return AliExpressMapper.to_card(AliExpressProductParser.parse(json.dumps(self.payload), expected_external_id=REF))

    def test_probe_maps_one_price_and_display_names(self):
        card = self.card()
        self.assertEqual(card.price, Decimal('77648.00'))
        self.assertEqual(card.variants[0].options['Цвет'], 'Black')
        self.assertEqual(card.variants[0].options['Комплект'], '12GB 256GB')
        self.assertIsNone(card.seller)
        self.assertTrue(card.image_url)
        self.assertEqual(card.rating.reviews_count, 22)
        self.assertEqual(card.attributes, ())
        normalized = json.dumps(card_to_dict(card))
        self.assertNotIn('activityAmount', normalized)
        self.assertNotIn('79316', normalized)
        self.assertNotIn('122312', normalized)

    def test_price_priority_missing_null_and_zero(self):
        self.row['priceWithCoupon'] = None
        self.assertEqual(self.card().price, Decimal('79316.00'))
        self.row.pop('activityAmount')
        self.assertEqual(self.card().price, Decimal('122312.00'))
        self.row['amount']['cents'] = '0'
        self.assertEqual(self.card().price, Decimal('0.00'))
        self.row['amount'] = None
        with self.assertRaises(MarketplaceSchemaChanged):
            self.card()

    def test_corrupt_present_price_does_not_fall_through(self):
        for amount in [{}, {'cents':'1','currency':'USD'}, {'cents':'-1','currency':'RUB'},
                       {'cents':True,'currency':'RUB'}, {'cents':'1.2','currency':'RUB'}]:
            self.row['priceWithCoupon']['amount'] = amount
            with self.subTest(amount=amount), self.assertRaises(MarketplaceSchemaChanged):
                self.card()

    def test_selected_stock_and_unknown(self):
        self.row['availQuantity'] = 0
        card = self.card()
        self.assertEqual(card.availability.value, 'out_of_stock')
        self.assertIsNone(card.price)
        self.row.pop('availQuantity')
        self.assertEqual(self.card().availability.value, 'unknown')
        self.row['availQuantity'] = -1
        with self.assertRaises(MarketplaceSchemaChanged): self.card()

    def test_mismatch_missing_duplicate_sku(self):
        original = deepcopy(self.payload)
        for key in ['id','activeSkuId']:
            self.payload = deepcopy(original)
            self.payload['data'][key] = '9'
            with self.assertRaises(MarketplaceSchemaChanged): self.card()
        self.payload = deepcopy(original)
        self.payload['data']['skuInfo']['priceList'] = []
        with self.assertRaises(MarketplaceSchemaChanged): self.card()
        self.payload = deepcopy(original)
        self.payload['data']['skuInfo']['priceList'].append(self.row)
        with self.assertRaises(MarketplaceSchemaChanged): self.card()

    def test_optional_fields_and_missing_coupon(self):
        self.row.pop('priceWithCoupon')
        for key in ['gallery','rating','reviews','characteristics','description']:
            self.payload['data'].pop(key)
        self.payload['data']['skuInfo'].pop('propertyList')
        card=self.card()
        self.assertEqual(card.price,Decimal('79316.00'))
        self.assertIsNone(card.image_url)
        self.assertIsNone(card.rating)
        self.assertEqual(card.attributes,())
        self.assertEqual(card.description,'')
        self.assertEqual(dict(card.variants[0].options),{})

    def test_product_discovery_has_variants_without_price_or_selected_sku(self):
        self.payload['data'].pop('activeSkuId')
        product = AliExpressProductParser.parse(self.payload, expected_external_id=REF.split(':')[0])
        card = AliExpressMapper.to_card(product)
        self.assertEqual(card.ref.external_id, REF.split(':')[0])
        self.assertIsNone(card.price)
        self.assertEqual(card.availability.value, 'unknown')
        self.assertTrue(card.variants)
        self.assertFalse(any(v.selected for v in card.variants))
        self.payload['data']['skuInfo']['priceList'] = []
        with self.assertRaises(MarketplaceSchemaChanged):
            AliExpressProductParser.parse(self.payload, expected_external_id=REF.split(':')[0])

    def test_variant_images_match_properties_and_selected_snapshot(self):
        data = self.payload['data']
        properties = data['skuInfo']['propertyList']
        expected = {str(v['id']): v.get('imageMainUrl') or v.get('imagePreviewUrl')
                    for p in properties for v in p['values']}
        rows = data['skuInfo']['priceList']
        cards = self.card()
        for row, variant in zip(rows, cards.variants):
            image = next((expected[k] for k in row['skuPropIds'].split(',') if expected.get(k)), None)
            self.assertEqual(variant.image_url, image)
        self.assertEqual(cards.image_url, next(v.image_url for v in cards.variants if v.selected))
        # Drop only the selected color photo: never borrow another color's photo.
        selected_ids = set(self.row['skuPropIds'].split(','))
        for p in properties:
            for v in p['values']:
                if str(v['id']) in selected_ids:
                    v.pop('imageMainUrl', None)
                    v.pop('imagePreviewUrl', None)
        self.assertEqual(self.card().image_url, data['gallery'][0]['imageUrl'])
