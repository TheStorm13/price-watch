import unittest

from marketplace_connector.application.card_identity import validate_card_identity
from marketplace_connector.connectors.wildberries.identity import WildberriesRef
from marketplace_connector.domain.errors import InvalidProductId
from price_watch.api.schemas import CardCreate


class WildberriesIdentityTests(unittest.TestCase):
    def test_exact_size_and_canonical_url(self):
        ref = WildberriesRef.parse('179224846:296499716')
        self.assertEqual(WildberriesRef.from_url(ref.url + '&targetUrl=SN'), ref)
        card = CardCreate(marketplace='wildberries', external_id=ref.external_id)
        self.assertEqual(str(card.url), ref.url)
        self.assertEqual(validate_card_identity('wildberries', ref.external_id), (ref.external_id, ref.url))
        self.assertNotEqual(ref, WildberriesRef.parse('179224846:296499717'))

    def test_invalid_id(self):
        for value in ['', '1:', '1:2:3', '１:2', '1:٢', '-1:2', '0:2', '1:0', '01:2', '1:9007199254740992']:
            with self.subTest(value=value), self.assertRaises(InvalidProductId):
                WildberriesRef.parse(value)

    def test_invalid_url_and_mismatch(self):
        ref = WildberriesRef.parse('1:2')
        for url in [ref.url+'&size=2',
                    ref.url.replace('https:', 'http:'), ref.url.replace('www.wildberries.ru', 'evil.ru'),
                    ref.url+'&size=', ref.url+'#fragment']:
            with self.subTest(url=url), self.assertRaises(InvalidProductId):
                WildberriesRef.from_url(url)
        for value in ['1:3', '2:2']:
            with self.assertRaises(InvalidProductId):
                validate_card_identity('wildberries', value, ref.url)

    def test_product_only_starts_discovery(self):
        marketplace = 'wildberries'
        ref_type = WildberriesRef
        ref = ref_type.parse('123')
        self.assertEqual(ref.external_id, '123')
        self.assertEqual(ref_type.from_url(ref.url), ref)
        self.assertEqual(CardCreate(marketplace=marketplace, external_id='123').external_id, '123')
        self.assertEqual(validate_card_identity(marketplace, '123', ref_type.parse('123:456').url)[0], '123')
        self.assertEqual(validate_card_identity(marketplace, '123:456', ref.url)[0], '123:456')
