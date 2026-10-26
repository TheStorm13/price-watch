"""Chrome profile smoke test; it never contacts Ozon or opens the user profile."""

import asyncio
import http.client
import json
import os
import shutil
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from playwright.async_api import async_playwright

from marketplace_connector.connectors.ozon import AsyncOzonClient
from marketplace_connector.browser.profile_lifecycle import _profile_lock_is_live


CHROME = shutil.which("google-chrome-stable") or shutil.which("google-chrome")


class ProfileLockTests(unittest.TestCase):
    def test_waits_for_live_chrome_lock_and_ignores_stale_lock(self):
        with TemporaryDirectory() as directory:
            lock = Path(directory) / "SingletonLock"
            lock.symlink_to(f"host-{os.getpid()}")
            self.assertTrue(_profile_lock_is_live(Path(directory)))
            lock.unlink()
            lock.symlink_to("host-99999999")
            self.assertFalse(_profile_lock_is_live(Path(directory)))


@unittest.skipUnless(CHROME, "requires system Google Chrome")
class ProfileLifecycleTests(unittest.IsolatedAsyncioTestCase):
    async def test_worker_closes_its_chrome_cleanly(self):
        with TemporaryDirectory(prefix="price-watch-worker-profile-test-") as directory:
            profile = Path(directory)
            client = AsyncOzonClient(profile, headless=True)
            async with client.collection_session():
                self.assertIsNotNone(client.session._async_context)
            preferences = json.loads((profile / "Default/Preferences").read_text())
            self.assertEqual(preferences["profile"]["exit_type"], "Normal")

    async def _launch(self, profile: Path) -> tuple[subprocess.Popen, str]:
        process = subprocess.Popen(
            [
                CHROME,
                "--headless=new",
                "--remote-debugging-port=0",
                f"--user-data-dir={profile}",
                "--no-first-run",
                "about:blank",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            for _ in range(100):
                port_file = profile / "DevToolsActivePort"
                if port_file.is_file():
                    port = port_file.read_text().splitlines()[0]
                    connection = http.client.HTTPConnection("127.0.0.1", int(port), timeout=0.2)
                    try:
                        connection.request("GET", "/json/version")
                        if connection.getresponse().status == 200:
                            return process, port
                    except OSError:
                        pass
                    finally:
                        connection.close()
                if process.poll() is not None:
                    raise AssertionError(f"Chrome exited before opening CDP: {process.returncode}")
                await asyncio.sleep(0.1)
            raise AssertionError("Chrome did not open CDP")
        except BaseException:
            process.kill()
            process.wait(timeout=5)
            raise

    async def test_cookie_survives_desktop_close_command_and_browser_restart(self):
        with TemporaryDirectory(prefix="price-watch-profile-test-") as directory:
            profile = Path(directory)
            process, port = await self._launch(profile)
            try:
                async with async_playwright() as playwright:
                    browser = await playwright.chromium.connect_over_cdp(
                        f"http://127.0.0.1:{port}", no_defaults=True
                    )
                    await browser.contexts[0].add_cookies([
                        {
                            "name": "price_watch_profile_test",
                            "value": "saved",
                            "domain": ".ozon.ru",
                            "path": "/",
                            "expires": 2_000_000_000,
                        }
                    ])
                    await browser.close()

                closed = await asyncio.to_thread(
                    subprocess.run,
                    [
                        sys.executable,
                        "-c",
                        "from marketplace_connector.browser.profile_lifecycle import main; raise SystemExit(main())",
                        str(profile),
                    ],
                    capture_output=True,
                    text=True,
                    timeout=15,
                    check=False,
                )
                self.assertEqual(closed.returncode, 0, closed.stderr)
                process.wait(timeout=5)
                preferences = json.loads((profile / "Default/Preferences").read_text())
                self.assertEqual(preferences["profile"]["exit_type"], "Normal")

                process, port = await self._launch(profile)
                async with async_playwright() as playwright:
                    browser = await playwright.chromium.connect_over_cdp(
                        f"http://127.0.0.1:{port}", no_defaults=True
                    )
                    cookies = await browser.contexts[0].cookies("https://www.ozon.ru/")
                    self.assertTrue(any(
                        cookie["name"] == "price_watch_profile_test"
                        and cookie["value"] == "saved"
                        for cookie in cookies
                    ))
                    session = await browser.new_browser_cdp_session()
                    try:
                        await session.send("Browser.close")
                    except Exception:
                        pass
                process.wait(timeout=5)
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait(timeout=5)
                    await asyncio.sleep(0.2)
