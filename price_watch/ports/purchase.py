from typing import Protocol
from ..domain.purchase import PurchaseSettings


class PurchaseSettingsStore(Protocol):
    async def get_settings(self) -> PurchaseSettings: ...
    async def update_settings(self, changes: dict) -> PurchaseSettings: ...
