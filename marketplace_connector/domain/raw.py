"""Internal representation of a marketplace response."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping


@dataclass(frozen=True)
class RawMarketplaceResponse:
    marketplace: str
    external_id: str
    payload: Mapping[str, Any]
    raw_text: str
    received_at: datetime
