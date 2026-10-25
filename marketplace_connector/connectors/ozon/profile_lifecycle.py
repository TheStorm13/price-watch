"""Gracefully close only the Chrome associated with a managed profile."""

from __future__ import annotations

import argparse
import asyncio
import http.client
import json
import logging
import os
from contextlib import suppress
from pathlib import Path

from playwright.async_api import Browser, Error as PlaywrightError, Playwright, async_playwright

from ...domain.errors import MarketplaceUnavailable


logger = logging.getLogger(__name__)


def _debug_endpoint(profile_dir: Path) -> tuple[int, str] | None:
    try:
        port_text, browser_path = (profile_dir / "DevToolsActivePort").read_text().splitlines()[:2]
        port = int(port_text)
    except (OSError, ValueError, IndexError):
        return None
    if not 1 <= port <= 65535 or not browser_path.startswith("/devtools/browser/"):
        return None
    return port, browser_path


def _matching_browser_is_listening(port: int, browser_path: str) -> bool:
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=0.5)
    try:
        connection.request("GET", "/json/version")
        response = connection.getresponse()
        if response.status != 200:
            return False
        details = json.loads(response.read())
        return details.get("webSocketDebuggerUrl", "").endswith(browser_path)
    except (OSError, ValueError, http.client.HTTPException):
        return False
    finally:
        connection.close()


def _profile_lock_is_live(profile_dir: Path) -> bool:
    lock_path = profile_dir / "SingletonLock"
    if not lock_path.is_symlink():
        return False
    try:
        _, separator, pid_text = os.readlink(lock_path).rpartition("-")
    except FileNotFoundError:
        return False
    if not separator or not pid_text.isdigit():
        return True
    return Path(f"/proc/{pid_text}").exists()


async def request_browser_close(browser: Browser) -> None:
    """CDP Browser.close flushes Chrome's profile before it exits."""
    session = await browser.new_browser_cdp_session()
    with suppress(PlaywrightError):
        # The connection may disappear while Chrome is shutting down.
        await session.send("Browser.close")


async def close_profile_browser(profile_dir: Path, playwright: Playwright) -> bool:
    endpoint = _debug_endpoint(profile_dir)
    if endpoint is None:
        return False
    port, browser_path = endpoint
    if not await asyncio.to_thread(_matching_browser_is_listening, port, browser_path):
        return False

    logger.info("Штатно закрываю Chrome с профилем %s", profile_dir)
    try:
        browser = await playwright.chromium.connect_over_cdp(
            f"http://127.0.0.1:{port}", timeout=5_000, is_local=True, no_defaults=True,
        )
    except PlaywrightError as exc:
        raise MarketplaceUnavailable("Не удалось подключиться к Chrome для закрытия") from exc
    try:
        await request_browser_close(browser)
    finally:
        with suppress(PlaywrightError):
            await browser.close()

    deadline = asyncio.get_running_loop().time() + 5
    while (
        await asyncio.to_thread(_matching_browser_is_listening, port, browser_path)
        or await asyncio.to_thread(_profile_lock_is_live, profile_dir)
    ):
        if asyncio.get_running_loop().time() >= deadline:
            raise MarketplaceUnavailable("Chrome не освободил профиль после команды закрытия")
        await asyncio.sleep(0.1)
    return True


async def _close_from_cli(profile_dir: Path) -> bool:
    async with async_playwright() as playwright:
        return await close_profile_browser(profile_dir, playwright)


def main() -> int:
    parser = argparse.ArgumentParser(description="Штатно закрыть Chrome с профилем price-watch")
    parser.add_argument("profile_dir", type=Path)
    args = parser.parse_args()
    try:
        if asyncio.run(asyncio.wait_for(_close_from_cli(args.profile_dir), timeout=10)):
            return 0
    except (MarketplaceUnavailable, PlaywrightError, TimeoutError) as exc:
        parser.exit(1, f"Не удалось закрыть Chrome: {exc}\n")
    parser.exit(1, "Не найден работающий Chrome с этим профилем\n")


if __name__ == "__main__":
    raise SystemExit(main())
