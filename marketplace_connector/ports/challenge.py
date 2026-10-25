"""User-interaction port used by asynchronous connectors."""

from typing import Protocol

from ..domain.errors import ChallengeRequired


class ChallengeHandler(Protocol):
    async def handle_async(self, marketplace: str, message: str) -> None:
        ...


class RejectChallengeHandler:
    async def handle_async(self, marketplace: str, message: str) -> None:
        raise ChallengeRequired(f"{marketplace}: {message}")
