"""User-interaction port used by asynchronous connectors."""

import asyncio
from typing import Callable, Protocol

from ..domain.errors import ChallengeRequired


class ChallengeHandler(Protocol):
    async def handle_async(self, marketplace: str, message: str) -> None:
        ...


class RejectChallengeHandler:
    async def handle_async(self, marketplace: str, message: str) -> None:
        raise ChallengeRequired(f"{marketplace}: {message}")


class CallableChallengeHandler:
    def __init__(self, callback: Callable[[str], object]):
        self._callback = callback

    async def handle_async(self, marketplace: str, message: str) -> None:
        await asyncio.to_thread(self._callback, message)
