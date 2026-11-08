"""Production browser fetch bridge: full bodies, 100/101 admission, cancellation."""
import asyncio
import json
import shutil
import unittest
from tempfile import TemporaryDirectory
from unittest.mock import AsyncMock

from marketplace_connector.browser.session import ChromeSession
from marketplace_connector.connectors.ozon.json_transport import OzonJsonTransport
from marketplace_connector.connectors.aliexpress.json_transport import AliExpressJsonTransport
from tests.test_ozon_json_transport import product_text
from tests.test_aliexpress_transport import RAW, REF


@unittest.skipUnless(shutil.which('google-chrome-stable') or shutil.which('google-chrome'), 'requires Chrome')
class RequestPoolsBrowserTests(unittest.IsolatedAsyncioTestCase):
    async def test_hundred_streaming_bodies_hold_permits_cancel_admits_101(self):
        with TemporaryDirectory(prefix='request-pool-synthetic-') as directory:
            session = ChromeSession(directory, headless=True)
            async with session.collection_session() as context:
                for cls, ref, raw in ((OzonJsonTransport, '1', product_text()), (AliExpressJsonTransport, REF, RAW)):
                    with self.subTest(transport=cls.__name__):
                        transport = cls(context, AsyncMock(), max_attempts=1, request_timeout=10)
                        await transport._start()
                        transport._bootstrap = asyncio.create_task(asyncio.sleep(0))
                        await transport.page.evaluate('''raw => {
                            globalThis.synthetic = {started: 0, bodies: new Map()};
                            globalThis.fetch = async (url, {signal}) => {
                                const id = ++synthetic.started;
                                const stream = new ReadableStream({start(controller) {
                                    synthetic.bodies.set(id, () => {controller.enqueue(new TextEncoder().encode(raw)); controller.close();});
                                    signal.addEventListener('abort', () => controller.error(new DOMException('Aborted', 'AbortError')), {once:true});
                                }});
                                const response = new Response(stream, {headers:{'content-type':'application/json'}});
                                Object.defineProperty(response, 'url', {value:url});
                                return response;
                            };
                        }''', raw)
                        tasks = [asyncio.create_task(transport.fetch(ref)) for _ in range(101)]
                        try:
                            await transport.page.wait_for_function('synthetic.started === 100', timeout=8000)
                            self.assertEqual(transport.pool.in_flight, 100)
                            self.assertEqual(transport.pool.pending, 1)
                            self.assertTrue(all(not task.done() for task in tasks))
                            tasks[0].cancel()
                            with self.assertRaises(asyncio.CancelledError): await tasks[0]
                            await transport.page.wait_for_function('synthetic.started === 101', timeout=3000)
                            self.assertEqual(transport.pool.in_flight, 100)
                            await transport.page.evaluate('''() => {
                                for (const [id, release] of synthetic.bodies) if (id !== 1) release();
                            }''')
                            self.assertEqual(await asyncio.gather(*tasks[1:]), [raw] * 100)
                            self.assertEqual(transport.pool.in_flight, 0)
                        finally:
                            for task in tasks: task.cancel()
                            await asyncio.gather(*tasks, return_exceptions=True)
                            await transport.close()
