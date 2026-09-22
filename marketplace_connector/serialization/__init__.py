"""Stable serialization boundary for the public product contract."""

from .product_json import snapshot_to_dict, snapshot_to_json

__all__ = ["snapshot_to_dict", "snapshot_to_json"]
