"""Read-only thumbnail contract for HTTP consumers."""
from typing import Protocol


class ThumbnailReader(Protocol):
    async def get(self, url: str) -> bytes: ...
