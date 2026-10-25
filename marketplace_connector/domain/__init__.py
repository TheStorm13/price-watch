"""Stable domain contract shared by all marketplace connectors."""

from .models import (
    Attribute,
    Availability,
    ProductRef,
    MarketplaceCard,
    ProductVariant,
    Rating,
    Seller,
)

__all__ = [
    "Attribute",
    "Availability",
    "ProductRef",
    "MarketplaceCard",
    "ProductVariant",
    "Rating",
    "Seller",
]
