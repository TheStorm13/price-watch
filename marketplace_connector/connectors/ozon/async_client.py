"""Concurrent Ozon JSON requests through one persistent Chrome session."""

from __future__ import annotations

import asyncio
import http.client
import logging
import os
import shutil
import socket
import subprocess
import time
from contextlib import asynccontextmanager, suppress
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Union
from urllib.parse import urlparse

from playwright.async_api import Error as PlaywrightError
from playwright.async_api import Playwright, async_playwright

from ...domain.errors import InvalidProductId, MarketplaceUnavailable
from .json_transport import HOME_URL, OzonJsonTransport
from .models import OzonResponse
from ...ports.challenge import ChallengeHandler, RejectChallengeHandler
from .profile_lifecycle import close_profile_browser, request_browser_close


logger = logging.getLogger(__name__)


class AsyncOzonClient:
    """Read Ozon cards through concurrent fetch calls on one storefront page."""

    marketplace = "ozon"
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
        *,
        concurrency: int = 5,
        starts_per_second: float = 5,
        request_timeout: float = 30,
        max_attempts: int = 3,
        max_retry_wait: float = 30,
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
        self._transport_options = dict(concurrency=concurrency, starts_per_second=starts_per_second,
                                       request_timeout=request_timeout, max_attempts=max_attempts,
                                       max_retry_wait=max_retry_wait)
        # Validate before launching Chrome. The real transport belongs to a session.
        OzonJsonTransport(None, None, **self._transport_options)
        self._transport = None
        self._session_lock = asyncio.Lock()
        self._auto_session = None
        self._auto_users = 0
        self._session_open = False

    @asynccontextmanager
    async def collection_session(self):
        if self._session_open:
            raise RuntimeError("Сеанс Ozon уже открыт")
        self._session_open = True
        try:
            self.profile_dir.mkdir(parents=True, exist_ok=True)
            async with async_playwright() as playwright:
                self._async_playwright = playwright
                self._challenge_lock = asyncio.Lock()
                try:
                    await self._launch_async_context(playwright)
                    self._transport = OzonJsonTransport(
                        self._async_context, self._prepare_storefront, **self._transport_options,
                    )
                    yield
                finally:
                    try:
                        if self._transport is not None:
                            await self._transport.close()
                    finally:
                        self._transport = None
                        try:
                            await self._close_async_context()
                        finally:
                            self._async_playwright = None
                            self._challenge_lock = None
        finally:
            self._session_open = False

    @asynccontextmanager
    async def _request_session(self):
        # Concurrent standalone callers own one reference-counted session. An
        # explicit collection session remains owned by its outer context manager.
        automatic = False
        async with self._session_lock:
            if self._auto_session is not None or not self._session_open:
                if self._auto_session is None:
                    session = self.collection_session()
                    await session.__aenter__()
                    self._auto_session = session
                self._auto_users += 1
                automatic = True
            transport = self._transport
        try:
            if transport is None:
                raise MarketplaceUnavailable("Сеанс Ozon ещё не готов")
            yield transport
        finally:
            if automatic:
                async with self._session_lock:
                    self._auto_users -= 1
                    if self._auto_users == 0:
                        session, self._auto_session = self._auto_session, None
                        await session.__aexit__(None, None, None)

    async def _prepare_storefront(self, page):
        response = await page.goto(HOME_URL, wait_until="domcontentloaded", timeout=90_000)
        if await self._is_antibot_page_async(page):
            if not await self._wait_for_antibot_async(page):
                await self._handle_antibot_async(page, "сессия")
            # The challenge can replace its initial 403 document. Its stale
            # navigation response no longer describes the current page.
            response = None
        elif response is not None and response.status in (401, 403):
            await self._handle_antibot_async(page, "сессия", force=True)
            response = None
        location = urlparse(page.url)
        if (location.scheme != "https" or location.netloc != "www.ozon.ru"
                or response is not None and response.status >= 400):
            raise MarketplaceUnavailable("Не удалось открыть главную страницу Ozon")

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
        if await close_profile_browser(self.profile_dir, playwright):
            self._cleanup_stale_profile_locks()

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
                try:
                    await request_browser_close(browser)
                except PlaywrightError as exc:
                    logger.warning("Не удалось штатно закрыть Chrome сбора: %s", exc)
                with suppress(PlaywrightError):
                    await browser.close()
        finally:
            if process is not None and process.poll() is None:
                try:
                    await asyncio.to_thread(process.wait, timeout=5)
                except subprocess.TimeoutExpired:
                    logger.warning("Chrome сбора не завершился штатно; посылаю SIGTERM")
                    with suppress(ProcessLookupError):
                        process.terminate()
                    try:
                        await asyncio.to_thread(process.wait, timeout=3)
                    except subprocess.TimeoutExpired:
                        logger.error("Chrome сбора завис; посылаю SIGKILL")
                        process.kill()
                        await asyncio.to_thread(process.wait, timeout=5)

    async def fetch_product_async(self, external_id: Union[str, int]) -> OzonResponse:
        article = self.normalize_product_id(external_id)
        raw_text = await self.fetch_raw_text_async(article, validate=False)
        return OzonResponse(
            external_id=article,
            raw_text=raw_text,
            received_at=datetime.now(timezone.utc),
        )

    async def fetch_raw_text_async(self, external_id: Union[str, int], *, validate: bool = True) -> str:
        article = self.normalize_product_id(external_id)
        # Keep the keyword for callers; access/schema checks also apply to raw
        # and validate=False. Successful response text is returned unchanged.
        async with self._request_session() as transport:
            return await transport.fetch(article)

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

    async def _handle_antibot_async(self, page, article: str, *, force: bool = False) -> None:
        async with self._challenge_lock:
            if not force and not await self._is_antibot_page_async(page):
                return
            logger.warning("Ozon запросил проверку для артикула %s", article)
            if (self.headless or self.virtual_display) and self._async_process is not None:
                raise MarketplaceUnavailable(
                    "Ozon запросил ручную проверку. Откройте Chrome кнопкой в приложении, "
                    "пройдите проверку на Ozon и повторите сбор."
                )
            message = (
                f"Ozon ({article}): перейдите на общую вкладку Ozon в Chrome, "
                "пройдите проверку и нажмите «Проверка пройдена» в приложении."
            )
            await self.challenge_handler.handle_async(self.marketplace, message)
            response = await page.reload(wait_until="domcontentloaded", timeout=90_000)
            if (not await self._wait_for_antibot_async(page)
                    or response is not None and isinstance(response.status, int) and response.status >= 400):
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
