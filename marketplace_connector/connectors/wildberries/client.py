"""WB client sharing the run's Chrome owner and challenge lock."""
import asyncio
from contextlib import asynccontextmanager
from urllib.parse import urlsplit

from playwright.async_api import Error as PlaywrightError

from ...browser.session import ChromeSession
from ...domain.errors import MarketplaceUnavailable
from ...ports.challenge import RejectChallengeHandler
from .identity import WildberriesRef
from .transport import HOME_URL, WildberriesTransport


class AsyncWildberriesClient:
    marketplace = 'wildberries'

    def __init__(self, profile_dir, challenge_handler=None, chrome_binary=None,
                 chrome_platform='x11', browser_channel='chrome', headless=False,
                 virtual_display=False, *, session=None, **transport_options):
        self.session = session or ChromeSession(profile_dir, chrome_binary=chrome_binary,
            chrome_platform=chrome_platform, browser_channel=browser_channel,
            headless=headless, virtual_display=virtual_display)
        self.challenge_handler = challenge_handler or RejectChallengeHandler()
        self._options = transport_options
        WildberriesTransport(None, None, **transport_options)
        self._transport = None
        self._open = False
        self._lock = asyncio.Lock()
        self._automatic = None
        self._users = 0

    @asynccontextmanager
    async def collection_session(self):
        if self._open:
            raise RuntimeError('Сеанс WB уже открыт')
        self._open = True
        try:
            async with self.session.collection_session() as context:
                self._transport = WildberriesTransport(context, self._prepare_storefront, **self._options)
                try:
                    yield
                finally:
                    await self._transport.close()
                    self._transport = None
        finally:
            self._open = False

    @asynccontextmanager
    async def _request_session(self):
        automatic = False
        async with self._lock:
            if self._automatic is not None or not self._open:
                if self._automatic is None:
                    manager = self.collection_session()
                    await manager.__aenter__()
                    self._automatic = manager
                self._users += 1
                automatic = True
            transport = self._transport
        try:
            if transport is None:
                raise MarketplaceUnavailable('Сеанс WB ещё не готов')
            yield transport
        finally:
            if automatic:
                async with self._lock:
                    self._users -= 1
                    if self._users == 0:
                        manager, self._automatic = self._automatic, None
                        await manager.__aexit__(None, None, None)

    async def fetch_product_async(self, external_id):
        ref = WildberriesRef.parse(external_id)
        async with self._request_session() as transport:
            return await transport.fetch(ref.external_id)

    async def _ready(self, page, timeout=15000):
        try:
            await page.wait_for_function('!!(window.wb?.user?.getUserGrade && window.wb?.xnm?.getXnmProducts)', timeout=timeout)
            location = urlsplit(page.url)
            return location.scheme == 'https' and location.netloc == 'www.wildberries.ru'
        except PlaywrightError:
            return False

    async def _prepare_storefront(self, page, *, force=False):
        await page.goto(HOME_URL, wait_until='domcontentloaded', timeout=90000)
        if not force and await self._ready(page):
            return
        async with self.session.challenge_lock:
            if not force and await self._ready(page, timeout=1000):
                return
            if self.session.headless or self.session.virtual_display:
                raise MarketplaceUnavailable('WB запросил ручную проверку. Откройте Chrome кнопкой в приложении, пройдите проверку Wildberries и повторите сбор.')
            await self.challenge_handler.handle_async(self.marketplace,
                'Wildberries: пройдите проверку на общей вкладке WB в Chrome и нажмите «Проверка пройдена».')
            await page.reload(wait_until='domcontentloaded', timeout=90000)
            if not await self._ready(page):
                raise MarketplaceUnavailable('WB не пропустил проверку после подтверждения пользователя')
