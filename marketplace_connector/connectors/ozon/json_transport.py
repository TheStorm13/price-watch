"""Bounded composer requests in a single, owned Ozon storefront page.

The dispatch policy is local: it is not a published Ozon rate limit.
"""

from __future__ import annotations

import asyncio
import json
import math
from contextlib import suppress
from datetime import datetime, timezone
from decimal import Decimal
from email.utils import parsedate_to_datetime
from urllib.parse import quote, urlsplit
from uuid import uuid4

from playwright.async_api import Error as PlaywrightError

from ...domain.errors import MarketplaceSchemaChanged, MarketplaceUnavailable, ProductNotFound, RateLimited
from .mapper import OzonMapper
from .parser import OzonProductParser


HOME_URL = "https://www.ozon.ru/"
API_PATH = "/api/composer-api.bx/page/json/v2"

# The timer covers both headers and the body. Cancellation waits for fetch to
# settle before Python releases the slot; neighboring controllers are untouched.
FETCH_SCRIPT = """async ({url, id, timeoutMs}) => {
    const registry = globalThis.__priceWatchRequests ??= new Map();
    const controller = new AbortController();
    let finished;
    const done = new Promise(resolve => { finished = resolve; });
    registry.set(id, {controller, done});
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    try {
        const response = await fetch(url, {
            method: 'GET', credentials: 'include', signal: controller.signal,
            headers: {'accept': 'application/json, text/plain, */*'}
        });
        return {status: response.status, contentType: response.headers.get('content-type') || '',
            retryAfter: response.headers.get('retry-after'), url: response.url,
            redirected: response.redirected, text: await response.text()};
    } catch (_) {
        return {error: controller.signal.aborted ? 'timeout' : 'network'};
    } finally {
        clearTimeout(timer);
        registry.delete(id);
        finished();
    }
}"""

ABORT_SCRIPT = """async (id) => {
    const request = globalThis.__priceWatchRequests?.get(id);
    if (request) { request.controller.abort(); await request.done; }
}"""


def retry_after_seconds(value, *, now=None, fallback=1.0):
    """Accept delta-seconds or an HTTP date; never treat NaN as a deadline."""
    if not isinstance(value, str):
        return fallback
    value = value.strip()
    if value.isascii() and value.isdigit():
        try:
            seconds = float(value)
            return seconds if math.isfinite(seconds) else float("inf")
        except ValueError:
            return float("inf")
    try:
        date = parsedate_to_datetime(value)
        if date.tzinfo is None:
            return fallback
        return max(0.0, (date - (now or datetime.now(timezone.utc))).total_seconds())
    except (ValueError, TypeError, OverflowError):
        return fallback


def _reject_non_json_constant(_value):
    raise ValueError("Non-finite number is not a JSON value")


def validate_composer_text(raw_text, article):
    try:
        payload = json.loads(raw_text, parse_float=Decimal, parse_constant=_reject_non_json_constant)
    except (ValueError, TypeError) as exc:
        raise MarketplaceSchemaChanged("Ozon вернул некорректный JSON") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("widgetStates"), dict):
        raise MarketplaceSchemaChanged("В ответе Ozon нет объекта widgetStates")
    # Missing widgets retain the parser's existing fallback priorities. Present
    # but corrupt consumed widgets must not silently become empty product data.
    prefixes = (
        "webProductHeading-", "webPrice-", "webStickyProducts-", "webCurrentSeller-",
        "webReviewProductScore-", "webShortCharacteristics-", "webAspects-", "webGallery-",
    )
    for name, value in payload["widgetStates"].items():
        if not name.startswith(prefixes):
            continue
        if isinstance(value, str):
            try:
                value = json.loads(value, parse_float=Decimal, parse_constant=_reject_non_json_constant)
            except ValueError as exc:
                raise MarketplaceSchemaChanged("Повреждён товарный виджет Ozon") from exc
        if not isinstance(value, dict):
            raise MarketplaceSchemaChanged("Изменился формат товарного виджета Ozon")
    try:
        data = OzonProductParser.parse(payload, expected_external_id=article)
    except ProductNotFound:
        # This is a valid composer document. The connector retains ownership of
        # the established, narrowly evidenced ProductNotFound business rule.
        return raw_text
    try:
        OzonMapper.to_card(data)
    except (TypeError, ValueError, AttributeError, KeyError) as exc:
        raise MarketplaceSchemaChanged("Изменилась структура товарных данных Ozon") from exc
    return raw_text


class OzonJsonTransport:
    def __init__(self, context, prepare_page, *, concurrency=5, starts_per_second=5,
                 request_timeout=30, max_attempts=3, max_retry_wait=30):
        for name, value in (("concurrency", concurrency), ("max_attempts", max_attempts)):
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ValueError(f"{name} должен быть положительным целым")
        for name, value in (("starts_per_second", starts_per_second),
                            ("request_timeout", request_timeout), ("max_retry_wait", max_retry_wait)):
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
                raise ValueError(f"{name} должен быть конечным положительным числом")
        self.context = context
        self.prepare_page = prepare_page
        self.concurrency = concurrency
        self.rate = starts_per_second
        self.request_timeout = request_timeout
        self.max_attempts = max_attempts
        self.max_retry_wait = max_retry_wait
        self.page = None
        self._bootstrap = None
        self._recovery = None
        self._generation = 0
        self._condition = asyncio.Condition()
        self._active = 0
        self._tokens = float(concurrency)
        self._updated = 0.0
        self._cooldown = 0.0
        self._failure = None
        self._closed = False
        self._owners = set()

    async def _start(self):
        try:
            self.page = await self.context.new_page()
            await self.prepare_page(self.page)
        except BaseException as exc:
            if self.page is not None:
                with suppress(PlaywrightError):
                    await self.page.close()
                self.page = None
            if isinstance(exc, (PlaywrightError, TimeoutError)):
                raise MarketplaceUnavailable("Не удалось открыть сессию Ozon") from exc
            raise

    async def fetch(self, article):
        owner = asyncio.current_task()
        self._owners.add(owner)
        try:
            if self._closed:
                raise MarketplaceUnavailable("Сеанс Ozon закрыт")
            if (self._bootstrap is not None and self._bootstrap.done()
                    and not self._bootstrap.cancelled()
                    and isinstance(self._bootstrap.exception(), MarketplaceUnavailable)):
                # A later application attempt may retry temporary preparation.
                # Existing waiters still observe their original failed task.
                self._bootstrap = None
            if self._bootstrap is None:
                self._bootstrap = asyncio.create_task(self._start())
                self._bootstrap.add_done_callback(self._retrieve_exception)
            await asyncio.shield(self._bootstrap)
            # Keep the product page (gallery/aspects) even when the SKU is sold
            # out; Ozon otherwise redirects it to a search/recommendations page.
            url = HOME_URL.rstrip("/") + API_PATH + "?url=" + quote(f"/product/{article}/?oos_search=false", safe="")
            for attempt in range(self.max_attempts):
                result, generation = await self._attempt(url)
                recovering = self._needs_recovery(result)
                if recovering:
                    await self._join_recovery(generation)
                    error = self._access_error()
                else:
                    error = self._response_error(result)
                    if error is None:
                        return self._validated_text(result, article)
                if attempt + 1 == self.max_attempts:
                    raise error
                if result.get("status") == 429 or recovering:
                    # The gate rechecks the shared deadline on every dispatch.
                    continue
                await asyncio.sleep(min(0.5 * 2 ** attempt, self.max_retry_wait))
            raise AssertionError("unreachable")
        finally:
            self._owners.discard(owner)

    def _response_error(self, result):
        """Return a retryable error, or raise immediately for a permanent one."""
        if result.get("error"):
            message = "Таймаут запроса Ozon" if result["error"] == "timeout" else "Сетевая ошибка запроса Ozon"
            return MarketplaceUnavailable(message)
        status = result.get("status")
        if status == 429:
            remaining = max(0, self._cooldown - asyncio.get_running_loop().time())
            return RateLimited("Ozon ограничил частоту запросов", retry_after=remaining)
        if isinstance(status, int) and 500 <= status < 600:
            return MarketplaceUnavailable(f"Ozon временно недоступен (HTTP {status})")
        if status != 200:
            raise MarketplaceUnavailable(f"Ozon вернул неожиданный HTTP-статус {status}")
        return None

    @staticmethod
    def _validated_text(result, article):
        content_type = result.get("contentType", "").lower().split(";", 1)[0].strip()
        if content_type != "application/json" and not content_type.endswith("+json"):
            raise MarketplaceSchemaChanged("Ozon вернул неожиданный тип ответа вместо JSON")
        return validate_composer_text(result.get("text"), article)

    @staticmethod
    def _access_error():
        return MarketplaceUnavailable(
            "Ozon отклонил доступ после восстановления сессии. "
            "Откройте Chrome, проверьте доступ к Ozon и повторите сбор."
        )

    async def _reserve(self):
        async with self._condition:
            while True:
                if self._closed:
                    raise MarketplaceUnavailable("Сеанс Ozon закрыт")
                if self._failure:
                    raise self._failure
                now = asyncio.get_running_loop().time()
                remaining = max(0.0, self._cooldown - now)
                if remaining > self.max_retry_wait:
                    raise RateLimited("Ozon требует длительную паузу перед запросами", retry_after=remaining)
                self._tokens = min(self.concurrency, self._tokens + (now - self._updated) * self.rate)
                self._updated = now
                if (self._recovery is not None and not self._recovery.done()) or self._active >= self.concurrency:
                    await self._condition.wait()
                    continue
                delay = max(remaining, (1 - self._tokens) / self.rate, 0)
                if delay:
                    with suppress(TimeoutError):
                        await asyncio.wait_for(self._condition.wait(), timeout=delay)
                    continue
                self._active += 1
                self._tokens -= 1
                return self._generation

    async def _attempt(self, url):
        generation = await self._reserve()
        result = None
        try:
            result = await self._evaluate(url)
            return result, generation
        finally:
            async with self._condition:
                if result is not None:
                    if result.get("status") == 429:
                        wait = retry_after_seconds(result.get("retryAfter"))
                        self._cooldown = max(self._cooldown, asyncio.get_running_loop().time() + wait)
                    if self._needs_recovery(result) and self._generation == generation and self._recovery is None:
                        # Pause atomically, before releasing the failing slot.
                        self._recovery = asyncio.create_task(self._recover())
                        self._recovery.add_done_callback(self._retrieve_exception)
                    elif self._needs_recovery(result) and generation > 0:
                        self._failure = self._access_error()
                self._active -= 1
                self._condition.notify_all()

    @staticmethod
    def _needs_recovery(result):
        status = result.get("status")
        if status in (401, 403):
            return True
        if status != 200:
            return False
        final = urlsplit(result.get("url", ""))
        if final.scheme != "https" or final.netloc != "www.ozon.ru" or final.path != API_PATH:
            return True
        text = result.get("text", "")
        if "text/html" in result.get("contentType", "").lower() or text.lstrip().startswith("<"):
            return True
        # Match the observed block envelope at its root without inspecting or
        # logging private values. A product mentioning anti-bot is still data.
        if '"incidentId"' in text and '"blockURL"' in text and '"widgetStates"' not in text:
            try:
                envelope = json.loads(text)
            except ValueError:
                return False
            return isinstance(envelope, dict) and {"incidentId", "blockURL"} <= envelope.keys()
        return False

    async def _recover(self):
        try:
            async with self._condition:
                await self._condition.wait_for(lambda: self._active == 0)
            await self.prepare_page(self.page)
            self._generation += 1
        except (PlaywrightError, TimeoutError) as exc:
            self._failure = MarketplaceUnavailable("Не удалось восстановить сессию Ozon")
            raise self._failure from exc
        except Exception as exc:
            self._failure = exc
            raise
        finally:
            async with self._condition:
                self._condition.notify_all()

    async def _join_recovery(self, generation):
        if self._recovery is not None:
            await asyncio.shield(self._recovery)
        if self._generation <= generation:
            raise MarketplaceUnavailable("Ozon отклонил доступ. Откройте Chrome, проверьте доступ к Ozon и повторите сбор.")

    async def _evaluate(self, url):
        request_id = uuid4().hex
        evaluation = asyncio.create_task(self.page.evaluate(FETCH_SCRIPT, {
            "url": url, "id": request_id, "timeoutMs": self.request_timeout * 1000,
        }))
        try:
            result = await asyncio.wait_for(asyncio.shield(evaluation), self.request_timeout + 2)
            if not isinstance(result, dict):
                raise MarketplaceSchemaChanged("Некорректный результат браузерного запроса Ozon")
            return result
        except (asyncio.CancelledError, TimeoutError):
            try:
                await asyncio.wait_for(self.page.evaluate(ABORT_SCRIPT, request_id), timeout=2)
            except (PlaywrightError, TimeoutError):
                self._failure = MarketplaceUnavailable("Страница Ozon не отвечает; повторите сбор")
            finally:
                evaluation.cancel()
                await asyncio.gather(evaluation, return_exceptions=True)
            if asyncio.current_task().cancelling():
                raise
            return {"error": "timeout"}
        except PlaywrightError:
            return {"error": "network"}

    @staticmethod
    def _retrieve_exception(task):
        if not task.cancelled():
            task.exception()

    async def close(self):
        async with self._condition:
            if self._closed:
                return
            self._closed = True
            self._condition.notify_all()
        tasks = set(self._owners)
        tasks.discard(asyncio.current_task())
        tasks.update(task for task in (self._bootstrap, self._recovery) if task is not None)
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        if self.page is not None:
            with suppress(PlaywrightError):
                await self.page.close()
