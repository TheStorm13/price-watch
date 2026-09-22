"""User-interaction port used by connectors requiring manual verification."""

from typing import Callable, Protocol

from ..domain.errors import ChallengeRequired


class ChallengeHandler(Protocol):
    def handle(self, marketplace: str, message: str) -> None:
        ...


class RejectChallengeHandler:
    def handle(self, marketplace: str, message: str) -> None:
        raise ChallengeRequired(f"{marketplace}: {message}")


class CallableChallengeHandler:
    def __init__(self, callback: Callable[[str], object]):
        self._callback = callback

    def handle(self, marketplace: str, message: str) -> None:
        self._callback(message)
