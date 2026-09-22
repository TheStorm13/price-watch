"""Backward-compatible adapter from the common contract to legacy entities."""

from typing import Any, Dict, Union

from marketplace_connector.connectors.ozon.mapper import OzonMapper
from marketplace_connector.domain.models import Availability

from .models import ProductCard, ProductVariant, Seller


JsonObject = Dict[str, Any]


class ProductCardNormalizer:
    """Compatibility facade; new code should use ``OzonMapper``."""

    @classmethod
    def from_raw(cls, raw: Union[str, JsonObject]) -> ProductCard:
        snapshot = OzonMapper.to_snapshot(raw)

        characteristics = {
            item.name: item.values[0] if len(item.values) == 1 else list(item.values)
            for item in snapshot.attributes
        }
        variants = [
            ProductVariant(
                article=item.ref.external_id,
                name=item.title,
                option=item.options.get("option", ""),
                url=item.url,
                available=item.availability == Availability.IN_STOCK,
                selected=item.selected,
            )
            for item in snapshot.variants
        ]
        seller = snapshot.seller
        return ProductCard(
            article=snapshot.ref.external_id,
            name=snapshot.title,
            available=snapshot.availability == Availability.IN_STOCK,
            card_price=int(snapshot.price) if snapshot.price is not None else None,
            url=snapshot.url,
            rating=float(snapshot.rating.value) if snapshot.rating else None,
            reviews_count=snapshot.rating.reviews_count if snapshot.rating else 0,
            seller=Seller(
                id=(seller.external_id or "") if seller else "",
                name=seller.name if seller else "",
                rating=float(seller.rating.value) if seller and seller.rating else None,
            ),
            characteristics=characteristics,
            description=snapshot.description,
            variants=variants,
        )
