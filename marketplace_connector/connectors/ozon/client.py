"""Fetch Ozon product JSON through a visible Playwright-managed browser."""

from __future__ import annotations

import json
import http.client
import logging
import os
import re
import shutil
import socket
import subprocess
from datetime import datetime, timezone
from pathlib import Path
import time
from typing import Optional, Union

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Playwright, sync_playwright

from ...domain.errors import InvalidProductId, MarketplaceUnavailable
from ...domain.raw import RawMarketplaceResponse
from ...ports.challenge import ChallengeHandler, RejectChallengeHandler


logger = logging.getLogger(__name__)


class _AttachedChromeContext:
    """A Playwright context backed by a separately launched regular Chrome."""

    def __init__(self, browser, context, process: subprocess.Popen):
        self._browser = browser
        self._context = context
        self._process = process

    @property
    def pages(self):
        return self._context.pages

    def new_page(self):
        return self._context.new_page()

    def close(self) -> None:
        try:
            self._browser.close()
        finally:
            if self._process.poll() is None:
                self._process.terminate()
                try:
                    self._process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self._process.kill()
                    self._process.wait(timeout=5)


class OzonClient:
    """Ozon-specific transport; it does not build public product entities."""

    marketplace = "ozon"
    PRODUCT_URL = "https://www.ozon.ru/product/{article}/"
    API_URL = (
        "https://www.ozon.ru/api/composer-api.bx/page/json/v2"
        "?url=/product/{article}&__rr=1"
    )
    ANTIBOT_MARKERS = (
        "antibot",
        "fab_",
        "похоже, нет соединения",
        "выключите vpn",
    )

    def __init__(
        self,
        profile_dir: Union[str, Path],
        challenge_handler: Optional[ChallengeHandler] = None,
        chrome_binary: Optional[Union[str, Path]] = None,
        json_wait_seconds: int = 15,
        chrome_platform: str = "x11",
        browser_channel: str = "chrome",
        headless: bool = False,
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

    def fetch_product(self, external_id: Union[str, int]) -> RawMarketplaceResponse:
        article = self.normalize_product_id(external_id)
        raw_text = self.fetch_raw_text(article)
        try:
            payload = json.loads(raw_text)
        except json.JSONDecodeError as exc:
            raise MarketplaceUnavailable("Ozon вернул некорректный JSON") from exc
        if not isinstance(payload, dict):
            raise MarketplaceUnavailable("Ozon вернул JSON неожиданного типа")
        return RawMarketplaceResponse(
            marketplace=self.marketplace,
            external_id=article,
            payload=payload,
            raw_text=raw_text,
            received_at=datetime.now(timezone.utc),
        )

    def fetch_raw_text(self, external_id: Union[str, int]) -> str:
        article = self.normalize_product_id(external_id)
        product_url = self.PRODUCT_URL.format(article=article)
        api_url = self.API_URL.format(article=article)
        self.profile_dir.mkdir(parents=True, exist_ok=True)
        self._cleanup_stale_profile_locks()

        logger.info("Запуск Playwright Chrome для артикула %s", article)
        try:
            with sync_playwright() as playwright:
                context = self._launch_context(playwright)
                try:
                    page = context.pages[0] if context.pages else context.new_page()
                    page.goto(product_url, wait_until="domcontentloaded", timeout=90_000)
                    if self._is_antibot_page(page):
                        logger.info("Ожидаю завершения автоматической проверки Ozon")
                        if not self._wait_for_antibot(page):
                            self._handle_antibot(page)
                            page.reload(wait_until="domcontentloaded", timeout=90_000)
                            if not self._wait_for_antibot(page):
                                raise MarketplaceUnavailable(
                                    "Ozon не пропустил проверку после подтверждения пользователя"
                                )

                    raw_text = self._fetch_json_in_page(page, api_url)
                    if self._is_antibot_text(raw_text):
                        self._handle_antibot(page)
                        raw_text = self._fetch_json_in_page(page, api_url)
                    return self._validate_json_text(raw_text)
                finally:
                    context.close()
        except MarketplaceUnavailable:
            raise
        except PlaywrightError as exc:
            raise MarketplaceUnavailable(f"Playwright не смог получить данные Ozon: {exc}") from exc

    def _launch_context(self, playwright: Playwright):
        executable = self._find_chrome_executable(playwright)
        debug_port = self._reserve_debug_port()
        args = [
            str(executable),
            f"--remote-debugging-port={debug_port}",
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

        chrome_log = self.profile_dir / "chrome.log"
        with chrome_log.open("ab") as log_file:
            process = subprocess.Popen(
                args,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
        try:
            self._wait_for_debug_port(process, debug_port)
            browser = playwright.chromium.connect_over_cdp(
                f"http://127.0.0.1:{debug_port}",
                timeout=10_000,
                is_local=True,
                no_defaults=True,
            )
            if not browser.contexts:
                raise MarketplaceUnavailable("Chrome не создал основной профиль")
            return _AttachedChromeContext(browser, browser.contexts[0], process)
        except Exception:
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=5)
            raise

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
                raise MarketplaceUnavailable(
                    f"Chrome завершился с кодом {process.returncode}"
                )
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

    def _handle_antibot(self, page) -> None:
        incident = self._find_incident(page)
        suffix = f" Код инцидента: {incident}." if incident else ""
        logger.warning("Ozon вернул антибот-страницу%s", suffix)
        self.challenge_handler.handle(
            self.marketplace,
            "Ozon запросил проверку. Выполните её в открытом Chrome или обновите "
            f"страницу, дождитесь загрузки товара и нажмите «Продолжить».{suffix}",
        )

    def _wait_for_antibot(self, page) -> bool:
        deadline = time.monotonic() + self.json_wait_seconds
        while time.monotonic() < deadline:
            if not self._is_antibot_page(page):
                return True
            page.wait_for_timeout(250)
        return False

    @staticmethod
    def _fetch_json_in_page(page, api_url: str) -> str:
        result = page.evaluate(
            """async (url) => {
                const response = await fetch(url, {
                    credentials: 'include',
                    headers: {'accept': 'application/json, text/plain, */*'}
                });
                return {status: response.status, text: await response.text()};
            }""",
            api_url,
        )
        text = result.get("text", "") if isinstance(result, dict) else ""
        if not text:
            status = result.get("status") if isinstance(result, dict) else "unknown"
            raise MarketplaceUnavailable(f"Ozon вернул пустой ответ (HTTP {status})")
        return text

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
    def _is_antibot_page(cls, page) -> bool:
        return cls._is_antibot_text(cls._page_text(page))

    @classmethod
    def _is_antibot_text(cls, text: str) -> bool:
        lowered = text.lower()
        return any(marker in lowered for marker in cls.ANTIBOT_MARKERS)

    @classmethod
    def _find_incident(cls, page) -> Optional[str]:
        match = re.search(r"fab_[a-z0-9_]+", cls._page_text(page), re.IGNORECASE)
        return match.group(0) if match else None

    @staticmethod
    def _page_text(page) -> str:
        parts = []
        try:
            parts.append(page.title())
        except PlaywrightError:
            pass
        try:
            parts.append(page.locator("body").inner_text(timeout=1_000))
        except PlaywrightError:
            pass
        return "\n".join(parts)

    @staticmethod
    def _extract_card_json(page):
        candidates = []
        for selector in ("pre", "body"):
            try:
                texts = page.locator(selector).all_inner_texts()
            except PlaywrightError:
                continue
            for text in texts:
                stripped = text.strip()
                if stripped and stripped not in candidates:
                    candidates.append(stripped)

        for text in candidates:
            try:
                payload = json.loads(text)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict) and "widgetStates" in payload:
                return text
        return False

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
            raise MarketplaceUnavailable(
                f"Профиль Chrome уже используется процессом {pid}"
            )
        logger.warning("Удаляю устаревшую блокировку профиля Chrome: pid=%s", pid)
        for name in ("SingletonLock", "SingletonCookie", "SingletonSocket"):
            path = self.profile_dir / name
            try:
                path.unlink()
            except FileNotFoundError:
                pass

    @staticmethod
    def _resolve_chrome_binary(
        configured: Optional[Union[str, Path]],
    ) -> Optional[Path]:
        if configured is None:
            return None
        binary = Path(configured).expanduser().resolve()
        if not binary.is_file():
            raise FileNotFoundError(f"Chrome не найден: {binary}")
        return binary
