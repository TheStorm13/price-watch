"""AliExpress.ru product identity with an optional exact SKU; IDs remain strings."""
from dataclasses import dataclass
import re
from urllib.parse import parse_qs, urlsplit

from ...domain.errors import InvalidProductId

_DIGITS = re.compile(r"[0-9]+\Z")


@dataclass(frozen=True)
class AliExpressRef:
    product_id: str
    sku_id: str | None = None

    def __post_init__(self):
        for value in (self.product_id,) + ((self.sku_id,) if self.sku_id is not None else ()):
            if not isinstance(value, str) or not _DIGITS.fullmatch(value):
                raise InvalidProductId("AliExpress ID должен состоять из цифр ASCII")

    @property
    def external_id(self) -> str:
        return f"{self.product_id}:{self.sku_id}" if self.sku_id is not None else self.product_id

    @property
    def url(self) -> str:
        return f"https://aliexpress.ru/item/{self.product_id}.html" + (f"?sku_id={self.sku_id}" if self.sku_id is not None else "")

    @classmethod
    def parse(cls, value: str) -> "AliExpressRef":
        if not isinstance(value, str):
            raise InvalidProductId("AliExpress ID должен быть строкой productId или productId:skuId")
        parts = value.strip().split(":")
        if len(parts) not in (1, 2) or any(not _DIGITS.fullmatch(p) for p in parts):
            raise InvalidProductId("AliExpress ID должен иметь формат productId или productId:skuId из цифр ASCII")
        return cls(*parts)

    @classmethod
    def from_url(cls, value: str) -> "AliExpressRef":
        location = urlsplit(value)
        match = re.fullmatch(r"/item/([0-9]+)\.html", location.path)
        if (location.scheme != "https" or location.netloc != "aliexpress.ru"
                or not match or location.fragment):
            raise InvalidProductId("Используйте полную ссылку https://aliexpress.ru/item/…html?sku_id=…")
        skus = parse_qs(location.query, keep_blank_values=True).get("sku_id", [])
        if len(skus) > 1 or (skus and not _DIGITS.fullmatch(skus[0])):
            raise InvalidProductId("Ссылка должна содержать единственный числовой sku_id")
        return cls(match[1], skus[0] if skus else None)
