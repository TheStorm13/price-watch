"""Per-transport HTTP admission. Recovery/cooldown are coordinated by the caller."""
import asyncio

from .collection_policy import MAX_IN_FLIGHT_REQUESTS


class RequestPool:
    def __init__(self, max_in_flight_requests=MAX_IN_FLIGHT_REQUESTS):
        if isinstance(max_in_flight_requests, bool) or not isinstance(max_in_flight_requests, int) or max_in_flight_requests < 1:
            raise ValueError('max_in_flight_requests должен быть положительным целым')
        self.max_in_flight_requests = max_in_flight_requests
        self._slots = asyncio.BoundedSemaphore(max_in_flight_requests)
        self.in_flight = 0
        self.pending = 0
        self.peak = 0

    async def acquire(self):
        self.pending += 1
        try:
            await self._slots.acquire()
        finally:
            self.pending -= 1
        self.in_flight += 1
        self.peak = max(self.peak, self.in_flight)

    def release(self):
        self._slots.release()
        self.in_flight -= 1
