"""Stable domain contract shared by all marketplace connectors."""

from .models import (
    Attribute,
    Availability,
    ProductRef,
    ProductSnapshot,
    ProductVariant,
    Rating,
    Seller,
)

__all__ = [
    "Attribute",
    "Availability",
    "ProductRef",
    "ProductSnapshot",
    "ProductVariant",
    "Rating",
    "Seller",
]
