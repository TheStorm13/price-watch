"""WB runtime transport with bounded native retries and an owned storefront page.

WB calls are serialized on this page so native runtime/cache mutations and access
recovery cannot race another size. Other marketplace pages remain concurrent.
"""
from __future__ import annotations

import asyncio
import math
from contextlib import suppress
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urlsplit, parse_qs
from uuid import uuid4

from playwright.async_api import Error as PlaywrightError

from ...domain.errors import MarketplaceSchemaChanged, MarketplaceUnavailable, RateLimited
from .identity import WildberriesRef

HOME_URL = 'https://www.wildberries.ru/'
RUNTIME_SCRIPT = Path(__file__).with_name('runtime.js').read_text()
ABORT_SCRIPT = """async id => {
 const r = globalThis.__priceWatchWbRequests?.get(id);
 if (r) {r.controller.abort(); await Promise.race([r.done, new Promise(resolve => setTimeout(resolve, 1000))]);}
}"""


def retry_after(value):
    try:
        if value and value.strip().isascii() and value.strip().isdigit():
            return float(value)
        date = parsedate_to_datetime(value)
        return max(0, (date - datetime.now(timezone.utc)).total_seconds())
    except (ValueError, TypeError, OverflowError):
        return 1.0


def endpoint(url):
    parsed = urlsplit(url)
    if parsed.hostname and (parsed.hostname == 'wildberries.ru' or parsed.hostname.endswith('.wildberries.ru')):
        if '/cards/v4/detail' in parsed.path:
            return 'detail'
        if parsed.path.endswith('/v6/grade'):
            return 'grade'
    return None


class WildberriesTransport:
    def __init__(self, context, prepare_page, *, request_timeout=45, max_attempts=3,
                 starts_per_second=3, max_retry_wait=30):
        if isinstance(max_attempts, bool) or not isinstance(max_attempts, int) or max_attempts < 1:
            raise ValueError('max_attempts должен быть положительным целым')
        for value in (request_timeout, starts_per_second, max_retry_wait):
            if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value) or value <= 0:
                raise ValueError('Ограничения WB должны быть конечными положительными числами')
        self.context, self.prepare_page = context, prepare_page
        self.request_timeout, self.max_attempts = request_timeout, max_attempts
        self.rate, self.max_retry_wait = starts_per_second, max_retry_wait
        self.page = None
        self._lock = asyncio.Lock()
        self._dispatch = asyncio.Lock()
        self._cooldown = self._next_start = 0
        self._counts, self._errors = {}, {}
        self._fatal = None
        self._responses = set()
        self._owners = set()
        self._closed = False
        self._article = None
        self._cancelled = False

    async def _gate(self):
        async with self._dispatch:
            while True:
                now = asyncio.get_running_loop().time()
                delay = max(self._cooldown, self._next_start) - now
                if delay > self.max_retry_wait:
                    raise RateLimited('WB требует длительную паузу', retry_after=delay)
                if delay <= 0:
                    self._next_start = now + 1 / self.rate
                    return
                await asyncio.sleep(delay)

    def _tracked_endpoint(self, url):
        kind = endpoint(url)
        if kind == 'detail':
            ids = parse_qs(urlsplit(url).query).get('nm', [])
            if self._article is None or not any(self._article in value.split(',') for value in ids):
                return None  # Ignore unrelated storefront recommendations.
        return kind

    async def _route(self, route):
        kind = self._tracked_endpoint(route.request.url)
        if not kind:
            await route.fallback()
            return
        try:
            access_error = self._errors.get(kind)
            blocked = isinstance(access_error, MarketplaceUnavailable) and any(
                token in str(access_error) for token in ('HTTP 403', 'HTTP 498', 'HTTP 401'))
            if self._closed or self._cancelled or self._fatal or blocked:
                await route.abort()
                return
            self._counts[kind] = self._counts.get(kind, 0) + 1
            if self._counts[kind] > self.max_attempts:
                self._fatal = MarketplaceUnavailable('WB превысил лимит сетевых попыток')
                await route.abort()
                return
            await self._gate()
            if self._cancelled or self._closed:
                await route.abort()
                return
            await route.fallback()
        except RateLimited as exc:
            self._fatal = exc
            await route.abort()
        except PlaywrightError:
            pass  # The browser may already have aborted this request.

    def _response(self, response):
        kind = self._tracked_endpoint(response.url)
        if kind:
            task = asyncio.create_task(self._inspect(response, kind, self._article))
            self._responses.add(task)
            task.add_done_callback(self._responses.discard)

    async def _inspect(self, response, kind, article):
        status = response.status
        try:
            if status == 429:
                seconds = retry_after(response.headers.get('retry-after'))
                self._cooldown = max(self._cooldown, asyncio.get_running_loop().time() + seconds)
                self._errors[kind] = RateLimited('WB ограничил частоту запросов', retry_after=seconds)
                return
            if status != 200:
                self._errors[kind] = MarketplaceUnavailable(f'WB: HTTP {status}')
                return
            if 'application/json' not in response.headers.get('content-type', '').lower():
                raise ValueError('неожиданный тип ответа')
            data = await response.json()
            if not isinstance(data, dict):
                raise ValueError('неверная схема')
            if kind == 'grade':
                if data.get('state') != 0 or not isinstance(data.get('payload'), dict):
                    raise ValueError('неверные условия кошелька')
                payments = data['payload'].get('payments')
                if not isinstance(payments, list):
                    raise ValueError('неверные способы оплаты')
            elif article:
                products = data.get('products')
                if not isinstance(products, list) or sum(str(p.get('id')) == article for p in products if isinstance(p, dict)) != 1:
                    raise ValueError('ответ не содержит ровно один выбранный товар')
                if parse_qs(urlsplit(response.url).query).get('curr') != ['rub']:
                    raise ValueError('неподтверждённая валюта')
            self._errors.pop(kind, None)
        except (ValueError, TypeError, PlaywrightError):
            self._fatal = MarketplaceSchemaChanged(f'WB: неверный JSON {kind}')

    async def _drain(self):
        while self._responses:
            tasks = tuple(self._responses)
            # Completed gather() can return without yielding. Remove the snapshot
            # now rather than depending on queued done callbacks to clear it.
            self._responses.difference_update(tasks)
            await asyncio.gather(*tasks)

    async def _start(self):
        self.page = await self.context.new_page()
        await self.page.route('**/*', self._route)
        self.page.on('response', self._response)
        await self.prepare_page(self.page)

    async def fetch(self, external_id):
        ref = WildberriesRef.parse(external_id)  # Legacy IDs fail before browser/network.
        owner = asyncio.current_task()
        self._owners.add(owner)
        try:
            async with self._lock:
                if self._closed:
                    raise MarketplaceUnavailable('Сеанс WB закрыт')
                self._counts, self._errors, self._fatal = {}, {}, None
                self._article, self._cancelled = ref.nm_id, False
                try:
                    if self.page is None:
                        await self._start()
                    for recovery in range(2):
                        result = await self._evaluate(ref)
                        await self._drain()
                        if self._fatal:
                            raise self._fatal
                        error = next(iter(self._errors.values()), None)
                        if error:
                            # Recovery is serialized; no neighboring target loses I/O.
                            if recovery == 0 and isinstance(error, MarketplaceUnavailable) and any(
                                    token in str(error) for token in ('HTTP 403', 'HTTP 498', 'HTTP 401')):
                                await self.prepare_page(self.page, force=True)
                                self._errors.clear()
                                continue
                            raise error
                        if isinstance(result, dict) and result.get('errorKind') == 'timeout':
                            await self._close_page()
                            raise MarketplaceUnavailable('Таймаут запроса WB')
                        if not isinstance(result, dict) or result.get('error'):
                            raise MarketplaceSchemaChanged('WB: ' + str(result.get('error') if isinstance(result, dict) else 'неверный runtime ответ'))
                        if result.get('metadataTimedOut'):
                            await self._close_page()
                        return result
                    raise MarketplaceUnavailable('WB: доступ не восстановлен')
                except (PlaywrightError, TimeoutError) as exc:
                    raise MarketplaceUnavailable('Таймаут или ошибка браузера WB') from exc
                finally:
                    self._article = None
        finally:
            self._owners.discard(owner)

    async def _evaluate(self, ref):
        request_id = uuid4().hex
        evaluation = asyncio.create_task(self.page.evaluate(RUNTIME_SCRIPT, {
            'id': request_id, 'nmId': ref.nm_id, 'timeoutMs': self.request_timeout * 1000}))
        try:
            return await asyncio.wait_for(asyncio.shield(evaluation), self.request_timeout + 1)
        except (asyncio.CancelledError, TimeoutError):
            self._cancelled = True
            with suppress(PlaywrightError, TimeoutError):
                await asyncio.wait_for(self.page.evaluate(ABORT_SCRIPT, request_id), 2)
            evaluation.cancel()
            await asyncio.gather(evaluation, return_exceptions=True)
            # Grade/static helpers do not accept a signal. Closing only this WB
            # page stops them before the next target; shared Chrome stays alive.
            await self._close_page()
            raise

    async def _close_page(self):
        if self.page is not None:
            page, self.page = self.page, None
            page.remove_listener('response', self._response)
            with suppress(PlaywrightError):
                await page.unroute_all(behavior='ignoreErrors')
                await page.close()
            await self._drain()

    async def close(self):
        self._closed = True
        tasks = self._owners - {asyncio.current_task()}
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        await self._close_page()
