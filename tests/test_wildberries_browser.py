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
},xnm:{
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
        self.client = AsyncWildberriesClient(self.directory.name, session=self.session, request_timeout=2, starts_per_second=100)
        self.manager = self.client.collection_session()
        await self.manager.__aenter__()
        self.payload = json.loads(FIXTURE.read_text())['product']
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

    async def test_legacy_fails_before_network(self):
        with self.assertRaisesRegex(InvalidProductId,'Не указан размер'):
            await self.client.fetch_product_async('179224846')
        self.assertEqual(self.navigations,[])

    async def test_timeout_closes_only_wb_page_and_next_target_recovers(self):
        self.wait=asyncio.Event()
        self.client._transport.request_timeout=.2
        with self.assertRaises(MarketplaceUnavailable): await self.card()
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
