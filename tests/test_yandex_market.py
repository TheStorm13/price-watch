"""Real storefront fixtures with synthetic failure and pricing boundaries."""
import asyncio
from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal
from html import escape
import json
from pathlib import Path
import unittest
from unittest.mock import AsyncMock

from marketplace_connector.application.card_identity import validate_card_identity, validate_variant_identity
from marketplace_connector.connectors.yandex_market.discovery import discover_family
from marketplace_connector.connectors.yandex_market.parser import parse_product
from marketplace_connector.connectors.yandex_market.pricing import select_price
from marketplace_connector.domain.errors import AuthenticationRequired, InvalidProductId, MarketplaceSchemaChanged, MarketplaceUnavailable
from marketplace_connector.serialization.product_json import card_to_dict

SEED = '5355099814'
NOW = datetime(2026, 11, 10, tzinfo=timezone.utc)
CAPTURE = json.loads((Path(__file__).parent / 'fixtures/yandex_market/family.json').read_text())
FAMILY = CAPTURE['products']
for _product in FAMILY.values():
    _product['collections']['shopPromoCodeFull'] = CAPTURE['shared_promos'][_product['promo_fixture']]


def html(sku=SEED, *, data=None, extra=0):
    data = deepcopy(data or FAMILY[sku])
    parts = ['<noframes>' + json.dumps({'collections': data['collections']}, ensure_ascii=False) + '</noframes>']
    groups = {}
    for edge in data['edges']:
        groups.setdefault(edge['filterid'], []).append(edge)
    for edges in groups.values():
        parts.append('<div data-zone-name="filter" data-zone-data=\'' + json.dumps({'numValues': len(edges) + extra}) + '\'>')
        for e in edges:
            parts.append('<div data-zone-name="filterValue" ' + ' '.join(f'{k}="{escape(v, quote=True)}"' for k, v in e.items()) + '></div>')
        parts.append('</div>')
    return ''.join(parts)


def price_inputs():
    c = deepcopy(FAMILY[SEED]['collections'])
    return next(iter(c['price'].values())), next(iter(c['buyOption'].values())), c['shopPromoCodeFull']


def external_article_html(data=None):
    data = data or json.loads((Path(__file__).parent / 'fixtures/yandex_market/external_article.json').read_text())
    return ('<noframes>' + json.dumps({'collections': data['collections']}) + '</noframes>'
            '<div data-zone-name="filter" data-zone-data=\''
            + json.dumps({'numValues': data['declared']}) + '\'></div>')


def external_family_html(article):
    """Synthetic exact offers over the captured ten-article storefront group."""
    data = json.loads((Path(__file__).parent / 'fixtures/yandex_market/external_article.json').read_text())
    c = data['collections']
    meta = next(iter(c['productCardMeta'].values()))
    compose = next(iter(c['compose'].values()))
    buy = next(iter(c['buyOption'].values()))
    if article != '6019174271':
        meta['marketSku'] = compose['skuId'] = buy['skuId'] = article
        meta['productId'] = compose['productId'] = buy['productId'] = 'other-model-' + article[-1]
    compose['oskuId'] = article
    jump = next(iter(c['jumpListShort'].values()))
    jump['showAllTransition']['params']['oskuId'] = article
    for snippet in jump['snippets']:
        snippet['productPayload']['jumpList'] = {'isSelected': snippet['snippetId'] == article}
    return external_article_html(data)


class YandexParserTests(unittest.TestCase):
    def test_external_article_preserves_selected_product_with_different_internal_sku(self):
        result = parse_product(external_article_html(), '6019174271', now=NOW)
        card = result.card
        self.assertEqual(card.ref.external_id, '6019174271')
        self.assertTrue(card.url.endswith('/6019174271'))
        self.assertEqual(card.price, Decimal('3058.20'))
        self.assertEqual(card.extensions['yandex_market']['market_sku_id'], '6249927249')
        self.assertEqual(card.extensions['yandex_market']['promo_code'], 'HOME11')
        self.assertEqual(len(result.edges), 10)
        self.assertIn('241701528573190144', result.edges)
        self.assertIsNone(result.discovery_error)
        validate_card_identity('yandex-market', card.ref.external_id, card.url)

    def test_external_article_rejects_wrong_offer_or_internal_sku(self):
        for field in ('oskuId', 'skuId', 'offerId'):
            data = json.loads((Path(__file__).parent / 'fixtures/yandex_market/external_article.json').read_text())
            next(iter(data['collections']['compose'].values()))[field] = '123'
            with self.subTest(field=field), self.assertRaises(MarketplaceSchemaChanged):
                parse_product(external_article_html(data), '6019174271', now=NOW)

    def test_structured_control_requires_complete_count_and_exact_selected_article(self):
        for failure in ('count', 'selected', 'target', 'continuation'):
            data = json.loads((Path(__file__).parent / 'fixtures/yandex_market/external_article.json').read_text())
            jump = next(iter(data['collections']['jumpListShort'].values()))
            if failure == 'count': data['declared'] += 1
            if failure == 'selected':
                for snippet in jump['snippets']: snippet['productPayload'].pop('jumpList', None)
            if failure == 'target':
                jump['snippets'][0]['productPayload']['targetLinkParams']['offerLinkParams']['oskuId'] = '123'
            if failure == 'continuation': jump['showAllTransition']['type'] = 'unknown'
            with self.subTest(failure=failure):
                result = parse_product(external_article_html(data), '6019174271', now=NOW)
                self.assertIsNotNone(result.discovery_error)
                self.assertEqual(result.card.price, Decimal('3058.20'))

    def test_card_plus_one_offer_promo_and_safe_serialization(self):
        result = parse_product(html(), SEED, now=NOW)
        self.assertEqual(result.card.price, Decimal('2663.10'))
        self.assertEqual(result.card.extensions['yandex_market']['promo_code'], 'CLOTH11')
        self.assertEqual(result.options, {'Цвет': 'голубой в полоску', 'Размер': '50'})
        self.assertEqual(len(result.edges), 14)
        json.dumps(card_to_dict(result.card))
        self.assertIsNone(result.discovery_error)

    def test_auth_sku_compose_and_offer_mismatch_are_errors(self):
        for field in ('auth', 'sku', 'offer'):
            data = deepcopy(FAMILY[SEED])
            c = data['collections']
            if field == 'auth': c['currentUser']['fixture']['isAuth'] = False
            if field == 'sku': next(iter(c['compose'].values()))['skuId'] = '123'
            if field == 'offer': next(iter(c['buyOption'].values()))['offerId'] = 'another'
            with self.subTest(field=field), self.assertRaises(AuthenticationRequired if field == 'auth' else MarketplaceSchemaChanged):
                parse_product(html(data=data), SEED, now=NOW)

    def test_missing_auth_data_is_schema_error_not_claim_of_logged_out_user(self):
        with self.assertRaises(MarketplaceSchemaChanged):
            parse_product('<!DOCTYPE html>', SEED, now=NOW)

    def test_incomplete_control_keeps_price(self):
        result = parse_product(html(extra=1), SEED, now=NOW)
        self.assertIsNotNone(result.discovery_error)
        self.assertEqual(result.card.price, Decimal('2663.10'))

    def test_unavailable_exact_sku_keeps_identity(self):
        data = deepcopy(FAMILY[SEED])
        next(iter(data['collections']['buyOption'].values()))['maximum'] = 0
        card = parse_product(html(data=data), SEED, now=NOW).card
        self.assertIsNone(card.price)
        self.assertEqual(card.availability.value, 'out_of_stock')
        self.assertEqual(card.ref.external_id, SEED)

    def test_no_sizes_does_not_mean_out_of_stock_but_no_delivery_does(self):
        data = deepcopy(FAMILY[SEED])
        buy = next(iter(data['collections']['buyOption'].values()))
        buy['hasAnySize'] = False
        card = parse_product(html(data=data), SEED, now=NOW).card
        self.assertEqual(card.availability.value, 'in_stock')
        self.assertEqual(card.price, Decimal('2663.10'))
        buy['hasAnyDelivery'] = False
        card = parse_product(html(data=data), SEED, now=NOW).card
        self.assertEqual(card.availability.value, 'out_of_stock')
        self.assertIsNone(card.price)

    def test_malformed_availability_does_not_mark_out_of_stock(self):
        data = deepcopy(FAMILY[SEED])
        next(iter(data['collections']['buyOption'].values()))['hasAnyDelivery'] = None
        with self.assertRaises(MarketplaceSchemaChanged):
            parse_product(html(data=data), SEED, now=NOW)

    def test_start_date_and_quantity_restrictions_exclude_promos(self):
        p, b, promos = price_inputs()
        b['minimum'] = 2
        self.assertEqual(select_price(p, b, promos, now=NOW)[0], Decimal('2959'))
        b['minimum'] = 1
        promos['cf_144101']['startDate'] = '2026-11-11T00:00:00Z'
        self.assertEqual(select_price(p, b, promos, now=NOW)[0], Decimal('2959'))

    def test_identity_and_declared_membership(self):
        self.assertEqual(validate_variant_identity('yandex-market', SEED, '5355099813')[0], '5355099813')
        for sku, url in [('１２３', None), ('123', 'https://market.yandex.ru/card/a/124'), ('123', 'https://market.yandex.ru.evil/card/a/123')]:
            with self.subTest(sku=sku, url=url), self.assertRaises(InvalidProductId):
                validate_card_identity('yandex-market', sku, url)

    def test_price_conditions_caps_expiry_and_unbound_promos(self):
        p, b, promos = price_inputs()
        promo = promos['cf_144101']
        promo['discount']['percent'] = 50
        final, detail = select_price(p, b, promos, now=NOW)
        self.assertEqual(final, Decimal('2459.00'))
        promo['endDate'] = NOW.isoformat()
        self.assertEqual(select_price(p, b, promos, now=NOW)[0], Decimal('2959'))
        p, b, promos = price_inputs()
        b['promos'] = []
        self.assertIsNone(select_price(p, b, promos, now=NOW)[1]['promo_code'])

    def test_absolute_discount_not_effective_percent_and_no_stacking(self):
        p, b, promos = price_inputs()
        promo = promos['cf_144097']
        promo['conditions'] = {'orderMinPrice': {'value': 2959, 'currency': 'RUR'}}
        final, detail = select_price(p, b, promos, now=NOW)
        self.assertEqual(final, Decimal('1959.00'))
        self.assertEqual(detail['promo_code'], 'NOV1000')
        promo['conditions']['orderMinPrice']['value'] = 2960
        self.assertEqual(select_price(p, b, promos, now=NOW)[0], Decimal('2663.10'))

    def test_clipped_absolute_unknown_conditions_and_regular_fallback(self):
        p, b, promos = price_inputs()
        for promo in promos.values(): promo['conditions'] = {'unverifiedRule': True}
        self.assertEqual(select_price(p, b, promos, now=NOW)[0], Decimal('2959'))
        p['mainPrice'] = {'type':'regular','price':{'value':3051,'currency':'RUR'}}
        self.assertEqual(select_price(p, b, {}, now=NOW)[0], Decimal('3051'))
        del p['mainPrice']['price']
        with self.assertRaises(MarketplaceSchemaChanged):select_price(p, b, {}, now=NOW)


class YandexDiscoveryTests(unittest.IsolatedAsyncioTestCase):
    async def test_unexpected_model_in_size_color_control_remains_discovery_error(self):
        from dataclasses import replace
        root = replace(parse_product(html(), SEED, now=NOW), edges=('5355104657',))
        async def fetch(sku):
            return root if sku == SEED else replace(root, parent_id='other', edges=())
        snapshots = {}
        await discover_family(None, SEED, snapshots, fetch_product=fetch)
        self.assertEqual(list(snapshots), [SEED])
        self.assertIn('variant_discovery_error', snapshots[SEED].extensions)
        self.assertEqual(snapshots[SEED].price, Decimal('2663.10'))

    async def test_all_declared_articles_are_collected_across_internal_product_ids(self):
        snapshots = {}
        transport = AsyncMock(fetch=AsyncMock(side_effect=external_family_html))
        await discover_family(transport, '6019174271', snapshots)
        self.assertEqual(len(snapshots), 10)
        self.assertEqual(transport.fetch.await_count, 10)
        card = snapshots['6019174271']
        self.assertEqual(card.price, Decimal('3058.20'))
        self.assertEqual([v.ref.external_id for v in card.variants if v.selected], ['6019174271'])
        self.assertNotIn('variant_discovery_error', card.extensions)
        self.assertEqual(set(v.ref.external_id for v in card.variants), set(snapshots))

    async def test_complete_real_graph_has_64_unique_skus_and_exact_prices(self):
        transport = AsyncMock()
        transport.fetch.side_effect = lambda sku: html(sku)
        snapshots = {}
        await discover_family(transport, SEED, snapshots)
        self.assertEqual(set(snapshots), set(FAMILY))
        self.assertEqual(transport.fetch.await_count, 64)
        for sku, card in snapshots.items():
            self.assertEqual(len(card.variants), 64)
            self.assertEqual([v.ref.external_id for v in card.variants if v.selected], [sku])
            self.assertNotIn('variant_discovery_error', card.extensions)
            self.assertIsNotNone(card.price)

    async def test_partial_network_and_foreign_parent_keep_verified_price(self):
        async def fetch(sku):
            if sku == '5355104662': raise MarketplaceUnavailable('synthetic')
            data = deepcopy(FAMILY[sku])
            if sku == '5355104657':
                for k in ('compose','productCardMeta','buyOption'):
                    next(iter(data['collections'][k].values()))['productId'] = '999'
            return html(sku, data=data)
        snapshots = {}
        await discover_family(AsyncMock(fetch=fetch), SEED, snapshots)
        self.assertIn('variant_discovery_error', snapshots[SEED].extensions)
        self.assertNotIn('5355104662', snapshots)
        self.assertNotIn('5355104657', snapshots)
        self.assertIsNotNone(snapshots[SEED].price)
