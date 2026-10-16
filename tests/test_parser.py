import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import AsyncMock, MagicMock, patch

from marketplace_connector.connectors.ozon import AsyncOzonClient
from marketplace_connector.domain.errors import MarketplaceUnavailable
from ozon_article_json.parser import OzonRawCardParser


class ParserTests(unittest.TestCase):
    def test_normalizes_numeric_article(self):
        self.assertEqual(OzonRawCardParser.normalize_article(" 1604900984 "), "1604900984")

    def test_rejects_invalid_article(self):
        for article in ("", "12-34", "товар", True, None):
            with self.subTest(article=article), self.assertRaises(ValueError):
                OzonRawCardParser.normalize_article(article)

    def test_chrome_channel_never_falls_back_to_chromium(self):
        with TemporaryDirectory() as directory:
            client = AsyncOzonClient(directory)
            with patch("marketplace_connector.connectors.ozon.async_client.shutil.which", return_value=None):
                with self.assertRaisesRegex(MarketplaceUnavailable, "Google Chrome"):
                    client._find_chrome_executable(MagicMock())

    def test_removes_only_stale_profile_locks(self):
        with TemporaryDirectory() as directory:
            profile = Path(directory)
            (profile / "SingletonLock").symlink_to("host-99999999")
            (profile / "SingletonCookie").symlink_to("cookie")
            (profile / "SingletonSocket").symlink_to("/tmp/missing-socket")
            AsyncOzonClient(profile)._cleanup_stale_profile_locks()
            for name in ("SingletonLock", "SingletonCookie", "SingletonSocket"):
                self.assertFalse((profile / name).is_symlink())

    def test_does_not_remove_live_profile_lock(self):
        with TemporaryDirectory() as directory:
            profile = Path(directory)
            lock = profile / "SingletonLock"
            lock.symlink_to(f"host-{os.getpid()}")
            with self.assertRaisesRegex(MarketplaceUnavailable, "уже используется"):
                AsyncOzonClient(profile)._cleanup_stale_profile_locks()
            self.assertTrue(lock.is_symlink())


class ParserAsyncTests(unittest.IsolatedAsyncioTestCase):
    async def test_legacy_parser_facade_fetches_asynchronously(self):
        with TemporaryDirectory() as directory:
            parser = OzonRawCardParser(directory)
            with patch.object(parser, "fetch_raw_text_async", new_callable=AsyncMock,
                              return_value='{"widgetStates":{}}') as fetch:
                result = await parser.fetch("100")
            self.assertEqual(result, '{"widgetStates":{}}')
            fetch.assert_awaited_once_with("100")


if __name__ == "__main__":
    unittest.main()
