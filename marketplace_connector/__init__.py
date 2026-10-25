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
    MarketplaceCard,
    ProductVariant,
    Rating,
    Seller,
)
from .serialization.product_json import card_to_dict, card_to_json

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
    "MarketplaceCard",
    "ProductVariant",
    "RateLimited",
    "Rating",
    "Seller",
    "UnknownMarketplace",
    "card_to_dict",
    "card_to_json",
]
