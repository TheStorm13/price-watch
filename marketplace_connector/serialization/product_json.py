"""Serialize product snapshots without leaking Python-specific types."""

import json
from typing import Any, Dict, Optional

from ..domain.models import (
    Attribute,
    ProductRef,
    MarketplaceCard,
    ProductVariant,
    Rating,
    Seller,
)


def _ref(value: ProductRef) -> Dict[str, str]:
    return {"marketplace": value.marketplace, "external_id": value.external_id}


def _rating(value: Optional[Rating]) -> Optional[Dict[str, Any]]:
    if value is None:
        return None
    return {
        "value": format(value.value, "f"),
        "scale": format(value.scale, "f"),
        "reviews_count": value.reviews_count,
    }


def _seller(value: Optional[Seller]) -> Optional[Dict[str, Any]]:
    if value is None:
        return None
    return {
        "external_id": value.external_id,
        "name": value.name,
        "rating": _rating(value.rating),
    }


def _attribute(value: Attribute) -> Dict[str, Any]:
    return {"name": value.name, "values": list(value.values), "group": value.group}


def _variant(value: ProductVariant) -> Dict[str, Any]:
    return {
        "ref": _ref(value.ref),
        "title": value.title,
        "url": value.url,
        "availability": value.availability.value,
        "selected": value.selected,
        "options": dict(value.options),
    }


def card_to_dict(snapshot: MarketplaceCard) -> Dict[str, Any]:
    return {
        "schema_version": "2.0",
        "ref": _ref(snapshot.ref),
        "title": snapshot.title,
        "url": snapshot.url,
        "availability": snapshot.availability.value,
        "price": format(snapshot.price, ".2f") if snapshot.price is not None else None,
        "image_url": snapshot.image_url,
        "seller": _seller(snapshot.seller),
        "rating": _rating(snapshot.rating),
        "attributes": [_attribute(item) for item in snapshot.attributes],
        "description": snapshot.description,
        "variants": [_variant(variant) for variant in snapshot.variants],
        "collected_at": snapshot.collected_at.isoformat(),
        "extensions": dict(snapshot.extensions),
    }


def card_to_json(snapshot: MarketplaceCard, indent: Optional[int] = 2) -> str:
    return json.dumps(card_to_dict(snapshot), ensure_ascii=False, indent=indent)
