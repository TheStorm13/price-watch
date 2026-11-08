"""Actual Chrome runs the production bridge against a synthetic WB storefront."""
import asyncio
import json
import shutil
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import AsyncMock

from marketplace_connector.browser.session import ChromeSession
from marketplace_connector.connectors.wildberries.client import AsyncWildberriesClient
from marketplace_connector.connectors.wildberries.connector import WildberriesConnector
from marketplace_connector.domain.errors import MarketplaceSchemaChanged, MarketplaceUnavailable, RateLimited, InvalidProductId
from tests.test_wildberries_mapper import FIXTURE, REF

# This fixture models the storefront lifecycle, not an independent price parser.
# The real bridge must explicitly prepare grade before the normalizer gets it.
HOME = '''<html><script>
window.testState={discount:0,percent:3,auth:false,gradeCalls:0,xinfoCalls:0,earlyFailures:0};
window.wb={user:{
 getCurrency:()=> 'RUB',
 getXinfo:async()=>{testState.xinfoCalls++;if(testState.xinfoCalls<=testState.earlyFailures)throw Error('host not initialized');return 'curr=rub&dest=123';},
 getUserGrade:async()=> {
  if(!testState.auth)return null;
  const r=await fetch('/test/v6/grade');const d=await r.json();
  testState.gradeCalls++;testState.discount=d.payload.payments[0].discount_value;
  return {...d.payload,currency:'RUB',expire:Date.now()+300000};
 },
 setDiscountForUnAuth:async()=>{
  let c=JSON.parse(localStorage.getItem('wbx_default_discounts'));
  if(!c || c.expire<Date.now()){
   const r=await fetch('/test/v6/grade');
   if(!r.ok)return;
   const d=await r.json(); if(d.state!==0)return;
   c={wctype_id:1,discount_value:d.payload.payments[0].discount_value,expire:Date.now()+300000};
   localStorage.setItem('wbx_default_discounts',JSON.stringify(c));
  }
  testState.gradeCalls++;testState.discount=c?.discount_value??0;
 }
},helpers:{url:{urlProductStatic:id=>`https://basket-12.wbbasket.ru/vol1792/part179224/${id}/info/ru/card.json`},getCardImgName:({idx})=>idx},xnm:{
 getXnmProducts:async(ids,detail,a,b,c,d,signal)=>{
  let r;
  for(let attempt=0;attempt<5;attempt++){
   try{r=await fetch('/__internal/u-card/cards/v4/detail?curr=rub&nm='+ids[0],{signal});}
   catch(e){if(signal.aborted)throw e;continue;}
   if(r.ok)break;
  }
  if(!r?.ok)return {};
  const p=(await r.json()).products[0];
  for(const s of p.sizes){
   s.price.paymentDiscountAmount=Math.ceil(s.price.priceToShow/100*testState.discount/100);
   s.price.priceWithDiscount=1;
  }
  return {[p.id]:p};
 },
 getProductColorsByNmIdsAsync:async()=>({})
}};
</script></html>'''


@unittest.skipUnless(shutil.which('google-chrome-stable') or shutil.which('google-chrome'), 'requires Chrome')
class WildberriesBrowserTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.directory = TemporaryDirectory(prefix='wb-synthetic-')
        self.session = ChromeSession(self.directory.name, headless=True)
        self.client = AsyncWildberriesClient(self.directory.name, session=self.session, request_timeout=2)
        self.manager = self.client.collection_session()
        await self.manager.__aenter__()
        self.payload = json.loads(FIXTURE.read_text())['product']
        self.payload.pop('imageUrl', None)
        self.payload['id'] = int(self.payload['id'])
        self.payload['supplierId'] = int(self.payload['supplierId'])
        for s in self.payload['sizes']:
            s['optionId'] = int(s['optionId'])
            s['price'] = {'priceToShow': 105600, 'paymentDiscountAmount': 0}
        self.home = HOME
        self.grade_status = self.detail_status = 200
        self.grade_data = {'state':0, 'payload':{'payments':[{'wctype_id':1,'discount_value':3}]}}
        self.retry_after = '0'
        self.detail_type = 'application/json'
        self.detail_body = None
        self.counts = {'detail':0, 'grade':0}
        self.wait = None
        self.navigations = []
        await self.session.context.route('https://www.wildberries.ru/**', self.route)

    async def asyncTearDown(self):
        await self.manager.__aexit__(None,None,None)
        self.directory.cleanup()

    async def route(self, route):
        url=route.request.url
        if route.request.is_navigation_request():
            self.navigations.append(url)
            await route.fulfill(status=200,content_type='text/html',body=self.home)
        elif '/v6/grade' in url:
            self.counts['grade']+=1
            await route.fulfill(status=self.grade_status,content_type='application/json',body=json.dumps(self.grade_data))
        else:
            self.counts['detail']+=1
            if self.wait: await self.wait.wait()
            await route.fulfill(status=self.detail_status,content_type=self.detail_type,
                headers={'retry-after':self.retry_after},body=self.detail_body or json.dumps({'products':[self.payload]}))

    async def card(self):
        return await WildberriesConnector(self.client).get_product(REF)

    async def test_cold_then_fresh_cache_initializes_discount_and_one_price(self):
        self.assertEqual(str((await self.card()).price),'1024.00')
        self.assertEqual(str((await self.card()).price),'1024.00')
        self.assertEqual(self.counts, {'detail':2,'grade':1})
        self.assertEqual(self.navigations,['https://www.wildberries.ru/'])
        self.assertEqual(await self.client._transport.page.evaluate('__priceWatchWbRequests.size'),0)

    async def test_hundred_http_requests_admitted_and_101_waits(self):
        from urllib.parse import parse_qs, urlsplit
        entered, release = asyncio.Event(), asyncio.Event()
        original = self.route
        async def route(request):
            if '/cards/v4/detail' not in request.request.url:
                await original(request)
                return
            self.counts['detail'] += 1
            if self.counts['detail'] == 100:
                entered.set()
            await release.wait()
            payload = dict(self.payload, id=int(parse_qs(urlsplit(request.request.url).query)['nm'][0]))
            await request.fulfill(content_type='application/json', body=json.dumps({'products': [payload]}))
        await self.session.context.unroute('https://www.wildberries.ru/**', self.route)
        await self.session.context.route('https://www.wildberries.ru/**', route)
        tasks = [asyncio.create_task(self.client.fetch_product_async(str(1000+i))) for i in range(101)]
        try:
            await asyncio.wait_for(entered.wait(), 8)
            stats = await self.client._transport.page.evaluate('({active:__priceWatchWbNetwork.active.size,pending:__priceWatchWbNetwork.pending.size})')
            self.assertEqual(stats, {'active': 100, 'pending': 1})
            self.assertEqual(self.counts['detail'], 100)
        finally:
            release.set()
            results = await asyncio.gather(*tasks, return_exceptions=True)
        self.assertTrue(all(isinstance(r, dict) and 'product' in r for r in results), results)
        self.assertEqual(self.counts['detail'], 101)
        self.assertEqual(await self.client._transport.page.evaluate('__priceWatchWbNetwork.peak'), 100)

    async def test_cancel_metadata_request_keeps_other_article_alive(self):
        from urllib.parse import parse_qs, urlsplit
        self.home = HOME.replace('getProductColorsByNmIdsAsync:async()=>({})',
            "getProductColorsByNmIdsAsync:async ids=>{await fetch('https://basket-12.wbbasket.ru/vol1/part1/'+ids[0]+'/info/ru/card.json');return {};}")
        metadata_entered, metadata_release = asyncio.Event(), asyncio.Event()
        async def metadata(route):
            metadata_entered.set()
            await metadata_release.wait()
            try:
                await route.fulfill(content_type='application/json', body='{}')
            except Exception:
                pass  # The cancelled target has already aborted its request.
        await self.session.context.route('https://basket-12.wbbasket.ru/**', metadata)
        original = self.route
        async def detail(route):
            if '/cards/v4/detail' in route.request.url:
                payload = dict(self.payload, id=int(parse_qs(urlsplit(route.request.url).query)['nm'][0]))
                await route.fulfill(content_type='application/json', body=json.dumps({'products': [payload]}))
            else:
                await original(route)
        await self.session.context.unroute('https://www.wildberries.ru/**', self.route)
        await self.session.context.route('https://www.wildberries.ru/**', detail)
        first = asyncio.create_task(self.client.fetch_product_async('1001'))
        await asyncio.wait_for(metadata_entered.wait(), 5)
        second = asyncio.create_task(self.client.fetch_product_async('1002'))
        page = self.client._transport.page
        try:
            first.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await first
            self.assertFalse(page.is_closed())
            metadata_release.set()
            self.assertEqual((await second)['product']['id'], '1002')
        finally:
            metadata_release.set()
            for task in (first, second): task.cancel()
            await asyncio.gather(first, second, return_exceptions=True)

    async def test_native_sdk_timeout_does_not_include_pool_queue(self):
        from urllib.parse import parse_qs, urlsplit
        self.client._transport.max_in_flight_requests = 1
        self.home = HOME.replace("ids[0],{signal}", "ids[0],{signal:AbortSignal.timeout(30)}")
        first_entered, release = asyncio.Event(), asyncio.Event()
        original = self.route
        async def detail(route):
            if '/cards/v4/detail' not in route.request.url:
                await original(route)
                return
            article = parse_qs(urlsplit(route.request.url).query)['nm'][0]
            if article == '1001':
                first_entered.set()
                await release.wait()
            payload = dict(self.payload, id=int(article))
            await route.fulfill(content_type='application/json', body=json.dumps({'products': [payload]}))
        await self.session.context.unroute('https://www.wildberries.ru/**', self.route)
        await self.session.context.route('https://www.wildberries.ru/**', detail)
        first = asyncio.create_task(self.client.fetch_product_async('1001'))
        await asyncio.wait_for(first_entered.wait(), 5)
        second = asyncio.create_task(self.client.fetch_product_async('1002'))
        try:
            await asyncio.sleep(.1)  # Exceeds the native 30ms timeout while queued.
            self.assertFalse(first.done())
            self.assertFalse(second.done())
            release.set()
            results = await asyncio.gather(first, second)
            self.assertEqual([r['product']['id'] for r in results], ['1001', '1002'])
            self.assertGreater(await self.client._transport.page.evaluate('__priceWatchWbNetwork.queueMs'), 70)
        finally:
            release.set()
            for task in (first, second): task.cancel()
            await asyncio.gather(first, second, return_exceptions=True)

    async def test_same_article_sizes_share_io_and_keep_exact_prices(self):
        other = json.loads(json.dumps(self.payload['sizes'][0]))
        other.update(optionId=296499717, name='Second size')
        other['price']['priceToShow'] = 205600
        self.payload['sizes'].append(other)
        connector = WildberriesConnector(self.client)
        first, second = await asyncio.gather(connector.get_product(REF), connector.get_product('179224846:296499717'))
        self.assertEqual([str(c.price) for c in (first, second)], ['1024.00', '1994.00'])
        self.assertEqual(self.counts['detail'], 1)
        self.assertEqual([c.ref.external_id for c in (first, second)], [REF, '179224846:296499717'])
        self.assertEqual([[v.ref.external_id for v in c.variants if v.selected] for c in (first, second)], [[REF], ['179224846:296499717']])

    async def test_unsettled_native_helper_stops_instead_of_hanging(self):
        from marketplace_connector.domain.errors import UnsafeBrowserTeardown
        self.client._transport.request_timeout = .1
        self.home = HOME.replace('getProductColorsByNmIdsAsync:async()=>({})', 'getProductColorsByNmIdsAsync:async()=>new Promise(()=>{})')
        with self.assertRaises(UnsafeBrowserTeardown):
            await asyncio.wait_for(self.card(), 5)
        self.assertTrue(self.client._transport.page.is_closed())
        with self.assertRaises(UnsafeBrowserTeardown): await self.card()

    async def test_cancel_wallet_waiter_keeps_shared_bootstrap_for_other_article(self):
        entered, release = asyncio.Event(), asyncio.Event()
        original = self.route
        async def route(request):
            if '/v6/grade' in request.request.url:
                self.counts['grade'] += 1
                entered.set()
                await release.wait()
                await request.fulfill(content_type='application/json', body=json.dumps(self.grade_data))
            else:
                await original(request)
        await self.session.context.unroute('https://www.wildberries.ru/**', self.route)
        await self.session.context.route('https://www.wildberries.ru/**', route)
        self.detail_body = json.dumps({'products': [dict(self.payload, id=1002)]})
        first = asyncio.create_task(self.client.fetch_product_async('1001'))
        await asyncio.wait_for(entered.wait(), 5)
        second = asyncio.create_task(self.client.fetch_product_async('1002'))
        try:
            await asyncio.sleep(.02)
            first.cancel()
            with self.assertRaises(asyncio.CancelledError): await first
            self.assertFalse(self.client._transport.page.is_closed())
            self.assertEqual(self.counts['grade'], 1)
            release.set()
            self.assertEqual((await second)['product']['id'], '1002')
            self.assertEqual(self.counts['grade'], 1)
        finally:
            release.set()
            for task in (first, second): task.cancel()
            await asyncio.gather(first, second, return_exceptions=True)

    async def test_stale_cache_and_changed_percent(self):
        await self.card()
        await self.client._transport.page.evaluate("localStorage.setItem('wbx_default_discounts', JSON.stringify({wctype_id:1,discount_value:0,expire:1}))")
        self.grade_data['payload']['payments'][0]['discount_value']=5
        self.assertEqual(str((await self.card()).price),'1003.00')
        self.assertEqual(self.counts['grade'],2)

    async def test_authenticated_grade_does_not_call_unauth_setter(self):
        self.home=HOME.replace('auth:false','auth:true').replace("let c=JSON.parse", "throw Error('unauth setter called'); let c=JSON.parse")
        self.assertEqual(str((await self.card()).price),'1024.00')

    async def test_confirmed_zero_and_stock(self):
        self.grade_data['payload']['payments'][0]['discount_value']=0
        self.assertEqual(str((await self.card()).price),'1056.00')
        self.payload['sizes'][0]['stocks']=[]
        self.assertIsNone((await self.card()).price)

    async def test_grade_failure_does_not_use_ordinary(self):
        self.grade_status=503
        with self.assertRaises(MarketplaceUnavailable): await self.card()
        self.assertEqual(self.counts['detail'],0)

    async def test_malformed_grade_does_not_use_ordinary(self):
        self.grade_data={'state':0,'payload':{}}
        with self.assertRaises(MarketplaceSchemaChanged): await self.card()
        self.assertEqual(self.counts['detail'],0)

    async def test_bounded_native_retries(self):
        self.detail_status=503
        with self.assertRaises(MarketplaceUnavailable): await self.card()
        self.assertEqual(self.counts['detail'],3)

    async def test_long_retry_after_stops_native_retry(self):
        self.detail_status=429
        self.retry_after='60'
        with self.assertRaises(RateLimited): await self.card()
        self.assertEqual(self.counts['detail'],1)

    async def test_blocked_hidden_no_fake_price(self):
        for status in [403,498]:
            self.detail_status=status
            with self.assertRaisesRegex(MarketplaceUnavailable,'ручную проверку'): await self.card()
            self.assertLessEqual(self.counts['detail'],6)

    async def test_cancel_one_target_then_neighbor_succeeds(self):
        self.wait=asyncio.Event()
        task=asyncio.create_task(self.card())
        async with asyncio.timeout(5):
            while self.counts['detail']==0: await asyncio.sleep(.01)
        neighbor=asyncio.create_task(self.card())
        task.cancel()
        with self.assertRaises(asyncio.CancelledError): await task
        self.wait.set()
        self.assertEqual(str((await neighbor).price),'1024.00')
        self.assertIsNotNone(self.session._async_process)

    async def test_product_only_discovers_sizes_before_exact_price_collection(self):
        connector = WildberriesConnector(self.client)
        discovery = await connector.get_product(REF.split(':')[0])
        self.assertIsNone(discovery.price)
        self.assertEqual(discovery.ref.external_id, REF.split(':')[0])
        self.assertEqual(discovery.variants[0].ref.external_id, REF)
        self.assertEqual(str((await connector.get_product(REF)).price), '1024.00')
        self.assertEqual(self.counts['detail'], 2)

    async def test_http_timeout_leaves_page_reusable(self):
        self.wait=asyncio.Event()
        self.client._transport.request_timeout=.2
        with self.assertRaises(MarketplaceUnavailable): await self.card()
        self.assertFalse(self.client._transport.page.is_closed())
        self.wait.set()
        self.client._transport.request_timeout=2
        self.assertEqual(str((await self.card()).price),'1024.00')

    async def test_three_marketplaces_use_separate_pages_one_chrome(self):
        from marketplace_connector.connectors.ozon import AsyncOzonClient
        from marketplace_connector.connectors.aliexpress.client import AsyncAliExpressClient
        from tests.test_aliexpress_transport import RAW as ALI_RAW, REF as ALI_REF
        ozon=AsyncOzonClient(self.directory.name,session=self.session)
        ali=AsyncAliExpressClient(self.directory.name,session=self.session)
        async def ozon_route(route):
            if route.request.is_navigation_request():
                await route.fulfill(content_type='text/html',body='<html>storefront</html>')
            else:
                await route.fulfill(content_type='application/json',body='{"widgetStates":{"webProductHeading-1":{"title":"Synthetic Ozon"}}}')
        async def ali_route(route):
            if route.request.is_navigation_request():
                await route.fulfill(content_type='text/html',body='<html>storefront</html>')
            else:
                await route.fulfill(content_type='application/json',body=ALI_RAW)
        await self.session.context.route('https://www.ozon.ru/**',ozon_route)
        await self.session.context.route('https://aliexpress.ru/**',ali_route)
        process=self.session._async_process
        async with ozon.collection_session(), ali.collection_session():
            self.assertEqual(self.session._users,3)
            result=await asyncio.gather(self.card(),ozon.fetch_product_async('123'),ali.fetch_product_async(ALI_REF))
            self.assertEqual(str(result[0].price),'1024.00')
            self.assertEqual(len({id(c._transport.page) for c in (self.client,ozon,ali)}),3)
            self.assertIs(self.session._async_process,process)
        self.assertEqual(self.session._users,1)
        self.assertEqual(str((await self.card()).price),'1024.00')

    async def test_html_and_duplicate_products_are_schema_errors(self):
        self.detail_type='text/html'
        self.detail_body='<html>blocked</html>'
        with self.assertRaises(MarketplaceSchemaChanged): await self.card()
        self.detail_type='application/json'
        self.detail_body=json.dumps({'products':[self.payload,self.payload]})
        with self.assertRaises(MarketplaceSchemaChanged): await self.card()

    async def test_visible_manual_recovery_is_bounded_and_profile_stays(self):
        self.detail_status=403
        self.session.headless=False
        async def confirm(*args): self.detail_status=200
        self.client.challenge_handler=type('Handler',(),{'handle_async':AsyncMock(side_effect=confirm)})()
        self.assertEqual(str((await self.card()).price),'1024.00')
        self.client.challenge_handler.handle_async.assert_awaited_once()
        self.assertEqual(self.counts['detail'],2)

    async def test_retry_after_cooldown_applies_to_native_retry(self):
        self.detail_status=429
        self.retry_after='1'
        original=self.route
        async def routed(route):
            if self.counts['detail']==1: self.detail_status=200
            await original(route)
        await self.session.context.unroute('https://www.wildberries.ru/**',self.route)
        await self.session.context.route('https://www.wildberries.ru/**',routed)
        start=asyncio.get_running_loop().time()
        self.assertEqual(str((await self.card()).price),'1024.00')
        self.assertGreaterEqual(asyncio.get_running_loop().time()-start,1)
        self.assertEqual(self.counts['detail'],2)

    async def test_runtime_globals_precede_profile_initialization(self):
        self.home=HOME.replace('earlyFailures:0','earlyFailures:2')
        self.assertEqual(str((await self.card()).price),'1024.00')
        self.assertEqual(await self.client._transport.page.evaluate('testState.xinfoCalls'),3)
        self.assertEqual(self.counts['detail'],1)

    async def test_image_url_uses_native_routing_and_article_photo(self):
        card = await self.card()
        self.assertEqual(card.image_url, 'https://basket-12.wbbasket.ru/vol1792/part179224/179224846/images/big/1.webp')
        self.assertTrue(all(v.image_url == card.image_url for v in card.variants))
        self.payload['pics'] = 0
        card = await self.card()
        self.assertIsNone(card.image_url)
        self.assertEqual(str(card.price), '1024.00')

    async def test_optional_image_helper_failure_does_not_fail_price(self):
        self.home = HOME.replace('getCardImgName:({idx})=>idx', "getCardImgName:()=>{throw Error('photo unavailable')}")
        card = await self.card()
        self.assertIsNone(card.image_url)
        self.assertEqual(str(card.price), '1024.00')

    async def test_unsettled_profile_helpers_fail_closed_for_every_waiter(self):
        from marketplace_connector.domain.errors import UnsafeBrowserTeardown
        self.client._transport.request_timeout = .1
        for helper in ('getXinfo', 'getUserGrade', 'setDiscountForUnAuth'):
            with self.subTest(helper=helper):
                # Each subcase owns a fresh page but the same isolated Chrome.
                if self.client._transport._failure:
                    await self.client._transport.close()
                    from marketplace_connector.connectors.wildberries.transport import WildberriesTransport
                    self.client._transport = WildberriesTransport(self.session.context,
                        self.client._prepare_storefront, request_timeout=.1)
                self.home = HOME
                self.home = self.home.replace('</script>',
                    f"window.wb.user.{helper}=()=>new Promise(()=>{{}});</script>")
                tasks = [asyncio.create_task(self.client.fetch_product_async(str(i))) for i in (1001, 1002)]
                results = await asyncio.wait_for(asyncio.gather(*tasks, return_exceptions=True), 5)
                self.assertTrue(all(isinstance(r, UnsafeBrowserTeardown) for r in results), results)
                self.assertTrue(self.client._transport.page.is_closed())
                self.assertEqual(self.client._transport._wallet_users, {})
                requests = dict(self.counts)
                await asyncio.sleep(.15)
                self.assertEqual(self.counts, requests)

    async def test_profile_generations_do_not_accumulate_in_sequential_collection(self):
        for _ in range(12):
            self.assertEqual(str((await self.card()).price), '1024.00')
            self.assertEqual(self.client._transport._wallet_users, {})
            self.assertLessEqual(len(self.client._transport._profiles), 1)

    async def test_old_profile_failure_is_not_replaced_by_new_profile(self):
        from urllib.parse import parse_qs, urlsplit
        entered, release = asyncio.Event(), asyncio.Event()
        original = self.route
        async def route(request):
            if '/cards/v4/detail' not in request.request.url:
                await original(request)
                return
            article = parse_qs(urlsplit(request.request.url).query)['nm'][0]
            if article == '1001':
                entered.set()
                await release.wait()
            payload = dict(self.payload, id=int(article))
            await request.fulfill(content_type='application/json', body=json.dumps({'products': [payload]}))
        await self.session.context.unroute('https://www.wildberries.ru/**', self.route)
        await self.session.context.route('https://www.wildberries.ru/**', route)
        first = asyncio.create_task(self.client.fetch_product_async('1001'))
        try:
            await asyncio.wait_for(entered.wait(), 5)
            self.assertEqual(len(self.client._transport._profiles), 1)
            old = self.client._transport._profile
            old.fatal = MarketplaceSchemaChanged('old profile inspection failed')
            second = await self.client.fetch_product_async('1002')
            self.assertEqual(second['product']['id'], '1002')
            self.assertEqual(len(self.client._transport._profiles), 2)
            release.set()
            with self.assertRaisesRegex(MarketplaceSchemaChanged, 'old profile'):
                await first
            self.assertEqual(len(self.client._transport._profiles), 1)
        finally:
            release.set()
            first.cancel()
            await asyncio.gather(first, return_exceptions=True)

    async def test_wallet_http_queue_wait_does_not_expire_bootstrap_watchdog(self):
        from urllib.parse import parse_qs, urlsplit
        transport = self.client._transport
        transport.max_in_flight_requests = 1
        transport.request_timeout = .5
        first_entered = asyncio.Event()
        original = self.route
        async def route(request):
            if '/cards/v4/detail' not in request.request.url:
                await original(request)
                return
            article = parse_qs(urlsplit(request.request.url).query)['nm'][0]
            first_entered.set()
            await asyncio.sleep(.3)
            payload = dict(self.payload, id=int(article))
            await request.fulfill(content_type='application/json', body=json.dumps({'products': [payload]}))
        await self.session.context.unroute('https://www.wildberries.ru/**', self.route)
        await self.session.context.route('https://www.wildberries.ru/**', route)
        tasks = [asyncio.create_task(self.client.fetch_product_async('1001'))]
        try:
            await asyncio.wait_for(first_entered.wait(), 5)
            tasks.append(asyncio.create_task(self.client.fetch_product_async('1002')))
            await transport.page.wait_for_function("[...__priceWatchWbNetwork.pending].some(r=>r.article==='1002')")
            await transport.page.evaluate("localStorage.removeItem('wbx_default_discounts')")
            tasks.append(asyncio.create_task(self.client.fetch_product_async('1003')))
            results = await asyncio.wait_for(asyncio.gather(*tasks), 8)
            self.assertEqual([r['product']['id'] for r in results], ['1001', '1002', '1003'])
            self.assertEqual(self.counts['grade'], 2)
            self.assertFalse(transport.page.is_closed())
        finally:
            for task in tasks: task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
