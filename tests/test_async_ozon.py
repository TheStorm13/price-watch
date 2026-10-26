import asyncio
import json
import subprocess
import unittest
from contextlib import asynccontextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import AsyncMock, MagicMock, patch

from marketplace_connector.connectors.ozon import AsyncOzonClient
from marketplace_connector.domain.errors import MarketplaceUnavailable


class AsyncOzonClientTests(unittest.IsolatedAsyncioTestCase):
    async def test_bootstrap_accepts_an_automatically_resolved_challenge(self):
        with TemporaryDirectory() as directory:
            client = AsyncOzonClient(directory)
            page = MagicMock(url='https://www.ozon.ru/')
            page.goto = AsyncMock(return_value=MagicMock(status=403))
            with (patch.object(client, '_is_antibot_page_async', AsyncMock(return_value=True)),
                  patch.object(client, '_wait_for_antibot_async', AsyncMock(return_value=True)),
                  patch.object(client, '_handle_antibot_async', AsyncMock()) as handle):
                await client._prepare_storefront(page)
            handle.assert_not_awaited()

    async def test_cancelled_collection_closes_browser_and_profile_process(self):
        with TemporaryDirectory() as directory:
            client = AsyncOzonClient(directory, virtual_display=True)
            browser = MagicMock()
            browser.close = AsyncMock()
            process = MagicMock()
            process.poll.return_value = None
            entered = asyncio.Event()

            @asynccontextmanager
            async def fake_playwright():
                yield MagicMock()

            async def fake_launch(_playwright):
                client.session._async_context = MagicMock()
                client.session._async_browser = browser
                client.session._async_process = process

            async def collect_until_cancelled():
                async with client.collection_session():
                    entered.set()
                    await asyncio.Event().wait()

            async def immediate_to_thread(function, *args, **kwargs):
                return function(*args, **kwargs)

            with (
                patch("marketplace_connector.browser.session.async_playwright", fake_playwright),
                patch.object(client.session, "_launch_async_context", side_effect=fake_launch),
                patch("marketplace_connector.browser.session.asyncio.to_thread", immediate_to_thread),
                patch("marketplace_connector.browser.session.request_browser_close", new_callable=AsyncMock) as close_browser,
            ):
                task = asyncio.create_task(collect_until_cancelled())
                await entered.wait()
                task.cancel()
                with self.assertRaises(asyncio.CancelledError):
                    await task

            browser.close.assert_awaited_once()
            close_browser.assert_awaited_once_with(browser)
            process.terminate.assert_not_called()
            process.wait.assert_called_once_with(timeout=5)
            process.kill.assert_not_called()
            self.assertIsNone(client.session._async_process)
            self.assertIsNone(client.session._async_playwright)

    async def test_browser_cleanup_kills_process_that_ignores_terminate(self):
        with TemporaryDirectory() as directory:
            client = AsyncOzonClient(directory)
            process = MagicMock()
            process.poll.return_value = None
            process.wait.side_effect = [subprocess.TimeoutExpired("chrome", 5), subprocess.TimeoutExpired("chrome", 3), 0]
            client.session._async_process = process

            async def immediate_to_thread(function, *args, **kwargs):
                return function(*args, **kwargs)

            with patch("marketplace_connector.browser.session.asyncio.to_thread", immediate_to_thread):
                await client.session._close_async_context()

            process.terminate.assert_called_once()
            process.kill.assert_called_once()
            self.assertEqual(process.wait.call_count, 3)
            self.assertIsNone(client.session._async_process)

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
            async def immediate_to_thread(function, *args, **kwargs):
                return function(*args, **kwargs)
            with patch("marketplace_connector.browser.profile_lifecycle.http.client.HTTPConnection",
                       return_value=Connection()), patch(
                           "marketplace_connector.browser.profile_lifecycle.asyncio.to_thread",
                           immediate_to_thread,
                       ):
                await client.session._close_open_profile_browser(playwright)

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
            async def immediate_to_thread(function, *args, **kwargs):
                return function(*args, **kwargs)
            with patch("marketplace_connector.browser.profile_lifecycle.http.client.HTTPConnection",
                       return_value=connection), patch(
                           "marketplace_connector.browser.profile_lifecycle.asyncio.to_thread",
                           immediate_to_thread,
                       ):
                await AsyncOzonClient(directory, virtual_display=True).session._close_open_profile_browser(playwright)
            playwright.chromium.connect_over_cdp.assert_not_called()

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
            client.session._async_process = MagicMock()
            with patch.object(client, "_is_antibot_page_async", new_callable=AsyncMock, return_value=True):
                with self.assertRaisesRegex(MarketplaceUnavailable, "Откройте Chrome"):
                    await client._handle_antibot_async(MagicMock(), "100")
            handler.handle_async.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
