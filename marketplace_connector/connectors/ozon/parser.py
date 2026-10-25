"""Decode Ozon structures without constructing application entities."""
import json
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, Mapping, Optional, Union
from urllib.parse import parse_qs, urlparse
from ...domain.errors import MarketplaceSchemaChanged, ProductNotFound
from .models import OzonProductData, OzonPrice

JsonObject = Dict[str, Any]

class OzonProductParser:
    @classmethod
    def parse(cls, raw, expected_external_id=None, collected_at=None):
        payload = cls._decode_document(raw)
        widgets = payload.get("widgetStates")
        if not isinstance(widgets, dict):
            raise MarketplaceSchemaChanged("В ответе Ozon отсутствует widgetStates")
        if cls._is_unavailable_search(payload, widgets, expected_external_id):
            raise ProductNotFound(f"Ozon перенаправил товар {expected_external_id} на поиск")
        price = cls._widget(widgets, "webPrice-")
        return OzonProductData(
            requested_id=expected_external_id,
            received_at=collected_at or datetime.now(timezone.utc),
            analytics_sku=cls._dig(payload, "pageInfo", "analyticsInfo", "sku"),
            canonical_url=cls._canonical_url(payload),
            heading=cls._widget(widgets, "webProductHeading-"),
            price=OzonPrice(price.get("cardPrice"), "isAvailable" in price, price.get("isAvailable")),
            sticky=cls._widget(widgets, "webStickyProducts-"),
            seller=cls._widget(widgets, "webCurrentSeller-"),
            review=cls._widget(widgets, "webReviewProductScore-"),
            characteristics=cls._widget(widgets, "webShortCharacteristics-"),
            aspects=cls._widget(widgets, "webAspects-"),
            gallery=cls._widget(widgets, "webGallery-"),
            seo_product=cls._ld_product(payload),
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
            payload, _ = json.JSONDecoder(parse_float=Decimal).raw_decode(raw[start:])
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
                    decoded = json.loads(value, parse_float=Decimal)
                except json.JSONDecodeError:
                    continue
                if isinstance(decoded, dict):
                    return decoded
        return {}

    @staticmethod
    def _is_unavailable_search(
        payload: JsonObject, widget_states: JsonObject, expected_external_id: Optional[str]
    ) -> bool:
        if not expected_external_id or any(
            key.startswith(("webProductHeading-", "webPrice-"))
            for key in widget_states
        ):
            return False
        page_info = payload.get("pageInfo")
        if not isinstance(page_info, dict) or page_info.get("pageType") != "search":
            return False
        page_url = page_info.get("url")
        if not isinstance(page_url, str):
            return False
        parsed = urlparse(page_url)
        return (
            parsed.netloc in ("", "ozon.ru", "www.ozon.ru")
            and parsed.scheme in ("", "https")
            and parsed.path.rstrip("/") == "/search"
            and parse_qs(parsed.query).get("product_id") == [expected_external_id]
        )

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
                decoded = json.loads(value, parse_float=Decimal)
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

    @staticmethod
    def _dig(value, *path):
        for key in path:
            if not isinstance(value, dict):
                return None
            value = value.get(key)
        return value
