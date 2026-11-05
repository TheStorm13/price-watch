"""Run the actual fetch JavaScript against intercepted, synthetic Ozon routes.

No Ozon network traffic or real user profile is used.
"""
import asyncio
import json
import shutil
import unittest
from tempfile import TemporaryDirectory
from urllib.parse import parse_qs, urlsplit

from marketplace_connector.connectors.ozon.async_client import AsyncOzonClient
from marketplace_connector.connectors.ozon.json_transport import API_PATH, HOME_URL
from marketplace_connector.domain.errors import MarketplaceUnavailable


@unittest.skipUnless(shutil.which('google-chrome-stable') or shutil.which('google-chrome'), 'requires system Google Chrome')
class FetchBrowserTests(unittest.IsolatedAsyncioTestCase):
    async def test_real_fetch_parallelism_credentials_raw_timeout_and_individual_abort(self):
        with TemporaryDirectory(prefix='price-watch-fetch-test-') as directory:
            client = AsyncOzonClient(directory, headless=True, request_timeout=3, max_attempts=1)
            async with client.collection_session():
                context = client.session._async_context
                await context.add_cookies([{'name': 'synthetic_session', 'value': 'test-only', 'url': HOME_URL}])
                entered = asyncio.Event()
                release = asyncio.Event()
                requests = []
                async def route_request(route):
                    request = route.request
                    if urlsplit(request.url).path != API_PATH:
                        await route.fulfill(status=200, content_type='text/html', body='<html>storefront</html>')
                        return
                    path = parse_qs(urlsplit(request.url).query)['url'][0]
                    self.assertEqual(parse_qs(urlsplit(path).query), {'oos_search': ['false']})
                    sku = path.split('/')[2]
                    headers = await request.all_headers()
                    requests.append((sku, request.method, headers.get('cookie', '')))
                    if len(requests) == 5:
                        entered.set()
                    if sku in ('90', '91'):
                        await asyncio.sleep(.7)
                    else:
                        await release.wait()
                    body = ' {"widgetStates":{"webProductHeading-1":{"title":"synthetic"}}}\n'
                    await route.fulfill(status=200, content_type='application/json', body=body)
                await context.route('https://www.ozon.ru/**', route_request)
                tasks = [asyncio.create_task(client.fetch_raw_text_async(str(i))) for i in range(5)]
                await asyncio.wait_for(entered.wait(), 5)
                self.assertFalse(any(task.done() for task in tasks))
                tasks[0].cancel()
                with self.assertRaises(asyncio.CancelledError):
                    await tasks[0]
                release.set()
                results = await asyncio.gather(*tasks[1:])
                self.assertEqual(len(set(results)), 1)
                self.assertTrue(results[0].startswith(' {') and results[0].endswith('\n'))
                self.assertTrue(all(method == 'GET' and 'synthetic_session=test-only' in cookie for _, method, cookie in requests))
                page = client._transport.page
                self.assertEqual(page.url, HOME_URL)
                self.assertEqual(await page.evaluate('globalThis.__priceWatchRequests.size'), 0)
                # Use a full-sized timer for the parallel bootstrap; shorten only
                # after the independent cancellation and metadata checks above.
                client._transport.request_timeout = .03
                with self.assertRaisesRegex(MarketplaceUnavailable, 'Таймаут'):
                    await client.fetch_raw_text_async('90')
                self.assertEqual(await page.evaluate('globalThis.__priceWatchRequests.size'), 0)
                client._transport.request_timeout = 3
                self.assertEqual(json.loads(await client.fetch_raw_text_async('92'))['widgetStates']['webProductHeading-1']['title'], 'synthetic')
