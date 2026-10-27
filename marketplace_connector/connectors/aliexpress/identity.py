"""Exact AliExpress.ru product/SKU identity; IDs always remain strings."""
from dataclasses import dataclass
import re
from urllib.parse import parse_qs, urlsplit

from ...domain.errors import InvalidProductId

_DIGITS = re.compile(r"[0-9]+\Z")


@dataclass(frozen=True)
class AliExpressRef:
    product_id: str
    sku_id: str

    @property
    def external_id(self) -> str:
        return f"{self.product_id}:{self.sku_id}"

    @property
    def url(self) -> str:
        return f"https://aliexpress.ru/item/{self.product_id}.html?sku_id={self.sku_id}"

    @classmethod
    def parse(cls, value: str) -> "AliExpressRef":
        if not isinstance(value, str):
            raise InvalidProductId("AliExpress ID должен быть строкой productId:skuId")
        parts = value.strip().split(":")
        if len(parts) == 1:
            raise InvalidProductId("Не указан SKU")
        if len(parts) != 2 or any(not _DIGITS.fullmatch(p) for p in parts):
            raise InvalidProductId("AliExpress ID должен иметь формат productId:skuId из цифр ASCII")
        return cls(*parts)

    @classmethod
    def from_url(cls, value: str) -> "AliExpressRef":
        location = urlsplit(value)
        match = re.fullmatch(r"/item/([0-9]+)\.html", location.path)
        if (location.scheme != "https" or location.netloc != "aliexpress.ru"
                or not match or location.fragment):
            raise InvalidProductId("Используйте полную ссылку https://aliexpress.ru/item/…html?sku_id=…")
        skus = parse_qs(location.query, keep_blank_values=True).get("sku_id", [])
        if len(skus) != 1 or not _DIGITS.fullmatch(skus[0]):
            raise InvalidProductId("Ссылка должна содержать единственный числовой sku_id")
        return cls(match[1], skus[0])
