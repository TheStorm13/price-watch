import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import AsyncMock, MagicMock, patch

from marketplace_connector.connectors.ozon import AsyncOzonClient
from marketplace_connector.domain.errors import MarketplaceUnavailable



class ParserTests(unittest.TestCase):
    def test_normalizes_numeric_article(self):
        self.assertEqual(AsyncOzonClient.normalize_product_id(" 1604900984 "), "1604900984")

    def test_rejects_invalid_article(self):
        for article in ("", "12-34", "товар", True, None):
            with self.subTest(article=article), self.assertRaises(ValueError):
                AsyncOzonClient.normalize_product_id(article)

    def test_chrome_channel_never_falls_back_to_chromium(self):
        with TemporaryDirectory() as directory:
            client = AsyncOzonClient(directory)
            with patch("marketplace_connector.browser.session.shutil.which", return_value=None):
                with self.assertRaisesRegex(MarketplaceUnavailable, "Google Chrome"):
                    client.session._find_chrome_executable(MagicMock())

    def test_removes_only_stale_profile_locks(self):
        with TemporaryDirectory() as directory:
            profile = Path(directory)
            (profile / "SingletonLock").symlink_to("host-99999999")
            (profile / "SingletonCookie").symlink_to("cookie")
            (profile / "SingletonSocket").symlink_to("/tmp/missing-socket")
            AsyncOzonClient(profile).session._cleanup_stale_profile_locks()
            for name in ("SingletonLock", "SingletonCookie", "SingletonSocket"):
                self.assertFalse((profile / name).is_symlink())

    def test_does_not_remove_live_profile_lock(self):
        with TemporaryDirectory() as directory:
            profile = Path(directory)
            lock = profile / "SingletonLock"
            lock.symlink_to(f"host-{os.getpid()}")
            with self.assertRaisesRegex(MarketplaceUnavailable, "уже используется"):
                AsyncOzonClient(profile).session._cleanup_stale_profile_locks()
            self.assertTrue(lock.is_symlink())
