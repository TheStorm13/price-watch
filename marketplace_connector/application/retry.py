"""One application-level retry, outside each connector's transport attempts."""
from asyncio import sleep
import logging
import math
from collections.abc import Awaitable, Callable
from typing import TypeVar

from ..domain.errors import ProductNotFound, RateLimited, UnsafeBrowserTeardown

logger = logging.getLogger(__name__)
T = TypeVar('T')
MAX_RETRY_WAIT = 30.0


async def fetch_with_retry(fetch: Callable[[], Awaitable[T]]) -> T:
    try:
        return await fetch()
    except (ProductNotFound, UnsafeBrowserTeardown):
        raise  # Neither a confirmed absence nor unsafe teardown allows another fetch.
    except Exception as first:
        delay = 1.0
        if isinstance(first, RateLimited):
            wait = first.retry_after
            if not first.retry_allowed or (wait is not None and wait > MAX_RETRY_WAIT):
                raise
            if wait is not None and not math.isnan(wait):
                delay = max(delay, wait)
        logger.warning('Получение товара не удалось; повтор через %s с', delay, exc_info=True)
        await sleep(delay)
        try:
            return await fetch()
        except Exception as final:
            if final is first:
                raise
            raise final from first
