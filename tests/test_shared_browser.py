"""Shared Chrome ownership and actual Ali fetch with intercepted synthetic data."""
import asyncio
import json
import shutil
import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import AsyncMock, MagicMock, patch
from marketplace_connector.browser.session import ChromeSession
from marketplace_connector.connectors.ozon import AsyncOzonClient
from marketplace_connector.connectors.aliexpress.client import AsyncAliExpressClient
from marketplace_connector.connectors.aliexpress.json_transport import HOME_URL, API_PATH
from marketplace_connector.domain.errors import MarketplaceUnavailable
from tests.test_aliexpress_transport import RAW, REF


class SharedOwnershipTests(unittest.IsolatedAsyncioTestCase):
    async def test_failed_acquire_has_no_owner_and_can_retry(self):
        session = ChromeSession('/tmp/unused-shared-session')
        manager = MagicMock(__aenter__=AsyncMock(return_value=MagicMock()), __aexit__=AsyncMock())
        async def launch(pw): session._async_context=MagicMock()
        with (patch('marketplace_connector.browser.session.async_playwright', return_value=manager),
              patch.object(session,'_launch_async_context',side_effect=RuntimeError('launch failed'))):
            with self.assertRaises(RuntimeError): await session.acquire()
        self.assertEqual(session._users,0)
        self.assertIsNone(session._playwright_manager)
        with (patch('marketplace_connector.browser.session.async_playwright', return_value=manager),
              patch.object(session,'_launch_async_context',side_effect=launch),
              patch.object(session,'_close_async_context',new_callable=AsyncMock) as close):
            await session.acquire()
            await session.acquire()
            await session.release()
            close.assert_not_awaited()
            await session.release()
            close.assert_awaited_once()

    async def test_two_marketplaces_serialize_manual_checks(self):
        session = ChromeSession('/tmp/unused-shared-session')
        active=peak=0
        async def handle(marketplace,message):
            nonlocal active,peak
            active+=1;peak=max(peak,active)
            await asyncio.sleep(.01)
            active-=1
        handler=MagicMock(handle_async=AsyncMock(side_effect=handle))
        clients=[AsyncOzonClient(session.profile_dir,session=session,challenge_handler=handler),
                 AsyncAliExpressClient(session.profile_dir,session=session,challenge_handler=handler)]
        pages=[MagicMock(reload=AsyncMock(return_value=MagicMock(status=200))) for _ in clients]
        with (patch.object(clients[0],'_wait_for_antibot_async',AsyncMock(return_value=True)),
              patch.object(clients[1],'_wait_for_antibot_async',AsyncMock(return_value=True))):
            await asyncio.gather(*(client._handle_antibot_async(page,'test',force=True) for client,page in zip(clients,pages)))
        self.assertEqual(peak,1)
        self.assertEqual({call.args[0] for call in handler.handle_async.await_args_list},{'ozon','aliexpress'})

    async def test_hidden_and_failed_manual_check(self):
        for hidden in [True,False]:
            client=AsyncAliExpressClient('/tmp/unused-shared-session',headless=hidden)
            client.challenge_handler=MagicMock(handle_async=AsyncMock())
            page=MagicMock(reload=AsyncMock(return_value=MagicMock(status=429)))
            with patch.object(client,'_wait_for_antibot_async',AsyncMock(return_value=False)):
                with self.assertRaises(MarketplaceUnavailable): await client._handle_antibot_async(page,'test',force=True)
            self.assertEqual(client.challenge_handler.handle_async.await_count,0 if hidden else 1)


class ManualCancellationTests(unittest.IsolatedAsyncioTestCase):
    async def test_cancel_manual_wait_releases_shared_lock(self):
        session = ChromeSession('/tmp/unused-manual-cancel')
        entered = asyncio.Event()
        async def handle(*args):
            entered.set()
            await asyncio.Event().wait()
        client = AsyncAliExpressClient(session.profile_dir, session=session,
            challenge_handler=MagicMock(handle_async=AsyncMock(side_effect=handle)))
        task = asyncio.create_task(client._handle_antibot_async(MagicMock(), 'test', force=True))
        await asyncio.wait_for(entered.wait(), 1)
        self.assertTrue(session.challenge_lock.locked())
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.assertFalse(session.challenge_lock.locked())


@unittest.skipUnless(shutil.which('google-chrome-stable') or shutil.which('google-chrome'),'requires Chrome')
class SharedBrowserTests(unittest.IsolatedAsyncioTestCase):
    async def test_actual_fetch_shared_owner_cancel_timeout_and_cookie_restart(self):
        with TemporaryDirectory(prefix='price-watch-ali-browser-') as directory:
            session=ChromeSession(directory,headless=True)
            ozon=AsyncOzonClient(directory,session=session)
            ali=AsyncAliExpressClient(directory,session=session,max_in_flight_requests=5,max_attempts=1,request_timeout=3)
            requests=[]
            five,release=asyncio.Event(),asyncio.Event()
            async with ozon.collection_session():
                process=session._async_process
                async with ali.collection_session():
                    self.assertIs(session._async_process,process)
                    context=session.context
                    await context.add_cookies([dict(name='synthetic_session',value='test-only',url=HOME_URL,expires=time.time()+3600)])
                    async def route_request(route):
                        request=route.request
                        if request.is_navigation_request():
                            self.assertEqual(request.url,HOME_URL)
                            await route.fulfill(status=200,content_type='text/html',body='<html>storefront</html>')
                            return
                        self.assertIn(API_PATH,request.url)
                        headers=await request.all_headers()
                        requests.append(headers)
                        if len(requests)==5:five.set()
                        await release.wait()
                        await route.fulfill(status=200,content_type='application/json',body=RAW)
                    await context.route('https://aliexpress.ru/**',route_request)
                    async def ozon_route(route):
                        if route.request.is_navigation_request():
                            self.assertEqual(route.request.url, 'https://www.ozon.ru/')
                            await route.fulfill(status=200, content_type='text/html', body='<html>storefront</html>')
                        else:
                            await release.wait()
                            await route.fulfill(status=200, content_type='application/json',
                                body='{"widgetStates":{"webProductHeading-1":{"title":"Synthetic Ozon"}}}')
                    await context.route('https://www.ozon.ru/**', ozon_route)
                    ozon_task = asyncio.create_task(ozon.fetch_product_async('1604900984'))
                    tasks=[asyncio.create_task(ali.fetch_product_async(REF)) for _ in range(5)]
                    await asyncio.wait_for(five.wait(),5)
                    tasks[0].cancel()
                    with self.assertRaises(asyncio.CancelledError): await tasks[0]
                    release.set()
                    results=await asyncio.gather(*tasks[1:])
                    self.assertEqual((await ozon_task).card.ref.external_id, '1604900984')
                    self.assertIsNot(ozon._transport.page, ali._transport.page)
                    self.assertTrue(all(result.raw_text==RAW for result in results))
                    self.assertTrue(all('synthetic_session=test-only' in r.get('cookie','') for r in requests))
                    self.assertEqual(ali._transport.page.url,HOME_URL)
                    self.assertEqual(await ali._transport.page.evaluate('globalThis.__priceWatchRequests.size'),0)
                    release.clear()
                    ali._transport.request_timeout=.03
                    with self.assertRaisesRegex(MarketplaceUnavailable,'Таймаут'): await ali.fetch_product_async(REF)
                    release.set()
                self.assertIs(session._async_process,process)
                self.assertEqual(session._users,1)
            self.assertIsNone(session._async_process)
            preferences=json.loads((Path(directory)/'Default/Preferences').read_text())
            self.assertEqual(preferences['profile']['exit_type'],'Normal')
            async with session.collection_session():
                cookies=await session.context.cookies(HOME_URL)
                self.assertTrue(any(c['name']=='synthetic_session' for c in cookies))

class FourMarketplaceOwnershipTests(unittest.IsolatedAsyncioTestCase):
    async def test_builder_gives_four_adapters_one_owner(self):
        from marketplace_connector.connectors.builder import build_connectors
        registry = build_connectors(['ozon','aliexpress','wildberries','yandex-market'], profile_dir='/tmp/unused-three-owner')
        clients = [registry.get(name)._client for name in ['ozon','aliexpress','wildberries','yandex-market']]
        self.assertTrue(all(client.session is clients[0].session for client in clients))
        self.assertTrue(all(client.session.challenge_lock is clients[0].session.challenge_lock for client in clients))
