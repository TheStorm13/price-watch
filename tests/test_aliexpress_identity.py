import unittest
from marketplace_connector.connectors.aliexpress.identity import AliExpressRef
from marketplace_connector.application.card_identity import validate_card_identity
from marketplace_connector.domain.errors import InvalidProductId
from price_watch.api.schemas import CardCreate


class AliExpressIdentityTests(unittest.TestCase):
    def test_exact_strings_and_url(self):
        value = '1005009868651525:12000061135122688'
        ref = AliExpressRef.parse(value)
        self.assertEqual(AliExpressRef.from_url(ref.url + '&spmC=foo'), ref)
        self.assertEqual(CardCreate(marketplace='aliexpress', external_id=value).external_id, value)
        self.assertEqual(validate_card_identity('aliexpress', value)[1], ref.url)

    def test_reject_ambiguous_or_missing_sku(self):
        for value in ['', '1:', '1:2:3', '１:2', '1:٢', '-1:2']:
            with self.subTest(value=value), self.assertRaises(InvalidProductId):
                AliExpressRef.parse(value)
        for url in ['https://ali.click/foo',
                    'https://aliexpress.com/item/1.html?sku_id=2',
                    'https://aliexpress.ru/item/1.html?sku_id=2&sku_id=2',
                    'https://aliexpress.ru/item/1.html?sku_id=']:
            with self.subTest(url=url), self.assertRaises(InvalidProductId):
                AliExpressRef.from_url(url)
        with self.assertRaises(InvalidProductId):
            validate_card_identity('aliexpress', '1:2', 'https://aliexpress.ru/item/1.html?sku_id=3')

    def test_product_only_starts_discovery(self):
        marketplace = 'aliexpress'
        ref_type = AliExpressRef
        ref = ref_type.parse('123')
        self.assertEqual(ref.external_id, '123')
        self.assertEqual(ref_type.from_url(ref.url), ref)
        self.assertEqual(CardCreate(marketplace=marketplace, external_id='123').external_id, '123')
        self.assertEqual(validate_card_identity(marketplace, '123', ref_type.parse('123:456').url)[0], '123')
        self.assertEqual(validate_card_identity(marketplace, '123:456', ref.url)[0], '123:456')
