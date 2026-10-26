"""Reference-counted ownership of one managed Chrome process and profile."""

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
from pathlib import Path
from typing import Optional, Union
from urllib.parse import urlparse

from playwright.async_api import Error as PlaywrightError
from playwright.async_api import Playwright, async_playwright

from ..domain.errors import MarketplaceUnavailable
from .profile_lifecycle import close_profile_browser, request_browser_close


logger = logging.getLogger(__name__)


class ChromeSession:
    def __init__(self, profile_dir, *, chrome_binary=None, chrome_platform="x11",
                 browser_channel="chrome", headless=False, virtual_display=False):
        self.profile_dir = Path(profile_dir).expanduser().resolve()
        self.chrome_binary = self._resolve_chrome_binary(chrome_binary)
        if chrome_platform not in {"auto", "x11", "wayland"}:
            raise ValueError("chrome_platform должен быть auto, x11 или wayland")
        self.chrome_platform = chrome_platform
        self.browser_channel = browser_channel
        self.headless = headless
        self.virtual_display = virtual_display
        self._async_context = self._async_browser = self._async_process = None
        self._async_playwright = None
        self._playwright_manager = None
        self._users = 0
        self._lock = asyncio.Lock()
        self.challenge_lock = asyncio.Lock()

    @property
    def context(self):
        if self._async_context is None:
            raise MarketplaceUnavailable("Chrome session ещё не готов")
        return self._async_context

    async def acquire(self):
        async with self._lock:
            if self._users == 0:
                self.profile_dir.mkdir(parents=True, exist_ok=True)
                manager = async_playwright()
                self._async_playwright = await manager.__aenter__()
                self._playwright_manager = manager
                try:
                    await self._launch_async_context(self._async_playwright)
                except BaseException:
                    await self._close_async_context()
                    await manager.__aexit__(None, None, None)
                    self._async_playwright = self._playwright_manager = None
                    raise
            self._users += 1
            return self.context

    async def release(self):
        async with self._lock:
            if self._users == 0:
                raise RuntimeError("Chrome session release без acquire")
            self._users -= 1
            if self._users == 0:
                try:
                    await self._close_async_context()
                finally:
                    manager, self._playwright_manager = self._playwright_manager, None
                    self._async_playwright = None
                    if manager is not None:
                        await manager.__aexit__(None, None, None)

    @asynccontextmanager
    async def collection_session(self):
        context = await self.acquire()
        try:
            yield context
        finally:
            await self.release()

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
        logger.info("Запуск Chrome для сбора товаров")
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
