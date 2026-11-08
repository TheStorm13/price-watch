"""Ozon family traversal through production parsers, executor and PostgreSQL."""
import asyncio
import copy
import json
import os
import unittest
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from marketplace_connector.application.card_identity import validate_card_identity, validate_variant_identity
from marketplace_connector.connectors.ozon.connector import OzonConnector
from marketplace_connector.connectors.ozon.mapper import OzonMapper
from marketplace_connector.connectors.ozon.models import OzonResponse
from marketplace_connector.connectors.ozon.parser import OzonProductParser
from marketplace_connector.domain.errors import InvalidProductId, ProductNotFound
from price_watch.domain.models import LeaseLost
from tests import test_product_variants as variant_tests

SEED = '2936650207'
FAMILY = json.loads((Path(__file__).parent / 'fixtures/ozon/variant-family.json').read_text())


def payload(sku, family=FAMILY):
    """Observed edges/options; synthetic prices and images, no profile data."""
    current = family[sku]['options']
    aspects = []
    for name in current:
        members = []
        for other in family[sku]['neighbors']:
            options = family[other]['options']
            if any(options.get(key) != value for key, value in current.items() if key != name):
                continue
            members.append({'sku': other, 'link': f'/product/{other}/', 'active': other == sku,
                'availability': 'inStock', 'data': {'searchableText': options[name],
                'title': 'Кеды Thomas Munz', 'coverImage': f'https://img.test/{other}.jpg'}})
        aspects.append({'aspectName': name, 'variants': members})
    return {'pageInfo': {'analyticsInfo': {'sku': sku}},
        'seo': {'link': [{'rel': 'canonical', 'href': f'https://www.ozon.ru/product/{sku}/'}]},
        'widgetStates': {'webProductHeading-1': {'title': 'Кеды Thomas Munz'},
            'webPrice-1': {'cardPrice': 100 + int(sku[-2:]), 'isAvailable': True},
            'webAspects-1': {'aspects': aspects}}}


class FixtureClient:
    def __init__(self, fail=(), missing=(), unavailable=()):
        self.calls = []
        self.opens = 0
        self.fail = set(fail)
        self.missing = set(missing)
        self.unavailable = set(unavailable)
        self.family = copy.deepcopy(FAMILY)
        self.incomplete = False
        self.image_revision = ''

    @asynccontextmanager
    async def collection_session(self):
        self.opens += 1
        yield

    async def fetch_product_async(self, sku):
        self.calls.append(sku)
        if sku in self.fail:
            raise RuntimeError('Synthetic request failure')
        if sku in self.missing:
            raise ProductNotFound(sku)
        raw = payload(sku, self.family)
        if sku in self.unavailable:
            raw['widgetStates']['webPrice-1'] = {'price': '1 563 ₽', 'cardPrice': 1563, 'isAvailable': False}
        if self.image_revision:
            raw['widgetStates']['webGallery-1'] = {'images': [f'https://img.test/{sku}-{self.image_revision}.jpg']}
        if self.incomplete:
            raw['widgetStates']['webAspects-1']['nextPage'] = '/unrecognised-continuation'
        return OzonResponse(json.dumps(raw), OzonMapper.to_card(OzonProductParser.parse(
            raw, expected_external_id=sku, collected_at=datetime.now(timezone.utc))))

    async def fetch_raw_text_async(self, sku):
        return (await self.fetch_product_async(sku)).raw_text


class OzonVariantParserTests(unittest.TestCase):
    def test_graph_exposes_twelve_skus_and_current_keeps_both_aspects(self):
        pending = [SEED]
        found = {}
        while pending:
            sku = pending.pop()
            if sku in found:
                continue
            card = OzonMapper.to_card(OzonProductParser.parse(payload(sku), expected_external_id=sku))
            own = next(v for v in card.variants if v.selected)
            self.assertEqual(dict(own.options), FAMILY[sku]['options'])
            self.assertEqual(card.extensions, {})
            found[sku] = card
            pending.extend(v.ref.external_id for v in card.variants if v.ref.external_id not in found)
        self.assertEqual(set(found), set(FAMILY))
        self.assertEqual(len(found[SEED].variants), 7)

    def test_unknown_continuation_is_explicit_but_keeps_exact_price(self):
        raw = payload(SEED)
        raw['widgetStates']['webAspects-1']['nextPage'] = '/more'
        card = OzonMapper.to_card(OzonProductParser.parse(raw, expected_external_id=SEED))
        self.assertIsNotNone(card.price)
        self.assertIn('nextPage', card.extensions['variant_discovery_error'])

    def test_exact_urls_and_declarative_membership(self):
        self.assertEqual(validate_variant_identity('ozon', SEED, '2936649562')[0], '2936649562')
        self.assertEqual(validate_card_identity('ozon', SEED)[1], f'https://www.ozon.ru/product/{SEED}/')
        for url in [f'https://ozon.ru.evil.test/product/{SEED}/', 'https://www.ozon.ru/product/123/',
                    f'http://www.ozon.ru/product/{SEED}/', f'https://www.ozon.ru/product/{SEED}/#fragment']:
            with self.subTest(url=url), self.assertRaises(InvalidProductId):
                validate_card_identity('ozon', SEED, url)
        for sku in ['12:34', '１２３', 'abc']:
            with self.subTest(sku=sku), self.assertRaises(InvalidProductId):
                validate_card_identity('ozon', sku)
        with self.assertRaises(InvalidProductId):
            validate_variant_identity('wildberries', SEED, '123:4')


class OzonNumericCliTests(unittest.IsolatedAsyncioTestCase):
    async def test_unavailable_numeric_and_raw_keep_image_and_skus_without_database(self):
        import io
        from contextlib import redirect_stdout
        from marketplace_connector.connectors.ozon import cli
        for raw in (False, True):
            fixture = FixtureClient(unavailable=[SEED])
            fixture.image_revision = 'unavailable'
            args = cli.build_parser().parse_args([SEED, *(['--raw'] if raw else [])])
            output = io.StringIO()
            with patch.dict(os.environ, {}, clear=True), patch.object(cli, 'AsyncOzonClient', return_value=fixture), redirect_stdout(output):
                self.assertEqual(await cli._run(args), 0)
            self.assertEqual(fixture.calls, [SEED])
            result = json.loads(output.getvalue())
            if raw:
                self.assertIn('webGallery-1', result['widgetStates'])
                self.assertIn('webAspects-1', result['widgetStates'])
            else:
                self.assertEqual(result['availability'], 'out_of_stock')
                self.assertIsNone(result['price'])
                self.assertEqual(result['image_url'], f'https://img.test/{SEED}-unavailable.jpg')
                self.assertEqual(len(result['variants']), 7)

    async def test_numeric_and_raw_cli_make_one_exact_request_without_database(self):
        import io
        from contextlib import redirect_stdout
        from marketplace_connector.connectors.ozon import cli
        for raw in (False, True):
            fixture = FixtureClient()
            args = cli.build_parser().parse_args([SEED, *(['--raw'] if raw else [])])
            output = io.StringIO()
            with patch.dict(os.environ, {}, clear=True), patch.object(cli, 'AsyncOzonClient', return_value=fixture), redirect_stdout(output):
                self.assertEqual(await cli._run(args), 0)
            self.assertEqual(fixture.calls, [SEED])
            result = json.loads(output.getvalue())
            if raw:
                self.assertIn('widgetStates', result)
            else:
                own = next(v for v in result['variants'] if v['selected'])
                self.assertEqual(own['options'], FAMILY[SEED]['options'])


@unittest.skipUnless(os.environ.get('TEST_DATABASE_URL'), 'requires disposable TEST_DATABASE_URL')
class OzonVariantIntegrationTests(unittest.IsolatedAsyncioTestCase):
    asyncSetUp = variant_tests.ProductVariantTests.asyncSetUp
    asyncTearDown = variant_tests.ProductVariantTests.asyncTearDown
    executor = variant_tests.ProductVariantTests.executor

    async def add_ozon(self, sku=SEED):
        response = await self.client.post('/api/cards', json={'marketplace': 'ozon', 'externalId': sku})
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    async def variants(self, card):
        return (await self.client.get(f'/api/cards/{card["id"]}/variants')).json()

    async def test_twelve_exact_prices_metadata_switch_and_no_duplicate_observations(self):
        card = await self.add_ozon()
        original_id = card['primaryVariantId']
        # Existing single-SKU card with history must expand in place.
        solo = FixtureClient()
        solo.family[SEED]['neighbors'] = [SEED]
        first = await self.executor(OzonConnector(solo)).collect(card['id'])
        self.assertEqual(first.total_count, 1)
        original_point = (await self.client.get(f'/api/cards/{card["id"]}/chart')).json()['points'][0]
        fixture = FixtureClient()
        result = await self.executor(OzonConnector(fixture)).collect(card['id'])
        self.assertEqual((result.total_count, result.success_count, result.failure_count), (12, 12, 0))
        self.assertEqual(len(fixture.calls), 12)
        self.assertEqual(set(fixture.calls), set(FAMILY))
        self.assertEqual(fixture.opens, 1)
        variants = await self.variants(card)
        self.assertEqual(len(variants), 12)
        for v in variants:
            self.assertEqual(v['options'], FAMILY[v['externalId']]['options'])
            self.assertEqual(v['imageUrl'], f'https://img.test/{v["externalId"]}.jpg')
        path = f'/api/cards/{card["id"]}'
        before = (await self.client.get(path + '/chart')).json()
        self.assertEqual(len(before['points']), 12)
        self.assertIn(original_point, before['points'])
        self.assertEqual((await self.client.get(path)).json()['primaryVariantId'], original_id)
        other = next(v for v in variants if v['externalId'] != SEED)
        changed = await self.client.patch(path, json={'primaryVariantId': other['id']})
        self.assertEqual(changed.status_code, 200, changed.text)
        self.assertEqual(changed.json()['options'], other['options'])
        self.assertEqual(changed.json()['externalId'], SEED)
        self.assertEqual((await self.client.get(path + '/chart')).json(), before)
        fixture.calls.clear()
        fixture.image_revision = 'new'
        await self.executor(OzonConnector(fixture)).collect(card['id'])
        self.assertEqual(len(fixture.calls), 12)
        self.assertEqual((await self.client.get(path + '/chart')).json(), before)
        self.assertTrue(all(v['imageUrl'].endswith('-new.jpg') for v in await self.variants(card)))
        duplicate = await self.client.post('/api/cards', json={'marketplace': 'ozon', 'externalId': other['externalId']})
        self.assertEqual(duplicate.status_code, 409)
        invalid = await self.client.patch(path, json={'url': f'https://www.ozon.ru/product/{SEED}/'})
        self.assertEqual(invalid.status_code, 422)

    async def test_partial_failure_exact_retry_then_normal_discovery_and_stale_lease(self):
        card = await self.add_ozon()
        failed = '2936649562'
        fixture = FixtureClient(fail=[failed])
        result = await self.executor(OzonConnector(fixture)).collect(card['id'])
        self.assertEqual((result.total_count, result.success_count, result.failure_count), (12, 11, 1))
        retry = await self.stores.runs.create_retry_run(result.run_id)
        targets = await self.stores.runs.cards_for_run(retry.id)
        self.assertEqual([t.ref.external_id for t in targets], [failed])
        owned = await self.stores.runs.claim_next_run()
        fixture.fail.clear()
        fixture.calls.clear()
        new_sku = '9990001'
        fixture.family[new_sku] = {'options': {'Цвет': 'черный; серый', 'Размер': '46 RU / 46'}, 'neighbors': [failed, new_sku]}
        fixture.family[failed]['neighbors'].append(new_sku)
        done = await self.executor(OzonConnector(fixture)).execute(owned)
        self.assertEqual((done.total_count, done.success_count), (1, 1))
        self.assertEqual(fixture.calls, [failed])
        self.assertEqual(len(await self.variants(card)), 12)
        with self.assertRaises(LeaseLost):
            await self.stores.runs.save_result(owned.lease, targets[0], await OzonConnector(fixture).get_product(failed))
        self.assertEqual(len((await self.client.get(f'/api/cards/{card["id"]}/chart')).json()['points']), 12)
        fixture.calls.clear()
        expanded = await self.executor(OzonConnector(fixture)).collect(card['id'])
        self.assertEqual((expanded.total_count, expanded.success_count), (13, 13))
        self.assertEqual(fixture.calls.count(new_sku), 1)

    async def test_missing_neighbor_keeps_all_other_histories(self):
        card = await self.add_ozon()
        fixture = FixtureClient(missing=['2936649562'])
        result = await self.executor(OzonConnector(fixture)).collect(card['id'])
        self.assertEqual((result.success_count, result.failure_count), (12, 0))
        variants = await self.variants(card)
        missing = next(v for v in variants if v['externalId'] in fixture.missing)
        self.assertEqual((missing['currentPrice'], missing['currentAvailability']), (None, 'out_of_stock'))
        self.assertEqual(sum(v['currentPrice'] is not None for v in variants), 11)

    async def test_limit_and_unsupported_continuation_keep_valid_prices(self):
        card = await self.add_ozon()
        fixture = FixtureClient()
        with patch('price_watch.infrastructure.postgres.runs_repository.MAX_OZON_VARIANTS', 3):
            result = await self.executor(OzonConnector(fixture)).collect(card['id'])
        self.assertEqual(result.total_count, 3)
        self.assertGreater(result.failure_count, 0)
        self.assertEqual(len(fixture.calls), 3)
        self.assertEqual(len((await self.client.get(f'/api/cards/{card["id"]}/chart')).json()['points']), 3)
        result = await self.executor(OzonConnector(fixture)).collect(card['id'])
        self.assertEqual((result.total_count, result.failure_count), (12, 0))
        fixture.incomplete = True
        result = await self.executor(OzonConnector(fixture)).collect(card['id'])
        self.assertEqual(result.failure_count, 12)
        self.assertEqual(sum(v['currentPrice'] is not None for v in await self.variants(card)), 12)

    async def test_conflicting_owner_is_reported_without_moving_histories(self):
        first = await self.add_ozon()
        other = await self.add_ozon('2936649562')
        result = await self.executor(OzonConnector(FixtureClient())).collect(first['id'])
        self.assertGreater(result.failure_count, 0)
        details = await self.stores.runs.get_run(result.run_id, include_errors=True)
        messages = ' '.join(e['message'] for e in details.errors)
        self.assertIn(str(other['id']), messages)
        self.assertEqual(len(await self.variants(first)), 11)
        self.assertEqual(len(await self.variants(other)), 1)
        self.assertIsNone((await self.variants(other))[0]['currentPrice'])

    async def test_transfer_roundtrip_idempotence_and_conflicting_owner_preflight(self):
        card = await self.add_ozon()
        await self.executor(OzonConnector(FixtureClient())).collect(card['id'])
        variants = await self.variants(card)
        await self.client.patch(f'/api/cards/{card["id"]}', json={'primaryVariantId': variants[-1]['id']})
        exported = (await self.client.get('/api/cards/export')).json()
        await self.client.delete(f'/api/cards/{card["id"]}')
        restored = await self.client.post('/api/cards/import', json=exported)
        self.assertEqual(restored.status_code, 200, restored.text)
        self.assertEqual((await self.client.get('/api/cards/export')).json(), exported)
        duplicate = await self.client.post('/api/cards/import', json=exported)
        self.assertEqual(duplicate.json()['observationsAdded'], 0)
        bad = copy.deepcopy(exported)
        bad['cards'][0]['externalId'] = variants[-1]['externalId']
        conflict = await self.client.post('/api/cards/import', json=bad)
        self.assertEqual(conflict.status_code, 409, conflict.text)
        preview = await self.client.post('/api/cards/import/preview', json=bad)
        self.assertEqual(preview.status_code, 409, preview.text)
        self.assertEqual((await self.client.get('/api/cards/export')).json(), exported)

    async def test_concurrent_add_and_discovery_never_duplicate_owner(self):
        card = await self.add_ozon()
        fixture = FixtureClient()
        await asyncio.gather(self.executor(OzonConnector(fixture)).collect(card['id']),
            self.client.post('/api/cards', json={'marketplace': 'ozon', 'externalId': '2936649562'}))
        exported = (await self.client.get('/api/cards/export')).json()
        refs = [v['externalId'] for c in exported['cards'] for v in c['variants']]
        self.assertEqual(len(refs), len(set(refs)))

    async def test_concurrent_import_and_add_never_duplicate_owner_or_partially_import(self):
        card = await self.add_ozon()
        await self.executor(OzonConnector(FixtureClient())).collect(card['id'])
        exported = (await self.client.get('/api/cards/export')).json()
        await self.client.delete(f'/api/cards/{card["id"]}')
        exported['cards'][0]['marketplace'] = 'Ozon'
        imported, added = await asyncio.gather(self.client.post('/api/cards/import', json=exported),
            self.client.post('/api/cards', json={'marketplace': 'ozon', 'externalId': '2936649562'}))
        self.assertIn((imported.status_code, added.status_code), [(200, 409), (409, 201)])
        result = (await self.client.get('/api/cards/export')).json()
        self.assertEqual(len(result['cards']), 1)
        refs = [v['externalId'] for c in result['cards'] for v in c['variants']]
        self.assertEqual(len(refs), len(set(refs)))
        self.assertEqual(len(refs), 12 if imported.status_code == 200 else 1)

    async def test_foreign_marketplace_discovery_is_rejected_without_wrong_history(self):
        from dataclasses import replace
        class ForeignConnector(OzonConnector):
            async def get_product(self, sku):
                snapshot = await super().get_product(sku)
                candidate = snapshot.variants[0]
                return replace(snapshot, variants=(replace(candidate, ref=replace(candidate.ref, marketplace='wildberries')),))
        card = await self.add_ozon()
        result = await self.executor(ForeignConnector(FixtureClient())).collect(card['id'])
        self.assertEqual((result.total_count, result.failure_count), (1, 1))
        self.assertEqual(len(await self.variants(card)), 1)
        self.assertEqual((await self.client.get(f'/api/cards/{card["id"]}/chart')).json()['points'], [])

    async def test_queue_schedule_and_direct_cli_use_same_primary_policy(self):
        card = await self.add_ozon()
        await self.executor(OzonConnector(FixtureClient())).collect(card['id'])
        queued = await self.client.post('/api/runs', json={'cardId': card['id']})
        self.assertEqual(queued.status_code, 202, queued.text)
        from marketplace_connector import ConnectorRegistry
        from price_watch.worker import CollectionWorker
        async def factory(run):
            return ConnectorRegistry([OzonConnector(FixtureClient())])
        worker = CollectionWorker(self.stores.runs, factory, execution=self.stores.runs)
        self.assertTrue(await worker.run_once())
        result = await self.stores.runs.get_run(queued.json()['id'])
        self.assertEqual((result.total_count, result.success_count), (1, 1))
        # Schedule target selection is shared with queued and direct collection.
        from datetime import timedelta
        due = await self.stores.runs.create_due_run(datetime.now(timezone.utc) + timedelta(days=2))
        self.assertIsNotNone(due)
        self.assertEqual(len(await self.stores.runs.cards_for_run(due.id)), 1)
        self.assertTrue(await worker.run_once())
        # Exercise the direct CLI entry point against the same exact adapters.
        import io
        from contextlib import redirect_stdout
        from price_watch import cli
        args = cli.build_parser().parse_args(['collect', '--card-id', str(card['id'])])
        fixture = FixtureClient()
        output = io.StringIO()
        with patch.object(cli, '_build_connectors', return_value=ConnectorRegistry([OzonConnector(fixture)])), redirect_stdout(output):
            self.assertEqual(await cli._execute(args, self.db), 0)
        self.assertEqual(json.loads(output.getvalue())['success_count'], 1)
        self.assertEqual(len(fixture.calls), 1)
