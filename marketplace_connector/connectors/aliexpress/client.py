"""Concurrent AliExpress JSON requests through one persistent Chrome session."""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager, suppress
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Union
from urllib.parse import urlparse

from playwright.async_api import Error as PlaywrightError

from ...domain.errors import MarketplaceUnavailable
from .json_transport import HOME_URL, AliExpressJsonTransport
from .models import AliExpressResponse
from .identity import AliExpressRef
from ...ports.challenge import ChallengeHandler, RejectChallengeHandler
from ...browser.session import ChromeSession


logger = logging.getLogger(__name__)


class AsyncAliExpressClient:
    """Read AliExpress cards through concurrent fetch calls on one storefront page."""

    marketplace = "aliexpress"
    ANTIBOT_MARKERS = ("_____tmd_____", "captcha", "капча", "пройдите проверку", "подтвердите, что вы человек", "проверка безопасности")

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
        session: ChromeSession | None = None,
        concurrency: int | None = 1,
        starts_per_second: float | None = 5,
        request_timeout: float = 30,
        max_attempts: int = 3,
        max_retry_wait: float = 30,
    ):
        self.session = session or ChromeSession(
            profile_dir, chrome_binary=chrome_binary, chrome_platform=chrome_platform,
            browser_channel=browser_channel, headless=headless, virtual_display=virtual_display,
        )
        self.challenge_handler = challenge_handler or RejectChallengeHandler()
        if json_wait_seconds <= 0:
            raise ValueError("json_wait_seconds должен быть положительным")
        self.json_wait_seconds = json_wait_seconds
        self.headless = self.session.headless
        self.virtual_display = self.session.virtual_display
        self._challenge_lock = self.session.challenge_lock
        self._transport_options = dict(concurrency=concurrency, starts_per_second=starts_per_second,
                                       request_timeout=request_timeout, max_attempts=max_attempts,
                                       max_retry_wait=max_retry_wait)
        # Validate before launching Chrome. The real transport belongs to a session.
        AliExpressJsonTransport(None, None, **self._transport_options)
        self._transport = None
        self._session_lock = asyncio.Lock()
        self._auto_session = None
        self._auto_users = 0
        self._session_open = False
        self._storefront_prepared = False

    @asynccontextmanager
    async def collection_session(self):
        if self._session_open:
            raise RuntimeError("Сеанс AliExpress уже открыт")
        self._session_open = True
        self._storefront_prepared = False
        try:
            async with self.session.collection_session() as context:
                try:
                    self._transport = AliExpressJsonTransport(context, self._prepare_storefront, **self._transport_options)
                    yield
                finally:
                    if self._transport is not None:
                        await self._transport.close()
                    self._transport = None
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
                raise MarketplaceUnavailable("Сеанс AliExpress ещё не готов")
            yield transport
        finally:
            if automatic:
                async with self._session_lock:
                    self._auto_users -= 1
                    if self._auto_users == 0:
                        session, self._auto_session = self._auto_session, None
                        await session.__aexit__(None, None, None)

    async def _prepare_storefront(self, page):
        recovering = self._storefront_prepared
        response = await page.goto(HOME_URL, wait_until="domcontentloaded", timeout=90_000)
        if await self._is_antibot_page_async(page):
            if not await self._wait_for_antibot_async(page):
                await self._handle_antibot_async(page, "сессия")
            # The challenge can replace its initial 403 document. Its stale
            # navigation response no longer describes the current page.
            response = None
        elif recovering or response is not None and response.status in (401, 403, 429):
            await self._handle_antibot_async(page, "сессия", force=True)
            response = None
        location = urlparse(page.url)
        if (location.scheme != "https" or location.netloc != "aliexpress.ru"
                or response is not None and response.status >= 400):
            raise MarketplaceUnavailable("Не удалось открыть главную страницу AliExpress")
        self._storefront_prepared = True

    async def fetch_product_async(self, external_id: str) -> AliExpressResponse:
        article = self.normalize_product_id(external_id)
        raw_text = await self.fetch_raw_text_async(article)
        return AliExpressResponse(
            external_id=article,
            raw_text=raw_text,
            received_at=datetime.now(timezone.utc),
        )

    async def fetch_raw_text_async(self, external_id: str) -> str:
        article = self.normalize_product_id(external_id)
        async with self._request_session() as transport:
            return await transport.fetch(article)

    async def _is_antibot_page_async(self, page) -> bool:
        parts = []
        with suppress(PlaywrightError):
            parts.append(await page.title())
        with suppress(PlaywrightError):
            parts.append(await page.locator("body").inner_text(timeout=1_000))
        return "_____tmd_____" in page.url or self._is_antibot_text("\n".join(parts))

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
            logger.warning("AliExpress запросил проверку для артикула %s", article)
            if self.headless or self.virtual_display:
                raise MarketplaceUnavailable(
                    "AliExpress запросил ручную проверку. Откройте Chrome кнопкой в приложении, "
                    "пройдите проверку на AliExpress и повторите сбор."
                )
            message = (
                f"AliExpress ({article}): перейдите на общую вкладку AliExpress в Chrome, "
                "пройдите проверку и нажмите «Проверка пройдена» в приложении."
            )
            await self.challenge_handler.handle_async(self.marketplace, message)
            response = await page.reload(wait_until="domcontentloaded", timeout=90_000)
            if (not await self._wait_for_antibot_async(page)
                    or response is not None and isinstance(response.status, int) and response.status >= 400):
                raise MarketplaceUnavailable(
                    "AliExpress не пропустил проверку после подтверждения пользователя"
                )

    @classmethod
    def _is_antibot_text(cls, text: str) -> bool:
        lowered = text.lower()
        return any(marker in lowered for marker in cls.ANTIBOT_MARKERS)

    @staticmethod
    def normalize_product_id(value) -> str:
        return AliExpressRef.parse(value).external_id
