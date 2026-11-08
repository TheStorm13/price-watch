"""Ozon transport and decoded widgets; these types never escape the adapter."""
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any
from ...domain.models import MarketplaceCard


@dataclass(frozen=True)
class OzonResponse:
    raw_text: str
    card: MarketplaceCard


@dataclass(frozen=True)
class OzonPrice:
    card_price: Decimal | int | str | None
    availability_specified: bool
    is_available: Any


@dataclass(frozen=True)
class OzonProductData:
    requested_id: str | None
    received_at: datetime
    analytics_sku: Any
    canonical_url: str
    heading: dict[str, Any]
    price: OzonPrice
    sticky: dict[str, Any]
    seller: dict[str, Any]
    review: dict[str, Any]
    characteristics: dict[str, Any]
    aspects: dict[str, Any]
    gallery: dict[str, Any]
    seo_product: dict[str, Any]
    discovery_error: str | None = None
