"""Read all inputs under one consistent storage snapshot."""
from typing import Protocol
from ..application.catalog_models import CatalogInputs


class CatalogReader(Protocol):
    async def read_catalog(self) -> CatalogInputs: ...
