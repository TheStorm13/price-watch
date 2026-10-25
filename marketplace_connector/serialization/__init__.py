"""Stable serialization boundary for the public product contract."""

from .product_json import card_to_dict, card_to_json

__all__ = ["card_to_dict", "card_to_json"]
