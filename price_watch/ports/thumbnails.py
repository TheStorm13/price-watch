"""Read-only prepared image contract for HTTP consumers."""
from typing import Literal, Protocol

ThumbnailProfile = Literal["list", "tile", "detail"]
THUMBNAIL_BOXES: dict[ThumbnailProfile, tuple[int, int]] = {
    "list": (51, 68), "tile": (276, 368), "detail": (384, 512),
}
MAX_THUMBNAIL_SIZE = 4096  # Largest profile at the maximum supported DPR (8).


class ThumbnailReader(Protocol):
    async def get(self, url: str, size: tuple[int, int]) -> bytes: ...
