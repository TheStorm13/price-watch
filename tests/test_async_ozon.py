import asyncio
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import AsyncMock, MagicMock, patch

from marketplace_connector.connectors.ozon import AsyncOzonClient
from marketplace_connector.domain.errors import MarketplaceUnavailable


class AsyncOzonClientTests(unittest.IsolatedAsyncioTestCase):
    async def test_background_collection_closes_open_profile_browser(self):
        with TemporaryDirectory() as directory:
            Path(directory, "DevToolsActivePort").write_text(
                "19222\n/devtools/browser/app-profile\n"
            )
            client = AsyncOzonClient(directory, virtual_display=True)
            alive = True

            class Connection:
                def request(self, *_args):
                    if not alive:
                        raise OSError("Chrome closed")

                def getresponse(self):
                    response = MagicMock(status=200)
                    response.read.return_value = json.dumps({
                        "webSocketDebuggerUrl":
                            "ws://127.0.0.1:19222/devtools/browser/app-profile"
                    }).encode()
                    return response

                def close(self):
                    pass

            async def close_browser(_command):
                nonlocal alive
                alive = False

            session = MagicMock()
            session.send = AsyncMock(side_effect=close_browser)
            browser = MagicMock()
            browser.new_browser_cdp_session = AsyncMock(return_value=session)
            browser.close = AsyncMock()
            playwright = MagicMock()
            playwright.chromium.connect_over_cdp = AsyncMock(return_value=browser)
            with patch("marketplace_connector.connectors.ozon.async_client.http.client.HTTPConnection",
                       return_value=Connection()):
                await client._close_open_profile_browser(playwright)

            session.send.assert_awaited_once_with("Browser.close")
            browser.close.assert_awaited_once()

    async def test_stale_debug_port_does_not_close_another_browser(self):
        with TemporaryDirectory() as directory:
            Path(directory, "DevToolsActivePort").write_text(
                "19222\n/devtools/browser/app-profile\n"
            )
            response = MagicMock(status=200)
            response.read.return_value = json.dumps({
                "webSocketDebuggerUrl": "ws://127.0.0.1:19222/devtools/browser/other"
            }).encode()
            connection = MagicMock()
            connection.getresponse.return_value = response
            playwright = MagicMock()
            with patch("marketplace_connector.connectors.ozon.async_client.http.client.HTTPConnection",
                       return_value=connection):
                await AsyncOzonClient(directory, virtual_display=True)._close_open_profile_browser(playwright)
            playwright.chromium.connect_over_cdp.assert_not_called()

    async def test_concurrent_products_use_separate_pages_in_one_context(self):
        with TemporaryDirectory() as directory:
            client = AsyncOzonClient(directory)
            context = MagicMock()
            pages = [MagicMock(), MagicMock()]
            for page in pages:
                page.goto = AsyncMock()
                page.close = AsyncMock()
            context.new_page = AsyncMock(side_effect=pages)
            client._async_context = context
            with (
                patch.object(client, "_is_antibot_page_async", new_callable=AsyncMock, return_value=False),
                patch.object(client, "_fetch_json_in_page_async", new_callable=AsyncMock, return_value='{"widgetStates":{}}'),
            ):
                results = await asyncio.gather(
                    client.fetch_raw_text_async("100"),
                    client.fetch_raw_text_async("200"),
                )

            self.assertEqual(results, ['{"widgetStates":{}}'] * 2)
            self.assertEqual(context.new_page.await_count, 2)
            for page in pages:
                page.goto.assert_awaited_once()
                page.close.assert_awaited_once()

    async def test_challenges_are_presented_one_at_a_time(self):
        class Handler:
            def __init__(self):
                self.active = 0
                self.peak = 0
                self.messages = []

            async def handle_async(self, marketplace, message):
                self.active += 1
                self.peak = max(self.peak, self.active)
                self.messages.append(message)
                await asyncio.sleep(0.01)
                self.active -= 1

        with TemporaryDirectory() as directory:
            handler = Handler()
            client = AsyncOzonClient(directory, challenge_handler=handler)
            client._challenge_lock = asyncio.Lock()
            pages = [MagicMock(), MagicMock()]
            for page in pages:
                page.reload = AsyncMock()
            with (
                patch.object(client, "_is_antibot_page_async", new_callable=AsyncMock, return_value=True),
                patch.object(client, "_wait_for_antibot_async", new_callable=AsyncMock, return_value=True),
            ):
                await asyncio.gather(
                    client._handle_antibot_async(pages[0], "100"),
                    client._handle_antibot_async(pages[1], "200"),
                )

            self.assertEqual(handler.peak, 1)
            self.assertEqual(len(handler.messages), 2)
            self.assertIn("100", handler.messages[0])
            self.assertIn("200", handler.messages[1])

    async def test_headless_challenge_reports_action_instead_of_waiting_forever(self):
        with TemporaryDirectory() as directory:
            handler = MagicMock()
            handler.handle_async = AsyncMock()
            client = AsyncOzonClient(directory, challenge_handler=handler, headless=True)
            client._challenge_lock = asyncio.Lock()
            client._async_process = MagicMock()
            with patch.object(client, "_is_antibot_page_async", new_callable=AsyncMock, return_value=True):
                with self.assertRaisesRegex(MarketplaceUnavailable, "Откройте Chrome"):
                    await client._handle_antibot_async(MagicMock(), "100")
            handler.handle_async.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
