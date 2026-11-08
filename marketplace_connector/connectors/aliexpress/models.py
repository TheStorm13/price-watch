"""Adapter-private responses and validated SKU data."""
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any
from ...domain.models import MarketplaceCard
from .identity import AliExpressRef
from ...domain.models import Availability


@dataclass(frozen=True)
class AliExpressResponse:
    raw_text: str
    card: MarketplaceCard


@dataclass(frozen=True)
class AliExpressProductData:
    ref: AliExpressRef
    data: dict[str, Any]
    selected: dict[str, Any] | None
    price: Decimal | None
    availability: Availability
    collected_at: datetime
