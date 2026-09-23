import json
import os
import subprocess
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import ANY, MagicMock, patch

from ozon_article_json.parser import OzonRawCardParser
from marketplace_connector.connectors.ozon.client import OzonClient
from marketplace_connector.domain.errors import MarketplaceUnavailable


class FakeLocator:
    def __init__(self, text):
        self.text = text

    def all_inner_texts(self):
        return [self.text]


class FakePage:
    def __init__(self, body_text):
        self.body_text = body_text

    def locator(self, selector):
        return FakeLocator(self.body_text)


class ParserTests(unittest.TestCase):
    def test_normalizes_numeric_article(self):
        self.assertEqual(
            OzonRawCardParser.normalize_article(" 1604900984 "),
            "1604900984",
        )

    def test_rejects_invalid_article(self):
        for article in ("", "12-34", "товар", True, None):
            with self.subTest(article=article):
                with self.assertRaises(ValueError):
                    OzonRawCardParser.normalize_article(article)

    def test_extracts_raw_card_json(self):
        raw = json.dumps({"widgetStates": {"webPrice-1": "{}"}})
        page = FakePage(raw)

        self.assertEqual(OzonRawCardParser._extract_card_json(page), raw)

    def test_rejects_antibot_html(self):
        page = FakePage("Antibot Challenge Page")

        self.assertFalse(OzonRawCardParser._extract_card_json(page))

    def test_launches_persistent_playwright_context(self):
        with TemporaryDirectory() as directory:
            client = OzonClient.__new__(OzonClient)
            client.profile_dir = Path(directory)
            client.chrome_binary = Path("/usr/bin/google-chrome-stable")
            client.chrome_platform = "x11"
            client.browser_channel = "chrome"
            client.headless = False
            playwright = MagicMock()
            playwright.chromium.connect_over_cdp.return_value.contexts = [MagicMock()]

            with (
                patch.object(client, "_reserve_debug_port", return_value=19222),
                patch.object(client, "_wait_for_debug_port"),
                patch("marketplace_connector.connectors.ozon.client.subprocess.Popen") as popen,
            ):
                client._launch_context(playwright)

        popen.assert_called_once_with(
            [
                "/usr/bin/google-chrome-stable",
                "--remote-debugging-port=19222",
                "--remote-debugging-address=127.0.0.1",
                f"--user-data-dir={directory}",
                "--no-first-run",
                "--no-default-browser-check",
                "--start-maximized",
                "--ozone-platform=x11",
                "about:blank",
            ],
            stdout=ANY,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        playwright.chromium.connect_over_cdp.assert_called_once_with(
            "http://127.0.0.1:19222",
            timeout=10_000,
            is_local=True,
            no_defaults=True,
        )

    def test_uses_bundled_chromium_without_channel(self):
        with TemporaryDirectory() as directory:
            client = OzonClient.__new__(OzonClient)
            client.profile_dir = Path(directory)
            client.chrome_binary = None
            client.chrome_platform = "x11"
            client.browser_channel = "chromium"
            client.headless = False
            playwright = MagicMock()

            self.assertEqual(
                client._find_chrome_executable(playwright),
                Path(playwright.chromium.executable_path),
            )

    def test_chrome_channel_never_falls_back_to_chromium(self):
        client = OzonClient.__new__(OzonClient)
        client.chrome_binary = None
        client.browser_channel = "chrome"
        with patch("marketplace_connector.connectors.ozon.client.shutil.which") as which:
            which.side_effect = (
                lambda name: "/usr/bin/chromium" if name == "chromium" else None
            )
            with self.assertRaisesRegex(MarketplaceUnavailable, "Google Chrome"):
                client._find_chrome_executable(MagicMock())
        self.assertEqual(
            [call.args[0] for call in which.call_args_list],
            ["google-chrome-stable", "google-chrome"],
        )

    def test_removes_only_stale_profile_locks(self):
        with TemporaryDirectory() as directory:
            profile = Path(directory)
            (profile / "SingletonLock").symlink_to("host-99999999")
            (profile / "SingletonCookie").symlink_to("cookie")
            (profile / "SingletonSocket").symlink_to("/tmp/missing-socket")
            client = OzonClient.__new__(OzonClient)
            client.profile_dir = profile

            client._cleanup_stale_profile_locks()

            self.assertFalse((profile / "SingletonLock").is_symlink())
            self.assertFalse((profile / "SingletonCookie").is_symlink())
            self.assertFalse((profile / "SingletonSocket").is_symlink())

    def test_does_not_remove_live_profile_lock(self):
        with TemporaryDirectory() as directory:
            profile = Path(directory)
            lock = profile / "SingletonLock"
            lock.symlink_to(f"host-{os.getpid()}")
            client = OzonClient.__new__(OzonClient)
            client.profile_dir = profile

            with self.assertRaisesRegex(Exception, "уже используется"):
                client._cleanup_stale_profile_locks()

            self.assertTrue(lock.is_symlink())


if __name__ == "__main__":
    unittest.main()
