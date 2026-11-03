import json
import unittest
from copy import deepcopy
from decimal import Decimal
from pathlib import Path

from marketplace_connector.connectors.wildberries.mapper import WildberriesMapper
from marketplace_connector.domain.errors import MarketplaceSchemaChanged
from marketplace_connector.serialization.product_json import card_to_dict

REF = '179224846:296499716'
FIXTURE = Path(__file__).parent / 'fixtures/wildberries/runtime-product.json'


class WildberriesMapperTests(unittest.TestCase):
    def setUp(self):
        self.payload = json.loads(FIXTURE.read_text())
        self.size = self.payload['product']['sizes'][0]

    def card(self):
        return WildberriesMapper.to_card(self.payload, REF)

    def test_single_wallet_price_and_metadata(self):
        card = self.card()
        self.assertEqual(card.price, Decimal('1024.00'))
        self.assertEqual(card.rating.value, Decimal('4.8'))
        self.assertEqual(card.rating.reviews_count, 6470)
        self.assertEqual(card.seller.name, 'ALDINI')
        self.assertTrue(card.variants[0].selected)
        self.assertEqual(card.attributes, ())
        serialized = json.dumps(card_to_dict(card))
        for hidden in ['105600', '1056', 'paymentDiscountAmount', 'priceToShow']:
            self.assertNotIn(hidden, serialized)
        self.assertEqual(dict(card.extensions), {})

    def test_native_discounts_not_fixed_percentage_or_other_bank(self):
        self.size['price']['paymentDiscountAmount'] = '53'
        self.size['price']['priceWithDiscount'] = '1'
        self.assertEqual(self.card().price, Decimal('1003.00'))
        self.size['price']['paymentDiscountAmount'] = '0'
        self.assertEqual(self.card().price, Decimal('1056.00'))
        self.size['price'] = {'priceToShow': '0', 'paymentDiscountAmount': '0'}
        self.assertEqual(self.card().price, Decimal('0.00'))

    def test_bad_amount_does_not_use_ordinary_price(self):
        for field, value in [('paymentDiscountAmount', None), ('paymentDiscountAmount', '-1'),
                ('paymentDiscountAmount', 'NaN'), ('paymentDiscountAmount', 'Infinity'),
                ('paymentDiscountAmount', '1057'), ('paymentDiscountAmount', '0.001'),
                ('paymentDiscountAmount', 0), ('priceToShow', '1.5'), ('priceToShow', None)]:
            with self.subTest(field=field, value=value):
                original = deepcopy(self.size['price'])
                self.size['price'][field] = value
                with self.assertRaises(MarketplaceSchemaChanged): self.card()
                self.size['price'] = original
        for field, value in [('currency', 'USD'), ('walletReady', False), ('walletReady', None)]:
            with self.subTest(field=field), self.assertRaises(MarketplaceSchemaChanged):
                WildberriesMapper.to_card({**self.payload, field: value}, REF)

    def test_exact_stock_and_identity(self):
        neighbor = deepcopy(self.size)
        neighbor['optionId'] = '296499717'
        neighbor['price']['priceToShow'] = '1'
        self.payload['product']['sizes'].insert(0, neighbor)
        self.size['stocks'] = []
        self.assertIsNone(self.card().price)
        self.assertEqual(self.card().availability.value, 'out_of_stock')
        self.size.pop('stocks')
        self.assertEqual(self.card().availability.value, 'unknown')
        self.assertEqual(self.card().price, Decimal('1024.00'))
        self.payload['product']['sizes'].append(deepcopy(self.size))
        with self.assertRaises(MarketplaceSchemaChanged): self.card()

    def test_missing_size_product_and_bad_stock(self):
        for mutate in [lambda p: p['product'].update(id='1'),
                       lambda p: p['product']['sizes'][0].update(optionId='1'),
                       lambda p: p['product']['sizes'][0].update(stocks=[{'qty': -1}]),
                       lambda p: p['product']['sizes'][0].update(price=None)]:
            payload = deepcopy(self.payload)
            mutate(payload)
            with self.assertRaises(MarketplaceSchemaChanged): WildberriesMapper.to_card(payload, REF)

    def test_optional_static_color_and_description(self):
        self.payload['metadata']={'options':[{'name':'Цвет','value':'графит, темно-серый'}]}
        card=self.card()
        self.assertEqual(card.attributes[0].values,('графит, темно-серый',))
        self.assertEqual(card.description,'')
        self.assertEqual(card.image_url, self.payload['product']['imageUrl'])

    def test_product_discovery_has_variants_without_borrowing_size_price(self):
        card = WildberriesMapper.to_card(self.payload, REF.split(':')[0])
        self.assertEqual(card.ref.external_id, REF.split(':')[0])
        self.assertIsNone(card.price)
        self.assertEqual(card.availability.value, 'unknown')
        self.assertTrue(card.variants)
        self.assertFalse(any(v.selected for v in card.variants))

    def test_images_belong_to_article_and_all_sizes(self):
        image = self.payload['product']['imageUrl']
        card = self.card()
        self.assertEqual(card.image_url, image)
        self.assertTrue(all(v.image_url == image for v in card.variants))
        self.assertEqual(card_to_dict(card)['variants'][0]['image_url'], image)
        for value in [None, '', 12, 'javascript:alert(1)', 'https://[']:
            self.payload['product']['imageUrl'] = value
            card = self.card()
            self.assertIsNone(card.image_url)
            self.assertEqual(card.price, Decimal('1024.00'))
