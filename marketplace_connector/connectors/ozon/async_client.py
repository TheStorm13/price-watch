"""Concurrent Ozon transport using one Chrome and separate async pages."""

from __future__ import annotations

import asyncio
import http.client
import json
import logging
import os
import re
import shutil
import socket
import subprocess
import time
from contextlib import asynccontextmanager, suppress
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Union

from playwright.async_api import Error as PlaywrightError
from playwright.async_api import Playwright, async_playwright

from ...domain.errors import InvalidProductId, MarketplaceUnavailable
from ...domain.raw import RawMarketplaceResponse
from ...ports.challenge import ChallengeHandler, RejectChallengeHandler


logger = logging.getLogger(__name__)


class AsyncOzonClient:
    """Read Ozon cards concurrently through tabs in one persistent Chrome."""

    marketplace = "ozon"
    PRODUCT_URL = "https://www.ozon.ru/product/{article}/"
    API_URL = (
        "https://www.ozon.ru/api/composer-api.bx/page/json/v2"
        "?url=/product/{article}&__rr=1"
    )
    ANTIBOT_MARKERS = ("antibot", "fab_", "похоже, нет соединения", "выключите vpn")

    def __init__(
        self,
        profile_dir: Union[str, Path],
        challenge_handler: Optional[ChallengeHandler] = None,
        chrome_binary: Optional[Union[str, Path]] = None,
        json_wait_seconds: int = 15,
        chrome_platform: str = "x11",
        browser_channel: str = "chrome",
        headless: bool = False,
        virtual_display: bool = False,
    ):
        self.profile_dir = Path(profile_dir).expanduser().resolve()
        self.challenge_handler = challenge_handler or RejectChallengeHandler()
        self.chrome_binary = self._resolve_chrome_binary(chrome_binary)
        if json_wait_seconds <= 0:
            raise ValueError("json_wait_seconds должен быть положительным")
        if chrome_platform not in {"auto", "x11", "wayland"}:
            raise ValueError("chrome_platform должен быть auto, x11 или wayland")
        self.json_wait_seconds = json_wait_seconds
        self.chrome_platform = chrome_platform
        self.browser_channel = browser_channel
        self.headless = headless
        self.virtual_display = virtual_display
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
        if self.virtual_display:
            await self._close_open_profile_browser(playwright)
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

    async def _close_open_profile_browser(self, playwright: Playwright) -> None:
        """Close the app's visible Chrome before a desktop worker reuses its profile."""
        port_file = self.profile_dir / "DevToolsActivePort"
        try:
            port_text, browser_path = port_file.read_text().splitlines()[:2]
            port = int(port_text)
        except (OSError, ValueError, IndexError):
            return
        if not 1 <= port <= 65535 or not browser_path.startswith("/devtools/browser/"):
            return

        def matching_browser_is_listening() -> bool:
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

        if not await asyncio.to_thread(matching_browser_is_listening):
            return
        logger.info("Закрываю Chrome приложения перед фоновым сбором Ozon")
        browser = await playwright.chromium.connect_over_cdp(
            f"http://127.0.0.1:{port}", timeout=5_000, is_local=True, no_defaults=True,
        )
        try:
            with suppress(PlaywrightError):
                session = await browser.new_browser_cdp_session()
                await session.send("Browser.close")
        finally:
            with suppress(PlaywrightError):
                await browser.close()
        deadline = asyncio.get_running_loop().time() + 5
        while True:
            if not await asyncio.to_thread(matching_browser_is_listening):
                try:
                    self._cleanup_stale_profile_locks()
                    return
                except MarketplaceUnavailable:
                    pass
            if asyncio.get_running_loop().time() >= deadline:
                raise MarketplaceUnavailable("Не удалось закрыть Chrome приложения перед сбором")
            await asyncio.sleep(0.1)

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
            await self.challenge_handler.handle_async(self.marketplace, message)
            await page.reload(wait_until="domcontentloaded", timeout=90_000)
            if not await self._wait_for_antibot_async(page):
                raise MarketplaceUnavailable(
                    "Ozon не пропустил проверку после подтверждения пользователя"
                )

    def _find_chrome_executable(self, playwright: Playwright) -> Path:
        if self.chrome_binary is not None:
            return self.chrome_binary
        if self.browser_channel == "chromium":
            return Path(playwright.chromium.executable_path)
        for name in ("google-chrome-stable", "google-chrome"):
            path = shutil.which(name)
            if path:
                return Path(path)
        raise MarketplaceUnavailable("Не найден установленный Google Chrome")

    @staticmethod
    def _reserve_debug_port() -> int:
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            return int(listener.getsockname()[1])

    @staticmethod
    def _wait_for_debug_port(process: subprocess.Popen, port: int) -> None:
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            if process.poll() is not None:
                raise MarketplaceUnavailable(f"Chrome завершился с кодом {process.returncode}")
            connection = http.client.HTTPConnection("127.0.0.1", port, timeout=0.5)
            try:
                connection.request("GET", "/json/version")
                if connection.getresponse().status == 200:
                    return
            except OSError:
                time.sleep(0.1)
            finally:
                connection.close()
        raise MarketplaceUnavailable("Chrome не открыл порт управления за 10 секунд")

    @staticmethod
    def _validate_json_text(raw_text: str) -> str:
        try:
            payload = json.loads(raw_text)
        except json.JSONDecodeError as exc:
            raise MarketplaceUnavailable("Ozon вернул HTML вместо JSON") from exc
        if not isinstance(payload, dict) or "widgetStates" not in payload:
            raise MarketplaceUnavailable("В ответе Ozon нет widgetStates")
        return raw_text

    @classmethod
    def _is_antibot_text(cls, text: str) -> bool:
        lowered = text.lower()
        return any(marker in lowered for marker in cls.ANTIBOT_MARKERS)

    @staticmethod
    def normalize_product_id(value: Union[str, int]) -> str:
        if isinstance(value, bool):
            raise InvalidProductId("Идентификатор товара должен состоять из цифр")
        normalized = str(value).strip()
        if not normalized or not normalized.isascii() or not normalized.isdigit():
            raise InvalidProductId("Идентификатор товара должен состоять из цифр")
        return normalized

    def _cleanup_stale_profile_locks(self) -> None:
        lock_path = self.profile_dir / "SingletonLock"
        if not lock_path.is_symlink():
            return
        target = os.readlink(lock_path)
        _, separator, pid_text = target.rpartition("-")
        if not separator or not pid_text.isdigit():
            raise MarketplaceUnavailable(
                f"Профиль Chrome заблокирован: {lock_path} -> {target}"
            )
        pid = int(pid_text)
        if Path(f"/proc/{pid}").exists():
            raise MarketplaceUnavailable(f"Профиль Chrome уже используется процессом {pid}")
        logger.warning("Удаляю устаревшую блокировку профиля Chrome: pid=%s", pid)
        for name in ("SingletonLock", "SingletonCookie", "SingletonSocket"):
            path = self.profile_dir / name
            try:
                path.unlink()
            except FileNotFoundError:
                pass

    @staticmethod
    def _resolve_chrome_binary(configured: Optional[Union[str, Path]]) -> Optional[Path]:
        if configured is None:
            return None
        binary = Path(configured).expanduser().resolve()
        if not binary.is_file():
            raise FileNotFoundError(f"Chrome не найден: {binary}")
        return binary
