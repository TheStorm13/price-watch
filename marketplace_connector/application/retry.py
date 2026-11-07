"""One application-level retry, outside each connector's transport attempts."""
from asyncio import sleep
import logging
import math
from collections.abc import Awaitable, Callable
from typing import TypeVar

from ..domain.errors import ProductNotFound, RateLimited

logger = logging.getLogger(__name__)
T = TypeVar('T')


async def fetch_with_retry(fetch: Callable[[], Awaitable[T]]) -> T:
    try:
        return await fetch()
    except ProductNotFound:
        raise  # Confirmed absence is a domain result, not a failed request.
    except Exception as first:
        delay = 1.0
        if isinstance(first, RateLimited) and first.retry_after is not None:
            wait = first.retry_after
            if not math.isnan(wait):
                delay = max(delay, wait)
        logger.warning('Получение товара не удалось; повтор через %s с', delay, exc_info=True)
        await sleep(delay)
        try:
            return await fetch()
        except Exception as final:
            if final is first:
                raise
            raise final from first
