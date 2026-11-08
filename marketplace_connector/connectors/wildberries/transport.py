"""Concurrent native WB runtime with per-article state and HTTP admission."""
from __future__ import annotations

import asyncio
import json
import math
from contextlib import suppress
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urlsplit, parse_qs
from uuid import uuid4

from playwright.async_api import Error as PlaywrightError

from ...application.collection_policy import MAX_IN_FLIGHT_REQUESTS
from ...domain.errors import MarketplaceSchemaChanged, MarketplaceUnavailable, RateLimited, UnsafeBrowserTeardown
from .identity import WildberriesRef

HOME_URL = 'https://www.wildberries.ru/'
RUNTIME_SCRIPT = Path(__file__).with_name('runtime.js').read_text()
NETWORK_SCRIPT = Path(__file__).with_name('network.js').read_text()
ABORT_SCRIPT = """async id => {
 const r = globalThis.__priceWatchWbRequests?.get(id);
 if (!r) return true;
 r.controller.abort();
 return await Promise.race([r.done.then(() => true), new Promise(resolve => setTimeout(() => resolve(false), 1500))]);
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
    if parsed.hostname and (parsed.hostname == 'wildberries.ru' or parsed.hostname.endswith('.wildberries.ru') or parsed.hostname == 'wb.ru' or parsed.hostname.endswith('.wb.ru')):
        if '/cards/v4/detail' in parsed.path:
            return 'detail'
        if parsed.path.endswith('/v6/grade'):
            return 'grade'
    return None


@dataclass
class ArticleState:
    counts: dict = field(default_factory=dict)
    errors: dict = field(default_factory=dict)
    fatal: Exception | None = None
    task: asyncio.Task | None = None
    waiters: int = 0
    responses: set = field(default_factory=set)


class WildberriesTransport:
    def __init__(self, context, prepare_page, *, request_timeout=45, max_attempts=3,
                 max_in_flight_requests=MAX_IN_FLIGHT_REQUESTS, max_retry_wait=30):
        for name, value in (('max_attempts', max_attempts), ('max_in_flight_requests', max_in_flight_requests)):
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise ValueError(f'{name} должен быть положительным целым')
        for value in (request_timeout, max_retry_wait):
            if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value) or value <= 0:
                raise ValueError('Ограничения WB должны быть конечными положительными числами')
        self.context, self.prepare_page = context, prepare_page
        self.request_timeout, self.max_attempts = request_timeout, max_attempts
        self.max_in_flight_requests, self.max_retry_wait = max_in_flight_requests, max_retry_wait
        self.page = None
        self._bootstrap = None
        self._recovery = None
        self._generation = 0
        self._articles = {}
        self._profile = ArticleState()
        self._profiles = {0: self._profile}
        self._wallet_generation = 0
        self._responses = set()
        self._owners = set()
        self._closed = False
        self._failure = None

    def _state(self, url):
        kind = endpoint(url)
        if kind == 'grade':
            return kind, None, self._profile
        if kind == 'detail':
            ids = parse_qs(urlsplit(url).query).get('nm', [])
            for article in self._articles:
                if any(article in value.split(',') for value in ids):
                    return kind, article, self._articles[article]
        return None, None, None

    async def _route(self, route):
        kind, _, state = self._state(route.request.url)
        if state is None:
            await route.fallback()
            return
        try:
            error = state.errors.get(kind)
            blocked = isinstance(error, MarketplaceUnavailable) and any(
                token in str(error) for token in ('HTTP 403', 'HTTP 498', 'HTTP 401'))
            if self._closed or state.fatal or blocked:
                await route.abort()
                return
            state.counts[kind] = state.counts.get(kind, 0) + 1
            if state.counts[kind] > self.max_attempts:
                state.fatal = MarketplaceUnavailable('WB превысил лимит сетевых попыток')
                await route.abort()
                return
            await route.fallback()
        except PlaywrightError:
            pass

    def _response(self, response):
        kind, article, state = self._state(response.url)
        if state is not None:
            task = asyncio.create_task(self._inspect(response, kind, article, state, self._generation))
            self._responses.add(task)
            state.responses.add(task)
            task.add_done_callback(self._responses.discard)
            task.add_done_callback(state.responses.discard)

    async def _inspect(self, response, kind, article, state, generation):
        status = response.status
        try:
            if status == 429:
                state.errors[kind] = RateLimited('WB ограничил частоту запросов', retry_after=retry_after(response.headers.get('retry-after')))
                return
            if status != 200:
                state.errors[kind] = MarketplaceUnavailable(f'WB: HTTP {status}')
                if status in (401, 403, 498):
                    if self._generation == 0 and self._recovery is None:
                        # The SDK can already be retrying in the paused HTTP
                        # queue; recovery cannot wait for its parent Promise.
                        self._recovery = asyncio.create_task(self._recover())
                    elif generation == self._generation and generation > 0:
                        self._failure = MarketplaceUnavailable('WB отклонил доступ после восстановления сессии')
                        await self.page.close()
                return
            if 'application/json' not in response.headers.get('content-type', '').lower():
                raise ValueError('неожиданный тип ответа')
            data = await response.json()
            if not isinstance(data, dict):
                raise ValueError('неверная схема')
            if kind == 'grade':
                if data.get('state') != 0 or not isinstance(data.get('payload'), dict):
                    raise ValueError('неверные условия кошелька')
                if not isinstance(data['payload'].get('payments'), list):
                    raise ValueError('неверные способы оплаты')
            elif article:
                products = data.get('products')
                if not isinstance(products, list) or sum(str(p.get('id')) == article for p in products if isinstance(p, dict)) != 1:
                    raise ValueError('ответ не содержит ровно один выбранный товар')
                if parse_qs(urlsplit(response.url).query).get('curr') != ['rub']:
                    raise ValueError('неподтверждённая валюта')
            state.errors.pop(kind, None)
        except (ValueError, TypeError, PlaywrightError):
            state.fatal = MarketplaceSchemaChanged(f'WB: неверный JSON {kind}')

    async def _drain(self, state=None):
        responses = self._responses if state is None else state.responses
        while responses:
            tasks = tuple(responses)
            responses.difference_update(tasks)
            await asyncio.gather(*tasks)

    def _new_wallet(self):
        self._wallet_generation += 1
        self._profile = ArticleState()
        self._profiles[self._wallet_generation] = self._profile
        return self._wallet_generation

    async def _start(self):
        self.page = await self.context.new_page()
        config = json.dumps(dict(maxInFlight=self.max_in_flight_requests,
            timeoutMs=self.request_timeout * 1000, maxRetryWaitMs=self.max_retry_wait * 1000))
        await self.page.expose_function('__priceWatchWbWalletStarting', self._new_wallet)
        await self.page.add_init_script(f'({NETWORK_SCRIPT})({config})')
        await self.page.route('**/*', self._route)
        self.page.on('response', self._response)
        await self.prepare_page(self.page)

    async def fetch(self, external_id):
        ref = WildberriesRef.parse(external_id)
        owner = asyncio.current_task()
        self._owners.add(owner)
        state = None
        try:
            if self._failure:
                raise self._failure
            if self._closed:
                raise MarketplaceUnavailable('Сеанс WB закрыт')
            if self._bootstrap is None:
                self._bootstrap = asyncio.create_task(self._start())
            await asyncio.shield(self._bootstrap)
            if self._recovery is not None:
                await asyncio.shield(self._recovery)
            state = self._articles.get(ref.nm_id)
            if state is None:
                state = self._articles[ref.nm_id] = ArticleState()
                state.task = asyncio.create_task(self._fetch_article(ref, state))
            state.waiters += 1
            return await asyncio.shield(state.task)
        finally:
            try:
                if state is not None:
                    await self._release_article(ref.nm_id, state)
            finally:
                self._owners.discard(owner)

    async def _release_article(self, article, state):
        state.waiters -= 1
        if state.waiters:
            return
        try:
            # An ordinary success/error was already propagated by shield.
            # Only the last cancelled waiter must stop an unfinished task.
            if not state.task.done():
                state.task.cancel()
                with suppress(asyncio.CancelledError):
                    await state.task
        finally:
            if state.waiters == 0 and self._articles.get(article) is state:
                self._articles.pop(article, None)

    async def _recover(self):
        try:
            # Pause new native HTTP, drain active bodies, then replace only the
            # WB document. Queued evaluations observe document loss and retry.
            await self.page.evaluate('__priceWatchWbNetwork.paused = true')
            await self.page.wait_for_function('__priceWatchWbNetwork.active.size === 0',
                timeout=(self.request_timeout + 2) * 1000)
            await self.prepare_page(self.page, force=True)
            self._generation += 1
            self._profile = ArticleState()
        except BaseException as exc:
            self._failure = exc
            raise

    async def _fetch_article(self, ref, state):
        generation = self._generation
        for attempt in range(2):
            try:
                return await self._evaluate_article(ref, state)
            except UnsafeBrowserTeardown as exc:
                self._failure = exc
                with suppress(PlaywrightError):
                    await self.page.close()
                raise
            except MarketplaceUnavailable as exc:
                access = any(token in str(exc) for token in ('HTTP 403', 'HTTP 498', 'HTTP 401'))
                if self._failure:
                    raise self._failure
                if access and self._generation > 0 and generation == self._generation:
                    self._failure = MarketplaceUnavailable('WB отклонил доступ после восстановления сессии')
                    # Fatal stage failure: stopping its page drains every queued
                    # native helper before any later marketplace can start.
                    await self.page.close()
                    raise self._failure
                recovering = self._recovery is not None and (not self._recovery.done() or self._generation != generation)
                if attempt or not access and not recovering:
                    raise
                if self._recovery is None:
                    self._recovery = asyncio.create_task(self._recover())
                await asyncio.shield(self._recovery)
                state.counts.clear()
                state.errors.clear()
                state.fatal = None
                generation = self._generation
        raise MarketplaceUnavailable('WB: доступ не восстановлен')

    async def _evaluate_article(self, ref, state):
        request_id = uuid4().hex
        evaluation = asyncio.create_task(self.page.evaluate(RUNTIME_SCRIPT, {
            'id': request_id, 'nmId': ref.nm_id, 'timeoutMs': self.request_timeout * 1000}))
        try:
            result = await asyncio.shield(evaluation)
            if isinstance(result, dict) and result.get('errorKind') == 'unsafe':
                raise UnsafeBrowserTeardown('WB: native helper не завершился; сбор остановлен')
            await self._drain(state)
            profile = self._profiles.get(result.get('walletGeneration') if isinstance(result, dict) else None, self._profile)
            await self._drain(profile)
            for current in (state, profile):
                if current.fatal:
                    raise current.fatal
                if current.errors:
                    raise next(iter(current.errors.values()))
            if await self.page.evaluate('Boolean(__priceWatchWbNetwork.unsupportedXHR)'):
                raise MarketplaceSchemaChanged('WB перешёл на неподдерживаемый XHR transport')
            if not isinstance(result, dict) or result.get('error'):
                raise MarketplaceSchemaChanged('WB: ' + str(result.get('error') if isinstance(result, dict) else 'неверный runtime ответ'))
            return result
        except asyncio.CancelledError:
            try:
                stopped = await asyncio.wait_for(self.page.evaluate(ABORT_SCRIPT, request_id), 2)
                if stopped is not True:
                    raise UnsafeBrowserTeardown('WB: не подтверждена остановка native helpers')
            except (PlaywrightError, TimeoutError) as exc:
                raise UnsafeBrowserTeardown('WB: не подтверждена отмена запроса') from exc
            finally:
                evaluation.cancel()
                await asyncio.gather(evaluation, return_exceptions=True)
            raise
        except PlaywrightError as exc:
            raise MarketplaceUnavailable('Ошибка браузера WB') from exc

    async def _close_page(self):
        if self.page is not None:
            page, self.page = self.page, None
            page.remove_listener('response', self._response)
            with suppress(PlaywrightError):
                await page.close()
            await self._drain()

    async def close(self):
        self._closed = True
        tasks = self._owners - {asyncio.current_task()}
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        for shared in (self._bootstrap, self._recovery):
            if shared is not None:
                shared.cancel()
                await asyncio.gather(shared, return_exceptions=True)
        await self._close_page()
