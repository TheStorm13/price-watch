"""Public connector port."""

from typing import Protocol, runtime_checkable

from ..domain.models import ProductSnapshot


@runtime_checkable
class MarketplaceConnector(Protocol):
    marketplace: str

    def get_product(self, external_id: str) -> ProductSnapshot:
        """Return a normalized product snapshot."""
        ...
