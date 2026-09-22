"""Marketplace-independent product connector API."""

from .application.product_service import ConnectorRegistry, ProductService
from .domain.errors import (
    AuthenticationRequired,
    ChallengeRequired,
    ConnectorError,
    InvalidProductId,
    MarketplaceSchemaChanged,
    MarketplaceUnavailable,
    ProductNotFound,
    RateLimited,
    UnknownMarketplace,
)
from .domain.models import (
    Attribute,
    Availability,
    ProductRef,
    ProductSnapshot,
    ProductVariant,
    Rating,
    Seller,
)
from .serialization.product_json import snapshot_to_dict, snapshot_to_json

__all__ = [
    "Attribute",
    "AuthenticationRequired",
    "Availability",
    "ChallengeRequired",
    "ConnectorError",
    "ConnectorRegistry",
    "InvalidProductId",
    "MarketplaceSchemaChanged",
    "MarketplaceUnavailable",
    "ProductNotFound",
    "ProductRef",
    "ProductService",
    "ProductSnapshot",
    "ProductVariant",
    "RateLimited",
    "Rating",
    "Seller",
    "UnknownMarketplace",
    "snapshot_to_dict",
    "snapshot_to_json",
]
