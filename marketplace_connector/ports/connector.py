"""Public connector port."""

from contextlib import AbstractAsyncContextManager
from typing import Protocol, runtime_checkable

from ..domain.models import ProductSnapshot


@runtime_checkable
class MarketplaceConnector(Protocol):
    marketplace: str

    def collection_session(self) -> AbstractAsyncContextManager[None]:
        """Share connector resources across one collection run."""
        ...

    async def get_product(self, external_id: str) -> ProductSnapshot:
        """Return a normalized product snapshot."""
        ...
