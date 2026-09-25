"""Concurrent Ozon transport using one Chrome and separate async pages."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import socket
import subprocess
from contextlib import asynccontextmanager, suppress
from datetime import datetime, timezone
from typing import Union

from playwright.async_api import Error as PlaywrightError
from playwright.async_api import Playwright, async_playwright

from ...domain.errors import MarketplaceUnavailable
from ...domain.raw import RawMarketplaceResponse
from .client import OzonClient


logger = logging.getLogger(__name__)


class AsyncOzonClient(OzonClient):
    """Read Ozon cards concurrently through tabs in one persistent Chrome."""

    def __init__(self, *args, **kwargs):
        self.virtual_display = kwargs.pop("virtual_display", False)
        super().__init__(*args, **kwargs)
        self._async_context = None
        self._async_browser = None
        self._async_process = None
        self._async_playwright = None
        self._challenge_lock = None

    @asynccontextmanager
    async def collection_session(self):
        if self._async_playwright is not None:
            raise RuntimeError("Сеанс Ozon уже открыт")
        self.profile_dir.mkdir(parents=True, exist_ok=True)
        async with async_playwright() as playwright:
            self._async_playwright = playwright
            self._challenge_lock = asyncio.Lock()
            try:
                await self._launch_async_context(playwright)
                yield
            finally:
                try:
                    await self._close_async_context()
                finally:
                    self._async_playwright = None
                    self._challenge_lock = None

    async def _launch_async_context(self, playwright: Playwright) -> None:
        self._cleanup_stale_profile_locks()
        executable = self._find_chrome_executable(playwright)
        port = self._reserve_debug_port()
        chrome_env = os.environ.copy()
        if self.virtual_display:
            self._check_virtual_display(chrome_env.get("DISPLAY", ""))
        args = [
            str(executable),
            f"--remote-debugging-port={port}",
            "--remote-debugging-address=127.0.0.1",
            f"--user-data-dir={self.profile_dir}",
            "--no-first-run",
            "--no-default-browser-check",
            "--start-maximized",
        ]
        if self.chrome_platform != "auto":
            args.append(f"--ozone-platform={self.chrome_platform}")
        if self.headless:
            args.append("--headless=new")
        args.append("about:blank")
        logger.info("Запуск Chrome для асинхронного сбора Ozon")
        with (self.profile_dir / "chrome.log").open("ab") as log_file:
            self._async_process = subprocess.Popen(
                args,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                start_new_session=True,
                env=chrome_env,
            )
        try:
            await asyncio.to_thread(self._wait_for_debug_port, self._async_process, port)
            self._async_browser = await playwright.chromium.connect_over_cdp(
                f"http://127.0.0.1:{port}",
                timeout=10_000,
                is_local=True,
                no_defaults=True,
            )
            if not self._async_browser.contexts:
                raise MarketplaceUnavailable("Chrome не создал основной профиль")
            self._async_context = self._async_browser.contexts[0]
        except BaseException:
            await self._close_async_context()
            raise

    @staticmethod
    def _check_virtual_display(display: str) -> None:
        if not display.startswith(":") or not display[1:].isdigit():
            raise MarketplaceUnavailable("Не задан скрытый дисплей Chrome")
        path = f"/tmp/.X11-unix/X{display[1:]}"
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
                connection.settimeout(1)
                connection.connect(path)
        except OSError as exc:
            raise MarketplaceUnavailable(f"Скрытый дисплей Chrome недоступен: {path}") from exc

    async def _close_async_context(self) -> None:
        browser = self._async_browser
        process = self._async_process
        self._async_context = None
        self._async_browser = None
        self._async_process = None
        try:
            if browser is not None:
                with suppress(PlaywrightError):
                    await browser.close()
        finally:
            if process is not None and process.poll() is None:
                with suppress(ProcessLookupError):
                    process.terminate()
                try:
                    await asyncio.to_thread(process.wait, timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    await asyncio.to_thread(process.wait, timeout=5)

    async def fetch_product_async(self, external_id: Union[str, int]) -> RawMarketplaceResponse:
        article = self.normalize_product_id(external_id)
        raw_text = await self.fetch_raw_text_async(article)
        payload = json.loads(raw_text)
        return RawMarketplaceResponse(
            marketplace=self.marketplace,
            external_id=article,
            payload=payload,
            raw_text=raw_text,
            received_at=datetime.now(timezone.utc),
        )

    async def fetch_raw_text_async(self, external_id: Union[str, int]) -> str:
        article = self.normalize_product_id(external_id)
        if self._async_context is None:
            async with self.collection_session():
                return await self.fetch_raw_text_async(article)
        page = await self._async_context.new_page()
        try:
            await page.goto(
                self.PRODUCT_URL.format(article=article),
                wait_until="domcontentloaded",
                timeout=90_000,
            )
            if await self._is_antibot_page_async(page):
                if not await self._wait_for_antibot_async(page):
                    await self._handle_antibot_async(page, article)

            raw_text = await self._fetch_json_in_page_async(page, article)
            if self._is_antibot_text(raw_text):
                await self._handle_antibot_async(page, article, check_json=True)
                raw_text = await self._fetch_json_in_page_async(page, article)
            return self._validate_json_text(raw_text)
        except (PlaywrightError, TimeoutError) as exc:
            raise MarketplaceUnavailable(f"Playwright не смог получить данные Ozon: {exc}") from exc
        finally:
            with suppress(PlaywrightError):
                await page.close()

    async def _fetch_json_in_page_async(self, page, article: str) -> str:
        result = await asyncio.wait_for(
            page.evaluate(
                """async (url) => {
                    const response = await fetch(url, {
                        credentials: 'include',
                        headers: {'accept': 'application/json, text/plain, */*'}
                    });
                    return {status: response.status, text: await response.text()};
                }""",
                self.API_URL.format(article=article),
            ),
            timeout=30,
        )
        text = result.get("text", "") if isinstance(result, dict) else ""
        if not text:
            status = result.get("status") if isinstance(result, dict) else "unknown"
            raise MarketplaceUnavailable(f"Ozon вернул пустой ответ (HTTP {status})")
        return text

    async def _is_antibot_page_async(self, page) -> bool:
        parts = []
        with suppress(PlaywrightError):
            parts.append(await page.title())
        with suppress(PlaywrightError):
            parts.append(await page.locator("body").inner_text(timeout=1_000))
        return self._is_antibot_text("\n".join(parts))

    async def _wait_for_antibot_async(self, page) -> bool:
        deadline = asyncio.get_running_loop().time() + self.json_wait_seconds
        while asyncio.get_running_loop().time() < deadline:
            if not await self._is_antibot_page_async(page):
                return True
            await asyncio.sleep(0.25)
        return False

    async def _handle_antibot_async(self, page, article: str, check_json: bool = False) -> None:
        async with self._challenge_lock:
            if check_json:
                current = await self._fetch_json_in_page_async(page, article)
                if not self._is_antibot_text(current):
                    return
            elif not await self._is_antibot_page_async(page):
                return
            logger.warning("Ozon запросил проверку для артикула %s", article)
            if (self.headless or self.virtual_display) and self._async_process is not None:
                raise MarketplaceUnavailable(
                    "Ozon запросил ручную проверку. Откройте Chrome кнопкой в приложении, "
                    "пройдите проверку на Ozon и повторите сбор."
                )
            message = (
                f"Артикул {article}: перейдите на его вкладку в Chrome, "
                "пройдите проверку и нажмите «Проверка пройдена» в приложении."
            )
            async_handle = getattr(self.challenge_handler, "handle_async", None)
            if async_handle is not None:
                await async_handle(self.marketplace, message)
            else:
                await asyncio.to_thread(self.challenge_handler.handle, self.marketplace, message)
            await page.reload(wait_until="domcontentloaded", timeout=90_000)
            if not await self._wait_for_antibot_async(page):
                raise MarketplaceUnavailable(
                    "Ozon не пропустил проверку после подтверждения пользователя"
                )

    def fetch_product(self, external_id: Union[str, int]) -> RawMarketplaceResponse:
        """Synchronous compatibility entry point using the async transport."""
        return asyncio.run(self.fetch_product_async(external_id))

    def fetch_raw_text(self, external_id: Union[str, int]) -> str:
        return asyncio.run(self.fetch_raw_text_async(external_id))
