"""Map Ozon composer JSON to the marketplace-independent contract."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Iterable, Mapping, Optional, Union
from urllib.parse import urljoin, urlparse

from ...domain.errors import MarketplaceSchemaChanged
from ...domain.models import (
    Attribute,
    Availability,
    ProductRef,
    ProductSnapshot,
    ProductVariant,
    Rating,
    Seller,
)


JsonObject = Dict[str, Any]


class OzonMapper:
    marketplace = "ozon"
    OZON_URL = "https://www.ozon.ru"

    @classmethod
    def to_snapshot(
        cls,
        raw: Union[str, Mapping[str, Any]],
        expected_external_id: Optional[str] = None,
        collected_at: Optional[datetime] = None,
    ) -> ProductSnapshot:
        payload = cls._decode_document(raw)
        widget_states = payload.get("widgetStates")
        if not isinstance(widget_states, dict):
            raise MarketplaceSchemaChanged("В ответе Ozon отсутствует widgetStates")

        heading = cls._widget(widget_states, "webProductHeading-")
        price = cls._widget(widget_states, "webPrice-")
        sticky = cls._widget(widget_states, "webStickyProducts-")
        seller_widget = cls._widget(widget_states, "webCurrentSeller-")
        review = cls._widget(widget_states, "webReviewProductScore-")
        characteristics = cls._widget(widget_states, "webShortCharacteristics-")
        aspects = cls._widget(widget_states, "webAspects-")
        gallery = cls._widget(widget_states, "webGallery-")
        ld_product = cls._ld_product(payload)

        external_id = str(
            cls._first(
                cls._dig(payload, "pageInfo", "analyticsInfo", "sku"),
                sticky.get("sku"),
                ld_product.get("sku"),
                expected_external_id,
            )
            or ""
        )
        title = str(
            cls._first(
                heading.get("title"), sticky.get("name"), ld_product.get("name")
            )
            or ""
        )
        if not external_id or not title:
            raise MarketplaceSchemaChanged(
                "Ответ Ozon не содержит обязательные идентификатор и название товара"
            )
        if expected_external_id and external_id != expected_external_id:
            raise MarketplaceSchemaChanged(
                f"Ozon вернул товар {external_id} вместо {expected_external_id}"
            )

        seller_link = str(cls._dig(sticky, "seller", "link") or "")
        seller_name = str(cls._dig(sticky, "seller", "name") or "")
        seller_rating_value = cls._decimal(
            cls._dig(seller_widget, "rating", "title", "text")
        )

        rating_value = cls._decimal(
            cls._first(
                review.get("totalScore"),
                cls._dig(ld_product, "aggregateRating", "ratingValue"),
            )
        )
        reviews_count = cls._integer(
            cls._first(
                review.get("reviewsCount"),
                cls._dig(ld_product, "aggregateRating", "reviewCount"),
            )
        ) or 0
        return ProductSnapshot(
            ref=ProductRef(cls.marketplace, external_id),
            title=title,
            url=cls._canonical_url(payload)
            or str(cls._dig(ld_product, "offers", "url") or ""),
            availability=cls._availability(price, ld_product),
            price=cls._price_number(price.get("cardPrice")),
            image_url=cls._image_url(gallery, ld_product, aspects, external_id),
            seller=(
                Seller(
                    external_id=cls._seller_id(seller_link, seller_widget) or None,
                    name=seller_name,
                    rating=(Rating(seller_rating_value) if seller_rating_value is not None else None),
                )
                if seller_name or seller_link
                else None
            ),
            rating=(
                Rating(rating_value, reviews_count=reviews_count)
                if rating_value is not None
                else None
            ),
            attributes=tuple(cls._characteristics(characteristics)),
            description=str(ld_product.get("description") or ""),
            variants=tuple(cls._variants(aspects, external_id)),
            collected_at=collected_at or datetime.now(timezone.utc),
        )

    @staticmethod
    def _decode_document(raw: Union[str, Mapping[str, Any]]) -> JsonObject:
        if isinstance(raw, Mapping):
            return dict(raw)
        if not isinstance(raw, str):
            raise TypeError("Ожидалась JSON-строка или словарь")
        start = raw.find("{")
        if start < 0:
            raise MarketplaceSchemaChanged("JSON-объект не найден")
        try:
            payload, _ = json.JSONDecoder().raw_decode(raw[start:])
        except json.JSONDecodeError as exc:
            raise MarketplaceSchemaChanged(f"Некорректный JSON: {exc}") from exc
        if not isinstance(payload, dict):
            raise MarketplaceSchemaChanged("Корневое значение JSON должно быть объектом")
        return payload

    @staticmethod
    def _widget(widget_states: JsonObject, prefix: str) -> JsonObject:
        for key, value in widget_states.items():
            if not key.startswith(prefix):
                continue
            if isinstance(value, dict):
                return value
            if isinstance(value, str):
                try:
                    decoded = json.loads(value)
                except json.JSONDecodeError:
                    continue
                if isinstance(decoded, dict):
                    return decoded
        return {}

    @classmethod
    def _ld_product(cls, payload: JsonObject) -> JsonObject:
        scripts = cls._dig(payload, "seo", "script") or []
        for script in scripts:
            if not isinstance(script, dict) or script.get("type") != "application/ld+json":
                continue
            value = script.get("innerHTML")
            if not isinstance(value, str):
                continue
            try:
                decoded = json.loads(value)
            except json.JSONDecodeError:
                continue
            if isinstance(decoded, dict) and decoded.get("@type") == "Product":
                return decoded
        return {}

    @classmethod
    def _canonical_url(cls, payload: JsonObject) -> str:
        for link in cls._dig(payload, "seo", "link") or []:
            if isinstance(link, dict) and link.get("rel") == "canonical":
                return str(link.get("href") or "")
        return ""

    @classmethod
    def _image_url(cls, gallery: JsonObject, ld_product: JsonObject,
                   aspects: JsonObject, external_id: str) -> Optional[str]:
        """Use the first product photo, with structured data and selected variant as fallbacks."""
        def valid_url(value: Any) -> Optional[str]:
            if not isinstance(value, str):
                return None
            value = value.strip()
            if not value:
                return None
            url = urljoin(cls.OZON_URL, value)
            parsed = urlparse(url)
            return url if parsed.scheme == "https" and parsed.hostname else None

        for key in ("images", "gallery", "items"):
            images = gallery.get(key)
            if isinstance(images, list):
                for image in images:
                    value = image if isinstance(image, str) else (
                        image.get("src") or image.get("url") or image.get("image")
                        if isinstance(image, dict) else None
                    )
                    if isinstance(value, dict):
                        value = value.get("url") or value.get("src")
                    result = valid_url(value)
                    if result:
                        return result

        image = ld_product.get("image")
        candidates = image if isinstance(image, list) else [image]
        for candidate in candidates:
            if isinstance(candidate, dict):
                candidate = candidate.get("url") or candidate.get("contentUrl")
            result = valid_url(candidate)
            if result:
                return result

        for item in cls._walk_dicts(aspects):
            if str(item.get("sku") or "") == external_id:
                result = valid_url(cls._dig(item, "data", "coverImage"))
                if result:
                    return result
        return None

    @classmethod
    def _seller_id(cls, seller_link: str, seller_widget: JsonObject) -> str:
        match = re.search(r"(?:-|/)(\d+)/?$", seller_link)
        if match:
            return match.group(1)
        value = cls._dig(
            seller_widget,
            "header", "badge", "subscribed", "common", "action", "params", "sellerId",
        )
        return str(value or "")

    @classmethod
    def _availability(cls, price: JsonObject, ld_product: JsonObject) -> Availability:
        if "isAvailable" in price:
            return Availability.IN_STOCK if cls._as_bool(price["isAvailable"]) else Availability.OUT_OF_STOCK
        value = cls._dig(ld_product, "offers", "availability")
        if value is None or value == "":
            return Availability.UNKNOWN
        return Availability.IN_STOCK if str(value).endswith("/InStock") else Availability.OUT_OF_STOCK

    @staticmethod
    def _as_bool(value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return value != 0
        return str(value).strip().lower() in {
            "true", "1", "yes", "in_stock", "instock", "available", "instock",
        }

    @classmethod
    def _characteristics(cls, widget: JsonObject) -> Iterable[Attribute]:
        for item in widget.get("characteristics", []):
            if not isinstance(item, dict):
                continue
            title_parts = cls._dig(item, "title", "textRs") or []
            title = "".join(
                str(part.get("content") or "")
                for part in title_parts
                if isinstance(part, dict)
            ).strip()
            values = tuple(
                str(value.get("text") or "").strip()
                for value in item.get("values", [])
                if isinstance(value, dict) and value.get("text")
            )
            if title and values:
                yield Attribute(name=title, values=values)

    @classmethod
    def _variants(
        cls, aspects: JsonObject, current_id: str
    ) -> Iterable[ProductVariant]:
        seen = set()
        for item in cls._walk_dicts(aspects):
            external_id = str(item.get("sku") or "")
            if not external_id or external_id in seen or not item.get("link"):
                continue
            data = item.get("data") if isinstance(item.get("data"), dict) else {}
            seen.add(external_id)
            option = str(data.get("searchableText") or "")
            yield ProductVariant(
                ref=ProductRef(cls.marketplace, external_id),
                title=str(data.get("title") or ""),
                url=urljoin(cls.OZON_URL, str(item.get("link") or "")),
                availability=(
                    Availability.IN_STOCK
                    if cls._as_bool(item.get("availability"))
                    else Availability.OUT_OF_STOCK
                ),
                selected=external_id == current_id,
                options={"option": option} if option else {},
            )

    @staticmethod
    def _walk_dicts(value: Any) -> Iterable[JsonObject]:
        if isinstance(value, dict):
            yield value
            for nested in value.values():
                yield from OzonMapper._walk_dicts(nested)
        elif isinstance(value, list):
            for nested in value:
                yield from OzonMapper._walk_dicts(nested)

    @staticmethod
    def _dig(value: Any, *path: str) -> Any:
        current = value
        for key in path:
            if not isinstance(current, dict):
                return None
            current = current.get(key)
        return current

    @staticmethod
    def _first(*values: Any) -> Any:
        return next((value for value in values if value is not None and value != ""), None)

    @staticmethod
    def _integer(value: Any) -> Optional[int]:
        number = OzonMapper._decimal(value)
        return int(number) if number is not None else None

    @staticmethod
    def _price_number(value: Any):
        number = OzonMapper._decimal(value)
        if number is None:
            return None
        if number == number.to_integral_value():
            return int(number)
        return float(number)

    @staticmethod
    def _decimal(value: Any) -> Optional[Decimal]:
        if value is None or value == "" or isinstance(value, bool):
            return None
        if isinstance(value, Decimal):
            return value
        if isinstance(value, (int, float)):
            return Decimal(str(value))
        text = str(value).strip().replace("\u00a0", "").replace("\u2009", "").replace(" ", "")
        match = re.search(r"-?\d+(?:[.,]\d+)?", text)
        if not match:
            return None
        try:
            return Decimal(match.group(0).replace(",", "."))
        except InvalidOperation:
            return None
