"""Read-only prepared image contract for HTTP consumers."""
from typing import Literal, Protocol

ThumbnailProfile = Literal["list", "tile", "detail"]
THUMBNAIL_BOXES: dict[ThumbnailProfile, tuple[int, int]] = {
    "list": (68, 68), "tile": (278, 190), "detail": (158, 158),
}
MAX_THUMBNAIL_SIZE = 2224  # Largest profile at the maximum supported DPR (8).


class ThumbnailReader(Protocol):
    async def get(self, url: str, size: tuple[int, int]) -> bytes: ...
